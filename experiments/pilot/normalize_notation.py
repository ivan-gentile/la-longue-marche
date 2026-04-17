"""
Post-processing notation normalization for Grothendieck transcriptions.

Two modes:
  --mode regex   : Deterministic regex replacements (free, fast)
  --mode llm     : LLM-assisted normalization (thorough, handles context)

Usage:
    # Preview regex changes (dry run)
    python3 normalize_notation.py --mode regex --dry-run

    # Apply regex normalizations
    python3 normalize_notation.py --mode regex

    # LLM normalization (needs API key)
    GEMINI_API_KEY=key python3 normalize_notation.py --mode llm --dry-run
    GEMINI_API_KEY=key python3 normalize_notation.py --mode llm

    # Process a single volume
    python3 normalize_notation.py --mode regex --volume 140-3

    # Show statistics only
    python3 normalize_notation.py --stats
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
PRODUCTION_DIR = BASE_DIR / "production"

VOLUMES = {
    "140-3": {"pdf": "140-3.pdf", "pages": 696},
    "140-4": {"pdf": "140-4.pdf", "pages": 280},
}

# =============================================================================
# CANONICAL NOTATION TABLE
# (Based on Grothendieck's own usage in the manuscript TOC and Part 1 reference)
# =============================================================================

CANONICAL_NOTATION = """
Canonical notation for this manuscript (Grothendieck, "La longue marche"):

OPERATOR NAMES (always use \\operatorname{}):
  \\operatorname{Sl}   — NOT SL, not bare Sl
  \\operatorname{Gl}   — NOT GL, not bare Gl
  \\operatorname{Ker}  — NOT bare Ker, \\text{Ker}, \\mathrm{Ker}
  \\operatorname{Aut}  — NOT bare Aut, \\text{Aut}
  \\operatorname{Im}   — NOT bare Im, \\text{Im}
  \\operatorname{Hom}  — NOT bare Hom, \\text{Hom}
  \\operatorname{Spec} — NOT bare Spec
  \\operatorname{Gal}  — NOT bare Gal
  \\operatorname{Norm} — NOT bare Norm, \\text{Norm}
  \\operatorname{Loc}  — NOT bare Loc
  \\operatorname{Ens}  — category of sets
  \\operatorname{Ob}   — objects of a category

CALLIGRAPHIC:
  \\mathcal{X} — NEVER \\cal{X} or \\cal X

DECORATORS:
  \\hat{X}      — for single symbols: \\hat{C}, \\hat{\\pi}, \\hat{\\mathbb{Z}}
  \\widehat{XY} — for compound operator names: \\widehat{Sl}, \\widehat{Gl}, \\widehat{Cont}

SECTION REFERENCES:
  § N — Unicode section sign, NOT \\S N

ISOMORPHISMS:
  \\simeq            — isomorphism (default)
  \\xrightarrow{\\sim} — isomorphism arrow
  \\sim              — equivalence relation (keep when used as relation, not isomorphism)
"""

# =============================================================================
# REGEX NORMALIZATION RULES
# =============================================================================

def build_regex_rules():
    """Build list of (pattern, replacement, description) tuples."""
    rules = []

    # --- \cal → \mathcal ---
    # Old TeX \cal{X} → \mathcal{X}
    rules.append((
        re.compile(r'\\cal\{'),
        r'\\mathcal{',
        "\\cal{} → \\mathcal{}"
    ))
    # Old TeX \cal X (space-separated, single char)
    rules.append((
        re.compile(r'\\cal\s+([A-Z])'),
        r'\\mathcal{\1}',
        "\\cal X → \\mathcal{X}"
    ))

    # --- SL → Sl (Grothendieck's convention) ---
    # SL( → Sl( — but NOT inside \operatorname{SL} (handle that separately)
    rules.append((
        re.compile(r'(?<!\\operatorname\{)(?<!\\text\{)(?<!\\mathrm\{)SL\('),
        r'\\operatorname{Sl}(',
        "bare SL( → \\operatorname{Sl}("
    ))
    rules.append((
        re.compile(r'\\operatorname\{SL\}'),
        r'\\operatorname{Sl}',
        "\\operatorname{SL} → \\operatorname{Sl}"
    ))
    rules.append((
        re.compile(r'\\text\{SL\}'),
        r'\\operatorname{Sl}',
        "\\text{SL} → \\operatorname{Sl}"
    ))
    rules.append((
        re.compile(r'\\mathrm\{SL\}'),
        r'\\operatorname{Sl}',
        "\\mathrm{SL} → \\operatorname{Sl}"
    ))

    # --- GL → Gl ---
    rules.append((
        re.compile(r'(?<!\\operatorname\{)(?<!\\text\{)(?<!\\mathrm\{)GL\('),
        r'\\operatorname{Gl}(',
        "bare GL( → \\operatorname{Gl}("
    ))
    rules.append((
        re.compile(r'\\operatorname\{GL\}'),
        r'\\operatorname{Gl}',
        "\\operatorname{GL} → \\operatorname{Gl}"
    ))
    rules.append((
        re.compile(r'\\text\{GL\}'),
        r'\\operatorname{Gl}',
        "\\text{GL} → \\operatorname{Gl}"
    ))
    rules.append((
        re.compile(r'\\mathrm\{GL\}'),
        r'\\operatorname{Gl}',
        "\\mathrm{GL} → \\operatorname{Gl}"
    ))

    # --- Bare Sl( and Gl( → \operatorname ---
    # Match bare Sl( that's not already wrapped
    rules.append((
        re.compile(r'(?<!\\operatorname\{)(?<!\\text\{)(?<!\\mathrm\{)(?<!\\widehat\{)(?<![A-Za-z])Sl\('),
        r'\\operatorname{Sl}(',
        "bare Sl( → \\operatorname{Sl}("
    ))
    rules.append((
        re.compile(r'(?<!\\operatorname\{)(?<!\\text\{)(?<!\\mathrm\{)(?<!\\widehat\{)(?<![A-Za-z])Gl\('),
        r'\\operatorname{Gl}(',
        "bare Gl( → \\operatorname{Gl}("
    ))

    # --- Operator names: various wrappings → \operatorname ---
    operators = ["Ker", "Aut", "Im", "Hom", "Spec", "Gal", "Norm", "Loc", "Ens", "Ob"]

    for op in operators:
        # \text{Op} → \operatorname{Op}
        rules.append((
            re.compile(rf'\\text\{{{op}\}}'),
            rf'\\operatorname{{{op}}}',
            f"\\text{{{op}}} → \\operatorname{{{op}}}"
        ))
        # \mathrm{Op} → \operatorname{Op}
        rules.append((
            re.compile(rf'\\mathrm\{{{op}\}}'),
            rf'\\operatorname{{{op}}}',
            f"\\mathrm{{{op}}} → \\operatorname{{{op}}}"
        ))
        # Bare Op( → \operatorname{Op}( when in math context
        # We detect math context by: preceded by $, \, {, (, space+$ etc.
        # Safe heuristic: Op followed by ( or _ or ^ or \
        rules.append((
            re.compile(rf'(?<!\\operatorname\{{)(?<!\\text\{{)(?<!\\mathrm\{{)(?<![A-Za-z]){op}(?=[\(_^\\])'),
            rf'\\operatorname{{{op}}}',
            f"bare {op} → \\operatorname{{{op}}} (before math operators)"
        ))

    # --- \S followed by digit/space+digit → § ---
    rules.append((
        re.compile(r'\\S\s+(\d)'),
        r'§ \1',
        "\\S N → § N"
    ))

    # --- Environment mismatches ---
    # \begin{matrix}...\end{array} → \end{matrix}
    # This is a simple heuristic; for complex nesting we'd need a parser
    rules.append((
        re.compile(r'\\begin\{matrix\}(.*?)\\end\{array\}', re.DOTALL),
        r'\\begin{matrix}\1\\end{matrix}',
        "\\begin{matrix}...\\end{array} mismatch → \\end{matrix}"
    ))

    # --- \widehat{\mathbb{Z}} → \hat{\mathbb{Z}} (single symbol) ---
    rules.append((
        re.compile(r'\\widehat\{\\mathbb\{Z\}\}'),
        r'\\hat{\\mathbb{Z}}',
        "\\widehat{\\mathbb{Z}} → \\hat{\\mathbb{Z}}"
    ))

    return rules


# =============================================================================
# LLM NORMALIZATION PROMPT
# =============================================================================

LLM_NORMALIZE_PROMPT = f"""You are a mathematical typesetting normalizer for Grothendieck's manuscripts.

Given a transcription, normalize ALL notation to the canonical forms below.
Return ONLY the normalized transcription — no commentary, no explanation.

{CANONICAL_NOTATION}

RULES:
1. Apply ALL canonical forms above consistently
2. Do NOT change the mathematical CONTENT — only the FORMATTING of notation
3. Do NOT change French text, prose, [MARGIN:] markers, or [unclear] markers
4. Do NOT add or remove content — only normalize existing notation
5. Preserve all line breaks and paragraph structure exactly
6. When \\sim is used as an equivalence RELATION (not isomorphism), keep it as \\sim
7. For \\hat vs \\widehat: use \\hat for single symbols (\\hat{{C}}, \\hat{{\\pi}}, \\hat{{\\mathbb{{Z}}}})
   and \\widehat for compound names (\\widehat{{Sl}}, \\widehat{{Gl}}, \\widehat{{Cont}})
"""


# =============================================================================
# STATISTICS
# =============================================================================

def collect_stats(data: dict) -> dict:
    """Collect notation statistics from a volume's transcriptions."""
    stats = Counter()

    for pkey, entry in data.items():
        if entry.get("status") != "success":
            continue
        text = entry.get("transcription", "")

        # \cal vs \mathcal
        if re.search(r'\\cal[\s{]', text):
            stats["\\cal (old)"] += 1
        if "\\mathcal{" in text:
            stats["\\mathcal (standard)"] += 1

        # SL vs Sl
        if re.search(r'(?<![A-Za-z])SL\(', text):
            stats["SL( (uppercase)"] += 1
        if re.search(r'(?<![A-Za-z])Sl\(', text):
            stats["Sl( (Grothendieck)"] += 1

        # GL vs Gl
        if re.search(r'(?<![A-Za-z])GL\(', text):
            stats["GL( (uppercase)"] += 1
        if re.search(r'(?<![A-Za-z])Gl\(', text):
            stats["Gl( (Grothendieck)"] += 1

        # Ker variants
        for variant, label in [
            (r'(?<![A-Za-z\\])Ker[\(_^]', "Ker (bare)"),
            (r'\\text\{Ker\}', "\\text{Ker}"),
            (r'\\mathrm\{Ker\}', "\\mathrm{Ker}"),
            (r'\\operatorname\{Ker\}', "\\operatorname{Ker}"),
        ]:
            if re.search(variant, text):
                stats[label] += 1

        # Aut variants
        for variant, label in [
            (r'(?<![A-Za-z\\])Aut[\(_^]', "Aut (bare)"),
            (r'\\text\{Aut\}', "\\text{Aut}"),
            (r'\\operatorname\{Aut\}', "\\operatorname{Aut}"),
        ]:
            if re.search(variant, text):
                stats[label] += 1

        # \hat vs \widehat
        if "\\hat{" in text:
            stats["\\hat{}"] += 1
        if "\\widehat{" in text:
            stats["\\widehat{}"] += 1

        # § vs \S
        if "§" in text:
            stats["§ (unicode)"] += 1
        if re.search(r'\\S\s+\d', text):
            stats["\\S N (LaTeX)"] += 1

        # \simeq vs \sim vs \cong
        if "\\simeq" in text:
            stats["\\simeq"] += 1
        if re.search(r'(?<!\\)\\sim(?![eq])', text):
            stats["\\sim"] += 1
        if "\\cong" in text:
            stats["\\cong"] += 1

        # operatorname already used
        if "\\operatorname{" in text:
            stats["\\operatorname{} (already)"] += 1

    return stats


# =============================================================================
# MAIN LOGIC
# =============================================================================

def apply_regex_normalization(text: str, rules: list, verbose: bool = False) -> tuple:
    """Apply regex rules to text. Returns (normalized_text, changes_list)."""
    changes = []
    result = text

    for pattern, replacement, description in rules:
        matches = pattern.findall(result)
        if matches:
            new_result = pattern.sub(replacement, result)
            if new_result != result:
                count = len(matches)
                changes.append({"rule": description, "count": count})
                if verbose:
                    # Show first match context
                    m = pattern.search(result)
                    if m:
                        start = max(0, m.start() - 20)
                        end = min(len(result), m.end() + 20)
                        context = result[start:end].replace("\n", "↵")
                        print(f"      {description}: {count}x  ...{context}...")
                result = new_result

    return result, changes


def normalize_regex(volumes: list, dry_run: bool = False, verbose: bool = False):
    """Apply regex normalizations to all transcriptions."""
    rules = build_regex_rules()

    for vol_key in volumes:
        results_file = PRODUCTION_DIR / vol_key / "transcriptions.json"
        if not results_file.exists():
            print(f"  {vol_key}: transcriptions.json not found")
            continue

        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        total_pages = sum(1 for v in data.values() if v.get("status") == "success")
        pages_changed = 0
        all_changes = Counter()

        for pkey in sorted(data.keys(), key=lambda x: int(x)):
            entry = data[pkey]
            if entry.get("status") != "success":
                continue

            text = entry["transcription"]
            if verbose:
                print(f"    p{pkey}:")

            normalized, changes = apply_regex_normalization(text, rules, verbose=verbose)

            if changes:
                pages_changed += 1
                for c in changes:
                    all_changes[c["rule"]] += c["count"]
                if not dry_run:
                    data[pkey]["transcription"] = normalized
                    data[pkey]["normalized"] = True

        print(f"\n  {vol_key}: {pages_changed}/{total_pages} pages would be changed")
        if all_changes:
            print(f"  Changes by rule:")
            for rule, count in sorted(all_changes.items(), key=lambda x: -x[1]):
                print(f"    {rule}: {count}")

        if not dry_run and pages_changed > 0:
            # Backup
            backup_file = PRODUCTION_DIR / vol_key / "transcriptions_pre_normalize.json"
            if not backup_file.exists():
                with open(results_file, "r", encoding="utf-8") as f:
                    backup_data = f.read()
                with open(backup_file, "w", encoding="utf-8") as f:
                    f.write(backup_data)
                print(f"  Backed up to {backup_file.name}")

            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  Applied {sum(all_changes.values())} changes to {pages_changed} pages")


def normalize_llm(volumes: list, dry_run: bool = False, model_key: str = "flash-lite",
                   thinking_level: str = "low"):
    """Apply LLM-based normalization to all transcriptions."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("ERROR: pip install google-genai")
        sys.exit(1)

    MODELS = {
        "pro": {"id": "gemini-3.1-pro-preview", "cost_input": 2.00, "cost_output": 12.00},
        "flash-lite": {"id": "gemini-3.1-flash-lite-preview", "cost_input": 0.25, "cost_output": 1.50},
    }

    model_cfg = MODELS[model_key]
    model_id = model_cfg["id"]

    for vol_key in volumes:
        results_file = PRODUCTION_DIR / vol_key / "transcriptions.json"
        if not results_file.exists():
            print(f"  {vol_key}: transcriptions.json not found")
            continue

        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        total_pages = sum(1 for v in data.values() if v.get("status") == "success")

        # Estimate cost
        avg_chars = sum(len(v.get("transcription", "")) for v in data.values()
                        if v.get("status") == "success") / max(total_pages, 1)
        avg_tokens = avg_chars / 4  # rough estimate
        est_cost = total_pages * (
            (avg_tokens + 500) * model_cfg["cost_input"]  # input: transcription + prompt
            + avg_tokens * model_cfg["cost_output"]         # output: normalized version
        ) / 1_000_000

        print(f"\n  {vol_key}: {total_pages} pages, avg {avg_chars:.0f} chars/page")
        print(f"  Model: {model_id} (thinking={thinking_level})")
        print(f"  Est. cost: ~${est_cost:.2f}")

        if dry_run:
            print("  [DRY RUN]")
            continue

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: Set GEMINI_API_KEY")
            sys.exit(1)

        client = genai.Client(api_key=api_key)

        # Backup
        backup_file = PRODUCTION_DIR / vol_key / "transcriptions_pre_llm_normalize.json"
        if not backup_file.exists():
            with open(results_file, "r", encoding="utf-8") as f:
                backup_data = f.read()
            with open(backup_file, "w", encoding="utf-8") as f:
                f.write(backup_data)
            print(f"  Backed up to {backup_file.name}")

        normalized_file = PRODUCTION_DIR / vol_key / "normalized_transcriptions.json"
        normalized = {}
        if normalized_file.exists():
            with open(normalized_file, encoding="utf-8") as f:
                normalized = json.load(f)

        done = sum(1 for v in normalized.values() if v.get("status") == "success")
        errors = 0

        for pkey in sorted(data.keys(), key=lambda x: int(x)):
            entry = data[pkey]
            if entry.get("status") != "success":
                continue

            if pkey in normalized and normalized[pkey].get("status") == "success":
                continue

            text = entry["transcription"]
            print(f"  [{done+1}/{total_pages}] p{pkey}...", end="", flush=True)

            try:
                response = client.models.generate_content(
                    model=model_id,
                    contents=[text],
                    config=types.GenerateContentConfig(
                        system_instruction=LLM_NORMALIZE_PROMPT,
                        temperature=0.0,
                        max_output_tokens=16000,
                        thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
                    )
                )

                result_text = ""
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "thought") and part.thought:
                            continue
                        if part.text:
                            result_text += part.text

                # Sanity check: output shouldn't be drastically different in length
                len_ratio = len(result_text.strip()) / max(len(text), 1)
                if 0.7 < len_ratio < 1.3:
                    normalized[pkey] = {
                        "status": "success",
                        "transcription": result_text.strip(),
                        "original_length": len(text),
                        "normalized_length": len(result_text.strip()),
                    }
                    done += 1
                    print(f" OK ({len(text)}→{len(result_text.strip())} chars)")
                else:
                    normalized[pkey] = {
                        "status": "error",
                        "error": f"Length mismatch: {len(text)}→{len(result_text.strip())} (ratio={len_ratio:.2f})",
                    }
                    errors += 1
                    print(f" LENGTH MISMATCH (ratio={len_ratio:.2f})")

            except Exception as e:
                normalized[pkey] = {"status": "error", "error": str(e)}
                errors += 1
                print(f" ERROR: {str(e)[:80]}")

            # Save after each page
            with open(normalized_file, "w", encoding="utf-8") as f:
                json.dump(normalized, f, ensure_ascii=False, indent=2)

            time.sleep(2)

        # Merge successful normalizations back
        merged = 0
        for pkey, norm_entry in normalized.items():
            if norm_entry.get("status") == "success":
                data[pkey]["transcription"] = norm_entry["transcription"]
                data[pkey]["llm_normalized"] = True
                merged += 1

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n  {vol_key}: {merged} pages normalized, {errors} errors")


def show_stats(volumes: list):
    """Show notation statistics across volumes."""
    for vol_key in volumes:
        results_file = PRODUCTION_DIR / vol_key / "transcriptions.json"
        if not results_file.exists():
            print(f"  {vol_key}: transcriptions.json not found")
            continue

        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        stats = collect_stats(data)

        print(f"\n  {'='*50}")
        print(f"  {vol_key} — Notation Statistics")
        print(f"  {'='*50}")
        for key, count in sorted(stats.items(), key=lambda x: -x[1]):
            print(f"    {key:<35} {count:>4} pages")


def main():
    parser = argparse.ArgumentParser(description="Normalize notation in transcriptions")
    parser.add_argument("--mode", choices=["regex", "llm"],
                        help="Normalization mode")
    parser.add_argument("--volume", choices=list(VOLUMES.keys()) + ["all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--stats", action="store_true",
                        help="Show notation statistics only")
    parser.add_argument("--model", choices=["pro", "flash-lite"], default="flash-lite",
                        help="Model for LLM mode (default: flash-lite)")
    parser.add_argument("--thinking", default="low",
                        help="Thinking level for LLM mode")
    args = parser.parse_args()

    volumes = list(VOLUMES.keys()) if args.volume == "all" else [args.volume]

    if args.stats:
        show_stats(volumes)
        return

    if not args.mode:
        parser.error("--mode required (or use --stats)")

    print("=" * 70)
    print(f"NOTATION NORMALIZATION — Mode: {args.mode}")
    print("=" * 70)

    if args.mode == "regex":
        normalize_regex(volumes, dry_run=args.dry_run, verbose=args.verbose)
    elif args.mode == "llm":
        normalize_llm(volumes, dry_run=args.dry_run, model_key=args.model,
                       thinking_level=args.thinking)

    if not args.dry_run:
        print("\nPost-normalization stats:")
        show_stats(volumes)


if __name__ == "__main__":
    main()
