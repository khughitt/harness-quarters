# Dispositions: adding-a-harness review findings (hq-94632d)

Runbook: docs/runbooks/adding-a-harness.md on branch docs/harness-runbook-corrections.
Sources: files:adding-a-harness-review-report.md (I1-I10, M1-M13),
files:adding-a-harness-supplemental-review.md (S1-S6).
Revisions checked (all at the supplemental review's bases except obs, whose later
commits touch task records only): lore e9f5c15, ops bd9dfe6, relay 50366c8,
tasks d9d5e37, obs 838f2b1, familiar eef1ee3, hq main ac68432.

Section numbers refer to the corrected runbook.

| Finding | Disposition | Where |
| --- | --- | --- |
| I1 superpowers is an upstream submodule; stale tool list | fixed: upstream contribution plus pin bump; tool list removed, notes described as platform notes | 1 map, 2 "Superpowers platform notes" |
| I2 cli.toml vocabulary and conformance tests | fixed: ops change first, adopt per project with the parser change | 1 map, 6 "Shared CLI vocabulary first" |
| I3 PreToolUse guard, subscriber harness lists, relay-guard-probe | fixed: hook role added, Command guard section, subscribers per selected layer, probe tables named | 5 "Standard hook roles", "Command guard"; 6 "Relay consumers" |
| I4 agy/hook as existing adapter | fixed: named as the model adapter with its three roles and tests | 0 examples, 5 consequences |
| I5 one probe per fact; wake-judge JUDGES | fixed, with a correction: harness-only facts may point `probe` at `<name>/probes/` (pi does) | 4 "Reproducible probes" |
| I6 shared normalizeEvent/parsePayload; opencode bridge in integrations/; parseEvidence order | fixed | 6 relay items 3-6 |
| I7 tasks: host config, fixture copy, app-server, array length, missing lists | fixed | 6 "tasks ancestry and claims" |
| I8 tt broadcast; tt-report AGENTS; harness-remap, obs-index, keys.toml | fixed | 1 map, 6 "Test-run provenance" |
| I9 claude-provenance is Claude-only | fixed | 5 item 3, 6 "Child-shell environment" |
| I10 approval under every profile; merge vs apply activation | fixed | 8 items 2-3 |
| M1 obs failure modes | fixed | 6 "Relay consumers", "Native session provenance" |
| M2 join.SOURCES dict, CODEX_SESSION_ID, malformed classification | fixed | 6 provenance and test-run provenance |
| M3 more obs lists | fixed by discovery; the named ones are listed as examples | 1, 7 obs item 3 |
| M4 more relay lists | fixed | 6 relay item 1 |
| M5 claim-guard details | fixed | 5 "Extending ... claim-guard" |
| M6 TASKS_FORMAT default | fixed | 6 "Child-shell environment" |
| M7 Claude skill links | fixed | 2 "Skills delivery" |
| M8 strict JSON clean filter | fixed | 3.3 |
| M9 section numbering | fixed: 3.1-3.6 under section 3, no "four-part" count | 3 |
| M10 Source pruned has no default | fixed | 7 archive item 1 |
| M11 alphabetical order is convention; Undeclared vs unknown | fixed | 4 item 1 |
| M12 hq AGENTS.md Layout and README | fixed | 2 homes bullets, checklist |
| M13 payload keys | fixed for model, to_model, scratchpad_dir, session_crons; agy executionNum/terminationReason dropped (unverified), pointed at the facts notes | 5 table |
| S1 shell-tool mapping across the guard path | fixed: five-link path, mapping or coordinated change, three-case evidence | 5 "Command guard" |
| S2 settings symlink survives harness saves | fixed: probe before choosing, post-apply link-check with a new value; hq-b24c39 named, not implemented | 3.1, 3.5, 8 item 6 |
| S3 familiar compatibility before observer enablement | fixed: conditional on the layer; closed sets named | 6 "Relay consumers", 0 |
| S4 selected-layer acceptance | fixed: depth ladder replaced by a layer table with evidence; examples marked with limits | 0 |
| S5 discovery plus ownership/distribution map; recovery links | fixed: discovery first, source/distribution/activation table, relay-runtime.md linked, per-host vs one end-to-end check | 1, 8 |
| S6 hook_event_name optional; preserve original report | fixed in runbook (optional, must match when present); original report left unedited | 6 relay item 3 |

Deliberate exclusions: no runtime remedy (hq-b24c39 stays separate); no edits in
consumer repositories; the static obs registry list is kept only as examples behind
discovery, not as a complete inventory.

## Review round 2 (claude-code/claude-opus-5-5, against 4995d62)

The reviewer read ops at 0b00025 and obs at f518180 (later than the bases above).

| Finding | Disposition | Where (496faef) |
| --- | --- | --- |
| C1 subscriber file naming a new slug breaks older pinned hook images | fixed: ordering hazard spelled out (release, move every hook image, then render, then check an existing harness) | 1 map, 6 Subscribers, 8 step 4 |
| I1 runtime pin takes effect on merge | fixed | 1 map, 2 pinned runtime bullet, 8 steps 1-2 |
| I2 approval after landing; link apply and subscriber render without approval | fixed: approval is step 1; section 2 and section 6 point at it | 2 first-run step 2, 6, 8 step 1 |
| I3 settings-save probe against the live home | fixed: disposable home before section 2; live link-check left to post-apply | 3.1 |
| I4 agy/hook does not go through relay | fixed: relayed and direct-adapter routes separated | 5 Command guard |
| I5 disposition record missing | fixed: this attachment | task record |
| M1 discovery grep misses bare keys and path constants | fixed: second pattern | 1 |
| M2 relay `model` enum | fixed: listed, with the grep that finds every enum | 6 |
| M3 relay conformance test name | fixed | 6 |
| M4 hook scripts not read through home links | fixed | 1 map |
| M5 hq-b24c39 "designing" | fixed: "open remedy" | 3.1 |
| M6 guard needs adapter `refuse` | fixed | 5, 6 relay item 2 |
| M7 `isHarness(row, ops)` | fixed | 6 relay item 2 |

## Review round 3 (scoped re-review of 496faef)

| Finding | Disposition | Where (8626ff1) |
| --- | --- | --- |
| I-A hook images take effect on merge across hosts, not per host | fixed: classed with merge-activated surfaces; install everywhere first, one approved hq merge, then per-host render | 1 map, 6 Subscribers step 2, 8 steps 1 and 4 |
| M-A second grep used `$repo` outside the loop | fixed: folded into the loop | 1 |
| M-B disposable home may lack credentials | fixed: copy only the credential file, delete afterwards | 3.1 |
| M-C section 2 did not point at the 3.1 probe | fixed | 2 first-run step 2 |

## Review round 4 (scoped re-review of 8626ff1): accept

| Finding | Disposition | Where (9e4a2ba) |
| --- | --- | --- |
| N1 "then `hq`" read as one merge | fixed: hq lands in stages (pin, hook images, template), never as one merge | 8 step 2 |
| N2 "every host installs first" impossible for the CLI pin | fixed: image versions before the image merge; pin on other hosts as soon as it syncs | 1 map |
| cosmetic wrap in section 2 step 2 | fixed | 2 |

These post-acceptance wording fixes were self-checked (ops-check, ops-docs check), not re-reviewed.

Final branch: docs/harness-runbook-corrections at 9e4a2ba (commits 4995d62, 496faef, 8626ff1, 9e4a2ba).
