---
id: hq-eeb4d6
title: "rename-cutover: narrow rollback's differing-file copy and fold the detached cutover's deferred review minors"
status: todo
priority: 3
size: s
complexity: mid
process: direct
created: 2026-11-02T19:54:56Z
updated: 2026-11-02T19:54:56Z
depends: []
tags: [rename-cutover]
source: hq-5300fd
agent: claude-code/claude-opus-5-5
origin: agent
---

Deferred minors from hq-5300fd (detached rename-cutover): the Task 5 review (hq-b6a563) and the final whole-branch review, both claude-code/claude-opus-5-5, accepted with these left for later. None loses data; each stop names its remedy and a retry converges.

1. Narrow rollback differing-file copy (final review M1, Task 5 minor 1). differing_files copies every untracked file under an owned path whose bytes differ from the saved head, including a detached repo records directory p/: other sessions drafts and ignored caches are copied on every attempt, and an unreadable untracked file or directory under p/ stops rollback although rollback never touches it (spec 4.5 step 1 says those are left alone). Narrowest correct rule: copy a file on disk, not in the index and not a leftover, iff it lies under new/ or the saved head holds its path and the bytes differ; enumerate the latter from the saved head ls-tree and walk the disk only under new/. Needs a spec revision 7 sentence in docs/specs/2026-11-02-detached-rename-cutover-design.md 4.5 step 2; test_detached_rollback_stops_on_a_directory_under_p_the_copy_cannot_read becomes a pass-and-leave-alone test.
2. Concurrent-writers paragraph (M2): a file recreated between attempts at a path only the current HEAD holds is picked up by the revert commit (commit -- paths runs in only mode), so the retry stops at the hook or check_records. Fail-safe; qualify the spec claim that a retry converges from any stop.
3. Messages (M3, M4, Task 5 minor 3): the copy-failure stop should say the checkout was moved back to the old root; OSError other than FileExistsError from the leftovers mkdir and from save_reset_patch write_text should become the same Stop.
4. Patch labels (M5, Task 5 minor 4): an in-tree repo named records-x and a records repository x, or an in-tree repo named checkout, share a patch label; refuse at save when any two labels are equal, without renaming in-tree labels.
5. Tidy (M6, Task 5 minor 2): remove_leftovers re-implements prune_empty; leftovers_dir and save_reset_patch share the next-unused-number loop; holds() runs git per owned path in restore_records and commit_records where one git_files set would do; test helpers extra_detached, nested_records_repo and linked lack the show-toplevel and absolute-git-dir asserts the global fixture rule asks for.

Verification: RED-first tests in tools/test_rename_cutover.py for items 1, 3 and 4; just test green.

## Notes

- 2026-11-02T19:54:56Z (add): created
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
