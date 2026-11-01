# Supplemental review of harness onboarding

Reviewer: codex/gpt-6.1-sol, verified with `relay model --harness codex --pretty` in the reviewing turn.
Verdict: revise the runbook before relying on it for onboarding. This is a review, not execution of hq-94632d. That task remains todo.

## Basis and limits

Reviewed hq `0dc4f3190fef7d79f3a742ce91c2edfff93b1941`, `docs/runbooks/adding-a-harness.md` (unchanged since ee76bbc), SHA-256 `03e96603f6b5c4226f7f345145d08b0f4ca0eb53ab8218aceebfd7e8efc0d70d`.
Read hq-94632d, its complete attachment `adding-a-harness-review-report.md` (SHA-256 `84fb23ae44a4ea1866bf1ae1179209de14b707e0168552b3be4859bb22d09b6a`), hq-90a198 and all its notes, hq's authority document `docs/specs/2026-10-06-residue-design.md`, and hq-b24c39.

Consumer checkout bases inspected:

- lore: `e9f5c15087375b9175964c45c25f5eea3947980a`
- ops: `bd9dfe607792995db1b19a4ab444c7b55e33757b`
- relay: `50366c82bcd6702dbb35d054fdb7b5f34f6c2c02`
- tasks: `d9d5e37040b56c13dc7866b513bb53ac0fc94320`
- obs: `b557f2671bbb1249492f6d6ca8a878a7cd2e4a7e`
- fam code: `eef1ee3508fc2f99e631c23bc43a9650b9b9de21`

This is a targeted source review, not an exhaustive re-audit of all roughly 110 claims in the first report. No suites, live harnesses, upstream network checks or deployments were run. The current attachment contains a review, not raw probe transcripts. Existing test-pass notes prove those checks passed as recorded; they do not prove every operational claim in a runbook. The atomic-write defect below is recorded evidence from hq-b24c39, not a live reproduction in this review.

## Assessment of the attached review

Its overall diagnosis and discovery-first recommendation are sound. Direct checks support the important distinctions: lore's Superpowers path is a submodule; ops distinguishes broadcast tt from adopted CLI contracts; relay/obs conformance tests read cli.toml; agy/hook is an existing adapter; facts have one probe field per fact and wake-judge has a JUDGES dispatch; relay parsing/normalization are shared; tasks' ancestry fixture is a pinned copy with refresh instructions; tt-report enumerates known agent keys; claude-provenance requires Claude-specific context. The live-surface approval correction agrees with the session's global instructions.

Preserve the original report and record dispositions for its I1-I10 and M1-M13 rather than silently replacing the evidence. The six supplemental findings below are the counts in this task's impl round 1 note; they do not recalculate or subsume the original report's counts.

## Important

### 1. Guard delivery must include shell-tool mapping, not only the harness slug

What this is: adding a subscriber can appear to install the command safety guard while its tool filter excludes the new harness's shell calls.

Problem: hq `relay/subscribers.template.json:9` restricts ops-guard to `tools: ["Bash"]`; relay `src/subscribers.js:93` matches tool names literally. Relay `src/adapters/index.js:35` extracts command text only from `Bash` plus `tool_input.command`. Ops `hooks/relay-guard:28,67` knows only Bash as a command-bearing tool and allows null commands for other tool names. Thus a native tool called `run_command` or `shell` can miss the subscriber entirely, or be treated as a non-command if a partial integration merely broadens the filter.

Fix: document the entire native hook -> tool name and command extraction -> subscriber filter -> policy -> native denial path. Reuse the agy/hook translation at lines 161-183 as an example of mapping run_command/CommandLine to Bash/command. An alternate contract needs coordinated reader changes. Require isolated evidence for a harmless permitted command, a policy-refused fixture command, and malformed command input; verify the native tool never executes the refused fixture. This is additional to the original I3/I6.

If skipped: an onboarded shell can run outside the intended command guard despite having relay hooks and a subscriber entry.

### 2. Check that settings symlinks survive actual harness saves

What this is: the live-state pipeline only works while the harness continues writing the tracked target.

Problem: runbook lines 132-135 expressly assume writes through the home symlink. Its post-apply check at lines 614-619 asks for clean Git state and a saved record, but never reruns link-check after a settings save. A disconnected tracked file can remain clean, and a pre-existing pick record can look valid. hq-b24c39 records agy atomically replacing its settings symlink with a regular file; the currently inspected refresh script operates on tracked checkout files and contains no home-file reconciliation.

Fix: before choosing the delivery contract, probe whether settings writes follow the symlink or replace it. After a fresh model/effort/trust change and restart, check the link target, `just link-check`, and that the saved record contains the new value. Describe replacement-writing harnesses as needing an explicit supported synchronization contract. Name hq-b24c39 as the existing agy defect; do not implement that remedy inside this documentation task or present agy as a proven complete hygiene example.

If skipped: settings and trust can silently diverge from tracked configuration while Git remains clean.

### 3. Familiar needs its own compatibility check before observer enablement

What this is: the original report correctly adds familiar to consumer discovery, but widening hq's subscriber harness lists is insufficient.

Problem: fam `src/render/harness.js:1-4` throws on a harness outside claude-code/codex/opencode, and `src/observe/emission.js:38` calls that function. Further closed sets appear in `src/bus/sessions.js:12` and `src/attention/model.js:70,280`. Existing familiar subscribers therefore cannot automatically consume any new relay harness merely because the template admits it.

Fix: include fam in discovery and the dependency matrix when familiar observation is selected. Update and test its event/session validation and terminal behavior before enabling the observer, or leave that harness explicitly excluded and record the omitted layer. Home/instruction-only onboarding does not need familiar support.

If skipped: optional observation can reject events or throw during rendering after a seemingly successful relay rollout.

## Minor

### 4. Replace the apparent depth ladder with explicit layer acceptance

What this is: the introductory examples and final table combine supported capabilities, desired integrations and optional consumers.

Problem: a reader can treat the example harness at a named depth as evidence that the whole bundle works. hq-b24c39 already contradicts that inference for agy's hygiene. The existing post-apply check covers only picks, not the other selected layers.

Fix: start each onboarding with a small selected-layer checklist: required, optional/deferred, unsupported, and the evidence that passes each selected layer. Include profile/home resolution, instructions/skills loading, native denial and Stop behavior, concurrent-session identity, provenance joins, session resume, and capture-only archive checks where selected. Keep capture and pruning independently gated; no blanket requirement to implement every layer. Mark example rows as current examples with known limits, not support certifications.

If skipped: completion remains ambiguous and intended future integration can be mistaken for established capability.

### 5. Give discovery and rollout a short ownership/dependency map

What this is: the original review's discovery-first proposal is useful, but search hits alone do not say where edits belong or when changes activate.

Problem: flat search results cannot distinguish a source contract from its vendored copy, a submodule, a fixed fixture, or a live hook image. The current rollout text has no general recovery checkpoint, although relay-runtime.md already documents runtime/state preservation and rollback.

Fix: put discovery first using existing canonical slugs, short aliases and relevant harness environment markers. Classify hits as source, distributed copy, test/fixture, live consumer or documentation; retain a compact source -> consumer -> distribution -> activation map. Link existing relay-runtime.md recovery instructions instead of copying them, and require preservation of current settings/trust/live picks and existing runtime versions before an approved activation. Do not prescribe a destructive reset or downgrade of durable state. Keep per-host prerequisites separate from one representative end-to-end check for each distinct configuration path.

If skipped: subsequent edits will reproduce adoption, fixture and rollout-order errors even if the present inventory is expanded.

### 6. Tighten evidence language in the original report

What this is: the report's parser description can be read as requiring hook_event_name on every payload.

Problem: relay `src/adapters/payload.js:16` checks hook_event_name only if present, comparing it with the native event's base name. It is optional. The original report also names ops and lore as main rather than pinning their exact revisions, which limits historical reproducibility.

Fix: say explicitly that hook_event_name is optional and must agree when supplied. Preserve the original report unedited; use the frozen bases above for this supplemental review and record exact revisions/hashes for later review evidence. Do not claim raw runtime evidence exists where only a review or outcome note is attached.

If skipped: a documentation correction can introduce a new schema requirement, and a later reader cannot reconstruct all historical claims precisely.

## Proposed scope and acceptance for hq-94632d

Keep it a documentation correction. The original user-origin task hq-90a198 asks for an end-to-end runbook with incremental integrations; it does not authorize implementing every missing harness capability. No new registry framework or manifest refactor is needed here.

Acceptance:

1. Dispose of the original I1-I10 and M1-M13 and these six supplemental items, naming evidence and any deliberate exclusions.
2. Make discovery the first step; retain the ownership/distribution, coupled-reader, guard and rollout-order information that search cannot supply.
3. Add the shell-guard contract, settings-write/link-survival check, conditional fam coverage, selected-layer acceptance and recovery links.
4. Check every procedural command/path changed by the correction against its owning checkout. Use exact review revisions. Follow each invoking checkout's current test policy for verification; a suite pass is not a substitute for source validation or a selected-layer smoke result.
5. Keep runtime remedies such as hq-b24c39 separate, and retain explicit approval for live global activation. A docs-only merge does not grant that approval.

No implementation was started or claim acquired for this review. No worktree, scratch directory, off-tree evidence, service or live surface was created or changed. The only intended writes are this immutable attachment and task review notes. Existing codex/config.toml live changes and other sessions' work remain untouched. No pushes or feature branches are involved.
