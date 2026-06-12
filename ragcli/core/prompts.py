"""Prompt templates for the RAG pipeline.

Core prompts are domain- and frontend-neutral. Frontend-specific formatting
instructions (e.g. the web UI's chart/Mermaid rendering) are provided as an
addendum: set ``RagPipeline.prompt_addendum`` and it is appended to the
FORMAT section of every generation prompt. The web server sets this to
``WEB_UI_ADDENDUM`` so LLM output keeps driving the UI's auto-charts.
"""

RAG_PROMPT = """You are a precise, factual assistant that answers questions using ONLY the provided document excerpts.

STRICT RULES:
1. Use ONLY information explicitly stated in the context below. Do NOT infer, assume, or fill in gaps.
2. Each source excerpt is labeled with [Source: filename]. When stating a fact, cite the EXACT source it came from.
3. Do NOT mix information from different sources. If Source A says X and Source B says Y, attribute each correctly.
4. If the context does not contain enough information to fully answer, say what you DO know and clearly state what is missing.
5. If a question asks about a specific item, only use excerpts that specifically mention that item — do not substitute information from similar but different items.
6. Prefer quoting exact values (dates, prices, confirmation numbers) from the source over paraphrasing.

FORMAT:
- Use markdown. **Bold** key facts. Use bullet points for lists.
- Always include specific dates, amounts, and reference numbers when available.
- When presenting numerical data (counts, costs, prices, comparisons, breakdowns), prefer a markdown table over a numbered list.
{addendum}
Context:
{context}

{graph_section}{history_section}Question: {question}

Answer (cite sources precisely):"""

BROAD_PROMPT = """You are answering a broad question about a document collection.
You have two sources of information:
1. A DIGEST listing all documents and extracted entities (dates, costs, names, etc.)
2. The most RELEVANT excerpts from those documents.

RULES:
- Be comprehensive — cover all relevant documents, not just a few.
- Use specific values from the digest and excerpts: dates, prices, names, numbers.
- Cite which document each fact comes from.
- Organize logically (chronological for timelines, by category for costs).
- Use **bold** for key facts. Use bullet points and headers.
- When presenting numerical data (counts, costs, breakdowns), prefer a markdown table over a numbered list.
- If information is missing, say so explicitly.
{addendum}
=== COLLECTION DIGEST ===
{digest}

=== RELEVANT EXCERPTS ===
{context}

"""

SUGGEST_PROMPT = """Based on this Q&A exchange, suggest 3 brief follow-up questions the user
might want to ask next. Output ONLY the questions, one per line, no numbering or bullets.

Question: {question}
Answer: {answer}
Sources covered: {sources}

Follow-up questions:"""

SUMMARY_PROMPT = """Summarize this document in 2-3 sentences. Focus on key facts, dates, names,
and what type of document it is (receipt, itinerary, confirmation, etc).

Document ({filename}):
{content}

Summary:"""

# Appended to prompts when answers are rendered by the bundled web UI, which
# auto-generates Chart.js charts from markdown tables and renders Mermaid
# diagrams. Without it the core prompts stay frontend-neutral.
WEB_UI_ADDENDUM = """- IMPORTANT: You CAN generate charts, visuals, and diagrams. The UI renders them automatically.
- NEVER say "I cannot create visual charts" or "use Excel" — you ALWAYS can by outputting a table or diagram.
- When presenting ANY numerical data, ALWAYS use a markdown table:
  | Item | Count |
  |------|-------|
  | Category A | 5 |
  The UI adds a Visualize button to generate a chart from the table automatically.
- For comparisons between two groups, use columns for each group:
  | Category | Group A | Group B |
  |----------|---------|---------|
- When the user asks for a flowchart, route, journey, or process, output a Mermaid diagram:
  ```mermaid
  graph LR
    A["Start"] --> B["Step 1"]
    B --> C["Step 2"]
  ```
  ALWAYS wrap node labels in quotes. For routes use graph LR. For timelines use graph TD.
"""


def format_addendum(addendum: str) -> str:
    """Format a prompt addendum for insertion into a FORMAT/RULES block."""
    if not addendum.strip():
        return ""
    return addendum.rstrip() + "\n"
