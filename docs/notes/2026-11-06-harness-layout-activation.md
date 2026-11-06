# Harness layout activation request

Task: hq-b77d0c; operational child: hq-fd490e. Status: ready for separate live activation approval.

## Decision

Approve the frozen runtime below for activation from main during a no-settings-writer
window covering **Titan and Europa** (proposed shared hosts, not yet confirmed).
This authorizes the local fast-forward, the named config restore and patch carry,
record-key changes, home-link reconciliation, the individual ignored-file dispositions,
and the conditional recovery in the tested runbook. It does not authorize stopping
unrelated processes, paid probes, a push, or any change outside these named surfaces.

All affected harnesses must stop saving settings throughout the transition. Other
hosts must remain quiescent until adopted or explicitly kept quiescent by agreement.
If the active controller cannot avoid settings writes, the acting operator must run
this from an ordinary shell after the controller exits. Do not infer quiescence
from a quiet process listing. Confirm the full shared-host list before starting.

## Frozen inputs

Repository: hq.

- Main base `BEFORE`: `71a4934294f055d42c1cf9dae8290937656fc934`.
- Accepted runtime `REVIEWED`: `062f7131a59dc81fb22148b05a11741e5642853a`.
- Runbook: `docs/runbooks/harness-layout.md` at `REVIEWED`.
- Spec: `docs/specs/2026-11-05-harness-layout-design.md` at `d1399577ffe0fd65feaaa4393332e4f8b3f26498`.
- Plan: `docs/plans/2026-11-05-harness-layout.md` at `432432185328918540402a4f7ebc00820b7642de`.
- Build worktree: `.worktrees/hq-b77d0c`, branch `refactor/hq-b77d0c-harness-layout`.

If main advances, stop and reconcile before using this request. Later record-only
commits on the build branch are allowed; the runbook checks frozen helper/runbook
equality, and only the frozen runtime advances main. After successful activation,
the controller may integrate record-only descendants, checking that they change no
runtime files. No amended runtime is implicitly approved.

## Verification and limits

Focused baseline: 1099 existing cases and 17 protected-path cases passed. Changed
behavior: all 637 affected non-relay cases are covered by passing original and
corrective runs; 462 relay cases passed serially. Final completion at REVIEWED:
45 layout/protected cases passed, 115 unrelated cases deselected. Mandatory hygiene,
facts/manifest checks and staged whitespace validation passed. Automatic broad
runs were deliberately omitted under validated policy-off; no remote evidence or
live model probe is claimed. Independent final review: accept by `codex/gpt-6-astra`, no Critical or Important findings.
Two documentation minors remain deferred: README private-path wording and the
adding-a-harness templates. They do not change runtime links; the full report and
dispositions are in the execution workspace (`final-r1-report.md`, `progress.md`).

The rehearsal uses real old/new capture/restore hooks, Git clean filters and link
reconciliation in isolated fixtures. It covers unfiltered JSON/TOML edits beside
picks/trust, detached settings with a newer synced base, foreign-anchor refusal,
malformed/colliding/partial records, writer detection, ignored-file preservation
and pre/post-merge rollback. Both Codex hook blobs remain byte-identical.

The execution ledger and detailed test evidence remain owned by hq-b77d0c at
`$WORK_ROOT/hq/hq-b77d0c/plans/harness-layout/`. The ledger records the spec-review
rulings and the bounded implementation decisions: git apply uses the configured
clean filter; patch comparison ignores only index-hash headers, preserving hunks.

## Exact initiating-host scope

Only `agy/settings.json` has an unfiltered main diff: `agentMode: auto`. Preserve
it as an unstaged change at `harnesses/agy/settings.json`; do not commit it, add it
to clean_keys, or overwrite it with the tracked default. The approved dirty-path
restore in runbook step 2 is exactly:

```sh
git restore --source="$BEFORE" --worktree -- agy/settings.json
```

The six files marked carry below move to the same path prefixed by `harnesses/`.
The two cache files are snapshotted, verified regenerable, then individually removed.
Use hash/absence checks and empty-directory `rmdir`; no recursive root deletion.
Refresh observations at the agreed window and stop on an unaccounted file or changed
unfiltered delta. Raw live config hashes are observations, not permission to discard
subsequent picker changes; capture those through the existing tools before mutation.

| Path | Disposition | Observed SHA256 |
| --- | --- | --- |
| `agy/settings.json` | preserve unstaged | `edef24cfdd814b8a3097ee6d7e559ebe0fb8a4b592c27363a9d3520e3ae12edc` |
| `claude/mods/cli-pane/.claude-plugin/types/.gitignore` | carry | `cdbcae15105d6b781e620813c79c7e868740d4e9cc53ce6f5fcbbc12387adf4b` |
| `claude/mods/cli-pane/.claude-plugin/types/claude-code-mcp/index.d.ts` | carry | `d6080b6cf72842b1de66a4d57c7743077d3c6ef826871450e9adeacadc1a6594` |
| `claude/mods/cli-pane/.claude-plugin/types/claude-code-tools/index.d.ts` | carry | `988168f92c87f9dafed33fe83730abea1d79eed0eec72e26d342b64f2405e4ea` |
| `claude/mods/cli-pane/.claude-plugin/types/claude-code/index.d.ts` | carry | `042ff9743dc3fee570ff699e51ebc1071252c3eec6116294a72bf0568e5aed37` |
| `claude/mods/cli-pane/.claude-plugin/types/tsconfig.json` | carry | `75aed92a02defcb18af89f4d6f834c976945c28b7e09b0090776eb73c90953f2` |
| `claude/mods/cli-pane/tsconfig.json` | carry | `4087cf0ba92fde503ed0e7c56f37bcb26ad0c085873f10219d0336c0f19b5a8f` |
| `claude/probes/__pycache__/subagent-write-probe.cpython-314.pyc` | snapshot and discard cache | `f841962d70e38e9aa5f31c3917cf03c67dc492450d5bc27644ba7e910c8399dc` |
| `claude/probes/__pycache__/successor-link-probe.cpython-314.pyc` | snapshot and discard cache | `1bfc8ebda2722565465784d4b84460f6033512fd7585259768d73c9c9e2bbd6a` |

All 16 affected native links currently resolve to the old main targets. Native
home names stay unchanged. Private work configs are regular files and remain under
`local/`. A bounded scan of registered projects (excluding historical docs/tasks)
and the two private configs found no matching old hq subdirectory references.
The `hq`, `harness-state-refresh` and `relay` launchers resolve to main, and `just`
is the system executable. Recheck these at activation; these observations are not
a promise about external scripts outside the registry.

## Operator inputs and sequence

Use the tested runbook, from a Bash shell with `set -euo pipefail`. Set:

```sh
BEFORE=71a4934294f055d42c1cf9dae8290937656fc934
REVIEWED=062f7131a59dc81fb22148b05a11741e5642853a
SNAP="$WORK_ROOT/hq/hq-b77d0c/activation-initiating-2026-11-06"
```

`SNAP` must not already exist. hq-fd490e owns the private snapshots after creation;
record that creation immediately. Use a separate host-local `activation-adopting-2026-11-06`
snapshot directory on Europa. Names are frozen for the first attempt; an existing
snapshot is retained, never overwritten or silently reused.

1. Verify the accepted runtime, main base, no-writer agreement, launchers, dirty
   path and ignored-file inventories. Create SNAP with mode 700. Copy the three
   exact lists below into files named `carry-paths.txt`, `discard-paths.txt` and
   `runtime-paths.txt` inside SNAP.
2. Extract the runbook's four tested scripts, snapshot every named raw config,
   record, trust/private file, detached setting and ignored file, and save/check
   the immutable checkpoint as its Snapshot section specifies.
3. Run old-path codex-trust/live-picks sync; require agy's settings link restored.
   Save `unfiltered.patch`, verify it is the sole approved agy edit, then snapshot
   the post-capture generation separately and checkpoint it. Verify unchanged
   inputs before making intentional changes; never rebaseline a failed checkpoint.
4. Restore only the dirty agy path using the command above, verify clean index and
   config base, checkpoint the intentional changes, preview/apply the finite helper
   forward, then immediately `git merge --ff-only "$REVIEWED"` with normal hooks.
5. Check hook stderr and restored picks/trust. Apply the saved patch with
   `git apply --check --directory=harnesses` then `git apply --directory=harnesses`.
   Carry/remove only the listed ignored entries, reconcile `just link --apply`,
   and run explicit trust/pick sync plus every runbook verification.
6. Compare parsed picks, trust, private bytes and normalized unfiltered patch with
   snapshots without printing values. Require old roots absent and links converged.
   Keep each other host quiescent until its links are adopted. A detached agy file
   on a post-sync host follows the tested anchor-repair and three-way alignment
   procedure; a conflict retains both copies and stops for operator resolution.
7. Record host adoption and run exits. Release the window only after every affected
   host is adopted or explicitly remains quiescent. Keep snapshots and worktree
   under open task ownership until remaining adoption and cleanup are settled.

On a detected writer, stop; retain snapshots and request a fresh window. A failure
before HEAD advances permits only the runbook's reverse-rekey/reapply recovery.
After HEAD advances, use its corrective commit with the exact runtime list below,
retaining newer task/spec/plan/review history; do not reset the branch. Unexpected
conflicts or unreviewed runtime changes stop either recovery path.

## Frozen file lists

### carry-paths.txt

```text
claude/mods/cli-pane/.claude-plugin/types/.gitignore
claude/mods/cli-pane/.claude-plugin/types/claude-code-mcp/index.d.ts
claude/mods/cli-pane/.claude-plugin/types/claude-code-tools/index.d.ts
claude/mods/cli-pane/.claude-plugin/types/claude-code/index.d.ts
claude/mods/cli-pane/.claude-plugin/types/tsconfig.json
claude/mods/cli-pane/tsconfig.json
```

### discard-paths.txt

```text
claude/probes/__pycache__/subagent-write-probe.cpython-314.pyc
claude/probes/__pycache__/successor-link-probe.cpython-314.pyc
```

### runtime-paths.txt

Both sides of every rename are included; task/spec/plan/review history is excluded.

```text
.gitattributes
.githooks/codex-trust
.githooks/harness-state-clean
.githooks/harness-state-refresh
.githooks/harness_state.py
.githooks/live-picks
.githooks/test_codex_trust.py
.githooks/test_harness_manifest.py
.githooks/test_harness_state_clean.py
.githooks/test_harness_state_refresh.py
.githooks/test_live_picks.py
.githooks/test_pre_commit.py
.githooks/test_pre_commit_facts.py
.gitignore
.ops-check.toml
AGENTS.md
README.md
agy/hook
agy/hooks.json
agy/settings.json
agy/skills.json
claude/agents/.gitkeep
claude/archive/agents/architecture-analyst.md
claude/archive/agents/docker-diagnostics.md
claude/archive/agents/documentation-summarizer.md
claude/archive/agents/fallback-kid.md
claude/archive/agents/meta.md
claude/archive/agents/spec-specialist.md
claude/archive/commands/_code_audit.md
claude/archive/commands/_code_audit_tasks.md
claude/archive/commands/_spec_align.md
claude/archive/commands/code-suggest-reorg.md
claude/archive/commands/doc-clean.md
claude/archive/commands/doc-distill.md
claude/archive/commands/doc-find.md
claude/archive/commands/doc-next-steps.md
claude/archive/commands/doc-recent.md
claude/archive/commands/doc-update.md
claude/commands/.gitkeep
claude/mods/cli-pane/.claude-plugin/plugin.json
claude/mods/cli-pane/.gitignore
claude/mods/cli-pane/hooks/hooks.json
claude/mods/cli-pane/hooks/register.tsx
claude/mods/cli-pane/hooks/sgr.ts
claude/mods/cli-pane/tests/cli-pane.test.ts
claude/mods/cli-pane/types/index.d.ts
claude/plans/.gitkeep
claude/probes/subagent-write-probe.py
claude/probes/successor-link-probe.py
claude/probes/turn-pause-probe.py
claude/scripts/compact_stats.py
claude/settings.json
claude/statusline-command.sh
codex/archive/codex-ssh-agent.service
codex/config.toml
codex/hooks.json
codex/probes/turn-pause-probe.py
codex/ssh-guide.md
codex/work/hooks.json
docs/runbooks/adding-a-harness.md
docs/runbooks/harness-layout.md
docs/runbooks/relay-runtime.md
external/ponytail/config.json
facts/capabilities.toml
harnesses.toml
harnesses/agy/hook
harnesses/agy/hooks.json
harnesses/agy/settings.json
harnesses/agy/skills.json
harnesses/claude/agents/.gitkeep
harnesses/claude/archive/agents/architecture-analyst.md
harnesses/claude/archive/agents/docker-diagnostics.md
harnesses/claude/archive/agents/documentation-summarizer.md
harnesses/claude/archive/agents/fallback-kid.md
harnesses/claude/archive/agents/meta.md
harnesses/claude/archive/agents/spec-specialist.md
harnesses/claude/archive/commands/_code_audit.md
harnesses/claude/archive/commands/_code_audit_tasks.md
harnesses/claude/archive/commands/_spec_align.md
harnesses/claude/archive/commands/code-suggest-reorg.md
harnesses/claude/archive/commands/doc-clean.md
harnesses/claude/archive/commands/doc-distill.md
harnesses/claude/archive/commands/doc-find.md
harnesses/claude/archive/commands/doc-next-steps.md
harnesses/claude/archive/commands/doc-recent.md
harnesses/claude/archive/commands/doc-update.md
harnesses/claude/commands/.gitkeep
harnesses/claude/mods/cli-pane/.claude-plugin/plugin.json
harnesses/claude/mods/cli-pane/.gitignore
harnesses/claude/mods/cli-pane/hooks/hooks.json
harnesses/claude/mods/cli-pane/hooks/register.tsx
harnesses/claude/mods/cli-pane/hooks/sgr.ts
harnesses/claude/mods/cli-pane/tests/cli-pane.test.ts
harnesses/claude/mods/cli-pane/types/index.d.ts
harnesses/claude/plans/.gitkeep
harnesses/claude/probes/subagent-write-probe.py
harnesses/claude/probes/successor-link-probe.py
harnesses/claude/probes/turn-pause-probe.py
harnesses/claude/scripts/compact_stats.py
harnesses/claude/settings.json
harnesses/claude/statusline-command.sh
harnesses/codex/archive/codex-ssh-agent.service
harnesses/codex/config.toml
harnesses/codex/hooks.json
harnesses/codex/probes/turn-pause-probe.py
harnesses/codex/ssh-guide.md
harnesses/codex/work/hooks.json
harnesses/pi/bin/pi
harnesses/pi/extensions/harness-state.ts
harnesses/pi/package-lock.json
harnesses/pi/package.json
harnesses/pi/probes/durable-probe.mjs
harnesses/pi/probes/extension-probe.py
harnesses/pi/probes/mcp-probe-server.py
harnesses/pi/probes/rpc-probe.py
harnesses/pi/settings.json
justfile
links.toml
pi/bin/pi
pi/extensions/harness-state.ts
pi/package-lock.json
pi/package.json
pi/probes/durable-probe.mjs
pi/probes/extension-probe.py
pi/probes/mcp-probe-server.py
pi/probes/rpc-probe.py
pi/settings.json
ponytail/config.json
tools/harness-layout-picks
tools/relay_cutover_bootstrap/inputs.py
tools/test_agy_hooks.py
tools/test_capture_notice_wiring.py
tools/test_claim_guard_wiring.py
tools/test_harness_facts.py
tools/test_harness_layout.py
tools/test_harness_links.py
tools/test_pi_extension_probe.py
tools/test_pi_launcher.py
tools/test_pi_rpc_probe.py
tools/test_relay_cutover_transport.py
tools/test_relay_wiring.py
tools/test_subagent_write_probe.py
tools/test_successor_link_probe.py
tools/test_turn_pause_hook.py
tools/test_turn_pause_wiring.py
tools/test_worker_defaults.py
tools/turn_pause/hook.py
```
