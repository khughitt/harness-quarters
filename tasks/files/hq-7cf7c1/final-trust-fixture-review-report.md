What this change does: It isolates the trust fixtures from caller editor/pager settings, credentials, Git routing, and global/system configuration. The final adjustment gives each temporary HOME its own empty global config file.

Verdict: Ship after the controller’s final verification passes. No Critical, Important, or Minor findings.

Checked:

- All six original subprocess sites receive the key-built fixture environment.
- Repository root and absolute Git directory assertions precede fixture configuration and staging.
- Existing trust, filter, failure, locking, deletion, linked-worktree, and rebase assertions remain intact.
- Fabricated contamination regressions cover editor/pager overrides, Git routing/configuration, and a fake credential, including successful rebase continuation.
- Independent final-adjustment self-check passed: global Git config reads and writes stayed inside the fixture HOME under combined synthetic contamination; the fabricated caller’s config remained unchanged.
- Reviewed copied hooks and shared mechanics, including atomic replacement and failure reporting.
- Read attached RED evidence and baseline results: four failing regression cases before isolation; baseline **231 + 1037 + 389 + 1 passed**.
- `git diff --check` passed. Covered fingerprint matched before and after review: `6dcc3e93cb84a8464d5688be85514d2c769977bb`.

Reviewer: `codex/gpt-6.1-sol`, verified this turn.
Reviewer session: `codex:01a16dee-d9c7-7841-b3f0-0d74284bf999`.

No files, index, HEAD, or task records changed; no pushes or surviving review processes. Existing worktree remains in place.

Not checked: Controller-owned final suite, other fixture families, or new filesystem fault injection; production rename/delete behavior is unchanged.
Remaining risk: completion still requires the controller’s final GREEN results.
