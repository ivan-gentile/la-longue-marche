"""Gemini 3.1 Pro vs Claude Opus 4.7 benchmark.

Scope:
  - 5 ground-truth pages from 140-3 (pages 495-499), behind Section 49.1
    where Mateo's `49.1new.tex` gives us a real reference.
  - 7 blind pages sampled across 140-3 and 140-4: a mix of diagram-heavy,
    prose-dense, notation-heavy pages. For these we use Flash-Lite LLM
    judge + a human A/B viewer we'll send to Mateo.
  - Bonus: a single "whole-document" Gemini 3.1 Pro call over pages 495-504
    as one 10-page PDF, to see if full-document mode competes with
    page-by-page.

Reuses `prompts_v2.py` so the prompt and context mechanism are identical
across models (apples-to-apples).

Outputs:
  experiments/pilot/bench_opus_vs_gemini/
    results.json         — all raw transcriptions + tokens/cost/latency
    per_model_scores.json — `diagnose_49_1` categorized scores (ground truth slice)
    summary.md           — headline table
  experiments/pilot/benchmark_opus_vs_gemini.html — A/B viewer for Mateo
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: pip install google-genai python-dotenv pymupdf anthropic")
    sys.exit(1)

from anthropic import Anthropic
import fitz

from prompts_v2 import get_prompt
from diagnose_49_1 import categorize, score as score_profile

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RAW_PDF_DIR = REPO / "raw_pdf"
DEFAULT_OUT_DIR = HERE / "bench_opus_vs_gemini"
OUT_DIR = DEFAULT_OUT_DIR
OUT_DIR.mkdir(exist_ok=True)

GEMINI_MODEL_ID = "gemini-3.1-pro-preview"
GEMINI_THINKING = "medium"
GEMINI_PRICES = {"in": 2.00, "out": 12.00}  # USD per 1M tokens

CLAUDE_MODEL_ID = "claude-opus-4-7"
# Standard Anthropic Opus pricing at the time of writing (USD per 1M tokens)
CLAUDE_PRICES = {"in": 15.00, "out": 75.00}

DEFAULT_PROMPT_STYLE = "text-first-fewshot"
PROMPT_STYLE = DEFAULT_PROMPT_STYLE  # mutated by --prompt-style
MAX_OUTPUT_TOKENS = 16000

# Page selection
GROUND_TRUTH_PAGES = [
    ("140-3", 495),
    ("140-3", 496),
    ("140-3", 497),
    ("140-3", 498),
    ("140-3", 499),
]

# Blind A/B set: diagram-heavy, prose-dense, notation-heavy.
# Choices are informed by experiments/pilot/diagram_pages.json and the
# existing production transcriptions (for prose/notation density).
BLIND_PAGES = [
    ("140-3", 9),    # diagram-heavy, commutative diagram (12)
    ("140-3", 10),   # stacked-arrow diagram
    ("140-3", 146),  # category-theory prose with marginal notes
    ("140-3", 300),  # mid-volume prose/notation mix
    ("140-3", 600),  # later-volume dense notation
    ("140-4", 17),   # geometric/figure page
    ("140-4", 95),   # transition prose with margin commentary
]

# Whole-doc chunk: pages 495-504 of 140-3 (contains Section 49.1)
WHOLE_DOC_VOLUME = "140-3"
WHOLE_DOC_PAGES = list(range(495, 505))


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------


def page_pdf_bytes(doc: fitz.Document, page_idx_0: int) -> bytes:
    """Extract a single PDF page as its own PDF, 0-indexed."""
    out = fitz.open()
    out.insert_pdf(doc, from_page=page_idx_0, to_page=page_idx_0)
    data = out.tobytes()
    out.close()
    return data


def pages_pdf_bytes(doc: fitz.Document, first_0: int, last_0: int) -> bytes:
    """Extract a multi-page slice as a single PDF."""
    out = fitz.open()
    out.insert_pdf(doc, from_page=first_0, to_page=last_0)
    data = out.tobytes()
    out.close()
    return data


def open_volume(vol: str) -> fitz.Document:
    return fitz.open(str(RAW_PDF_DIR / f"{vol}.pdf"))


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------


def call_gemini(client, system_prompt: str, user_text: str,
                 curr_pdf_bytes: bytes, prev_pdf_bytes: bytes | None,
                 prev_label: str | None = None) -> dict:
    parts = []
    if prev_pdf_bytes is not None:
        parts.append(types.Part.from_bytes(data=prev_pdf_bytes, mime_type="application/pdf"))
        parts.append(types.Part.from_text(
            text=prev_label or "[Previous page shown above for context]"
        ))
    parts.append(types.Part.from_bytes(data=curr_pdf_bytes, mime_type="application/pdf"))
    parts.append(types.Part.from_text(text=user_text))

    t0 = time.monotonic()
    response = client.models.generate_content(
        model=GEMINI_MODEL_ID,
        contents=[types.Content(parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=1.0,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level=GEMINI_THINKING),
        ),
    )
    dt = time.monotonic() - t0

    text = ""
    if response.candidates:
        for p in response.candidates[0].content.parts:
            if getattr(p, "thought", False):
                continue
            if p.text:
                text += p.text

    um = getattr(response, "usage_metadata", None)
    tok_in = getattr(um, "prompt_token_count", 0) if um else 0
    tok_out = getattr(um, "candidates_token_count", 0) if um else 0
    cost = (tok_in * GEMINI_PRICES["in"] + tok_out * GEMINI_PRICES["out"]) / 1_000_000

    return {
        "model": GEMINI_MODEL_ID,
        "text": text.strip(),
        "tokens_in": tok_in,
        "tokens_out": tok_out,
        "cost_usd": round(cost, 4),
        "latency_s": round(dt, 2),
    }


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------


def _claude_doc(pdf_bytes: bytes) -> dict:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.b64encode(pdf_bytes).decode("ascii"),
        },
    }


def call_claude(client: Anthropic, system_prompt: str, user_text: str,
                  curr_pdf_bytes: bytes, prev_pdf_bytes: bytes | None,
                  prev_label: str | None = None) -> dict:
    content = []
    if prev_pdf_bytes is not None:
        content.append(_claude_doc(prev_pdf_bytes))
        content.append({"type": "text", "text": prev_label or "[Previous page shown above for context]"})
    content.append(_claude_doc(curr_pdf_bytes))
    content.append({"type": "text", "text": user_text})

    t0 = time.monotonic()
    msg = client.messages.create(
        model=CLAUDE_MODEL_ID,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )
    dt = time.monotonic() - t0

    text = ""
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            text += block.text
    tok_in = msg.usage.input_tokens
    tok_out = msg.usage.output_tokens
    cost = (tok_in * CLAUDE_PRICES["in"] + tok_out * CLAUDE_PRICES["out"]) / 1_000_000

    return {
        "model": CLAUDE_MODEL_ID,
        "text": text.strip(),
        "tokens_in": tok_in,
        "tokens_out": tok_out,
        "cost_usd": round(cost, 4),
        "latency_s": round(dt, 2),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


_PRODUCTION_CACHE: dict[str, dict] = {}


def _load_production(vol: str) -> dict:
    if vol not in _PRODUCTION_CACHE:
        path = HERE / "production" / vol / "transcriptions.json"
        _PRODUCTION_CACHE[vol] = json.loads(path.read_text(encoding="utf-8"))
    return _PRODUCTION_CACHE[vol]


def gemini_from_production(vol: str, page_1: int) -> dict:
    """Return the shipped Gemini output for this page (from production JSON).

    This is the actual transcription Mateo received, the one in the .tex
    we sent him. It is the honest Gemini side of the comparison.
    """
    d = _load_production(vol)
    entry = d.get(str(page_1), {})
    text = entry.get("transcription", "")
    usage = entry.get("usage", {}) or {}
    tok_in = usage.get("prompt_tokens") or 0
    tok_out = usage.get("output_tokens") or 0
    cost = (tok_in * GEMINI_PRICES["in"] + tok_out * GEMINI_PRICES["out"]) / 1_000_000
    return {
        "model": GEMINI_MODEL_ID + " (from production/transcriptions.json)",
        "text": text,
        "tokens_in": tok_in,
        "tokens_out": tok_out,
        "cost_usd": round(cost, 4),
        "latency_s": None,
        "source": "cached",
    }


def run_single_page(gem_client, claude_client, vol: str, page_1: int,
                    results: dict, gemini_source: str) -> None:
    """Run Claude on one page. Fetch Gemini either live or from cache."""
    key = f"{vol}_p{page_1}"
    print(f"\n  [{key}] ", end="", flush=True)

    doc = open_volume(vol)
    try:
        page_idx_0 = page_1 - 1
        curr_bytes = page_pdf_bytes(doc, page_idx_0)
        prev_bytes = page_pdf_bytes(doc, page_idx_0 - 1) if page_idx_0 > 0 else None
        prev_label = f"[Previous page {page_1 - 1} shown above for context]" if prev_bytes else None

        system_prompt, user_text = get_prompt(PROMPT_STYLE)

        # Gemini
        if gemini_source == "live":
            print("gemini(live)...", end="", flush=True)
            gem = call_gemini(gem_client, system_prompt, user_text, curr_bytes, prev_bytes, prev_label)
            print(f" {len(gem['text'])}ch ${gem['cost_usd']} / ", end="", flush=True)
        else:
            gem = gemini_from_production(vol, page_1)
            print(f"gemini(cached) {len(gem['text'])}ch / ", end="", flush=True)

        # Claude
        print("claude...", end="", flush=True)
        cla = call_claude(claude_client, system_prompt, user_text, curr_bytes, prev_bytes, prev_label)
        print(f" {len(cla['text'])}ch ${cla['cost_usd']}", flush=True)

        results[key] = {
            "volume": vol,
            "page": page_1,
            "gemini_pbp": gem,
            "claude_pbp": cla,
        }
    finally:
        doc.close()

    # persist incrementally
    (OUT_DIR / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run_whole_doc(gem_client, vol: str, pages_1: list[int], results: dict) -> None:
    first_0 = pages_1[0] - 1
    last_0 = pages_1[-1] - 1
    print(f"\n  [{vol}_p{pages_1[0]}-{pages_1[-1]} WHOLE] ", end="", flush=True)

    doc = open_volume(vol)
    try:
        chunk_bytes = pages_pdf_bytes(doc, first_0, last_0)
    finally:
        doc.close()

    system_prompt, _ = get_prompt(PROMPT_STYLE)
    user_text = (
        f"The document above contains pages {pages_1[0]} to {pages_1[-1]} "
        "of the manuscript, concatenated. Transcribe all pages in order. "
        "Insert `%% ===== Page N =====` markers between them so pages remain "
        "identifiable in the output."
    )

    parts = [
        types.Part.from_bytes(data=chunk_bytes, mime_type="application/pdf"),
        types.Part.from_text(text=user_text),
    ]

    t0 = time.monotonic()
    response = gem_client.models.generate_content(
        model=GEMINI_MODEL_ID,
        contents=[types.Content(parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=1.0,
            max_output_tokens=MAX_OUTPUT_TOKENS * 3,
            thinking_config=types.ThinkingConfig(thinking_level=GEMINI_THINKING),
        ),
    )
    dt = time.monotonic() - t0

    text = ""
    for p in response.candidates[0].content.parts:
        if getattr(p, "thought", False):
            continue
        if p.text:
            text += p.text
    um = getattr(response, "usage_metadata", None)
    tok_in = getattr(um, "prompt_token_count", 0) if um else 0
    tok_out = getattr(um, "candidates_token_count", 0) if um else 0
    cost = (tok_in * GEMINI_PRICES["in"] + tok_out * GEMINI_PRICES["out"]) / 1_000_000

    print(f" {len(text)}ch ${cost:.4f} in {dt:.1f}s", flush=True)

    results["__whole_doc__"] = {
        "volume": vol,
        "pages": pages_1,
        "model": GEMINI_MODEL_ID,
        "text": text.strip(),
        "tokens_in": tok_in,
        "tokens_out": tok_out,
        "cost_usd": round(cost, 4),
        "latency_s": round(dt, 2),
    }
    (OUT_DIR / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Post-hoc scoring on ground-truth slice
# ---------------------------------------------------------------------------


def score_ground_truth(results: dict, new_tex: str) -> dict:
    """Score the ground-truth slice against Mateo's `49.1new.tex` using the
    shared `diagnose_49_1` categorization (so the metric is exactly the one
    used in `49_1_error_profile.md`)."""
    per_variant: dict = {}

    # Keys for pages 495-499 of 140-3
    gt_keys = [k for k in results if k.startswith("140-3_p49") and int(k.split("_p")[1]) in range(495, 500)]

    gem_all = "\n\n".join(results[k]["gemini_pbp"]["text"] for k in gt_keys)
    cla_all = "\n\n".join(results[k]["claude_pbp"]["text"] for k in gt_keys)

    variants = [("gemini_pbp", gem_all), ("claude_pbp", cla_all)]

    whole = results.get("__whole_doc__", {}).get("text")
    if whole:
        variants.append(("gemini_whole_doc", whole))

    # Also include the shipped 49.1old.tex baseline for reference
    old_tex = (REPO / "reference" / "validation" / "49.1old.tex").read_text(encoding="utf-8")
    variants.insert(0, ("shipped_49_1_old", old_tex))

    for label, text in variants:
        profile = categorize(text, new_tex)
        scr = score_profile(profile)
        per_variant[label] = {"profile": profile, "score": scr, "length": len(text)}
    return per_variant


# ---------------------------------------------------------------------------
# A/B viewer for the blind slice
# ---------------------------------------------------------------------------


VIEWER_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Grothendieck OCR benchmark — Mateo A/B viewer</title>
<style>
  :root {
    --bg: #0f1115;
    --fg: #e7e9ee;
    --panel: #161a22;
    --border: #283041;
    --accent: #7aa2f7;
    --good: #9ece6a;
  }
  html, body { background: var(--bg); color: var(--fg); margin: 0; font-family: system-ui, -apple-system, sans-serif; }
  header { padding: 16px 24px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 24px; }
  header h1 { margin: 0; font-size: 18px; font-weight: 500; }
  .muted { color: #8e96a8; }
  .container { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px 24px; min-height: calc(100vh - 120px); }
  .pane { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; display: flex; flex-direction: column; }
  .pane h2 { margin: 0; padding: 10px 14px; font-size: 14px; font-weight: 500; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; }
  .pane pre { flex: 1; overflow: auto; margin: 0; padding: 14px; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 13px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  nav { padding: 10px 24px; border-top: 1px solid var(--border); display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  button { background: var(--panel); color: var(--fg); border: 1px solid var(--border); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 14px; }
  button:hover { border-color: var(--accent); }
  button.vote { padding: 8px 16px; font-weight: 500; }
  button.vote.active { background: var(--accent); color: #0b0d12; border-color: var(--accent); }
  .label { padding: 2px 8px; background: var(--border); border-radius: 4px; font-size: 11px; color: #c0c5d1; }
  .stats { margin-left: auto; font-size: 12px; color: #8e96a8; }
  .export { margin-left: 12px; }
</style>
</head>
<body>
<header>
  <h1>Grothendieck OCR benchmark — blind A/B</h1>
  <span class="muted">Gemini 3.1 Pro vs Claude Opus 4.7 — same prompt, same context, pages randomized per card</span>
  <span class="stats" id="stats"></span>
</header>
<div class="container">
  <div class="pane"><h2>A <span class="label" id="labelA">?</span></h2><pre id="textA"></pre></div>
  <div class="pane"><h2>B <span class="label" id="labelB">?</span></h2><pre id="textB"></pre></div>
</div>
<nav>
  <button id="prev">&larr; prev</button>
  <span id="pageLabel" class="muted">page ?/?</span>
  <button id="next">next &rarr;</button>
  <button class="vote" id="voteA">A wins</button>
  <button class="vote" id="voteEq">equal / tie</button>
  <button class="vote" id="voteB">B wins</button>
  <button class="vote" id="reveal">reveal which is which</button>
  <button class="export" id="export">export my votes (JSON)</button>
</nav>
<script>
const DATA = __DATA__;  // injected by Python
const PAGES = DATA.items;
const STORAGE_KEY = "grothendieck-ab-votes-v1";
let votes = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
let idx = 0;
let revealed = false;

function render() {
  const p = PAGES[idx];
  // Stable pseudo-random assignment per page key so the same page always
  // shows the same models in the same slots (but distribution is mixed).
  const flip = hash(p.key) % 2 === 1;
  const modelA = flip ? "claude" : "gemini";
  const modelB = flip ? "gemini" : "claude";
  document.getElementById("textA").textContent = p[modelA + "_text"];
  document.getElementById("textB").textContent = p[modelB + "_text"];
  document.getElementById("labelA").textContent = revealed ? modelA : "hidden";
  document.getElementById("labelB").textContent = revealed ? modelB : "hidden";
  document.getElementById("pageLabel").textContent = `page ${idx + 1}/${PAGES.length} — ${p.volume} p.${p.page}`;
  // highlight active vote
  for (const id of ["voteA", "voteEq", "voteB"]) {
    document.getElementById(id).classList.remove("active");
  }
  const v = votes[p.key];
  if (v === "A") document.getElementById("voteA").classList.add("active");
  if (v === "tie") document.getElementById("voteEq").classList.add("active");
  if (v === "B") document.getElementById("voteB").classList.add("active");
  // Store which model is in which slot so the export is meaningful
  p._slotA = modelA;
  p._slotB = modelB;
  updateStats();
}

function hash(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h) + s.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

function updateStats() {
  const done = Object.keys(votes).length;
  const scored = Object.fromEntries([["claude", 0], ["gemini", 0], ["tie", 0]]);
  for (const p of PAGES) {
    const v = votes[p.key];
    if (!v) continue;
    if (v === "tie") scored.tie += 1;
    else scored[v === "A" ? p._slotA : p._slotB] += 1;
  }
  document.getElementById("stats").textContent =
      `voted ${done}/${PAGES.length} — claude ${scored.claude} gemini ${scored.gemini} tie ${scored.tie}`;
}

function vote(letter) {
  const p = PAGES[idx];
  votes[p.key] = letter;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(votes));
  render();
}

document.getElementById("prev").onclick = () => { idx = Math.max(0, idx - 1); revealed = false; render(); };
document.getElementById("next").onclick = () => { idx = Math.min(PAGES.length - 1, idx + 1); revealed = false; render(); };
document.getElementById("voteA").onclick = () => vote("A");
document.getElementById("voteEq").onclick = () => vote("tie");
document.getElementById("voteB").onclick = () => vote("B");
document.getElementById("reveal").onclick = () => { revealed = !revealed; render(); };
document.getElementById("export").onclick = () => {
  // Re-render once for every page to populate slot assignments
  const snapshot = { generated: new Date().toISOString(), votes: [] };
  for (let i = 0; i < PAGES.length; i++) {
    const p = PAGES[i];
    const flip = hash(p.key) % 2 === 1;
    const modelA = flip ? "claude" : "gemini";
    const modelB = flip ? "gemini" : "claude";
    const v = votes[p.key];
    let winner = null;
    if (v === "A") winner = modelA;
    if (v === "B") winner = modelB;
    if (v === "tie") winner = "tie";
    snapshot.votes.push({ key: p.key, volume: p.volume, page: p.page, vote: v || null, winner });
  }
  const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "grothendieck_ab_votes.json";
  a.click();
};
document.addEventListener("keydown", e => {
  if (e.key === "ArrowLeft") document.getElementById("prev").click();
  else if (e.key === "ArrowRight") document.getElementById("next").click();
  else if (e.key === "a" || e.key === "A") vote("A");
  else if (e.key === "b" || e.key === "B") vote("B");
  else if (e.key === "=" || e.key === "0") vote("tie");
  else if (e.key === "r") document.getElementById("reveal").click();
});

render();
</script>
</body>
</html>
"""


def render_ab_viewer(results: dict) -> None:
    items = []
    for key, r in results.items():
        if key.startswith("__"):
            continue
        # Only blind slice (skip 140-3 pages 495-499 ground-truth)
        if r["volume"] == "140-3" and 495 <= r["page"] <= 499:
            continue
        items.append({
            "key": key,
            "volume": r["volume"],
            "page": r["page"],
            "gemini_text": r["gemini_pbp"]["text"],
            "claude_text": r["claude_pbp"]["text"],
            "gemini_cost": r["gemini_pbp"]["cost_usd"],
            "claude_cost": r["claude_pbp"]["cost_usd"],
            "gemini_latency": r["gemini_pbp"]["latency_s"],
            "claude_latency": r["claude_pbp"]["latency_s"],
        })
    html = VIEWER_TEMPLATE.replace("__DATA__", json.dumps({"items": items}))
    (HERE / "benchmark_opus_vs_gemini.html").write_text(html, encoding="utf-8")
    print(f"Wrote benchmark_opus_vs_gemini.html with {len(items)} A/B pairs")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def write_summary(results: dict, gt_scores: dict) -> None:
    lines = []
    lines.append("# Opus 4.7 vs Gemini 3.1 Pro benchmark — summary")
    lines.append("")
    lines.append(f"Run: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Cost + latency totals")
    lines.append("")
    lines.append("| Model | Pages | Input tok | Output tok | Cost (USD) | Avg latency (s) |")
    lines.append("|-------|-------|-----------|------------|------------|-----------------|")
    for label in ["gemini_pbp", "claude_pbp"]:
        n = 0; ti = 0; to = 0; c = 0.0; lat = 0.0; lat_n = 0
        for k, r in results.items():
            if k.startswith("__"):
                continue
            x = r.get(label)
            if not x:
                continue
            n += 1
            ti += x.get("tokens_in") or 0
            to += x.get("tokens_out") or 0
            c += x.get("cost_usd") or 0.0
            l = x.get("latency_s")
            if l is not None:
                lat += l; lat_n += 1
        avg_lat = lat / lat_n if lat_n else None
        avg_str = f"{avg_lat:.1f}" if avg_lat is not None else "n/a (cached)"
        lines.append(f"| {label} | {n} | {ti:,} | {to:,} | ${c:.3f} | {avg_str} |")
    wd = results.get("__whole_doc__")
    if wd:
        lines.append(
            f"| gemini_whole_doc ({len(wd['pages'])} pages in one call) | "
            f"{len(wd['pages'])} | {wd['tokens_in']:,} | {wd['tokens_out']:,} | "
            f"${wd['cost_usd']:.3f} | {wd['latency_s']:.1f} |"
        )
    lines.append("")
    lines.append("## Ground-truth slice (Section 49.1, 140-3 p.495-499)")
    lines.append("")
    lines.append("Scored with the `diagnose_49_1` categorization against `49.1new.tex`.")
    lines.append("Higher `quality` = closer to Mateo's publishable conventions.")
    lines.append("")
    lines.append("| Variant | length (chars) | raw residue/kc | notation drift/kc | structure coverage | composite quality |")
    lines.append("|---------|----------------|----------------|-------------------|--------------------|-------------------|")
    for label, v in gt_scores.items():
        s = v["score"]
        lines.append(
            f"| {label} | {v['length']:,} | {s['raw_density_per_kchar']} | "
            f"{s['notation_density_per_kchar']} | {s['structure_coverage']:.0%} | "
            f"**{s['quality']:.3f}** |"
        )
    lines.append("")
    lines.append("See [`49_1_error_profile.md`](49_1_error_profile.md) for the category definitions.")
    lines.append("")
    lines.append("## Blind A/B slice")
    lines.append("")
    lines.append(
        "See [`benchmark_opus_vs_gemini.html`](benchmark_opus_vs_gemini.html) — "
        "open in a browser, click A/B on each pair. Votes persist in localStorage; "
        "the 'export my votes' button produces a JSON we can incorporate."
    )
    lines.append("")
    (OUT_DIR / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote summary.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-ground-truth", action="store_true")
    parser.add_argument("--skip-blind", action="store_true")
    parser.add_argument("--skip-whole-doc", action="store_true")
    parser.add_argument("--resume", action="store_true",
                         help="Reuse cached results.json when a page is already there.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--gemini-source", choices=["cached", "live"], default="cached",
                         help="cached: use production transcriptions.json (default, no cost); "
                              "live: call Gemini fresh (needs GEMINI_API_KEY).")
    parser.add_argument("--prompt-style", default=DEFAULT_PROMPT_STYLE,
                         help="override default prompt style (e.g. mateo-canonical)")
    parser.add_argument("--output-subdir", default=None,
                         help="override output directory name under experiments/pilot/")
    args = parser.parse_args()

    # Apply output dir override
    global OUT_DIR, PROMPT_STYLE
    if args.output_subdir:
        OUT_DIR = HERE / args.output_subdir
        OUT_DIR.mkdir(exist_ok=True)
    PROMPT_STYLE = args.prompt_style

    ant_api = os.environ.get("ANTHROPIC_API_KEY")
    if not ant_api:
        print("ERROR: set ANTHROPIC_API_KEY in .env")
        sys.exit(1)
    claude_client = Anthropic(api_key=ant_api)

    gem_client = None
    if args.gemini_source == "live" or not args.skip_whole_doc:
        gem_api = os.environ.get("GEMINI_API_KEY")
        if not gem_api:
            print("WARNING: GEMINI_API_KEY not set — forcing --gemini-source=cached and --skip-whole-doc")
            args.gemini_source = "cached"
            args.skip_whole_doc = True
        else:
            gem_client = genai.Client(api_key=gem_api)

    results_path = OUT_DIR / "results.json"
    results: dict = {}
    if args.resume and results_path.exists():
        results = json.loads(results_path.read_text(encoding="utf-8"))
        print(f"Resuming with {len(results)} cached entries")

    targets = []
    if not args.skip_ground_truth:
        targets += GROUND_TRUTH_PAGES
    if not args.skip_blind:
        targets += BLIND_PAGES
    if args.limit:
        targets = targets[:args.limit]

    print("=" * 70)
    print(f"Benchmarking {len(targets)} pages (Gemini 3.1 Pro vs Opus 4.7)")
    print("=" * 70)

    for (vol, page) in targets:
        key = f"{vol}_p{page}"
        if args.resume and key in results and "gemini_pbp" in results[key] and "claude_pbp" in results[key]:
            print(f"  [{key}] (cached)")
            continue
        run_single_page(gem_client, claude_client, vol, page, results, args.gemini_source)

    if not args.skip_whole_doc and gem_client is not None:
        if args.resume and "__whole_doc__" in results:
            print("  [whole_doc] (cached)")
        else:
            run_whole_doc(gem_client, WHOLE_DOC_VOLUME, WHOLE_DOC_PAGES, results)

    # Ground-truth scoring
    new_tex = (REPO / "reference" / "validation" / "49.1new.tex").read_text(encoding="utf-8")
    gt_scores = score_ground_truth(results, new_tex)
    (OUT_DIR / "per_model_scores.json").write_text(
        json.dumps(gt_scores, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    write_summary(results, gt_scores)
    render_ab_viewer(results)
    print("\nDone.")


if __name__ == "__main__":
    main()
