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
agreement on content tokens against Mateo's corrected text, so it is the
one that tracks omissions and silent rewording. Costs include thinking
tokens, billed at the output rate.

| Model | Word sim | Omitted | Inserted | $/1000 pages | s/page |
|---|---|---|---|---|---|
| `gemini-3.1-pro-preview` (current canonical model) | **0.573** | 104 | 37 | $93 | 53.3 |
| `gemini-3.7-flash` (released 2026-08-13) | **0.562** | 99 | 50 | **$15** | **12.3** |
| `gemini-3.6-flash` | 0.487 | 111 | 30 | $71 | 43.7 |
| `gemini-3.5-flash-lite` | 0.313 | 244 | 12 | $8 | 12.3 |
| `gemini-3.1-flash-lite-preview` (previous draft model)¹ | 0.449 | 270 | 39 | ~$3 | 7.4 |

¹ from the earlier `bench_mateo_flash_lite` run on the same five pages.

## What this says

**Gemini 3.7 Flash is the significant change.** It reaches Pro-level
fidelity — 0.562 against Pro's 0.573, with *fewer* omitted tokens (99
against 104) — at a sixth of the cost and a quarter of the latency. On
these five pages the gap to Pro is smaller than the gap between two Pro
runs of the same pages would likely be, so the honest reading is "close
to Pro", not "beats Pro".

**Newer is not automatically better.** `gemini-3.5-flash-lite` is the
newest Flash-Lite and the cheapest model tested, and it is markedly
*worse* than the two-generations-older Flash-Lite it would replace:
0.313 against 0.449, omitting 244 of 763 reference tokens. Had the
model ids simply been bumped to the latest of each tier, the draft
quality would have dropped without anyone noticing. This is the reason
the gate exists.

**Caveat.** Five pages is a small sample from one section, scored
against a reference that carries Mateo's editorial layer, so absolute
values are not meaningful — only the comparison between candidates is.
Before any full-corpus re-run on 3.7 Flash, the comparison should be
repeated on a wider page sample, and ideally on pages from a different
part of the manuscript.

## Decision

- `models.py` now carries the whole tier list; `gemini-3.7-flash` is the
  `flash` key and `gemini-3.1-pro-preview` remains `pro`.
- The **default for full runs stays Pro**: the canonical corpus is the
  scholarly deliverable and Pro is still the most faithful model
  measured.
- `gemini-3.7-flash` replaces Flash-Lite as the **cost-effective draft
  model** for new documents, where it is better on fidelity than the old
  Flash-Lite on every measure taken here.
- `gemini-3.5-flash-lite` is **not adopted**.
- Existing corpora keep the model that produced them: mixing generations
  inside one document would make it inconsistent for review, so the
  standalone runners pin their model id deliberately.
