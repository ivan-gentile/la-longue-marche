"""Bourbaki schemes benchmark — "controlled-setting" sanity check.

Runs the same pipeline architecture on an early, typed Grothendieck text
(Mateo's suggestion from the March 21 email). Typed text removes the
handwriting ambiguity, so any residual errors are attributable to the
prompt or to the pipeline, not the OCR.

Defaults to Claude Opus 4.7 over the first 5 pages (matches the
comparative posture of the main benchmark). With `--gemini` and a key,
runs the full document through Gemini 3.1 Pro in a single whole-document
call (proof of the "full documents on the gemini api" path). Both modes
write their LaTeX output under `tex_output/`.
"""

from __future__ import annotations

import argparse
import base64
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
TEX_OUT.mkdir(exist_ok=True)

from anthropic import Anthropic
import fitz


CLAUDE_MODEL_ID = "claude-opus-4-7"
CLAUDE_PRICES = {"in": 15.00, "out": 75.00}  # USD per 1M tokens
GEMINI_MODEL_ID = "gemini-3.1-pro-preview"
GEMINI_PRICES = {"in": 2.00, "out": 12.00}
MAX_OUTPUT_TOKENS = 16000


PROMPT = r"""This is a scanned page from an early typed Grothendieck text
on the theory of schemes (EGA-era, Bourbaki archives). The scan is a
typewritten page in French, with mathematical notation.

## Your task
Transcribe this page faithfully into LaTeX.

Rules:
1. French prose exactly as typed, preserving accents.
2. Mathematical notation in LaTeX: $A$, $\mathcal{O}_X$, $\operatorname{Spec}$,
   $\mathbb{Z}$, $f: X \to Y$, etc.
3. Displayed equations on their own line: $$ ... $$.
4. Section headings: \section*{...} or \subsection*{...}
5. Numbered items keep their numbering: "1.", "§1.", "a)", etc.
6. Commutative diagrams: use \begin{tikzcd}...\end{tikzcd}.
7. Underlined or italicized key terms: \emph{...}.
8. Uncertain reading: [unclear: best guess].

## Do NOT
- Do NOT add commentary or explanation.
- Do NOT wrap the output in a full document (no preamble, no \begin{document}).
- Do NOT use code fences.

Output pure LaTeX body only.
"""


def pdf_slice(first_0: int, last_0: int) -> bytes:
    """Return a PDF byte stream for pages [first_0..last_0] (0-indexed, inclusive)."""
    src = fitz.open(str(PDF_PATH))
    try:
        out = fitz.open()
        out.insert_pdf(src, from_page=first_0, to_page=last_0)
        data = out.tobytes()
        out.close()
        return data
    finally:
        src.close()


# ---------------------------------------------------------------------------
# Claude per-page
# ---------------------------------------------------------------------------


def claude_page(client: Anthropic, page_1: int) -> dict:
    pdf_bytes = pdf_slice(page_1 - 1, page_1 - 1)
    content = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.b64encode(pdf_bytes).decode("ascii"),
            },
        },
        {"type": "text", "text": PROMPT},
    ]
    t0 = time.monotonic()
    msg = client.messages.create(
        model=CLAUDE_MODEL_ID,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[{"role": "user", "content": content}],
    )
    dt = time.monotonic() - t0
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    tok_in = msg.usage.input_tokens
    tok_out = msg.usage.output_tokens
    cost = (tok_in * CLAUDE_PRICES["in"] + tok_out * CLAUDE_PRICES["out"]) / 1_000_000
    return {
        "model": CLAUDE_MODEL_ID,
        "page": page_1,
        "text": text.strip(),
        "tokens_in": tok_in,
        "tokens_out": tok_out,
        "cost_usd": round(cost, 4),
        "latency_s": round(dt, 2),
    }


# ---------------------------------------------------------------------------
# Gemini whole-document
# ---------------------------------------------------------------------------


def gemini_whole_doc(first_page_1: int, last_page_1: int) -> dict:
    from google import genai
    from google.genai import types

    gem_api = os.environ.get("GEMINI_API_KEY")
    if not gem_api:
        raise RuntimeError("GEMINI_API_KEY not set")
    client = genai.Client(api_key=gem_api)

    pdf_bytes = pdf_slice(first_page_1 - 1, last_page_1 - 1)
    parts = [
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        types.Part.from_text(text=(
            f"The attached PDF contains pages {first_page_1} to {last_page_1} of the "
            "Bourbaki schemes manuscript. " + PROMPT +
            "\nInsert `%% ===== Page N =====` markers between consecutive pages so the "
            "output remains page-addressable."
        )),
    ]

    t0 = time.monotonic()
    response = client.models.generate_content(
        model=GEMINI_MODEL_ID,
        contents=[types.Content(parts=parts)],
        config=types.GenerateContentConfig(
            temperature=1.0,
            max_output_tokens=MAX_OUTPUT_TOKENS * 4,
            thinking_config=types.ThinkingConfig(thinking_level="medium"),
        ),
    )
    dt = time.monotonic() - t0

    text = ""
    for p in response.candidates[0].content.parts:
        if getattr(p, "thought", False):
            continue
        if p.text:
            text += p.text
    um = getattr(response, "usage_metadata", None)
    tok_in = getattr(um, "prompt_token_count", 0) if um else 0
    tok_out = getattr(um, "candidates_token_count", 0) if um else 0
    cost = (tok_in * GEMINI_PRICES["in"] + tok_out * GEMINI_PRICES["out"]) / 1_000_000
    return {
        "model": GEMINI_MODEL_ID,
        "pages": [first_page_1, last_page_1],
        "text": text.strip(),
        "tokens_in": tok_in,
        "tokens_out": tok_out,
        "cost_usd": round(cost, 4),
        "latency_s": round(dt, 2),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=5,
                         help="number of pages from the start to process (default 5)")
    parser.add_argument("--gemini-whole-doc", action="store_true",
                         help="additionally run a single whole-document Gemini call over the same pages")
    args = parser.parse_args()

    if not PDF_PATH.exists():
        print(f"ERROR: {PDF_PATH} not found")
        sys.exit(1)

    ant_api = os.environ.get("ANTHROPIC_API_KEY")
    if not ant_api:
        print("ERROR: set ANTHROPIC_API_KEY")
        sys.exit(1)
    claude = Anthropic(api_key=ant_api)

    pages = list(range(1, args.pages + 1))
    print(f"Running Claude Opus 4.7 on Bourbaki pages 1-{pages[-1]}")

    claude_results = []
    for p in pages:
        print(f"  p{p}... ", end="", flush=True)
        r = claude_page(claude, p)
        claude_results.append(r)
        print(f"{len(r['text'])}ch ${r['cost_usd']} {r['latency_s']}s")

    # Aggregate LaTeX
    tex_lines = []
    tex_lines.append("% Bourbaki schemes — AI transcription (Claude Opus 4.7, page-by-page)")
    tex_lines.append("% Source: https://archives-bourbaki.ahp-numerique.fr/files/original/1ab847431b6cd9cfd28c9224f29129f4.pdf")
    tex_lines.append(f"% Generated: {datetime.now().strftime('%Y-%m-%d')}  (first {len(pages)} of 437 pages)")
    tex_lines.append("")
    for r in claude_results:
        tex_lines.append(f"%% ===== Page {r['page']} =====")
        tex_lines.append("")
        tex_lines.append(r["text"])
        tex_lines.append("")
        tex_lines.append("\\newpage")
        tex_lines.append("")

    tex_path = TEX_OUT / f"bourbaki_schemes_opus_p1-{pages[-1]}.tex"
    tex_path.write_text("\n".join(tex_lines), encoding="utf-8")
    print(f"\nWrote {tex_path.relative_to(REPO)}")

    total_cost = sum(r["cost_usd"] for r in claude_results)
    print(f"Total Claude cost: ${total_cost:.3f}")

    # Optional: whole-document Gemini
    if args.gemini_whole_doc:
        if not os.environ.get("GEMINI_API_KEY"):
            print("Skipping --gemini-whole-doc: GEMINI_API_KEY not set.")
        else:
            print(f"\nRunning Gemini 3.1 Pro on pages 1-{pages[-1]} in a single whole-document call...")
            g = gemini_whole_doc(1, pages[-1])
            print(f"  done: {len(g['text'])}ch, ${g['cost_usd']}, {g['latency_s']}s")
            gtex_path = TEX_OUT / f"bourbaki_schemes_gemini_whole_p1-{pages[-1]}.tex"
            gtex_path.write_text(
                "% Bourbaki schemes — Gemini 3.1 Pro whole-document single call\n"
                f"% Generated: {datetime.now().strftime('%Y-%m-%d')}\n\n"
                + g["text"],
                encoding="utf-8",
            )
            print(f"  wrote {gtex_path.relative_to(REPO)}")

    # Save structured results JSON
    results_json = HERE / "results.json"
    results_json.write_text(json.dumps({
        "claude": claude_results,
        "pages_requested": pages,
        "generated": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {results_json.relative_to(REPO)}")


if __name__ == "__main__":
    main()
