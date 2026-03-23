"""Index project files into ChromaDB using Ollama embeddings."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import chromadb
import ollama as ollama_lib

from convaier.config import OllamaConfig
from convaier.rag.chunker import Chunk, chunk_file, collect_files

log = logging.getLogger("convaier")

COLLECTION_NAME = "convaier_code"
DB_DIR = ".convaier/rag"
EMBED_MODEL = "nomic-embed-text"


def _get_db(project_root: Path) -> chromadb.ClientAPI:
    db_path = project_root / DB_DIR
    db_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(db_path))


def _get_collection(db: chromadb.ClientAPI) -> chromadb.Collection:
    return db.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _embed_texts(texts: list[str], config: OllamaConfig) -> list[list[float]]:
    """Get embeddings from Ollama."""
    client = ollama_lib.Client(host=config.host, timeout=config.timeout)
    response = client.embed(model=EMBED_MODEL, input=texts)
    return response.embeddings


def _chunk_id(chunk: Chunk) -> str:
    """Stable ID for a chunk."""
    raw = f"{chunk.file}:{chunk.start_line}-{chunk.end_line}"
    return hashlib.md5(raw.encode()).hexdigest()


def index_project(
    project_root: Path,
    config: OllamaConfig,
    force: bool = False,
) -> int:
    """Index all code files. Returns number of chunks indexed."""
    db = _get_db(project_root)
    collection = _get_collection(db)

    if force:
        # Drop and recreate
        db.delete_collection(COLLECTION_NAME)
        collection = _get_collection(db)

    files = collect_files(project_root)
    log.info("  Found %d files to index", len(files))

    all_chunks: list[Chunk] = []
    for f in files:
        all_chunks.extend(chunk_file(f, project_root))

    if not all_chunks:
        log.info("  No chunks to index")
        return 0

    # Filter out already indexed chunks (by ID)
    existing_ids = set(collection.get()["ids"]) if not force else set()
    new_chunks = [c for c in all_chunks if _chunk_id(c) not in existing_ids]

    if not new_chunks:
        log.info("  All %d chunks already indexed", len(all_chunks))
        return len(all_chunks)

    # Batch embed and store
    BATCH_SIZE = 20
    indexed = 0
    for i in range(0, len(new_chunks), BATCH_SIZE):
        batch = new_chunks[i:i + BATCH_SIZE]
        texts = [c.content for c in batch]
        ids = [_chunk_id(c) for c in batch]
        metadatas = [
            {"file": c.file, "start_line": c.start_line, "end_line": c.end_line}
            for c in batch
        ]

        try:
            embeddings = _embed_texts(texts, config)
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            indexed += len(batch)
            log.info("  Indexed %d/%d chunks", indexed, len(new_chunks))
        except Exception as e:
            log.error("  Embedding failed for batch %d: %s", i // BATCH_SIZE, e)

    total = len(existing_ids) + indexed
    log.info("  Total: %d chunks in index", total)
    return total
