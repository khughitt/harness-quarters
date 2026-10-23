---
id: hq-7cf7c1
title: "Test suite subprocesses inherit the calling session's editor and pager environment, so exported editor variables fail the rebase-continue test"
status: idea
priority: 2
created: 2026-10-23T16:54:42Z
updated: 2026-10-23T16:54:42Z
depends: []
tags: [feedback, friction, "from:hq"]
---

Running the repository suite from an agent session whose environment exports terminal-program variables (editor and pager overrides set to noninteractive values) produced one failure in a git-rebase-with-stop-hook test: a rebase continue that the test drives with a core.editor command-line setting failed, and the error named an editor false. Root cause: the test's git helper starts subprocesses with the inherited environment, and a GIT_EDITOR export outranks that core.editor setting, so the continue tried to open editor false and died. Expected: the suite passes whatever the calling session's terminal-program variables are. Suggested direction: the test's subprocess helper builds its environment key by key (at minimum unsetting editor and pager exports and inherited git variables) rather than passing the environment through. Verified in a fresh worktree before any change: the single test passes again with the three editor variables removed from the environment.
