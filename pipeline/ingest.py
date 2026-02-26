"""
Brain Ingestion Pipeline

Reads changed markdown files and ingests them into LightRAG
(Qdrant vector DB + Neo4j graph DB) with sentence-transformers
embeddings and OpenAI GPT-4o-mini entity extraction.

Deletion is handled directly via Qdrant/Neo4j APIs (not LightRAG)
to avoid silent failures from LightRAG's adelete_by_doc_ids.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import frontmatter
import numpy as np
import openai
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
from neo4j import GraphDatabase
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from config import (
    BRAIN_DIR,
    CHUNK_OVERLAP_TOKEN_SIZE,
    CHUNK_TOKEN_SIZE,
    COLLECTION_CHUNKS,
    COLLECTION_ENTITIES,
    COLLECTION_RELATIONSHIPS,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    ENTITY_TYPES,
    EXCLUDED_FILES,
    EXCLUDED_PATTERNS,
    LIGHTRAG_WORKING_DIR,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USERNAME,
    OPENAI_API_KEY,
    QDRANT_API_KEY,
    QDRANT_URL,
    WORKSPACE_ID,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File detection
# ---------------------------------------------------------------------------

def _is_excluded(filepath: str) -> bool:
    """Check if a file should be excluded from ingestion."""
    name = Path(filepath).name
    if name in EXCLUDED_FILES:
        return True
    if name in EXCLUDED_PATTERNS:
        return True
    return False


def get_changed_files() -> dict[str, list[str]]:
    """Return lists of changed/deleted markdown files.

    Uses CHANGED_FILES / DELETED_FILES env vars set by the GitHub Actions
    workflow.  Falls back to scanning all .md files (first run or cache miss).
    """
    changed_env = os.environ.get("CHANGED_FILES", "").strip()
    deleted_env = os.environ.get("DELETED_FILES", "").strip()

    if changed_env or deleted_env:
        changed = [f for f in changed_env.split("\n") if f.strip()] if changed_env else []
        deleted = [f for f in deleted_env.split("\n") if f.strip()] if deleted_env else []
    else:
        # Fallback: scan all .md files in brain dir
        log.info("No CHANGED_FILES env var — scanning all .md files")
        changed = [
            str(p.relative_to(BRAIN_DIR))
            for p in BRAIN_DIR.rglob("*.md")
            if not any(part.startswith(".") for part in p.relative_to(BRAIN_DIR).parts)
            and not str(p.relative_to(BRAIN_DIR)).startswith("pipeline/")
        ]
        deleted = []

    # Filter exclusions
    changed = [f for f in changed if not _is_excluded(f)]
    deleted = [f for f in deleted if not _is_excluded(f)]

    log.info("Changed files (%d): %s", len(changed), changed)
    log.info("Deleted files (%d): %s", len(deleted), deleted)
    return {"changed": changed, "deleted": deleted}


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

def parse_markdown(filepath: Path) -> tuple[dict, str]:
    """Parse a markdown file into (frontmatter_dict, body_text)."""
    post = frontmatter.load(filepath)
    return dict(post.metadata), post.content


def prepare_document(relative_path: str, metadata: dict, body: str) -> str:
    """Build an enriched text string for LightRAG ingestion.

    Prepends metadata so entity extraction can leverage titles, tags, etc.
    """
    title = metadata.get("title", "")
    tags = ", ".join(str(t) for t in metadata.get("tags", []))
    summary = metadata.get("summary", "")

    header = f"Title: {title}\nPath: {relative_path}\nTags: {tags}\nSummary: {summary}"
    return f"{header}\n\n{body}"


# ---------------------------------------------------------------------------
# LightRAG model functions
# ---------------------------------------------------------------------------

_st_model: SentenceTransformer | None = None


def _get_st_model() -> SentenceTransformer:
    global _st_model
    if _st_model is None:
        _st_model = SentenceTransformer(EMBEDDING_MODEL)
    return _st_model


async def _embedding_func(texts: list[str]) -> np.ndarray:
    model = _get_st_model()
    return model.encode(texts, normalize_embeddings=True)


def create_embedding_func() -> EmbeddingFunc:
    return EmbeddingFunc(
        embedding_dim=EMBEDDING_DIM,
        max_token_size=512,
        func=_embedding_func,
        model_name=EMBEDDING_MODEL,
    )


def create_llm_func():
    """Return an async LLM function compatible with LightRAG's interface."""
    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

    async def llm_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list | None = None,
        **kwargs,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            messages=messages,
        )
        return response.choices[0].message.content

    return llm_func


# ---------------------------------------------------------------------------
# Direct Qdrant / Neo4j deletion (bypasses LightRAG)
# ---------------------------------------------------------------------------

def _qdrant_filter(field: str, value: str) -> models.Filter:
    """Build a Qdrant filter matching a payload field + workspace."""
    return models.Filter(
        must=[
            models.FieldCondition(key=field, match=models.MatchValue(value=value)),
            models.FieldCondition(key="workspace_id", match=models.MatchValue(value=WORKSPACE_ID)),
        ]
    )


def ensure_payload_indexes(qdrant: QdrantClient) -> None:
    """Create keyword indexes required for filtered deletion.

    Qdrant requires a payload index before filtering on a field.
    Idempotent — silently skips if the index already exists.
    """
    indexes = [
        (COLLECTION_CHUNKS, "full_doc_id"),
        (COLLECTION_ENTITIES, "file_path"),
        (COLLECTION_RELATIONSHIPS, "file_path"),
    ]
    for collection, field in indexes:
        try:
            qdrant.create_payload_index(
                collection_name=collection,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            log.info("Created index: %s.%s", collection, field)
        except Exception:
            pass  # Index already exists


def delete_document_from_stores(
    rel_path: str,
    qdrant: QdrantClient,
    neo4j_driver,
) -> None:
    """Delete all traces of a document directly from Qdrant + Neo4j.

    Used for file deletions and orphan cleanup where no re-insertion follows.
    For updates (delete + re-insert), use snapshot_old_points / delete_old_points
    to avoid data loss on insert failure.
    """
    # Qdrant: chunks (keyed by full_doc_id)
    qdrant.delete(
        collection_name=COLLECTION_CHUNKS,
        points_selector=models.FilterSelector(filter=_qdrant_filter("full_doc_id", rel_path)),
    )
    # Qdrant: entities (keyed by file_path)
    qdrant.delete(
        collection_name=COLLECTION_ENTITIES,
        points_selector=models.FilterSelector(filter=_qdrant_filter("file_path", rel_path)),
    )
    # Qdrant: relationships (keyed by file_path)
    qdrant.delete(
        collection_name=COLLECTION_RELATIONSHIPS,
        points_selector=models.FilterSelector(filter=_qdrant_filter("file_path", rel_path)),
    )

    # Neo4j: nodes + their relationships
    with neo4j_driver.session() as session:
        session.run(
            "MATCH (n:base) WHERE n.file_path = $path DETACH DELETE n",
            path=rel_path,
        )
        session.run(
            "MATCH ()-[r:DIRECTED]->() WHERE r.file_path = $path DELETE r",
            path=rel_path,
        )

    log.info("Direct-deleted from stores: %s", rel_path)


def _scroll_point_ids(
    qdrant: QdrantClient,
    collection: str,
    field: str,
    value: str,
) -> list:
    """Collect all point IDs matching a filter from a Qdrant collection."""
    ids = []
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=collection,
            scroll_filter=_qdrant_filter(field, value),
            limit=100,
            offset=offset,
            with_payload=False,
        )
        ids.extend(p.id for p in points)
        if offset is None:
            break
    return ids


def snapshot_old_points(doc_ids: list[str], qdrant: QdrantClient) -> dict:
    """Record existing Qdrant point IDs before insertion.

    Returns a dict mapping collection names to lists of point IDs.
    These IDs can be safely deleted after successful insertion,
    because newly inserted points will have different IDs.
    """
    old = {COLLECTION_CHUNKS: [], COLLECTION_ENTITIES: [], COLLECTION_RELATIONSHIPS: []}
    for doc_id in doc_ids:
        old[COLLECTION_CHUNKS].extend(
            _scroll_point_ids(qdrant, COLLECTION_CHUNKS, "full_doc_id", doc_id)
        )
        old[COLLECTION_ENTITIES].extend(
            _scroll_point_ids(qdrant, COLLECTION_ENTITIES, "file_path", doc_id)
        )
        old[COLLECTION_RELATIONSHIPS].extend(
            _scroll_point_ids(qdrant, COLLECTION_RELATIONSHIPS, "file_path", doc_id)
        )

    for col, ids in old.items():
        if ids:
            log.info("Snapshot: %d old points in %s", len(ids), col)
    return old


def delete_old_points(old_points: dict, qdrant: QdrantClient) -> None:
    """Delete previously snapshotted point IDs from Qdrant.

    Called after successful insertion to remove stale data.
    New points (from ainsert) have different IDs, so they are safe.
    """
    for collection, point_ids in old_points.items():
        if not point_ids:
            continue
        qdrant.delete(
            collection_name=collection,
            points_selector=models.PointIdsList(points=point_ids),
        )
        log.info("Deleted %d old points from %s", len(point_ids), collection)


def cleanup_orphan_entries(
    qdrant: QdrantClient,
    neo4j_driver,
    valid_paths: set[str],
) -> int:
    """Remove Qdrant/Neo4j entries whose source files no longer exist.

    Runs only during full re-ingest (no CHANGED_FILES env var) to clean up
    zombie data from renamed/moved files.
    """
    # Collect all unique full_doc_ids from chunks collection
    all_doc_ids: set[str] = set()
    offset = None
    while True:
        result = qdrant.scroll(
            collection_name=COLLECTION_CHUNKS,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="workspace_id",
                        match=models.MatchValue(value=WORKSPACE_ID),
                    )
                ]
            ),
            limit=100,
            offset=offset,
            with_payload=["full_doc_id"],
        )
        points, offset = result
        for p in points:
            doc_id = p.payload.get("full_doc_id", "")
            if doc_id:
                all_doc_ids.add(doc_id)
        if offset is None:
            break

    orphans = all_doc_ids - valid_paths
    if not orphans:
        log.info("No orphan entries found in Qdrant.")
        return 0

    log.info("Found %d orphan doc_ids: %s", len(orphans), sorted(orphans))
    for orphan_path in orphans:
        delete_document_from_stores(orphan_path, qdrant, neo4j_driver)

    return len(orphans)


def verify_ingestion(rel_path: str, qdrant: QdrantClient) -> bool:
    """Verify that a document has chunks in Qdrant after insertion."""
    result = qdrant.count(
        collection_name=COLLECTION_CHUNKS,
        count_filter=_qdrant_filter("full_doc_id", rel_path),
        exact=True,
    )
    if result.count == 0:
        log.warning("VERIFICATION FAILED: no chunks found for %s", rel_path)
        return False
    log.info("Verified: %s (%d chunks)", rel_path, result.count)
    return True


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

async def run_ingestion() -> None:
    files = get_changed_files()

    if not files["changed"] and not files["deleted"]:
        log.info("No files to process — exiting.")
        return

    # Set env vars that LightRAG storage backends read
    os.environ["QDRANT_URL"] = QDRANT_URL
    os.environ["QDRANT_API_KEY"] = QDRANT_API_KEY
    os.environ["NEO4J_URI"] = NEO4J_URI
    os.environ["NEO4J_USERNAME"] = NEO4J_USERNAME
    os.environ["NEO4J_PASSWORD"] = NEO4J_PASSWORD

    # Direct clients for reliable deletion
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    is_full_scan = not os.environ.get("CHANGED_FILES", "").strip() \
                   and not os.environ.get("DELETED_FILES", "").strip()

    try:
        # Ensure Qdrant payload indexes exist for filtered deletion
        ensure_payload_indexes(qdrant)

        # --- Full re-ingest: clean up orphan entries first ---
        if is_full_scan:
            valid_paths = set(files["changed"])
            orphan_count = cleanup_orphan_entries(qdrant, neo4j_driver, valid_paths)
            log.info("Orphan cleanup: removed %d stale entries", orphan_count)

        # --- Handle deleted files ---
        for rel_path in files["deleted"]:
            log.info("Deleting: %s", rel_path)
            delete_document_from_stores(rel_path, qdrant, neo4j_driver)

        # --- Handle changed (new + modified) files ---
        texts = []
        doc_ids = []
        for rel_path in files["changed"]:
            abs_path = BRAIN_DIR / rel_path
            if not abs_path.exists():
                log.warning("File not found, skipping: %s", abs_path)
                continue

            try:
                metadata, body = parse_markdown(abs_path)
            except Exception:
                log.warning("Failed to parse %s — skipping", rel_path, exc_info=True)
                continue

            if not body.strip():
                log.info("Empty body, skipping: %s", rel_path)
                continue

            doc_text = prepare_document(rel_path, metadata, body)
            texts.append(doc_text)
            doc_ids.append(rel_path)
            log.info("Prepared: %s (%d chars)", rel_path, len(doc_text))

        if texts:
            # 1. Snapshot old Qdrant point IDs (before any changes)
            old_points = snapshot_old_points(doc_ids, qdrant)

            # 2. Insert new content (old points still exist, temporary duplicates)
            rag = LightRAG(
                working_dir=LIGHTRAG_WORKING_DIR,
                embedding_func=create_embedding_func(),
                llm_model_func=create_llm_func(),
                vector_storage="QdrantVectorDBStorage",
                graph_storage="Neo4JStorage",
                chunk_token_size=CHUNK_TOKEN_SIZE,
                chunk_overlap_token_size=CHUNK_OVERLAP_TOKEN_SIZE,
            )
            rag.addon_params["entity_types"] = ENTITY_TYPES
            await rag.initialize_storages()

            log.info("Inserting %d documents into LightRAG...", len(texts))
            await rag.ainsert(texts, ids=doc_ids, file_paths=doc_ids)
            log.info("Ingestion complete — %d documents processed.", len(texts))

            await rag.finalize_storages()

            # 3. Delete old points by ID (new points have different IDs, safe)
            delete_old_points(old_points, qdrant)

            # 4. Post-insert verification
            failed = []
            for doc_id in doc_ids:
                if not verify_ingestion(doc_id, qdrant):
                    failed.append(doc_id)
            if failed:
                log.error("VERIFICATION FAILED for %d documents: %s", len(failed), failed)
            else:
                log.info("All %d documents verified in Qdrant.", len(doc_ids))
        else:
            log.info("No documents to insert.")

    finally:
        neo4j_driver.close()
        qdrant.close()


def main() -> None:
    # Validate required env vars
    missing = []
    for var in ("OPENAI_API_KEY", "QDRANT_URL", "QDRANT_API_KEY", "NEO4J_URI", "NEO4J_PASSWORD"):
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    asyncio.run(run_ingestion())


if __name__ == "__main__":
    main()
