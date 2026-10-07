---
id: hq-de40d0
title: "Harness configs still read as modified after a model switch: refresh the stat and strip Codex bookkeeping keys"
status: done
priority: "2"
size: s
complexity: mid
process: direct
owner: main
created: 2026-09-27T12:07:23Z
updated: 2026-09-27T13:25:00Z
started: 2026-09-27T13:21:46Z
completed: 2026-09-27T13:25:00Z
depends: []
tags: [hooks]
agent: claude-code/claude-opus-5-5
---

Follow-up to ai-589cdd (the harness-state clean filter, .githooks/harness-state-clean). Two kinds of noise remain in claude/settings*.json and codex/config*.toml; each is a child.

(1) Codex bookkeeping reaches the diff: screen_reader_detection_done under [tui], the [tui.model_availability_nux] counters, and last_updated/last_revision under [marketplaces.*]. The filter strips only top-level model/model_reasoning_effort, so these table keys need a table-aware strip. Hook trusted_hash and project trust_level are real configuration and stay.

(2) After a model or effort switch, git status shows M on a file whose filtered diff is empty: git treats a size mismatch with the index entry as modified without running the clean filter, and update-index --refresh reports 'needs update'. README already documents git add -u -- claude codex as the manual fix; the child automates it from the harnesses.

Neither harness supports config includes (checked 2026-09-21 in ai-589cdd). Observed 2026-09-27: claude/settings.json shows M with git diff --quiet true; codex/config.toml's diff is two bookkeeping hunks plus one real trusted_hash hunk.

Done when both children are done and, after a model switch and a Codex session, git status lists only files with real configuration changes.

## Notes

- 2026-09-27T13:09:02Z (main): scope: scoped; todo goal P2 s mid direct with children  (strip Codex bookkeeping keys, table-aware filter) and  (automate the index-stat refresh: Claude from PostModelSwitch or ConfigChange per probe, Codex from Stop; never blocks on index.lock); README's manual git add -u stays the fallback
- 2026-09-27T13:09:10Z (main): scope: scoped; todo goal P2 s mid direct with children ai-91fa3a (strip Codex bookkeeping keys, table-aware filter) and ai-fb0e2a (automate the index-stat refresh: Claude from PostModelSwitch or ConfigChange per probe, Codex from Stop; never blocks on index.lock); README's manual git add -u stays the fallback
- 2026-09-27T13:20:37Z (main): Both children landed (3f36bf5, d6b4de0). Claude verified end to end: a filtered-empty mark on claude/settings.json cleared by a headless session's Stop. Codex not yet: the new Stop entry needs trusting in a Codex session (it writes a hooks.state trusted_hash to codex/config*.toml); then a Codex model switch plus one turn should leave git status clean. Close after that.
- 2026-09-27T13:21:46Z (main): started
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T13:25:00Z (main): done
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T13:25:00Z (main): Harness configs no longer read as modified after a switch: the filter strips Codex bookkeeping (3f36bf5) and a Stop hook in both harnesses clears the size-only mark (d6b4de0). Verified end to end: a Claude headless turn and a Codex turn (after trusting the new Stop hook, then /model to gpt-6-luna) each cleared a filtered-empty mark; git diff showed no model or bookkeeping keys. Commits the new hook's Codex trust hash.
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
