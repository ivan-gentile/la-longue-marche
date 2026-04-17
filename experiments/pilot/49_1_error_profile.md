# Section 49.1 error profile

Categorized comparison of our pipeline output ([`49.1old.tex`](../../reference/validation/49.1old.tex), 12,535 chars) against Mateo's corrected version ([`49.1new.tex`](../../reference/validation/49.1new.tex), 14,714 chars).

The categories are designed to be reused on any Part II page. The same script can score Opus 4.7 output or refreshed Gemini output against Mateo's conventions, not just Section 49.1.

## Summary score

- Composite quality (old, higher is better): **0.113** / 1.0
- Structure coverage: 7% of Mateo-style markers present at least once
- Raw pipeline residue density: 4.71 per 1 000 chars
- Notation drift density: 5.42 per 1 000 chars
- French abbreviation residue density: 0.16 per 1 000 chars

## 1. Raw pipeline signals (should be 0 in a publishable file)

| id | description | old | new |
|----|-------------|-----|-----|
| `unresolved_unclear` | Unresolved `[unclear]` markers (model hedged instead of committing) | 26 | 0 |
| `margin_placeholder` | Margin notes left as `[MARGIN: ...]` placeholders (should be footnotes or \leqno labels) | 16 | 0 |
| `diagram_placeholder` | Diagram placeholders (should be tikzcd / tikzpicture) | 0 | 0 |
| `crossed_out_placeholder` | Crossed-out markers kept inline | 3 | 0 |
| `raw_page_separator` | Raw page separators from the pipeline (no place in a compiled chapter) | 7 | 0 |
| `raw_newpage` | Free-standing \newpage from the pipeline | 7 | 0 |

## 2. Publishable structure Mateo uses

| id | description | old | new |
|----|-------------|-----|-----|
| `chapter_heading` | `\chapter*` heading | 0 | 1 |
| `toc_entry` | TOC entries (\addcontentsline) | 0 | 2 |
| `label_anchor` | `\label{...}` anchors | 0 | 1 |
| `leqno_numbering` | Left-side equation numbering (\leqno) | 0 | 32 |
| `footnote` | Footnotes (from authorial margin commentary) | 0 | 5 |
| `tikzpicture` | Real tikzpicture environments | 0 | 1 |
| `tikzcd` | Real tikzcd commutative diagrams | 0 | 0 |
| `aligned_env` | Aligned math environments | 1 | 5 |
| `operatorname` | \operatorname{...} instead of \text{...} | 0 | 15 |
| `user_macro_Ker` | `\Ker` user macro (instead of \ker) | 0 | 4 |
| `user_macro_Aut` | `\Aut` user macro | 0 | 7 |
| `user_macro_SL` | `\SL` user macro (instead of Sl or SL) | 0 | 1 |
| `user_macro_defeq` | `\defeq` macro (definition-equals) | 0 | 5 |
| `user_macro_isom` | `\isom` macro (isomorphism) | 0 | 1 |

## 3. Notation drift (old vs canonical)

| id | description | hits in old | surviving in new |
|----|-------------|-------------|------------------|
| `hat_G_to_frakS` | `\widehat{\mathfrak{G}}_{0,3}^+` or `\hat{\mathcal{G}}` → canonical `\mathfrak{S}_{0,3}^{+\wedge}` | 13 | 0 |
| `text_int_to_op` | `\text{int}` → `\operatorname{int}` | 2 | 0 |
| `text_Norm_to_op` | `\text{Norm}` / `Norm_` → `\operatorname{Norm}` | 3 | 0 |
| `Cent_to_Centr` | `Cent_M` → `\underline{\operatorname{Centr}}_\mathcal{M}` | 2 | 0 |
| `Zhat_bb_to_bf` | `\hat{\mathbb{Z}}` → `\hat{\mathbf{Z}}` | 5 | 0 |
| `L_bb_to_upright` | `\mathbb{L}_0^\sim` → `L_0^\mathfrak{S}` | 6 | 0 |
| `lowerker_to_upper` | `\ker(...)` → `\Ker(...)` | 2 | 0 |
| `Sl_to_SL` | `Sl(` → `\SL` | 1 | 0 |
| `calC_to_frakS` | `\mathcal{C}` (image of phi) → `\mathfrak{S}` | 4 | 0 |
| `lowercase_g_to_calG` | lowercase `g` subgroup → `\mathcal{G}` | 30 | 1 |

## 4. French abbreviation residue

| id | description | old | new |
|----|-------------|-----|-----|
| `abbr_hom` | `hom.` → `homomorphisme` | 0 | 0 |
| `abbr_autom` | `autom.` → `automorphisme` | 0 | 0 |
| `abbr_ss_groupe` | `ss-groupe` → `sous-groupe` | 1 | 0 |
| `abbr_s_g` | `s-g` → `sous-groupe` | 1 | 0 |
| `abbr_c_j` | `c-j.` → `conjugaison` | 0 | 0 |
| `abbr_cent` | `cent.` → `centralisateur` | 0 | 0 |

## 5. Takeaways that drive prompt refresh

- **Primary gap is structural, not mathematical.** The pipeline
  reads Grothendieck well but does not produce publishable LaTeX
  scaffolding (chapter heading, \leqno, \label, \addcontentsline,
  footnotes). Prompt must either require or explicitly forbid this,
  not leave it ambiguous.
- **Margin notes serve multiple purposes in Grothendieck's
  manuscript.** Some are authorial commentary (→ footnote), some
  are equation numbers (→ \leqno), some are inline annotations.
  `[MARGIN: ...]` as a single placeholder loses this distinction;
  the prompt should mark the intended role.
- **Unresolved `[unclear]` markers are often decidable from math
  context.** Mateo commits to a reading; our pipeline hedges. The
  prompt should encourage committing with a confidence annotation,
  not leaving the token blank.
- **Notation conventions are specific to this manuscript.** Adding
  a canonical-notation block to the prompt (and a few-shot pool
  drawn from sections 19–36 of Part I) addresses most of the
  symbol-level drift.
- **Commutative diagrams are best expressed as `tikzcd` /
  `tikzpicture`.** The diagram-tikzcd prompt already exists; it
  needs to be rolled out across the full corpus.

