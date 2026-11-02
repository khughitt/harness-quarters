# Active-time cutoff calibration

Type: report; hq-b2b50b. Proposed activation: 16 active hours, retaining 500 root
calls, 30 tree spawns and 2 root compactions. Activation awaits user approval.

## Evidence

The user asked for a historic-data cutoff that avoids prematurely stopping valid
long plan executions, suggesting 12 or 16 hours. The filing session's human turn
at 2026-11-02T19:13:47Z states that request; its feedback call and result bind it to
hq-b2b50b. The reported execution replayed as 4.099 active hours, 59 calls, seven
spawns and no compactions. It pauses under four hours and proceeds under every
larger candidate tested.

The comparison reuses `tools/turn_pause/replay.py` and its hook engine from hq
revision `2a868f10e142a98f2f6328146803113aeb53e2b6`. It parses
each tree once and replays five candidate defaults, without refusing calls or
modifying the stores. Script and output are task attachments:

- `tasks/files/hq-b2b50b/active-cutoff-measure.py`
- `tasks/files/hq-b2b50b/active-cutoff-measurement.json`

Run the script from this checkout with `python3
tasks/files/hq-b2b50b/active-cutoff-measure.py`. It reads the local Claude and Codex
stores and obs's read-only child index. A two-root pilot exercised the reported
session and the original runaway controller: 122 files in 5.37 seconds. The full
run read 2,028 roots and 6,596 files in 116.24 seconds, covering turns starting in
[2026-10-02T00:00:00Z, 2026-11-02T20:00:00Z). It yielded 6,005 turns: 3,490 Claude
Code and 2,515 Codex. No explicit-budget turns or unreadable scheduled-prompt
records were reported.

| Active hours per turn | Median | p90 | p99 | p99.9 | Maximum |
| --- | --- | --- | --- | --- | --- |
| Claude Code | 0.051 | 0.411 | 2.761 | 9.549 | 21.101 |
| Codex | 0.070 | 0.487 | 4.164 | 10.195 | 41.643 |

“Time only” counts completed replay states exceeding time while remaining within
all three other limits. “First pause” follows event order and can be time even
when a later call or spawn would also cross its limit.

| Active cutoff | Turns exceeding time | Time only | First pause by time | First pause by calls | First pause by spawns | Total paused |
| --- | --- | --- | --- | --- | --- | --- |
| 4 h | 45 | 27 | 40 | 3 | 9 | 52 |
| 8 h | 13 | 3 | 5 | 8 | 14 | 27 |
| 12 h | 3 | 1 | 2 | 9 | 15 | 26 |
| 16 h | 2 | 1 | 1 | 9 | 16 | 26 |
| 24 h | 1 | 0 | 0 | 9 | 16 | 25 |

No candidate first paused on compactions. The eight-hour combined total is 27,
not 26; the initial task decision note's eight-hour total was an arithmetic error.

## Decision and limits

Use 16 hours. It provides headroom beyond both p99.9 values and the observed
15.655-hour plan execution. Twelve hours pauses the same 26 turns but stops that
execution on time before its 31st spawn at 14.021 active hours. Sixteen hours
lets the more specific spawn limit act. Twenty-four hours removes the sole
independent time-only stop, so it adds less protection against an unattended
long call.

The original 41.643-hour controller still pauses at its 501st root call after
9.857 active hours with either 12 or 16 hours. Its earlier 4.435-hour turn proceeds
at 16 hours. The independent time-only case is a 21.101-hour Claude controller
with 183 calls, 27 spawns and no compactions, paused at 16.104 active hours by the
next hooked call. Its transcript shows ongoing final-review corrections; it is
an extreme duration, not a verified invalid session. Time cannot distinguish
valid long work from a runaway by itself.

This preserves the existing definition of activity, including time with a tool
in flight and short gaps, and the existing strict “above limit” boundary.
Compared with four hours, a low-call, low-spawn runaway may consume up to twelve
additional active hours. This is a conservative tail guard, not a guarantee of
zero false positives. The other limits can still stop valid large executions.

The replay is one host's currently retained stores, not a labelled validity
dataset. Retention, missing descendants in obs's index, copied Claude histories,
and partial turns at the window edges limit inference. The reported session was
already truncated by its real four-hour pause; replay cannot predict work that
would have followed without that pause. Codex compactions remain uncounted;
unrecorded nested calls and calls left in flight until Stop retain the replay's
documented limitations. This window and current replay differ from the frozen
design's original measurement; its numbers remain historical evidence.

## Budget and activation consequences

Budget directives still scale unnamed counters by requested time divided by the
default. With 16 hours, `budget: 12h` means 375 calls, 23 spawns and 2 compactions;
`budget: 48h` means 1,500 calls, 90 spawns and 6 compactions. Named counts override
scaling. No parser, counter or budget algorithm changes are needed.

Changing the live file during an existing turn triggers its `limits-changed`
pause. A fresh genuine user prompt starts a turn with the new defaults. Merge
is a live hook change and requires user approval; the worktree alone does not
activate it. The 2026-11-01 design spec remains the frozen original decision.
