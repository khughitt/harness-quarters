# The records repository's pre-commit hook

`pre-commit` is a byte-for-byte copy of the records repository's `.githooks/pre-commit`,
the hook that repository installs with `git config core.hooksPath .githooks`. It runs
`tasks check` for each project directory with staged files and refuses a top-level
directory whose index holds files but no `tasks/.config.toml`.

`tools/test_rename_cutover.py` installs a copy of it in each sandbox's records
repository (through `core.hooksPath`), so every record commit a test makes, whether
tasks makes it or a test runs the commit `rename-cutover apply` prints, meets the
refusal the live repository makes. Tests never read the live file: they share no state
with the host.

Whoever changes the records repository's hook copies it here again, with its mode
(`cp` keeps the executable bit), and runs `just test`.
