"""Knowledge graph — extracts entities and relationships from documents."""

import json
import re
from pathlib import Path

import networkx as nx


# --- Domain detection ---

DOMAIN_KEYWORDS = {
    "travel": [
        "hotel", "flight", "airline", "booking", "reservation", "itinerary",
        "cruise", "excursion", "check-in", "departure", "arrival", "airport",
        "passport", "visa", "luggage", "boarding", "terminal", "gate",
    ],
    "policy": [
        "policy", "procedure", "compliance", "regulation", "requirement",
        "employee", "handbook", "section", "effective date", "department",
        "approval", "violation", "guideline", "standard", "protocol",
    ],
    "financial": [
        "invoice", "payment", "balance", "account", "transaction",
        "revenue", "expense", "budget", "quarterly", "fiscal",
        "profit", "loss", "asset", "liability", "dividend",
    ],
    "legal": [
        "contract", "agreement", "clause", "party", "obligation",
        "liability", "indemnify", "jurisdiction", "arbitration",
        "termination", "amendment", "warranty", "confidential",
    ],
    "medical": [
        "patient", "diagnosis", "treatment", "prescription", "physician",
        "symptom", "dosage", "medical", "clinical", "healthcare",
    ],
}


def detect_domain(texts: list[str]) -> str:
    """Detect the domain of a collection from sample text."""
    combined = " ".join(t[:500] for t in texts[:20]).lower()
    scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in combined)
    best = max(scores, key=scores.get)
    return best if scores[best] >= 3 else "general"


# --- Domain-specific LLM extraction prompts ---

DOMAIN_EXTRACT_PROMPTS = {
    "travel": (
        "Extract travel-related entities from this document. For each, give type and value.\n"
        "Types: person, hotel, airline, flight_number, airport, city, country, cruise_line, "
        "ship, excursion, tour, restaurant, transport, date_range, check_in_time, "
        "check_out_time, confirmation_number, cost, address, phone, email.\n"
        "Focus on actionable travel details: where, when, how much, confirmation numbers.\n\n"
    ),
    "policy": (
        "Extract policy-related entities from this document. For each, give type and value.\n"
        "Types: policy_name, topic, section, department, role, requirement, effective_date, "
        "review_date, approval_authority, penalty, exception, definition, procedure_step, "
        "compliance_standard, contact.\n"
        "Focus on the policy structure: what rules, who they apply to, key dates.\n\n"
    ),
    "financial": (
        "Extract financial entities from this document. For each, give type and value.\n"
        "Types: company, account, amount, date, transaction_type, invoice_number, "
        "payment_method, tax, category, budget_item, quarter, fiscal_year, contact.\n"
        "Focus on specific numbers, dates, and account references.\n\n"
    ),
    "legal": (
        "Extract legal entities from this document. For each, give type and value.\n"
        "Types: party, agreement_type, effective_date, termination_date, clause, "
        "obligation, jurisdiction, governing_law, amount, penalty, contact.\n"
        "Focus on parties, key dates, obligations, and specific terms.\n\n"
    ),
    "general": (
        "Extract all named entities from this document. For each, give type and value.\n"
        "Types: person, organization, location, date, amount, reference_number, "
        "topic, contact, event.\n\n"
    ),
}


# --- Regex extractors ---

MONEY_RE = re.compile(
    r'[\$\£\€][\d,]+(?:\.\d{2})?'
    r'|(?:USD|EUR|GBP)\s*[\d,]+(?:\.\d{2})?'
    r'|[\d,]+(?:\.\d{2})?\s*(?:dollars|euros|pounds)',
    re.IGNORECASE,
)

DATE_RE = re.compile(
    r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?'
    r'|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'\s+\d{1,2}(?:\s*[-\u2013,]\s*\d{1,2})?,?\s*\d{4}\b'
    r'|\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b'
    r'|\b\d{4}[/\-]\d{1,2}[/\-]\d{1,2}\b',
    re.IGNORECASE,
)

CONFIRMATION_RE = re.compile(
    r'(?:confirmation|booking|reservation|reference|order|record\s*locator|PNR)'
    r'\s*(?:#|number|no\.?|code)?[:\s]*([A-Z0-9]{5,12})',
    re.IGNORECASE,
)

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')

# Travel-specific
TIME_RE = re.compile(r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b')
ADDRESS_RE = re.compile(r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Blvd|Way|Close|Cl)\b', re.IGNORECASE)


def extract_entities_regex(text: str, source_file: str, domain: str = "general") -> list[dict]:
    """Extract entities from text using regex."""
    entities: list[dict] = []

    for match in MONEY_RE.finditer(text):
        entities.append({
            "type": "cost" if domain == "travel" else "amount",
            "value": match.group().strip(),
            "source": source_file,
            "context": _get_context(text, match.start(), 80),
        })

    for match in DATE_RE.finditer(text):
        entities.append({
            "type": "date",
            "value": match.group().strip(),
            "source": source_file,
            "context": _get_context(text, match.start(), 80),
        })

    for match in CONFIRMATION_RE.finditer(text):
        entities.append({
            "type": "confirmation_number",
            "value": match.group(1).strip(),
            "source": source_file,
            "context": _get_context(text, match.start(), 80),
        })

    for match in EMAIL_RE.finditer(text):
        entities.append({"type": "email", "value": match.group().strip(), "source": source_file})

    for match in PHONE_RE.finditer(text):
        entities.append({"type": "phone", "value": match.group().strip(), "source": source_file})

    # Domain-specific regex
    if domain == "travel":
        for match in TIME_RE.finditer(text):
            entities.append({
                "type": "time", "value": match.group().strip(), "source": source_file,
                "context": _get_context(text, match.start(), 80),
            })
        for match in ADDRESS_RE.finditer(text):
            entities.append({
                "type": "address", "value": match.group().strip(), "source": source_file,
            })

    return entities


def extract_entities_llm(text: str, source_file: str, generator, domain: str = "general") -> list[dict]:
    """Extract entities using the LLM with domain-specific prompts."""
    domain_prompt = DOMAIN_EXTRACT_PROMPTS.get(domain, DOMAIN_EXTRACT_PROMPTS["general"])

    prompt = (
        domain_prompt
        + 'Output as JSON array: [{"type": "...", "value": "..."}]\n'
        + "Only output the JSON, nothing else.\n\n"
        + f"Document ({Path(source_file).name}):\n{text[:3000]}"
    )

    try:
        response, _ = generator.generate(prompt)
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[-1].rsplit("```", 1)[0]

        raw = json.loads(response)
        if not isinstance(raw, list):
            return []

        return [
            {"type": e["type"], "value": str(e["value"]), "source": source_file}
            for e in raw
            if isinstance(e, dict) and "type" in e and "value" in e
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _get_context(text: str, pos: int, window: int) -> str:
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    return text[start:end].replace("\n", " ").strip()


# --- Knowledge Graph ---

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
        if self.graph_path.exists():
            try:
                data = json.loads(self.graph_path.read_text())
                self.domain = data.get("_domain", "general")
                self.graph = nx.node_link_graph(data, edges="edges")
            except (json.JSONDecodeError, nx.NetworkXError, KeyError):
                try:
                    self.graph = nx.node_link_graph(data, edges="links")
                except Exception:
                    self.graph = nx.Graph()

    def save(self) -> None:
        self.graphs_dir.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph, edges="edges")
        data["_domain"] = self.domain
        tmp = self.graph_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
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
        generator=None,
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

    def get_stats(self) -> dict:
        type_counts: dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            ntype = data.get("type", "unknown")
            type_counts[ntype] = type_counts.get(ntype, 0) + 1
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "entity_types": type_counts,
            "domain": self.domain,
        }

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
