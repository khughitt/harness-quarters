# Find and reopen existing context

Scoped 2026-10-10. Ideas: hq-b7b9ac, hq-839083. Goal: hq-65f661.

## Problem

Find a thought or a previous agent conversation without remembering its ID.
These are separate entry points into existing context: a thought picker inside
Claude's pane, and a terminal session list that resumes the correct harness.

## Current behaviour and evidence

- `claude/mods/cli-pane/hooks/register.tsx` already runs `/m <argument>` through
  `mindful show` and renders the result outside model context. Empty `/m` shows
  usage. The same module serves `/tas`; commits 38b6821 and 911a145 supplied the
  pane and SGR handling. Its tests assert process arguments, errors, truncation
  and absence of conversation output.
- mind6-96e1c0 records the user's decision to adopt the `/tas` pane approach.
  Its source thought requests tags and color during discovery. Generated plugin
  types expose `Input.onInput`, `Select.onSelect` and colored `Text`; Select
  options accept only string labels. Mobile has neither Input nor Select.
- A read-only `mindful --json search` sample returned `{row, score, sources}`;
  row contains typed id, title, alias, tag aliases and visual identity/style
  fields. These are not resolved display colors. The existing SGR renderer can
  display CLI colors, but its use alongside selection needs a runtime check.
- Local CLI help offers Claude `--resume <id>` and `codex resume <id>`; Codex's
  native picker has cwd filtering and `--all`. No session was launched.
- `agents/bin/session-episodes` filters on task lifecycle text and excludes
  subagents: its output cannot list all ordinary chats. Its header readers are
  useful starting points, not an established resume contract.
  `tools/session_archive/config.py:sources` distinguishes personal/work homes
  and Codex archived sessions. obs-914269 and research obs-c7d924 already own
  archive-root coverage and thread/file identity questions.

## Constraints

Keep `/m <argument>` working for IDs and aliases, with no prompt insertion or
model turn. The new picker starts from empty `/m`; `/tas` keeps its behavior.
Retain readable tags alongside color, explicit CLI failures, and bounded output.
Do not reimplement mindful's palette. Mobile's limitation must be visible.

A session selection must retain its harness, home and cwd; never silently
resume in a different home or directory. Research uses read-only metadata and
stub launchers. No live resume, host routing changes or full transcript scan.
Reuse obs's identity research; hq owns the launcher, not a second index.

## Alternatives

1. **Extend the existing pane and delegate session launch to native resume —
   current lean.** Bounded search in the pane; a small list/filter/select
   command for sessions, using a proven existing metadata source.
2. **Use only explicit thought IDs and each harness's native picker.** No new
   code, but leaves the requested thought discovery and cross-harness list
   unsolved. Keep as the comparison baseline.
3. **Build a shared search TUI or custom completion/index layer.** Premature:
   the two surfaces have different data and controls. Full-text session search
   remains in the original idea for a later milestone.

## Unanswered questions

- Answered 2026-10-15 (hq-4ba161; see Picker findings): an Input over a
  column of Button rows gives typeahead, readable tags and selection; row color
  waits on mind6-5a8082.
- Answered 2026-10-15 (hq-434be2; see
  `docs/notes/2026-10-15-session-discovery-contract.md`): each harness's own
  list suffices. Claude's `history.jsonl` and Codex's `state_5.sqlite`
  `threads` give id, home, cwd and recency without a transcript scan or a
  second index, and nothing waits on obs-c7d924.
- Answered there too: every home and project by default, newest first, with
  harness/home/`--here`/`--archived` filters. Subagents, exec and SDK runs, and
  pruned transcripts are excluded and counted. A missing cwd is shown and its
  launch refused. The launcher adds the user's per-home permission flags
  (decided 2026-10-15). 491 older Codex rollouts without a row stay open for the
  implementation task.

## Picker findings (hq-4ba161, 2026-10-15)

Probed headlessly under `claude plugin test` (Claude Code 2.1.296, mindful
0.1.0) with a scratch copy of cli-pane and two synthetic thoughts; no live
surface. The kit checks the tree a hook returns, never a surface's paint, so
focus is proven only as the drawn `autoFocus` prop.

- **Interaction.** Empty `/m` opens the pane with an `Input` (`key="query"`,
  `autoFocus`) and no process run. `onInput` runs `mindful --json search
  --limit 10 <query>`; each result is a `plain` `Button` keyed by the thought's
  uid, its children the title, a dim alias and tag chips (`Text`). A press, or
  Enter on an unchanged query (first row), runs `mindful show <alias|uid>` in the
  same pane and replaces the picker, as `/m <ID>` does. A blank query clears the
  rows without running anything. Select is not used: string labels only, no
  highlight callback.
- **Overlapping searches.** The kit lets two `ui.input` acts overlap. Each
  search takes a sequence number and drops an answer that is not the latest;
  without that guard the slower, earlier query's rows win (checked by removing it).
- **Empty and error results.** `[]` draws "No thoughts match."; a non-zero exit
  draws its stderr in red; a run that cannot start draws `mindful: <reason>`.
  A test simulates that start failure with `{ deny }` from its `process.run` hook:
  a throwing hook is skipped and the host's real CLI runs (hq-8b6ae8 fixes the
  existing test that does this).
- **Color source: (b), mindful resolves it.** Search rows carry slot indices,
  and the colors the art draws depend on the active scheme, so a row swatch
  needs a resolved color from mindful: mind6-5a8082. Until it lands, rows carry
  tags only and the picked thought's `show` art supplies color, as today.
- **Mobile.** No `Input`, so no search: the pane says to type `/m <ID>`. Button
  rows with `Text` children do validate on mobile.
- **Boundary.** Unchanged: `/m <argument>` (aliases included) and `/tas`.
  Changed: empty `/m` opens the picker, so its usage test becomes the picker's
  opening test (`/tas` keeps its usage line). Picker state is a second
  `$.state` value in the mod's contract. Tests the implementation carries: the
  opening field, typing to rows, press and Enter to show, empty/failed/blank
  queries, out-of-order answers, the direct path, and mobile's line.

## Proposed decomposition

| Task | Disposition or next result |
| --- | --- |
| hq-b7b9ac | Scoped 2026-10-15: the empty-`/m` picker implementation (s, low, direct) |
| hq-c677ae | Row color from mindful; waits on mind6-5a8082 and hq-b7b9ac |
| hq-4ba161 | Done 2026-10-15: interaction, color source and test boundary under Picker findings |
| hq-839083 | Briefed; retains its source and waits for hq-434be2 |
| hq-434be2 | Done 2026-10-15: native sources and launch contract in `docs/notes/2026-10-15-session-discovery-contract.md` |

Both research tasks belong to hq-65f661. Each result updates this brief and adds
a finding note to its waiting idea before the result's branch merges. Neither follow-up is a
production implementation task; no speculative design task is needed yet.
