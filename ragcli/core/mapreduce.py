"""Map-reduce processor — handles broad questions across all documents."""

from pathlib import Path
from typing import Optional

from ragcli.core.errors import RagError

MAP_PROMPT = """Extract ONLY factual information from these documents that DIRECTLY answers the question.

RULES:
- Only include facts explicitly stated in the text. Do NOT infer or assume.
- For each fact, write: [SourceFile] fact
- Include specific values: dates, times, prices, confirmation numbers, names, addresses.
- If a document is not relevant to the question, skip it entirely — do NOT mention it.
- Do NOT include general policies, disclaimers, or boilerplate text unless specifically asked.
- Keep it concise — facts only, no commentary.

Question: {question}

Documents:
{batch_content}

Relevant facts (skip irrelevant documents):"""

REDUCE_PROMPT = """Combine these extracted facts into one clear, well-organized answer.

RULES:
1. Only include information that was actually extracted — do NOT add, infer, or guess.
2. If two sources say different things about the same topic, show both and note the conflict.
3. Organize by topic (e.g., hotels, flights, activities) or chronologically — whichever fits better.
4. Use **bold** for key facts: dates, prices, confirmation numbers, names.
5. Cite the source file for each fact in parentheses.
6. If information the user likely wants is missing, say "Not found in documents" for that item.
7. Do NOT pad the answer with irrelevant details or policies.

Question: {question}

Extracted facts:
{extractions}

Answer:"""

COLLECTION_SUMMARY_PROMPT = """Summarize these documents into a structured overview.
Include: what type of documents they are, key dates, key people/organizations,
major costs/amounts, important reference numbers, and the overall purpose/theme.
Be specific — include actual values, not vague descriptions.

Documents:
{batch_content}

Structured summary:"""

COLLECTION_MERGE_PROMPT = """Combine these partial summaries into one comprehensive collection overview.
Organize by theme/category. Include all specific details (dates, costs, names, reference numbers).

Partial summaries:
{summaries}

Complete collection overview:"""


def map_reduce_query(
    question: str,
    all_chunks: list[dict],
    generator,
    batch_size: int = 8,
) -> tuple[str, list[str]]:
    """
    Process all chunks in batches to answer a broad question.

    Returns: (answer, list of source files used)
    """
    # Map phase: extract relevant info from each batch
    extractions: list[str] = []
    all_sources: set[str] = set()
    errors: list[str] = []
    batches = 0

    for i in range(0, len(all_chunks), batch_size):
        batches += 1
        batch = all_chunks[i : i + batch_size]
        batch_content = ""
        for chunk in batch:
            fname = Path(chunk["source_file"]).name
            batch_content += f"\n[Source: {fname}]\n{chunk['content']}\n---\n"
            all_sources.add(chunk["source_file"])

        prompt = MAP_PROMPT.format(question=question, batch_content=batch_content)
        try:
            response, _ = generator.generate(prompt)
            if response.strip() and "no relevant information" not in response.lower():
                extractions.append(response.strip())
        except Exception as e:
            errors.append(str(e))

    # Every batch failed: surface the real problem (e.g. bad API key) instead
    # of pretending nothing was found.
    if errors and len(errors) == batches:
        raise RagError(f"All LLM calls failed during map-reduce: {errors[-1]}")

    if not extractions:
        return "I couldn't find relevant information across the documents.", list(all_sources)

    # Reduce phase: combine all extractions into a final answer
    combined = "\n\n---\n\n".join(extractions)
    prompt = REDUCE_PROMPT.format(question=question, extractions=combined)

    try:
        answer, _ = generator.generate(prompt)
        return answer.strip(), list(all_sources)
    except Exception:
        # If reduce fails, return the raw extractions
        return combined, list(all_sources)


def build_collection_summary(
    all_chunks: list[dict],
    generator,
    batch_size: int = 10,
) -> Optional[str]:
    """
    Build a comprehensive summary of all documents in a collection.
    Processes in batches via map-reduce.

    Returns: summary string, or None on failure.
    """
    if not all_chunks:
        return None

    # Deduplicate chunks by source file — take first chunk from each
    seen_files: set[str] = set()
    representative_chunks: list[dict] = []
    for chunk in all_chunks:
        if chunk["source_file"] not in seen_files:
            seen_files.add(chunk["source_file"])
            representative_chunks.append(chunk)

    # Map phase: summarize batches
    partial_summaries: list[str] = []
    errors: list[str] = []
    batches = 0

    for i in range(0, len(representative_chunks), batch_size):
        batches += 1
        batch = representative_chunks[i : i + batch_size]
        batch_content = ""
        for chunk in batch:
            fname = Path(chunk["source_file"]).name
            batch_content += f"\n[{fname}]\n{chunk['content'][:500]}\n---\n"

        prompt = COLLECTION_SUMMARY_PROMPT.format(batch_content=batch_content)
        try:
            response, _ = generator.generate(prompt)
            if response.strip():
                partial_summaries.append(response.strip())
        except Exception as e:
            errors.append(str(e))

    if errors and len(errors) == batches:
        raise RagError(f"All LLM calls failed while summarizing the collection: {errors[-1]}")

    if not partial_summaries:
        return None

    # If only one batch, return it directly
    if len(partial_summaries) == 1:
        return partial_summaries[0]

    # Reduce phase: merge partial summaries
    combined = "\n\n---\n\n".join(partial_summaries)
    prompt = COLLECTION_MERGE_PROMPT.format(summaries=combined)

    try:
        summary, _ = generator.generate(prompt)
        return summary.strip()
    except Exception:
        return combined
