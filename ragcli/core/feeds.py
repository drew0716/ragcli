"""RSS/Atom feed fetcher — converts feed articles into documents."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import feedparser


class FeedManager:
    """Manages RSS/Atom feeds for a collection."""

    def __init__(self, rag_dir: Path | None = None) -> None:
        self.rag_dir = rag_dir or Path.cwd() / ".rag"
        self.feeds_path = self.rag_dir / "feeds.json"

    def load(self) -> dict[str, dict]:
        """Load feed config: {collection_name: {url, last_fetched, article_count}}."""
        if self.feeds_path.exists():
            return json.loads(self.feeds_path.read_text())
        return {}

    def save(self, feeds: dict[str, dict]) -> None:
        self.rag_dir.mkdir(parents=True, exist_ok=True)
        self.feeds_path.write_text(json.dumps(feeds, indent=2, default=str))

    def add_feed(self, collection: str, url: str) -> dict:
        """Register a feed URL for a collection."""
        feeds = self.load()
        if collection not in feeds:
            feeds[collection] = []

        # Check if URL already exists
        for f in feeds[collection]:
            if f["url"] == url:
                return f

        entry = {
            "url": url,
            "added": datetime.now().isoformat(),
            "last_fetched": None,
            "article_count": 0,
        }
        feeds[collection].append(entry)
        self.save(feeds)
        return entry

    def remove_feed(self, collection: str, url: str) -> bool:
        feeds = self.load()
        if collection not in feeds:
            return False
        before = len(feeds[collection])
        feeds[collection] = [f for f in feeds[collection] if f["url"] != url]
        self.save(feeds)
        return len(feeds[collection]) < before

    def get_feeds(self, collection: str) -> list[dict]:
        feeds = self.load()
        return feeds.get(collection, [])

    def fetch_feed(
        self,
        url: str,
        docs_dir: Path,
        max_articles: int = 50,
    ) -> list[dict]:
        """
        Fetch an RSS/Atom feed and save articles as markdown files.
        Returns list of {title, filename, is_new}.
        """
        # Fetch with httpx first (handles SSL better than urllib on macOS)
        try:
            import httpx

            response = httpx.get(url, timeout=30.0, follow_redirects=True, verify=False)
            feed = feedparser.parse(response.text)
        except Exception:
            # Fallback to feedparser's built-in fetching
            feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse feed: {feed.bozo_exception}")

        results: list[dict] = []
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

            # Strip HTML tags for clean text
            content = _strip_html(content)

            if not content.strip():
                continue

            # Generate a stable filename from the title
            safe_title = re.sub(r"[^a-zA-Z0-9\s-]", "", title)[:60].strip()
            safe_title = re.sub(r"\s+", "-", safe_title)
            # Add a short hash to avoid collisions
            url_hash = hashlib.md5(link.encode()).hexdigest()[:6]
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

            results.append({
                "title": title,
                "filename": filename,
                "is_new": is_new,
                "link": link,
                "published": published,
            })

        return results

    def fetch_all_feeds(
        self,
        collection: str,
        docs_dir: Path,
        max_articles: int = 50,
    ) -> list[dict]:
        """Fetch all feeds for a collection. Returns list of results per feed."""
        feeds = self.load()
        collection_feeds = feeds.get(collection, [])
        all_results: list[dict] = []

        for feed_entry in collection_feeds:
            url = feed_entry["url"]
            try:
                articles = self.fetch_feed(url, docs_dir, max_articles)
                feed_entry["last_fetched"] = datetime.now().isoformat()
                feed_entry["article_count"] = len(articles)
                all_results.append({
                    "url": url,
                    "articles": articles,
                    "new_count": sum(1 for a in articles if a["is_new"]),
                    "total": len(articles),
                })
            except Exception as e:
                all_results.append({
                    "url": url,
                    "error": str(e),
                    "articles": [],
                    "new_count": 0,
                    "total": 0,
                })

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
