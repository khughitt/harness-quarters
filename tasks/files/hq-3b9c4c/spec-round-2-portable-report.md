## Review: strict obs consumer design (hq-3b9c4c, revision e07e23c)

I recommend accepting this revision. Nothing in it blocks approval, and the eight issues below are all minor. The task is still parked on your review gate: approving the revision is your call, and after that the task's agent revises the implementation plan, which you'll review separately. I changed nothing and wrote no task note.

**What I checked.** I read the spec at `.worktrees/hq-3b9c4c/docs/specs/2026-09-30-session-archive-design.md`. The working file matches e07e23c exactly. I compared it with:
- the contract it cites: obs `<obs-checkout>/docs/specs/2026-10-16-index-state-readiness-design.md`, sections 3, 5, 6, 7, 9 and 11.1;
- the obs producer, `<obs-checkout>/index_state.py`, plus the `files` table and the Codex identity builder;
- the current hq reader and decision code (`tools/session_archive/inputs.py`, `decide.py`, `prune.py`);
- obs's acceptance probe (`tools/retention_readiness.py`).

**Where it holds up:**
- **Field table matches the producer.** Every field in the §3.4.0 table matches what `index_state.evaluate` emits. Things the spec lets be null that can never be null (`inode`, `malformed_lines`, `indexed_schema`) only make it more tolerant, so they are safe.
- **One hash pass is enough.** Requiring `byte_offset == indexed_span.length == live.size` first makes the full-file hash prq already computes equal to the span hash. That justifies "no second hashing pass" and closes the gap where a file is rewritten at the same size while keeping its inode and mtime.
- **Codex identity agrees with obs.** hq and obs use the same filename pattern, and the identity builder never puts null or empty values into `ancestors` or `conflicts`. So the "lists of nonempty strings" check won't halt a run on today's data.
- **Exact-path keys fix the link halt and fail safe.** Keying by exact path fixes the halt from the 2026-10-22 note. Both sides build paths from `$HOME/.claude/projects` without resolving links, so the spellings match. If they ever stopped matching, every unit would be kept as `unindexed`, never deleted wrongly.
- **Rollout order is right.** Installing the strict reader before pruning is enabled, with hq-624351 owning all live steps, matches obs §9.

**Minor findings:**

1. **Unknown harness halts every prune** (§3.4.0 table, "Path and harness"). obs's evolution rule only limits new reason codes. Adding a new harness value (say, pi transcripts) doesn't require a contract bump, but this table would treat it as malformed and stop every prune. Nothing would be deleted wrongly, so the cost is that pruning stops, not data loss. Recommendation: accept any nonempty harness string, check `identity` only for the two known harnesses, and let unknown-harness rows match no source. The alternative is keeping the hard stop and stating it as a deliberate choice.
2. **No integration test runs the fresh-proof wiring end to end** (Acceptance, line 302 onward). obs's probe builds `FileFacts` itself and looks up rows by `realpath`, so it never exercises hq's `_facts`. The spec doesn't require an hq integration case where real temporary files plus contract-2 output make a unit eligible, and then keep it once one inode is changed. Without that case, a wiring bug could make the device/inode check meaningless (the digest check would still guard the bytes) or keep every unit, and only the live dry run would show it. Recommendation: name that pair of cases.
3. **"Revision 3" isn't a fixed citation** (line 216). The obs spec was edited twice after its revision 3 label (6a9e418 and 4723076 on 2026-10-21, both about symlinks) without changing the label. Recommendation: cite obs commit 4723076.
4. **"Lexically normalized" is ambiguous** (table row). It could mean "reject paths that aren't normalized" or "normalize them before keying". Normalizing `link/..` would be wrong for the reason the next paragraph gives. Recommendation: key by the exact string and say what happens to input that isn't normalized.
5. **The duplicate-path allowance is unnecessary leniency** (line 256). obs's `files.path` is `UNIQUE`, so duplicate paths can't occur. Aborting on any duplicate is simpler and fits "explicit over defensive".
6. **Process notes will go stale once approved** (lines 213–215 and 225–226). Who asked for what in which session, and "the controller's recommendations, subject to this document's review", belong on the task, not in the decision record.
7. **Two wording slips.** Line 298 says "this plan's old global contract" but means `docs/plans/2026-09-30-session-archive.md`. Rollout step 3, line 496, says "that reader" where it means the old contract-1 reader.
8. **§5 Testing has no pointer to §3.4.0.** The Status line says the revision "updates … verification obligations", but §5 is unchanged. One cross-reference would fix it.

**One decision worth confirming.** The spec adopts obs's position that `malformed_lines` and `unrecognized_records` don't block pruning, because the verified archive keeps the raw bytes for replay. That makes the archive re-read check (`obs-de84cb`) the only protection for evidence obs couldn't read. Rollout step 4 already requires it before the first `--apply`. obs explicitly allows a stricter consumer, so this is a policy choice for you rather than a defect.

**Outside this revision.** §3.2 says obs reads neither `archived_sessions` nor `~/.codex-work/sessions`. obs's `store_roots` now includes both, although `obs-914269` is still todo. Those sources are still not pruned, so nothing is unsafe, but the sentence is now wrong.

**Review note for the task.** As reviewer I wrote no note. Whoever writes it can use: `review: spec round 2 — verdict: accept; findings: minor 8; reviewer: claude-code/claude-opus-5-5`

Nothing was pushed, and I started no processes. The worktree `.worktrees/hq-3b9c4c` (branch `fix/hq-3b9c4c-strict-readiness`) is untouched and still owned by hq-3b9c4c.
