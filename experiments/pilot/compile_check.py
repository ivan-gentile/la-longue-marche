"""Compile each deliverable with pdflatex and attribute every error to a page.

`audit_corpus.py` checks that a page is *structurally* sound — no echo, no
leaked reasoning, no truncation, environments matched. That is not the same
as compiling: a transcription of handwritten mathematics can be perfectly
well-formed as text and still contain a missing `$` or an unbalanced brace
that stops LaTeX.

This script closes that gap. It compiles each file in `tex_output/` once,
with `tex_output/preamble.tex`, reads the line numbers back out of the log,
and maps them to the `%% ===== Page N =====` markers, so every error is
attributed to the page that produced it. The result is
`experiments/pilot/COMPILE_REPORT.md`: how many pages compile clean, and
exactly which ones do not.

Requires a TeX distribution (`pdflatex`, plus tikz-cd, ulem, cancel,
mathtools). Skips cleanly if pdflatex is absent.

Usage:
    python experiments/pilot/compile_check.py
    python experiments/pilot/compile_check.py --only varietes_categories_U46
"""

from __future__ import annotations

import argparse
import bisect
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TEX_OUT = REPO / "tex_output"

FILES = [
    ("la_longue_marche_140-3_mateo-canonical", 696, "La Longue Marche 140-3 (canonical)"),
    ("la_longue_marche_140-4_mateo-canonical", 280, "La Longue Marche 140-4 (canonical)"),
    ("la_longue_marche_140-3_flash-lite-mateo", 696, "La Longue Marche 140-3 (flash-lite)"),
    ("la_longue_marche_140-4_flash-lite-mateo", 280, "La Longue Marche 140-4 (flash-lite)"),
    ("bourbaki_schemes_pages_flash-lite", 437, "Préschémas (Bourbaki Schémas)"),
    ("varietes_categories_U46", 100, "Catégories de variétés (U46)"),
]

PAGE_MARKER_RE = re.compile(r"^%% ===== Page (\d+) =====", re.M)
ERROR_RE = re.compile(r"^(!.*?)$\n(?:.*?\n)??l\.(\d+)", re.M | re.S)


def page_index(tex: str) -> tuple[list[int], list[int]]:
    """Return (marker line numbers, page numbers) for bisecting."""
    lines, pages = [], []
    for m in PAGE_MARKER_RE.finditer(tex):
        lines.append(tex.count("\n", 0, m.start()) + 1)
        pages.append(int(m.group(1)))
    return lines, pages


def compile_one(stem: str, workdir: Path, timeout: int) -> tuple[str, int, bool]:
    """Compile one file; return (log text, pdf page count, timed_out).

    A file that makes pdflatex hang must not take the whole report down with
    it: the process is killed, the partial log is still read, and the run
    moves on to the next file.
    """
    shutil.copy(TEX_OUT / f"{stem}.tex", workdir / f"{stem}.tex")
    (workdir / "doc.tex").write_text(
        f"\\input{{preamble}}\n\\input{{{stem}}}\n\\end{{document}}\n", encoding="utf-8"
    )
    timed_out = False
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-no-shell-escape",
             "-jobname", stem, "doc.tex"],
            cwd=workdir, capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(["pkill", "-f", f"-jobname {stem}"], capture_output=True)
    log = workdir / f"{stem}.log"
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    pdf = workdir / f"{stem}.pdf"
    pages = 0
    if pdf.exists():
        try:
            import fitz
            pages = len(fitz.open(str(pdf)))
        except Exception:
            pages = -1
    return text, pages, timed_out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="compile just this stem")
    ap.add_argument("--timeout", type=int, default=600,
                    help="seconds allowed per file before pdflatex is killed "
                         "and the file is reported as hanging (default 600)")
    args = ap.parse_args()

    if not shutil.which("pdflatex"):
        print("pdflatex not found — skipping compile check")
        return

    targets = [f for f in FILES if not args.only or f[0] == args.only]
    rows, details = [], []

    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        shutil.copy(TEX_OUT / "preamble.tex", workdir / "preamble.tex")

        for stem, total, label in targets:
            src = TEX_OUT / f"{stem}.tex"
            if not src.exists():
                continue
            tex = src.read_text(encoding="utf-8")
            marker_lines, marker_pages = page_index(tex)

            log, pdf_pages, timed_out = compile_one(stem, workdir, args.timeout)

            # The body is \input at a fixed offset; line numbers in the log
            # refer to the body file itself, so they map directly.
            by_page: Counter = Counter()
            kinds: Counter = Counter()
            for msg, lineno in ERROR_RE.findall(log):
                idx = bisect.bisect_right(marker_lines, int(lineno)) - 1
                if 0 <= idx < len(marker_pages):
                    by_page[marker_pages[idx]] += 1
                kinds[re.sub(r"\d+", "N", msg.strip())[:60]] += 1

            n_errors = sum(kinds.values())
            bad_pages = sorted(by_page)

            # How far did the compiler actually get? pdflatex stops at a fatal
            # error, at its 100-error limit, or when we kill it — and pages it
            # never read must not be counted as clean. Without this, a single
            # bad page early in a file silently certified every page after it.
            reached_line = max(
                (int(n) for n in re.findall(r"^l\.(\d+)", log, re.M)), default=0)
            aborted = (timed_out
                       or "Fatal error occurred" in log
                       or "That makes 100 errors" in log)
            if aborted and reached_line:
                idx = bisect.bisect_right(marker_lines, reached_line) - 1
                verified_to = marker_pages[idx] if 0 <= idx < len(marker_pages) else 0
            else:
                verified_to = total
            clean = max(verified_to - len([p for p in bad_pages if p <= verified_to]), 0)
            rows.append((label, stem, total, clean, len(bad_pages), n_errors,
                         pdf_pages, timed_out, verified_to))

            if bad_pages:
                details.append(f"### {label}\n")
                details.append(
                    f"{len(bad_pages)} page(s) produce LaTeX errors. Most common:\n")
                details.append("\n".join(
                    f"- {v}x `{k}`" for k, v in kinds.most_common(6)) + "\n")
                shown = ", ".join(
                    f"{p} ({by_page[p]})" for p in bad_pages[:40])
                more = f" … and {len(bad_pages) - 40} more" if len(bad_pages) > 40 else ""
                details.append(f"\nPages (error count): {shown}{more}\n")
            scope = ("" if verified_to == total
                     else f" (compiler only reached page {verified_to}; "
                          f"pages {verified_to + 1}-{total} were never read)")
            print(f"{label}: {clean}/{verified_to} pages compile clean{scope}, "
                  f"{n_errors} errors, PDF {pdf_pages} pages"
                  + ("  [pdflatex HUNG]" if timed_out else ""))

    lines = [
        "# Compile check",
        "",
        f"Generated {date.today().isoformat()} by "
        "`experiments/pilot/compile_check.py` with `tex_output/preamble.tex`.",
        "",
        "`audit_corpus.py` checks that pages are structurally sound. This is the "
        "separate question of whether the LaTeX actually compiles: a "
        "transcription of handwritten mathematics can be well-formed as text and "
        "still carry a missing `$` or an unbalanced brace. Errors are attributed "
        "to the page whose `%% ===== Page N =====` marker precedes them.",
        "",
        "A compiler that stops early has not certified the pages it never "
        "read: the **Verified through** column says how far it got, and "
        "**Compile clean** counts only within that range.",
        "",
        "| Document | Pages | Verified through | Compile clean | With errors | Total errors | PDF pages |",
        "|---|---|---|---|---|---|---|",
    ]
    for label, stem, total, clean, bad, errs, pdf_pages, timed_out, verified_to in rows:
        state = (f"{pdf_pages}" if pdf_pages
                 else ("— (pdflatex hung)" if timed_out else "— (aborted)"))
        scope = ("all" if verified_to == total else f"page {verified_to} only")
        lines.append(f"| {label} | {total} | {scope} | **{clean}** | {bad} | {errs} | {state} |")
    lines += ["", *details]

    out = HERE / "COMPILE_REPORT.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
