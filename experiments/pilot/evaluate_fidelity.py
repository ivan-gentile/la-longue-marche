"""Content-level fidelity metrics for a transcription against a reference.

Complements diagnose_49_1.py, which scores LaTeX *style conformance*
(scaffolding, canonical notation, pipeline residue). This script measures
what that score cannot see and what matters most for scholarly review:
whether the transcribed *content* matches the reference — omissions,
insertions, and rewordings — using sequence alignment.

Metrics per candidate:
  - char similarity   difflib ratio over comment-stripped, whitespace-
                      collapsed text (markup included)
  - word similarity   difflib ratio over content tokens (LaTeX commands,
                      braces and math delimiters stripped, lowercased)
  - omitted tokens    reference tokens absent from the candidate
                      ("delete" opcodes), with the largest spans quoted —
                      the omission classes Mateo reports live here
  - inserted tokens   candidate tokens absent from the reference
                      (hallucination / duplicated-context indicator)

Absolute values conflate transcription fidelity with Mateo's editorial
layer (the reference is his corrected version, not a diplomatic
transcription), so compare candidates against each other, not to 1.0.

Usage:
    python experiments/pilot/evaluate_fidelity.py --preset 49.1
    python experiments/pilot/evaluate_fidelity.py --reference ref.tex --candidate out.tex
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

COMMENT_RE = re.compile(r"(?m)^\s*%.*$")
ENV_RE = re.compile(r"\\(?:begin|end)\{[a-zA-Z*]+\}")
MATH_DELIM_RE = re.compile(r"\$\$?|\\\[|\\\]")
COMMAND_RE = re.compile(r"\\[a-zA-Z@]+\*?")
TOKEN_RE = re.compile(r"[a-zà-öø-ÿœ0-9'\-]{2,}", re.IGNORECASE)


def normalize_chars(tex: str) -> str:
    s = COMMENT_RE.sub(" ", tex)
    return re.sub(r"\s+", " ", s).strip()


def content_tokens(tex: str) -> list[str]:
    s = COMMENT_RE.sub(" ", tex)
    s = ENV_RE.sub(" ", s)
    s = MATH_DELIM_RE.sub(" ", s)
    s = COMMAND_RE.sub(" ", s)
    s = re.sub(r"[{}~^_&=+|<>]", " ", s)
    return [t.lower() for t in TOKEN_RE.findall(s)]


def compare(reference: str, candidate: str, min_span: int = 8) -> dict:
    ref_c, cand_c = normalize_chars(reference), normalize_chars(candidate)
    char_sim = difflib.SequenceMatcher(None, ref_c, cand_c, autojunk=False).ratio()

    ref_t, cand_t = content_tokens(reference), content_tokens(candidate)
    sm = difflib.SequenceMatcher(None, ref_t, cand_t, autojunk=False)
    word_sim = sm.ratio()

    omitted = inserted = replaced = 0
    spans = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "delete":
            omitted += i2 - i1
            if i2 - i1 >= min_span:
                spans.append({"ref_tokens": i2 - i1, "excerpt": " ".join(ref_t[i1:i2])[:200]})
        elif op == "insert":
            inserted += j2 - j1
        elif op == "replace":
            replaced += i2 - i1
    spans.sort(key=lambda s: -s["ref_tokens"])

    return {
        "char_similarity": round(char_sim, 3),
        "word_similarity": round(word_sim, 3),
        "reference_tokens": len(ref_t),
        "candidate_tokens": len(cand_t),
        "omitted_tokens": omitted,
        "replaced_tokens": replaced,
        "inserted_tokens": inserted,
        "omission_spans": spans[:10],
    }


# ---------------------------------------------------------------------------
# Preset: Section 49.1 — every cached candidate vs Mateo's corrected version
# ---------------------------------------------------------------------------

PAGES_49_1 = [str(p) for p in range(495, 500)]


def _bench_pages(bench: str, field: str) -> str:
    data = json.loads((HERE / bench / "results.json").read_text(encoding="utf-8"))
    parts = []
    for p in PAGES_49_1:
        entry = data.get(f"140-3_p{p}", {}).get(field) or {}
        parts.append(entry.get("text", ""))
    return "\n\n".join(parts)


def _production_pages(prod: str) -> str:
    data = json.loads(
        (HERE / prod / "140-3" / "transcriptions.json").read_text(encoding="utf-8")
    )
    return "\n\n".join(
        data[p]["transcription"] for p in PAGES_49_1 if data.get(p, {}).get("status") == "success"
    )


def preset_49_1() -> None:
    reference = (REPO / "reference" / "validation" / "49.1new.tex").read_text(encoding="utf-8")
    candidates = {
        "shipped baseline (49.1old, text-first-fewshot)": (
            REPO / "reference" / "validation" / "49.1old.tex"
        ).read_text(encoding="utf-8"),
        "Claude Opus 4.7 + mateo-canonical": _bench_pages("bench_mateo_canonical", "claude_pbp"),
        "Gemini 3.1 Pro + mateo-canonical": _bench_pages("bench_mateo_gemini", "gemini_pbp"),
        "Gemini 3.1 Flash-Lite + mateo-canonical": _bench_pages(
            "bench_mateo_flash_lite", "gemini_pbp"
        ),
        "shipped corpus (production Flash-Lite + mateo-canonical)": _production_pages(
            "production-flash-lite-mateo"
        ),
    }

    results = {name: compare(reference, cand) for name, cand in candidates.items()}

    lines = [
        "# Section 49.1 fidelity comparison (content-level)",
        "",
        "Every cached candidate vs Mateo's corrected `49.1new.tex`",
        "(140-3 PDF pages 495-499). Generated by `evaluate_fidelity.py",
        "--preset 49.1` — no API calls, cached outputs only.",
        "",
        "These numbers measure **content agreement** (omissions, insertions,",
        "rewording), the failure classes invisible to the style-conformance",
        "composite in the README. The reference includes Mateo's editorial",
        "layer, so compare candidates against each other, not to 1.0.",
        "",
        "| Candidate | Char sim | Word sim | Omitted | Reworded | Inserted | Ref tokens |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, r in results.items():
        lines.append(
            f"| {name} | {r['char_similarity']} | {r['word_similarity']} "
            f"| {r['omitted_tokens']} | {r['replaced_tokens']} | {r['inserted_tokens']} "
            f"| {r['reference_tokens']} |"
        )
    lines.append("")
    for name, r in results.items():
        if r["omission_spans"]:
            lines.append(f"## Largest omissions — {name}")
            lines.append("")
            for s in r["omission_spans"][:5]:
                lines.append(f"- ({s['ref_tokens']} tokens) “{s['excerpt']}”")
            lines.append("")

    (HERE / "fidelity_49_1.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "fidelity_49_1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", HERE / "fidelity_49_1.md")
    for name, r in results.items():
        print(
            f"  {name}: char {r['char_similarity']}, word {r['word_similarity']}, "
            f"omitted {r['omitted_tokens']}, inserted {r['inserted_tokens']}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preset", choices=["49.1"])
    ap.add_argument("--reference", type=Path)
    ap.add_argument("--candidate", type=Path)
    args = ap.parse_args()

    if args.preset == "49.1":
        preset_49_1()
        return
    if not (args.reference and args.candidate):
        ap.error("provide --preset 49.1 or both --reference and --candidate")
    res = compare(
        args.reference.read_text(encoding="utf-8"), args.candidate.read_text(encoding="utf-8")
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
