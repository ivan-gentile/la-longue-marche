"""Rebuild `tex_output/la_longue_marche_{volume}.tex` from the current
`production/{volume}/transcriptions.json`.

Simple deterministic concatenation:

    % <header>
    %% ===== Page 1 =====
    <transcription>
    \newpage
    %% ===== Page 2 =====
    ...

Run this after `retranscribe_diagrams.py --merge` and
`normalize_notation.py --mode regex` so the output reflects the latest
corpus state. Unlike earlier hand-assembled tex files, this is
reproducible from the repo.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PRODUCTION_DIR = HERE / "production"
OUT_DIR = REPO / "tex_output"

VOLUMES = {
    "140-3": {"pages": 696, "label": "Volume 140-3"},
    "140-4": {"pages": 280, "label": "Volume 140-4"},
}


def build_volume(vol_key: str) -> Path:
    data_path = PRODUCTION_DIR / vol_key / "transcriptions.json"
    if not data_path.exists():
        raise FileNotFoundError(data_path)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    total = VOLUMES[vol_key]["pages"]

    success = sum(1 for v in data.values() if v.get("status") == "success")
    diagram_merged = sum(1 for v in data.values() if v.get("source") == "diagram-retranscription")

    lines: list[str] = []
    lines.append(f"% La Longue Marche — {VOLUMES[vol_key]['label']}")
    lines.append("% AI Transcription (Gemini 3.1 Pro, medium thinking)")
    lines.append(f"% {success} of {total} pages transcribed successfully")
    if diagram_merged:
        lines.append(f"% {diagram_merged} diagram pages re-transcribed with tikz-cd enhanced prompt")
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

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"la_longue_marche_{vol_key}.tex"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> None:
    for vol in VOLUMES:
        path = build_volume(vol)
        size_kb = path.stat().st_size / 1024
        print(f"  wrote {path.relative_to(REPO)} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
