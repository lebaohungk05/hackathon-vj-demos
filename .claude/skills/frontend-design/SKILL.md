---
name: frontend-design
description: Visual and interaction design for any web UI - new pages, components, dashboards, or reshaping an existing one. Use whenever the ask touches how something looks or feels to use, including "make this look better", "fix the spacing", styling, colour, typography, fonts, responsive behaviour, polish, or a UI that "sucks to use" - even when the word "design" is absent. Covers aesthetic direction, a token/typography/motion system, spatial composition, and a usability audit.
---

# Frontend Design

Approach this as the design lead at a small studio known for giving every client a visual identity that could not be mistaken for anyone else's. This client has already rejected proposals that felt templated, and is paying for a distinctive point of view: make deliberate, opinionated choices about palette, typography, and layout that are specific to this brief, and take one real aesthetic risk you can justify.

## Two things you cannot skip

Everything else in this skill is judgement. These two are not, because both failures are invisible from the code and both have shipped repeatedly.

**1. You cannot see what you made.** UI is generated as a token stream, never as pixels, so you cannot perceive a collision, an edge tangent, or lopsided weight. Render it, screenshot it, and have **fresh eyes** critique the image — a separate judge that did not write the page, told to hunt for what is wrong. Grading your own output rationalizes it. Full procedure: [references/spatial.md](references/spatial.md) §1.

**2. Horizontal overflow must be measured, not assumed.** A sideways scrollbar is invisible at desktop width, so no amount of looking at your own window catches it, and it re-appears every time a header or toolbar row gains an item. Before calling any UI done:

```js
document.documentElement.scrollWidth - document.documentElement.clientWidth   // must be 0
```

at **~390px and ~1024px**, this turn. Default to `flex-wrap: wrap` on header/toolbar rows and `body { overflow-x: clip }` so it passes by construction — but a backstop is not a measurement. If you have not measured narrow, say "haven't checked overflow yet" rather than "done". Recurrence cases and how to find the offending element: [references/spatial.md](references/spatial.md) §4.

## Ground it in the subject

If the brief does not pin down what the product or subject is, pin it yourself before designing: name one concrete subject, its audience, and the page's single job, and state your choice. If there's any information in your memory about the human's preferences, context about what they're building, or designs you've made before – use that as a hint. The subject's own world, its materials, instruments, artifacts, and vernacular, is where distinctive choices come from. Build with the brief's real content and subject matter throughout.

## Design principles

For web designs, the hero is a thesis. Open with the most characteristic thing in the subject's world, in whatever form makes sense for it: a headline, an image, an animation, a live demo, an interactive moment. Be deliberate with your choice: a big number with a small label, supporting stats, and a gradient accent is the template answer, only use if that's truly the best option.

Typography carries the personality of the page. Pair the display and body faces deliberately, not the same families you would reach for on any other project, and set a clear type scale with intentional weights, widths, and spacing. Make the type treatment itself a memorable part of the design, not a neutral delivery vehicle for the content.

Structure is information. Structural devices, numbering, eyebrows, dividers, labels, should encode something true about the content, not decorate it. Many generic designs use numbered markers (01 / 02 / 03), but that's only appropriate if the content actually is a sequence - like a real process or a typed timeline where order carries information the reader needs. Question if choices like numbered markers actually make sense before incorporating them.

Leverage motion deliberately. Think about where and if animation can serve the subject: a page-load sequence, a scroll-triggered reveal, hover micro-interactions, ambient atmosphere. An orchestrated moment usually lands harder than scattered effects; choose what the direction calls for. However, sometimes less is more, and extra animation contributes to the feeling that the design is AI-generated.

Match complexity to the vision. Maximalist directions need elaborate execution; minimal directions need precision in spacing, type, and detail. Elegance is executing the chosen vision well.

Consider written content carefully. Often a design brief may not contain real content, and it's up to you to come up with copy. Copy can make a design feel as templated as the design itself. See the below section on writing for more guidance.

## Your first idea is the average — and there are two averages

AI-generated design right now clusters around three looks: (1) a warm cream background (near #F4F1EA) with a high-contrast serif display and a terracotta accent; (2) a near-black background with a single bright acid-green or vermilion accent; (3) a broadsheet-style layout with hairline rules, zero border-radius, and dense newspaper-like columns. All three are legitimate for some briefs, but they are defaults rather than choices, and they appear regardless of subject.

The trap is that there is a **second** average, and it is the more dangerous one. Past the generic-AI mean (Inter, purple-on-white gradients, centered single column, three equal cards) sits the **designer-trend mean**: oversized condensed caps, dark mode plus grain, monospace "vibes" microtext, sticker badges. Landing on the second is not taste — it is a more flattering average, which is exactly why it slips past.

So: treat your first instinct as the mean and deviate deliberately **toward this product's specific world**, not toward another trend. If the result could be any startup, you shipped the mean. Where the brief pins down a visual direction, follow it exactly — the brief's own words always win, including when it asks for one of these looks. Where it leaves an axis free, don't spend that freedom on a default.

Just like a human designer who's hired, there's often a careful balance between doing what you're good at and taking each project as a chance to experiment and learn.

## Process: brainstorm, explore, plan, critique, build, critique again

Work in two passes. First, brainstorm a short design plan based on the human's design brief: create a compact token system with color, type, layout, and signature. Color: describe the palette as 4–6 named hex values. Type: the typefaces for 2+ roles (a characterful display face that's used with restraint, a complementary body face, and a utility face for captions or data if needed). Layout: a layout concept, using one-sentence prose descriptions and ASCII wireframes to ideate and compare. Signature: the single unique element this page will be remembered by that embodies the brief in an appropriate way.

Then review that plan against the brief before building: if any part of it reads like the generic default you would produce for any similar page (work through a similar prompt to see if you arrive somewhere similar) rather than a choice made for this specific brief — revise that part, say what you changed and why. Only after you've confirmed the relative uniqueness of your design plan should you start to write the code, following the revised plan exactly and deriving every color and type decision from it.

When writing the code, be careful of structuring your CSS selector specificities. It's easy to generate CSS classes that cancel each other out (especially with a type-based selector like .section and a element-based selector like .cta). This can happen often with paddings/margins between sections.

Try to do a lot of this planning and iteration in your thinking, and only show ideas to the user when you have higher confidence it'll delight them.

## Restraint and self-critique

Spend your boldness in one place. Let the signature element be the one memorable thing, keep everything around it quiet and disciplined, and cut any decoration that does not serve the brief. Not taking a risk can be a risk itself! Build to a quality floor without announcing it: responsive down to mobile, visible keyboard focus, reduced motion respected. Critique your own work as you build, taking screenshots if your environment supports it – a picture is worth 1000 tokens. Consider Chanel's advice: before leaving the house, take a look in the mirror and remove one accessory. Human creators have memory and always try to do something new, so if you have a space to quickly jot down notes about what you've tried, it can help you in future passes.

## More on writing in design

Words appear in a design for one reason: to make it easier to understand, and therefore easier to use. They are design material, not decoration. Bring the same intentionality to copy that you would bring to spacing and color. Before writing anything, ask what the design needs to say, and how it can best be said to help the person navigate the experience.

Write from the end user's side of the screen. Name things by what people control and recognize, never by how the system is built. A person manages notifications, not webhook config. Describe what something does in plain terms rather than selling it. Being specific is always better than being clever.

Use active voice as default. A control should say exactly what happens when it's used: "Save changes," not "Submit." An action keeps the same name through the whole flow, so the button that says "Publish" produces a toast that says "Published." The vocabulary of an interface is the signposting for someone navigating the product. Cohesion and consistency are how people learn their way around.

Treat failure and emptiness as moments for direction, not mood. Explain what went wrong and how to fix it, in the interface's voice rather than a person's. Errors don't apologize, and they are never vague about what happened. An empty screen is an invitation to act.

Keep the register conversational and tuned: plain verbs, sentence case, no filler, with tone matched to the brand and the audience. Let each element do exactly one job. A label labels, an example demonstrates, and nothing quietly does double duty.

## References — load what the task needs

Each is self-contained. Read the ones that apply rather than all of them; the point of them being separate files is that a token-system question does not need the philosophy of art direction.

| File | Load when | What is in it |
|---|---|---|
| [references/direction.md](references/direction.md) | **Every design task**, before coding | Purpose, tone, domain and colour world, the signature element, the review bar, and a cross-domain lens (cinema, architecture, marketing, UX, automotive, industrial design) |
| [references/design-system.md](references/design-system.md) | Implementing anything | Token architecture, typography hierarchy, loading order, never letting fonts pop in, graceful loading, chrome that stays still, motion timing, nested radii, colour semantics, backgrounds |
| [references/spatial.md](references/spatial.md) | Composing a layout; a UI "looks off" | The render-then-critique loop, the overflow gate in full, task-order layout, measurable balance, and the layout audit — plus why optimising the audit's *signals* makes a design blander |
| [references/usability.md](references/usability.md) | A UI is hard to use, needs an instruction wall, or is interactive and about to ship | Nielsen's 10 plus interaction heuristics, scored by a separate judge on the rendered UI, into a severity-ranked fix list. Usability is not aesthetics |
| [references/motion.md](references/motion.md) | Anything beyond a single micro-interaction | When a transition earns its keep, style by navigation kind (a slide between peers lies about depth), a duration table, compositor-only mechanics |
| [references/interaction-rules.md](references/interaction-rules.md) | Building a bulk-select, an algorithm explainer, or running a model for assets | Select-all needs its inverse; show the equation and annotate its terms; name the model and its cost |
| [references/philosophy.md](references/philosophy.md) | High-concept work, campaigns, a manifesto | Naming a movement and expressing it visually, with five worked examples |
| [scripts/layout-audit.js](scripts/layout-audit.js) | Auditing a rendered page | Dependency-free, browser-only. Paste into Playwright `browser_evaluate`; returns measured findings **and draws them as an SVG overlay**, so the next screenshot is annotated. Read [references/spatial.md](references/spatial.md) §7 first — it separates the checks that are real defects from the ones that are merely convention |

**Gates are necessary, not sufficient.** Overflow, contrast and tap-target size are facts, and failing one is a real bug. Balance, alignment and spacing rhythm are *conventions* — they measure how closely a layout matches a symmetric, gridded aesthetic, which is the mean you are trying to leave. Never optimise those to a score.

## In this repository

The app under [web/](../../../web/) is React + Tailwind v4. Two things cost time here before, so they are written down:

- **`dark:` follows `prefers-color-scheme` unless you say otherwise.** Tailwind v4 needs `@custom-variant dark (&:where(.dark, .dark *))` declared in the CSS for a class-based toggle to work at all. Without it a theme toggle appears to do nothing while the OS setting silently wins.
- **`bg-transparent` on a `<select>` leaves the dropdown unreadable.** The platform paints the open list, not your CSS, so the options keep the system background against your inherited text colour. Set colours explicitly on `select`, `option`, `input` and `textarea` — including `html.dark select option`.
