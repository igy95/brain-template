"""Configuration for the Brain ingestion pipeline."""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# External services (injected via env vars / GitHub Secrets)
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
NEO4J_URI = os.environ.get("NEO4J_URI", "")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

# ---------------------------------------------------------------------------
# Model settings
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 4096

# ---------------------------------------------------------------------------
# LightRAG settings
# ---------------------------------------------------------------------------
LIGHTRAG_WORKING_DIR = os.environ.get("LIGHTRAG_WORKING_DIR", ".lightrag_data")
CHUNK_TOKEN_SIZE = 1200
CHUNK_OVERLAP_TOKEN_SIZE = 100

# Domain-specific entity types for knowledge graph extraction.
# Replaces LightRAG defaults (Person, Creature, Organization, Location,
# Event, Concept, Method, Content, Data, Artifact, NaturalObject)
# which lack team/product/technology/project/service — causing UNKNOWN entities.
ENTITY_TYPES = [
    "person", "organization", "team", "concept", "method",
    "product", "technology", "event", "content", "data",
    "artifact", "project", "location", "service",
]

# ---------------------------------------------------------------------------
# Qdrant collection names (LightRAG naming convention)
# ---------------------------------------------------------------------------
_MODEL_SUFFIX = "all_minilm_l6_v2_384d"
COLLECTION_CHUNKS = f"lightrag_vdb_chunks_{_MODEL_SUFFIX}"
COLLECTION_ENTITIES = f"lightrag_vdb_entities_{_MODEL_SUFFIX}"
COLLECTION_RELATIONSHIPS = f"lightrag_vdb_relationships_{_MODEL_SUFFIX}"
WORKSPACE_ID = "_"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BRAIN_DIR = Path(os.environ.get("GITHUB_WORKSPACE", Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Ingestion exclusions — metadata files that are not knowledge content
# ---------------------------------------------------------------------------
EXCLUDED_FILES = {"README.md", "CLAUDE.md", "index.md", "schema.md"}
EXCLUDED_PATTERNS = {"_meta.md"}
