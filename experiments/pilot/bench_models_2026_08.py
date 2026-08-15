"""Benchmark the August 2026 Gemini models on the Section 49.1 ground truth.

The repo's Flash tier was two generations behind (gemini-3.1-flash-lite,
January 2026) while gemini-3.7-flash shipped on 2026-08-13. This project's
rule is that a model or prompt change ships only if it improves the
Section 49 numbers, so a new model gets measured here before it becomes
a default anywhere.

Runs each model over 140-3 PDF pages 495-499 — the pages Mateo corrected
by hand (`reference/validation/49.1new.tex`) — with the production
`mateo-canonical` prompt and the production request shape (previous page
attached as visual context, medium thinking, 16k output cap). Results
land in `bench_models_2026_08/results.json` and are picked up
automatically by `evaluate_fidelity.py --preset 49.1`.

Usage:
    python experiments/pilot/bench_models_2026_08.py
    python experiments/pilot/bench_models_2026_08.py --models flash pro
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
sys.path.insert(0, str(HERE))

from models import MODELS  # noqa: E402
from prompts_v2 import get_prompt  # noqa: E402

PDF = REPO / "raw_pdf" / "140-3.pdf"
OUT_DIR = HERE / "bench_models_2026_08"
PAGES = list(range(495, 500))  # Section 49.1
PROMPT_STYLE = "mateo-canonical"
THINKING_LEVEL = "medium"
MAX_OUTPUT_TOKENS = 16000
REQUEST_TIMEOUT_MS = 300_000
DELAY = 3.0

DEFAULT_MODELS = ["flash", "flash-lite", "flash-3.6", "pro"]


def extract_page(doc, page_idx: int) -> bytes:
    import fitz

    single = fitz.open()
    single.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
    data = single.tobytes()
    single.close()
    return data


def transcribe(client, types, doc, model_id: str, page: int) -> dict:
    """One page, production request shape. page is 1-indexed."""
    system_prompt, user_text = get_prompt(PROMPT_STYLE)
    idx = page - 1
    parts = []
    if idx > 0:
        parts.append(
            types.Part.from_bytes(data=extract_page(doc, idx - 1), mime_type="application/pdf")
        )
        parts.append(types.Part.from_text(text=f"[Previous page {idx} shown above for context]"))
    parts.append(types.Part.from_bytes(data=extract_page(doc, idx), mime_type="application/pdf"))
    parts.append(types.Part.from_text(text=user_text))

    t0 = time.monotonic()
    response = client.models.generate_content(
        model=model_id,
        contents=[types.Content(parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=1.0,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
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

    um = getattr(response, "usage_metadata", None)
    return {
        "text": text,
        "latency_s": round(time.monotonic() - t0, 1),
        "usage": {
            "prompt_tokens": getattr(um, "prompt_token_count", None),
            "output_tokens": getattr(um, "candidates_token_count", None),
            "thinking_tokens": getattr(um, "thoughts_token_count", None),
        } if um is not None else {},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                    help=f"model keys from models.py (default: {' '.join(DEFAULT_MODELS)})")
    args = ap.parse_args()

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
    client = genai.Client(api_key=api_key)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / "results.json"
    results = {}
    if results_path.exists():
        results = json.loads(results_path.read_text(encoding="utf-8"))

    doc = fitz.open(str(PDF))
    for key in args.models:
        spec = MODELS[key]
        model_id = spec["id"]
        bucket = results.setdefault(model_id, {"model_key": key, "pages": {}})
        print(f"\n=== {model_id} ({key})")
        for page in PAGES:
            if str(page) in bucket["pages"]:
                print(f"  p{page}: cached")
                continue
            print(f"  p{page}: ...", end="", flush=True)
            try:
                bucket["pages"][str(page)] = transcribe(client, types, doc, model_id, page)
                print(f" OK ({len(bucket['pages'][str(page)]['text'])}ch, "
                      f"{bucket['pages'][str(page)]['latency_s']}s)")
            except Exception as e:
                print(f" ERROR: {str(e)[:100]}")
                bucket["pages"][str(page)] = {"error": str(e), "text": ""}
            results_path.write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            time.sleep(DELAY)

        ok = [p for p in bucket["pages"].values() if p.get("text")]
        tok_in = sum(p.get("usage", {}).get("prompt_tokens") or 0 for p in ok)
        tok_out = sum(p.get("usage", {}).get("output_tokens") or 0 for p in ok)
        tok_think = sum(p.get("usage", {}).get("thinking_tokens") or 0 for p in ok)
        cost = (tok_in * spec["cost_input"]
                + (tok_out + tok_think) * spec["cost_output"]) / 1_000_000
        latency = [p["latency_s"] for p in ok if "latency_s" in p]
        bucket["summary"] = {
            "pages_ok": len(ok),
            "tokens_in": tok_in,
            "tokens_out": tok_out,
            "tokens_thinking": tok_think,
            "cost_5_pages": round(cost, 4),
            "cost_per_1000_pages": round(cost / max(len(ok), 1) * 1000, 2),
            "avg_latency_s": round(sum(latency) / len(latency), 1) if latency else None,
            "benchmarked": datetime.now().isoformat(),
        }
        print(f"  -> {len(ok)}/5 pages, ${cost:.4f} for 5 pages "
              f"(${bucket['summary']['cost_per_1000_pages']:.0f} per 1000 pages), "
              f"avg {bucket['summary']['avg_latency_s']}s/page")
        results_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    doc.close()
    print(f"\nwrote {results_path.relative_to(REPO)}")
    print("Now run: python experiments/pilot/evaluate_fidelity.py --preset 49.1")


if __name__ == "__main__":
    main()
