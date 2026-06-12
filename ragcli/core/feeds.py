"""RSS/Atom feed fetcher — converts feed articles into documents."""

import hashlib
import ipaddress
import json
import re
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import feedparser
from pydantic import BaseModel, Field

from ragcli.core.errors import RagError


class FeedConfig(BaseModel):
    """A registered feed for a collection."""

    url: str
    added: str = ""
    last_fetched: Optional[str] = None
    article_count: int = 0


class FeedArticle(BaseModel):
    """A single article fetched from a feed."""

    title: str
    filename: str
    is_new: bool
    link: str = ""
    published: str = ""


class FeedFetchResult(BaseModel):
    """Result of fetching one feed."""

    url: str
    articles: list[FeedArticle] = Field(default_factory=list)
    new_count: int = 0
    total: int = 0
    error: Optional[str] = None


def validate_feed_url(url: str) -> None:
    """Reject URLs that aren't plain public http(s) endpoints.

    Blocks non-http schemes and private/loopback/link-local/metadata addresses
    so the feed fetcher can't be used for SSRF against internal services.
    Raises RagError with a human-readable message.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise RagError(f"Feed URLs must be http(s), got: {parsed.scheme or 'no scheme'}")
    hostname = parsed.hostname
    if not hostname:
        raise RagError("Feed URL has no hostname.")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise RagError(f"Could not resolve feed host '{hostname}': {e}") from e

    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            raise RagError(
                f"Feed host '{hostname}' resolves to a private or local address ({addr}) — "
                "refusing to fetch it."
            )


class FeedManager:
    """Manages RSS/Atom feeds for a collection."""

    def __init__(self, rag_dir: Path | None = None) -> None:
        self.rag_dir = rag_dir or Path.cwd() / ".rag"
        self.feeds_path = self.rag_dir / "feeds.json"

    def load(self) -> dict[str, list[FeedConfig]]:
        """Load feed config: {collection_name: [FeedConfig, ...]}."""
        if not self.feeds_path.exists():
            return {}
        try:
            raw = json.loads(self.feeds_path.read_text(encoding="utf-8"))
            return {k: [FeedConfig(**f) for f in v] for k, v in raw.items()}
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise RagError(
                f"Could not read {self.feeds_path}: {e}\n"
                "The file may be corrupted — delete it and re-add your feeds."
            ) from e

    def save(self, feeds: dict[str, list[FeedConfig]]) -> None:
        self.rag_dir.mkdir(parents=True, exist_ok=True)
        data = {k: [f.model_dump() for f in v] for k, v in feeds.items()}
        self.feeds_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def add_feed(self, collection: str, url: str) -> FeedConfig:
        """Register a feed URL for a collection. Validates the URL first."""
        validate_feed_url(url)
        feeds = self.load()
        if collection not in feeds:
            feeds[collection] = []

        for f in feeds[collection]:
            if f.url == url:
                return f

        entry = FeedConfig(url=url, added=datetime.now().isoformat())
        feeds[collection].append(entry)
        self.save(feeds)
        return entry

    def remove_feed(self, collection: str, url: str) -> bool:
        feeds = self.load()
        if collection not in feeds:
            return False
        before = len(feeds[collection])
        feeds[collection] = [f for f in feeds[collection] if f.url != url]
        self.save(feeds)
        return len(feeds[collection]) < before

    def get_feeds(self, collection: str) -> list[FeedConfig]:
        return self.load().get(collection, [])

    def fetch_feed(
        self,
        url: str,
        docs_dir: Path,
        max_articles: int = 50,
    ) -> list[FeedArticle]:
        """
        Fetch an RSS/Atom feed and save articles as markdown files.
        """
        validate_feed_url(url)

        import httpx

        try:
            response = httpx.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RagError(f"Could not fetch feed {url}: {e}") from e

        feed = feedparser.parse(response.text)
        if feed.bozo and not feed.entries:
            raise RagError(f"Failed to parse feed {url}: {feed.bozo_exception}")

        results: list[FeedArticle] = []
        docs_dir.mkdir(parents=True, exist_ok=True)

        for entry in feed.entries[:max_articles]:
            title = entry.get("title", "Untitled")
            link = entry.get("link", "")
            published = entry.get("published", entry.get("updated", ""))
            author = entry.get("author", "")

            # Get content — try content, then summary, then description
            content = ""
            if hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "description"):
                content = entry.description

            content = _strip_html(content)

            if not content.strip():
                continue

            # Generate a stable filename from the title
            safe_title = re.sub(r"[^a-zA-Z0-9\s-]", "", title)[:60].strip()
            safe_title = re.sub(r"\s+", "-", safe_title)
            # Add a short hash to avoid collisions
            url_hash = hashlib.md5(link.encode("utf-8")).hexdigest()[:6]
            filename = f"{safe_title}-{url_hash}.md"
            filepath = docs_dir / filename

            is_new = not filepath.exists()

            # Build markdown document
            md = f"# {title}\n\n"
            if author:
                md += f"**Author:** {author}  \n"
            if published:
                md += f"**Published:** {published}  \n"
            if link:
                md += f"**Source:** {link}  \n"
            md += f"\n---\n\n{content}\n"

            filepath.write_text(md, encoding="utf-8")

            results.append(FeedArticle(
                title=title,
                filename=filename,
                is_new=is_new,
                link=link,
                published=published,
            ))

        return results

    def fetch_all_feeds(
        self,
        collection: str,
        docs_dir: Path,
        max_articles: int = 50,
    ) -> list[FeedFetchResult]:
        """Fetch all feeds for a collection. Returns one result per feed."""
        feeds = self.load()
        collection_feeds = feeds.get(collection, [])
        all_results: list[FeedFetchResult] = []

        for feed_entry in collection_feeds:
            url = feed_entry.url
            try:
                articles = self.fetch_feed(url, docs_dir, max_articles)
                feed_entry.last_fetched = datetime.now().isoformat()
                feed_entry.article_count = len(articles)
                all_results.append(FeedFetchResult(
                    url=url,
                    articles=articles,
                    new_count=sum(1 for a in articles if a.is_new),
                    total=len(articles),
                ))
            except RagError as e:
                all_results.append(FeedFetchResult(url=url, error=str(e)))

        self.save(feeds)
        return all_results


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    # Remove tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#39;", "'")
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
