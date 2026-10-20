# Session-log acceptance cases

hq-6e5d88, 2026-10-20. A small, replayable case set derived from the
[session-log survey](2026-10-20-session-log-survey.md) (hq-de3e4c) and its
[episode ledger](data/2026-10-20-session-log-survey.jsonl). It judges the
search/show reader proposed in the
[store-reach brief](2026-10-20-session-store-reach-brief.md) §4 alternative 4, and later
evidence-labelled tracing. These are cases and fixtures only: they add no reader, parser,
eval runner or eval record schema. Shared eval records stay with obs-abfcf9, and the
harness-version store samples stay with obs-f5710b. Ten cases cover all seven surveyed
question types. Passing them says nothing about population prevalence or automated trace
precision.

The set is small because each case answers one surveyed question and carries several
distinctions. Three cases share the reconstruct type because they need three different
links:

| Case | Link evidence |
|---|---|
| SL2 | the outputs of one session |
| SL8 | a parent→child session link |
| SL9 | an SDK dispatch, which names a call rather than a session |

Removing any case leaves a required distinction (listed under **Required distinctions**)
uncovered.

## Fixtures and replay

The records live under `tools/fixtures/session-logs/`, in each harness's native format.
Every identifier, path, task id, model name and text in them is synthetic.

| Short | File (under `tools/fixtures/session-logs/`) | Harness, home | Holds |
|---|---|---|---|
| CA | `home/.claude/projects/-w-alpha/c0000000-0000-4000-8000-00000000000a.jsonl` | Claude, personal | a denied then successful park, a request-blob copy, an async Agent dispatch with its queued notice, a typed `/tasks` command, an unknown record kind, a read of the report |
| AG | `home/.claude/projects/-w-alpha/c0000000-0000-4000-8000-00000000000a/subagents/agent-a0000000000000b01.jsonl` | Claude, personal | CA's reviewer child |
| AG meta | `home/.claude/projects/-w-alpha/c0000000-0000-4000-8000-00000000000a/subagents/agent-a0000000000000b01.meta.json` | Claude, personal | the child's dispatch metadata |
| CW | `home/.claude-work/projects/-w-beta/c0000000-0000-4000-8000-00000000000b.jsonl` | Claude, work | two pushes and their pre-push outputs, an injected mention, a request-blob copy |
| CW2 | `home/.claude-work/projects/-w-beta/c0000000-0000-4000-8000-00000000000c.jsonl` | Claude, work | a `--resume` fork of CW: lines 1–3 copied, then a third push |
| XP | `home/.codex/sessions/2026/10/08/rollout-2026-10-08T10-00-00-01900000-0000-7000-8000-0000000000a1.jsonl` | Codex, personal | the controller: injected context, the human ask, `spawn_agent`, wait |
| XC | `home/.codex/sessions/2026/10/08/rollout-2026-10-08T10-00-11-01900000-0000-7000-8000-0000000000c1.jsonl` | Codex, personal | XP's unforked child: an encrypted dispatch and a successful `tasks feedback` |
| XA | `home/.codex/archived_sessions/rollout-2026-09-20T09-00-00-01900000-0000-7000-8000-0000000000a2.jsonl` | Codex, personal, archived | a human turn listing eight review findings beside an AGENTS.md injection that names them |
| XW | `home/.codex-work/sessions/2026/10/10/rollout-2026-10-10T08-00-00-01900000-0000-7000-8000-0000000000b1.jsonl` | Codex, work | a one-turn session in `/w/beta` |
| CD | `degraded/.claude/projects/-w-delta/c0000000-0000-4000-8000-00000000000d.jsonl` | Claude, personal | a malformed line 2; line 3 mentions a cleanup command clipped from absent session `c0000000-0000-4000-8000-00000000000f` (CF) |
| CU | `degraded/.claude-work/projects/-w-delta/c0000000-0000-4000-8000-00000000000e.jsonl` | Claude, work | readable in git; replay makes it unreadable |
| XD | `degraded/.codex/sessions/2026/10/11/rollout-2026-10-11T10-00-00-01900000-0000-7000-8000-0000000000d1.jsonl` | Codex, personal | ends in a partial line 3 with no newline, as a live append leaves it |
| SDK | `captures/sdk-stream.jsonl` | Claude SDK `stream-json` capture | two Agent dispatches whose child events carry `parent_tool_use_id` |

`home/` has five of the six roots, the shape of the surveyed host. There is no
`.codex-work/archived_sessions`. `degraded/` has only `.claude/projects`,
`.claude-work/projects` and `.codex/sessions`. The SDK capture is not a store. A reader
receives it as an explicit file. The repository's `.gitignore` re-includes the fixture
homes' dot-directories, which a global ignore of `.claude` or `.codex` would otherwise
hide from git.

The records follow the formats observed on this host on 2026-10-20 (Claude Code 2.1.x,
Codex CLI 0.163):

- Claude Code writes one record per API content block. Records of one message share
  `message.id` and count `apiBlockIndex` from 0, and each tool result is its own record.
  In these fixtures, multi-block content appears only in `api-request-blob` copies and
  in Codex content and output arrays.
- Prompt records carry `origin.kind`. A typed prompt also carries `promptSource`
  `typed`; a slash-command record carries none.
- A Codex root's `session_meta` has `session_id` equal to its `id`. An unforked child
  (`fork_turns` `none`) has a single `session_meta` whose `session_id` is the parent's.
  A forked child also has a second, inherited `session_meta` whose `payload.id` is the
  parent's (E069); no fixture forks.

The project's other tests build their homes under `tmp_path`. These fixtures are static
files instead, so that a reader in any language can replay them and anyone can inspect
them for private content.

**Replay.** Copy a fixture home to a scratch directory, and set it as `HOME` for the reader
under test. For `degraded/`, also `chmod 000` CU in the copy, because git cannot store an
unreadable file. In shell:

    scratch=$(mktemp -d)
    cp -r tools/fixtures/session-logs/home tools/fixtures/session-logs/degraded "$scratch"/
    chmod 000 "$scratch"/degraded/.claude-work/projects/-w-delta/*.jsonl
    HOME="$scratch"/home <reader> …      # SL1–SL8; SL10 uses "$scratch"/degraded

`materialize()` in `tools/test_session_log_cases.py` does the same in Python. That module
also proves every expected fact and negative below from the fixture bytes alone, with
plain JSON reads; `just test` runs it. Replay as a non-root user. Root reads a mode-0
file, so under root CU becomes a parsed match and SL10's expectation no longer holds. The
self-check then skips only its permission assertion. A reader's acceptance test replays
the fixtures, runs each case's question in its own syntax, and compares the answer with
the expectations here.

## Notation

`CA:4#0` means line 4 of CA, content block 0. Lines count from 1 and blocks from 0, as in
the survey ledger. Roles, evidence kinds and link directions use the survey's terms:

- **Roles:** `human`, `assistant`, `tool_call`, `tool_output`, `injected`, `metadata`,
  plus `dispatch` for a brief delivered to a child. In Claude records, the human role
  follows `origin.kind` where it is recorded. A leading `<` is not the marker.
- **Evidence kinds:** `successful_task_command`, `tool_output_match`, `tool_call_match`,
  `native_metadata`, `textual_mention`.
- **Links:** `child_to_parent` and `parent_to_child` are session links. `sdk_dispatch`
  binds an event to a dispatching tool call, not to a session.

**Outcomes** are `found`, `not_found` (bounded by stated coverage) or `unknown`.
`unavailable` marks evidence that exists but cannot be read.

Each case states the question in the abstract, independent of CLI spelling.

## Cases

| Case | Question type | Surveyed episodes | Fixture | Basis |
|---|---|---|---|---|
| SL1 | Record formats and parser fidelity | E008 | CA | observed; the request-blob copy and the unknown record kind are synthetic |
| SL2 | Reconstruct or verify what happened | E002 | CA | observed shape; synthetic content |
| SL3 | Runtime identity and model attribution | E092, E160 | XP, XC, CA, AG | observed; depth 1, unforked |
| SL4 | Store coverage, retention and availability | E036, E044 | home | observed; the Codex-work session is synthetic |
| SL5 | Recover earlier content | E152, E052, E126 | XA, CW, CW2 | observed; the archived placement and the repeated AGENTS.md phrase are synthetic |
| SL6 | Measure patterns across sessions | E175, E126 | CW, CW2 | observed |
| SL7 | Trace report/task origins | E046 | XC, XP, CA | observed; the parent's plain brief is synthetic |
| SL8 | Reconstruct (parent→child), incidental parent fields | E072, E085, E142 | CA, AG, XC | observed; the human-origin command record is synthetic |
| SL9 | Reconstruct (SDK dispatch) | E107 | SDK | observed |
| SL10 | Coverage of empty matches; unrecoverable content | E104, E142, E001, E036 | degraded | observed failures; unreadable file synthetic |

"Observed" means a surveyed episode needed the distinction, against records of this
shape. "Synthetic" means the fixture covers a shape that no cited episode exercised.
The survey sampled no Codex-work investigation (Method and limits), and its obstacle
tallies record no unreadable file. The parent's plain `spawn_agent` brief was seen in this
host's Codex store while these cases were being derived: a 1,932-character brief, plain
in the parent's arguments and encrypted in the child's `agent_message`. No surveyed
episode used that route.

### SL1 — calls, results and content blocks

**Question.** In CA, list each tool call, its result and their positions. Show the
records a reader does not recognise.

**Expected.**
- Five calls, each paired by call id with one result:

  | Call id | Call | Result | Error |
  |---|---|---|---|
  | `toolu_fx_park1` | `CA:4#0` | `CA:7#0` | yes |
  | `toolu_fx_status` | `CA:5#0` | `CA:6#0` | no |
  | `toolu_fx_park2` | `CA:8#0` | `CA:9#0` | no |
  | `toolu_fx_agent` | `CA:11#0` | `CA:12#0` | no |
  | `toolu_fx_show` | `CA:17#0` | `CA:18#0` | no |

- `CA:3`–`CA:5` are one message, `msg_fx_m1`, with `apiBlockIndex` 0–2: a text block,
  then two calls.
- The two results come back in the reverse record order (`CA:6` before `CA:7`). Pairing
  by position or by adjacency gets this wrong.
- Every assistant record ran `claude-model-a`, as `message.model` and `requestedModel`
  agree.
- `CA:10` is an `api-request-blob`: it re-carries the calls at `CA:10#1` and `CA:10#2`
  with the same ids, and has no uuid or timestamp. It is a copy, not two more calls.
- `CA:16` (`future-record-kind`) appears in a bounded raw or unfiltered stream with its
  line reference. It is not dropped. `CA:13` (`queue-operation`) is metadata.

**Hard negative.** Counting tool_use blocks per file gives seven, not five.

### SL2 — what happened, from outputs rather than inputs

**Question.** Was the attempt to park zz-000001 blocked? Was the claim released
afterwards?

**Expected.** Found.
- The block is the tool output at `CA:7#0` (`is_error`, "hook denied"), paired with the
  call at `CA:4#0`.
- The release is the `successful_task_command` at `CA:8#0`, whose output at `CA:9#0`
  is `{"id":"zz-000001","warnings":[]}`.

**Hard negatives.**
- The call input at `CA:4#0` alone proves neither outcome.
- `CA:2` is an injected `isMeta` system reminder that names zz-000001. It is neither the
  human nor a claim event.
- `CA:10` is not a second attempt.
- CA's human records are `CA:1` and `CA:15`, both `origin.kind` `human`. Only `CA:1` has
  `promptSource` `typed`. `CA:15` is a
  typed `/tasks` command and begins with `<command-message>`. `CA:14` is a task
  notification (`origin.kind` `task-notification`), also beginning with `<`. A rule that
  treats every leading `<` as injected loses `CA:15`, and one that requires
  `promptSource` `typed` loses it too.

### SL3 — runtime model, creation model and controller

**Question.** Which model ran child XC, and which thread controls it? For the Claude
child AG, which model ran it?

**Expected.**
- **XC's models.** Runtime model `codex-model-b`, from `XC:3` `turn_context`, turn
  `turn-c1`. The creation model `codex-model-a` (`XC:1`
  `base_instructions.provenance.model`) is labelled as creation, never as runtime.
  `codex-model-b` in XP's spawn arguments (`XP:7`) is a request. XP itself ran
  `codex-model-a` (`XP:3`).
- **XC's controller.** XP, by `child_to_parent` from `XC:1`
  `source.subagent.thread_spawn.parent_thread_id` (`native_metadata`).
- **AG's models.** Runtime model `claude-model-b`, from its assistant records'
  `message.model`. Two other model values are not runtime evidence:
  - `sonnet` in the dispatch input (`CA:11#0`) and in the child's `.meta.json` is a
    requested alias;
  - `resolvedModel` `claude-model-b` in the launch result (`CA:12`) records what the
    alias resolved to. It is not proof of the model that ran.

**Hard negatives.**
- `XC:1` has `session_id` equal to XP's id. That id is inherited metadata and does not
  identify XC. XC's own id is `payload.id`.
- XC has one `session_meta`, as an unforked child does.

**Limits.**
- At depth 1, `session_id` equals the controller. At depth 2 the two differ, so a reader
  that takes the controller from `session_id` passes SL3 and SL7 here but fails on
  deeper children.
- A forked child carries a second `session_meta` with the parent's id, plus copied parent
  history (E069). A reader that takes the last or every `session_meta` gives such a child
  its parent's identity.

No depth-2 or forked fixture is included.

### SL4 — stores, homes and coverage

**Question.** Which sessions ran in `/w/beta`, in which home? Where is XA stored?

**Expected.**
- `/w/beta` sessions: CW and CW2 (Claude, `work`, from `.claude-work`) and XW (Codex,
  `work`, from `.codex-work/sessions`). Profile comes from the home searched, not from
  the cwd or the investigating session.
- XA is in `.codex/archived_sessions` (Codex, `personal`, archived).
- The listing's coverage names five searched roots and reports
  `.codex-work/archived_sessions` as absent. An absent root is a coverage fact, not an
  error.

**Hard negative.** A reader limited to the default homes, or to sessions with an
interactive preview, misses XW, XA or the subagent AG. That is the brief's §2 gap.

### SL5 — recovering a human turn

**Question.** Recover the user's message that listed the eight review findings. Then
recover the human ask to push in `/w/beta`.

**Expected.** Found in both cases.
- **The findings.** The human match is `XA:5`, found in an archived store. `XA:4` contains
  the same phrase but begins `# AGENTS.md`, so it is `injected`: it appears under that role
  and never as human.
- **The push.** `CW:1` ("Push the branch."). `CW2:1` repeats it with the same uuid `u-w01`
  under a different `sessionId`, so it is copied history from a resume, not a second ask.
  `CW2:4` ("Push again after the fix.") is a distinct human turn.

### SL6 — an aggregate over tool outputs

**Question.** In work-profile sessions, what durations did the pre-push test-fast hook
report?

**Expected.** Three distinct outputs, deduplicated by call id:

| Call id | Session | Output | Result | Duration |
|---|---|---|---|---|
| `toolu_fx_push1` | CW | `CW:3#0` | passed | 41.2 s |
| `toolu_fx_push2` | CW | `CW:6#0` | failed (`is_error`) | 63.0 s |
| `toolu_fx_push3` | CW2 | `CW2:6#0` | passed | 38.9 s |

Five tool_result blocks match. `CW:7#0` (request blob) and `CW2:3#0` (resume copy) repeat
`toolu_fx_push1`. `CW:4` is an injected reminder that mentions pre-push and is no hook
output. The personal home holds none of these.

The answer comes from ordinary JSON processing of the reader's records, for example
filtering to tool outputs in work homes, then grouping by call id with `jq` or Python.
It needs no aggregate verb.

### SL7 — tracing a report to its origin

**Question.** Which session and which human turn originated report zz-0000f1?

**Expected.** Found, as typed evidence links:

1. **The filing.** `successful_task_command` in XC: the call at `XC:5` (`call_fx_file`,
   `tasks feedback … "$(cat fb.txt)" …`), with output at `XC:6` (`exit_code` 0, id
   zz-0000f1). The report id appears only in the output, so a search of tool inputs
   alone cannot anchor it.
2. **The controller.** `child_to_parent`, XC → XP, from `XC:1`
   `thread_spawn.parent_thread_id` (`native_metadata`).
3. **The human turn.** The originating human turn is `XP:6`, the only human record in XP.
4. **The dispatch brief.** In XC (`XC:4`) it is `encrypted_content`, so it is
   unavailable there. Following the controller recovers it from XP's `spawn_agent` call
   (`XP:7`, `call_fx_spawn`). XP's `SubAgentActivity` `started` item (`XP:8`) binds that
   call to XC:
   - its `item.id` equals the spawn `call_id`;
   - its `agent_thread_id` is XC.

   Agent path `/root/filer` (`XP:8`, `XP:9`, `XC:1`) agrees, but that is supporting
   evidence only. A reader that cannot make the binding reports the brief as
   unavailable. It never substitutes the parent's text without the binding.

**Hard negatives.**
- `XP:4` is an AGENTS.md injection that mentions `tasks feedback`.
- `XP:13` is an assistant `textual_mention` ("The worker filed zz-0000f1.").
- `CA:17#0` is `tasks show zz-0000f1`, with the report's title in its output at `CA:18#0`.
  It is the only tool input anywhere that names the id.
- `CA:15` is a human command naming the same id. A read and a human mention are not
  ownership. A trace that returns CA as the origin fails.

### SL8 — parent to child, and fields that only look like parent links

**Question.** Did CA's reviewer finish before the controller was notified?

**Expected.** Found: the child finished 20 s before the notice was delivered, and 1 s
before it was queued.
- **The link.** `parent_to_child`, from the launch result's
  `toolUseResult.agentId` (`CA:12`) to `subagents/agent-a0000000000000b01.jsonl`. The
  child's `.meta.json` `toolUseId` names the dispatching call `toolu_fx_agent`.
- **The times.**
  - The child's last record (`AG:4`) is at 12:02:40Z.
  - The notification is queued at 12:02:41Z (`CA:13`, `queue-operation` `enqueue`).
  - It is delivered at 12:03:00Z as `CA:14`, injected, with `origin.kind`
    `task-notification` and the same content.
- **The child's first record.** `AG:1` is a `user`-type record holding the dispatch
  prompt from `CA:11#0`. Its role is `dispatch`, not `human`.
- **The child's identity.** Every AG record carries `sessionId` CA, the parent's id. The
  child is identified by its `agentId` and its path.

**Hard negatives (incidental parent fields).**
- `parentUuid` in CA's records (for example `CA:2` → `u-a01`) threads messages. It is not
  a parent session, and CA has none.
- `turn_attribution.parent_turn_id` at `XC:2` is a turn pointer, not a session link.
- XP's `session_meta` has no `parent_thread_id`: it is a root.

A parent pointer printed in a tool output is likewise text, not a recorded link (E142's
ruling).

### SL9 — SDK dispatch links

**Question.** In the SDK capture (an explicit file input), which Agent dispatch did each
child write belong to? Which write was refused?

**Expected.** Found.

| Child call | Call line | Dispatch (`sdk_dispatch`) | Result | Outcome |
|---|---|---|---|---|
| `toolu_fx_wA` | `SDK:4` | `toolu_fx_dA` (`SDK:2#0`) | `SDK:7#0` | success |
| `toolu_fx_wB` | `SDK:5` | `toolu_fx_dB` (`SDK:3#0`) | `SDK:6#0` | `is_error`, refused |

Both dispatches' own results are root events, at `SDK:8` and `SDK:9`, with
`parent_tool_use_id` null. Each event holds one content block.

**Hard negatives.**
- Every event shares one `session_id`, so the session cannot separate the children.
- An `sdk_dispatch` link names a tool call. It is never reported as `child_to_parent`.
- Results arrive in a different order from the calls.

### SL10 — empty matches carry their coverage

**Question A.** Search the degraded home for `needle-term`, in every role.

**Expected.** The outcome is `unknown`, never a bare `not_found`. There are zero parsed
matches, and coverage reports:

| Coverage | What the replay reports |
|---|---|
| Searched roots | `.claude/projects`, `.claude-work/projects`, `.codex/sessions` |
| Absent roots | `.codex/archived_sessions`, `.codex-work/sessions`, `.codex-work/archived_sessions` |
| Unreadable file | CU, mode 0 after replay |
| Malformed line | `CD:2`, a complete line that is not JSON |
| Truncated line | `XD:3`, a partial final line with no newline, which a live append can complete later |

The term is in CU, `CD:2` and `XD:3`, so the empty result is not evidence of absence.
A reader may report raw-text hits in those lines separately, labelled unparsed, but never
as parsed matches of a role.

**Question B.** Recover the complete cleanup command that a hook blocked in session CF.

**Expected.** The outcome is `unknown`.
- CF is in no searched root, so it is reported unavailable, with the coverage of
  Question A.
- The only evidence is the `textual_mention` at `CD:3` (assistant), whose command text
  was clipped.
- The answer must not present `rm -rf build/cache` as the recovered command. This is
  E104's outcome.

## Required distinctions

| Distinction | Cases |
|---|---|
| Both harnesses; home routing (personal/work, archived) | SL3, SL4, SL5, SL6, SL7 |
| Historical outputs versus inputs | SL2, SL6, SL7 |
| Call/result pairing, split records and content-block references | SL1, SL6, SL7, SL9 |
| Human versus injected or copied history (by origin, not by a leading `<`) | SL1, SL2, SL5, SL6, SL7, SL8 |
| Runtime versus creation (and requested) model | SL1, SL3 |
| Child→parent, parent→child, SDK dispatch links | SL3, SL7, SL8, SL9 |
| Incidental and inherited parent fields | SL3 (and its forked limit), SL8 |
| Mention versus work ownership | SL2, SL7 |
| Empty match with missing, unreadable, malformed, truncated coverage | SL4, SL10 |
| Unknown outcomes preserved | SL7 (unavailable brief without binding), SL10 |
| Aggregates through ordinary JSON processing | SL6 |

## Checking the cases against their sources

On 2026-10-20 every cited episode's trigger, call, result and outcome reference matched
its source line's SHA-256 on the surveyed host. The episodes are E001, E002, E008, E036,
E044, E046, E052, E069, E072, E085, E092, E104, E107, E126, E142, E152, E160 and E175.
To recheck, resolve each ledger `source` glob beneath that host's home and compare the
line hashes. A changed or missing line is reported as unavailable, as the survey's
"Rechecking the evidence" says.

The fixtures copy no transcript text. They reproduce each episode's record shapes and its
distinction: the field, its position, and what it does or does not prove. Their content
is synthetic.
