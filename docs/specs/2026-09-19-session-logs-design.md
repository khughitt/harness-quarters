# Session logs: the reading skill and the pre-flow episode tool

Status: approved — user review 2026-09-19 after four revision rounds; implemented on branch session-logs, with the post-implementation review fixes (pasted-content human turns, project-qualified task refs, retired and distinct note-missing counts) folded in
Task: ai-bc49ed
Consumers: obs Task 4 (`obs-e1dd2b`, `baseline.py`) per the approved first-slice plan in the obs checkout, `docs/plans/2026-09-17-first-observability-slice.md`.

## 1. Purpose

Two deliverables, one seam.

1. A skill, `session-logs`, that tells an agent where each coding harness keeps
   its local session store, what the records look like, which records are a
   human speaking and which are injected context, how to find the session
   behind a task, worktree, or commit, and how sessions duplicate on resume.
2. A tool, `agents/bin/session-episodes`, that turns the Claude Code and Codex
   stores plus the projects' task records into source-referenced *pre-flow
   episodes*: one record per `tasks start` whose turn ended, with when it
   ended, whether the task was parked or closed and when, when the next human
   turn came and whether it asked about status. obs's proxy baseline consumes
   that file and computes the incident rate; this tool never computes it.

The lit incident behind `ai-6c8245` is the reference episode: a `tasks start`,
a turn that ended with review outstanding and no park, and a next human turn
that asked "Is the task still executing?".

## 2. Boundaries

| Owner | Has | Does not have |
| --- | --- | --- |
| ai (this spec) | The skill; the episode extractor and its labels; store knowledge written down | The incident predicate, denominators, cutoffs, coverage reporting (obs Task 4) |
| obs | Harness adapters and the content-free sqlite index (slice 2); opencode and Crush adapters (`obs-175b10`); `baseline.py` | Any transcript text, per-command task ids, or turn text — its index contract forbids them, which is why the episode pass lives here |
| ops | `bin/obs-index` until its retirement task lands | New features; nothing here extends it |
| tasks | Lifecycle notes with `harness_session` provenance (`tasks-b07adc`) | — |

`episodes.jsonl` is the only interface between ai and obs. Its fields are the
ones the obs plan's Task 4 test names, plus four the tool adds (`id`,
`anchor_source`, `label_source`, `closure_source`); obs ignores keys it does
not use and rejects a record missing a required one. Only turns proven to have completed are
written (§4.3): harness waits, interruptions, unknown endings and ambiguous
continuations are counted in the run summary and never reach obs, so the
consumer contract needs no change to stay sound — the plan's "prepared input
excludes known legitimate harness waits" is met upstream.

## 3. The skill

`agents/skills/session-logs/SKILL.md`, symlinked from `~/.claude/skills/session-logs`
like `flow`. Sections, in order:

**Stores.** One table, four rows:

| Harness | Store | Unit | Notes |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl` | one JSONL file per session; subagent transcripts are files whose records are all `isSidechain` | `--resume` forks a new uuid that carries the old history: two files, one conversation |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl` | one rollout per session; `session_meta` first | on this host no session has a second rollout (0 of 14,456); `obs-index`'s "fresh rollout per resume" premise is not observed |
| opencode | `~/.local/share/opencode/opencode.db` (sqlite; `opencode-local.db` beside it) | rows, not files | store only; no tooling here until `obs-175b10` |
| Crush | `~/.crush/crush.db` and `<project>/.crush/crush.db` (sqlite) | rows, per project | store only; as above |

**Record shapes.** For Claude Code: `type` in `user`, `assistant`, `system`,
`attachment`, `ai-title`, …; every timed record has `timestamp`, `sessionId`,
`cwd`, `gitBranch`, `uuid`/`parentUuid`; `message.content` is a string or a
list of blocks (`text`, `tool_use`, `tool_result`). For Codex: `session_meta`
(id, cwd, originator, `thread_source`), `response_item` (`message` with role,
`function_call`/`custom_tool_call` with `name` and `arguments`), `event_msg`
(`task_started`, `task_complete`, `user_message`, `token_count`), `turn_context`,
`compacted`. The skill shows one minimal record of each kind that matters and
names the field the reader wants, not the whole schema.

**Human or injected.** Claude: `isMeta`, `isCompactSummary`, `isSidechain`,
`tool_result`-only user records, and text beginning `<` (system reminders, hook
context) are not the human — except a turn beginning `<pasted_content id="…">`,
which is the person pasting (about 5% of recent human turns); its wrapper tags
are stripped and the text inside and after them is the turn. Codex: user messages beginning with `# AGENTS.md`,
`<environment_context>`, `<INSTRUCTIONS>`, `<skills_instruct`, `<turn_aborted>`,
`<permissions`, `<user_shell`, `<collaboration_mode`, or any `<`, are injected.
This is the same list the obs adapters and `obs-index` use; the skill says so
and names both so a divergence is found, not discovered.

**Finding the session behind a thing.** By task id: the task's lifecycle notes
carry `provenance: {"harness_session": "claude-code:<uuid>" | "codex:<uuid>"}`
since 2026-09-17; before that, search *tool-call inputs* for
`tasks start <id>` — never the raw text, which also matches the tasks skill's
own instructions and Codex's AGENTS.md injection (text grep finds 1482 Codex
files; tool-call matching finds the real ones). By worktree: `cwd` on any
timed record (Claude) or `session_meta.cwd` (Codex). By commit: a `Bash`
tool-call input containing `git commit`, then the sha in its result.

**Reading a turn.** A turn is one human record through the assistant's last
record before the next human record; Codex brackets it natively with
`task_started`/`task_complete`. Recipes use `jq`/`python3 -c` one-liners the
agent can paste; nothing is invented that the tool below does not also do.

**Preparing pre-flow episodes.** The recipe: `session-episodes extract`; walk
the candidates file with `show` and `confirm` (a start whose id line is in
the output and attributable is `yes`); review positives and a sample of
negatives with `show`, correct with `label`; re-run `extract`; hand
`episodes.jsonl` to `obs baseline`. It states what the file does
and does not contain (§5) so the agent can say so when handing it over.

## 4. The tool

`agents/bin/session-episodes`, Python 3.11 standard library, invoked by path
like `flow-state`. Tests in `agents/bin/test_session_episodes.py`, pytest,
loading the script the way `test_flow_state.py` does, with synthetic Claude and
Codex fixtures written to a temporary directory. Read-only over every store and
every `tasks/` directory.

```
session-episodes extract  [--since DAYS] [--project PREFIX] [--window-minutes N]
                          [--labels PATH] [--anchors PATH] --out PATH
session-episodes show     <id>        --episodes PATH     # an episode or an unconfirmed candidate
session-episodes confirm  <id> yes|no --episodes PATH [--anchors PATH]
session-episodes label    <id> yes|no --episodes PATH [--labels PATH]
```

`--episodes` is the file `extract` wrote; `show`, `confirm` and `label` read
refs from it and from the candidates file beside it, so they need no store
scan and no registry. `--labels` and `--anchors` default to
`<episodes stem>.labels.jsonl` and `<episodes stem>.anchors.jsonl` beside the
episodes file in every subcommand, and `extract` writes unconfirmed candidates
to `<stem>.candidates.jsonl` there, so the loop `extract → show → confirm /
label → extract` works with the same `--out`/`--episodes` path and nothing
else. Environment: `SESSION_LOGS_CLAUDE`
and `SESSION_LOGS_CODEX` override the store roots (tests use them); the tasks
registry `~/.config/tasks/projects.toml` supplies project roots, as `obs-index`
and obs `stores.py` do.

### 4.1 Population

Every Claude file and Codex rollout on the host is scanned; a file matters
only through the anchors it holds. Excluded, with the reason counted in the
run summary:

- `subagent`: a Claude file with no main-line record; a Codex rollout whose
  `thread_source` is neither absent nor `user`. Per file. A rollout's
  `session_meta` is its first record; a thread forked from another copies the
  parent's `session_meta` in with the parent's history (1,223 of 14,460
  rollouts on this host hold two, 291 of them a subagent's own over a `user`
  parent's), and only the first names the rollout. (Revised 2026-09-19: the
  first implementation took the last, which classified those 291 as user
  threads under the parent's id.)
- `non-interactive`: Claude `entrypoint` not `cli`; Codex `originator` not
  `codex-tui`/`codex_exec` — the `obs-index` `INTERACTIVE` table. Per file.
- `unregistered`: an anchor whose task id's prefix is not a registered
  project. Per anchor. Ownership is the task's, not the shell's: a
  `tasks start lit-…` run from `/tmp` belongs to `lit`, and the file's `cwd`
  is not consulted. (Revised at plan review, 2026-09-19: the draft excluded
  files by `cwd`, which would have dropped such starts.)

Three prefilters decide, before a file's records are decoded, that it
cannot contribute, and each is exact — a skipped file would have held no
anchor, no fork copy of one, and no confirmable transition — so they change
the run's cost and nothing in its output beyond the counts of what was
looked at. In order, cheapest first: `subagent_meta`, a Codex rollout whose
first line is a `session_meta` with a subagent `thread_source` (its header
alone is read); `before_since`, a file whose mtime is earlier than `--since`,
since no record postdates its file's mtime (this is the §9 allowance,
reported); `no_lifecycle_text`, a file whose raw text nowhere matches the
`tasks … start|park|done|drop` shape the anchor and transition regexes
accept, over the JSON line as written (escaped whitespace at any depth,
non-ASCII spaces, quoted `-C` and `--flag` arguments; a match means parse,
not anchor). The summary counts each skip under `skipped`; `files` still
counts every file, and `excluded` still classifies every file, because the
header read settles `subagent` and `entrypoint` the way the full read does.
`malformed_lines` counts only parsed files. Measured 2026-09-19 on a frozen
copy of both stores: identical episodes and candidates, 402 s and 13.4 GB
resident to 130 s and 2.3 GB.

No file is dropped as a duplicate. A Claude `--resume` fork copies the earlier
records under their original identities (`uuid`, tool-call `id`; 6 of 1,028
files on this host share their first record with another file) and rewrites
`sessionId` to the fork's own, so duplication is resolved per anchor, not per
file: an anchor is one episode however many files contain it (§4.2). Its
continuation evidence comes from the files jointly (§4.3): the main-line
`uuid` sequences after the anchor must be prefix-compatible through the
episode's boundary (the next human record, or the end of the shorter file);
files that agree that far are one continuation and the longest supplies the
records past the shorter ones' ends; files that diverge before the boundary
make the episode `ambiguous`, counted and not written. Every file that held
the anchor is listed in the refs. Resolve this continuation before confirming
the anchor: a compatible longer file can supply the result missing from a
shorter copy. Candidates, `show` and confirmation digests use that same
selected file first in their refs. The same rule applies to Codex by `call_id`
should a session ever span two rollouts; none does today (0 of 14,456).
`obs-index`'s "keep the largest file" rule is not used: it cannot show that the
largest file contains the others, and rounding first timestamps can merge
unrelated Claude sessions.

### 4.2 Anchors

**Commands.** The shell text of a tool call is: Claude `Bash` → `input.command`;
Codex `function_call` named `shell`/`exec_command` → the `command` array or
`cmd` string in its JSON `arguments`; Codex `custom_tool_call` → for
*discovery*, the static string literals given to a `cmd` key inside its
JavaScript `input`, in any of the forms observed in September's rollouts: `"cmd": "…"` (243 of 1,112 calls
mentioning a start), bare `cmd: "…"` (782), `cmd: '…'` (7), and a template
literal `` cmd: `…` `` with no `${` (12). A literal is decoded by its own
quoting rules and counts only when it is the *whole* value — followed by `,`
or `}` — so a literal prefix of a concatenation (`"tasks start x" + " …"`) or
a conditional is not a command. A literal is still not an execution: `if
(false) { … exec_command({cmd: "tasks start x"}) }` extracts a start that
never ran. So for *attribution* a custom call is readable only when its
**whole** JavaScript is one of the four single-call forms the store shows
(550 of 555 single-exec wrappers with a start in September): `const r =
await tools.exec_command({…}); text(r.output);`, `text(await
tools.exec_command({…}));`, `text((await tools.exec_command({…})).output);`,
`const r = await tools.exec_command({…}); text(r);`, around an object literal
of scalar properties with one `cmd`. Any other wrapper — a second call, a
variable, a branch, a computed property — is `outside-grammar` for its
output and goes to the note or review routes. A call whose `input` mentions `tasks start`
but yields no literal that way — a `${…}` interpolation (50), a variable, a
concatenation — is counted as `unsupported-wrapper` with its ref (its task
id taken from the id lines in its result when they name one, so it can be
reviewed), never confirmed by its output; a note can still confirm it. Any
other tool is not a command.

**Results.** The paired result is Claude's `tool_result` block with the same
`tool_use_id` (content a string or a list of `text` blocks), Codex's
`function_call_output` (`output` a string, or a JSON string holding
`{"output": …}`) or `custom_tool_call_output` (`output` a list of
`input_text` blocks) with the same `call_id`. The result text is the
concatenation of the blocks.

**Two readings of a command.** For *finding* candidates the tool reads
loosely: heredoc bodies lifted out, quoted strings blanked, a regex over what
is left — so a `tasks start x-000001` inside a string or a data heredoc is a
mention, not a candidate (58 of 1,144 anchors in the first dry run were such
mentions) — plus the *nested* executable text kept aside as candidates of its
own (`reason: nested`): a heredoc fed to `bash`, `sh`, `zsh`, `dash`, `ssh`,
`sudo`, `env`, `nohup`, `eval`, `source` or `.`; a shell's quoted string
argument (`bash -c '…'`, `ssh host "…"`); a double-quoted `$(…)`. For
*confirming* a transition from its own output the tool reads strictly, and
the strict reading accepts exactly one shape: an optional `cd <path> &&`,
then one `tasks [-C path] [--pretty] SUBCOMMAND args…`, an optional trailing
`2>&1` or `2>/dev/null`, and nothing else — no other operator, no
redirection of stdout, no pipe, no second command, no newline, no heredoc.
No token anywhere in the command — the `cd` path, the `-C` argument, a
message, a redirection target — may hold `$` or a backtick: an expansion in
any position can print into the captured output (`tasks -C "$(cat f >&2)"
start X` does), so the check runs over every word before any is skipped.
A Codex custom call is read this way only through a supported whole-wrapper
form (*Commands* above); several `cmd` literals in one call share one output
and are never attributed. The tool does no other shell or JavaScript
interpretation.

**Candidates.** Each `tasks start <id>` found is a candidate for that id:
by the strict reading when the command is a single invocation (so `tasks
start "x-000001"`, `tasks --pretty start x-000001` and `tasks -C p start
x-000001` are found), else by the loose reading, whose regex accepts the
same `-C`/`--pretty` forms and keeps a quoted string that is exactly one
task id. Transitions (§4.4) are found the same two ways. The match proves nothing by itself — `echo "tasks
start x-000001"` and `false && tasks start x-000001` both match — so a
candidate becomes an anchor only when the start is corroborated by one of,
tried in this order. A result containing a line matching `^error:` (the
tasks CLI's failure prefix) blocks every automatic route: contradictory
evidence goes to review as `error-output`.

- **Its own result, when the command is that one invocation.** Every
  id-printing subcommand (`start`, `note`, `edit`, `park`, `done`, `drop`,
  `dep`, `shelve`, `unshelve` — verified against the CLI on 2026-09-19)
  prints exactly one line on success: `{"id": "<id>", "warnings": […]}`, or
  the bare id under `--pretty`. When the command's strict reading is `tasks
  start <this id>`, nothing else could have printed, so one id line for the
  task (a bare-id line only under `--pretty`) is proof: `tasks start X`,
  `cd /w && tasks start X`, `tasks start X 2>&1`, `tasks start X --pretty`
  confirm; the same with an empty or unrelated output is `no-id-line`;
  anything the strict reading rejects — `tasks start X >/dev/null`, `tasks
  start X 2>&1 | tail -1`, `just setup && tasks start X`, `tasks start X &&
  git add tasks`, `false && …`, `…; cat saved.jsonl`, `…; MODE=x cat
  saved.jsonl`, a `printf` that formats an id object, `… | grep --regexp=id
  saved.jsonl`, `…; tasks note X checked >&2`, a loop, a heredoc, a `$(…)` —
  is `outside-grammar` however many id lines the output holds. Surrounding
  commands are not interpreted; a start in such a command is corroborated by
  a note or by review. `anchor_source: result`.
- **A lifecycle note.** A `started` or `resumed` note in the task record
  within 120 s of the call whose provenance `harness_session` is one of the
  anchor's candidate sessions (§4.7). `anchor_source: note`.
- **Not a route: the `started:` stamp alone.** The record's `started:` field
  is the task's first start and survives resumes, but it proves the task
  started, not that *this* call started it — a second session's failed
  attempt seconds later matches it just as well. Within 120 s of the call it
  is written on the candidate as `stamp_delta_s`, a hint for the reviewer
  (315 of 922 candidates in the dry run carry one).
- **Not a route: exit-status inference from `>/dev/null && …`.** It was
  tried and withdrawn: `tasks start X >/dev/null 2>&1 && true; printf after`
  prints after a failed start, and a harness envelope (`Script completed …
  Output:`) is not command output, so "any output means the start exited 0"
  holds for neither the control flow nor the provenance. Discarded-output
  starts — most often `tasks start X >/dev/null && …` — go to review with the
  stamp hint.

- **A reviewed confirmation.** Historical wrappers the two rules above cannot
  read are common enough to matter — the lit reference anchor itself is a
  `Promise.all` of three literals, the start beside inspection commands with
  pipes and `|| true`, no stamped note — and the parser is not extended for
  them. Instead `extract` writes every uncorroborated candidate to
  `<stem>.candidates.jsonl` (`id` as §4.7 computes it, `task_id`, `reason` ∈
  `outside-grammar | no-id-line | error-output | nested | unsupported-wrapper`,
  candidate sessions, `call_at`, `stamp_delta_s`, refs), `show <id>` prints its command literals and result text,
  and `confirm <id> yes|no` appends `{"id", "confirmed", "evidence_digest",
  "confirmed_at"}` to the anchors file, `evidence_digest` being the first 12
  hex digits of SHA-256 over the command text and result text `show` printed.
  On the next `extract`, a candidate with a matching `confirmed: true` record
  is an anchor (`anchor_source: reviewed`); a `confirmed: false` record
  retires it from the candidates file; a digest mismatch is counted as
  `stale-confirmation` and ignored. The reviewer's job is the one the rules
  do mechanically: did this start run, on the evidence of this command and
  this output.

An uncorroborated, unreviewed candidate is counted as `unconfirmed-start` by
reason in the summary and is not an episode. Each anchor opens one episode:
`task_id`, `session_key` (§4.7), `started_at` (the call's timestamp, epoch
ms), `anchor_source` ∈ `result | note | reviewed`, and the anchor's refs.

Revised at plan review, 2026-09-19, over two dry runs of the assembled plan
against the real stores: the draft's *linear* form (no pipes at all) and its
two-source ladder left 788 of 1,144 anchors for hand review; a first
relaxation (any pipe, heredocs stripped, the `started:` stamp as a route)
confirmed 777 but could be fooled by `| sed p`, by a printing heredoc and by
a stamp that belonged to another session's start; a second relaxation (filter
names, a `>/dev/null &&` exit-status route) fell to `head -n 2 file`, to
`"$(… | sed p)"` hidden by quote blanking, and to unconditional output after
the chain; a third (a filter-name allowlist over an otherwise open command)
fell to `cat saved.jsonl` as a sibling segment, to `grep -e id file` and
`head 123`, and to a quoted task id the counter could not see; a fourth (a
grammar of "silent" commands plus filters with operand policies) fell to
`MODE=x cat file`, to a `printf` format that assembles an id object, to
`grep --regexp=id file`, and to `>&2` into a captured stderr. Each attempt
was shell interpretation, and shell interpretation has no bottom. The
reviewer's recommendation, adopted here, is to stop: automatic attribution
only for a command that *is* the one `tasks` invocation, note corroboration
or review for everything around it. Under that rule 162 anchors confirm
automatically (35 by result, 127 by note) and 922 go to review — the honest
cost of attribution on this history, with `stamp_delta_s` to order the
queue. The queue is the price of the harness idioms in the history (`tasks
start X >/dev/null && …`, `tasks start X | tail -1`, a start among
inspection commands); the flow rule landed with `ai-6c8245` and provenance
notes since 2026-09-17 make future starts confirm by note. A command that starts two ids yields two anchors. Two anchors
for the same task in one turn collapse to the first; in different turns they
are separate episodes (a resume in the same session is a new start). The same
tool-call id seen in several files is one anchor (§4.1).

### 4.3 Turn end

`ended_at` is the end of the turn containing the anchor, and the turn's
outcome decides whether the episode exists. Only `completed` turns are
written. `wait` (a harness waiting on the user is not a stopped turn; the obs
charter's §4 table says the same), `interrupted`, `unknown` and `ambiguous`
(§4.1) are counted by kind in the summary and not written, because an episode
without proof that the turn ended would otherwise satisfy obs's denominator
on a readable record and an elapsed window alone.

Codex, from the turn's events after the anchor's `task_started`:

- `completed`: the turn's `task_complete`; `ended_at` is its timestamp.
- `interrupted`: `turn_aborted` before any `task_complete`.
- `wait`: the turn's last tool call is `request_user_input` with no output.
- `unknown`: none of the above before the next `task_started` or the end of
  the file; `ended_at` is the turn's last timed record, never a record of a
  later turn.

Claude, from the main-line records after the anchor up to the next human
record or the end of the file:

- `completed`: the last `assistant` record is text only (no `tool_use`
  block) and contains nonempty text; a thinking-only or empty record is not
  completion evidence. A `tool_result` with no assistant record after it proves the tool
  finished, not the turn: that is `unknown`.
- `wait`: the last `assistant` record's pending `tool_use` is
  `AskUserQuestion`, `EnterPlanMode` or `ExitPlanMode` (the tools whose result
  is the human's answer).
- `interrupted`: the next `user` record is the harness's
  `[Request interrupted by user]` marker, or a pending `tool_use` has a
  `tool_result` flagged as interrupted.
- `unknown`: anything else — a pending `tool_use`, a trailing `tool_result`,
  a file that ends mid-turn.

For Claude, `ended_at` is the timestamp of the last `assistant` record in the
turn whatever the outcome; for Codex it is `task_complete` when present and
the turn's last timed record otherwise, as above. An anchor held by several
files is classified over their joint, prefix-compatible continuation (§4.1);
files that diverge before the boundary make it `ambiguous`.

### 4.4 Park and close

`parked_at` and `closed_at` are the earliest corroborated evidence after
`started_at`, each `null` when none exists. Absence of a marker is not
absence of a transition: generated `done`/`dropped` notes date from
2026-09-17 (lit has 19 done tasks, 19 `completed:` stamps, 5 closure notes),
and a note written in a worktree is absent from the main checkout until the
branch merges (this task's own record, today). So three sources are read and
the earliest wins, with `closure_source` naming which supplied `closed_at`:

- **Task-record copies.** The record is read from the project's registered
  root *and* from every path `git -C <root> worktree list --porcelain`
  reports; notes are append-only and timestamped, so the copies' notes are
  unioned. `parked_at`: the first note matching
  `^- (\S+) \([^)]*\): parked \(waiting on `. `closed_at` (`note`): the first
  note whose generated text is `done`, `dropped`, or begins `completed; next
  due`.
- **Confirmed transcript transitions.** A `tasks park|done|drop <id>` command
  in any scanned session, confirmed by §4.2's attribution rule
  (`closure_source: transcript`). Unconfirmed calls are ignored. Its time is
  not the call's: a harness may return the result of `tasks park X …` long
  after issuing it, and the park happened somewhere in `[call_at, result_at]`, the timestamps of the tool call and its
  result record. When a matching lifecycle note exists within that interval
  (plus 120 s) and at or after the episode's `started_at`, the note's timestamp is the transition time and the note is
  the source. Otherwise the interval is the evidence: the transition is
  recorded at `result_at` (it had happened by then), and when the interval
  straddles the episode's cutoff — `call_at ≤ ended_at + N < result_at` — the
  episode's `window_complete` is false, because the tool cannot say which side
  the park fell on. `started_at` uses `call_at`: it is a lower bound for
  `ended_at` and nothing in the proxy measures from it.
- **The `completed:` stamp** (`closure_source: stamp`). It survives only the
  latest closure — a reopen clears it, a recompletion overwrites it, a drop
  never sets it — so it is the last resort, and it is still a real closure
  time.

When a confirmed transcript transition has no note within 120 s in any copy,
the summary counts `note-missing` with both refs; the transition stands (it
was confirmed), and the count tells the reader how much of the history the
notes alone would have lost. A record that cannot be read in any copy makes
`join_class` `unknown`, leaves both fields `null` unless a confirmed transcript
transition supplies one, and is counted.

A park or close *before* `ended_at` (the agent parked mid-turn, then kept
going) is kept as-is; obs's predicate is "within N minutes of `ended_at`" and it
decides.

### 4.5 Next human turn and the label

`next_human_at` is the timestamp of the first human record after `ended_at` in
the same session, `null` when none. `status_question` is:

- `null` when there is no next human turn;
- the reviewed value when the labels file has one for this episode id
  (`label_source: reviewed`);
- otherwise the heuristic (`label_source: heuristic`): true when the turn's
  text, lowercased, matches any of a fixed pattern list kept in the script and
  quoted in the skill — `still (running|executing|going|working)`,
  `is (it|that|this|the task) (still )?(running|done|finished|complete)`,
  `(did|has) (it|that) (finish|complete|stop)`, `\bstatus\b`, `\bprogress\b`,
  `where (are we|is it|did .* (stop|leave off))`, `what('s| is) (left|next|
  happening)`, `(are|is) (you|anything) (still )?(working|running)`. The list
  is a starting point; reviews change it in one place and the change is
  visible in the diff.

`show <id>` prints the anchor command, the turn's last assistant text, and the
next human turn's text, each with its source ref, to the terminal. It is the
only path by which transcript text leaves the stores, and it writes nothing.

`label <id> yes|no` appends `{"id", "status_question", "message_digest",
"labelled_at"}` to the labels file, where `message_digest` is the first 12
hex digits of SHA-256 over the next human turn's text as `show` printed it.
The last line for an id wins. On `extract`, a label applies only when the
episode's current next human turn has the same digest; otherwise the label is
counted as `stale-label`, ignored, and the heuristic applies. Ids are stable
across runs (§4.7), so a label survives re-extraction exactly as long as the
message it judged does.

### 4.6 Window

`window_complete` is true when the park/close evidence covers the whole
interval `[ended_at, ended_at + N minutes]` (`--window-minutes`, default 10,
the charter's N): every task-record copy §4.4 names was readable (a worktree
path the list reports but the tool cannot read makes it false), the
extraction ran at or after `ended_at + N`, and the anchor's own session was
scanned through `ended_at + N` or to its end (so a `tasks park` in that
session inside the window would have been seen). The transcript's length
alone does not make it true — a next human turn one minute after `ended_at`
says nothing about a park at minute six. Otherwise false, and obs excludes the
episode from the denominator. Whether a next human turn was observed is
`next_human_at`, a separate condition obs applies itself.

What this cannot see, stated in the skill: a park or close recorded only on a
branch that was deleted unmerged, by a session whose store is not on this
host. The `note-missing` count (§4.4) is the measured lower bound on that
kind of loss.

### 4.7 Identity and refs

`id` is the first 12 hex digits of SHA-256 over the harness name, the anchor
tool call's own id (Claude `tool_use.id`, Codex `call_id`) and `task_id`. These
survive a Claude resume fork (which changes the session uuid and the file), so
a reviewed label stays attached when a later extraction reads a different file.

`session_key` is the session that *executed* the anchor. A fork rewrites
`sessionId` on the records it copies (verified on `a464b513`/`01b5d3cc`: same
record `uuid`s, different `sessionId`), so the record cannot say. When the
anchor is in one file, `session_key` is that file's session. When it is in
several, the candidates are their sessions, and origin is resolved only by a
stamped `started`/`resumed` note within 120 s naming one of them; otherwise
`session_key` is `null`, the candidates are listed in the summary, and the
episode is `join_class: unknown` — the task join holds but the session does
not, and obs treats explicit nulls as unknown. File mtime is reported as a
hint in the summary and never used.

`source_refs` is the physical evidence, kept apart from identity: a list of
`<harness>:<session-uuid>:<absolute path>#L<1-based line>` strings in the order
anchor, turn end, park, close, next human turn, then any further file that
held the anchor; a task-record source is `tasks:<project>:<path>#L<line>`.
Absolute paths point into the user's home; the file is local evidence for a
local report and the skill says not to paste it anywhere public.

`join_class` is `stamped` when the task record carries a provenance note whose
`harness_session` equals `session_key`, else `inferred` (the anchor was a tool
call, not a stamp), else `unknown` per §4.4.

### 4.8 Run summary

`extract` prints a JSON summary to stderr: files seen per harness, exclusions
by reason, files skipped unparsed by prefilter (§4.1), anchors found, episodes written, label sources, candidates retired
by `confirm no`, `note-missing` (distinct transcript-only transitions), `--since`
and `--window-minutes`, and the stores' roots. That is the input provenance obs
Task 4 publishes; the tool does not write it into `episodes.jsonl`.

## 5. What `episodes.jsonl` contains

One JSON object per line:

```json
{"id": "3f2a9c1d0e7b", "task_id": "lit-1a2b3c", "session_key": "codex:01a0af15-…",
 "started_at": 1758121000000, "ended_at": 1758124995000,
 "parked_at": null, "closed_at": null,
 "next_human_at": 1758125300000, "status_question": true, "label_source": "heuristic",
 "anchor_source": "reviewed", "closure_source": null, "window_complete": true, "join_class": "inferred",
 "source_refs": ["codex:01a0af15-…:/home/…/rollout-….jsonl#L412", "…#L2210", "…#L2214"]}
```

No transcript text, no commands beyond the task id they named, no titles. It is
safe to attach to a task note or an obs report; the source refs are how a
reader gets back to the text, through `show` or the skill's recipes.

## 6. Errors

A malformed JSON line is skipped and counted per file in the summary. A store
root that does not exist is reported and skipped; a registered project whose
`tasks/` is missing is an error, not a silent `unknown`. An unknown episode id
to `show` or `label` exits 2 with the id. A labels file line that is not JSON
or lacks `id` fails the run: the file is small and hand-edited, so fail early.

## 7. Testing

Fixtures build the smallest Claude file and Codex rollout that exercise a rule;
no real transcript is committed. One test per rule:

- commands and results: Claude `Bash`/`tool_result` (string and block
  content); Codex `function_call`+`function_call_output`; Codex
  `custom_tool_call` with a JS `tools.exec_command({cmd: …})` wrapper and
  `custom_tool_call_output` as `input_text` blocks — the lit shape — in each
  literal form (`"cmd":`, bare `cmd:`, single-quoted, template without `${`),
  with two `cmd` strings in one call counted together, and a `${…}` wrapper
  counted as `unsupported-wrapper`.
- structure: quotes blanked (a `|` in quotes is not a pipe), heredoc bodies
  lifted, executable heredocs and `-c` strings kept as nested text, data-only
  `cat > f <<EOF` recognised.
- anchors: confirmed by an attributable id line (JSON, and bare id under
  `--pretty`); confirmed by a `started` note; a discarded-output start is a
  `no-id-line` candidate carrying `stamp_delta_s`; `just setup && tasks start X`
  and `tasks start X 2>&1 | tail -1` confirm; `false && tasks start X; tasks
  show X` and `false && tasks start X; tasks note X` are `unconfirmed-start`;
  every shape the strict reading rejects (34 pinned forms, from `>/dev/null`
  and `| tail -1` through loops, heredocs, `$(…)`, `MODE=x cat`, a `printf`
  format and `>&2`) is `outside-grammar` however many id lines the output
  holds; the twelve reviewer regressions across four rounds run through a
  bash stub and produce no episode; a start inside `bash <<'EOF'` is a `nested`
  candidate; a start inside `python3 - <<'EOF'` or a quoted string is not a
  candidate; a result with an `error:` line is `error-output` even when the
  record's `started:` stamp and another session's note agree on the time;
  the strict reading yields subcommand, task id (quoted or not) and
  `--pretty`, and honours `-C`, `cd … &&`, `2>&1` and `2>/dev/null` only;
  the lit shape — one `custom_tool_call` whose `Promise.all` holds
  `tasks start X`, an inspection literal, and a literal with pipes and `||
  true`, its output starting with X's id line — is an `outside-grammar` candidate,
  becomes an episode with `anchor_source: reviewed` after `confirm yes`, is
  retired after `confirm no`, and is `stale-confirmation` when the output text
  changes; `echo "tasks start …"` and a failed start (no id line)
  are `unconfirmed-start`; text-only mention (skill instructions in a
  `tool_result`, Codex AGENTS.md injection) is not a candidate; `--force`;
  two ids in one command; same task twice in one turn collapses.
- turn outcome: Codex `task_complete`, `turn_aborted`, pending
  `request_user_input`, missing `task_complete` bounded by the next
  `task_started`; Claude text-only last record, pending `AskUserQuestion`,
  `[Request interrupted by user]`, trailing `tool_result` with no assistant
  record after it (`unknown`), other pending `tool_use` (`unknown`); only
  `completed` is written and every other kind is counted; `ended_at` never
  crosses into a later turn.
- park/close: from a park note; from a `done`, `dropped`, or recurrence note;
  from a confirmed transcript `done` with no note (`closure_source:
  transcript`, `note-missing` counted) recorded at `result_at`; a note inside
  the call's interval supplies the time over the call; a lone `tasks park X`
  whose result arrived after `ended_at + N` (the interval straddles the
  cutoff) makes `window_complete` false; from `completed:` alone (`closure_source: stamp`); earliest of
  note/transcript/stamp wins; a note present only in a worktree copy is
  found; before `ended_at` kept.
- label: each heuristic pattern positive; plain follow-up work negative; no
  next turn null; reviewed override wins when the digest matches and is
  `stale-label` when the message changed.
- window: all copies readable, extraction after `ended_at + N`, session
  scanned through the window → true; extraction inside N → false; an
  unreadable worktree copy → false; `join_class: unknown` → false regardless
  of a next human turn.
- population: subagent, non-interactive, unregistered — each counted, none
  written.
- identity and resumes: same input twice gives byte-identical output; adding a
  Claude fork file (same record uuids, rewritten `sessionId`, longer
  continuation) keeps the episode id and its reviewed label, extends the
  continuation from the longer file, lists both files' refs, and sets
  `session_key` to `null` unless a stamped note names one candidate; a fork
  that diverges before the next human record makes the episode `ambiguous`
  and unwritten (a Codex fixture with two rollouts sharing `call_id`s
  exercises the same path).
- CLI: `show`, `confirm` and `label` resolve an episode or candidate from
  `--episodes` and default the labels, anchors and candidates paths beside it.

Acceptance against real data, recorded on the task and not in the tests: run
`extract` over all history; find the lit parent's start (Codex
`01a0af15-98bd-7d83-8d44-56080d74f8e7`, rollout line 44, `lit-f43833`) in the
candidates file as `outside-grammar`, `show` and `confirm yes` it, re-run, and
confirm the episode appears with `anchor_source: reviewed`,
`status_question: true` and the expected refs; confirm the seven
`completed:`-only children get a `closed_at`; hand the file to obs Task 4
(whose report is the measured result).

## 8. Out of scope

opencode and Crush extraction (`obs-175b10` supplies adapters; the skill's
store rows are updated then). Strict flow-era episodes (obs `state.json`).
Retiring `obs-index` (ops). Anything that reads a store over the network or
writes to one. An LLM labeler.

## 9. Open questions

None blocking. `--since` applies to `started_at`; file mtime skips files
early and the summary reports how many (`skipped.before_since`, §4.1). Sampled
data behind §4.3: Claude records carry no `stopReason`, and 96 of the 150
most recent Claude files end on a pending `tool_use`; Codex has 1,699
`task_started` against 1,667 `task_complete` and 14 `turn_aborted` in
September's rollouts, so the unpaired cases are real, not hypothetical.
