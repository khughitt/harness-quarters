# Strict obs consumer verification

Approved design: hq cfaed41. Approved plan: hq 0154323, Tasks 18–19.

Strict consumer: 8d26e255ef974467c0c8102fa65ce44892eca3c0.
Producer/probe: obs 49388f683f91667b0e5040279985ff12c63df30d.
Producer contract citation: obs 4723076. Historical reader: hq 889000e.

Full hq baseline: 1674 passed. Final full just test: 1793 passed (231 agent + 1170 hook/tool + 391 parallel cutover + 1 isolated signal); only the final isolated segment deselected 154. Focused reader/proof/CLI: 214 passed. Protocol/probe regression: 76 passed. These focused counts overlap the full suite.

Full obs baseline just test-fast: 1632 passed. Focused just test-one test_retention_readiness test_index_state: 21 passed. Final just gate: 1633 passed; existing undefined-tag warnings and synthetic diagnostics did not fail checks.

RED evidence: original reader 90 failures; real proof 12 failures; extended decision records 12 failures. Environment helper, explicit tasks PATH and synthetic credential-leak regressions failed before their corrections. Safe old probe failed with the obsolete FileFacts positional constructor, missing inode/harness/thread_id. Subsequent GREEN uses each extracted reader production capture_file, Manifest, Context, _facts and archive read-back.

Post-commit paired command: python3 tools/retention_readiness.py <hq-worktree> --strict-rev 8d26e25. Exit status: 0. Both readers loaded actual contract-2 output; assertions verified all 11 rows and only current/claude_current were eligible under the strict consumer.

| Case | Producer reasons | Strict consumer | Historical reader |
|---|---|---|---|
| claude_current | none | eligible | eligible |
| current | none | eligible | eligible |
| stale_schema | index_schema_stale | index-stale | index-stale |
| stale_extractors | extractors_stale | index-stale | eligible |
| partial_tail | partial_tail, unread_bytes | index-stale | eligible |
| unread_bytes | unread_bytes | index-stale | index-stale |
| inode_replaced | replaced | index-stale | eligible |
| preserved_stat_rewrite | none | index-stale | eligible |
| missing | missing | unindexed | unindexed |
| unavailable | unavailable | absent | absent |
| identity_mismatch | identity_mismatch | index-stale | eligible |

Exact successful JSON is attached as paired-acceptance-8d26e25.json. Live archive capture/prune, installation, archive replay, timer changes and source enablement were not run. hq-624351 owns rollout and obs-de84cb remains its required replay gate. Final implementation review is separately recorded; this verification report does not substitute for it.
