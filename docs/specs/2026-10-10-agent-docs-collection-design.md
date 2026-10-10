# Agent docs in mindful: the collection and the external document reference — design

Task: `hq-5a3e12`, under `hq-d7b5b2`. Status: draft, revised 2026-10-10 after spec review round 1 (codex).
Brief: lore `docs/notes/2026-10-02-agent-working-docs-brief.md` (§5 holds the user's
decision and hq-fa8757's findings). Research: `hq-fa8757` (notes of 2026-10-10).

## 1. Decision and scope

The narrative layer of agent work (scoping briefs, handoffs, implementation plans) leaves
project repositories and lives in the user's mindful corpus as thoughts owned by the agent
that wrote them. Task records and design specs stay in the repository. The user decided
this on 2026-10-02 (brief §5); this design settles how the pieces fit.

1. **One reference form**, `mindful:thought:<32 hex>`, used wherever a record points at a
   document outside the repository (§3).
2. **The tasks CLI accepts an external document link** in `--plan` and `--spec`, fetches
   its body through a command configured per scheme on the host, and keeps every check
   that reads a plan today (`--step`, `step_missing`, `unlinked_step`, `doc_missing`)
   working against the fetched body, and `tasks doc` prints that body so execution
   helpers that need a file get a local snapshot (§4.3, §6.4).
3. **obs recognises the reference** instead of treating it as a repository path, and its
   outcome measures say so (§5).
4. **The collection** is the shared corpus, separated by owner and tag: no second home,
   no new mindful structure (§6).
5. **The write path** works while the web app holds the writer lock: ops's `mindful-op`
   carries an agent-authored capture and an etag-checked edit, with the body read from a
   file (§6.3).
6. **The personal profile says `design_docs: mindful`**, the staging hook refuses a new
   plan or brief in the tree under it, and the skills that write or read these documents
   name the new location (§7, §8).

Not in this design: moving task records or specs (the user kept them in the repository;
brief §4 alternative 3 is rejected); migrating the ~300 existing plans and 73 briefs (they
stay where they are and keep resolving; new documents go to mindful); a `tasks` command
that prints a fetched document (filed as an idea, §11); a mindful CLI that forwards writes
to a running server (§6.3 rejects it for now and files the idea); indexing mindful writes
in obs as an authorship signal (§5.3 defers it); and the work and external profiles, which
keep `exclude`.

## 2. Evidence from the tree (2026-10-10)

What each project does today, from reading the code (file references are repository
relative; line numbers as of this date).

**mindful v6** holds the documents without change. `mindful add <title> --body-file <path>
--as agent:<id>@<model> --tag <t> --alias <a> --link-to <ref>` stores the markdown body
verbatim (hq-fa8757: 4345 bytes, same SHA-1, `### Task N:` headings kept); the id
`thought:<32 hex>` survives edits; `show` accepts the id, an id prefix, a bare uid prefix,
an alias or a title, and `--json show` returns `{id, uid, title, alias, body, authorship,
version, archived, related}`. Live checks this session: `show` rejects a `mindful:` prefix
("no thought matching"); `edit` takes only `--body <text>` or `-i` (no `--body-file`);
`list`/`search --by agent:<id>` filter on `createdBy`, with no kind-only filter. Tags are
thoughts: `#name` in search resolves by alias only (`packages/mindful/src/search.ts:54`),
so a tag must exist as an aliased thought before it can be used. Under the raw/curated
design (`docs/designs/2026-10-05-mindful-v6-raw-curated-design.md` §4–§5) every capture,
agent capture included, is raw, hidden from the curated default views once the rollout
switches defaults, and always reachable by exact ref. The web app takes the writer lock
for its lifetime (`packages/web/src/lib/server/runtime.ts:39`); a CLI write then fails with
`data dir … is read-only in this process: locked by web pid …`. `POST /api/op` on the
loopback origin takes one JSON op (`capture`, `edit` with a required 64-hex `etag`,
`get`, `tag`, `structure.add`, …) with structured `actor`/`via` objects
(`packages/mindful/src/contracts/ops.ts`); the web app was listening on 3331 when this
was written.

**tasks** rejects anything but a repository path. `validate_doc_shape` (`src/format.rs:306`)
requires a normalised `.md` path and runs on every record parse through `validate_task`,
so a record holding `mindful:thought:…` would fail to load (`Error::Parse` from
`read_task_with_raw`, `src/repo.rs:511`). `validate_doc_path` (`:319`) requires a
`plan_dirs`/`spec_dirs` prefix. `Resolver::resolve_doc` (`src/resolve.rs:136`) treats a
value with no `/` and no `.md` as a bare name and substring-searches the roots. Files are
opened directly in `step_exists` (`src/resolve.rs:181`; callers `commands/mod.rs:1033`,
`commands/edit.rs:362`, `commands/show.rs:133`, `moving/preflight.rs:166`) and in `check`
(`commands/check.rs:457-491` for `doc_in_main_checkout`, `doc_missing`, `step_missing`;
`:544-565` for `unlinked_step`). `show` renders the absolute path (`show_text.rs:294`). The
project config (`src/repo.rs:118`, committed and synced) has no scheme table; the host
config (`src/config.rs`, `$XDG_CONFIG_HOME/tasks/config.toml`) exists for machine-specific
settings. The closest subprocess pattern is the editor launch, `sh -c "<cmd> \"$1\""`
(`commands/edit.rs:312`), and the capped stdout read in `src/clipboard.rs:57`. `--source`
is opaque by design (`docs/specs/2026-09-06-task-source-design.md:16-22`); 196 records
across the registry hold `mindful:thought:<hex>`, and the scope skill already strips the
prefix before `mindful --json show` (`skills/scope/SKILL.md:52-54`).

**obs** never opens a spec or plan. `join.task_index_rows` (`join.py:284`) stores `spec`
and `plan` as strings. `outcomes._repository_path` (`outcomes.py:318-327`) passes any
non-absolute string through as a repository-relative path, so a reference would reach
`authorship.attribute` (`authorship.py:166`) as a path no session ever wrote: authors
empty, reason `None`, every factor `unknown`, where a missing link gives reason
`no_path`. `review_text.DOC_PATH` and `KIND_CUES` (`review_text.py:40-43`) recognise only
`docs/(specs|designs|plans)/…md`, so a review round that cites a thought can fall to
`artifact_unknown` (`outcomes._placed`, `:268`). `shell_clear` (`shell_clear.py:391`)
treats any `mindful` command as uncleared. The outcome-measures spec says a spec or plan
"is a path in a checkout" (`docs/specs/2026-09-28-outcome-measures-design.md:244`).

**ops** validates `design_docs` against `("commit", "exclude")` (`bin/ops-profile:37`),
layers it per profile from `profiles.toml` (personal `commit`, work and external
`exclude`), and prints it in the session line (`:544`). The staging hook
`hooks/claude-pretooluse` check 4 refuses a new or changed file under `docs/superpowers/`
when the value is not `commit` (`:113`, `:1915-1947`); it never inspects `docs/plans/` or
`docs/notes/`. `bin/mindful-op` is the only loopback client: it posts one JSON op from
stdin for the kinds `capture, get, journal, tag, untag, archive, triage.queue,
triage.mark`, builds a capture from a paste with `--capture-paste --via-agent`, and
requires explicit `actor` and `via` on a JSON mutation plus an `etag` on a write to an
existing thought. `edit` is not among its kinds.

**lore and the skills.** The personal profile (`profiles/personal.md:3-7`) names
`docs/specs/` and `docs/plans/`; the global "Design & Plan Docs" fragment
(`instructions/fragments/design-docs.md`) says the profile decides and the hook enforces.
The scope skill (tasks `skills/scope/SKILL.md:100-117`) writes briefs at
`docs/notes/YYYY-MM-DD-<topic>-brief.md` and sets the goal's source to that path; the
tasks skill (`skills/tasks/SKILL.md:585-598`) attaches plans with `--plan <topic>` and
`--step`; the flow skill (flows `skills/flow/SKILL.md:84-86`) records `gate: planned
<path>`, and `bin/flow-state:25` excludes `docs/specs` and `docs/plans` from the
fingerprint. The vendored writing-plans skill defaults to `docs/superpowers/plans/` and
defers to user preference.

## 3. The reference form

**`mindful:thought:<32 lowercase hex>`.** The scheme is `mindful`; the remainder,
`thought:<hex>`, is exactly what `mindful show` accepts. This is the form the 196 existing
`--source` values already use, so one spelling covers sources, specs, plans, gate notes
and prose.

Rejected: `thought:<hex>` as the stored form. It would make `thought` the scheme and tie
the tracker's dispatch to mindful's id vocabulary; it also differs from every existing
source. The scope skill's prefix-strip stays as the one place that knows the remainder is
a mindful ref.

**Only ids in records.** `mindful show` also resolves aliases and titles, and a writer may
type one (`tasks edit <id> --plan mindful:agent-docs-plan`), but an alias can be moved and
a title changed, so the record must hold the id. Resolution at write time: the tracker
fetches with the reference as typed, reads the canonical id from the fetch (§4.2), and
stores `mindful:thought:<hex>`. A reference that resolves to nothing is refused as today's
`doc_not_found`.

**Generality.** The tracker sees `<scheme>:<rest>`, with `<scheme>` matching
`[a-z][a-z0-9-]*` and `<rest>` non-empty, and knows nothing about mindful. A second scheme
needs one line of host config and no code. Nothing in this design introduces a second
scheme; the generality is there so that the tracker never learns mindful's name.

## 4. The tasks extension

### 4.1 Shape and validation

A `spec` or `plan` value is **external** when its first path segment (the text before any
`/`) contains `:` and matches `<scheme>:<rest>` as above. Everything else keeps today's
rules (a normalised `.md` path under the configured roots, or a bare name resolved by
substring). A repository path can never contain `:` in its first segment today
(`docs/…`), so no existing record changes meaning.

`validate_doc_shape` accepts the external form and `validate_doc_path` skips the root
check for it. Parse must succeed **whether or not the host knows the scheme**: a record
is synced between hosts, and a host without mindful configured must still read it. The
scheme is checked at write time and by `check`, never at parse.

A binary older than this change cannot parse a record holding an external link: it fails
the record with `Error::Parse`, as it does any malformed value. The rollout (§9) installs
the new binary on every host before the first external link is written, the same rule the
task-move and provenance designs set.

### 4.2 The fetch

Host config, `$XDG_CONFIG_HOME/tasks/config.toml`:

```toml
[docs.schemes]
mindful = "mindful-doc"
```

The value is a command run as `sh -c '<cmd> "$1"' -- <rest>`, the editor's pattern, with
`<rest>` as its single argument. The contract:

- **stdout** is one JSON object: `{"id": "<canonical rest>", "body": "<markdown>"}`.
  `id` is what the tracker stores after the scheme (`thought:<hex>`); `body` is the
  document the heading checks read.
- **exit 0** on success. Any other exit is a fetch failure; stderr (first 200 bytes)
  goes into the error or finding.
- stdout is read capped (the clipboard reader's pattern and cap), stderr drained on a
  thread, and the child is killed on overflow. A 30-second timeout kills a hung command;
  the editor launch has none, and a fetch that blocks on a lock or a network would
  otherwise hang `check`.

Why host config and not the project's `tasks/.config.toml`: the command is machine-specific
(where mindful is installed, whether it is at all), and a command in a synced,
committed file would run for anyone who clones the repository. The project config stays
ignorant of schemes; a project's records may reference any scheme, and a host that lacks
it reports `doc_unreachable` (§4.4). `HostConfig` keeps `deny_unknown_fields`; `docs` is a
new optional table on it.

`mindful-doc` is a small script in ops `bin/`: it runs `mindful --json show "$1"`, and
prints `{"id": <id>, "body": <body>}`; a mindful error passes through as a non-zero exit
with the `detail` on stderr. It is the only place that knows mindful's JSON shape. It is
not a tracker concern; it lives with the other host tooling and is installed by the
dotfiles link that puts `mindful-op` on `PATH`.

Rejected: the tracker reading `MINDFUL_HOME/thought/<hex>.md` directly. It is faster
(no node start-up) and needs no lock, but the file format belongs to the nodes library,
alias resolution would need the derived catalog, and it would put mindful's layout in
the tracker. If `check` over many external plans proves slow, `mindful-doc` can read the
file itself; the contract above does not change.

### 4.3 One reader behind every file open

`Resolver::read(kind, value) -> Result<Doc>` where `Doc { reference: String, body:
String }` is the single way a plan or spec body reaches the code. For a path it is
today's `find` plus `read_to_string` (worktree first, then the main checkout, with the
same `doc_in_main_checkout` note); for an external link it is the fetch. Call sites that
move behind it:

- `step_exists` (`src/resolve.rs:181`) and its four callers.
- `check`'s `step_missing` read (`check.rs:481-491`) and `unlinked_step` read (`:544-565`),
  which read each distinct plan once per run, external ones included.
- `show`'s historical-plan read for a closed task (`show.rs:119-131`).

`resolve_doc` keeps path resolution and bare-name search for paths; for an external
value it runs the fetch once, returns the canonical reference, and the write stores it.

`tasks doc <id> --plan|--spec` is the reader exposed as a command: it prints the linked
document's body to stdout through `Resolver::read`, for a path or an external link alike,
and fails with the same errors as `check` would report. It exists so that nothing outside
the tracker needs to know a scheme's tool to read a linked document (§6.4).
`Resolver::abs`, which builds the display path, returns the reference itself for an
external link, and `show` prints it as given (no absolute path, no `(main checkout)`
suffix).

### 4.4 Findings and errors

- Write time (`add`, `edit`, the editor path, `move` preflight): a scheme missing from
  host config is `Error::Config("tasks/config.toml: [docs.schemes] has no <scheme>; a
  record may reference it, but this host cannot resolve it")`; a failed fetch is
  `DocNotFound` with the command's stderr, the same kind a missing path gives, so
  `add_validates_before_writing` holds for external links.
- `check`: for an open task whose link is external, a missing scheme or a failed fetch is
  the **warning** `doc_unreachable` (detail names the scheme and the command's stderr or
  "no [docs.schemes] <scheme> on this host"), beside `doc_missing`, which stays an error
  for paths. The precedent is `unreachable_dep`: a reference this host cannot reach is
  not evidence that the document is gone. A fetched plan whose headings lack a step's
  heading is `step_missing`, an error, as for a path.
- `show` on a closed task whose external plan cannot be fetched warns "historical plan
  <reference> is unavailable", as it does for a missing path.
- `move` preflight (`validate_destination_docs`): an external link is project-independent
  and passes without a fetch; the heading check for `--step` fetches as `add` does.

### 4.5 What does not change

`--source` stays opaque. `--step` keeps the `### Task N:` contract. `spec_dirs` and
`plan_dirs` keep their meaning for paths. The linked-project overlay resolves paths as
today; an external link needs no overlay. `tasks edit <id>` in `$EDITOR` validates the
external form like the flag path.

### 4.6 Tests

Unit: `validate_doc_shape` accepts `mindful:thought:<hex>` and `x:y`, rejects `:y`, `x:`
and `Docs:plan.md`-style first segments that are not a scheme (`src/format.rs`
`rejects_non_normalized_doc_paths` gains cases). Integration (`tests/cli.rs`, with a stub
scheme command written into a scratch host config): `add` and `edit` store the canonical
id returned by the fetch; `--step` is checked against the fetched body; `check` reports
`step_missing` and `unlinked_step` from a fetched plan; `check` reports `doc_unreachable`
on a missing scheme and on a non-zero fetch, and a hung fetch is killed at the timeout;
`show` prints the reference and warns on an unfetchable historical plan; `move` carries an
external link across projects; a record with an external link loads on a host whose
config has no `[docs.schemes]`.

## 5. obs

### 5.1 A reference is not a path

`outcomes._repository_path` returns `None` for a value whose first segment matches the
external form (§4.1), as it does for a path outside the checkout. `authorship.attribute`
then reports the round with a new reason, **`external_doc`**, carrying the reference, in
place of `no_path`. The two states differ: `no_path` means the task has no link to the
artifact; `external_doc` means the link exists but no file write in any session can match
it. Both leave the factors `unknown`. The reason is new vocabulary in the outcome-measures
spec (§5.4).

Rejected: returning `no_path`, as the research note suggested. A dashboard reading
`no_path` would count a linked plan as unlinked, and the later authorship signal (§5.3)
needs the reference kept.

### 5.2 Review rounds that cite a thought

`review_text.DOC_PATH` gains the reference pattern, `mindful:thought:[0-9a-f]{32}`;
`_cited` classifies it as `plan` or `spec` by matching it against the target task's own
`plan`/`spec` field rather than by directory, since the reference has none; with no
matching field the kind stays `unknown` as for an uncued citation. `KIND_CUES` is
unchanged: the words `plan` and `spec` in a note already cue the kind.

`shell_clear` learns the `mindful` command family: `show`, `list`, `search`, `config`,
`help` and the read ops through `mindful-op` (`get`, `journal`, `triage.queue`) are
reads and clear; `add`, `edit`, `tag` and `mindful-op` mutations are writes; `mindful-doc` is a read. Today any `mindful` invocation leaves a round uncleared,
which would make every round whose agent fetched its plan incomplete.

### 5.3 Deferred: mindful writes as authorship

A `mindful add`/`edit` or a `mindful-op capture`/`edit` in a session is an observed write
to a document, and the reference it returns could attribute a plan round the way a file
write does. That needs a parser for the command's output in `call_evidence`, synthetic
write rows keyed by reference, and a branch in `attribute`. It is filed as an obs idea
(§11), not built here: the first measure of this design's effect is how many rounds land
in `external_doc`, which the pilot report can count.

### 5.4 Spec and tests

Amend `docs/specs/2026-09-28-outcome-measures-design.md` where it says a spec or plan
"is a path in a checkout" (`:244-249`) so that it is "a path in a checkout, or an external document reference the task links", and add
`external_doc` to the reason vocabulary. Tests: `test_authorship.py` gains
`test_external_doc_is_unknown_with_reference`; `test_outcomes_derive.py` gains a task
linked to a thought whose rounds are placed with `external_doc`; `test_review_text.py`
gains a cited reference classified by the task's field; `test_shell_clear` (or its home)
gains the mindful read/write cases. The index schema is unchanged: `spec` and `plan` are
already strings.

## 6. The collection in mindful

### 6.1 Shape

- **Shared corpus.** No second `MINDFUL_HOME`, no structure that must exist first. A
  separate home would lose relations to the user's thoughts (a brief born from an idea
  links back to it with `--link-to`) and need its own index and web app.
- **Owner.** Every document is captured `--as agent:<harness>@<model>` (CLI) or with
  `actor {kind: agent, id: <harness>, model: <model>}` (op), the agent that wrote it;
  `via` is the same actor. `list --by agent:<harness>` and `search --by` give one
  harness's documents; the raw/curated rollout keeps them out of the curated views.
- **Tags.** One aliased tag thought, `agent-docs` (alias `agent-docs`), on every
  document, and one per kind: `brief`, `plan`, `handoff`. These four tag thoughts are
  created once in the live corpus by the rollout (§9), by the user's self, since a tag is
  a curated vocabulary entry rather than an agent document.
- **Title.** `<prefix>: <document title>`, for example `hq: Agent docs in mindful — plan`.
  `search '#agent-docs #plan hq'` lists a project's plans; no per-project set or tag is
  created (a set would need a second write per document and cannot scope a search
  anyway). Rejected: a set per project.
- **Body.** The document as the skill writes it today, verbatim: a brief's six sections,
  a plan's `### Task N:` headings. The first body line names the task it serves
  (`Task: hq-5a3e12`), as specs do, so a thought read on its own says where it belongs.
- **Alias.** Optional, for a document the agent will refer to by name in prose; never
  required, never stored in a record (§3).

### 6.2 Reading

Agents read with `mindful --json show thought:<hex>` (strip the scheme first, as the
scope skill does), or with `tasks doc <id> --plan` when the record links the document.
Both work while the web app holds the lock: reads drop to read-only mode and succeed. A
read that precedes a revision is different: it goes through `mindful-op` (`{"kind":
"get", "ref": "thought:<hex>"}`), whose result carries the `etag` of the state read, and
the agent keeps that etag for the edit (§6.3). `show --json` returns no etag, so a body
read through it cannot be revised safely.

### 6.3 Writing while the web app holds the lock

The common case on the desktop host is a running web app (listening on 3331 as this was
written), so the CLI write path fails exactly when an agent needs it. The write path is
**`mindful-op`** in ops, extended:

- `edit` joins `KINDS`; it needs an `etag`, like the other writes to an existing thought.
- `--as-agent <harness>[@<model>]` sets both `actor` and `via` to that agent on a
  `--capture-paste` capture or a JSON mutation that carries neither, the way `--self`
  does for the human.
- `--body-file <path>` on `--capture-paste` replaces stdin with the file, so a long plan
  is not pushed through a PTY frame.
- `mindful-op --edit <ref> --etag <etag> --body-file <path> --as-agent …` is the revise.
  `--etag` is required and is the etag returned by the `get` the agent prepared the
  revision from; `mindful-op` never fetches one itself, because an etag taken at save
  time would only guard the moment between its own read and write, and a body prepared
  from an older read would overwrite whatever changed in between. A `VERSION_CONFLICT`
  from the service is reported as such, with the current etag; the agent re-reads, redoes
  its change on the current body, and edits again. Nothing is merged.
- When no server answers on the origin, `mindful-op` fails as today (connection refused,
  reported). The skill text then says to use the CLI: `mindful add … --as …` for a new
  document and, until mind6 lands `edit --body-file` (§9), `mindful edit <ref> --body
  "$(cat <path>)"`.

Rejected for now: the mindful CLI forwarding a write to the running server when the data
directory is locked. It is the better long-term shape (one command, one flag set, no
agent-specific tool) but is a mindful design decision against its "one writer at a time"
contract and its guide; it is filed as a mind6 idea (§11). The one mind6 change this
design asks for is `edit --body-file <path|->`, matching `add`, so the CLI path can carry
a long body without the argument-length limit.

### 6.4 The execution snapshot

The execution skills drive their helpers with a plan **file**: superpowers'
`sdd-workspace PLAN_FILE`, `task-brief PLAN_FILE N` and `task-done PLAN_FILE …` each
check `[ -f "$plan" ]` and exit 2 otherwise, key the workspace
`.superpowers/sdd/<plan-basename>/` on the file's basename, record the plan's
repo-relative path in a `plan-path` marker, and name it on the ledger's first line. A
plan that passes `tasks check` as `mindful:thought:<hex>` would therefore fail the moment
implementation starts. The snapshot closes that gap:

- **Location.** `<repo root>/.superpowers/sdd/plans/<hex>.md`, where `<hex>` is the
  thought id in the record's `plan` field. The directory is under the self-ignoring
  `.superpowers/sdd/` the helpers already use, so it never reaches `git status` or a
  commit; the name derives from the id, not the title, so it is stable across sessions,
  worktrees of one repository, and title edits, and two plans never collide.
- **Writer.** `plan-snapshot <task-id>` in ops `bin/`: it reads the record's `plan`
  (`tasks show --json`); for a repository path it prints that path and writes nothing;
  for an external link it runs `tasks doc <task-id> --plan`, writes the body to the
  location above (creating `.superpowers/sdd/` with the same self-ignoring `.gitignore`
  `sdd-workspace` writes, so the snapshot is ignored from its first byte), and prints
  the snapshot path. Skills pass its output as `PLAN_FILE`. A fetch failure is the
  tracker's error, exit non-zero, and nothing is written.
- **Refresh.** Every call re-fetches and overwrites. The snapshot is read-only by
  convention: a plan revision goes to mindful through `mindful-op --edit` (§6.3) and the
  next `plan-snapshot` call brings it down. The executing skills call it at execution
  start and after every plan revision they make.
- **Resume.** A session that resumes execution calls `plan-snapshot` before
  `sdd-workspace`. The ledger's first line names the snapshot path, which is unchanged,
  so the ledger is recognised as this plan's; its `Task <N>: complete` lines stay valid
  because the drift contract (`tasks check` `step_missing`) holds the headings of tasks
  that are still open, and a renumbering is caught there before execution resumes.
- Under `design_docs: commit` nothing changes: `plan-snapshot` prints the repository
  path, and the helpers read the committed file as today.

## 7. The profile value and the hook

`design_docs: mindful` is a third value in ops `bin/ops-profile` `VALUES`. Meaning: design
specs are committed under `docs/specs/` as under `commit`; briefs, handoffs and
implementation plans are mindful thoughts referenced by `mindful:thought:<hex>`. The
session line reads `design docs: mindful (specs in docs/specs; briefs, handoffs, plans in
mindful)`. `profiles.toml` sets personal to `mindful`; work and external keep `exclude`,
since the corpus is the user's personal one and work documents do not belong in it.
`repository_layer` keeps its single upgrade to `commit`: a repository that documents
`docs/superpowers/…` or sets `ops.designDocs commit` opts back into committed plans, and
nothing in a repository can select `mindful`.

`audit()` lists excluded design docs only under `exclude`; under `mindful` it also lists
plans and briefs in the tree, so the user sees new in-tree documents that bypassed the
hook (an editor, a `git add` outside the harness).

The staging hook, check 4: under `mindful`, a **new** (untracked) file matching
`docs/plans/*.md`, `docs/superpowers/plans/*.md`, or `docs/notes/*-brief.md` and
`docs/notes/*-handoff.md` is refused with "refusing to put a new plan or brief in the
tree: this profile keeps them in mindful (mindful-op --capture-paste --as-agent …); specs
stay under docs/specs/". A change to a document git already tracks passes: the ~300
plans and 73 briefs in the tree stay where they are (§1), an active plan is revised and
committed in place for the rest of its life, and nothing is ever required to migrate. A
rename of a tracked plan is a change to a tracked path and passes too. Specs under
`docs/specs/` and `docs/superpowers/specs/` pass. Under `commit` and `exclude` the check
is unchanged.

Constraint, stated for the record: flow-trial-1 (2026-10-05 to 2027-01-10) measures tasks
whose plans so far were repository files. The user chose to start now (brief §5); the
trial's analysis notes the date plans moved (§9 records it on the trial task).

## 8. Skills and instructions

Each change is a line or two of wording; the skills live in their owning repositories.

- **lore** `profiles/personal.md`: specs are committed under `docs/specs/`; briefs,
  handoffs and plans are mindful thoughts written through `mindful-op`, referenced as
  `mindful:thought:<hex>`; the `docs/superpowers/` default is never right here.
  `instructions/fragments/design-docs.md`: "whether design specs are committed, and where
  plans and briefs live, is the profile's call".
- **tasks** `skills/tasks/SKILL.md` "With superpowers": writing-plans attaches with
  `--plan mindful:thought:<hex>` under `design_docs: mindful`; `--step` is checked against
  the fetched plan; `tasks check` reports `doc_unreachable` on a host without the scheme.
  `skills/scope/SKILL.md` §4: the handoff brief is captured as a thought under
  `design_docs: mindful` (`mindful-op --capture-paste --as-agent … --tag agent-docs --tag
  brief`), the goal's `--source` is the reference, and `brief: <reference>` goes in the
  audit note; the existing-brief search becomes `mindful search '#agent-docs #brief
  <prefix>'` beside the `docs/notes/` glob. The read step keeps its prefix strip.
  `skills/curate/SKILL.md`: a fixable link may be a reference. The "With superpowers"
  lines for executing-plans and subagent-driven-development: run `plan-snapshot <id>`
  first and hand its output to the helpers as the plan file (§6.4).
- **flows** `skills/flow/SKILL.md`: `gate: planned <path or reference>`; the dispatch
  brief carries "the contract or its path or reference"; the implementing gate's
  worktree step runs `plan-snapshot <id>` before any execution helper. `bin/flow-state`'s
  fingerprint exclusion is unchanged (a plan in mindful is not in the tree, and
  `.superpowers/` is ignored).
- **ops** `skills/quick-add/SKILL.md`: unchanged; its captures are the human's, via the
  agent.
- The vendored writing-plans, brainstorming, executing-plans and
  subagent-driven-development skills and their scripts are unchanged: the location
  clause is satisfied by the profile text, and the helpers receive the snapshot path as
  `PLAN_FILE`.

## 9. Rollout and pieces

Order matters: a record with an external link must not be written before every host's
`tasks` binary parses it, and the first plan must not go to mindful before the fetch and
the write path exist.

1. **tasks** (piece, planned there: the resolver is a design decision in that project's
   terms): §4 in full, `tasks doc`, with the tests of §4.6. Install the binary on both
   hosts.
2. **ops** (piece, direct): `mindful-doc`; `plan-snapshot`; `mindful-op` `edit`,
   `--as-agent`, `--body-file`, `--edit --etag`; `ops-profile` `mindful` and the session
   line; the hook's new-plan/brief classes and refusal text; `audit()`; tests in
   `tests/test_ops_profile.py`, `tests/test_pretooluse.py`, `tests/test_mindful_op.py`
   and one for `plan-snapshot`. The host config line
   `[docs.schemes] mindful = "mindful-doc"` on both hosts, by the dotfiles that own
   `~/.config/tasks/config.toml` (a dots piece if that file is managed there; otherwise an
   ops rollout step).
3. **mind6** (piece, direct): `edit --body-file <path|->`, mirroring `add`.
4. **obs** (piece, direct): §5.1, §5.2, §5.4.
5. **lore, tasks skills, flows** (one piece each, direct): §8 wording. The tag thoughts
   `agent-docs`, `brief`, `plan`, `handoff` are created once by the user in the live
   corpus (a rollout step on the ops piece, run by hand and noted there).
6. **Switch**: `profiles.toml` personal → `mindful` lands last, in the ops piece's final
   commit, after 1–5 are installed on both hosts. A note on the flow-trial-1 task records
   the date.

A parent must be in the task's own project (tasks `src/hierarchy.rs` `validate_parent`),
so the pieces are not children of this task. Each is filed in its owning project
(`tasks add … --project <prefix>`, with `--source` naming this spec) and this task
depends on each (`tasks dep hq-5a3e12 --on <piece>`), the tasks skill's shape for work
spanning projects. This task returns to `ready` when the last piece closes and is closed
after the acceptance of §10 is observed.

## 10. Acceptance

- A plan captured with `mindful-op --capture-paste --as-agent claude-code@<model>
  --body-file <plan.md> --tag agent-docs --tag plan` while the web app runs returns a
  `thought:<hex>`; `tasks edit <id> --plan mindful:thought:<hex> --step "Task 1: …"`
  succeeds; `tasks check` is clean; `tasks show <id>` prints the reference.
- On the second host, with the binary installed but no `[docs.schemes]`, `tasks check`
  warns `doc_unreachable` for that task and every other command reads the record.
- `tasks check` reports `step_missing` after the plan's heading is renamed through
  `mindful-op --edit --etag <etag from the get>`, and is clean after the child's `--step`
  is updated. The same edit sent again with the old etag is refused with
  `VERSION_CONFLICT`, and `mindful-op` reports it without writing.
- `plan-snapshot <id>` writes `.superpowers/sdd/plans/<hex>.md`, `git status` does not
  show it, `sdd-workspace` and `task-brief` run against it and `task-brief … 1` extracts
  Task 1; after a revision through `mindful-op --edit`, a second `plan-snapshot` call
  overwrites it and the workspace resolved by `sdd-workspace` is the same directory.
- obs: the task's plan rounds carry reason `external_doc`; a `review: plan round 1 …`
  note that cites the reference is placed as a plan round; a session that ran `mindful
  --json show` is cleared.
- The hook refuses `git add docs/plans/x.md` in a personal checkout and allows
  `docs/specs/x-design.md`; `ops-profile session` prints the new line.

## 11. Ideas filed, not built

- mind6: the CLI forwards a write to the running web app when the data directory is
  locked by a web process on this host (§6.3).
- obs: mindful writes as an authorship signal for plan rounds (§5.3).
- mind6: a kind-only authorship filter (`--by agent:*`) for listing every agent's
  documents at once.
