"""
Scan production transcriptions and identify all pages containing diagrams.

Outputs diagram_pages.json with page list, classification, and metadata.

Usage:
    python3 find_diagram_pages.py
    python3 find_diagram_pages.py --verbose
"""

import argparse
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
PRODUCTION_DIR = BASE_DIR / "production"
OUTPUT_FILE = BASE_DIR / "diagram_pages.json"

VOLUMES = {
    "140-3": {"pdf": "140-3.pdf", "pages": 696},
    "140-4": {"pdf": "140-4.pdf", "pages": 280},
}

# Detection patterns
DIAGRAM_MARKER = re.compile(r'\[DIAGRAM:([^\]]*)\]', re.IGNORECASE)
DOWNARROW = re.compile(r'\\downarrow|\\uparrow|\\Downarrow|\\Uparrow')
HORIZ_ARROW = re.compile(r'\\longrightarrow|\\longleftarrow|\\hookrightarrow|\\twoheadrightarrow|\\xrightarrow|\\xleftarrow')
SEARROW = re.compile(r'\\searrow|\\swarrow|\\nearrow|\\nwarrow')
MATRIX_ENV = re.compile(r'\\begin\{(matrix|array|pmatrix|bmatrix)\}')
TIKZCD_ENV = re.compile(r'\\begin\{tikzcd\}')


def classify_diagram(text: str) -> dict:
    """Analyze a transcription and return diagram metadata."""
    markers = DIAGRAM_MARKER.findall(text)
    downarrows = len(DOWNARROW.findall(text))
    horiz_arrows = len(HORIZ_ARROW.findall(text))
    diag_arrows = len(SEARROW.findall(text))
    has_matrix = bool(MATRIX_ENV.search(text))
    has_tikzcd = bool(TIKZCD_ENV.search(text))
    total_arrows = downarrows + horiz_arrows + diag_arrows

    # Classify diagram handling approach
    approaches = []
    if markers:
        approaches.append("marker")
    if downarrows >= 2 and not has_matrix:
        approaches.append("stacked-arrows")
    if has_matrix:
        approaches.append("matrix-env")
    if has_tikzcd:
        approaches.append("tikzcd")
    if diag_arrows > 0:
        approaches.append("diagonal-arrows")

    # Determine if this page has a 2D diagram (not just horizontal exact sequences)
    has_2d_diagram = (
        downarrows >= 2
        or diag_arrows > 0
        or bool(markers)
        or (has_matrix and downarrows >= 1)
    )

    return {
        "has_diagram": has_2d_diagram,
        "marker_count": len(markers),
        "marker_descriptions": markers[:5],  # first 5
        "downarrows": downarrows,
        "horiz_arrows": horiz_arrows,
        "diag_arrows": diag_arrows,
        "total_arrows": total_arrows,
        "has_matrix_env": has_matrix,
        "has_tikzcd": has_tikzcd,
        "approaches": approaches,
    }


def scan_volume(volume_key: str, verbose: bool = False) -> list:
    """Scan a volume and return list of diagram page entries."""
    results_file = PRODUCTION_DIR / volume_key / "transcriptions.json"
    if not results_file.exists():
        print(f"  WARNING: {results_file} not found")
        return []

    with open(results_file, encoding="utf-8") as f:
        data = json.load(f)

    diagram_pages = []
    for pkey in sorted(data.keys(), key=lambda x: int(x)):
        entry = data[pkey]
        if entry.get("status") != "success":
            continue

        text = entry.get("transcription", "")
        info = classify_diagram(text)

        if info["has_diagram"]:
            page_entry = {
                "volume": volume_key,
                "page": int(pkey),
                **info,
            }
            diagram_pages.append(page_entry)

            if verbose:
                approaches_str = ", ".join(info["approaches"]) if info["approaches"] else "none"
                desc = info["marker_descriptions"][0][:60] if info["marker_descriptions"] else ""
                print(f"  p{pkey:>4}: arrows={info['total_arrows']:>3} "
                      f"↓={info['downarrows']:>2} ↗={info['diag_arrows']:>1} "
                      f"[{approaches_str}] {desc}")

    return diagram_pages


def main():
    parser = argparse.ArgumentParser(description="Find diagram pages in transcriptions")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("Scanning for diagram pages...")
    all_pages = []

    for vol_key in VOLUMES:
        print(f"\n  Volume {vol_key}:")
        pages = scan_volume(vol_key, verbose=args.verbose)
        all_pages.extend(pages)
        print(f"  → {len(pages)} diagram pages found")

    # Summary statistics
    by_approach = {}
    for p in all_pages:
        for a in p["approaches"]:
            by_approach[a] = by_approach.get(a, 0) + 1

    high_complexity = [p for p in all_pages if p["total_arrows"] >= 10]
    marker_only = [p for p in all_pages if p["approaches"] == ["marker"]]

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  Total diagram pages: {len(all_pages)}")
    print(f"  By volume: 140-3={sum(1 for p in all_pages if p['volume']=='140-3')}, "
          f"140-4={sum(1 for p in all_pages if p['volume']=='140-4')}")
    print(f"  By approach:")
    for approach, count in sorted(by_approach.items(), key=lambda x: -x[1]):
        print(f"    {approach}: {count}")
    print(f"  High complexity (≥10 arrows): {len(high_complexity)}")
    print(f"  Marker-only (no rendering): {len(marker_only)}")
    print(f"  Already tikzcd: {by_approach.get('tikzcd', 0)}")

    # Save output
    output = {
        "generated": __import__("datetime").datetime.now().isoformat(),
        "total_diagram_pages": len(all_pages),
        "summary": {
            "by_volume": {
                "140-3": sum(1 for p in all_pages if p["volume"] == "140-3"),
                "140-4": sum(1 for p in all_pages if p["volume"] == "140-4"),
            },
            "by_approach": by_approach,
            "high_complexity": len(high_complexity),
            "marker_only": len(marker_only),
        },
        "pages": all_pages,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
