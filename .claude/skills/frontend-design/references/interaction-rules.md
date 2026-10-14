<!-- Adapted from ckw-design-skill (MIT, Conner K Ward), commit c8de7c8 — extracted from its entry
     SKILL.md, which mixed these specific UI rules in with its routing. They are rules about
     interfaces, not about how to load a skill, so they live here. See ../NOTICE. -->

# Specific interface rules

Narrow, concrete rules that each exist because of a particular way interfaces go wrong. Unlike the
rest of this skill they are not about direction or composition — read them when building the thing
they name.

## Select-all always has a deselect — no dead-end selections

Any **"Select all"** affordance MUST be paired with a way to **clear the selection** — preferably
the *same button*, label-flipped when everything is already selected ("Select all" ⇄ "Deselect
all"). A select-all with no inverse is a trap: the user over-selects (or hits it by reflex), then
has to un-click items one by one, or reload the page, to get back. The cost is silent — it only
bites *after* they have committed to the wrong set.

- **Toggle the same button** (simplest, fewest controls): when all visible items are selected, the
  button reads "Deselect all" and clears; otherwise "Select all". One control, no dead end.
- Or a **separate Clear/Deselect** shown whenever the selection is non-empty.
- The deselect must reach the **same scope** the select-all did (all *shown*, all *filtered*, all
  *on this page*) — do not let "Select all" grab 500 while "Clear" drops only the 50 on screen.
- This generalizes: any reversible bulk toggle (select, expand-all, mute-all, check-all) needs its
  inverse one tap away. Never strand the user mid-task.

## Algorithm explainers — show the equation, annotate the terms

Whenever a UI surfaces an algorithm or model to the user (an "ⓘ how this works" panel, a model
breakdown, a methods note), **include the actual equation, typeset, with its key terms annotated**
— do not settle for prose. A scorer described only in words ("ranks by how much of the picked color
is present") is unfalsifiable hand-waving; the formula `score = Σ fracᵢ · max(0, 1 − ΔEᵢ/τ)` with
each term labelled tells the user *exactly* what the knob does.

- Render one clean, central equation per algorithm — the core, not every detail. Use proper
  notation: σ for sigmoid, Σ for sums, ‖·‖ for norms, superscripts, ΔE, ∇²; a monospace/serif-math
  block set off from the prose.
- **Annotate every symbol** immediately below: what `e_x`, `w`, `τ`, `Q` each are, one line each.
  An unlabelled equation is decoration; a labelled one is a spec.
- Keep it dependency-light — styled HTML/Unicode math works offline; reach for KaTeX/MathJax only
  if the expressions genuinely need it.
- State the **decision rule** alongside the score (e.g. "personal if P ≥ 0.55").

**Example (a logistic head):**

> P(personal │ x) = σ(**w**·**e**ₓ + b),  σ(z) = 1 / (1 + e⁻ᶻ)
> • **e**ₓ — the image's 768-d embedding · **w**, b — weights learned from your labels
> · decision: personal if P ≥ 0.55, reference if P ≤ 0.40.

## When design work runs a model, name the model and the cost

When design work involves running an LLM or an image model (generated assets, VLM analysis, layout
critique), say which model and roughly what it costs **before** running it, and annotate the result
with what actually ran.

- **Before:** "gpt-4o-mini layout critique on 8 designs · est. ~$0.04 total".
- **After:** the model used, the actual cost if it differed, and key params (seed, prompt,
  settings). Put it where the user reads it — the message, a contact-sheet header, an asset caption
  — not buried in a log.
- Include seeds in generated filenames (`hero_banner_seed3891.jpg`) so a result can be reproduced.
- **Why:** the user is deciding whether the cost-to-quality trade is worth it. An unlabelled cost
  hides the most important lever.
