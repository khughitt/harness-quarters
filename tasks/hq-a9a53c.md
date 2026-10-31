---
id: hq-a9a53c
title: A plan that replaces or re-expresses a function lists every caller of the old one
status: shelved
priority: 2
defer: 2026-11-30
created: 2026-09-24T14:36:14Z
updated: 2026-10-31T11:07:26Z
depends: []
tags: [flow]
source: ai-c78706
agent: "claude-code/claude-opus-5-5[1m]"
---

Retro group (curation pass ai-c78706), 2 retros in one effort: ai-e2fac3 (the review's important finding was a call site the plan did not list; a grep for gates( callers would have caught it in a minute), ai-634de8 (two reviews found callers of the raw gates() the plan omitted; 'a grep callers of the old function line belongs in any plan that re-expresses one'). Proposal: one line where plans are written under the flow: a plan that replaces, renames, or re-expresses a function carries the grep of its callers and names each one's disposition. Target: the flow skill's planned state, or the writing-plans override note (superpowers is vendored: override, never edit). Weak recurrence (one effort tree); human decides.

## Notes

- 2026-09-24T14:50:06Z (main): shelved: a review outside ai-634de8's tree finds a caller that a plan re-expressing a function did not list
- 2026-09-24T14:50:06Z (main): scope: shelved; both retros are the same finding in one effort (ai-e2fac3 inside ai-634de8); a one-line plan rule on one instance is untested; wakes on a second effort
- 2026-10-31T11:07:24Z (main): shelved: a review outside ai-634de8's tree finds a caller that a plan re-expressing a function did not list
- 2026-10-31T11:07:26Z (main): scope: shelved; renewed missing checkpoint to 2026-11-30 with the original second-effort condition intact. Source hq-c78706 records the initial proposals as one functional-core effort; 127 later retros since 2026-09-24 (no scan warnings) do not clearly establish another review finding an omitted caller. Checked obs-8cfc12: a real CLI test exposed rendering/exit behavior beyond plan snippets, not an identified review finding of an unlisted caller, so it does not satisfy this condition. Current writing-plans/flow skill searches and open lore/flows caller searches found no matching existing follow-up. This remains a proposed general rule, not permission to add it. Evidence: hq 58c9ffb, flows 55b28e4, obs 2e31cd0. origin: filing unavailable (no stamped creation occurrence); source hq-c78706 identifies agent curation proposals but does not bind this member's filing call; origin field unchanged.
  provenance: {"harness_session":"codex:01a1919f-7e52-7202-94dd-12751aee4777","harness_session_source":"CODEX_THREAD_ID"}
