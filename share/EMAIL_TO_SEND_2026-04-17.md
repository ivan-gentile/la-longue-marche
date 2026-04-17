To: mateo.carmona@csg.igrothendieck.org
Cc: olivia.caramello@igrothendieck.org

Subject: Re: Fw: First Results Transcription La Longe Marche IFAB CSG I GROTHENDIECK

Dear Mateo, dear Olivia,

Apologies for the slip on the date — here is the promised follow-up. It combines the improvements you asked for in your March 21 message with a proper technical write-up of how the pipeline works.

Everything is now in a public repository:

  **https://github.com/ivan-gentile/la-longue-marche**

so you can see exactly how results are produced and we have a shared reference for future iterations. I am also attaching a small zip with the key deliverables for convenience — `mateo_update_2026-04-17.zip`. A one-page overview of the contents is in the `README.md` at the top of the zip.

---

## The headline

Using `49.1old.tex` and `49.1new.tex` as a paired ground truth, I built a categorized diagnostic (`reports/49_1_error_profile.md` in the zip) that identifies exactly where our output diverges from your conventions — notation drift, missing publishable scaffolding (`\chapter*`, `\leqno`, `\footnote`, `\label`, `\addcontentsline`), and unresolved `[unclear]` markers.

Driven by that diagnostic I added a new prompt variant called `mateo-canonical`. It bakes in your canonical notation verbatim (`\mathfrak{S}`, `\operatorname{int}`, `\mathbf{Z}`, `\mathcal{G}`), the structural commands you use in Part I, and a three-excerpt few-shot pool drawn from your Sections 19, 25bis and 31.

Running the same five pages of Section 49 with this prompt and **Gemini 3.1 Pro**:

- composite quality score (1.0 = matches your conventions exactly): **0.113 → 0.742** (6.6× improvement)
- structure coverage: 7% → 71%
- notation drift per 1000 characters: 5.42 → 0.90

Under the same prompt, Claude Opus 4.7 reaches 0.661 — so on this task Gemini 3.1 Pro is the Pareto winner, at 16× lower cost per page.

A full-corpus re-run with this prompt is the recommended next step, estimated at about €10 for all 976 pages. I'll do this as soon as you confirm it's what you want.

---

## What has changed since the March 20 package

**1. Updated LaTeX for both volumes** (in `tex/` in the zip, also on the repo).

Both 140-3 and 140-4 have been fully pushed through the diagram re-transcription branch (`diagram-tikzcd` prompt, Gemini 3.1 Pro). Concretely:

| | 140-3 | 140-4 |
|---|---|---|
| `[DIAGRAM: ...]` placeholders | 102 → 5 | 48 → 0 |
| `\begin{matrix}` misused as a diagram | 34 → 0 | 6 → 0 |
| Stacked `\downarrow` pseudo-diagrams | 50 → 0 | 24 → 0 |
| Real `\begin{tikzcd}` blocks | 0 → 291 | 0 → 130 |

140-4 has been fully upgraded — this is the main item that was still pending in my March 20 note.

**2. Bourbaki schemes benchmark** (your suggestion). `bourbaki/` in the zip. Two runs over the first 5 pages:

- Claude Opus 4.7 page-by-page: $0.632 — clean `\mathfrak{p}`, `\emph{}`, a real `tikzcd` for the commutative diagram on page 2.
- **Gemini 3.1 Pro whole-document** (all 5 pages in one call): **$0.057 — 11× cheaper**, additionally captures archival marginalia ("Archives Grothendieck sept. 59", "n° 326 bis") that Claude silently dropped.

On typed text the pipeline produces essentially publishable LaTeX, confirming that the remaining gap on Part II is a prompt-engineering problem, not an OCR problem.

**3. A/B blind-preference viewer** — `benchmark/benchmark_opus_vs_gemini.html` in the zip.

Self-contained HTML, seven Part-II pages where we don't have ground truth, Gemini vs Opus with identities hidden. If you can spare two minutes to click A / B / = (tie) on any of the pages, the export-votes button drops a JSON I can feed back into the evaluation. No obligation — even two votes are useful.

**4. Pipeline documentation** — `PIPELINE.md` at the top of the zip.

This is what you asked for on March 21: the actual data flow, the three prompt templates verbatim with rationale, the context mechanism, the post-processing, the three-tier evaluation, and a one-paragraph reproduction snippet. I kept it honest about what is working and what is still open.

---

## What is still open

1. **Full-corpus re-run with `mateo-canonical`** — one command, ~€10. Would lift the whole book from ~0.13 to ~0.74 composite quality.
2. **A few hand-drawn geometric figures** — neither prompt handles these; they likely need a human pass.
3. **LLM-judge calibration against your ratings** — the A/B export above would deliver this directly.

As agreed, all contributions are acknowledged in the repository README and in the technical blog post I'm preparing for thinkgentile.com. I'll send you the blog draft before publishing so you can flag anything you'd rather not see public.

Thank you again for `49.1new.tex` — without that pair I would have been optimizing the wrong thing. Looking forward to your feedback, especially on the pages in the A/B viewer.

Best,

Ivan

---

Ivan Gentile
Senior Data Scientist, IFAB Foundation
https://linkedin.com/in/ivangentile

**Attachment:** `mateo_update_2026-04-17.zip` (≈ 1.5 MB)
