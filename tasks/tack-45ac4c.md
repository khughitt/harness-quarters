---
id: tack-45ac4c
title: Design composable project profiles for agent instructions and behavior
status: done
priority: "2"
size: m
complexity: high
process: planned
owner: project-profiles
created: 2026-09-19T16:02:58Z
updated: 2026-09-21T12:08:47Z
started: 2026-09-19T16:12:47Z
completed: 2026-09-21T12:08:47Z
depends: []
tags: [rules, hooks, skills]
model: "claude-opus-5[1m]"
agent: codex
spec: docs/specs/2026-09-19-project-profiles-design.md
plan: docs/plans/2026-09-19-project-profiles.md
---

Context

On 2026-09-19, review of the global Design & Plan Docs rule exposed an overbroad default. The motivating incident (ai-889237, commit f6e3f0e) was unwanted design/plan documents in work and external PRs, but the implementation disabled committing them in personal projects too. c15f2709 (ai-341dcc) shortened that rule; 734e9b2d (ai-4a90a7) combined status guidance. Immediate correction ai-699ae6 restores committing plans/specs by default in personal projects and shortens the global prose. The user wants different project contexts recognized explicitly instead of adding more conditional rules to one user-level AGENTS.md.

Design scope

- Support personal, work, and external projects as initial profiles or documented examples. Allow arbitrary user-defined profiles, including different kinds of personal projects; avoid a hard-coded three-category switch.
- Explore composition: core + one or more selected profiles + repository-specific instructions/configuration. Decide explicit ordering, conflict handling, and how session instructions retain precedence. Prefer composition over inheritance and hand-maintained copies of AGENTS.md.
- Define how a project selects profiles, how defaults/overrides work, and how a user or agent can inspect the effective profile and the source of each setting. Consider canonical checkouts, linked worktrees/symlinks, forks, owned public repos, and mixed account contexts. A repo being outside the work directory does not establish that it is personal.
- Determine which elements profiles configure: AGENTS.md/CLAUDE.md, harness settings, skills, hooks, and behavior such as design-doc tracking, GitHub account selection and external-PR requirements. Start with demonstrated differences; avoid building an unrestricted configuration system speculatively.
- Assess reuse of ai-ec379d, the existing recursive instruction/skill-fragment composition idea, rather than introducing a second incompatible composition mechanism. Neither task must depend on the other until the design establishes a need.

Integration and migration

The ops hooks/claude-pretooluse design_doc/design_docs_wanted check still blocks staging or committing docs/superpowers/ unless root instructions name a directory inside it or the user sets ops.designDocs. Its refusal text states the old universal default. This behavior needs alignment with the corrected policy; changing AGENTS.md alone does not change that hook. Coordinate an ops task once the classification/selection contract is defined. Check current hook ownership before editing it.

Plan how to handle existing .git/info/exclude entries in personal checkouts without bulk staging private or unrelated files. Keep legitimate work/external exclusions and preserve excluded docs when removing worktrees. Do not reinterpret historical audit entries as current policy. Keep shared user-level instructions short and put profile-specific details in their selected layer.

Acceptance for the design

A reviewed spec and implementation plan describe profile selection, ordered composition, provenance/explainability, and safe migration, with concrete examples for personal/work/external plus a custom profile. Show how the policy and hook agree on document tracking in each example, including worktrees and an explicitly overridden project. Identify cross-project work and ownership before implementation. This task records the follow-up; no profile machinery is part of ai-699ae6.

## Notes

- 2026-09-19T16:12:47Z (main): started
  provenance: {"harness_session":"claude-code:059a3301-decb-4400-9836-602dac084b44","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-19T16:34:15Z (project-profiles): Brainstorm done: selection via identity.toml profiles + profiles.toml path families + git config agent.profile override, external by default; delivery via SessionStart injection of ai fragments; typed keys design_docs/gh_account/pr_draft/home owned by at most one selected profile (conflict = check error); homes stay a session fact; settings/skills per home out of v1. Spec docs/specs/2026-09-19-project-profiles-design.md; open question: what installs the AGENTS.md/settings copies into the four harness homes.
- 2026-09-19T16:34:22Z (project-profiles): tasks check in the worktree reports pre-existing doc_missing for the flow-state-machine spec/plan: they sit in main's .git/info/exclude and are absent from any worktree — the §9 step 4 migration case, not caused here.
- 2026-09-19T16:34:22Z (project-profiles): parked (waiting on user, review): User reviews docs/specs/2026-09-19-project-profiles-design.md (branch project-profiles, .worktrees/project-profiles); on approval invoke writing-plans for the implementation plan; answer §11 open question 1 (what installs the four harness-home copies)
  provenance: {"harness_session":"claude-code:059a3301-decb-4400-9836-602dac084b44","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-19T16:58:53Z (project-profiles): Review round 1 (6 findings) applied: resolver failure refuses guarded writes naming no account (kind unresolved); claude-pretooluse + claude-profile registered in settings.work.json; ops-profile session is the complete fallback, run before any work; migration reordered fragments→ops→registration→hook consumers→prose removal; classify via canonical checkout, read repo prose from the working tree; the eight harness files are symlinks to tracked ai files (my earlier copy claim was an lsd artefact), installer dropped.
- 2026-09-19T16:58:58Z (project-profiles): parked (waiting on user, review): User reviews revised docs/specs/2026-09-19-project-profiles-design.md (c9401df, .worktrees/project-profiles) after review round 1; on approval invoke writing-plans
  provenance: {"harness_session":"claude-code:059a3301-decb-4400-9836-602dac084b44","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-19T17:02:24Z (project-profiles): resumed
  provenance: {"harness_session":"claude-code:059a3301-decb-4400-9836-602dac084b44","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-19T17:02:38Z (project-profiles): Review round 2: §13 tests the unresolved diagnostic and the hook/CLI exit codes; §9/§11 state that live checks follow integration to main in ai and ops because the home symlinks and hook paths target the main checkouts. No architectural blockers remain; §12 order question settled by declared order.
- 2026-09-19T17:16:10Z (project-profiles): Plans written: ai docs/plans/2026-09-19-project-profiles.md (steps ai-3a1a60, ai-c4cbbc, ai-922cfa) and ops docs/plans/2026-09-19-project-profiles.md under goal ops-4a3014 (steps ops-72a7df, ops-7272b3, ops-b601db, ops-0a0059, ops-acc467, ops-c29946, ops-ee2ee2). Cross-project deps to record once both branches are on main (tasks dep routes by registered root): ops-b601db on ai-3a1a60; ai-c4cbbc on ops-0a0059 and ops-b601db; ai-922cfa on ops-acc467.
- 2026-09-19T17:16:10Z (project-profiles): parked (waiting on user, review): User reviews the two implementation plans (ai .worktrees/project-profiles/docs/plans/2026-09-19-project-profiles.md; ops .worktrees/project-profiles/docs/plans/2026-09-19-project-profiles.md). On approval: merge both branches to main, record the four cross-project deps from the note, then execute ai-3a1a60 first.
  provenance: {"harness_session":"claude-code:059a3301-decb-4400-9836-602dac084b44","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-19T17:30:43Z (project-profiles): Plan review round 1 (7 findings) applied. ops: INSTRUCTION_FILES kept (design_dirs_named), os.environ in main(), profile_of catches every resolver exception so a guarded write never passes through the exit-0 wrapper, config_problems type-checks every container with hook-entry tests on malformed files, just install links ops-profile into ~/.local/bin and is verified from a non-checkout, audit emits git -C <checkout> add -- <quoted> and treats glob entries separately, Codex probe uses a disposable CODEX_HOME with a hook-only marker and a transcript read. ai: Task 2's work-home check proves registration via the existing attribution refusal; new Task 3 (ai-0a09d0) proves profile-aware enforcement with a tokenless GH_CONFIG_DIR and a stub gh after ops Task 5; Task 4 (ai-922cfa) removes prose only after that and after ops-profile resolves on PATH. Cross-project deps still to record after merge: ops-b601db on ai-3a1a60; ai-c4cbbc on ops-0a0059, ops-b601db; ai-0a09d0 on ops-acc467.
- 2026-09-19T17:30:43Z (project-profiles): parked (waiting on user, review): User re-reviews the revised plans (ai 4c6f67c, ops cf21485). On approval: merge both branches to main, record the cross-project deps from the note, run just install in ops main once ops Task 2 lands, then execute ai-3a1a60.
  provenance: {"harness_session":"claude-code:059a3301-decb-4400-9836-602dac084b44","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-19T17:33:26Z (project-profiles): resumed
  provenance: {"harness_session":"claude-code:059a3301-decb-4400-9836-602dac084b44","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-19T17:33:26Z (project-profiles): Plan review round 2 applied: work-home probe unsets GH_TOKEN/GITHUB_TOKEN and instructs one command with no account preflight, with calls.log read to tell a preflight from a guard miss; Codex probe runs codex exec --dangerously-bypass-hook-trust (as relay-guard-probe does) and requires ran.txt from the hook before NONE counts as a delivery result.
- 2026-09-19T17:33:26Z (project-profiles): parked (waiting on user, review): User approves the plans (ai c7df363, ops e364c4b) or asks for another pass. On approval: merge both branches to main, record the cross-project deps from the notes, then execute ai-3a1a60.
  provenance: {"harness_session":"claude-code:059a3301-decb-4400-9836-602dac084b44","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-19T17:39:52Z (main): Plans approved after three review rounds; both branches merged to main (ai 0c92888, ops e364c4b); four cross-project deps recorded. Execution paused at the user's request before ai-3a1a60. Worktrees kept for execution: ai .worktrees/project-profiles (branch project-profiles), ops .worktrees/project-profiles (branch project-profiles); both now equal main.
- 2026-09-19T17:39:52Z (main): parked (waiting on user): Execution: start ai-3a1a60 (fragments) in ai .worktrees/project-profiles, then ops-72a7df in the ops worktree; order per the plans.
  provenance: {"harness_session":"claude-code:059a3301-decb-4400-9836-602dac084b44","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T11:49:03Z (main): Park note is stale: ai-3a1a60 and ops-72a7df are done, and ai-c4cbbc (hooks registered in both homes, Profiles section) landed 2026-09-21. Remaining: ai-deb3e4 (Codex hooks file), ai-0a09d0 (work-home enforcement check, plan Task 3), then ai-922cfa (global prose). Migration item seen on the way: four spec/plan docs for the flow-state-machine and session-logs tasks live only in main's .git/info/exclude, so tasks check reports doc_missing in every ai worktree — the personal-profile exclusion legacy the design names.
- 2026-09-21T12:08:47Z (main): done
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T12:08:47Z (main): Spec and plan reviewed and executed: fragments (ai-3a1a60), resolver/checks/hooks in ops (ops-4a3014), hooks registered in both Claude homes with the Profiles section (ai-c4cbbc), enforcement proven live in the work home (ai-0a09d0), global prose removed (ai-922cfa), Codex registration after the SessionStart probe (ai-deb3e4). ops-profile audit exists for migration step 6; the per-checkout adds are the user's (ops task filed). Open follow-ups: ops-d12cb7 (home detection from the payload), ai-589cdd (tracked-settings noise)
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
