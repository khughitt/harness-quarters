# Turn-pause diagnostics and history

Type: reference. The protected-path guard permits validated filesystem reads
without permitting writes or changing pause state. Read-only history commands
will be documented here when their implementation is available.

The prepared default allows 60 tree spawns, with a warning at 45. Reaching 60
remains allowed; the next hooked decision after 61 spawns pauses the tree.
Explicit agent budgets override proportional scaling. Existing 16-hour,
500-root-call and two-root-compaction safeguards remain unchanged. Larger valid
plans can still cross 60; the measurement and its limits are retained on
hq-704fe5. Activation of a prepared default is a separate user-approved step.

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
