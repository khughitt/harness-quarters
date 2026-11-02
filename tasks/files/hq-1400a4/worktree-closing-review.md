What this change does: It permits `tasks -C DIR` before the existing closing subcommands, allowing paused agents to note and park claims in their authoritative worktree. It preserves command classification, read grace, protected-path checks, shell scanning, and the `show --no-fetch` requirement.

**Findings:** None. No Critical, Important, or Minor issues found. Verdict: Ship once the controller’s required full-suite gate passes.

**Evidence reviewed**

- Read hq-1400a4, its pause-contract reference, the complete implementation diff against main, and connected allowlist, hook, protection, and test code.
- Checked the original filing transcript: lines 459 and 466–484 establish stale task records, refusal of `tasks -C`, and the Stop hook demanding claim release. Lines 507–519 establish manual recovery and the human request to report the contradiction. Filing call and result at lines 531–532 confirm this task’s origin; copied transcript blocks were treated as duplicates.
- The task’s intended scope is the directory-selector fix. The human’s separate concern about the four-hour threshold is recorded evidence of additional intended work, not something this implementation resolves.

**Independent verification**

- `uv run -q --with pytest pytest tools/test_turn_pause_allowlist.py tools/test_turn_pause_hook.py -q`: **356 passed in 12.47s**.
- Hand-traced `tools/turn_pause/allowlist.py:177`: raw command scanning still precedes selector removal; only one nonempty, non-option directory selector is removed. Unsupported subcommands and repeated selectors remain refused.
- Hand-traced `tools/turn_pause/hook.py:205`: protection checks precede paused classification; bookkeeping consumes no grace, while record reads remain limited.
- Ran a separate temporary-project check using the real tasks CLI from another cwd. A note persisted and parking released the owned claim. The subprocess environment was built explicitly with temporary HOME/XDG locations, isolated task identity, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, a Git ceiling, and no inherited `GIT_*` variables.
- Tested deleted, nonexistent, non-directory, and renamed directory selectors. They failed visibly in the CLI without silently selecting another checkout. A renamed registered project correctly reported its stale registry configuration.
- Independently asserted refusal of nine malformed, empty, repeated, unsafe, or unsupported selector forms.
- `git diff --check`: passed.
- Before/after fingerprint: `bb8f5130e81403236a7f49d9d68e442c3e9a51e4`, unchanged.

Reviewer identity: **codex/gpt-6.1-sol**, verified by a fresh successful `timeout 2 relay model --harness codex --pretty`.

Not checked: live hook activation or another broad suite; the controller owns the running full-suite gate. Existing documented Codex hook visibility limitations remain.
