"""Scan every transcription corpus for silent defects.

Three failure classes can put wrong text in a deliverable without any
error being recorded, so none of them are visible in a run's success
count:

1. **Context echo** — the model transcribes the previous page (attached
   as visual context) instead of its target page, producing a corpus
   silently shifted by one. Detected as high similarity between a page
   and its predecessor.
2. **Empty or near-empty success** — a page stored as `success` with no
   real content; the resume logic then skips it forever and the tex
   renders a blank page under a valid marker.
3. **Duplicate pages** — identical text at two non-adjacent positions,
   which usually means one of them is wrong.

Reports only; it never modifies a corpus. Pages flagged here are the
ones worth re-running or checking against the scan.

Usage:
    python experiments/pilot/audit_corpus.py
    python experiments/pilot/audit_corpus.py --threshold 0.9
"""

from __future__ import annotations

import argparse
import difflib
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

CORPORA = [
    ("La Longue Marche 140-3 — mateo-canonical (Pro)",
     HERE / "production-mateo-canonical" / "140-3", 696),
    ("La Longue Marche 140-4 — mateo-canonical (Pro)",
     HERE / "production-mateo-canonical" / "140-4", 280),
    ("La Longue Marche 140-3 — flash-lite-mateo",
     HERE / "production-flash-lite-mateo" / "140-3", 696),
    ("La Longue Marche 140-4 — flash-lite-mateo",
     HERE / "production-flash-lite-mateo" / "140-4", 280),
    ("Préschémas (Bourbaki Schémas) — page-by-page",
     REPO / "experiments" / "bourbaki" / "production-pages", 437),
    ("Catégories de variétés (U46) — page-by-page",
     REPO / "experiments" / "varietes" / "production-pages", 100),
]

MIN_CHARS = 30


def normalize(text: str) -> str:
    """Drop comment lines so page markers/marginalia don't drive similarity."""
    return "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("%")
    ).strip()


def audit(path: Path, total: int, threshold: float) -> dict | None:
    tpath = path / "transcriptions.json"
    if not tpath.exists():
        return None
    data = json.loads(tpath.read_text(encoding="utf-8"))

    echoes: list[tuple[int, float]] = []
    empties: list[int] = []
    texts: dict[int, str] = {}

    for page in range(1, total + 1):
        entry = data.get(str(page), {})
        if entry.get("status") != "success":
            continue
        raw = entry.get("transcription", "") or ""
        if len(raw.strip()) < MIN_CHARS:
            empties.append(page)
            continue
        texts[page] = normalize(raw)

    for page, text in texts.items():
        prev = texts.get(page - 1)
        if not prev or not text:
            continue
        ratio = difflib.SequenceMatcher(None, prev, text).ratio()
        if ratio >= threshold:
            echoes.append((page, round(ratio, 3)))

    by_text: dict[str, list[int]] = {}
    for page, text in texts.items():
        by_text.setdefault(text, []).append(page)
    duplicates = [
        pages for text, pages in by_text.items()
        if len(pages) > 1 and max(pages) - min(pages) > 1
    ]

    return {
        "pages_with_text": len(texts),
        "echoes": echoes,
        "empty_successes": empties,
        "duplicate_groups": duplicates,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", type=float, default=0.75,
                    help="Similarity at or above which a page counts as an echo")
    args = ap.parse_args()

    lines = [
        "# Corpus audit — silent defects",
        "",
        f"Generated {date.today().isoformat()} by "
        "`experiments/pilot/audit_corpus.py` (no API calls). Echo threshold: "
        f"{args.threshold}.",
        "",
        "Checks each corpus for pages that were recorded as successful but "
        "may carry wrong content: a page echoing its predecessor (the model "
        "transcribing its context page instead of its target), a success with "
        "no real text, or identical text at two distant positions.",
        "",
        "| Corpus | Pages with text | Echoes | Empty successes | Duplicate groups |",
        "|---|---|---|---|---|",
    ]
    details: list[str] = []
    clean = True

    for name, path, total in CORPORA:
        res = audit(path, total, args.threshold)
        if res is None:
            continue
        n_e, n_x, n_d = (len(res["echoes"]), len(res["empty_successes"]),
                         len(res["duplicate_groups"]))
        if n_e or n_x or n_d:
            clean = False
        lines.append(
            f"| {name} | {res['pages_with_text']} | {n_e} | {n_x} | {n_d} |"
        )
        if n_e:
            details.append(f"### Echoes — {name}\n")
            details.append(
                "\n".join(f"- page {p}: {r} similarity to page {p - 1}"
                          for p, r in res["echoes"]) + "\n"
            )
        if n_x:
            details.append(f"### Empty successes — {name}\n")
            details.append(
                "- pages: " + ", ".join(str(p) for p in res["empty_successes"]) + "\n"
            )
        if n_d:
            details.append(f"### Duplicate groups — {name}\n")
            details.append(
                "\n".join("- pages " + ", ".join(str(p) for p in sorted(g))
                          for g in res["duplicate_groups"]) + "\n"
            )

    lines.append("")
    if clean:
        lines.append("No defects of any of the three classes were found.")
        lines.append("")
    else:
        lines += ["", *details]

    out = HERE / "CORPUS_AUDIT.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:40]))
    print(f"\nwrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
