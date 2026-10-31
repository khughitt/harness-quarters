# Archived dispatch evidence and contact with an active owner

## Problem

hq-d8a38c needs honest treatment of opaque archived tool arguments. hq-e15558
needs a supported way to coordinate with an already active task owner without
making the person carry messages. These are two session-tooling gaps, not a
request for another transcript reader or a general orchestration system.

## Current behaviour and evidence

- At hq `4cdeea3`, the installed session-logs skill describes textual arguments
  but gives no opaque-argument warning. At obs `ceddfe18`,
  `session_logs_records.py::_CodexFile.call` emits a function call's arguments as text;
  its explicit encrypted-content handling applies to other record shapes.
  An argument containing a `gAAAA` value is therefore not proof of a readable
  dispatch. The prefix is an observed warning sign, not a general cryptographic
  classifier or evidence that a supported decryption route exists.
- hq-d8a38c's filing is matched in Codex session
  `01a18c50-32b0-7103-beae-7c810e393c5c`: call L1265, created result L1268
  (`at: 2026-10-30T11:31:52Z`). Its check reported ten opaque prompt bodies
  while returned agent text remained readable. The subsequent correction at
  L1300/L1311 labels replacement text controller reconstruction and preserves
  the earlier evidence. The user's L15 asked to execute another task; this
  guidance gap was the agent's observation. Origin remains `agent`.
- hq-e15558's creation is matched in Codex session
  `01a18d3a-b9d1-76b1-9668-e1cdf3a7aa0d`: filing call L565, full created
  result delivered through the tracked poll at L581
  (`at: 2026-10-30T14:59:19Z`). The recurrence is inferred from the unique
  L621 feedback call and the matching 15:03:05 occurrence; its final feedback
  result was not recovered. L593's asynchronous answer contains a pasted
  owner's pin, followed outside that quotation by the user's own request to
  revisit relay support for inter-agent communication after the current work.
  The initial gap report was agent-authored; origin remains `mixed`.
- Relay `8ad31e0` exposes a registry and typed interaction inbox
  (`docs/api.md`, interaction messages and socket operations). An agent-valued
  envelope alone does not establish delivery into another live controller.
  Crew `250d776` documents Pi as its implemented runtime; crew-9b4b47 and
  crew-ba0a02 retain cross-harness delegation and its first review experiment.
  Their intended scope does not prove contact with an existing independent owner.

## Constraints

obs owns content parsing; hq owns homes, lifecycle and capability evidence.
Reuse obs-f5710b / obs-55431b for skill preparation. The approved reader spec
`docs/specs/2026-10-23-session-evidence-reader-design.md` section 11 still gates
skill/classifier changes on actual trial readout and date-specific assessment;
neither this brief nor the 2027-02-17 deferral authorizes activation. A new
opaque-value requirement needs the owner to reconcile its reviewed plan first.
Do not infer exact prompts from returns or decrypt private state speculatively.
Do not contact other agents, open desktop sessions, make model calls or change
host routing during the proposed research. Keep original report bodies and P2.

## Alternatives

1. **Recommended:** reuse the existing skill owner for evidence guidance and run
   one bounded capability study for contacting an existing owner. Preserve the
   distinction between readable archive text, opaque values and reconstruction.
2. Use committed artifacts and person-mediated contact when no route is proven.
   This is a documented limitation, not fulfillment of the user's contact request.
3. Build a new reader, bridge or worker launcher now. Reject: the reader already
   exists, delegation has owners, and existing-owner delivery is not yet qualified.

## Unanswered questions

- **Stage B skill owner:** which recorded fields are readable, which remain
  opaque, and is any supported recovery route established? State an explicit
  unavailable result otherwise. Include a synthetic mixed-argument example and
  distinguish labelled reconstruction from recovered verbatim text. Wake
  hq-d8a38c with delivered evidence before the result branch merges.
- **Contact-study owner:** can the current registry, relay adapters or native
  controls reach an already running independent owner? Separate addressing,
  delivery, acknowledgment and wake behavior. Identify supported configurations,
  authority requirements and the smallest missing contract if none works.
- The reader treats the actual asynchronous answer wrapper in L593 as injected,
  so a human-only query missed the user's request. obs-4c11a5 owns that newly
  reported classifier gap; it is related evidence, not a prerequisite for contact.

## Proposed decomposition

- hq-a4ed45 is the P2/xs/low/direct closeout goal for these two reports;
  no new lane.
- hq-d8a38c stays `briefed` and waits on existing obs-55431b, rather than
  creating a second skill-writing task. Its stamped handoff names
  `tasks doc hq-d8a38c brief`, which resolves this input across projects. Its
  owner reviews this requirement against the frozen Stage B plan and records
  any remaining recovery gap.
- hq-e15558 stays `briefed` and waits on hq-08cb52, P2/s/mid/direct:
  inspect the current owner-addressing and delivery surfaces, bound discovery
  to one session, and return evidence plus an owner-specific recommendation.
  hq-ba1758's three historical exchanges concern recurring payload failures;
  reuse its context without expanding or duplicating that study.
- On completion each follow-up updates this brief and runs
  `tasks note <waiting-idea> --no-reviewed "<finding and evidence>"` before
  its result branch merges. Neither report is fulfilled merely by filing work.
