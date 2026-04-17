"""
Benchmark V2: systematic evaluation across prompt, model, format, context, and pass modes.

Dimensions:
- 8 prompt styles (3 base × fewshot + 2 two-pass)
- 2 models (flash-lite, pro)
- 3 input formats (png-300dpi, png-150dpi, pdf-direct)
- Multi-page context (0 or 1 previous page image)
- Two-pass (via prompt style)

Smart phased presets avoid full cross-product.

Usage:
    GEMINI_API_KEY=key python3 run_benchmark_v2.py --list-presets
    GEMINI_API_KEY=key python3 run_benchmark_v2.py --preset phase-a --dry-run
    GEMINI_API_KEY=key python3 run_benchmark_v2.py --preset phase-a
    GEMINI_API_KEY=key python3 run_benchmark_v2.py --resume results_v2/run_...
"""

import argparse
import io
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
    import fitz  # PyMuPDF — for PDF page extraction and on-the-fly rendering
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None

from prompts_v2 import PROMPT_CONFIGS, get_prompt

# --- Paths ---
BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent.parent
IMAGES_DIR = BASE_DIR / "images"
IMAGES_150_DIR = BASE_DIR / "images_150dpi"
RESULTS_V2_DIR = BASE_DIR / "results_v2"
SCAN_PDF = PROJECT_DIR / "raw_pdf" / "140-2.pdf"

# Header/footer crop ratios (archive watermarks) — same as prepare.py
HEADER_CROP_RATIO = 0.04
FOOTER_CROP_RATIO = 0.05

# --- Models ---
MODELS = {
    "flash-lite": {
        "id": "gemini-3.1-flash-lite-preview",
        "thinking_levels": ["low", "medium"],
        "cost_input": 0.25,
        "cost_output": 1.50,
    },
    "pro": {
        "id": "gemini-3.1-pro-preview",
        "thinking_levels": ["medium", "high"],
        "cost_input": 2.00,
        "cost_output": 12.00,
    },
}

# Pages with alignment hints (from evaluate_v2.py)
BENCHMARK_PAGES = [5, 50, 51, 52, 53, 54]
# Consecutive pairs for multi-page testing (page, predecessor)
CONSECUTIVE_PAIRS = {5: 4, 52: 51, 54: 53}

DELAY = 2.0


# =============================================================================
# INPUT FORMAT HELPERS
# =============================================================================

def _render_pdf_page(page_idx: int, dpi: int = 300) -> bytes:
    """Render a PDF page to PNG bytes at given DPI, with watermark cropping."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) required for PDF rendering. pip install pymupdf")
    if Image is None:
        raise RuntimeError("Pillow required. pip install Pillow")

    doc = fitz.open(str(SCAN_PDF))
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    doc.close()

    # Crop archive watermarks
    w, h = img.size
    top = int(h * HEADER_CROP_RATIO)
    bottom = int(h * (1 - FOOTER_CROP_RATIO))
    img = img.crop((0, top, w, bottom))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _extract_pdf_page_bytes(page_idx: int) -> bytes:
    """Extract a single PDF page as a standalone PDF (bytes)."""
    if fitz is None:
        raise RuntimeError("PyMuPDF required for PDF extraction")

    doc = fitz.open(str(SCAN_PDF))
    single = fitz.open()
    single.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
    pdf_bytes = single.tobytes()
    single.close()
    doc.close()
    return pdf_bytes


def get_page_input(page_num: int, input_format: str) -> tuple:
    """Get (data_bytes, mime_type) for a page in the requested format.

    input_format: "png300", "png150", "pdf"
    """
    # scan page index: page_num maps to scan_page_idx = page_num (0-indexed)
    scan_idx = page_num

    if input_format == "png300":
        img_path = IMAGES_DIR / f"page_{page_num:04d}.png"
        if img_path.exists():
            with open(img_path, "rb") as f:
                return f.read(), "image/png"
        # Fallback: render on the fly
        return _render_pdf_page(scan_idx, dpi=300), "image/png"

    elif input_format == "png150":
        # Check cache
        img_path = IMAGES_150_DIR / f"page_{page_num:04d}.png"
        if img_path.exists():
            with open(img_path, "rb") as f:
                return f.read(), "image/png"
        # Render and cache
        IMAGES_150_DIR.mkdir(parents=True, exist_ok=True)
        data = _render_pdf_page(scan_idx, dpi=150)
        with open(img_path, "wb") as f:
            f.write(data)
        return data, "image/png"

    elif input_format == "pdf":
        return _extract_pdf_page_bytes(scan_idx), "application/pdf"

    else:
        raise ValueError(f"Unknown input format: {input_format}")


# =============================================================================
# PRESETS — smart phased experimental design
# =============================================================================

ALL_PROMPT_STYLES = list(PROMPT_CONFIGS.keys())

PRESETS = {
    # --- Quick sanity check ---
    "quick": {
        "description": "Sanity check: 3 base prompts × flash-lite × page 5",
        "conditions": [
            {"prompts": ["text-first", "latex-direct", "text-inline"],
             "models": ["flash-lite"], "thinking": {"flash-lite": "low"},
             "format": "png300", "n_prev_images": 0},
        ],
        "pages": [5],
    },

    # --- Phase A: Prompt sweep (the most important variable) ---
    "phase-a": {
        "description": "All 8 prompts × flash-lite × 3 pages = 24 calls",
        "conditions": [
            {"prompts": ALL_PROMPT_STYLES,
             "models": ["flash-lite"], "thinking": {"flash-lite": "low"},
             "format": "png300", "n_prev_images": 0},
        ],
        "pages": [5, 50, 54],
    },

    # --- Phase B: Model comparison (top prompts × both models) ---
    "phase-b": {
        "description": "Top 3 prompts × 2 models × 3 pages = 18 calls (9 new if phase-a done)",
        "conditions": [
            {"prompts": ["text-first", "text-first-fewshot", "two-pass"],
             "models": ["flash-lite", "pro"],
             "thinking": {"flash-lite": "low", "pro": "medium"},
             "format": "png300", "n_prev_images": 0},
        ],
        "pages": [5, 50, 54],
    },

    # --- Phase C: Input format (png300 vs png150 vs pdf) ---
    "phase-c": {
        "description": "Best prompt × 3 formats × 2 models × 2 pages = 12 calls (4 new)",
        "conditions": [
            {"prompts": ["text-first-fewshot"],
             "models": ["flash-lite", "pro"],
             "thinking": {"flash-lite": "low", "pro": "medium"},
             "format": fmt, "n_prev_images": 0}
            for fmt in ["png300", "png150", "pdf"]
        ],
        "pages": [5, 54],
    },

    # --- Phase D: Multi-page context (0 vs 1 previous image) ---
    "phase-d": {
        "description": "Best prompt × 2 context modes × 2 models × 3 pages = 12 calls (6 new)",
        "conditions": [
            {"prompts": ["text-first-fewshot"],
             "models": ["flash-lite", "pro"],
             "thinking": {"flash-lite": "low", "pro": "medium"},
             "format": "png300", "n_prev_images": n}
            for n in [0, 1]
        ],
        "pages": [5, 52, 54],  # These have predecessors: 4, 51, 53
    },

    # --- Full: Phase A + B combined ---
    "full": {
        "description": "8 prompts × 2 models × 3 pages = 48 calls",
        "conditions": [
            {"prompts": ALL_PROMPT_STYLES,
             "models": ["flash-lite", "pro"],
             "thinking": {"flash-lite": "low", "pro": "medium"},
             "format": "png300", "n_prev_images": 0},
        ],
        "pages": [5, 50, 54],
    },

    # --- All phases combined ---
    "all-phases": {
        "description": "Phases A+B+C+D combined = ~60 unique calls",
        "conditions": [
            # Phase A: all prompts, flash-lite
            {"prompts": ALL_PROMPT_STYLES,
             "models": ["flash-lite"], "thinking": {"flash-lite": "low"},
             "format": "png300", "n_prev_images": 0},
            # Phase B: top prompts, both models
            {"prompts": ["text-first", "text-first-fewshot", "two-pass"],
             "models": ["pro"], "thinking": {"pro": "medium"},
             "format": "png300", "n_prev_images": 0},
            # Phase C: format tests
            {"prompts": ["text-first-fewshot"],
             "models": ["flash-lite", "pro"],
             "thinking": {"flash-lite": "low", "pro": "medium"},
             "format": "png150", "n_prev_images": 0},
            {"prompts": ["text-first-fewshot"],
             "models": ["flash-lite", "pro"],
             "thinking": {"flash-lite": "low", "pro": "medium"},
             "format": "pdf", "n_prev_images": 0},
            # Phase D: multi-page
            {"prompts": ["text-first-fewshot"],
             "models": ["flash-lite", "pro"],
             "thinking": {"flash-lite": "low", "pro": "medium"},
             "format": "png300", "n_prev_images": 1},
        ],
        "pages": [5, 50, 52, 54],
    },
}


# =============================================================================
# CONDITION BUILDING
# =============================================================================

def make_condition_key(prompt: str, model: str, thinking: str,
                       fmt: str, n_prev: int) -> str:
    return f"{prompt}__{model}__{thinking}__{fmt}__{n_prev}img"


def expand_preset(preset_name: str) -> tuple:
    """Expand a preset into (conditions_list, pages).

    Returns list of (key, prompt, model_short, model_id, thinking, format, n_prev_images)
    """
    preset = PRESETS[preset_name]
    pages = preset["pages"]

    seen = set()
    conditions = []

    for cond_spec in preset["conditions"]:
        for prompt in cond_spec["prompts"]:
            for model_short in cond_spec["models"]:
                model_id = MODELS[model_short]["id"]
                thinking = cond_spec["thinking"].get(model_short, "low")
                fmt = cond_spec["format"]
                n_prev = cond_spec["n_prev_images"]

                key = make_condition_key(prompt, model_short, thinking, fmt, n_prev)
                if key not in seen:
                    seen.add(key)
                    conditions.append((key, prompt, model_short, model_id,
                                       thinking, fmt, n_prev))

    return conditions, pages


def build_conditions_from_args(args) -> tuple:
    """Build conditions from CLI arguments."""
    prompts = [args.prompt] if args.prompt else ALL_PROMPT_STYLES
    models = [args.model] if args.model else ["flash-lite"]
    fmt = args.format or "png300"
    n_prev = args.multi_page or 0

    conditions = []
    for prompt in prompts:
        for model_short in models:
            model_id = MODELS[model_short]["id"]
            if args.thinking:
                thinking = args.thinking
            else:
                thinking = MODELS[model_short]["thinking_levels"][0]
            key = make_condition_key(prompt, model_short, thinking, fmt, n_prev)
            conditions.append((key, prompt, model_short, model_id,
                               thinking, fmt, n_prev))

    pages = [int(p) for p in args.pages.split(",")] if args.pages else [5, 50, 54]
    return conditions, pages


# =============================================================================
# TRANSCRIPTION
# =============================================================================

def transcribe(client, model_id: str, thinking_level: str,
               system_prompt: str, content_parts: list) -> dict:
    """Run a single transcription call.

    content_parts: list of types.Part objects (images + text)
    """
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=[types.Content(parts=content_parts)],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=1.0,
                max_output_tokens=8192,
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


def build_content_parts(page_num: int, input_format: str,
                        n_prev_images: int, user_text: str) -> list:
    """Build the content parts list for an API call.

    Handles multi-image by prepending previous page images.
    """
    parts = []

    # Add previous page images if requested
    if n_prev_images > 0:
        predecessor = CONSECUTIVE_PAIRS.get(page_num)
        if predecessor:
            for offset in range(n_prev_images, 0, -1):
                prev_page = page_num - offset
                # Only add if we have the predecessor
                if prev_page >= 1:
                    try:
                        prev_data, prev_mime = get_page_input(prev_page, input_format)
                        parts.append(types.Part.from_bytes(data=prev_data, mime_type=prev_mime))
                        if offset == n_prev_images:
                            parts.append(types.Part.from_text(
                                text=f"[Previous page {prev_page} shown above for context]"
                            ))
                    except Exception:
                        pass  # Skip if predecessor not available

    # Add current page
    curr_data, curr_mime = get_page_input(page_num, input_format)
    parts.append(types.Part.from_bytes(data=curr_data, mime_type=curr_mime))
    parts.append(types.Part.from_text(text=user_text))

    return parts


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_benchmark(client, conditions, pages, delay, run_dir, existing_results=None):
    """Execute all benchmark conditions."""
    results = existing_results or {}

    # Count total and done
    total = len(conditions) * len(pages)
    done = 0
    for key, *_ in conditions:
        for p in pages:
            if key in results and str(p) in results.get(key, {}).get("pages", {}):
                done += 1
    remaining = total - done

    print(f"\n  Total: {total} | Done: {done} | Remaining: {remaining}")
    print(f"  Est. time: ~{remaining * (delay + 6):.0f}s ({remaining * (delay + 6) / 60:.1f} min)")
    print()

    i = 0
    for key, prompt_style, model_short, model_id, thinking, fmt, n_prev in conditions:
        if key not in results:
            results[key] = {
                "prompt_style": prompt_style,
                "model": model_short,
                "model_id": model_id,
                "thinking_level": thinking,
                "input_format": fmt,
                "n_prev_images": n_prev,
                "pages": {},
            }

        for page_num in sorted(pages):
            pkey = str(page_num)
            i += 1

            if pkey in results[key]["pages"]:
                print(f"  [{i}/{total}] {key} p{page_num}: SKIP (done)")
                continue

            # Build prompt
            system_prompt, user_text = get_prompt(prompt_style)

            # Build content parts (handles multi-image + format)
            try:
                content_parts = build_content_parts(page_num, fmt, n_prev, user_text)
            except Exception as e:
                print(f"  [{i}/{total}] {key} p{page_num}: SKIP ({e})")
                continue

            # Transcribe
            print(f"  [{i}/{total}] {key} p{page_num}...", end="", flush=True)
            result = transcribe(client, model_id, thinking, system_prompt, content_parts)

            results[key]["pages"][pkey] = result
            length = len(result.get("transcription", ""))
            tokens_in = result.get("usage", {}).get("prompt_tokens", "?")
            print(f" {result['status']} ({length}ch, {tokens_in}tok_in)")

            # Save after each call
            with open(run_dir / "benchmark_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            time.sleep(delay)

    return results


# =============================================================================
# OUTPUT
# =============================================================================

def print_summary(results):
    print(f"\n{'='*95}")
    print("BENCHMARK V2 RESULTS")
    print(f"{'='*95}")
    print(f"{'Condition':<55} {'Pages':>5} {'AvgLen':>7} {'AvgTokIn':>9} {'Err':>4}")
    print("-" * 85)

    for key in sorted(results.keys()):
        data = results[key]
        pages = data.get("pages", {})
        n = len(pages)
        lengths = [len(p.get("transcription", ""))
                    for p in pages.values() if p.get("status") == "success"]
        tok_ins = [p.get("usage", {}).get("prompt_tokens", 0)
                   for p in pages.values() if p.get("status") == "success"]
        errors = sum(1 for p in pages.values() if p.get("status") == "error")
        avg_len = sum(lengths) / len(lengths) if lengths else 0
        avg_tok = sum(tok_ins) / len(tok_ins) if tok_ins else 0

        print(f"  {key:<53} {n:>5} {avg_len:>6.0f} {avg_tok:>8.0f} {errors:>4}")


def save_transcriptions(results, run_dir):
    """Save human-readable transcription files."""
    txn_dir = run_dir / "transcriptions"
    txn_dir.mkdir(exist_ok=True)

    for cond_key, data in results.items():
        with open(txn_dir / f"{cond_key}.txt", "w", encoding="utf-8") as f:
            f.write(f"Condition: {cond_key}\n")
            f.write(f"Prompt: {data['prompt_style']}, Model: {data['model']}, "
                    f"Thinking: {data['thinking_level']}, "
                    f"Format: {data.get('input_format', 'png300')}, "
                    f"PrevImages: {data.get('n_prev_images', 0)}\n")
            f.write("=" * 60 + "\n\n")

            for pkey in sorted(data.get("pages", {}), key=int):
                page = data["pages"][pkey]
                f.write(f"\n{'='*40}\n")
                f.write(f"PAGE {pkey} — {page.get('status', '?')}\n")
                f.write(f"{'='*40}\n\n")
                text = page.get("transcription", "[no output]")

                # For two-pass: highlight the pass boundary
                if "---PASS2---" in text:
                    parts = text.split("---PASS2---", 1)
                    f.write("=== PASS 1 (Raw Reading) ===\n\n")
                    f.write(parts[0].strip())
                    f.write("\n\n=== PASS 2 (Clean Output) ===\n\n")
                    f.write(parts[1].strip())
                else:
                    f.write(text)
                f.write("\n\n")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark V2: prompt × model × format × context evaluation")

    # Preset or manual
    parser.add_argument("--preset", choices=list(PRESETS.keys()))
    parser.add_argument("--prompt", choices=list(PROMPT_CONFIGS.keys()))
    parser.add_argument("--model", choices=["flash-lite", "pro"])
    parser.add_argument("--thinking", choices=["low", "medium", "high"])
    parser.add_argument("--format", choices=["png300", "png150", "pdf"])
    parser.add_argument("--multi-page", type=int, choices=[0, 1, 2], default=0)
    parser.add_argument("--pages", help="Comma-separated page numbers")

    # Execution
    parser.add_argument("--delay", type=float, default=DELAY)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", help="Resume from existing run directory")
    parser.add_argument("--list-presets", action="store_true")

    args = parser.parse_args()

    if args.list_presets:
        print("Available presets:\n")
        for name, preset in PRESETS.items():
            conditions, pages = expand_preset(name)
            n_calls = len(conditions) * len(pages)
            print(f"  {name:<16} {n_calls:>4} calls — {preset['description']}")
        return

    # Build conditions
    if args.preset:
        conditions, pages = expand_preset(args.preset)
    else:
        conditions, pages = build_conditions_from_args(args)

    total_calls = len(conditions) * len(pages)

    print("=" * 70)
    print("BENCHMARK V2 — Multi-Dimensional Evaluation")
    print("=" * 70)
    if args.preset:
        print(f"  Preset:     {args.preset} — {PRESETS[args.preset]['description']}")
    print(f"  Conditions: {len(conditions)}")
    print(f"  Pages:      {pages}")
    print(f"  Total calls: {total_calls}")

    # Group by dimension for readability
    formats_used = set(c[5] for c in conditions)
    multi_used = set(c[6] for c in conditions)
    print(f"  Formats:    {sorted(formats_used)}")
    print(f"  Multi-page: {sorted(multi_used)}")

    print(f"\n  Conditions:")
    for key, prompt, model_s, model_id, think, fmt, nprev in conditions:
        print(f"    {key}")

    if args.dry_run:
        print(f"\n  [DRY RUN]")
        for model_s in set(c[2] for c in conditions):
            model_calls = sum(1 for c in conditions if c[2] == model_s) * len(pages)
            cfg = MODELS[model_s]
            # Input tokens vary by format/multi-page but ~1500-3000 per call
            avg_input = 2000 if any(c[6] > 0 for c in conditions) else 1500
            est = model_calls * (avg_input * cfg["cost_input"] + 2000 * cfg["cost_output"]) / 1_000_000
            print(f"    {model_s}: {model_calls} calls ≈ ${est:.2f}")
        return

    # API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Setup run directory
    existing = None
    if args.resume:
        run_dir = Path(args.resume)
        if not run_dir.exists():
            run_dir = RESULTS_V2_DIR / args.resume
        rf = run_dir / "benchmark_results.json"
        if rf.exists():
            with open(rf, encoding="utf-8") as f:
                existing = json.load(f)
            print(f"\n  Resuming: {len(existing)} conditions loaded")
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = f"_{args.preset}" if args.preset else ""
        run_dir = RESULTS_V2_DIR / f"run_{ts}{tag}"

    run_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    config = {
        "timestamp": datetime.now().isoformat(),
        "preset": args.preset,
        "pages": pages,
        "conditions": [
            {"key": k, "prompt": p, "model": m, "thinking": t,
             "format": fmt, "n_prev_images": n}
            for k, p, m, _, t, fmt, n in conditions
        ],
    }
    with open(run_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # Run
    start = time.time()
    results = run_benchmark(client, conditions, pages, args.delay, run_dir, existing)
    elapsed = time.time() - start

    # Save final
    with open(run_dir / "benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    save_transcriptions(results, run_dir)
    print_summary(results)

    print(f"\n  Elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Results: {run_dir}")
    print(f"\n  Next steps:")
    print(f"    python3 evaluate_v2.py --benchmark-only    # string-matching scores")
    print(f"    python3 judge_v2.py {run_dir.name}         # LLM-as-judge evaluation")


if __name__ == "__main__":
    main()
