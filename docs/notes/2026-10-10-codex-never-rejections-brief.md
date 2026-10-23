# Codex rejections under approval_policy = never — brief

Ideas: hq-48c5c6 (git-index unstaging rejected), hq-982164 (forced-remove cleanup
rejected), hq-5b8413 (conflict-resolution restore rejected). Scoped 2026-10-10;
hq-5b8413 added 2026-10-11; hq-52e1d9 (a third unstaging refusal) added 2026-10-17.

## 1. Problem

Codex runs here with `approval_policy = "never"`, so any command that some layer
marks "needs approval" is refused outright. Two reports from 2026-10-10 describe
refusals of safe, owned operations — unstaging a path from the index, and removing an
obsolete lock file — and a third that evening, taking the incoming side of a merge
conflict, where the rejection did not say which form would have been
accepted. Agents find a workaround by trial (an owned companion commit; an explicit
file deletion), which costs turns and teaches nothing durable. The outcome wanted: a
refusal is either intended by a rule hq owns and names the permitted alternative, or
it is an upstream behaviour recorded and worked around once.

## 2. Current behaviour and evidence

- `codex/config.toml:3` sets `approval_policy = "never"`; `approvals_reviewer = "user"`.
- `local/codex/rules/default.rules` (untracked, linked to `~/.codex/rules` by
  `links.toml:106`) holds 111 `prefix_rule` lines, almost all `allow`. Line 45 is
  `prefix_rule(pattern=["git", "restore"], decision="prompt")`. Under `never`, a
  `prompt` decision is a rejection.
- The installed Codex (0.162.1) carries the message "approval required by policy, but
  AskForApproval is set to Never", matching hq-48c5c6's wording. If the unstaging was
  `git restore --staged <path>`, line 45 is the likely rejecting rule.
- Session logs (read 2026-10-11) confirm both `git restore` commands. hq-48c5c6:
  `git restore --staged -- README.md tasks/ops-b46491.md` (rejected 15:22:47Z).
  hq-5b8413: `git restore --source=MERGE_HEAD --staged --worktree tools/README.md` in
  a mindful worktree mid-merge (rejected 20:29:35Z). Both carry the same message and
  match line 45, the only `prompt` rule; that it is the rule rather than a built-in
  check is still to be shown by the probe. The second form overwrites the working
  file, so the guard did its job there; what failed is the message, which names
  neither the risk nor an accepted form.
- The refusal recurs on Codex 0.163.0. hq-52e1d9 (crew, 2026-10-16) is a third
  instance: `git restore --staged docs/reports/cheap-model-pilot/round-1.json` in a
  crew worktree, refused twice (16:36:50Z, chained with `tasks park`; 16:38:50Z alone)
  with the same message, matching line 45. The agent described it as "automatic
  approval review", but `approvals_reviewer = "user"` and the error is the exec
  policy's `Rejected(...)` from `CreateProcess`; it worked around by keeping the
  artifact staged and repairing it in place.
- Codex's exec policy resolves overlapping rules to the strictest decision, so an
  `allow` for `["git", "restore", "--staged"]` cannot carve an exception out of the
  `prompt` on `["git", "restore"]` (confirmed by the probe below). The binary
  shows `prefix_rule` accepts a `justification`; under `never` the probe found that a
  `prompt` rule's text never reaches the agent, while a `forbidden` rule's does.
- hq-982164 is the forced-`rm` refusal already reported three times in ops
  (ops-75b29a canonical, ops-7933db, ops-97a39d) and once in lore (lore-304804, which
  attributes it to Codex's built-in exec policy refusing any forced `rm` under
  `never`). Open research ops-278533 identifies the rejecting layer and intended
  policy for those events; brief: ops `docs/notes/2026-09-30-adaptive-hook-messages-brief.md`.
- hq-1d228b (relay, 2026-10-17, Codex 0.163.0) is another forced-`rm` refusal: a
  `trap 'rm -rf "$tmp"' EXIT` around a `mktemp -d` test run was rejected with "rm -f
  style commands are not permitted. Use a safer approach"; `python3 shutil.rmtree` in
  the trap passed. That string occurs in the installed Codex binary and in no hook,
  rule or relay source here, so for this event the rejecting layer is Codex's built-in
  check. Proposed as a drop covered by ops-75b29a and ops-278533, like hq-982164.

### Probe results (hq-748431, 2026-10-22, Codex 0.163.0)

Method: `codex execpolicy check` against copies of the live rules (as is, without
line 45, with a `["git", "restore", "--staged"]` allow added, and with a
justification on line 45); `codex sandbox -P workspace-local` running each form in
throwaway repositories under a temporary `CODEX_HOME` that holds a copy of the
`workspace-local` profile (no model and no auth involved); and a read of
`codex-rs/core/src/exec_policy.rs`, `exec_policy_tests.rs`,
`shell-command/src/command_safety/is_dangerous_command.rs` and
`shell-command/src/bash.rs` at tag `rust-v0.163.0`.

- **The rejecting layer is line 45.** Both refused commands match only
  `["git", "restore"]` → `prompt`. Under `never`, a command whose decision comes from
  a `prompt` rule becomes `Forbidden` with the fixed `PROMPT_CONFLICT_REASON`. The
  built-in dangerous-command check on Linux flags only forced `rm` (and its wrappers),
  so no built-in check touches any `git` form; with line 45 removed, every form is
  unmatched and, under `never`, allowed to run inside the sandbox.
- **Strictest wins, so no carve-out.** With an `allow` for
  `["git", "restore", "--staged"]` added, `git restore --staged -- f` matches both
  rules and resolves to `prompt`.
- **A `prompt` rule's justification never reaches the agent under `never`.** The
  parser accepts it and `execpolicy check` shows it, but the `never` branch returns the
  fixed reason and drops it; the justification is only used when a prompt is actually
  shown. Upstream's test `exec_approval_requirement_respects_approval_policy` pins
  that message. A `forbidden` rule's justification is shown:
  `` `<cmd>` rejected: <justification> `` (pinned by
  `justification_is_included_in_forbidden_exec_approval_requirement`).
- **A command that no rule matches runs in the sandbox; one that only `allow` rules
  match skips it** (`bypass_sandbox` holds only when every parsed segment is
  explicitly allowed). This is why `git add` and `git commit` work everywhere.
- **The sandbox refuses index writes in a linked worktree.** A worktree's admin
  directory (`<main>/.git/worktrees/<name>/`, which holds its index) sits outside the
  profile's writable roots unless the main checkout is one of the five
  `workspace_roots` given `.git = "write"`. In that layout (all three refusals were in
  worktrees: ops, mindful and crew) every unmatched index write fails with
  `Unable to create '…/index.lock': Read-only file system`: `git reset -q -- <path>`,
  `git rm --cached`, `git checkout MERGE_HEAD -- <path>`, and
  `git show MERGE_HEAD:<path> > <path> && git add <path>`. Only the file write,
  `git show MERGE_HEAD:<path> > <path>` on its own, succeeds (but truncates `<path>`
  first, so it is not a safe form; see §4). In a main checkout every
  form passes. On this host, 563 Codex rollout files contain that `index.lock` error
  (from `git rm`, `git apply --cached` and chained `git -C … commit && …`, among
  others), so worktree sessions hit it routinely.
- **A redirection keeps a script from being split.** `bash.rs` rejects redirections,
  so `git show X:p > p && git add p` is judged as one unmatched `bash -lc` script and
  runs entirely in the sandbox. Issued as two calls, `git add p` matches its allow
  rule and skips the sandbox. (Review of hq-748431 found the redirect form unsafe;
  §4 gives the temporary-file form.)
- **Upstream.** openai/codex#41068 (open, 2026-08-27) reports the same dead end
  (`prompt` rules hard-rejected under `never`, a message naming neither the rule nor an
  action) and asks, among other remedies, for the matched rule and guidance. It covers
  this report; nothing new to file.
- Aside, out of scope here: `git reset --hard`, `git checkout -- <path>` and
  `git clean` match no rule, so under `never` they run unprompted in a main checkout
  (the sandbox allows writes there). Line 45 guards only `git restore`.

## 3. Constraints

- `local/` stays untracked (AGENTS.md); a rules change is a host-local edit, and the
  second host needs the same edit by hand.
- Codex's built-in safety checks and their messages are upstream code: an upstream
  search precedes any report or workaround (global Feedback rules).
- `git restore <path>` without `--staged` discards uncommitted work irreversibly; the
  `prompt` rule exists to stop exactly that.
- Do not equate a successful alternative command with authorization (ops-278533's
  framing applies here too).

## 4. Alternatives

1. **Keep the rule, add a justification** (superseded by 4; the forms listed here are
   unsafe as written, see 4) naming the permitted forms
   (`git restore --staged` is not among them; use `git reset -q -- <path>` or
   `git rm --cached` to unstage, and `git checkout MERGE_HEAD -- <path>` or
   `git show MERGE_HEAD:<path> > <path>` plus `git add` to take a conflict side), if
   the justification reaches the agent and those forms pass.
2. **Narrow the rule**: replace the blanket `git restore` prompt with prompts on the
   destructive shapes only, if prefix patterns can express them (they match leading
   tokens, so `git restore <path>` and `git restore --staged <path>` share a prefix —
   probably not expressible).
3. **Drop the rule** and rely on agents' instructions to avoid discarding work.
   Rejected for now: it removes the only mechanical guard on an irreversible command.

4. **Forbid with a justification, and allow the index-only forms** (added after the
   hq-748431 probe, revised by hq-499318 after two review rounds). Change line 45 to
   `decision="forbidden"` with a justification that names the permitted forms, and add
   `allow` rules, each ending in the option terminator `--`, so those forms skip the
   sandbox and can write a worktree's index:

   ```
   prefix_rule(pattern=["git", "restore"], decision="forbidden", justification="git restore can overwrite uncommitted work. To unstage, run git reset -q -- <path>; for a newly added file, git rm --cached -- <path> also works. To take one side of a conflict, write git show :3:./<path> (theirs; :2:./<path> for ours) to a temporary file and, only if that succeeds, copy it over the file: tmp=$(mktemp) && git show :3:./<path> > \"$tmp\" && cp \"$tmp\" \"<path>\" && rm \"$tmp\". Then run git add <path> as its own command.")
   prefix_rule(pattern=["git", "reset", "-q", "--"], decision="allow")
   prefix_rule(pattern=["git", "rm", "--cached", "--"], decision="allow")
   ```

   Why each detail is there:
   - The terminator in both allows: a prefix rule matches leading tokens and ignores
     what follows, so an unterminated `["git", "rm", "--cached"]` also allows
     `git rm --cached --no-cached -f -- <path>`, which deletes the working file,
     uncommitted content included (reproduced by review round 1 of hq-748431 and by
     hq-499318). After `--`, git reads everything as a pathspec, so no later option
     can widen either command. A wide pathspec still can (`git rm --cached -- ':(top)*'`
     stages the deletion of every file), but only in the index.
   - `git reset -q -- <path>` is the unstaging form: it unstages a tracked file and a
     new file alike, with or without a first commit, and leaves the working file
     intact. `git rm --cached -- <path>` is offered for new files only: on a tracked
     file it stages a deletion rather than an unstage (`D` plus `??`, whether or not the
     edit was staged), which a following `git commit` would land; on a new file with
     edits on top of what is staged it refuses (exit 1, nothing lost).
   - The stage path `:3:./<path>`: `MERGE_HEAD:<path>` is read from the repository
     root and exists only during a merge, so run from a subdirectory it silently copied
     a same-named top-level file (reproduced). `:3:` (the incoming side: theirs in a
     merge, the commit being replayed in a rebase or cherry-pick) and `:2:` (the
     current side) read the conflicted index entry, and `./` makes the path relative
     to the current directory, which is how `git status` prints it there.
   - The temporary file: `git show … > <path>` truncates the destination before git
     runs, so a wrong or missing source leaves it empty (reproduced). Written to a
     temporary file first, a failed `git show` stops the chain and leaves the file
     untouched (the temporary file is left behind). `cp` onto an existing file keeps
     its mode (probed with an executable file). The chain has a redirection, so Codex
     runs it whole in the sandbox, where both the temporary file and the worktree file
     are writable (probed with `TMPDIR` unset and set).
   - `git add <path>` as its own command: alone it matches its `allow` rule and skips
     the sandbox; chained after a redirection it would run sandboxed and fail on a
     worktree's read-only index.
   - Limits of the conflict form: it suits regular files. `cp` writes through a
     symlink at `<path>`; `git show` writes the repository form, so an `eol` or LFS
     filter leaves the working copy in that form (the staged content is still right);
     and a file deleted on the taken side fails safely without saying that `git rm`
     is the way to take the deletion.

   `execpolicy check` on that set (Codex 0.164.0): every `git restore` form resolves to
   `forbidden` and carries the text; `git reset -q -- <path>`, `git rm --cached -- <path>`
   and `git rm --cached -- --no-cached -f <path>` (pathspecs only) resolve to `allow`;
   `git rm --cached --no-cached -f -- <path>`, `git rm --cached -f -- <path>`,
   `git rm --cached <path>`, `git reset --hard` and `git reset -q --hard` match
   nothing, so they keep today's behaviour (sandboxed under `never`). `execpolicy
   check` does not split a `bash -lc` script, so it says nothing about the chained
   conflict form; that rests on `bash.rs` and the sandbox probe. Under `never`,
   `forbidden` and `prompt` refuse alike, so nothing is lost while the global policy
   stays `never`; a session run under `on-request` would no longer be offered the
   prompt. Between `rust-v0.163.0` and `rust-v0.164.0`, the source §2 relies on
   (`exec_policy.rs`, `bash.rs`, `is_dangerous_command.rs`) changed only in PowerShell
   handling and refactors that keep the Linux bash path's behaviour.

   **Applied 2026-10-23 on titan** (the first host; the second host still has
   line 45 as `prompt`). Line 45 of the live rules was replaced by the lines below.
   They differ from the reviewed text above only in two deferred minors of review
   round 2, folded in at application: the justification says that in a rebase `:3:`
   is your own commit being replayed, and it quotes every path and uses `cp --`.
   Checked: the quoted form on a path with a space, run from a
   subdirectory, took theirs and `git add -- "<path>"` staged it; `codex execpolicy
   check` on the edited live file gives `forbidden` with this text for `git restore`,
   `allow` for both new forms and for `git add -- <path>`, and no match for
   `git rm --cached --no-cached -f -- <path>`. Whether a Codex session already running
   reloads the rules was not checked; a new session reads the edited file.

   ```
   prefix_rule(pattern=["git", "restore"], decision="forbidden", justification="git restore can overwrite uncommitted work. To unstage, run git reset -q -- <path>; for a newly added file, git rm --cached -- <path> also works. To take one side of a conflict, write git show :3:./<path> (theirs; :2:./<path> for ours; in a rebase :3: is your own commit being replayed) to a temporary file and, only if that succeeds, copy it over the file: tmp=$(mktemp) && git show \":3:./<path>\" > \"$tmp\" && cp -- \"$tmp\" \"<path>\" && rm \"$tmp\". Then run git add -- \"<path>\" as its own command.")
   prefix_rule(pattern=["git", "reset", "-q", "--"], decision="allow")
   prefix_rule(pattern=["git", "rm", "--cached", "--"], decision="allow")
   ```

Probe verdict (hq-748431): 1 fails, because the justification is dropped under `never`,
and the forms it names fail in the sandbox in a worktree; 2 is inexpressible, because
strictest wins; 3 leaves `git restore <path>` unguarded in main checkouts and still
fails in worktrees. Recommendation: 4. The brief's fallback (documenting
`git reset -q -- <path>` in global guidance) fails in worktrees without the `allow`
rule. The runtime path of 4 rests on the source read and the sandbox probe, not on a
live model turn: the refusal text an agent sees and the sandbox skip of the new allows
are still to be observed in one Codex session after the edit.

## 5. Unanswered questions

- Answered by hq-748431 (§2, probe results): line 45 is the rejecting layer; a
  `prompt` rule's justification does not reach the agent under `never`, while a
  `forbidden` rule's does; the unstaging and conflict-side forms pass the built-in
  checks but fail the sandbox in a linked worktree unless an `allow` rule matches them.
- Does the alternative-4 edit read as intended in a live Codex turn (the refusal text
  shown, `git reset -q -- <path>` succeeding in a worktree, the temporary-file conflict
  stage form followed by a separate `git add`)? — the first session
  after the edit; hq-48c5c6 and hq-5b8413 carry it.
- Which layer refuses forced `rm`, and is a harness report warranted? — ops-278533.

## 6. Proposed decomposition

- hq-748431 (research, under goal hq-62c3b1) — wakes hq-48c5c6 and hq-5b8413, each
  holding a `depends` edge on it since 2026-10-17.
- hq-52e1d9 — proposed as a drop: same command shape and rule as hq-48c5c6.
- ops-278533 (existing research) — covers hq-982164, proposed as a drop.
