# Recent-session discovery: metadata source and launch contract

Task `hq-434be2`, 2026-10-15, under goal `hq-65f661`; brief
`docs/notes/2026-10-10-context-discovery-brief.md`. Claude Code 2.1.296, codex-cli
0.162.1, one host. Read-only: aggregate counts over native metadata, header records,
file names and stats; no transcript text quoted, no session resumed, no home changed.
Launches ran against stub `claude`/`codex` executables that print argv, cwd and the two
home variables.

## Answer

Each harness already keeps a session list beside its transcripts, and those lists
are enough. Claude Code has `<home>/history.jsonl`, one row per typed prompt. Codex has
`<home>/state_5.sqlite`, whose `threads` table has one row per thread. Neither needs a
second index or a transcript scan, and neither waits on obs-c7d924: the milestone can be
built on them now. obs's index is the better source only for what this milestone leaves
out (full-text search, turn counts), and its Codex coverage stops at `~/.codex/sessions`
until obs-914269 (which waits on obs-c7d924) lands.

## Sources compared

| Source | Thread id | Home | cwd | Recency | Interactive vs. other | Coverage on this host |
| --- | --- | --- | --- | --- | --- | --- |
| Claude `history.jsonl` | `sessionId` from 2025-10-31; 5,341 older lines have none | the file's home | `project`, per prompt | `timestamp` of the last prompt | every row is a typed prompt; subagents, `-p`/SDK runs and promptless opens write none | personal 3,824 sessions, work 301; 2 malformed lines (personal) |
| Claude `projects/*/<id>.jsonl` | file name | path | `cwd` on records | file mtime | `entrypoint` (`cli`, `sdk-cli`, `sdk-py`), `isSidechain` | needs a header read per file |
| Claude `sessions/<pid>.json` | `sessionId` | path | `cwd` | `updatedAt` | `kind` | live processes only (one file per running session) |
| Codex `state_5.sqlite` `threads` | `id` | path | `cwd` | `recency_at_ms` | `source` (`cli`, `vscode`, `exec`, subagent JSON), `thread_source`, `archived`, `preview` | personal 8,089 rows, work 659; every row's `rollout_path` exists but one (work) |
| Codex `session_index.jsonl` | `id` | path | none | `updated_at` | none | names only: no cwd, so not usable |
| obs `index.sqlite` `sessions` | `session_id` | derivable from `files.path` | `cwd` | `end_ms` | `interactive`, `subagent`, `entrypoint`, `human_turns` | both Claude homes; Codex personal `sessions/` only, no work home, no archived threads |
| `session-episodes` | — | — | — | — | task-lifecycle episodes only | not an inventory: drops ordinary chats and subagents by design |

### Native coverage, checked against the stores

- **Claude.** Of 2,250 personal top-level transcripts, 850 have a history row; 1,316 of
  the rest are `sdk-py` runs, 40 `sdk-cli`, 43 `cli` sessions with no human turn, and one
  with no entrypoint and no user record in its header. Work: 223 of 248; the rest are 19
  `sdk-cli`, 5 `cli` with no human turn, and one without an entrypoint. So every interactive session
  with a human turn is in history. 2,974 personal and 78 work history sessions have no
  transcript any more (pruned) and cannot be resumed. The transcript sits at
  `projects/<slug(cwd)>/<id>.jsonl` for 846 of 850; 4 sit under another directory, so
  find it by `projects/*/<id>.jsonl` (directory entries only), not by computing the slug.
- **Codex.** Interactive rows (`source` in `cli`/`vscode`, `thread_source` `user` or
  null): personal 1,612 (12 archived), work 281. Excluded: subagent rows (personal 5,863
  live and 582 archived, guardian reviewers among them; work 373) and 37 `exec` rows.
  `has_user_event` is 0 on every row and cannot be used. 594 archived rows match the 594 files in `archived_sessions/` exactly.
  8,707 personal rollouts from 2026-01 to 2026-07 have no row although `backfill_state`
  reads `complete`: 8,216 subagent rollouts and **491 interactive** ones. The work home
  has none missing.

## Sample rows and stub launches

Eight rows, the newest of each kind, from a prototype that lists all four homes in
0.45 s:

| Row | Listed | Launch (argv · cwd · env) |
| --- | --- | --- |
| Claude, personal | yes | `claude --resume <id>` · recorded cwd · both home variables unset |
| Claude, work | yes | `claude --resume <id>` · recorded cwd · `CLAUDE_CONFIG_DIR=~/.claude-work` |
| Claude, ordinary chat outside any tasks project, no lifecycle text | yes | as personal |
| Claude, transcript pruned | no (counted) | refused: transcript gone |
| Claude, cwd gone (a removed worktree's probe directory) | yes, marked | refused: names the missing cwd |
| Codex, personal | yes | `codex resume <id>` · recorded cwd · both unset |
| Codex, work | yes | `codex resume <id>` · recorded cwd · `CODEX_HOME=~/.codex-work` |
| Codex, archived | with `--archived` | as personal |
| Codex, cwd gone (a removed worktree) | yes, marked | refused: names the missing cwd |
| Subagent, either harness | no | — |

Missing cwd is common: 198 personal Claude history sessions and 52 personal interactive
Codex threads (1 work) point at directories that no longer exist, mostly removed `.worktrees/`.

## Recommendation: the smallest milestone

`hq sessions` (name open) lists, filters and launches; it owns no index.

- **List.** Rows from the four native sources above: harness, home, short id, recency,
  cwd (with `~`), a label (Codex `name` or `title`; Claude the session's first history
  `display`, trimmed), and a `cwd missing` mark. Newest first; 20 rows by default.
- **Default visibility.** Every home and every project. The point is finding a session
  without remembering where it ran. Filters: `--harness claude|codex`, `--home
  personal|work`, `--here` (cwd inside the current checkout or one of its worktrees),
  `--archived` (Codex archived threads, hidden by default as the native picker hides
  them). Codex rows with an empty `preview` (14 personal, 2 work) stay hidden, as Codex's
  own `idx_threads_visible_*` indexes leave them out; that is read from the schema, not
  from the picker.
- **Recency.** Codex `recency_at_ms`. Claude: the transcript's mtime, which is the last
  activity and so matches Codex. The last history prompt is a fallback only when the
  stat fails.
- **Excluded, and counted in one footer line:** subagents, `exec`/SDK runs, Claude
  sessions whose transcript is gone, Claude history lines without `sessionId`, and
  malformed lines. A missing or renamed `state_5.sqlite`, or a `threads` table without
  the columns read, is an error that names the file: Codex's state schema is internal,
  and a version bump must stop the list rather than empty it.
- **Select.** An interactive pick (fzf or a numbered prompt) over the listed rows; mobile
  is out of scope.
- **Launch flags (decided by the user, 2026-10-15).** The launcher adds the flags the
  user's own launchers use, configured per home, so a resumed session behaves like one
  started by hand. Today's values: both Claude homes `--dangerously-skip-permissions`;
  both Codex homes `--no-daemon --dangerously-bypass-approvals-and-sandbox`, placed
  before `resume`. The work Codex values follow the work resume alias, not the plain
  work launcher, which omits the bypass.
- **Launch.** `exec` in the recorded cwd with the argv above. A personal row unsets
  `CLAUDE_CONFIG_DIR`/`CODEX_HOME` rather than setting them to `~/.claude`/`~/.codex`:
  with `CLAUDE_CONFIG_DIR` set, Claude reads `.claude.json` inside that directory
  (`~/.claude-work/.claude.json` exists; the personal one is `~/.claude.json`), so setting
  it to `~/.claude` would start against different state. A row whose cwd is gone, or whose
  transcript is gone, is refused with the path; never launched elsewhere.

## Unresolved, for the implementation task

- **491 personal Codex rollouts without a row.** Whether `codex resume <id>` still opens
  them, and whether the native picker lists them, is unknown without a live launch. They
  date from before 2026-07-08 (the backfill watermark). Leave them out of the list and
  say so. A synthetic-home probe can settle it if they matter.
- **Codex cwd on resume.** Running in the recorded cwd avoids depending on whether
  `codex resume` uses the process cwd or the thread's. A one-off probe in a scratch
  `CODEX_HOME` would settle it; it is not needed for the milestone.
- **Agent-driven interactive sessions.** Live probes that drive a real TUI write history
  rows like a person does (the cwd-gone Claude sample is one). They are listed;
  filtering them needs a marker the probes do not leave yet.

## What depends on obs

Nothing in this milestone. obs-c7d924 matters only if listing moves onto obs's index
(for full-text search or per-session counts), and then through obs-914269: the index
must cover `archived_sessions/` and `~/.codex-work` under each rollout's thread identity
before it can replace the native Codex source.

Correction (2026-10-17): obs's index keeps counts and byte sizes, not message text, so it
cannot serve full-text search; see docs/notes/2026-10-17-session-search-brief.md.
