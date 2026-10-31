# Headless and isolated harness runs

Scoping handoff, 2026-10-15. Goal: hq-40a8d0. Ideas: hq-7a69dc, hq-7c80a5, hq-305ede;
hq-dd66c1 reviewed in the same pass (drop proposed, covered by crew-9b4b47).

Updated 2026-10-30: worker-boundary reports hq-f678e7, hq-0806e7 and
hq-dc6f2e join this existing effort. Cross-session messaging hq-e15558 is
related context only and was left for its separate coordination effort.

## Problem

Workers and probes now run harnesses without a person at the terminal: crew starts pi
per attempt, probes and experiments start Claude Code in scratch homes, controllers
hand work to subagents. Each run needs, before launch, the home it starts from, the
facts that say how the harness behaves there, and what to check when a child ends
abnormally. Today each caller rediscovers these and some learn them by failure.
The new cases require preserving completed work after an error and proving a
fresh analyst cannot read private inputs through any of its tools.

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
- **Completed work behind an error.** hq-f678e7 has two matched filing events
  in Codex 0.165.0 session `01a18943-2b9d-7e50-926f-b74169571349`:
  calls/results at lines 2988/2992 and 6123/6126. The first controller inspection
  found the correction, checks, report and released claim already persisted;
  the second found completed operation/report evidence but an unreleased claim.
  An error alone establishes neither no effects nor a completed handoff.
- **Cleanup refusal.** hq-dc6f2e's worker session
  `01a18ab4-a56f-7341-8244-8b69059d7b4a` (Codex 0.165.0), lines 256/259,
  records a pre-execution rejection of the temporary-file wrapper's `rm -f`
  cleanup. The memory-capture call at 263 and result at 274 completed the sole
  authorized invocation: expected stdout, empty stderr, exit 0. Filing 295/299
  matches the record. Keep the case; no permission weakening is justified.
- **Analyst isolation.** hq-0806e7's Codex 0.166.0 session
  `01a18e07-0ba0-7632-8a9b-faf99870ecb8`, human line 15, explicitly asks for
  enforced key/source/world denial and says unrestricted children do not provide
  it; filing 192/195 matches. This is a user requirement, not just an agent's
  preferred safeguard. Autonomy at `e6b726a3a92dda597a0cf84b32c1f037673d7589`
  has `python/src/autonomy/sandbox/{spec,static,bwrap}.py`: isolated binds,
  overlap rejection and a denied-path `stat` probe. autonomy-c5c566 proved pi
  RPC through sandboxed stdio, but its old shared-network, actor-readable
  credential recipe is not today's approved recipe. autonomy-e4c0b5 subsequently
  landed model-only egress (`d00d744`, documented `2ef0c0e`). Applicability to
  this analyst and every tool remains unproven; no live analyst was launched.

## Constraints

hq owns homes, capability facts and their probes; crew owns attempts and their agent
directory; lore owns worker instructions (lore-ba22f3, lore-f800a1) and the subagent
skills; relay owns identity and events. Facts are read only through
`tools/harness-facts`; `unknown` is an answer. A pi version change is a new epoch
(README "Re-probing pi"). crew-ba0a02 already records process-exit and cleanup
evidence for one cross-harness review; hq-3be737's brief covers the inverse Codex case
(a process ended that should have lived). Related isolated-run feedback already
scoped: hq-96435f, hq-da1015.

The original cases above remain historical evidence. Fresh context and enforced
access are separate checks: the [official multi-agent documentation](https://developers.openai.com/api/docs/guides/agents-api/multi-agent)
says agents sharing an environment share its filesystem; that API statement does
not qualify the installed CLI's isolation. hq records the supported launch and
capability evidence; autonomy owns confinement and authority. No shared launcher,
permission setting, world state or live source may be changed by this scope pass.

Upstream screen, 2026-10-30: open/closed issue and PR searches for `capacity
subagent` and `"rm -f" permitted` returned no matches. Existing
[Codex #54884](https://github.com/openai/codex/issues/54884) remains open: failed
API turns omit end hooks; it is related, not proof of the same failure.
Default branch was `67f0994b532b8740f14b5b738af7b7b2a915b1d6`; its
CHANGELOG points to releases and notes command-lifecycle fix #44557. The
0.166.0 release notes establish no fix for these two observations. Commit
search `capacity subagent` returned none. `develop` and `development` lookups
returned 404; a full feature-branch scan was stopped. This is a limited screen,
not a claim no upstream fix exists. Recheck the exact failure before proposing
an upstream report, pin or workaround; publication remains separately authorized.

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

Restricted analyst (hq-0806e7):
1. **Qualify the existing autonomy/pi launch and denial route first — lean.**
2. Use an independently confined Codex executor if its current contract proves
   every analyst tool is inside the boundary.
3. Keep the live analyst blocked when neither route can prove the required denial.
   Fresh context or a confined numerical subprocess alone is insufficient.

For hq-f678e7, reuse hq-624fb9's recovery investigation and add persisted-effect
and claim reconciliation to its question. Do not add a competing investigation
or assume the upstream event fix alone would preserve the completed outcome.
For hq-dc6f2e, retain the successful bounded memory-capture route and shelve
permission-policy work until it cannot meet a concrete authorized capture need.

## Unanswered questions

- What exit codes, default session directory, extension surface and context-file
  report does pi 1.1.0 give, and does any make a template necessary? hq-f1aff0.
- Which harness and child mechanism left the process running, and who started it?
  hq-624fb9.
- Should the isolated-home onboarding behaviour become a typed fact with a probe? Not
  until a second observation; hq-305ede records it as guidance.
- Which persisted results and claim/process checks must a controller reconcile
  after an error, and what remains an upstream reporting gap? hq-624fb9, now
  including both hq-f678e7 cases without losing the original process-survival case.
- Which existing launch confines the fresh analyst and all its tools, with an
  allowed-read control and denied-read checks for key, source and world?
  hq-a99924; domain execution stays blocked.

## Proposed decomposition

| Task | Next action | Ideas it wakes |
| --- | --- | --- |
| hq-f1aff0 | Probe the four pi facts and recommend template contents | hq-7a69dc (and a note on lore-ba22f3) |
| hq-624fb9 | Trace original and new capacity cases; reconcile effects, handoff, claims and processes | hq-7c80a5, hq-f678e7 |
| hq-305ede | Scoped: README guidance for isolated Claude Code homes | — |
| hq-a99924 | Qualify an existing confined analyst launch and prepare synthetic allowed/denied-read checks | hq-0806e7 |

hq-dc6f2e is shelved. Wake it when an authorized bounded diagnostic needs
file-backed capture that memory capture cannot satisfy, or refusal recurs with
no safe supported capture route. The other three original children and their
prior dispositions are unchanged; neither new idea is executable implementation.
