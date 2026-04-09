"""Query strategy — routes between specific retrieval and broad map-reduce."""

from enum import Enum

# Keywords that suggest the user wants a broad, comprehensive answer
BROAD_KEYWORDS = [
    "all", "every", "everything", "complete", "full", "entire", "overview",
    "summary", "summarize", "itinerary", "timeline", "schedule", "plan",
    "list all", "tell me about", "what do i have", "what's planned",
    "build", "compile", "comprehensive", "total", "breakdown",
    "how many", "how much total", "across all", "all the",
]

# Keywords that suggest a specific, targeted lookup
SPECIFIC_KEYWORDS = [
    "confirmation", "booking number", "reference", "check-in",
    "address", "phone", "email", "price of", "cost of",
    "which hotel", "which flight", "what time",
]


class QueryStrategy(Enum):
    SPECIFIC = "specific"   # Normal RAG retrieval
    BROAD = "broad"         # Map-reduce over all docs


def classify_query(question: str) -> QueryStrategy:
    """Determine if a question needs broad coverage or specific retrieval."""
    q = question.lower().strip()

    # Check for specific patterns first (higher priority)
    specific_score = sum(1 for kw in SPECIFIC_KEYWORDS if kw in q)
    broad_score = sum(1 for kw in BROAD_KEYWORDS if kw in q)

    # Question mark count and length also help
    # Short, specific questions: "What hotel in Dublin?"
    # Long, broad questions: "Can you build me a complete itinerary for the trip?"
    word_count = len(q.split())

    if specific_score > broad_score:
        return QueryStrategy.SPECIFIC

    if broad_score > 0:
        return QueryStrategy.BROAD

    # Longer questions with no specific indicators tend to be broad
    if word_count > 15:
        return QueryStrategy.BROAD

    return QueryStrategy.SPECIFIC
