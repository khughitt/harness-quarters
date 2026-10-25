---
id: hq-c5fd83
title: Restore original historical attachments after the verified layout exemption ships
status: todo
priority: 3
size: s
complexity: low
process: direct
created: 2026-10-25T10:54:20Z
updated: 2026-10-25T10:54:30Z
depends: [ops-6e157a]
tags: []
source: hq-c6a149
agent: claude-code
---

Adopting the shared checker (hq-c6a149) required the attachments the layout rule refuses to be represented by portable derivatives. Each original is preserved byte for byte under persistent WORK_ROOT storage; the files this task owns are those its retained: notes list, each with its SHA-256, and each original task carries the placeholder mapping and the raw item's identity. After the implemented attachment policy ships (ops-6e157a) and hq adopts that checker version, verify every raw copy's hash and the current attachment ledger, restore the exact original bytes through tasks detach and tasks attach under the same names, rerun the executing checker, and release each retained file only after its restored attachment is verified. Design completion alone does not trigger restoration.

## Notes

- 2026-10-25T10:54:30Z (feat/ops-check-hq-c6a149): Scratch directory created: host titan, path $WORK_ROOT/hq/hq-c5fd83, purpose exact raw copies of the attachments hq-c6a149 replaces with portable derivatives (one subdirectory per original task) and their manifest; owner task:hq-c5fd83; contents mutable and not yet checkpointed.
