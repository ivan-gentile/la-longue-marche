# Draft reply to Mateo — 2026-08-14

Status: DRAFT, not sent. Reply to Mateo's email of 2026-08-09
("Re: Observations on Transcription Gaps"). Cc: Olivia Caramello.

This draft absorbs the never-sent 2026-07-05 delta (root cause of the
two anomalies, issue form, coverage manifests) — Mateo has seen none of
that content.

Volunteer decision (resolved 2026-08-15): Ivan will read the terms and
possibly accept later; away late August – mid September and busy after.
The paragraph below says exactly that — keep working informally for
now, revisit when there is news.

Pre-send checklist:
- [x] Variétés run finished; COVERAGE.md reads 100/100
- [x] `audit_corpus.py` clean on every corpus, all seven defect classes
- [x] tikz-cd label fix in; canonical volumes compile 679/696 and 278/280 clean
- [ ] review website deployed — add its URL to the draft, send Mateo the
      password separately (never in this email thread)
- [ ] all commits pushed; the tex files open at their GitHub URLs

---

Subject: Re: Observations on Transcription Gaps

Dear Mateo,

Thank you for the detailed reply — no apology needed for the timing. It
is very good news that Section 49 is advancing; a first draft from your
hand is exactly what the research side of this work has been waiting
for, and I am happy to treat the points we exchanged as a working
framework rather than a fixed organisation of the project.

On the framework: thank you for the invitation — I am genuinely
interested, and I want to read the collaboration terms properly before
answering rather than answer lightly. The coming months make that
slower than I would like: I will be away from late August to
mid-September, and rather busy in the period that follows. So for now I
would ask to continue in the informal setting we have used so far,
under exactly the understanding you describe — anything that could
imply CSG involvement or representation will be discussed and confirmed
with you first — and to come back to the volunteer question when I can
give it the attention it deserves. In the meantime the work itself
continues, and I will keep sharing results as they land.

Since your message I have closed the open items on my side, so that
what you are working from is current and its limitations are stated.

**The canonical transcription is now complete.** The higher-fidelity
Gemini Pro run covers both volumes in full — 696/696 pages of 140-3 and
280/280 of 140-4, Section 49 included. Since you are drafting Section
49 now, `tex_output/la_longue_marche_140-3_mateo-canonical.tex` is the
file I would work from: measured against your corrected 49.1, it stays
markedly closer to the original wording than the fast-model draft
(word-level agreement 0.61 against 0.41, with far fewer silent
rewordings). Every deliverable also carries a page-level coverage
manifest, `tex_output/COVERAGE.md`, so a gap can never again be
something you discover by scrolling into it.

**The two anomalies you reported earlier are both resolved.** The
missing 140-3 pages 105–175 were a delivery failure of mine: a run died
on an API quota limit and the backfill that repaired it was never
published. The Préschémas gaps had a different cause — the
"whole document at once" mode silently skipped about 70 of the 437
pages and numbered the rest by the typescript's own chapter-restarting
page numbers, so the file could not be navigated against the scans.
That document has been re-transcribed page by page, with every marker
written by the pipeline from the PDF position:
`tex_output/bourbaki_schemes_pages_flash-lite.tex`, all 437 pages. I
also confirmed it was made from exactly the scans you linked — pages
1–210 correspond to U86u1 and 211–437 to U86u2 — and I can split it
into two files matching them if that helps your review.

**A defect I found while checking that file, which I want to report to
you directly.** Each page is transcribed with the previous page
attached as visual context, so words broken across a page break can be
resolved. In some cases the model transcribed that context page instead
of the intended one. The result is a page that looks perfectly normal —
no error, no gap, correct page marker — but carries the *previous*
page's text. In the Préschémas file this affected 22 of 437 pages. For
instance the page at PDF position 338 is an English errata sheet
("- II-xxi -", *P. II-104 ter, the cor.2 is incorrect*), but the file
contained a copy of page 337 instead. Worse, in two places the shift
meant a page of the source was absent from the transcription
altogether: PDF 182 ("Compléments au chap. 0") and PDF 384. All of them
have been re-transcribed and checked against the scans, and the file on
GitHub is corrected.

I should add that I only found the last of these because I went back
and checked my own check: the first version of this test compared the
two pages character by character, and a page whose lines had simply been
re-wrapped slipped under the threshold. Comparing word by word caught
four more.

I mention it in this much detail because it is precisely the class of
error your review is meant to catch and mine had not been catching: it
is invisible to any success count. Three things now guard against it —
the page attachments are labelled unambiguously, every runner compares
each page against its predecessor and retries when the two are
suspiciously alike, and a new audit
(`experiments/pilot/audit_corpus.py` → `CORPUS_AUDIT.md`) scans every
corpus before anything is shared.

That audit also looks for neighbouring failures that are equally
invisible to an error count, and it found those too: pages where the
model's own English deliberation reached the output instead of the
transcription, pages cut off mid-formula, mismatched LaTeX environments,
and a systematic escaping fault that had turned roughly 1,200 operator
names into a line break followed by a stray word. Some of those pages
were in the canonical La Longue Marche files. All of them have been
re-transcribed or repaired, and the audit is now clean on every corpus
I am pointing you to — including the two La Longue Marche variants, the
Préschémas file and Varieties.

On the context-echo defect specifically, the canonical La Longue Marche
corpus was unaffected, which I checked directly; one page of the
superseded Flash-Lite draft was, and it has been re-transcribed.

One more practical thing, since you may want to typeset these files
rather than only read them. They are LaTeX bodies that use a few macros
which, embarrassingly, nothing in the repository defined — so strictly
speaking they could not be compiled at all. There is now a
`tex_output/preamble.tex` that supplies them. With it, Varieties
compiles to a 100-page PDF with no errors and Préschémas produces its
437 pages. The two handwritten La Longue Marche volumes now compile
end to end as well — 679 of 696 pages of 140-3 and 278 of 280 of 140-4
produce no LaTeX error at all. Most of what used to fail turned out to
be one systematic quirk (commas inside commutative-diagram labels,
which the diagram package misparses) rather than hundreds of individual
faults, and that is now repaired mechanically on every rebuild. The
remaining errors are listed page by page in
`experiments/pilot/COMPILE_REPORT.md` rather than left for you to run
into; a page can be the right page, complete and well-formed, and still
contain a missing `$` in a formula.

In the same spirit I corrected the project's cost figures, which were
understated several-fold because the model's internal "thinking" tokens
are billed but were left out of my arithmetic. The corrected figures
are in `experiments/pilot/COSTS.md`. It does not change anything for
you, but the published record should be accurate.

**Varieties.** Thank you for this suggestion — it is a good
intermediate case: typewritten body with the mathematical script
letters added by hand, harder than Préschémas and far easier than La
Longue Marche. All 100 pages are transcribed with the same page-by-page
pipeline and are in the repository as
`tex_output/varietes_categories_U46.tex`, with coverage declared in the
manifest and the audit clean. Two details of that typescript that the
transcription tries to respect, and that are worth your eye: the
underline on a mathematical symbol is kept as notation rather than
turned into emphasis (so $\underline{K}$ stays distinct from $K$, and
the structure sheaf stays $\underline{O}_X$), and the handwritten hats
are kept ($\hat{\mathcal{C}}$ against $\mathcal{C}$). As always it is
a working draft and every line needs your verification.

**Filing anomalies.** The structured format you describe already exists
in the repository as the "Transcription anomaly" issue form — error
type, file, page, line, what the manuscript reads against what the
transcription reads, severity:
https://github.com/ivan-gentile/la-longue-marche/issues/new/choose —
with an equivalent CSV template in `evaluation/section-49/` if you
prefer to work offline. Both are ready whenever your Section 49 draft
reaches that stage, and whatever you file feeds directly into the
evaluation that drives the next round of changes.

One small practical point for when the draft arrives: I place the §49
heading at PDF page 495 of 140-3 and read the section through page 696,
while you cite pp. 494–695 — the same 202-page span, shifted by one, so
almost certainly a difference in counting convention. Worth pinning
down between us so that page references in anomaly reports line up
exactly.

Thank you again for the care in your reply. The distinction you draw
between facilitating access to the material and the research question
proper is one I will keep as the organising principle for this work.
I look forward to the Section 49 draft.

Best,
Ivan
