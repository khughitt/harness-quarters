---
id: tack-de8d97
title: Restore Codex project trust automatically after a checkout drops it
status: todo
priority: 3
size: s
complexity: mid
process: planned
created: 2026-09-28T10:51:24Z
updated: 2026-09-29T09:04:41Z
depends: []
tags: [rules]
agent: claude-code/claude-opus-5-5
---

From the local-layer review: with trust out of the index, a merge, rebase, checkout or clone that writes a new codex/config.toml blob into the main checkout drops the live [projects.*] tables on every host at once (the checkout is shared through Dropbox). README documents a manual save/restore. Wanted: keep the tables in local/ and restore them without a manual step, e.g. the clean filter writes a sidecar and a post-merge/post-checkout hook re-appends it. Needs a design: where the sidecar is refreshed and how stale entries are handled.

## Notes

- 2026-09-29T09:04:41Z (main): Moved off tack-5b608f when it closed: a follow-up to the local layer, not needed for publication.
