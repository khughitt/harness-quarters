# pi live picks: keep pi's default model and thinking level across Git updates

Status: approved for execution, 2026-10-15 (hq-24416e planned gate, a66b548);
revised after spec review round 1 (unchanged
selections emit no event, rollback of the record, a bounded refresh) and round 2
(rollback order). Approved for implementation planning by the user on 2026-10-15,
after the round 2 fix. Revised after plan review round 1: pi's entry moves to its own
record file (§3.1), which retires the rollback record edit; spec round 3 and plan
round 2 accepted this revision before the user approved execution. Task: `hq-24416e` (goal `hq-aa9b44`). Extends
`docs/specs/2026-10-10-live-model-preservation-design.md` (below, "the base design"),
whose record, rule, operations and failure handling apply unchanged except where this
document says otherwise. Builds on `hq-61a47e` (merge `6b434eb`), which tracks
`pi/settings.json`, links it into `~/.pi/agent`, and filters its defaults out of the
index.

Deployment: titan's separately approved rollout and live capture/checkout recovery
check passed on 2026-10-15. Europa's host apply is tracked by `hq-a8d65f`.

## 1. Problem

Since `hq-61a47e`, `~/.pi/agent/settings.json` is a link to `pi/settings.json`, and
the `harness-state` filter drops `defaultProvider`, `defaultModel` and
`defaultThinkingLevel` from what Git stages. Any Git command that writes a new blob of
the file (checkout, merge, rebase, stash, reset) therefore removes pi's defaults, and
pi starts on its automatic model and `medium` thinking until one is set again. The
checkout is shared through Dropbox, so every host loses them at once. `live-picks`
already prevents this for Claude Code and Codex; pi needs the same, plus a capture
point, because pi runs none of the hooks that capture for the other two.

### 1.1 What pi writes (pi 1.1.0, read 2026-10-15)

| Fields | Written when | Code |
|---|---|---|
| `defaultProvider` + `defaultModel` | a model is set as the default (`setModel` or a cycle with `persist`, including the default a provider login sets through `setModel`); each emits `model_select` | `dist/core/agent-session.js` ~1954, 2006, 2033; `dist/modes/interactive/interactive-mode.js` ~5078 |
| `defaultThinkingLevel` | a thinking level is set as the default (`setThinkingLevel` with `persist`) | `agent-session.js` ~2059 |
| `deviceId`, `trackingId` | first OpenAI login; analytics opt-in | `dist/core/settings-manager.js` ~815-836 |

Cycling without `persist` and RPC mode write none of them. The events fire only on a
change: `_emitModelSelect` returns early when the selected model equals the session's
(`agent-session.js` ~1930), and `setThinkingLevel` persists the default before it checks
whether the level changed (~2052-2060). Setting the session's current model or level as
the default therefore writes the file and emits nothing (reproduced against 1.1.0 in
spec review round 1). Nothing in pi removes the
defaults (no setter clears them, and `setDefaultModel`/`setDefaultProvider` have no
caller alone). pi writes through a
promise queue (`SettingsManager.enqueueWrite`): the write runs in a microtask queued
before the `model_select` or `thinking_level_select` event is emitted. Each write
re-reads the file and merges only the fields pi changed (`persistScopedSettings`), so a
field another process inserted survives pi's next write.

## 2. Goals and non-goals

Goals: the base design's goals, for `pi/settings.json` as a third owned file; a pick
made in a pi-only session, with no Claude Code or Codex turn ending, is captured.

Non-goals:

- `deviceId` and `trackingId`. The filter drops them (installation ids, public
  repository), but `live-picks` does not own them: a rewrite drops `deviceId`, and pi
  makes a new one at the next OpenAI login, which is harmless (`hq-61a47e` review).
  Owning them would make `forget pi/settings.json` reset the installation's id along
  with its model.
- A pi work home: there is none.
- pi sessions with another agent directory (crew's attempts, the pi probes): they do
  not load the extension in §3.3 and never touch this file.

## 3. Design

### 3.1 Units and record

`pi/settings.json` joins `OWNED`. Its entry lives in its own record,
`local/live-picks-pi.json`, untracked like `local/live-picks.json`, with the same
format and validation (one key, `pi/settings.json`; the Claude entry shape):

```json
{"pi/settings.json": {"state": "set",
                     "values": {"defaultProvider": "anthropic",
                                "defaultModel": "claude-opus-5-5",
                                "defaultThinkingLevel": "high"}}}
```

A separate file, not a third key in `local/live-picks.json`, because the pre-change
tool refuses a record naming a file it does not own, and that refusal stops Claude's
and Codex's preservation. Kept apart, the old tool never reads pi's record: a rollback
needs no record edit, and no capture in flight on any host (a pi extension, a Stop
refresh waiting on the lock with the new code loaded, a host Dropbox has not yet
synced) can leave the old tool refusing its record (plan review round 1). Each
owned file maps to one record (`RECORDS = {CLAUDE: …, CODEX: …, PI: …}`); every
operation reads, validates and writes the records of the files it touches, all under
the one host lock, and a record no file names (Claude and Codex share theirs) is
written only when its content changes. The base design's "one record per checkout"
becomes one record per tool generation.

Its units are `defaultProvider` + `defaultModel` (written together) and
`defaultThinkingLevel`, so a thinking default set before a rewrite is restored never
erases the saved model, and the reverse. The base design's rule (§3.2 there) applies
per unit unchanged: capture records the units the file holds and keeps the saved value
of the others; restore fills only a unit holding none of its fields. Since nothing in pi
removes the defaults, every all-absent unit in pi's file is a Git rewrite or a
hand edit; `live-picks forget pi/settings.json` is the reset to pi's automatic default.

### 3.2 Generalising `live-picks`

Today the tool branches on `name == CLAUDE` for "a JSON file". It changes to a table:

- `JSON_GROUPS = {CLAUDE: CLAUDE_GROUPS, PI: PI_GROUPS}`; a file is JSON when it is in
  the table, and its owned keys are the union of its groups.
- The import-time check becomes, per JSON file: the groups are disjoint and their
  union lies within the keys the filter drops for that file (`JSON_FILES`); for
  Claude the union still equals them. The filter must drop every owned key (the
  all-absent rule depends on it); it may drop more (pi's ids).
- `CLEAN` gains `PI: partial(clean_json, keys=PI_JSON_KEYS)`, so the "what Git stages is
  unchanged" check uses pi's filter keys.
- `pick`, `invalid`, `merged_values`, `missing`, `with_pick` and `without_pick` take the
  file's groups instead of the Claude constants. Serialization is the filter's
  (`indent=2`, `ensure_ascii=False`, final newline), which pi reads.

Codex's TOML path is untouched.

### 3.3 Capture: an hq-owned pi extension

`pi/extensions/harness-state.ts`, linked as
`~/.pi/agent/extensions/harness-state.ts` by `[harness.pi.links]` (pi loads every file
in that directory). It runs `~/.local/bin/harness-state-refresh` (the link the
Claude and Codex Stop hooks already call, so the extension never names the checkout)
with an empty stdin:

- on `model_select` and `thinking_level_select`, after yielding one macrotask
  (`setImmediate`), so pi's queued settings write has landed: a selection that changes
  the session's model or level is saved at once;
- on `agent_settled`, the turn-end backstop matching the other harnesses' Stop: it saves
  a default set without an event (the session's current model or level set as the
  default, §1.1) and any write path a later pi version adds;
- on `session_shutdown`, so a pick made just before quitting is saved.

**Capture window.** A default set without an event is saved at the next turn end or
exit, not at once. A Git rewrite of `pi/settings.json` in that window restores the
previous saved default, as a Claude or Codex pick made since the last Stop is (base
design §3.5); setting it again, or `forget`, corrects it.

**Bounded runs.** Each run is a child process started in its own process group, with a
10-second limit: on expiry the extension sends SIGTERM to the group, then SIGKILL after
one second, so the refresh and its `git` and `codex-trust` children all end. A run that
times out counts as a failure. The refresh's host lock waits without limit, so the bound
is what keeps a stuck lock holder from holding pi. While a run owns a process group,
a synchronous process-exit handler sends SIGKILL to that group, covering pi's emergency
exits that skip `session_shutdown`. The handler is removed when the run finishes.
SIGKILL and host failure cannot run JavaScript cleanup.

**Awaiting.** pi awaits event handlers (picker actions and shutdown wait on them). The
`model_select`, `thinking_level_select` and `agent_settled` handlers start a run and
return without awaiting it. `session_shutdown` awaits the run in flight and one final
run, each under the same limit; a rerun already pending is replaced by that final run,
so pi's exit is delayed by at most about 22 seconds and never left with an orphaned
child. Runs are serialised inside the extension (one at a time; a request while one
runs schedules one more, and further requests join it). A failure or timeout is shown once
per session through `ctx.ui.notify` (no-op outside interactive mode) and never fails the
pi operation. The refresh does what it does at a Claude Stop: capture, then (when the
index is free) Codex trust sync, restore, and staging of size-only marks.

Rejected: dispatching through relay's planned pi adapter (`relay-828903`), which does
not exist yet and would make pick preservation wait on it; capturing only at Claude or
Codex Stop, which misses a pi-only session.

### 3.4 Restore

Unchanged mechanism: `post-checkout`, `post-merge` and `post-rewrite` restore, and the
next refresh (any harness's turn end, or a pi event above) is the fallback. A restore
while pi runs is safe for pi's later writes (§1.1); the running pi keeps the model it
started with, as Claude and Codex do.

### 3.5 Docs

README: the pi bullet drops "No hook saves pi's defaults yet" and describes the
extension, `forget pi/settings.json`, and the per-unit rule; the Setup section's
`live-picks` paragraph names pi. The `live-picks`, `harness-state-clean` and
`harness-state-refresh` docstrings name pi. The base design gets an "Extended by" line.

## 4. Testing

### 4.1 Probes (scratch agent directory, `PI_CODING_AGENT_DIR`, no live home)

The extension takes its refresh command from `HQ_HARNESS_STATE_REFRESH` when set (the
probes' stub), else `~/.local/bin/harness-state-refresh`.

- **P1 — loading, shutdown and the bound** (`pi --mode rpc`, no TTY, no model call;
  `set_model` between the dummy provider's two models emits `model_select`, since
  `setModel` emits on any change, persisted or not):
  - P1a: with the extension linked into a scratch `extensions/` through a symlink and a
    stub that records each call, closing stdin runs the stub once, from
    `session_shutdown`.
  - P1b: a stub that ignores SIGTERM and starts a descendant that also ignores it
    (`trap '' TERM`) and sleeps: pi exits within the bound after stdin closes, and no
    process of the stub's group survives, so the SIGKILL path ran.
  - P1c: a stub that takes 3 seconds; two `set_model` calls in quick succession (one run
    in flight, one rerun pending), then stdin closes at once: the stub's start and end
    times show no overlap, exactly the run in flight and one final run, and pi exits
    within the bound.
- **P2 — the write precedes the deferred handler, and unchanged selections.**
  Interactive pi in a detached tmux session (a headless terminal, not the desktop),
  with a `models.json` defining a local dummy provider with models A and B. Two
  sessions, each from a fresh scratch `settings.json` saying default A, thinking
  `medium`:
  - Session 1 (changing selections), started with no `--model`, so it runs A/medium:
    set B as the default, then `high` as the default thinking level. The stub runs at
    each, and each run reads the new value from the file.
  - Session 2 (unchanged selections), started with `--model B --thinking high`, so the
    session's model and level differ from the saved defaults: set the current thinking
    level first,
    then the current model, as the default. Saving the model reapplies the saved
    thinking default, so thinking-first keeps both selections unchanged. The stub does
    not run at either pick, the
    file holds B/high afterwards, and the run at `session_shutdown` reads B/high.

  No request reaches any provider.

Each result goes into `facts/capabilities.toml` through `tools/harness-facts`, with
its record. If P2 fails, the picker-event handlers are dropped and capture relies on
`agent_settled` and `session_shutdown`.

### 4.2 Acceptance cases

The base design's §4.2 cases 1, 3, 4, 5, 6, 7, 8 and 12, run for `pi/settings.json`
in the existing temporary-repository fixtures, plus:

1. A thinking default set after a rewrite dropped both units: restore brings back the
   saved model and keeps the new thinking level; capture then saves both.
2. `deviceId` in the live file is neither captured nor restored, and a rewrite that
   drops it leaves it dropped.
3. The import-time check refuses groups that overlap, or that name a key the filter
   does not drop for that file.
4. Claude's and Codex's existing `test_live_picks.py` cases pass unchanged.
5. Rollback against the pre-change tool, pinned at commit `6b434eb` (main before this
   change, after `hq-61a47e`), read from the repository history with `git show` (the
   test skips with a named reason only when that commit is absent, as in a shallow
   clone): in a temporary repository whose `local/` holds a Claude and Codex record and
   a pi record, the pinned `live-picks` `capture`, `restore`, `hook post-merge` and
   `harness-state-refresh` all succeed and leave `local/live-picks-pi.json` byte for
   byte. A capture by this change's tool, started while the pinned tool runs and
   finishing after it (both under the lock), writes only the pi record, which the
   pinned tool's next `capture` still ignores.

## 5. Rollout and recovery

Merging into main activates the changed Git hooks and refresh (a separately approved
step, as in the base design), and the extension link appears at the next
`just link --apply` from main, on each host (`hq-a8d65f` covers europa). After the
apply: set a default model in pi, check that `local/live-picks-pi.json` holds it, run
`git checkout -- pi/settings.json` in main, and check that the default is back and
`git status` is clean.

Recovery, from main: revert the merge, then remove the
`~/.pi/agent/extensions/harness-state.ts` link on each host (its target is gone) and
check `just link-check`. The reverted tool reads only `local/live-picks.json`, so Claude
and Codex preservation keeps working throughout, whatever captures are still running;
`local/live-picks-pi.json` is left unread and may be deleted. pi then behaves as after
`hq-61a47e`: its defaults stay in the live file until a Git rewrite drops them.
