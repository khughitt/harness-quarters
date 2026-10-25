# ops-check adoption: the shared hygiene checks in hq's commit gate

Path placeholders name main checkouts or their parent directories. Substitute paths
from `tasks projects --paths --pretty` before using command examples.

Status: draft for review, revision 2, 2026-10-24.
- **Revision 1** (28ed52b) went through a fresh-context agent review: 2 important
  findings and 13 minor.
- **Revision 2** addresses all of them:
  - the existing hook-test fixture gains the checker, and only cases 1 to 3 need RED;
  - `local_layer` stays ahead of the hygiene check;
  - the second-host simulation covers checkout parents and that host's own banned
    list, and runs again on the final tip;
  - the reference rules name the prefix parser's traps;
  - the attachment records carry the reference's full field set;
  - the risks cover the working-tree read.
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
exits 1 with 291 lines of output. The table counts output lines; a file with more than
ten carrying lines prints ten and then one count line, given in brackets as the lines
it stands for.

| Group | Output lines | What carries the layout |
| --- | --- | --- |
| Relay cutover tool, its two test files | 122 (about 1,040 carrying lines) | the hostname: the tool drives exactly two named hosts |
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
2. The pre-commit hook runs `tools/ops-check` right after its staged `local/` refusal
   and before its other checks. It refuses the commit on any finding (exit 1) or when
   the checker cannot run (exit 2, or the file is missing).
3. `tools/ops-check` exits 0 over the tree on the primary host and with the second host's
   values simulated (section 4, D7).
4. Every attachment the layout rule refuses keeps its exact raw bytes, owned by an open
   restoration task, and is represented on its task by a labelled portable derivative.
5. README.md and AGENTS.md describe the gate as it runs. tools/README.md stays as ops
   publishes it: its generic row ("the pre-commit hook, `just check` and CI") cannot be
   edited here, and the root guides say which of those hq has.

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

### D2. The pre-commit hook runs ops-check ahead of the tree checks

`.githooks/pre-commit` gains `hygiene_check()`. `main()` runs `local_layer`, then
`hygiene_check`, then `docs_check` and `facts_check`:

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

Why this place: the ops template's check command runs the hygiene checks first, and the
later checks are easier to read once hygiene passes. `local_layer` stays ahead of it.
That check is cheap and staged-only. Its refusal of a force-added `local/` file is the
specific message, and a layout finding in that same file would otherwise mask it.

Effect on record commits: hq sets `[git] commit` for tasks, so every record write runs
this hook. A finding anywhere in the tree turns record commits into `commit_failed`
warnings until it is fixed. This is the intended gate; D8 documents the route for the
common case, a new attachment carrying host values.

Tests (in .githooks/test_pre_commit.py, beside the existing ones). The existing `world`
fixture creates tools/ops-docs and tools/harness-facts but no tools/ops-check. Once
the hook refuses a missing checker, every existing case in the file would fail on it.
So `world` changes in three ways:

- It carries the vendored tools/ops-check.
- It runs the hook and its own git commands with an environment built key by key:
  `PATH`; `HOME` at a temporary directory the test owns; `XDG_CONFIG_HOME` at an empty
  temporary directory, so no tasks registry or banned list is read;
  `GIT_CONFIG_GLOBAL` at a temporary file, with `GIT_AUTHOR_*` and `GIT_COMMITTER_*`
  set; and `GIT_CONFIG_NOSYSTEM=1`. No inherited `GIT_*` variable comes along.
- It no longer copies `os.environ`, which today carries the real `HOME` and
  `WORK_ROOT` into the checker.

The real hostname remains a layout value, and no fixture file contains it. A tracked
file carrying the fake `HOME` path is the planted finding. Cases:

1. a planted finding refuses, with the checker's line in stderr, and the docs check
   does not run (ordering);
2. a missing tools/ops-check refuses;
3. a checker that exits 2 refuses (a malformed `.ops-check.toml` produces it for real);
4. a clean fixture passes, and the existing cases keep their verdicts.

Cases 1 to 3 are each seen to fail against the hook without `hygiene_check` before the
hook changes. Case 4 passes both before and after; it guards that the new check does
not refuse a clean tree.

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
literally:

- claude/settings.json and both Codex hooks.json files: hook commands that name
  absolute script paths.
- codex/config.toml: workspace roots, filesystem grants, an MCP server's path argument,
  and `hooks.state` trust hashes keyed by absolute hook-file paths. Its project trust
  table is untracked, in local/.

The checker's docstring names this case ("a repository whose content is host
configuration by design").

Each D3 entry names one file, not a directory, so a new file under claude/ or codex/
(a mod, a probe, a new settings file) is still checked. Matching is a plain prefix
match, so an entry also admits a path that merely extends it (`codex/config.toml.bak`).
No such file is tracked, and none is expected.

Rejected: prefixes `claude/` and `codex/`, which would exempt mods and probes that are
ordinary code. Rejected: rewriting the hook commands to `$HOME`. The files are live
state that the clean filter and trust hooks guard (AGENTS.md Rules); changing what every
harness home executes is a behaviour change, outside a hygiene adoption.

### D4. The relay cutover tool keeps its host names, by path

Added to `layout_allowed`:

```toml
  "tools/relay_cutover_bootstrap/",
  "tools/relay-cutover-host",
  "tools/test_relay_cutover_bootstrap.py",
  "tools/test_relay_cutover_transport.py",
  "docs/runbooks/relay-cutover.md",
  "docs/plans/2026-10-19-relay-cutover.md",
```

The package is a directory prefix, so a new module of the tool is covered. The other
entries are exact paths, which remain prefix matches as D3 says.

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

Hygiene amendment hq-d5ba0a: fixed deployment paths are fleet configuration too.
The policy also allows tools/relay-cutover and tools/test_relay_cutover.py, which
recognize the deployed guard and invoke the fixed remote entry. The capture-notice,
claim-guard and relay wiring test files are allowed individually because they assert
the exact deployed hook strings. Replacing those literals would change the contracts
under test. The tools/relay-cutover prefix also covers its sibling executables under
the checker's prefix matching; those all belong to the same fleet tool.

### D5. Documents and helpers are rewritten to placeholders

Every other tracked file that carries a layout value on either host is rewritten:

| Value | Prose | Literal (commands, JSON, tables) |
| --- | --- | --- |
| primary host's name | "the primary host" | `host-a` |
| second host's name | "the second host" | `host-b` |
| the home directory | `~` | `~` |
| WORK_ROOT | `$WORK_ROOT` | `$WORK_ROOT` |
| a registered checkout or the sync root | `<project-checkout>`, "the sync root" | `<project-checkout>` |

Hygiene amendment hq-d5ba0a: use role placeholders such as `<hq-checkout>` for a
specific main checkout and `<checkout-parent>` for its parent. Home-relative aliases
of registered paths are machine layout too; a bare `~` remains valid.

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

The survey data's 183 records each carry the primary host's name in their `host`
field. They take `host-a`. The survey note's line telling a reader to resolve `source`
beneath the named host's home now says that `host-a` is the primary host and that the
mapping is on hq-c6a149.

The privacy denylist in tools/test_session_log_cases.py names both hosts on purpose: it
forbids them in fixtures. It moves into a module that holds only that pattern
(tools/session_log_private.py), and that one file is allowed by exact path. pytest puts
tools/ on the import path (tools/conftest.py), and nothing else imports the pattern.
Rejected: allowing the whole 500-line test file, which would also exempt any real leak
added to it. Rejected: spelling the names so the checker misses them, which defeats the
check.

One accepted cost: the closed task hq-bb90ca's attached `breaks.py` copies only the test
file into a scratch tree. A rerun of that historical harness would now fail on the
import. The attachment is evidence of a past run and stays as it is.

### D6. Attachments: raw bytes kept, portable derivatives attached

Until an executing ops-check admits ledger-backed attachments (ops-941e4f's design, then
ops-6e157a's remedy, then a published version), the lore reference's fallback applies to
every attachment the layout rule refuses on either host. Today that is nine files on six
tasks on the primary host (hq-48c5c6, hq-583ac7, hq-7b65dc, hq-7cf7c1, hq-c075d0,
hq-c6c847). The second host's name adds two files on hq-7a2b95: its smoke driver and
its rollout JSON, whose names begin with that host's name. A spec cannot spell those
names and still pass D7. The D7 run is the final word on the second host's set.

1. File a restoration task in hq, the counterpart of obs-875105. It depends on
   ops-6e157a and owns the raw copies. It restores the exact bytes through
   `tasks detach` and `tasks attach` once the shipped exemption admits them.
2. Copy each raw file to `$WORK_ROOT/hq/<restoration-id>/<task-id>/<name>` and verify
   its SHA-256 against the blob at main before the branch. Note the directory's creation
   at once.
3. On the restoration task, record a `retained:` note per file with the reference's full
   field set: host, kind `evidence`, path, state `kept`, verification `verified`,
   sha256, purpose, next_owner `task:<restoration-id>`, and cleanup_trigger. Add a
   scratch record with a manifest and its hash for the directory.
4. Make a derivative replacing every layout value with the D5 placeholders. On the
   original task, note the placeholder-to-original mapping for that file and the raw
   item's identity.
5. `tasks detach` the original and `tasks attach` the derivative under the same name.
   Its caption says it is a portable derivative and points at the raw item's
   `retained:` record on the restoration task. `tasks show` must list it.

Names are kept, so existing ledger lines and references still resolve. Four file names
spell the second host's name (two on hq-48c5c6, two on hq-7a2b95). The checker reads
content, not paths, so they pass. Renaming them would break those references for no
check's sake.

Closed tasks receive these lifecycle notes and attachments without reopening; obs did
the same. No raw copy is discarded; the git history of tasks/files also keeps the
originals, but the reference's raw-copy record is what the restoration task verifies.

Rejected: `layout_allowed = ["tasks/files/"]`. The reference forbids broadening an
exemption for this case: it would exempt every future attachment, ledger-backed or not.

### D7. The second host is checked by simulation

A run on the primary host sees only its own values, so the tree is checked twice:

1. `python3 tools/ops-check` as is.
2. The same with `XDG_CONFIG_HOME` pointed at a temporary directory holding a copy of
   the tasks registry and an `ops/ops-check.toml`. Its `banned` list merges:
   - the second host's hostname, WORK_ROOT and sync root;
   - each of its registered checkouts that differs from the primary host's, and each
     such checkout's parent;
   - the `banned` values of its own `ops/ops-check.toml`.

   Each value is read from that host over ssh at that moment, from its login
   environment, since a plain non-interactive ssh shows no WORK_ROOT. None is written
   into a tracked file.

Both must exit 0. The second host's home is the same path as the primary host's; if the
read shows otherwise, it joins the banned list.

The pair runs at two points:

- before the hook change commits;
- on the final branch tip, at verification, so the hook and guide commits are covered
  too. If main moves before the merge, the pair runs again on the merged tree.

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
    (lore `instructions/AGENTS.md`, ops `bin/project-colors`). The prefix is the bare
    word followed by one space, directly before the opening backtick. A possessive
    ("ops's") parses as the prefix "s", which is why three of today's findings fail;
  - a git-ignored path under local/, a file in a harness home (`auth.json`,
    `history.jsonl`, pi home names), a file a mod engine writes, and an example
    (`prefix/.worktrees`, `hq/tools`) are written without backticks, since they are
    destinations or examples, not claims about this tree.
- Two parser traps to keep in mind while editing:
  - A reference that opens a line takes its prefix from the last word of the line
    above. Several registered prefixes are common words ("tasks", "ops", "hq"), so
    rewrapping can create findings. The checker runs again after every guide edit.
  - A prefixed reference to a bare filename (ops `cli.toml`) is avoided. The
    checker's lookup of another project's tracked basenames inherits the hook's git
    environment, so from a hook it can read hq's index instead. Every D8 target has a
    slash and is checked by existence, so this does not arise. This was read from the
    code and not reproduced. If implementation reproduces it, it goes to ops as
    feedback.

## 5. Order of work

The hook runs from the worktree's own .githooks, so commits on the branch are gated from
the moment the hook change lands. The order is therefore: adopt the checker; fix the
references; add `.ops-check.toml`; rewrite documents and helpers; file the restoration
task and replace the attachments; confirm both D7 runs exit 0; then the hook change with
its tests; then the guides; then both D7 runs again on the final tip.

Record commits made before the hook change (attachment replacement, retained and mapping
notes) run only the old checks, so the unfinished cleanup does not block them. obs met
that blocking because its gate came first.

## 6. Acceptance

- tools/ops-check equals ops main's landed `bin/ops-check` byte for byte.
- `python3 tools/ops-check` exits 0 on the primary host, and with the second host's
  values simulated (D7), on the final tip.
- The four D2 test cases and the existing hook cases pass. Cases 1 to 3 were each seen
  failing first against the old hook.
- `just test` passes; `tools/harness-facts check` passes; `tasks check` is clean.
- For each replaced attachment: the raw copy's SHA-256 equals the pre-branch blob, its
  `retained:` record is on the restoration task, the derivative is listed by
  `tasks show`, and the mapping note is on the original task.
- In a temporary clone of the branch tip (with `just setup` run there, so its
  .githooks are installed), a commit with a planted layout value in a tracked file is
  refused by the real hook. The same commit without it succeeds. The clone is then
  deleted, so neither commit reaches the branch.

## 7. Risks

- Record commits fail more often: any session that attaches a raw log with host values
  gets `commit_failed` until it applies the fallback. D8 tells it how; the cost is the
  intended price of the gate.
- A future ops-check version may add a rule hq fails. `vendored publish` then writes the
  new copy into this tree, and the next commit here refuses until the finding is fixed.
  That is how the shared checks are meant to propagate.
- The D4 allowance outlives its reason if hq-7e81ed retires the tool and forgets the
  entries; the note on hq-7e81ed is the guard.
- The working-tree read crosses sessions. In the shared main checkout, one session's
  uncommitted edit that carries a layout value turns every other session's record
  commits into `commit_failed` until it is fixed or committed clean.
- The converse hole: a staged blob that carries a value passes when the working-tree
  copy was fixed afterwards but not restaged. The checker's contract reads the working
  tree, and this design does not change it.
- Cost: each commit, record commits included, pays one checker run. That is about 3 s
  on today's tree, measured with the findings present. It should drop once the
  reference findings, each of which costs git calls, are gone. The plan measures it
  again on the clean tree.
