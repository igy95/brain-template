"""
Post-ingestion quality processing for Neo4j knowledge graph.

Runs after LightRAG ingestion to fix known quality issues:
1. Merge case-sensitive duplicate entities
2. Remove low-value orphan nodes
3. Trim excessive <SEP> description accumulation
4. Reclassify UNKNOWN entities via LLM
5. Print quality report
"""

import json
import logging
import os
import sys

import openai
from neo4j import GraphDatabase

from config import (
    ENTITY_TYPES,
    LLM_MODEL,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USERNAME,
    OPENAI_API_KEY,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Entity pairs where same lowercase name maps to legitimately different concepts.
# These will NOT be merged during normalization.
MERGE_EXCEPTIONS = {
    frozenset({"VISITOR", "Visitor"}),  # state machine state vs person role
}

# Orphan nodes with these entity_types are safe to delete (low-value extractions).
ORPHAN_DELETE_TYPES = {"data", "UNKNOWN"}

# Maximum <SEP> segments to keep in descriptions.
MAX_SEP_SEGMENTS = 3


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


# ---------------------------------------------------------------------------
# Step 1: Merge case-sensitive duplicate entities
# ---------------------------------------------------------------------------

def merge_case_duplicates(driver) -> int:
    """Find and merge entities that differ only by case."""
    merged_count = 0

    with driver.session() as session:
        # Find all case-duplicate groups
        groups = session.run("""
            MATCH (n:base)
            WITH toLower(n.entity_id) AS lower_id, collect(n) AS nodes
            WHERE size(nodes) > 1
            RETURN lower_id,
                   [n IN nodes | n.entity_id] AS names,
                   [n IN nodes | n.entity_type] AS types
        """).data()

        for group in groups:
            names = group["names"]

            # Skip exception pairs
            if frozenset(names) in MERGE_EXCEPTIONS:
                log.info("Skipping merge exception: %s", names)
                continue

            # Pick canonical name: prefer the most common casing pattern
            # (Title Case > lower case > UPPER CASE)
            canonical = _pick_canonical(names)
            others = [n for n in names if n != canonical]

            if not others:
                continue

            for other_name in others:
                _merge_entity_into(session, source=other_name, target=canonical)
                merged_count += 1
                log.info("Merged '%s' → '%s'", other_name, canonical)

    return merged_count


def _pick_canonical(names: list[str]) -> str:
    """Pick the best canonical name from a list of case variants."""
    # Prefer names that are Title Case or have more uppercase letters
    # (e.g., "ChatGPT" over "chatgpt", "GitHub" over "GITHUB")
    def score(name: str) -> tuple:
        # Higher is better: (not_all_upper, has_mixed_case, length)
        is_all_upper = name == name.upper()
        has_proper_case = any(c.isupper() for c in name[1:]) and any(c.islower() for c in name)
        return (not is_all_upper, has_proper_case, len(name))

    return max(names, key=score)


def _merge_entity_into(session, source: str, target: str) -> None:
    """Merge source entity into target: move relationships, then delete source."""
    # Move outgoing relationships
    session.run("""
        MATCH (s:base {entity_id: $source})-[r:DIRECTED]->(t)
        WHERE t.entity_id <> $target
        WITH s, r, t, properties(r) AS props
        MERGE (canonical:base {entity_id: $target})
        MERGE (canonical)-[nr:DIRECTED]->(t)
        SET nr += props
        DELETE r
    """, source=source, target=target)

    # Move incoming relationships
    session.run("""
        MATCH (t)-[r:DIRECTED]->(s:base {entity_id: $source})
        WHERE t.entity_id <> $target
        WITH s, r, t, properties(r) AS props
        MERGE (canonical:base {entity_id: $target})
        MERGE (t)-[nr:DIRECTED]->(canonical)
        SET nr += props
        DELETE r
    """, source=source, target=target)

    # Delete source node (and any self-referencing relationships)
    session.run("""
        MATCH (s:base {entity_id: $source})
        DETACH DELETE s
    """, source=source)


# ---------------------------------------------------------------------------
# Step 2: Remove low-value orphan nodes
# ---------------------------------------------------------------------------

def cleanup_orphans(driver) -> int:
    """Delete orphan nodes (no relationships) with low-value entity types."""
    with driver.session() as session:
        result = session.run("""
            MATCH (n:base)
            WHERE NOT (n)-[:DIRECTED]-() AND NOT (n)<-[:DIRECTED]-()
              AND n.entity_type IN $types
            WITH n, n.entity_id AS eid
            DETACH DELETE n
            RETURN count(*) AS deleted
        """, types=list(ORPHAN_DELETE_TYPES)).single()
        deleted = result["deleted"] if result else 0
        log.info("Deleted %d low-value orphan nodes (types: %s)", deleted, ORPHAN_DELETE_TYPES)
        return deleted


# ---------------------------------------------------------------------------
# Step 2b: Remove unknown_source entities
# ---------------------------------------------------------------------------

def cleanup_unknown_source(driver) -> int:
    """Delete entities and relationships with file_path='unknown_source'.

    These are legacy entries from before the file_path parameter was added
    to the ingestion pipeline. After a full re-ingest, all entities should
    have a valid file_path. Entities that still show 'unknown_source' are
    stale duplicates that won't be updated by future runs.
    """
    with driver.session() as session:
        # Delete relationships first
        rel_result = session.run("""
            MATCH ()-[r:DIRECTED]->()
            WHERE r.file_path = 'unknown_source'
            DELETE r
            RETURN count(r) AS deleted
        """).single()
        deleted_rels = rel_result["deleted"] if rel_result else 0

        # Delete nodes
        node_result = session.run("""
            MATCH (n:base)
            WHERE n.file_path = 'unknown_source'
            DETACH DELETE n
            RETURN count(n) AS deleted
        """).single()
        deleted_nodes = node_result["deleted"] if node_result else 0

    total = deleted_nodes + deleted_rels
    log.info("Deleted %d unknown_source entries (%d nodes, %d relationships)",
             total, deleted_nodes, deleted_rels)
    return total


# ---------------------------------------------------------------------------
# Step 3: Trim excessive <SEP> description accumulation
# ---------------------------------------------------------------------------

def trim_descriptions(driver) -> int:
    """Trim node descriptions that have too many <SEP> segments."""
    trimmed = 0

    with driver.session() as session:
        nodes = session.run("""
            MATCH (n:base)
            WHERE n.description CONTAINS '<SEP>'
              AND size(split(n.description, '<SEP>')) > $max_segments
            RETURN n.entity_id AS eid, n.description AS desc
        """, max_segments=MAX_SEP_SEGMENTS).data()

        for node in nodes:
            segments = node["desc"].split("<SEP>")
            # Keep only the last N segments (most recent)
            trimmed_desc = "<SEP>".join(segments[-MAX_SEP_SEGMENTS:]).strip()
            session.run("""
                MATCH (n:base {entity_id: $eid})
                SET n.description = $desc
            """, eid=node["eid"], desc=trimmed_desc)
            trimmed += 1

        # Also trim relationship descriptions
        rels = session.run("""
            MATCH ()-[r:DIRECTED]->()
            WHERE r.description CONTAINS '<SEP>'
              AND size(split(r.description, '<SEP>')) > $max_segments
            RETURN elementId(r) AS rid, r.description AS desc
        """, max_segments=MAX_SEP_SEGMENTS).data()

        for rel in rels:
            segments = rel["desc"].split("<SEP>")
            trimmed_desc = "<SEP>".join(segments[-MAX_SEP_SEGMENTS:]).strip()
            session.run("""
                MATCH ()-[r:DIRECTED]->()
                WHERE elementId(r) = $rid
                SET r.description = $desc
            """, rid=rel["rid"], desc=trimmed_desc)
            trimmed += 1

    log.info("Trimmed %d descriptions (nodes + relationships)", trimmed)
    return trimmed


# ---------------------------------------------------------------------------
# Step 4: Reclassify UNKNOWN entities via LLM
# ---------------------------------------------------------------------------

RECLASSIFY_BATCH_SIZE = 30

RECLASSIFY_SYSTEM_PROMPT = f"""\
You are an entity type classifier for a knowledge graph.

Valid types: {json.dumps(ENTITY_TYPES)}

For each entity (id + description), return the single best matching type.
Respond with a JSON object mapping entity_id to type. Example:
{{"AI": "concept", "CX Team": "team"}}

Rules:
- Use ONLY types from the valid list above.
- If genuinely ambiguous, prefer "concept" as fallback.
- Return valid JSON only, no explanation."""


def reclassify_unknown(driver) -> int:
    """Reclassify UNKNOWN-type entities using GPT-4o-mini."""
    with driver.session() as session:
        unknowns = session.run("""
            MATCH (n:base)
            WHERE n.entity_type = 'UNKNOWN'
            RETURN n.entity_id AS id, n.description AS desc
        """).data()

    if not unknowns:
        log.info("No UNKNOWN entities to reclassify.")
        return 0

    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY not set — skipping reclassify.")
        return 0

    log.info("Reclassifying %d UNKNOWN entities...", len(unknowns))
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    valid_types = {t.lower() for t in ENTITY_TYPES}
    reclassified = 0

    # Process in batches
    for i in range(0, len(unknowns), RECLASSIFY_BATCH_SIZE):
        batch = unknowns[i:i + RECLASSIFY_BATCH_SIZE]
        entities_text = "\n".join(
            f"- {u['id']}: {(u['desc'] or '')[:200]}"
            for u in batch
        )

        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": RECLASSIFY_SYSTEM_PROMPT},
                    {"role": "user", "content": entities_text},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            mapping = json.loads(response.choices[0].message.content)
        except Exception:
            log.warning("LLM reclassify failed for batch %d", i, exc_info=True)
            continue

        with driver.session() as session:
            for entity_id, new_type in mapping.items():
                new_type_lower = new_type.lower()
                if new_type_lower not in valid_types:
                    log.warning("Invalid type '%s' for '%s' — skipping",
                                new_type, entity_id)
                    continue

                session.run(f"""
                    MATCH (n:base {{entity_id: $eid}})
                    WHERE n.entity_type = 'UNKNOWN'
                    REMOVE n:UNKNOWN
                    SET n:`{new_type_lower}`, n.entity_type = $new_type
                """, eid=entity_id, new_type=new_type_lower)
                reclassified += 1
                log.info("Reclassified '%s' → %s", entity_id, new_type_lower)

    log.info("Reclassified %d / %d UNKNOWN entities.", reclassified, len(unknowns))
    return reclassified


# ---------------------------------------------------------------------------
# Step 5: Quality report
# ---------------------------------------------------------------------------

def quality_report(driver) -> dict:
    """Generate and log a quality report of the knowledge graph."""
    with driver.session() as session:
        stats = session.run("""
            MATCH (n:base)
            WITH count(n) AS total_nodes
            OPTIONAL MATCH ()-[r:DIRECTED]->()
            WITH total_nodes, count(r) AS total_rels
            RETURN total_nodes, total_rels
        """).single()

        unknown_count = session.run("""
            MATCH (n:base) WHERE n.entity_type = 'UNKNOWN'
            RETURN count(n) AS cnt
        """).single()["cnt"]

        orphan_count = session.run("""
            MATCH (n:base)
            WHERE NOT (n)-[:DIRECTED]-() AND NOT (n)<-[:DIRECTED]-()
            RETURN count(n) AS cnt
        """).single()["cnt"]

        sep_nodes = session.run("""
            MATCH (n:base) WHERE n.description CONTAINS '<SEP>'
            RETURN count(n) AS cnt
        """).single()["cnt"]

        unknown_path = session.run("""
            MATCH (n:base) WHERE n.file_path = 'unknown_source'
            RETURN count(n) AS cnt
        """).single()["cnt"]

        case_dupes = session.run("""
            MATCH (n:base)
            WITH toLower(n.entity_id) AS lower_id, count(n) AS cnt
            WHERE cnt > 1
            RETURN count(*) AS groups
        """).single()["groups"]

        type_dist = session.run("""
            MATCH (n:base)
            RETURN n.entity_type AS type, count(n) AS cnt
            ORDER BY cnt DESC
        """).data()

    total_nodes = stats["total_nodes"]
    total_rels = stats["total_rels"]

    report = {
        "total_nodes": total_nodes,
        "total_relationships": total_rels,
        "unknown_type_count": unknown_count,
        "unknown_type_pct": round(unknown_count / max(total_nodes, 1) * 100, 1),
        "orphan_count": orphan_count,
        "orphan_pct": round(orphan_count / max(total_nodes, 1) * 100, 1),
        "sep_accumulated_nodes": sep_nodes,
        "unknown_file_path_count": unknown_path,
        "case_duplicate_groups": case_dupes,
        "entity_type_distribution": type_dist,
    }

    log.info("=== Knowledge Graph Quality Report ===")
    log.info("Nodes: %d | Relationships: %d", total_nodes, total_rels)
    log.info("UNKNOWN type: %d (%.1f%%)", unknown_count, report["unknown_type_pct"])
    log.info("Orphan nodes: %d (%.1f%%)", orphan_count, report["orphan_pct"])
    log.info("SEP-accumulated nodes: %d", sep_nodes)
    log.info("Unknown file_path: %d", unknown_path)
    log.info("Case-duplicate groups: %d", case_dupes)
    log.info("Entity types: %s", ", ".join(f"{t['type']}({t['cnt']})" for t in type_dist[:10]))

    # Warnings
    if report["unknown_type_pct"] > 5:
        log.warning("UNKNOWN type ratio %.1f%% exceeds 5%% threshold", report["unknown_type_pct"])
    if report["orphan_pct"] > 10:
        log.warning("Orphan node ratio %.1f%% exceeds 10%% threshold", report["orphan_pct"])
    if unknown_path > 0:
        log.warning("%d nodes still have unknown_source file_path", unknown_path)
    if case_dupes > 0:
        log.warning("%d case-duplicate groups remain", case_dupes)

    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("Starting post-ingestion processing...")

    driver = get_driver()
    try:
        merged = merge_case_duplicates(driver)
        log.info("Phase 1 complete: merged %d duplicate entities", merged)

        deleted = cleanup_orphans(driver)
        log.info("Phase 2 complete: removed %d orphan nodes", deleted)

        unknown = cleanup_unknown_source(driver)
        log.info("Phase 2b complete: removed %d unknown_source entries", unknown)

        trimmed = trim_descriptions(driver)
        log.info("Phase 3 complete: trimmed %d descriptions", trimmed)

        reclassified = reclassify_unknown(driver)
        log.info("Phase 4 complete: reclassified %d UNKNOWN entities", reclassified)

        quality_report(driver)
        log.info("Post-processing complete.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
