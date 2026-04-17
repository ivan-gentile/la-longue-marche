# Pipeline — La Longue Marche transcription

Dear Mateo, this document explains how the AI transcription pipeline
produces the LaTeX files in [`tex_output/`](tex_output/) from the
handwritten scans. It is the document you asked for in your March 21
email. Every prompt, model choice, and post-processing rule is either
reproduced inline below or linked to the script that implements it.

The repository is [`github.com/ivan-gentile/la-longue-marche`](https://github.com/ivan-gentile/la-longue-marche).
All figures below come from scripts you can re-run yourself.

---

## 1. Data flow

```
raw_pdf/140-3.pdf  ─┐
raw_pdf/140-4.pdf  ─┤
                    │
                    ▼
             fitz (PyMuPDF)                        ← no image rasterization;
             extract single page                     PDF bytes are sent directly
                    │
                    ▼
     previous page PDF + current page PDF         ← context mechanism
                    │
                    ▼
             Gemini 3.1 Pro (medium thinking)       ← production transcription
             with prompt "text-first-fewshot"
                    │
                    ▼
      production/<vol>/transcriptions.json         ← per-page {status, text, tokens}
                    │
                    ▼
 diagram pages re-run with "diagram-tikzcd"        ← merged back into the JSON
 (retranscribe_diagrams.py)
                    │
                    ▼
             normalize_notation.py --mode regex     ← canonicalize \operatorname, §, etc.
                    │
                    ▼
             build_tex.py                            ← concatenate into a single .tex
                    │
                    ▼
      tex_output/la_longue_marche_140-3.tex
      tex_output/la_longue_marche_140-4.tex
```

## 2. Model choice (why Gemini 3.1 Pro)

We benchmarked 17 configurations on 4 test pages at the start of the
project (see [`experiments/pilot/PILOT_RESULTS.md`](experiments/pilot/PILOT_RESULTS.md)).
The winner was **Gemini 3.1 Pro, medium thinking**, with

- PDF pages sent **directly** to the API (no image rasterization),
- the **previous page** attached alongside the current page as
  visual context, which was the single biggest quality lift,
- prompt `text-first-fewshot` (below).

We also ran **Claude Opus 4.7** vs Gemini 3.1 Pro on 12 pages in
April 2026. Summary (from [`experiments/pilot/bench_opus_vs_gemini/summary.md`](experiments/pilot/bench_opus_vs_gemini/summary.md)):

| Model | Pages | Cost | Avg latency | Notation drift (per 1000 chars) |
|-------|-------|------|-------------|---------------------------------|
| Gemini 3.1 Pro | 12 | $0.13 | (batch) | 7.10 |
| Claude Opus 4.7 | 12 | $2.06 | 24.5 s | 4.05 |

Opus is **15× more expensive** for modestly better notation drift. On
volume it produces 40% more text but sometimes includes the previous-page
context as transcription (a real failure mode).

**Decision**: Gemini 3.1 Pro stays the production model. Opus 4.7 is
useful as a quality probe on small samples.

## 3. Prompt templates

All prompts are in
[`experiments/pilot/prompts_v2.py`](experiments/pilot/prompts_v2.py).
Three matter:

### 3.1. `text-first-fewshot` (what produced the current corpus)

Text-first output with inline LaTeX, one few-shot excerpt from your
Part I Section 1 as calibration. This is the prompt behind the
`140-3` and `140-4` .tex files you already have.

### 3.2. `diagram-tikzcd` (re-runs diagram-heavy pages)

Specialized prompt that forbids `\begin{matrix}` and stacked
`\downarrow` constructions and requires `\begin{tikzcd}` for any 2D
structure, with three explicit tikz-cd examples drawn from your
manuscript.  This prompt re-transcribed 114 diagram pages in `140-3`
(merged into the current .tex file). The 59 diagram pages in `140-4`
are the immediate next target (see [Known open work](#8-known-open-work)).

### 3.3. `mateo-canonical` (April 2026 — driven by your `49.1new.tex`)

New prompt introduced after the Section 49.1 diagnostic. It was
shaped directly from the differences between our output
(`49.1old.tex`) and your corrected version (`49.1new.tex`). It
targets three gaps:

1. **Publishable scaffolding** — `\chapter*`, `\addcontentsline`,
   `\label`, `\leqno` for right-margin equation numbers, `\footnote`
   for authorial commentary. Our original prompt let the model
   decide how to output margin notes; this prompt tells it explicitly
   that a "(N)" in the right margin becomes `\leqno{(N)}`, and an
   authorial remark in the margin becomes `\footnote{...}`.

2. **Canonical notation (from your Part I)** — `\mathfrak{S}` not
   `\widehat{\mathfrak{G}}`, `\mathcal{G}` (capital) not lowercase `g`,
   `\operatorname{Norm}` not `\text{Norm}`, `\mathbf{Z}` not `\mathbb{Z}`,
   `\Ker` / `\Aut` / `\SL` / `\defeq` / `\isom` as user macros.

3. **Commitment on `[unclear]`** — the model commits to a best reading
   rather than leaving a blank hedge.

It also ships a three-excerpt few-shot pool drawn from Sections
19, 25bis, and 31 of your Part I corpus, so the model sees your
actual publishable style alongside the canonical-notation block.

**Measured effect** (Section 49.1, 5 pages, scored with the shared
[`diagnose_49_1.py`](experiments/pilot/diagnose_49_1.py) categorization):

| Variant | Raw residue/kc | Notation drift/kc | Structure coverage | Composite quality |
|---------|----------------|-------------------|--------------------|-------------------|
| Shipped 49.1old.tex | 4.71 | 5.42 | 7 % | **0.113** |
| Gemini 3.1 Pro + old prompt | 3.33 | 7.10 | 14 % | **0.132** |
| Claude Opus 4.7 + `mateo-canonical` | 0.71 | 1.42 | 71 % | **0.661** |
| **Gemini 3.1 Pro + `mateo-canonical`** | **0.80** | **0.90** | **71 %** | **0.742** |
| Gemini 3.1 Pro + `mateo-canonical`, whole-doc (10 pages in one call) | 0.62 | 0.75 | 50 % | **0.714** |

The 6.6× jump in composite quality from 0.113 to 0.742 is what the
full corpus would approach if we re-ran it with this prompt. The
most striking comparison is **Gemini 3.1 Pro beating Claude Opus 4.7
under the same prompt** (0.742 vs 0.661) at **16× lower cost**
($0.074 vs $1.173 for 5 pages). Prompt is the dominant variable;
model is a smaller second-order effect.

Whole-document Gemini is also competitive with page-by-page,
slightly cheaper per page (~$0.009 vs ~$0.015) and ~40 % faster
end-to-end, at the cost of slightly lower structural coverage.
Recommended for the Bourbaki typed-text branch; for handwritten
Part II I would still use page-by-page because the
previous-page visual context materially helps.

## 4. Context mechanism

For every page N (except page 1), we send the call as

```
system:   <prompt>
user:     [PDF of page N-1]
          "[Previous page N-1 shown above for context]"
          [PDF of page N]
          "Transcribe this page."
```

The previous page is sent **as an image**, not as text. This is
deliberate — the symbols `\hat{X}` vs `\tilde{X}`, or `\mathfrak{S}`
vs `\mathcal{S}`, are more reliably carried over visually than
through an extracted-text round-trip.

## 5. Post-processing

### 5.1. Diagram re-transcription branch

[`experiments/pilot/retranscribe_diagrams.py`](experiments/pilot/retranscribe_diagrams.py)
re-runs only pages flagged as diagram-heavy (by
[`experiments/pilot/find_diagram_pages.py`](experiments/pilot/find_diagram_pages.py))
with the `diagram-tikzcd` prompt. Results accumulate into
`production/<vol>/diagram_transcriptions.json`, then `--merge`
folds them into the main `transcriptions.json`. The merge leaves a
`transcriptions_pre_diagram.json` backup.

As of April 2026, both `140-3` and `140-4` have their diagram pages
re-transcribed with the `diagram-tikzcd` prompt and merged into the
main corpus. 140-3 contributed 114 pages; 140-4 contributed 59.

### 5.2. Notation normalization

[`experiments/pilot/normalize_notation.py`](experiments/pilot/normalize_notation.py)
in `--mode regex` applies deterministic replacements:

- `\text{Ker}` → `\operatorname{Ker}`; same for `Aut`, `Norm`, `Gal`, `Spec`, `Hom`.
- `\widehat{\mathbb{Z}}` → `\hat{\mathbb{Z}}`.
- `\S N` → `§ N`.
- `bare Sl(` → `\operatorname{Sl}(`; same for `Gl`.
- `\begin{matrix} ... \end{array}` mismatched environments → repaired to `\end{matrix}`.

Current pass: 167 replacements across 47 pages in `140-3`, 1
replacement in `140-4`.

### 5.3. Final build

[`experiments/pilot/build_tex.py`](experiments/pilot/build_tex.py)
concatenates every page of `transcriptions.json` into the single
`tex_output/la_longue_marche_<vol>.tex`. The format is:

```
% header
%% ===== Page N =====

<transcription>

\newpage
...
```

This is fully reproducible from the JSON. To regenerate your copy:
`python experiments/pilot/build_tex.py`.

## 6. Evaluation: three tiers

We intentionally do not trust a single metric.

1. **String-similarity** (SequenceMatcher) against your Part I .tex,
   run during the 2026-03 pilot. Useful for ranking configurations
   among themselves, not for absolute accuracy.

2. **LLM-as-judge** — Gemini Flash-Lite rates each page on 5
   dimensions (text accuracy, math accuracy, completeness,
   formatting, overall). Cheap and consistent but judge-biased.
   See [`experiments/pilot/judge_v2.py`](experiments/pilot/judge_v2.py).

3. **Categorized structural diff against your corrected version** —
   the [`diagnose_49_1.py`](experiments/pilot/diagnose_49_1.py)
   script you see above. It is derived from `49.1new.tex` and can be
   run on any page. Output:
   [`experiments/pilot/49_1_error_profile.md`](experiments/pilot/49_1_error_profile.md).

4. **Human A/B preference** (your help). The benchmark viewer at
   [`experiments/pilot/benchmark_opus_vs_gemini.html`](experiments/pilot/benchmark_opus_vs_gemini.html)
   shows seven blind pairs with model identities hidden. Two minutes
   of your time on this gives us post-hoc ground truth we can cite.

## 7. Reproducing a single page

```bash
# One-time
python -m pip install -r requirements.txt

# Transcribe Part II page 495 (the start of Section 49.I) as Gemini did
GEMINI_API_KEY=... python experiments/pilot/run_production.py \
    --volume 140-3 --resume
# (--resume means only uncompleted pages will be re-run)

# Or, to try the April 2026 mateo-canonical prompt on the same page:
ANTHROPIC_API_KEY=... python experiments/pilot/run_opus_vs_gemini.py \
    --gemini-source cached --skip-whole-doc --skip-blind \
    --prompt-style mateo-canonical --output-subdir bench_mateo_canonical \
    --limit 5
```

## 8. Known open work

1. **Full-corpus re-run with `mateo-canonical` prompt**. Based on the
   Section 49.1 measurement (0.113 → 0.742 composite quality), this is
   the biggest single lever on overall quality. Estimated cost ≈ $10
   at current token prices for all 976 pages.
2. **Geometric / hand-drawn figures**. Roughly 5 pages across `140-3`
   and a few in `140-4` contain pictorial figures (not commutative
   diagrams). The `diagram-tikzcd` prompt either produces a
   matrix-style placeholder or a long textual description. Neither is
   right. These pages will probably need human intervention regardless
   of prompt.
3. **LLM-judge calibration against your ratings**. We have judge
   scores over the full corpus, but not yet validated against expert
   judgement.

## 9. One-line summary

Current corpus: **Gemini 3.1 Pro + `text-first-fewshot` prompt + sequential
previous-page visual context + 114 diagram pages re-run with
`diagram-tikzcd` + regex notation normalization**. Next release candidate:
same, but with the `mateo-canonical` prompt instead of
`text-first-fewshot`, plus the `140-4` diagram branch completed.
