# Headless and isolated harness runs

Scoping handoff, 2026-10-15. Goal: hq-40a8d0. Ideas: hq-7a69dc, hq-7c80a5, hq-305ede;
hq-dd66c1 reviewed in the same pass (drop proposed, covered by crew-9b4b47).

## Problem

Workers and probes now run harnesses without a person at the terminal: crew starts pi
per attempt, probes and experiments start Claude Code in scratch homes, controllers
hand work to subagents. Each run needs, before launch, the home it starts from, the
facts that say how the harness behaves there, and what to check when a child ends
abnormally. Today each caller rediscovers these and some learn them by failure.

## Current behaviour and evidence

- **pi agent directories.** crew's core design (crew `docs/specs/2026-10-13-crew-core-design.md`
  §6.2, §9) gives each attempt its own `PI_CODING_AGENT_DIR` and says hq owns the
  template it copies. The implemented `prepareAgentDir` (crew `src/agent-dir.ts`, crew
  `90f1c66`) needs no template: it writes `AGENTS.md` and returns the credential env,
  and `src/runtime/pi-rpc.ts` passes `--session-dir`, `--no-extensions`, `--no-skills`
  and `--no-prompt-templates`. pi 1.1.0's agent directory also reads `settings.json`,
  `models.json`, `auth.json`, `mcp.json`, `SYSTEM.md` and `APPEND_SYSTEM.md` (installed
  `docs/configuration.md`). A project's `.pi/settings.json` `sessionDir` is read before
  trust is resolved (`docs/security.md`).
- **pi facts.** `facts/capabilities.toml` records pi's MCP, headless controls,
  idempotent submission, child conversations, turn resumption and usage (hq-57132d). It
  has no entry for exit codes, the default session directory, the extension API, or
  context-file reporting, which crew §9 lists as unknown. lore-ba22f3's scope note
  expects hq's probe to settle context-file reporting. crew's `contextLookup` skips
  `AGENTS.md` when `AGENTS.override.md` exists but keeps `CLAUDE.md`; pi's docs say the
  override replaces both in the same directory.
- **Isolated Claude Code homes.** With `CLAUDE_CONFIG_DIR` set, Claude Code reads and
  writes `.claude.json` inside that directory (trans runbook `docs/runbooks/phone-inbox.md`
  on 2.1.296; hq's `docs/notes/2026-10-15-session-discovery-contract.md`). A preference
  seed at the sibling path is ignored, and cleanup of the sibling leaves the generated
  file and its backups behind. In one interactive run on 2.1.296 a fresh home showed
  theme, terms, directory trust and the permission-mode notice, and the command-line
  prompt never reached a conversation; typing it afterwards worked. trans records
  this as specific to that run. hq's own probes (hq-b2515c, hq-7b65dc) used isolated
  homes without recording an onboarding contract.
- **A child's abnormal end.** hq-7c80a5 (from prism, a Codex session, 2026-10-14): a
  subagent's model-capacity failure arrived after its check finished and before its
  cleanup and report; the controller reaped a named test process and reconciled the
  preserved work before reassigning it. The session was not read in this pass, so the
  harness's child mechanism and the process's owner are unknown.

## Constraints

hq owns homes, capability facts and their probes; crew owns attempts and their agent
directory; lore owns worker instructions (lore-ba22f3, lore-f800a1) and the subagent
skills; relay owns identity and events. Facts are read only through
`tools/harness-facts`; `unknown` is an answer. A pi version change is a new epoch
(README "Re-probing pi"). crew-ba0a02 already records process-exit and cleanup
evidence for one cross-harness review; hq-3be737's brief covers the inverse Codex case
(a process ended that should have lived). Related isolated-run feedback already
scoped: hq-96435f, hq-da1015.

## Alternatives

pi template (hq-7a69dc):
1. **No hq template until a needed setting is shown — lean.** crew's flags and
   `prepareAgentDir` cover the first slice; record the facts first.
2. A checked-in template under `pi/` (settings, models) that crew copies.
3. An hq command that materializes a headless agent directory for a given pi pin.

A child's abnormal end (hq-7c80a5):
1. **Trace the one case first — lean**, then choose.
2. A controller recovery step in lore's subagent skills: after a child fails, list the
   processes and worktree state it left before reassigning.
3. An hq fact per harness, with a probe: does the harness stop a failed child's
   processes?

## Unanswered questions

- What exit codes, default session directory, extension surface and context-file
  report does pi 1.1.0 give, and does any make a template necessary? hq-f1aff0.
- Which harness and child mechanism left the process running, and who started it?
  hq-624fb9.
- Should the isolated-home onboarding behaviour become a typed fact with a probe? Not
  until a second observation; hq-305ede records it as guidance.

## Proposed decomposition

| Task | Next action | Ideas it wakes |
| --- | --- | --- |
| hq-f1aff0 | Probe the four pi facts and recommend template contents | hq-7a69dc (and a note on lore-ba22f3) |
| hq-624fb9 | Trace the prism session read-only and recommend skill step, fact, or nothing | hq-7c80a5 |
| hq-305ede | Scoped: README guidance for isolated Claude Code homes | — |
