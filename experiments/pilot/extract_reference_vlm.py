"""
Extract clean text from G103d reference PDF pages using Gemini VLM.

Replaces the noisy fitz page.get_text() extraction with VLM-based OCR
of the rendered PDF page images. Extracts both raw text (for comparison)
and LaTeX (for final output).

Usage:
    GEMINI_API_KEY=your_key python extract_reference_vlm.py
    GEMINI_API_KEY=your_key python extract_reference_vlm.py --pages 6,7,8,38
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: Install google-genai: pip install google-genai")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
REF_IMAGES_DIR = BASE_DIR / "reference" / "images"
OUTPUT_PATH = BASE_DIR / "reference" / "g103d_vlm_text.json"

MODEL = "gemini-3.1-flash-lite-preview"
DELAY = 1.5  # seconds between requests

# Prompt for RAW TEXT extraction (no LaTeX — for comparison with OCR output)
RAW_TEXT_PROMPT = """This is a page from a typeset mathematical document in French
("Esquisse d'un Programme" / Grothendieck's mathematical writings, typeset by Mateo Carmona).

Extract ALL the text content from this page as plain text. Rules:
1. Transcribe ALL text exactly as it appears, including mathematical expressions
2. For mathematical expressions, write them in a readable plain text form:
   - Subscripts: x_i, a_n
   - Superscripts: x^2, f^{-1}
   - Greek letters: spell out (alpha, beta, pi, etc.)
   - Fractions: a/b
   - Special symbols: describe simply (arrow, mapsto, subset, etc.)
3. Preserve paragraph structure with blank lines
4. Preserve section headers and numbering
5. Include footnotes and marginal annotations
6. Do NOT add any commentary or explanation — just the text content
7. Do NOT wrap in code blocks or add formatting markers

Output the raw text directly."""

# Prompt for LATEX extraction (for final output)
LATEX_PROMPT = """This is a page from a typeset mathematical document in French
("Esquisse d'un Programme" / Grothendieck's mathematical writings, typeset by Mateo Carmona).

Extract ALL the text content from this page as LaTeX. Rules:
1. Transcribe ALL text exactly as it appears
2. Mathematical expressions in proper LaTeX: $x^2$, $\\mathcal{O}_X$, $\\pi_1$, etc.
3. Display equations with $$ or \\begin{equation}
4. Preserve section headers: \\section{}, \\subsection{}
5. Preserve paragraph structure
6. Include footnotes
7. Do NOT add preamble, \\begin{document}, etc. — just the page content
8. Do NOT add unnecessary layout commands (\\hfill, \\vspace, \\noindent)
9. Focus on CONTENT, not visual layout reproduction

Output the LaTeX directly, no code fences."""


def img_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def extract_page(client, img_path: Path, prompt: str) -> str:
    """Extract text from a single page image using Gemini."""
    b64 = img_to_b64(img_path)

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part(text=prompt),
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="image/png",
                            data=base64.b64decode(b64),
                        )
                    ),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
            temperature=0.1,
        ),
    )

    # Extract text from response (skip thinking parts)
    text = ""
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "thought") and part.thought:
                continue  # skip thinking tokens
            if part.text:
                text += part.text
    return text.strip()


def main():
    parser = argparse.ArgumentParser(description="Extract G103d reference text using VLM")
    parser.add_argument("--pages", help="Comma-separated page numbers (default: all available)")
    parser.add_argument("--mode", choices=["raw", "latex", "both"], default="both",
                        help="Extraction mode (default: both)")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY environment variable")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Find available page images
    available = sorted(REF_IMAGES_DIR.glob("g103d_page_*.png"))
    page_map = {}
    for p in available:
        pnum = int(p.stem.split("_")[-1])
        page_map[pnum] = p

    if args.pages:
        target_pages = [int(x.strip()) for x in args.pages.split(",")]
    else:
        target_pages = sorted(page_map.keys())

    print(f"Extracting {len(target_pages)} pages with model {MODEL}")
    print(f"Mode: {args.mode}")
    print(f"Pages: {target_pages}")

    # Load existing results if any
    results = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            results = json.load(f)

    total = len(target_pages)
    modes = []
    if args.mode in ("raw", "both"):
        modes.append(("raw", RAW_TEXT_PROMPT))
    if args.mode in ("latex", "both"):
        modes.append(("latex", LATEX_PROMPT))

    for i, pnum in enumerate(target_pages):
        if pnum not in page_map:
            print(f"  [{i+1}/{total}] Page {pnum}: no image available, skipping")
            continue

        img_path = page_map[pnum]
        pkey = str(pnum)

        if pkey not in results:
            results[pkey] = {}

        for mode_name, prompt in modes:
            if mode_name in results[pkey]:
                print(f"  [{i+1}/{total}] Page {pnum} ({mode_name}): already extracted, skipping")
                continue

            print(f"  [{i+1}/{total}] Page {pnum} ({mode_name})...", end="", flush=True)
            try:
                text = extract_page(client, img_path, prompt)
                results[pkey][mode_name] = text
                print(f" {len(text)} chars")
            except Exception as e:
                print(f" ERROR: {e}")
                results[pkey][mode_name] = f"[ERROR: {e}]"

            time.sleep(DELAY)

        # Save after each page (in case of interruption)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Results saved to {OUTPUT_PATH}")
    print(f"Total pages extracted: {len(results)}")

    # Quick stats
    for pkey in sorted(results.keys(), key=int):
        raw_len = len(results[pkey].get("raw", ""))
        latex_len = len(results[pkey].get("latex", ""))
        print(f"  Page {pkey}: raw={raw_len}ch, latex={latex_len}ch")


if __name__ == "__main__":
    main()
