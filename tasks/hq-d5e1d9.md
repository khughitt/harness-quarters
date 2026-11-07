---
id: hq-d5e1d9
title: Make harness-links agy tests independent of the checkout's live agy/settings.json
status: doing
priority: 2
size: xs
complexity: low
process: direct
owner: test/hq-d5e1d9-isolated-agy-settings
created: 2026-11-01T19:15:14Z
updated: 2026-11-07T11:25:15Z
started: 2026-11-07T11:16:01Z
depends: []
tags: []
origin: agent
---

tools/test_harness_links.py test_real_manifest_adopts_agy_replaced_settings_on_anchored_host_and_clears_stat_mark and test_fresh_clone_strips_live_agy_picks_from_dirty_source_checkout copy the invoking checkout's working-tree agy/ (shutil.copytree from the checkout, and fresh_clone). A live, non-pick edit to the main checkout's agy/settings.json (here agy itself switching statusLine.enabled) then carries into the scratch clone and both fail on ' M agy/settings.json'. Observed in just test on main right after the hq-2eba07 merge (795571ba); both pass in a clean clone of the same commit. Copy committed blobs (git show HEAD:<path>) instead of working-tree files, keeping the dirty-source test's deliberate pick injection.

## Notes

- 2026-11-01T19:15:14Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-07T11:16:01Z (main): started
- 2026-11-07T11:16:03Z (test/hq-d5e1d9-isolated-agy-settings): resumed
- 2026-11-07T11:16:28Z (test/hq-d5e1d9-isolated-agy-settings): trial: flow-trial-1 — enrolled — flow off
- 2026-11-07T11:16:30Z (test/hq-d5e1d9-isolated-agy-settings): arm: flow-trial-1 — unit tack-d5e1d9 — flow off
- 2026-11-07T11:18:36Z (test/hq-d5e1d9-isolated-agy-settings): baseline: focused baseline under validated policy-off (.tt.toml automatic_broad = false, flow-trial-1 arm: flow off, unit tack-d5e1d9): just test-one tools/test_harness_links.py (62 passed); broad suite deliberately omitted.
- 2026-11-07T11:25:13Z (test/hq-d5e1d9-isolated-agy-settings): review: impl round 1 — verdict: accept; findings: none; reviewer: agy
- 2026-11-07T11:25:15Z (test/hq-d5e1d9-isolated-agy-settings): review detail: round 1 on commit 61d9874c9d0b6e80fea96721ccfe43baf4628014 (tree 10903253cd87b616a9755ac1e240dc12b3c7e7bf) by session:agy:7e06a670-8b3b-4d92-bcd1-ff986821d753 accepted with 0 findings. Reviewer label recorded as bare agy because timeout 2 relay model --harness agy --pretty exited 2 on hq's pinned relay v0.3.0.
