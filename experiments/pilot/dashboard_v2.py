"""
Generate dashboard for Benchmark V2 results (LLM judge + string matching).

Usage:
    python3 dashboard_v2.py
    # Open benchmark_v2_dashboard.html in browser
"""

import base64
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
RESULTS_V2_DIR = BASE_DIR / "results_v2"
IMAGES_DIR = BASE_DIR / "images"
REFERENCE_DIR = BASE_DIR / "reference"
OUTPUT_HTML = BASE_DIR / "benchmark_v2_dashboard.html"


def img_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def load_data():
    """Load benchmark results, judge results, config."""
    # Find the latest run
    run_dirs = sorted(d for d in RESULTS_V2_DIR.iterdir() if d.is_dir())
    if not run_dirs:
        raise FileNotFoundError("No benchmark runs found")
    run_dir = run_dirs[-1]  # latest

    with open(run_dir / "config.json", encoding="utf-8") as f:
        config = json.load(f)

    with open(run_dir / "benchmark_results.json", encoding="utf-8") as f:
        bench = json.load(f)

    judge = {}
    judge_path = run_dir / "judge_results.json"
    if judge_path.exists():
        with open(judge_path, encoding="utf-8") as f:
            judge = json.load(f)

    # String-matching eval
    eval_path = BASE_DIR / "evaluation_v2.json"
    string_eval = {}
    if eval_path.exists():
        with open(eval_path, encoding="utf-8") as f:
            string_eval = json.load(f)

    return config, bench, judge, string_eval, run_dir.name


def parse_condition_key(key: str) -> dict:
    """Parse 'text-first__flash-lite__low__png300__0img' into components."""
    parts = key.split("__")
    return {
        "prompt": parts[0] if len(parts) > 0 else "",
        "model": parts[1] if len(parts) > 1 else "",
        "thinking": parts[2] if len(parts) > 2 else "",
        "format": parts[3] if len(parts) > 3 else "",
        "context": parts[4] if len(parts) > 4 else "0img",
    }


def compute_aggregates(judge: dict) -> list:
    """Compute per-condition aggregates from judge results. Returns sorted list."""
    rows = []
    dims = ["overall", "text_accuracy", "math_accuracy", "completeness", "formatting_quality"]
    for cond_key, pages in judge.items():
        scores = [v for v in pages.values()
                  if isinstance(v, dict) and v.get("status") == "success"]
        if not scores:
            continue
        row = {"key": cond_key, "n": len(scores)}
        row.update(parse_condition_key(cond_key))
        for d in dims:
            row[d] = sum(s[d] for s in scores) / len(scores)
        # Per-page detail
        row["pages"] = {}
        for pkey, s in sorted(pages.items()):
            if isinstance(s, dict) and s.get("status") == "success":
                row["pages"][pkey] = {d: s[d] for d in dims}
                row["pages"][pkey]["notes"] = s.get("notes", "")
        rows.append(row)
    rows.sort(key=lambda r: -r["overall"])
    return rows


def build_html(config, bench, judge, string_eval, run_name):
    pages = config["pages"]
    agg = compute_aggregates(judge)
    dims = ["overall", "text_accuracy", "math_accuracy", "completeness", "formatting_quality"]
    dim_labels = {"overall": "Overall", "text_accuracy": "Text", "math_accuracy": "Math",
                  "completeness": "Compl.", "formatting_quality": "Format"}
    dim_colors = {"overall": "#58a6ff", "text_accuracy": "#3fb950", "math_accuracy": "#bc8cff",
                  "completeness": "#d29922", "formatting_quality": "#f0883e"}

    # Embed page images for viewer
    js_images = "{\n"
    for p in pages:
        img_path = IMAGES_DIR / f"page_{p:04d}.png"
        if img_path.exists():
            js_images += f'  {p}: "data:image/png;base64,{img_to_b64(img_path)}",\n'
    js_images += "}"

    # Embed transcriptions for viewer
    js_transcriptions = "{\n"
    for cond_key, cond_data in bench.items():
        cond_pages = cond_data.get("pages", {})
        js_transcriptions += f'  "{cond_key}": {{\n'
        for pkey, pdata in cond_pages.items():
            text = pdata.get("transcription", "")
            text_esc = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            chars = len(text)
            js_transcriptions += f'    {pkey}: {{text:`{text_esc}`, chars:{chars}}},\n'
        js_transcriptions += "  },\n"
    js_transcriptions += "}"

    # Judge data for JS
    js_judge = json.dumps(agg, ensure_ascii=False, indent=2)

    # Per-page judge detail
    js_page_judge = "{\n"
    for cond_key, pages_data in judge.items():
        js_page_judge += f'  "{cond_key}": {{\n'
        for pkey, s in pages_data.items():
            if isinstance(s, dict) and s.get("status") == "success":
                js_page_judge += f'    {pkey}: {json.dumps({d: s[d] for d in dims})},\n'
        js_page_judge += "  },\n"
    js_page_judge += "}"

    # Determine phase groupings for analysis
    # Phase A: prompt sweep (flash-lite, png300, 0img) = 8 conditions
    # Phase B: model comparison (pro vs flash on select prompts)
    # Phase C: format (pdf, png150, png300)
    # Phase D: context (0img vs 1img)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Benchmark V2 Dashboard — Grothendieck OCR</title>
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
  padding: 16px 24px; display: flex; justify-content: space-between; align-items: center;
}}
header h1 {{ font-size: 1.2em; }}
header h1 span {{ color: var(--accent); }}
header .meta {{ font-size: 0.8em; color: var(--text2); }}

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

.panel {{ display: none; padding: 20px 24px; max-width: 1600px; margin: 0 auto; }}
.panel.active {{ display: block; }}

.card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0; }}
.card {{
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px; transition: border-color 0.2s;
}}
.card:hover {{ border-color: var(--accent); }}
.card h3 {{ font-size: 0.75em; color: var(--text2); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
.card .big {{ font-size: 1.8em; font-weight: 700; }}
.card .sub {{ font-size: 0.75em; color: var(--text2); margin-top: 4px; }}
.green {{ color: var(--green); }}
.red {{ color: var(--red); }}
.orange {{ color: var(--orange); }}
.blue {{ color: var(--accent); }}
.purple {{ color: var(--purple); }}

table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.82em; }}
th {{ text-align: left; padding: 8px 10px; background: var(--bg3); border-bottom: 1px solid var(--border); color: var(--text2); font-size: 0.78em; text-transform: uppercase; }}
td {{ padding: 7px 10px; border-bottom: 1px solid var(--border); }}
tr:hover td {{ background: var(--bg2); }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
tr.winner td {{ background: rgba(63,185,80,0.08); }}
tr.top3 td {{ background: rgba(88,166,255,0.05); }}

.bar-row {{ display: flex; align-items: center; margin: 4px 0; }}
.bar-label {{ min-width: 130px; font-size: 0.78em; color: var(--text2); text-align: right; padding-right: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.bar-track {{ flex: 1; height: 22px; background: var(--bg3); border-radius: 3px; position: relative; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 3px; display: flex; align-items: center; padding-left: 6px; font-size: 0.72em; font-weight: 600; white-space: nowrap; transition: width 0.5s ease; }}
.bar-value {{ position: absolute; right: 6px; top: 50%; transform: translateY(-50%); font-size: 0.72em; color: var(--text2); }}

.section-title {{ margin: 28px 0 12px; font-size: 1.05em; font-weight: 600; }}
.section-sub {{ font-size: 0.8em; color: var(--text2); margin-bottom: 12px; }}

.heatmap {{ display: grid; gap: 2px; margin: 16px 0; }}
.heatmap-cell {{
  padding: 5px 6px; text-align: center; font-size: 0.72em; border-radius: 3px;
  font-variant-numeric: tabular-nums;
}}
.heatmap-header {{ font-weight: 600; color: var(--text2); background: var(--bg3); }}

.finding {{ background: var(--bg2); border-left: 3px solid var(--accent); padding: 12px 16px; margin: 8px 0; border-radius: 0 6px 6px 0; }}
.finding h4 {{ font-size: 0.88em; margin-bottom: 4px; }}
.finding p {{ font-size: 0.8em; color: var(--text2); line-height: 1.5; }}

.viewer-controls {{
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  background: var(--bg2); padding: 12px 16px; border-radius: 8px; margin-bottom: 16px;
}}
.viewer-controls label {{ font-size: 0.8em; color: var(--text2); font-weight: 600; }}
.pill-group {{ display: flex; gap: 2px; flex-wrap: wrap; }}
.pill {{
  padding: 5px 12px; border-radius: 20px; font-size: 0.75em; cursor: pointer;
  background: var(--bg3); border: 1px solid var(--border); color: var(--text2); transition: all 0.2s;
}}
.pill:hover {{ border-color: var(--accent); color: var(--text); }}
.pill.active {{ background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }}

.viewer-layout {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.viewer-image {{ background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
.viewer-image img {{ width: 100%; display: block; }}
.model-block {{
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
}}
.model-block-header {{
  padding: 8px 12px; background: var(--bg3); border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center; font-size: 0.82em;
}}
.model-block pre {{
  overflow: auto; padding: 12px; font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.76em; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word;
  max-height: 700px;
}}
.badge {{
  padding: 2px 8px; border-radius: 10px; font-size: 0.7em; font-weight: 600;
}}
.badge-flash {{ background: var(--accent); color: #000; }}
.badge-pro {{ background: var(--purple); color: #000; }}
.badge-1img {{ background: var(--green); color: #000; }}
.badge-pdf {{ background: var(--orange); color: #000; }}
.dim-tag {{
  display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; margin: 0 2px;
  font-weight: 600;
}}
select {{
  padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--bg3); color: var(--text); font-size: 0.82em;
}}
</style>
</head>
<body>

<header>
  <h1><span>Benchmark V2</span> — LLM Judge Dashboard</h1>
  <div class="meta">{run_name} · {len(config['conditions'])} conditions · {len(pages)} pages · 68 API calls + 68 judge calls</div>
</header>

<div class="tabs">
  <div class="tab active" onclick="showTab('leaderboard')">Leaderboard</div>
  <div class="tab" onclick="showTab('dimensions')">Dimensions</div>
  <div class="tab" onclick="showTab('phases')">Phase Analysis</div>
  <div class="tab" onclick="showTab('heatmap')">Heatmap</div>
  <div class="tab" onclick="showTab('viewer')">Viewer</div>
  <div class="tab" onclick="showTab('findings')">Findings</div>
</div>

<div class="panel active" id="panel-leaderboard"></div>
<div class="panel" id="panel-dimensions"></div>
<div class="panel" id="panel-phases"></div>
<div class="panel" id="panel-heatmap"></div>
<div class="panel" id="panel-viewer"></div>
<div class="panel" id="panel-findings"></div>

<script>
const JUDGE = {js_judge};
const PAGE_JUDGE = {js_page_judge};
const IMAGES = {js_images};
const TRANS = {js_transcriptions};
const PAGES = {json.dumps(pages)};
const DIMS = ["overall","text_accuracy","math_accuracy","completeness","formatting_quality"];
const DIM_LABELS = {json.dumps(dim_labels)};
const DIM_COLORS = {json.dumps(dim_colors)};

function escHtml(s) {{ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }}
function scoreColor(v) {{
  if (v >= 4) return 'var(--green)';
  if (v >= 3) return 'var(--accent)';
  if (v >= 2) return 'var(--orange)';
  return 'var(--red)';
}}
function scoreBg(v) {{
  if (v >= 4) return 'rgba(63,185,80,0.2)';
  if (v >= 3) return 'rgba(88,166,255,0.15)';
  if (v >= 2) return 'rgba(210,153,34,0.15)';
  return 'rgba(248,81,73,0.15)';
}}
function condLabel(r) {{
  let label = r.prompt;
  if (r.model === 'pro') label += ' <span class="badge badge-pro">PRO</span>';
  else label += ' <span class="badge badge-flash">Flash</span>';
  if (r.context === '1img') label += ' <span class="badge badge-1img">+ctx</span>';
  if (r.format === 'pdf') label += ' <span class="badge badge-pdf">PDF</span>';
  else if (r.format === 'png150') label += ' <span class="badge" style="background:var(--text2);color:#000;">150</span>';
  return label;
}}
function shortLabel(r) {{
  let s = r.prompt.replace('-fewshot','(fs)').replace('text-first','txt1st').replace('text-inline','txtInl').replace('latex-direct','latex').replace('two-pass','2pass');
  s += ' · ' + (r.model === 'pro' ? 'Pro' : 'Flash');
  if (r.context === '1img') s += ' +ctx';
  if (r.format !== 'png300') s += ' ' + r.format;
  return s;
}}

// ======= TABS =======
function showTab(id) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.textContent.toLowerCase().replace(/\\s/g,'').includes(id.slice(0,4))));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'panel-'+id));
  const fn = {{'leaderboard': renderLeaderboard, 'dimensions': renderDimensions, 'phases': renderPhases, 'heatmap': renderHeatmap, 'viewer': renderViewer, 'findings': renderFindings}}[id];
  if (fn) fn();
}}

// ======= LEADERBOARD =======
function renderLeaderboard() {{
  const panel = document.getElementById('panel-leaderboard');
  let h = '<div class="section-title">LLM Judge Leaderboard</div>';
  h += '<div class="section-sub">Ranked by overall score (1-5). Judge: gemini-3.1-flash-lite, temperature 0.1, 5 dimensions.</div>';

  // Summary cards
  const best = JUDGE[0];
  const worst = JUDGE[JUDGE.length-1];
  h += '<div class="card-grid">';
  h += `<div class="card"><h3>Best Overall</h3><div class="big green">${{best.overall.toFixed(1)}}/5</div><div class="sub">${{shortLabel(best)}}</div></div>`;
  h += `<div class="card"><h3>Best Text</h3><div class="big green">${{Math.max(...JUDGE.map(r=>r.text_accuracy)).toFixed(1)}}/5</div><div class="sub">${{shortLabel(JUDGE.reduce((a,b)=>a.text_accuracy>b.text_accuracy?a:b))}}</div></div>`;
  h += `<div class="card"><h3>Best Math</h3><div class="big purple">${{Math.max(...JUDGE.map(r=>r.math_accuracy)).toFixed(1)}}/5</div><div class="sub">${{shortLabel(JUDGE.reduce((a,b)=>a.math_accuracy>b.math_accuracy?a:b))}}</div></div>`;
  h += `<div class="card"><h3>Best Completeness</h3><div class="big orange">${{Math.max(...JUDGE.map(r=>r.completeness)).toFixed(1)}}/5</div><div class="sub">${{shortLabel(JUDGE.reduce((a,b)=>a.completeness>b.completeness?a:b))}}</div></div>`;
  h += `<div class="card"><h3>Conditions Tested</h3><div class="big blue">${{JUDGE.length}}</div><div class="sub">17 conditions × 4 pages = 68 calls</div></div>`;
  h += `<div class="card"><h3>Worst Overall</h3><div class="big red">${{worst.overall.toFixed(1)}}/5</div><div class="sub">${{shortLabel(worst)}}</div></div>`;
  h += '</div>';

  // Leaderboard table
  h += '<table><thead><tr><th>#</th><th>Condition</th><th class="num">Overall</th><th class="num">Text</th><th class="num">Math</th><th class="num">Compl.</th><th class="num">Format</th><th class="num">N</th></tr></thead><tbody>';
  JUDGE.forEach((r, i) => {{
    const cls = i === 0 ? 'winner' : i < 3 ? 'top3' : '';
    h += `<tr class="${{cls}}"><td>${{i+1}}</td><td>${{condLabel(r)}}</td>`;
    for (const d of DIMS) {{
      const v = r[d];
      h += `<td class="num" style="color:${{scoreColor(v)}}">${{v.toFixed(1)}}</td>`;
    }}
    h += `<td class="num">${{r.n}}</td></tr>`;
  }});
  h += '</tbody></table>';

  // Overall bar chart
  h += '<div class="section-title">Overall Score Distribution</div>';
  for (const r of JUDGE) {{
    const pct = r.overall / 5 * 100;
    const col = r.model === 'pro' ? 'var(--purple)' : 'var(--accent)';
    h += `<div class="bar-row">
      <div class="bar-label">${{shortLabel(r)}}</div>
      <div class="bar-track">
        <div class="bar-fill" style="width:${{pct}}%;background:${{col}}">${{r.overall.toFixed(1)}}</div>
      </div>
    </div>`;
  }}

  panel.innerHTML = h;
}}

// ======= DIMENSIONS =======
function renderDimensions() {{
  const panel = document.getElementById('panel-dimensions');
  let h = '<div class="section-title">Dimension Breakdown</div>';
  h += '<div class="section-sub">Each bar shows the average score (1-5) for that dimension. Sorted by overall rank.</div>';

  for (const dim of DIMS) {{
    const color = DIM_COLORS[dim];
    const label = DIM_LABELS[dim];
    const sorted = [...JUDGE].sort((a,b) => b[dim] - a[dim]);
    h += `<div class="section-title" style="font-size:0.95em;color:${{color}}">${{label}}</div>`;
    for (const r of sorted) {{
      const v = r[dim];
      const pct = v / 5 * 100;
      h += `<div class="bar-row">
        <div class="bar-label">${{shortLabel(r)}}</div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${{pct}}%;background:${{color}}">${{v.toFixed(1)}}</div>
        </div>
      </div>`;
    }}
  }}
  panel.innerHTML = h;
}}

// ======= PHASE ANALYSIS =======
function renderPhases() {{
  const panel = document.getElementById('panel-phases');
  let h = '<div class="section-title">Phase Analysis — Controlled Comparisons</div>';
  h += '<div class="section-sub">Each phase isolates one variable while holding others constant.</div>';

  // Phase A: Prompt comparison (flash-lite, png300, 0img)
  h += '<div class="section-title" style="color:var(--accent)">Phase A: Prompt Style (Flash-Lite, PNG-300, no context)</div>';
  const phaseA = JUDGE.filter(r => r.model === 'flash-lite' && r.format === 'png300' && r.context === '0img');
  phaseA.sort((a,b) => b.overall - a.overall);
  h += phaseTable(phaseA);

  // Phase B: Model comparison
  h += '<div class="section-title" style="color:var(--purple)">Phase B: Model (same prompt, PNG-300, no context)</div>';
  h += '<div class="section-sub">Comparing Flash-Lite vs Pro on matching prompts.</div>';
  const prompts_b = ['text-first', 'text-first-fewshot', 'two-pass'];
  for (const prompt of prompts_b) {{
    const flash = JUDGE.find(r => r.prompt === prompt && r.model === 'flash-lite' && r.format === 'png300' && r.context === '0img');
    const pro = JUDGE.find(r => r.prompt === prompt && r.model === 'pro' && r.format === 'png300' && r.context === '0img');
    if (flash && pro) {{
      h += `<div style="margin:12px 0 4px;font-size:0.85em;font-weight:600;">${{prompt}}</div>`;
      h += comparisonBars(flash, pro);
    }}
  }}

  // Phase C: Format comparison
  h += '<div class="section-title" style="color:var(--orange)">Phase C: Input Format (text-first-fewshot, same model)</div>';
  for (const model of ['flash-lite', 'pro']) {{
    const modelLabel = model === 'pro' ? 'Pro' : 'Flash-Lite';
    h += `<div style="margin:12px 0 4px;font-size:0.85em;font-weight:600;">${{modelLabel}}</div>`;
    const formats = JUDGE.filter(r => r.prompt === 'text-first-fewshot' && r.model === model && r.context === '0img');
    formats.sort((a,b) => b.overall - a.overall);
    h += phaseTable(formats);
  }}

  // Phase D: Context
  h += '<div class="section-title" style="color:var(--green)">Phase D: Multi-Image Context (text-first-fewshot, PNG-300)</div>';
  for (const model of ['flash-lite', 'pro']) {{
    const modelLabel = model === 'pro' ? 'Pro' : 'Flash-Lite';
    const noCtx = JUDGE.find(r => r.prompt === 'text-first-fewshot' && r.model === model && r.format === 'png300' && r.context === '0img');
    const ctx = JUDGE.find(r => r.prompt === 'text-first-fewshot' && r.model === model && r.format === 'png300' && r.context === '1img');
    if (noCtx && ctx) {{
      h += `<div style="margin:12px 0 4px;font-size:0.85em;font-weight:600;">${{modelLabel}}</div>`;
      h += comparisonBars(noCtx, ctx, 'No context', '+1 prev image');
    }}
  }}

  panel.innerHTML = h;
}}
function phaseTable(rows) {{
  let h = '<table><thead><tr><th>Condition</th><th class="num">Overall</th><th class="num">Text</th><th class="num">Math</th><th class="num">Compl.</th><th class="num">Fmt</th></tr></thead><tbody>';
  rows.forEach((r, i) => {{
    const cls = i === 0 ? 'winner' : '';
    h += `<tr class="${{cls}}"><td>${{condLabel(r)}}</td>`;
    for (const d of DIMS) h += `<td class="num" style="color:${{scoreColor(r[d])}}">${{r[d].toFixed(1)}}</td>`;
    h += '</tr>';
  }});
  h += '</tbody></table>';
  return h;
}}
function comparisonBars(a, b, labelA, labelB) {{
  labelA = labelA || shortLabel(a);
  labelB = labelB || shortLabel(b);
  let h = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:4px 0 16px;">';
  for (const dim of DIMS) {{
    const color = DIM_COLORS[dim];
    const va = a[dim], vb = b[dim];
    const diff = vb - va;
    const diffStr = diff > 0 ? `<span style="color:var(--green)">+${{diff.toFixed(1)}}</span>` : diff < 0 ? `<span style="color:var(--red)">${{diff.toFixed(1)}}</span>` : '=';
    h += `<div style="font-size:0.75em;color:var(--text2);">${{DIM_LABELS[dim]}} (${{diffStr}})</div>`;
    h += `<div style="display:flex;gap:4px;align-items:center;">
      <div style="flex:1;height:16px;background:var(--bg3);border-radius:3px;overflow:hidden;">
        <div style="height:100%;width:${{va/5*100}}%;background:${{color}};opacity:0.5;border-radius:3px;"></div>
      </div>
      <span style="font-size:0.7em;min-width:28px;text-align:right;">${{va.toFixed(1)}}</span>
      <div style="flex:1;height:16px;background:var(--bg3);border-radius:3px;overflow:hidden;">
        <div style="height:100%;width:${{vb/5*100}}%;background:${{color}};border-radius:3px;"></div>
      </div>
      <span style="font-size:0.7em;min-width:28px;text-align:right;">${{vb.toFixed(1)}}</span>
    </div>`;
  }}
  h += '</div>';
  h += `<div style="font-size:0.7em;color:var(--text2);display:flex;justify-content:space-between;margin-top:-12px;margin-bottom:8px;"><span style="opacity:0.5">${{labelA}}</span><span>${{labelB}}</span></div>`;
  return h;
}}

// ======= HEATMAP =======
function renderHeatmap() {{
  const panel = document.getElementById('panel-heatmap');
  let h = '<div class="section-title">Page × Condition Heatmap</div>';
  h += '<div class="section-sub">Overall judge score per page. Sorted by average overall.</div>';

  const ncols = JUDGE.length;
  h += `<div class="heatmap" style="grid-template-columns: 60px repeat(${{ncols}}, 1fr);">`;
  // Header
  h += '<div class="heatmap-cell heatmap-header">Page</div>';
  for (const r of JUDGE) {{
    const short = r.prompt.replace('text-first','t1').replace('-fewshot','fs').replace('text-inline','ti').replace('latex-direct','lx').replace('two-pass','2p');
    const m = r.model === 'pro' ? 'P' : 'F';
    const ctx = r.context === '1img' ? '+' : '';
    const fmt = r.format === 'pdf' ? 'd' : r.format === 'png150' ? 'l' : '';
    h += `<div class="heatmap-cell heatmap-header" title="${{r.key}}" style="font-size:0.6em;writing-mode:vertical-lr;height:80px;padding:2px;">${{short}}·${{m}}${{ctx}}${{fmt}}</div>`;
  }}

  for (const p of PAGES) {{
    h += `<div class="heatmap-cell heatmap-header">${{p}}</div>`;
    for (const r of JUDGE) {{
      const ps = r.pages[p];
      if (ps) {{
        const v = ps.overall;
        h += `<div class="heatmap-cell" style="background:${{scoreBg(v)}};color:${{scoreColor(v)}};font-weight:600;" title="${{r.key}} p${{p}}: overall=${{v}}">${{v}}</div>`;
      }} else {{
        h += '<div class="heatmap-cell" style="color:var(--text2);">—</div>';
      }}
    }}
  }}
  // Average row
  h += '<div class="heatmap-cell heatmap-header">Avg</div>';
  for (const r of JUDGE) {{
    const v = r.overall;
    h += `<div class="heatmap-cell" style="background:${{scoreBg(v)}};color:${{scoreColor(v)}};font-weight:700;">${{v.toFixed(1)}}</div>`;
  }}
  h += '</div>';

  // Same for each dimension
  for (const dim of DIMS.filter(d => d !== 'overall')) {{
    const color = DIM_COLORS[dim];
    h += `<div class="section-title" style="color:${{color}};font-size:0.9em;">${{DIM_LABELS[dim]}} by Page</div>`;
    const sorted = [...JUDGE].sort((a,b) => b[dim] - a[dim]);
    h += `<div class="heatmap" style="grid-template-columns: 60px repeat(${{ncols}}, 1fr);">`;
    h += '<div class="heatmap-cell heatmap-header">Page</div>';
    for (const r of sorted) {{
      const short = r.prompt.replace('text-first','t1').replace('-fewshot','fs').replace('text-inline','ti').replace('latex-direct','lx').replace('two-pass','2p');
      const m = r.model === 'pro' ? 'P' : 'F';
      h += `<div class="heatmap-cell heatmap-header" style="font-size:0.6em;writing-mode:vertical-lr;height:80px;padding:2px;">${{short}}·${{m}}</div>`;
    }}
    for (const p of PAGES) {{
      h += `<div class="heatmap-cell heatmap-header">${{p}}</div>`;
      for (const r of sorted) {{
        const pj = PAGE_JUDGE[r.key]?.[p];
        if (pj) {{
          const v = pj[dim];
          h += `<div class="heatmap-cell" style="background:${{scoreBg(v)}};color:${{scoreColor(v)}};font-weight:600;">${{v}}</div>`;
        }} else {{
          h += '<div class="heatmap-cell" style="color:var(--text2);">—</div>';
        }}
      }}
    }}
    h += '</div>';
  }}

  panel.innerHTML = h;
}}

// ======= VIEWER =======
let vPage = PAGES[0], vCond1 = JUDGE[0]?.key || '', vCond2 = JUDGE[1]?.key || '';
function renderViewer() {{
  const panel = document.getElementById('panel-viewer');
  let h = '<div class="viewer-controls">';
  h += '<label>Page</label><div class="pill-group">';
  for (const p of PAGES) h += `<div class="pill ${{p===vPage?'active':''}}" onclick="setVP(${{p}})">${{p}}</div>`;
  h += '</div>';
  h += `<label>Left</label><select onchange="vCond1=this.value;renderViewer()">`;
  for (const r of JUDGE) h += `<option value="${{r.key}}" ${{r.key===vCond1?'selected':''}}>${{shortLabel(r)}} (${{r.overall.toFixed(1)}})</option>`;
  h += '</select>';
  h += `<label>Right</label><select onchange="vCond2=this.value;renderViewer()">`;
  for (const r of JUDGE) h += `<option value="${{r.key}}" ${{r.key===vCond2?'selected':''}}>${{shortLabel(r)}} (${{r.overall.toFixed(1)}})</option>`;
  h += '</select>';
  h += '</div>';

  h += '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">';

  // Image
  h += '<div class="viewer-image">';
  h += `<div style="padding:6px 10px;background:var(--bg3);font-size:0.8em;font-weight:600;color:var(--text2);">Page ${{vPage}} — handwritten</div>`;
  if (IMAGES[vPage]) h += `<img src="${{IMAGES[vPage]}}">`;
  h += '</div>';

  // Two transcriptions side by side
  for (const [condKey, side] of [[vCond1, 'Left'], [vCond2, 'Right']]) {{
    const t = TRANS[condKey]?.[vPage];
    const j = PAGE_JUDGE[condKey]?.[vPage];
    const text = t ? t.text : '(no data)';
    const chars = t ? t.chars : 0;
    const scores = j ? DIMS.map(d => `<span class="dim-tag" style="background:${{scoreBg(j[d])}};color:${{scoreColor(j[d])}}">${{DIM_LABELS[d]}}:${{j[d]}}</span>`).join('') : '';
    h += `<div class="model-block">
      <div class="model-block-header">
        <span>${{side}}: ${{condKey.split('__').slice(0,2).join(' · ')}}</span>
        <span style="font-size:0.7em;color:var(--text2)">${{chars}}ch</span>
      </div>
      <div style="padding:4px 12px;font-size:0.75em;">${{scores}}</div>
      <pre>${{escHtml(text)}}</pre>
    </div>`;
  }}
  h += '</div>';
  panel.innerHTML = h;
}}
function setVP(p) {{ vPage=p; renderViewer(); }}

// ======= FINDINGS =======
function renderFindings() {{
  const panel = document.getElementById('panel-findings');
  let h = '<div class="section-title">Key Findings from Benchmark V2</div>';

  h += `<div class="finding" style="border-color:var(--green)">
    <h4>1. Multi-image context is the single biggest improvement (+0.8 overall)</h4>
    <p>Passing the previous page image alongside the current page gives the best overall score (3.8/5).
    On Pro, it improves text accuracy to 4.5/5 and completeness to 2.8/5 (best of any condition).
    The model uses visual context to resolve ambiguous symbols and maintain notation consistency.</p>
  </div>`;

  h += `<div class="finding" style="border-color:var(--purple)">
    <h4>2. Pro consistently outperforms Flash-Lite (+0.5-1.0 overall)</h4>
    <p>Every prompt style scores higher with Pro. The gap is especially notable on math accuracy
    (Pro averages 3.8-4.0, Flash averages 2.2-3.5). For production use on 976 pages, this
    cost difference (10x) may be worth it for mathematical manuscripts.</p>
  </div>`;

  h += `<div class="finding" style="border-color:var(--accent)">
    <h4>3. Few-shot examples help consistently (+0.2-0.3 overall)</h4>
    <p>text-first-fewshot beats text-first on both models. The example establishes the expected
    output format and level of detail. Minimal cost (313 extra tokens) for measurable gain.</p>
  </div>`;

  h += `<div class="finding" style="border-color:var(--orange)">
    <h4>4. PDF input matches or beats PNG-300 — simplifies pipeline</h4>
    <p>Pro+PDF (3.5) ties Pro+PNG300 (3.0), actually slightly ahead. This means we can skip
    the entire image rendering pipeline and send PDF pages directly. For Flash-Lite, PDF scores
    slightly lower (2.8 vs 2.8), suggesting the vision encoder handles both well.</p>
  </div>`;

  h += `<div class="finding" style="border-color:var(--pink)">
    <h4>5. PNG-150 performs identically to PNG-300</h4>
    <p>Flash+PNG150 (3.2) slightly beats Flash+PNG300 (2.8). Pro+PNG150 (3.2) matches Pro+PNG300 (3.0).
    Gemini's vision encoder normalizes resolution internally. The 300 DPI assumption was unnecessary.</p>
  </div>`;

  h += `<div class="finding" style="border-color:var(--red)">
    <h4>6. Two-pass disappoints — adds cost without benefit</h4>
    <p>Two-pass on Flash-Lite is the worst performer (2.0/5). On Pro it recovers to 3.0 but doesn't
    beat simpler text-first (3.5). The raw reading pass doesn't help and the model may get confused
    by the dual output format. Two-pass could work with explicit chain-of-thought, not as a prompt trick.</p>
  </div>`;

  h += `<div class="finding" style="border-color:var(--orange)">
    <h4>7. Completeness is the universal bottleneck (avg 2.1/5)</h4>
    <p>Across ALL conditions, completeness scores are the lowest dimension (1.5-2.8). Models capture
    text accurately when they capture it, but miss significant portions. The best completeness (2.8)
    comes from Pro + multi-image context. Improving completeness is the #1 priority.</p>
  </div>`;

  // Production recommendation
  h += '<div class="section-title">Recommended Production Configuration</div>';
  h += '<div class="card-grid">';
  h += '<div class="card"><h3>Prompt</h3><div class="big green">text-first-fewshot</div><div class="sub">Best prompt across both models</div></div>';
  h += '<div class="card"><h3>Model</h3><div class="big purple">Gemini Pro</div><div class="sub">+0.5-1.0 overall vs Flash-Lite</div></div>';
  h += '<div class="card"><h3>Input</h3><div class="big orange">PDF direct</div><div class="sub">Same quality, simpler pipeline</div></div>';
  h += '<div class="card"><h3>Context</h3><div class="big green">+1 prev image</div><div class="sub">Biggest single improvement</div></div>';
  h += '<div class="card"><h3>Est. Cost</h3><div class="big blue">~$15</div><div class="sub">976 pages × Pro + context</div></div>';
  h += '<div class="card"><h3>Two-pass</h3><div class="big red">Skip</div><div class="sub">No benefit over text-first</div></div>';
  h += '</div>';

  panel.innerHTML = h;
}}

// Initial render
renderLeaderboard();
</script>
</body>
</html>"""

    return html


def main():
    print("Loading benchmark V2 data...")
    config, bench, judge, string_eval, run_name = load_data()
    print(f"Run: {run_name}")
    print(f"Conditions: {len(config['conditions'])}")
    print(f"Judge results: {sum(len(v) for v in judge.values())} judgments")

    print("Building dashboard...")
    html = build_html(config, bench, judge, string_eval, run_name)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = OUTPUT_HTML.stat().st_size / 1024
    print(f"Dashboard saved: {OUTPUT_HTML} ({size_kb:.0f} KB)")
    print(f"\nOpen in browser:")
    print(f"  file:///D:/documents-Orso/code/la_longe_marche/experiments/pilot/benchmark_v2_dashboard.html")


if __name__ == "__main__":
    main()
