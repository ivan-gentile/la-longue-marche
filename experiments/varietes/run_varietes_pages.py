"""Page-by-page transcription of *Catégories de variétés* (U46).

Grothendieck typescript "Préliminaires au livre des variétés —
Catégories de variétés" (document n° 262, April 1957), 100 pages,
scans published by the CSG as U46.pdf. Requested by Mateo (2026-08-09)
as an additional straightforward case for the preliminary-draft
workflow.

Same census-gated design as experiments/bourbaki/run_bourbaki_pages.py:
one API call per PDF page, `%% ===== Page N =====` markers written by
the pipeline from the PDF index, so no page can disappear silently.
Unlike the Bourbaki typescript, this one has the mathematical script
letters written in by hand, so it runs on Gemini Pro with thinking
(~$8 for 100 pages at the assumed Pro prices below — thinking tokens
are billed at the output rate and dominate the bill).

Results accumulate in experiments/varietes/production-pages/
transcriptions.json (resume-safe); the final tex is written to
tex_output/varietes_categories_U46.tex.

Usage:
    python experiments/varietes/run_varietes_pages.py [--limit N]
    python experiments/varietes/run_varietes_pages.py --build-only

Existing results are always loaded and never re-paid; to start over,
delete production-pages/transcriptions.json explicitly.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PDF_PATH = REPO / "raw_pdf" / "U46.pdf"
OUT_DIR = HERE / "production-pages"
TEX_OUT = REPO / "tex_output"
TEX_NAME = "varietes_categories_U46.tex"

MODEL_ID = "gemini-3.1-pro-preview"
THINKING_LEVEL = "medium"
# USD per 1M tokens. Thinking tokens bill at the output rate.
PRICES = {"in": 2.00, "out": 12.00}
MAX_OUTPUT_TOKENS = 16000
DELAY = 3.0
MAX_BACKOFF = 300
# Consecutive quota errors after which the run aborts loudly instead of
# grinding through every remaining page at MAX_BACKOFF (the historical
# silent-quota failure mode documented in experiments/bourbaki/GAPS.md).
MAX_CONSECUTIVE_QUOTA_ERRORS = 5
# Similarity above which a page is assumed to have echoed its context page
# instead of transcribing its target. Distinct pages of this typescript score
# well under 0.10; a genuine echo scores above 0.90.
ECHO_SIMILARITY_THRESHOLD = 0.75

PROMPT = r"""This is one scanned page from the Grothendieck archives — the typescript
"Préliminaires au livre des variétés — Catégories de variétés" (document n° 262,
French, April 1957). The body is typewritten; the mathematical script letters
(calligraphic capitals such as C, M, V, Phi) and some symbols or corrections are
written in BY HAND between the typed characters.

## Your task
Transcribe the page attached under the [TARGET PAGE] label into LaTeX. A page
may also be attached under [CONTEXT — PREVIOUS PAGE]; that one exists only so
you can resolve words broken across the page break, and must NOT be
transcribed. If your output ends up reproducing the context page's content,
you have transcribed the wrong page.

Rules:
1. French prose exactly as typed, preserving accents, original spelling and
   punctuation. Do not modernise or correct the text.
2. Mathematical notation in LaTeX. The handwritten calligraphic capitals are
   mathematical objects: render them as $\mathcal{C}$, $\mathcal{M}$,
   $\mathcal{V}$, etc. Other math: $f(M)$, $f: M \to N$, $M \in \mathcal{M}$,
   subscripts $f_i$, $X_j$, etc.
2bis. Decorators on letters are meaningful notation, never emphasis and never
   scanning noise:
   - An underline under a math symbol of ANY alphabet keeps the underline in
     math mode: $\underline{K}$, $\underline{O}_X$,
     $\underline{\mathrm{Hom}}_{\underline{O}}$, $\underline{\Phi}$. The text
     deliberately contrasts $K$ with $\underline{K}$ and writes the structure
     sheaf as $\underline{O}_X$ — collapsing the underline destroys the
     distinction.
   - A handwritten hat over a letter is likewise meaningful: $\hat{\mathcal{C}}$,
     $\hat{G}$, $\hat{F}$. The text deliberately contrasts $\mathcal{C}$-espace
     with $\hat{\mathcal{C}}$-espace, and states identities such as
     $\hat{G}F = \hat{G}\hat{F}$.
3. Displayed or set-off conditions/axioms keep their labels exactly:
   M 1), M' 2), CV 3), CT 1), etc.
4. Headings: "Paragraphe : 1. ..." and similar become \section*{...};
   numbered sub-items keep their numbering (1., 2., 11. bis, a), etc.).
5. Statements like "PROPOSITION 16. -" stay in the body text as typed
   (small caps not required; keep the wording and numbering exactly).
6. Underlined French words or phrases in the prose (not math symbols, which
   rule 2bis covers): \emph{...}
6bis. Commutative diagrams or arrow diagrams (typed or hand-drawn):
   \begin{tikzcd}...\end{tikzcd}
7. If a handwritten correction changes the typed text, follow the corrected
   reading and do not reproduce the crossed-out version.
8. The typescript's own page number (e.g. "- 48 -") and the document stamp
   ("n° 262"): record them once at the top as a LaTeX comment line, e.g.
   "% typescript page 48 — n° 262", never as body text.
9. Archival marginalia (red-ink archive notes, stamps, hole punches):
   preserve as a LaTeX comment line, e.g. "% [marge: Archives Grothendieck
   Avril 57]".
10. Uncertain reading: [unclear: best guess]

## Do NOT
- Do NOT add page markers or page numbers of your own.
- Do NOT add commentary or explanation.
- Do NOT wrap the output in a full document (no \documentclass, no \begin{document}).
- Do NOT use code fences.

Output pure LaTeX body only — the content of this single page.
"""


def extract_page(doc, page_idx: int) -> bytes:
    import fitz

    single = fitz.open()
    single.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
    data = single.tobytes()
    single.close()
    return data


def save_results(results: dict, results_file: Path) -> None:
    """Atomically replace transcriptions.json.

    A plain write_text truncates first, so a kill mid-write would leave the
    only copy of every paid page unparseable.
    """
    tmp = results_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, results_file)


def request_page(client, types, doc, page_idx: int, corrective: bool = False):
    """One transcription call. Returns (text, usage); raises on empty/truncated.

    Each label precedes the PDF it describes. With the label placed *after*
    the bytes, Gemini Pro read it as tagging the following part and
    transcribed the context page instead of the target one.
    """
    parts = []
    if page_idx > 0:
        parts.append(types.Part.from_text(
            text=f"[CONTEXT — PREVIOUS PAGE] The PDF below is PDF page {page_idx} "
                 f"of the document. It is background only. Do NOT transcribe it."
        ))
        parts.append(
            types.Part.from_bytes(
                data=extract_page(doc, page_idx - 1), mime_type="application/pdf"
            )
        )
    parts.append(types.Part.from_text(
        text=f"[TARGET PAGE] The PDF below is PDF page {page_idx + 1} of the "
             f"document. This is the page to transcribe."
    ))
    parts.append(
        types.Part.from_bytes(data=extract_page(doc, page_idx), mime_type="application/pdf")
    )
    parts.append(types.Part.from_text(text=PROMPT))
    if corrective:
        parts.append(types.Part.from_text(
            text="IMPORTANT: a previous attempt returned the CONTEXT page's text. "
                 "Transcribe only the [TARGET PAGE] attachment — the last PDF "
                 "attached — and ignore the context page entirely."
        ))

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[types.Content(parts=parts)],
        config=types.GenerateContentConfig(
            temperature=1.0,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
        ),
    )
    candidate = response.candidates[0]
    text = "".join(
        p.text for p in candidate.content.parts
        if p.text and not getattr(p, "thought", False)
    ).strip()

    # An empty or truncated candidate must not be stored as success: it would
    # be skipped forever by the resume logic and rendered as a silently blank
    # page in the tex.
    finish = str(getattr(candidate, "finish_reason", ""))
    if not text:
        raise RuntimeError(f"empty output (finish_reason={finish})")
    if "STOP" not in finish.upper():
        raise RuntimeError(f"truncated output (finish_reason={finish})")

    um = getattr(response, "usage_metadata", None)
    usage = {
        "prompt_tokens": getattr(um, "prompt_token_count", None),
        "output_tokens": getattr(um, "candidates_token_count", None),
        "thinking_tokens": getattr(um, "thoughts_token_count", None),
    } if um is not None else {}
    return text, usage


def echo_similarity(text: str, prev_entry: dict) -> float:
    """How much this page's output looks like the previous page's output."""
    prev = (prev_entry or {}).get("transcription", "")
    if not prev or not text:
        return 0.0
    return difflib.SequenceMatcher(None, prev, text).ratio()


def placeholder_reason(entry: dict) -> str:
    if not entry:
        return "not yet attempted in this run"
    err = str(entry.get("error", ""))
    if "RESOURCE_EXHAUSTED" in err or "'code': 429" in err or err.startswith("429"):
        return "API daily quota exhausted (HTTP 429); queued for a future run"
    if err:
        return err.splitlines()[0][:120]
    return "no transcription recorded"


def build_tex(results: dict, total_pages: int) -> Path:
    success = sum(1 for v in results.values() if v.get("status") == "success")
    lines = [
        "% Catégories de variétés (Préliminaires au livre des variétés, n° 262)",
        "% Source scans: U46.pdf (CSG, csg.igrothendieck.org)",
        f"% Model: {MODEL_ID} (thinking={THINKING_LEVEL})",
        "% Markers written by the pipeline from the PDF page index",
        f"% Pages transcribed: {success}/{total_pages}",
        f"% Rebuilt: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]
    for page in range(1, total_pages + 1):
        entry = results.get(str(page), {})
        lines.append(f"%% ===== Page {page} =====")
        lines.append("")
        if entry.get("status") == "success":
            if entry.get("warning"):
                lines.append(f"%% [REVIEW: {entry['warning']}]")
            lines.append(entry.get("transcription", "").strip())
        else:
            lines.append(f"%% [page {page} not transcribed: {placeholder_reason(entry)}]")
        lines.append("")
        if page < total_pages:
            lines.append("\\newpage")
            lines.append("")
    out = TEX_OUT / TEX_NAME
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)} ({success}/{total_pages} pages)")
    return out


def write_summary(results: dict, total_pages: int, errors_this_run: int) -> float:
    ok = [v for v in results.values() if v.get("status") == "success"]
    tok_in = sum(v.get("usage", {}).get("prompt_tokens") or 0 for v in ok)
    tok_out = sum(v.get("usage", {}).get("output_tokens") or 0 for v in ok)
    tok_think = sum(v.get("usage", {}).get("thinking_tokens") or 0 for v in ok)
    # Thinking tokens are billed at the output rate and are reported
    # separately from candidates_token_count — leaving them out understates
    # the bill several-fold on a thinking model.
    cost = (tok_in * PRICES["in"] + (tok_out + tok_think) * PRICES["out"]) / 1_000_000
    (OUT_DIR / "summary.json").write_text(
        json.dumps(
            {
                "success": len(ok),
                "errors_this_run": errors_this_run,
                "total_pages": total_pages,
                "tokens_in": tok_in,
                "tokens_out": tok_out,
                "tokens_thinking": tok_think,
                "estimated_cost": round(cost, 3),
                "cost_note": "includes thinking tokens billed at the output rate",
                "model": MODEL_ID,
                "thinking_level": THINKING_LEVEL,
                "finished": datetime.now().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return cost


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resume", action="store_true",
                    help="Accepted for symmetry with the other runners; "
                         "existing results are always loaded and never re-paid")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after N API calls (smoke test)")
    ap.add_argument("--delay", type=float, default=DELAY)
    args = ap.parse_args()

    try:
        from google import genai
        from google.genai import types
        import fitz
    except ImportError:
        print("ERROR: pip install google-genai pymupdf python-dotenv")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_file = OUT_DIR / "transcriptions.json"
    # Always resume: a paid page is never re-run or overwritten by accident.
    results: dict = {}
    if results_file.exists():
        results = json.loads(results_file.read_text(encoding="utf-8"))
        print(f"Loaded {len(results)} existing pages from {results_file.name}")

    doc = fitz.open(str(PDF_PATH))
    total_pages = len(doc)

    if args.build_only:
        build_tex(results, total_pages)
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: set GEMINI_API_KEY in .env")
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    (OUT_DIR / "config.json").write_text(
        json.dumps(
            {
                "pdf": PDF_PATH.name,
                "total_pages": total_pages,
                "model": MODEL_ID,
                "thinking_level": THINKING_LEVEL,
                "mode": "page-by-page",
                "context": "previous_page_pdf",
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "started": datetime.now().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    backoff = args.delay
    done = errors = calls = 0
    consecutive_quota_errors = 0
    aborted = False

    for page_idx in range(total_pages):
        pkey = str(page_idx + 1)
        if results.get(pkey, {}).get("status") == "success":
            continue
        if args.limit is not None and calls >= args.limit:
            print(f"--limit {args.limit} reached, stopping")
            break

        print(f"  [{pkey}/{total_pages}] ...", end="", flush=True)
        t0 = time.monotonic()
        calls += 1
        try:
            text, usage = request_page(client, types, doc, page_idx)

            # Guard against the model transcribing its context page instead of
            # its target — the failure that produced a one-page-shifted corpus
            # on the first attempt at this document.
            prev_entry = results.get(str(page_idx))
            sim = echo_similarity(text, prev_entry)
            warning = None
            if sim >= ECHO_SIMILARITY_THRESHOLD:
                print(f" echo? ({sim:.2f}) retrying...", end="", flush=True)
                calls += 1
                text, usage = request_page(client, types, doc, page_idx, corrective=True)
                sim = echo_similarity(text, prev_entry)
                if sim >= ECHO_SIMILARITY_THRESHOLD:
                    warning = (f"possible context echo: {sim:.2f} similarity to the "
                               f"transcription of page {page_idx}")

            entry = {
                "status": "success",
                "transcription": text,
                "usage": usage,
                "latency_s": round(time.monotonic() - t0, 1),
            }
            if warning:
                entry["warning"] = warning
            results[pkey] = entry
            done += 1
            backoff = args.delay
            consecutive_quota_errors = 0
            print(f" OK ({len(text)}ch)" + (f" [WARNING: {warning}]" if warning else ""))
        except Exception as e:
            err = str(e)
            results[pkey] = {"status": "error", "error": err}
            errors += 1
            print(f" ERROR: {err[:80]}")
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                consecutive_quota_errors += 1
                backoff = min(backoff * 2, MAX_BACKOFF)
                print(f"    backing off {backoff:.0f}s "
                      f"(consecutive quota errors: {consecutive_quota_errors})")
                if consecutive_quota_errors >= MAX_CONSECUTIVE_QUOTA_ERRORS:
                    save_results(results, results_file)
                    print()
                    print("!" * 70)
                    print(f"QUOTA EXHAUSTED — {consecutive_quota_errors} consecutive quota "
                          f"errors, aborting at page {pkey}.")
                    print("Re-run the same command later to continue where this stopped.")
                    print("!" * 70)
                    aborted = True
                    break
            else:
                consecutive_quota_errors = 0

        save_results(results, results_file)
        time.sleep(backoff)

    doc.close()

    cost = write_summary(results, total_pages, errors)
    success = sum(1 for v in results.values() if v.get("status") == "success")
    print(f"\nDone: {success}/{total_pages} pages, {errors} errors this run, "
          f"~${cost:.2f} total (incl. thinking tokens)")
    build_tex(results, total_pages)

    if aborted:
        sys.exit(2)
    if success < total_pages and args.limit is None:
        print(f"WARNING: {total_pages - success} page(s) still untranscribed — "
              f"re-run to fill them in.")
        sys.exit(1)


if __name__ == "__main__":
    main()
