"""
Production transcription pipeline for Grothendieck manuscripts.

Optimal config from Benchmark V2:
- Prompt: text-first-fewshot
- Model: Gemini Pro (medium thinking)
- Input: PDF direct (no image rendering needed)
- Context: previous page image (biggest quality improvement)
- max_output_tokens: 16000 (up from 8192)

Usage:
    GEMINI_API_KEY=key python3 run_production.py --volume 140-3 --dry-run
    GEMINI_API_KEY=key python3 run_production.py --volume 140-3
    GEMINI_API_KEY=key python3 run_production.py --volume 140-4
    GEMINI_API_KEY=key python3 run_production.py --volume 140-3 --resume
    GEMINI_API_KEY=key python3 run_production.py --volume all
    GEMINI_API_KEY=key python3 run_production.py --volume all --model flash-lite --thinking high --output-dir production-flash-lite
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

# --- Paths ---
BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent.parent
RAW_PDF_DIR = PROJECT_DIR / "raw_pdf"
PRODUCTION_DIR = BASE_DIR / "production"

# --- Default config (overridable via CLI) ---
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

DEFAULT_MODEL = "pro"
DEFAULT_THINKING = "medium"
DEFAULT_PROMPT_STYLE = "text-first-fewshot"
PROMPT_STYLE = DEFAULT_PROMPT_STYLE  # mutated by --prompt-style
MAX_OUTPUT_TOKENS = 16000
DELAY = 5.0  # seconds between calls
MAX_BACKOFF = 300  # max backoff on 429 (5 min)

VOLUMES = {
    "140-3": {"pdf": "140-3.pdf", "pages": 696},
    "140-4": {"pdf": "140-4.pdf", "pages": 280},
}


def extract_pdf_page(doc, page_idx: int) -> bytes:
    """Extract a single PDF page as standalone PDF bytes."""
    single = fitz.open()
    single.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
    pdf_bytes = single.tobytes()
    single.close()
    return pdf_bytes


def transcribe_page(client, doc, page_idx: int, prev_page_idx: int = None,
                     model_id: str = None, thinking_level: str = None) -> dict:
    """Transcribe a single page with optional previous-page context."""
    system_prompt, user_text = get_prompt(PROMPT_STYLE)

    parts = []

    # Add previous page for context if available
    if prev_page_idx is not None and prev_page_idx >= 0:
        try:
            prev_bytes = extract_pdf_page(doc, prev_page_idx)
            parts.append(types.Part.from_bytes(data=prev_bytes, mime_type="application/pdf"))
            parts.append(types.Part.from_text(
                text=f"[Previous page {prev_page_idx + 1} shown above for context]"
            ))
        except Exception:
            pass  # skip context if extraction fails

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


def run_volume(client, volume_key: str, resume: bool = False,
               model_key: str = DEFAULT_MODEL, thinking_level: str = DEFAULT_THINKING,
               output_dir: Path = None):
    """Run transcription for an entire volume."""
    vol = VOLUMES[volume_key]
    pdf_path = RAW_PDF_DIR / vol["pdf"]
    model_cfg = MODELS[model_key]
    model_id = model_cfg["id"]

    if not pdf_path.exists():
        print(f"ERROR: {pdf_path} not found")
        return

    # Output directory
    out_dir = (output_dir or PRODUCTION_DIR) / volume_key
    out_dir.mkdir(parents=True, exist_ok=True)
    results_file = out_dir / "transcriptions.json"

    # Load existing results for resume
    results = {}
    if resume and results_file.exists():
        with open(results_file, encoding="utf-8") as f:
            results = json.load(f)
        print(f"  Resuming: {len(results)} pages already done")

    # Open PDF
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    print(f"  Volume: {volume_key} ({vol['pdf']})")
    print(f"  Pages: {total_pages}")
    print(f"  Model: {model_id} (thinking={thinking_level})")

    # Save config
    config = {
        "volume": volume_key,
        "pdf": vol["pdf"],
        "total_pages": total_pages,
        "model": model_id,
        "model_key": model_key,
        "prompt_style": PROMPT_STYLE,
        "thinking_level": thinking_level,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "context": "previous_page_pdf",
        "started": datetime.now().isoformat(),
    }
    with open(out_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # Transcribe all pages
    done = sum(1 for v in results.values() if v.get("status") == "success")
    errors = sum(1 for v in results.values() if v.get("status") == "error")
    skipped = 0
    backoff = DELAY
    start_time = time.time()

    for page_idx in range(total_pages):
        pkey = str(page_idx + 1)  # 1-indexed page numbers

        if pkey in results and results[pkey].get("status") == "success":
            skipped += 1
            continue

        # Previous page context (except for first page)
        prev_idx = page_idx - 1 if page_idx > 0 else None

        elapsed = time.time() - start_time
        remaining = total_pages - page_idx
        processed = done - (len([v for v in results.values() if v.get("status") == "success"]) - done) + 1
        rate = max(done - skipped, 1) / max(elapsed, 1)
        eta_min = remaining / rate / 60 if rate > 0 else 0

        print(f"  [{page_idx + 1}/{total_pages}] p{pkey} "
              f"(done:{done} err:{errors} eta:{eta_min:.0f}m)...",
              end="", flush=True)

        result = transcribe_page(client, doc, page_idx, prev_idx,
                                 model_id=model_id, thinking_level=thinking_level)

        # Backoff on rate limit errors
        if result["status"] == "error" and "429" in result.get("error", ""):
            backoff = min(backoff * 2, MAX_BACKOFF)
            print(f" RATE LIMITED — backing off {backoff:.0f}s...")
            time.sleep(backoff)
            # Retry once
            result = transcribe_page(client, doc, page_idx, prev_idx,
                                     model_id=model_id, thinking_level=thinking_level)
            if result["status"] == "error" and "429" in result.get("error", ""):
                print(f"  Still rate limited. Saving and continuing...")
                results[pkey] = result
                errors += 1
                with open(results_file, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                time.sleep(backoff)
                continue
        else:
            # Reset backoff on success
            backoff = DELAY

        results[pkey] = result

        chars = len(result.get("transcription", ""))
        tok_in = result.get("usage", {}).get("prompt_tokens", "?")
        tok_out = result.get("usage", {}).get("output_tokens", "?")

        if result["status"] == "success":
            done += 1
            print(f" OK ({chars}ch, in:{tok_in} out:{tok_out})")
        else:
            errors += 1
            print(f" ERROR: {result.get('error', '?')[:80]}")

        # Save after each page (resume-safe)
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(backoff)

    doc.close()

    # Final stats
    elapsed = time.time() - start_time
    success = sum(1 for v in results.values() if v.get("status") == "success")
    total_chars = sum(len(v.get("transcription", "")) for v in results.values()
                      if v.get("status") == "success")
    total_tok_in = sum(v.get("usage", {}).get("prompt_tokens", 0) or 0
                       for v in results.values() if v.get("status") == "success")
    total_tok_out = sum(v.get("usage", {}).get("output_tokens", 0) or 0
                        for v in results.values() if v.get("status") == "success")

    cost_in = model_cfg["cost_input"]
    cost_out = model_cfg["cost_output"]
    cost = (total_tok_in * cost_in + total_tok_out * cost_out) / 1_000_000

    print(f"\n  {'='*60}")
    print(f"  Volume {volume_key} complete")
    print(f"  {'='*60}")
    print(f"  Success: {success}/{total_pages}")
    print(f"  Errors:  {errors}")
    print(f"  Total chars: {total_chars:,}")
    print(f"  Tokens in:  {total_tok_in:,}")
    print(f"  Tokens out: {total_tok_out:,}")
    print(f"  Cost: ~${cost:.2f}")
    print(f"  Time: {elapsed/60:.1f} min")
    print(f"  Results: {results_file}")

    # Save final summary
    summary = {
        "volume": volume_key,
        "total_pages": total_pages,
        "success": success,
        "errors": errors,
        "total_chars": total_chars,
        "total_tokens_in": total_tok_in,
        "total_tokens_out": total_tok_out,
        "estimated_cost": round(cost, 2),
        "elapsed_seconds": round(elapsed),
        "model": model_id,
        "model_key": model_key,
        "thinking_level": thinking_level,
        "completed": datetime.now().isoformat(),
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return results


def main():
    parser = argparse.ArgumentParser(description="Production transcription pipeline")
    parser.add_argument("--volume", required=True,
                        choices=list(VOLUMES.keys()) + ["all"],
                        help="Which volume to transcribe")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from existing results")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=DELAY)
    parser.add_argument("--model", choices=list(MODELS.keys()), default=DEFAULT_MODEL,
                        help="Model to use (default: pro)")
    parser.add_argument("--thinking", default=DEFAULT_THINKING,
                        help="Thinking level (default: medium)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory (default: production/)")
    parser.add_argument("--prompt-style", type=str, default=DEFAULT_PROMPT_STYLE,
                        help=f"Prompt style key from prompts_v2.py (default: {DEFAULT_PROMPT_STYLE})")
    args = parser.parse_args()

    global PROMPT_STYLE
    PROMPT_STYLE = args.prompt_style

    model_key = args.model
    thinking_level = args.thinking
    model_cfg = MODELS[model_key]
    model_id = model_cfg["id"]
    output_dir = Path(BASE_DIR / args.output_dir) if args.output_dir else PRODUCTION_DIR

    volumes = list(VOLUMES.keys()) if args.volume == "all" else [args.volume]

    total_pages = sum(VOLUMES[v]["pages"] for v in volumes)

    print("=" * 70)
    print("PRODUCTION PIPELINE — Grothendieck Manuscript Transcription")
    print("=" * 70)
    print(f"  Volumes:    {volumes}")
    print(f"  Total pages: {total_pages}")
    print(f"  Model:      {model_id} (thinking={thinking_level})")
    print(f"  Prompt:     {PROMPT_STYLE}  (--prompt-style {args.prompt_style})")
    print(f"  Context:    previous page PDF")
    print(f"  Max tokens: {MAX_OUTPUT_TOKENS}")
    print(f"  Output:     {output_dir}")

    # Cost estimate
    avg_input = 3000
    avg_output = 1500
    est_cost = total_pages * (avg_input * model_cfg["cost_input"] + avg_output * model_cfg["cost_output"]) / 1_000_000
    call_time = 3 if model_key == "flash-lite" else 8
    est_time_min = total_pages * (args.delay + call_time) / 60

    print(f"  Est. cost:  ~${est_cost:.2f}")
    print(f"  Est. time:  ~{est_time_min:.0f} min ({est_time_min/60:.1f} hours)")

    if args.dry_run:
        print("\n  [DRY RUN]")
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    for vol in volumes:
        print(f"\n{'='*70}")
        print(f"Starting volume: {vol}")
        print(f"{'='*70}")
        run_volume(client, vol, resume=args.resume,
                   model_key=model_key, thinking_level=thinking_level,
                   output_dir=output_dir)

    print(f"\nAll volumes complete.")
    print(f"Results in: {output_dir}")
    print(f"\nNext: python3 judge_v2.py  (to quality-check transcriptions)")


if __name__ == "__main__":
    main()
