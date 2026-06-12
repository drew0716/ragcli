"""Entity extraction for the knowledge graph — regex and LLM extractors."""

import json
import re
from pathlib import Path

from ragcli.core.generator import BaseGenerator

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
    r'\s+\d{1,2}(?:\s*[-–,]\s*\d{1,2})?,?\s*\d{4}\b'
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

# Cap how much text the regex extractors scan — huge files would otherwise
# hang ingest, and entity-dense prefixes capture most of the value.
MAX_REGEX_SCAN_CHARS = 500_000


def extract_entities_regex(text: str, source_file: str, domain: str = "general") -> list[dict]:
    """Extract entities from text using regex."""
    entities: list[dict] = []
    text = text[:MAX_REGEX_SCAN_CHARS]

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


def extract_entities_llm(
    text: str, source_file: str, generator: BaseGenerator, domain: str = "general"
) -> list[dict]:
    """Extract entities using the LLM with domain-specific prompts.

    Returns [] when the LLM output isn't parseable. Connection/auth errors
    propagate so callers can surface them — they indicate a misconfiguration,
    not a bad document.
    """
    domain_prompt = DOMAIN_EXTRACT_PROMPTS.get(domain, DOMAIN_EXTRACT_PROMPTS["general"])

    prompt = (
        domain_prompt
        + 'Output as JSON array: [{"type": "...", "value": "..."}]\n'
        + "Only output the JSON, nothing else.\n\n"
        + f"Document ({Path(source_file).name}):\n{text[:3000]}"
    )

    response, _ = generator.generate(prompt)
    response = response.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[-1].rsplit("```", 1)[0]

    try:
        raw = json.loads(response)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []

    return [
        {"type": e["type"], "value": str(e["value"]), "source": source_file}
        for e in raw
        if isinstance(e, dict) and "type" in e and "value" in e
    ]


def _get_context(text: str, pos: int, window: int) -> str:
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    return text[start:end].replace("\n", " ").strip()
