# Session store retention — brief

Scoped 2026-09-29 from `tack-401088`. Evidence: sizes measured on the desktop host on
2026-09-29; obs README and evals charter; the Claude Code and Codex settings in this
repository.

## Problem

The agent session stores grow without bound on the root filesystem, but they are also
the only raw input obs can re-parse. Some of that raw input is already lost without
anyone deciding it should be. The outcome: a stated purpose for a session file past N
days, applied the same way to both harnesses, so root stays bounded and obs loses
nothing it has not already indexed.

## Current behaviour and evidence

- **Codex ages nothing.** `~/.codex` is 37G, up from 31G at filing on 2026-09-14:
  - `sessions/2026` is 22G, by month 01: 62M, 02: 233M, 03: 2.6G, 04: 3.0G, 05: 1.9G,
    06: 1.3G, 07: 3.1G, 08: 6.6G, 09: 3.1G.
  - `packages` is 8.9G. `standalone/releases` alone holds 22 kept Codex releases at about
    400M each (7.4G), with `current` pointing at 0.159.0; `app-server-daemon` is 1.6G.
  - `thread_history_1.sqlite` is 3.0G, `archived_sessions` 1.6G (rollouts back to
    2026-01-17), `logs_2.sqlite` 1.3G.
  - `codex/config.toml` sets no history or retention key, and `CODEX_HOME` is not
    relocated.
- **Claude Code ages on its own.** `claude/settings.json` sets no `cleanupPeriodDays`,
  so the 30-day default applies; the oldest transcript under `~/.claude/projects` is
  from 2026-08-29. `~/.claude` is 2.7G and `~/.claude-work` 598M.
- **Root has room today:** 88G free of 275G. `/mnt/backup` has 2.0T free.
- **The earlier snapshot is not on the backup disk.** The 10.8G tarball of both stores
  from 2026-08-30 is on the scratch SSD (`claude-codex-state-2026-08-30.tgz`), not
  under `/mnt/backup`.
- **obs reads the stores in place.** Its roots come from `OBS_CLAUDE_PROJECTS` and
  `OBS_CODEX_SESSIONS`, or the default paths. It writes only normalized metadata to its
  own index (3.4G, also on root) and marks rows from deleted files `missing_since_ms`
  rather than dropping them (obs README).
- **Deleting a raw file loses re-parse input.** The obs evals charter
  (`docs/specs/2026-09-17-obs-evals-charter-design.md` §8, in the obs checkout) says
  extracted events do not preserve every transcript detail or future re-parsing input.
  It defers pruning to "a later raw/derived retention decision", which is this idea. A
  newer obs schema cannot backfill a deleted file. The obs friction report of
  2026-09-23 records that Claude Code history before 2026-08-05 is already gone.
- `session-episodes` (the `session-logs` skill's tool) scans both stores in full unless
  given `--since`. Its labelled baseline dates from 2026-09-21 (`5ef877f`).

## Constraints

- Harness behaviour is upstream: Codex's auto-updater keeps old releases and Claude
  Code prunes at `cleanupPeriodDays`. This repository only configures them.
- The CACHE_DIR pattern (dotfiles `zshenv`, overridden per host in
  `shell/local/<host>.env.zsh`) and WORK_ROOT (`work-link`) are the precedents for moving
  host-local state off root.
- A retention rule must not outrun obs indexing. The obs context and cost spec already
  treats Claude's 30-day expiry as the indexing deadline and relies on an hourly timer.
- No open task in obs or elsewhere owns retention. The nearest are obs-175b10 (index the
  opencode and Crush stores) and dots-0925a6 (a pruning pattern for mindful backups).

## Alternatives

- **A. Archive, then prune.** Monthly: compress each month of raw sessions from both
  stores older than N days onto `/mnt/backup` after obs has indexed it, then delete the
  originals. Raise Claude Code's `cleanupPeriodDays` so its own pruning never runs
  first. Keeps re-parse input and bounds root.
- **B. Relocate.** Move `CODEX_HOME` (or its `sessions` directory) and the Claude stores
  onto host-local storage, following the CACHE_DIR pattern. Frees root but bounds
  nothing, and leaves Claude's silent 30-day loss in place.
- **C. Prune only.** Delete past N days in both stores, once obs has indexed them.
  Cheapest, but it accepts that obs can never re-parse old sessions.

Lean: A. Its archive half does not depend on N: until the policy is set, the only
step that frees space without deciding anything is removing superseded Codex releases
(7G, about a fifth of the store).

## Findings (`tack-1327b8`, 2026-09-30)

Observed with Codex 0.159.2 and Claude Code 2.1.285. Every Codex test ran in a throwaway
`CODEX_HOME` built from copies, with `rollout_path` rewritten into it and no `auth.json`,
so a resume that got as far as the model stopped at a 401. Every obs test ran against a
scratch copy with a throwaway `XDG_STATE_HOME`. Nothing live was moved or deleted.

**Codex resume needs the rollout file, in both history modes.** `state_5.sqlite` has
3381 `legacy` threads (2026-01-17 to 2026-08-09) and 3401 `paginated` ones (since
2026-08-08). `thread_history_1.sqlite` is a projection of paginated rollouts: it tracks a
byte offset into each file and holds no rows for legacy threads. With the rollout
present, `codex exec resume <id>` loaded the thread and failed only at auth. With it
removed, a legacy thread failed with `failed to resolve rollout path … file does not
exist`, and a paginated thread with `no rollout found for thread id`. The sqlite rows do
not stand in for the file.

**Codex has its own delete, and re-adopts a returned rollout.** `codex delete --force
<uuid>` removes the rollout, the `threads` row, and the thread's `thread_items`,
`thread_turns` and projection-state rows together. Without `--force` it refuses with no
TTY. A plain `rm` of the rollout would leave those rows behind in the 3G history
database. Copying a deleted thread's rollout back into `sessions/` and resuming it by id
recreated its `threads` row. An archive restored under the live `CODEX_HOME` therefore
brings those threads back as live sessions.

**Nobody resumes a Codex thread after a week.** Of 6782 threads, 6072 last changed within
a day of starting, 69 within 1–7 days and 10 within 7–30 days. The 631 changed 30 or more
days after starting are all bulk touches: 624 on 2026-09-14 and 7 on 2026-03-13. None is
a resume.

**Claude Code's `cleanupPeriodDays` covers more than transcripts** (code.claude.com docs,
`claude-directory` "Cleaned up automatically" and `data-usage`). At every startup it
deletes, by mtime, transcripts under `projects/` together with their `tool-results/` and
`subagents/`, plus `file-history/`, `plans/`, `debug/`, `paste-cache/`, `image-cache/`,
`uploads/`, `session-env/`, `tasks/`, `shell-snapshots/`, `backups/` and the legacy
`todos/`, `statsig/` and `logs/`. The minimum is 1 (0 fails validation), and there is no
documented maximum. Raising the value keeps all of these for longer, but everything
besides `projects/` (2.3G) totals under 60M today; `file-history` is the largest at 54M.
Desktop and Cowork transcripts follow a separate `desktopSessionCleanupPeriodDays`.

**Raising it is not a guarantee.** anthropics/claude-code#41458, open since 2026-03-31,
reports 490 sessions deleted despite `cleanupPeriodDays: 99999`. When settings fail to
load, cleanup silently falls back to the 30-day default. An archive step has to capture a
transcript before day 30 whatever the setting says. Restored files keep their old mtimes,
so the next startup cleanup deletes any restored file older than the setting.

**obs can read an unpacked archive, but at a new path it counts everything twice.** obs
keys `files` by absolute path. In a throwaway index of one Codex month (9 files) and one
small Claude project (12 files), a prune marked all 21 files `missing_since_ms` with
their rows kept. Indexing the unpacked archive at a new path through
`OBS_CODEX_SESSIONS` / `OBS_CLAUDE_PROJECTS` then added 21 new file rows and doubled
sessions (12→24, 9→18) and turns (3066→6132). `supersede_sessions` did not fire, because
it only supersedes a copy when the other copy has strictly more turns. Pointing the
variables at an archive also marks every live-root file missing until the next ordinary
run. Restoring the archive at its original path relinked cleanly: the missing marks
cleared and nothing was duplicated, with or without `--full`. That original path is the
live store, though (see the two restore hazards above). Re-parsing an archive safely needs
obs to index an archive root as an alias of the root it came from: `obs-de84cb` (idea).

## Recommendation

**A (archive, then prune), with N = 30**, applied the same way to both stores:

- A monthly job archives a calendar month once all of its files are more than 30 days
  old and obs has indexed them. On the 1st it archives the month before last, as one
  tarball per harness on `/mnt/backup`. It then prunes the originals: `codex delete
  --force` per thread for Codex, so the sqlite stays in step, and file removal for
  Claude.
- `cleanupPeriodDays: 90` in `claude/settings.json`, so that with a monthly cadence
  (files up to about 62 days old) Claude's own cleanup never runs first. #41458 means
  this lowers the risk of Claude pruning first but does not remove it.
- Past 30 days a session file is kept for obs re-parse only, not for resumability (the
  resume counts above).

Rejected: **C** saves one job but gives up re-parse for good, and the obs charter treats
re-parse input as worth keeping. **B** frees root space but leaves both stores
unbounded, along with Claude's silent 30-day loss.

Two steps do not depend on N and can go first:

- Raising `cleanupPeriodDays` now stops the daily loss of transcripts that obs has not
  yet had a reason to re-parse.
- Removing superseded Codex releases (`tack-079ad1`, about 7G) frees space.

## Unanswered questions

- Adopt A with N = 30 and `cleanupPeriodDays: 90`, or another policy? *The user.*

## Proposed decomposition

| Task | What | Waiting |
|---|---|---|
| `tack-1327b8` | Research: what a Codex or Claude session file is still needed for past 30 days, and whether obs can index an archive (done 2026-09-30) | tack-401088 |
| `obs-de84cb` | Index an unpacked archive under the paths it was first indexed at | A only |
| `tack-079ad1` | Remove superseded Codex standalone releases, keeping current and previous | — |

Parent goal: `tack-1a3278`. `tack-401088` stays an idea until the user sets the policy,
then becomes the implementation of the chosen alternative.
