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

- Can the existing controls show useful color and tags while preserving
  typeahead, focus and selection? hq-4ba161 tests a tiny headless fixture,
  including delayed search responses and empty/error states.
- Which available metadata supplies recency, correct thread identity and
  home/cwd without reading every transcript? hq-434be2 compares existing
  sources and names any prerequisite from obs-c7d924.
- What is the smallest explicit policy for project/home visibility, archived
  or noninteractive rows, and missing cwd? The same session investigation
  recommends it from its evidence; unresolved identity stays explicit.

## Proposed decomposition

| Task | Disposition or next result |
| --- | --- |
| hq-b7b9ac | Briefed; retains its source and waits for hq-4ba161 |
| hq-4ba161 | P2, small, mid complexity, direct: at most 45 minutes; supported picker interaction and verification boundary |
| hq-839083 | Briefed; retains its source and waits for hq-434be2 |
| hq-434be2 | P2, medium, mid complexity, direct: at most 60 minutes/eight metadata samples; source and native launch contract |

Both research tasks belong to hq-65f661. Each result updates this brief and adds
a finding note to its waiting idea in the same commit. Neither follow-up is a
production implementation task; no speculative design task is needed yet.
