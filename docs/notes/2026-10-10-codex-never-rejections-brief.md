# Codex rejections under approval_policy = never — brief

Ideas: hq-48c5c6 (git-index unstaging rejected), hq-982164 (forced-remove cleanup
rejected), hq-5b8413 (conflict-resolution restore rejected). Scoped 2026-10-10;
hq-5b8413 added 2026-10-11.

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
- Codex's exec policy resolves overlapping rules to the strictest decision, so an
  `allow` for `["git", "restore", "--staged"]` cannot carve an exception out of the
  `prompt` on `["git", "restore"]` (to be confirmed in the research below). The binary
  shows `prefix_rule` accepts a `justification`; whether that text reaches the agent
  when a rule is refused under `never` is unknown.
- hq-982164 is the forced-`rm` refusal already reported three times in ops
  (ops-75b29a canonical, ops-7933db, ops-97a39d) and once in lore (lore-304804, which
  attributes it to Codex's built-in exec policy refusing any forced `rm` under
  `never`). Open research ops-278533 identifies the rejecting layer and intended
  policy for those events; brief: ops `docs/notes/2026-09-30-adaptive-hook-messages-brief.md`.

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

1. **Keep the rule, add a justification** naming the permitted forms
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

Lean: 1, falling back to documenting `git reset -q -- <path>` in the global guidance
if justifications do not surface under `never`.

## 5. Unanswered questions

- Is line 45, rather than a built-in check, the layer that rejected both `git restore`
  commands (now identified in §2)? — research hq-748431 (probe).
- Does a rule's `justification` reach the agent when `never` refuses it, and do
  `git reset -q -- <path>` / `git rm --cached` and the conflict-side forms pass the
  built-in checks? — hq-748431.
- Which layer refuses forced `rm`, and is a harness report warranted? — ops-278533.

## 6. Proposed decomposition

- hq-748431 (research, under goal hq-62c3b1) — wakes hq-48c5c6 and hq-5b8413.
- ops-278533 (existing research) — covers hq-982164, proposed as a drop.
