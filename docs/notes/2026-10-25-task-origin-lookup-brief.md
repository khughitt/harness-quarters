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
  establish whose ask the record holds. obs-d98663 owns implementation; no
  `session_logs.py` exists in obs main at `9fda68a`.
- obs-02e88b already investigates report-to-request joins in at most six cases,
  including unstamped and unavailable sources. Reuse its evidence and existing
  brief rather than commission another origin-join study. obs-c5c599 owns the
  wider timeline, stage and aggregation effort.
- hq-c8aef1 itself has no creation occurrence stamp or `origin_session`. Stage 1
  is unavailable (no stamp) under the current retrieval procedure; stage 2 is not
  applicable. Its origin remains unknown. This does not establish that its
  transcript is absent from this host.

## Constraints

obs owns content parsing and the session reader; hq owns store location and
lifecycle. Compose supported reader output rather than adding another parser,
index or store-root list. The reviewed reader's Stage A/Stage B separation and
2027-02-16 trial-readout gate remain in force; this brief authorizes no rollout.
Preserve the original capture on hq-c8aef1. hq-4d77cc and hq-34163a remain related,
unprocessed reports about Claude subagent files and Codex parent traversal.
Missing stamps, unreadable transcripts, competing calls and unavailable stderr
must remain explicit limitations. Creation-time proximity alone cannot prove
creation or user intent; any historical fallback must label its evidence strength.

## Alternatives

1. **Lean: compose the supported reader with occurrence binding.** Reuse stamps,
   call/result records and parent links, applying scope's two-stage evidence
   rules. After the reader and existing join study land, determine the smallest
   command surface and owner through design review. This is the controller's
   recommendation, not an established user preference about syntax.
2. Document a multi-command recipe only. Useful as an interim path, but it leaves
   the captured one-command outcome open and still requires manual binding.
3. Add a standalone hq transcript scanner now. Reject: it duplicates parsing and
   discovery, and precedes the existing reader and join evidence.

## Unanswered questions

- Which request edges can be established, inferred or only reported unavailable?
  obs-02e88b's existing bounded study answers this; consume the shipped producer
  semantics rather than its now-historical assumption that tasks-a58a90 is open.
- Does the implemented reader expose enough call/result and relationship evidence
  for occurrence binding, including reuse ambiguity and older requests? Evaluate
  obs-d98663's delivered interface against the manual demonstrations, then design
  any missing composition. Neither generic task selection nor this brief settles it.
- How should an unstamped historical lookup be bounded and labelled, and where
  should the single-command composition live? These remain design decisions after
  the evidence above, without promising a time-match heuristic as proof.

## Proposed decomposition

- hq-c8aef1 stays an idea with verdict `briefed`, under existing goal hq-cff824,
  and waits on obs-02e88b and obs-d98663. Preserve priority 2 and the original body.
- Reuse obs-02e88b's existing six-case bound and brief. Add hq-c8aef1 to its
  `Ideas it wakes`; completion records its finding with `--no-reviewed` before
  merging. No additional research or design task is filed in this pass.
- obs-d98663 remains the existing reader build, without expanding its reviewed
  contract. Its dependency closure readmits this idea; re-scope against both
  outcomes before commissioning a design or implementation of the origin query.
