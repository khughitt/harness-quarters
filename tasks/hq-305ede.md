---
id: hq-305ede
title: "Document how to prepare, verify and clean up an isolated Claude Code home for probes and experiments"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-14T10:43:34Z
updated: 2026-10-15T13:05:19Z
depends: []
parent: hq-40a8d0
tags: [feedback, gap, "from:trans"]
agent: codex
---

Why: a scratch Claude Code home (CLAUDE_CONFIG_DIR) is how hq's probes and other projects' experiments run Claude Code without touching live state, and two traps cost a trans live slice (2026-10-14, Claude Code 2.1.296): preference seeding and cleanup used a sibling .claude.json while this version reads and writes .claude.json inside CLAUDE_CONFIG_DIR, so the seed was ignored and generated preferences and their backups were left behind; and after first-run onboarding (theme, terms, directory trust, permission-mode notice) the command-line prompt never reached a conversation (idle session, no transcript, no tool call) until it was typed again.

Done: a short README.md section beside 'Re-probing a fact' on isolated Claude Code homes: the config file lives at $CLAUDE_CONFIG_DIR/.claude.json (cite the Claude Code version it was observed on); seed only the onboarding/account fields a run needs, at that path; finish or pre-seed onboarding, then confirm a real transcript and tool call before treating a seed prompt as run; cleanup removes that file and its preference backups along with copied credentials, after every owned process has stopped. Record the unsubmitted prompt as a single observation (trans says it is specific to that run), not a fact: no capability-fact entry without a probe. just test passes (the pre-commit docs check).

Where to look: trans docs/runbooks/phone-inbox.md (the observation and the corrected supervisor) and docs/notes/2026-10-14-android-live-approval.md; this task's two trans feedback notes; hq docs/notes/2026-10-15-session-discovery-contract.md ('Launch': CLAUDE_CONFIG_DIR and .claude.json); README.md 'Re-probing a fact'; hq-7b65dc's deferred minor (session_store ignores CLAUDE_CONFIG_DIR). Brief: docs/notes/2026-10-15-headless-workers-brief.md.

Original capture: Isolated Claude first-run onboarding can leave an initial command-line prompt unsubmitted. Experiment guidance should finish onboarding and verify a real conversation/tool call before assuming the seed prompt ran. Observed with Claude Code 2.1.296 and a fresh private configuration directory: theme, terms, directory trust and permission-mode notice preceded an idle session with no transcript/tool call; manually entering the same prompt produced the intended tool call and receipt. Prepared preference copy also used a sibling configuration path while this version wrote its config inside the private directory; capture that version-specific path and cleanup contract in capability guidance.

## Notes

- 2026-10-14T12:59:05Z (feedback): feedback from trans: Confirmed isolated Claude preference seeding and cleanup must use the override directory’s actual config file and preference backups; a sibling seed is not read, and cleanup of that sibling leaves generated account preferences behind.
- 2026-10-14T12:59:05Z (feedback): detail from trans: The bounded slice restored the endpoint/process state and removed copied credentials, but generated private preferences and backups remained. Those files were removed manually after verifying all owned processes had stopped. Experiment supervisor now seeds only allowed onboarding/account fields at the actual config path and removes that file plus its preference backups; focused checks cover normal expiry, hangup and restoration failure.
