"""Post-process the `production-mateo-canonical/` corpus.

Steps:
 1. Overlay the existing diagram_transcriptions.json (from the older
    `production/` run with the `diagram-tikzcd` prompt) on top of the
    new mateo-canonical output, so diagram pages keep their specialized
    tikz-cd output.
 2. Run regex notation normalization on the merged corpus (in place).
 3. Build tex_output/la_longue_marche_{vol}_mateo-canonical.tex.
 4. Score Section 49.1 (140-3 pages 495-499) against `49.1new.tex`
    using the shared diagnose_49_1 categorization, and print the
    composite quality.

Usage:
    python experiments/pilot/finalize_mateo_canonical.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
NEW_PROD = HERE / "production-mateo-canonical"
OLD_PROD = HERE / "production"
TEX_OUT = REPO / "tex_output"

VOLUMES = {
    "140-3": {"pages": 696, "label": "Volume 140-3"},
    "140-4": {"pages": 280, "label": "Volume 140-4"},
}


# ---------------------------------------------------------------------------
# Step 1: overlay diagram re-transcriptions
# ---------------------------------------------------------------------------


def overlay_diagrams(vol: str) -> dict:
    """Return merged transcriptions.json for vol after overlaying diagrams."""
    new_path = NEW_PROD / vol / "transcriptions.json"
    diag_path = OLD_PROD / vol / "diagram_transcriptions.json"

    new_data = json.loads(new_path.read_text(encoding="utf-8"))
    diag_count = 0

    if diag_path.exists():
        diag_data = json.loads(diag_path.read_text(encoding="utf-8"))
        for pkey, entry in diag_data.items():
            if entry.get("status") == "success":
                new_data[pkey] = {
                    **entry,
                    "source": "diagram-retranscription",
                }
                diag_count += 1

    # Backup before overwriting
    backup = NEW_PROD / vol / "transcriptions_pre_diagram_overlay.json"
    if not backup.exists():
        backup.write_text(
            json.dumps(new_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    new_path.write_text(
        json.dumps(new_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  {vol}: overlaid {diag_count} diagram retranscriptions")
    return new_data


# ---------------------------------------------------------------------------
# Step 2: notation normalization (regex only)
# ---------------------------------------------------------------------------


def normalize_inplace(vol: str) -> None:
    """Apply normalize_notation.py regex rules to the new corpus in place."""
    sys.path.insert(0, str(HERE))
    import normalize_notation as nn

    rules = nn.build_regex_rules()

    path = NEW_PROD / vol / "transcriptions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    total = 0
    pages_changed = 0
    for pkey, entry in data.items():
        if entry.get("status") != "success":
            continue
        text = entry.get("transcription", "")
        new_text, changes = nn.apply_regex_normalization(text, rules)
        if changes:
            pages_changed += 1
            total += sum(c["count"] for c in changes)
            entry["transcription"] = new_text
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  {vol}: notation normalization applied {total} changes over {pages_changed} pages")


# ---------------------------------------------------------------------------
# Step 3: build tex_output
# ---------------------------------------------------------------------------


def build_tex(vol: str) -> Path:
    data = json.loads((NEW_PROD / vol / "transcriptions.json").read_text(encoding="utf-8"))
    total = VOLUMES[vol]["pages"]
    success = sum(1 for v in data.values() if v.get("status") == "success")
    diag_merged = sum(1 for v in data.values() if v.get("source") == "diagram-retranscription")

    lines: list[str] = []
    lines.append(f"% La Longue Marche — {VOLUMES[vol]['label']} — mateo-canonical re-run")
    lines.append("% Model: Gemini 3.1 Pro (medium thinking)")
    lines.append("% Prompt: mateo-canonical (notation + structure block, Part I few-shot pool)")
    lines.append(f"% Pages transcribed: {success}/{total}")
    if diag_merged:
        lines.append(f"% Pages overlaid from diagram-tikzcd branch: {diag_merged}")
    lines.append(f"% Rebuilt: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    for page in range(1, total + 1):
        key = str(page)
        entry = data.get(key, {})
        lines.append(f"%% ===== Page {page} =====")
        lines.append("")
        if entry.get("status") == "success":
            lines.append(entry.get("transcription", "").strip())
        else:
            lines.append(f"%% [page {page} missing or failed: {entry.get('error', 'no entry')}]")
        lines.append("")
        if page < total:
            lines.append("\\newpage")
            lines.append("")

    out_path = TEX_OUT / f"la_longue_marche_{vol}_mateo-canonical.tex"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    kb = out_path.stat().st_size / 1024
    print(f"  wrote {out_path.relative_to(REPO)} ({kb:.1f} KB, {success}/{total} pages)")
    return out_path


# ---------------------------------------------------------------------------
# Step 4: score Section 49.1 against 49.1new.tex
# ---------------------------------------------------------------------------


def score_section_49() -> dict:
    from diagnose_49_1 import categorize, score as score_profile

    data = json.loads((NEW_PROD / "140-3" / "transcriptions.json").read_text(encoding="utf-8"))
    pages = [str(p) for p in range(495, 500)]
    text = "\n\n".join(data[p]["transcription"] for p in pages if data.get(p, {}).get("status") == "success")

    new_tex = (REPO / "reference" / "validation" / "49.1new.tex").read_text(encoding="utf-8")
    profile = categorize(text, new_tex)
    scr = score_profile(profile)
    return {"length": len(text), "score": scr}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 70)
    print("Finalizing mateo-canonical corpus")
    print("=" * 70)

    # Step 1
    print("\n[1/4] Overlay diagram re-transcriptions...")
    for vol in VOLUMES:
        overlay_diagrams(vol)

    # Step 2
    print("\n[2/4] Notation normalization (regex, in place)...")
    for vol in VOLUMES:
        try:
            normalize_inplace(vol)
        except AttributeError as e:
            print(f"  {vol}: {e!r} — skipping (normalize_notation has no apply_regex_rules fn)")

    # Step 3
    print("\n[3/4] Build tex_output files...")
    for vol in VOLUMES:
        build_tex(vol)

    # Step 4
    print("\n[4/4] Score Section 49.1 on the new corpus...")
    res = score_section_49()
    s = res["score"]
    print(f"  length: {res['length']:,} chars")
    print(f"  raw residue per 1000 chars:     {s['raw_density_per_kchar']}")
    print(f"  notation drift per 1000 chars:  {s['notation_density_per_kchar']}")
    print(f"  structure coverage:             {s['structure_coverage']:.0%}")
    print(f"  COMPOSITE QUALITY:              {s['quality']}")
    print()
    print("  (shipped corpus scored 0.113, Claude+mateo-canonical 0.661,")
    print("   pilot Gemini+mateo-canonical on 5 pages scored 0.742)")

    # Persist the final score as a small report
    out = NEW_PROD / "FINAL_SCORE.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
