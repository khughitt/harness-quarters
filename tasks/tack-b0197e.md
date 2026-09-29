---
id: tack-b0197e
title: "Scrub tack's tracked tree for publication: work names, host paths, third-party copies, license"
status: done
priority: 2
size: s
complexity: low
process: direct
created: 2026-09-28T09:27:27Z
updated: 2026-09-28T09:51:28Z
completed: 2026-09-28T09:51:28Z
depends: []
parent: tack-5b608f
tags: [rules]
model: claude-opus-5-5
agent: claude-code/claude-opus-5-5
---

From tack-8062ad findings note. Redact work/client names and gh account in docs/specs+plans 2026-09-19 project-profiles, doc/instruction-provenance.md, doc/ref/marimo-best-practices.md, agents/profiles/work.md and the listed task notes (task notes via tasks edit); replace home-directory and Dropbox absolute paths in docs and AGENTS.md prose; make curate/scope/quick-add symlinks relative or link-managed; drop the stale autoMode.environment from claude/settings.json; remove doc/ref copies of upstream docs and the saved blog page (link instead); add LICENSE and carry addyosmani/agent-skills' MIT notice. Check: the work-name and host-path grep (its terms live off the tracked tree) over HEAD returns nothing outside the local layer.

## Notes

- 2026-09-28T09:46:54Z (tack-scrub): Tree scrub done for docs, work profile (account now read from the profile line's gh: field), path rule wording, symlinks (relative sibling links), doc/ref upstream copies removed, autoMode dropped, LICENSE + upstream MIT notice. codex/rules/default.rules (Codex-written host paths) belongs to tack-4cd688's local layer. Blocker: notes in 8 task records (0a09d0 8062ad 91fa3a 922cfa bb99d4 bc49ed c4cbbc deb3e4) carry the names/paths; tasks refuses note edits (append-only; feedback tasks-cc9a31).
- 2026-09-28T09:51:27Z (tack-scrub): One-time direct edit of note text in 8 task records (user-approved 2026-09-28; CLI notes are append-only, tasks-cc9a31): same redaction map as the docs; tasks check clean.
- 2026-09-28T09:51:28Z (tack-scrub): done
  provenance: {"harness_session":"claude-code:344dc247-3419-4443-85b2-8c2de56a3ee4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-28T09:51:28Z (tack-scrub): Tracked tree scrubbed except tack-4cd688's local-layer files (work configs, codex project trust and rules, the generated AGENTS.md projects block): work account, work paths and vendors, host paths redacted in docs and task notes; relative sibling skill links; upstream doc copies removed; autoMode dropped; LICENSE and upstream MIT notice added; tests 415+71 pass
  provenance: {"harness_session":"claude-code:344dc247-3419-4443-85b2-8c2de56a3ee4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
