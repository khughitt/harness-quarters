# ops-check adoption: the shared hygiene checks in hq's commit gate

Status: draft for review, revision 1, 2026-10-24.
Task: hq-c6a149 (found by the curate-docs pass hq-30fd95)
Inputs: ops `bin/ops-check` (version 14, its docstring is the contract), ops `README.md`
(Consumers and the front-door adoption steps), the retained-item records reference in
the lore skill corpus (its "Attachment layout refusal" section), and the obs adoption
obs-d95365 with its restoration task obs-875105.

## 1. Problem

hq vendors tools/ops-docs but not tools/ops-check, so the shared hygiene checks (guide
references, conflicted copies, agent scratch, machine layout, adopted copies) never run
here. The pre-commit hook is hq's only check gate: there is no CI, no pre-push suite and
no `just check`.

Running ops main's checker over a fresh worktree of main (9738ea0) on the primary host
exits 1 with 291 finding lines:

| Group | Lines | What carries the layout |
| --- | --- | --- |
| Relay cutover tool, its two test files | about 1,020 (capped to 131 lines of output) | the hostname: the tool drives exactly two named hosts |
| Harness settings | 35 | the home directory in hook commands, registered checkouts as Codex trust keys |
| docs/ notes, plans, runbooks, specs | 57 (plus 193 capped) | hostnames in prose and commands, home and WORK_ROOT paths |
| tasks/files attachments | 44 (plus 15 capped), 9 files on 6 tasks | raw logs, probe output, ledgers |
| Test helpers | 2 | a privacy denylist naming the hosts, one docstring |
| facts/capabilities.toml | 1 | a hostname in a fact's note |
| README.md, AGENTS.md references | 29 and 1 | missing or ignored paths in backticks |

Two properties of the checker shape the design:

- The layout values are read from the machine the check runs on: its hostname, home,
  WORK_ROOT, registered checkouts and their parents, and any `banned` values in the
  user's `ops/ops-check.toml`. A tree clean on the primary host can still fail on the
  second host, whose hostname appears about 700 times in tracked files and is invisible
  to a run here.
- Matching is case-sensitive and whole-word. `layout_allowed` in a root `.ops-check.toml`
  is a list of path prefixes (plain `startswith`), and `tasks/*.md` records are exempt.

## 2. Outcome

After this change:

1. tools/ops-check is a byte-identical copy of a version ops main has landed, adopted
   with ops `bin/vendored` (`vendored adopt ops-check`).
2. The pre-commit hook runs `tools/ops-check` before its other checks and refuses the
   commit on any finding (exit 1) or when the checker cannot run (exit 2, or the file is
   missing).
3. `tools/ops-check` exits 0 over the tree on the primary host and with the second host's
   values simulated (section 4, D7).
4. Every attachment the layout rule refuses keeps its exact raw bytes, owned by an open
   restoration task, and is represented on its task by a labelled portable derivative.
5. README.md, AGENTS.md and tools/README.md describe the gate as it runs.

## 3. Scope

In: the adoption, the hook, `.ops-check.toml`, the doc and helper rewrites, the
attachment fallback, the reference rewrites, a restoration follow-up task, guide text.

Out:

- tt adoption and a `just check` recipe. `just test` calls pytest directly; obs-d95365
  made the same call. Adopting the front door is its own task if wanted.
- Fixing or retiring the relay cutover tool (hq-7e81ed). D4 makes adoption independent
  of that decision.
- The attachment-layout exemption itself (ops-941e4f, ops-6e157a).
- Rewriting harness settings to avoid absolute paths (D3).

## 4. Decisions

### D1. Adopt through `vendored adopt`, unchanged

Run ops `bin/vendored adopt ops-check` in the worktree. It writes the landed bytes of
ops main's `bin/ops-check` (version 14 at a1c9cf9 today; whatever main has landed when
the step runs) and keeps tools/README.md, which already lists ops-check, in step. The
copy is never edited; `vendored check` in ops judges it, and `vendored publish` updates
it afterwards.

Rejected: copying the file by hand. Publish only refreshes copies that already exist,
and a hand copy has no landed-version guarantee.

### D2. The pre-commit hook runs ops-check first

`.githooks/pre-commit` gains `hygiene_check()`, run before `local_layer`, `docs_check`
and `facts_check`:

- tools/ops-check missing: refuse, naming ops `bin/vendored adopt ops-check` as the
  repair (the same shape as the existing tools/ops-docs check).
- exit 1: pass the checker's stderr through and refuse with one line saying the
  findings must be fixed in the tree, pointing at the guide section (D8).
- exit 2 or any other non-zero: pass stderr through and refuse; the checker could not
  run, which is never a pass.

The checker reads tracked files from the working tree, not the staged blobs. That is
its contract everywhere it runs, and the hook keeps it: a tracked file with an unstaged
finding refuses a commit that does not touch it. The fact check stays staged-tree, as
it is today.

Why first: every later check is cheaper to read once hygiene passes, and the ops
template's check command runs it first.

Effect on record commits: hq sets `[git] commit` for tasks, so every record write runs
this hook. A finding anywhere in the tree turns record commits into `commit_failed`
warnings until it is fixed. This is the intended gate; D8 documents the route for the
common case, a new attachment carrying host values.

Tests (in .githooks/test_pre_commit.py, beside the existing ones): a fixture repository
whose tools/ops-check is the vendored copy, run with an environment built key by key
(`PATH`, `HOME` at a temporary directory the test owns, `XDG_CONFIG_HOME` at an empty
temporary directory so no tasks registry or banned list is read, `GIT_CONFIG_GLOBAL`
and `GIT_CONFIG_NOSYSTEM`). A tracked file carrying that fake `HOME` path is the
planted finding. Cases:

1. a planted finding refuses, with the checker's line in stderr, and the docs check
   does not run (ordering);
2. a missing tools/ops-check refuses;
3. a checker that exits 2 refuses (a malformed `.ops-check.toml` produces it for real);
4. a clean fixture passes.

Each is seen to fail against a hook without `hygiene_check` before the hook changes.

### D3. Harness settings are host configuration by design

`.ops-check.toml`:

```toml
layout_allowed = [
  "claude/settings.json",
  "codex/config.toml",
  "codex/hooks.json",
  "codex/work/hooks.json",
  # D4 entries follow
]
```

These four files are linked into harness homes and carry what the harnesses read
literally: Codex trust tables keyed by absolute project paths, and hook commands that
name absolute script paths. The checker's docstring names this case ("a repository
whose content is host configuration by design").

Each entry is a file, not a directory prefix, so a new file under claude/ or codex/
(a mod, a probe, a new settings file) is still checked.

Rejected: prefixes `claude/` and `codex/`, which would exempt mods and probes that are
ordinary code. Rejected: rewriting the hook commands to `$HOME`. The files are live
state that the clean filter and trust hooks guard (AGENTS.md Rules); changing what every
harness home executes is a behaviour change, outside a hygiene adoption.

### D4. The relay cutover tool keeps its host names, by path

Added to `layout_allowed`:

```toml
  "tools/relay_cutover_bootstrap/",
  "tools/relay-cutover-host",
  "tools/test_relay_cutover_",
  "docs/runbooks/relay-cutover.md",
  "docs/plans/2026-10-19-relay-cutover.md",
```

The tool operates exactly two named hosts: its host table, its operation-id grammar
and its input-manifest validation spell them, and its tests assert the refusals for
any other host. Its runbook and the plan that scripts its window use the names as the
tool's arguments (`--host`, `--observe`, `ssh … <host>`). The names are the tool's
fleet configuration, the same class as D3.

hq-7e81ed decides whether the tool is fixed or retired. Retirement deletes the code and
moves or restates the runbook (that task's own curate-docs note), and its entries go in
the same change. The implementation notes this on hq-7e81ed.

Rejected: parametrizing the hosts now. That touches about a thousand lines of a
23,000-line tool whose future is undecided, for no behaviour gain. Rejected: waiting for
hq-7e81ed, which would tie a hygiene gate to an unrelated scope decision.

The other relay-cutover documents (the bootstrap plan, the cutover ledger attachment)
mention a host in passing and follow D5 and D6.

### D5. Documents and helpers are rewritten to placeholders

Every other tracked file that carries a layout value on either host is rewritten:

| Value | Prose | Literal (commands, JSON, tables) |
| --- | --- | --- |
| primary host's name | "the primary host" | `host-a` |
| second host's name | "the second host" | `host-b` |
| the home directory | `~` | `~` |
| WORK_ROOT | `$WORK_ROOT` | `$WORK_ROOT` |
| a registered checkout or the sync root | `~/d/<project>`, "the sync root" | `~/d/<project>` |

Within a rewritten document every spelling of a host name is replaced, capitalized
ones included, so the document reads consistently, although the checker matches only
the lowercase word. The mapping from `host-a` and `host-b` to the real names is written
once as a task note on hq-c6a149 (records are exempt), never in a tracked file.

This covers: docs/notes (the claim-guard judgment, the Codex never-rejections brief, the
session-log survey note and its data file under docs/notes/data), docs/plans (session
archive, pi live picks, relay cutover bootstrap), docs/specs (session archive, pi live
picks, operator runbooks), the session-archive test helper's docstring and the fact
note in facts/capabilities.toml (which `tools/harness-facts check` then still passes).

The originals stay in git history before this branch, as obs-d95365 did for its
historical documents. A design spec or plan is a decision record; replacing a host
name with its role changes no decision.

The privacy denylist in tools/test_session_log_cases.py names both hosts on purpose: it
forbids them in fixtures. It moves into a module that holds only that pattern
(tools/session_log_private.py), and that one file is allowed by exact path. Rejected:
allowing the whole 500-line test file, which would also exempt any real leak added to
it. Rejected: spelling the names so the checker misses them, which defeats the check.

### D6. Attachments: raw bytes kept, portable derivatives attached

Until an executing ops-check admits ledger-backed attachments (ops-941e4f's design, then
ops-6e157a's remedy, then a published version), the lore reference's fallback applies to
every attachment the layout rule refuses on either host: today nine files on six tasks
on the primary host (hq-48c5c6, hq-583ac7, hq-7b65dc, hq-7cf7c1, hq-c075d0, hq-c6c847),
plus whatever the D7 simulation adds (hq-7a2b95 at least).

1. File a restoration task in hq, the counterpart of obs-875105: it depends on
   ops-6e157a, owns the raw copies, and restores the exact bytes through `tasks detach`
   and `tasks attach` once the shipped exemption admits them.
2. Copy each raw file to `$WORK_ROOT/hq/<restoration-id>/<task-id>/<name>`, verify its
   SHA-256 against the blob at main before the branch, note the directory's creation at
   once, and record a `retained:` evidence note per file on the restoration task (host,
   path, sha256, purpose, owner, trigger) plus a manifest for the directory.
3. Make a derivative replacing every layout value with the D5 placeholders. On the
   original task, note the placeholder-to-original mapping for that file and the raw
   item's identity.
4. `tasks detach` the original and `tasks attach` the derivative under the same name,
   captioned as a portable derivative pointing at the restoration task. `tasks show`
   must list it.

Closed tasks receive these lifecycle notes and attachments without reopening; obs did
the same. No raw copy is discarded; the git history of tasks/files also keeps the
originals, but the reference's raw-copy record is what the restoration task verifies.

Rejected: `layout_allowed = ["tasks/files/"]`. The reference forbids broadening an
exemption for this case: it would exempt every future attachment, ledger-backed or not.

### D7. The second host is checked by simulation

A run on the primary host sees only its own values. Before the hook change commits, the
tree is checked twice:

1. `python3 tools/ops-check` as is.
2. The same with `XDG_CONFIG_HOME` pointed at a temporary directory holding a copy of
   the tasks registry and an `ops/ops-check.toml` whose `banned` lists the second host's
   hostname, its WORK_ROOT and its sync root, each read from that host's login
   environment over ssh at that moment (a plain non-interactive ssh shows no WORK_ROOT) (never written into a tracked file). Its registered checkouts that differ from
   the primary host's are banned too.

Both must exit 0. The second host's home is the same path as the primary host's; if the
read shows otherwise, it joins the banned list.

Rejected: running the real checker on the second host. Its checkout follows main
through sync, so it cannot see the branch before the merge, and the simulation covers
the same values. A run there after integration is a welcome observation, not a gate.

### D8. Guides

- AGENTS.md Gates: the pre-commit hook runs tools/ops-check first; what it checks in one
  line; a record commit refused by it means a finding in the tree; a new attachment
  carrying host values follows the retained-item reference's fallback (raw copy kept,
  derivative attached), and `.ops-check.toml` is not widened for it.
- README.md: the same in its checks section, and `.ops-check.toml` in Layout with the
  D3/D4 reasons in one line each.
- tools/README.md: as `vendored adopt` writes it.
- The 30 reference findings are fixed by these rules:
  - a path that exists elsewhere in this tree gets its real path (`pi/extensions/…`);
  - a path in another project gets that project's prefix before the backticks
    (lore `instructions/AGENTS.md`, ops `bin/project-colors`);
  - a git-ignored path under local/, a file in a harness home (`auth.json`,
    `history.jsonl`, pi home names), a file a mod engine writes, and an example
    (`prefix/.worktrees`, `hq/tools`) are written without backticks, since they are
    destinations or examples, not claims about this tree.

## 5. Order of work

The hook runs from the worktree's own .githooks, so commits on the branch are gated from
the moment the hook change lands. The order is therefore: adopt the checker; fix the
references; add `.ops-check.toml`; rewrite documents and helpers; file the restoration
task and replace the attachments; confirm both D7 runs exit 0; then the hook change with
its tests; then the guides.

## 6. Acceptance

- tools/ops-check equals ops main's landed `bin/ops-check` byte for byte.
- `python3 tools/ops-check` exits 0 on the primary host, and with the second host's
  values simulated (D7).
- The four D2 test cases pass, each seen failing first against the old hook.
- `just test` passes; `tools/harness-facts check` passes; `tasks check` is clean.
- For each replaced attachment: the raw copy's SHA-256 equals the pre-branch blob, its
  `retained:` record is on the restoration task, the derivative is listed by
  `tasks show`, and the mapping note is on the original task.
- A commit with a planted layout value in a tracked file is refused by the real hook in
  the worktree, and the same commit without it succeeds.

## 7. Risks

- Record commits fail more often: any session that attaches a raw log with host values
  gets `commit_failed` until it applies the fallback. D8 tells it how; the cost is the
  intended price of the gate.
- A future ops-check version may add a rule hq fails. `vendored publish` then writes the
  new copy into this tree, and the next commit here refuses until the finding is fixed.
  That is how the shared checks are meant to propagate.
- The D4 allowance outlives its reason if hq-7e81ed retires the tool and forgets the
  entries; the note on hq-7e81ed is the guard.
