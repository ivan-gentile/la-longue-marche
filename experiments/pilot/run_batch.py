"""
Batch API submission for remaining transcription pages.

Uses inline requests (no Files API needed).
50% cheaper than regular API, no rate limits, results within 24h.

Usage:
    GEMINI_API_KEY=key python3 run_batch.py --volume all --dry-run
    GEMINI_API_KEY=key python3 run_batch.py --volume all
    GEMINI_API_KEY=key python3 run_batch.py --status JOB_NAME
    GEMINI_API_KEY=key python3 run_batch.py --collect JOB_NAME
    GEMINI_API_KEY=key python3 run_batch.py --collect-all
    GEMINI_API_KEY=key python3 run_batch.py --list-jobs
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: pip install google-genai")
    sys.exit(1)

try:
    import fitz
except ImportError:
    print("ERROR: pip install pymupdf")
    sys.exit(1)

from prompts_v2 import get_prompt

# --- Paths ---
BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent.parent
RAW_PDF_DIR = PROJECT_DIR / "raw_pdf"
PRODUCTION_DIR = BASE_DIR / "production"

# --- Config (same as run_production.py) ---
MODEL_ID = "gemini-3.1-pro-preview"
THINKING_LEVEL = "medium"
PROMPT_STYLE = "text-first-fewshot"
MAX_OUTPUT_TOKENS = 16000

# Pages per batch chunk — keeps requests manageable in memory
BATCH_SIZE = 15

VOLUMES = {
    "140-3": {"pdf": "140-3.pdf", "pages": 696},
    "140-4": {"pdf": "140-4.pdf", "pages": 280},
}


def extract_pdf_page(doc, page_idx: int) -> bytes:
    """Extract a single PDF page as standalone PDF bytes."""
    single = fitz.open()
    single.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
    pdf_bytes = single.tobytes()
    single.close()
    return pdf_bytes


def get_remaining_pages(volume_key: str) -> list[int]:
    """Get list of page indices that still need transcription."""
    results_file = PRODUCTION_DIR / volume_key / "transcriptions.json"
    existing = {}
    if results_file.exists():
        with open(results_file, encoding="utf-8") as f:
            existing = json.load(f)

    vol = VOLUMES[volume_key]
    pdf_path = RAW_PDF_DIR / vol["pdf"]
    doc = fitz.open(str(pdf_path))
    total = len(doc)
    doc.close()

    remaining = []
    for page_idx in range(total):
        pkey = str(page_idx + 1)
        if pkey not in existing or existing[pkey].get("status") != "success":
            remaining.append(page_idx)
    return remaining


def build_inline_requests(doc, page_indices: list[int], volume_key: str) -> list:
    """Build InlinedRequest objects for a chunk of pages."""
    system_prompt, user_text = get_prompt(PROMPT_STYLE)
    requests = []

    for page_idx in page_indices:
        pkey = str(page_idx + 1)
        parts = []

        # Previous page context
        if page_idx > 0:
            try:
                prev_bytes = extract_pdf_page(doc, page_idx - 1)
                parts.append(types.Part.from_bytes(data=prev_bytes, mime_type="application/pdf"))
                parts.append(types.Part.from_text(
                    text=f"[Previous page {page_idx} shown above for context]"
                ))
            except Exception:
                pass

        # Current page
        curr_bytes = extract_pdf_page(doc, page_idx)
        parts.append(types.Part.from_bytes(data=curr_bytes, mime_type="application/pdf"))
        parts.append(types.Part.from_text(text=user_text))

        req = types.InlinedRequest(
            metadata={"key": f"{volume_key}_p{pkey}"},
            contents=[types.Content(parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=1.0,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
            ),
        )
        requests.append(req)

    return requests


def submit_batches(client, volume_key: str, remaining: list[int],
                   batch_size: int = BATCH_SIZE) -> list[str]:
    """Build and submit inline batch jobs in chunks."""
    vol = VOLUMES[volume_key]
    pdf_path = RAW_PDF_DIR / vol["pdf"]
    doc = fitz.open(str(pdf_path))

    job_names = []
    total_chunks = (len(remaining) + batch_size - 1) // batch_size

    for chunk_start in range(0, len(remaining), batch_size):
        chunk = remaining[chunk_start:chunk_start + batch_size]
        chunk_num = chunk_start // batch_size + 1

        print(f"\n  Chunk {chunk_num}/{total_chunks}: {len(chunk)} pages "
              f"(p{chunk[0]+1}..p{chunk[-1]+1})")

        # Build requests
        print(f"    Building requests...", end="", flush=True)
        requests = build_inline_requests(doc, chunk, volume_key)
        print(f" {len(requests)} ready")

        # Submit
        try:
            batch_job = client.batches.create(
                model=MODEL_ID,
                src=requests,
                config=types.CreateBatchJobConfig(
                    display_name=f"grothendieck_{volume_key}_c{chunk_num}"
                ),
            )
            job_names.append(batch_job.name)
            print(f"    Submitted: {batch_job.name} (state: {batch_job.state})")
        except Exception as e:
            print(f"    ERROR: {e}")

        # Brief pause between submissions
        if chunk_start + batch_size < len(remaining):
            time.sleep(2)

    doc.close()
    return job_names


def check_status(client, job_name: str):
    """Check batch job status."""
    job = client.batches.get(name=job_name)
    print(f"  Job: {job.name}")
    print(f"  State: {job.state}")
    if hasattr(job, "dest") and job.dest:
        print(f"  Output: {job.dest}")
    return job


def list_jobs(client):
    """List all batch jobs."""
    job_file = PRODUCTION_DIR / "batch_jobs.json"
    if not job_file.exists():
        print("  No batch_jobs.json found.")
        return

    with open(job_file, encoding="utf-8") as f:
        jobs_list = json.load(f)

    all_names = []
    for entry in jobs_list:
        all_names.extend(entry.get("batch_names", []))

    print(f"  {len(all_names)} batch jobs recorded:")
    for name in all_names:
        try:
            job = client.batches.get(name=name)
            print(f"    {name}: {job.state.name}")
        except Exception as e:
            print(f"    {name}: ERROR ({e})")


def collect_results(client, job_name: str):
    """Collect batch results and merge into production transcriptions."""
    job = client.batches.get(name=job_name)

    if job.state.name != "JOB_STATE_SUCCEEDED":
        print(f"  Job not done yet. State: {job.state.name}")
        return

    if not hasattr(job, "dest") or not job.dest:
        print("  ERROR: No destination found on job")
        return

    result_file_name = job.dest.file_name
    print(f"  Downloading results from: {result_file_name}")
    file_content_bytes = client.files.download(file=result_file_name)
    file_content = file_content_bytes.decode("utf-8")
    _merge_results(file_content)


def collect_all_results(client):
    """Collect results from all batch jobs recorded in batch_jobs.json."""
    job_file = PRODUCTION_DIR / "batch_jobs.json"
    if not job_file.exists():
        print("  No batch_jobs.json found.")
        return

    with open(job_file, encoding="utf-8") as f:
        jobs_list = json.load(f)

    all_names = []
    for entry in jobs_list:
        all_names.extend(entry.get("batch_names", []))

    print(f"  Found {len(all_names)} batch jobs to check")

    for name in all_names:
        print(f"\n  Checking {name}...")
        try:
            job = client.batches.get(name=name)
            print(f"    State: {job.state.name}")

            if job.state.name == "JOB_STATE_SUCCEEDED":
                if hasattr(job, "dest") and job.dest:
                    result_file_name = job.dest.file_name
                    print(f"    Downloading results...")
                    file_content_bytes = client.files.download(file=result_file_name)
                    file_content = file_content_bytes.decode("utf-8")
                    _merge_results(file_content)
                else:
                    print(f"    No output file found")
        except Exception as e:
            print(f"    ERROR: {e}")


def _merge_results(file_content: str):
    """Parse batch result JSONL and merge into production transcriptions."""
    results_by_volume = {}
    for line in file_content.strip().splitlines():
        entry = json.loads(line)

        # Get key from metadata
        metadata = entry.get("metadata", {})
        key = metadata.get("key", entry.get("key", ""))

        if "_p" not in key:
            continue
        vol_key, pkey = key.rsplit("_p", 1)

        if vol_key not in results_by_volume:
            results_by_volume[vol_key] = {}

        response = entry.get("response", {})
        if not response:
            results_by_volume[vol_key][pkey] = {
                "status": "error",
                "error": "empty response",
                "transcription": "",
                "source": "batch",
            }
            continue

        # Extract text (skip thinking parts)
        text = ""
        candidates = response.get("candidates", [])
        if candidates:
            for part in candidates[0].get("content", {}).get("parts", []):
                if part.get("thought"):
                    continue
                if "text" in part:
                    text += part["text"]

        usage = {}
        um = response.get("usage_metadata", {})
        if um:
            usage = {
                "prompt_tokens": um.get("prompt_token_count"),
                "output_tokens": um.get("candidates_token_count"),
                "thinking_tokens": um.get("thoughts_token_count"),
            }

        results_by_volume[vol_key][pkey] = {
            "status": "success",
            "transcription": text.strip(),
            "usage": usage,
            "source": "batch",
        }

    # Merge into existing production results
    for vol_key, batch_results in results_by_volume.items():
        out_dir = PRODUCTION_DIR / vol_key
        out_dir.mkdir(parents=True, exist_ok=True)
        results_file = out_dir / "transcriptions.json"

        existing = {}
        if results_file.exists():
            with open(results_file, encoding="utf-8") as f:
                existing = json.load(f)

        merged = 0
        for pkey, result in batch_results.items():
            if result["status"] == "success":
                existing[pkey] = result
                merged += 1

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        success = sum(1 for v in existing.values() if v.get("status") == "success")
        total = VOLUMES[vol_key]["pages"]
        print(f"    {vol_key}: merged {merged} batch results -> {success}/{total} total")


def main():
    parser = argparse.ArgumentParser(description="Batch API for remaining transcriptions")
    parser.add_argument("--volume", choices=list(VOLUMES.keys()) + ["all"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"Pages per batch chunk (default: {BATCH_SIZE})")
    parser.add_argument("--status", metavar="JOB_NAME", help="Check job status")
    parser.add_argument("--collect", metavar="JOB_NAME", help="Collect results from completed job")
    parser.add_argument("--collect-all", action="store_true", help="Collect all batch results")
    parser.add_argument("--list-jobs", action="store_true", help="List all batch jobs")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    if args.status:
        check_status(client, args.status)
        return

    if args.collect:
        collect_results(client, args.collect)
        return

    if args.collect_all:
        collect_all_results(client)
        return

    if args.list_jobs:
        list_jobs(client)
        return

    # Submit new batch
    if not args.volume:
        parser.error("--volume required for submission")

    volumes = list(VOLUMES.keys()) if args.volume == "all" else [args.volume]

    print("=" * 70)
    print("BATCH SUBMISSION — Grothendieck Manuscript Transcription")
    print("=" * 70)

    all_remaining = {}
    for vol in volumes:
        remaining = get_remaining_pages(vol)
        all_remaining[vol] = remaining
        print(f"  {vol}: {len(remaining)} pages remaining")

    total_remaining = sum(len(r) for r in all_remaining.values())
    total_chunks = sum((len(r) + args.batch_size - 1) // args.batch_size
                       for r in all_remaining.values() if r)
    print(f"  Total: {total_remaining} pages in {total_chunks} batch chunks")
    print(f"  Model: {MODEL_ID} (thinking={THINKING_LEVEL})")
    print(f"  Chunk size: {args.batch_size} pages/chunk")
    print(f"  Est. cost: ~${total_remaining * 0.005:.2f} (50% batch discount)")

    if args.dry_run:
        print("\n  [DRY RUN]")
        return

    if total_remaining == 0:
        print("\n  Nothing to do — all pages already transcribed!")
        return

    # Process each volume
    all_job_names = []
    for vol in volumes:
        if not all_remaining[vol]:
            continue
        print(f"\n{'='*70}")
        print(f"  Processing {vol} ({len(all_remaining[vol])} pages)...")
        print(f"{'='*70}")
        job_names = submit_batches(client, vol, all_remaining[vol],
                                   batch_size=args.batch_size)
        all_job_names.extend(job_names)

    # Save job info
    job_info = {
        "batch_names": all_job_names,
        "total_requests": total_remaining,
        "volumes": {v: len(r) for v, r in all_remaining.items()},
        "submitted": datetime.now().isoformat(),
        "model": MODEL_ID,
        "batch_size": args.batch_size,
    }
    job_file = PRODUCTION_DIR / "batch_jobs.json"
    jobs = []
    if job_file.exists():
        with open(job_file, encoding="utf-8") as f:
            jobs = json.load(f)
    jobs.append(job_info)
    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print(f"  All batches submitted! {len(all_job_names)} jobs:")
    for name in all_job_names:
        print(f"    {name}")
    print(f"\n  Check status:  GEMINI_API_KEY=key python3 run_batch.py --list-jobs")
    print(f"  Collect ALL:   GEMINI_API_KEY=key python3 run_batch.py --collect-all")
    print(f"  Results expected within 24 hours.")


if __name__ == "__main__":
    main()
