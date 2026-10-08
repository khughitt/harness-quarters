# Declared surface drift — brief

Scoped 2026-10-08 from `hq-b5595a`, `hq-ac80cb`, `hq-e18255` and `hq-fe88ef`, the
follow-ups the residue (`hq-dcb11a`) and the rename (`hq-8b7a28`) filed and did not
act on.

## Problem

hq declares what every harness home on every host runs: `links.toml` routes the homes,
the hook commands in the tracked settings call the guards, and `facts/capabilities.toml`
says what each harness has been shown to do. Each of the four ideas is a place where
what a host runs has drifted from, or can silently drift from, that declaration: a skill
no manifest names, a home that lacks the skills its instructions assume, hook strings
that break on a rename, and facts probed on a harness version no longer installed.

## Current behaviour and evidence

- **Stray Codex skill (`hq-b5595a`).** On the second host,
  `~/.codex/skills/security-best-practices` is a real directory dated 2026-02-17
  (`SKILL.md`, `LICENSE.txt`, `agents/openai.yaml`, `references/` for Python,
  JavaScript/TypeScript and Go frameworks): an OpenAI-curated skill installed by hand.
  No manifest line declares it, this host lacks it, and lore's
  `skills/security-and-hardening` (linked into `~/.agents/skills`) covers the same
  ground for both harnesses.
- **Work Claude home (`hq-ac80cb`).** `[harness.claude-work.links]` declares
  `CLAUDE.md`, `settings.json` and the status line, and no skills;
  `~/.claude-work/skills` holds only the harness-synced directory. The personal home
  declares six (`flow`, `session-logs`, `curate`, `scope`, `tasks`, `quick-add`), and
  Codex's work home reads `~/.agents/skills`, which has them all. The global
  instructions linked into the work home require `tasks` and the Trials rule's flow,
  and lore's `profiles/work.md` writes specs through `tasks where`.
- **Stale facts (`hq-e18255`).** Installed today: Claude Code 2.1.294 and Codex
  0.161.0. Every fact entry was probed on Claude Code 2.1.282 or 2.1.284 and Codex
  0.156.1. `harness-facts` has `check`, `list` and `get`; none compares versions.
  Codex's `controller-wake = false` is live: ops `hooks/claim-guard` mirrors it as
  `CHILD_WAKES`, the global Processes rule cites it, and the Codex long-waits brief
  (`docs/notes/2026-10-08-codex-long-waits-brief.md`) builds its constraint on it.
- **Hook paths (`hq-fe88ef`).** `claude/settings.json`, `codex/hooks.json`,
  `codex/hooks.work.json` and the untracked `local/claude/settings.work.json` call
  `~/d/lore/hooks/claude-profile` and five ops hooks (`claim-guard`,
  `claude-sessionstart`, `claude-provenance`, `claude-pretooluse`,
  `claude-posttooluse`) by checkout path. Codex keys hook trust by a hash of the
  command (`[hooks.state.*] trusted_hash`), so renaming lore or ops changes those strings
  and costs a re-trust in every Codex home on both hosts. `harness-state-refresh` already
  moved behind `~/.local/bin` for this reason (rename design §3); ops's `just install`
  links six of its `bin/` tools there but none of its hooks. familiar's hooks name
  `~/d/familiar/bin/familiar` too, while an npm-installed `familiar` is already on
  `PATH`.

## Constraints

- Home routing changes only in `links.toml`, applied by `just link --apply` from main on
  each host (AGENTS.md). Nothing prunes undeclared paths (residue design §5).
- Capability facts are read only through `tools/harness-facts`; `unknown` is never a
  default. A value change lands as a pair with ops's `claim-guard` constants until
  `tasks-56b450` moves the guard onto the view (residue design §4.7).
- Re-probing follows the README's "Re-probing a fact": both child kinds, three outcomes,
  one commit.
- Codex hook trust is live state on both hosts; a command change costs one re-trust per
  Codex home per host.

## Alternatives

For the open decision, who compares the installed version with the probed one, and
when (`hq-e18255`):

1. **On read.** `harness-facts get` and `lookup` report `stale: true` beside an entry
   whose `version` differs from the installed harness. Every consumer sees it, but a
   read must then run the harness's `--version`, and the guard's read path gains a
   subprocess.
2. **On demand plus a gate.** A `harness-facts stale` command lists entries whose
   probed version trails the installed one; `just test` (or ops-check) reports it as a
   warning. Cheap and explicit, but it only fires when someone runs hq's gates. **Lean.**
3. **On upgrade.** A pacman or npm post-install hook files a re-probe task when a
   harness version changes. Timely, but host-specific and one more piece of host state.

The other three have a lean and are scoped on their tasks: remove the stray skill
(rejected: declaring it, which would duplicate lore's skill on one host only); mirror
the personal home's six skill links in the work home (rejected: leaving the work home
bare, which contradicts the instructions it loads); link lore's and ops's hooks into
`~/.local/bin` from hq's `links.toml` (rejected: ops's own `just install`, since home
routing is declared here), leaving familiar to fam.

## Unanswered questions

1. Does any fact's value change on the installed versions? The answer sets how much a
   staleness check is worth. Answered by `hq-b2515c` (below).
2. Is a version difference stale on any change, or only on a minor or major one? The
   user, once question 1 shows how often values move.
3. Should a stale fact change a consumer's behaviour, or only be reported? The user;
   `unknown` is never a default, so the lean is report only.

## Proposed decomposition

- Goal `hq-72fd4b` holds all of these.
- `hq-b2515c` (research): re-probe the three facts on Claude Code 2.1.294 and Codex
  0.161.0. Wakes `hq-e18255`.
- `hq-e18255` stays an idea until that result; then it is designed from this brief.
- `hq-b5595a`, `hq-ac80cb`, `hq-fe88ef`: scoped `todo`, independent of each other and of
  the research.
