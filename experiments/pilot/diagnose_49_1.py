"""Diagnostic: compare our pipeline output against Mateo's corrected version.

Reads:
  reference/validation/49.1old.tex  — produced by current pipeline (Gemini 3.1 Pro)
  reference/validation/49.1new.tex  — Mateo's corrected, publishable version

Writes:
  experiments/pilot/49_1_error_profile.md   (human-readable report)
  experiments/pilot/49_1_error_profile.json (machine-readable, consumed by the
                                              benchmark scorer and the blog post)

The categories are derived from a side-by-side inspection of the two files.
They are designed to be applicable to any other Part II page we transcribe,
so the same script can later score Opus and refreshed Gemini outputs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
OLD_PATH = REPO / "reference" / "validation" / "49.1old.tex"
NEW_PATH = REPO / "reference" / "validation" / "49.1new.tex"
OUT_MD = HERE / "49_1_error_profile.md"
OUT_JSON = HERE / "49_1_error_profile.json"


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

# Signals that an `old` file is raw pipeline output, not publishable LaTeX.
# Each pattern here should ideally appear 0 times in a clean `new` file.
RAW_PIPELINE_SIGNALS: list[tuple[str, str, str]] = [
    ("unresolved_unclear", r"\[unclear[^\]]*\]", "Unresolved `[unclear]` markers (model hedged instead of committing)"),
    ("margin_placeholder", r"\[MARGIN:[^\]]*\]", "Margin notes left as `[MARGIN: ...]` placeholders (should be footnotes or \\leqno labels)"),
    ("diagram_placeholder", r"\[DIAGRAM:[^\]]*\]", "Diagram placeholders (should be tikzcd / tikzpicture)"),
    ("crossed_out_placeholder", r"\[crossed out[^\]]*\]|\[unclear crossed[^\]]*\]", "Crossed-out markers kept inline"),
    ("raw_page_separator", r"%% ===== Page \d+ =====", "Raw page separators from the pipeline (no place in a compiled chapter)"),
    ("raw_newpage", r"\\newpage", "Free-standing \\newpage from the pipeline"),
]

# Publishable-LaTeX structure that `new` has and `old` typically lacks.
# A good output of our pipeline should tend towards these counts.
STRUCTURE_MARKERS: list[tuple[str, str, str]] = [
    ("chapter_heading", r"\\chapter\*", "`\\chapter*` heading"),
    ("toc_entry", r"\\addcontentsline", "TOC entries (\\addcontentsline)"),
    ("label_anchor", r"\\label\{", "`\\label{...}` anchors"),
    ("leqno_numbering", r"\\leqno", "Left-side equation numbering (\\leqno)"),
    ("footnote", r"\\footnote\{|\\footnotetext\{", "Footnotes (from authorial margin commentary)"),
    ("tikzpicture", r"\\begin\{tikzpicture\}", "Real tikzpicture environments"),
    ("tikzcd", r"\\begin\{tikzcd\}", "Real tikzcd commutative diagrams"),
    ("aligned_env", r"\\begin\{aligned\}", "Aligned math environments"),
    ("operatorname", r"\\operatorname\{", "\\operatorname{...} instead of \\text{...}"),
    ("user_macro_Ker", r"\\Ker\b", "`\\Ker` user macro (instead of \\ker)"),
    ("user_macro_Aut", r"\\Aut\b", "`\\Aut` user macro"),
    ("user_macro_SL", r"\\SL\b", "`\\SL` user macro (instead of Sl or SL)"),
    ("user_macro_defeq", r"\\defeq\b", "`\\defeq` macro (definition-equals)"),
    ("user_macro_isom", r"\\isom\b", "`\\isom` macro (isomorphism)"),
]

# Symbol-level notation drift: (label, pattern in old, pattern in new)
# Mateo's canonical form is on the right.
NOTATION_DRIFT: list[tuple[str, str, str, str]] = [
    ("hat_G_to_frakS", r"\\widehat\{\\mathfrak\{G\}\}|\\hat\{\\mathfrak\{G\}\}|\\hat\{\\mathcal\{G\}\}", r"\\mathfrak\{S\}",
        r"`\widehat{\mathfrak{G}}_{0,3}^+` or `\hat{\mathcal{G}}` → canonical `\mathfrak{S}_{0,3}^{+\wedge}`"),
    ("text_int_to_op", r"\\text\{int\}", r"\\operatorname\{int\}",
        r"`\text{int}` → `\operatorname{int}`"),
    ("text_Norm_to_op", r"\\text\{Norm\}|\bNorm_", r"\\operatorname\{Norm\}",
        r"`\text{Norm}` / `Norm_` → `\operatorname{Norm}`"),
    ("Cent_to_Centr", r"\bCent_", r"\\operatorname\{Centr\}",
        r"`Cent_M` → `\underline{\operatorname{Centr}}_\mathcal{M}`"),
    ("Zhat_bb_to_bf", r"\\hat\{\\mathbb\{Z\}\}", r"\\hat\{\\mathbf\{Z\}\}",
        r"`\hat{\mathbb{Z}}` → `\hat{\mathbf{Z}}`"),
    ("L_bb_to_upright", r"\\mathbb\{L\}_", r"L_[0-9a-zA-Z]*\^\\mathfrak",
        r"`\mathbb{L}_0^\sim` → `L_0^\mathfrak{S}`"),
    ("lowerker_to_upper", r"\\ker\(", r"\\Ker\(",
        r"`\ker(...)` → `\Ker(...)`"),
    ("Sl_to_SL", r"\bSl\(", r"\\SL",
        r"`Sl(` → `\SL`"),
    ("calC_to_frakS", r"\\mathcal\{C\}", r"\\mathfrak\{S\}",
        r"`\mathcal{C}` (image of phi) → `\mathfrak{S}`"),
    ("lowercase_g_to_calG", r"(?<![A-Za-z\\])g(?![A-Za-z])", r"\\mathcal\{G\}",
        r"lowercase `g` subgroup → `\mathcal{G}`"),
]

# French-abbreviation residue (expansions Mateo prefers)
ABBREVIATION_RESIDUE: list[tuple[str, str, str]] = [
    ("abbr_hom", r"\bhom\.\b", "`hom.` → `homomorphisme`"),
    ("abbr_autom", r"\bautom\.\b", "`autom.` → `automorphisme`"),
    ("abbr_ss_groupe", r"\bss-groupe\b", "`ss-groupe` → `sous-groupe`"),
    ("abbr_s_g", r"\bs-g\b", "`s-g` → `sous-groupe`"),
    ("abbr_c_j", r"\bc-j\.\b", "`c-j.` → `conjugaison`"),
    ("abbr_cent", r"\bcent\.\b", "`cent.` → `centralisateur`"),
]


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def count_all(patterns: list[tuple], text: str) -> dict[str, int]:
    """Return {id: count} for each pattern tuple (id, pattern, [rest])."""
    out: dict[str, int] = {}
    for item in patterns:
        key, pat = item[0], item[1]
        out[key] = len(re.findall(pat, text))
    return out


def categorize(old: str, new: str) -> dict:
    raw = count_all(RAW_PIPELINE_SIGNALS, old)
    raw_new = count_all(RAW_PIPELINE_SIGNALS, new)  # sanity: should be ~0
    struct_old = count_all(STRUCTURE_MARKERS, old)
    struct_new = count_all(STRUCTURE_MARKERS, new)
    notation_old = {k: len(re.findall(pat_old, old)) for (k, pat_old, _, _) in NOTATION_DRIFT}
    notation_new = {k: len(re.findall(pat_old, new)) for (k, pat_old, _, _) in NOTATION_DRIFT}  # drift that survived
    abbr_old = count_all(ABBREVIATION_RESIDUE, old)
    abbr_new = count_all(ABBREVIATION_RESIDUE, new)

    return {
        "raw_pipeline_signals": {"old": raw, "new": raw_new},
        "structure_markers": {"old": struct_old, "new": struct_new},
        "notation_drift_in_old": notation_old,
        "notation_drift_in_new": notation_new,
        "abbreviation_residue": {"old": abbr_old, "new": abbr_new},
        "lengths": {"old_chars": len(old), "new_chars": len(new)},
    }


def score(profile: dict) -> dict:
    """Compute a simple normalized quality score in [0, 1].

    Heuristic: 1.0 would be 'no raw pipeline leftovers, all Mateo-style
    structure present, no notation drift, no raw abbreviations'. It's a
    coarse summary we can report per-page for other transcriptions.
    """
    raw_leftovers = sum(profile["raw_pipeline_signals"]["old"].values())
    # Count of distinct structure kinds that are present (>=1) in old
    structure_present = sum(1 for v in profile["structure_markers"]["old"].values() if v > 0)
    structure_total = len(profile["structure_markers"]["old"])
    notation_drift = sum(profile["notation_drift_in_old"].values())
    abbr_hits = sum(profile["abbreviation_residue"]["old"].values())
    # Normalize per 1000 chars of old text to make it comparable page-to-page
    k = max(profile["lengths"]["old_chars"] / 1000.0, 1.0)
    raw_density = raw_leftovers / k
    notation_density = notation_drift / k
    abbr_density = abbr_hits / k

    # Turn densities into penalties in [0, 1], cap at reasonable levels
    def cap(x, hi):
        return min(x / hi, 1.0)

    penalty = (
        0.40 * cap(raw_density, 3.0)  # unresolved markers, margins, diagram placeholders
        + 0.30 * (1.0 - structure_present / structure_total)
        + 0.20 * cap(notation_density, 3.0)
        + 0.10 * cap(abbr_density, 2.0)
    )
    return {
        "raw_density_per_kchar": round(raw_density, 2),
        "notation_density_per_kchar": round(notation_density, 2),
        "abbr_density_per_kchar": round(abbr_density, 2),
        "structure_coverage": round(structure_present / structure_total, 2),
        "composite_penalty": round(penalty, 3),
        "quality": round(1.0 - penalty, 3),
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_markdown(profile: dict, scr: dict) -> str:
    def row(cat: list, old_counts: dict, new_counts: dict | None = None) -> list[str]:
        lines = []
        header = "| id | description | old | new |" if new_counts else "| id | description | hits |"
        sep = "|----|-------------|-----|-----|" if new_counts else "|----|-------------|-----|"
        lines.append(header)
        lines.append(sep)
        for item in cat:
            key, _, desc = item[0], item[1], item[-1]
            if new_counts is not None:
                lines.append(f"| `{key}` | {desc} | {old_counts[key]} | {new_counts[key]} |")
            else:
                lines.append(f"| `{key}` | {desc} | {old_counts[key]} |")
        return lines

    out = []
    out.append("# Section 49.1 error profile")
    out.append("")
    out.append(
        "Categorized comparison of our pipeline output "
        "([`49.1old.tex`](../../reference/validation/49.1old.tex), "
        f"{profile['lengths']['old_chars']:,} chars) against "
        "Mateo's corrected version "
        "([`49.1new.tex`](../../reference/validation/49.1new.tex), "
        f"{profile['lengths']['new_chars']:,} chars)."
    )
    out.append("")
    out.append(
        "The categories are designed to be reused on any Part II page. The "
        "same script can score Opus 4.7 output or refreshed Gemini output "
        "against Mateo's conventions, not just Section 49.1."
    )
    out.append("")
    out.append("## Summary score")
    out.append("")
    out.append(f"- Composite quality (old, higher is better): **{scr['quality']:.3f}** / 1.0")
    out.append(f"- Structure coverage: {scr['structure_coverage']:.0%} of Mateo-style markers present at least once")
    out.append(f"- Raw pipeline residue density: {scr['raw_density_per_kchar']} per 1 000 chars")
    out.append(f"- Notation drift density: {scr['notation_density_per_kchar']} per 1 000 chars")
    out.append(f"- French abbreviation residue density: {scr['abbr_density_per_kchar']} per 1 000 chars")
    out.append("")
    out.append("## 1. Raw pipeline signals (should be 0 in a publishable file)")
    out.append("")
    out += row(RAW_PIPELINE_SIGNALS, profile["raw_pipeline_signals"]["old"],
               profile["raw_pipeline_signals"]["new"])
    out.append("")
    out.append("## 2. Publishable structure Mateo uses")
    out.append("")
    out += row(STRUCTURE_MARKERS, profile["structure_markers"]["old"],
               profile["structure_markers"]["new"])
    out.append("")
    out.append("## 3. Notation drift (old vs canonical)")
    out.append("")
    out.append("| id | description | hits in old | surviving in new |")
    out.append("|----|-------------|-------------|------------------|")
    for (key, _pat_old, _pat_new, desc) in NOTATION_DRIFT:
        out.append(
            f"| `{key}` | {desc} | "
            f"{profile['notation_drift_in_old'][key]} | "
            f"{profile['notation_drift_in_new'][key]} |"
        )
    out.append("")
    out.append("## 4. French abbreviation residue")
    out.append("")
    out += row(ABBREVIATION_RESIDUE, profile["abbreviation_residue"]["old"],
               profile["abbreviation_residue"]["new"])
    out.append("")
    out.append("## 5. Takeaways that drive prompt refresh")
    out.append("")
    out.append("- **Primary gap is structural, not mathematical.** The pipeline")
    out.append("  reads Grothendieck well but does not produce publishable LaTeX")
    out.append("  scaffolding (chapter heading, \\leqno, \\label, \\addcontentsline,")
    out.append("  footnotes). Prompt must either require or explicitly forbid this,")
    out.append("  not leave it ambiguous.")
    out.append("- **Margin notes serve multiple purposes in Grothendieck's")
    out.append("  manuscript.** Some are authorial commentary (→ footnote), some")
    out.append("  are equation numbers (→ \\leqno), some are inline annotations.")
    out.append("  `[MARGIN: ...]` as a single placeholder loses this distinction;")
    out.append("  the prompt should mark the intended role.")
    out.append("- **Unresolved `[unclear]` markers are often decidable from math")
    out.append("  context.** Mateo commits to a reading; our pipeline hedges. The")
    out.append("  prompt should encourage committing with a confidence annotation,")
    out.append("  not leaving the token blank.")
    out.append("- **Notation conventions are specific to this manuscript.** Adding")
    out.append("  a canonical-notation block to the prompt (and a few-shot pool")
    out.append("  drawn from sections 19–36 of Part I) addresses most of the")
    out.append("  symbol-level drift.")
    out.append("- **Commutative diagrams are best expressed as `tikzcd` /")
    out.append("  `tikzpicture`.** The diagram-tikzcd prompt already exists; it")
    out.append("  needs to be rolled out across the full corpus.")
    out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def diagnose(old_text: str, new_text: str) -> tuple[dict, dict, str]:
    profile = categorize(old_text, new_text)
    scr = score(profile)
    md = render_markdown(profile, scr)
    return profile, scr, md


def main() -> None:
    old = OLD_PATH.read_text(encoding="utf-8")
    new = NEW_PATH.read_text(encoding="utf-8")
    profile, scr, md = diagnose(old, new)

    OUT_MD.write_text(md, encoding="utf-8")
    OUT_JSON.write_text(json.dumps({"profile": profile, "score": scr}, indent=2), encoding="utf-8")

    print(f"Wrote {OUT_MD.relative_to(REPO)}")
    print(f"Wrote {OUT_JSON.relative_to(REPO)}")
    print()
    print("Score summary:")
    for k, v in scr.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
