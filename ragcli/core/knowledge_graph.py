"""Knowledge graph — per-collection entity graph with domain-aware extraction."""

import json
import re
from pathlib import Path
from typing import Optional

import networkx as nx
from pydantic import BaseModel, Field

from ragcli.core.generator import BaseGenerator

# Re-exported for backwards compatibility — extraction lives in kg_extraction.
from ragcli.core.kg_extraction import (  # noqa: F401
    DOMAIN_EXTRACT_PROMPTS,
    DOMAIN_KEYWORDS,
    detect_domain,
    extract_entities_llm,
    extract_entities_regex,
)


class GraphStats(BaseModel):
    """Summary statistics for a knowledge graph."""

    total_nodes: int
    total_edges: int
    entity_types: dict[str, int] = Field(default_factory=dict)
    domain: str = "general"


class KnowledgeGraph:
    """Per-collection knowledge graph with domain-aware entity extraction."""

    def __init__(self, rag_dir: Path | None = None, collection: str = "default") -> None:
        self.rag_dir = rag_dir or Path.cwd() / ".rag"
        self.graphs_dir = self.rag_dir / "graphs"
        self.graphs_dir.mkdir(parents=True, exist_ok=True)
        self.collection = collection
        self.graph_path = self.graphs_dir / f"{self._safe_name(collection)}.json"
        self.graph = nx.Graph()
        self.domain: str = "general"
        self._load()

    def _safe_name(self, name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]", "-", name).strip("-") or "default"

    def _load(self) -> None:
        if not self.graph_path.exists():
            return
        try:
            data = json.loads(self.graph_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self.graph = nx.Graph()
            return
        self.domain = data.get("_domain", "general")
        try:
            self.graph = nx.node_link_graph(data, edges="edges")
        except (nx.NetworkXError, KeyError):
            try:
                self.graph = nx.node_link_graph(data, edges="links")
            except Exception:
                self.graph = nx.Graph()

    def save(self) -> None:
        self.graphs_dir.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph, edges="edges")
        data["_domain"] = self.domain
        tmp = self.graph_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.graph_path)

    def set_domain(self, domain: str) -> None:
        """Set the domain for this graph (affects extraction prompts)."""
        self.domain = domain

    def detect_and_set_domain(self, texts: list[str]) -> str:
        """Auto-detect domain from sample texts and set it."""
        self.domain = detect_domain(texts)
        return self.domain

    def add_document(
        self,
        source_file: str,
        text: str,
        generator: Optional[BaseGenerator] = None,
        use_llm: bool = True,
    ) -> int:
        doc_name = Path(source_file).name
        doc_node = f"doc:{doc_name}"
        self.graph.add_node(doc_node, type="document", name=doc_name, path=source_file)

        regex_entities = extract_entities_regex(text, source_file, domain=self.domain)
        llm_entities: list[dict] = []
        if use_llm and generator:
            llm_entities = extract_entities_llm(text, source_file, generator, domain=self.domain)

        all_entities = regex_entities + llm_entities
        added = 0

        for entity in all_entities:
            etype = entity["type"]
            evalue = entity["value"]
            entity_key = f"{etype}:{evalue.lower().strip()}"

            if not self.graph.has_node(entity_key):
                self.graph.add_node(
                    entity_key, type=etype, value=evalue, sources=[source_file],
                )
                added += 1
            else:
                sources = self.graph.nodes[entity_key].get("sources", [])
                if source_file not in sources:
                    sources.append(source_file)
                    self.graph.nodes[entity_key]["sources"] = sources

            self.graph.add_edge(
                doc_node, entity_key, relation="contains",
                context=entity.get("context", ""),
            )

        # Co-occurrence edges
        doc_entities = list(set(
            f"{e['type']}:{e['value'].lower().strip()}" for e in all_entities
        ))
        for i, e1 in enumerate(doc_entities):
            for e2 in doc_entities[i + 1:]:
                if e1 != e2:
                    if self.graph.has_edge(e1, e2):
                        self.graph[e1][e2]["weight"] = self.graph[e1][e2].get("weight", 1) + 1
                    else:
                        self.graph.add_edge(e1, e2, relation="co_occurs", weight=1)

        return added

    def remove_document(self, source_file: str) -> None:
        doc_name = Path(source_file).name
        doc_node = f"doc:{doc_name}"
        if not self.graph.has_node(doc_node):
            return
        neighbors = list(self.graph.neighbors(doc_node))
        self.graph.remove_node(doc_node)
        for n in neighbors:
            if self.graph.has_node(n) and self.graph.degree(n) == 0:
                self.graph.remove_node(n)
            elif self.graph.has_node(n):
                sources = self.graph.nodes[n].get("sources", [])
                self.graph.nodes[n]["sources"] = [s for s in sources if s != source_file]

    def query_entities(self, question: str) -> list[dict]:
        question_lower = question.lower()
        matches: list[dict] = []

        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "document":
                continue
            value = data.get("value", "")
            ntype = data.get("type", "")

            if value.lower() in question_lower or question_lower in value.lower():
                matches.append({
                    "entity": value, "type": ntype,
                    "sources": data.get("sources", []), "relevance": 1.0,
                })
                continue

            for word in question_lower.split():
                if len(word) > 3 and word in value.lower():
                    matches.append({
                        "entity": value, "type": ntype,
                        "sources": data.get("sources", []), "relevance": 0.5,
                    })
                    break

        matches.sort(key=lambda m: m["relevance"], reverse=True)
        return matches[:10]

    def get_related_sources(self, question: str, max_depth: int = 2) -> list[str]:
        entity_matches = self.query_entities(question)
        if not entity_matches:
            return []

        related: dict[str, float] = {}
        for match in entity_matches:
            entity_key = f"{match['type']}:{match['entity'].lower().strip()}"
            if not self.graph.has_node(entity_key):
                continue
            for source in match.get("sources", []):
                related[source] = related.get(source, 0) + match["relevance"]
            if max_depth > 1:
                for neighbor in self.graph.neighbors(entity_key):
                    n_data = self.graph.nodes.get(neighbor, {})
                    if n_data.get("type") == "document":
                        path = n_data.get("path", "")
                        if path:
                            related[path] = related.get(path, 0) + match["relevance"] * 0.5
                    else:
                        for src in n_data.get("sources", []):
                            related[src] = related.get(src, 0) + match["relevance"] * 0.3

        return [s for s, _ in sorted(related.items(), key=lambda x: x[1], reverse=True)][:10]

    def get_stats(self) -> GraphStats:
        type_counts: dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            ntype = data.get("type", "unknown")
            type_counts[ntype] = type_counts.get(ntype, 0) + 1
        return GraphStats(
            total_nodes=self.graph.number_of_nodes(),
            total_edges=self.graph.number_of_edges(),
            entity_types=type_counts,
            domain=self.domain,
        )

    def get_all_entities(self) -> list[dict]:
        entities: list[dict] = []
        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "document":
                continue
            entities.append({
                "id": node, "type": data.get("type", "unknown"),
                "value": data.get("value", ""),
                "sources": data.get("sources", []),
                "connections": self.graph.degree(node),
            })
        entities.sort(key=lambda e: e["connections"], reverse=True)
        return entities

    def get_entity_neighborhood(self, entity_id: str) -> dict:
        if not self.graph.has_node(entity_id):
            return {"entity": None, "connections": []}
        data = self.graph.nodes[entity_id]
        connections = []
        for neighbor in self.graph.neighbors(entity_id):
            n_data = self.graph.nodes.get(neighbor, {})
            edge_data = self.graph[entity_id][neighbor]
            connections.append({
                "id": neighbor,
                "type": n_data.get("type", "unknown"),
                "value": n_data.get("value", n_data.get("name", "")),
                "relation": edge_data.get("relation", ""),
                "weight": edge_data.get("weight", 1),
            })
        return {
            "entity": {
                "id": entity_id, "type": data.get("type", ""),
                "value": data.get("value", ""), "sources": data.get("sources", []),
            },
            "connections": connections,
        }
