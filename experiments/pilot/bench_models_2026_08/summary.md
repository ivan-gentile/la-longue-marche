# August 2026 Gemini model refresh — measured on Section 49.1

The repo's Flash tier was two generations behind: it used
`gemini-3.1-flash-lite-preview` (January 2026) while `gemini-3.7-flash`
shipped on 2026-08-13. This project's rule is that a model change ships
only if it improves the Section 49 numbers, so each candidate was run
over 140-3 PDF pages 495–499 — the five pages Mateo corrected by hand —
with the production `mateo-canonical` prompt and the production request
shape (previous page as visual context, medium thinking, 16k cap).

Reproduce with `python experiments/pilot/bench_models_2026_08.py`, then
`python experiments/pilot/evaluate_fidelity.py --preset 49.1`.

## Results

Word similarity is the fidelity metric that matters here: it measures
agreement on content tokens against Mateo's corrected text, so it tracks
omissions and silent rewording. Costs include thinking tokens, billed at
the output rate. Every row is five of five pages, run through this same
harness.

| Model | Word sim | Omitted | Inserted | $/1000 pages | s/page |
|---|---|---|---|---|---|
| `gemini-3.1-pro-preview` (canonical model) | **0.573** | 104 | 37 | $93 | 53.3 |
| `gemini-3.7-flash` (released 2026-08-13) | **0.562** | **99** | 50 | **$15** | **12.3** |
| `gemini-3.6-flash` | 0.487 | 111 | 30 | $71 | 43.7 |
| `gemini-3.5-flash-lite` | 0.344 | 142 | 14 | $9 | 12.4 |
| `gemini-3.1-flash-lite-preview` (previous draft model) | 0.301 | 166 | 33 | $4 | 6.3 |

## What this says

**Gemini 3.7 Flash is the significant change.** It reaches Pro-level
fidelity — 0.562 against Pro's 0.573, with *fewer* omitted tokens (99
against 104) — at a sixth of the cost and a quarter of the latency. On
these five pages the gap to Pro is smaller than the gap between two Pro
runs of the same pages would likely be, so the honest reading is "close
to Pro", not "beats Pro".

**The Flash-Lite tier is not a substitute for it.** Both Flash-Lite
models sit far below 3.7 Flash (0.344 and 0.301 against 0.562) while
saving only a few dollars per thousand pages. For a corpus that a
scholar has to verify line by line, that trade is not worth taking.

**A correction to an earlier version of this note.** It previously
claimed the newest Flash-Lite measured *worse* than the older one it
would replace, and drew a "newer is not automatically better" moral from
it. That was wrong, for two compounding reasons:

1. The 3.5 Flash-Lite row had been scored on **four** of the five pages
   — the call for page 496 timed out and the harness recorded the
   failure but still scored the truncated text against the full
   reference, turning a harness error into ~100 phantom "omitted"
   tokens.
2. The comparison figure for 3.1 Flash-Lite came from a **different**
   benchmark (`bench_mateo_flash_lite`), run with different settings and
   without thinking-token accounting, so the two numbers were never
   comparable.

Re-running page 496 and putting 3.1 Flash-Lite through *this* harness
reverses the finding: within the Flash-Lite tier the newer model is the
better one (0.344 against 0.301, 142 omitted against 166). The moral
that survives is about method, not models — a cross-harness comparison
is not evidence, and a candidate scored on fewer pages than its
reference will always look like it omitted the difference.

**Caveat.** Five pages is a small sample from one section, scored
against a reference that carries Mateo's editorial layer, so absolute
values are not meaningful — only the comparison between candidates is.
Before any full-corpus re-run on 3.7 Flash, repeat the comparison on a
wider page sample, ideally from a different part of the manuscript.

## Decision

- `models.py` carries the whole tier list; `gemini-3.7-flash` is the
  `flash` key and `gemini-3.1-pro-preview` remains `pro`.
- The **default for full runs stays Pro**: the canonical corpus is the
  scholarly deliverable and Pro is still the most faithful model
  measured.
- `gemini-3.7-flash` is the **cost-effective draft model** for new
  documents, well clear of both Flash-Lite generations on fidelity.
- Existing corpora keep the model that produced them: mixing generations
  inside one document would make it inconsistent for review, so the
  standalone runners pin their model id deliberately.
