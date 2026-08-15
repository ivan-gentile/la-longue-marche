"""Page-by-page re-transcription of the Bourbaki schemes PDF.

Replaces the whole-document chunk mode, whose two defects are documented
in GAPS.md: ~70 of 437 pages silently merged or skipped, and page
markers invented by the model from the typescript's own pagination.
Here the pipeline makes one API call per PDF page and writes the
`%% ===== Page N =====` markers itself from the PDF index, so no page
can disappear silently and every page is navigable against the scan.

Results accumulate in experiments/bourbaki/production-pages/
transcriptions.json (resume-safe); the final tex is written to
tex_output/bourbaki_schemes_pages_flash-lite.tex.

Usage:
    python experiments/bourbaki/run_bourbaki_pages.py [--resume]
    python experiments/bourbaki/run_bourbaki_pages.py --build-only
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PDF_PATH = REPO / "raw_pdf" / "bourbaki_schemes.pdf"
OUT_DIR = HERE / "production-pages"
TEX_OUT = REPO / "tex_output"

# Pinned deliberately: this document's 437 pages were transcribed with this
# model, and repairs (--pages) must stay on it — mixing models inside one
# transcription would make the corpus inconsistent for review. Newer models
# are in experiments/pilot/models.py; adopting one here means re-running the
# whole document.
MODEL_ID = "gemini-3.1-flash-lite-preview"
PRICES = {"in": 0.25, "out": 1.50}
MAX_OUTPUT_TOKENS = 16000
DELAY = 2.0
MAX_BACKOFF = 300
# Similarity above which a page is assumed to have echoed its context page
# instead of transcribing its target.
ECHO_SIMILARITY_THRESHOLD = 0.75

PROMPT = r"""This is one scanned page from the Bourbaki archives — an early typed
manuscript by Alexander Grothendieck developing the theory of schemes (EGA-era,
French, circa 1958-59).

## Your task
Transcribe the page attached under the [TARGET PAGE] label into LaTeX. A page
may also be attached under [CONTEXT — PREVIOUS PAGE]; that one exists only so
you can resolve words broken across the page break, and must NOT be
transcribed. If your output ends up reproducing the context page's content,
you have transcribed the wrong page.

Rules:
1. French prose exactly as typed, preserving accents.
2. Mathematical notation in LaTeX: $A$, $\mathcal{O}_X$, $\operatorname{Spec}$,
   $\mathbb{Z}$, $f: X \to Y$, etc.
3. Displayed equations: $$ ... $$.
4. Section/subsection headings: \section*{...} or \subsection*{...}
5. Numbered items keep their numbering (§1., 1., a), etc.).
6. Commutative diagrams: \begin{tikzcd}...\end{tikzcd}
7. Underlined or italicised terms: \emph{...}
8. Archival marginalia (stamps, hand-written notes in margins): preserve as
   plain text comments or \marginpar{...}
9. Uncertain reading: [unclear: best guess]

## Do NOT
- Do NOT add page markers or page numbers of your own.
- Do NOT add commentary or explanation.
- Do NOT wrap the output in a full document (no \documentclass, no \begin{document}).
- Do NOT use code fences.

Output pure LaTeX body only — the content of this single page.
"""


def extract_page(doc, page_idx: int) -> bytes:
    single = __import__("fitz").open()
    single.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
    data = single.tobytes()
    single.close()
    return data


def request_page(client, types, doc, page_idx: int, corrective: bool = False):
    """One transcription call. Returns (text, usage); raises on empty output.

    Each label precedes the PDF it describes: with the label placed *after*
    the bytes, the model sometimes read it as tagging the following part and
    transcribed the context page instead of the target one (15 pages of the
    first 437-page run were shifted this way).
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
            temperature=1.0, max_output_tokens=MAX_OUTPUT_TOKENS
        ),
    )
    candidate = response.candidates[0]
    text = "".join(
        p.text for p in candidate.content.parts
        if p.text and not getattr(p, "thought", False)
    ).strip()
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


def _words(text: str) -> list[str]:
    """Lowercased word tokens, insensitive to line wrapping and hyphenation."""
    s = re.sub(r"(?m)^\s*%.*$", " ", text)
    s = re.sub(r"-\s*\n\s*", "", s)
    return [w.lower() for w in re.findall(r"[a-zà-öø-ÿœ0-9]+", s, re.IGNORECASE)]


def echo_similarity(text: str, prev_entry: dict) -> float:
    """Word-level similarity to the previous page.

    Compared at word level deliberately: a character-level comparison
    missed real echoes whose text had merely been re-wrapped (0.21-0.71
    character similarity against 0.75-0.96 word similarity).
    """
    prev = (prev_entry or {}).get("transcription", "")
    a, b = _words(prev), _words(text or "")
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def save_results(results: dict, results_file: Path) -> None:
    """Atomically replace transcriptions.json (a truncating write can lose all)."""
    tmp = results_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, results_file)


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
        "% Bourbaki schemes — page-by-page transcription",
        f"% Model: {MODEL_ID}",
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
    out = TEX_OUT / "bourbaki_schemes_pages_flash-lite.tex"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)} ({success}/{total_pages} pages)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--delay", type=float, default=DELAY)
    ap.add_argument("--pages", type=int, nargs="+", default=None,
                    help="Re-transcribe these PDF pages even if already successful "
                         "(used to repair the context-echo pages found by "
                         "experiments/pilot/audit_corpus.py)")
    args = ap.parse_args()
    if args.pages:
        args.resume = True  # never discard the rest of the corpus

    try:
        from google import genai
        from google.genai import types
        import fitz
    except ImportError:
        print("ERROR: pip install google-genai pymupdf python-dotenv")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_file = OUT_DIR / "transcriptions.json"
    results: dict = {}
    if (args.resume or args.build_only) and results_file.exists():
        results = json.loads(results_file.read_text(encoding="utf-8"))
        print(f"Loaded {len(results)} existing pages")

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
    done = errors = 0
    forced = set(args.pages or [])
    for page_idx in range(total_pages):
        pkey = str(page_idx + 1)
        if results.get(pkey, {}).get("status") == "success" and (page_idx + 1) not in forced:
            continue

        print(f"  [{pkey}/{total_pages}] ...", end="", flush=True)
        t0 = time.monotonic()
        try:
            text, usage = request_page(client, types, doc, page_idx)

            # Guard against the model transcribing its context page instead of
            # its target page.
            prev_entry = results.get(str(page_idx))
            sim = echo_similarity(text, prev_entry)
            warning = None
            if sim >= ECHO_SIMILARITY_THRESHOLD:
                print(f" echo? ({sim:.2f}) retrying...", end="", flush=True)
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
            print(f" OK ({len(text)}ch)" + (f" [WARNING: {warning}]" if warning else ""))
        except Exception as e:
            err = str(e)
            results[pkey] = {"status": "error", "error": err}
            errors += 1
            print(f" ERROR: {err[:80]}")
            if "429" in err:
                backoff = min(backoff * 2, MAX_BACKOFF)
                print(f"    backing off {backoff:.0f}s")

        save_results(results, results_file)
        time.sleep(backoff)

    doc.close()

    success = sum(1 for v in results.values() if v.get("status") == "success")
    tok_in = sum(
        v.get("usage", {}).get("prompt_tokens", 0) for v in results.values()
        if v.get("status") == "success"
    )
    tok_out = sum(
        v.get("usage", {}).get("output_tokens", 0) for v in results.values()
        if v.get("status") == "success"
    )
    # Thinking tokens are billed at the output rate and reported separately
    # from candidates_token_count. This run has no thinking config, so the sum
    # is zero here, but the arithmetic must not lie if that ever changes.
    tok_think = sum(
        v.get("usage", {}).get("thinking_tokens") or 0 for v in results.values()
        if v.get("status") == "success"
    )
    cost = (tok_in * PRICES["in"] + (tok_out + tok_think) * PRICES["out"]) / 1_000_000
    (OUT_DIR / "summary.json").write_text(
        json.dumps(
            {
                "success": success,
                "errors": errors,
                "total_pages": total_pages,
                "tokens_in": tok_in,
                "tokens_out": tok_out,
                "tokens_thinking": tok_think,
                "estimated_cost": round(cost, 3),
                "finished": datetime.now().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nDone: {success}/{total_pages} pages, {errors} errors, ~${cost:.2f}")
    build_tex(results, total_pages)


if __name__ == "__main__":
    main()
