"""
Pilot experiment runner: 4 conditions × 10 pages.

Requires GEMINI_API_KEY environment variable.

Usage:
    GEMINI_API_KEY=your_key python run_pilot.py
    GEMINI_API_KEY=your_key python run_pilot.py --experiment A
    GEMINI_API_KEY=your_key python run_pilot.py --model gemini-3.1-pro-preview
    GEMINI_API_KEY=your_key python run_pilot.py --model gemini-3.1-flash-lite-preview
    GEMINI_API_KEY=your_key python run_pilot.py --dry-run

Models:
    gemini-3.1-flash-lite-preview  — cheapest, $0.25/$1.50 per 1M tokens (default)
    gemini-3.1-pro-preview         — best quality, $2/$12 per 1M tokens
"""

import argparse
import base64
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
    print("ERROR: Install google-genai: pip install google-genai")
    sys.exit(1)

# --- Configuration ---
BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"
STRIPS_DIR = BASE_DIR / "strips"
RESULTS_DIR = BASE_DIR / "results"
METADATA_PATH = BASE_DIR / "pilot_metadata.json"

DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
DELAY_BETWEEN_REQUESTS = 2.0  # seconds

# Model-specific settings
MODEL_CONFIGS = {
    "gemini-3.1-flash-lite-preview": {
        "thinking_level": "low",       # default is 'minimal', bump to 'low' for OCR quality
        "cost_per_1m_input": 0.25,
        "cost_per_1m_output": 1.50,
    },
    "gemini-3.1-pro-preview": {
        "thinking_level": "medium",    # default is 'high' but medium balances cost/quality for OCR
        "cost_per_1m_input": 2.00,
        "cost_per_1m_output": 12.00,
    },
}

# --- Prompts ---

SYSTEM_PROMPT_BASE = """You are an expert transcriber of handwritten mathematical manuscripts.

This is a scanned page from Alexandre Grothendieck's "La longue marche à travers la théorie de Galois" (1981), handwritten in French with dense mathematical notation.

## Your task
Transcribe this handwritten page into LaTeX, preserving:
1. ALL mathematical notation in LaTeX: $x^2$, $\\mathcal{O}_X$, $\\lim_{n \\to \\infty}$, etc.
2. French text exactly as written (preserve abbreviations like "hom.", "autom.", "resp.")
3. Page structure: section headers, numbered items, paragraph breaks
4. Commutative diagrams: describe as [DIAGRAM: brief description of arrows and objects]
5. Marginal notes: mark as [MARGIN: content]
6. Illegible text: mark as [unclear] or [unclear: best guess]

## Notation conventions in this manuscript
- Category theory: $\\mathcal{C}$, $\\hat{C}$ (presheaf category), arrows $\\to$, $\\hookrightarrow$
- Fundamental groupoid: $\\Pi_1(E)$, $\\pi_1$
- Decorators: hat ($\\hat{\\pi}$), tilde ($\\tilde{X}$), bar ($\\bar{k}$)
- Set notation: $(Ens)$ = category of sets, $Ob$ = objects

## Output format
- Pure LaTeX transcription, no commentary
- Use \\section{}, \\subsection{} for headers
- Use \\begin{equation}...\\end{equation} for displayed math
- Use inline $...$ for inline math
- Preserve Grothendieck's own numbering (Proposition 1.1, etc.)
"""

CONTEXT_PROMPT_TEMPLATE = """## Previous page transcription (for continuity)
The following is the transcription of the immediately preceding page. Use it to:
- Maintain consistent notation and symbol choices
- Understand ongoing mathematical arguments
- Resolve ambiguous handwriting using context

<previous_page>
{previous_transcription}
</previous_page>

Now transcribe the current page:
"""

STRIP_PROMPT_ADDITION = """## Important: This is a HORIZONTAL STRIP of a page
This image shows only a portion of the full page (one horizontal strip).
Transcribe only what you see in this strip. Do not try to complete sentences
that are cut off at the top or bottom — mark them as [continues above] or [continues below].
"""


def load_image_as_bytes(path: Path) -> bytes:
    """Load image file as bytes."""
    with open(path, 'rb') as f:
        return f.read()


def get_thinking_level(model: str) -> str:
    """Get appropriate thinking level for model."""
    if model in MODEL_CONFIGS:
        return MODEL_CONFIGS[model]["thinking_level"]
    # Sensible defaults
    if "flash-lite" in model:
        return "low"
    if "pro" in model:
        return "medium"
    return "low"


def transcribe_image(client, model: str, image_bytes: bytes, prompt: str,
                     mime_type: str = "image/png") -> dict:
    """Send image to Gemini for transcription.

    Uses Gemini 3 best practices:
    - temperature=1.0 (Gemini 3 default; lower values can cause looping)
    - media_resolution_high for images (1120 tokens, best for handwriting OCR)
    - thinking_level tuned per model
    """
    thinking_level = get_thinking_level(model)

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        types.Part.from_text(text=prompt),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=1.0,  # Gemini 3 default — do NOT lower, causes looping
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
            )
        )
        text = response.text if response.text else ""
        return {
            "status": "success",
            "transcription": text,
            "model": model,
            "thinking_level": thinking_level,
            "usage": {
                "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', None),
                "output_tokens": getattr(response.usage_metadata, 'candidates_token_count', None),
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "model": model,
        }


def run_experiment_A(client, model, pages, delay):
    """Full page, no context."""
    print("\n  Experiment A: Full page, no context")
    results = {}

    for page_num in pages:
        img_path = IMAGES_DIR / f"page_{page_num:04d}.png"
        if not img_path.exists():
            print(f"    Page {page_num}: SKIP (image not found)")
            continue

        img_bytes = load_image_as_bytes(img_path)
        prompt = SYSTEM_PROMPT_BASE + "\nTranscribe this page:"

        result = transcribe_image(client, model, img_bytes, prompt)
        results[page_num] = result
        status = result["status"]
        length = len(result.get("transcription", ""))
        print(f"    Page {page_num}: {status} ({length} chars)")

        time.sleep(delay)

    return results


def run_experiment_B(client, model, pages, delay):
    """Full page, with previous page context."""
    print("\n  Experiment B: Full page, with context")
    results = {}
    prev_transcription = None

    for page_num in pages:
        img_path = IMAGES_DIR / f"page_{page_num:04d}.png"
        if not img_path.exists():
            print(f"    Page {page_num}: SKIP (image not found)")
            continue

        img_bytes = load_image_as_bytes(img_path)

        if prev_transcription:
            context = CONTEXT_PROMPT_TEMPLATE.format(previous_transcription=prev_transcription)
            prompt = SYSTEM_PROMPT_BASE + "\n" + context
        else:
            prompt = SYSTEM_PROMPT_BASE + "\nTranscribe this page (this is the first page, no prior context):"

        result = transcribe_image(client, model, img_bytes, prompt)
        results[page_num] = result
        status = result["status"]
        length = len(result.get("transcription", ""))
        print(f"    Page {page_num}: {status} ({length} chars) {'[with context]' if prev_transcription else '[first page]'}")

        # Use this transcription as context for next page
        if result["status"] == "success":
            prev_transcription = result["transcription"]
        # If error, keep previous context

        time.sleep(delay)

    return results


def run_experiment_C(client, model, pages, delay):
    """Strips, no context."""
    print("\n  Experiment C: Strips, no context")
    results = {}

    for page_num in pages:
        page_results = {"strips": [], "merged": ""}

        # Find all strips for this page
        strip_paths = sorted(STRIPS_DIR.glob(f"page_{page_num:04d}_strip_*.png"))
        if not strip_paths:
            print(f"    Page {page_num}: SKIP (no strips found)")
            continue

        strip_texts = []
        for strip_path in strip_paths:
            strip_name = strip_path.stem
            img_bytes = load_image_as_bytes(strip_path)
            prompt = SYSTEM_PROMPT_BASE + "\n" + STRIP_PROMPT_ADDITION

            result = transcribe_image(client, model, img_bytes, prompt)
            page_results["strips"].append({
                "strip": strip_name,
                **result
            })

            if result["status"] == "success":
                strip_texts.append(result["transcription"])

            time.sleep(delay)

        # Simple merge: concatenate strips (overlap dedup would be a later refinement)
        page_results["merged"] = "\n\n% --- strip boundary ---\n\n".join(strip_texts)

        results[page_num] = page_results
        n_ok = sum(1 for s in page_results["strips"] if s["status"] == "success")
        print(f"    Page {page_num}: {n_ok}/{len(strip_paths)} strips OK, merged {len(page_results['merged'])} chars")

    return results


def run_experiment_D(client, model, pages, delay):
    """Strips, with previous page context."""
    print("\n  Experiment D: Strips, with context")
    results = {}
    prev_page_transcription = None

    for page_num in pages:
        page_results = {"strips": [], "merged": ""}

        strip_paths = sorted(STRIPS_DIR.glob(f"page_{page_num:04d}_strip_*.png"))
        if not strip_paths:
            print(f"    Page {page_num}: SKIP (no strips found)")
            continue

        strip_texts = []
        prev_strip_text = None

        for i, strip_path in enumerate(strip_paths):
            strip_name = strip_path.stem
            img_bytes = load_image_as_bytes(strip_path)

            # Build prompt with available context
            prompt = SYSTEM_PROMPT_BASE + "\n" + STRIP_PROMPT_ADDITION

            context_parts = []
            if i == 0 and prev_page_transcription:
                context_parts.append(
                    f"## Context from previous page\n<previous_page>\n{prev_page_transcription[-2000:]}\n</previous_page>"
                )
            if prev_strip_text:
                context_parts.append(
                    f"## Context from previous strip (above this one)\n<previous_strip>\n{prev_strip_text}\n</previous_strip>"
                )

            if context_parts:
                prompt += "\n" + "\n\n".join(context_parts)

            prompt += "\n\nTranscribe this strip:"

            result = transcribe_image(client, model, img_bytes, prompt)
            page_results["strips"].append({
                "strip": strip_name,
                **result
            })

            if result["status"] == "success":
                strip_texts.append(result["transcription"])
                prev_strip_text = result["transcription"]

            time.sleep(delay)

        page_results["merged"] = "\n\n% --- strip boundary ---\n\n".join(strip_texts)
        results[page_num] = page_results

        # Use merged result as context for next page
        if strip_texts:
            prev_page_transcription = page_results["merged"]

        n_ok = sum(1 for s in page_results["strips"] if s["status"] == "success")
        ctx_label = "[with page context]" if prev_page_transcription else "[first page]"
        print(f"    Page {page_num}: {n_ok}/{len(strip_paths)} strips OK, merged {len(page_results['merged'])} chars {ctx_label}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Run Grothendieck OCR pilot experiments")
    parser.add_argument("--experiment", choices=["A", "B", "C", "D"], help="Run only this experiment")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL})")
    parser.add_argument("--delay", type=float, default=DELAY_BETWEEN_REQUESTS, help="Delay between API calls (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--group", choices=["a", "b", "both"], default="both", help="Page group to run")
    parser.add_argument("--both-models", action="store_true",
                        help="Run with both gemini-3.1-flash-lite-preview AND gemini-3.1-pro-preview")
    args = parser.parse_args()

    # Load metadata
    if not METADATA_PATH.exists():
        print("ERROR: Run prepare.py first to generate pilot assets")
        sys.exit(1)

    with open(METADATA_PATH) as f:
        metadata = json.load(f)

    # Determine which pages to run
    if args.group == "a":
        pages = metadata["benchmark_pages"]["group_a"]
    elif args.group == "b":
        pages = metadata["benchmark_pages"]["group_b"]
    else:
        pages = metadata["all_pages"]

    # Determine which experiments to run
    experiments = ["A", "B", "C", "D"]
    if args.experiment:
        experiments = [args.experiment]

    # Count API calls
    n_pages = len(pages)
    n_strips = metadata["settings"]["num_strips"]
    call_counts = {
        "A": n_pages,
        "B": n_pages,
        "C": n_pages * n_strips,
        "D": n_pages * n_strips,
    }
    total_calls = sum(call_counts[e] for e in experiments)

    print("=" * 60)
    print("GROTHENDIECK OCR PILOT — Experiment Runner")
    print("=" * 60)
    print(f"  Model:       {args.model}")
    print(f"  Pages:       {pages}")
    print(f"  Experiments: {experiments}")
    print(f"  API calls:   {total_calls}")
    print(f"  Delay:       {args.delay}s between calls")
    thinking_lvl = get_thinking_level(args.model)
    print(f"  Thinking:    {thinking_lvl}")
    print(f"  Est. time:   ~{total_calls * (args.delay + 5):.0f}s ({total_calls * (args.delay + 5) / 60:.1f} min)")

    if args.both_models:
        print("\n  === BOTH MODELS MODE ===")
        print("  Will run all experiments with Flash-Lite first, then Pro.\n")

    if args.dry_run:
        print("\n  [DRY RUN — not executing]")
        for exp in experiments:
            print(f"    Experiment {exp}: {call_counts[exp]} calls")
        if args.both_models:
            print(f"    × 2 models = {total_calls * 2} total calls")
        return

    # Check API key (only needed for actual runs)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY environment variable")
        print("  export GEMINI_API_KEY=your_key_here")
        sys.exit(1)

    # Initialize client
    client = genai.Client(api_key=api_key)

    # Handle --both-models by recursively running with each model
    if args.both_models:
        import subprocess
        env = os.environ.copy()
        base_cmd = [sys.executable, __file__]
        if args.experiment:
            base_cmd += ["--experiment", args.experiment]
        base_cmd += ["--delay", str(args.delay), "--group", args.group]

        for model_id in ["gemini-3.1-flash-lite-preview", "gemini-3.1-pro-preview"]:
            print(f"\n{'#'*60}")
            print(f"# Running with: {model_id}")
            print(f"{'#'*60}")
            cmd = base_cmd + ["--model", model_id]
            subprocess.run(cmd, env=env)

        print(f"\n{'#'*60}")
        print("# Both models complete! Compare results directories.")
        print(f"{'#'*60}")
        return

    # Create results directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_DIR / f"run_{timestamp}_{args.model.replace('/', '_')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    all_results = {
        "timestamp": timestamp,
        "model": args.model,
        "pages": pages,
        "experiments": {},
    }

    # Run experiments
    start_time = time.time()

    experiment_runners = {
        "A": run_experiment_A,
        "B": run_experiment_B,
        "C": run_experiment_C,
        "D": run_experiment_D,
    }

    for exp_id in experiments:
        print(f"\n{'='*40}")
        print(f"Running Experiment {exp_id}")
        print(f"{'='*40}")

        runner = experiment_runners[exp_id]
        exp_results = runner(client, args.model, pages, args.delay)
        all_results["experiments"][exp_id] = exp_results

        # Save intermediate results
        with open(run_dir / f"experiment_{exp_id}.json", 'w', encoding='utf-8') as f:
            json.dump(exp_results, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time

    # Save combined results
    all_results["elapsed_seconds"] = elapsed
    with open(run_dir / "all_results.json", 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # Also save human-readable transcriptions
    for exp_id, exp_results in all_results["experiments"].items():
        with open(run_dir / f"transcriptions_{exp_id}.txt", 'w', encoding='utf-8') as f:
            f.write(f"Experiment {exp_id} — {args.model}\n")
            f.write(f"{'=' * 60}\n\n")

            for page_num in sorted(exp_results.keys(), key=lambda x: int(x)):
                result = exp_results[page_num]

                if isinstance(result, dict) and "merged" in result:
                    # Strip experiment
                    f.write(f"\n{'='*40}\n")
                    f.write(f"PAGE {page_num} (merged from strips)\n")
                    f.write(f"{'='*40}\n\n")
                    f.write(result["merged"])
                elif isinstance(result, dict) and "transcription" in result:
                    f.write(f"\n{'='*40}\n")
                    f.write(f"PAGE {page_num}\n")
                    f.write(f"{'='*40}\n\n")
                    f.write(result.get("transcription", "[ERROR]"))

                f.write("\n\n")

    # Summary
    print(f"\n{'='*60}")
    print("PILOT COMPLETE")
    print(f"{'='*60}")
    print(f"  Time elapsed: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"  Results dir:  {run_dir}")
    print(f"  Files:")
    for f in sorted(run_dir.iterdir()):
        size = f.stat().st_size
        print(f"    {f.name} ({size:,} bytes)")

    print(f"\n  Next step: Run evaluate.py to compare against reference")


if __name__ == "__main__":
    main()
