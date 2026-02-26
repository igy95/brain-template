"""
Inbox Classifier for Brain

Reads files from inbox/, uses OpenAI API to classify them
into appropriate categories, moves them, and updates _meta.md files.
Designed to run weekly via GitHub Actions cron.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path

import frontmatter
import openai

from config import BRAIN_DIR, LLM_MODEL, OPENAI_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

INBOX_DIR = BRAIN_DIR / "inbox"


def get_inbox_files() -> list[Path]:
    """Return .md files in inbox/ excluding _meta.md."""
    if not INBOX_DIR.exists():
        return []
    return [f for f in INBOX_DIR.glob("*.md") if f.name != "_meta.md"]


def read_index() -> str:
    """Read index.md to understand category structure."""
    index_path = BRAIN_DIR / "index.md"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return ""


def classify_file(client: openai.OpenAI, index_content: str, metadata: dict, body: str) -> dict | None:
    """Ask GPT-4o-mini to classify a document into the right category.

    Returns dict with keys: target_category, suggested_filename, updated_tags
    or None on failure.
    """
    prompt = f"""You are classifying a document for a personal knowledge base (Brain).

Here is the current category structure from index.md:
---
{index_content}
---

Here is the document to classify:

Frontmatter:
{json.dumps(metadata, ensure_ascii=False, default=str)}

Body (first 500 chars):
{body[:500]}

Classify this document. Respond with ONLY a JSON object (no markdown fences):
{{
  "target_category": "category/subcategory",
  "suggested_filename": "kebab-case-name.md",
  "updated_tags": ["tag1", "tag2", "tag3"]
}}

Rules:
- target_category must be an existing folder path (e.g., "tech/frontend", "business", "life")
- suggested_filename must be kebab-case with .md extension
- updated_tags: 3-7 tags, English, lowercase
- If you're unsure, use the closest matching category"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("Failed to parse classification response: %s", text)
        return None


def update_meta(folder: Path, title: str, filename: str, summary: str) -> None:
    """Add an entry to a folder's _meta.md."""
    meta_path = folder / "_meta.md"
    if not meta_path.exists():
        return

    content = meta_path.read_text(encoding="utf-8")

    # Remove the "No documents yet" placeholder if present
    content = content.replace("_No documents yet._", "")

    entry = f"- **[{title}]({filename})** — {summary}\n"
    if entry not in content:
        content = content.rstrip() + "\n" + entry

    meta_path.write_text(content, encoding="utf-8")


def remove_from_inbox_meta(filename: str) -> None:
    """Remove an entry from inbox/_meta.md."""
    meta_path = INBOX_DIR / "_meta.md"
    if not meta_path.exists():
        return

    content = meta_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    filtered = [line for line in lines if filename not in line]
    meta_path.write_text("\n".join(filtered), encoding="utf-8")


def main() -> None:
    if not OPENAI_API_KEY:
        log.error("OPENAI_API_KEY not set")
        sys.exit(1)

    inbox_files = get_inbox_files()
    if not inbox_files:
        log.info("Inbox is empty — nothing to classify.")
        return

    log.info("Found %d files in inbox to classify", len(inbox_files))

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    index_content = read_index()
    moved_count = 0

    for filepath in inbox_files:
        log.info("Processing: %s", filepath.name)

        try:
            post = frontmatter.load(filepath)
            metadata = dict(post.metadata)
            body = post.content
        except Exception:
            log.warning("Failed to parse %s — skipping", filepath.name, exc_info=True)
            continue

        result = classify_file(client, index_content, metadata, body)
        if not result:
            log.warning("Classification failed for %s — leaving in inbox", filepath.name)
            continue

        target_category = result.get("target_category", "").strip("/")
        suggested_filename = result.get("suggested_filename", filepath.name)
        updated_tags = result.get("updated_tags", metadata.get("tags", []))

        target_dir = BRAIN_DIR / target_category
        if not target_dir.exists():
            log.warning("Target category %s doesn't exist — leaving in inbox", target_category)
            continue

        # Update frontmatter tags if changed
        if updated_tags:
            metadata["tags"] = updated_tags

        # Write updated file to target location
        target_path = target_dir / suggested_filename
        if target_path.exists():
            # Avoid overwriting — append a suffix
            stem = target_path.stem
            target_path = target_dir / f"{stem}-from-inbox.md"

        post.metadata = metadata
        target_path.write_text(frontmatter.dumps(post), encoding="utf-8")

        # Remove from inbox
        filepath.unlink()

        # Update metadata files
        title = metadata.get("title", suggested_filename.replace("-", " ").replace(".md", ""))
        summary = metadata.get("summary", "")
        update_meta(target_dir, title, suggested_filename, summary)
        remove_from_inbox_meta(filepath.name)

        moved_count += 1
        log.info("Moved: inbox/%s → %s/%s", filepath.name, target_category, suggested_filename)

    log.info("Classification complete — moved %d files.", moved_count)


if __name__ == "__main__":
    main()
