"""Search the RAG index for relevant code context."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import chromadb
import ollama as ollama_lib

from convaier.config import OllamaConfig
from convaier.rag.indexer import COLLECTION_NAME, DB_DIR, EMBED_MODEL

log = logging.getLogger("convaier")


@dataclass
class SearchResult:
    file: str
    start_line: int
    end_line: int
    content: str
    distance: float


def search_context(
    query: str,
    project_root: Path,
    config: OllamaConfig,
    n_results: int = 5,
) -> list[SearchResult]:
    """Search for code chunks relevant to the query."""
    db_path = project_root / DB_DIR
    if not db_path.exists():
        log.debug("  RAG index not found, skipping context search")
        return []

    try:
        db = chromadb.PersistentClient(path=str(db_path))
        collection = db.get_collection(COLLECTION_NAME)
    except Exception:
        log.debug("  RAG collection not found")
        return []

    # Embed query
    client = ollama_lib.Client(host=config.host, timeout=config.timeout)
    response = client.embed(model=EMBED_MODEL, input=[query])
    query_embedding = response.embeddings[0]

    # Search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
    )

    search_results = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            dist = results["distances"][0][i] if results["distances"] else 0.0
            search_results.append(SearchResult(
                file=meta.get("file", ""),
                start_line=meta.get("start_line", 0),
                end_line=meta.get("end_line", 0),
                content=doc,
                distance=dist,
            ))

    return search_results


def build_rag_context(
    diff: str,
    changed_files: list[str],
    project_root: Path,
    config: OllamaConfig,
    max_results: int = 3,
    max_context_chars: int = 2000,
) -> str:
    """Build a context string from RAG search results."""
    # Use diff as query to find related code
    query = f"Code related to these changes:\n{diff[:2000]}"

    results = search_context(query, project_root, config, n_results=max_results)
    if not results:
        return ""

    # Filter out chunks from changed files (we already have those)
    results = [r for r in results if r.file not in changed_files]
    if not results:
        return ""

    parts = ["== Related Code (from project context) =="]
    total = 0
    for r in results:
        chunk_text = f"\n--- {r.file}:{r.start_line}-{r.end_line} (relevance: {1 - r.distance:.2f}) ---\n{r.content}"
        if total + len(chunk_text) > max_context_chars:
            break
        parts.append(chunk_text)
        total += len(chunk_text)

    return "\n".join(parts)
