# Profile: external

A repository the user does not maintain: an upstream project, a fork, a clone
outside the registry. Before any other work, read its contributor guidelines —
`CONTRIBUTING` in any casing at the root, under `.github/`, or under `docs/`;
developer or hacking guides; `.github/PULL_REQUEST_TEMPLATE.md` or
`PULL_REQUEST_TEMPLATE/*`; any repo-level `AGENTS.md` or `CLAUDE.md` — and
search its open and closed PRs and issues (`gh pr list --state all --search`,
`gh issue list --state all --search`). On a duplicate or a prior closed
attempt, stop and tell the user; otherwise reference what was found and link
the issue the PR fixes. The guidelines decide everything: attribution only
where and how they explicitly ask, and the branch, commits, PR title, base
branch, template sections filled with real content, sign-off, changelog
entries, and tests. Every PR is a draft (`gh pr create --draft`; the user
promotes it); `--body` replaces the template, so prefer `--body-file` from a
filled copy. When a convention cannot be met, say so instead of opening a PR
that violates it. Design specs and plans stay out of the tree: write them at
the skill's path, add that path to `.git/info/exclude`, and copy them out
before removing a worktree. GitHub writes use the `khughitt` account.
