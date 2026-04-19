"""Quick Flash-Lite comparison on Bourbaki typed pages.

Runs Gemini 3.1 Flash-Lite over the same 5 Bourbaki pages we already have
Pro (whole-doc) and Claude Opus 4.7 (page-by-page) output for. Outputs a
side-by-side LaTeX file and reports cost + latency. No quality metric —
just a visual comparison.
"""

from __future__ import annotations

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

from google import genai
from google.genai import types
import fitz

MODEL_ID = "gemini-3.1-flash-lite-preview"
PRICES = {"in": 0.25, "out": 1.50}

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
5. Numbered items keep their numbering.
6. Commutative diagrams: use \begin{tikzcd}...\end{tikzcd}.
7. Underlined or italicized key terms: \emph{...}.
8. Uncertain reading: [unclear: best guess].

## Do NOT
- Do NOT add commentary.
- Do NOT wrap the output in a full document.
- Do NOT use code fences.

Output pure LaTeX body only.
"""


def main() -> None:
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    mode = sys.argv[2] if len(sys.argv) > 2 else "whole"  # "whole" or "page"

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    src = fitz.open(str(PDF_PATH))
    try:
        if mode == "whole":
            out = fitz.open()
            out.insert_pdf(src, from_page=0, to_page=pages - 1)
            pdf_bytes = out.tobytes()
            out.close()

            parts = [
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                types.Part.from_text(text=(
                    f"The attached PDF contains pages 1 to {pages} of the Bourbaki "
                    f"schemes manuscript. {PROMPT}\n"
                    "Insert `%% ===== Page N =====` markers between consecutive pages."
                )),
            ]
            t0 = time.monotonic()
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[types.Content(parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    max_output_tokens=32000,
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
            ti, to = um.prompt_token_count, um.candidates_token_count
            cost = (ti * PRICES["in"] + to * PRICES["out"]) / 1_000_000

            print(f"Whole-doc Flash-Lite on pages 1-{pages}:")
            print(f"  {len(text)} chars, ${cost:.4f}, {dt:.1f}s")
            print(f"  tokens: in={ti:,}, out={to:,}")

            out_path = TEX_OUT / f"bourbaki_schemes_flash_lite_whole_p1-{pages}.tex"
            out_path.write_text(
                f"% Bourbaki schemes — Gemini 3.1 Flash-Lite whole-document single call\n"
                f"% Generated: {datetime.now().strftime('%Y-%m-%d')}\n"
                f"% Cost: ${cost:.4f}, latency {dt:.1f}s\n\n"
                + text.strip(),
                encoding="utf-8",
            )
            print(f"  wrote {out_path.relative_to(REPO)}")

        elif mode == "page":
            tex_lines = [
                f"% Bourbaki schemes — Gemini 3.1 Flash-Lite page-by-page",
                f"% Generated: {datetime.now().strftime('%Y-%m-%d')}",
                "",
            ]
            total_cost = 0.0
            total_dt = 0.0
            for page_1 in range(1, pages + 1):
                slice_ = fitz.open()
                slice_.insert_pdf(src, from_page=page_1 - 1, to_page=page_1 - 1)
                pdf_bytes = slice_.tobytes()
                slice_.close()

                parts = [
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    types.Part.from_text(text=PROMPT),
                ]
                t0 = time.monotonic()
                response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=[types.Content(parts=parts)],
                    config=types.GenerateContentConfig(temperature=1.0, max_output_tokens=16000),
                )
                dt = time.monotonic() - t0
                total_dt += dt

                text = ""
                for p in response.candidates[0].content.parts:
                    if getattr(p, "thought", False):
                        continue
                    if p.text:
                        text += p.text
                um = response.usage_metadata
                ti, to = um.prompt_token_count, um.candidates_token_count
                cost = (ti * PRICES["in"] + to * PRICES["out"]) / 1_000_000
                total_cost += cost
                print(f"  p{page_1}: {len(text)}ch ${cost:.4f} {dt:.1f}s")

                tex_lines.extend([
                    f"%% ===== Page {page_1} =====",
                    "",
                    text.strip(),
                    "",
                    "\\newpage",
                    "",
                ])

            print(f"\nTotal: ${total_cost:.4f}, {total_dt:.1f}s")
            out_path = TEX_OUT / f"bourbaki_schemes_flash_lite_pbp_p1-{pages}.tex"
            out_path.write_text("\n".join(tex_lines), encoding="utf-8")
            print(f"  wrote {out_path.relative_to(REPO)}")
    finally:
        src.close()


if __name__ == "__main__":
    main()
