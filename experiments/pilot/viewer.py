"""
Generate an HTML viewer to compare handwritten images with transcriptions side-by-side.

Usage:
    python viewer.py
    # Then open pilot_viewer.html in browser
"""

import base64
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"
RESULTS_DIR = BASE_DIR / "results"
OUTPUT_HTML = BASE_DIR / "pilot_viewer.html"


def image_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_results():
    """Find all result directories and load them."""
    runs = {}
    for run_dir in sorted(RESULTS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        results_file = run_dir / "all_results.json"
        if results_file.exists():
            with open(results_file, encoding="utf-8") as f:
                data = json.load(f)
            model = data.get("model", run_dir.name)
            runs[model] = data
    return runs


def get_transcription_text(result):
    """Extract transcription text from a result dict."""
    if isinstance(result, dict) and "merged" in result:
        return result["merged"]
    if isinstance(result, dict) and "transcription" in result:
        return result.get("transcription", "")
    return ""


def build_html(runs: dict) -> str:
    # Collect all pages
    all_pages = set()
    for run_data in runs.values():
        all_pages.update(run_data.get("pages", []))
    all_pages = sorted(all_pages)

    models = list(runs.keys())
    experiments = ["A", "B", "C", "D"]
    exp_names = {
        "A": "Full page, no context",
        "B": "Full page, with context",
        "C": "Strips, no context",
        "D": "Strips, with context",
    }

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Grothendieck OCR Pilot — Visual Comparison</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; }}
h1 {{ padding: 20px; background: #16213e; text-align: center; font-size: 1.4em; }}
.controls {{
    position: sticky; top: 0; z-index: 100;
    background: #0f3460; padding: 12px 20px;
    display: flex; gap: 16px; align-items: center; flex-wrap: wrap;
    border-bottom: 2px solid #e94560;
}}
.controls label {{ font-weight: bold; font-size: 0.85em; }}
.controls select, .controls button {{
    padding: 6px 12px; border-radius: 4px; border: 1px solid #555;
    background: #1a1a2e; color: #e0e0e0; font-size: 0.9em; cursor: pointer;
}}
.controls button {{ background: #e94560; border: none; font-weight: bold; }}
.controls button:hover {{ background: #c73a54; }}
.comparison {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 0; min-height: calc(100vh - 120px);
}}
.panel {{ padding: 10px; overflow: auto; }}
.panel-image {{ background: #222; border-right: 2px solid #e94560; text-align: center; }}
.panel-image img {{ max-width: 100%; height: auto; }}
.panel-text {{ background: #1a1a2e; }}
.panel-text pre {{
    white-space: pre-wrap; word-wrap: break-word;
    font-family: 'Fira Code', 'Consolas', monospace; font-size: 0.82em;
    line-height: 1.5; padding: 10px; color: #c8d6e5;
}}
.model-section {{ margin-bottom: 20px; border: 1px solid #333; border-radius: 6px; overflow: hidden; }}
.model-header {{
    background: #16213e; padding: 8px 12px; font-weight: bold; font-size: 0.9em;
    border-bottom: 1px solid #333;
}}
.model-header .tag {{
    display: inline-block; background: #e94560; color: white;
    padding: 2px 8px; border-radius: 3px; font-size: 0.8em; margin-left: 8px;
}}
.page-nav {{ display: flex; gap: 4px; }}
.page-nav button {{
    min-width: 36px; padding: 6px 8px; font-size: 0.85em;
}}
.page-nav button.active {{ background: #53d769; color: #000; }}
.hidden {{ display: none; }}
.stats {{ font-size: 0.75em; color: #888; margin-top: 4px; }}
</style>
</head>
<body>
<h1>Grothendieck OCR Pilot — Visual Comparison</h1>

<div class="controls">
    <div>
        <label>Page:</label>
        <div class="page-nav" id="page-nav">
"""

    for p in all_pages:
        active = "active" if p == all_pages[0] else ""
        html += f'            <button class="{active}" onclick="showPage({p})">{p}</button>\n'

    html += f"""
        </div>
    </div>
    <div>
        <label>Experiment:</label>
        <select id="exp-select" onchange="updateView()">
"""
    for exp_id in experiments:
        html += f'            <option value="{exp_id}">{exp_id}) {exp_names[exp_id]}</option>\n'

    html += """
        </select>
    </div>
</div>

<div class="comparison">
    <div class="panel panel-image" id="image-panel"></div>
    <div class="panel panel-text" id="text-panel"></div>
</div>

<script>
"""

    # Embed all data as JS
    # Images (base64)
    html += "const IMAGES = {\n"
    for p in all_pages:
        img_path = IMAGES_DIR / f"page_{p:04d}.png"
        if img_path.exists():
            b64 = image_to_base64(img_path)
            html += f'  {p}: "data:image/png;base64,{b64}",\n'
    html += "};\n\n"

    # Strip images
    html += "const STRIP_IMAGES = {\n"
    for p in all_pages:
        html += f"  {p}: [\n"
        for s in range(1, 4):
            strip_path = BASE_DIR / "strips" / f"page_{p:04d}_strip_{s}.png"
            if strip_path.exists():
                b64 = image_to_base64(strip_path)
                html += f'    "data:image/png;base64,{b64}",\n'
        html += "  ],\n"
    html += "};\n\n"

    # Transcriptions
    html += "const TRANSCRIPTIONS = {\n"
    for model, run_data in runs.items():
        html += f'  "{escape_html(model)}": {{\n'
        for exp_id in experiments:
            exp_data = run_data.get("experiments", {}).get(exp_id, {})
            html += f'    "{exp_id}": {{\n'
            for p in all_pages:
                p_str = str(p)
                if p_str in exp_data:
                    text = get_transcription_text(exp_data[p_str])
                    chars = len(text)
                    # Escape for JS string
                    text_escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                    html += f'      {p}: {{text: `{text_escaped}`, chars: {chars}}},\n'
            html += "    },\n"
        html += "  },\n"
    html += "};\n\n"

    html += f"const MODELS = {json.dumps(models)};\n"
    html += f"const PAGES = {json.dumps(all_pages)};\n"

    html += """
let currentPage = PAGES[0];
let currentExp = "A";

function showPage(page) {
    currentPage = page;
    document.querySelectorAll('.page-nav button').forEach(b => {
        b.classList.toggle('active', parseInt(b.textContent) === page);
    });
    updateView();
}

function updateView() {
    currentExp = document.getElementById('exp-select').value;
    const isStrips = (currentExp === "C" || currentExp === "D");

    // Image panel
    const imgPanel = document.getElementById('image-panel');
    if (isStrips && STRIP_IMAGES[currentPage]) {
        imgPanel.innerHTML = '<p style="padding:8px;font-size:0.8em;color:#888;">Strips (3 per page):</p>' +
            STRIP_IMAGES[currentPage].map((src, i) =>
                `<div style="margin:4px 0;border:1px solid #444;"><img src="${src}" style="width:100%;"></div>`
            ).join('');
    } else {
        imgPanel.innerHTML = IMAGES[currentPage]
            ? `<img src="${IMAGES[currentPage]}">`
            : '<p>No image</p>';
    }

    // Text panel
    const textPanel = document.getElementById('text-panel');
    let html = '';
    for (const model of MODELS) {
        const data = TRANSCRIPTIONS[model]?.[currentExp]?.[currentPage];
        const text = data ? data.text : '(no data)';
        const chars = data ? data.chars : 0;
        const shortName = model.includes('flash-lite') ? 'Flash-Lite' : 'Pro';
        const tag = model.includes('flash-lite') ? '💨 fast' : '🧠 quality';
        html += `
            <div class="model-section">
                <div class="model-header">
                    ${shortName} <span class="tag">${tag}</span>
                    <span class="stats">${chars} chars</span>
                </div>
                <pre>${escapeHtml(text)}</pre>
            </div>`;
    }
    textPanel.innerHTML = html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initial render
updateView();
</script>
</body>
</html>"""

    return html


def main():
    print("Loading results...")
    runs = load_results()
    print(f"Found {len(runs)} model runs: {list(runs.keys())}")

    print("Building HTML viewer...")
    html = build_html(runs)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = OUTPUT_HTML.stat().st_size / 1024 / 1024
    print(f"Viewer saved: {OUTPUT_HTML} ({size_mb:.1f} MB)")
    print(f"Open in browser: file:///{OUTPUT_HTML}")


if __name__ == "__main__":
    main()
