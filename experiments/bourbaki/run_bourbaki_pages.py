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
PDF_PATH = REPO / "raw_pdf" / "bourbaki_schemes.pdf"
OUT_DIR = HERE / "production-pages"
TEX_OUT = REPO / "tex_output"

MODEL_ID = "gemini-3.1-flash-lite-preview"
PRICES = {"in": 0.25, "out": 1.50}
MAX_OUTPUT_TOKENS = 16000
DELAY = 2.0
MAX_BACKOFF = 300

PROMPT = r"""This is one scanned page from the Bourbaki archives — an early typed
manuscript by Alexander Grothendieck developing the theory of schemes (EGA-era,
French, circa 1958-59).

## Your task
Transcribe THIS page (the last attached PDF) into LaTeX. If a previous page is
attached, it is context only — do NOT transcribe it.

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
    for page_idx in range(total_pages):
        pkey = str(page_idx + 1)
        if results.get(pkey, {}).get("status") == "success":
            continue

        parts = []
        if page_idx > 0:
            parts.append(
                types.Part.from_bytes(
                    data=extract_page(doc, page_idx - 1), mime_type="application/pdf"
                )
            )
            parts.append(types.Part.from_text(text="[Previous page, context only]"))
        parts.append(
            types.Part.from_bytes(data=extract_page(doc, page_idx), mime_type="application/pdf")
        )
        parts.append(types.Part.from_text(text=PROMPT))

        print(f"  [{pkey}/{total_pages}] ...", end="", flush=True)
        t0 = time.monotonic()
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[types.Content(parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=1.0, max_output_tokens=MAX_OUTPUT_TOKENS
                ),
            )
            text = "".join(
                p.text
                for p in response.candidates[0].content.parts
                if p.text and not getattr(p, "thought", False)
            ).strip()
            um = response.usage_metadata
            results[pkey] = {
                "status": "success",
                "transcription": text,
                "usage": {
                    "prompt_tokens": um.prompt_token_count,
                    "output_tokens": um.candidates_token_count,
                },
                "latency_s": round(time.monotonic() - t0, 1),
            }
            done += 1
            backoff = args.delay
            print(f" OK ({len(text)}ch)")
        except Exception as e:
            err = str(e)
            results[pkey] = {"status": "error", "error": err}
            errors += 1
            print(f" ERROR: {err[:80]}")
            if "429" in err:
                backoff = min(backoff * 2, MAX_BACKOFF)
                print(f"    backing off {backoff:.0f}s")

        results_file.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
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
    cost = (tok_in * PRICES["in"] + tok_out * PRICES["out"]) / 1_000_000
    (OUT_DIR / "summary.json").write_text(
        json.dumps(
            {
                "success": success,
                "errors": errors,
                "total_pages": total_pages,
                "tokens_in": tok_in,
                "tokens_out": tok_out,
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
