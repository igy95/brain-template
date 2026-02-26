"""
Brain MCP Server — Semantic search over Qdrant Cloud.

Provides brain_search (document chunks) and brain_entities (knowledge graph
entities) tools for Claude Code, reading vectors stored by the LightRAG
ingestion pipeline.

Environment variables:
    QDRANT_URL      — Qdrant Cloud cluster URL
    QDRANT_API_KEY  — Qdrant Cloud API key
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

# Load .env from pipeline directory (same dir as this script)
load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
BRAIN_REPO_ROOT = Path(__file__).resolve().parent.parent  # brain/ repo root

from config import (
    COLLECTION_CHUNKS,
    COLLECTION_ENTITIES,
    COLLECTION_RELATIONSHIPS,
    EMBEDDING_MODEL,
    WORKSPACE_ID,
)

# ---------------------------------------------------------------------------
# Lazy-loaded singletons
# ---------------------------------------------------------------------------

_st_model: SentenceTransformer | None = None
_qdrant: QdrantClient | None = None


def _get_model() -> SentenceTransformer:
    global _st_model
    if _st_model is None:
        log.info("Loading embedding model: %s", EMBEDDING_MODEL)
        _st_model = SentenceTransformer(EMBEDDING_MODEL)
    return _st_model


def _get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set")
        _qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    return _qdrant


def _workspace_filter() -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="workspace_id",
                match=models.MatchValue(value=WORKSPACE_ID),
            )
        ]
    )


def _embed(text: str) -> list[float]:
    model = _get_model()
    vec = model.encode([text], normalize_embeddings=True)[0]
    return vec.tolist()


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "brain-search",
    instructions=(
        "Brain semantic search server. "
        "Use brain_search to find relevant knowledge by meaning. "
        "Use brain_entities to explore concepts and entities in the knowledge graph. "
        "Results include source file paths for citation.\n\n"
        "## Token Optimization Guidelines\n"
        "- ALWAYS start with a single targeted query. Do NOT run multiple searches (parallel or sequential) unless the first attempt is insufficient.\n"
        "- Use summary_only=true by default for brain_search. This returns only metadata (title, path, tags, summary, score) — "
        "dramatically reducing tokens. Only use summary_only=false when you need the full document content.\n"
        "- Use low top_k (3-5) for most queries. Only increase if results are insufficient.\n"
        "- brain_search: for document/knowledge lookup (notes, plans, analysis, how-to).\n"
        "- brain_entities: for concept/relationship exploration (what entities exist, how they connect). "
        "Do NOT use brain_entities for action items, task lists, or document lookup.\n"
        "- Write queries in the same language as the brain content (primarily Korean). Avoid redundant English translations.\n"
        "- Typical flow: brain_search(summary_only=true, top_k=5) → identify relevant doc → Read the file directly if full content is needed.\n"
        "- Result paths are absolute file paths. You can pass them directly to the Read tool without any path resolution."
    ),
)


_CONTENT_PREVIEW_CHARS = 200


def _extract_metadata(content: str) -> dict:
    """Extract frontmatter metadata (Title, Path, Tags, Summary) from document content.

    If frontmatter is missing (non-first chunks), returns a truncated content
    preview so the caller always has something meaningful to display.
    """
    meta: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        for key in ("Title:", "Path:", "Tags:", "Summary:"):
            if stripped.startswith(key):
                meta[key.rstrip(":").lower()] = stripped[len(key):].strip()
                break
        # Stop after hitting the first markdown heading (content body starts)
        if stripped.startswith("# ") and meta:
            break
    # Fallback: if no frontmatter found, provide a content preview
    if not meta.get("title") and not meta.get("summary"):
        preview = content[:_CONTENT_PREVIEW_CHARS].strip()
        if len(content) > _CONTENT_PREVIEW_CHARS:
            preview += "..."
        meta["preview"] = preview
    return meta


@mcp.tool()
def brain_search(query: str, top_k: int = 5, summary_only: bool = True) -> str:
    """Search Brain documents by semantic similarity.

    Returns the most relevant document chunks with source file paths.
    Use this for questions like "what do I know about X" or "find notes about Y".

    Args:
        query: Natural language search query.
        top_k: Number of results to return (default 5, max 20).
        summary_only: If true (default), return only metadata (title, path, tags,
            summary, score) instead of full content. Use false only when you need
            the complete document text.
    """
    top_k = min(max(top_k, 1), 20)
    embedding = _embed(query)
    client = _get_qdrant()

    results = client.query_points(
        collection_name=COLLECTION_CHUNKS,
        query=embedding,
        limit=top_k,
        with_payload=True,
        query_filter=_workspace_filter(),
    ).points

    if not results:
        return json.dumps({"results": [], "message": "No matching documents found."})

    items = []
    for p in results:
        content = p.payload.get("content", "")
        source = p.payload.get("full_doc_id", "")
        score = round(p.score, 4)

        # Resolve relative path to absolute using repo root
        rel_path = source
        abs_path = str(BRAIN_REPO_ROOT / rel_path) if rel_path else ""

        if summary_only:
            meta = _extract_metadata(content)
            item = {
                "path": abs_path or meta.get("path", source),
                "score": score,
            }
            if meta.get("title"):
                item["title"] = meta["title"]
            if meta.get("tags"):
                item["tags"] = meta["tags"]
            if meta.get("summary"):
                item["summary"] = meta["summary"]
            if meta.get("preview"):
                item["preview"] = meta["preview"]
            items.append(item)
        else:
            items.append({
                "content": content,
                "source": source,
                "file_path": p.payload.get("file_path", ""),
                "score": score,
            })

    return json.dumps({"results": items}, ensure_ascii=False)


@mcp.tool()
def brain_entities(query: str, top_k: int = 10) -> str:
    """Search entities (concepts, people, products, etc.) in the knowledge graph.

    Returns entities semantically related to the query, with their descriptions
    and source documents. Use this to explore what concepts exist in the brain
    and how they relate to each other.

    Args:
        query: Natural language query or entity name to search for.
        top_k: Number of results to return (default 10, max 30).
    """
    top_k = min(max(top_k, 1), 30)
    embedding = _embed(query)
    client = _get_qdrant()

    results = client.query_points(
        collection_name=COLLECTION_ENTITIES,
        query=embedding,
        limit=top_k,
        with_payload=True,
        query_filter=_workspace_filter(),
    ).points

    if not results:
        return json.dumps({"results": [], "message": "No matching entities found."})

    items = []
    for p in results:
        items.append({
            "entity_name": p.payload.get("entity_name", ""),
            "description": p.payload.get("content", ""),
            "source_id": p.payload.get("source_id", ""),
            "file_path": p.payload.get("file_path", ""),
            "score": round(p.score, 4),
        })

    return json.dumps({"results": items}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
