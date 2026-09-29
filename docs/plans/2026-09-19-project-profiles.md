# Project Profiles (ai side) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the instruction fragments, hook registration, and global-prose changes that give every session a declared project profile.

**Architecture:** ai owns the text and the harness wiring; ops owns resolution and enforcement (its own plan, `ops` `docs/plans/2026-09-19-project-profiles.md`). The two plans interleave: ai Task 1 lands before ops validates fragments; ai Task 2 lands after ops ships the `claude-profile` hook; ai Task 3 (the enforcement check) runs after ops's hook reads the resolver; ai Task 4 removes prose only after Task 3 has passed and `ops-profile` resolves on PATH. Every harness home symlinks to the tracked files here, so a change is live in every home once it is on `main`.

**Tech Stack:** Markdown, JSON (Claude Code settings), TOML (Codex config). No code in this repository changes.

**Spec:** `docs/specs/2026-09-19-project-profiles-design.md`

## Global Constraints

- Fragments are plain markdown, one file per profile, `agents/profiles/<name>.md`, no frontmatter, no includes (spec §5).
- The `## Profiles` section in `AGENTS.md` is the text in spec §7.2, verbatim.
- Hook commands in settings files are written `~/d/ops/hooks/<name>`, matching the existing entries.
- No path under the user's home or the Dropbox mount appears in a fragment or in `AGENTS.md` prose.
- Task 4 removes prose only after Task 3's enforcement check has passed and `ops-profile` is callable from a directory that is no checkout.
- No live check may be able to reach GitHub: work-home probes run with a tokenless `GH_CONFIG_DIR` and a stub `gh` (Task 3).
- Commits use conventional-commit subjects; no attribution trailers.

---

### Task 1: The three profile fragments

**Files:**
- Create: `agents/profiles/personal.md`
- Create: `agents/profiles/work.md`
- Create: `agents/profiles/external.md`
- Modify: `agents/skills/README.md` (one paragraph pointing at `agents/profiles/`)

**Interfaces:**
- Produces: the files ops `profiles.toml` names by `fragment = "<name>"` and ops `ops-profile session` prints. ops resolves the ai root through the tasks registry, so these must be on ai `main` before ops's fragment check exists (ops Task 3).

- [ ] **Step 1: Write `agents/profiles/personal.md`**

```markdown
# Profile: personal

A repository the user maintains for themself. Design specs and implementation
plans are committed by default, under the convention the repository documents
(`docs/specs/` and `docs/plans/` unless its own instructions name another
place); the `docs/superpowers/` default of the brainstorming and writing-plans
skills is never the right directory here. Pull requests, where the repository
uses them, need no draft. GitHub writes use the `khughitt` account: check
`gh auth status` before a write and `gh auth switch --user khughitt` when the
active account differs — the active account is global state and is often the
other one.
```

- [ ] **Step 2: Write `agents/profiles/work.md`**

```markdown
# Profile: work

A repository worked under the work account. Design specs and plans stay out of
the tree unless the repository's own instructions ask for them: write the doc
at the skill's path, add that path to `.git/info/exclude`, and copy it out
before removing a worktree. GitHub writes use the `<work-account>` account:
check `gh auth status` before a write and `gh auth switch --user <work-account>`
when the active account differs. The repository's own guidelines decide
branch, commit, and review conventions.
```

- [ ] **Step 3: Write `agents/profiles/external.md`**

```markdown
# Profile: external

A repository the user does not maintain: an upstream project, a fork, a clone
outside the registry. Before any other work, read its contributor guidelines —
`CONTRIBUTING` in any casing at the root, under `.github/`, or under `docs/`;
developer or hacking guides; `.github/PULL_REQUEST_TEMPLATE.md` or
`PULL_REQUEST_TEMPLATE/*`; any repo-level `AGENTS.md` or `CLAUDE.md` — and
search its open and closed PRs and issues (`gh pr list --state all --search`,
`gh issue list --state all --search`). On a duplicate or a prior closed
attempt, stop and tell the user; otherwise reference what was found and link
the issue the PR fixes. The guidelines decide everything: attribution only
where and how they explicitly ask, and the branch, commits, PR title, base
branch, template sections filled with real content, sign-off, changelog
entries, and tests. Every PR is a draft (`gh pr create --draft`; the user
promotes it); `--body` replaces the template, so prefer `--body-file` from a
filled copy. When a convention cannot be met, say so instead of opening a PR
that violates it. Design specs and plans stay out of the tree: write them at
the skill's path, add that path to `.git/info/exclude`, and copy them out
before removing a worktree. GitHub writes use the `khughitt` account.
```

- [ ] **Step 4: Point the skills README at the fragments**

Append to `agents/skills/README.md`:

```markdown

Profile fragments — the instructions that differ between kinds of project —
live beside this directory in `agents/profiles/`, one file per profile. ops
`profiles.toml` names them and `ops-profile session` prints the ones a
checkout selects; the design is `docs/specs/2026-09-19-project-profiles-design.md`.
```

- [ ] **Step 5: Check the constraints**

Run: `grep -n "/home/\|Dropbox" agents/profiles/*.md; head -1 agents/profiles/*.md`
Expected: the grep prints nothing; each file's first line is `# Profile: <name>`.

- [ ] **Step 6: Commit**

```bash
git add agents/profiles agents/skills/README.md
git commit -m "feat(profiles): personal, work, and external instruction fragments"
```

Then merge to `main` (fast-forward from the worktree branch) before ops Task 3 runs, since ops validates fragments through ai's registered root.

---

### Task 2: Register the hooks in both homes and add the Profiles section

**Files:**
- Modify: `claude/settings.json` (`hooks.SessionStart`: one more entry)
- Modify: `claude/settings.work.json` (`hooks.SessionStart` and `hooks.PreToolUse`: one more entry each)
- Modify: `AGENTS.md` (new `## Profiles` section after `## Git`)

**Interfaces:**
- Consumes: ops `hooks/claude-profile` (ops Task 4) and `hooks/claude-pretooluse`, both on ops `main` — the settings entries name `~/d/ops/hooks/...`, the main checkout.
- Produces: a `profile:` line in every Claude Code session in either home.

- [ ] **Step 1: Confirm the ops hook exists on ops main**

Run: `test -x ~/d/ops/hooks/claude-profile && git -C ~/d/ops log --oneline -1 -- hooks/claude-profile`
Expected: one commit line. If the file is missing, stop: ops Task 4 has not merged.

- [ ] **Step 2: Add the SessionStart entry to `claude/settings.json`**

In `hooks.SessionStart`, after the `claude-provenance` entry, add:

```json
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "~/d/ops/hooks/claude-profile"
          }
        ]
      }
```

- [ ] **Step 3: Add both entries to `claude/settings.work.json`**

In `hooks.SessionStart`, after the existing Familiar entry, add the same `claude-profile` entry as Step 2. In `hooks.PreToolUse`, after the Familiar entry, add:

```json
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/d/ops/hooks/claude-pretooluse"
          }
        ]
      }
```

- [ ] **Step 4: Validate both files parse and carry the entries**

Run:
```bash
for f in claude/settings.json claude/settings.work.json; do
  jq -e '[.hooks.SessionStart[].hooks[].command] | index("~/d/ops/hooks/claude-profile")' $f >/dev/null && echo "$f: profile hook ok"
done
jq -e '[.hooks.PreToolUse[].hooks[].command] | index("~/d/ops/hooks/claude-pretooluse")' claude/settings.work.json >/dev/null && echo "work: pretooluse ok"
```
Expected: three `ok` lines.

- [ ] **Step 5: Add the `## Profiles` section to `AGENTS.md`**

Insert after the `## Git` section (before `## Design & Plan Docs`), leaving every existing sentence in place:

```markdown
## Profiles

Every checkout has a profile — `personal`, `work`, `external`, or one the user
defined — that carries the instructions and settings that differ between
kinds of project. Your session starts with a `profile:` line followed by the
profile's instructions; if it did not, run `ops-profile session` and read
its output before any other work — the profile says what to read and do
before touching a repository. Later layers win: core, then the profile, then
this repository's own instructions, then the user in the session.
```

- [ ] **Step 6: Run the ai pre-commit check and commit**

```bash
python3 .githooks/pre-commit || true   # the projects block is untouched; expect no output
git add claude/settings.json claude/settings.work.json AGENTS.md
git commit -m "feat(profiles): register the profile and pretooluse hooks in both homes; Profiles section"
```

Merge to `main`. The symlinks make it live at the next session start.

- [ ] **Step 7: Live check, personal home**

Start a Claude Code session in `~/d/ai` and one in `/tmp` (clone anything unregistered there first, e.g. `git clone --depth 1 https://github.com/obra/superpowers /tmp/superpowers-probe`). In each, the first turn's context must contain a line starting `profile:`. Record in the task note: the two lines verbatim (expected `profile: personal (identity.toml [ai].profiles); …` and `profile: external (profiles.toml default); …`).

- [ ] **Step 8: Live check, work home — both hooks fire**

Run `clw` in `~/d/<work>/<repo>`. Confirm the line `profile: work (identity.toml [rad].profiles); home: work; …`. Then, in a scratch repository (`tmp=$(mktemp -d); git -C $tmp init -q`), ask the session to run `git -C $tmp commit --allow-empty -m "probe" -m "Claude-Session: https://claude.ai/code/session_probe"`: the attribution check (hook check 3, which exists today) must refuse it with `claude-pretooluse: refusing to write an AI attribution line`. That proves `claude-pretooluse` is registered and running in the work home; profile-aware refusals are not tested here because they arrive with ops Task 5 (Task 3 below covers them). Record both observations in the task note. Nothing here contacts GitHub.

---

### Task 3: Profile-aware enforcement check in the work home

**Files:**
- None changed; the deliverable is the recorded observation on this task.

**Interfaces:**
- Consumes: ops Task 5 on ops `main` (`grep -c ops-profile ~/d/ops/hooks/claude-pretooluse` ≥ 1) and Task 2's note. Do not start otherwise.
- Produces: the proof spec §5 asks for — the profile-aware account refusal running in the work home — without any real `gh` write being possible.

- [ ] **Step 1: Build a disposable gh**

The hook reads the active account from `$GH_CONFIG_DIR/hosts.yml` and never calls `gh` for the account check, so a config dir with no tokens and a stub `gh` on PATH make a real write impossible whatever the guard does:

```bash
probe=$(mktemp -d)
mkdir -p $probe/gh $probe/bin
cat > $probe/gh/hosts.yml <<'EOF2'
github.com:
    users:
        khughitt:
            oauth_token: none
        <work-account>:
            oauth_token: none
    git_protocol: ssh
    user: khughitt
EOF2
cat > $probe/bin/gh <<'EOF2'
#!/bin/sh
echo "STUB GH CALLED: $*" >> "$(dirname "$0")/../calls.log"
exit 1
EOF2
chmod +x $probe/bin/gh
echo $probe
```

- [ ] **Step 2: Start the work home with the stub in front**

```bash
(
  unset GH_TOKEN GITHUB_TOKEN
  cd ~/d/<work>/<repo>
  GH_CONFIG_DIR="$probe/gh" PATH="$probe/bin:$PATH" clw
)
```

`clw` is a shell alias, so it is launched from a subshell rather than through `env`, which cannot expand aliases. `GH_TOKEN` or `GITHUB_TOKEN` in the environment makes the hook's `active_account()` ignore the hosts file (a token overrides it), so both are unset first.

In the session say, verbatim: *This is a hook probe. Run exactly one command, `gh issue comment 1 --body probe`, and show me the exact response. Do not run `gh auth status`, do not switch accounts, and do not run anything else first.* The instructions the session loaded tell it to check the account before a write; the probe overrides that for one command, otherwise the preflight itself would reach the stub and spoil the assertion below. Expected: a `claude-pretooluse` refusal naming `profile work (identity.toml [rad].profiles)` and `<work-account>`, and `$probe/calls.log` does not exist afterwards (the stub was never reached). If `calls.log` exists, read it: a `gh auth status` line means the agent ran the preflight anyway — repeat the instruction; a `gh issue comment` line means the guard did not run — stop, that is a failure of Task 2. Then ask it to run `gh pr view 1`: the stub is reached (`calls.log` gains one line, exit 1) — reads are not guarded.

- [ ] **Step 3: Record and clean up**

Paste the refusal text and `ls $probe/calls.log` output (or its absence after the first command) into the task note, then `rm -rf $probe`. Nothing in `~/.config/gh` was touched and no GitHub request was made.

---

### Task 4: Remove the profile-specific prose from the global file

**Files:**
- Modify: `AGENTS.md` (`## Git` bullets 2 and 3; `## Design & Plan Docs`)
- Modify: `codex/config.toml` (`developer_instructions`)
- Modify: `README.md` (one sentence)

**Interfaces:**
- Consumes: Task 3 recorded as passed; `ops-profile` on PATH (ops Task 2 Step 6 ran `just install` in the ops main checkout). Do not start otherwise: the removed sentences are the only guard until then, and the new prose names a command that must resolve.

- [ ] **Step 1: Confirm the preconditions**

Run: `tasks show <the Task 3 id> --pretty | grep -c "<work-account>"; cd /tmp && command -v ops-profile && ops-profile explain ~/d/ai | head -3`
Expected: a count ≥ 1; then `~/.local/bin/ops-profile` (or wherever `just install` linked it) and the first lines of an explanation from a directory that is no checkout. If the command is missing, run `cd ~/d/ops && just install` and retry; if that recipe is missing, ops Task 2 is not on ops `main`: stop.

- [ ] **Step 2: Rewrite the Git section**

Replace the second and third bullets of `## Git` (the "No AI attribution by default…" bullet and the "`gh` is logged in to two accounts…" bullet) with:

```markdown
- No AI attribution by default: no attribution trailer, co-author line, or footer on commits, PRs, or comments, and harness-injected forms (`Claude-Session:`, a session URL, "Generated with Claude Code") stay out everywhere. The profile says which `gh` account a checkout uses and what a repository you do not maintain requires before a PR; `gh` holds two accounts and the active one is global state, so check `gh auth status` before any `gh` write.
```

Leave the first bullet (conventional commits), the worktree bullet, the path-reporting bullet, and the home-path bullet unchanged.

- [ ] **Step 3: Rewrite the Design & Plan Docs section**

Replace the whole section body with:

```markdown
- Whether design specs and plans are committed is the profile's call; the repository's own instructions override it, and the hook that guards staging names both.
- Verify document status against the code before relying on it; update it and related docs when work lands.
```

- [ ] **Step 4: Empty the Codex developer instructions**

In `codex/config.toml`, replace the `developer_instructions = """…"""` block with:

```toml
# codex-specific instructions: none; the profile fragments carry the per-project rules.
developer_instructions = ""
```

- [ ] **Step 5: README sentence**

In `README.md`, after the first paragraph, add:

```markdown
Per-project profiles (`agents/profiles/`) carry what differs between personal,
work, and external checkouts; ops resolves which applies
(`docs/specs/2026-09-19-project-profiles-design.md`).
```

- [ ] **Step 6: Word count and constraint check**

Run: `wc -w AGENTS.md; grep -n "<work-account>\|docs/superpowers\|<work>/" AGENTS.md`
Expected: the grep prints nothing (the account and directory names now live only in fragments and ops). Record the before/after word count in the closing note (before: the count on `main` at the time of Task 2's merge).

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md codex/config.toml README.md
git commit -m "docs(rules): profile fragments carry the per-project rules; global prose shrinks"
```

Merge to `main`; start one session in `~/d/ai` and confirm the profile line still appears and the Git section reads as written.
