# Profile: work

A repository worked under the work account. Design specs and plans stay out of
the tree unless the repository's own instructions ask for them: write the doc
at the skill's path, add that path to `.git/info/exclude`, and copy it out
before removing a worktree. GitHub writes use the work account the session's
`profile:` line names after `gh:`: check `gh auth status` before a write and
`gh auth switch --user <that account>` when the active account differs. The repository's own guidelines decide
branch, commit, and review conventions.
