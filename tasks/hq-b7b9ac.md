---
id: hq-b7b9ac
title: "cli-pane /m: pick a thought from a typeahead when no ID is given"
status: done
priority: 2
size: s
complexity: low
process: direct
owner: thought-picker-impl
created: 2026-10-09T14:46:50Z
updated: 2026-10-15T09:12:28Z
started: 2026-10-15T08:36:45Z
completed: 2026-10-15T09:12:28Z
depends: []
parent: hq-65f661
tags: [claude]
source: mind6-96e1c0
---

Why: finding a thought for `/m` today needs its ID or alias. The source thought (mindful:thought:5499887366b74519c03214ddaa3aafcc, via mind6-96e1c0) asks for a thought (tag) autocomplete inside Claude Code, with color, in a side panel. The cli-pane mod (claude/mods/cli-pane, 38b6821) already answers `/m <ID>` with `mindful show <ID>` in a pane outside the conversation, as `/tas` does for tasks; the mod API has no dynamic argument completion (`$.command.register` takes a static `argumentHint`), so the picker lives in that pane.

Settled by hq-4ba161 (probe, Claude Code 2.1.296, mindful 0.1.0; do not re-derive): docs/notes/2026-10-10-context-discovery-brief.md "Picker findings", probe sources attached to hq-4ba161 (picker-probe-register.tsx, picker-probe.test.ts, picker-probe-types.d.ts), which pass 9 tests under `claude plugin test`.
- Empty `/m` opens pane `m` with an `Input` (`key="query"`, `autoFocus`) and runs nothing. `onInput` runs `mindful --json search --limit 10 <query>`; each hit is a `plain` `Button` keyed by uid with children: title, dim alias, `#tag` chips (`Text`). Select is not used (string labels, no highlight callback).
- A press, or Enter on an unchanged query (the first row), runs `mindful show <alias|uid>` and shows it in the same pane, replacing the picker; title `/m <alias|uid>`.
- Each search takes a sequence number; an answer that is not the latest is dropped (without it the slower earlier query wins).
- `[]` draws "No thoughts match."; a non-zero exit draws its stderr in red; a run that cannot start draws `mindful: <reason>`; a blank query clears rows and runs nothing.
- Mobile has no `Input`: the pane says to type `/m <ID>`.
- The helpers that take `$` (show, search) must be top-level function declarations: `claude plugin validate` refuses `$` passed to a function declared inside `register`.
- No prompt insertion and no model turn (brief constraint): picking only shows the thought.

Done when: the empty-`/m` picker above is in claude/mods/cli-pane/hooks/register.tsx, with the picker value declared in types/index.d.ts beside `views`; `/m <argument>` (aliases included) and `/tas` (including its empty-argument usage line) behave as today; tests/cli-pane.test.ts replaces the "missing ID shows usage" case for `/m` with the picker's opening test, keeps it for `/tas`, and carries the probe's cases: opening field, typing to rows, press and Enter to show, empty/failed/cannot-start/blank queries, out-of-order answers (simulate a start failure with `{ deny }`, never a throw: a throwing test hook is skipped and the host CLI runs), the direct path, and mobile's line; `just mods` passes and `tsc -p claude/mods/cli-pane` type-checks.

Out of scope: a per-row color swatch (hq-c677ae, after mind6-5a8082 emits a resolved color); the existing cannot-start test's throw (hq-8b6ae8, same file, either order).

Where to look: claude/mods/cli-pane/hooks/register.tsx, hooks/sgr.ts, types/index.d.ts, tests/cli-pane.test.ts; the probe attachments on hq-4ba161; generated types at claude/mods/cli-pane/.claude-plugin/types/claude-code/index.d.ts (InputProps, ButtonProps, Mounted.input/press). Use the plugin-authoring skill.

## Notes

- 2026-10-10T13:27:26Z (main): scope: briefed; hq-4ba161 will verify tags/color and typeahead in the existing pane; preserve nonempty /m arguments and pane-only selection; brief: docs/notes/2026-10-10-context-discovery-brief.md
- 2026-10-15T08:25:35Z (thought-picker): hq-4ba161 answered: build empty /m as an Input over plain Button rows (Select can't style or preview), latest-sequence guard for overlapping searches, show the pick in the same pane; row color waits on mind6-5a8082, mobile shows a type /m <ID> line; tests and boundary in docs/notes/2026-10-10-context-discovery-brief.md (Picker findings), probe sources attached to hq-4ba161
- 2026-10-15T08:30:04Z (main): scope: scoped; the source thought's three asks are answered (pane Input typeahead, color via mind6-5a8082, the existing pane) and hq-4ba161's probe settles approach and tests; body rewritten with done-when; color split to hq-c677ae; brief: docs/notes/2026-10-10-context-discovery-brief.md
- 2026-10-15T08:36:45Z (main): started
  provenance: {"harness_session":"claude-code:580b355d-7f7a-47ff-82fa-b402d867244d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-15T08:36:55Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-15T08:36:55Z (main): arm: flow-trial-1 — unit tack-b7b9ac — flow on
- 2026-10-15T08:36:56Z (thought-picker-impl): resumed
  provenance: {"harness_session":"claude-code:580b355d-7f7a-47ff-82fa-b402d867244d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-15T08:37:18Z (thought-picker-impl): gate: scoped — adopted
- 2026-10-15T08:37:18Z (thought-picker-impl): gate: implementing .worktrees/thought-picker-impl
- 2026-10-15T08:54:08Z (thought-picker-impl): review: impl round 1 — verdict: revise; findings: important 2, minor 7; reviewer: claude-code
- 2026-10-15T09:04:39Z (thought-picker-impl): impl round 1 fixes: typing pauses 200 ms then one search runs at a time (newest text next); show and empty /m drop pending answers; Enter on unsearched text searches at once and shows the first match; -- before terms; mindful's JSON error envelope read as kind: detail; non-row output is a named error; picker attached by a command field
- 2026-10-15T09:10:53Z (thought-picker-impl): review: impl round 2 — verdict: accept; findings: minor 4; reviewer: claude-code
- 2026-10-15T09:12:03Z (thought-picker-impl): gate: verified tree:f1b92520c863779fae670e469f91baf7c5f66628 — checks: just mods (validate + claude plugin test) 26 pass 0 fail and tsc against the 2.1.296 API types exit 0 at this tree. Picker tests were seen failing before the code and 26 targeted mutants each failed at least one test (one redundant recheck removed). rowsOf's contract ran over every thought of the live mindful store via search: 6891 of 6891 rows matched with 0 mismatches. just test not rerun (no Python touched and its one failure is hq-a6454e); review: important addressed late search answer reopened the picker over a shown thought, important addressed every keystroke ran a full mindful search with unbounded overlap, minor addressed a query starting with a dash parsed as an option, minor addressed malformed output and the JSON error envelope shown raw, minor addressed Enter before an answer needed a second Enter, minor addressed picker chosen by array position, minor addressed mobile line hard-coded the command, minor deferred Enter repeats a search already in flight (hq-6bc076), minor deferred no test pins that Enter waits for a running search (hq-6bc076), minor deferred rowsOf passes a null hit and an alias-less tag (hq-6bc076), minor deferred process run start sits outside its try (hq-6bc076), minor deferred null tag aliases dropped silently (hq-6bc076), minor deferred void handlers leave rejections unhandled (hq-6bc076), minor deferred typing during a show can redraw the picker (hq-6bc076), minor deferred hot reload resets the sequence counter (hq-6bc076); reviewer: claude-code/claude-opus-5-5
- 2026-10-15T09:12:27Z (thought-picker-impl): retro: the hq-4ba161 probe made the build quick, but its two synthetic thoughts hid the real cost: a search takes 3.4 s and 620 MB, so per-keystroke search was the main defect. A probe that drives a real CLI should time one real call. Mutation sweeps earned their keep: one caught a press test that passed vacuously, one found a redundant recheck, and adding clock.settle() fixed held-answer tests that passed for the wrong reason. Splicing edits by offsets computed before an earlier replace corrupted the test file once: edit by unique anchors only.
- 2026-10-15T09:12:28Z (thought-picker-impl): done
  provenance: {"harness_session":"claude-code:580b355d-7f7a-47ff-82fa-b402d867244d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-15T09:12:28Z (thought-picker-impl): Empty /m opens a thought picker in its pane: a paused one-at-a-time mindful search drawn as pressable rows with alias and tags; a press or Enter shows the thought in place; late answers never reopen it; mobile says to type /m <ID>. Row color is hq-c677ae (after mind6-5a8082); review minors are hq-6bc076.
  provenance: {"harness_session":"claude-code:580b355d-7f7a-47ff-82fa-b402d867244d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
