---
id: hq-b7b9ac
title: "cli-pane /m: pick a thought from a typeahead when no ID is given"
status: todo
priority: 2
size: s
complexity: low
process: direct
created: 2026-10-09T14:46:50Z
updated: 2026-10-15T08:30:06Z
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
