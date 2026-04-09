"""Agentic query layer — LLM plans and executes multi-step retrievals."""

import json
import time
from pathlib import Path
from typing import Optional

AGENT_SYSTEM = """You are a document research agent. You answer questions by using tools to search through a collection of documents.

Available tools (call by outputting JSON):
- {{"tool": "search", "query": "search terms"}} — semantic search across all documents
- {{"tool": "entity", "type": "cost|date|hotel|person|confirmation_number|...", "value": "optional filter"}} — find entities in the knowledge graph
- {{"tool": "document", "filename": "name.pdf"}} — get the full content of a specific document
- {{"tool": "list"}} — list all documents in the collection
- {{"tool": "answer", "text": "your final answer"}} — provide the final answer

RULES:
1. Think step by step. Start by understanding what information you need.
2. Use multiple tool calls if needed — don't try to answer from a single search.
3. If a search doesn't find what you need, try different search terms or look up entities.
4. When you have enough information, use the "answer" tool with a comprehensive response.
5. In your answer, cite sources with **bold** key facts and use markdown formatting.
6. If information is missing, say so explicitly.
7. Output ONE tool call per response as a JSON object on its own line.
8. IMPORTANT: You CAN generate charts and diagrams. When asked for a chart or visual, output data as a markdown table (the UI auto-generates charts from tables). NEVER say "I cannot create visuals".
9. For numerical breakdowns, ALWAYS use a markdown table — not a numbered list.
10. For flowcharts or routes, output a Mermaid diagram with node labels in quotes.

Collection info:
{collection_info}
"""

AGENT_CONTINUE = """Tool result:
{tool_result}

Based on this result, decide your next action. Either call another tool to gather more information, or use {{"tool": "answer", "text": "..."}} to provide your final answer.

Remember: be thorough. If you haven't checked all relevant documents, keep searching."""

MAX_STEPS = 6


def run_agent_query(
    question: str,
    generator,
    embedder,
    store,
    kg,
    collection_info: str = "",
    chat_history: Optional[list] = None,
) -> tuple[str, list[dict], float]:
    """
    Run an agentic query that plans and executes multi-step retrievals.

    Returns: (answer, sources_used, latency_ms)
    """
    start = time.time()
    sources_used: list[dict] = []

    # Build system prompt
    system = AGENT_SYSTEM.format(collection_info=collection_info or "No collection info available.")

    # Add chat history context
    if chat_history:
        recent = chat_history[-6:]
        history_text = "\n".join(
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content[:200]}"
            for m in recent
        )
        system += f"\n\nRecent conversation:\n{history_text}\n"

    messages = system + f"\n\nUser question: {question}\n\nYour first action:"

    for step in range(MAX_STEPS):
        # Get LLM's next action
        response, _ = generator.generate(messages)
        response = response.strip()

        # Parse tool call from response
        tool_call = _extract_tool_call(response)

        if not tool_call:
            # LLM didn't output a valid tool call — treat response as answer
            return response, sources_used, round((time.time() - start) * 1000, 1)

        tool_name = tool_call.get("tool", "")

        # Execute the tool
        if tool_name == "answer":
            answer = tool_call.get("text", response)
            return answer, sources_used, round((time.time() - start) * 1000, 1)

        elif tool_name == "search":
            query = tool_call.get("query", question)
            result = _tool_search(query, embedder, store)
            for r in result.get("results", []):
                sources_used.append({"file": r["file"], "relevance": r["score"]})
            tool_result = json.dumps(result, indent=2)

        elif tool_name == "entity":
            etype = tool_call.get("type", "")
            evalue = tool_call.get("value", "")
            result = _tool_entity(etype, evalue, kg)
            tool_result = json.dumps(result, indent=2)

        elif tool_name == "document":
            filename = tool_call.get("filename", "")
            result = _tool_document(filename, store)
            if result.get("file"):
                sources_used.append({"file": result["file"], "relevance": 1.0})
            tool_result = json.dumps(result, indent=2)

        elif tool_name == "list":
            result = _tool_list(store)
            tool_result = json.dumps(result, indent=2)

        else:
            tool_result = json.dumps({"error": f"Unknown tool: {tool_name}"})

        # Continue the conversation
        messages += f"\n{response}\n\n" + AGENT_CONTINUE.format(tool_result=tool_result)

    # Max steps reached — ask for final answer
    messages += "\n\nYou've used all available steps. Provide your final answer now using the answer tool."
    response, _ = generator.generate(messages)
    tool_call = _extract_tool_call(response)
    if tool_call and tool_call.get("tool") == "answer":
        return tool_call.get("text", response), sources_used, round((time.time() - start) * 1000, 1)
    return response, sources_used, round((time.time() - start) * 1000, 1)


def _extract_tool_call(text: str) -> Optional[dict]:
    """Extract a JSON tool call from LLM output."""
    # Try to find JSON in the text
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if "tool" in obj:
                    return obj
            except json.JSONDecodeError:
                continue

    # Try to find JSON anywhere in the text
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start:end])
            if "tool" in obj:
                return obj
        except json.JSONDecodeError:
            pass

    return None


def _tool_search(query: str, embedder, store, top_k: int = 8) -> dict:
    """Semantic search tool."""
    query_embedding = embedder.embed_query(query)
    results = store.query(query_embedding, top_k=top_k)

    items = []
    for chunk, score in results:
        items.append({
            "file": Path(chunk.source_file).name,
            "content": chunk.content[:400],
            "score": round(score, 3),
            "page": chunk.page,
        })

    return {"query": query, "results": items, "total": len(items)}


def _tool_entity(entity_type: str, value: str, kg) -> dict:
    """Knowledge graph entity lookup."""
    if value:
        # Search for specific value
        matches = kg.query_entities(value)
    else:
        # Get all entities of a type
        all_entities = kg.get_all_entities()
        matches = [
            {"entity": e["value"], "type": e["type"], "sources": e["sources"]}
            for e in all_entities
            if not entity_type or e["type"] == entity_type
        ][:15]

    return {
        "type": entity_type,
        "value": value,
        "matches": matches[:15],
    }


def _tool_document(filename: str, store) -> dict:
    """Get full content of a specific document by filename."""
    # Search for chunks from this file
    all_data = store._collection.get(
        where={"source_file": {"$contains": filename}} if filename else None,
        limit=20,
    )

    if not all_data["documents"]:
        # Try fuzzy match
        all_data = store._collection.get(limit=store.count() or 1)
        matching_docs = []
        if all_data["documents"]:
            for i, meta in enumerate(all_data["metadatas"] or []):
                src = meta.get("source_file", "")
                if filename.lower() in Path(src).name.lower():
                    matching_docs.append(all_data["documents"][i])
                    if not matching_docs:
                        return {"file": filename, "error": "Document not found", "content": ""}

            return {
                "file": filename,
                "content": "\n\n---\n\n".join(matching_docs[:10]),
                "chunks": len(matching_docs),
            }

    content = "\n\n---\n\n".join(all_data["documents"][:10])
    return {"file": filename, "content": content, "chunks": len(all_data["documents"])}


def _tool_list(store) -> dict:
    """List all documents in the collection."""
    all_data = store._collection.get(limit=store.count() or 1)
    files: dict[str, int] = {}
    if all_data["metadatas"]:
        for meta in all_data["metadatas"]:
            src = Path(meta.get("source_file", "")).name
            if src:
                files[src] = files.get(src, 0) + 1

    return {
        "total_documents": len(files),
        "documents": [{"name": name, "chunks": count} for name, count in sorted(files.items())],
    }
