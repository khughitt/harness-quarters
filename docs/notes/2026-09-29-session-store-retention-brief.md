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

## Unanswered questions

- What is a session file for after N days: resumability, obs re-parse, or nothing? And
  what is N? *The user, informed by `tack-1327b8`.*
- Does `codex resume` or `thread_history_1.sqlite` need rollout files that are gone or
  archived? Can obs index an unpacked archive through `OBS_CODEX_SESSIONS`? *`tack-1327b8`.*
- Does raising `cleanupPeriodDays` change anything besides transcript lifetime (for
  example, other state Claude Code prunes on the same clock)? *`tack-1327b8`.*

## Proposed decomposition

| Task | What | Waiting |
|---|---|---|
| `tack-1327b8` | Research: what a Codex or Claude session file is still needed for past 30 days, and whether obs can index an archive | tack-401088 |
| `tack-079ad1` | Remove superseded Codex standalone releases, keeping current and previous | — |

Parent goal: `tack-1a3278`. `tack-401088` stays an idea until the user sets the policy,
then becomes the implementation of the chosen alternative.
