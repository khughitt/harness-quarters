---
id: tack-b5171d
title: Host pointers repointed for a live test are restored before the task parks
status: done
priority: "2"
size: s
complexity: mid
process: direct
owner: main
created: 2026-09-21T10:29:09Z
updated: 2026-09-21T13:53:28Z
started: 2026-09-21T13:52:26Z
completed: 2026-09-21T13:53:28Z
depends: []
tags: [rules, skills]
source: niri-material ring-beam rollout 2026-09-21
agent: claude-code/claude-opus-5
---

Recurring friction: a planned task tests its implementation live by repointing a host-level pointer into its worktree and parks without restoring it or recording it. On 2026-09-19 prism-aec90f symlinked ~/bin/prism (which the Noctalia panel and every 'prism apply' use) into its worktree for a live review. The next rollout (niri-material ring beam, 2026-09-21) assumed PATH prism was the main checkout: main could not read the worktree format's profiles, merging main into the branch conflicted on ~900 lines, and the daily driver sat for minutes with a config the installed compositor could not load; the fix was an unplanned bridge worktree (prism-1514d3-bridge).

Add to the global instructions and to the parking/finishing steps of the relevant skills (superpowers finishing-a-development-branch Step 6, using-git-worktrees, the tasks park protocol):
- A live test that must run a worktree's code goes through an explicit path ($WORKTREE/bin/<tool>) or an env override, never by repointing a shared launcher, symlink, service unit or config include on the host.
- When a host pointer must be repointed, the task records it in a note at that moment (what, from, to, how to restore) and restores it before 'tasks park' or 'tasks done'; while it stands, the park note names it.
- Worktree removal checks for host pointers resolving into the worktree first (readlink -f over ~/bin/*, ~/.local/bin/*, user systemd units, known config includes) and refuses while one does.
- A rollout that hands live state to another project's tool checks where that tool resolves on PATH before assuming the main checkout.

Evidence: prism-aec90f notes of 2026-09-21; niri-material memory arch-package-pin-rollout.

## Notes

- 2026-09-21T13:52:26Z (main): started
  provenance: {"harness_session":"claude-code:95c6e29f-0d94-4e60-9943-1aeedd49379f","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T13:53:28Z (ai-b5171d): superpowers finishing-a-development-branch and using-git-worktrees are the pinned upstream plugin (agents/skills/superpowers submodule, 6.3.0) and cannot carry the step; the global rule in AGENTS.md wins over them per the skill precedence, and the tasks skill (tasks 9191141) and flow step 5 carry it where the park protocol lives.
- 2026-09-21T13:53:28Z (main): done
  provenance: {"harness_session":"claude-code:95c6e29f-0d94-4e60-9943-1aeedd49379f","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T13:53:28Z (main): Rule added to AGENTS.md (Git section, after the worktree bullet) and to flow step 5; the tasks skill's park step and worktree paragraph carry it in tasks 9191141. superpowers is the pinned upstream plugin, so its Step 6 is covered by the global rule's precedence rather than edited.
  provenance: {"harness_session":"claude-code:95c6e29f-0d94-4e60-9943-1aeedd49379f","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
