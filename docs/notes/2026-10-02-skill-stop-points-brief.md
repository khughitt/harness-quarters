# Brief: superpowers stop points under the Decisions rule

Ideas: tack-e293d7, tack-b8223d. Related context: tack-c437b4, tack-89dff8 (SDD review
defects, upstream).

## 1. Problem

The global Decisions rule tells agents to act on a held recommendation and stop only for
review, taste, spend, or outside actions. Two vendored superpowers skills script stops
that the rule says to skip, and agents follow the skill: a finished, authorized
implementation halts for a user turn that adds no information.

## 2. Current behaviour and evidence

- **finishing-a-development-branch** (tack-e293d7, reported from tasks under Codex): Step 4
  says "present exactly these 3 options … Which option?" and "Present the menu exactly
  as written" (`agents/vendor/superpowers/skills/finishing-a-development-branch/SKILL.md:54-80`).
  The skill's own wording is more specific than the global rule, so the agent asks.
- **subagent-driven-development final review** (tack-b8223d, reported from ops): after
  the final review, "ONE fix subagent … exactly one scoped re-review … There is no
  second fix wave — residual load-bearing findings surface to your human partner"
  (`…/subagent-driven-development/SKILL.md:458-469`). When the re-review reproduced
  load-bearing protection gaps, the run stopped and needed a new user turn to resume.
  Upstream obra/superpowers#2431 (open) proposes one targeted extra round for
  Critical/Important breakage *introduced by* the fix wave.
- The Decisions rule landed in tack-062b74 and tack-c62995 (both done). Neither named
  skill-scripted stops; `using-superpowers` says user instructions outrank skills, but
  a general rule loses to a skill's "exactly as written".
- Counterexample worth keeping: tack-7d9375 was parked for its integration decision on
  2026-10-02 because merging made a global rule live for every session. That stop was
  right, and is an outside-the-repository effect, not a menu.

## 3. Constraints

- Vendored superpowers skills are upstream; local changes go in tack's own skills,
  wrappers, or instructions (`docs/notes/2026-09-29-cross-harness-review-brief.md` §3).
  The skills are symlinked unmodified from the pinned submodule.
- Spec and plan gates stay with the human (Decisions rule; tack-91e028).
- Profiles set PR policy (`PRs: by-permission` for personal); a push or PR is an outside
  action and stays a stop.
- flow-trial-1 runs half of enrolled tasks with flow off from 2026-10-05, so a fix that
  lives only in the flow skill misses those tasks and confounds the trial.

## 4. Alternatives

1. **Name skill stop points in the Decisions rule (lean).** One sentence: a skill's
   scripted question (an integration menu, a "surface residual findings" step) is a
   bounded decision under this rule unless it falls in the stop list. A local merge is
   bounded; a push, a PR, or a merge that makes a live global surface change (tack's
   own instructions, hooks, services) is an outside action and stops. For final-review
   residuals: continue corrective rounds on load-bearing findings up to the task loop's
   five-round breaker, then surface.
2. **Flow skill owns integration and fix waves.** Precise, but only reaches flow-on
   tasks, and changes one arm of a running trial.
3. **Upstream only.** Comment on #2431 and propose a "repository instructions choose"
   clause for finishing. Slow and may be declined; keep as a complement to 1.

## 5. Unanswered questions

- Is a local merge of a finished, reviewed branch a decision you want agents to take
  without asking, with the outside-effect exception above? — the user.
- Should final-review corrective rounds be capped at five (the task loop's breaker) or
  at one extra round (#2431's proposal)? — the user; #2431's outcome informs it.
- Comment on #2431 with the protection-gap case from tack-b8223d? — the user (public post).

## 6. Proposed decomposition

Goal: tack-36f493 (this brief). No research is needed: the evidence is the skill text
above. Once the questions are answered, the change is one Decisions-rule edit under
`--process direct`, filed as a child of the goal; tack-e293d7 and tack-b8223d wait on
those answers. tack-c437b4 and tack-89dff8 are review-quality defects in upstream SDD and
are handled outside this goal.
