# Adding an agent harness

Integrating a coding-agent harness spans `hq` (home routing, live-state hygiene,
capability facts, session discovery, transcript archiving) and the consumer
repositories that enumerate harnesses (`lore`, `ops`, `relay`, `tasks`, `obs`, and
`familiar` when its observer is wanted). Cross-repository paths below use
`<hq-checkout>`, `<lore-checkout>`, `<ops-checkout>`, `<relay-checkout>`,
`<tasks-checkout>`, `<obs-checkout>` and `<fam-checkout>` so examples carry no host
layout; paths without a checkout prefix are relative to `<hq-checkout>`.

No list in this document can name every harness enumeration and stay accurate.
Discovery (section 1) finds them; the rest of the runbook covers what a search cannot
show: which copy is the source, how a change is distributed, which readers must change
together, which guards a harness needs, and the order in which changes take effect.

## 0. Choose the layers

Onboarding is incremental. Before editing anything, write a short layer list on the
onboarding task, with each layer marked **selected**, **deferred** or **unsupported**,
and for each selected layer the evidence that will pass it:

| Layer | Section | Passing evidence when selected |
| --- | --- | --- |
| Home routing, global instructions, skills | 2 | `just link-check` converged; a fresh session shows the global instructions and lists the skills |
| Live-state hygiene | 3 | a model/effort change survives a checkout, the home link still resolves after the harness saves, `git status` stays clean |
| Capability facts | 4 | `tools/harness-facts check` passes; each fact a consumer gates on is probed or explicitly `unknown` |
| Profile at session start | 5 | a personal and a work session each print the right `profile:` line |
| Command guard (PreToolUse) | 5 | an allowed command runs, a refused fixture command never executes, a malformed command input is refused |
| Turn-boundary claim guard (Stop) | 5 | a turn ending with a live claim is held once, then released |
| Relay observation, ancestry, provenance | 6 | two concurrent sessions resolve to distinct identities; stamped notes join in `obs index` |
| Familiar observer | 6 | familiar renders the new harness's events without errors |
| Session discovery and resume | 7 | `hq sessions` lists and `-i` resumes a session |
| Transcript capture | 7 | `session-archive capture` copies the store; pruning stays off (separately gated) |
| `obs` adapter | 7 | `obs index` over the real store completes |

Leave a layer deferred rather than wiring it halfway: a half-wired guard looks
installed while it protects nothing.

The existing harnesses are current examples, not certifications; each has known
limits:

- `opencode`: home routing, a relay server-plugin bridge, tasks process detection,
  facts, and session-logs documentation. No relay guard (relay refuses guard
  subscribers for it).
- `pi`, `pi-durable`: a pinned runtime and launcher, live-state hygiene through an
  in-process extension, and probes.
- `agy`: split homes, a skills manifest, workspace trust and anchored atomic-save
  settings adoption in `live-picks` and `links.toml` (3.1), relay dispatch on
  `SessionStart`, `PreToolUse` and `Stop` (`ops-guard` and `familiar-agy`), and a
  local adapter hook (`agy/hook`) for detached `settings.json` healing, `SessionStart`
  `injectSteps` wrapping and a one-shot `Stop` claim check until native `claim-guard`
  and `SessionStart` support land (ops-33cef9, hq-c59809).
- `claude-code`, `codex`: every layer, through relay.

## 1. Discover every enumeration

Search each repository for the existing harness names, not for a list someone wrote
down. Use the canonical slugs, the short keys, and the environment markers:

```sh
for repo in <hq-checkout> <lore-checkout> <ops-checkout> <relay-checkout> \
            <tasks-checkout> <obs-checkout> <fam-checkout>; do
  git -C "$repo" grep -n -I -E \
    "claude-code|opencode|\"claude\"|'claude'|\"codex\"|'codex'|CLAUDECODE|CODEX_(CI|THREAD_ID|SESSION_ID)|CLAUDE_CODE_SESSION_ID" \
    -- ':!tasks/' ':!docs/specs/' ':!docs/plans/'
  # bare TOML keys and path-shaped constants the first pattern misses
  git -C "$repo" grep -n -I -E \
    '(^|[^a-z-])(claude|codex)[[:space:]]*=|\[harness\.|"(claude|codex)/' \
    -- ':!tasks/' ':!docs/specs/' ':!docs/plans/'
done
```

The second pattern catches what the first cannot without a quote or the full slug: bare
TOML keys (`claude = "~/.claude"` in `<ops-checkout>/profiles.toml`, `[harness.claude]`
in `links.toml`) and path-shaped constants (`"claude/settings.json"` in
`harnesses.toml` and the hook tests, `"codex/config.toml"` in `.githooks/codex-trust`,
`"agy/settings.json"` in `.githooks/live-picks`).

Hits run to hundreds in the larger repositories, mostly tests. Group them by file and
classify each site before editing it:

- **source**: the place a change is made;
- **distributed copy**: vendored, broadcast, submodule or fixture copy of a source
  elsewhere (never edit it in place; see the map below);
- **test or fixture**: a test list or recorded contract that must grow with the source;
- **live consumer**: a hook, service or rendered config on the host that picks the
  change up at activation;
- **documentation**: text that names the harness set.

A hit inside a closed set (an enum, a `const` array, a `typedef` union, a validator)
rejects the new harness until it is extended. A hit inside a two-way branch
(`claude`-else-`codex`) silently treats the new harness as one of the existing two.

### Source, distribution and activation

| Source | Copies and readers | Distribution | Takes effect |
| --- | --- | --- | --- |
| `<ops-checkout>/cli.toml` (`[vocabulary.values.harness]`, relay `hook`/`install`/`ask` and obs `index`/`report` `--harness` enums); also `keys.toml` and `cli_surface.py` | byte-identical vendored copy in relay, obs and other projects; each project's conformance test compares its live parser with the rows | adopted: change ops first, then `vendored adopt cli.toml` (ops `bin/vendored`) from each project's checkout, in the same change as its parser | when each project's change merges |
| `<ops-checkout>/bin/tt` | copy in every project | broadcast: `just vendor-publish tt` from ops after the merge (not an adoption pass) | when the broadcast lands |
| `<lore-checkout>/vendor/superpowers` | submodule pinned to `github.com/obra/superpowers` | upstream contribution or fork, then a pin bump in lore | when lore's pin bump merges |
| relay `test/fixtures/ancestry.json` (and `handles.json`) | byte copy in `<tasks-checkout>/tests/fixtures/relay/`, pinned to a relay revision in its README | copy the file from the newer relay revision and update that revision in one tasks commit | tasks tests only |
| `<relay-checkout>` source | the CLI pin in `relay/package.json` and `relay/package-lock.json`; each harness's hook images name a fixed versioned runtime path | `just relay-install` into the versioned root on this host **before** merging the pin, on other hosts as soon as it syncs; hook images (the tracked hook configs) move per harness in their own hq merge, under their own approval ([Pinned relay runtime](relay-runtime.md)) | CLI pin and hook images: both on merge, on every host sharing the checkout. The launcher exits 127, and a hook image's command cannot start, where the version it names is not installed: every host installs a hook image's version before the image merge; for the CLI pin, other hosts install as soon as the pin merge syncs |
| `relay/subscribers.template.json` | rendered to `~/.config/relay/subscribers.json`, one file read by **every** relayed harness's hook images | `just relay-subscribers` (with `FORCE=1` over a different file) on each host | per host, at render. A file naming a harness outside a runtime's closed list fails to load in that runtime, which then denies every refusable event (see section 6, Subscribers) |
| hook scripts in `<ops-checkout>/hooks`, `<lore-checkout>/hooks`, `agy/hook` | invoked by path from the tracked hook configs and the subscriber file | none | on merge to each owner's main |
| `links.toml` | home links on each host | `just link --apply` from `<hq-checkout>` main on each host | per host, at apply |
| tracked harness settings (`claude/settings.json`, `codex/*.toml`, `agy/settings.json`, …) | read through home links | none | on merge to main, while the link still resolves |

## 2. Home routing and surface delivery (`hq`, `lore`)

### Naming

Pick a canonical lowercase slug matching `[a-z][a-z0-9-]*` for
`harnesses.toml`, `facts/capabilities.toml` and cross-project `--harness` flags (`claude-code`, `codex`,
`opencode`, `pi`, `agy`). Where a harness has execution modes with different
durability or capability guarantees, declare separate fact slugs (`pi` and
`pi-durable`).

Existing consumers also use short keys:

- `links.toml` names `[harness.<home>]` groups by home role (`claude`, `claude-work`,
  `codex`, `codex-work`, `opencode`, `pi`, `agy`, `agy-config`).
- `tools/hq_cli/`, `<ops-checkout>/bin/ops-profile`, `<ops-checkout>/bin/tt`
  (`agent_of`), `<ops-checkout>/bin/tt-report`, `<ops-checkout>/bin/harness-remap`,
  `<ops-checkout>/bin/obs-index` and `<obs-checkout>/tt_runs.py` (`AGENTS`) key
  Claude Code as `claude`.

For a new harness, use one slug everywhere unless a split home needs `<slug>-config` or
`<slug>-work` in `links.toml`.

### Declaring homes in `links.toml`

Add `[harness.<name>]` and `[harness.<name>.links]`. Targets are either
`<hq-checkout>`-relative or `<project>:<relative-path>`, which `tools/harness-links`
resolves through `tasks projects --paths --json`:

```toml
[harness.<name>]
home = "~/.<harness>"
[harness.<name>.links]
"AGENTS.md" = "lore:instructions/AGENTS.md"
"settings.json" = "<name>/settings.json"
"hooks.json" = "<name>/hooks.json"
```

- **Global instructions**: always target `lore:instructions/AGENTS.md` under the
  filename the harness loads globally (`CLAUDE.md` for Claude Code; `AGENTS.md` for
  Codex, OpenCode, `pi` and Antigravity).
- **Split homes**: when a harness separates app-data state from customization files,
  declare two groups (`[harness.agy]` at `~/.gemini/antigravity-cli` for
  `settings.json`, `[harness.agy-config]` at `~/.gemini/config` for `AGENTS.md`,
  `hooks.json` and `skills.json`). A separate work home gets its own group
  (`[harness.<name>-work]`).
- **Pinned CLI runtime (optional)**: when `hq` pins and launches the harness itself (as
  `pi/package.json` + `pi/bin/pi` and `relay/package.json` + `relay/bin/relay` do), add
  `"~/.local/bin/<tool>" = "<name>/bin/<tool>"` under `[required]` and a
  `just <name>-install` recipe that installs with `npm ci --ignore-scripts` under
  `~/.local/share/<name>/<version>`, outside the synced checkout. The launcher reads
  the pin from the checkout each time it runs, so a pin change takes effect on merge:
  install it on this host before merging and on each other host as soon as it syncs.
- A new tracked `<name>/` directory is also described in hq's `AGENTS.md` Layout and in
  `README.md`.

### Skills delivery

`[required]` in `links.toml` populates `~/.agents/skills/` with one symlink per skill
into its owning checkout (`lore`, including its Superpowers submodule, `flows`, `tasks`,
`ops`, `hq`). Deliver that surface by the lightest route the harness supports:

1. **Native `~/.agents/skills` discovery** (`codex`, `pi`): nothing to link.
2. **Directory manifest** (`agy`): link a tracked manifest such as `agy/skills.json`
   containing `{"entries": [{"path": "../../.agents/skills"}]}` (`agy` resolves relative
   entries against the manifest directory `~/.gemini/config` and rejects unexpanded
   `~/`).
3. **Home-local skill directory** (`claude`): link each skill the harness does not get
   another way under `skills/<skill-name>`. Claude Code gets Superpowers from its
   plugin, so `[harness.claude.links]` lists only the non-Superpowers skills, and
   `[harness.claude-work.links]` lists none.

### Superpowers platform notes

`using-superpowers` lists per-harness reference files under **Platform Adaptation**
(`references/claude-code-tools.md`, `codex-tools.md`, `pi-tools.md`,
`antigravity-tools.md`, …) in `<lore-checkout>/vendor/superpowers`. That directory is
a submodule of the upstream Superpowers repository, so a note for a new harness is an
upstream contribution (or a fork) followed by a pin bump in lore, never a lore commit.
Read the current upstream files for their shape; they are platform notes, not tool
mapping tables.

### Untracked `local/` files and `.ops-check.toml`

- **Work and host state (`local/`)**: keep work profiles, rule directories, saved trust
  and machine-owned pick records under `local/` (`local/claude/settings.work.json`,
  `local/codex/config.work.toml`, `local/codex/rules`, `local/live-picks-*.json`).
  `.githooks/pre-commit` refuses any staged path under `local/`. If `just link --apply`
  needs an empty directory under `local/` before work configs arrive from another host,
  create it in `justfile`'s `setup` recipe.
- **Host-layout check (`.ops-check.toml`)**: pre-commit runs `tools/ops-check`, which
  scans tracked files for `$HOME`, the hostname, `$WORK_ROOT`, every registered
  checkout path, their parent sync directory, and home-relative aliases resolving into
  them. Add a tracked harness config or hook file to `layout_allowed` only when the
  harness reads literal host paths at runtime (`claude/settings.json`,
  `codex/config.toml`, `codex/hooks.json`, `codex/work/hooks.json`,
  `agy/settings.json`). Never widen `.ops-check.toml` for documentation or task
  attachments.

### First-run ordering

`tools/harness-links` applies `[harness.<name>]` only when `home` already exists as a
real directory (not a symlink), and refuses to overwrite an existing real file; a
refusal aborts the whole `--apply` pass with no partial writes.

1. Land every target named in `links.toml` in its owning project's main checkout.
2. After the section 3.1 save probe and the approval in section 8 step 1, from
   `<hq-checkout>` on `main` (never a worktree, which would leave live harnesses
   pointing into temporary storage), create the home and converge links **before**
   the harness's first interactive run:

   ```sh
   mkdir -p ~/.<harness>
   just link
   just link --apply
   just link-check
   ```

3. If a first run already created a real `settings.json` or `config.toml` in the home,
   move it aside, copy any settings worth keeping into the tracked `<name>/...` file,
   then rerun `just link --apply`.

## 3. Live-state and session-state hygiene (`hq`)

When a harness writes session picks (`/model`, `/effort`, default thinking level),
installation identifiers (`deviceId`, `trackingId`), UI counters or workspace trust into
its settings, wire the filter and refresh pipeline below so runtime state stays live on
disk without polluting the Git index or disappearing across `git checkout`.

### 3.1 Probe how the harness saves settings

The whole pipeline assumes the harness writes **through** its home symlink into the
tracked file, or has an explicit adoption contract when it saves atomically (write a
temporary file, rename it over the path, replacing the symlink with a regular file;
`agy` does this).

Probe this before section 2 links the live home, in a disposable one: the clean filter
is not wired yet, so an in-place save into the live link would write runtime keys
unfiltered into main's working tree, and an atomic save would leave a real file that
`just link-check` then refuses. Point the harness's config-directory variable (or
`HOME`) at a temporary directory whose settings file is a symlink to a scratch copy.
If the harness then has no credentials, copy only its credential file into the
temporary home (as `<ops-checkout>/bin/relay-guard-probe` `CREDENTIALS` does) and delete
it afterwards. Change a setting inside the harness, and check:

```sh
readlink -f <temp-home>/<settings-file>   # still resolves to the scratch copy
diff <scratch-copy> <before-copy>         # the change landed in the scratch copy
```

A harness that replaces the link needs an explicit synchronization contract before its
live-state layer counts as selected: for `agy`, `.githooks/live-picks` checks an
in-checkout anchor link (`~/.gemini/config/hooks.json` or `skills.json`), reads any
detached regular `~/.gemini/antigravity-cli/settings.json` during `capture`, adopts its
picks and tracked settings back into `agy/settings.json` while atomically restoring the
symlink on `restore`, `hook` and `forget`, `agy/hook` runs `harness-state-refresh` on
`SessionStart` and `PreToolUse` when the file is regular, and `[harness.agy]` declares
`adopt = ["settings.json"]` with `anchors` in `links.toml` so `just link-check` flags an
unhealed zero-turn replacement and `just link --apply` converges it via `live-picks sync`
(still refusing pre-existing files on an unanchored host). The live `just link-check`
after a real save belongs to the post-apply checks (section 8).

### 3.2 Declare the harness and its live config in `harnesses.toml`

`harnesses.toml` is the one list of harnesses: `[harnesses.<name>]` declares the slug
(capability facts read it, section 4), and `[harnesses.<name>.live_state]` declares the
tracked config the filter cleans and `live-picks` preserves. A harness with no tracked
live config is a bare `[harnesses.<name>]` table (`opencode`, `pi-durable`).

```toml
[harnesses.<name>.live_state]
config = "<name>/settings.json"          # the file the home links to
filter_glob = "<name>/settings*.json"     # every tracked variant the filter takes
format = "json"                           # or "toml"
clean_keys = ["model", "effort", "installId"]
unrestored_keys = ["installId"]
picks_record = "local/live-picks-<name>.json"
pick_units = [["model"], ["effort"]]
```

- `config` and `filter_glob` are directory-qualified, outside `local/`, and `config`
  matches `filter_glob`. The glob's only wildcard is `*`, at most one per `/` segment,
  and it never crosses `/` (`claude/settings*.json` does not take
  `claude/settings/nested.json`), as in `.gitattributes`. No two entries share a
  `config` or `filter_glob`, and no two globs can match one path (`agy/settings*.json`
  and `agy/settings-x*.json` are refused together).
- `clean_keys` lists what the filter strips. For JSON, top-level keys. For TOML, a list
  of `{ table = "<regex>", keys = [...] }` rules, where `table` is a regex the table
  header must fully match and `""` is the top level before the first header.
- `clean_tables` (TOML only) lists regexes of whole tables to drop, header and body
  (`'projects\..+'` for Codex's per-directory trust).
- `trust_table` (TOML only) names the one `clean_tables` entry whose tables a trust
  helper saves and restores (3.6); it must appear in `clean_tables`.
- `pick_units` groups the picker keys `live-picks` saves and restores. Each unit is one
  picker's fields (`[["model", "modelSettings"], ["effortLevel"]]` for Claude's `/model`
  and `/effort`), restored only when the live file holds none of them. TOML units are
  top-level one-line keys, merged in declaration order. `picks_record` is the untracked
  `local/<file>` that saves them; a record of its own per harness isolates parse errors,
  refusals and migrations.
- `unrestored_keys` lists stripped keys no picker owns, which are neither saved nor
  restored and which `forget` leaves in the file (pi's `deviceId` and `trackingId`).
- **Partition invariant**: the pick-unit keys and `unrestored_keys` are disjoint, and
  together they are exactly the filterable keys: every JSON `clean_keys` entry, or every
  top-level (`table = ""`) TOML key. A key in neither would be stripped and silently lost
  at the next checkout; `.githooks/harness_state.py` refuses the manifest instead.
- **Clean-only entry**: omit both `picks_record` and `pick_units` when the filter should
  strip keys that nothing preserves. `unrestored_keys` then defaults to every filterable
  key, `live-picks` skips the entry, and `forget` refuses it.

`python3 .githooks/harness_state.py check` validates the manifest, `.gitattributes` and
the filter config, and the pre-commit hook runs it over the staged tree (3.3).

### 3.3 Route the file through `.gitattributes`

Add exactly the declared `filter_glob`, once:

```gitattributes
<name>/settings*.json filter=harness-state
```

`.gitattributes` and `harnesses.toml` must agree both ways: a declared glob without its
line, a line no entry declares, a repeated line or a negated `filter` attribute is
refused. `.githooks/harness-state-clean` cleans a path only when one `filter_glob`
matches it and exits non-zero for any other path, JSON or TOML. `just setup` writes the
filter config: `filter.harness-state.clean = .githooks/harness-state-clean %f`,
`required = true`, so a failing clean (a broken manifest, an unparsable config) stops
git instead of staging live picks, and `smudge = cat`, the identity, because git treats a
required filter with no smudge as failed at every checkout of a filtered file. That
config lives in the repository's `.git`, which the synced checkout shares between hosts;
each host still runs `just setup` once after pulling a change to the recipe, which is
idempotent.

What the filter does with the declared keys: JSON configs are parsed strictly and
re-serialized with `json.dumps(indent=2, ensure_ascii=False)`, so a JSONC file (with
comments) fails the filter and the tracked file's formatting is normalized. TOML configs
are cleaned line by line, keeping comments and every other table intact.

- **What to strip and what to keep**: strip per-session model/effort keys, host
  workspace trust, transient fetch/UI stamps, and per-installation identifiers (`pi`'s
  `deviceId` and `trackingId`). Keep configuration that should travel through Git
  (enabled model lists, plugin toggles, hook trust hashes, version-pinned changelog
  markers such as `pi`'s `lastChangelogVersion`).
- **Failure and recovery**: while `harnesses.toml` is broken, `git add`, `git diff` and
  `git status` on a changed config fail; restore the manifest (`git checkout --
  harnesses.toml`), never unset `required`. The filter also refuses, with
  `harness-state-clean: <path>: <problem>`, a live config that is not valid JSON, and
  `cannot load .githooks/harness_state.py` when that module will not import (conflict
  markers); fix the file or restore the module. During a merge or rebase `git checkout --
  harnesses.toml` fails on an unmerged path: resolve the conflict, or run `git merge
  --abort` / `git rebase --abort`, instead. A blob staged before `just setup` holds
  its picks; the pre-commit hook refuses it until `git add --renormalize <path>`.

### 3.4 Preserve user picks across checkouts in `.githooks/live-picks`

Because the smudge is the identity, any Git command that rewrites the working-tree file
drops the filtered keys. `.githooks/live-picks` saves the live picks of every entry with
a `picks_record` and restores a unit that holds none of its keys; declaring the entry
(3.2) is the whole registration. JSON records store `"values"`, TOML records the
one-line top-level `"lines"`. A TOML pick spanning lines, or a duplicate or quoted key
that does not round-trip, is refused rather than written.

`.githooks/post-checkout`, `post-merge` and `post-rewrite` call
`live-picks hook <hook-name>` under `local/harness-state.lock`, skipping linked
worktrees and in-progress rebases. A hook reports any failure, a broken
`harnesses.toml` included, on stderr and exits 0, and the next turn end retries; the
CLI commands exit non-zero. Because absence means a Git rewrite rather than a user
reset, resetting a pick to the harness default uses `.githooks/live-picks forget <file>`.

A harness whose saves replace the home link (3.1) also needs an adoption adapter, which
the manifest does not describe: `agy`'s `AGY_HOME`, `AGY_LINK` and `AGY_ANCHORS` in
`live-picks`, with `adopt` and `anchors` under `[harness.agy]` in `links.toml`.

### 3.5 Clear Git's stat-dirty marker in `.githooks/harness-state-refresh`

Git marks a tracked file `M` whenever its size differs from the index entry, without
running the clean filter first. `.githooks/harness-state-refresh` takes its paths from
every declared `filter_glob` (as `:(glob)` pathspecs, so they match as `.gitattributes`
does). It runs `live-picks capture`, then checks the manifest and the filter config
(refusing, naming `just setup`, when they are not what `just setup` writes), syncs trust
and restores dropped picks when `index.lock` is free, and runs `git add` on files whose
filtered diff is empty. It acts on tracked files only; repairing a home link the harness
replaced requires the adoption adapter in `live-picks` and `links.toml` (3.1, 3.4).

Trigger `~/.local/bin/harness-state-refresh` (a `[required]` link, so hook configs
never hardcode `<hq-checkout>`) from whichever lifecycle hook the harness provides:

- **`Stop` command hook** (`claude/settings.json`, `codex/hooks.json`,
  `codex/work/hooks.json`, `agy/hooks.json`): drains stdin, writes nothing to stdout,
  and refreshes at the end of every turn.
- **In-process extension** (`pi/extensions/harness-state.ts`): schedules a refresh via
  `setImmediate` after `model_select` and `thinking_level_select` (so the harness's
  own write lands first), plus on `agent_settled` and `session_shutdown`.

### 3.6 Workspace trust preservation

- **Single JSON key** (`agy/settings.json`'s `trustedWorkspaces`): declare it in
  `clean_keys` and as its own pick unit, `["trustedWorkspaces"]`.
- **Dynamic TOML tables per directory** (`codex/config.toml`'s `[projects."<path>"]`):
  drop them through `clean_tables` and name that pattern as `trust_table`. Saving and
  restoring them is a helper of its own, not a manifest entry: `.githooks/codex-trust`
  serves `codex` alone (it reads `trust_table` from the `codex` entry), persisting tables
  in the untracked `local/codex/trust.toml`, acquiring `local/harness-state.lock`,
  enforcing `0600` on `local/` files, merging newly trusted paths without pruning absent
  ones, exposing `forget <path>`, and running from the checkout hooks and
  `harness-state-refresh`. A second harness with trust tables needs a helper modeled on
  it.

What stays outside `harnesses.toml`: home routing (`links.toml`, section 2), session
listing (`tools/hq.toml`), the trust helper above and `agy`'s home adoption. Each
describes a different contract, and the manifest declares only what the filter, the
refresh and `live-picks` share.

Add unit coverage for the new config's clean filter, `live-picks`
capture/restore/forget, and `harness-state-refresh` under `.githooks/` (`just test`);
`.githooks/test_harness_manifest.py` checks the shipped manifest against
`.gitattributes` and `git check-attr`.

## 4. Capability facts and probes (`hq`)

`facts/capabilities.toml` records what each harness has been shown to do; consumers
gate safety-critical behaviour on it (`claim-guard` controller wakes, live-pick reset
semantics, question-routing design).

### Declaring the harness and reading facts

1. In a worktree, declare `[harnesses.<name>]` in `harnesses.toml` (3.2; kept
   alphabetical by convention, which no check enforces). `tools/harness-facts` reads
   the declared names from there; `facts/capabilities.toml` holds only facts, and a
   `harnesses` key in it is refused. Until `<name>` is declared, `lookup` of any fact for
   it raises `Undeclared`; afterwards every undeclared entry reads `unknown`. Removing a
   harness that a fact entry still names fails `check`. `.githooks/pre-commit` runs
   the staged `tools/harness-facts check` and `.githooks/harness_state.py check` over
   the same staged tree.
2. Read facts only through `tools/harness-facts` (linked at
   `~/.agents/bin/harness-facts`), never by parsing the file:
   - CLI: `tools/harness-facts check`, `list [--pretty]`, `get <fact> <harness>`
     (`claim-guard` uses `~/.agents/bin/harness-facts list`).
   - In-process module (for hooks that cannot afford a subprocess): load
     `tools/harness-facts` with `importlib.machinery.SourceFileLoader` (with
     `sys.dont_write_bytecode = True`) and call `lookup(fact, harness)`.

### Recording `unknown` and `probed`

- **`unknown`**: a harness with no `[facts.<fact>.harness.<name>]` table reads as
  `{"fact": …, "harness": …, "type": …, "status": "unknown"}` (plus `"note"` on an
  explicit `unknown` entry); `value`, `version`, `date` and `evidence` are omitted, so
  consumers check `status == "probed"` before reading `value`. An explicit
  `status = "unknown"` table may carry only `status` and an optional `note`.
- **`unknown` is not `false`**: each consumer chooses its own safe fallback. When a
  probe proves the harness lacks a capability, record `status = "probed"` with
  `value = false` (boolean) or `value = []` (set).
- **Required fields for `probed`**:

  ```toml
  [facts.controller-wake.harness.<name>]
  status = "probed"
  value = false
  version = "1.2.0"
  date = 2026-10-31
  evidence = "hq-b2515c"
  note = "Isolated terminal run: background child finished after turn end and no new controller turn started within 170s."
  ```

  `date` is an unquoted TOML local date; quoted strings and timestamps are rejected.
  `evidence` names the task(s) whose notes or attachments keep the raw probe output.

### Reproducible probes

`probe` is a key of the fact (`FACT_KEYS = type, description, probe, harness`), one per
fact; harness entries cannot carry their own. `check` verifies that the path exists
inside `<hq-checkout>`.

- **A fact that already has a probe**: extend that probe rather than adding a second.
  The claim-guard facts (`controller-wake`, `controller-wake-kinds`) point at
  `agents/bin/wake-judge`; add a `judge_<name>` function and register it in its
  `JUDGES` table.
- **A fact only this harness has** (as the `pi` facts point at
  `pi/probes/extension-probe.py`): place the probe under `<name>/probes/` and set
  `probe` on the fact.
- **A shared fact with no probe yet**: write one that every harness can run, or keep
  the harness-specific procedure in the evidence task and leave `probe` unset.

Probes use temporary config directories and isolated scratch workspaces, never live
homes. Document the harness's version-upgrade re-probe procedure in `README.md` beside
"Re-probing a fact" and "Re-probing pi"; an inconclusive run leaves the facts file
unchanged.

## 5. Hooks, profiles and guards (`lore`, `ops`, `hq`)

### Standard hook roles

- **Session start (`SessionStart`)**:
  - `<lore-checkout>/hooks/claude-profile`: loads `<ops-checkout>/bin/ops-profile`
    in-process, passes the hook payload to `profiles.resolve(cwd or fallback_cwd, env,
    payload)` and `profiles.session_text(res)` (so `home_of()` can inspect
    `transcript_path`, which the `ops-profile session` CLI does not accept), prints the
    `profile:` line and profile instructions, and appends
    `export AGENT_PROFILE=<profiles>` to `CLAUDE_ENV_FILE` when provided.
  - `<ops-checkout>/hooks/capture-notice` (personal homes only): prints pending mindful
    capture counts.
  - Optional: `<ops-checkout>/hooks/claude-sessionstart` (Projects/lore drift check,
    `halt` notice, synced-root `git-index-health` repair).
- **Before a tool runs (`PreToolUse`)**: `<ops-checkout>/hooks/relay-guard`, the
  command policy. See [Command guard](#command-guard) below; a harness without it runs
  shell commands unguarded.
- **Turn boundary (`Stop`, plus `SubagentStop` where workers fire their own stop hook,
  as in Codex)**:
  - `<ops-checkout>/hooks/claim-guard --harness <name>`: blocks turn completion once
    while this session holds live claims that probed `controller-wake`,
    `controller-wake-kinds` and `stop-input-in-flight-statuses` facts do not cover.
  - `~/.local/bin/harness-state-refresh` (section 3.5).

### Schema, payload and stdout differences

Probe the harness's exact hook contract before wiring shared scripts directly. Existing
harnesses differ on four axes:

| Axis | Claude Code and Codex | Antigravity (`agy`) |
| --- | --- | --- |
| Config structure | `{"hooks": {"<Event>": [{"matcher": "...", "hooks": [{"type": "command", "command": "...", "timeout": ...}]}]}}` in `claude/settings.json` or `codex/hooks.json` | Top-level hook names in `agy/hooks.json`: `{"<hook-name>": {"enabled": true, "Stop": [{"type": "command", "command": "..."}], "PreToolUse": [{"matcher": "...", "hooks": [...]}]}}` (flat handler lists on `SessionStart`, `PreInvocation`, `PostInvocation`, `Stop`; `matcher` + `hooks` groups only on `PreToolUse` and `PostToolUse`) |
| Stdin payload keys | `snake_case`: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `stop_hook_active`, `agent_id`, `tool_name`, `tool_input`, `background_tasks`; ops hooks also read `model`, `to_model`, `scratchpad_dir` and `session_crons` where Claude Code sends them | Protojson `camelCase`: `conversationId`, `workspacePaths`, `transcriptPath`, `artifactDirectoryPath`, `modelName`, `toolCall.name`, `toolCall.args`, `fullyIdle` (and further Stop fields recorded in the facts notes) |
| Shell tool | `Bash` with `tool_input.command` | `run_command` with `toolCall.args.CommandLine` |
| Stdout contract | `SessionStart`: plain text injected into context. `Stop`: `{"decision": "block", "reason": "..."}` blocks; empty stdout allows | Empty stdout is a no-op, **but** non-empty stdout must be event-shaped JSON: `SessionStart` / `PreInvocation` need `{"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]}`, and `Stop` blocks with `{"decision": "continue", "reason": "..."}` |

Consequences:

- **Adapter hooks for JSON-stdout harnesses**: do not wire plain-text `claude-profile`
  or `capture-notice` to a harness that parses `SessionStart` stdout as JSON, or emit
  `"decision": "block"` where only `"continue"` holds the turn. Write one adapter hook
  in the harness's directory, as `agy/hook` does: it heals detached `settings.json`
  files on `SessionStart` and `PreToolUse` (emitting empty stdout on `PreToolUse` so
  `agy` keeps its permission flow), wraps `claude-profile` and `capture-notice` output
  in `injectSteps`, and runs a one-shot Stop claim check until claim-guard supports agy
  natively (ops-33cef9), while `agy/hooks.json` routes `SessionStart`, `PreToolUse` (`*`)
  and `Stop` through `relay` (`v0.3.0`). Its tests are `tools/test_agy_hooks.py` and
  the agy cases in `tools/test_claim_guard_wiring.py`,
  `tools/test_capture_notice_wiring.py` and `tools/test_relay_wiring.py`.
- **Interactive hook trust (Codex)**: Codex hashes every hook command per home. Any
  edit to `codex/hooks.json` or `codex/work/hooks.json` lands with no Codex TUI or
  `codex app-server` running, followed by an interactive `/hooks` review in each home
  under `--no-daemon` ([Pinned relay runtime](relay-runtime.md)).

### Command guard

`<ops-checkout>/hooks/relay-guard` reads a schema-1 before-tool envelope and treats
only `COMMAND_TOOLS = {"Bash"}` as command-bearing: a `null` command on `Bash` is
refused, and on any other tool name is allowed without running the policy. Every link
on the way to it must know the new harness's shell tool. There are two routes:

- **Relayed** (Claude Code, Codex, agy):
  1. native before-tool payload, either in snake_case with `tool_name` and `tool_input`
     or normalized by the adapter's `nativeFields` (`agy` maps `conversationId` ->
     `session_id`, `workspacePaths[0]` -> `cwd`, and `run_command` / `args.CommandLine`
     -> `Bash` + `{command}`);
  2. relay's shared `normalizeEvent` (`<relay-checkout>/src/adapters/index.js`) sets
     `tool.command` only for `tool_name == "Bash"` with a string `tool_input.command`;
     anything else becomes `null`;
  3. the `ops-guard` subscriber in `relay/subscribers.template.json` lists
     `"harnesses": ["claude-code", "codex", "agy"]` and `"tools": ["Bash"]`, matched
     literally (`src/subscribers.js`), and relay accepts a guard subscriber only when the
     harness's adapter declares `replies[<native>].refuse` for its before-tool events
     (raise the harness's handler `timeout` and `--outer-ms` together when its default
     outer timeout leaves less than `ops-guard`'s 30 s plus observer budgets, as `agy`
     raises both to 60 s / 60000 ms);
  4. relay-guard's policy;
  5. a denial encoded in the harness's own reply schema (the adapter's `encodeReply`),
     with empty stdout on allow so the harness keeps its own permission prompts.

  A native tool named `run_command` or `shell` either misses the subscriber or, if the
  filter is merely widened, reaches the policy as a non-command and is allowed. Have
  the adapter or bridge emit `Bash` + `command`, or change extraction, `COMMAND_TOOLS`
  and the subscriber filter together.
- **Direct adapter** (before a relay adapter exists): when onboarding a harness before
  relay speaks its protocol, an in-tree adapter hook can build the schema-1 `before-tool`
  envelope itself, call relay-guard, fail closed on any unreadable payload or guard
  error, and encode the denial in the harness's schema until relay takes over.

The guard layer passes only with isolated evidence for three cases: a harmless permitted
command runs; a fixture command the policy refuses is denied and never executes; a
malformed command input is refused. For a relayed harness, also extend
`<ops-checkout>/bin/relay-guard-probe` (`CREDENTIALS`, `HELP_COMMANDS`,
`harness_command()`, `hook_document()`), whose output is the evidence file
`relay install --evidence` reads. relay refuses guard subscribers for `opencode`
(`validateCapabilities`), so that harness has no command guard today.

### Extending `ops-profile` and `claim-guard` (`<ops-checkout>`)

1. **`bin/ops-profile`**:
   - Add `"<agent-key>": ("<HOME_ENV_VAR>", "~/.<default-home>")` to `HARNESS`. Keep
     `<agent-key>` identical to the key `tt.agent_of(env)` returns (`home_of()` indexes
     `HARNESS` with it) and to the key in `<obs-checkout>/tt_runs.py` `AGENTS`.
   - Add `<agent-key> = "..."` to **every** `[home.<profile-home>]` table in
     `profiles.toml`: `config_problems()` rejects a profile config unless every home
     declares a path for every `HARNESS` key.
   - `home_of(env, config, payload)` matches `payload["transcript_path"]` against
     configured homes first, then falls back to `tt.agent_of(env)` and the home
     variable. A harness that sends `transcriptPath` or writes transcripts outside its
     config home (agy writes under `~/.gemini/antigravity-cli/brain/<id>` while reading
     hooks from `~/.gemini/config`) needs the path normalized in its adapter or its
     transcript root registered.
2. **`hooks/claim-guard`**:
   - Add `<name>` to `HARNESSES` **and** a `BOUNDED_WAIT[<name>]` string:
     `wait_branch()` indexes it whenever `wake` resolves to `None` or
     `controller-wake` is probed false, including when claims or facts cannot be read.
   - Adding to `HARNESSES` also widens `held()`'s `wanted` set: claims recorded as
     `<any HARNESSES entry>:<session>` match for every non-Codex harness, Claude Code
     included.
   - claim-guard filters claims on `live` and session, not `doing` status, and fails
     closed on unreadable Stop input or claims.
   - Map the harness's loop-breaker field (`stop_hook_active`, or agy's `fullyIdle`
     and Stop fields), worker identifier (`agent_id`) and blocking decision (`"block"`
     or `"continue"`). The `SubagentStop` check in `decide()`, the `root_session ==
     "codex:…"` match in `held()` and the `related` computation are Codex-only;
     generalize them if the harness fires `SubagentStop` or records worker claims.
3. **Verified model provenance**: `<ops-checkout>/hooks/claude-provenance` is
   Claude-only (it hard-codes `claude-code` and needs `CLAUDE_ENV_FILE` and the
   payload's `scratchpad_dir`). A harness that should export verified `TASKS_AGENT`
   and `TASKS_MODEL` needs its own hook from a source that reports the live model.
4. **Hook wiring tests in `hq`**: extend `tools/test_capture_notice_wiring.py`,
   `tools/test_claim_guard_wiring.py` and `tools/test_relay_wiring.py` so hook command
   strings and ordering cannot drift silently.

## 6. Relay, ancestry and provenance (`ops`, `relay`, `tasks`, `obs`, `familiar`, `hq`)

### Shared CLI vocabulary first (`<ops-checkout>`)

Add the slug to `cli.toml`: `[vocabulary.values.harness]` and each `--harness` enum the
harness should appear in (`git grep -n 'shared = "harness"' cli.toml` lists them: relay
`hook`, `install`, `ask`, `model`; obs `index`, `report`). Each project's conformance
test (`tests/test_cli_surface.py` in obs, `test/cli-surface.test.js` in relay)
requires its live parser to equal these rows, so widening relay `HARNESSES` or the obs
`--harness` choices without this change fails those tests. After the ops merge, each
project runs `vendored adopt cli.toml` (ops `bin/vendored`) from its own checkout in
the same change that widens its parser.

### `relay` (`<relay-checkout>`)

1. **Closed sets**: `HARNESSES` in `src/commands.js`, `harnesses` in `src/protocol.js`
   (with any worker, background and scope invariants there and in
   `src/bus/transaction.js`), `HARNESSES` in `src/subscribers.js` and
   `src/interaction/message.js`, `harnesses` in `src/install/atomic.js`, the `Harness`
   union in `src/types.js`, `ROUTES` in `src/routes/index.js`, the "closed union" in
   `docs/api.md`, opencode-specific flag branches in `bin/relay.js`, and the test
   lists.
2. **Adapter**: implement `src/adapters/<name>.js` and register it in `adapters` in
   `src/adapters/index.js`:
   - events and state: `events` (`nativeEvent -> {kind, level}`), `stateForEvent`,
     `reduceState`, `replies` flags (`refuse` on each before-tool event is required
     for a guard subscriber), `outerTimeouts`, `encodeReply`, optional `nativeFields`,
     `failureExitCode`, and `workerIdOf` / `backgroundOf`;
   - process tree: `isHarness(row, ops)` (only Claude Code's uses `ops`, which supplies
     `executableOf`), `resolveSessionPid`, `resolveTerminalPid`.
3. **Payload parsing is shared, with optional adapter field normalization**:
   `normalizeEvent` (`src/adapters/index.js`) calls `parsePayload`
   (`src/adapters/payload.js`), which parses the UTF-8 JSON object `data`, runs
   `adapter.nativeFields(data, nativeEvent)` when defined, and then requires a non-empty
   `session_id`, an absolute `cwd`, and on `PreToolUse` a `tool_name` and object
   `tool_input`; `hook_event_name` is optional but must match the native event when
   present. A camelCase harness implements `nativeFields` on its adapter to map native
   keys into that shared contract before validation.
4. **Plugin-event harnesses**: when the harness exposes plugin events rather than shell
   hooks, follow `integrations/opencode/` (`plugin.js`, `binding.js`, `hook.js`,
   `queue.js`, `window.js`, exported from `package.json` as `./opencode`); its event
   table is `src/adapters/opencode.js`.
5. **Installer**: add bindings to `table` in `src/install/hooks.js` (`bindingsFor`,
   `planHooks`), a `src/install/<name>.js` planner, and a `harness === '<name>'`
   branch in `bin/relay.js` (whose `else` otherwise falls through to `planOpenCode`).
6. **Question routes**: probe and record the `answer-*` facts first. `relay install`
   does not read the facts file; it validates `--evidence <file>` with `parseEvidence`
   then `validateCapabilities` (`src/install/capabilities.js`, which hard-codes the
   opencode refusals) and `ROUTE_EVIDENCE` / `routeBindings()` in
   `src/install/hooks.js`, plus the `'claude-code'` route guards in `hooks.js` and
   `bin/relay.js`.

### Relay consumers

- **`<obs-checkout>/record.py` `HARNESSES`**: add `<name>` whenever relay publishes
  envelopes for it. Otherwise `obs ingest` rejects them, printing only
  `{"event": "obs-ingest-failed", "error": "ValueError"}`.
- **Subscribers (`hq`)**: `relay/subscribers.template.json` scopes `ops-guard` to
  `["claude-code", "codex", "agy"]` and pairs `familiar`, `familiar-opencode`,
  `familiar-teardown`, `familiar-teardown-codex` and `familiar-agy` to their respective
  harnesses and event kinds. Add the harness only to the subscribers whose layer is
  selected; adding it to `ops-guard` alone does not guard it (Command guard above).

  **Ordering hazard**: every relayed harness's hook images read the one rendered
  `~/.config/relay/subscribers.json`, and each runtime rejects the whole file if any
  `harnesses` entry is outside its closed list (`src/subscribers.js`). A rejected file
  sends dispatch down its fail-closed path: every refusable event is denied (so every
  PreToolUse call is blocked) and other events exit 1. Hook images name fixed runtime
  versions (versions can differ across harnesses; `tools/test_relay_wiring.py` records
  them), and a CLI pin change does not move them. So, in this order:
  1. land and install a relay release whose `HARNESSES` includes the new slug (and, for
     a guard subscriber, whose new adapter declares `refuse` for its before-tool
     events);
  2. once **every** host sharing the checkout has installed that release, move every
     relayed harness's hook images to it in one approved hq merge, with the Codex
     no-process and `/hooks` re-trust steps ([Pinned relay runtime](relay-runtime.md));
     the merge takes effect on every host at once;
  3. only then, with approval, add the slug to the template and run
     `just relay-subscribers` on each host;
  4. run one hook from an existing harness (a harmless command in Claude Code and in
     Codex) against the new file and confirm it is allowed.
- **Familiar (`<fam-checkout>`)**, only when its observer is selected:
  `src/render/harness.js` throws on any harness outside its set, and
  `src/observe/emission.js` calls it, so events from a new harness throw during
  rendering. `src/bus/sessions.js` and `src/attention/model.js` hold further closed
  sets. Extend and test these before adding the harness to the familiar subscribers;
  otherwise leave it out of them and record the layer as deferred.

### `tasks` ancestry and claims (`<tasks-checkout>`)

1. **Process ancestry (`src/relay/ancestry.rs`)**: add `("<comm>", "<name>")` to
   `HARNESS_COMMS` and grow its array length (`[(&str, &str); N]`). Relay-bound claims
   are enabled per host by `[identity] relay = true` in
   `$XDG_CONFIG_HOME/tasks/config.toml`, not per project.
2. **Daemons and versioned binaries**: if the harness runs under versioned names,
   Node/Bun entrypoints, or long-lived daemon or PTY-host subcommands, extend
   `harness_of()` and `boundary_scope()` so concurrent sessions under one daemon do not
   collapse onto one PID. Today `boundary_scope` returns early for every harness but
   Claude Code, whose roles are `CLAUDE_ROLES = [daemon, bg-pty-host]`; nothing handles
   Codex `app-server`.
3. **Fixture**: `tests/fixtures/relay/ancestry.json` is a byte copy of relay's
   `test/fixtures/ancestry.json`, pinned to a relay revision in that directory's README.
   Add new trees in relay, then copy the file and update the revision in one tasks
   commit; never hand-edit the copy. A new chain whose `session` is null also needs its
   expectation in `NULL_SESSION_EXPECTED` in `ancestry.rs`.
4. **Further closed sets**: `HARNESSES` in `src/relay/snapshot.rs` (without it tasks
   rejects the harness's relay snapshot rows); `hint_for` and the Claude-only form of
   `same_session` in `src/relay/resolve.rs`; the native identity levels in
   `identity_from` and the Codex-only branch of `proves_ownership` in `src/claims.rs`;
   the `--origin-session` help text and validation.

### Native session provenance (`<tasks-checkout>`, `<obs-checkout>`)

- Lifecycle transitions and `tasks note --stamp` record
  `provenance: {"harness_session": "<name>:<id>", "harness_session_source": "<ENV_VAR>"}`
  when the harness exports a native session variable to child shells
  (`CLAUDE_CODE_SESSION_ID`; `CODEX_THREAD_ID` or `CODEX_SESSION_ID`).
- For a new verified variable, extend `validate`, `validate_session_key`,
  `resolve_from` and (for a separate worker root variable) `resolve_root_from` in
  `src/provenance.rs`, and in lockstep `<obs-checkout>/join.py`: `<name>` in
  `HARNESSES` and `"<ENV_VAR>": "<name>"` in the `SOURCES` dict. Otherwise `obs index`
  fails on the first stamped note from that harness: the task is reported on stderr,
  counted as failed, outcomes are skipped, and the run exits 1 with `index_failed`.
- `TASKS_SESSION` and `TASKS_SESSION_PID` are claim-ownership overrides, never
  provenance. When a harness exports no native session ID (`agy`, `pi` without an
  extension), `--stamp` omits `provenance`; report session attribution as absent rather
  than inventing one.

### Child-shell environment

- `TASKS_FORMAT=json` is already the CLI default; set it in the harness's child
  environment only to override an inherited `pretty`.
- Set `TASKS_AGENT=<name>/<model>` and `TASKS_MODEL=<model>` only from a hook that
  verifies the live model (section 5, item 3); otherwise set `TASKS_AGENT=<name>`
  without guessing a model from static defaults.

### Test-run provenance (`<ops-checkout>`, `<obs-checkout>`)

Extend `agent_of(env)` in `<ops-checkout>/bin/tt` to recognize the harness's
environment marker and session variable, so runs appended to
`~/.local/share/ops/runs.jsonl` carry its agent key and session ID. `tt` is broadcast:
after the merge, `just vendor-publish tt` from ops writes it into every project.

Register the same key, in the same change, in every reader:

- `HARNESS` in `<ops-checkout>/bin/ops-profile` (section 5);
- `AGENTS` in `<ops-checkout>/bin/tt-report`, which otherwise counts the harness's runs
  as malformed and skips them without warning;
- `AGENTS` in `<obs-checkout>/tt_runs.py` (`{'claude': 'claude-code', 'codex':
  'codex', …}`), with the target slug in `<obs-checkout>/join.py` `HARNESSES`; a slug
  missing there makes `tt_runs` classify the record as malformed;
- `HARNESSES` in `<ops-checkout>/bin/harness-remap`, `INTERACTIVE` in
  `<ops-checkout>/bin/obs-index`, and the tasks-tui launch bindings in
  `<ops-checkout>/keys.toml` (an adopted file, like `cli.toml`).

## 7. Session discovery, archive and transcript readers (`hq`, `obs`)

Read `docs/notes/2026-10-15-session-discovery-contract.md` first: `hq sessions` keeps no
index, reads each harness's native metadata directly, and raises `SourceError` when a
present home's metadata is missing, unreadable or at an unexpected schema version.

One module per harness carries all of it: `tools/harness_stores/<name>.py` exports an
`ADAPTER` (`tools/harness_stores/model.py`, `Adapter`). `hq sessions`, `session-archive`
and `session-episodes` each read the registry, so a new harness is not threaded through
their code. Use `claude.py`, `codex.py` and `agy.py` as models (agy is the one whose
transcript does not name its own working directory).

### The adapter (`hq`)

1. **`tools/harness_stores/<name>.py`**: define the `Adapter` fields: `slug` (the key in
   `harnesses.toml`, `[harnesses.<slug>]`), `alias` (the `hq sessions --harness` value),
   `colour`, `home_variable` (the environment variable naming a work home, or `None`),
   `homes(user_home)` returning `Home` entries, `list_sessions(home, archived)` returning
   `(list[Session], counts)`, `notes_segment` for the footer, `exclusion_reasons`,
   `resume_argv(session, flags)`, `archive_sources(user_home)`, `episode_env` and
   `episode_root`. `Session` carries `home`, `id`, `cwd` (`None` when the transcript store
   cannot name one; listing and launch then refuse the row, they never guess), `recency_ms`,
   `label`, `transcript`, and `excluded` (`"non-interactive"`, `"transcript gone"` or a
   reason of your own listed in `exclusion_reasons`). Split JSONL on `"\n"`, not
   `str.splitlines()`, which breaks on `U+2028` inside JSON strings. A source that has
   drifted raises `SourceError` naming the file; never return an empty list for it.
2. **Register it** in `tools/harness_stores/__init__.py` (`ADAPTERS`; the order is the
   display order).
3. **Colour and flags**: define `<NAME> = Colour(oklch(L, C, H), <xterm-256-index>)` in
   `tools/hq_cli/color.py`, with both its 24-bit and xterm-256 forms reaching
   `contrast(..., DARK) >= 3` and `contrast(..., LIGHT) >= 3`, and add
   `[homes.<home-name>]` `flags = [...]` to `tools/hq.toml`. For a work home selected by
   an environment variable, set `home_variable` on the adapter.

### Transcript capture and pruning (`tools/session_archive/`)

1. Declare sources in the adapter's `archive_sources(user_home)` as
   `Source(name, harness, home, root, prune, ...)`, passing `prune=None` (the archive
   does not prune it) explicitly, as it has no default. Use `required=False` for a home that may be absent
   on an archive host, so a host without it skips the source instead of aborting the
   run. Narrow a source with `descend` and `select` (agy's brain tree holds many
   files that are not transcripts), and set `append_only=True` only for files that
   grow by appending; a database rewritten in place is `append_only=False` so the
   mirror rotates it. `capture` walks regular files under `Source.root`, skips files
   mutated mid-copy (`"busy"`), and keeps non-append rewrites under `versions/`
   (`"diverged"`).
2. `check_sources()` runs before every `session-archive` command and aborts the whole
   run (`EX_HOST`), for every harness, if any source's home or root is a symlink, or if
   a root is missing and the source is either required or already captured (an optional
   source whose root is absent and never captured is skipped). Once a required `Source`
   lands, run `mkdir -p <Source.root>` on **every** archive-configured host before the
   daily capture timer runs.
3. Pruning is opt-in per harness: give the `Source` a `PruneHooks` and `decide.py` and
   `prune.py` dispatch through it; `prune=None` means the archive never prunes it. Do so
   only once `<obs-checkout>` indexes the store at contract-2 readiness (see
   `docs/specs/2026-09-30-session-archive-design.md`), the obs identity check in
   `tools/session_archive/inputs.py` accepts the harness, and live pruning is separately
   approved.
   Never add a harness's `comm` to `uninspectable_ok` in
   `~/.config/session-archive/config.toml`: that would suppress `InspectionFailed`
   during `prune` and risk deleting open session files. Archive tests use temporary
   directories, never live homes.

### `session-logs`, `session-episodes` and `obs` (`hq`, `<obs-checkout>`)

1. **`agents/skills/session-logs/SKILL.md`**: document the live store path, the session
   unit (JSONL file, SQLite database, or per-conversation directory), record types,
   subagent storage, how a tool result is paired with its call (by id or by position),
   and the markers that tell human prompts from injected context.
2. **`agents/bin/session-episodes`**: add the harness to `READERS` (slug to glob,
   header reader, full reader and turn function) and to `INTERACTIVE`; roots come from
   the adapter's `episode_env` and `episode_root`, so `_roots()` needs no edit. A
   harness stays out of `DEFAULT_HARNESSES` (readable only with `--harness <name>`)
   until its episodes are judged useful. Keep the reader in step with the obs adapter's
   prompt stripping.
3. **Capability facts**: record what the store cannot do as facts rather than prose:
   `tool-result-call-ids`, `session-metadata-marks-headless`, `transcript-self-describing`
   and `session-archive-complete` (section 4). A `false` is an answer; an unprobed
   value is `unknown`.
4. **`<obs-checkout>`**: implement `<name>_adapter.py` (session metadata, turns, usage,
   tool and shell calls, skill reads, hook runs, turn-end reasons, truncation markers)
   and register it in `stores.py` (`ADAPTERS`, `SKILL_COVERAGE`, `store_roots()` with an
   `OBS_<NAME>_...` override so tests never read live homes, `_paths()`, `_peek_cwd()`,
   `_initial_state()`). Discovery (section 1) finds the remaining registries; among
   them are `index.py`, `obs.py` (with `main()`'s default harness list kept equal to
   `stores.ADAPTERS`), the `session_logs*.py` pipeline (or an explicit exclusion in
   `session_logs_place.roots()`), `dashboard.py`, `catalog.py`, `hook_report.py`,
   `tt_report.py` (`TOOLS` shell-tool names), `index_state.py`, `baseline.py`,
   `sweep.py`, `task_activity.py` and `stores.run()`'s Codex-only branches,
   `tools/archive_replay_rehearsal.py`, `tools/retention_readiness.py`, the README's
   `--harness` text, and tests that pass a fixed harness list to `stores.run` or assert
   exact skills coverage.
5. Run the adapter against the real local store (`obs index`) and verify `tt_runs`
   session-key joins before enabling archive pruning.

## 8. Rollout

1. **Get approval before landing anything live**: a merge or apply that changes a live
   global surface (hook scripts, tracked settings, home links, runtime pins, hook
   images, the subscriber file, archive pruning) needs the user's approval under every
   profile, and approving a docs change or a plan does not grant it. Ask per surface,
   naming when it activates:
   - hook scripts, tracked settings, runtime CLI pins and hook images (tracked hook
     configs) take effect when they merge to their owner's main, on every host sharing
     the checkout;
   - `links.toml` and the subscriber file take effect on each host's
     `just link --apply` and `just relay-subscribers`.
2. **Verify in worktrees, then land in order**: `ops` first when `cli.toml`, `tt` or
   shared hooks change; then each consumer (`relay`, `tasks`, `obs`, `familiar`,
   `lore`) with its adoption in the same change; then `hq`, in the stages section 6
   (Subscribers) and step 4 give (pin, then hook images, then the subscriber template),
   never as one merge. Each project verifies by its own test policy and gates (in
   `hq`: `just test`, which the pre-commit hook complements with `tools/ops-check`,
   `tools/ops-docs check`, `tools/harness-facts check` and `.githooks/harness_state.py check`). A green suite does not replace the selected-layer
   evidence in section 0. Every target named in `links.toml` exists on its owner's main
   branch before links are applied. A runtime pin is installed on this host
   (`just relay-install`, `just <name>-install`) before it merges.
3. **Preserve before activating**: keep current settings, saved trust, live picks and
   every runtime version a hook image names recoverable. Follow
   [Pinned relay runtime](relay-runtime.md) for relay state preservation and rollback;
   never reset or downgrade durable state to recover.
4. **Across hosts, in this order** (section 6, Subscribers, ordering hazard):
   1. on every host, install each runtime version a pin or hook image will name, and
      `mkdir -p` any new `Source.root` on archive-configured hosts;
   2. once, globally: the hq merge that moves the hook images;
   3. on each host: render subscribers, then `mkdir -p <home>`, `just link --apply` and
      `just link-check` from `<hq-checkout>` main before the harness's first
      interactive run.
5. **One end-to-end check per configuration path**: verify every selected layer on one
   host and one profile; other hosts and profiles configured by the same process count
   as covered. A host or profile reached through a different path gets its own check.
6. **Post-apply live checks**:
   - complete any per-home interactive hook trust review (Codex `/hooks`);
   - change model or effort in the harness, restart it, finish a turn, then confirm the
     home link still resolves into `<hq-checkout>` (`just link-check`),
     `git -C <hq-checkout> status` shows no dirty marker on the tracked config, and
     `local/live-picks-<name>.json` holds the **new** value, not an older record;
   - run the guard and claim-guard evidence from section 5 against the live wiring.

## Onboarding checklist

| Layer | Repositories | Key files | Verification |
| --- | --- | --- | --- |
| Discovery | all | section 1 search | every hit classified on the onboarding task |
| Home routing and instructions | `hq` (`lore` upstream for Superpowers notes) | `links.toml`, `justfile`, `.ops-check.toml`, `AGENTS.md`, `README.md` | `tools/ops-check`, `just link`, `just link-check` on main after apply |
| Live-state hygiene | `hq` | `harnesses.toml`, `.gitattributes`, optional trust helper or adoption adapter, `just setup` on every host | `just test`, `.githooks/harness_state.py check`; link survives a harness save; clean `git status` after a turn |
| Capability facts and probes | `hq` | `harnesses.toml`, `facts/capabilities.toml`, `agents/bin/wake-judge` `JUDGES`, `<name>/probes/`, `README.md` | `tools/harness-facts check`, `list --pretty` |
| Profile, command guard, claim guard | `lore`, `ops`, `relay`, `hq` | `<name>/hooks.json` or adapter hook, `<ops-checkout>/bin/ops-profile`, `profiles.toml`, `hooks/relay-guard`, `hooks/claim-guard`, `bin/relay-guard-probe`, `relay/subscribers.template.json`, `tools/test_*_wiring.py` | owners' tests; three-case guard evidence; held-once Stop |
| CLI vocabulary, relay, ancestry, provenance | `ops`, `relay`, `tasks`, `obs`, `familiar`, `hq` | `<ops-checkout>/cli.toml`, `bin/tt`, `bin/tt-report`, `keys.toml`; `<relay-checkout>/src/`, `bin/relay.js`; `<tasks-checkout>/src/relay/`, `src/provenance.rs`, `src/claims.rs`, fixture copy; `<obs-checkout>/{record,join,tt_runs}.py`; `<fam-checkout>/src/` if selected; `relay/package*.json` | owners' tests including conformance; distinct identities for concurrent sessions; stamped notes join |
| Sessions, archive, `obs` | `hq`, `obs` | `tools/hq_cli/`, `tools/hq.toml`, `tools/session_archive/`, `agents/skills/session-logs/SKILL.md`, `agents/bin/session-episodes`, `<obs-checkout>/<name>_adapter.py`, `stores.py` and the registries discovery finds | `just test`, `hq sessions`, obs tests, live `obs index` |
