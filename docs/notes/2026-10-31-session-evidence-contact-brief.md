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

### Independent-owner contact study, 2026-11-08 (hq-08cb52)

Inspected at hq `73c7c383`, relay `88e54f01`, and band (formerly crew) `f0a9f409`.
Existing relay interaction suites (`node --test test/*interaction* test/*inbox*`:
155 passed, 0 failed in 26.7 s) and a synthetic no-model `openInbox` check confirm
that **no supported route currently delivers a coordination request into an already
running, independently owned task session without human relay**:

1. **Targeting and liveness discovery (supported):** Task lifecycle notes record
   `provenance.harness_session` (`<harness>:<sessionId>`), and `relay list --json` /
   `$STATE/agents.json` (`docs/registry.md`) indexes live rows by `agentId`
   (`<harness>:<sessionId>`) with `state` (`idle`, `working`, `needs-input`,
   `needs-approval`, `done`, `error`),
   `cwd`, `projectKey` and `process` (`Handle`). A controller can resolve and verify
   an active independent owner's `agentId`.
2. **Envelope validation versus inbox admission (blocked at admission):**
   - `validateMessage` (`src/interaction/message.js:43-49`,
     `schemas/interaction/message.schema.json`) accepts
     `Party = { kind: 'agent', agentId: '<claude-code|codex|opencode>:...' }` in both
     `from` and `to` (`agy:` is not yet in `HARNESSES` at `src/interaction/message.js:12`).
   - **Detached `ask`** (`relay inbox ask --file PATH` or socket `op: "ask"` with
     `native: null`): `src/serve/inbox.js:86-87` and
     `src/interaction/lifecycle.js:226-229` require
     `message.from.kind === 'agent' && message.to.kind === 'user'`. Passing
     `to: { kind: 'agent', agentId: 'codex:owner-thread' }` to `inbox.ask` in an
     isolated temporary state directory fails immediately with
     `INVALID_MESSAGE: detached ask requires an agent sender, user recipient, null waiter, false handback, and createdAt no more than one second ahead`.
   - **Native `ask`** (`native !== null`): `src/serve/inbox.js:111` rejects external
     socket `ask` for `codex` with `UNSUPPORTED_ROUTE` (`Codex ownership is internal`);
     `src/routes/codex.js:16` and `src/routes/claude-code.js:24` hardcode
     `to: { kind: 'user' }` for the calling agent's own blocked `AskUserQuestion` or
     `item/tool/requestUserInput` call; and `src/serve/inbox.js:95` returns
     `{ passthrough: true }` without persisting an entry whenever
     `presence.mode === 'here'`.
   - **`notify` (`kind: "notice"`):** `inbox.notify` (`src/serve/inbox.js:149-154`)
     stores a `NoticeEntry` with an agent `to` party and pushes `{ type: 'entry', entry }`
     to socket `watch` listeners, but `src/cli/desk.js` exposes no `notify` CLI
     subcommand, `inbox.answer` (`src/serve/inbox.js:126`) refuses notices with
     `NOT_A_QUESTION`, and no harness hook, plugin or connector subscribes to `watch`
     or reads `NoticeEntry` rows.
3. **Delivery and acknowledgment into an active session (unsupported):**
   - Native collaboration tools (Codex `send_input`, Claude Code `SendMessage`/`Task`,
     Antigravity `send_message`/`invoke_subagent`) only address descendants within the
     caller's own session tree.
   - `relay ask --harness claude-code` (`src/routes/ask.js`) and the Codex `0.166.0`
     `app-server` connector (`src/serve/codex/connector.js`,
     `src/serve/codex/delivery.js`) only deliver an `AnswerBody` back to an agent
     already blocked inside its own outbound user question (`AskUserQuestion` or
     `item/tool/requestUserInput` in plan mode while `presence === 'away'`).
   - `relay hook` (`src/dispatch.js`) runs static `subscribersPath` (`$XDG_CONFIG_HOME/relay/subscribers.json`, `src/bus/paths.js:16`) guards and
     observers on the target session's own lifecycle/tool events, never querying
     `$STATE/inbox/` for inbound messages addressed to that session's `agentId`.
   - CLI resume (`claude -p --resume <uuid>`, `codex exec resume <threadId>`) cannot
     message a live owner: Claude `--resume` forks a new session UUID copying prior
     records (`agents/skills/session-logs/SKILL.md`), and `codex exec resume` is
     refused by `thread-writer-locks/<tid>.lock` while a turn is active or runs a
     separate headless process outside the live TUI when idle.
4. **Waking an idle controller (`tools/harness-facts list` at hq `73c7c383`):**
   - `controller-wake` is `true` for `claude-code` (`2.1.295`, hq-b2515c,
     `controller-wake-kinds = ["shell", "subagent"]`) and `agy` (`1.4.12`, hq-e72097,
     `["shell", "subagent"]`), `false` for `codex` (`0.156.1`, tack-00ccb6), and
     `unknown` for `opencode`, `pi` and `pi-durable`.
   - Even on `claude-code` and `agy`, a wake occurs only when a background shell
     command or subagent **started by that controller** exits (or a `schedule` timer
     fires in `agy`); no external socket or hook push wakes an idle session that has
     no pending child or timer.
5. **Relation to `band-9b4b47` / `band-ba0a02` and `hq-ba1758`:**
   - `band-ba0a02` (completed 2026-11-08 at band `f0a9f409`) verified spawning a new
     headless `claude -p --bare` review session (`--session-id`, stream/result usage,
     `SIGTERM` cancel) and woke `band-9b4b47`, which filed `band-938597` to design
     `band`'s local runtime seam and §4 owner handoffs. Spawning a new worker session
     does not contact an already active independent task owner.
   - `hq-ba1758` studies recurring payload/handoff failures across user-mediated
     Claude-Codex exchanges; its message-field findings remain complementary.
6. **Smallest owner-specific recommendation:**
   - Do not build a parallel bridge, reader, envelope schema or delegation system in
     hq. Under the accepted 2026-10-25 orchestration-boundaries contract, `relay`
     owns interaction envelopes, `$STATE/serve.sock` and hook delivery, while `hq`
     owns harness hook wiring and capability facts.
   - To support direct coordination with an active independent owner (`hq-e15558`),
     scope an owner-reviewed `relay` contract extension covering:
     (a) **Agent-targeted detached questions** in `src/serve/inbox.js` and
     `src/interaction/lifecycle.js` (`from: { kind: 'agent', ... }`,
     `to: { kind: 'agent', agentId }` with `'agy'` added to `HARNESSES`), plus
     recipient filtering (`--to <agentId>`) and agent-responder attribution on
     `relay inbox list` / `answer` / `take`;
     (b) **Hook-boundary delivery for active owners** via a `relay` observer or
     `PostToolUse` / `Stop` subscriber that injects pending questions addressed to
     the current session's `agentId` as `additionalContext` (or blocks `Stop` until
     answered/deferred), allowing the owner to reply with `relay inbox answer` while
      the sender polls or awaits `relay inbox take`; and
     (c) **Explicit idle-wake boundary**: an idle `claude-code` or `agy` owner can be
     woken only if it intentionally leaves a background shell waiter running (using
     their proven `shell` `controller-wake-kinds`), whereas waking an idle `codex`
     owner is unsupported (`controller-wake = false`) without a future `app-server`
     turn-injection contract.

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
- **Contact-study owner (answered by hq-08cb52):** addressing and liveness discovery
  work today via task provenance plus `relay list` (`$STATE/agents.json`), and
  `validateMessage` accepts agent-valued `to` parties (`claude-code|codex|opencode`),
  but `relay serve` rejects agent-targeted detached questions at admission
  (`INVALID_MESSAGE`), native question routes (`claude-code` `AskUserQuestion` and
  `codex` `0.166.0` `requestUserInput`) only answer an agent's own outbound user
  question, `relay hook` never reads `$STATE/inbox/` for inbound agent messages,
  and idle controllers cannot be woken from outside without an already running
  child (`claude-code`, `agy`) or at all on `codex` (`controller-wake = false`).
  The smallest missing contract is an owner-reviewed `relay` extension for
  agent-targeted detached questions (`to: { kind: 'agent', agentId }`), `--to`
  filtering/agent answer attribution, and `relay` hook `additionalContext` delivery
  at tool/turn boundaries.
  Handed to relay as relay-f11acb (2026-11-08).
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
- hq-08cb52 is **done** (2026-11-08) and woke hq-e15558: no current route delivers
  into an already active independent owner; recommends an owner-reviewed `relay`
  contract extension for agent-targeted detached questions and hook-boundary
  delivery rather than a parallel bridge or reader in hq.
  hq-ba1758's three historical exchanges concern recurring payload failures;
  reuse its context without expanding or duplicating that study.
- relay-f11acb (idea, filed 2026-11-08 by the scope pass on hq-e15558) carries the
  study's proposed extension (agent-targeted detached questions, `--to` filtering and
  agent answer attribution, hook-boundary delivery, an explicit idle-wake boundary)
  to relay's owner for review. hq-e15558 stays `briefed` and depends on it. The user's
  recorded ask (L593) chose direct agent-to-agent support over person-mediated
  contact, so the remaining choice is relay's contract shape, not whether to build it.
  Once relay ships a subscriber, hq wires it into the harness hooks.
- On completion each follow-up updates this brief and runs
  `tasks note <waiting-idea> --no-reviewed "<finding and evidence>"` before
  its result branch merges. Neither report is fulfilled merely by filing work.
