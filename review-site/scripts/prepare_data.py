#!/usr/bin/env python3
"""Build the review-site data files from the production transcription runs.

For each document this reads the canonical transcriptions.json (and, for the
La Longue Marche volumes, the flash-lite alternate corpus), applies the
inclusion rules, and writes one compact JSON file per document to
review-site/data/<id>.json for the Next.js review app to consume.

Contract (shared with the app):

    {
      "id": "140-3", "title": "...", "subtitle": "...", "totalPages": 696,
      "issueFile": "tex_output/...", "hasAlt": true,
      "pages": {
        "495": { "text": "<canonical LaTeX>",
                  "alt": "<flash-lite LaTeX, only when it also qualifies>",
                  "sim": 0.62,
                  "warnings": ["..."],
                  "source": "diagram-retranscription" }
      }
    }

Rules:
  * A page key exists only when the canonical entry has status == "success"
    and its trimmed transcription is at least MIN_CHARS characters.
  * "alt" is present only when the alternate corpus has that page as a
    success meeting the same length bar.
  * "sim" (only when alt is present) is a word-level SequenceMatcher ratio
    using the same tokenization as the corpus audit (audit_corpus.words),
    rounded to 3 decimals.
  * Source entries may carry a "warning" string; it is normalized to the
    list field "warnings", omitted when empty.
  * "source" is copied through when the entry has one.
  * Missing page keys mean "not transcribed" — the app renders a placeholder.

Re-runnable: output files are overwritten in place. No API calls.

Usage (from the repo root):
    python3 review-site/scripts/prepare_data.py
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO / "review-site" / "data"

# Word tokenization must match the project's audit semantics exactly, so it
# is imported from the audit rather than reimplemented here.
sys.path.insert(0, str(REPO / "experiments" / "pilot"))
from audit_corpus import words  # noqa: E402

MIN_CHARS = 30  # same bar as the corpus audit's "empty success" check
LOW_SIM = 0.60  # reporting threshold for the stats table only

DOCUMENTS = [
    {
        "id": "140-3",
        "title": "La Longue Marche — Volume 140-3",
        "subtitle": ("Handwritten manuscript — canonical reading: "
                     "Gemini 3.1 Pro, prompt mateo-canonical"),
        "totalPages": 696,
        "issueFile": "tex_output/la_longue_marche_140-3_mateo-canonical.tex",
        "canonical": "experiments/pilot/production-mateo-canonical/140-3/transcriptions.json",
        "alternate": "experiments/pilot/production-flash-lite-mateo/140-3/transcriptions.json",
    },
    {
        "id": "140-4",
        "title": "La Longue Marche — Volume 140-4",
        "subtitle": ("Handwritten manuscript — canonical reading: "
                     "Gemini 3.1 Pro, prompt mateo-canonical"),
        "totalPages": 280,
        "issueFile": "tex_output/la_longue_marche_140-4_mateo-canonical.tex",
        "canonical": "experiments/pilot/production-mateo-canonical/140-4/transcriptions.json",
        "alternate": "experiments/pilot/production-flash-lite-mateo/140-4/transcriptions.json",
    },
    {
        "id": "preschemas",
        "title": "Préschémas (Bourbaki, Schémas)",
        "subtitle": "Typescript — Gemini Flash-Lite, page-by-page",
        "totalPages": 437,
        "issueFile": "tex_output/bourbaki_schemes_pages_flash-lite.tex",
        "canonical": "experiments/bourbaki/production-pages/transcriptions.json",
        "alternate": None,
    },
    {
        "id": "varietes",
        "title": "Catégories de variétés (U46)",
        "subtitle": "Typescript with handwritten symbols — page-by-page",
        "totalPages": 100,
        "issueFile": "tex_output/varietes_categories_U46.tex",
        "canonical": "experiments/varietes/production-pages/transcriptions.json",
        "alternate": None,
    },
]


def qualifying_text(entry: dict | None) -> str | None:
    """The entry's transcription, or None when it does not qualify.

    Qualifies = recorded as a success and at least MIN_CHARS after trimming.
    """
    if not entry or entry.get("status") != "success":
        return None
    text = entry.get("transcription") or ""
    if len(text.strip()) < MIN_CHARS:
        return None
    return text


def normalize_warnings(entry: dict) -> list[str]:
    """Collect warning strings from an entry as a flat list.

    Production entries carry at most a single "warning" string, but a
    "warnings" list is accepted too so a future corpus change won't drop data.
    """
    out: list[str] = []
    w = entry.get("warning")
    if isinstance(w, str) and w.strip():
        out.append(w)
    elif isinstance(w, list):
        out.extend(str(x) for x in w if str(x).strip())
    ws = entry.get("warnings")
    if isinstance(ws, str) and ws.strip():
        out.append(ws)
    elif isinstance(ws, list):
        out.extend(str(x) for x in ws if str(x).strip())
    return out


def word_similarity(a: str, b: str) -> float:
    """Word-token similarity, matching the audit's echo-detection semantics."""
    return difflib.SequenceMatcher(None, words(a), words(b), autojunk=False).ratio()


def build_document(doc: dict) -> tuple[dict, dict]:
    """Build one document's data file content. Returns (data, stats)."""
    canonical = json.loads((REPO / doc["canonical"]).read_text(encoding="utf-8"))
    alternate = None
    if doc["alternate"]:
        alternate = json.loads((REPO / doc["alternate"]).read_text(encoding="utf-8"))

    pages: dict[str, dict] = {}
    missing: list[int] = []
    sims: list[float] = []
    n_warned = 0

    for page in range(1, doc["totalPages"] + 1):
        key = str(page)
        entry = canonical.get(key)
        text = qualifying_text(entry)
        if text is None:
            missing.append(page)
            continue

        record: dict = {"text": text}

        if alternate is not None:
            alt_text = qualifying_text(alternate.get(key))
            if alt_text is not None:
                record["alt"] = alt_text
                sim = round(word_similarity(text, alt_text), 3)
                record["sim"] = sim
                sims.append(sim)

        warnings = normalize_warnings(entry)
        if warnings:
            record["warnings"] = warnings
            n_warned += 1

        source = entry.get("source")
        if source:
            record["source"] = source

        pages[key] = record

    data = {
        "id": doc["id"],
        "title": doc["title"],
        "subtitle": doc["subtitle"],
        "totalPages": doc["totalPages"],
        "issueFile": doc["issueFile"],
        "hasAlt": doc["alternate"] is not None,
        "pages": pages,
    }
    stats = {
        "included": len(pages),
        "total": doc["totalPages"],
        "missing": missing,
        "with_alt": len(sims),
        "mean_sim": (sum(sims) / len(sims)) if sims else None,
        "min_sim": min(sims) if sims else None,
        "low_sim": sum(1 for s in sims if s < LOW_SIM),
        "with_warnings": n_warned,
    }
    return data, stats


def fmt(value: float | None, spec: str = ".3f") -> str:
    return "-" if value is None else format(value, spec)


def validate(out_paths: dict[str, Path]) -> None:
    """Re-open every written file and spot-check known pages."""
    loaded = {doc_id: json.loads(p.read_text(encoding="utf-8"))
              for doc_id, p in out_paths.items()}

    p495 = loaded["140-3"]["pages"].get("495")
    assert p495 is not None, "140-3 page 495 missing"
    assert p495.get("text") and p495.get("alt"), "140-3 page 495 lacks text or alt"
    assert loaded["preschemas"]["pages"].get("338"), "preschemas page 338 missing"
    assert loaded["varietes"]["pages"].get("1"), "varietes page 1 missing"
    print("Validation pass: all files re-load as JSON; "
          "140-3 p.495 has text+alt, preschemas p.338 and varietes p.1 exist.")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    header = (f"{'doc':<12} {'pages':>9} {'alt':>5} {'mean sim':>9} "
              f"{'min sim':>8} {'sim<' + format(LOW_SIM, '.2f'):>9} "
              f"{'warned':>7} {'size MB':>8}")
    print(header)
    print("-" * len(header))

    out_paths: dict[str, Path] = {}
    all_missing: dict[str, list[int]] = {}

    for doc in DOCUMENTS:
        data, stats = build_document(doc)
        out_path = DATA_DIR / f"{doc['id']}.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        out_paths[doc["id"]] = out_path

        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"{doc['id']:<12} {stats['included']:>4}/{stats['total']:<4} "
              f"{stats['with_alt']:>5} {fmt(stats['mean_sim']):>9} "
              f"{fmt(stats['min_sim']):>8} {stats['low_sim']:>9} "
              f"{stats['with_warnings']:>7} {size_mb:>8.2f}")

        if stats["missing"]:
            all_missing[doc["id"]] = stats["missing"]

    print()
    for doc_id, missing in all_missing.items():
        print(f"WARNING: {doc_id} is missing {len(missing)} page(s): "
              + ", ".join(str(p) for p in missing))
    if not all_missing:
        print("All documents complete: every page qualified for inclusion.")

    validate(out_paths)


if __name__ == "__main__":
    main()
