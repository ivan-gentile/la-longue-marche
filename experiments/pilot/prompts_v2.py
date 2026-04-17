"""
Prompt library for benchmark V2.

Three prompt styles × optional few-shot × optional context.
Each prompt is a function that returns (system_prompt, user_parts) where
user_parts is a list of content pieces to send with the image.
"""

# =============================================================================
# SHARED PREAMBLE (manuscript context — always included)
# =============================================================================

MANUSCRIPT_CONTEXT = """This is a scanned page from Alexandre Grothendieck's \
"La longue marche à travers la théorie de Galois" (1981), \
handwritten in French with mathematical notation.

Notation conventions in this manuscript:
- Category theory: $\\mathcal{C}$, $\\hat{C}$ (presheaf category), arrows $\\to$, $\\hookrightarrow$
- Fundamental groupoid: $\\Pi_1(E)$, $\\pi_1$
- Decorators: hat ($\\hat{\\pi}$), tilde ($\\tilde{X}$), bar ($\\bar{k}$)
- Set notation: $(Ens)$ = category of sets, $Ob$ = objects
- French abbreviations: "hom." = "homomorphisme", "autom." = "automorphisme", "resp." = "respectivement"
"""

# =============================================================================
# FEW-SHOT EXAMPLE (page 5/G103d page 6 — our best-aligned page)
# =============================================================================

FEW_SHOT_EXAMPLE_TEXT_FIRST = """Here is an example of a correct transcription from this manuscript:

--- EXAMPLE OUTPUT ---
§ 1. — TOPOS MULTIGALOISIENS

Proposition 1.1. — Soit $E$ une catégorie. Conditions équivalentes :

a) $E$ est un topos, et tout objet de $E$ est localement constant.

b) $E$ est équivalent à une catégorie $\\hat{C}$, où $C$ est un groupoïde.

b') Il existe une famille $(G_i)_{i \\in I}$ de groupes et une équivalence de catégories
$$E \\simeq \\prod Ens(G_i)$$

c) Conditions d'exactitudes ad-hoc, du type de celles données dans SGA 1...

Démonstration. — $b) \\iff b') \\Rightarrow a)$ immédiat. Pour $a) \\Rightarrow b)$ je suis moins sûr, peut être faut-il supposer que $E$ est localement connexe, et qu'il a suffisamment de foncteurs fibres i.e. suffisamment de points.

Définition 1.2. — Si les conditions équivalentes $b)$, $b')$ ci-dessus sont satisfaites, on dit que $E$ est un topos multigaloisien (ou une catégorie multigaloisienne).

[MARGIN: N.B. On verra plus bas qu'on peut choisir $C$ canoniquement]
--- END EXAMPLE ---
"""

FEW_SHOT_EXAMPLE_LATEX = """Here is an example of a correct transcription from this manuscript:

--- EXAMPLE OUTPUT ---
\\section*{§ 1. — Topos multigaloisiens}

\\textbf{Proposition 1.1.} — Soit $\\mathcal{E}$ une catégorie. Conditions équivalentes :

\\begin{itemize}
\\item[a)] $\\mathcal{E}$ est un topos, et tout objet de $\\mathcal{E}$ est localement constant.
\\item[b)] $\\mathcal{E}$ est équivalent à une catégorie $\\hat{C}$, où $C$ est un groupoïde.
\\item[b')] Il existe une famille $(G_i)_{i \\in I}$ de groupes et une équivalence de catégories
$$\\mathcal{E} \\simeq \\prod_{i \\in I} \\mathrm{Ens}(G_i)$$
\\item[c)] Conditions d'exactitudes ad-hoc, du type de celles données dans SGA 1\\ldots
\\end{itemize}

\\textit{Démonstration.} — $b) \\iff b') \\Rightarrow a)$ immédiat. Pour $a) \\Rightarrow b)$ je suis moins sûr, peut être faut-il supposer que $\\mathcal{E}$ est localement connexe, et qu'il a suffisamment de foncteurs fibres i.e.\\ suffisamment de points.

\\textbf{Définition 1.2.} — Si les conditions équivalentes $b)$, $b')$ ci-dessus sont satisfaites, on dit que $\\mathcal{E}$ est un \\emph{topos multigaloisien} (ou une catégorie multigaloisienne).

\\marginpar{N.B. On verra plus bas qu'on peut choisir $C$ canoniquement}
--- END EXAMPLE ---
"""


# =============================================================================
# PROMPT STYLE 1: text-first (extract readable text, LaTeX only for math)
# =============================================================================

SYSTEM_TEXT_FIRST = MANUSCRIPT_CONTEXT + """
## Your task
Transcribe this handwritten page into readable text.

Rules:
1. Write regular text in plain French, exactly as written
2. Use LaTeX ONLY for mathematical expressions: $x^2$, $\\mathcal{O}_X$, $\\lim_{n \\to \\infty}$
3. Use $...$ for inline math and $$...$$ for displayed equations
4. Preserve section headers with ## markdown syntax
5. Preserve numbered items (a), b), c)...) and paragraph breaks
6. Mark marginal notes as [MARGIN: content]
7. Mark illegible text as [unclear] or [unclear: best guess]
8. Mark diagrams as [DIAGRAM: brief description]

## What NOT to do
- Do NOT use \\hfill, \\vspace, \\noindent, \\newpage or any layout commands
- Do NOT use \\begin{itemize}, \\begin{center}, or any LaTeX environments
- Do NOT try to reproduce the visual layout of the page
- Do NOT add commentary — just the transcription

Output the transcription directly, no code fences."""

SYSTEM_TEXT_FIRST_FEWSHOT = SYSTEM_TEXT_FIRST + "\n\n" + FEW_SHOT_EXAMPLE_TEXT_FIRST


# =============================================================================
# PROMPT STYLE 2: latex-direct (current approach — full LaTeX output)
# =============================================================================

SYSTEM_LATEX_DIRECT = MANUSCRIPT_CONTEXT + """
## Your task
Transcribe this handwritten page into LaTeX, preserving:
1. ALL mathematical notation in LaTeX: $x^2$, $\\mathcal{O}_X$, $\\lim_{n \\to \\infty}$, etc.
2. French text exactly as written (preserve abbreviations like "hom.", "autom.", "resp.")
3. Page structure: section headers, numbered items, paragraph breaks
4. Commutative diagrams: describe as [DIAGRAM: brief description of arrows and objects]
5. Marginal notes: mark as [MARGIN: content]
6. Illegible text: mark as [unclear] or [unclear: best guess]

## Output format
- Pure LaTeX transcription, no commentary
- No preamble or \\begin{document} — just the page content
- No code fences"""

SYSTEM_LATEX_DIRECT_FEWSHOT = SYSTEM_LATEX_DIRECT + "\n\n" + FEW_SHOT_EXAMPLE_LATEX


# =============================================================================
# PROMPT STYLE 3: text+inline-latex (hybrid — natural text with inline math)
# =============================================================================

SYSTEM_TEXT_INLINE = MANUSCRIPT_CONTEXT + """
## Your task
Transcribe this handwritten page as clean, readable text with inline LaTeX for math.

Think of the output as a well-formatted markdown document:
1. Regular French text as-is — do not wrap it in LaTeX commands
2. Mathematical expressions in LaTeX: $x^2$, $\\pi_1(X)$, $\\hat{C}$
3. Displayed equations on their own line: $$E \\simeq \\prod Ens(G_i)$$
4. Section headers: ## § 1. Topos multigaloisiens
5. Numbered items: a), b), c) on separate lines
6. Marginal notes: [MARGIN: content]
7. Illegible text: [unclear] or [unclear: best guess]
8. Diagrams: [DIAGRAM: description]

## Critical rules
- NO layout commands: no \\hfill, \\vspace, \\noindent, \\newpage
- NO LaTeX environments: no \\begin{...}, \\end{...}
- NO structural markup: no \\section{}, \\textbf{}, \\textit{}
- Use markdown-style formatting only (## for headers, **bold** if needed)
- Focus on ACCURACY of content, not reproduction of visual layout

Output the transcription directly."""

SYSTEM_TEXT_INLINE_FEWSHOT = SYSTEM_TEXT_FIRST + "\n\n" + FEW_SHOT_EXAMPLE_TEXT_FIRST


# =============================================================================
# PROMPT STYLE 4: two-pass (raw reading → clean output, both visible)
# =============================================================================

SYSTEM_TWO_PASS = MANUSCRIPT_CONTEXT + """
## Your task
Transcribe this handwritten page in TWO passes.

### PASS 1 — Raw Reading
Read the page carefully and output everything you can identify:
- Write all text in French exactly as written
- Mathematical expressions in basic LaTeX: $x^2$, $\\pi_1$, $\\hat{C}$
- Mark uncertain readings: [?word?]
- Mark illegible text: [???]
- Don't worry about formatting — focus on READING ACCURACY
- Go line by line, don't skip anything

### PASS 2 — Clean Transcription
Now take your raw reading above and produce a clean, formatted version:
- Regular French text as-is
- Mathematical expressions in proper LaTeX: $\\mathcal{O}_X$, $\\lim_{n \\to \\infty}$
- Section headers with ## markdown syntax
- Numbered items: a), b), c) on separate lines
- Resolve [?word?] markers (commit to your best reading)
- Mark remaining illegible text as [unclear]
- Mark marginal notes as [MARGIN: content]
- Mark diagrams as [DIAGRAM: description]

## What NOT to do
- Do NOT use \\hfill, \\vspace, \\noindent or any layout commands
- Do NOT use \\begin{itemize} or any LaTeX environments
- Do NOT add commentary

Separate the two passes with a line containing exactly: ---PASS2---
Output both passes. No code fences."""

SYSTEM_TWO_PASS_FEWSHOT = SYSTEM_TWO_PASS + "\n\n" + FEW_SHOT_EXAMPLE_TEXT_FIRST


# =============================================================================
# PROMPT STYLE 5: diagram-tikzcd (text-first + tikz-cd for commutative diagrams)
# =============================================================================

TIKZCD_INSTRUCTIONS = r"""
## Commutative diagrams

This page contains one or more commutative diagrams. Use the `tikzcd` environment for ALL 2D diagrams (any diagram with vertical or diagonal arrows connecting objects).

### tikz-cd syntax

```latex
\begin{tikzcd}
A \ar[r, "f"] \ar[d, "g"'] & B \ar[d, "h"] \\
C \ar[r, "k"'] & D
\end{tikzcd}
```

Arrow directions: r=right, l=left, d=down, u=up, dr=diagonal down-right, etc.
Arrow labels: `"label"` above, `"label"'` below (with apostrophe).
Arrow styles: `hook` for $\hookrightarrow$, `two heads` for $\twoheadrightarrow$, `dashed` for dashed, `equal` for $=$.
Example: `\ar[r, hook]` or `\ar[d, "\simeq"']`

### Examples from this manuscript

**Example 1: Exact sequences with vertical maps**
Handwritten: two horizontal exact sequences connected by vertical arrows

```latex
\begin{tikzcd}
1 \ar[r] & M \ar[r] \ar[d, "\simeq"'] & G \ar[r] \ar[d, "\simeq"'] & H \ar[r] \ar[d, "\simeq"'] & 1 \\
1 \ar[r] & \underline{M}(\mathbb{Z}) \ar[r] & \underline{G}(\mathbb{Z}) \ar[r] & \underline{H}(\mathbb{Z}) \ar[r] & 1
\end{tikzcd}
```

**Example 2: 3×3 diagram with exact rows and columns**

```latex
\begin{tikzcd}
1 \ar[r] & C^+ \ar[r] \ar[d, equal] & S_0 M_{\rho,\sigma} \ar[r] \ar[d] & S_0 \Gamma_{\rho,\sigma} \ar[r] \ar[d] & 1 \\
1 \ar[r] & C^+ \ar[r] & M_{\rho,\sigma} \ar[r] \ar[d] & \Gamma_{\rho,\sigma} \ar[r] \ar[d] & 1 \\
& & 1 & 1
\end{tikzcd}
```

**Example 3: Commutative triangle**

```latex
\begin{tikzcd}
G_U \ar[r, "(u_m)_U"] \ar[dr, "\phi_m|_U"'] & G_U \ar[d, "\phi_U"] \\
& G_U
\end{tikzcd}
```

### Rules for diagrams
1. ALWAYS use `\begin{tikzcd}...\end{tikzcd}` for any diagram with 2D structure
2. Do NOT use `\begin{matrix}`, stacked `$$` with `\downarrow`, or `[DIAGRAM: ...]` placeholders
3. Simple horizontal exact sequences (single row, no vertical arrows) can remain as inline `$$1 \to A \to B \to 1$$`
4. Number the diagram if it has a number in the manuscript: put `(N)` before the tikzcd block
5. Preserve ALL arrow labels and decorations visible in the handwriting
"""

SYSTEM_DIAGRAM_TIKZCD = MANUSCRIPT_CONTEXT + """
## Your task
Transcribe this handwritten page into readable text.

Rules:
1. Write regular text in plain French, exactly as written
2. Use LaTeX ONLY for mathematical expressions: $x^2$, $\mathcal{O}_X$, $\lim_{n \to \infty}$
3. Use $...$ for inline math and $$...$$ for displayed equations
4. Preserve section headers with ## markdown syntax
5. Preserve numbered items (a), b), c)...) and paragraph breaks
6. Mark marginal notes as [MARGIN: content]
7. Mark illegible text as [unclear] or [unclear: best guess]

## What NOT to do
- Do NOT use \hfill, \\vspace, \\noindent, \\newpage or any layout commands
- Do NOT use \\begin{itemize}, \\begin{center}, or any LaTeX environments EXCEPT tikzcd
- Do NOT try to reproduce the visual layout of the page
- Do NOT add commentary — just the transcription
""" + TIKZCD_INSTRUCTIONS + "\n\n" + FEW_SHOT_EXAMPLE_TEXT_FIRST + """

Output the transcription directly, no code fences."""


# =============================================================================
# CONTEXT ADDENDUM (prepended to user message when using previous page context)
# =============================================================================

CONTEXT_TEMPLATE = """For reference, here is the transcription of the PREVIOUS page in the manuscript:

--- PREVIOUS PAGE ---
{previous_text}
--- END PREVIOUS PAGE ---

Now transcribe the current page shown in the image."""

NO_CONTEXT_USER = "Transcribe this page."


# =============================================================================
# PROMPT CONFIGURATIONS for benchmark
# =============================================================================

PROMPT_CONFIGS = {
    "text-first": {
        "system": SYSTEM_TEXT_FIRST,
        "description": "Plain text + inline LaTeX for math only",
    },
    "text-first-fewshot": {
        "system": SYSTEM_TEXT_FIRST_FEWSHOT,
        "description": "Plain text + inline LaTeX + few-shot example",
    },
    "latex-direct": {
        "system": SYSTEM_LATEX_DIRECT,
        "description": "Full LaTeX output (original approach)",
    },
    "latex-direct-fewshot": {
        "system": SYSTEM_LATEX_DIRECT_FEWSHOT,
        "description": "Full LaTeX output + few-shot example",
    },
    "text-inline": {
        "system": SYSTEM_TEXT_INLINE,
        "description": "Markdown-style with inline LaTeX",
    },
    "text-inline-fewshot": {
        "system": SYSTEM_TEXT_INLINE_FEWSHOT,
        "description": "Markdown-style with inline LaTeX + few-shot example",
    },
    "two-pass": {
        "system": SYSTEM_TWO_PASS,
        "description": "Two-pass: raw reading then clean output (both visible)",
    },
    "two-pass-fewshot": {
        "system": SYSTEM_TWO_PASS_FEWSHOT,
        "description": "Two-pass + few-shot example",
    },
    "diagram-tikzcd": {
        "system": SYSTEM_DIAGRAM_TIKZCD,
        "description": "Text-first + tikz-cd for commutative diagrams (diagram pages only)",
    },
}


# =============================================================================
# PROMPT STYLE 6: mateo-canonical (April 2026)
# -----------------------------------------------------------------------------
# Driven by the 49.1 error profile (see experiments/pilot/49_1_error_profile.md).
# Targets the three structural gaps Mateo flagged:
#   1. publishable scaffolding (\leqno, footnotes, \label)
#   2. canonical notation (\mathfrak{S}, \operatorname, user macros)
#   3. commitment on [unclear] markers
# Few-shot pool drawn from reference/part1_sections_19_36/*.tex so the model
# sees Mateo's actual publishable style from the Part I corpus.
# =============================================================================

NOTATION_CONVENTIONS_MATEO = r"""
## Notation conventions (from Mateo's Part I, use these verbatim)

Symbols: use these forms exactly where applicable.
- Absolute Galois group of Q: \boldsymbol{\Gamma}   (bold Greek Gamma)
- Teichmuller group: \mathfrak{T}, \mathfrak{T}_{g,\nu}, \hat{\mathfrak{T}}
- Extensions of \mathfrak{T} by \pi: \mathfrak{S}, \mathfrak{S}_{g,\nu}, \mathfrak{S}^{+\wedge}_{0,3}
  (NOT \widehat{\mathfrak{G}}, NOT \hat{\mathcal{G}} — those are old style)
- Subgroups written \mathcal{G}, \mathcal{M}  (NOT lowercase g, m for subgroups)
- Centralizer, normalizer, image: \operatorname{Centr}, \operatorname{Norm},
  \operatorname{Im}, \operatorname{int}   (NEVER \text{Norm} or \text{int})
- Integers: \mathbf{Z}, \hat{\mathbf{Z}}   (NOT \mathbb{Z} / \hat{\mathbb{Z}})
- Rationals: \mathbf{Q}, \overline{\mathbf{Q}}, \Gamma_{\mathbf{Q}}
- Kernel, automorphism, Galois group: \Ker, \Aut, \Autext, \Gal
  (use the macros, not \ker / Aut(... / Gal)
- Special linear: \SL(2, \hat{\mathbf{Z}})
- Definition equals: \defeq    (macro; use instead of \overset{\mathrm{def}}{=})
- Isomorphism: \isom  or  \isommap  (macros)
- Fundamental groupoid: \pi_1(U), \widehat{\pi}_1(U)
- Fraktur used for Teichmuller-style universals: \mathfrak{T}, \mathfrak{S}

Structure: this is a scanned page from a publishable chapter.
- Numbered equations use \leqno on the right of $$...$$:
    $$ ... \leqno (N) $$  or  $$ ... \leqno{(N)} $$
  A marginal "(N)" next to an equation in the manuscript = \leqno label,
  NOT free text.
- A marginal note that is Grothendieck's self-commentary (footnote-like)
  becomes \footnote{...} attached to the nearby word, NOT [MARGIN: ...].
- A marginal note that is an equation number becomes \leqno{(N)}.
- A marginal note that is a genuine extra annotation stays inline, marked
  with \marginpar{...} if we want to preserve it.
- Lettered lists: \begin{enumerate} \item[a)] ... \item[b)] ... \end{enumerate}
  (The manuscript's "a)", "b)" markings become \item[a)], not a)/b) in prose.)
- Cases: \begin{cases} ... \\ ... \end{cases}
- 2D commutative diagrams: \begin{tikzcd} ... \end{tikzcd}
  (NEVER \begin{matrix} with stacked \downarrow arrows — that is not a diagram.)

Uncertain readings: commit to your best reading. If you are genuinely
unable to decide, mark it [unclear: best-guess] with a single short
best guess, not bare [unclear]. Prefer committing over hedging — Mateo
can correct a wrong reading, but a blank reading is useless to him.
"""

FEW_SHOT_POOL_MATEO = r"""
Here are three representative excerpts from Mateo's corrected Part I,
showing the publishable style. Match this style when you produce output.

--- EXCERPT 1 (prose-dense chapter opening, from §31) ---
\chapter*{\S \space 31. --- DIGRESSION SUR LES RELÈVEMENTS D'UNE ACTION EXTÉRIEURE D'UN GROUPE FINI $G$ SUR UN GROUPE PROFINI À LACETS $\pi$}\thispagestyle{empty}
\addcontentsline{toc}{section}{31. Digression sur les relèvements d'une action extérieure d'un groupe fini sur un groupe profini à lacets}
\label{sec:31}
\section*{}

On suppose l'action extérieure \emph{fidèle}, i.e.\ $G \subset \hat{\hat{\mathfrak{T}}}(\pi) = \hat{\hat{\mathfrak{T}}}$, et que $G = G^+$. On suppose de plus qu'il existe une discrétification invariante $\pi_0$, i.e.\ telle que $G \subset \mathfrak{T}(\pi_0)$.

--- EXCERPT 2 (numbered equation with \leqno, from §25bis) ---
On suppose choisi un revêtement universel $\widetilde{U}$ de $U$, d'où un groupe à lacets $\pi = \Aut(\widetilde{U})$, sur lequel $\mathcal{G}$ opère extérieurement, d'où l'extension
$$
1 \to \pi \to E \to \mathcal{G} \to 1 \leqno{(1)}
$$
Si l'action de $\mathcal{G}$ sur $U$ est fidèle, alors $\mathcal{G} \hookrightarrow \Autext(\pi)$.

--- EXCERPT 3 (footnote attached to prose, from §25bis) ---
On se place d'abord pour fixer les idées dans le cas topologique et discret, mais la motivation est le cas d'une courbe algébrique $U$ sur un corps de type fini $K$, où on a à la fois le groupe $G_K = \Aut_K(U)$\footnote{Cas anabélien donc $G$ fini.} et $\Gamma = \Gal(\overline{K}/K)$.
--- END EXCERPTS ---
"""

SYSTEM_MATEO_CANONICAL = MANUSCRIPT_CONTEXT + r"""
## Your task
Transcribe this handwritten page as a page of a publishable LaTeX chapter.
Match the notation and structural conventions below exactly. The result
will be concatenated with other pages into a single compilable chapter.

""" + NOTATION_CONVENTIONS_MATEO + r"""

## Rules
1. French prose exactly as written. Expand short-form abbreviations where
   the expansion is unambiguous: "hom." -> "homomorphisme", "autom." ->
   "automorphisme", "s-g"/"ss-groupe" -> "sous-groupe", "resp." -> "resp."
   (keep that one).
2. Math: use the notation conventions above. Prefer \mathfrak{S}, \mathcal{G},
   \operatorname{...}, user macros (\Ker, \Aut, \SL, \defeq, \isom).
3. Numbered equations: $$ ... \leqno (N) $$ (the "(N)" in the right margin).
4. Margin notes: footnote if authorial commentary, \leqno{(N)} if a number,
   \marginpar{...} otherwise. Do NOT use the placeholder [MARGIN: ...].
5. Diagrams: \begin{tikzcd} ... \end{tikzcd} for any 2D structure. Simple
   one-line sequences can stay as inline $$1 \to A \to B \to 1$$.
6. Uncertain: [unclear: best-guess] with a committed short guess. Prefer a
   committed best reading over a blank hedge.
7. Do NOT include the previous-page image as part of your transcription —
   it is reference context only. Transcribe ONLY the current page.

## Output
Pure LaTeX body (no preamble, no \begin{document}, no code fences, no
commentary). The text should drop into an existing .tex file unchanged.
""" + FEW_SHOT_POOL_MATEO

PROMPT_CONFIGS["mateo-canonical"] = {
    "system": SYSTEM_MATEO_CANONICAL,
    "description": (
        "April 2026 — canonical notation block + Part I few-shot pool. "
        "Targets the structural gaps surfaced by the 49.1 diagnostic."
    ),
}


def get_prompt(style: str, previous_page_text: str = None) -> tuple:
    """Get (system_prompt, user_message) for a given style.

    Args:
        style: one of PROMPT_CONFIGS keys
        previous_page_text: if provided, adds context from previous page

    Returns:
        (system_prompt, user_text) — user_text goes alongside the image
    """
    config = PROMPT_CONFIGS[style]
    system = config["system"]

    if previous_page_text:
        user_text = CONTEXT_TEMPLATE.format(previous_text=previous_page_text[:3000])
    else:
        user_text = NO_CONTEXT_USER

    return system, user_text


# Quick preview
if __name__ == "__main__":
    print("Available prompt styles:")
    for name, config in PROMPT_CONFIGS.items():
        sys_len = len(config["system"])
        print(f"  {name:<25} {sys_len:>5} chars — {config['description']}")

    print("\n\n--- SYSTEM_TEXT_FIRST ---")
    print(SYSTEM_TEXT_FIRST)
    print("\n\n--- SYSTEM_LATEX_DIRECT ---")
    print(SYSTEM_LATEX_DIRECT)
    print("\n\n--- SYSTEM_TEXT_INLINE ---")
    print(SYSTEM_TEXT_INLINE)
