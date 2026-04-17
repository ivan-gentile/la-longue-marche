"""
Generate interactive page-by-page viewer for Grothendieck manuscript transcriptions.

Left panel: PDF page image (loaded from external folder)
Right panel: Transcription (switchable between raw text and rendered LaTeX)
Navigation: prev/next buttons, volume selector, page number input

Usage:
    python3 viewer_dashboard.py
    # Open viewer_dashboard.html in browser (from same directory)
"""

import base64
import json
import sys
from pathlib import Path

import fitz

BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent.parent
RAW_PDF_DIR = PROJECT_DIR / "raw_pdf"
PRODUCTION_DIR = BASE_DIR / "production"
OUTPUT_HTML = BASE_DIR / "viewer_dashboard.html"
PAGES_DIR = BASE_DIR / "viewer_pages"

VOLUMES = {
    "140-3": {"pdf": "140-3.pdf", "pages": 696},
    "140-4": {"pdf": "140-4.pdf", "pages": 280},
}


def main():
    print("Loading production data...")
    data = {}
    for vol_key, vol_info in VOLUMES.items():
        results_file = PRODUCTION_DIR / vol_key / "transcriptions.json"
        if results_file.exists():
            with open(results_file, encoding="utf-8") as f:
                data[vol_key] = json.load(f)
        else:
            data[vol_key] = {}

    # Stats
    total_success = 0
    total_pages = 0
    total_chars = 0
    for vol_key, vol_info in VOLUMES.items():
        s = sum(1 for v in data[vol_key].values() if v.get("status") == "success")
        total_success += s
        total_pages += vol_info["pages"]
        total_chars += sum(len(v.get("transcription", "")) for v in data[vol_key].values() if v.get("status") == "success")
        print(f"  {vol_key}: {s}/{vol_info['pages']} pages")

    # Render page images to external JPEG files
    print("Rendering page images to viewer_pages/ ...")
    for vol_key, vol_info in VOLUMES.items():
        pdf_path = RAW_PDF_DIR / vol_info["pdf"]
        vol_dir = PAGES_DIR / vol_key
        vol_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(str(pdf_path))
        total = vol_info["pages"]

        for page_num in range(1, total + 1):
            img_path = vol_dir / f"{page_num}.jpg"
            if img_path.exists():
                continue  # Skip already rendered
            page = doc[page_num - 1]
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            pix.save(str(img_path), "jpeg")
            if page_num % 100 == 0 or page_num == total:
                print(f"  {vol_key}: {page_num}/{total}")

        doc.close()

    # Build transcription data (text only, no images)
    print("Building transcription data...")
    trans_data = {}
    for vol_key, vol_info in VOLUMES.items():
        vol_trans = {}
        for page_num in range(1, vol_info["pages"] + 1):
            entry = data[vol_key].get(str(page_num), {})
            status = entry.get("status", "missing")
            trans = entry.get("transcription", "")
            vol_trans[page_num] = {
                "text": trans,
                "chars": len(trans),
                "status": status,
            }
        trans_data[vol_key] = vol_trans

    trans_js = json.dumps(trans_data, ensure_ascii=False)

    # Volume info for JS
    volumes_js = json.dumps({
        vol_key: {"pages": vol_info["pages"]}
        for vol_key, vol_info in VOLUMES.items()
    })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>La Longue Marche — Page Viewer</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<style>
:root {{
  --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
  --border: #30363d; --text: #c9d1d9; --text2: #8b949e;
  --accent: #58a6ff; --green: #3fb950; --red: #f85149;
  --orange: #d29922; --purple: #bc8cff;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}

/* Top bar */
.topbar {{
  background: var(--bg2); border-bottom: 1px solid var(--border);
  padding: 10px 20px; display: flex; align-items: center; gap: 16px; flex-shrink: 0;
}}
.topbar h1 {{ font-size: 1em; white-space: nowrap; }}
.topbar h1 span {{ color: var(--accent); }}
.topbar .stats {{ font-size: 0.78em; color: var(--text2); }}

/* Navigation */
.nav {{
  background: var(--bg3); border-bottom: 1px solid var(--border);
  padding: 8px 20px; display: flex; align-items: center; gap: 12px; flex-shrink: 0;
}}
.nav select, .nav input {{
  background: var(--bg); color: var(--text); border: 1px solid var(--border);
  border-radius: 4px; padding: 5px 8px; font-size: 0.85em;
}}
.nav input[type=number] {{ width: 70px; }}
.nav button {{
  background: var(--bg2); color: var(--text); border: 1px solid var(--border);
  border-radius: 4px; padding: 5px 14px; font-size: 0.85em; cursor: pointer;
  transition: background 0.15s;
}}
.nav button:hover {{ background: var(--accent); color: #000; }}
.nav button:disabled {{ opacity: 0.3; cursor: default; background: var(--bg2); color: var(--text); }}
.nav .sep {{ width: 1px; height: 20px; background: var(--border); }}
.nav .page-info {{ font-size: 0.82em; color: var(--text2); min-width: 100px; }}
.mode-toggle {{
  display: flex; border: 1px solid var(--border); border-radius: 4px; overflow: hidden; margin-left: auto;
}}
.mode-toggle button {{
  border: none; border-radius: 0; border-right: 1px solid var(--border);
  padding: 5px 12px;
}}
.mode-toggle button:last-child {{ border-right: none; }}
.mode-toggle button.active {{ background: var(--accent); color: #000; }}

/* Main viewer */
.viewer {{
  flex: 1; display: flex; overflow: hidden;
}}

/* Left panel: PDF page */
.panel-left {{
  flex: 1; overflow: auto; display: flex; align-items: flex-start; justify-content: center;
  background: #1a1a2e; padding: 10px;
}}
.panel-left img {{
  max-width: 100%; max-height: calc(100vh - 100px); object-fit: contain;
}}

/* Divider */
.divider {{
  width: 4px; background: var(--border); cursor: col-resize; flex-shrink: 0;
}}
.divider:hover {{ background: var(--accent); }}

/* Right panel: Transcription */
.panel-right {{
  flex: 1; overflow: auto; padding: 20px; background: var(--bg);
}}
.panel-right pre {{
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 0.82em; line-height: 1.7; white-space: pre-wrap; word-wrap: break-word;
  color: var(--text);
}}
.panel-right .latex-rendered {{
  font-family: 'Computer Modern', 'Latin Modern Roman', Georgia, serif;
  font-size: 1em; line-height: 1.8; color: var(--text);
}}
.panel-right .latex-rendered p {{
  margin-bottom: 0.8em;
}}
.panel-right .no-transcription {{
  color: var(--text2); font-style: italic; padding: 40px; text-align: center;
}}
.panel-right .status-badge {{
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.72em;
  margin-bottom: 12px;
}}
.status-success {{ background: rgba(63,185,80,0.15); color: var(--green); }}
.status-error {{ background: rgba(248,81,73,0.15); color: var(--red); }}
.status-missing {{ background: rgba(139,148,158,0.15); color: var(--text2); }}

/* Keyboard shortcut hint */
.shortcuts {{
  font-size: 0.7em; color: var(--text2); display: flex; gap: 12px; align-items: center;
}}
.shortcuts kbd {{
  background: var(--bg); border: 1px solid var(--border); border-radius: 3px;
  padding: 1px 5px; font-family: monospace; font-size: 0.95em;
}}
</style>
</head>
<body>

<div class="topbar">
  <h1><span>La Longue Marche</span> — Viewer</h1>
  <div class="stats">{total_success}/{total_pages} pages · {total_chars:,} characters · Gemini 3.1 Pro</div>
</div>

<div class="nav">
  <select id="vol-select" onchange="changeVolume()">
    <option value="140-3">Volume 140-3 (696 pages)</option>
    <option value="140-4">Volume 140-4 (280 pages)</option>
  </select>
  <button onclick="prevPage()" id="btn-prev" title="Previous page">&#9664; Prev</button>
  <input type="number" id="page-input" min="1" value="1" onchange="goToPage()" onkeydown="if(event.key==='Enter')goToPage()">
  <button onclick="nextPage()" id="btn-next" title="Next page">Next &#9654;</button>
  <div class="sep"></div>
  <div class="page-info" id="page-info">Page 1 / 696</div>
  <div class="sep"></div>
  <div class="shortcuts">
    <kbd>&#8592;</kbd><kbd>&#8594;</kbd> navigate
    <kbd>T</kbd> toggle view
  </div>
  <div class="mode-toggle">
    <button id="btn-text" class="active" onclick="setMode('text')">Source</button>
    <button id="btn-latex" onclick="setMode('latex')">Rendered</button>
  </div>
</div>

<div class="viewer">
  <div class="panel-left" id="panel-left">
    <img id="page-img" src="" alt="Loading...">
  </div>
  <div class="divider" id="divider"></div>
  <div class="panel-right" id="panel-right">
    <pre id="text-view"></pre>
    <div id="latex-view" class="latex-rendered" style="display:none"></div>
  </div>
</div>

<script>
const VOLUMES = {volumes_js};
const TRANS = {trans_js};

let currentVol = '140-3';
let currentPage = 1;
let mode = 'text'; // 'text' or 'latex'

function loadPage() {{
  const entry = TRANS[currentVol] && TRANS[currentVol][currentPage];
  const maxPage = VOLUMES[currentVol].pages;

  // Update nav
  document.getElementById('page-input').value = currentPage;
  document.getElementById('page-input').max = maxPage;
  document.getElementById('page-info').textContent = `Page ${{currentPage}} / ${{maxPage}}`;
  document.getElementById('btn-prev').disabled = currentPage <= 1;
  document.getElementById('btn-next').disabled = currentPage >= maxPage;

  // Image from external file
  document.getElementById('page-img').src = `viewer_pages/${{currentVol}}/${{currentPage}}.jpg`;

  if (!entry) {{
    document.getElementById('text-view').textContent = 'No data for this page.';
    document.getElementById('latex-view').innerHTML = '<div class="no-transcription">No data for this page.</div>';
    return;
  }}

  // Status + transcription
  const statusClass = entry.status === 'success' ? 'status-success' : entry.status === 'error' ? 'status-error' : 'status-missing';
  const statusLabel = entry.status === 'success' ? `✓ ${{entry.chars}} chars` : entry.status === 'error' ? '✗ Error' : '— Missing';

  if (entry.status === 'success' && entry.text) {{
    // Text view (raw LaTeX source)
    document.getElementById('text-view').textContent = entry.text;

    // LaTeX rendered view
    const lines = entry.text.split('\\n');
    let htmlContent = `<span class="status-badge ${{statusClass}}">${{statusLabel}}</span><br><br>`;
    let inDisplayMath = false;
    let displayBlock = '';

    for (const line of lines) {{
      if (line.trim().startsWith('$$') && !inDisplayMath) {{
        inDisplayMath = true;
        displayBlock = line.trim().slice(2);
        if (displayBlock.endsWith('$$')) {{
          displayBlock = displayBlock.slice(0, -2);
          inDisplayMath = false;
          htmlContent += `<div style="text-align:center;margin:12px 0;overflow-x:auto;" class="math-display" data-math="${{escAttr(displayBlock)}}"></div>`;
        }}
      }} else if (inDisplayMath) {{
        if (line.trim().endsWith('$$')) {{
          displayBlock += '\\n' + line.trim().slice(0, -2);
          inDisplayMath = false;
          htmlContent += `<div style="text-align:center;margin:12px 0;overflow-x:auto;" class="math-display" data-math="${{escAttr(displayBlock)}}"></div>`;
        }} else {{
          displayBlock += '\\n' + line;
        }}
      }} else if (line.trim() === '') {{
        htmlContent += '<br>';
      }} else {{
        htmlContent += `<p>${{escHtml(line)}}</p>`;
      }}
    }}

    document.getElementById('latex-view').innerHTML = htmlContent;

    // Render display math blocks with KaTeX
    document.querySelectorAll('.math-display').forEach(el => {{
      try {{
        katex.render(el.dataset.math, el, {{ displayMode: true, throwOnError: false, trust: true }});
      }} catch(e) {{
        el.textContent = el.dataset.math;
      }}
    }});

    // Render inline math in paragraphs
    renderMathInElement(document.getElementById('latex-view'), {{
      delimiters: [
        {{left: '$$', right: '$$', display: true}},
        {{left: '$', right: '$', display: false}},
      ],
      throwOnError: false,
      trust: true,
    }});

  }} else {{
    const msg = entry.status === 'error' ? 'Transcription failed for this page.' : 'No transcription available.';
    document.getElementById('text-view').textContent = msg;
    document.getElementById('latex-view').innerHTML = `<div class="no-transcription">${{msg}}</div>`;
  }}

  updateModeView();
}}

function setMode(m) {{
  mode = m;
  document.getElementById('btn-text').classList.toggle('active', m === 'text');
  document.getElementById('btn-latex').classList.toggle('active', m === 'latex');
  updateModeView();
}}

function updateModeView() {{
  document.getElementById('text-view').style.display = mode === 'text' ? 'block' : 'none';
  document.getElementById('latex-view').style.display = mode === 'latex' ? 'block' : 'none';
}}

function prevPage() {{ if (currentPage > 1) {{ currentPage--; loadPage(); }} }}
function nextPage() {{ if (currentPage < VOLUMES[currentVol].pages) {{ currentPage++; loadPage(); }} }}

function goToPage() {{
  const val = parseInt(document.getElementById('page-input').value);
  const max = VOLUMES[currentVol].pages;
  if (val >= 1 && val <= max) {{ currentPage = val; loadPage(); }}
}}

function changeVolume() {{
  currentVol = document.getElementById('vol-select').value;
  currentPage = 1;
  loadPage();
}}

function escHtml(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}
function escAttr(s) {{ return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}

// Keyboard navigation
document.addEventListener('keydown', e => {{
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.key === 'ArrowLeft') {{ prevPage(); e.preventDefault(); }}
  else if (e.key === 'ArrowRight') {{ nextPage(); e.preventDefault(); }}
  else if (e.key === 't' || e.key === 'T') {{ setMode(mode === 'text' ? 'latex' : 'text'); e.preventDefault(); }}
}});

// Draggable divider
const divider = document.getElementById('divider');
let isDragging = false;
divider.addEventListener('mousedown', () => {{ isDragging = true; document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none'; }});
document.addEventListener('mousemove', e => {{
  if (!isDragging) return;
  const container = document.querySelector('.viewer');
  const rect = container.getBoundingClientRect();
  const pct = ((e.clientX - rect.left) / rect.width) * 100;
  if (pct > 20 && pct < 80) {{
    document.querySelector('.panel-left').style.flex = `0 0 ${{pct}}%`;
    document.querySelector('.panel-right').style.flex = `0 0 ${{100 - pct}}%`;
  }}
}});
document.addEventListener('mouseup', () => {{ isDragging = false; document.body.style.cursor = ''; document.body.style.userSelect = ''; }});

// Init
loadPage();
</script>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = OUTPUT_HTML.stat().st_size / (1024 * 1024)
    print(f"\nViewer saved: {OUTPUT_HTML} ({size_mb:.1f} MB)")
    print(f"Open: file:///D:/documents-Orso/code/la_longe_marche/experiments/pilot/viewer_dashboard.html")


if __name__ == "__main__":
    main()
