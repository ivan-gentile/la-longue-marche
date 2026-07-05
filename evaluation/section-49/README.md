# Section 49 — research test case

Shared workspace for the track agreed with Mateo (June 2026): treat
Section 49 of *La Longue Marche* as the representative test case,
document the recurring error classes systematically, and validate every
pipeline change here before extending it to the rest of the corpus.

## Where Section 49 lives

| What | Where |
|---|---|
| Section heading | volume 140-3, **PDF page 495** (`\chapter*{§ 49 — Homomorphismes de M_{0,3}, les groupes M_{g,0} généralisés}`) |
| Extent | PDF pages 495–696 of 140-3 (no §50 heading found in this volume) |
| Ground truth | `reference/validation/49.1new.tex` — Mateo's corrected Section 49.1 (= PDF pages 495–499); `49.1old.tex` is the shipped February output over the same pages |
| Manuscript page | Grothendieck's own pagination puts §49 at p. 550 (per the manuscript's table of contents, PDF page 5) |

## Current transcription state (see `tex_output/COVERAGE.md`)

- `flash-lite-mateo` (complete): covers all of §49, draft quality.
- `mateo-canonical` (Gemini 3.1 Pro): **does not yet cover §49** apart
  from scattered diagram-overlay pages — pages 495–696 are first in the
  queue for the next quota window.

## What we know about error classes here

1. Style profile (`experiments/pilot/49_1_error_profile.md`): the
   February pipeline read the mathematics well but produced no
   publishable scaffolding; the `mateo-canonical` prompt fixed most of
   that (composite style 0.113 → 0.74+).
2. Content fidelity (`experiments/pilot/fidelity_49_1.md`, July 2026):
   the style gains did **not** carry content. Against Mateo's corrected
   text (763 content tokens), Flash-Lite outputs omit or rewrite about
   half; Gemini 3.1 Pro is the most faithful; Opus inserts spurious
   text. This matches Mateo's review experience (omissions, silent
   rewording) and drives the model choice for §49.

## How to report anomalies

- Preferred: the **"Transcription anomaly"** issue form on GitHub
  (error type, file, PDF page, line, manuscript reading vs
  transcription reading, severity).
- Offline alternative: fill `anomalies_template.csv` in this folder and
  send it by email — same fields, directly machine-readable.

## The evaluation loop

1. Mateo's corrected pages land in `reference/validation/` (one file
   per subsection, like `49.1new.tex`); anomaly reports land as issues
   or CSV rows.
2. Candidates are scored with
   `python experiments/pilot/evaluate_fidelity.py --preset 49.1`
   (content) and `experiments/pilot/diagnose_49_1.py` (style).
3. A prompt or model change ships to the full corpus only after it
   improves these numbers on §49 without regressing either dimension.
