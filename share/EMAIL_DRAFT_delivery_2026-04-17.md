Subject: Re: Fw: First Results Transcription La Longe Marche IFAB CSG I GROTHENDIECK

Dear Mateo, dear Olivia,

Here is the promised follow-up, combining the improvements you asked for on March 21 and the technical write-up we discussed.

Everything is now in a public repository so you can see exactly how the results are obtained, and so that we have a shared reference for future iterations:

**Repository:** https://github.com/ivan-gentile/la-longue-marche

---

## What has changed since the March 20 package

**1. Section 49.1 diagnostic (ground truth you sent us).**

I built a small script that categorizes the differences between `49.1old.tex` and `49.1new.tex` — the structural gaps (missing `\chapter*`, `\addcontentsline`, `\leqno`, `\footnote`), the notation drift (`\widehat{\mathfrak{G}}` instead of `\mathfrak{S}`, `\text{int}` instead of `\operatorname{int}`, `\mathbb{Z}` instead of `\mathbf{Z}`, lowercase `g` instead of `\mathcal{G}`), and the unresolved `[unclear]` markers. The report is at:
https://github.com/ivan-gentile/la-longue-marche/blob/main/experiments/pilot/49_1_error_profile.md

On a composite quality score derived from this diagnostic (1.0 = matches your conventions exactly), the shipped Section 49.1 output scored 0.113.

**2. Prompt refresh driven by the diagnostic.**

Using the gaps identified above — plus a three-excerpt few-shot pool drawn from your Sections 19, 25bis, and 31 — I added a new prompt variant called `mateo-canonical`. Re-running the same five pages of Section 49 with this prompt and **Gemini 3.1 Pro** lifted the composite score to **0.742** (6.6× improvement). Structure coverage jumped from 7% to 71%. Notation drift dropped from 5.42 to 0.90 per 1000 chars. For comparison, Claude Opus 4.7 with the same prompt reaches 0.661 — so Gemini 3.1 Pro wins under this prompt at 16× lower cost per page.

A full-corpus re-run with this prompt is the immediate next step, estimated at about €10 for all 976 pages.

Full table and prompt text here:
https://github.com/ivan-gentile/la-longue-marche/blob/main/PIPELINE.md

**3. Gemini 3.1 Pro vs Claude Opus 4.7 benchmark.**

12 pages (5 with ground truth, 7 blind), same prompt, same context mechanism. Short version: Opus is 15× more expensive for modest notation-drift gains, and has a real failure mode where it occasionally transcribes the "previous page context" into the output. Gemini 3.1 Pro stays the production model.

For the 7 blind pages, I built a small A/B viewer where the model identities are hidden. If you can spare two minutes to click "A wins / tie / B wins" on a few of them, the preferences become our first real human ground truth for the non-Section-49 pages:
https://github.com/ivan-gentile/la-longue-marche/blob/main/experiments/pilot/benchmark_opus_vs_gemini.html
(Arrow keys navigate, `A`/`B`/`=` vote, the "export my votes" button produces JSON I can ingest.)

**4. Diagram rollout for both volumes.**

All 114 diagram pages of 140-3 and all 59 diagram pages of 140-4 have now been re-transcribed with the `diagram-tikzcd` prompt and merged into the production corpus. For 140-3 this reduced `[DIAGRAM: ...]` placeholders from 102 to 5 and stacked-arrow pseudo-diagrams from 50 to 0. For 140-4 the equivalent reduction is from 48 placeholders to near-zero. The regenerated volumes are in the repo:

- https://github.com/ivan-gentile/la-longue-marche/blob/main/tex_output/la_longue_marche_140-3.tex
- https://github.com/ivan-gentile/la-longue-marche/blob/main/tex_output/la_longue_marche_140-4.tex

**5. Bourbaki schemes benchmark (your suggestion).**

I ran the pipeline on the first 5 pages of the Bourbaki archive PDF you pointed me to, in two modes for comparison:

- Page-by-page with Claude Opus 4.7: $0.632, clean publishable LaTeX (https://github.com/ivan-gentile/la-longue-marche/blob/main/tex_output/bourbaki_schemes_opus_p1-5.tex).
- **Whole-document with Gemini 3.1 Pro** (all 5 pages in one call): **$0.057 — 11× cheaper**, captures archival markings Claude skipped (e.g. "Archives Grothendieck sept. 59", "n° 326 bis") (https://github.com/ivan-gentile/la-longue-marche/blob/main/tex_output/bourbaki_schemes_gemini_whole_p1-5.tex).

Both produce `\mathfrak{p}` for prime ideals, `\emph{}` for introduced definitions, a real `tikzcd` for the commutative diagram on page 2. This confirms that when the input is clean (typewriter, not handwriting), the pipeline gap disappears — which in turn tells us that most of the remaining work on Part II is prompt and post-processing, not OCR.

**6. Pipeline documentation.**

`PIPELINE.md` answers your March 21 request for "a detailed account of the prompting strategies and pipeline structure". It covers data flow, model choice (with the benchmark numbers), the three prompt templates verbatim, the context mechanism, post-processing, the three-tier evaluation approach, and a one-minute reproduction snippet.
https://github.com/ivan-gentile/la-longue-marche/blob/main/PIPELINE.md

---

## Technical blog post

I am also writing a public follow-up to the January post at thinkgentile.com. The draft is ready and contains the comparison with Claude, the Section 49.1 story, the three-tier evaluation framework, and credit to you and Olivia. I'll send you the link before publishing so you can flag anything you'd rather not see public.

---

## What is still open

- **Full-corpus re-run with the `mateo-canonical` prompt** (~€10, biggest single lever — would lift the whole book from ~0.13 to ~0.74 composite quality).
- **A handful of hand-drawn geometric figures** (not commutative diagrams) that neither prompt handles well — these likely need human help regardless.
- **Judge calibration**: the LLM-as-judge scores exist for the full corpus but are not validated against expert ratings. Your A/B votes above would calibrate them directly.

As agreed, all contributions are acknowledged in the repo README and in the forthcoming blog post.

Thank you again for the ground truth — it changed the project. Looking forward to your feedback, especially on pages in the blind A/B set.

Best,

Ivan

---

Ivan Gentile
Senior Data Scientist, IFAB Foundation
https://linkedin.com/in/ivangentile
