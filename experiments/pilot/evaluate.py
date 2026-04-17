"""
Evaluate pilot results against G103d reference text.

Uses fuzzy text matching to align transcriptions with ground truth,
then computes similarity metrics.

Usage:
    python evaluate.py results/run_TIMESTAMP/
    python evaluate.py results/run_TIMESTAMP/ --verbose
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path


BASE_DIR = Path(__file__).parent
REFERENCE_DIR = BASE_DIR / "reference"


def load_reference():
    """Load G103d full text."""
    ref_path = REFERENCE_DIR / "g103d_full_text.json"
    with open(ref_path, encoding='utf-8') as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    """Normalize text for comparison: strip LaTeX commands, normalize whitespace."""
    # Remove LaTeX commands but keep content
    text = re.sub(r'\\(?:section|subsection|textbf|textit|emph)\{([^}]*)\}', r'\1', text)
    # Remove display math delimiters but keep content
    text = re.sub(r'\\begin\{equation\}', '', text)
    text = re.sub(r'\\end\{equation\}', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove pilot markers
    text = re.sub(r'\[DIAGRAM:.*?\]', '', text)
    text = re.sub(r'\[MARGIN:.*?\]', '', text)
    text = re.sub(r'\[unclear.*?\]', '', text)
    text = re.sub(r'\[continues.*?\]', '', text)
    text = re.sub(r'%.*?strip boundary.*?\n', '', text)
    return text.strip()


def extract_key_phrases(text: str, min_len: int = 20) -> list:
    """Extract significant phrases for matching."""
    # Split on sentence boundaries and math delimiters
    chunks = re.split(r'[.;:]\s+|\$\$|\n\n', text)
    phrases = []
    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) >= min_len:
            phrases.append(chunk)
    return phrases


def find_best_reference_match(transcription: str, reference_pages: dict,
                               search_window: int = 50) -> dict:
    """Find the best matching reference pages for a transcription."""
    norm_trans = normalize_text(transcription)
    if not norm_trans:
        return {"best_page": None, "score": 0, "details": "Empty transcription"}

    best_score = 0
    best_page = None
    page_scores = {}

    for page_num, ref_text in reference_pages.items():
        norm_ref = normalize_text(ref_text)
        if not norm_ref:
            continue

        # Use SequenceMatcher for similarity
        matcher = difflib.SequenceMatcher(None, norm_trans[:2000], norm_ref[:2000])
        score = matcher.ratio()
        page_scores[page_num] = score

        if score > best_score:
            best_score = score
            best_page = page_num

    return {
        "best_page": best_page,
        "score": best_score,
        "top_5": sorted(page_scores.items(), key=lambda x: -x[1])[:5],
    }


def compute_transcription_quality(transcription: str) -> dict:
    """Compute quality metrics for a single transcription."""
    if not transcription:
        return {"length": 0, "has_latex": False, "unclear_count": 0, "line_count": 0}

    return {
        "length": len(transcription),
        "line_count": transcription.count('\n') + 1,
        "has_latex": '$' in transcription or '\\' in transcription,
        "latex_inline_count": transcription.count('$') // 2,
        "latex_display_count": transcription.count('\\begin{equation'),
        "unclear_count": transcription.lower().count('[unclear'),
        "diagram_count": transcription.lower().count('[diagram'),
        "margin_count": transcription.lower().count('[margin'),
        "french_markers": sum(1 for w in ['soit', 'donc', 'alors', 'catégorie', 'foncteur', 'topos']
                              if w in transcription.lower()),
    }


def compare_experiments(results: dict, reference: dict, verbose: bool = False) -> dict:
    """Compare all experiments against reference."""
    comparison = {}

    for exp_id, exp_results in results["experiments"].items():
        exp_comparison = {"pages": {}, "summary": {}}

        total_score = 0
        total_length = 0
        total_unclear = 0
        n_pages = 0

        for page_key, page_result in exp_results.items():
            # Get the transcription text
            if isinstance(page_result, dict) and "merged" in page_result:
                transcription = page_result["merged"]
            elif isinstance(page_result, dict) and "transcription" in page_result:
                transcription = page_result.get("transcription", "")
            else:
                continue

            # Quality metrics
            quality = compute_transcription_quality(transcription)

            # Reference matching
            ref_match = find_best_reference_match(transcription, reference)

            page_comparison = {
                "quality": quality,
                "reference_match": {
                    "best_page": ref_match["best_page"],
                    "similarity_score": round(ref_match["score"], 4),
                    "top_matches": [(p, round(s, 4)) for p, s in ref_match.get("top_5", [])],
                },
            }

            exp_comparison["pages"][page_key] = page_comparison

            total_score += ref_match["score"]
            total_length += quality["length"]
            total_unclear += quality["unclear_count"]
            n_pages += 1

        # Summary
        if n_pages > 0:
            exp_comparison["summary"] = {
                "n_pages": n_pages,
                "avg_similarity": round(total_score / n_pages, 4),
                "avg_length": round(total_length / n_pages),
                "total_unclear": total_unclear,
                "avg_unclear_per_page": round(total_unclear / n_pages, 1),
            }

        comparison[exp_id] = exp_comparison

    return comparison


def print_comparison_table(comparison: dict):
    """Print a nicely formatted comparison table."""
    experiment_names = {
        "A": "Full page, no context",
        "B": "Full page, with context",
        "C": "Strips, no context",
        "D": "Strips, with context",
    }

    print(f"\n{'='*80}")
    print("EXPERIMENT COMPARISON")
    print(f"{'='*80}")

    # Summary table
    print(f"\n{'Experiment':<30} {'Avg Sim':>8} {'Avg Len':>8} {'Unclear':>8} {'Pages':>6}")
    print("-" * 68)

    for exp_id in ["A", "B", "C", "D"]:
        if exp_id not in comparison:
            continue
        summary = comparison[exp_id]["summary"]
        name = experiment_names.get(exp_id, exp_id)
        print(f"  {exp_id}) {name:<26} {summary['avg_similarity']:>7.1%} "
              f"{summary['avg_length']:>7} {summary['total_unclear']:>7} "
              f"{summary['n_pages']:>5}")

    print()

    # Per-page detail
    print(f"\n{'='*80}")
    print("PER-PAGE SIMILARITY SCORES")
    print(f"{'='*80}")

    # Collect all pages across experiments
    all_pages = set()
    for exp_data in comparison.values():
        all_pages.update(exp_data["pages"].keys())
    all_pages = sorted(all_pages, key=lambda x: int(x))

    header = f"{'Page':>6}"
    for exp_id in ["A", "B", "C", "D"]:
        if exp_id in comparison:
            header += f"  {'Exp '+exp_id:>10}"
    print(header)
    print("-" * len(header))

    for page in all_pages:
        row = f"{page:>6}"
        for exp_id in ["A", "B", "C", "D"]:
            if exp_id in comparison and page in comparison[exp_id]["pages"]:
                score = comparison[exp_id]["pages"][page]["reference_match"]["similarity_score"]
                row += f"  {score:>9.1%}"
            else:
                row += f"  {'---':>10}"
        print(row)

    # Key findings
    print(f"\n{'='*80}")
    print("KEY FINDINGS")
    print(f"{'='*80}")

    if "A" in comparison and "B" in comparison:
        diff_AB = comparison["B"]["summary"]["avg_similarity"] - comparison["A"]["summary"]["avg_similarity"]
        direction = "+" if diff_AB > 0 else ""
        print(f"  Context effect (full page):  {direction}{diff_AB:.1%} "
              f"({'helps' if diff_AB > 0.01 else 'hurts' if diff_AB < -0.01 else 'neutral'})")

    if "A" in comparison and "C" in comparison:
        diff_AC = comparison["C"]["summary"]["avg_similarity"] - comparison["A"]["summary"]["avg_similarity"]
        direction = "+" if diff_AC > 0 else ""
        print(f"  Strip effect (no context):   {direction}{diff_AC:.1%} "
              f"({'helps' if diff_AC > 0.01 else 'hurts' if diff_AC < -0.01 else 'neutral'})")

    if "C" in comparison and "D" in comparison:
        diff_CD = comparison["D"]["summary"]["avg_similarity"] - comparison["C"]["summary"]["avg_similarity"]
        direction = "+" if diff_CD > 0 else ""
        print(f"  Context effect (strips):     {direction}{diff_CD:.1%} "
              f"({'helps' if diff_CD > 0.01 else 'hurts' if diff_CD < -0.01 else 'neutral'})")

    if "A" in comparison and "D" in comparison:
        diff_AD = comparison["D"]["summary"]["avg_similarity"] - comparison["A"]["summary"]["avg_similarity"]
        direction = "+" if diff_AD > 0 else ""
        print(f"  Best vs baseline (D vs A):   {direction}{diff_AD:.1%}")

    # Recommendation
    if comparison:
        best_exp = max(comparison.keys(),
                       key=lambda k: comparison[k]["summary"]["avg_similarity"])
        best_score = comparison[best_exp]["summary"]["avg_similarity"]
        print(f"\n  >>> BEST: Experiment {best_exp} ({experiment_names.get(best_exp, best_exp)}) "
              f"with {best_score:.1%} average similarity")


def main():
    parser = argparse.ArgumentParser(description="Evaluate pilot results against reference")
    parser.add_argument("results_dir", help="Path to results directory (e.g., results/run_TIMESTAMP/)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed per-page analysis")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        # Try relative to pilot dir
        results_dir = RESULTS_DIR / args.results_dir
    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {args.results_dir}")
        sys.exit(1)

    # Load results
    results_path = results_dir / "all_results.json"
    if not results_path.exists():
        print(f"ERROR: all_results.json not found in {results_dir}")
        sys.exit(1)

    with open(results_path, encoding='utf-8') as f:
        results = json.load(f)

    print(f"Loaded results: {results['model']}, {results['timestamp']}")
    print(f"Experiments: {list(results['experiments'].keys())}")

    # Load reference
    print("Loading G103d reference text...")
    reference = load_reference()
    print(f"Reference: {len(reference)} pages")

    # Compare
    comparison = compare_experiments(results, reference, verbose=args.verbose)

    # Print
    print_comparison_table(comparison)

    # Save evaluation
    eval_path = results_dir / "evaluation.json"
    with open(eval_path, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    print(f"\n  Evaluation saved: {eval_path}")


if __name__ == "__main__":
    main()
