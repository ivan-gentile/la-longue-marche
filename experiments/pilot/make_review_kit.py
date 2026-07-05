"""Build a self-contained side-by-side review kit for a page range.

For each page: the scan (rendered from raw_pdf/ at review resolution)
on the left, the transcription on the right, keyboard navigation, and
a "report anomaly" link that opens the GitHub issue form pre-filled
with file, page and error-type fields.

The kit is written to share/review_kit_<vol>_<first>-<last>/ as plain
files (index.html + img/), meant to be zipped and sent to the reviewer
privately — scan images stay out of the public repository.

Usage:
    python experiments/pilot/make_review_kit.py --volume 140-3 --pages 495-696
    python experiments/pilot/make_review_kit.py --volume 140-4 --pages 1-280 --dpi 120
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

import fitz

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SHARE = REPO / "share"

VOLUMES = {"140-3": "140-3.pdf", "140-4": "140-4.pdf"}
ISSUE_URL = (
    "https://github.com/ivan-gentile/la-longue-marche/issues/new"
    "?template=transcription-anomaly.yml&labels=anomaly"
)

# Preferred source per page: the higher-effort canonical run where it
# has content, the complete Flash-Lite draft otherwise.
SOURCES = [
    ("mateo-canonical (Gemini 3.1 Pro)", HERE / "production-mateo-canonical"),
    ("flash-lite-mateo (Gemini 3.1 Flash-Lite)", HERE / "production-flash-lite-mateo"),
]


def load_pages(vol: str) -> dict[int, tuple[str, str]]:
    """page -> (variant label, transcription text), preferring canonical."""
    merged: dict[int, tuple[str, str]] = {}
    for label, base in reversed(SOURCES):  # canonical last so it wins
        path = base / vol / "transcriptions.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for k, v in data.items():
            text = (v.get("transcription") or "").strip()
            if v.get("status") == "success" and len(text) >= 30:
                merged[int(k)] = (label, text)
    return merged


PAGE_TMPL = """<section class="page" id="p{page}">
<h2>Page {page} <span class="variant">{variant}</span>
<a class="report" href="{issue}&title={issue_title}&file={issue_file}&page={page}"
   target="_blank" rel="noopener">report anomaly</a></h2>
<div class="cols">
  <div class="scan"><img loading="lazy" src="img/p{page}.jpg" alt="scan of page {page}"></div>
  <pre class="tex">{text}</pre>
</div>
</section>
"""

STYLE = """
body{font-family:Georgia,serif;margin:0;background:#faf8f4;color:#222}
header{position:sticky;top:0;background:#2b2118;color:#f5efe3;padding:.6rem 1rem;
  display:flex;gap:1rem;align-items:baseline;z-index:2}
header input{width:5rem;font-size:1rem}
h2{margin:.3rem 0;font-size:1.05rem}
.variant{font-size:.75rem;color:#7a6a52;font-weight:normal;margin-left:.6rem}
.report{font-size:.75rem;margin-left:.8rem}
.page{border-top:2px solid #d8cfc0;padding:.4rem 1rem 1.2rem}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.scan img{width:100%;border:1px solid #c9bda9;background:#fff}
pre.tex{white-space:pre-wrap;font-family:ui-monospace,Consolas,monospace;
  font-size:.82rem;line-height:1.45;background:#fff;border:1px solid #c9bda9;
  padding:.8rem;overflow-x:auto;margin:0}
@media (max-width:900px){.cols{grid-template-columns:1fr}}
"""

SCRIPT = """
document.getElementById('goto').addEventListener('change', e => {
  const el = document.getElementById('p' + e.target.value);
  if (el) el.scrollIntoView();
});
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--volume", required=True, choices=list(VOLUMES))
    ap.add_argument("--pages", required=True, help="range, e.g. 495-696")
    ap.add_argument("--dpi", type=int, default=110)
    args = ap.parse_args()

    m = re.fullmatch(r"(\d+)-(\d+)", args.pages)
    if not m:
        ap.error("--pages must look like 495-696")
    first, last = int(m.group(1)), int(m.group(2))

    out = SHARE / f"review_kit_{args.volume}_{first}-{last}"
    (out / "img").mkdir(parents=True, exist_ok=True)

    pages = load_pages(args.volume)
    doc = fitz.open(str(REPO / "raw_pdf" / VOLUMES[args.volume]))
    tex_file = f"tex_output/la_longue_marche_{args.volume}_mateo-canonical.tex"

    sections = []
    zoom = args.dpi / 72
    for page in range(first, last + 1):
        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        pix.save(out / "img" / f"p{page}.jpg", jpg_quality=70)
        variant, text = pages.get(page, ("—", "[page not transcribed yet]"))
        sections.append(
            PAGE_TMPL.format(
                page=page,
                variant=html.escape(variant),
                text=html.escape(text),
                issue=ISSUE_URL,
                issue_title=quote(f"[anomaly] {args.volume} p.{page}: "),
                issue_file=quote(tex_file, safe=""),
            )
        )
        if (page - first) % 25 == 0:
            print(f"  rendered p{page}")
    doc.close()

    page_html = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>Review — {args.volume} pages {first}-{last}</title>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<style>{STYLE}</style></head><body>"
        f"<header><strong>La Longue Marche — {args.volume}, pages {first}–{last}</strong>"
        f"<label>go to page <input id='goto' type='number' min='{first}' max='{last}'></label>"
        "<span style='font-size:.75rem'>scan left — transcription right — "
        "“report anomaly” opens a pre-filled GitHub issue</span></header>"
        + "\n".join(sections)
        + f"<script>{SCRIPT}</script></body></html>"
    )
    (out / "index.html").write_text(page_html, encoding="utf-8")
    size_mb = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"wrote {out} ({size_mb:.1f} MB, {last - first + 1} pages)")


if __name__ == "__main__":
    main()
