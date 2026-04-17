#!/usr/bin/env python3
"""
DFB Training Assistant — PDF Ingestion Script
==============================================
Converts a new PDF into a knowledge chunk (.md file) and adds it to manifest.json.
The Claude API is used to generate a one-sentence summary for the manifest.

Usage (simple):
    python3 ingest.py "My New Manual.pdf"

Usage (with options):
    python3 ingest.py "My New Manual.pdf" --topic "Fire Investigation" --pages "1-50"

Usage (split into multiple chunks by page range):
    python3 ingest.py "My New Manual.pdf" --topic "Fire Investigation" --chunk "intro" --pages "1-20"
    python3 ingest.py "My New Manual.pdf" --topic "Fire Investigation" --chunk "techniques" --pages "21-60"

After running this script:
    1. A new .md file will appear in the knowledge/ folder
    2. manifest.json will be updated with the new chunk's summary
    3. Open app.py and add keywords to TOPIC_HINTS for the new subject
    4. Upload the new .md + updated manifest.json + app.py to GitHub → Render redeploys
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import date

# ── Dependency check ───────────────────────────────────────────────────────────

try:
    import pdfplumber
except ImportError:
    print("\n❌  pdfplumber not installed.")
    print("   Run:  pip3 install pdfplumber --break-system-packages\n")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("\n❌  anthropic not installed.")
    print("   Run:  pip3 install anthropic --break-system-packages\n")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).parent
KNOWLEDGE   = BASE_DIR / "knowledge"
MANIFEST    = KNOWLEDGE / "manifest.json"

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_api_key() -> str:
    """Load the Anthropic API key from .env or environment."""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key and key != "paste-your-key-here":
                    return key
    return os.environ.get("ANTHROPIC_API_KEY", "")


def load_manifest() -> dict:
    """Load the existing manifest.json. Creates a skeleton if it doesn't exist."""
    if MANIFEST.exists():
        with open(MANIFEST, "r", encoding="utf-8") as f:
            return json.load(f)
    # Skeleton manifest if starting from scratch
    return {
        "generated": str(date.today()),
        "dfb_standard_check": {
            "active": True,
            "rule": "Safety-critical lines are wrapped in blockquotes prefixed with ⚠️ SAFETY — Action > Condition > Standard",
            "format": "Action > Condition > Standard"
        },
        "chunks": [],
        "sources": []
    }


def save_manifest(manifest: dict):
    """Write updated manifest back to disk."""
    KNOWLEDGE.mkdir(exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"   ✅  manifest.json updated")


def next_chunk_number(manifest: dict) -> int:
    """Return the next available two-digit chunk number (e.g. 30 after 01–29)."""
    existing = []
    for chunk in manifest.get("chunks", []):
        match = re.match(r'^(\d+)_', chunk["file"])
        if match:
            existing.append(int(match.group(1)))
    return (max(existing) + 1) if existing else 1


def extract_text_from_pdf(pdf_path: Path, page_range: str = None) -> tuple[str, str]:
    """
    Extract text from a PDF, optionally limited to a page range like "1-50".
    Returns (extracted_text, actual_pages_string).
    """
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        # Parse page range
        if page_range:
            parts = page_range.split("-")
            try:
                start = int(parts[0]) - 1          # convert to 0-indexed
                end   = int(parts[1]) if len(parts) > 1 else total_pages
            except ValueError:
                print(f"⚠️  Invalid page range '{page_range}'. Using all pages.")
                start, end = 0, total_pages
        else:
            start, end = 0, total_pages

        start = max(0, start)
        end   = min(total_pages, end)

        pages_used = []
        text_parts = []

        for i in range(start, end):
            page      = pdf.pages[i]
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(page_text)
                pages_used.append(i + 1)   # back to 1-indexed for display

        extracted = "\n\n".join(text_parts)
        if pages_used:
            pages_str = f"{pages_used[0]}–{pages_used[-1]}"
        else:
            pages_str = f"{start+1}–{end}"

        return extracted, pages_str


def clean_text(raw: str) -> str:
    """
    Light cleanup of PDF-extracted text:
    - Collapse multiple blank lines to two
    - Strip trailing whitespace from lines
    - Remove form-feed characters
    """
    raw = raw.replace("\f", "\n")
    lines = [line.rstrip() for line in raw.splitlines()]
    # Collapse 3+ consecutive blank lines to 2
    cleaned = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def generate_summary(text: str, topic: str, api_key: str) -> str:
    """
    Use Claude Haiku to write a one-sentence manifest summary for this chunk.
    Falls back to a placeholder if the API call fails.
    """
    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""You are writing a one-sentence description for a knowledge-base index entry.
The content is Dublin Fire Brigade training material on the topic: {topic}

Here is an excerpt from the content (first 3000 characters):
{text[:3000]}

Write ONE sentence (max 40 words) that:
- Starts with a verb (e.g. "Covers", "Describes", "Details", "Explains")
- Says what subjects/equipment/procedures are covered
- Is specific enough to distinguish this chunk from others on the same broad topic
- Does NOT start with "This chunk" or "This document"

Reply with the single sentence only. No quotes. No full stop at the end."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip().rstrip(".")
    except Exception as e:
        print(f"   ⚠️  Could not generate summary via API ({e}). Using placeholder.")
        return f"Covers {topic} training material"


def slugify(text: str) -> str:
    """Convert a topic/chunk name to a safe filename slug."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s_]', '', text)
    text = re.sub(r'[\s]+', '_', text)
    return text[:40]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ingest a PDF into the DFB knowledge base.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ingest.py "New Manual.pdf"
  python3 ingest.py "New Manual.pdf" --topic "Fire Investigation" --pages "1-60"
  python3 ingest.py "New Manual.pdf" --topic "Fire Investigation" --chunk "scene-examination" --pages "61-120"
        """
    )
    parser.add_argument("pdf",
                        help="Path to the PDF file to ingest")
    parser.add_argument("--topic",
                        default=None,
                        help="Topic name for this chunk (e.g. 'Fire Investigation'). Prompted if not given.")
    parser.add_argument("--chunk",
                        default=None,
                        help="Short name for this chunk (e.g. 'scene-examination'). Derived from topic if not given.")
    parser.add_argument("--pages",
                        default=None,
                        help="Page range to extract, e.g. '1-50'. Extracts all pages if not given.")
    parser.add_argument("--no-summary",
                        action="store_true",
                        help="Skip Claude API summary generation and use a placeholder.")

    args = parser.parse_args()

    # ── Validate PDF path ──────────────────────────────────────────────────────
    pdf_path = Path(args.pdf)
    if not pdf_path.is_absolute():
        pdf_path = BASE_DIR / pdf_path
    if not pdf_path.exists():
        print(f"\n❌  PDF not found: {pdf_path}\n")
        sys.exit(1)

    print(f"\n🚒  DFB Ingest — {pdf_path.name}")
    print("─" * 50)

    # ── Topic (prompt if not given) ────────────────────────────────────────────
    topic = args.topic
    if not topic:
        topic = input("📚  Topic name (e.g. 'Fire Investigation'): ").strip()
        if not topic:
            print("❌  Topic name is required.\n")
            sys.exit(1)

    # ── Chunk name ─────────────────────────────────────────────────────────────
    chunk_name = args.chunk if args.chunk else slugify(topic)

    # ── Load manifest and determine file number ────────────────────────────────
    KNOWLEDGE.mkdir(exist_ok=True)
    manifest    = load_manifest()
    chunk_num   = next_chunk_number(manifest)
    output_file = f"{chunk_num:02d}_{chunk_name}.md"
    output_path = KNOWLEDGE / output_file

    print(f"   PDF:        {pdf_path.name}")
    print(f"   Topic:      {topic}")
    print(f"   Pages:      {args.pages or 'all'}")
    print(f"   Output:     knowledge/{output_file}")
    print()

    # ── Extract text ───────────────────────────────────────────────────────────
    print("📄  Extracting text from PDF...")
    raw_text, pages_str = extract_text_from_pdf(pdf_path, args.pages)

    if not raw_text.strip():
        print("❌  No text could be extracted. The PDF may be image-only (scanned).")
        print("   You will need to manually transcribe or OCR the content.\n")
        sys.exit(1)

    text = clean_text(raw_text)
    size_kb = round(len(text.encode("utf-8")) / 1024, 1)
    print(f"   ✅  Extracted {len(text):,} characters ({size_kb} KB) from pages {pages_str}")

    # ── Generate manifest summary ──────────────────────────────────────────────
    if args.no_summary:
        summary = f"Covers {topic} training material"
        print(f"   ⏭️   Skipping API summary (--no-summary flag)")
    else:
        api_key = load_api_key()
        if api_key:
            print("🤖  Generating manifest summary via Claude API...")
            summary = generate_summary(text, topic, api_key)
            print(f"   ✅  Summary: {summary}")
        else:
            print("   ⚠️  No API key found — using placeholder summary.")
            print("       (Edit manifest.json manually to improve it)")
            summary = f"Covers {topic} training material"

    # ── Write the .md chunk file ───────────────────────────────────────────────
    print(f"💾  Writing knowledge/{output_file}...")
    md_content = f"# {topic}\n\n{text}\n"
    output_path.write_text(md_content, encoding="utf-8")
    print(f"   ✅  Written ({size_kb} KB)")

    # ── Update manifest.json ───────────────────────────────────────────────────
    print("📋  Updating manifest.json...")

    # Add chunk entry
    new_chunk = {
        "file":    output_file,
        "pages":   pages_str,
        "size_kb": size_kb,
        "summary": summary
    }
    manifest["chunks"].append(new_chunk)

    # Add or update source entry
    source_name = pdf_path.name
    existing_source = next((s for s in manifest.get("sources", []) if s["file"] == source_name), None)
    if not existing_source:
        manifest.setdefault("sources", []).append({
            "file":  source_name,
            "pages": int(pages_str.split("–")[-1]) if "–" in pages_str else 0,
            "topic": topic
        })

    manifest["generated"] = str(date.today())
    save_manifest(manifest)

    # ── Done ───────────────────────────────────────────────────────────────────
    print()
    print("✅  Done! Next steps:")
    print(f"   1. Open app.py and add keywords for '{topic}' to the TOPIC_HINTS dict")
    print(f"      (copy the pattern from existing entries — map keywords to ['{chunk_num:02d}'])")
    print(f"   2. Upload knowledge/{output_file} to GitHub")
    print(f"   3. Upload updated knowledge/manifest.json to GitHub")
    print(f"   4. Upload updated app.py to GitHub")
    print(f"   → Render will auto-redeploy in ~2 minutes")
    print()


if __name__ == "__main__":
    main()
