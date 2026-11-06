# Harness layout activation report

Owner: hq-b77d0c; operation: hq-fd490e. Both Titan and Europa adopted the new
layout on 2026-11-06. The shared no-settings-writer window can end.

## Inputs and result

The user approved the activation package at
`b0c044f11ef8c4c43487ab9688a05055d7529d09:docs/notes/2026-11-06-harness-layout-activation.md`
and renewed the quiet window with “Ready” after the first attempt stopped.
Main advanced from `71a4934294f055d42c1cf9dae8290937656fc934` to the independently
accepted runtime `062f7131a59dc81fb22148b05a11741e5642853a` by fast-forward.
Subsequent integration is restricted to task and operational records.

`agy/`, `claude/`, `codex/` and `pi/` are now under `harnesses/`; `ponytail/` is
under `external/`. All five old root directories are absent on both hosts. Native
home names and session stores remain unchanged. The unfiltered `agentMode: auto`
setting remains an unstaged edit in `harnesses/agy/settings.json`.

## Preservation and checks

Titan ran the accepted capture, finite record rekey, merge, patch carry and link
procedure. Every saved pick-record value is equal to the captured value; only the
four configuration keys changed. Saved Codex project trust and private work
configuration bytes are equal. Existing hook trust entries and both Codex hook
JSON blobs are unchanged. Six generated mod files were carried byte-for-byte;
two regenerable probe cache files were snapshotted then individually removed.
Europa had those six files but neither cache file.

Titan passed `just link-check`, `tools/harness-facts check`,
`python3 .githooks/harness_state.py check`, and mandatory `just check-hygiene`.
The index is clean; normalized unfiltered patches compare equal before/after.
Europa verified the synced configs and records against its own before snapshot,
then ran `just link --apply`, explicit trust/pick sync and `just link-check`.
Its final settings, records and private bytes equal the verified synced snapshot.
Both hosts verified old-root absence and original Codex hook bytes.

No new runtime code was written in this operational task. The accepted focused
build evidence remains valid; policy-off broad testing was not rerun or claimed
as passed. No paid probe or remote CI result is claimed. No push occurred.

## Operational observations and rulings

Attempt 1 stopped before capture or migration because Titan agy settings changed
mtime while retaining identical contents and mode. Both observations were kept;
the failed checkpoint was not overwritten. Attempt 2 used new snapshot directories
and the user's fresh window.

An overly broad final operator assertion compared all parsed Codex fields. The
only difference was `tui.screen_reader_detection_done`, which the preexisting
clean filter deliberately strips and does not restore (README state-hygiene
contract). Every other parsed field, including picks and trust, remained equal.
The verification was corrected to that existing contract; no filter or saved-state
ownership changed. Original raw bytes remain in the private snapshot. The cost is
the existing one-time detection behavior on checkout, not a new migration policy.

Europa's Ponytail link was absent in its initial snapshot. An initial operator
assertion incorrectly required every native path to be a symlink; the tested guard
confirmed unchanged absence. The declared link tool created it. That same approved
full reconciliation removed an already-retired, owned `~/.agents/.skill-lock.json`
link under the existing manifest rule; its target bytes were not removed.
No foreign link was adopted and no ownership check was relaxed.

## Evidence and remaining housekeeping

Private raw evidence stays outside Git under each host's declared storage:
`$WORK_ROOT/hq/hq-b77d0c/activation-initiating-2026-11-06[-attempt2]/` on Titan and
`$WORK_ROOT/hq/hq-b77d0c/activation-adopting-2026-11-06[-attempt2]/` on Europa.
Each attempt-2 `verified.json`, `operations.log`, command outputs and immutable
snapshots bind the observations above. Task retention notes/manifests locate the
complete sets and their owners.

Recovery-evidence custody and eventual retirement are tracked by hq-b08a11.
Two pre-merge Minor documentation findings remain in hq-b42a68: private-path wording
in README and future-harness path templates in the adding-a-harness runbook.
Neither blocks the active layout. Worktree cleanup and exact custody receipts are
recorded on the source tasks; cleanup does not discard private recovery snapshots.
