Subject: La Longue Marche transcription update and current materials

Ciao Mateo, Ciao Olivia,

I am following up on the transcription thread and sending the current materials in a cleaner package.

I am attaching the current full LaTeX exports for volumes 140-3 and 140-4, together with the benchmark dashboard, the production dashboard, and the page-by-page viewer.

In addition, after the first full transcription run, I started a quality-improvement pass focused on the two main issues that emerged during review:

- consistency of notation across pages
- handling of commutative diagrams and other 2D mathematical layouts

At this stage the notation is much more consistent across the corpus, and the diagram-specific pipeline is showing clear improvements on many pages. I am also attaching a short before/after note with a few representative examples.

The important caveat is that the diagram work is not yet fully rolled out across the whole corpus, so I would present the current material as the best current full export plus an ongoing improvement branch, rather than as the final stabilized edition.

Contents of the package:

- `la_longue_marche_140-3_current_2026-03-20.tex`
- `la_longue_marche_140-4_current_2026-03-20.tex`
- `viewer_dashboard.html`
- `production_dashboard.html`
- `benchmark_v2_dashboard.html`
- `BEFORE_AFTER_LATEX_EXAMPLES_2026-03-20.md`
- `STAKEHOLDER_UPDATE_2026-03-20.md`

For the viewer:

`viewer_dashboard.html` needs the rendered page images in a folder named `viewer_pages/` placed in the same directory as the HTML file. Once the folder is there, the viewer can be opened directly in the browser. Arrow keys navigate pages, and `T` toggles between LaTeX source and rendered math.

Download for `viewer_pages/`:
https://www.swisstransfer.com/d/df1e9652-a75a-4930-8eb4-1b3e7bd3a6ba

I would be very interested in your feedback, especially on the mathematical notation conventions and on the pages where diagrams matter most for archival use.

Best,

Ivan
