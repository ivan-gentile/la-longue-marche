To: mateo.carmona@csg.igrothendieck.org
Cc: olivia.caramello@igrothendieck.org

Subject: Re: Fw: First Results Transcription La Longe Marche IFAB CSG I GROTHENDIECK

Dear Mateo, dear Olivia,

Apologies for the delay past April 17 — the full-corpus re-run I wanted to include took longer than expected due to API quota limits. It is now complete. Here is the full update.

Everything is in a public repository:

  **https://github.com/ivan-gentile/la-longue-marche**

I am also attaching a zip (`mateo_update_2026-04-19.zip`) with the key deliverables. A README at the top of the zip summarises the contents.

---

## The headline

Using `49.1old.tex` and `49.1new.tex` as a paired ground truth, I built a categorized diagnostic that identifies exactly where our output diverges from your conventions — notation drift, missing publishable scaffolding (`\chapter*`, `\leqno`, `\footnote`, `\label`, `\addcontentsline`), and unresolved `[unclear]` markers.

Driven by that diagnostic I added a new prompt variant called `mateo-canonical`. It bakes in your canonical notation verbatim (`\mathfrak{S}`, `\operatorname{int}`, `\mathbf{Z}`, `\mathcal{G}`), the structural commands you use in Part I, and a three-excerpt few-shot pool drawn from your Sections 19, 25bis and 31.

**Model comparison on Section 49.1 (5-page ground-truth sample):**

| Model | Composite quality | Cost / 5 pages | Avg latency |
|-------|------------------|----------------|-------------|
| Shipped baseline (`text-first-fewshot`) | 0.113 | — | — |
| Claude Opus 4.7 + `mateo-canonical` | 0.661 | $1.173 | 28.6 s |
| Gemini 3.1 Pro + `mateo-canonical` | 0.742 | $0.074 | 67.8 s |
| **Gemini 3.1 Flash-Lite + `mateo-canonical`** | **0.777** | **$0.008** | **7.4 s** |

The composite quality metric ranges from 0 to 1.0 (1.0 = matches your conventions exactly). It combines three sub-scores: raw pipeline residue density, notation drift density, and publishable structure coverage.

The surprise is **Gemini 3.1 Flash-Lite** — the smallest, cheapest Gemini model — beating both Pro and Claude Opus on quality. At 150× lower cost than Opus and 9× lower latency than Pro, it became our production choice.

**Full-corpus result (all 976 pages, Flash-Lite + mateo-canonical):**

- 140-3: 696/696 pages (100%), with 114 diagram pages re-transcribed via `diagram-tikzcd` prompt
- 140-4: 280/280 pages (100%), with 58 diagram pages re-transcribed
- Section 49.1 composite quality on the complete corpus: **0.67** (6× improvement over shipped baseline)
- Total API cost: **< $0.60** for all 976 pages

The tex files are in `tex/` in the zip.

---

## What has changed since the March 20 package

**1. Updated LaTeX for both volumes** (in `tex/` in the zip, also on the repo).

Both 140-3 and 140-4 have been fully re-run with the `mateo-canonical` prompt and the diagram re-transcription branch:

| | 140-3 | 140-4 |
|---|---|---|
| `[DIAGRAM: ...]` placeholders | 102 → 5 | 48 → 0 |
| `\begin{matrix}` misused as a diagram | 34 → 0 | 6 → 0 |
| Stacked `\downarrow` pseudo-diagrams | 50 → 0 | 24 → 0 |
| Real `\begin{tikzcd}` blocks | 0 → 291 | 0 → 130 |

140-4 has been fully upgraded — this was the main item still pending in my March 20 note.

**2. Bourbaki schemes benchmark** (your suggestion). `bourbaki/` in the zip.

- Five-page comparison: Claude Opus 4.7 page-by-page ($0.632) vs Gemini 3.1 Pro whole-document ($0.057, 11× cheaper). Gemini additionally captures archival marginalia ("Archives Grothendieck sept. 59", "n° 326 bis") that Claude silently dropped.
- **Full 437-page Bourbaki transcription** now also available (`bourbaki/bourbaki_schemes_full_flash-lite.tex`, ~1 MB). On typed text the pipeline produces essentially publishable LaTeX, confirming that the remaining gap on Part II is a prompt-engineering problem, not an OCR problem.

**3. A/B blind-preference viewer** — `benchmark/benchmark_opus_vs_gemini.html` in the zip.

Self-contained HTML, seven Part-II pages where we don't have ground truth, Gemini vs Opus with identities hidden. If you can spare two minutes to click A / B / = (tie) on any of the pages, the export-votes button drops a JSON I can feed back into the evaluation. No obligation — even two votes are useful.

**4. Pipeline documentation** — `PIPELINE.md` at the top of the zip.

The actual data flow, the three prompt templates verbatim with rationale, the context mechanism, the post-processing, the three-tier evaluation, and a reproduction snippet. Kept honest about what is working and what is still open.

---

## What is still open

1. **A few hand-drawn geometric figures** — neither prompt handles these; they likely need a human pass (~5 pages across both volumes).
2. **LLM-judge calibration against your ratings** — the A/B export above would deliver this directly.
3. **Gemini 3.1 Pro full-corpus run** — currently at ~50% completion (resumed after quota reset). Will provide a second corpus for comparison once it finishes.

---

As agreed, all contributions are acknowledged in the repository README and in the technical blog post published at:
**https://thinkgentile.com/posts/grothendieck-ocr-deep-dive**

Please let me know if you'd like anything changed before I share that post more widely.

Thank you again for `49.1new.tex` — without that pair I would have been optimizing the wrong thing. Looking forward to your feedback.

Best,

Ivan

---

Ivan Gentile
Senior Data Scientist, IFAB Foundation
https://linkedin.com/in/ivangentile

**Attachment:** `mateo_update_2026-04-19.zip`
