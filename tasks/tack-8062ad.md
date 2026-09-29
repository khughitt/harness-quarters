---
id: tack-8062ad
title: "Find what in tack's tree and history must not be public, and choose scrub or fresh history"
status: done
priority: 2
size: m
complexity: mid
process: direct
owner: main
created: 2026-09-27T13:35:14Z
updated: 2026-09-28T09:27:36Z
started: 2026-09-28T09:25:37Z
completed: 2026-09-28T09:27:27Z
depends: []
parent: tack-5b608f
tags: [rules]
model: claude-opus-5-5
agent: claude-code/claude-opus-5-5
---

Question: What in the tracked tree and the full git history is sensitive — work or client names, MCP server URLs, trusted project paths, the autoMode environment text in claude/settings.json, home and Dropbox paths, account names, anything in session-derived notes under docs/ — and does going public need a history rewrite or a fresh history?
Where to start: codex/config.work.toml and claude/settings.work.json (work MCP servers and projects), claude/settings.json autoMode, codex/config.toml [projects.*], docs/notes and docs/reports, archive/; git log -p for removed secrets; a scanner such as gitleaks over the full history.
Bound: Read-only: a findings list with file, commit and kind, plus a recommendation (edit in place, move to an untracked local layer, rewrite history, or publish from a squashed fresh history). No rewrite or visibility change.
Expected result: The findings and the recommendation as a note here; the remediation is filed from them and the public step depends on it.
Ideas it wakes: none.

## Notes

- 2026-09-28T09:25:37Z (main): started
  provenance: {"harness_session":"claude-code:344dc247-3419-4443-85b2-8c2de56a3ee4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-28T09:27:27Z (main): Findings (349 commits, 295 tracked files). gitleaks over full history: no secrets. HISTORY-ONLY: b0e3454 claude/claude.json (removed 3aa59a0) is a full ~/.claude.json: Anthropic accountUuid, organizationUuid, email, userID, billing type, 10 project paths incl. work checkouts, githubRepoPaths naming work org repos. WORK/CLIENT NAMES (tree + ~25 commits incl. commit subjects e121918, 7475511): codex/config.work.toml (work checkout trust list, work SaaS MCP server URLs), claude/settings.work.json (work plugins), codex/config.toml [projects.*] (work paths), agents/profiles/work.md (work gh account), generated AGENTS.md projects block (nrp/rad/vdocs describe client work), docs/specs+plans 2026-09-19 project-profiles, doc/instruction-provenance.md, doc/ref/marimo-best-practices.md, task notes tack-0a09d0/bb99d4/c4cbbc/922cfa/deb3e4. HOST PATHS: home-directory and Dropbox absolute in AGENTS.md, codex configs, docs, tasks; tracked symlinks curate/scope/quick-add point at absolute Dropbox paths. STALE: claude/settings.json autoMode.environment describes the familiar repo (not sensitive, wrong). THIRD-PARTY: doc/ref holds copied upstream docs (r3f, xstate, vitest, Khronos wiki) and a 4.2M saved blog page (doc/ref/noise); vendored addyosmani/agent-skills lacks its MIT notice; repo has no LICENSE. docs/notes briefs: clean.
- 2026-09-28T09:27:27Z (main): Recommendation: publish from a fresh squashed history, not a filter-repo scrub. Rejected scrub because the work names live in ~25 commits' contents AND commit subjects plus the root commit's claude.json; replace-text + message rewriting is easy to miss one of, and a miss is permanent once public. Before the squash, fix the tree: move host- and work-specific layers to an untracked local layer (work configs, codex project trust list, the generated projects block), redact work names and host paths in docs/tasks, drop or link out third-party copies, add LICENSE and the vendored MIT notice. Keep the full history as a private archive (bundle or khughitt/tack-history) before force-pushing the new root. Treating employer/client names as private is my default; override if you are fine naming the employer.
- 2026-09-28T09:27:27Z (main): done
  provenance: {"harness_session":"claude-code:344dc247-3419-4443-85b2-8c2de56a3ee4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-28T09:27:27Z (main): Findings and recommendation (fresh squashed history after tree remediation) in notes; remediation filed as null, null, null; public step depends on null
  provenance: {"harness_session":"claude-code:344dc247-3419-4443-85b2-8c2de56a3ee4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-28T09:27:36Z (main): Correction to the close note (ids were not captured): remediation is tack-4cd688 (local layer, planned), tack-b0197e (tree scrub), tack-90bf74 (fresh history; depends on both); tack-58f6b7 depends on tack-90bf74.
