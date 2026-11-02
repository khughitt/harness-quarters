---
id: hq-d5e1d9
title: Make harness-links agy tests independent of the checkout's live agy/settings.json
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-11-01T19:15:14Z
updated: 2026-11-01T19:15:14Z
depends: []
tags: []
origin: agent
---

tools/test_harness_links.py test_real_manifest_adopts_agy_replaced_settings_on_anchored_host_and_clears_stat_mark and test_fresh_clone_strips_live_agy_picks_from_dirty_source_checkout copy the invoking checkout's working-tree agy/ (shutil.copytree from the checkout, and fresh_clone). A live, non-pick edit to the main checkout's agy/settings.json (here agy itself switching statusLine.enabled) then carries into the scratch clone and both fail on ' M agy/settings.json'. Observed in just test on main right after the hq-2eba07 merge (795571ba); both pass in a clean clone of the same commit. Copy committed blobs (git show HEAD:<path>) instead of working-tree files, keeping the dirty-source test's deliberate pick injection.

## Notes

- 2026-11-01T19:15:14Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
