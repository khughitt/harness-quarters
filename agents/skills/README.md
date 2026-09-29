# agents/skills

`~/.agents/skills` symlinks here; it is the skill directory for every harness other
than Claude Code, which reads skills from `~/.claude/skills` and plugins from its own
cache. Its readers are Codex (shown as root `r0`), OpenCode (a recursive `**/SKILL.md`
scan) and Crush (dotfiles' `crush/patch_skills_user_invocable.py` patches the
directory for its command palette).

The layout is flat: every skill sits directly at `agents/skills/<name>/SKILL.md`, as a
directory or a symlink to one. Codex shows each as `r0/<name>/SKILL.md`, and a flat path
is the one an agent guesses; nested skill directories were read back with a level
dropped or added. Keep new skills at this depth.

- `tasks`, `curate`, `scope`, `quick-add` — symlinks into the tasks and ops checkouts,
  so the skills those repositories ship are always the checked-out version. A new skill
  needs a link here and one under `~/.claude/skills`; nothing creates them (tasks-ffa10e).
- `flow/` — the explicit task state machine (states, gates, `gate:` notes) and
  its walker; `agents/bin/flow-state` derives a task's state. Linked from
  `~/.claude/skills/flow` like the others.
- `session-logs/` — where each harness keeps its session store, how to read it,
  and the `agents/bin/session-episodes` tool that prepares pre-flow episodes for
  obs. Linked from `~/.claude/skills/session-logs` like the others.
- `api-and-interface-design/`, `code-simplification/`, `context-engineering/`,
  `documentation-and-adrs/`, `observability-and-instrumentation/`,
  `performance-optimization/`, `security-and-hardening/` — vendored copies from
  addyosmani/agent-skills. Their shared checklists live in `references/` (not a skill;
  `references/source.md` names the origin), cited from a skill as `../references/<file>.md`.
- The superpowers skills (`brainstorming`, `writing-plans`, … one symlink per skill) —
  links into `agents/vendor/superpowers/skills/`, a git submodule of obra/superpowers
  pinned at a release tag. This is the only superpowers copy the non-Claude harnesses
  see: the Codex remote plugin `superpowers@openai-curated-remote` is uninstalled
  (`codex plugin remove`). A `[plugins.…] enabled = false` entry does not hide a remote
  plugin, whose install state syncs from the account; if it returns, remove it again.
  Claude Code loads superpowers as the `superpowers@claude-plugins-official` plugin, so
  keep the submodule on the same version as the installed plugin (`~/.claude/plugins/installed_plugins.json`)
  or the two harnesses run different skills. Bump with
  `git -C agents/vendor/superpowers checkout <tag>` and commit the pointer; when the
  release adds or removes a skill, add or remove its link here
  (`ln -s ../vendor/superpowers/skills/<name> agents/skills/<name>`). On a fresh clone,
  `git submodule update --init`.

Profile fragments — the instructions that differ between kinds of project —
live beside this directory in `agents/profiles/`, one file per profile. ops
`profiles.toml` names them and `ops-profile session` prints the ones a
checkout selects; the design is `docs/specs/2026-09-19-project-profiles-design.md`.
