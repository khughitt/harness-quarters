# Path mistakes — brief

Scoped 2026-09-27 from `ai-ae8196`. Evidence: obs `docs/reports/2026-09-26-tool-failure-modes.md`
§2–3 (in the obs checkout), plus direct scans of the Claude Code and Codex session stores
on 2026-09-27, described below.

## Problem

Most of the file-not-found errors the obs report counts are not the working agent getting
lost. They come from two places the agent does not control: a background reviewer that
Claude Code starts in a worktree, and the way Codex is shown the paths of its skills. The
goal is that neither produces a steady stream of failed reads, and that what remains is
the agent's own mistakes, measured by obs.

## Current behaviour and evidence

**Claude Code: the reviewer is the `security-guidance` plugin.** The report's "worktree
session read the main-checkout path" (112), "session started in an already-deleted
worktree" (88), the invented `/home/user/…` root (31) and the 75 Bash errors in a deleted
cwd all come from headless `sdk-py` sessions. Their first prompt is "Review this change
for security vulnerabilities", which is `security-guidance@claude-plugins-official` 2.0.8
(`hooks/llm.py`, `hooks/review_api.py` in the plugin cache), enabled in
`claude/settings.json`. It runs asynchronously on `Stop`, `SubagentStop`, `git commit`
and `git push`, in the session's cwd, on Opus 4.7, and rewakes the session with findings.

- Of 1,131 transcripts whose project directory is a worktree, 1,123 are these reviewer
  sessions; 12,211 of their 12,251 assistant messages are Opus 4.7. Interactive sessions
  almost never start inside a worktree here.
- Every failed Read in those transcripts is the reviewer's: 145 on the main-checkout path
  of a file that exists only on the branch, 87 on its own worktree after it was removed,
  18 on `/home/user/…`.
- It is still running: 52 reviewer sessions in August, 1,283 in September (to 09-27).
- The race: a commit in a worktree starts a review; finishing the branch removes the
  worktree seconds later; the reviewer then starts, or keeps reading, in a directory that
  no longer exists.

So the question the idea asked — does the worktree path rule need restating for the
agent — has no evidence behind it. The rule in AGENTS.md Git is fine as written.

**Codex: skill paths behind aliases and nested directories.** Codex shows skills as
`file: r0/agent-skills/api-and-interface-design/SKILL.md` with a table mapping `r0` to
`ai/agents/skills` (the target of `~/.agents/skills`), `r3` to the superpowers plugin cache
and so on. Agents mis-expand these. Failing paths in the 2026-09 rollouts, by text
occurrence (the same failure appears in more than one record, so these are shares, not
counts):

- The middle directory dropped or added under `r0`: `agents/skills/api-and-interface-design/SKILL.md`
  (170), `documentation-and-adrs` (122), `security-and-hardening` (99), `performance-optimization`
  (24); `agents/skills/agent-skills/tasks/SKILL.md` (52) for a skill that is at the top level.
  `agents/skills/` nests `agent-skills/<skill>/` and `superpowers/skills/<skill>/` beside
  top-level links (`tasks`, `flow`, …).
- The alias kept literally: `agents/skills/r0/…`, `r3/…`, `r4/…` (about 100).
- A superseded plugin version: `superpowers/6.3.0/…` and `ponytail/4.9.0/…` after Codex
  replaced them with 6.4.2 and 4.10.0 (about 150), and ponytail looked up under the wrong
  marketplace directory (`openai-curated-remote/ponytail`, about 30).
- A skill's own relative reference resolved against the wrong base:
  `superpowers/<v>/skills/references/codex-tools.md`, `skills/writing-good-tests.md` (about 150).

Superpowers is listed twice in Codex: from the `agents/skills/superpowers` submodule
(pinned at v6.3.0, commit `6cd51ba`) under `r0`, and from the Codex plugin (6.4.2) under `r3`.
`codex/rules/default.rules:107` still allows a `superpowers/6.3.0/…/review-package` path
that no longer exists.

## Constraints

- `agents/skills/README.md` defines the layout: `~/.agents/skills` links to `agents/skills`,
  the skill directory for every harness other than Claude Code; the superpowers submodule
  is kept on the Claude plugin's version.
- The `security-guidance` plugin is upstream (Anthropic's official marketplace); ai can
  only enable, disable or configure it.
- Codex's alias rendering, plugin-cache replacement and relative-reference resolution are
  upstream Codex behaviour.
- obs-18b8eb (todo, obs) will label file-not-found by path relation at index time; that is
  where any fix is measured.
- ai-7349c4 (todo) will shrink the worktree rule once ops-09a86b lands; nothing here
  changes that bullet.

## Alternatives

For the reviewer:

- **A. Disable `security-guidance`.** Removes every reviewer failure and about 1,300
  Opus 4.7 sessions a month. Loses whatever its findings catch.
- **B. Keep it and report upstream**: the review should run against the commit, not a
  live cwd, and must not start in a removed directory.
- **C. Keep it and hold worktree removal until the review returns.** An instruction in the
  finishing step; the review's latency then lands on every branch finish.

Lean: decide on what it catches. If its findings rarely changed code, A; otherwise B, and
not C.

**Measured 2026-09-27 (ai-3b2222): A, done in `8d701d6`.** Across the whole Claude Code store
(2026-08 → 09-27) the reviewer ran 1,335 sessions (52 in August, 1,283 in September),
6,728 requests, 5.0M output tokens, 251M cache-read and 49M cache-write tokens: about
$556 at Opus 4.7 list prices. The plugin blanks the OAuth token whenever
`ANTHROPIC_API_KEY` is set (`_agentic_spawn_env` in `hooks/llm.py`), and it is set in the
session environment here, so this was most likely billed to that API key rather than to
the subscription; billing itself was not checked. 15 sessions
returned any candidate finding; one reached a working session (2026-09-21, "terminal
escape injection in `bin/host-load`"), and that session fixed it as ops `64fddd4`, a
low-severity hardening of a local tool. Even that rewake arrived with its findings body
replaced by an auth-source warning; only the one-line summary survived. The plugin's own
log (`~/.claude/security/log.txt`) keeps about 15 hours; in that window 128 reviews all
reported nothing. One minor fix in seven weeks does not pay for the cost and the
failure noise. Disabling also removes the plugin's regex warnings on edits, which are the
same plugin.

For Codex skills:

- **D. Flatten `agents/skills`**: every skill directly under it, so the path an agent
  guesses is the real one; take superpowers out of it where Codex already has the plugin.
- **E. Leave the layout** and report the alias mis-expansion upstream.

Lean: D, after checking which harnesses read `~/.agents/skills` and that Codex lists a
flat layout once. The superseded-version and relative-reference failures stay upstream
reports either way.

**Checked 2026-09-27 (ai-929d4f): D, with superpowers from the pinned submodule.**

- Readers of `~/.agents/skills`: Codex (root `r0`), Crush (its binary names
  `.agents/skills`; `dotfiles/crush/patch_skills_user_invocable.py` patches that directory)
  and OpenCode (a recursive `**/SKILL.md` scan). Both were used in September. Neither gets
  superpowers any other way, so the submodule cannot simply go.
- A flat entry already renders correctly: the top-level links (`tasks`, `flow`, `scope`, …)
  appear as `r0/<name>/SKILL.md`. Codex follows symlinked skill directories and recurses
  into nested ones.
- `codex debug prompt-input` renders the catalog with no model call. With
  `-c 'skills.config=[{path="<…>/SKILL.md", enabled=false}]'` the entry disappears
  (38 → 37); a directory path hides nothing. The remote superpowers plugin (`r3`) is not
  in that render, only in live sessions.
- The three superpowers copies have drifted: the submodule is at v6.3.0, the Claude plugin
  at 6.4.1, the Codex plugin at 6.4.2. The README's "keep the submodule on the Claude
  plugin's version" has not held.
- The vendored agent-skills cite `../../references/<file>.md`, which from
  `agents/skills/agent-skills/<skill>/` resolves to a missing `agents/skills/references/`:
  the vendoring dropped upstream's `skills/` level. That is the
  `agents/skills/references/security-checklist.md` failure in the list above.

Recommendation: every skill directly under `agents/skills`; the vendored references move
to one shared directory with the links rewritten to match; superpowers comes from the
submodule alone, bumped to the Claude plugin's version, with the Codex remote plugin
disabled. One pinned copy then serves Codex, OpenCode and Crush at a path that changes
only on a deliberate bump, which also ends the superseded-version failures for
superpowers. The rejected alternative, keeping the Codex plugin and hiding the 14
submodule entries through `skills.config`, keeps a copy that updates itself
mid-session and a 14-path list to maintain. The stale `superpowers/6.3.0` allow rule in
`codex/rules/default.rules` goes with it. Literal-alias and skill-relative-reference
misreads stay upstream Codex issues.

## Unanswered questions

- Keep or disable the security reviewer? *Measured by ai-3b2222 (above): lean disable;
  the user decides.*
- Which harnesses read `~/.agents/skills`, and does a flat layout list once? *Answered by
  ai-929d4f (above).*
- Whether to file the Codex and plugin behaviour upstream. *The user; outside the
  repository. Plugin side filed 2026-09-27: claude-plugins-official#6320 (worktree-removal
  race), +1 on #4960 (findings body) and #4693 (invented roots), comment on
  claude-code#96860 (API-key billing). Codex alias mis-expansion and skill-relative
  references are not yet reported.*

## Proposed decomposition

| Task | What | Waiting |
|---|---|---|
| ai-3b2222 | Measure the security reviewer's cost and what its findings changed (done; disabled in `8d701d6`) | ai-ae8196 |
| ai-929d4f | Check who reads `~/.agents/skills` and whether a flat layout lists once in Codex (done) | ai-ae8196 |
| ai-cea269 | Flatten `agents/skills`; superpowers from the pinned submodule alone (done; `f4f1a94`, `86c3c77`) | — |

Parent goal: ai-e2ed51. Rescoped 2026-09-27: every question ai-ae8196 asked is answered
and its fixes have landed, so it is proposed for drop. The goal closes on measurement:
it depends on obs-18b8eb, whose path-relation labels should show reviewer and Codex
skill-path file-not-found near zero after 2026-09-27.
