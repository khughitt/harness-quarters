# Recover a task's filing call and preserve cited transcript evidence

## Problem

hq-c8aef1 asks for one task-id command returning the creating session and preceding
human turns. hq-f127d1 asks to preserve cited session:line evidence as byte-exact
excerpts, with earlier assistant context, a row map, per-line SHA-256 and the whole
source file's hash. Both need supported evidence retrieval rather than repeated
handwritten scans. Neither nearby human text nor adjacent assistant text alone
establishes an originating ask or approval.

## Current behaviour and evidence

- **Reader delivered.** obs-d98663 merged at `062b73e`; hq's amended contract is
  revision 10 `e4f3d69`, `docs/specs/2026-10-23-session-evidence-reader-design.md`.
  At obs `beae367`, `session_logs.py` exposes search/show, task-evidence selection,
  paired calls/results, roles, source references and line hashes. It has no
  occurrence-binding or excerpt-export command. `session_logs_read.py::shaped`
  decodes raw bytes with replacement and caps display strings; that is not
  byte-exact preservation. `session_logs_lines.py` already reads physical bytes
  and hashes them; reuse that capability through a reviewed ownership/interface decision.
- **Fresh bounded check, 2026-10-29.** Showing lines 578–580 of
  `claude-code:f6ee61db-6c3f-480e-9fef-5b3a53b153c6` returned three records,
  call/result peers, hashes and `outcome: found`, with no limit hit. The full JSON
  result at line 580 matches hq-f127d1, `action: created` and
  `at: 2026-10-29T14:33:38Z`; line 579 is its filing call. Request-blob copies
  at lines 583–584 repeat that call/result and are not independent filings.
  The user's line 519 asks, “Great! Are there any follow ups we should create?”
  The agent proposed this particular tool from its preservation workaround:
  hq-f127d1's `origin: agent` remains supported. Stage 1 is matched; stage 2
  is not applicable (no `origin_session`). No transcript text is copied here
  beyond that short question.
- **Existing origin evidence.** tasks-053e89 delivered occurrence stamps at tasks
  `7c3b9d2`; older records are not backfilled. hq-c8aef1 has no creation
  occurrence stamp, so its stage 1 is unavailable under the current procedure,
  not proof that its transcript is absent. Stage 2 is not applicable; origin
  remains unknown. tasks-4d39db's attached `retrieval-demo-report.md` records
  matched/inferred/ambiguous/unavailable cases, including sourced id-only reuse
  with unavailable stderr.
- **Completed research, reused.** obs-02e88b merged at `5b012ee`; its attached
  `join-study-report.md` covers six cases: two matched Codex filing calls and
  one inferred Claude id-only call. Indexed human-turn positions and byte counts
  are not the user's words or ask attribution (sampled gaps: 108 s–38 min);
  no `origin_session` appeared in 46 stamped occurrences. These are recorded
  findings, not a fresh replication. The earlier full six-root reader run
  reported 25,563 files / 33 GiB / zero exceptions; it is also historical evidence.

## Constraints

obs owns parsing and the reader's `session-logs/1` interface; hq owns store
location/lifecycle and versioned samples. Consumers do not read index SQL or add
another store list/classifier. obs-a19f59 already designs the indexed friction
trace, depending on obs-f3c099's occurrence projection. It explicitly leaves
matched transcript calls and user words to hq-c8aef1/the reader; do not duplicate
that join study or expand those tasks incidentally. lore-2d31f3 separately owns
reversible placeholder derivatives, not raw transcript export.

Spec section 11 still gates treatment/measurement and Stage B rollout until the
2027-02-16 trial readout, followed by a date-specific reassessment. These handoffs
authorize design only, not new skills, links, collectors or activation. Preserve
the ideas' captured bodies and P2. Missing stamps, unreadable/remote/pruned
sources, competing calls, absent stderr and lookup errors remain distinct.
Existing hq-4d77cc/hq-34163a drops were tracking dispositions into
obs-d98663/obs-f5710b, not proof that every integration is delivered.
hq-042f9e's notification example remains a caution: event timestamp, file/parent
order and processing time differ; the latter was unknown. Its interpretation
guidance stays with obs-f5710b, not these follow-ups.

## Alternatives

1. **Lean: two small compositions over the reader.** Design filing-call binding
   separately from cited-line preservation, with shared references and honest
   evidence outcomes. Set ownership and any narrowly needed byte-reading interface
   in review. This is the scoping agent's recommendation, not an approved CLI.
2. Keep a multi-command/manual recipe. Useful today, but leaves both captured
   one-command outcomes and repeatable preservation open.
3. Add an independent hq scanner/index. Reject: it duplicates the assigned parsing
   boundary and risks differing role, copy and availability rules.

## Unanswered questions

- **Origin design owner:** settle the smallest command surface, full/id-only
  creation versus reuse, ambiguity, bounded unstamped-history fallback and older
  request navigation. Source words remain evidence; proximity is not attribution.
- **Export design owner:** settle citation identity, assistant-context selection
  (including absent/ambiguous context), byte/newline fidelity, map format, duplicate
  citations, concurrent source changes, whole-file hashing, local output permissions
  and partial-write/overwrite behavior. Display JSON is not the raw preservation format.
- **Both owners:** map existing demonstrations and small fixtures to correctness
  checks, and establish implementation/activation gate obligations. No new broad
  research is justified by the evidence gathered in this pass.

## Proposed decomposition

- Reuse hq-cff824; parent the previously unparented hq-f127d1 beneath it.
  Both ideas stay `briefed`; no duplicate goal is needed.
- hq-c4c026: design task-origin lookup from this brief (P2, m, high,
  planned), a child of hq-cff824. hq-c8aef1 waits on it; its obs-02e88b and
  obs-d98663 edges remain satisfied. Reuse the indexed trace work as related
  context rather than a redundant prerequisite.
- hq-3d5da7: design cited transcript export from this brief (P2, m, high,
  planned), also a child of hq-cff824. hq-f127d1 waits on it.
- Each design needs user review, then separate plan review before implementation.
  On completion, each follow-up updates this brief and runs `tasks note <idea>
  --no-reviewed "<finding and accepted revisions>"` on its waiting idea before
  its result branch merges. Original sources, original bodies and prior evidence
  remain intact.
