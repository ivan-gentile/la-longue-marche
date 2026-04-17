"""
Generate production dashboard showing transcription progress and quality.

Usage:
    python3 production_dashboard.py
    # Open production_dashboard.html in browser
"""

import base64
import json
import random
from pathlib import Path

import fitz

BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent.parent
RAW_PDF_DIR = PROJECT_DIR / "raw_pdf"
PRODUCTION_DIR = BASE_DIR / "production"
OUTPUT_HTML = BASE_DIR / "production_dashboard.html"

VOLUMES = {
    "140-3": {"pdf": "140-3.pdf", "pages": 696},
    "140-4": {"pdf": "140-4.pdf", "pages": 280},
}


def render_page_image(pdf_path: Path, page_idx: int, dpi: int = 120) -> str:
    """Render a PDF page to base64 PNG."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_idx]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(img_bytes).decode()


def load_production_data():
    """Load all production transcription data."""
    data = {}
    for vol_key, vol_info in VOLUMES.items():
        results_file = PRODUCTION_DIR / vol_key / "transcriptions.json"
        if results_file.exists():
            with open(results_file, encoding="utf-8") as f:
                data[vol_key] = json.load(f)
        else:
            data[vol_key] = {}
    return data


def get_sample_pages(data: dict, vol_key: str, n: int = 8) -> list[int]:
    """Get a spread of sample pages for visual preview."""
    success_pages = sorted(
        int(k) for k, v in data[vol_key].items()
        if v.get("status") == "success"
    )
    if len(success_pages) <= n:
        return success_pages

    # Pick evenly spaced pages
    step = len(success_pages) // n
    return [success_pages[i * step] for i in range(n)]


def build_html(data: dict):
    """Build the production dashboard HTML."""
    # Compute stats per volume
    vol_stats = {}
    for vol_key, vol_info in VOLUMES.items():
        results = data[vol_key]
        total = vol_info["pages"]
        success = sum(1 for v in results.values() if v.get("status") == "success")
        errors = sum(1 for v in results.values() if v.get("status") == "error")
        remaining = total - success
        total_chars = sum(len(v.get("transcription", "")) for v in results.values()
                         if v.get("status") == "success")
        total_tok_in = sum(v.get("usage", {}).get("prompt_tokens", 0) or 0
                          for v in results.values() if v.get("status") == "success")
        total_tok_out = sum(v.get("usage", {}).get("output_tokens", 0) or 0
                           for v in results.values() if v.get("status") == "success")
        avg_chars = total_chars / success if success else 0

        # Cost estimate (Pro pricing)
        cost = (total_tok_in * 2.00 + total_tok_out * 12.00) / 1_000_000

        vol_stats[vol_key] = {
            "total": total, "success": success, "errors": errors,
            "remaining": remaining, "total_chars": total_chars,
            "total_tok_in": total_tok_in, "total_tok_out": total_tok_out,
            "avg_chars": avg_chars, "cost": cost,
            "pct": success / total * 100,
        }

    grand_success = sum(s["success"] for s in vol_stats.values())
    grand_total = sum(s["total"] for s in vol_stats.values())
    grand_chars = sum(s["total_chars"] for s in vol_stats.values())
    grand_cost = sum(s["cost"] for s in vol_stats.values())
    grand_pct = grand_success / grand_total * 100

    # Render sample pages with transcriptions
    sample_pages_js = "{"
    for vol_key in VOLUMES:
        samples = get_sample_pages(data, vol_key, n=6)
        pdf_path = RAW_PDF_DIR / VOLUMES[vol_key]["pdf"]

        for page_num in samples:
            page_idx = page_num - 1
            try:
                img_b64 = render_page_image(pdf_path, page_idx, dpi=120)
                trans = data[vol_key].get(str(page_num), {}).get("transcription", "")
                chars = len(trans)
                trans_esc = trans.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                sample_pages_js += f'  "{vol_key}_p{page_num}": {{"img":"data:image/png;base64,{img_b64}","text":`{trans_esc}`,"chars":{chars},"vol":"{vol_key}","page":{page_num}}},\n'
            except Exception as e:
                print(f"  Warning: couldn't render {vol_key} p{page_num}: {e}")

    sample_pages_js += "}"

    # Page completion map (for heatmap)
    completion_js = "{"
    for vol_key in VOLUMES:
        completion_js += f'  "{vol_key}": {{'
        total = VOLUMES[vol_key]["pages"]
        for page_num in range(1, total + 1):
            pkey = str(page_num)
            status = data[vol_key].get(pkey, {}).get("status", "missing")
            chars = len(data[vol_key].get(pkey, {}).get("transcription", ""))
            completion_js += f'{page_num}:{{s:"{status[0]}",c:{chars}}},'
        completion_js += "},\n"
    completion_js += "}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Production Dashboard — Grothendieck OCR</title>
<style>
:root {{
  --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
  --border: #30363d; --text: #c9d1d9; --text2: #8b949e;
  --accent: #58a6ff; --green: #3fb950; --red: #f85149;
  --orange: #d29922; --purple: #bc8cff; --pink: #f0883e;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); }}

header {{
  background: var(--bg2); border-bottom: 1px solid var(--border);
  padding: 20px 24px;
}}
header h1 {{ font-size: 1.3em; margin-bottom: 4px; }}
header h1 span {{ color: var(--accent); }}
header .meta {{ font-size: 0.8em; color: var(--text2); }}

.container {{ max-width: 1400px; margin: 0 auto; padding: 20px 24px; }}

.card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 16px 0; }}
.card {{
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px; transition: border-color 0.2s;
}}
.card h3 {{ font-size: 0.72em; color: var(--text2); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
.card .big {{ font-size: 1.8em; font-weight: 700; }}
.card .sub {{ font-size: 0.72em; color: var(--text2); margin-top: 4px; }}
.green {{ color: var(--green); }}
.red {{ color: var(--red); }}
.orange {{ color: var(--orange); }}
.blue {{ color: var(--accent); }}
.purple {{ color: var(--purple); }}

.section {{ margin: 32px 0; }}
.section-title {{ font-size: 1.1em; font-weight: 600; margin-bottom: 12px; }}
.section-sub {{ font-size: 0.8em; color: var(--text2); margin-bottom: 12px; }}

.progress-bar {{
  height: 24px; background: var(--bg3); border-radius: 6px; overflow: hidden;
  display: flex; margin: 8px 0;
}}
.progress-fill {{
  height: 100%; display: flex; align-items: center; justify-content: center;
  font-size: 0.72em; font-weight: 600; transition: width 0.5s ease;
}}

.vol-row {{ display: grid; grid-template-columns: 80px 1fr 100px; gap: 12px; align-items: center; margin: 8px 0; }}
.vol-label {{ font-weight: 600; font-size: 0.9em; }}
.vol-count {{ font-size: 0.8em; color: var(--text2); text-align: right; }}

.heatstrip {{
  display: flex; flex-wrap: wrap; gap: 1px; margin: 8px 0;
}}
.heatstrip-cell {{
  width: 6px; height: 18px; border-radius: 1px;
}}

table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.82em; }}
th {{ text-align: left; padding: 8px 10px; background: var(--bg3); border-bottom: 1px solid var(--border); color: var(--text2); font-size: 0.78em; text-transform: uppercase; }}
td {{ padding: 7px 10px; border-bottom: 1px solid var(--border); }}
tr:hover td {{ background: var(--bg2); }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

.viewer-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
.viewer-card {{
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
}}
.viewer-card-header {{
  padding: 8px 12px; background: var(--bg3); border-bottom: 1px solid var(--border);
  font-size: 0.82em; font-weight: 600; display: flex; justify-content: space-between;
}}
.viewer-card img {{ width: 100%; display: block; cursor: pointer; }}
.viewer-card pre {{
  padding: 10px 12px; font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.72em; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word;
  max-height: 300px; overflow: auto; display: none;
}}

.config-box {{
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px;
  padding: 16px; font-size: 0.82em;
}}
.config-row {{ display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--border); }}
.config-row:last-child {{ border-bottom: none; }}
.config-key {{ color: var(--text2); }}
.config-val {{ font-weight: 600; }}
</style>
</head>
<body>

<header>
  <h1><span>La Longue Marche</span> — Production Transcription Dashboard</h1>
  <div class="meta">Grothendieck Manuscripts · Gemini 3.1 Pro · {grand_success}/{grand_total} pages ({grand_pct:.0f}%) · Generated 2026-03-06</div>
</header>

<div class="container">

  <!-- Summary Cards -->
  <div class="card-grid">
    <div class="card"><h3>Pages Transcribed</h3><div class="big green">{grand_success}</div><div class="sub">of {grand_total} total</div></div>
    <div class="card"><h3>Completion</h3><div class="big blue">{grand_pct:.0f}%</div><div class="sub">batch jobs processing remaining {grand_total - grand_success}</div></div>
    <div class="card"><h3>Total Characters</h3><div class="big">{grand_chars:,}</div><div class="sub">~{grand_chars // 5:,} words of mathematical French</div></div>
    <div class="card"><h3>Cost So Far</h3><div class="big orange">${grand_cost:.2f}</div><div class="sub">Gemini Pro pricing</div></div>
    <div class="card"><h3>Model</h3><div class="big purple">Pro</div><div class="sub">gemini-3.1-pro-preview, medium thinking</div></div>
    <div class="card"><h3>Avg per Page</h3><div class="big">{grand_chars // grand_success if grand_success else 0}</div><div class="sub">characters of transcription</div></div>
  </div>

  <!-- Progress per Volume -->
  <div class="section">
    <div class="section-title">Progress by Volume</div>"""

    for vol_key, s in vol_stats.items():
        pct = s["pct"]
        color = "var(--green)" if pct > 80 else "var(--accent)" if pct > 40 else "var(--orange)"
        html += f"""
    <div class="vol-row">
      <div class="vol-label">{vol_key}</div>
      <div class="progress-bar">
        <div class="progress-fill" style="width:{pct:.0f}%;background:{color}">{s['success']}/{s['total']}</div>
      </div>
      <div class="vol-count">{pct:.0f}% · {s['remaining']} left</div>
    </div>"""

    html += f"""
  </div>

  <!-- Page Completion Heatmap -->
  <div class="section">
    <div class="section-title">Page Completion Map</div>
    <div class="section-sub">Each cell = 1 page. Green = transcribed, red = error, dark = remaining.</div>
    <div id="heatmap-container"></div>
  </div>

  <!-- Volume Stats Table -->
  <div class="section">
    <div class="section-title">Detailed Statistics</div>
    <table>
      <thead>
        <tr><th>Volume</th><th class="num">Pages</th><th class="num">Done</th><th class="num">Errors</th><th class="num">Characters</th><th class="num">Avg/Page</th><th class="num">Tokens In</th><th class="num">Tokens Out</th><th class="num">Cost</th></tr>
      </thead>
      <tbody>"""

    for vol_key, s in vol_stats.items():
        html += f"""
        <tr>
          <td><strong>{vol_key}</strong></td>
          <td class="num">{s['total']}</td>
          <td class="num" style="color:var(--green)">{s['success']}</td>
          <td class="num" style="color:var(--red)">{s['errors']}</td>
          <td class="num">{s['total_chars']:,}</td>
          <td class="num">{s['avg_chars']:.0f}</td>
          <td class="num">{s['total_tok_in']:,}</td>
          <td class="num">{s['total_tok_out']:,}</td>
          <td class="num">${s['cost']:.2f}</td>
        </tr>"""

    html += f"""
        <tr style="font-weight:700;border-top:2px solid var(--border);">
          <td>Total</td>
          <td class="num">{grand_total}</td>
          <td class="num" style="color:var(--green)">{grand_success}</td>
          <td class="num" style="color:var(--red)">{sum(s['errors'] for s in vol_stats.values())}</td>
          <td class="num">{grand_chars:,}</td>
          <td class="num">{grand_chars // grand_success if grand_success else 0}</td>
          <td class="num">{sum(s['total_tok_in'] for s in vol_stats.values()):,}</td>
          <td class="num">{sum(s['total_tok_out'] for s in vol_stats.values()):,}</td>
          <td class="num">${grand_cost:.2f}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Pipeline Configuration -->
  <div class="section">
    <div class="section-title">Pipeline Configuration</div>
    <div class="config-box">
      <div class="config-row"><span class="config-key">Model</span><span class="config-val">gemini-3.1-pro-preview</span></div>
      <div class="config-row"><span class="config-key">Thinking Level</span><span class="config-val">medium</span></div>
      <div class="config-row"><span class="config-key">Prompt Style</span><span class="config-val">text-first-fewshot</span></div>
      <div class="config-row"><span class="config-key">Input Format</span><span class="config-val">PDF direct (no image rendering)</span></div>
      <div class="config-row"><span class="config-key">Context</span><span class="config-val">Previous page PDF passed alongside current page</span></div>
      <div class="config-row"><span class="config-key">Max Output Tokens</span><span class="config-val">16,000</span></div>
      <div class="config-row"><span class="config-key">Temperature</span><span class="config-val">1.0</span></div>
      <div class="config-row"><span class="config-key">Optimal Config Source</span><span class="config-val">Benchmark V2 — 17 conditions × 4 pages = 68 experiments</span></div>
    </div>
  </div>

  <!-- Sample Transcriptions -->
  <div class="section">
    <div class="section-title">Sample Transcriptions</div>
    <div class="section-sub">Click any page image to toggle transcription view.</div>
    <div class="viewer-grid" id="viewer-grid"></div>
  </div>

</div>

<script>
const COMPLETION = {completion_js};
const SAMPLES = {sample_pages_js};

// Render heatmap
function renderHeatmap() {{
  const container = document.getElementById('heatmap-container');
  let h = '';
  for (const [vol, pages] of Object.entries(COMPLETION)) {{
    const total = Object.keys(pages).length;
    h += `<div style="margin:8px 0"><span style="font-size:0.82em;font-weight:600;">${{vol}}</span> <span style="font-size:0.72em;color:var(--text2);">${{total}} pages</span></div>`;
    h += '<div class="heatstrip">';
    for (let i = 1; i <= total; i++) {{
      const p = pages[i];
      let color = 'var(--bg3)';
      let title = `p${{i}}: missing`;
      if (p) {{
        if (p.s === 's') {{ color = 'var(--green)'; title = `p${{i}}: ${{p.c}} chars`; }}
        else if (p.s === 'e') {{ color = 'var(--red)'; title = `p${{i}}: error`; }}
      }}
      h += `<div class="heatstrip-cell" style="background:${{color}}" title="${{title}}"></div>`;
    }}
    h += '</div>';
  }}
  container.innerHTML = h;
}}

// Render sample viewer
function renderViewer() {{
  const grid = document.getElementById('viewer-grid');
  let h = '';
  for (const [key, sample] of Object.entries(SAMPLES)) {{
    h += `<div class="viewer-card">
      <div class="viewer-card-header">
        <span>${{sample.vol}} — Page ${{sample.page}}</span>
        <span style="color:var(--text2)">${{sample.chars}} chars</span>
      </div>
      <img src="${{sample.img}}" onclick="this.parentElement.querySelector('pre').style.display = this.parentElement.querySelector('pre').style.display === 'block' ? 'none' : 'block'" title="Click to show transcription">
      <pre>${{escHtml(sample.text)}}</pre>
    </div>`;
  }}
  grid.innerHTML = h;
}}

function escHtml(s) {{ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }}

renderHeatmap();
renderViewer();
</script>
</body>
</html>"""

    return html


def main():
    print("Loading production data...")
    data = load_production_data()

    for vol_key in VOLUMES:
        success = sum(1 for v in data[vol_key].values() if v.get("status") == "success")
        print(f"  {vol_key}: {success}/{VOLUMES[vol_key]['pages']}")

    print("Rendering sample pages...")
    html = build_html(data)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = OUTPUT_HTML.stat().st_size / 1024
    print(f"\nDashboard saved: {OUTPUT_HTML} ({size_kb:.0f} KB)")
    print(f"Open: file:///D:/documents-Orso/code/la_longe_marche/experiments/pilot/production_dashboard.html")


if __name__ == "__main__":
    main()
