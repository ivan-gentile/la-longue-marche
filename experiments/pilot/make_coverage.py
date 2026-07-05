"""Generate the page-coverage manifest for the tex_output deliverables.

Reads the per-page transcriptions.json of each production variant and
writes:

  tex_output/coverage.json   machine-readable manifest
  tex_output/COVERAGE.md     human-readable summary for reviewers

A page counts as "transcribed" when its entry has status == "success"
and a non-trivial transcription. Anything else is listed as missing,
so a reviewer never has to discover a gap by scrolling into it.

Usage:
    python experiments/pilot/make_coverage.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TEX_OUT = REPO / "tex_output"

VARIANTS = {
    "flash-lite-mateo": {
        "dir": HERE / "production-flash-lite-mateo",
        "tex": "la_longue_marche_{vol}_flash-lite-mateo.tex",
        "note": "complete corpus, shipped April 2026",
    },
    "mateo-canonical": {
        "dir": HERE / "production-mateo-canonical",
        "tex": "la_longue_marche_{vol}_mateo-canonical.tex",
        "note": "higher-effort Gemini Pro re-run, in progress (free-tier daily quota)",
    },
}

VOLUMES = {"140-3": 696, "140-4": 280}


def page_ranges(pages: list[int]) -> str:
    out: list[str] = []
    start = prev = None
    for p in sorted(pages):
        if start is None:
            start = prev = p
            continue
        if p == prev + 1:
            prev = p
            continue
        out.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = p
    if start is not None:
        out.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(out)


def volume_coverage(variant_dir: Path, vol: str, total: int) -> dict:
    data = json.loads((variant_dir / vol / "transcriptions.json").read_text(encoding="utf-8"))
    config = json.loads((variant_dir / vol / "config.json").read_text(encoding="utf-8"))

    transcribed: list[int] = []
    overlaid: list[int] = []
    for page in range(1, total + 1):
        entry = data.get(str(page), {})
        text = entry.get("transcription", "") or ""
        if entry.get("status") == "success" and len(text.strip()) >= 30:
            transcribed.append(page)
            if entry.get("source") == "diagram-retranscription":
                overlaid.append(page)
    missing = [p for p in range(1, total + 1) if p not in set(transcribed)]

    return {
        "model": config.get("model"),
        "prompt_style": config.get("prompt_style"),
        "thinking_level": config.get("thinking_level"),
        "run_started": config.get("started"),
        "total_pages": total,
        "pages_transcribed": len(transcribed),
        "pages_from_diagram_overlay": len(overlaid),
        "pages_missing": len(missing),
        "missing_ranges": page_ranges(missing),
    }


def main() -> None:
    manifest: dict = {"generated": date.today().isoformat(), "variants": {}}

    for name, spec in VARIANTS.items():
        manifest["variants"][name] = {"note": spec["note"], "volumes": {}}
        for vol, total in VOLUMES.items():
            cov = volume_coverage(spec["dir"], vol, total)
            cov["tex_file"] = spec["tex"].format(vol=vol)
            manifest["variants"][name]["volumes"][vol] = cov

    (TEX_OUT / "coverage.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Page coverage of the tex_output deliverables",
        "",
        f"Generated {manifest['generated']} by `experiments/pilot/make_coverage.py`.",
        "",
        "A page is counted only when the model returned a non-trivial",
        "transcription. Untranscribed pages keep their `%% ===== Page N =====`",
        "marker in the tex file with a one-line reason, so page alignment with",
        "the scans is preserved. Machine-readable version: `coverage.json`.",
        "",
    ]
    for name, vspec in manifest["variants"].items():
        lines.append(f"## Variant `{name}` — {vspec['note']}")
        lines.append("")
        lines.append("| Volume | Tex file | Model | Pages transcribed | Missing | Missing ranges |")
        lines.append("|---|---|---|---|---|---|")
        for vol, cov in vspec["volumes"].items():
            ranges = cov["missing_ranges"] or "—"
            if len(ranges) > 140:
                ranges = ranges[:140] + "… (full list in coverage.json)"
            lines.append(
                f"| {vol} | `{cov['tex_file']}` | {cov['model']} "
                f"| **{cov['pages_transcribed']}/{cov['total_pages']}** "
                f"| {cov['pages_missing']} | {ranges} |"
            )
        lines.append("")

    lines += [
        "## Reading guide",
        "",
        "- `flash-lite-mateo` is the complete working draft of both volumes.",
        "- `mateo-canonical` is the higher-effort Gemini Pro re-run of the same",
        "  pages; it is being filled in as API quota allows and its gaps are",
        "  listed above. Where it covers a page, prefer it over `flash-lite-mateo`.",
        "- Section 49 begins at PDF page 495 of 140-3.",
        "- The Bourbaki *Schémas* typescript transcription",
        "  (`bourbaki_schemes_full_flash-lite.tex`, 437 pages) is complete.",
        "",
    ]
    (TEX_OUT / "COVERAGE.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {TEX_OUT / 'coverage.json'}")
    print(f"wrote {TEX_OUT / 'COVERAGE.md'}")
    for name, vspec in manifest["variants"].items():
        for vol, cov in vspec["volumes"].items():
            print(f"  {name} {vol}: {cov['pages_transcribed']}/{cov['total_pages']} ({cov['pages_missing']} missing)")


if __name__ == "__main__":
    main()
