# Intake

Ask all of it before writing. Use `AskUserQuestion` so the answers arrive as choices rather than
prose - it is faster for the user and it removes the ambiguity that a free-text answer leaves.

Batch the questions: up to four per call, and do not ask a second round about something you
could have asked in the first.

## Always ask

| # | Question | Options to offer |
|---|---|---|
| 1 | **Audience** | Customer only / Team only / Both (default: both) |
| 2 | **Format** | Excel / Word / PowerPoint - multi-select, several is normal |
| 3 | **Language** | VI / EN / JA / mixed (say which mix) |
| 4 | **Look** | Professional / Minimal / Dense / Match an existing file |
| 5 | **Destination** | New SharePoint document / Update an existing one (get its name or link) |

## Always establish, by asking or by reading the system

These are not preferences, they are facts the document is wrong without.

- **What is the reader trying to achieve**, in one sentence. If you cannot write it, you cannot
  write the document.
- **Who performs each step** - the customer, us, or a shared step. This drives the edition split
  and it changes the wording of every instruction. A handover in the middle of a procedure is
  where procedures stall: if a sequence bounces customer → us → customer, say so up front or
  restructure so it does not.
- **What the reader already has** versus what they must create. Nothing is documented for a
  resource that already exists.
- **What must not be touched.** Production systems, live workspaces, shared repositories. Get
  this explicitly; it constrains every mechanism you can propose.
- **Required role per step.** State only the role that is *needed*. Listing who cannot do it
  reads as an accusation and helps nobody - a reader with the wrong role finds out at the step
  that fails.
- **Scale.** Five items and five hundred items are different documents. Ask for counts, and ask
  whether anything is shared between items.

## Ask again when

- A step turns out not to work as written. Do not paper over it - report what actually happened
  and ask how they want it handled.
- A constraint appears that invalidates a mechanism. Say which mechanism died and offer the
  alternatives with their trade-offs, then let the user choose.
- The manager adds a requirement. Confirm your reading of it before rewriting - a requirement
  relayed second-hand is the most likely thing in the whole process to be misunderstood.

## What never to assume

| Do not assume | Ask or test instead |
|---|---|
| The customer's environment resembles your test one | Ask for counts, versions, and whether features like row-level security are in use |
| A portal menu path from memory | Walk it, or have the user walk it and send the screen |
| That an option in a dialog is available | Options grey out. Have someone open the dialog |
| That the reader is technical | Assume they are not, unless told. It only costs brevity |
| That the format is obvious from the content | A procedure can be a spreadsheet, a document or a deck. Ask |
| That "update the doc" means edit the local copy | It usually means the SharePoint one. Ask which |
