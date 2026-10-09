---
id: hq-ed4ea4
title: "Re-probing procedure: the background child writes its final output and exit status to a file, so a Codex run stays judgeable after its terminal indicator disappears"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-08T23:32:28Z
updated: 2026-10-09T01:29:31Z
depends: []
tags: []
agent: codex
---

README 'Re-probing a fact' asks a did-not-wake verdict to show from the child's own output that it finished, but the procedure never says to capture that output durably. In Codex the running-terminal indicator vanishes and the output with it, so the run becomes inconclusive. Add to the procedure: the probe's background command redirects its output to a file under the probe's scratch dir and appends an exit-status line with a timestamp (cmd > out 2>&1; echo "exit $? $(date -Is)" >> out), and the evidence note records that file's path next to the transcript.

## Notes

- 2026-10-09T01:29:29Z (main): Triage: scoped from feedback report into a README procedure fix.
