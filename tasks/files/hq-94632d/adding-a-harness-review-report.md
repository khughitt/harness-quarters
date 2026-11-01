# Review: docs/runbooks/adding-a-harness.md (landed ee76bbc, hq-90a198)

Reviewer: claude-code/claude-opus-5-5 (hq claims checked directly; ops/lore, relay/tasks
and obs claims checked by three read-only subagents, with the load-bearing ones
spot-checked). Revisions read: hq main 5c933f9, relay 50366c8, tasks d9d5e37, obs da86328,
ops and lore main.

Line numbers refer to the runbook at ee76bbc.

## Overall

Roughly 110 concrete claims checked; about 85 hold. The errors cluster in two kinds:

1. Steps that cannot be done where the runbook says, or by the method it gives
   (superpowers submodule, tt distribution, the tasks fixture, relay adapter normalization,
   per-harness probes).
2. Missing harness enumerations. The three agents found about twenty lists the runbook
   never names, including the shared `cli.toml` vocabulary, which breaks conformance tests
   in relay and obs.

Structural recommendation: no static inventory can list every harness enumeration and stay
accurate. Make discovery the primary step: grep each consumer for the existing slugs
(`claude-code`, `codex`, `opencode`) and the short keys (`claude`, `codex`). Then keep the
document for what grep cannot show: lockstep pairs across repositories, distribution
mechanics (adopt or broadcast, submodule, fixture copy), safety guards, and ordering.

## Important

I1. Superpowers tool mapping cannot land in lore (lines 17, 83-88).
`lore/vendor/superpowers` is a git submodule pinned to github.com/obra/superpowers v7.0.1.
A new `references/<name>-tools.md`, or an edit to `SKILL.md`, is an upstream contribution
(or a fork) followed by a pin bump; it is not a lore commit. The Claude tool list
(`Bash, Read, Write, Edit, Task, TodoWrite`) is also stale. Upstream e7ddc25 pruned the
per-harness mapping tables; `claude-code-tools.md` names `Agent`, not `Task`; and
`codex-tools.md` is no longer a tool mapping.

I2. The shared CLI vocabulary `cli.toml` is never mentioned (sections 5 and 6).
ops `cli.toml` holds:
- the shared `harness` set (line 33);
- the obs `index` and `report` `--harness` enums (lines 997 and 1011);
- the relay `hook`, `install` and `ask` `--harness` enums (lines 2883, 2893 and 2924).

Each project vendors the file byte-identical, adopts changes with `bin/vendored adopt
cli.toml`, and has a conformance test that requires its live parser to equal the rows.
Following the runbook (widen relay `HARNESSES` and the obs `--harness` choices) therefore
fails `tests/test_cli_surface.py` in obs and the equivalent test in relay. The change
starts in ops.

I3. The PreToolUse safety guard and relay subscribers are missing (section 4 "Standard hook
roles"; section 5).
- `ops/hooks/relay-guard` is the PreToolUse command policy. Claude Code and Codex reach it
  through relay subscribers; agy reaches it through `agy/hook`. The runbook's hook roles
  list only SessionStart and Stop, so a harness onboarded by the runbook runs without the
  guard.
- `hq/relay/subscribers.template.json` scopes each subscriber with
  `"harnesses": ["claude-code", "codex"]`: ops-guard, the familiar observer and
  familiar-teardown. A relayed new harness gets none of them until it is added there and
  `just relay-subscribers` is rendered on each host. That puts familiar among the
  consumers too; the runbook names five.
- `ops/bin/relay-guard-probe` produces the evidence JSON that `relay install --evidence`
  consumes. Its `CREDENTIALS`, `HELP_COMMANDS`, `harness_command()` and `--harness`
  choices cover only claude-code and codex. Lines 421-426 do not mention it.

I4. The existing JSON-stdout adapter `agy/hook` is not named (lines 17, 342-346).
`agy/hook` already does what the runbook asks a reader to write:
- it wraps `claude-profile` and `capture-notice` output in agy's `injectSteps` envelope;
- it translates PreToolUse `run_command` into a relay-guard envelope, failing closed;
- it runs a one-shot Stop claim check (a stand-in until ops-33cef9 gives claim-guard
  native agy support).

The depth table's agy row omits it, and so does section 4.

I5. The per-harness probe advice does not fit the facts schema (lines 290-298).
`probe` is a fact-level key (`FACT_KEYS = type, description, probe, harness`), one per fact;
entries cannot carry one. Facts that already have a probe (`controller-wake` and
`controller-wake-kinds` point at `agents/bin/wake-judge`) leave no slot for
`<name>/probes/<script>`. The claim-guard facts need their own route: add a
`judge_<name>` to `wake-judge`'s `JUDGES`. The runbook does not mention `JUDGES`.

I6. The relay adapter boundary is described wrongly (lines 406-411).
- `normalizeEvent` (`src/adapters/index.js`) and `parsePayload` (`src/adapters/payload.js`)
  are shared functions, not adapter fields. `parsePayload` requires a snake_case
  `session_id`, an absolute `cwd`, and a `hook_event_name` that matches the event. A
  camelCase harness therefore needs a change to the shared parser, or a bridge that emits
  snake_case.
- The opencode bridge lives in `integrations/opencode/` (`plugin.js`, `binding.js`,
  `hook.js`, `queue.js`, `window.js`), exported from `package.json`. It is not in
  `src/adapters/opencode.js`, which is only an event table. That table also maps
  `permission.pending` and `session.error`.
- `parseEvidence` (`capabilities.js`) runs before `validateCapabilities`, and
  `validateCapabilities` hard-codes opencode refusals.

I7. Several tasks claims are wrong (lines 436-457).
- `[identity] relay = true` is host configuration (`$XDG_CONFIG_HOME/tasks/config.toml`,
  `src/config.rs`). It is not set per project.
- `tests/fixtures/relay/ancestry.json` is a byte copy of relay's `test/fixtures/ancestry.json`,
  pinned to a relay revision (per its README). Refresh it by copying from relay and
  updating that revision; do not hand-add trees. New null-session chains also need
  `NULL_SESSION_EXPECTED` in `ancestry.rs`. The two copies have already drifted.
- Codex `app-server` is not handled anywhere in tasks. `boundary_scope` returns early for
  every harness except claude-code, and only `CLAUDE_ROLES = [daemon, bg-pty-host]` exists.
- `HARNESS_COMMS` is a fixed-size array (`[(&str, &str); 3]`), so its length must change too.
- Missing lists:
  - `src/relay/snapshot.rs` `HARNESSES: [&str; 3]`: without it, tasks rejects relay
    snapshot rows from the new harness;
  - `src/relay/resolve.rs` `hint_for` and the claude-code-only form of `same_session`;
  - the native claim-identity levels in `src/claims.rs` `identity_from`, and the
    codex-only branch in `proves_ownership`;
  - the `--origin-session` help text and its validation.

I8. Test-run provenance distribution and readers (line 477; section 5 "Test-run provenance").
- `tt` is a broadcast file (`ops/bin/vendored` `BROADCAST`): `vendored publish` /
  `just vendor-publish tt` writes it into every project after the merge. Adoption passes
  cover only `cli.toml`, `cli_surface.py` and `keys.toml`.
- `ops/bin/tt-report` `AGENTS = ("claude", "codex", None)` counts any other agent's runs as
  malformed and skips them. A new `tt.agent_of` key therefore drops that harness's test
  runs from `tt-report` without any warning.
- Further short-key lists: `ops/bin/harness-remap` `HARNESSES`, `ops/bin/obs-index`
  `INTERACTIVE`, and the tasks-tui launch bindings in `ops/keys.toml`.

I9. `claude-provenance` is Claude-only (lines 316-319, 467-468).
It hard-codes `claude-code` and needs `CLAUDE_ENV_FILE` and the payload's `scratchpad_dir`.
A new harness that wants verified `TASKS_AGENT` and `TASKS_MODEL` needs its own hook; the
runbook implies `claude-provenance` can be reused.

I10. The approval gate is understated (lines 600-603).
The runbook says to obtain approval "where the checkout profile or runbook requires it".
The global instructions treat a merge that changes a live global surface (hooks,
services) as an action outside the repository under every profile, so it always needs the
user's approval. "Take effect … as soon as they merge or apply" also merges two cases:
- symlinked settings and hooks take effect on merge;
- `links.toml` changes take effect only on each host's `just link --apply`.

## Minor

M1. obs failure modes are misdescribed.
- An unknown provenance source does not raise out of `obs index`. That one task fails to
  index (stderr line, `counts["failed"]`), outcomes are skipped, and the run exits 1 with
  `index_failed`.
- The `obs ingest` `ValueError` message is never printed; only
  `{"event": "obs-ingest-failed", "error": "ValueError"}` appears.

M2. obs `join.py` `SOURCES` is a dict from env var to slug, so the entry must be
`"<ENV_VAR>": "<name>"`, and the value is checked. `CODEX_SESSION_ID` is also an accepted
source in obs and tasks; the runbook names only `CLAUDE_CODE_SESSION_ID` and
`CODEX_THREAD_ID`. A slug that `AGENTS` maps to but that is missing from `join.HARNESSES`
makes `tt_runs` classify the record as malformed; it does not leave the fields `None`.

M3. More obs lists:
- tests that pass a fixed `["claude-code", "codex"]` to `stores.run` (incomplete runs
  once `ADAPTERS` grows);
- `test_cli_surface.py`'s exact skills-coverage assertion;
- `tools/archive_replay_rehearsal.py`;
- the codex-only branches in `task_activity.py` and in `stores.run()` (`missing_usage`,
  `duplicate_threads`);
- `README.md` `--harness` documentation;
- `tools/retention_readiness.py`.

M4. More relay lists:
- `src/interaction/message.js` `HARNESSES`;
- the `src/types.js` `Harness` union;
- `src/routes/index.js` `ROUTES`;
- opencode-specific flag branches in `bin/relay.js`;
- `docs/api.md`'s "closed union";
- test lists.

M5. claim-guard details.
- It filters claims on `live` and session, not on `doing` status.
- It fails closed on an unreadable Stop input or unreadable claims.
- `wait_branch` also reads `BOUNDED_WAIT` when `controller-wake` is probed false.
- In `held()`, the `wanted` set accepts `<any HARNESSES entry>:<id>` for non-codex
  harnesses, so adding to `HARNESSES` widens what Claude Code matches.
- `related` is computed for codex only.

M6. `TASKS_FORMAT=json` is already the default (line 465); setting it only overrides an
inherited `pretty`.

M7. Claude skills (line 80). Claude links only the seven non-superpowers skills, because
superpowers arrives through the plugin, and `claude-work` links none. "Link required
skills individually" misstates both.

M8. The JSON clean filter needs strict JSON and normalizes formatting.
`clean_json` re-serializes with `json.dumps(indent=2, ensure_ascii=False)`. A JSONC config
(comments) fails the filter outright. Worth one sentence in section 2.2.

M9. Section 2 announces a "four-part" pipeline but has five numbered subsections. Its
`### 1.`-`### 5.` numbering also restarts inside `## 2.`.

M10. `Source(name, kind, home, root, pruned=False)` (line 519) reads as if `pruned` had a
default; it does not. Pass it explicitly.

M11. Alphabetical order of `harnesses` (line 246) is a convention; `harness-facts check`
does not enforce it. Adding the slug there is also what turns `lookup` of every fact
from `Undeclared` into `unknown`.

M12. Not listed: a new `<name>/` directory in hq also updates hq's own `AGENTS.md` Layout
and `README.md`.

M13. The hook payload key list omits keys the ops hooks read: `scratchpad_dir`, `model`,
`to_model` and `session_crons`. `executionNum` and `terminationReason` for agy could not
be checked against code.

## Confirmed accurate (sample)

- **hq routing:**
  - `links.toml` groups and the split agy homes;
  - the `[required]` runtime links and the `pi-install` / `relay-install` recipes;
  - `.ops-check.toml` `layout_allowed`;
  - first-run ordering, and the harness-links real-directory gate.
- **hq live state:**
  - `.gitattributes`;
  - `harness-state-clean` routing, including the global TOML keys and the exit on an
    unmatched JSON path;
  - `live-picks` `OWNED`, `RECORDS`, `JSON_GROUPS`, the Claude/agy equality assertion,
    `CLEAN`, `FIELD`, and `missing()`'s `KeyError` for a second TOML harness;
  - the checkout hooks, the lock, and the linked-worktree and rebase skips;
  - `harness-state-refresh` `PATTERNS`, the size-only `M` explanation, and the lock skip.
- **hq facts:** the `harness-facts` validation rules (slug regex, probe path inside the
  checkout, unquoted local date, `unknown` omissions).
- **hq sessions and archive:**
  - the `hq_cli` homes, choices, `harness_hue`, the `Colour` constants, `HOME_VARIABLES`,
    and `hq.toml`;
  - `session_archive` `check_sources` and its command list.
- **relay:** the allowlists, the adapter interface fields (other than I6), and the
  installer files.
- **tasks:** the provenance functions and the `--stamp` shape.
- **ops:**
  - the `ops-profile` `HARNESS` shape, `home_of`, and `config_problems`;
  - claim-guard `HARNESSES`, `BOUNDED_WAIT`, and the `decide()` codex branch;
  - claude-profile's in-process loading.
- **obs:** the registries named in section 6 all exist as described.
