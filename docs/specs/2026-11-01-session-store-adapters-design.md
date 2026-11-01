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
3. Claude Code and Codex move behind the seam with no change in behaviour; their existing
   tests pass unchanged (only imports and fixture wiring may change).
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
| `list_sessions(home, archived)` → sessions and per-reason exclusion counts | hq sessions | `read_claude`, `read_codex`, footer counts in `cli.collect()` |
| `resume_argv(session, flags)` and `environment(session, base)` | hq sessions `-i` | `launch.argv`, `launch.environment`, `HOME_VARIABLES` |
| `colour` | hq sessions | `color.CLAUDE`, `color.CODEX`, `harness_hue` |
| `archive_sources(user_home)` → `Source` rows, each with a capture selector | session-archive | `config.sources()`, `decide.is_transcript` |
| `prune` hooks (unit listing, deletion protocol, `harness` label) or "not pruned" | session-archive prune | `claude_units`/`codex_units`, `delete_*_unit`, kind branches in `prune.py`, `inputs.py`, `decide.py` |
| `episode_roots(env)` and the episodes harness label | session-episodes | `_roots()`, `scan_stores()` arguments |

The Claude Code and Codex adapters wrap the existing functions; this work moves code,
it does not rewrite readers. Footer text stays byte-identical for existing homes.
`tools/hq.toml` keeps per-home launch flags, gaining `[homes.agy]`.

### session-archive changes

- `Source` gains a capture selector: a predicate on the path relative to the root. Claude
  Code and Codex select everything (today's behaviour). agy selects only transcripts (below).
- `check_sources()` keeps aborting on a symlinked root, and on a missing root whose
  harness home exists. A source whose whole harness home is absent on a host (agy is not
  installed there) is skipped and named in the run report rather than aborting the run.
  Claude Code and Codex keep today's rule exactly: a missing root aborts. (My call: an
  uninstalled harness should not stop every other harness's capture, but a vanished
  transcript directory under an existing home is still the failure the rule exists for.)
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
- **Row values.** `cwd`: the path of the first `file://` URI in `workspace_uris`; a row
  with none is excluded as `no workspace`. `recency_ms`: `last_modified_time`. `label`:
  `title`, else `preview`. `transcript`:
  `brain/<id>/.system_generated/logs/transcript_full.jsonl`.
- **Exclusions.** A row with a non-empty `parent_conversation_id` is a subagent
  conversation (`invoke_subagent`, agent name `research`) and is excluded as
  `non-interactive`. A row whose transcript file is absent is `transcript gone`.
  `status`, `killed` and `nesting_depth` drive no rule (my call, for parity: Claude Code
  and Codex have no running-session guard on resume either). A running conversation is
  listed and resumable, as a running Claude Code or Codex session is today.
- **Headless runs.** `agy -p` conversations may not be distinguishable from interactive
  ones in the summaries (`source` was empty on every row here). The builder probes this in
  an isolated agy home. If they cannot be told apart, they are listed, and a capability
  fact records that agy's session metadata does not mark headless runs.
- **Resume.** `agy [flags] --conversation <id>` in the recorded cwd (`--resume` does not
  exist). Flags come from `[homes.agy]` in `tools/hq.toml`, matching the user's own agy
  launcher; the builder reads it from the dotfiles or, if there is none, uses `[]`.
- **Archive.** One source: root `~/.gemini/antigravity-cli/brain`, `pruned=False`,
  selecting only `<id>/.system_generated/logs/transcript.jsonl` and
  `transcript_full.jsonl`. Not captured: `logs/chunks/` (byte-identical split copies of
  the two transcripts, checked on one conversation), `steps/`, `messages/`, `scratch/`,
  `task.md`, and `conversations/<id>.db` (agy's native SQLite store, 152 MB here, outside
  the root). `transcript_full.jsonl` kept its prefix while a live session appended to it
  (one observation over several minutes); a rewrite would still be kept under
  `versions/`.
- **Episodes.** session-episodes gains an agy reader in its own file. Until the
  flow-trial-1 readout it runs only when asked (`--harness agy`, or the builder's
  equivalent flag); the default `extract` reads Claude Code and Codex exactly as today,
  with an unchanged stderr summary (my call, from the trial gate; agy sessions all fall
  inside the trial, so the default run loses nothing). When agy is asked for, an agy
  schema change stops that run with an error naming agy. Making agy part of the default
  run after the readout is a follow-up for obs-f5710b, which owns the tool by then.
  - Human turn: a `USER_INPUT` step with `source: USER_EXPLICIT`; the person's text is
    inside `<USER_REQUEST>…</USER_REQUEST>`, and the `<ADDITIONAL_METADATA>` and
    `<USER_SETTINGS_CHANGE>` blocks after it are agy's. `SYSTEM_MESSAGE`, `CHECKPOINT`
    and `ERROR_MESSAGE` steps are injected.
  - Tool calls: `PLANNER_RESPONSE.tool_calls[]` (`name`, `args`; shell commands are
    `run_command` with `args.CommandLine`). agy records no call ids: each call's result is
    the next `GENERIC` step, in order. The reader derives a call id from the conversation
    id and the call's step index and position.
  - Interactive and subagent: from the summaries row of the conversation, as in listing.
  - Provenance: `agy:<conversation-id>` (tasks-75a0fe).
- **session-logs skill.** A Stores row and record shapes for agy, its human-or-injected
  markers, and how to find the session behind a task id, worktree or commit.

### Capability facts

Each gap found becomes a fact in `facts/capabilities.toml` for agy, with Claude Code and
Codex values where they are known, following the file's existing schema and the README's
probing rules. Expected from what is known now:

- tool results carry a call id (agy: no, positional pairing);
- session metadata marks headless runs (agy: unknown until probed);
- the archive holds the harness's native session store (agy: no, transcripts only).

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
- agy's colour (meeting the contrast rule in `color.py`) and display padding.
- Fixture design for agy (a small summaries database and two transcripts built in tests).
- The probe for headless runs, and the exact facts, names and types.
- Commit order: the seam with Claude Code and Codex first, proven by the unchanged
  suites; agy after.
