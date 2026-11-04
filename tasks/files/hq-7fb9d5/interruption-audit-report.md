# Turn-pause interruption audit, November 1–4, 2026

Type: report. Owner: hq-7fb9d5. Investigation only: no limits, hooks, instructions, host pointers or services changed.

## Finding

Seven interruptions in six local Claude Code/Codex sessions were attributable to the new turn-pause mechanism or its interpretation. None supplies evidence of a runaway. Four were unnecessary stops without any exhausted configured limit; three were driven by the spawn/time policy during planned implementation. The latter are correct threshold enforcement or anticipation, but look premature for the stated goal of stopping runaway execution. This supports the user's concern, without establishing a population-wide 100% false-positive rate or proving that every unfinished operation was healthy.

“Valid” needs two distinct questions: did the counter rule apply, and was interrupting the work useful? Two enforced pauses applied the configured rule correctly. Five other interruptions occurred while the hook had not paused. A hard-pause-only dashboard would therefore miss most of this sample.

## Scope and method

On November 4, around 09:40–09:44 UTC, searched retained personal and work Claude/Codex stores for records dated since November 1 00:00 UTC. This deliberately includes the rollout weekend and the initial four-hour policy, as well as the last two days. Files were selected by modification time; records by their own timestamp. The first pass read 854 files (656 Claude, 198 Codex), approximately 1.078 GB, in 119.44 seconds, producing 488 candidate records in 138 files. It checked assistant messages, actual tool outputs and Claude attachments rather than counting raw text matches in user-injected AGENTS instructions or tool inputs. A broader second pass over 232 root files read assistant messages and Codex developer messages, including warning contexts, in 4.82 seconds. Both passes reported zero parse failures in candidate lines. The first pass is not a whole-file malformed-record audit.

Manually reviewed the candidate roots, their surrounding transcript records, pause reports, relevant task/source records, and current counter implementation. Excluded implementation probes, test output, quoted policy, injected context, ordinary review/publication gates, and repeated refusals from the same paused turn. The current investigation itself is excluded. Work stores are included when locally present; absence of a hit does not prove hooks were installed there. No other host or pruned/archive backup was scanned. Files were live during collection, so this is a discovery snapshot, not a transactionally frozen census.

Replayed each identified tree with the existing tools/turn_pause/replay.py, using the observed pre-change four-hour defaults for the two November 2 Claude cases and current 16-hour defaults for Codex. Read-only obs parent links supplied Codex descendants. These are retrospective estimates, not historical hook state; actual contemporaneous status/refusal text takes precedence. The scripts and small evidence files accompany this report. Raw selected records are in source-excerpts.json with original session/file/line references; case-metrics.json holds replay state and token snapshots.

## Cases

All times below are UTC. Counts in the table are contemporaneous observations unless explicitly labelled replay. Subsequent closeout calls can increase them.

| Case | When and work | What happened | Assessment |
| --- | --- | --- | --- |
| A | Nov 2 14:02, Claude, fam-f5f24c | Hook refused calls at about 2h33m, 129/500 root calls, 31/30 spawns, 0 compactions. Part A/B and C1–C5 had progressed; C6 implementation was committed and its review had started. | Correct spawn-rule enforcement; premature for this planned multi-repository execution. No observed runaway. |
| B | Nov 2 19:08, Claude, mm-f202b2 | Hook refused calls at about 4h03m, 48/500 calls, 7/30 spawns, 0 compactions. Tasks 1–3 were reviewed; Task 4's fixture correction and tests remained. | Correct old four-hour enforcement; premature. User explicitly identified this as valid long work. The time threshold has since been fixed. |
| C | Nov 3 09:56, Codex, lore-a8b553 / obs-50bfe3 | Agent read active 0:16/16:00 as a sixteen-minute cap, interrupted the baseline with SIGINT, and parked for a budget. Status remained paused:no; 48–52/500 calls, no spawns. | Clear interpretation/presentation false positive. Sixteen hours was configured. User corrected it; explicit time units have since landed. |
| D | Nov 3 21:28, Codex, tasks-4ef22d, first implementation stop | Warning at 375/500. Pause report sampled 5h35m, 406/500 calls, 1/30 spawns, manual compactions 2/2, paused:no. Tasks 1–7 were implemented; Task 8 remained. Replay reaches 415 calls including closeout. | Unnecessary warning-driven stop. No hard limit was exhausted; two compactions is within the allowed count. Existing execution authorization was still valid. |
| E | Nov 4 01:11, same Codex session, next implementation turn | Report sampled 3h19m, root calls 445/500, spawns 3/30, manual compactions 2/2, paused:no. Agent added reviewers' 34+17+6 calls to reach 502 and stopped before delivery. | Unnecessary counter-scope change. Implemented call limit counts root attempts; descendants contribute time and tree spawns, not root calls. Final review had accepted the corrections. This does not claim the substantial work was cheap. |
| F | Nov 4 02:21, Codex, tasks-e16bbe, user's example | Report sampled 4h24m, 325/500 calls, 30/30 agents, manual compactions 1/2, paused:no. All eleven task steps accepted; next whole-branch reviewer would be agent 31. Replay: 4.443h, 326 calls, 30 spawns, no hook pause. | Proactive policy stop anticipating the next required spawn, not a hook false trigger. The cap is too small for this otherwise progressing workflow. About 1–2h of integration/review remained, by the controller's estimate. |
| G | Nov 4 03:23, Codex, dots-ec778d | Warning at 375/500; agent stopped after a 16-case diagnostic at a reported 390/500. Version pins, complete cold proof and review remained. Later explicitly acknowledged no hard limit or new approval gate existed. Replay: 3.476h, 388 recorded calls, 1 spawn. | Unnecessary warning-driven stop. The underlying version failures were real unfinished work, not a reason the range guard required a user decision. Two-call replay/report discrepancy is not evidence of a misfiring hook. |

The six sessions are:

- A: claude-code:f5ed2d6a-dc73-443e-ac25-c0a4357da4cb, main transcript lines 1076, 1097, 1152.
- B: claude-code:c67f4b5f-818d-4533-83b0-172009b992c2, lines 432, 483, 499, 519.
- C: codex:01a19f20-a422-75b0-8476-0ed9ba0dd8c9, lines 725, 798–833, 840, 876, 884.
- D/E: codex:01a1a10b-15de-7a00-81ba-4469c83141b8, lines 4152/4695 and 7176/7711; tasks-4ef22d attachments execution-pause-r2-report.md and execution-pause-r3-report.md.
- F: codex:01a1a368-49dd-7552-84a0-019d41d3bc0e, lines 2903, 2958, 2960; controller-pause-report.md in its recorded multipart-attachments execution workspace.
- G: codex:01a1a0ca-e9f8-7e91-9095-4e88cd515d24, lines 9882, 10019, 10035, 10046. The last two are subsequent corrections, not separate events.

A's required workflow itself explains the spawn pressure: A1–A6 implement/review, a whole-branch review and correction/re-review, B1 implement/review, and C1–C6 implement/review plus prerequisite/adoption workers. F's thirty dispatches are eleven implementers, eleven task reviewers, five scoped re-reviewers and three prerequisite implementation/review workers. There is no need to posit an uncontrolled review loop to reach thirty. That does not settle whether the review workflow could be cheaper; lore-56a1c7 owns proportionality.

For E, “the turn includes subagents' work” and root-only calls are easy to conflate. The implementation is unambiguous: counters.attempt increments calls only when ev.agent is None; spawn events increment the root's tree counter. The audit does not silently change the established metric to a tree call budget.

Additional friction, excluded from the seven session interruptions: protected-path refusals stopped read-only hook inspection and a worktree host-pointer audit. Existing hq-c58737 and hq-5aa005 track these; the current protect.touches_protected matches strings without distinguishing read from mutation. B also encountered a closing-allowlist/claim-guard deadlock that required the user to park worktree tasks manually; hq-1400a4 addressed it. hq-5dc59c records refusal text asking for a goal pause that its tool requires the user to request. These are different failure modes from exceeding a duration budget.

## Recovered reference data

### Historical human turns: the unit the guard limits

The frozen November 1 design measurement covered 5,483 turns in October 2–November 1. These figures are historical measurements, not fresh labels of legitimate work:

| Metric per turn | Claude p50 | Claude p90 | Claude p99 | Claude p99.9 | Codex p50 | Codex p90 | Codex p99 | Codex p99.9 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Active minutes | 2.8 | 25.4 | 163 | 510 | 6.0 | 32.0 | 252 | 616 |
| Root tool calls | 9 | 49 | 143 | 300 | 12 | 55 | 246 | 700 |
| Tree spawns | 0 | 1 | 16 | 38 | 0 | 1 | 19 | 50 |

Source: docs/specs/2026-11-01-turn-pause-design.md, Measured range; frozen scripts/data are attachments on lore-911121. Historical Codex compaction figures there were transcript-derived; current live/replay Codex hooks do not count compactions.

The later hq-b2b50b calibration replayed 6,005 turns (3,490 Claude, 2,515 Codex) over October 2–November 2 20:00 UTC. Claude/Codex active-hour medians were 0.051/0.070, p99 2.761/4.164, and p99.9 9.549/10.195. At current defaults it predicted 26 first pauses: 1 on time, 9 on calls, 16 on spawns. Thus spawns account for 62% of predicted stops after the time correction. Increasing only time again would barely affect the problem. The report explicitly disclosed that other limits could still stop valid large executions.

Source: docs/notes/2026-11-02-active-cutoff-report.md and tasks/files/hq-b2b50b/active-cutoff-measurement.json. Sixteen-hour activation is recorded at merge 4bf3214bdfe757b951b4c7881163c49848fb0cfe. hq-414f8a later changed ambiguous HH:MM labels to explicit hours/minutes at fix 176a7331, merged 57313dba. Current CLI/source agree on 57,600 seconds, 500 root calls, 30 tree spawns and two root compactions, with strict above-limit enforcement.

### Earlier whole-session token/model-call statistics

Recovered the exact original query/result, not just a later paraphrase: Claude session 1219a183-f486-4832-ac92-170d315e5fc2, lines 228, 234–235. The thirty-day top-level Codex sample had at least one human turn, n=1,129:

| Whole-session measure | Median | p90 | p99 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Model responses (called “steps”) | 30 | 125 | 709 | 2,196 |
| Cumulative input/context tokens | 2.91M | 20.66M | 129.38M | 488.84M |
| Tool calls | 28 | 123 | 706 | 1,910 |
| Compactions | 0 | 1 | 4 | 12 |
| Indexed active hours | 0.17 | 1.19 | 9.86 | 39.91 |

These are whole sessions, often with several human turns, whereas the guard resets at a genuine human prompt. “Model responses,” “human turns,” and “tool calls” are different quantities. Input/context tokens include cached rereads; they are not unique text or a billing estimate. Older all-history sessions had very different tails (model-response p99 4,469, input p99 594.22M); the narrower thirty-day cohort was a deliberate choice. The index active-time definition also differs from the later in-flight tree replay. These distributions cannot be mixed into one threshold without matching units and cohorts.

For context, F had 71.72M cumulative root input/context tokens and about 190k output tokens at its stop; C's erroneous sixteen-minute turn added about 5.03M input tokens. D/E/G added roughly 91.57M/65.19M/69.47M root input tokens in their respective turns, measured as changes in the raw cumulative counter across the turn boundary. The D/E/G whole-session totals were much larger because those sessions had multiple human turns. These are root-only observations; no full subtree billing or quota reconstruction is claimed. They show that useful plan work can be expensive, not that every high-token run should proceed indefinitely.

## What can be monitored today

1. Exact session state: hq pause status --session SESSION_ID --json. It reports used/limit counters, pause reason and notification status. hq pause limits --json reports defaults. Always pass the id when looking at another session: directory fallback can select a different/latest session. JSON expresses active time in seconds and uses null for uncounted Codex compactions.
2. Find the session: hq sessions --harness codex -n 50, or --harness claude. This lists/resumes sessions; it is not a pause-event report.
3. Agent-waiting work: tasks list --all-projects --parked --waiting-on user is a current host's queue, not a historical event census. Reason decision includes many ordinary decisions; some premature stops did not ask for a budget, and parks may already have been cleared or live in another checkout/host.
4. Notification at an enforced pause: hq attempts a critical desktop notification and a relay inbox notice when relay is reachable. Relay notices have a 24-hour TTL. Proactive/warning-driven stops such as D/E/F/G do not necessarily take this path. The notifier reports launch/socket outcomes, not confirmed human receipt.
5. Existing obs report hooks measures Claude Stop-hook blocks, not PreToolUse denials; Codex has no indexed hook-run outcome here. A fresh report for November 1–4 showed zero Stop blocks for turn-pause despite the real A/B pauses. A zero there is not evidence of zero pause events. On this host invoke python3 with the registered obs checkout's obs.py; there is no obs executable on PATH.

There is currently no fleet/history command in hq pause, no durable transition journal in turn_pause, and no implemented session-size alarm baseline in obs. Current hook state is replaced at the next genuine prompt, deleted at SessionEnd and pruned after seven idle days. It cannot reconstruct history. obs-59789b explicitly owns session/tree baselines and alarms, including Codex rate-limit usage, but remains shelved; its hq-9aa713 wake condition has occurred. This is intended work, not current capability.

## Recommendation

First correct warning semantics and counter interpretation: a 75% warning should prompt a concise status/update and preparation while authorized work continues; it must explicitly say it is not a stop or new approval gate. Name root calls versus tree spawns in agent-facing guidance and use the hook status as the authoritative counter snapshot. Do not stop healthy work merely because two allowed compactions have occurred. Unit-label ambiguity is already fixed.

Second, recalibrate the spawn cap against approved multi-step executions as a distinct cohort. A thirty-agent cap is below the historical p99.9 for both harnesses and conflicts with eleven-step implement/review plans once their prerequisite/correction reviews are included. Prefer removing spawn count as a standalone hard stop or moving its hard cap substantially higher while retaining time/call backstops; choose exact replacement numbers with a labelled tail sample and replay before activation. Keep spawn growth visible as a warning. This is a recommendation for a subsequent design, not an activated policy change or a claim that another arbitrary count is proven safe.

For easy monitoring, hq should persist bounded transition records (warning, enforced pause, genuine-user reset/resume) with root/turn, timestamp, reason, measured counts and limits, then expose an hq pause history/list view that obs can consume outside hooks. It also needs a way to recognize agent-initiated stops/parks, since a hook-only journal would miss five of these seven cases. Reuse task park/provenance evidence and distinguish self-stop from enforced pause rather than interpreting every decision park as a guard event. Start with this evidence route before adding a more complex anomaly detector. The broader per-session/tree token and rate-limit alarm remains obs-59789b's recorded scope.

Rejected for this investigation: changing the live thresholds now (the user requested assessment; activation is separately gated), raising time alone (16/26 current-replay stops were spawns), treating every pause as an enforcement bug (A/B counted correctly), and claiming 100% population false positives (local discovery and policy interpretation do not justify it).

Follow-up reports: hq-1942a1 carries the user's monitoring/calibration concern; lore-83be38 records warning/counter-scope ambiguity. Existing hq-c58737, hq-5aa005, hq-5dc59c cover independent guard friction. None was silently triaged or implemented by this audit.

## Verification and limits

Verified seven cases against raw records/pause reports, ran the existing tree replay for all seven, recovered the original baseline query/result, read current counter/CLI/notification/store code, and checked current CLI limits/status. No application code changed; no suite run was needed for this investigation. Scanner extraction has small assertions excluding user instructions and tool-input matches; the broader pass recovered the same seven events and direct warning contexts. It is a discovery aid, not a shipped or fully tested monitoring tool. Numeric replay differences and uncounted Codex compactions remain explicit above.

This is one host's surviving records, not a measured sensitivity/specificity study. No new known-runaway event was found in the window; the original October 29–31 controller remains a historical positive control, caught by the 501st root call after about 9.857 active hours in the earlier sixteen-hour replay. Its absence from this week's positives cannot establish that the safeguards have no benefit. No global percentiles were re-indexed or recomputed; the recovered frozen measurements are sufficient to answer the reference-data question.
