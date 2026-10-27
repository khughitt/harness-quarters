I read the diff from e07e23c to cfaed41 for the spec and the task's latest notes. The working file matches cfaed41.

Each finding against revision 3:
1. Unknown harness: fixed. Any nonempty harness string is accepted and gets the common field checks. Only claude-code and codex can match an hq source. identity is treated as opaque for other harnesses. A new obs harness no longer stops every prune.
2. Integration through _facts: fixed, and it's stronger than I asked. A pair of tests now goes through load_obs_state and the production _facts/evaluate with real temporary files, and FileFacts may not be built by hand. The negative case swaps in a new inode with the same bytes, size and mtime, so the first condition it fails is condition 3 (index-stale). That isolates the device/inode check from the archive conditions.
3. Citation: pinned to obs 4723076, which is still the latest commit on that spec.
4. Path spelling: fixed. Paths are kept exactly as obs emits them. Dot and dot-dot components and repeated or trailing separators are rejected, not normalized. obs builds its paths with Path, which never produces those spellings except .. from an environment override, so live output won't trip this.
5. Duplicates: any repeated path now aborts the run, identical rows included.
6. Process notes: the session-history and "controller's recommendations" passages are gone. The Status line still says what revision 3 addressed, which is fine there.
7. Wording: the plan is named by path, and rollout step 3 now says "the old contract-1 reader".
8. §5 Testing: now opens with a pointer to §3.4.0's Acceptance.

Other changes:
- §3.2 source discovery: the stale claim is corrected. The text now says obs discovers both Codex archived_sessions stores and .codex-work, but those sources stay capture-only until obs-914269 and a separate source-table change.
- Diagnostic counts: kept non-blocking. The ruling records Why and Cost, and that stays your policy call.
- Test run: the agent's note says the full just test passed with 1674 tests. That only covers the unchanged runtime; nothing in the strict consumer is built yet.

Keith: approved for planning.
