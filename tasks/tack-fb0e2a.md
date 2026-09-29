---
id: tack-fb0e2a
title: Refresh the harness configs' index stat from the harnesses after a switch
status: done
priority: "3"
size: s
complexity: mid
process: direct
owner: main
created: 2026-09-27T13:09:02Z
updated: 2026-09-27T13:19:52Z
started: 2026-09-27T13:15:49Z
completed: 2026-09-27T13:19:52Z
depends: [tack-91fa3a]
parent: tack-de40d0
tags: [hooks]
agent: claude-code/claude-opus-5-5
---

Why: after /model or /effort, git status marks claude/settings*.json (and the Codex picker marks codex/config*.toml) as modified although the filtered content equals the index — a size mismatch git reports without running the clean filter. The mark hides whether real configuration changed; README's manual fix (git add -u -- claude codex) is easy to forget.

Done: one script in .githooks (harness-state-refresh) stages each harness config whose filtered diff is empty (git diff --quiet -- <file> && git add -- <file>) and touches nothing else; it runs against this checkout by its own location, not the cwd, because the hook fires in every project. It exits 0 without staging when .git/index.lock exists: the mark is cosmetic and must never block a turn, and the script says so in its header. Wiring: Claude Code runs it from the event a probe shows fires on both /model and /effort (PostModelSwitch is already wired for claude-provenance; ConfigChange if PostModelSwitch misses effort); Codex runs it from its Stop hook in ~/.codex/hooks.json, the only event it has near a picker write. Record the Codex entry in ai-539508's cutover inventory so the relay cutover carries it.

Check: switch model and effort in Claude, and the model in a Codex session; git status stays clean each time. A real edit (a plugin toggle) still shows M. With a stale index.lock present the hook exits 0 and stages nothing.

Where: .githooks/, claude/settings.json and claude/settings.work.json hooks, ~/.codex/hooks.json, README.md (the size-only residual paragraph).

## Notes

- 2026-09-27T13:15:49Z (main): started
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T13:19:52Z (stat-refresh): probe (Claude Code 2.1.283, tmux session with a --settings hook overlay): /model fires PostModelSwitch (source=command); /effort writes modelSettings.<model>.effortLevel but fires no hook; ConfigChange does not fire on the harness's own writes. Wired Stop in both harnesses instead; rejected PostModelSwitch+Stop as two wirings for a cosmetic mark
- 2026-09-27T13:19:52Z (stat-refresh): done
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T13:19:52Z (stat-refresh): Stop hook .githooks/harness-state-refresh in claude/settings*.json and codex/hooks*.json stages harness configs whose filtered diff is empty (size-only mark), from any cwd, skipping while index.lock is held; tests cover clear, real change left unstaged, and lock skip; README updated; cutover inventory noted on ai-539508
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
