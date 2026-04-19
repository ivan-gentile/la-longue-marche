"""Post-process the `production-flash-lite-mateo/` corpus.

Steps:
 1. Overlay existing diagram_transcriptions.json (tikz-cd specialized run)
 2. Regex notation normalization in place
 3. Build tex_output/la_longue_marche_{vol}_flash-lite-mateo.tex
 4. Score Section 49.1 vs 49.1new.tex and print composite quality

Usage:
    python experiments/pilot/finalize_flash_lite.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

NEW_PROD = HERE / "production-flash-lite-mateo"
OLD_PROD = HERE / "production"
TEX_OUT = REPO / "tex_output"

VOLUMES = {
    "140-3": {"pages": 696, "label": "Volume 140-3"},
    "140-4": {"pages": 280, "label": "Volume 140-4"},
}

sys.path.insert(0, str(HERE))
import normalize_notation as nn
from diagnose_49_1 import categorize, score as score_profile


def overlay_diagrams(vol: str) -> int:
    path = NEW_PROD / vol / "transcriptions.json"
    diag_path = OLD_PROD / vol / "diagram_transcriptions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    merged = 0
    if diag_path.exists():
        diag = json.loads(diag_path.read_text(encoding="utf-8"))
        for pkey, entry in diag.items():
            if entry.get("status") == "success":
                data[pkey] = {**entry, "source": "diagram-retranscription"}
                merged += 1
    backup = NEW_PROD / vol / "transcriptions_pre_diagram_overlay.json"
    if not backup.exists():
        backup.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {vol}: overlaid {merged} diagram retranscriptions")
    return merged


def normalize_inplace(vol: str) -> None:
    rules = nn.build_regex_rules()
    path = NEW_PROD / vol / "transcriptions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    total, pages_changed = 0, 0
    for entry in data.values():
        if entry.get("status") != "success":
            continue
        text = entry.get("transcription", "")
        new_text, changes = nn.apply_regex_normalization(text, rules)
        if changes:
            pages_changed += 1
            total += sum(c["count"] for c in changes)
            entry["transcription"] = new_text
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {vol}: {total} changes over {pages_changed} pages")


def build_tex(vol: str) -> None:
    data = json.loads((NEW_PROD / vol / "transcriptions.json").read_text(encoding="utf-8"))
    total = VOLUMES[vol]["pages"]
    success = sum(1 for v in data.values() if v.get("status") == "success")
    diag_merged = sum(1 for v in data.values() if v.get("source") == "diagram-retranscription")

    lines: list[str] = []
    lines.append(f"% La Longue Marche — {VOLUMES[vol]['label']} — Flash-Lite + mateo-canonical")
    lines.append("% Model: Gemini 3.1 Flash-Lite (thinking=low)")
    lines.append("% Prompt: mateo-canonical (notation + structure block, Part I few-shot pool)")
    lines.append(f"% Pages transcribed: {success}/{total}")
    if diag_merged:
        lines.append(f"% Pages overlaid from diagram-tikzcd branch: {diag_merged}")
    lines.append(f"% Rebuilt: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    for page in range(1, total + 1):
        entry = data.get(str(page), {})
        lines.append(f"%% ===== Page {page} =====")
        lines.append("")
        if entry.get("status") == "success":
            lines.append(entry.get("transcription", "").strip())
        else:
            lines.append(f"%% [page {page} missing or failed]")
        lines.append("")
        if page < total:
            lines.append("\\newpage")
            lines.append("")

    out = TEX_OUT / f"la_longue_marche_{vol}_flash-lite-mateo.tex"
    out.write_text("\n".join(lines), encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"  {vol}: wrote {out.relative_to(REPO)} ({kb:.1f} KB, {success}/{total} pages)")


def score_49() -> dict:
    data = json.loads((NEW_PROD / "140-3" / "transcriptions.json").read_text(encoding="utf-8"))
    gt = [str(p) for p in range(495, 500) if data.get(str(p), {}).get("status") == "success"]
    text = "\n\n".join(data[p]["transcription"] for p in gt)
    new_tex = (REPO / "reference" / "validation" / "49.1new.tex").read_text(encoding="utf-8")
    scr = score_profile(categorize(text, new_tex))
    return {"length": len(text), "score": scr}


def main() -> None:
    print("=" * 70)
    print("Finalizing Flash-Lite + mateo-canonical corpus")
    print("=" * 70)

    print("\n[1/4] Overlay diagram re-transcriptions...")
    for vol in VOLUMES:
        overlay_diagrams(vol)

    print("\n[2/4] Notation normalization...")
    for vol in VOLUMES:
        normalize_inplace(vol)

    print("\n[3/4] Build tex_output...")
    for vol in VOLUMES:
        build_tex(vol)

    print("\n[4/4] Score Section 49.1...")
    res = score_49()
    s = res["score"]
    print(f"  chars: {res['length']:,}")
    print(f"  raw residue/kch:    {s['raw_density_per_kchar']}")
    print(f"  notation drift/kch: {s['notation_density_per_kchar']}")
    print(f"  structure coverage: {s['structure_coverage']:.0%}")
    print(f"  COMPOSITE QUALITY:  {s['quality']}")
    print("\n  Baselines: shipped 0.113 / Pro+mateo 0.742 / pilot Flash-Lite 0.777")

    (NEW_PROD / "FINAL_SCORE.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nWrote {(NEW_PROD / 'FINAL_SCORE.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
