"""
Re-transcribe diagram pages with tikz-cd enhanced prompt.

Reads diagram_pages.json (from find_diagram_pages.py), re-runs only those pages
with the diagram-tikzcd prompt, and saves results separately. Option to merge
back into main transcriptions.json.

Usage:
    # First: generate diagram page list
    python3 find_diagram_pages.py

    # Dry run — see what would be re-transcribed
    GEMINI_API_KEY=key python3 retranscribe_diagrams.py --dry-run

    # Run re-transcription (default: pro model)
    GEMINI_API_KEY=key python3 retranscribe_diagrams.py

    # Use flash-lite (cheaper, faster)
    GEMINI_API_KEY=key python3 retranscribe_diagrams.py --model flash-lite

    # Re-run only high-complexity pages (≥10 arrows)
    GEMINI_API_KEY=key python3 retranscribe_diagrams.py --min-arrows 10

    # Merge results back into main transcriptions.json
    python3 retranscribe_diagrams.py --merge
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: pip install google-genai")
    sys.exit(1)

try:
    import fitz
except ImportError:
    print("ERROR: pip install pymupdf")
    sys.exit(1)

from prompts_v2 import get_prompt

BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent.parent
RAW_PDF_DIR = PROJECT_DIR / "raw_pdf"
PRODUCTION_DIR = BASE_DIR / "production"
DIAGRAM_PAGES_FILE = BASE_DIR / "diagram_pages.json"

MODELS = {
    "pro": {
        "id": "gemini-3.1-pro-preview",
        "cost_input": 2.00,
        "cost_output": 12.00,
    },
    "flash-lite": {
        "id": "gemini-3.1-flash-lite-preview",
        "cost_input": 0.25,
        "cost_output": 1.50,
    },
}

VOLUMES = {
    "140-3": {"pdf": "140-3.pdf", "pages": 696},
    "140-4": {"pdf": "140-4.pdf", "pages": 280},
}

PROMPT_STYLE = "diagram-tikzcd"
MAX_OUTPUT_TOKENS = 16000
DELAY = 5.0
MAX_BACKOFF = 300


def extract_pdf_page(doc, page_idx: int) -> bytes:
    """Extract a single PDF page as standalone PDF bytes."""
    single = fitz.open()
    single.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
    pdf_bytes = single.tobytes()
    single.close()
    return pdf_bytes


def transcribe_page(client, doc, page_idx: int, prev_page_idx: int = None,
                     model_id: str = None, thinking_level: str = "medium") -> dict:
    """Transcribe a single page with diagram-tikzcd prompt."""
    system_prompt, user_text = get_prompt(PROMPT_STYLE)

    parts = []

    # Previous page context
    if prev_page_idx is not None and prev_page_idx >= 0:
        try:
            prev_bytes = extract_pdf_page(doc, prev_page_idx)
            parts.append(types.Part.from_bytes(data=prev_bytes, mime_type="application/pdf"))
            parts.append(types.Part.from_text(
                text=f"[Previous page {prev_page_idx + 1} shown above for context]"
            ))
        except Exception:
            pass

    # Current page
    curr_bytes = extract_pdf_page(doc, page_idx)
    parts.append(types.Part.from_bytes(data=curr_bytes, mime_type="application/pdf"))
    parts.append(types.Part.from_text(text=user_text))

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=[types.Content(parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=1.0,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
            )
        )

        text = ""
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "thought") and part.thought:
                    continue
                if part.text:
                    text += part.text

        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "prompt_tokens": getattr(um, "prompt_token_count", None),
                "output_tokens": getattr(um, "candidates_token_count", None),
                "thinking_tokens": getattr(um, "thoughts_token_count", None),
            }

        return {"status": "success", "transcription": text.strip(), "usage": usage}

    except Exception as e:
        return {"status": "error", "error": str(e), "transcription": ""}


def merge_results():
    """Merge diagram retranscriptions back into main transcriptions.json."""
    for vol_key in VOLUMES:
        diagram_file = PRODUCTION_DIR / vol_key / "diagram_transcriptions.json"
        main_file = PRODUCTION_DIR / vol_key / "transcriptions.json"

        if not diagram_file.exists():
            print(f"  {vol_key}: no diagram_transcriptions.json found, skipping")
            continue

        if not main_file.exists():
            print(f"  {vol_key}: no transcriptions.json found, skipping")
            continue

        with open(diagram_file, encoding="utf-8") as f:
            diagram_data = json.load(f)
        with open(main_file, encoding="utf-8") as f:
            main_data = json.load(f)

        # Backup main file
        backup_file = PRODUCTION_DIR / vol_key / "transcriptions_pre_diagram.json"
        if not backup_file.exists():
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(main_data, f, ensure_ascii=False, indent=2)
            print(f"  {vol_key}: backed up to {backup_file.name}")

        merged = 0
        for pkey, entry in diagram_data.items():
            if entry.get("status") == "success":
                main_data[pkey] = entry
                main_data[pkey]["source"] = "diagram-retranscription"
                merged += 1

        with open(main_file, "w", encoding="utf-8") as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2)

        print(f"  {vol_key}: merged {merged} diagram retranscriptions into transcriptions.json")


def main():
    parser = argparse.ArgumentParser(description="Re-transcribe diagram pages with tikz-cd prompt")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", choices=list(MODELS.keys()), default="pro")
    parser.add_argument("--thinking", default="medium")
    parser.add_argument("--min-arrows", type=int, default=0,
                        help="Only re-transcribe pages with >= N arrows")
    parser.add_argument("--volume", choices=list(VOLUMES.keys()) + ["all"], default="all")
    parser.add_argument("--merge", action="store_true",
                        help="Merge diagram results into main transcriptions.json (no API needed)")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--delay", type=float, default=DELAY)
    args = parser.parse_args()

    if args.merge:
        print("Merging diagram retranscriptions into main transcriptions...")
        merge_results()
        return

    # Load diagram pages
    if not DIAGRAM_PAGES_FILE.exists():
        print("ERROR: diagram_pages.json not found. Run find_diagram_pages.py first.")
        sys.exit(1)

    with open(DIAGRAM_PAGES_FILE, encoding="utf-8") as f:
        diagram_data = json.load(f)

    pages = diagram_data["pages"]

    # Filter
    if args.min_arrows > 0:
        pages = [p for p in pages if p.get("total_arrows", 0) >= args.min_arrows]

    volumes_filter = list(VOLUMES.keys()) if args.volume == "all" else [args.volume]
    pages = [p for p in pages if p["volume"] in volumes_filter]

    # Group by volume
    by_volume = {}
    for p in pages:
        vol = p["volume"]
        if vol not in by_volume:
            by_volume[vol] = []
        by_volume[vol].append(p)

    model_cfg = MODELS[args.model]
    model_id = model_cfg["id"]

    print("=" * 70)
    print("DIAGRAM RE-TRANSCRIPTION — tikz-cd Enhanced Prompt")
    print("=" * 70)
    print(f"  Total pages to re-transcribe: {len(pages)}")
    for vol, vol_pages in by_volume.items():
        print(f"    {vol}: {len(vol_pages)} pages")
    print(f"  Model: {model_id} (thinking={args.thinking})")
    print(f"  Prompt: {PROMPT_STYLE}")
    print(f"  Min arrows filter: {args.min_arrows}")

    # Cost estimate
    avg_input = 4000  # diagram prompt is larger
    avg_output = 1500
    est_cost = len(pages) * (avg_input * model_cfg["cost_input"] + avg_output * model_cfg["cost_output"]) / 1_000_000
    print(f"  Est. cost: ~${est_cost:.2f}")

    if args.dry_run:
        print("\n  [DRY RUN]")
        print(f"\n  Pages that would be re-transcribed:")
        for p in pages:
            print(f"    {p['volume']} p{p['page']:>4} "
                  f"(arrows={p['total_arrows']}, approaches={p['approaches']})")
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Process each volume
    for vol_key, vol_pages in by_volume.items():
        vol_info = VOLUMES[vol_key]
        pdf_path = RAW_PDF_DIR / vol_info["pdf"]

        if not pdf_path.exists():
            print(f"ERROR: {pdf_path} not found")
            continue

        out_dir = PRODUCTION_DIR / vol_key
        out_dir.mkdir(parents=True, exist_ok=True)
        results_file = out_dir / "diagram_transcriptions.json"

        # Load existing for resume
        results = {}
        if args.resume and results_file.exists():
            with open(results_file, encoding="utf-8") as f:
                results = json.load(f)
            print(f"  Resuming: {len(results)} pages already done")

        doc = fitz.open(str(pdf_path))
        backoff = args.delay
        start_time = time.time()
        done = 0
        errors = 0

        print(f"\n{'='*70}")
        print(f"  Volume {vol_key}: {len(vol_pages)} diagram pages")
        print(f"{'='*70}")

        for i, page_info in enumerate(vol_pages):
            page_num = page_info["page"]
            page_idx = page_num - 1  # 0-indexed
            pkey = str(page_num)

            if pkey in results and results[pkey].get("status") == "success":
                continue

            prev_idx = page_idx - 1 if page_idx > 0 else None

            print(f"  [{i+1}/{len(vol_pages)}] p{pkey} "
                  f"(arrows={page_info['total_arrows']})...",
                  end="", flush=True)

            result = transcribe_page(client, doc, page_idx, prev_idx,
                                     model_id=model_id, thinking_level=args.thinking)

            # Rate limit handling
            if result["status"] == "error" and "429" in result.get("error", ""):
                backoff = min(backoff * 2, MAX_BACKOFF)
                print(f" RATE LIMITED — backing off {backoff:.0f}s...")
                time.sleep(backoff)
                result = transcribe_page(client, doc, page_idx, prev_idx,
                                         model_id=model_id, thinking_level=args.thinking)
            else:
                backoff = args.delay

            results[pkey] = result

            if result["status"] == "success":
                done += 1
                chars = len(result.get("transcription", ""))
                has_tikzcd = "tikzcd" in result.get("transcription", "")
                print(f" OK ({chars}ch, tikzcd={'YES' if has_tikzcd else 'no'})")
            else:
                errors += 1
                print(f" ERROR: {result.get('error', '?')[:80]}")

            # Save after each page
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            time.sleep(backoff)

        doc.close()

        # Stats
        elapsed = time.time() - start_time
        success = sum(1 for v in results.values() if v.get("status") == "success")
        tikzcd_count = sum(1 for v in results.values()
                          if v.get("status") == "success" and "tikzcd" in v.get("transcription", ""))

        print(f"\n  {vol_key} complete: {success}/{len(vol_pages)} pages")
        print(f"  Pages with tikzcd output: {tikzcd_count}")
        print(f"  Errors: {errors}")
        print(f"  Time: {elapsed/60:.1f} min")
        print(f"  Results: {results_file}")

    print(f"\n{'='*70}")
    print(f"  Done! To merge into main transcriptions:")
    print(f"  python3 retranscribe_diagrams.py --merge")


if __name__ == "__main__":
    main()
