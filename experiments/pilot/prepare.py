"""
Pilot preparation: render benchmark pages, extract reference text, generate strips.

This script needs NO API key. Run it first to prepare all assets for the pilot.

Usage:
    python prepare.py
"""

import fitz  # PyMuPDF
import json
import os
from pathlib import Path
from PIL import Image
import io

# --- Configuration ---
BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent.parent
SCAN_PDF = PROJECT_DIR / "raw_pdf" / "140-2.pdf"
REFERENCE_PDF = PROJECT_DIR / "G103d.pdf"
IMAGES_DIR = BASE_DIR / "images"
STRIPS_DIR = BASE_DIR / "strips"
REFERENCE_DIR = BASE_DIR / "reference"

# Benchmark pages: Grothendieck page numbers (scan_page = groth_page + 1)
# Group A: early pages (§1, Topos multigaloisiens) — foundational, medium density
# Group B: mid-document pages (around §10-11) — denser, more notation
BENCHMARK_PAGES = {
    "group_a": [1, 2, 3, 4, 5],      # Grothendieck pages 1-5
    "group_b": [50, 51, 52, 53, 54],  # Grothendieck pages 50-54
}

# Image settings
FULL_PAGE_DPI = 300
STRIP_DPI = 300
NUM_STRIPS = 3
STRIP_OVERLAP_RATIO = 0.15  # 15% overlap between strips

# Header/footer crop ratios (archive watermarks)
HEADER_CROP_RATIO = 0.04   # top 4%
FOOTER_CROP_RATIO = 0.05   # bottom 5%


def render_page_to_image(doc, page_idx, dpi=300):
    """Render a PDF page to PIL Image at given DPI."""
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=dpi)
    img_data = pix.tobytes("png")
    return Image.open(io.BytesIO(img_data))


def crop_archive_borders(img):
    """Remove archive header and footer watermarks."""
    w, h = img.size
    top = int(h * HEADER_CROP_RATIO)
    bottom = int(h * (1 - FOOTER_CROP_RATIO))
    return img.crop((0, top, w, bottom))


def generate_strips(img, num_strips=3, overlap_ratio=0.15):
    """Split image into horizontal strips with overlap."""
    w, h = img.size

    # Calculate strip height with overlap
    # Total height covered = strip_height * num_strips - overlap * (num_strips - 1)
    # h = strip_height * num_strips - strip_height * overlap_ratio * (num_strips - 1)
    # h = strip_height * (num_strips - overlap_ratio * (num_strips - 1))
    effective_multiplier = num_strips - overlap_ratio * (num_strips - 1)
    strip_height = int(h / effective_multiplier)
    overlap_px = int(strip_height * overlap_ratio)

    strips = []
    for i in range(num_strips):
        top = i * (strip_height - overlap_px)
        bottom = min(top + strip_height, h)
        strip = img.crop((0, top, w, bottom))
        strips.append(strip)

    return strips


def extract_reference_text(ref_doc):
    """Extract all text from G103d.pdf organized by page."""
    reference = {}
    for i in range(len(ref_doc)):
        text = ref_doc[i].get_text().strip()
        if text:
            reference[i + 1] = text  # 1-indexed
    return reference


def find_reference_sections(ref_doc):
    """Map section numbers to G103d page ranges."""
    sections = {}
    current_section = None

    for i in range(len(ref_doc)):
        text = ref_doc[i].get_text()
        for line in text.split('\n'):
            if '§' in line and '—' in line:
                # Extract section number
                parts = line.split('§')[1].split('—')[0].strip().rstrip('.')
                current_section = parts
                if current_section not in sections:
                    sections[current_section] = {"start": i + 1, "end": None, "title": line.strip()[:80]}

    # Set end pages
    section_keys = list(sections.keys())
    for idx, key in enumerate(section_keys):
        if idx + 1 < len(section_keys):
            sections[key]["end"] = sections[section_keys[idx + 1]]["start"] - 1
        else:
            sections[key]["end"] = len(ref_doc)

    return sections


def main():
    print("=" * 60)
    print("GROTHENDIECK OCR PILOT — Preparation")
    print("=" * 60)

    # Verify source files exist
    assert SCAN_PDF.exists(), f"Scan PDF not found: {SCAN_PDF}"
    assert REFERENCE_PDF.exists(), f"Reference PDF not found: {REFERENCE_PDF}"

    # Create output directories
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    STRIPS_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    # Open PDFs
    scan_doc = fitz.open(str(SCAN_PDF))
    ref_doc = fitz.open(str(REFERENCE_PDF))

    print(f"\nScan PDF: {len(scan_doc)} pages")
    print(f"Reference PDF: {len(ref_doc)} pages")

    all_pages = BENCHMARK_PAGES["group_a"] + BENCHMARK_PAGES["group_b"]
    print(f"Benchmark pages (Grothendieck numbering): {all_pages}")

    # --- Step 1: Render benchmark pages as full-page images ---
    print(f"\n--- Step 1: Rendering {len(all_pages)} pages at {FULL_PAGE_DPI} DPI ---")

    for groth_page in all_pages:
        scan_page_idx = groth_page  # scan page index is groth_page + 1 - 1 (0-indexed)
        # Actually: scan page 2 = groth page 1, so scan_page_idx = groth_page (0-indexed: groth_page)

        if scan_page_idx >= len(scan_doc):
            print(f"  WARNING: Grothendieck page {groth_page} (scan idx {scan_page_idx}) out of range")
            continue

        # Render full page
        img = render_page_to_image(scan_doc, scan_page_idx, dpi=FULL_PAGE_DPI)

        # Save raw (with archive header)
        raw_path = IMAGES_DIR / f"page_{groth_page:04d}_raw.png"
        img.save(str(raw_path))

        # Crop archive borders
        img_cropped = crop_archive_borders(img)
        cropped_path = IMAGES_DIR / f"page_{groth_page:04d}.png"
        img_cropped.save(str(cropped_path))

        # Generate strips
        strips = generate_strips(img_cropped, NUM_STRIPS, STRIP_OVERLAP_RATIO)
        for s_idx, strip in enumerate(strips):
            strip_path = STRIPS_DIR / f"page_{groth_page:04d}_strip_{s_idx + 1}.png"
            strip.save(str(strip_path))

        print(f"  Page {groth_page}: {img.size} → cropped {img_cropped.size} → {len(strips)} strips")

    # --- Step 2: Extract reference text ---
    print(f"\n--- Step 2: Extracting reference text from G103d.pdf ---")

    ref_text = extract_reference_text(ref_doc)
    ref_sections = find_reference_sections(ref_doc)

    # Save full reference text
    full_ref_path = REFERENCE_DIR / "g103d_full_text.json"
    with open(full_ref_path, 'w', encoding='utf-8') as f:
        json.dump(ref_text, f, ensure_ascii=False, indent=2)
    print(f"  Full reference: {len(ref_text)} pages → {full_ref_path}")

    # Save section map
    sections_path = REFERENCE_DIR / "g103d_sections.json"
    with open(sections_path, 'w', encoding='utf-8') as f:
        json.dump(ref_sections, f, ensure_ascii=False, indent=2)
    print(f"  Section map: {len(ref_sections)} sections → {sections_path}")

    # Extract reference text for benchmark-relevant sections
    # Group A (pages 1-5) → §1 (G103d pages 6-9)
    # Group B (pages 50-54) → §10 area (G103d pages ~50-55)

    # Save section-specific reference
    for section_id, section_info in ref_sections.items():
        start = section_info["start"]
        end = section_info["end"]
        section_text = []
        for p in range(start, end + 1):
            if p in ref_text:
                section_text.append(f"--- G103d page {p} ---\n{ref_text[p]}")

        if section_text:
            section_path = REFERENCE_DIR / f"section_{section_id.replace(' ', '_')}.txt"
            with open(section_path, 'w', encoding='utf-8') as f:
                f.write(f"Section: {section_info['title']}\n")
                f.write(f"G103d pages: {start}-{end}\n\n")
                f.write("\n\n".join(section_text))

    print(f"  Extracted {len(ref_sections)} section reference files")

    # --- Step 3: Create pilot metadata ---
    print(f"\n--- Step 3: Creating pilot metadata ---")

    metadata = {
        "benchmark_pages": BENCHMARK_PAGES,
        "all_pages": all_pages,
        "settings": {
            "full_page_dpi": FULL_PAGE_DPI,
            "strip_dpi": STRIP_DPI,
            "num_strips": NUM_STRIPS,
            "strip_overlap_ratio": STRIP_OVERLAP_RATIO,
            "header_crop_ratio": HEADER_CROP_RATIO,
            "footer_crop_ratio": FOOTER_CROP_RATIO,
        },
        "experiments": [
            {
                "id": "A",
                "name": "full_page_no_context",
                "description": "Full page image, no sequential context",
                "image_type": "full_page",
                "with_context": False,
            },
            {
                "id": "B",
                "name": "full_page_with_context",
                "description": "Full page image, with previous page transcription as context",
                "image_type": "full_page",
                "with_context": True,
            },
            {
                "id": "C",
                "name": "strips_no_context",
                "description": "3 horizontal strips per page, no sequential context",
                "image_type": "strips",
                "with_context": False,
            },
            {
                "id": "D",
                "name": "strips_with_context",
                "description": "3 horizontal strips per page, with previous page transcription as context",
                "image_type": "strips",
                "with_context": True,
            },
        ],
        "reference_pdf": "G103d.pdf",
        "scan_pdf": "raw_pdf/140-2.pdf",
    }

    meta_path = BASE_DIR / "pilot_metadata.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print("PREPARATION COMPLETE")
    print(f"{'=' * 60}")

    # Count generated files
    n_images = len(list(IMAGES_DIR.glob("*.png")))
    n_strips = len(list(STRIPS_DIR.glob("*.png")))
    n_refs = len(list(REFERENCE_DIR.glob("*")))

    print(f"  Full-page images: {n_images} (in {IMAGES_DIR})")
    print(f"  Strip images:     {n_strips} (in {STRIPS_DIR})")
    print(f"  Reference files:  {n_refs} (in {REFERENCE_DIR})")
    print(f"  Metadata:         {meta_path}")

    print(f"\n  Experiments to run (4 conditions × {len(all_pages)} pages):")
    print(f"    A) Full page, no context:   {len(all_pages)} API calls")
    print(f"    B) Full page, with context: {len(all_pages)} API calls")
    print(f"    C) Strips, no context:      {len(all_pages) * NUM_STRIPS} API calls")
    print(f"    D) Strips, with context:    {len(all_pages) * NUM_STRIPS} API calls")
    total_calls = len(all_pages) * 2 + len(all_pages) * NUM_STRIPS * 2
    print(f"    TOTAL: {total_calls} API calls")
    print(f"\n  Estimated cost (Gemini 2.0 Flash): ~${total_calls * 0.003:.2f}")
    print(f"  Estimated cost (Gemini 2.5 Pro):   ~${total_calls * 0.02:.2f}")

    print(f"\n  Next step: Set GEMINI_API_KEY and run pilot_run.py")

    scan_doc.close()
    ref_doc.close()


if __name__ == "__main__":
    main()
