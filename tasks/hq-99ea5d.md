---
id: hq-99ea5d
title: Five eval cases before the eval schema
status: done
priority: "2"
size: s
complexity: mid
process: direct
owner: main
created: 2026-09-22T03:05:35Z
updated: 2026-09-24T14:46:36Z
started: 2026-09-24T14:38:00Z
completed: 2026-09-24T14:46:36Z
depends: [hq-634de8]
tags: [flow, obs]
model: "claude-opus-5-5[1m]"
agent: claude-code/claude-fable-5-1
---

Outcome: five eval case files in ai, written before any shared schema exists, to find out what a case record needs. Cases: the two stall shapes on ai-c62995 (repeated parking of a claimed unblocked task; a subagent ending its turn with a live claim); the induced vacuous park from the Stop-hook probe ai-80b836; a skill invoked when its trigger applied (from obs skill telemetry, obs-e52980); a gate note the corpus must reject (ai-634de8 section 4.1). Each case names a subject at a version (skill, flow, rule, hook), inputs (a prompt, a fixture, a task or session id), an expected answer typed as boolean, choice, or score against a rubric, and a judge (a check command, a bounded question, or human). Approach: a provisional frontmatter under agents/evals/cases/, one file per case, no runner and no validator; a short note on the task recording which fields every case needed, which only some needed, and which judge kinds appeared. Verification: five files exist; the note lists the fields; the frontmatter is identical in shape across the five or the note says where it could not be. Feeds the obs goal that defines the shared case and verdict schema.

## Notes

- 2026-09-22T03:05:35Z (main): gate: scoped — probe before schema: five cases, provisional frontmatter, note the fields; direct
- 2026-09-24T14:38:00Z (main): started
  provenance: {"harness_session":"claude-code:a326cf7b-df61-4526-b766-65c25ebbbbde","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-24T14:38:08Z (feat/eval-cases): gate: implementing — worktree .worktrees/eval-cases (feat/eval-cases)
- 2026-09-24T14:42:18Z (feat/eval-cases): fields: every case needed id, title, subject{kind,name,version}, inputs[{kind,ref}], expected{type,claim,value}, observed{value,at}, judge{kind, question | command+pass}, source, evidence. Only some: expected.rubric (score, choice), expected.choices (choice), expected.reason (a choice with a sub-answer: the malformed why), inputs.window/agent/cwd/value (session windows, a subagent id, inline fixtures), judge.cwd. Judge kinds: question 3, check 2, human 0. Top-level shape identical across the five; nested optional keys vary as listed.
- 2026-09-24T14:42:18Z (feat/eval-cases): schema findings: (1) observed is separate from expected — a case pins a failure at a version (two cases expected!=observed), so the shared schema needs a verdict per subject version beside the case, not one answer; (2) subject.version is a set (one rule spans the tasks skill and AGENTS.md in two repos) and not always a git rev (the Stop-hook probe is a harness version plus model); (3) subject.kind needed parser beyond skill/flow/rule/hook; (4) every case needed expected.claim, the proposition the typed answer answers; (5) session inputs point into live stores (~/.codex, ~/.claude, the obs index), which retention (ai-401088) will delete — cases need a snapshot or a retention exemption; (6) a check judge could not express ordering against the transcript, so the first tasks call moved into inputs.
- 2026-09-24T14:46:28Z (feat/eval-cases): review corrections to the field notes: the session's working directory is inputs.session_cwd and the check's is judge.cwd (distinct meanings, both kept). More schema findings: (7) a vendored plugin's version at a past session is not recorded anywhere (superpowers before 6.3.0 in the subagent case), so a subject version must be captured when the case is written; (8) an uncommitted probe stub cannot be a reproducible subject, so a hook case needs its stub committed or inlined; (9) a question judge's rubric must count the loose form of the claim explicitly (says it will continue), or two judges disagree (2 vs 5).
- 2026-09-24T14:46:28Z (feat/eval-cases): gate: verified tree:b2c27a19975279bf904132805a9ab8d4452072b4 — checks: yaml parse of all five frontmatters (one top-level shape and every subject.version a list) and both check judges print their pass values and tasks check clean; review: important addressed stall-repeated-park rubric counted only turn ends naming a step, important addressed subagent subject cited an AGENTS.md section added after the incident, important addressed subagent case named the controller task not the claimed ns-6c56fc, minor addressed probe overstated for the subagent Stop, minor addressed reopen gap was 50s not 34s, minor addressed probe version was a string not a list, minor addressed cwd meant two things; reviewer: claude-code/claude-opus-5-5[1m]
- 2026-09-24T14:46:36Z (feat/eval-cases): retro: pinning each case to a real session turned up two facts the scoping missed — the subagent's claim was on ns-6c56fc, not the goal task, and a past plugin version cannot be recovered — and the reviewer caught both only because the brief pointed it at the raw transcripts rather than my summaries. Hurt: I wrote the implementing gate from the main checkout after creating the worktree and had to move it, the where-am-I shape filed as ai-69cba6 an hour earlier.
- 2026-09-24T14:46:36Z (feat/eval-cases): done
  provenance: {"harness_session":"claude-code:a326cf7b-df61-4526-b766-65c25ebbbbde","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-24T14:46:36Z (feat/eval-cases): five provisional eval cases under agents/evals/cases; fields and nine schema findings recorded in notes
  provenance: {"harness_session":"claude-code:a326cf7b-df61-4526-b766-65c25ebbbbde","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
