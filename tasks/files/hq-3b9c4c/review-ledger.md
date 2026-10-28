# Strict consumer design review ledger

Reviewer: claude-code/claude-opus-5-5, relayed by user. Frozen input: hq e07e23c,
docs/specs/2026-09-30-session-archive-design.md. Round 2: accept, minor 8.
No human design approval was included in the relayed review. Revision 3 is the
controller's correction pass and remains pending human approval.

Ruling: M1 fixed in revision 3, §3.4.0 field table and readiness paragraph. Accept nonempty unknown harnesses, match no hq source, interpret identity only for known harnesses. Why: unrelated producer expansion should not halt known-source pruning. Cost: future harnesses need explicit source support before they can be pruned.

Ruling: M2 fixed in revision 3, §3.4.0 Acceptance. Require real-file contract-2 loader-to-_facts/evaluate eligibility and preserved-bytes inode-replacement cases. Why: direct FileFacts fixtures and the external probe miss production wiring. Cost: two filesystem integration cases add suite time.

Ruling: M3 fixed in revision 3, §3.4.0 Intent and authority. Pin the producer document at obs 4723076. Why: its revision label alone does not identify immutable bytes. Cost: a later contract change requires an explicit citation update.

Ruling: M4 fixed in revision 3, §3.4.0 path table and Exact path identity. Keep exact strings; reject dot/dot-dot components, repeated separators and trailing separators without normalization. Why: normalization can change symlink path meaning. Cost: noncanonical producer spellings stop the run until corrected.

Ruling: M5 fixed in revision 3, §3.4.0 Contract boundary and Exact path identity. Abort on every duplicate path, identical or conflicting. Why: producer files.path is unique; no coalescing is needed. Cost: malformed redundant output stops pruning.

Ruling: M6 fixed in revision 3, §3.4.0 Intent and Approaches. Remove session-origin narrative and temporary controller-review wording; provenance remains on the task. Why: the design should retain decisions rather than transient process narration. Cost: readers consult the task for origin.

Ruling: M7 fixed in revision 3, §3.4.0 Implementation boundary and §4 step 3. Name the exact implementation plan and old contract-1 reader. Why: both references were ambiguous. Cost: no runtime change.

Ruling: M8 fixed in revision 3, §5. Add the §3.4.0 Acceptance pointer. Why: test obligations must be discoverable from Testing. Cost: the pointer must stay aligned with the section.

Policy disposition: retain the existing non-blocking malformed/unrecognized diagnostic counts and mandatory archive-replay gate. Why: verified raw archive bytes preserve replay input without keeping every skipped record live forever. Cost: evidence obs did not understand depends on successful archive preservation and the rollout replay check. No policy expansion or gate removal.

Adjacent documentation correction: §3.2 now distinguishes discovery of extra Codex roots from enabling their pruning. Verified against stores.store_roots and the unchanged hq source table. No source was enabled.

minor (deferred): none. Runtime implementation and acceptance checks remain future work after human design and plan approval.
