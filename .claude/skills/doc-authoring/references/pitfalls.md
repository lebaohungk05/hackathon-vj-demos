# Pitfalls

Read this before the first build, not after the first failure. Every entry has already cost
hours.

## Excel holds the file

`PermissionError: [Errno 13] Permission denied` on save means the workbook is **open in Excel**.
Windows locks it. Nothing in the code is wrong.

Ask the user to close it, then rebuild. The same lock blocks `git pull`, `git checkout` and `mv`
on that file, so a "corrupt repo" that appeared right after a build is usually just this.

## Encoding on Windows

Printing Japanese sheet names crashes with `UnicodeEncodeError` under cp1252. **The file was
still written correctly** - only the terminal output failed. Do not treat it as a failed build.

Run verification scripts with `PYTHONIOENCODING=utf-8`.

Related: a Python heredoc containing literal Japanese may be decoded as cp1252 before Python
sees it, so a `str.replace` silently matches nothing. Use `\uXXXX` escapes, or write the script
to a file first.

## Style objects are not assignable between cells

`target.fill = source.fill` raises `TypeError: unhashable type: 'StyleProxy'`. Build one
`PatternFill` (or `Font`, `Border`) and assign that object to both cells.

## Long scripts go in a file

A long heredoc in bash breaks on quoting - an apostrophe in prose, a `"` inside a `'''` block,
a `\\"` escape. Write the script to the scratchpad and run it by path. Faster than debugging the
shell, and re-runnable.

## Never undo an edit with `git checkout --`

Reverting a file to test something discards **uncommitted work** on that file. Copy to the
scratchpad and restore from the copy instead. This has destroyed a full rewrite once already.

## Verify by reading back

The write call returning cleanly proves nothing. Load the artifact and assert on it:

```python
wb = openpyxl.load_workbook(path)
for ws in wb:
    print(ws.title, ws.sheet_state, ws.max_row, len(ws._images))
```

Then assert the strings that must survive are present, unchanged and untranslated - the verbatim
line a manager asked for, an account address, a server name. A translation pass that quietly
localises a value the reader is meant to copy is the defect nobody catches by eye.

## Do not rebuild what you did not change

A shared layout module is imported by several documents. Building them all rewrites every file,
and the zip bytes change even when no cell does - which shows up as a diff nobody can explain.

Build only the editions you are working on. If unrelated files change, prove the content is
identical before committing, and revert them if it is:

```python
# compare cell values, fills and row heights between the old and new bytes
```

## Redeploying wipes cached data

Updating a semantic model definition through an API clears its data. Anything downloaded between
the redeploy and the next refresh comes down empty, and the failure surfaces later as an
unrelated-looking error. Refresh after every redeploy, and tell the user when the environment
last changed so they do not work from a stale download.

## Screenshot numbering drifts

Every restructure renumbers captures. Renumber by **section order**, rename the files that
survive instead of re-shooting them, and update both language editions in the same pass. Then let
the build tell you what is missing rather than checking by eye.
