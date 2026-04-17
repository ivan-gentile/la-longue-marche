# La Longue Marche: transcription quality update

Date: 2026-03-20

## Executive summary

We addressed the two main quality issues raised during review:

1. notation inconsistency across pages
2. poor handling of commutative diagrams and other 2D mathematical layouts

The notation issue is largely under control in the current production corpus. The diagram issue is partially solved at the pipeline level and partially validated on one volume, but it is not yet fully rolled out into the main production viewer.

The important distinction is:

- the implementation work exists end-to-end
- the production corpus is only partially upgraded for diagrams

## What has been implemented

### 1. Diagram discovery

New script: `find_diagram_pages.py`

Purpose:

- scans existing transcriptions
- identifies pages likely containing diagrams
- classifies the diagram style currently used in the transcription

Current scan result:

- 178 diagram pages total
- 119 pages in `140-3`
- 59 pages in `140-4`
- 147 pages contain `[DIAGRAM: ...]` placeholders
- 87 pages are placeholder-only and therefore not renderable
- 57 pages contain stacked arrow layouts
- 30 pages contain `matrix`-based pseudo-diagrams

### 2. Diagram-specific transcription prompt

Updated file: `prompts_v2.py`

New prompt style:

- `diagram-tikzcd`

Purpose:

- keeps the existing text-first transcription style
- adds explicit instructions to use `tikzcd` for 2D diagrams
- includes few-shot examples for exact sequences, commutative squares, and triangles

### 3. Diagram re-transcription pipeline

New script: `retranscribe_diagrams.py`

Purpose:

- re-runs only pages identified as diagram-heavy
- stores the results separately in `diagram_transcriptions.json`
- supports merge into the main `transcriptions.json`
- supports dry-run, resume, and volume filtering

### 4. Notation normalization

New script: `normalize_notation.py`

Purpose:

- post-processes the production corpus to enforce canonical notation
- supports a deterministic regex mode and a more expensive LLM mode

Regex normalization was already executed on the production transcriptions.

## Current measured status

### Notation consistency

Status: mostly solved in production

After regex normalization, the remaining notation drift is low:

For `140-3`:

- `Sl(` remains on 3 pages
- `Gl(` remains on 1 page

For `140-4`:

- `Sl(` remains on 2 pages

This means the bulk inconsistencies have already been removed:

- `\cal` to `\mathcal`
- operator standardization toward `\operatorname{...}`
- `\S` replaced by `§`
- several environment mismatches repaired

Conclusion:

- notation consistency is in acceptable shape for stakeholder review
- a final LLM normalization pass is optional, not required for a first external update

### Diagram handling

Status: pipeline implemented, production rollout incomplete

Current main production transcriptions still contain many non-renderable or weakly renderable diagram pages:

For `140-3` current production:

- 102 pages still contain `[DIAGRAM: ...]`
- 34 pages still contain `\begin{matrix}` pseudo-diagrams
- 50 pages still contain stacked `\downarrow` layouts

For `140-4` current production:

- 45 pages still contain `[DIAGRAM: ...]`
- 6 pages still contain `\begin{matrix}` pseudo-diagrams
- 24 pages still contain stacked `\downarrow` layouts

An experimental re-transcription was completed for part of `140-3`:

- output file: `production/140-3/diagram_transcriptions.json`
- pages completed: 84
- successful responses: 84
- pages now using `tikzcd`: 68
- pages still using `matrix`: 5
- pages still using stacked arrows: 1
- pages still using `[DIAGRAM: ...]`: 0

Conclusion:

- the new prompt materially improves diagram rendering
- it is strong enough to replace many placeholders with real LaTeX diagrams
- it is not yet a complete solution for all diagram pages
- the results have not yet been merged into the main production corpus

## LaTeX quality assessment

### What improved

- many 2D diagrams were converted from placeholders into actual `tikzcd` structures
- notation is significantly more consistent across the corpus
- the viewer can already display the normalized text corpus

### What still fails

The remaining LaTeX issues are concentrated in diagram-heavy pages.

Observed failure modes:

- some pages still use `matrix` instead of `tikzcd` for 2D structures
- some pages still use vertical stacks with `\downarrow`
- some outputs overuse math mode for prose-adjacent fragments
- some diagram pages are conceptually geometric drawings rather than clean algebraic diagrams, and the model does not always know when to:
  - convert to `tikzcd`
  - preserve as descriptive text
  - keep a mixed representation

Representative examples:

- page 9 in `140-3`: strong improvement in the experimental branch, with a real `tikzcd`
- page 10 in `140-3`: still falls back to a `matrix` plus arrows
- page 17 in `140-3`: geometric figure remains textual rather than convertible into `tikzcd`
- many `140-4` pages remain on the old placeholder-based output because that volume has not yet been re-run

## Recommended message to stakeholder

The honest status update is:

- transcription consistency is substantially improved and mostly stabilized
- diagram transcription now has a dedicated solution path and shows strong early results
- the diagram upgrade is not fully deployed across the whole corpus yet
- the current viewer remains good for text review, but not yet final for diagram-heavy pages

In other words:

- the problem is no longer “unsolved”
- it is now “implemented and partially validated, pending full rollout and QA”

## Full rollout plan

To turn the current work into the full production solution:

1. Finish diagram re-transcription for all 178 identified pages, especially all of `140-4`.
2. Review the non-`tikzcd` outputs from the re-run and flag pages that still need manual or prompt-assisted correction.
3. Merge validated diagram outputs into `production/*/transcriptions.json`.
4. Re-run regex normalization on the merged corpus so the new diagram pages inherit the same notation conventions.
5. Regenerate `viewer_dashboard.html`.
6. Run a targeted QA pass on:
   - high-complexity diagrams
   - pages with remaining `matrix`
   - pages with remaining `\downarrow`
   - pages mixing prose, formulas, and hand-drawn geometry

## Practical next step

If the goal is a credible stakeholder update now, the recommended position is:

- share the current progress as a successful stabilization of notation plus a working diagram-upgrade pipeline
- do not claim the diagram problem is finished in production
- present the remaining work as a bounded rollout task, not as open-ended research

## Relevant files

- `find_diagram_pages.py`
- `prompts_v2.py`
- `retranscribe_diagrams.py`
- `normalize_notation.py`
- `diagram_pages.json`
- `production/140-3/diagram_transcriptions.json`
- `production/140-3/transcriptions.json`
- `production/140-4/transcriptions.json`
