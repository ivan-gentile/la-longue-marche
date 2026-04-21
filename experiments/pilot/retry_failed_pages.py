"""Retry specific failed pages in a Flash-Lite transcription run.

Usage:
    python experiments/pilot/retry_failed_pages.py --volume 140-3 --pages 354 507 508
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: pip install google-genai"); sys.exit(1)

try:
    import fitz
except ImportError:
    print("ERROR: pip install pymupdf"); sys.exit(1)

from dotenv import load_dotenv
load_dotenv(HERE.parent.parent / ".env")

from prompts_v2 import get_prompt

RAW_PDF_DIR = HERE.parent.parent / "raw_pdf"
FLASH_LITE_DIR = HERE / "production-flash-lite-mateo"

MODELS = {
    "flash-lite": {
        "id": "gemini-3.1-flash-lite-preview",
        "cost_input": 0.25 / 1e6,
        "cost_output": 1.50 / 1e6,
    }
}


def transcribe_page(client, pdf_path: Path, page_num: int, prompt_style: str, model_id: str) -> dict:
    doc = fitz.open(str(pdf_path))
    page = doc[page_num - 1]
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()

    system_prompt, user_prompt = get_prompt(prompt_style)

    t0 = time.time()
    resp = client.models.generate_content(
        model=model_id,
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
            user_prompt,
        ],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
        ),
    )
    latency = time.time() - t0
    text = resp.text or ""
    usage = resp.usage_metadata
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    cost = in_tok * MODELS["flash-lite"]["cost_input"] + out_tok * MODELS["flash-lite"]["cost_output"]
    return {
        "status": "success",
        "transcription": text,
        "latency_s": round(latency, 2),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": round(cost, 6),
        "model": model_id,
        "prompt_style": prompt_style,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--volume", required=True)
    parser.add_argument("--pages", nargs="+", type=int, required=True)
    parser.add_argument("--prompt-style", default="mateo-canonical")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set"); sys.exit(1)

    client = genai.Client(api_key=api_key)
    model_id = MODELS["flash-lite"]["id"]
    vol = args.volume
    pdf_path = RAW_PDF_DIR / f"{vol}.pdf"
    trans_path = FLASH_LITE_DIR / vol / "transcriptions.json"

    data = json.loads(trans_path.read_text(encoding="utf-8"))

    for page_num in args.pages:
        key = str(page_num)
        print(f"  Retrying page {page_num}...", end=" ", flush=True)
        try:
            result = transcribe_page(client, pdf_path, page_num, args.prompt_style, model_id)
            data[key] = result
            trans_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"OK ({result['output_tokens']} tok, ${result['cost_usd']:.5f}, {result['latency_s']:.1f}s)")
        except Exception as e:
            print(f"FAILED: {e}")
            time.sleep(10)

    succ = sum(1 for v in data.values() if v.get("status") == "success")
    err  = sum(1 for v in data.values() if v.get("status") == "error")
    print(f"\nFinal: {succ} success, {err} error in {trans_path}")


if __name__ == "__main__":
    main()
