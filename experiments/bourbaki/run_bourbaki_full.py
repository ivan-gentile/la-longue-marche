"""Transcribe the full 437-page Bourbaki schemes PDF with Gemini 3.1 Flash-Lite.

Sends the PDF in chunks of CHUNK_SIZE pages per API call (whole-document mode).
Results are saved incrementally to experiments/bourbaki/bourbaki_full_results.json
and a final compiled .tex is written to tex_output/bourbaki_schemes_full.tex.

Usage:
    python experiments/bourbaki/run_bourbaki_full.py
    python experiments/bourbaki/run_bourbaki_full.py --resume  (skip done chunks)
    python experiments/bourbaki/run_bourbaki_full.py --model pro  (use Pro instead)
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
TEX_OUT = REPO / "tex_output"
RESULTS_PATH = HERE / "bourbaki_full_results.json"

MODELS = {
    "flash-lite": {
        "id": "gemini-3.1-flash-lite-preview",
        "prices": {"in": 0.25, "out": 1.50},
        "chunk": 50,  # pages per API call
    },
    "pro": {
        "id": "gemini-3.1-pro-preview",
        "prices": {"in": 2.00, "out": 12.00},
        "chunk": 20,  # smaller chunks for Pro to stay under token limits
    },
}

PROMPT = r"""This is a scanned document from the Bourbaki archives — an early typed
manuscript by Alexander Grothendieck developing the theory of schemes (EGA-era,
French, circa 1958-59).

## Your task
Transcribe ALL pages in this PDF into LaTeX, in order.

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

## Page markers
Insert `%% ===== Page N =====` at the start of each page's content so the
output remains page-addressable. Use the physical page number from the document.

## Do NOT
- Do NOT add commentary or explanation.
- Do NOT wrap the output in a full document (no \documentclass, no \begin{document}).
- Do NOT use code fences.

Output pure LaTeX body only.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["flash-lite", "pro"], default="flash-lite")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    try:
        from google import genai
        from google.genai import types
        import fitz
    except ImportError:
        print("ERROR: pip install google-genai pymupdf python-dotenv")
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: set GEMINI_API_KEY in .env")
        sys.exit(1)

    cfg = MODELS[args.model]
    model_id = cfg["id"]
    prices = cfg["prices"]
    chunk_size = cfg["chunk"]

    src = fitz.open(str(PDF_PATH))
    total_pages = len(src)
    print(f"Bourbaki full run — {total_pages} pages")
    print(f"Model: {model_id} | chunk: {chunk_size} pages | "
          f"est. cost: ~${total_pages * 0.0015:.2f} (Flash-Lite) | "
          f"est. time: ~{total_pages * 2.6 / 60:.0f} min")

    # Load existing results
    results: dict = {}
    if args.resume and RESULTS_PATH.exists():
        results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        print(f"Resuming: {len(results)} chunks already done")

    client = genai.Client(api_key=api_key)

    # Build list of chunks: (chunk_index, first_page_1, last_page_1)
    chunks = []
    page = 1
    idx = 0
    while page <= total_pages:
        last = min(page + chunk_size - 1, total_pages)
        chunks.append((idx, page, last))
        page = last + 1
        idx += 1

    total_cost = 0.0
    total_in = 0
    total_out = 0
    start = time.monotonic()

    for chunk_idx, first_1, last_1 in chunks:
        key = f"chunk_{chunk_idx:03d}_p{first_1}-{last_1}"
        if args.resume and key in results:
            print(f"  [{key}] (cached)")
            total_cost += results[key].get("cost_usd", 0)
            continue

        print(f"  [{key}] ({last_1 - first_1 + 1} pages)... ", end="", flush=True)

        # Extract pages as a single PDF
        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(src, from_page=first_1 - 1, to_page=last_1 - 1)
        pdf_bytes = chunk_doc.tobytes()
        chunk_doc.close()

        user_text = (
            f"The attached PDF contains pages {first_1} to {last_1} of the Bourbaki "
            f"schemes manuscript (part of a {total_pages}-page document). "
            + PROMPT
        )

        t0 = time.monotonic()
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=[types.Content(parts=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    types.Part.from_text(text=user_text),
                ])],
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    max_output_tokens=64000,
                ),
            )
            dt = time.monotonic() - t0

            text = ""
            for p in response.candidates[0].content.parts:
                if getattr(p, "thought", False):
                    continue
                if p.text:
                    text += p.text

            um = response.usage_metadata
            ti = um.prompt_token_count
            to = um.candidates_token_count
            cost = (ti * prices["in"] + to * prices["out"]) / 1_000_000
            total_cost += cost
            total_in += ti
            total_out += to

            results[key] = {
                "chunk_idx": chunk_idx,
                "first_page": first_1,
                "last_page": last_1,
                "text": text.strip(),
                "tokens_in": ti,
                "tokens_out": to,
                "cost_usd": round(cost, 5),
                "latency_s": round(dt, 1),
                "status": "success",
            }
            print(f"{len(text)}ch ${cost:.4f} {dt:.1f}s")

        except Exception as e:
            dt = time.monotonic() - t0
            results[key] = {
                "chunk_idx": chunk_idx,
                "first_page": first_1,
                "last_page": last_1,
                "text": "",
                "error": str(e),
                "status": "error",
                "latency_s": round(dt, 1),
            }
            print(f"ERROR: {str(e)[:80]}")

        RESULTS_PATH.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    src.close()
    elapsed = time.monotonic() - start

    # Compile into final .tex
    print("\nCompiling final LaTeX...")
    lines: list[str] = [
        "% Bourbaki schemes — complete transcription (437 pages)",
        f"% Model: {model_id} (whole-document chunks of {chunk_size} pages each)",
        f"% Generated: {datetime.now().strftime('%Y-%m-%d')}",
        f"% Total cost: ${total_cost:.3f} | tokens in: {total_in:,} out: {total_out:,}",
        f"% Source: https://archives-bourbaki.ahp-numerique.fr/files/original/"
        "1ab847431b6cd9cfd28c9224f29129f4.pdf",
        "",
    ]
    for chunk_idx, first_1, last_1 in chunks:
        key = f"chunk_{chunk_idx:03d}_p{first_1}-{last_1}"
        r = results.get(key, {})
        if r.get("status") == "success":
            lines.append(r["text"])
        else:
            lines.append(f"%% [chunk {key} failed: {r.get('error', 'missing')}]")
        lines.append("")

    out_path = TEX_OUT / f"bourbaki_schemes_full_{args.model}.tex"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    kb = out_path.stat().st_size / 1024

    success = sum(1 for r in results.values() if r.get("status") == "success")
    err = sum(1 for r in results.values() if r.get("status") == "error")

    print(f"\nDone.")
    print(f"  Chunks: {success} success, {err} error")
    print(f"  Output: {out_path.relative_to(REPO)} ({kb:.1f} KB)")
    print(f"  Total cost: ${total_cost:.3f}")
    print(f"  Total time: {elapsed/60:.1f} min")


if __name__ == "__main__":
    main()
