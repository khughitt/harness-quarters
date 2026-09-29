---
id: tack-bdff6f
title: "retros: list the retro notes across every registered project"
status: done
priority: "2"
size: s
complexity: low
process: direct
owner: main
created: 2026-09-15T01:01:58Z
updated: 2026-09-22T11:28:29Z
started: 2026-09-22T11:03:06Z
completed: 2026-09-22T11:28:29Z
depends: []
parent: tack-756baa
tags: [flow, obs, skills]
source: "mindful:thought:48e70c654fd84c6ab72d3f06b6261683"
agent: claude-code/claude-opus-5
---

Why: every task closed under the flow ends with a retro: note (spec docs/specs/2026-09-15-flow-state-machine-design.md §3.2, verified → closed), two or three lines on what helped or hurt; 16 tasks carry one across ai and obs as of 2026-09-21 (17 notes: obs-03e018 closed twice), and nothing reads them together. The periodic curation pass (ai-c78706, every 30 days, human at the promotion step) needs them in one view.

Decision: the note is the store. Spec §7 left mindful capture or a journal open; both would be a second copy of text the tracker already holds and obs already joins on (obs-a6c7d4 reads gate: and retro: notes from task records), so the listing reads the records and nothing is written elsewhere.

Done: agents/bin/retros prints, across every project in the tasks registry (tasks projects), one entry per retro: note — project, task id, date, title, and the retro text — newest first, with --since <date|Nd> and --project <prefix> filters and --json. Source of the notes: first try the route flow-state already uses — parsed notes from tasks show --json (and tasks list --all-projects --status done for the population) — and write a second Markdown parser only if that route is too slow over every closed task in every project or does not carry the note text whole; record which in a note. A project whose root is unreachable is reported, not skipped silently.

Check: the listing agrees with grep -l '^- .*retro: ' over each registered project's tasks/ (16 tasks, 17 notes, on 2026-09-21); --since 7d returns only the ones dated in that window; a retro that spans continuation lines prints whole. Tests beside the script, as the repo's other agents/bin tools are tested.

## Notes

- 2026-09-22T00:30:22Z (main): scope: scoped; the retro block already exists (flow spec §3.2, 16 retros on record), the note stays the store (spec §7 resolved: no mindful or journal copy, obs joins on task notes), what remained is the cross-project listing that the recurring curation pass ai-c78706 reads; todo P2 s low direct under ai-756baa; brief: docs/notes/2026-09-21-flow-gates-brief.md
- 2026-09-22T11:03:06Z (main): gate: scoped — adopted
- 2026-09-22T11:03:06Z (main): started
  provenance: {"harness_session":"claude-code:0f2dcf45-c26b-4be3-a6d9-06e7b85c1d88","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T11:03:06Z (main): gate: implementing .worktrees/retros
- 2026-09-22T11:09:17Z (feat/retros): route: tasks show, no second parser — tasks list --all-projects (every status, not only done, so a retro on a reopened record is not missed) for the population, then tasks show per id over 16 threads: 2.0s over all 2222 records, 0.16s with --project; serial was 15.5s. The note text arrives whole because the tracker's notes are single-line by construction — a hand-written continuation that is not the provenance JSON fails tasks check with a parse error, so the Check's 'spans continuation lines' case cannot exist on a valid record.
- 2026-09-22T11:28:11Z (feat/retros): gate: verified tree:61075d9eb427c56ce8de341a177a4690af8e44b2 — checks: uv run --with pytest pytest agents/bin .githooks -q 397 passed and the live listing agrees with grep -rl '^- .*retro: ' over every registered root (20 tasks 21 notes) and three mutations of the guarded paths each fail their test; review: important addressed every record is read from its registered root with -C so the listing no longer depends on the checkout, important addressed a failed project listing exits 2 and is tested, important addressed unparsable show output becomes one unreadable warning instead of ending the run, minor addressed warnings are scoped to the project asked for, minor addressed the status vocabulary is read from the roster rather than a hardcoded copy, minor addressed retro_text runs against the gate-note corpus, minor addressed the JSON carries the timestamp it sorted by, minor addressed --since uses the UTC clock, minor addressed argument parsing refuses a flag where a value belongs, minor addressed a repeated flag is refused, minor addressed failures travel as TasksError rather than SystemExit, minor addressed a missing tasks binary exits 2 instead of a traceback, minor addressed an unreadable record names its reason, minor addressed the wrap width counts the indent once, minor addressed the fake tasks falls back to the cwd and omits empty notes as the real one does, minor deferred the status names come from the roster counts map rather than a vocabulary the tracker publishes as one which fails loudly rather than silently; reviewer: claude-code/claude-opus-5
- 2026-09-22T11:28:19Z (feat/retros): retro: two review rounds on a 200-line tool found two important bugs I could not have seen from inside — the cwd-dependent tasks show (the listing differed per checkout) and an untested failure path — and the second round's only important finding was a test gap, not a code bug, which says the first round's fixes were the right shape. Running three mutations against the new tests before the gate was cheap and turned 'I added a test' into 'the test fails without the fix'. Measuring the slow route (15.5s serial, 1.6s over 16 threads) settled the second-parser question in one experiment instead of an argument.
- 2026-09-22T11:28:29Z (feat/retros): done
  provenance: {"harness_session":"claude-code:0f2dcf45-c26b-4be3-a6d9-06e7b85c1d88","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T11:28:29Z (feat/retros): agents/bin/retros lists every retro: note across the tasks registry — newest first with --since, --project and --json, each record read from its registered root; 21 notes over 20 tasks today, matching the grep reference
  provenance: {"harness_session":"claude-code:0f2dcf45-c26b-4be3-a6d9-06e7b85c1d88","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
