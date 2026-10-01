# Project profiles: composable instruction and behavior layers per checkout

Status: approved — user review 2026-09-19 after two revision rounds
Task: ai-45ac4c
Related: ai-699ae6 (the prose correction this follows), ai-ec379d (fragment
assembly; neither task depends on the other), ops `hooks/claude-pretooluse`
(the guard this realigns), ops `docs/specs/2026-09-07-project-identity-design.md`
(the registry + identity model this extends).

## 1. Purpose

The global instructions serve every session in every checkout, so every
difference between kinds of project has been written as a conditional inside
one file — "personal projects commit design docs; work and external projects
exclude them", "`<work-account>` only under `~/d/<work>/`" — and enforced by a
hook that re-derives the same classification from paths and directory names.
The 2026-09-19 review found the design-doc rule had drifted to a universal
default (ai-889237) with no personal-project justification, and that fixing the
prose (ai-699ae6) left the hook stating the old rule. The two guards that work,
prose and hook, disagreed because neither read a declared classification.

This design gives a checkout a declared **profile**: a named layer that carries
the instructions and the few typed settings that differ between kinds of
project. A session's effective configuration is an ordered composition of
layers — core, the checkout's profiles, the repository's own instructions, the
user's words in the session — and one resolver answers, for hooks, harnesses,
and people, which profile applies and where each setting came from.

Profiles are user-defined and any number may apply. `personal`, `work`, and
`external` are the three shipped as examples because they are the three the
record demonstrates; a fourth, custom one is worked through in §8.

## 2. Boundaries

| Owner | Has | Does not have |
| --- | --- | --- |
| ops | `profiles.toml` (definitions, path families); the `profiles` field in `identity.toml`; `bin/ops-profile` (resolve, explain, check, audit); the hooks that read it; `ops-check` validation | Instruction text |
| ai | `agents/profiles/<name>.md` fragments; the global `AGENTS.md` prose that names profiles; hook registration in every tracked harness settings file | Resolution logic |
| tasks | The registry: which projects exist and where (unchanged) | Anything about profiles |
| relay | Future: SessionStart context dispatch to Codex/opencode once relay exposes it (its v1 deliberately does not) | v1 delivery |

The interface between ops and ai is two files ops reads by name through the
tasks registry (the ai root), the same way `ops-projects` finds `AGENTS.md`:
`agents/profiles/<name>.md` for each profile named in `profiles.toml`.

## 3. The model

### 3.1 Layers

A session's effective configuration is these layers, in this order; later
layers take precedence over earlier ones:

1. **core** — the global `AGENTS.md` (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`).
   Rules true of every session.
2. **profiles** — the checkout's declared profiles, in declared order. Each
   contributes an instruction fragment and may set typed keys (§3.3).
3. **repository** — the checkout's own `AGENTS.md`/`CLAUDE.md`, and its per-clone
   git config (`ops.designDocs`, `agent.profile`). The harness already reads the
   instruction files after the global one; this design does not move them.
4. **session** — what the user says in the conversation. Never encoded; always wins.

Prose composes by concatenation in layer order: a later layer's text is read
after an earlier one's and, by the ordering stated in the session line (§5),
overrides it where they disagree. Prose is never merged or diffed.

Typed keys compose by ownership, not by overlay: within the profile layer, a
key is set by **at most one** selected profile, and two selected profiles that
both set a key are a check error (§6), not a last-wins resolution. A repository
layer setting overrides a profile's; the session overrides everything. This is
composition over inheritance: profiles do not extend one another, and a
project selects the set it wants rather than a point on a hierarchy.

### 3.2 Profiles

A profile is a table in ops `profiles.toml`:

```toml
# Each profile: the fragment ai ships for it, the typed keys it sets, and the
# harness home it expects. Keys a profile does not set are left to another
# selected profile or to the core default.

[profile.personal]
fragment = "personal"          # ai agents/profiles/personal.md
home = "personal"
design_docs = "commit"
gh_account = "khughitt"
pr_draft = "by-permission"

[profile.work]
fragment = "work"
home = "work"
design_docs = "exclude"
gh_account = "<work-account>"
pr_draft = "by-permission"

[profile.external]
fragment = "external"
home = "personal"
design_docs = "exclude"
gh_account = "khughitt"
pr_draft = "required"

# A custom profile that adds instructions and sets no keys (§8.4).
[profile.science]
fragment = "science"

# Path families: an unregistered checkout under one of these resolves to the
# named profiles. Matched by real path, longest prefix first.
[[family]]
path = "~/d/<work>"
profiles = ["work"]

# Every checkout nothing else claims.
[default]
profiles = ["external"]
```

`fragment` names a file `agents/profiles/<fragment>.md` in the ai checkout. A
profile with no `fragment` contributes only keys. Every key is optional;
`ops-profile check` requires that after composition every key has a value for
every registered project (the core supplies no defaults — a project whose
selected profiles leave `design_docs` unset is a check error, because "unset"
is exactly the silent fallback that produced ai-889237).

`home` is advisory (§3.4). Profile names are lowercase identifiers; `core`,
`repository`, and `session` are reserved.

### 3.3 Typed keys (v1)

Only differences the record demonstrates get a key. Each key names the
consumer that acts on it.

| Key | Values | Consumer | Today's mechanism it replaces |
| --- | --- | --- | --- |
| `design_docs` | `commit`, `exclude` | pretooluse check 4; brainstorming/writing-plans prose | the `docs/superpowers/` directory rule + universal default |
| `gh_account` | a gh login | pretooluse check 1; the gh rule in `AGENTS.md`; Codex `developer_instructions` | the `~/d/<work>` path constant in the hook |
| `pr_draft` | `required`, `by-permission` | pretooluse check 2 | `by-permission` for everyone (live `gh repo view`) |
| `home` | a home name (§3.4) | the session line (advisory) | nothing |

`pr_draft = "by-permission"` keeps today's behavior: draft when the active
account's permission on the target is below WRITE. `required` means draft
regardless, which is what `external` wants: an owned fork of an upstream
project still opens drafts upstream, and the permission query is not needed to
know that.

Skills, plugins, model, and per-home settings are **not** keys in v1: they are
properties of a harness home, hand-maintained in `claude/settings*.json` and
`codex/config*.toml` as today. §10 records the reason and what would change it.

### 3.4 Harness homes

A session runs in a harness home: `~/.claude` or `~/.claude-work`
(`CLAUDE_CONFIG_DIR`), `~/.codex` or `~/.codex-work` (`CODEX_HOME`). The home
is a **session** fact chosen at launch, not a project fact, and this design
leaves that so: the profile resolves from the checkout regardless of home, so a
work checkout opened in the personal home still gets the work profile's
instructions and keys.

`profiles.toml` names the homes so the session line can report a mismatch:

```toml
[home.personal]
claude = "~/.claude"
codex = "~/.codex"

[home.work]
claude = "~/.claude-work"
codex = "~/.codex-work"
```

The resolver reports the current home by matching the running home against
these. From a hook, the payload's `transcript_path` names it: Claude writes the
transcript under `CLAUDE_CONFIG_DIR/projects/`, Codex under
`CODEX_HOME/sessions/`, and a Codex SessionStart hook's environment carries
nothing of its own (a Codex launched inside a Claude session even inherits
`CLAUDECODE=1`), so the environment is only the fallback. Without a payload
(`ops-profile session`), `CLAUDE_CONFIG_DIR` / `CODEX_HOME` decide (unset means
the personal default). A home a profile expects that differs from the one
running is a warning in the session line, never a block. A session with no
matching home reports `home: unknown`.

## 4. Selection and resolution

`ops-profile resolve [PATH]` (default: cwd) answers with the profile list and
its source. Steps, first match wins:

1. **Checkout**: `git rev-parse --git-common-dir` from PATH; the checkout is the
   parent of the common git dir, so a linked worktree resolves to its main
   checkout, as `expected_account` in the hook already does. Both sides are
   compared as real paths (`Path.resolve()`), so a symlinked `.worktrees/` on
   `WORK_ROOT` and a registry root written under `~/d` (itself a symlink)
   match. Outside any git checkout, PATH itself is the checkout. The canonical
   checkout answers only *classification* (steps 2–5); the repository layer —
   instruction files, and the docs they name — is read from the working tree
   PATH sits in (`git rev-parse --show-toplevel`), which for a linked worktree
   is the worktree, so a branch that changes its `AGENTS.md` is read as that
   branch has it.
2. **Per-clone override**: `git config --get agent.profile` in that checkout, a
   comma-separated list (`personal` or `personal,science`). Source:
   `git config agent.profile`. This is the escape hatch for a fork, an owned
   public repository cloned outside the registry, a temp-dir clone, or a
   registered project the user wants treated differently in one clone.
3. **Registry**: the checkout equals a registered root → that project's
   `profiles` in `identity.toml`. Source: `identity.toml [<prefix>].profiles`.
4. **Path family**: the checkout is under a `[[family]]` path (longest prefix
   wins). Source: `profiles.toml family <path>`.
5. **Default**: `[default].profiles`. Source: `profiles.toml default`.

The default is `external` and the design keeps it that way: a repository being
outside the work tree, or under `~/d`, does not establish that it is personal.
A personal project earns `personal` by being registered (and declared) or by a
family the user writes. Registered projects **must** declare `profiles`;
`ops-projects check` (hence `ops-check`, hence the ops pre-commit hook) fails
on a registered project without it, the same way it fails on one without an
identity table. Inference from paths, remotes, or `gh` is never used for a
registered project.

Resolution never queries the network. `gh repo view` remains inside pretooluse
check 2 only, for `pr_draft = "by-permission"`.

Provenance is carried per fact. Resolution output (`--json`):

```json
{
  "checkout": "~/d/ai",
  "path": "$WORK_ROOT/ai/.worktrees/project-profiles",
  "worktree": true,
  "project": "ai",
  "profiles": [{"name": "personal", "source": "identity.toml [ai].profiles"}],
  "home": {"name": "personal", "source": "CLAUDE_CONFIG_DIR unset"},
  "keys": {
    "design_docs": {"value": "commit", "source": "profile personal"},
    "gh_account": {"value": "khughitt", "source": "profile personal"},
    "pr_draft": {"value": "by-permission", "source": "profile personal"}
  },
  "fragments": ["~/d/ai/agents/profiles/personal.md"],
  "warnings": []
}
```

A repository-layer key override appears with its own source (`git config
ops.designDocs`, or `AGENTS.md names docs/superpowers/specs`); the hook keeps
reading those two opt-ins because they are the repository layer, and the
resolver reports them so `explain` and the hook agree. The instruction-file
opt-in is also read from `docs/AGENTS.md` and `docs/CLAUDE.md`, where the
directory is named relative to `docs/` (`docs/AGENTS.md names
superpowers/{plans,specs}`); a bare `superpowers/` does not count there either
(ops-36646d).

## 5. Delivery: the session line and the fragment

`ops-profile session [PATH]` prints, for injection into the session's context:

```
profile: personal (identity.toml [ai].profiles); home: personal; design docs: commit; gh: khughitt; PRs: by-permission — later layers win: core < profile < this repository's instructions < you. `ops-profile explain` shows every source.

<contents of agents/profiles/personal.md>
```

One line of facts, then the fragment text, in declared profile order when
several apply. A warning (home mismatch, a fragment file missing) is appended
as one more line prefixed `warning:`. `session` is the one command whose
output is the complete profile layer — line plus every fragment — and it is
what both the hook and an agent without a line run; `explain` (§4) prints the
provenance table and no fragment text, for a person or an agent asking *why*.

Inside the hook a resolver failure prints one line, `profile: unresolved —
<error>; run ops-profile session after fixing it`, and exits 0: a session
that starts without a profile layer is recoverable and a session that fails
to start is not. Run by hand, `session` exits 1 on the same failure.

**Claude Code**: a new ops hook, `hooks/claude-profile`, registered for
`SessionStart` (`startup|resume`) in `claude/settings.json` **and**
`claude/settings.work.json`. Its stdout is added to context, which is the
mechanism `claude-sessionstart` uses today. It also appends
`export AGENT_PROFILE=<names>` to `CLAUDE_ENV_FILE`, as `claude-provenance`
does for `TASKS_MODEL`, so a later command or hook can read it without
re-resolving — a cache, not the authority; hooks that block still call the
resolver.

The guard must run wherever the line is promised. `claude/settings.work.json`
registers only Familiar's `PreToolUse` today, so the work home has none of
the ops checks; it gains `hooks/claude-pretooluse` on `Bash` alongside the
profile hook, and the live check in §13 starts a session in each home and
confirms both hooks fired. Whether the work home also takes
`claude-sessionstart`, `claude-provenance`, and `claude-posttooluse` is a
separate decision this design does not make.

**Codex**: `~/.codex/hooks.json` carries a `SessionStart` entry today, but
whether Codex adds hook stdout to the model's context is unverified here and
relay's design marks SessionStart context as deliberately unexposed in its v1.
The implementation plan carries a probe (the pattern of `ops-c8e4d1`): if Codex
injects, register the same hook; if not, Codex sessions rely on the core prose
(§7) and run `ops-profile session` themselves before any task work. Either way the hooks that block
(pretooluse) are Claude Code native; Codex enforcement arrives with relay's
guard dispatch and is out of scope here.

**Fragments**: `agents/profiles/<name>.md` in ai, plain markdown, one file per
profile, no frontmatter, no includes. They hold what the profile *differs* on:

- `personal.md`: design specs and plans are committed under the repository's
  documented convention (`docs/specs/`, `docs/plans/`, or what its instructions
  name); PRs to the user's own repositories need no draft; `khughitt`.
- `work.md`: specs and plans stay out of the tree unless the repository asks
  for them (`.git/info/exclude`, copy out before removing a worktree);
  `<work-account>`; the checkout's guidelines decide the rest.
- `external.md`: read the contributor guidelines first; every PR is a draft;
  attribution only where the guidelines ask; specs and plans stay excluded;
  search open and closed PRs and issues before starting; `khughitt`.

Each fragment is short (the personal one is three or four sentences). The
rules they carry are moved out of the global `AGENTS.md`, not duplicated
(§7). When ai-ec379d lands, these files become its render targets: a profile
fragment is a fragment with a `fragment` root, and provenance metadata arrives
with the assembler. Nothing in this design blocks on that, and nothing in it
needs changing for it beyond the files gaining frontmatter.

## 6. Checks

`ops-profile check` runs inside `ops-projects check` (so in `ops-check`, the
pre-commit hook, and the SessionStart staleness notice):

- every registered project declares `profiles`, each naming a defined profile;
- no two selected profiles of any registered project set the same key;
- after composition every registered project has a value for every key;
- every `fragment` names an existing file in the ai checkout (environmental
  note, not a failure, when ai is not registered on this machine — the
  `elsewhere` convention);
- `[[family]]` paths are absolute after `~` expansion and `[default].profiles`
  is non-empty;
- `identity.toml` tables accept `profiles` (the `FIELDS` tuple in
  `ops-projects` grows by one); unknown fields still fail.

`ops-profile check` says nothing about unregistered checkouts: their profile is
a runtime resolution, and `explain` is how a person inspects one.

## 7. The hooks and the prose

### 7.1 pretooluse

Check 1 (`gh` account): `expected_account(cwd)` becomes the resolver's
`gh_account`. The refusal names the profile and its source: "cwd resolves to
profile `work` (identity.toml [rad].profiles), whose gh account is
`<work-account>`". The `WORK_ACCOUNT` constant and the `~/d/<work>` test leave
the hook; the family in `profiles.toml` carries that fact once.

Check 2 (draft PRs): runs `gh repo view` only when `pr_draft` is
`by-permission`; `required` refuses a non-draft `gh pr create` without the
network call, naming the profile.

Check 4 (design docs): the trigger stays what it is — a stage or commit that
would carry a path under `docs/superpowers/` — and the decision becomes the
following. A deletion, or a move out of the directory, is not carrying a doc
and always passes, so a shipped plan can be dropped (ops-bcb318).

- `design_docs = commit` (profile or repository layer): allow.
- `design_docs = exclude` and no repository-layer opt-in: refuse. The refusal
  states the profile and source ("profile `external` (profiles.toml default)")
  and the three ways to change it, in precedence order: name the directory in
  the checkout's instruction file, `git config ops.designDocs commit`, or
  `git config agent.profile personal` when the classification itself is wrong.

The refusal no longer states a universal default. The existing pointers at the
checkout's convention (`docs/specs/` named in its instructions; docs already
tracked under `docs/superpowers/`) stay, because they are still the most useful
thing to say to an agent who reached for the wrong directory in a repository
that has a right one. Where the tree already tracks docs under `docs/superpowers/` and its
instructions name no other directory, the refusal drops the harness-convention
claim and leads with `git config ops.designDocs commit`: the repository may be
shared, and its instructions not ours to edit (ops-36646d).

Resolver failure inside the hook (no ops checkout, a malformed
`profiles.toml`, an undeclared registered project): there is no conservative
substitute identity — treating a work checkout as `external` would refuse
`<work-account>` and wave `khughitt` writes through — so the hook substitutes
nothing. A resolution failure is itself the positive finding: a `gh` write, a
non-draft `gh pr create`, or a design-doc stage is refused with the resolver's
error and the fix (`profiles.toml`, the identity table, or `git config
agent.profile` in this clone), and never with an account or a profile the hook
guessed. Commands the three checks do not guard are unaffected. The block is
logged with kind `unresolved`. Check 3 (attribution) does not read the
resolver and is unchanged.

The hook classifies through the canonical checkout (§4 step 1) but reads the
repository layer from the working tree it is acting on: the `AGENTS.md` /
`CLAUDE.md` at the top level of the worktree cwd sits in, as today's
`design_docs_wanted` does. Git config is shared by every worktree of a
checkout, so `ops.designDocs` and `agent.profile` read the same from either.

### 7.2 The global prose

`AGENTS.md` loses the profile-specific sentences and gains one short section:

> ## Profiles
>
> Every checkout has a profile — `personal`, `work`, `external`, or one the user
> defined — that carries the instructions and settings that differ between
> kinds of project. Your session starts with a `profile:` line followed by the
> profile's instructions; if it did not, run `ops-profile session` and read
> its output before any other work — the profile says what to read and do
> before touching a repository. Later layers win: core, then the profile, then
> this repository's own instructions, then the user in the session.

"Before any other work" is the rule, not "before a write": the external
fragment's first instruction is to read the contributor guidelines and search
existing PRs and issues, which is worthless after an hour of edits.

The Git bullet keeps "no AI attribution by default" and the two-account fact
moves into the fragments and the resolver; the guideline-reading and draft
requirement moves into `external.md`; the Design & Plan Docs bullet keeps
"verify document status against the code" and drops the per-kind default
(profiles say it). Codex `developer_instructions` in `codex/config.toml`, which
repeats the account rule, is emptied. Net effect on the shared file: fewer
words than ai-699ae6 left it, and no conditional sentence whose condition is
"which kind of project this is".

## 8. Worked examples

Each example gives the declaration, the resolution, the session line, and what
the hook does on `git add docs/superpowers/specs/x.md` and on a `gh pr create`.

### 8.1 `ai` — personal, in a linked worktree

`identity.toml`: `[ai] profiles = ["personal"]`. cwd
`$WORK_ROOT/ai/.worktrees/project-profiles`. Step 1 finds the common git
dir under `~/d/ai`; step 3 matches the registry.
Line: `profile: personal (identity.toml [ai].profiles); home: personal; design docs: commit; gh: khughitt; PRs: by-permission`.
Hook: the stage is allowed; the PR is judged by permission (`khughitt` has
ADMIN on `khughitt/ai`: no draft needed). The repository's own convention is
`docs/specs/`, so the agent writes there anyway; the hook's convention pointer
would say so if it did reach for `docs/superpowers/`.

### 8.2 `rad` — work, registered under the work tree

`identity.toml`: `[rad] profiles = ["work"]`. Registered, so step 3 answers
before the family would. Launched with `clw` (home `work`).
Line: `profile: work (identity.toml [rad].profiles); home: work; design docs: exclude; gh: <work-account>; PRs: by-permission`.
Hook: the stage is refused, naming profile `work` and the repository-layer
opt-ins; a `gh` write under `khughitt` is refused with the switch command; a PR
is judged by permission. Opened in the personal home instead, the line ends
`warning: profile work expects home work; running in personal` and everything
else is the same.

### 8.3 A temp-dir clone of an upstream project — external by default

`/tmp/opencode-pr-48990`: unregistered, under no family. Step 5.
Line: `profile: external (profiles.toml default); home: personal; design docs: exclude; gh: khughitt; PRs: required`.
Hook: the stage is refused as an external checkout; `gh pr create` without
`--draft` is refused without a network call; the external fragment told the
agent to read CONTRIBUTING and search existing PRs before it got here.

### 8.4 `ns` — personal plus a custom profile, and one overridden clone

`identity.toml`: `[ns] profiles = ["personal", "science"]`. `science` sets no
keys and ships a fragment about notebooks, data provenance, and figure
directories; declared second, its text follows `personal.md`. Keys resolve
from `personal` alone, so there is no conflict to report.
Line: `profile: personal, science (identity.toml [ns].profiles); …design docs: commit…`.

The user has a second clone of `ns` at `~/scratch/ns-review` for reviewing a
collaborator's fork, and ran `git config agent.profile external` there. Step 2
answers first: `profile: external (git config agent.profile)`, design docs
excluded, PRs drafts. `ops-profile explain` in that clone shows the override
and, below it, what the registry would have said had the override been absent.

### 8.5 An unregistered work repository

`~/d/<work>/<unregistered-repo>`: not in the registry; the `~/d/<work>` family claims it
(step 4). `profile: work (profiles.toml family ~/d/<work>)`. This is today's
hook behavior, now with a stated source.

## 9. Migration

Ordered so that every commit passes its own gate on this machine (where ai
and ops are both registered, so `ops-check` validates fragments as soon as
validation exists) and so that a global rule is removed only after the layer
that replaces it is being delivered.

1. **ai**: the three fragments under `agents/profiles/`, merged to `main` —
   `ops-check` reads ai through its registered root, not a worktree. Nothing
   reads them yet; the commit changes no behavior.
2. **ops**: `profiles.toml` with the three profiles, the `~/d/<work>` family,
   the homes, and the `external` default; `profiles` on every identity table
   (`nrp`, `rad` → `work`; every other registered project → `personal`);
   `bin/ops-profile`; `ops-projects check` extended; tests. The fragment
   check passes because step 1 landed first; `hooks/claude-profile` lands here
   too, unregistered. Merged to ops `main` before step 3, since the settings
   files name `~/d/ops/hooks/`.
3. **ai**: `hooks/claude-profile` and `hooks/claude-pretooluse` registered in
   both Claude settings files (§5); the `## Profiles` section added to
   `AGENTS.md` with the old sentences still in place. The symlinks in the four
   homes (§11) make this live at the next session start once merged to ai
   `main`; the §13 live check runs after that merge, in both homes.
4. **ops**: pretooluse checks 1, 2, 4 read the resolver; refusal text updated;
   the scratch-repo checks from ai-341dcc rerun (a `docs/superpowers` stage is
   still blocked in an unregistered scratch repo, now naming `external`; it is
   allowed in a scratch repo with `git config agent.profile personal`; an
   unresolvable clone refuses with the error, naming no account). Merged to
   ops `main` before its scratch-repo checks, which run the installed hook.
5. **ai**: the prose removals in `AGENTS.md` (§7.2) and `developer_instructions`
   emptied in `codex/config.toml` — only now, with delivery and enforcement
   both verified.
6. **Excluded docs in personal checkouts**: `ops-profile audit [PATH]` lists,
   for a checkout whose `design_docs` is `commit`, the entries in
   `.git/info/exclude` that match spec and plan paths (`docs/specs/`,
   `docs/plans/`, `docs/superpowers/`, and any directory the checkout's
   instructions name), with the `git add` line for each, and prints nothing
   for a checkout whose profile excludes. It never writes: the user runs the
   adds per checkout, one commit each, after reading the doc. Today's
   inventory is `ai` (four: the flow-state-machine and session-logs specs and
   plans) and `wali` (two). Every other exclude entry — `.codex/config.toml`
   (Familiar's per-project pet), `.worktrees`, `.cargo/config.toml`, the
   mindful `.claude/*` state, a work repository's docs — is not a spec or plan and is
   not listed. Work and external exclusions are untouched by construction.
7. **Codex probe** for SessionStart context (§5), then registration or not.

Historical `attribution-blocks.log` entries keep their old `kind` and reasons;
the log gains a `profile` field on new lines. Nothing rewrites the past.

## 10. Out of scope, and why

- **Per-profile harness settings, plugins, skills, models.** These are per
  home and hand-maintained (`settings.work.json`, `config.work.toml`,
  `~/.claude-work/skills`). Two homes exist; the only recorded failure is
  drift between the tracked variant and the installed copy, which `host-drift`
  already models for system files. A profile that needed a *third* home, or a
  key that needed to change a harness setting at session time, would reopen
  this. Until then a settings overlay renderer is a system without a user.
- **Enforcement in Codex, opencode, Crush.** Relay's guard dispatch owns that.
- **Per-profile hook sets.** Every hook runs everywhere and reads the profile.
- **Classification by remote or by `gh`.** Declared or defaulted, never inferred.
- **Session-layer encoding.** The user's words are read by the model; no key
  records them.

## 11. How the homes are wired

Nothing installs: each harness home links to the tracked file.

| Installed | Links to |
| --- | --- |
| `~/.claude/CLAUDE.md`, `~/.claude-work/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.codex-work/AGENTS.md` | ai `AGENTS.md` |
| `~/.claude/settings.json` | ai `claude/settings.json` |
| `~/.claude-work/settings.json` | ai `claude/settings.work.json` |
| `~/.codex/config.toml` | ai `codex/config.toml` |
| `~/.codex-work/config.toml` | ai `codex/config.work.toml` |

The links target the main checkout, so a change to `AGENTS.md` or a settings
file is live in every home at the next session start once it is on ai `main`
— and not while it sits on a worktree branch. The same holds for ops: the
hooks registered in the settings files are `~/d/ops/hooks/*`, the main
checkout, so a hook change is live only once merged there. That is why
migration steps 3 and 5 are separate commits, why each live check follows an
integration to `main` in the repository it exercises, and why step 3 runs the
live check before step 5 removes anything. The ai README's "links to" is accurate; this design adds no
installer.

## 12. Open question

**Profile order in `identity.toml` for projects with several.** The spec says
declared order is fragment order. Whether a project wants its custom profile's
text before or after `personal.md` is a per-project choice; the examples put
the kind first and the flavor second.

## 13. Testing

- **ops** `tests/test_ops_profile.py`: resolution in a temp registry +
  identity + profiles fixture — worktree to main checkout, symlinked roots,
  override, family longest-prefix, default; key conflict, missing key, missing
  fragment, unknown profile name; `session` output shape, warning on home
  mismatch; on resolver failure the one-line `profile: unresolved — <error>`
  diagnostic with exit 0 under the hook and exit 1 from the CLI; `audit`
  listing only spec/plan patterns and
  never writing.
- **ops** `tests/test_pretooluse.py`: the three checks against a stubbed
  resolver — allow under `commit`, refuse under `exclude` naming the source,
  repository opt-in beating profile `exclude`, `required` refusing without the
  network stub being called, `by-permission` calling it, the `unresolved`
  refusal, naming no account, when the resolver raises.
- **ops** `tests/test_ops_projects.py`: `profiles` accepted, missing `profiles`
  a failure, unknown field still a failure.
- **ai**: the fragments have no test; `AGENTS.md` word count before and after
  is recorded in the closing note, as ai-341dcc did.
- **Live**: the ai-341dcc scratch-repo checks (§9 step 4); one real session
  start in a personal, a work, and an external checkout, reading the line; and
  in the work home specifically, a session start that shows the line and a
  `gh` write under the wrong account that is refused, proving both hooks run
  there.
