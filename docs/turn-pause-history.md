# Turn-pause diagnostics and history

Type: reference. The protected-path guard permits validated filesystem reads
without permitting writes or changing pause state, and `hq pause history` /
`hq pause list` expose read-only transition history and turn summaries from the
local store.

The prepared version-1 root envelope requires private `prompt_guards` metadata
with sorted unique cron digests and wake rows `[digest, not_before, not_after]`.
Digests are lowercase SHA-256 of stripped UTF-8 prompt text; they are matching
fingerprints, not anonymization, and permit guesses for short prompts. They stay
in private mode-0700/0600 storage and outside event snapshots/public handoff.
Ending a root clears active counters while retaining its known schedules and
bounded transition history. SessionEnd and seven-day idle clearing capture the
guards atomically with the closing event. The hook rejects late tool calls until
a genuine root prompt resumes; worker/injected text cannot consume wake guards.
The reviewed rule retains known schedules while a root is ended, then clears guards on genuine
resume; prior jobs need fresh native evidence afterward. Expired wake windows
and evicted root records cannot establish earlier provenance.

Each real turn has a persistent generation/turn identity. Its first warning,
prepared pause, aggregate notification outcome, reset/resume and end are recorded
with scoped counter snapshots. A committed pause is a prepared refusal, not
proof that the harness obeyed or the person saw a notice. Delivery/receipt remains
unknown. Ended records expire lazily after30days or beyond512 roots; maintenance
affects at most32 records per pass and reports remaining cleanup debt. Repeated
maintenance does not refresh an already-ended record.

The prepared default allows 60 tree spawns, with a warning at 45. Reaching 60
remains allowed; the next hooked decision after 61 spawns pauses the tree.
Explicit agent budgets override proportional scaling. Existing 16-hour,
500-root-call and two-root-compaction safeguards remain unchanged. Larger valid
plans can still cross 60; the measurement and its limits are retained on
hq-704fe5. Activation of a prepared default is a separate user-approved step.

## Read-only history and turn summaries

Inspect local transition records and root/turn summaries with:

```text
hq pause history [--session ROOT] [--harness claude-code|codex]
                 [--since RFC 3339] [--until RFC 3339] [-n N] [--json]
hq pause list    [--session ROOT] [--harness claude-code|codex]
                 [--since RFC 3339] [--until RFC 3339] [-n N] [--json]
```

- **Selection and window.** Omitting `--session` queries all locally available
  root records without `CODEX_THREAD_ID` or current-directory fallback.
  `--session ROOT` selects a root session id (live worker resolution remains on
  `hq pause status`). `--since` and `--until` require RFC 3339 timestamps with an
  explicit UTC offset (`Z` or `[+-]HH:MM`) and form a half-open `[since, until)`
  interval. `-n N` bounds returned rows (`1..1000`, default `50`). Invalid
  ranges, naive timestamps, malformed JSON, or unsupported record versions fail
  with exit status `1`.
- **Read-only boundary.** Neither command creates the state directory, rewrites
  records, reads session transcripts, or runs document providers. While a turn is
  paused, `hq pause history` and `hq pause list` are classified as `read` and
  spend the 25-read grace, whereas `hq pause status` and `hq pause limits` remain
  `bookkeeping`.
- **Ordering and summaries.** `hq pause history` orders events newest-first by
  `(at, harness, root, generation, turn, sequence)`. `hq pause list` emits one
  `(harness, root, generation, turn)` summary per observed turn, ordered by the
  turn's last retained event (`last_event_at`, then identity and `last_sequence`).
  Summaries report `started_at` and `ended_at` (nullable when truncated or still
  open), `origin`, `end_kind`, `end_reason`, `event_count`, `event_kinds`,
  `warnings`, `enforced_pause`, `notification`, `snapshot`, `root_active`,
  `root_ended_at`, and `truncated`. Roots with no observed turn produce no
  fabricated summary and are reported in `coverage.unobserved_roots` and
  `diagnostics`.
- **Version-1 JSON envelope and obs handoff.** `--json` outputs `version` (`1`),
  `observed_at` (UTC epoch seconds), `host`, `coverage` (`status`:
  `available` | `partial` | `unavailable`, `scope: "local_store"`,
  `observation: "per_root_atomic"`, root/event bounds, `dropped_events`,
  `unobserved_roots`, `disappeared_files`), `window`, `events` or `summaries`,
  `truncated`, `retention` (`30` days / `512` ended roots / `128` events /
  `131072` bytes / `32` maintenance mutations and dropped metadata),
  `cleanup_debt`, and `diagnostics`. A missing store directory yields
  `coverage.status == "unavailable"` with empty rows, never proof of zero
  interruptions.
- **Consumer correlation rules (obs-1450e7).** Portable handoff fixtures in
  `tools/fixtures/turn-pause/history/obs-handoff-cases.json` keep hook transition
  events (`hook_events`) separate from external `task_evidence` and
  `session_evidence` arrays across audit equivalents A–G and control cases.
  Consumers derive pre-enforcement self-stops outside hooks by joining stamped
  task parks and session evidence to the qualified session and enclosing genuine
  human turn (`generation`, `turn`, and time bounds). Ordinary approval/review
  decision parks and warnings followed by continued execution are not
  interruptions; missing transcripts, unstamped parks, or ambiguous joins remain
  `unknown`, and absence of a self-stop record never proves continuation. Private
  `prompt_guards`, raw schedule text, and `cwd` never appear in public snapshots
  or handoff fixtures.

## Inspecting protected paths

Claude's native Read/Grep/Glob tools can inspect files. Both harnesses can use a
single `cat`, `head`, `tail`, `wc`, `ls` or `readlink -f` command with the existing
restricted reader options. Use a concrete expanded absolute path or a path
relative to the checkout; tilde syntax, globs, wrappers, redirects, substitutions
and compound commands do not pass. Bash may include its ordinary description
and integer timeout metadata, but no extra execution fields.

Split an action and its verification into separate calls. For example, a merge
followed by a read in one shell command is refused even when the read is safe.
While paused, reads spend the existing25-read grace. Bookkeeping and owned
cancellation retain their existing permissions; a read never clears a pause.

## Checking host pointers before worktree removal

Enumerate entries in the user's bin and .local/bin directories, user systemd
units (including drop-ins), and known configuration includes declared by the
project's link/config manifests. Use individual `ls -la` calls with concrete
paths, then resolve each literal entry with `readlink -f`. Inspect unit/include
contents with the allowed readers for embedded paths, not just symlink targets.

Check every resolved target and embedded path against the worktree's real
location, including links through another symlink. A missing, unreadable or
uninspected entry makes the audit incomplete; do not report a clean audit until
it has a disposition. A pointer resolving into a worktree prevents its removal.
This procedure inspects pointers and does not repoint launchers or live settings.
