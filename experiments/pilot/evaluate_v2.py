"""
Evaluate pilot results against G103d reference text — V2 with page alignment.

Key improvements over v1:
1. Manual page alignment between 140-2 PDF pages and G103d reference pages
2. Much stronger text normalization (strips ALL LaTeX formatting noise)
3. Multiple similarity metrics (SequenceMatcher, word overlap, key phrase matching)
4. Content-focused scoring (ignores layout commands like \hfill, \vspace)
5. Per-page aligned comparison + content accuracy analysis

Usage:
    python evaluate_v2.py
    python evaluate_v2.py --verbose
"""

import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).parent
REFERENCE_DIR = BASE_DIR / "reference"
RESULTS_DIR = BASE_DIR / "results"

# =============================================================================
# PAGE ALIGNMENT
# =============================================================================
# 140-2 PDF page index → G103d reference page(s)
# Based on TOC analysis and content matching.
#
# PDF pages 1-4 are cover + table of contents (no direct reference equivalent)
# PDF page 5 starts § 1. Topos multigaloisiens → G103d pages 6-9
# PDF pages 50-54 → around sections 12-13 based on Grothendieck's pagination
#
# Grothendieck's own page numbering (from TOC):
#   § 1 starts at his page 1 → PDF page ~5
#   § 12 starts at his page 41 → PDF page ~45
#   § 13 starts at his page 53 → PDF page ~57
# So PDF pages 50-54 ≈ Grothendieck pages 46-50 ≈ end of §12
# §12 in G103d = pages 56-65
#
# We'll do content-based alignment: for each transcription, find the BEST
# matching reference pages from a narrow window, then use that for scoring.

PAGE_ALIGNMENT_HINTS = {
    # PDF page: (approximate G103d pages to search, description)
    # Alignment determined by content-based matching across all 303 reference pages.
    #
    # Key insight: 140-2 PDF page numbers ≠ Grothendieck's own pagination.
    # The PDF has ~575 pages for content that maps to 305 G103d pages.
    # Pages 1-4 are cover/TOC. Page 5 starts §1. Page 54 starts §8.
    # Pages 50-53 are deep in §7 (Reformulation "bordélique") — a long
    # section (G103d pages 21-37) with dense, highly technical content.
    #
    1: ([], "Cover page — no reference equivalent"),
    2: ([], "Table of contents page 1 — no direct reference"),
    3: ([4, 5, 6], "Table of contents page 2 / pre-§1"),
    4: ([5, 6], "Pre-section / transition to §1"),
    5: ([6, 7, 8], "§1 Topos multigaloisiens — Prop 1.1"),
    # Pages 50-53: §7 "Reformulation bordélique" (G103d 21-37)
    # Content-based search shows NO strong match for these pages.
    # The reference text extraction loses too much mathematical structure
    # (commutative diagrams, symbol-heavy proofs) for string matching to work.
    50: ([30, 31, 32, 33, 34, 35], "§7 Reformulation bordélique — dense math"),
    51: ([33, 34, 35, 36, 37], "§7 late — systems of isomorphisms"),
    52: ([34, 35, 36, 37], "§7 late — continued"),
    53: ([35, 36, 37], "§7 end — NB notation"),
    54: ([38, 39, 40, 41], "§8 Réflexion taxonomique — strong match"),
}


def load_reference():
    """Load G103d reference text.

    Prefers VLM-extracted text (raw mode) over fitz page.get_text().
    Falls back to fitz extraction for pages without VLM text.
    """
    # Load fitz-extracted text as fallback
    fitz_path = REFERENCE_DIR / "g103d_full_text.json"
    with open(fitz_path, encoding='utf-8') as f:
        fitz_ref = json.load(f)

    # Load VLM-extracted text (better quality)
    vlm_path = REFERENCE_DIR / "g103d_vlm_text.json"
    vlm_ref = {}
    if vlm_path.exists():
        with open(vlm_path, encoding='utf-8') as f:
            vlm_data = json.load(f)
        for pkey, entry in vlm_data.items():
            # Prefer raw text; fall back to latex (stripped) if raw not available
            raw = entry.get("raw", "")
            if raw and len(raw) > 200:
                vlm_ref[pkey] = raw
            else:
                latex = entry.get("latex", "")
                if latex and len(latex) > 200:
                    vlm_ref[pkey] = latex

    # Merge: VLM overrides fitz where available
    reference = dict(fitz_ref)
    n_vlm = 0
    for pkey, text in vlm_ref.items():
        reference[pkey] = text
        n_vlm += 1

    print(f"  Reference: {len(fitz_ref)} fitz pages + {n_vlm} VLM-upgraded pages")
    return reference


def normalize_text_strict(text: str) -> str:
    """Aggressively normalize text for content comparison.

    Strips ALL LaTeX formatting, layout commands, markers, and whitespace noise.
    Focuses on pure textual content for fair comparison.
    """
    if not text:
        return ""

    # Remove pilot markers
    text = re.sub(r'\[DIAGRAM:.*?\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\[MARGIN:.*?\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\[unclear.*?\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\[continues.*?\]', '', text, flags=re.DOTALL)
    text = re.sub(r'%.*?strip boundary.*?\n', '', text)

    # Remove LaTeX layout commands (Pro's over-formatting issue)
    text = re.sub(r'\\hfill\b', '', text)
    text = re.sub(r'\\vfill\b', '', text)
    text = re.sub(r'\\vspace\{[^}]*\}', '', text)
    text = re.sub(r'\\hspace\{[^}]*\}', '', text)
    text = re.sub(r'\\noindent\b', '', text)
    text = re.sub(r'\\newpage\b', '', text)
    text = re.sub(r'\\\\', ' ', text)  # line breaks → space

    # Remove environment wrappers but keep content
    text = re.sub(r'\\begin\{(?:center|itemize|enumerate|equation\*?|align\*?|gather\*?)\}', '', text)
    text = re.sub(r'\\end\{(?:center|itemize|enumerate|equation\*?|align\*?|gather\*?)\}', '', text)
    text = re.sub(r'\\item\b\s*(?:\[[^\]]*\])?', '', text)

    # Remove section/formatting commands but keep content
    text = re.sub(r'\\(?:section|subsection|subsubsection|paragraph)\*?\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\(?:textbf|textit|emph|textsuperscript|textsubscript|mathrm|mathbf|mathit|mathcal|mathbb|hat|tilde|widehat|widetilde|overline|underline)\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\(?:text|mbox|operatorname)\{([^}]*)\}', r'\1', text)

    # Simplify math delimiters
    text = re.sub(r'\$\$', ' ', text)

    # Remove standalone backslash commands without braces
    text = re.sub(r'\\(?:quad|qquad|,|;|!|>)\b', ' ', text)
    text = re.sub(r'\\(?:left|right|big|Big|bigg|Bigg)[|(\[{)\]}]?', '', text)

    # Keep math content but simplify
    # Don't remove $ delimiters — they mark important content boundaries

    # Normalize unicode
    text = text.replace('≈', '~').replace('→', '->').replace('⇒', '=>')
    text = text.replace('≃', '~').replace('≊', '~')
    text = text.replace('\u00a7', '§')  # section sign

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    return text.strip().lower()


def extract_content_words(text: str) -> list:
    """Extract meaningful content words from normalized text."""
    normalized = normalize_text_strict(text)
    # Split on non-alphanumeric (keeping accented chars)
    words = re.findall(r'[a-zà-ÿ0-9$\\]+', normalized)
    # Filter very short words and common LaTeX noise
    stopwords = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou',
                 'en', 'on', 'est', 'a', 'i', 'il', 'que', 'qui', 'ce', 'se',
                 'ne', 'pas', 'par', 'pour', 'dans', 'sur', 'avec', 'au', 'aux',
                 'si', 'sa', 'son', 'ses'}
    return [w for w in words if len(w) > 1 and w not in stopwords]


def word_overlap_score(text_a: str, text_b: str) -> float:
    """Compute word-level Jaccard-like overlap between two texts."""
    words_a = Counter(extract_content_words(text_a))
    words_b = Counter(extract_content_words(text_b))

    if not words_a or not words_b:
        return 0.0

    # Intersection count (min of each word's count)
    intersection = sum((words_a & words_b).values())
    # Union count
    union = sum((words_a | words_b).values())

    return intersection / union if union > 0 else 0.0


def sequence_similarity(text_a: str, text_b: str) -> float:
    """SequenceMatcher on normalized texts."""
    norm_a = normalize_text_strict(text_a)
    norm_b = normalize_text_strict(text_b)

    if not norm_a or not norm_b:
        return 0.0

    # Use first 3000 chars for efficiency
    matcher = difflib.SequenceMatcher(None, norm_a[:3000], norm_b[:3000])
    return matcher.ratio()


def find_aligned_reference(transcription: str, reference: dict,
                           hint_pages: list, search_radius: int = 5) -> dict:
    """Find best matching reference using alignment hints.

    First searches hint pages, then expands by search_radius if needed.
    Returns best match with multiple metrics.
    """
    if not transcription or not transcription.strip():
        return {
            "best_page": None, "seq_score": 0, "word_score": 0,
            "combined_score": 0, "search_pages": [], "all_scores": {}
        }

    # Build search window
    search_pages = set()
    for p in hint_pages:
        for offset in range(-search_radius, search_radius + 1):
            page_key = str(p + offset)
            if page_key in reference:
                search_pages.add(page_key)

    # If no hints, search more broadly (but still not all 303 pages)
    if not search_pages:
        # Search first 20 and around page 60 area
        for p in range(1, 20):
            if str(p) in reference:
                search_pages.add(str(p))
        for p in range(55, 75):
            if str(p) in reference:
                search_pages.add(str(p))

    best_combined = 0
    best_page = None
    all_scores = {}

    for page_key in sorted(search_pages, key=lambda x: int(x)):
        ref_text = reference[page_key]

        seq_score = sequence_similarity(transcription, ref_text)
        word_score = word_overlap_score(transcription, ref_text)
        combined = 0.5 * seq_score + 0.5 * word_score

        all_scores[page_key] = {
            "seq_score": round(seq_score, 4),
            "word_score": round(word_score, 4),
            "combined": round(combined, 4),
        }

        if combined > best_combined:
            best_combined = combined
            best_page = page_key

    # Sort by combined score
    top_matches = sorted(all_scores.items(), key=lambda x: -x[1]["combined"])[:5]

    return {
        "best_page": best_page,
        "seq_score": all_scores.get(best_page, {}).get("seq_score", 0),
        "word_score": all_scores.get(best_page, {}).get("word_score", 0),
        "combined_score": round(best_combined, 4),
        "search_pages": sorted(search_pages, key=lambda x: int(x)),
        "top_matches": top_matches,
    }


def compute_quality_metrics(transcription: str) -> dict:
    """Compute comprehensive quality metrics."""
    if not transcription:
        return {"length": 0, "content_words": 0, "has_latex": False,
                "unclear_count": 0, "formatting_ratio": 0}

    content_words = extract_content_words(transcription)

    # Count formatting commands (Pro's over-formatting metric)
    formatting_commands = len(re.findall(
        r'\\(?:hfill|vfill|vspace|hspace|newpage|noindent|begin|end|item)\b',
        transcription
    ))
    total_commands = len(re.findall(r'\\[a-zA-Z]+', transcription))
    content_commands = total_commands - formatting_commands

    return {
        "length": len(transcription),
        "line_count": transcription.count('\n') + 1,
        "content_words": len(content_words),
        "unique_content_words": len(set(content_words)),
        "has_latex": '$' in transcription or '\\' in transcription,
        "latex_inline_count": transcription.count('$') // 2,
        "unclear_count": transcription.lower().count('[unclear'),
        "diagram_count": transcription.lower().count('[diagram'),
        "margin_count": transcription.lower().count('[margin'),
        "formatting_commands": formatting_commands,
        "content_commands": content_commands,
        "formatting_ratio": round(formatting_commands / max(total_commands, 1), 3),
        "french_math_terms": sum(1 for w in [
            'soit', 'donc', 'alors', 'catégorie', 'foncteur', 'topos',
            'proposition', 'définition', 'démonstration', 'groupoïde',
            'équivalence', 'revêtement', 'connexe', 'morphisme'
        ] if w in transcription.lower()),
    }


def evaluate_all(reference: dict, verbose: bool = False) -> dict:
    """Run aligned evaluation on all result directories."""
    results_dirs = sorted(RESULTS_DIR.iterdir())

    all_evaluations = {}

    for run_dir in results_dirs:
        if not run_dir.is_dir():
            continue
        results_file = run_dir / "all_results.json"
        if not results_file.exists():
            continue

        with open(results_file, encoding='utf-8') as f:
            results = json.load(f)

        model = results.get("model", run_dir.name)
        print(f"\n{'='*80}")
        print(f"MODEL: {model}")
        print(f"{'='*80}")

        model_eval = {"model": model, "experiments": {}}

        for exp_id in ["A", "B", "C", "D"]:
            exp_data = results.get("experiments", {}).get(exp_id, {})
            if not exp_data:
                continue

            exp_eval = {"pages": {}, "summary": {}}
            scores = []

            for page_key, page_result in sorted(exp_data.items(), key=lambda x: int(x[0])):
                page_num = int(page_key)

                # Get transcription
                if isinstance(page_result, dict) and "merged" in page_result:
                    transcription = page_result["merged"]
                elif isinstance(page_result, dict) and "transcription" in page_result:
                    transcription = page_result.get("transcription", "")
                else:
                    continue

                # Get alignment hints
                hints = PAGE_ALIGNMENT_HINTS.get(page_num, ([], "unknown"))
                hint_pages, description = hints

                # Quality metrics
                quality = compute_quality_metrics(transcription)

                # Aligned reference matching
                ref_match = find_aligned_reference(transcription, reference, hint_pages)

                page_eval = {
                    "description": description,
                    "quality": quality,
                    "reference_match": ref_match,
                    "has_reference": len(hint_pages) > 0,
                }

                exp_eval["pages"][page_key] = page_eval

                if hint_pages:  # Only include aligned pages in summary
                    scores.append({
                        "page": page_num,
                        "combined": ref_match["combined_score"],
                        "seq": ref_match["seq_score"],
                        "word": ref_match["word_score"],
                        "unclear": quality["unclear_count"],
                        "formatting_ratio": quality["formatting_ratio"],
                        "content_words": quality["content_words"],
                    })

            # Summary (only pages with reference alignment)
            if scores:
                exp_eval["summary"] = {
                    "n_pages_total": len(exp_eval["pages"]),
                    "n_pages_aligned": len(scores),
                    "avg_combined_score": round(sum(s["combined"] for s in scores) / len(scores), 4),
                    "avg_seq_score": round(sum(s["seq"] for s in scores) / len(scores), 4),
                    "avg_word_score": round(sum(s["word"] for s in scores) / len(scores), 4),
                    "total_unclear": sum(s["unclear"] for s in scores),
                    "avg_formatting_ratio": round(sum(s["formatting_ratio"] for s in scores) / len(scores), 3),
                    "avg_content_words": round(sum(s["content_words"] for s in scores) / len(scores)),
                    "per_page": scores,
                }

            model_eval["experiments"][exp_id] = exp_eval

        # Print summary
        print_model_summary(model_eval, verbose)

        all_evaluations[model] = model_eval

    return all_evaluations


def print_model_summary(model_eval: dict, verbose: bool = False):
    """Print formatted evaluation summary for a model."""
    exp_names = {
        "A": "Full page, no context",
        "B": "Full page, with context",
        "C": "Strips, no context",
        "D": "Strips, with context",
    }

    print(f"\n{'Experiment':<30} {'Combined':>9} {'SeqMatch':>9} {'WordOvlp':>9} "
          f"{'Unclear':>8} {'FmtRatio':>9} {'Words':>7}")
    print("-" * 90)

    for exp_id in ["A", "B", "C", "D"]:
        exp = model_eval["experiments"].get(exp_id)
        if not exp or "summary" not in exp:
            continue
        s = exp["summary"]
        name = exp_names.get(exp_id, exp_id)
        print(f"  {exp_id}) {name:<26} {s['avg_combined_score']:>8.1%} "
              f"{s['avg_seq_score']:>8.1%} {s['avg_word_score']:>8.1%} "
              f"{s['total_unclear']:>7} {s['avg_formatting_ratio']:>8.1%} "
              f"{s['avg_content_words']:>6}")

    if verbose:
        print(f"\n  Per-page detail (aligned pages only):")
        for exp_id in ["A", "B", "C", "D"]:
            exp = model_eval["experiments"].get(exp_id)
            if not exp or "summary" not in exp:
                continue
            print(f"\n  Experiment {exp_id}:")
            for score in exp["summary"]["per_page"]:
                print(f"    Page {score['page']:>3}: combined={score['combined']:.1%} "
                      f"seq={score['seq']:.1%} word={score['word']:.1%} "
                      f"unclear={score['unclear']} fmt={score['formatting_ratio']:.1%}")


RESULTS_V2_DIR = BASE_DIR / "results_v2"


def evaluate_benchmark_v2(reference: dict, verbose: bool = False) -> dict:
    """Evaluate benchmark V2 results (from run_benchmark_v2.py).

    These have a different structure: {condition_key: {pages: {page: {transcription}}}}
    """
    if not RESULTS_V2_DIR.exists():
        return {}

    all_evals = {}

    for run_dir in sorted(RESULTS_V2_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        results_file = run_dir / "benchmark_results.json"
        if not results_file.exists():
            continue

        with open(results_file, encoding="utf-8") as f:
            results = json.load(f)

        print(f"\n{'='*80}")
        print(f"BENCHMARK V2: {run_dir.name}")
        print(f"{'='*80}")

        run_eval = {}

        for cond_key, cond_data in sorted(results.items()):
            pages_data = cond_data.get("pages", {})
            if not pages_data:
                continue

            cond_eval = {"pages": {}, "summary": {}}
            scores = []

            for page_key, page_result in sorted(pages_data.items(), key=lambda x: int(x[0])):
                page_num = int(page_key)
                transcription = page_result.get("transcription", "")

                if not transcription or page_result.get("status") != "success":
                    continue

                hints = PAGE_ALIGNMENT_HINTS.get(page_num, ([], "unknown"))
                hint_pages, description = hints

                quality = compute_quality_metrics(transcription)
                ref_match = find_aligned_reference(transcription, reference, hint_pages)

                cond_eval["pages"][page_key] = {
                    "description": description,
                    "quality": quality,
                    "reference_match": ref_match,
                    "has_reference": len(hint_pages) > 0,
                }

                if hint_pages:
                    scores.append({
                        "page": page_num,
                        "combined": ref_match["combined_score"],
                        "seq": ref_match["seq_score"],
                        "word": ref_match["word_score"],
                        "unclear": quality["unclear_count"],
                        "formatting_ratio": quality["formatting_ratio"],
                        "content_words": quality["content_words"],
                    })

            if scores:
                cond_eval["summary"] = {
                    "n_pages_aligned": len(scores),
                    "avg_combined_score": round(sum(s["combined"] for s in scores) / len(scores), 4),
                    "avg_seq_score": round(sum(s["seq"] for s in scores) / len(scores), 4),
                    "avg_word_score": round(sum(s["word"] for s in scores) / len(scores), 4),
                    "total_unclear": sum(s["unclear"] for s in scores),
                    "avg_formatting_ratio": round(sum(s["formatting_ratio"] for s in scores) / len(scores), 3),
                    "avg_content_words": round(sum(s["content_words"] for s in scores) / len(scores)),
                    "per_page": scores,
                }
                cond_eval["metadata"] = {
                    "prompt_style": cond_data.get("prompt_style"),
                    "model": cond_data.get("model"),
                    "thinking_level": cond_data.get("thinking_level"),
                    "use_context": cond_data.get("use_context"),
                }

            run_eval[cond_key] = cond_eval

        # Print summary table
        print(f"\n{'Condition':<50} {'Combined':>9} {'SeqMatch':>9} {'FmtRatio':>9} {'Words':>7}")
        print("-" * 90)
        ranked = sorted(
            [(k, v) for k, v in run_eval.items() if v.get("summary")],
            key=lambda x: -x[1]["summary"]["avg_combined_score"]
        )
        for cond_key, cond_eval in ranked:
            s = cond_eval["summary"]
            print(f"  {cond_key:<48} {s['avg_combined_score']:>8.1%} "
                  f"{s['avg_seq_score']:>8.1%} {s['avg_formatting_ratio']:>8.1%} "
                  f"{s['avg_content_words']:>6}")

        if verbose:
            print(f"\n  Per-page detail:")
            for cond_key, cond_eval in ranked[:5]:  # Top 5 only
                if not cond_eval.get("summary"):
                    continue
                print(f"\n  {cond_key}:")
                for score in cond_eval["summary"]["per_page"]:
                    print(f"    Page {score['page']:>3}: combined={score['combined']:.1%} "
                          f"seq={score['seq']:.1%} word={score['word']:.1%} "
                          f"fmt={score['formatting_ratio']:.1%}")

        all_evals[run_dir.name] = run_eval

    return all_evals


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate pilot results v2 (aligned)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--benchmark-only", action="store_true",
                        help="Only evaluate benchmark V2 results (skip pilot)")
    args = parser.parse_args()

    print("Loading G103d reference text...")
    reference = load_reference()
    print(f"Reference: {len(reference)} pages")

    all_evals = {}

    # Evaluate pilot results (original A/B/C/D experiments)
    if not args.benchmark_only:
        print("\nRunning aligned evaluation (pilot)...")
        pilot_evals = evaluate_all(reference, verbose=args.verbose)
        all_evals["pilot"] = pilot_evals

    # Evaluate benchmark V2 results
    if RESULTS_V2_DIR.exists():
        print("\nRunning benchmark V2 evaluation...")
        bench_evals = evaluate_benchmark_v2(reference, verbose=args.verbose)
        all_evals["benchmark_v2"] = bench_evals

    # Save
    eval_path = BASE_DIR / "evaluation_v2.json"
    with open(eval_path, 'w', encoding='utf-8') as f:
        json.dump(all_evals, f, ensure_ascii=False, indent=2)
    print(f"\nEvaluation saved: {eval_path}")

    # Cross-model comparison (pilot only)
    pilot_evals = all_evals.get("pilot", {})
    if len(pilot_evals) > 1:
        print(f"\n{'='*80}")
        print("CROSS-MODEL COMPARISON — PILOT (aligned pages only)")
        print(f"{'='*80}")

        for exp_id in ["A", "B", "C", "D"]:
            print(f"\n  Experiment {exp_id}:")
            for model, eval_data in pilot_evals.items():
                exp = eval_data["experiments"].get(exp_id)
                if not exp or "summary" not in exp:
                    continue
                s = exp["summary"]
                short = "Flash-Lite" if "flash-lite" in model else "Pro"
                print(f"    {short:<12} combined={s['avg_combined_score']:.1%} "
                      f"fmt_ratio={s['avg_formatting_ratio']:.1%} "
                      f"unclear={s['total_unclear']}")


if __name__ == "__main__":
    main()
