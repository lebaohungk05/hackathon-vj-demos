# Screenshots

Written **after** the document, never before. A capture taken for a step that later changes is
wasted work you asked someone else to do.

## The brief

Produce one numbered list, in the order the document presents them. Number by section so a
reader of the brief and a reader of the document are looking at the same thing. Per capture:

| Field | Example |
|---|---|
| File name | `45-save-a-copy-1.png` - number, then what it shows, kebab-case |
| Where | `Fabric portal > the Prod workspace` - the product and the path |
| What must be in frame | The specific control, and any value that has to stay legible |
| Redact | Which strings to black out, or "nothing" |
| Staged or live | Whether the form can be opened, filled, captured and cancelled |

Say which captures can be **staged** - a create form for a resource that already exists can be
opened, filled with throwaway values, captured, then cancelled. The UI is identical and nothing
is created. Everything that shows a *result* has to be captured live: a staged screenshot of a
step nobody ran is exactly the failure this whole process exists to catch.

Split a capture in two when one screen carries two decisions. The menu that reveals a command
and the dialog that command opens are two captures, not one.

## The location label

Screenshots are cropped to the part that matters, which routinely crops away the part that says
where you are. An Entra pane and a Fabric admin pane are both a left rail and a list of settings.

So each image carries a small line **above** it naming the product and path -
`Fabric portal > Admin portal > Tenant settings` - while the caption **below** says what to look
at. Two different jobs, two positions.

## Redaction

**Only identifiers.** An early instinct is to black out more; that is wrong, because a screenshot
with the menu path obscured no longer shows the reader where to click.

Black out with a solid box, not a blur:

- **GUIDs** anywhere - workspace ids in the address bar, ids inside connection strings, tenant
  and request ids in error details.
- **Sign-in addresses and tenant names**, unless they are addresses the customer must grant
  access *to* - those are content, and belong in a table as well.
- **Fragments of a subscription id embedded in a host name.** A demo server called
  `demo-prod-1281292b.database.windows.net` ends in the first eight characters of a subscription
  id: black out the suffix, keep the readable stem.
- **Passwords and secrets.** Capture a credentials dialog *before* anything is typed.

Leave visible: menu paths, button labels, field names, branch names, folder names, workspace
names, product names.

The team edition keeps everything except secrets.

## Checking what comes back

For every capture received, compare it against the caption you wrote.

- Caption describes a different screen → **fix the caption**, not the screenshot. The capture
  usually shows the more useful moment. A menu with the command highlighted beats a screen taken
  after the command ran.
- Wrong screen entirely, or the required control is not in frame → ask for a re-shoot, and say
  precisely what is missing.
- Redaction missed → say which string and where, do not silently ship it.

Then rebuild and confirm the image landed: the build should report which files are still
missing, and reading the workbook back should show the expected image count per section.

## Example values in a capture

A screenshot inevitably shows names from your test environment. Where the reader is meant to
choose their own, add a note under that image:

> The workspace name "pbir-dev" is for demonstration purpose only. Please choose an actual name
> for your Dev workspace.

One note under the capture that shows it, not a general disclaimer nobody reads.
