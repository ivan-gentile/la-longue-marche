#!/usr/bin/env python3
"""Render manuscript PDF pages to JPEG and upload them to Vercel Blob.

Blob layout (contract): scans/<doc-id>/<NNNN>.jpg where NNNN is the
1-indexed PDF page number zero-padded to 4 digits (scans/140-3/0495.jpg).
The review app serves these through an authenticated proxy; the blobs
themselves live on the store's public base (SCAN_BASE_URL).

Vercel Blob REST API (as implemented by @vercel/blob 2.8.0, API version 12):
  base URL   https://vercel.com/api/blob   (override: VERCEL_BLOB_API_URL)
  upload     PUT  {base}/?pathname=<path>  body = raw bytes
             headers: authorization: Bearer <token>
                      x-api-version: 12
                      x-vercel-blob-store-id: <field 4 of the rw token>
                      x-vercel-blob-access: private  (private store)
                      x-content-type: image/jpeg
                      x-add-random-suffix: 0     (exact pathname, no suffix)
                      x-allow-overwrite: 0|1
                      x-cache-control-max-age: <seconds>
  list       GET  {base}?prefix=<p>&limit=<n>[&cursor=<c>]
             response: {"blobs": [{"pathname": ..., "size": ...}, ...],
                        "cursor": ..., "hasMore": bool}

Usage:
  python3 review-site/scripts/upload_scans.py --dry-run
  BLOB_READ_WRITE_TOKEN=... python3 review-site/scripts/upload_scans.py
  python3 review-site/scripts/upload_scans.py --docs 140-4 --limit 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from urllib.parse import urlencode

import fitz  # pymupdf
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]

BLOB_API_VERSION = "12"
DEFAULT_BLOB_API_URL = "https://vercel.com/api/blob"
CACHE_CONTROL_MAX_AGE = str(365 * 24 * 3600)  # scans are immutable; cache 1 year
LIST_PAGE_SIZE = 1000
RETRIES = 2  # additional attempts after the first failure
BACKOFF_SECONDS = (2.0, 6.0)

# Contract document ids -> source PDF (relative to repo root) + expected pages.
DOCS = {
    "140-3": {"pdf": "raw_pdf/140-3.pdf", "pages": 696},
    "140-4": {"pdf": "raw_pdf/140-4.pdf", "pages": 280},
    "preschemas": {"pdf": "raw_pdf/bourbaki_schemes.pdf", "pages": 437},
    "varietes": {"pdf": "raw_pdf/U46.pdf", "pages": 100},
}

# One representative page per document, rendered by --dry-run.
DRY_RUN_SAMPLES = {"140-3": 500, "140-4": 100, "preschemas": 50, "varietes": 10}


def load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, does not override existing env."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def blob_pathname(doc_id: str, page_number: int) -> str:
    return f"scans/{doc_id}/{page_number:04d}.jpg"


def render_page_jpeg(doc: fitz.Document, page_index: int, dpi: int, quality: int) -> bytes:
    """Render 0-indexed page to JPEG bytes at the given DPI and quality."""
    zoom = dpi / 72.0
    page = doc.load_page(page_index)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return pix.tobytes("jpg", jpg_quality=quality)


class BlobClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = (
            os.environ.get("VERCEL_BLOB_API_URL") or DEFAULT_BLOB_API_URL
        ).rstrip("/")
        # Read-write tokens look like vercel_blob_rw_<storeId>_<secret>.
        parts = token.split("_")
        self.store_id = parts[3] if len(parts) > 3 else ""
        self._local = threading.local()

    def _session(self) -> requests.Session:
        # requests.Session is not thread-safe; one per upload thread.
        if not hasattr(self._local, "session"):
            self._local.session = requests.Session()
        return self._local.session

    def _headers(self) -> dict:
        headers = {
            "authorization": f"Bearer {self.token}",
            "x-api-version": BLOB_API_VERSION,
        }
        if self.store_id:
            headers["x-vercel-blob-store-id"] = self.store_id
        return headers

    def list_pathnames(self, prefix: str) -> set:
        """All existing blob pathnames under `prefix` (cursor-paginated)."""
        pathnames: set = set()
        cursor = None
        while True:
            params = {"prefix": prefix, "limit": str(LIST_PAGE_SIZE)}
            if cursor:
                params["cursor"] = cursor
            resp = self._session().get(
                f"{self.base_url}?{urlencode(params)}",
                headers=self._headers(),
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            for blob in data.get("blobs", []):
                pathnames.add(blob["pathname"])
            cursor = data.get("cursor")
            if not data.get("hasMore") or not cursor:
                return pathnames

    def put(self, pathname: str, body: bytes, allow_overwrite: bool) -> None:
        """Upload one blob at exactly `pathname` (no random suffix).

        Raises RuntimeError after exhausting retries. A pre-existing blob
        when allow_overwrite is False raises FileExistsError so the caller
        can count it as skipped.
        """
        headers = self._headers()
        headers.update(
            {
                # The store is private: scans must never be publicly readable.
                "x-vercel-blob-access": "private",
                "x-content-type": "image/jpeg",
                "x-add-random-suffix": "0",
                "x-allow-overwrite": "1" if allow_overwrite else "0",
                "x-cache-control-max-age": CACHE_CONTROL_MAX_AGE,
                "content-type": "image/jpeg",
            }
        )
        url = f"{self.base_url}/?{urlencode({'pathname': pathname})}"
        last_error = "unknown error"
        for attempt in range(RETRIES + 1):
            try:
                resp = self._session().put(url, data=body, headers=headers, timeout=120)
            except requests.RequestException as exc:
                last_error = f"network error: {exc}"
            else:
                if resp.ok:
                    return
                message = ""
                try:
                    message = resp.json().get("error", {}).get("message") or ""
                except (ValueError, AttributeError):
                    message = resp.text[:200]
                last_error = f"HTTP {resp.status_code}: {message}"
                if not allow_overwrite and "already exists" in message.lower():
                    raise FileExistsError(pathname)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("retry-after")
                    if retry_after:
                        try:
                            time.sleep(min(float(retry_after), 60.0))
                        except ValueError:
                            pass
            if attempt < RETRIES:
                time.sleep(BACKOFF_SECONDS[attempt])
        raise RuntimeError(f"{pathname}: {last_error}")


class DocStats:
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.rendered = 0
        self.uploaded = 0
        self.skipped = 0
        self.bytes_uploaded = 0
        self.failures = []  # (page_number, error message)
        self.lock = threading.Lock()


def process_document(
    doc_id: str, cfg: dict, args: argparse.Namespace, client: BlobClient
) -> DocStats:
    stats = DocStats(doc_id)
    pdf_path = REPO_ROOT / cfg["pdf"]
    if not pdf_path.is_file():
        stats.failures.append((0, f"PDF not found: {pdf_path}"))
        return stats

    existing: set = set()
    if not args.overwrite:
        try:
            existing = client.list_pathnames(f"scans/{doc_id}/")
        except requests.RequestException as exc:
            print(f"[{doc_id}] WARNING: listing existing blobs failed ({exc}); "
                  "resume disabled for this doc, uploading all pages.")
    print(f"[{doc_id}] {len(existing)} pages already in Blob")

    doc = fitz.open(pdf_path)
    if doc.page_count != cfg["pages"]:
        print(f"[{doc_id}] WARNING: PDF has {doc.page_count} pages, "
              f"contract says {cfg['pages']}")
    n_pages = doc.page_count if args.limit is None else min(args.limit, doc.page_count)

    def upload_job(page_number: int, body: bytes) -> None:
        try:
            client.put(blob_pathname(doc_id, page_number), body, args.overwrite)
        except FileExistsError:
            with stats.lock:
                stats.skipped += 1
        except Exception as exc:  # noqa: BLE001 - recorded, reported at the end
            with stats.lock:
                stats.failures.append((page_number, str(exc)))
        else:
            with stats.lock:
                stats.uploaded += 1
                stats.bytes_uploaded += len(body)

    def progress(processed: int) -> None:
        with stats.lock:
            mb = stats.bytes_uploaded / (1024 * 1024)
            print(f"[{doc_id}] {processed}/{n_pages} processed | "
                  f"rendered {stats.rendered}, uploaded {stats.uploaded}, "
                  f"skipped {stats.skipped}, failed {len(stats.failures)} | "
                  f"{mb:.1f} MB uploaded")

    pending: list = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for i in range(n_pages):
            page_number = i + 1
            pathname = blob_pathname(doc_id, page_number)
            if pathname in existing and not args.overwrite:
                with stats.lock:
                    stats.skipped += 1
            else:
                body = render_page_jpeg(doc, i, args.dpi, args.quality)
                with stats.lock:
                    stats.rendered += 1
                pending.append(pool.submit(upload_job, page_number, body))
                # Keep at most ~3x concurrency renders in flight (memory bound).
                if len(pending) >= args.concurrency * 3:
                    done, not_done = wait(pending, return_when=FIRST_COMPLETED)
                    pending = list(not_done)
            if page_number % 25 == 0:
                progress(page_number)
        if pending:
            wait(pending)
    doc.close()
    progress(n_pages)
    return stats


def run_dry_run(args: argparse.Namespace) -> int:
    sample_dir = Path(args.sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)
    print(f"Dry run: rendering sample pages to {sample_dir} "
          f"(dpi={args.dpi}, quality={args.quality}); no uploads.\n")

    per_doc_kb = {}
    total_estimate_mb = 0.0
    for doc_id in args.docs:
        cfg = DOCS[doc_id]
        sample_page = DRY_RUN_SAMPLES[doc_id]
        pdf_path = REPO_ROOT / cfg["pdf"]
        if not pdf_path.is_file():
            print(f"[{doc_id}] ERROR: PDF not found: {pdf_path}")
            return 1
        doc = fitz.open(pdf_path)
        if sample_page > doc.page_count:
            print(f"[{doc_id}] ERROR: sample page {sample_page} > "
                  f"{doc.page_count} pages in PDF")
            return 1
        zoom = args.dpi / 72.0
        page = doc.load_page(sample_page - 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        body = pix.tobytes("jpg", jpg_quality=args.quality)
        out = sample_dir / f"{doc_id}_{sample_page:04d}.jpg"
        out.write_bytes(body)
        kb = len(body) / 1024.0
        per_doc_kb[doc_id] = kb
        doc_mb = kb * cfg["pages"] / 1024.0
        total_estimate_mb += doc_mb
        print(f"[{doc_id}] page {sample_page}: {pix.width}x{pix.height} px, "
              f"{kb:.1f} KB -> est. {doc_mb:.1f} MB for {cfg['pages']} pages "
              f"({out.name})")
        doc.close()

    total_pages = sum(DOCS[d]["pages"] for d in args.docs)
    print(f"\nEstimated total for {total_pages} pages at these settings: "
          f"{total_estimate_mb:.1f} MB "
          f"(avg {1024 * total_estimate_mb / total_pages:.0f} KB/page; "
          f"target ~150-300 KB/page)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render PDF pages to JPEG and upload to Vercel Blob "
                    "(scans/<id>/<NNNN>.jpg)."
    )
    parser.add_argument("--docs", nargs="+", default=list(DOCS.keys()),
                        choices=list(DOCS.keys()), metavar="ID",
                        help="document ids to process (default: all four)")
    parser.add_argument("--dpi", type=int, default=130,
                        help="render resolution (default: 130)")
    parser.add_argument("--quality", type=int, default=72,
                        help="JPEG quality 1-100 (default: 72)")
    parser.add_argument("--dry-run", action="store_true",
                        help="render one sample page per doc locally; no network")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="only the first N pages per doc (for testing)")
    parser.add_argument("--concurrency", type=int, default=4,
                        help="parallel upload threads (default: 4)")
    parser.add_argument("--overwrite", action="store_true",
                        help="re-upload pages even if already present in Blob")
    parser.add_argument("--sample-dir",
                        default=os.path.join(tempfile.gettempdir(),
                                             "upload_scans_samples"),
                        help="where --dry-run writes sample JPEGs")
    args = parser.parse_args()

    # Deduplicate --docs, preserving the contract order.
    args.docs = [d for d in DOCS if d in set(args.docs)]

    if args.dry_run:
        return run_dry_run(args)

    load_dotenv(REPO_ROOT / ".env")
    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    if not token:
        print("ERROR: BLOB_READ_WRITE_TOKEN is not set (env or repo-root .env). "
              "Refusing to start a non-dry run.", file=sys.stderr)
        return 2

    client = BlobClient(token)
    all_stats = [process_document(doc_id, DOCS[doc_id], args, client)
                 for doc_id in args.docs]

    print("\n=== Summary ===")
    print(f"{'doc':<12} {'uploaded':>9} {'skipped':>8} {'failed':>7} {'MB':>8}")
    any_failures = False
    for stats in all_stats:
        mb = stats.bytes_uploaded / (1024 * 1024)
        print(f"{stats.doc_id:<12} {stats.uploaded:>9} {stats.skipped:>8} "
              f"{len(stats.failures):>7} {mb:>8.1f}")
        if stats.failures:
            any_failures = True
    if any_failures:
        print("\nFailed pages:")
        for stats in all_stats:
            for page_number, error in stats.failures:
                print(f"  {stats.doc_id} p.{page_number}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
