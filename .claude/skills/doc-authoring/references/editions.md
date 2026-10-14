# The two editions

One source, two renderings. The customer edition is a subset of the team edition in content but
not in effort - cutting is the work.

## Customer edition

**Contains:** title, one-sentence purpose, required role, numbered steps, screenshots, and
nothing else.

**Cut on sight:**

| Cut | Why |
|---|---|
| "In our test we used X" notes | Names your environment next to a step telling the reader to name theirs. Invites the exact copy-paste mistake it was meant to prevent |
| Conclusions about why a design is right | A reader following a procedure reads it as a step they might have missed, and stops |
| Who *cannot* do this | They find out at the step that fails. Listing it up front reads as an accusation |
| Reassurance about what is not affected | Say it once on the summary page, never per sheet |
| Explanations of a mechanism | If the step is right, the mechanism does not matter. If the step is wrong, explaining it will not save the reader |
| Conditional openers - "start at step 1 if you need X, at step 3 if you have it" | Make the reader classify themselves before they have started. Give one path, with the optional steps marked |

**Keep, always:**

- Anything the reader cannot recover from by reading the steps. The test: if this goes wrong,
  does the error message name the cause? If not, the warning stays.
- A destructive choice, at the step where it is made - not in a callout after it.
- A note when a screenshot shows an example value the reader must replace.

**Wording:** short sentences, imperative, one action per step. A step with two verbs is two
steps. Suggest concrete names rather than "name it" - a reader who has to invent a name stops to
invent one.

## Team edition

Everything above, plus what a colleague picking this up in six months needs:

- **Why this mechanism and not the others.** Name the alternatives and what killed each.
- **What failed, with the exact error text.** The searchable string is the valuable part.
- **What was verified and how** - the API call, the command, the number that proved it. A claim
  that "the copy worked" is worth nothing next to "the report rendered 330.15K, which is
  SUM(net_amount) of the Dev database, versus 30.15K in Prod".
- **Costs and limits.** What this costs per week, what it does not scale to, what needs redoing.
- **Open questions**, named as open.

## Parity between languages

Two language editions of the same document must be **block-for-block identical** - same sections,
same number of steps, same number of screenshots. A reader should be able to put them side by
side, and a reviewer who does not read one language should still see that nothing was dropped.

Enforce it in the build, not by eye:

```python
def shape(sections):
    return [(len(blocks), [b[0] for b in blocks]) for _name, blocks in sections]

if shape(built["en"]) != shape(built["ja"]):
    ...  # print the first divergence, exit non-zero
```

Wording is what a translation is for; structure is not. Import every shared constant - server
names, URLs, account addresses, counts - from one module rather than restating them per language.
A value that disagrees between editions is a real defect and an easy one to miss in a language
you do not read.

## Redaction, by edition

The customer edition is the one that leaves the building. See `screenshots.md` for what to black
out in captures; the same list applies to body text:

- **Redact:** GUIDs, sign-in addresses that are not deliberately shared, tenant names,
  subscription-id fragments embedded in host names, anything secret.
- **Never redact:** menu paths, button labels, field names, product names. A screenshot with the
  path blacked out no longer shows the reader where to click, and that is the whole point of it.
- **Deliberately visible:** addresses the customer has to grant access *to*. Those are content,
  not leakage - list them in a table so they can be copied.
