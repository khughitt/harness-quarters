# Session-store adapters: one module per harness, agy first

Task `hq-57d68e`, under goal `hq-19bd76`. Status: draft for review, 2026-11-01.

## Intent

The user is adopting Antigravity CLI (agy) beside Claude Code and Codex, and later wants
pi, Crush and opencode at the same level. Their words (2026-10-31 and 2026-11-01): make
new harnesses "well-supported in hq, relay, and the like"; "better compartmentalize /
abstract out harness-specific logic so that it is not spread across many different
places"; aim for parity, and "in cases where it cannot be met, document it clearly in the
harness capabilities".

hq's session tools know only Claude Code and Codex, each through code written for that
harness and spread across files. `docs/runbooks/adding-a-harness.md` section 7 lists about
ten edit points for one new harness: `tools/hq_cli/{sessions,cli,launch,color}.py`,
`tools/hq.toml`, `tools/session_archive/{config,decide,inputs,prune}.py`, and
`agents/bin/session-episodes` (`INTERACTIVE`, `_roots`, `scan_stores`, `turn_after`,
`_session_for`). This work gathers each harness's session-store knowledge into one module,
moves Claude Code and Codex behind it unchanged, and adds agy as the first new harness
through it. hq-963ea4 (pi), hq-ce3ab4 (Crush) and hq-aafc2a (opencode) then reuse it.

## Goals

1. One adapter module per harness holds what hq knows about that harness's session store:
   where its homes are, how to list sessions from native metadata, how to resume one,
   which files the archive captures, and where session-episodes finds transcripts.
2. `hq sessions`, `session-archive` and `session-episodes` iterate a registry of adapters
   instead of branching on harness names. Adding a harness is one module, one registry
   entry, a colour and a launch-flags table, plus that harness's transcript parsing in
   session-episodes.
3. Claude Code and Codex move behind the seam with no change in behaviour: their rows,
   footer segments, launch argv and archive decisions, and `hq sessions --harness
   claude|codex` output, stay byte-identical. Their tests pass with only imports and
   fixture wiring changed; closed-set tests over every home or source
   (`test_tracked_launch_config_matches_the_users_aliases`,
   `test_sources_table_matches_spec`) and unfiltered `hq sessions` fixture expectations
   gain the agy entry (an `absent: agy` footer segment where the fixture has no agy home).
4. agy reaches parity: `hq sessions` lists and resumes agy conversations;
   `session-archive capture` mirrors agy transcripts; `session-episodes` reads them; the
   session-logs skill documents the store.
5. Each place agy cannot match Claude Code and Codex is recorded as a capability fact in
   `facts/capabilities.toml`, with evidence, rather than left implicit.

## Non-goals

- Transcript content parsing as a shared abstraction. obs-f5710b's ownership split
  (revision 3, A10) gives content parsing to obs and location and lifecycle to hq, and
  plans to move session-episodes and the session-logs skill to obs after the flow-trial-1
  readout (2027-02-16). The adapter holds location and lifecycle; session-episodes keeps
  its per-harness parsing in its own file, as today.
- Pruning agy. The agy source is captured with `pruned=False`; pruning waits for obs to
  index agy (obs-b00808) and a separate approval, as the runbook requires for every store.
- obs's agy adapter (obs-b00808), relay's agy adapter (relay-7b8340), and live-state
  settings hygiene (hq-2eba07's manifest).
- A rendered capability matrix (hq-60f715). This work adds facts the matrix will show.
- pi, Crush and opencode adapters (their own tasks).

## Anti-goals

- A second session index or cache in hq. `hq sessions` keeps reading native metadata at
  run time (`docs/notes/2026-10-15-session-discovery-contract.md`).
- A silent fallback. A present home whose metadata is missing, unreadable or at an
  unexpected schema still stops the listing with `SourceError`; an agy schema change is
  reported, not papered over.
- A configuration layer that only renames constants. Paths, argv shapes and exclusion
  rules live as code in the adapter, where the reader that depends on them is.
- Behaviour drift for Claude Code or Codex, including the archive's safety checks and
  the episodes output that feeds obs's baseline.

## Constraints

- **Ownership.** hq owns where stores are and their lifecycle; obs owns content parsing
  (obs-f5710b). session-episodes and the session-logs skill are hq's until that move.
- **session-episodes is a standalone standard-library script** reached through
  `~/.agents/bin`, and its tests run from `agents/bin/`. It may import the adapter package
  by resolving its own real path to the hq checkout; it must fail with a clear error if
  that import fails, never fall back to built-in roots.
- **session-archive's capture contract** (`docs/specs/2026-09-30-session-archive-design.md`):
  it walks regular files under each source root, never follows symlinks, records non-append
  rewrites under `versions/`, and `check_sources()` aborts the whole run (exit 2) when a
  root is missing or a symlink.
- **Tests never read live homes.** Fixtures and temporary directories only, built
  environments per the global Tests rules.
- **Capability facts** are edited in a worktree and read only through
  `tools/harness-facts`; `unknown` is an answer, never a default.
- **Harness names.** The canonical harness slugs (`claude-code`, `codex`, `agy`, ...) are
  declared once: today in `facts/capabilities.toml`'s `harnesses`, and in `harnesses.toml`
  once hq-2eba07 lands (its draft spec moves the list there and names session discovery
  and archiving as out of its scope). An adapter is keyed by its canonical slug and keeps
  no second list: a test asserts every registered adapter's slug is a declared harness,
  read through `tools/harness-facts`. `hq sessions --harness` keeps its short names
  (`claude`, `codex`), which become a display alias on the adapter.
- **The flow-trial-1 gate.** Until the readout (2027-02-16), nothing here may change what
  obs and the trial's verdict tools measure (obs-f5710b, revision 3, change 5).
  session-episodes' default output feeds obs's baseline, so it must stay byte-identical.

## Approaches

1. **One adapter module per harness in hq (chosen by the user, 2026-11-01).** A package
   with one module per harness and a registry; the tools loop over the registry.
   Trade-off: one refactor of three tools now, with Claude Code and Codex behaviour to
   preserve; afterwards a harness is one file.
2. **A declarative per-harness configuration file plus a reader per store format**,
   aligned with hq-2eba07's live-state manifest. Rejected: what differs between harnesses
   is mostly the readers, which stay code, so the file adds indirection without removing
   much. If hq-2eba07's manifest proves useful for paths and argv later, those values can
   move into it.
3. **One more hard-coded branch per tool**, as the runbook describes today. Rejected: it
   is the spreading the user asked to stop.

## Design

### The adapter package

A package `tools/harness_stores/` (name is the builder's call) with one module per
harness (`claude.py`, `codex.py`, `agy.py`) and an `__init__.py` holding the ordered
registry. Each adapter is an object composed of plain functions and data, not a class
hierarchy. It provides:

| Part | Used by | Claude Code / Codex today |
| --- | --- | --- |
| `slug` (canonical, as declared for capability facts) and `alias` for `--harness` and display | hq sessions, archive, facts | `claude-code`/`claude`, `codex`/`codex` |
| `homes(user_home)` → `Home(name, kind, path)` | hq sessions | `sessions.homes()` |
| `list_sessions(home, archived)` → `(sessions, home_notes)`; `exclusion_reasons`, an ordered tuple | hq sessions | `read_claude`, `read_codex`, `Skipped`, footer counts in `cli.collect()` |
| `resume_argv(session, flags)` and `environment(session, base)` | hq sessions `-i` | `launch.argv`, `launch.environment`, `HOME_VARIABLES` |
| `colour` | hq sessions | `color.CLAUDE`, `color.CODEX`, `harness_hue` |
| `archive_sources(user_home)` → `Source` rows, each with a capture selector | session-archive | `config.sources()`, `decide.is_transcript` |
| `prune` hooks (unit listing, deletion protocol, `harness` label) or "not pruned" | session-archive prune | `claude_units`/`codex_units`, `delete_*_unit`, kind branches in `prune.py`, `inputs.py`, `decide.py` |
| `episode_roots(env)` and the episodes harness label | session-episodes | `_roots()`, `scan_stores()` arguments |

The Claude Code and Codex adapters wrap the existing functions; this work moves code,
it does not rewrite readers. `tools/hq.toml` keeps per-home launch flags, gaining
`[homes.agy]`.

`list_sessions` returns every session, excluded ones included as `Session` rows with
`excluded` set, exactly as `read_claude` and `read_codex` do now, so `cli.collect()` can
apply `--here` before counting exclusions (today's order; counting inside the adapter
would change `--here` footers). `home_notes` carries home-wide counts that belong to no
session, such as Claude's skipped history lines. The footer builds each harness's
segment from its adapter's `exclusion_reasons`, in that order, so Claude Code and Codex
segments read as today.

`Session.cwd` becomes `str | None`. A session with no cwd is never kept by `--here`
(`os.path.realpath("")` is the current directory and would match) and cannot be
resumed. `Session.transcript` is the file `-i` checks before launching; nothing assumes
it lies under `Home.path` or is one file per session (Crush and opencode keep SQLite
databases elsewhere).

### session-archive changes

- `Source` gains a capture selector: a predicate on the path relative to the root. Claude
  Code and Codex select everything (today's behaviour). agy selects only transcripts (below).
- Each source is `required` or `optional`. Claude Code and Codex sources are required
  and keep today's rule exactly: a missing or symlinked root aborts the run (exit 2).
- An optional source (agy) is skipped when its root does not exist (`os.path.lexists`
  false) and the manifest has never captured that source on this archive. Home presence
  is not the test: `just link --apply` creates `~/.gemini/antigravity-cli` for its
  `settings.json` link before agy has ever run, leaving the home present and `brain/`
  absent. Once the manifest holds a capture for the source, a missing root aborts as for
  a required source. (My call: an uninstalled or never-used harness must not stop every
  other harness's capture, while a transcript directory that vanishes after capture is
  still the failure the rule exists for.)
- A symlinked root or a symlinked harness home aborts for every source; `check_sources`
  tests `home.is_symlink()` as well as `root.is_symlink()`, since quarantine work
  traverses the home.
- A skipped source is not walked. `capture`'s report gives it an explicit entry
  (`{"skipped": "root absent, never captured"}`, exact shape the builder's), counted as
  healthy, so the run's `ok` and `status` stay true.
- Kind branches in `prune.py`, `inputs.py` and `decide.py` dispatch through the adapter;
  an adapter without prune hooks makes `prune` skip its sources and say so.

### The agy adapter

Facts below were read from this host's store on 2026-11-01 (agy 1.4.12).

- **Home.** One home, `~/.gemini/antigravity-cli`, kind `personal`. No environment
  variable selects another home (none found in the binary's strings or `--help`), so
  `environment()` passes the base environment through.
- **Listing.** `conversation_summaries.db`, table `conversation_summaries`, opened
  `mode=ro`. Columns used: `conversation_id`, `title`, `preview`, `workspace_uris` (JSON
  list of `file://` URIs), `last_modified_time` (text timestamp with nanoseconds and
  offset), `parent_conversation_id`. A missing table
  or column, or a value of the wrong shape, is `SourceError` ("agy's summary schema
  changed"), as for Codex. `history.jsonl` is not used: it names only some conversations
  (7 of 20 here).
- **Row values.** `cwd`: the first entry of `workspace_uris`, parsed with
  `urllib.parse.urlparse` and decoded with `unquote`; it must have scheme `file`, an
  empty or `localhost` host and an absolute path, otherwise `SourceError`. A row whose
  list is empty has `cwd = None` and is excluded as `no workspace`. `recency_ms`: `last_modified_time`. `label`:
  `title`, else `preview`. `transcript`:
  `brain/<id>/.system_generated/logs/transcript_full.jsonl`.
- **Exclusions.** A row with a non-empty `parent_conversation_id` is a subagent
  conversation (`invoke_subagent`; agent names `research` and `self` seen here) and is
  excluded as `non-interactive`. A row whose transcript file is absent is
  `transcript gone`. `exclusion_reasons` is `("non-interactive", "transcript gone",
  "no workspace")`.
  `status`, `killed` and `nesting_depth` drive no rule (my call, for parity: Claude Code
  and Codex have no running-session guard on resume either; `status` can also stay
  `RUNNING` after an abrupt exit). A running conversation is
  listed and resumable, as a running Claude Code or Codex session is today.
- **Headless runs.** `agy -p` conversations may not be distinguishable from interactive
  ones in the summaries (`source` was empty on every row here). The builder probes this in
  an isolated agy home. If they cannot be told apart, they are listed, and a capability
  fact records that agy's session metadata does not mark headless runs.
- **Resume.** `agy [flags] --conversation <id>` in the recorded cwd (`--resume` does not
  exist). `[homes.agy]` in `tools/hq.toml` is `flags = ["--dangerously-skip-permissions"]`,
  matching the user's `ay` alias in the dotfiles.
- **Archive.** Two optional sources, both `pruned=False`:
  - `agy`: root `~/.gemini/antigravity-cli/brain`, selecting only
    `<id>/.system_generated/logs/transcript.jsonl` and `transcript_full.jsonl`.
    `transcript_full.jsonl` kept its prefix while a live session appended to it (one
    observation over several minutes); a rewrite would still be kept under `versions/`.
  - `agy-summaries`: root `~/.gemini/antigravity-cli`, selecting only
    `conversation_summaries.db` (40 KB here, no WAL file beside it). It holds the only
    copy of each conversation's workspace, title and subagent parent, which an archived
    transcript needs to be attributed. SQLite rewrites it in place, so each changed
    capture is a new entry under `versions/`, and a copy that races a write is reported
    `busy` and retried on the next run, as for any file. (My call: small, and without it
    an archive re-read cannot recover agy's cwd.)
  - Not captured, and recorded as a capability fact: `conversations/<id>.db` (agy's
    native SQLite store, 152 MB here, rewritten in place; it holds the per-step model and
    token metadata, and is what `agy --conversation` resumes from); tool outputs too large
    for `transcript_full.jsonl`, which agy spills to `steps/<N>/output.txt` (154 steps,
    16 MB here); and `logs/chunks/` (byte-identical split copies of the two transcripts,
    checked on one conversation), `messages/`, `scratch/` and `task.md`.
- **Episodes.** session-episodes gains an agy reader in its own file.
  - *Selection.* `extract` takes a repeatable `--harness` (`claude-code`, `codex`,
    `agy`); without it the set is Claude Code and Codex, read exactly as today with an
    unchanged stderr summary (my call, from the trial gate; agy sessions all fall inside
    the trial, so the default run loses nothing). `show`, `confirm` and `label` take no
    `--harness`: they dispatch every ref by its harness, `agy:` refs included. Making agy
    part of the default run after the readout is a follow-up for obs-f5710b, which owns
    the tool by then.
  - *Root.* `SESSION_LOGS_AGY` names the agy home (`~/.gemini/antigravity-cli`) by
    default; the reader walks `brain/*/.system_generated/logs/transcript_full.jsonl`.
    An agy transcript is read on its own, with no summaries row needed: a conversation
    is a subagent when it has no `USER_INPUT` step with `source: USER_EXPLICIT` (here,
    all 14 top-level conversations open with one; all 13 subagent conversations have
    none and open with a `SYSTEM_MESSAGE`). So an archived mirror re-parses like a live
    one, and episodes never reads `conversation_summaries.db`. A transcript line that is
    not a JSON step object stops the run with an error naming agy and the file.
  - *Human turn.* A `USER_INPUT` step with `source: USER_EXPLICIT`; the person's text is
    inside `<USER_REQUEST>…</USER_REQUEST>`, and the `<ADDITIONAL_METADATA>` and
    `<USER_SETTINGS_CHANGE>` blocks after it are agy's. Every other step type is the
    harness's.
  - *Tool calls and results.* Calls are `PLANNER_RESPONSE.tool_calls[]` (`name`, `args`;
    shell commands are `run_command` with `args.CommandLine`). agy records no call ids:
    the k-th call of a planner step pairs with the k-th `GENERIC` step after it, and the
    reader derives a call id from the conversation id, the planner step index and k.
    Three cases the pairing must handle, all seen here:
    1. A `run_command` that outlives `WaitMsBeforeAsync` (75 here, including most
       `tasks start` calls): its `GENERIC` step has `status: RUNNING` and content naming
       `background task with task id: <bg-id>`. Its result text and time come from the
       later `SYSTEM_MESSAGE` whose content names `sender=<bg-id>` and `finished with
       result:`. Until that message exists the result is absent, as for a Claude or
       Codex call with no result yet.
    2. A `GENERIC` step with `status: ERROR` (29 here; content `Encountered error in step
       execution: …`) is an error result: `attribute` and `_confirm` treat it as they
       treat an error line today, never as a match.
    3. Fewer `GENERIC` steps than calls (an interrupted or still-running step): the
       unpaired calls have no result.
  - *Turn and outcome.* A turn runs from a human `USER_INPUT` to the step before the next
    one, spanning the controller-wake `SYSTEM_MESSAGE` steps (`[Message] … sender=…`)
    and the planner steps they trigger. Outcome uses the existing vocabulary
    (`completed`, `wait`, `interrupted`, `unknown`) with the Claude reader's rules for
    pending calls: `wait` when the only pending calls are `ask_question` (added to
    `WAIT_TOOLS`); `unknown` when the turn ends with other unpaired calls, a background
    task with no result yet, or an `ERROR_MESSAGE` as its last step; otherwise
    `completed`. agy marks no user interrupt that was seen here, so `interrupted` is
    unused unless the builder finds one.
  - *Provenance.* `agy:<conversation-id>` (tasks-75a0fe).
- **session-logs skill.** A Stores row and record shapes for agy, its human-or-injected
  markers, and how to find the session behind a task id, worktree or commit.

### Capability facts

Each gap found becomes a fact in `facts/capabilities.toml` for agy, with Claude Code and
Codex values where they are known, following the file's existing schema and the README's
probing rules. Expected from what is known now:

- tool results carry a call id (agy: no, positional pairing, and backgrounded commands
  report later in a system message);
- session metadata marks headless runs (agy: unknown until probed);
- transcripts are self-describing (agy: no cwd or title in the transcript; they live in
  `conversation_summaries.db`, which the archive therefore captures);
- the archive holds everything needed to resume or fully re-read a session (agy: no;
  `conversations/<id>.db`, spilled tool outputs and model/token metadata are not
  captured).

The builder names and types the facts; the set grows with what the work finds.

### Coordination with hq-2eba07

hq-2eba07 (doing, draft spec uncommitted) moves the harness list into `harnesses.toml`
and rewrites runbook sections 3 and 4; this work adds facts and rewrites section 7.
Neither waits on the other. Whichever lands second rebases: if hq-2eba07 lands first,
the slug test reads the list through `tools/harness-facts` as before, which by then reads
`harnesses.toml`; new agy facts go under the facts file's existing per-fact tables, which
hq-2eba07 does not change.

### Runbook

`docs/runbooks/adding-a-harness.md` section 7 is rewritten to the adapter route: write the
module, register it, add its colour and launch flags, add its episodes reader and skill
rows, record its gaps as facts.

## Left to the builder

- Package and module names; the adapter's exact shape (a frozen dataclass of callables is
  the obvious fit) and how the registry is ordered.
- How session-episodes locates the package (resolving its real path) and the error text
  when it cannot.
- agy's colour, meeting the contrast rule in `color.py`; `test_harness_hues_are_apart`
  extends from the Claude/Codex pair to every pair of registered colours (OKLab distance
  `>= 0.15`). Display padding.
- Fixture design for agy: a small summaries database and transcripts built in tests,
  covering the three pairing cases, a subagent conversation, a percent-encoded workspace
  URI and an empty workspace list.
- The probe for headless runs, and the exact facts, names and types.
- Commit order: the seam with Claude Code and Codex first, proven by the unchanged
  suites; agy after.
