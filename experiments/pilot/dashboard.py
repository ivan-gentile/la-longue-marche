"""
Generate a comprehensive dashboard for pilot results.

Usage:
    python dashboard.py
    # Then open pilot_dashboard.html in browser
"""

import base64
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"
STRIPS_DIR = BASE_DIR / "strips"
RESULTS_DIR = BASE_DIR / "results"
REFERENCE_DIR = BASE_DIR / "reference"
REF_IMAGES_DIR = REFERENCE_DIR / "images"
OUTPUT_HTML = BASE_DIR / "pilot_dashboard.html"


def img_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def load_all_data():
    """Load all results, evaluations (v2), reference text."""
    runs = {}
    for run_dir in sorted(RESULTS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        results_file = run_dir / "all_results.json"
        if results_file.exists():
            with open(results_file, encoding="utf-8") as f:
                data = json.load(f)
            model = data.get("model", run_dir.name)
            runs[model] = {"results": data, "dir": str(run_dir)}

    # Load v2 evaluation (aligned, multi-metric)
    eval_v2 = {}
    eval_v2_path = BASE_DIR / "evaluation_v2.json"
    if eval_v2_path.exists():
        with open(eval_v2_path, encoding="utf-8") as f:
            eval_v2 = json.load(f)

    # Load reference text: fitz extraction (fallback) + VLM extraction (preferred)
    ref_fitz = {}
    ref_path = REFERENCE_DIR / "g103d_full_text.json"
    if ref_path.exists():
        with open(ref_path, encoding="utf-8") as f:
            ref_fitz = json.load(f)

    ref_vlm = {}  # page -> {"raw": ..., "latex": ...}
    vlm_path = REFERENCE_DIR / "g103d_vlm_text.json"
    if vlm_path.exists():
        with open(vlm_path, encoding="utf-8") as f:
            ref_vlm = json.load(f)

    # Merge: VLM raw text overrides fitz where available
    ref = dict(ref_fitz)
    ref_source = {}  # track which source each page uses
    for pkey, entry in ref_vlm.items():
        raw = entry.get("raw", "")
        if raw and len(raw) > 200:
            ref[pkey] = raw
            ref_source[pkey] = "vlm"
        elif entry.get("latex", "") and len(entry["latex"]) > 200:
            ref[pkey] = entry["latex"]
            ref_source[pkey] = "vlm-latex"

    return runs, eval_v2, ref, ref_vlm, ref_source


def get_text(result):
    if isinstance(result, dict) and "merged" in result:
        return result["merged"]
    if isinstance(result, dict) and "transcription" in result:
        return result.get("transcription", "")
    return ""


def build_dashboard(runs, eval_v2, ref, ref_vlm, ref_source):
    models = list(runs.keys())
    experiments = ["A", "B", "C", "D"]
    exp_names = {
        "A": "Full page · no context",
        "B": "Full page · with context",
        "C": "Strips · no context",
        "D": "Strips · with context",
    }

    all_pages = set()
    for m in runs.values():
        all_pages.update(m["results"].get("pages", []))
    all_pages = sorted(all_pages)

    # Pre-compute thumbnail images (smaller for dashboard)
    # We'll use the full images but let CSS handle sizing

    # Build JS data
    js_images = "{\n"
    for p in all_pages:
        img_path = IMAGES_DIR / f"page_{p:04d}.png"
        if img_path.exists():
            js_images += f'  {p}: "data:image/png;base64,{img_to_b64(img_path)}",\n'
    js_images += "}"

    js_strips = "{\n"
    for p in all_pages:
        js_strips += f"  {p}: [\n"
        for s in range(1, 4):
            sp = STRIPS_DIR / f"page_{p:04d}_strip_{s}.png"
            if sp.exists():
                js_strips += f'    "data:image/png;base64,{img_to_b64(sp)}",\n'
        js_strips += "  ],\n"
    js_strips += "}"

    js_transcriptions = "{\n"
    for model, entry in runs.items():
        short = "flash" if "flash" in model else "pro"
        js_transcriptions += f'  "{short}": {{\n'
        for exp_id in experiments:
            exp_data = entry["results"].get("experiments", {}).get(exp_id, {})
            js_transcriptions += f'    "{exp_id}": {{\n'
            for p in all_pages:
                ps = str(p)
                if ps in exp_data:
                    text = get_text(exp_data[ps])
                    chars = len(text)
                    unclear = text.lower().count("[unclear")
                    margin = text.lower().count("[margin")
                    diagram = text.lower().count("[diagram")
                    has_latex = 1 if "$" in text else 0
                    usage = exp_data[ps].get("usage", {})
                    prompt_tok = usage.get("prompt_tokens", 0) or 0
                    output_tok = usage.get("output_tokens", 0) or 0
                    text_esc = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                    js_transcriptions += (
                        f'      {p}: {{text:`{text_esc}`, chars:{chars}, unclear:{unclear}, '
                        f'margin:{margin}, diagram:{diagram}, latex:{has_latex}, '
                        f'prompt_tok:{prompt_tok}, output_tok:{output_tok}}},\n'
                    )
            js_transcriptions += "    },\n"
        js_transcriptions += "  },\n"
    js_transcriptions += "}"

    # Evaluation data (v2 - aligned, multi-metric)
    js_eval = "{\n"
    for model, eval_data in eval_v2.items():
        short = "flash" if "flash" in model else "pro"
        js_eval += f'  "{short}": {{\n'
        for exp_id, exp_eval in eval_data.get("experiments", {}).items():
            summary = exp_eval.get("summary", {})
            js_eval += f'    "{exp_id}": {{\n'
            js_eval += f'      summary: {json.dumps(summary)},\n'
            js_eval += f'      pages: {{\n'
            for pk, pv in exp_eval.get("pages", {}).items():
                ref_match = pv.get("reference_match", {})
                quality = pv.get("quality", {})
                combined = ref_match.get("combined_score", 0)
                seq = ref_match.get("seq_score", 0)
                word = ref_match.get("word_score", 0)
                fmt_ratio = quality.get("formatting_ratio", 0)
                content_words = quality.get("content_words", 0)
                has_ref = pv.get("has_reference", False)
                js_eval += (f'        {pk}: {{combined:{combined}, seq:{seq}, word:{word}, '
                            f'fmt:{fmt_ratio}, words:{content_words}, aligned:{str(has_ref).lower()}}},\n')
            js_eval += "      }\n"
            js_eval += "    },\n"
        js_eval += "  },\n"
    js_eval += "}"

    # Reference text — embed wider range for viewer comparison
    # Uses VLM-extracted text where available, fitz as fallback
    ref_pages_to_embed = set()
    for rp_int in list(range(1, 15)) + list(range(28, 45)) + list(range(55, 70)):
        ref_pages_to_embed.add(rp_int)

    js_ref = "{\n"
    for rp, rt in ref.items():
        rp_int = int(rp)
        if rp_int in ref_pages_to_embed:
            text_esc = rt.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            js_ref += f'  {rp}: `{text_esc}`,\n'
    js_ref += "}"

    # VLM LaTeX extractions (separate from raw — for side-by-side in viewer)
    js_ref_latex = "{\n"
    for rp, entry in ref_vlm.items():
        rp_int = int(rp)
        if rp_int in ref_pages_to_embed:
            latex = entry.get("latex", "")
            if latex and len(latex) > 200:
                text_esc = latex.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                js_ref_latex += f'  {rp}: `{text_esc}`,\n'
    js_ref_latex += "}"

    # Source tracking: which pages use VLM vs fitz
    js_ref_source = "{\n"
    for rp in sorted(ref_pages_to_embed):
        rp_str = str(rp)
        source = ref_source.get(rp_str, "fitz")
        js_ref_source += f'  {rp}: "{source}",\n'
    js_ref_source += "}"

    # Page alignment mapping: benchmark page → best G103d reference pages
    # From evaluate_v2.py content-based alignment
    page_alignment = {
        1: {"ref_pages": [], "desc": "Cover page"},
        2: {"ref_pages": [], "desc": "Table of contents (1)"},
        3: {"ref_pages": [4, 5], "desc": "TOC (2) / pre-§1"},
        4: {"ref_pages": [5, 6], "desc": "Transition to §1"},
        5: {"ref_pages": [6, 7, 8], "desc": "§1 Topos multigaloisiens"},
        50: {"ref_pages": [30, 31, 32, 33, 34], "desc": "§7 dense math (weak alignment)"},
        51: {"ref_pages": [34, 35, 36], "desc": "§7 systems of isomorphisms"},
        52: {"ref_pages": [35, 36, 37], "desc": "§7 late"},
        53: {"ref_pages": [36, 37], "desc": "§7 end"},
        54: {"ref_pages": [38, 39, 40], "desc": "§8 Réflexion taxonomique"},
    }
    js_alignment = json.dumps(page_alignment)

    # Reference page images (G103d rendered at 150 DPI)
    js_ref_images = "{\n"
    if REF_IMAGES_DIR.exists():
        for img_path in sorted(REF_IMAGES_DIR.glob("g103d_page_*.png")):
            # Extract page number from filename
            pnum = int(img_path.stem.split("_")[-1])
            b64 = img_to_b64(img_path)
            js_ref_images += f'  {pnum}: "data:image/png;base64,{b64}",\n'
    js_ref_images += "}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Grothendieck OCR Pilot Dashboard</title>
<style>
:root {{
  --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
  --border: #30363d; --text: #c9d1d9; --text2: #8b949e;
  --accent: #58a6ff; --green: #3fb950; --red: #f85149;
  --orange: #d29922; --purple: #bc8cff;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); }}

/* --- Header --- */
header {{
  background: var(--bg2); border-bottom: 1px solid var(--border);
  padding: 16px 24px; display: flex; justify-content: space-between; align-items: center;
}}
header h1 {{ font-size: 1.2em; }}
header h1 span {{ color: var(--accent); }}
header .meta {{ font-size: 0.8em; color: var(--text2); }}

/* --- Tabs --- */
.tabs {{
  display: flex; background: var(--bg2); border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 100;
}}
.tab {{
  padding: 10px 20px; cursor: pointer; font-size: 0.85em; font-weight: 600;
  border-bottom: 2px solid transparent; color: var(--text2); transition: all 0.2s;
}}
.tab:hover {{ color: var(--text); }}
.tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}

/* --- Panels --- */
.panel {{ display: none; padding: 20px 24px; }}
.panel.active {{ display: block; }}

/* --- Cards --- */
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin: 16px 0; }}
.card {{
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px;
  padding: 16px; transition: border-color 0.2s;
}}
.card:hover {{ border-color: var(--accent); }}
.card h3 {{ font-size: 0.85em; color: var(--text2); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
.card .big {{ font-size: 2em; font-weight: 700; }}
.card .sub {{ font-size: 0.8em; color: var(--text2); margin-top: 4px; }}
.green {{ color: var(--green); }}
.red {{ color: var(--red); }}
.orange {{ color: var(--orange); }}
.blue {{ color: var(--accent); }}
.purple {{ color: var(--purple); }}

/* --- Bar chart --- */
.bar-chart {{ margin: 16px 0; }}
.bar-row {{ display: flex; align-items: center; margin: 6px 0; }}
.bar-label {{ width: 200px; font-size: 0.8em; color: var(--text2); text-align: right; padding-right: 12px; }}
.bar-track {{ flex: 1; height: 24px; background: var(--bg3); border-radius: 4px; position: relative; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.5s ease; display: flex; align-items: center; padding-left: 8px; font-size: 0.75em; font-weight: 600; }}
.bar-fill.flash {{ background: var(--accent); }}
.bar-fill.pro {{ background: var(--purple); }}

/* --- Table --- */
table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.85em; }}
th {{ text-align: left; padding: 8px 12px; background: var(--bg3); border-bottom: 1px solid var(--border); color: var(--text2); font-size: 0.8em; text-transform: uppercase; }}
td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); }}
tr:hover td {{ background: var(--bg2); }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

/* --- Viewer --- */
.viewer-controls {{
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  background: var(--bg2); padding: 12px 16px; border-radius: 8px; margin-bottom: 16px;
}}
.viewer-controls label {{ font-size: 0.8em; color: var(--text2); font-weight: 600; }}
.pill-group {{ display: flex; gap: 2px; }}
.pill {{
  padding: 6px 14px; border-radius: 20px; font-size: 0.8em; cursor: pointer;
  background: var(--bg3); border: 1px solid var(--border); color: var(--text2); transition: all 0.2s;
}}
.pill:hover {{ border-color: var(--accent); color: var(--text); }}
.pill.active {{ background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }}
select {{
  padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--bg3); color: var(--text); font-size: 0.85em;
}}

.viewer-layout {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }}
@media (max-width: 1400px) {{ .viewer-layout {{ grid-template-columns: 1fr 1fr; }} }}
.viewer-image {{ background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
.viewer-image img {{ width: 100%; display: block; }}
.viewer-image .strip-img {{ border-bottom: 2px solid var(--orange); }}
.viewer-image .strip-img:last-child {{ border-bottom: none; }}
.viewer-text {{ display: flex; flex-direction: column; gap: 12px; }}
.model-block {{
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
  flex: 1; display: flex; flex-direction: column;
}}
.model-block-header {{
  padding: 8px 12px; background: var(--bg3); border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center; font-size: 0.85em;
}}
.model-block-header .badge {{
  padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: 600;
}}
.badge-flash {{ background: var(--accent); color: #000; }}
.badge-pro {{ background: var(--purple); color: #000; }}
.model-block pre {{
  flex: 1; overflow: auto; padding: 12px; font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.78em; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word;
  max-height: 600px;
}}

/* --- Findings --- */
.finding {{ background: var(--bg2); border-left: 3px solid var(--accent); padding: 12px 16px; margin: 8px 0; border-radius: 0 6px 6px 0; }}
.finding h4 {{ font-size: 0.9em; margin-bottom: 4px; }}
.finding p {{ font-size: 0.82em; color: var(--text2); line-height: 1.5; }}

/* --- Heatmap --- */
.heatmap {{ display: grid; gap: 2px; margin: 16px 0; }}
.heatmap-cell {{
  padding: 6px 8px; text-align: center; font-size: 0.75em; border-radius: 3px;
  font-variant-numeric: tabular-nums;
}}
.heatmap-header {{ font-weight: 600; color: var(--text2); background: var(--bg3); }}
</style>
</head>
<body>

<header>
  <h1><span>Grothendieck</span> OCR Pilot Dashboard</h1>
  <div class="meta">10 pages · 4 experiments · 2 models · 160 API calls · 2026-03-05</div>
</header>

<div class="tabs">
  <div class="tab active" onclick="showTab('overview')">Overview</div>
  <div class="tab" onclick="showTab('comparison')">Model Comparison</div>
  <div class="tab" onclick="showTab('heatmap')">Heatmap</div>
  <div class="tab" onclick="showTab('viewer')">Page Viewer</div>
  <div class="tab" onclick="showTab('findings')">Key Findings</div>
</div>

<div class="panel active" id="panel-overview"></div>
<div class="panel" id="panel-comparison"></div>
<div class="panel" id="panel-heatmap"></div>
<div class="panel" id="panel-viewer"></div>
<div class="panel" id="panel-findings"></div>

<script>
const IMAGES = {js_images};
const STRIPS = {js_strips};
const T = {js_transcriptions};
const EVAL = {js_eval};
const REF = {js_ref};
const REF_LATEX = {js_ref_latex};
const REF_SOURCE = {js_ref_source};
const PAGES = {json.dumps(all_pages)};
const EXPS = ["A","B","C","D"];
const EXP_NAMES = {json.dumps(exp_names)};
const PAGE_ALIGN = {js_alignment};
const REF_IMAGES = {js_ref_images};

function escHtml(s) {{ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }}

// --- Tab switching ---
function showTab(id) {{
  document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', t.textContent.toLowerCase().includes(id.slice(0,4))));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'panel-'+id));
  if (id === 'overview') renderOverview();
  if (id === 'comparison') renderComparison();
  if (id === 'heatmap') renderHeatmap();
  if (id === 'viewer') renderViewer();
  if (id === 'findings') renderFindings();
}}

// --- Overview ---
function renderOverview() {{
  const panel = document.getElementById('panel-overview');
  let h = '<h2 style="margin-bottom:16px;">Experiment Summary (v2 — aligned evaluation)</h2>';
  h += '<div class="card-grid">';

  // Summary cards from v2 eval
  const flashA = EVAL.flash?.A?.summary?.avg_combined_score || 0;
  const proB = EVAL.pro?.B?.summary?.avg_combined_score || 0;
  const proFmt = EVAL.pro?.B?.summary?.avg_formatting_ratio || 0;
  const flashFmt = EVAL.flash?.A?.summary?.avg_formatting_ratio || 0;
  h += card('Flash-Lite Best', (flashA*100).toFixed(1)+'%', 'Exp A · combined score (seq+word)', 'blue');
  h += card('Pro Best', (proB*100).toFixed(1)+'%', 'Exp B · combined score (seq+word)', 'purple');
  h += card('Pro Formatting Ratio', (proFmt*100).toFixed(0)+'%', 'Exp B · layout commands / total commands', 'red');
  h += card('Flash Formatting Ratio', (flashFmt*100).toFixed(0)+'%', 'Exp A · layout commands / total commands', 'green');

  // Timing
  h += card('Flash-Lite Speed', '8.1 min', '80 calls · ~6s/call', 'green');
  h += card('Pro Speed', '~48 min', '80 calls · ~36s/call', 'orange');
  h += card('Est. Cost Flash', '~$0.15', '80 calls · Flash-Lite', 'green');
  h += card('Est. Cost Pro', '~$2.50', '80 calls · Pro', 'orange');
  h += '</div>';

  // Per-experiment summary table
  h += '<h2 style="margin:24px 0 12px;">Results by Experiment (aligned pages only)</h2>';
  h += '<table><thead><tr><th>Experiment</th><th>Model</th><th class="num">Combined</th><th class="num">SeqMatch</th><th class="num">WordOverlap</th><th class="num">[unclear]</th><th class="num">Fmt Ratio</th><th class="num">Content Words</th></tr></thead><tbody>';
  for (const exp of EXPS) {{
    for (const [model, label] of [['flash','Flash-Lite'],['pro','Pro']]) {{
      const s = EVAL[model]?.[exp]?.summary;
      if (!s) continue;
      h += `<tr><td>${{exp}}) ${{EXP_NAMES[exp]}}</td><td>${{label}}</td>`;
      h += `<td class="num">${{((s.avg_combined_score||0)*100).toFixed(1)}}%</td>`;
      h += `<td class="num">${{((s.avg_seq_score||0)*100).toFixed(1)}}%</td>`;
      h += `<td class="num">${{((s.avg_word_score||0)*100).toFixed(1)}}%</td>`;
      h += `<td class="num">${{s.total_unclear||0}}</td>`;
      h += `<td class="num">${{((s.avg_formatting_ratio||0)*100).toFixed(0)}}%</td>`;
      h += `<td class="num">${{s.avg_content_words||0}}</td></tr>`;
    }}
  }}
  h += '</tbody></table>';
  panel.innerHTML = h;
}}
function card(title, value, sub, color) {{
  return `<div class="card"><h3>${{title}}</h3><div class="big ${{color}}">${{value}}</div><div class="sub">${{sub}}</div></div>`;
}}

// --- Comparison ---
function renderComparison() {{
  const panel = document.getElementById('panel-comparison');
  let h = '<h2 style="margin-bottom:16px;">Model Comparison by Experiment (v2 aligned)</h2>';
  h += '<p style="font-size:0.8em;color:var(--text2);margin-bottom:16px;">Combined score = 50% sequence similarity + 50% word overlap. Only aligned pages shown (pages with known reference mapping). Gray = unaligned page.</p>';

  for (const exp of EXPS) {{
    h += `<h3 style="margin:20px 0 8px;">${{exp}}) ${{EXP_NAMES[exp]}}</h3>`;
    h += '<div class="bar-chart">';
    for (const p of PAGES) {{
      const fd = EVAL.flash?.[exp]?.pages?.[p];
      const pd = EVAL.pro?.[exp]?.pages?.[p];
      const fs = fd?.combined || 0;
      const ps = pd?.combined || 0;
      const aligned = fd?.aligned || pd?.aligned || false;
      const maxVal = Math.max(fs, ps, 0.01);
      const scale = 80 / Math.max(maxVal, 0.4);
      const opacity = aligned ? '1' : '0.3';
      const suffix = aligned ? '' : ' (unaligned)';
      h += `<div class="bar-row" style="opacity:${{opacity}}">
        <div class="bar-label">Page ${{p}}${{suffix}}</div>
        <div class="bar-track">
          <div class="bar-fill flash" style="width:${{fs*scale}}%">${{(fs*100).toFixed(0)}}%</div>
        </div>
        <div style="width:8px"></div>
        <div class="bar-track">
          <div class="bar-fill pro" style="width:${{ps*scale}}%">${{(ps*100).toFixed(0)}}%</div>
        </div>
      </div>`;
    }}
    h += '</div>';
    h += '<div style="font-size:0.75em;color:var(--text2);margin-bottom:16px;"><span style="color:var(--accent);">■</span> Flash-Lite &nbsp; <span style="color:var(--purple);">■</span> Pro</div>';
  }}
  panel.innerHTML = h;
}}

// --- Heatmap ---
function renderHeatmap() {{
  const panel = document.getElementById('panel-heatmap');
  let h = '<h2 style="margin-bottom:16px;">Similarity Heatmap (v2 combined score)</h2>';

  for (const [model, label] of [['flash','Flash-Lite'],['pro','Pro']]) {{
    h += `<h3 style="margin:20px 0 8px;">${{label}}</h3>`;
    h += `<div class="heatmap" style="grid-template-columns: 80px repeat(${{EXPS.length}}, 1fr) 80px;">`;
    h += '<div class="heatmap-cell heatmap-header">Page</div>';
    for (const exp of EXPS) h += `<div class="heatmap-cell heatmap-header">Exp ${{exp}}</div>`;
    h += '<div class="heatmap-cell heatmap-header">Fmt %</div>';

    for (const p of PAGES) {{
      const pd = EVAL[model]?.A?.pages?.[p];
      const aligned = pd?.aligned || false;
      h += `<div class="heatmap-cell heatmap-header">${{p}}${{aligned?'':'*'}}</div>`;
      for (const exp of EXPS) {{
        const score = EVAL[model]?.[exp]?.pages?.[p]?.combined || 0;
        const pct = score * 100;
        let bg;
        if (pct < 5) bg = `rgba(248,81,73,${{0.3 + pct/5*0.3}})`;
        else if (pct < 15) bg = `rgba(210,153,34,${{0.3 + (pct-5)/10*0.4}})`;
        else if (pct < 30) bg = `rgba(63,185,80,${{0.3 + (pct-15)/15*0.4}})`;
        else bg = `rgba(63,185,80,0.8)`;
        h += `<div class="heatmap-cell" style="background:${{bg}}">${{pct.toFixed(1)}}%</div>`;
      }}
      // Formatting ratio (avg across experiments)
      let fmtSum=0, fmtN=0;
      for (const exp of EXPS) {{
        const f = EVAL[model]?.[exp]?.pages?.[p]?.fmt;
        if (f !== undefined) {{ fmtSum += f; fmtN++; }}
      }}
      const avgFmt = fmtN > 0 ? fmtSum/fmtN*100 : 0;
      const fmtBg = avgFmt > 30 ? 'rgba(248,81,73,0.5)' : avgFmt > 15 ? 'rgba(210,153,34,0.4)' : 'rgba(63,185,80,0.3)';
      h += `<div class="heatmap-cell" style="background:${{fmtBg}}">${{avgFmt.toFixed(0)}}%</div>`;
    }}
    h += '</div>';
    h += '<div style="font-size:0.75em;color:var(--text2);margin-top:4px;">* = no aligned reference page available. Fmt % = formatting commands / total LaTeX commands (high = over-formatting).</div>';
  }}

  // Per-page quality metrics
  h += '<h2 style="margin:24px 0 12px;">Quality Metrics (Exp A - baseline)</h2>';
  h += '<table><thead><tr><th>Page</th><th>Model</th><th class="num">Chars</th><th class="num">[unclear]</th><th class="num">[margin]</th><th class="num">[diagram]</th><th class="num">Prompt tok</th><th class="num">Output tok</th></tr></thead><tbody>';
  for (const p of PAGES) {{
    for (const [model,label] of [['flash','Flash-Lite'],['pro','Pro']]) {{
      const d = T[model]?.A?.[p];
      if (!d) continue;
      h += `<tr><td>${{p}}</td><td>${{label}}</td>`;
      h += `<td class="num">${{d.chars}}</td><td class="num">${{d.unclear}}</td>`;
      h += `<td class="num">${{d.margin}}</td><td class="num">${{d.diagram}}</td>`;
      h += `<td class="num">${{d.prompt_tok}}</td><td class="num">${{d.output_tok}}</td></tr>`;
    }}
  }}
  h += '</tbody></table>';
  panel.innerHTML = h;
}}

// --- Viewer ---
let vPage = PAGES[0], vExp = 'A', vRefView = 'raw';
function renderViewer() {{
  const panel = document.getElementById('panel-viewer');
  let h = '<div class="viewer-controls">';
  h += '<label>Page</label><div class="pill-group" id="v-pages">';
  for (const p of PAGES) h += `<div class="pill ${{p===vPage?'active':''}}" onclick="setVPage(${{p}})">${{p}}</div>`;
  h += '</div>';
  h += '<label>Experiment</label><div class="pill-group" id="v-exps">';
  for (const e of EXPS) h += `<div class="pill ${{e===vExp?'active':''}}" onclick="setVExp('${{e}}')">${{e[0]}}) ${{EXP_NAMES[e].split('·')[0]}}</div>`;
  h += '</div>';

  // Show alignment info
  const align = PAGE_ALIGN[vPage];
  if (align) {{
    const refLabel = align.ref_pages.length > 0
      ? `G103d pages ${{align.ref_pages.join(', ')}} — ${{align.desc}}`
      : `${{align.desc}} — no reference alignment`;
    h += `<div style="font-size:0.75em;color:var(--text2);margin-left:12px;">Reference: ${{refLabel}}</div>`;
  }}
  h += '</div>';

  const isStrips = vExp==='C'||vExp==='D';
  h += '<div class="viewer-layout">';

  // Column 1: Image
  h += '<div class="viewer-image">';
  h += '<div style="padding:6px 10px;background:var(--bg3);font-size:0.8em;font-weight:600;color:var(--text2);">Handwritten (140-2 page ' + vPage + ')</div>';
  if (isStrips && STRIPS[vPage]) {{
    for (const src of STRIPS[vPage]) h += `<img class="strip-img" src="${{src}}">`;
  }} else if (IMAGES[vPage]) {{
    h += `<img src="${{IMAGES[vPage]}}">`;
  }}
  h += '</div>';

  // Column 2: Model transcriptions
  h += '<div class="viewer-text">';
  for (const [model,label,badge] of [['flash','Flash-Lite','badge-flash'],['pro','Pro','badge-pro']]) {{
    const d = T[model]?.[vExp]?.[vPage];
    const text = d ? d.text : '(no data)';
    const ev = EVAL[model]?.[vExp]?.pages?.[vPage];
    const score = ev ? (ev.combined*100).toFixed(1)+'%' : '—';
    const fmt = ev ? (ev.fmt*100).toFixed(0)+'%' : '—';
    const stats = d ? `${{d.chars}}ch · ${{d.unclear}}unc · score:${{score}} · fmt:${{fmt}}` : '';
    h += `<div class="model-block">
      <div class="model-block-header">
        <span>${{label}} <span class="badge ${{badge}}">${{vExp}}</span></span>
        <span style="font-size:0.7em;color:var(--text2)">${{stats}}</span>
      </div>
      <pre>${{escHtml(text)}}</pre>
    </div>`;
  }}
  h += '</div>';

  // Column 3: Mateo's reference (G103d) — PDF image + VLM/fitz text + VLM LaTeX
  h += '<div class="viewer-text" style="gap:8px;">';
  const refPages = align?.ref_pages || [];
  if (refPages.length > 0) {{
    // Reference view toggle
    h += `<div style="display:flex;gap:4px;margin-bottom:4px;">
      <div class="pill ${{vRefView==='image'?'active':''}}" onclick="setRefView('image')" style="font-size:0.7em;padding:4px 10px;">PDF</div>
      <div class="pill ${{vRefView==='raw'?'active':''}}" onclick="setRefView('raw')" style="font-size:0.7em;padding:4px 10px;">Text</div>
      <div class="pill ${{vRefView==='latex'?'active':''}}" onclick="setRefView('latex')" style="font-size:0.7em;padding:4px 10px;">LaTeX</div>
      <div class="pill ${{vRefView==='all'?'active':''}}" onclick="setRefView('all')" style="font-size:0.7em;padding:4px 10px;">All</div>
    </div>`;

    for (const rp of refPages) {{
      const source = REF_SOURCE[rp] || 'fitz';
      const sourceLabel = source === 'vlm' ? 'VLM' : source === 'vlm-latex' ? 'VLM (from LaTeX)' : 'fitz';
      const sourceColor = source.startsWith('vlm') ? 'var(--green)' : 'var(--orange)';

      // PDF image
      if ((vRefView === 'image' || vRefView === 'all') && REF_IMAGES[rp]) {{
        h += `<div class="viewer-image" style="border-color:var(--green);">
          <div style="padding:6px 10px;background:#1a2e1a;font-size:0.8em;font-weight:600;color:var(--green);">G103d p.${{rp}} — PDF</div>
          <img src="${{REF_IMAGES[rp]}}" style="width:100%;">
        </div>`;
      }}

      // Raw/readable text (VLM or fitz)
      const refText = REF[rp];
      if ((vRefView === 'raw' || vRefView === 'all') && refText) {{
        h += `<div class="model-block" style="border-color:${{sourceColor}};">
          <div class="model-block-header" style="background:#1a2e1a;">
            <span style="color:var(--green);">G103d p.${{rp}} — text</span>
            <span style="font-size:0.65em;padding:2px 6px;border-radius:8px;background:${{sourceColor}};color:#000;font-weight:600;margin-left:6px;">${{sourceLabel}}</span>
            <span style="font-size:0.7em;color:var(--text2)">${{refText.length}}ch</span>
          </div>
          <pre style="color:#a8d8a8;">${{escHtml(refText)}}</pre>
        </div>`;
      }}

      // VLM LaTeX extraction
      const refLatex = REF_LATEX[rp];
      if ((vRefView === 'latex' || vRefView === 'all') && refLatex) {{
        h += `<div class="model-block" style="border-color:var(--accent);">
          <div class="model-block-header" style="background:#1a2a3a;">
            <span style="color:var(--accent);">G103d p.${{rp}} — LaTeX</span>
            <span style="font-size:0.65em;padding:2px 6px;border-radius:8px;background:var(--accent);color:#000;font-weight:600;margin-left:6px;">VLM</span>
            <span style="font-size:0.7em;color:var(--text2)">${{refLatex.length}}ch</span>
          </div>
          <pre style="color:#a8c8e8;">${{escHtml(refLatex)}}</pre>
        </div>`;
      }}

      // Nothing available
      if (!REF_IMAGES[rp] && !refText && !refLatex) {{
        h += `<div class="model-block" style="border-color:var(--border);">
          <div class="model-block-header"><span>G103d p.${{rp}}</span></div>
          <pre style="color:var(--text2);">(not embedded)</pre>
        </div>`;
      }}
    }}
  }} else {{
    h += `<div class="model-block" style="border-color:var(--border);">
      <div class="model-block-header">
        <span style="color:var(--text2);">Mateo Reference (G103d)</span>
      </div>
      <pre style="color:var(--text2);">No aligned reference pages for this benchmark page.
${{align?.desc || ''}}</pre>
    </div>`;
  }}
  h += '</div>';

  h += '</div>';
  panel.innerHTML = h;
}}
function setVPage(p) {{ vPage=p; renderViewer(); }}
function setVExp(e) {{ vExp=e; renderViewer(); }}
function setRefView(v) {{ vRefView=v; renderViewer(); }}

// --- Findings ---
function renderFindings() {{
  const panel = document.getElementById('panel-findings');
  panel.innerHTML = `
    <h2 style="margin-bottom:16px;">Key Findings</h2>

    <div class="finding" style="border-color:var(--green)">
      <h4>1. Full pages beat strips</h4>
      <p>Strips produced longer output but lower similarity to reference. They lose page-level context
      (marginal notes reference distant content) and the overlap/dedup adds noise. Full-page images give
      the model enough resolution for Grothendieck's handwriting at 300 DPI.</p>
    </div>

    <div class="finding" style="border-color:var(--purple)">
      <h4>2. Context helps Pro, neutral for Flash-Lite</h4>
      <p>Pro with context (Exp B): +1.9% similarity AND fewer [unclear] markers (23 vs 39).
      Flash-Lite with context: essentially neutral (-0.2%). Pro's deeper reasoning actually uses
      the previous page to resolve ambiguous symbols.</p>
    </div>

    <div class="finding" style="border-color:var(--accent)">
      <h4>3. Pro catches marginal notes that Flash-Lite misses</h4>
      <p>Grothendieck wrote extensive margin annotations. Pro consistently identifies and marks these
      as [MARGIN: ...], while Flash-Lite often ignores them or transcribes them inline without marking.
      This is significant for mathematical manuscripts where margins carry important commentary.</p>
    </div>

    <div class="finding" style="border-color:var(--red)">
      <h4>4. Pro over-formats: ~40% of LaTeX commands are layout noise</h4>
      <p>Pro (especially Exp B) tries to replicate the exact visual structure of the document using
      \\\\hfill, \\\\vspace, \\\\noindent, \\\\begin{{itemize}} etc. These layout commands are unnecessary —
      the model should reason about content, not reproduce page layout. Pro Exp B has a 39.5% formatting
      ratio vs Flash-Lite's 5%. This wastes tokens and adds noise without improving transcription accuracy.
      The prompt should be updated to explicitly discourage layout formatting.</p>
    </div>

    <div class="finding" style="border-color:var(--orange)">
      <h4>5. Flash-Lite is 6x faster, 15x cheaper</h4>
      <p>For core mathematical transcription (propositions, equations, section headers), both models
      perform comparably. Pro's advantages are in edge cases: marginal notes, uncertain readings.
      But Pro's formatting overhead partially negates its reasoning advantage.</p>
    </div>

    <h2 style="margin:24px 0 12px;">Recommended Production Pipeline</h2>

    <div class="card-grid">
      <div class="card">
        <h3>Step 1: Bulk Transcription</h3>
        <div class="big green">Flash-Lite</div>
        <div class="sub">Full page + no context · 976 pages · ~$0.50 · ~1.5h</div>
      </div>
      <div class="card">
        <h3>Step 2: Quality Pass</h3>
        <div class="big purple">Pro + context</div>
        <div class="sub">Re-run pages with &gt;3 [unclear] markers · ~$5 · ~2h</div>
      </div>
      <div class="card">
        <h3>Step 3: Expert Review</h3>
        <div class="big orange">Mateo + Expert</div>
        <div class="sub">Human verification of flagged sections</div>
      </div>
      <div class="card">
        <h3>Total Estimated Cost</h3>
        <div class="big green">~$6</div>
        <div class="sub">vs ~$30,000 for pure manual transcription</div>
      </div>
    </div>

    <h2 style="margin:24px 0 12px;">Critical Next Action</h2>
    <div class="finding" style="border-color:var(--red)">
      <h4>Ask Mateo for the .tex source of G103d.pdf</h4>
      <p>The biggest limitation of this pilot is evaluation quality. We're comparing OCR output against
      extracted text from a compiled PDF, with no page alignment. Having the original LaTeX would enable
      proper character-level accuracy measurement and page-aligned comparison. One email, massive ROI.</p>
    </div>
  `;
}}

// Initial render
renderOverview();
</script>
</body>
</html>"""

    return html


def main():
    print("Loading data...")
    runs, eval_v2, ref, ref_vlm, ref_source = load_all_data()
    print(f"Models: {list(runs.keys())}")
    print(f"Eval v2 models: {list(eval_v2.keys())}")
    print(f"Reference pages: {len(ref)} ({sum(1 for v in ref_source.values() if v.startswith('vlm'))} VLM-upgraded)")

    print("Building dashboard...")
    html = build_dashboard(runs, eval_v2, ref, ref_vlm, ref_source)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = OUTPUT_HTML.stat().st_size / 1024 / 1024
    print(f"Dashboard saved: {OUTPUT_HTML} ({size_mb:.1f} MB)")
    print(f"\nOpen in browser:")
    print(f"  file:///D:/documents-Orso/code/la_longe_marche/experiments/pilot/pilot_dashboard.html")


if __name__ == "__main__":
    main()
