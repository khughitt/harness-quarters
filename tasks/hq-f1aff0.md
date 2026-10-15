---
id: hq-f1aff0
title: "Record pi 1.1.0's exit codes, session-directory default, extension API and context-file reporting as capability facts"
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-10-15T13:04:19Z
updated: 2026-10-15T13:04:19Z
depends: []
parent: hq-40a8d0
tags: []
source: docs/notes/2026-10-15-headless-workers-brief.md
agent: claude-code
---

Question: For pi 1.1.0 in RPC mode through hq's launcher, what exit codes does the process give (normal end, abort, provider/auth failure, killed), where does it write sessions when no --session-dir is given (and does a project .pi/settings.json sessionDir win, since pi reads it before trust), what extension API does a headless run expose (load path, --no-extensions behaviour, events an extension can observe), and does pi report which context files it loaded?
Where to start: docs/notes/2026-10-15-headless-workers-brief.md; pi/probes/rpc-probe.py and README.md 'Re-probing pi'; facts/capabilities.toml (the pi entries from hq-57132d); the installed pi docs (configuration.md 'Agent directory' and 'Context files', environment-variables.md, extensions.md, rpc.md, sessions.md); crew docs/specs/2026-10-13-crew-core-design.md §6.2 and §9, crew src/agent-dir.ts (prepareAgentDir, contextLookup) and src/runtime/pi-rpc.ts (the argv crew passes).
Bound: Read the pinned source and docs first; then one scratch probe run per question in a disposable PI_CODING_AGENT_DIR, session directory and working directory, with the provider and spend bound hq-57132d used. Keep probe code out of the repository unless it extends pi/probes. No template implementation, no change to crew, no pi upgrade, no live home rewiring.
Expected result: facts/capabilities.toml entries for the pi harness (probed, or unknown with a note saying what was missing), passing tools/harness-facts check, with evidence on this task. A recommendation in the brief: which agent-directory files (settings.json keys, models.json, auth) a headless worker needs beyond what crew writes today, or that none are needed. Name any mismatch with crew's contextLookup (pi docs say AGENTS.override.md also replaces CLAUDE.md in the same directory; contextLookup skips only AGENTS.md).
Ideas it wakes: On completion, run tasks note hq-7a69dc --no-reviewed "<finding>" before this result's branch merges. Also note the context-file finding on lore-ba22f3 (its scope note expects this probe).
