# Recover a task's filing call and preceding human request

## Problem

hq-c8aef1 asks for one task-id command that finds the creating session and the
human turns preceding its creation call. Its captured workaround used an id grep,
creation-time comparison and handwritten role filtering. A later reader mentioning
the id is not its creator; a nearby human turn is not automatically its originating
ask. This pass preserves that requirement without treating the generic reader as
delivery of an origin query.

## Current behaviour and evidence

- tasks main `7c3b9d2` delivered creation and feedback-occurrence stamps through
  tasks-053e89. New records carry a `created` note with the occurrence time and
  `harness_session`; Codex workers may carry `root_session`, and an older ask may
  be identified by `origin_session`. Older records are not backfilled.
- The scope skill's two-stage procedure binds the filing call by arguments, time
  and result, then follows an older request only from that filing evidence.
  tasks-4d39db's attached `retrieval-demo-report.md` demonstrates matched,
  inferred, ambiguous and unavailable cases, including creation versus reuse with
  id-only output and absent stderr. These are recorded demonstrations, not fresh
  replications by this pass.
- hq's reviewed reader spec at `ae0f8ee`,
  `docs/specs/2026-10-23-session-evidence-reader-design.md`, D2 and section 9.4,
  supplies search/show, roles, paired calls/results, links, task evidence and
  coverage. It deliberately leaves trace composition for later. A task stamp or
  successful task command selects evidence; it does not bind a creation event or
  establish whose ask the record holds. obs-d98663 owns implementation and is
  live-claimed; no `session_logs*.py` exists in obs main at `707880a`.
- obs-02e88b is complete and merged (`5b012ee`). Its attached
  `join-study-report.md` checks six cases: two Codex filing calls bind as matched
  from their JSON results; one Claude id-only result binds as inferred. The index
  supplies the preceding human turn's position and byte count, not its words or
  intent; sampled gaps were 108 seconds to 38 minutes. No `origin_session` occurred
  in 46 stamped occurrences, so older-origin support remains unexercised by that
  sample. Unavailable sessions remain another-host-or-pruned, without guessing a host.
- obs-c5c599 now has existing follow-ups obs-f3c099 (preserve occurrence/session
  joins) and obs-a19f59 (design the indexed trace). The latter explicitly leaves
  transcript words and matched-call reading to this idea and obs-d98663. Reuse
  those owners; another join study or trace-design task would duplicate them.
- Related reports hq-4d77cc and hq-34163a map to the reviewed reader's sections
  5.2, 8 and 10: Claude child files, request-blob call deduplication and Codex
  controller links are already specified. Native spawn-result binding is stronger
  than the captured task-name workaround. Delivery remains obs-d98663, followed by
  obs-f5710b's deferred usage-skill and extractor integration.
- hq-042f9e adds a concrete guidance case. Its filing call is matched in
  `codex:01a17447-17a6-7e70-b83b-ade549ceec0a`, lines 274/279 (matching id,
  action and occurrence time). The original Claude child `agent-a3592a6be5c21c6d1`
  has a queued monitor notification at line 381 timestamped 13:44:10.616 UTC,
  inserted after line 380's 15:40:42.650 UTC result on 2026-09-24, with that
  result as its parent. The attachment's `prompt` holds the notification; this
  record has no `rendered` field. Event time, file/parent-chain position and actual
  processing time are different evidence. Spec sections 6.4/7.2 preserve file
  order and 8.1 includes attachments; the explicit interpretation caveat belongs
  in obs-f5710b's skill rewrite. Processing time remains unknown.
- hq-c8aef1 itself has no creation occurrence stamp or `origin_session`. Stage 1
  is unavailable (no stamp) under the current retrieval procedure; stage 2 is not
  applicable. Its origin remains unknown. This does not establish that its
  transcript is absent from this host.

## Constraints

obs owns content parsing and the session reader; hq owns store location and
lifecycle. Compose supported reader output rather than adding another parser,
index or store-root list. The reviewed reader's Stage A/Stage B separation and
2027-02-16 trial-readout gate remain in force; this brief authorizes no rollout.
Preserve the original captures. The three related guidance reports receive drop
proposals as covered work, not claims that their behavior has shipped. The current
skill and session-episodes still have the reported gaps at hq `dc51f61`.
Missing stamps, unreadable transcripts, competing calls and unavailable stderr
must remain explicit limitations. Creation-time proximity alone cannot prove
creation or user intent; any historical fallback must label its evidence strength.

## Alternatives

1. **Lean: compose the supported reader with occurrence binding.** Reuse stamps,
   call/result records and parent links, applying scope's two-stage evidence
   rules. With the join study complete, after the reader lands determine the smallest
   command surface and owner through design review. This is the controller's
   recommendation, not an established user preference about syntax.
2. Document a multi-command recipe only. Useful as an interim path, but it leaves
   the captured one-command outcome open and still requires manual binding.
3. Add a standalone hq transcript scanner now. Reject: it duplicates parsing and
   discovery, and precedes the existing reader and join evidence.

## Unanswered questions

- The six-case study establishes the available joins and their limits above; it
  does not validate older-request attribution or prove the nearest human turn is
  the ask. No additional research is needed before the reader can be evaluated.
- Does the implemented reader expose enough call/result and relationship evidence
  for occurrence binding, including reuse ambiguity and older requests? Evaluate
  obs-d98663's delivered interface against the manual demonstrations, then design
  any missing composition. Neither generic task selection nor this brief settles it.
- How should an unstamped historical lookup be bounded and labelled, and where
  should the single-command composition live? These remain design decisions after
  the evidence above, without promising a time-match heuristic as proof.

## Proposed decomposition

- hq-c8aef1 stays an idea with verdict `briefed`, under existing goal hq-cff824,
  and now waits only on open reader work obs-d98663. The existing obs-02e88b edge
  is satisfied; its completion already supplied the wake finding. Preserve
  priority 2 and the original body. No new goal, research or design task is needed.
- obs-d98663 remains the existing reader build, without expanding its reviewed
  contract. Its dependency closure readmits this idea; re-scope against both
  outcomes before commissioning a design or implementation of the origin query.
- hq-4d77cc and hq-34163a: propose drop as covered by obs-d98663 and obs-f5710b.
  hq-042f9e: propose drop into obs-f5710b with the attachment/order caveat above
  carried into that existing owner's task notes. No idea is dropped by this pass,
  and no skill, parser, extractor or live link changes before the trial gate.
