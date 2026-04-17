"""
LLM-as-judge evaluation for benchmark V2.

Replaces brittle string matching with structured LLM evaluation.
Uses a cheap model (flash-lite) to rate transcriptions against reference
on multiple dimensions.

Usage:
    GEMINI_API_KEY=key python3 judge_v2.py                        # judge all runs
    GEMINI_API_KEY=key python3 judge_v2.py run_20260305_phase-a   # judge specific run
    GEMINI_API_KEY=key python3 judge_v2.py --rejudge              # re-evaluate all
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: pip install google-genai")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
REFERENCE_DIR = BASE_DIR / "reference"
RESULTS_V2_DIR = BASE_DIR / "results_v2"

JUDGE_MODEL = "gemini-3.1-flash-lite-preview"
DELAY = 1.0

# Page alignment hints (from evaluate_v2.py)
PAGE_ALIGNMENT_HINTS = {
    5: [6, 7, 8],
    50: [30, 31, 32, 33, 34, 35],
    51: [33, 34, 35, 36, 37],
    52: [34, 35, 36, 37],
    53: [35, 36, 37],
    54: [38, 39, 40, 41],
}

JUDGE_PROMPT = """You are evaluating OCR transcription quality of a handwritten French mathematical manuscript (Grothendieck's "La longue marche", 1981).

## Reference text
This is from a published typeset edition of the same content (may not be a perfect page-level match, but covers the same mathematical material):

<reference>
{reference}
</reference>

## Transcription to evaluate
This was produced by a VLM reading the handwritten original:

<transcription>
{transcription}
</transcription>

## Rating dimensions
Rate each dimension 1-5:

1. **text_accuracy**: Are French words correctly transcribed?
   5=perfect, 4=minor errors (accents, abbreviations), 3=some wrong words, 2=many errors, 1=mostly wrong

2. **math_accuracy**: Are mathematical expressions correctly captured?
   5=all formulas correct, 4=minor notation differences ($E$ vs $\\mathcal{{E}}$), 3=some wrong symbols, 2=many formula errors, 1=math mostly wrong

3. **completeness**: Is all content from the reference captured in the transcription?
   5=nothing missing, 4=minor omissions, 3=some content missing, 2=significant gaps, 1=mostly incomplete

4. **formatting_quality**: Is the output clean and usable?
   5=clean minimal formatting, 4=slight excess formatting, 3=moderate clutter, 2=heavy layout noise (\\hfill etc.), 1=unreadable

5. **overall**: Holistic quality assessment.
   5=publication-ready, 4=good with minor fixes, 3=usable but needs editing, 2=poor, 1=unusable

## Important notes
- The reference is from a TYPESET version, the transcription is from HANDWRITTEN. Some differences are expected.
- Focus on whether the CONTENT is captured correctly, not whether formatting matches.
- Mathematical notation differences like $E$ vs $\\mathcal{{E}}$ are MINOR (score 4, not 3).
- If the transcription contains a two-pass output (PASS 1 + PASS 2), evaluate PASS 2 only.

Output valid JSON only (no markdown, no explanation outside JSON):
{{"text_accuracy": <1-5>, "math_accuracy": <1-5>, "completeness": <1-5>, "formatting_quality": <1-5>, "overall": <1-5>, "notes": "<1-2 sentences>"}}"""


def load_reference() -> dict:
    """Load reference texts (VLM preferred, fitz fallback)."""
    fitz_path = REFERENCE_DIR / "g103d_full_text.json"
    with open(fitz_path, encoding="utf-8") as f:
        fitz_ref = json.load(f)

    vlm_path = REFERENCE_DIR / "g103d_vlm_text.json"
    vlm_ref = {}
    if vlm_path.exists():
        with open(vlm_path, encoding="utf-8") as f:
            vlm_data = json.load(f)
        for pkey, entry in vlm_data.items():
            raw = entry.get("raw", "")
            if raw and len(raw) > 200:
                vlm_ref[pkey] = raw
            else:
                latex = entry.get("latex", "")
                if latex and len(latex) > 200:
                    vlm_ref[pkey] = latex

    ref = dict(fitz_ref)
    ref.update(vlm_ref)
    return ref


def get_reference_for_page(page_num: int, reference: dict) -> str:
    """Get the best reference text for a given manuscript page."""
    hints = PAGE_ALIGNMENT_HINTS.get(page_num, [])
    if not hints:
        return ""

    # Concatenate hint pages (they overlap but that's fine for judging)
    texts = []
    for h in hints[:3]:  # Max 3 reference pages to keep prompt manageable
        if str(h) in reference:
            texts.append(reference[str(h)][:2000])

    return "\n\n---\n\n".join(texts) if texts else ""


def extract_pass2(transcription: str) -> str:
    """Extract Pass 2 from a two-pass transcription."""
    if "---PASS2---" in transcription:
        return transcription.split("---PASS2---", 1)[1].strip()
    # Try variations
    for marker in ["--- PASS 2 ---", "PASS 2", "## PASS 2", "### Clean"]:
        if marker in transcription:
            return transcription.split(marker, 1)[1].strip()
    return transcription


def judge_single(client, transcription: str, reference: str) -> dict:
    """Judge a single transcription against reference."""
    # For two-pass, evaluate only pass 2
    eval_text = extract_pass2(transcription)

    prompt = JUDGE_PROMPT.format(
        reference=reference[:4000],
        transcription=eval_text[:4000],
    )

    try:
        response = client.models.generate_content(
            model=JUDGE_MODEL,
            contents=[types.Content(parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=500,
            )
        )

        text = response.text.strip() if response.text else ""

        # Parse JSON from response (handle markdown wrapping)
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        scores = json.loads(text)

        # Validate
        for key in ["text_accuracy", "math_accuracy", "completeness",
                     "formatting_quality", "overall"]:
            if key not in scores:
                scores[key] = 0
            scores[key] = max(1, min(5, int(scores[key])))

        scores["status"] = "success"
        return scores

    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"JSON parse: {e}", "raw": text}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def judge_run(client, run_dir: Path, reference: dict, rejudge: bool = False) -> dict:
    """Judge all transcriptions in a benchmark run."""
    results_file = run_dir / "benchmark_results.json"
    if not results_file.exists():
        print(f"  No results in {run_dir.name}")
        return {}

    with open(results_file, encoding="utf-8") as f:
        bench_results = json.load(f)

    # Load existing judgments
    judge_file = run_dir / "judge_results.json"
    judgments = {}
    if judge_file.exists() and not rejudge:
        with open(judge_file, encoding="utf-8") as f:
            judgments = json.load(f)

    total = sum(len(d.get("pages", {})) for d in bench_results.values())
    done = sum(len(v) for v in judgments.values())
    print(f"\n  Run: {run_dir.name}")
    print(f"  Transcriptions: {total} | Already judged: {done}")

    i = 0
    for cond_key, cond_data in sorted(bench_results.items()):
        if cond_key not in judgments:
            judgments[cond_key] = {}

        for pkey, page_data in sorted(cond_data.get("pages", {}).items()):
            i += 1

            if pkey in judgments[cond_key] and not rejudge:
                continue

            transcription = page_data.get("transcription", "")
            if not transcription or page_data.get("status") != "success":
                judgments[cond_key][pkey] = {"status": "skipped", "reason": "no transcription"}
                continue

            page_num = int(pkey)
            ref_text = get_reference_for_page(page_num, reference)
            if not ref_text:
                judgments[cond_key][pkey] = {"status": "skipped", "reason": "no reference"}
                continue

            print(f"  [{i}/{total}] {cond_key} p{pkey}...", end="", flush=True)
            result = judge_single(client, transcription, ref_text)
            judgments[cond_key][pkey] = result

            if result.get("status") == "success":
                print(f" overall={result['overall']}/5 text={result['text_accuracy']} "
                      f"math={result['math_accuracy']}")
            else:
                print(f" ERROR: {result.get('error', '?')}")

            # Save after each
            with open(judge_file, "w", encoding="utf-8") as f:
                json.dump(judgments, f, ensure_ascii=False, indent=2)

            time.sleep(DELAY)

    return judgments


def print_judge_summary(judgments: dict):
    """Print ranked summary of judge results."""
    print(f"\n{'='*100}")
    print("LLM JUDGE RESULTS (ranked by overall score)")
    print(f"{'='*100}")
    print(f"{'Condition':<55} {'Overall':>7} {'Text':>6} {'Math':>6} {'Compl':>6} {'Fmt':>6} {'N':>3}")
    print("-" * 95)

    # Aggregate per condition
    cond_scores = {}
    for cond_key, pages in judgments.items():
        scores = [v for v in pages.values()
                  if isinstance(v, dict) and v.get("status") == "success"]
        if not scores:
            continue

        avg = lambda key: sum(s[key] for s in scores) / len(scores)
        cond_scores[cond_key] = {
            "overall": avg("overall"),
            "text_accuracy": avg("text_accuracy"),
            "math_accuracy": avg("math_accuracy"),
            "completeness": avg("completeness"),
            "formatting_quality": avg("formatting_quality"),
            "n": len(scores),
        }

    # Sort by overall
    for key, s in sorted(cond_scores.items(), key=lambda x: -x[1]["overall"]):
        print(f"  {key:<53} {s['overall']:>6.1f} {s['text_accuracy']:>5.1f} "
              f"{s['math_accuracy']:>5.1f} {s['completeness']:>5.1f} "
              f"{s['formatting_quality']:>5.1f} {s['n']:>3}")

    # Also print per-page breakdown for top 5
    print(f"\n  Per-page detail (top 5 conditions):")
    top5 = sorted(cond_scores.items(), key=lambda x: -x[1]["overall"])[:5]
    for cond_key, _ in top5:
        print(f"\n  {cond_key}:")
        for pkey, score in sorted(judgments[cond_key].items()):
            if isinstance(score, dict) and score.get("status") == "success":
                print(f"    p{pkey}: overall={score['overall']} text={score['text_accuracy']} "
                      f"math={score['math_accuracy']} — {score.get('notes', '')[:80]}")


def main():
    parser = argparse.ArgumentParser(description="LLM-as-judge evaluation for benchmark V2")
    parser.add_argument("run", nargs="?", help="Specific run directory name (default: all)")
    parser.add_argument("--rejudge", action="store_true", help="Re-evaluate everything")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not args.dry_run:
        print("ERROR: Set GEMINI_API_KEY")
        sys.exit(1)

    print("Loading reference text...")
    reference = load_reference()

    # Find runs to judge
    if args.run:
        run_dirs = [RESULTS_V2_DIR / args.run]
    elif RESULTS_V2_DIR.exists():
        run_dirs = sorted(d for d in RESULTS_V2_DIR.iterdir() if d.is_dir())
    else:
        run_dirs = []

    if not run_dirs:
        print("No benchmark runs found. Run run_benchmark_v2.py first.")
        return

    # Count total judgments needed
    total_needed = 0
    for run_dir in run_dirs:
        rf = run_dir / "benchmark_results.json"
        if rf.exists():
            with open(rf, encoding="utf-8") as f:
                data = json.load(f)
            for cond in data.values():
                total_needed += len(cond.get("pages", {}))

    print(f"Runs to judge: {len(run_dirs)}")
    print(f"Total transcriptions: {total_needed}")
    print(f"Model: {JUDGE_MODEL}")

    est_cost = total_needed * (2000 * 0.25 + 500 * 1.50) / 1_000_000
    print(f"Est. cost: ~${est_cost:.3f}")

    if args.dry_run:
        print("\n[DRY RUN]")
        return

    client = genai.Client(api_key=api_key)

    all_judgments = {}
    for run_dir in run_dirs:
        if not (run_dir / "benchmark_results.json").exists():
            continue
        judgments = judge_run(client, run_dir, reference, rejudge=args.rejudge)
        if judgments:
            all_judgments[run_dir.name] = judgments
            print_judge_summary(judgments)

    # Save combined results
    combined_path = BASE_DIR / "judge_results_combined.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_judgments, f, ensure_ascii=False, indent=2)
    print(f"\nCombined results: {combined_path}")


if __name__ == "__main__":
    main()
