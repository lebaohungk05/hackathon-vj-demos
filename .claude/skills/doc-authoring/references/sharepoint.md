# SharePoint

Documents live on SharePoint. The repo holds the source that generates them; SharePoint holds the
thing people open.

## Connector

The Microsoft 365 connector supplies the tools -
`mcp__claude_ai_Microsoft_365__sharepoint_search`, `sharepoint_folder_search`,
`sharepoint_upload_file`, `sharepoint_update_file`, `sharepoint_copy_item`, and
`read_resource` to pull a file's contents.

They are deferred: fetch the schemas with `ToolSearch` before calling them.

If the connector is **not authorised**, say so plainly, tell the user to authorise it in their
claude.ai connector settings, and stop that step. Never invent a link, and never report a
document as published when it was not. Build the file locally, hand over the path, and offer to
upload once the connector is available.

## Before creating anything: search

```
sharepoint_search  →  a document with this name already?
```

If one exists, **edit it rather than creating a second**. The existing file keeps its link, its
version history and its permissions; a duplicate splits the truth in two and the wrong copy is
the one that gets read.

## Editing an existing document

1. Search for it; confirm with the user that it is the right one if more than one matches.
2. Pull it down with `read_resource`, into the scratchpad rather than the repo.
3. **Read it before changing it.** You are about to overwrite someone's work - know what is in
   there. If it was generated from source in a repo, prefer regenerating from that source; if it
   was hand-written, edit in place and preserve everything you did not come to change.
4. Apply the change, verify by reading the file back, then `sharepoint_update_file` to the same
   location so the link survives.

## Publishing a new document

1. Ask where it goes - site and folder. Do not guess a location.
2. Upload with `sharepoint_upload_file`.
3. Return the link, and say which editions and languages were uploaded.

## Rules

- **Only publish when the user says it is final.** A document under review stays local.
- **Both editions never go to the same audience folder.** The team edition holds unredacted
  identifiers and internal reasoning; keep it out of any folder shared with the customer, and say
  which folder each one went to.
- **Never upload a file you have not read back.** Verify locally first - a corrupted or truncated
  build published to SharePoint is worse than no publish, because it looks done.
- **Re-uploading replaces.** Confirm before overwriting a document you did not create in this
  session.
