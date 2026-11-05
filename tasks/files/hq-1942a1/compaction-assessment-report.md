# Automatic-Compaction Turn-Pause Assessment (`hq-1942a1`)

- Assessed window for local-store comparison sample: `[2026-11-01T00:00:00Z, 2026-11-04T23:30:00Z)`
- Baseline limits evaluated (`tools/turn_pause/limits.toml`): `active = 16h` (`57,600s`), `calls = 500`, `spawns = 30`, `compactions = 2` (warn fraction `0.75`: `active = 12h`, `calls = 375`, `spawns = 23`, `compactions = 2`)
- References: `tasks/files/hq-7fb9d5/interruption-audit-report.md` (`[ref:audit]`), `tasks/files/hq-7fb9d5/case-metrics.json`, `docs/specs/2026-11-01-turn-pause-design.md` (`[ref:pause-contract]`), `tools/turn_pause/{counters,adapters,replay,limits}.py`

---

## 1. Executive Summary & Recommendation

**Answer:** **No.** Automatic-compaction count (`compactions > 2`) does not independently identify runaway work well enough to justify a hard turn pause. Across all three harnesses (`Claude Code`, `Codex`, `Antigravity`), compaction count measures **session context-window turnover** (cumulative input/cached tokens read across the session) rather than runaway execution, behaves asymmetrically across harnesses, does not reset cleanly at human-turn boundaries when prior-turn context carries over, and provides **zero marginal runaway protection** on the October runaway control (`codex:01a18943-2b9d-7e50-926f-b74169571349`).

### Recommendation: Make Compaction Advisory Only (Option 3)

Among the three candidate policies—(1) retaining the hard `compactions = 2` cap, (2) raising the hard threshold, or (3) making compaction advisory while preserving `active` (`16h`), `calls` (`500`), and `spawns` (`30` / calibrated spawn policy)—**we recommend Option 3 (make automatic compaction advisory/informational only and remove it as an independent hard pause trigger in both hook enforcement and global instructions):**

1. **Zero marginal value on the October runaway control (`sun-fbaf80`):**
   - In `tools/turn_pause/replay.py`, `Codex` emits no compaction hook event (`compact_events = null` in `tools/turn_pause/facts.json`), so `hook_compactions = 0` throughout the entire `41.6430h` runaway turn (`2026-10-30T01:51:58Z`), and the turn is paused deterministically by **`calls` (`501 > 500`)** at `2026-10-30T11:43:22Z` (`active = 9.8567h`, `calls = 501`, `spawns = 28`, `compactions = 0`).
   - Even if a hypothetical transcript-level hook counted every raw `type == "compacted"` record in `codex:01a18943-2b9d-7e50-926f-b74169571349`, the runaway turn (`Turn 3`, started `2026-10-30T01:51:58Z`) only experienced **2 compactions** (`04:41:10Z` and `08:53:32Z`) before hitting `calls = 501` at `11:43:22Z`; its 3rd compaction (`2026-10-30T12:56:46Z`, rollout line `8922`) occurred **1 hour 13 minutes after** `calls = 501` had already paused the turn.
2. **Severe harness asymmetry and cross-turn carryover:**
   - **Claude Code (`~/.claude/projects`):** Hooking `PostCompact` observed `max = 1` compaction per turn across both the 30-day baseline (`3,033` turns) and the November 1–4 sample (`375` turns: `9` with `1` compaction, `0` with `>= 2`). A hard cap of `2` never fires on Claude Code.
   - **Codex (`~/.codex/sessions`):** Unhooked (`compactions -/2 (count your own)`). In raw rollout logs across `282` November 1–4 turns, `28` turns had `>= 1` `type == "compacted"` event, `5` had `2`, and `0` had `>= 3` within a single turn (`max = 2`), though multi-turn sessions reached `5` across turns (`codex:01a1a10b-15de-7a00-81ba-4469c83141b8`). Because session context carries over across human turns, Turn 2 of `01a1a10b-15de-7a00-81ba-4469c83141b8` compacted just **3.43 minutes** after the user prompt (`line 4753`).
   - **Antigravity (`~/.gemini/antigravity-cli/brain`):** Unhooked by `turn-pause` (`docs/specs/2026-11-01-turn-pause-design.md` §Coverage) and governed only by the instruction-level self-counting rule. Its runtime triggers an automatic `CHECKPOINT` compaction whenever `input_tokens + cache_read_tokens` crosses `~256,000` tokens (`257k–284k` observed), which occurs every **45–70 `read_file`/`edit_file` calls** (`7–30` minutes of normal codebase reading or TDD). Across `176` November 1–4 human turns (excluding this assessment session), `63` turns (`35.8%`) compacted `>= 1` time, `13` (`7.4%`) compacted `>= 2` times, and `3` (`1.7%`) compacted `3` times—all in `54.8–114.4` minutes and `177–327` calls.
3. **Why Option 2 (raising the threshold) is rejected:**
   - No single integer threshold bridges `Claude Code` (`max = 1`), `Codex` (unhooked, raw `max = 2` per turn), and `Antigravity` (`CHECKPOINT` every ~256k cached tokens plus cross-turn carryover where turns compact at `0.45–3.43` minutes after a user prompt).
   - Keeping any hard manual compaction stop on unhooked harnesses forces agents to estimate their own tool calls and compactions after context truncation—directly causing severe self-count distortion (`50` reported vs `112` actual calls in `relay-587bf8`; `~65` reported vs `177` actual calls in `mm-2f0a2f`) and premature boundary stops at `N/N` (`relay-587bf8` and `lore-3c26fa`).

---

## 2. Coverage, Methodology & Candidate-Selection Limits

### 2.1 Declared Window & Whole-Window Compaction Census (`[2026-11-01T00:00:00Z, 2026-11-04T23:30:00Z)`)

We reused `tools/turn_pause/replay.py` for `Claude Code` and `Codex` (augmented with a read-only scan for raw `type == "compacted"` records in `Codex` root rollouts) and scanned `Antigravity` compact transcripts (`~/.gemini/antigravity-cli/brain/*/.system_generated/logs/transcript.jsonl`, grouping human turns by `USER_INPUT` and counting automatic `CHECKPOINT` steps):

| Harness | Store / Method | Human Turns (`Nov 1–4`) | Turns w/ `>= 1` Compaction | Turns w/ `>= 2` Compactions | Turns w/ `>= 3` Compactions | Max Compactions / Turn |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `Claude Code` | `~/.claude/projects` via `tools/turn_pause/replay.py` (`PostCompact`) | 375 | 9 (`2.4%`) | 0 (`0.0%`) | 0 (`0.0%`) | 1 |
| `Codex` (hook) | `~/.codex/{sessions,archived_sessions}` via `replay.py` | 282 | 0 (`0.0%`) | 0 (`0.0%`) | 0 (`0.0%`) | 0 (unhooked) |
| `Codex` (raw rollout) | Root rollout `type == "compacted"` within turn span | 282 | 28 (`9.9%`) | 5 (`1.8%`) | 0 (`0.0%`) | 2 (`5` across session) |
| `Antigravity (agy)` | `~/.gemini/antigravity-cli/brain/*/transcript.jsonl` (`CHECKPOINT`, excl. current session) | 176 | 63 (`35.8%`) | 13 (`7.4%`) | 3 (`1.7%`) | 3 (`4` across session) |

### 2.2 Candidate-Selection Rules & Missing/Non-Replayable Inputs

- **Two reported cases (`R1`, `R2`):** Taken directly from the two November 4 recurrence reports on `hq-1942a1`.
  - **Missing stamp resolved:** Report `R1` (`2026-11-04T20:17:41Z`, filed via `tasks feedback --project hq --category friction --recur hq-1942a1`) had no `harness_session` stamp in `tasks/hq-1942a1.md`. We located the exact filing tool call at line `185` (`2026-11-04T20:17:26Z`) of `~/.gemini/antigravity-cli/brain/99572651-1d10-4b2c-b19e-ff00a4b561cb/.system_generated/logs/transcript.jsonl` (Turn 2), which reported the pause that ended Turn 1 (`lines 1–157`, task `relay-587bf8`).
  - Report `R2` (`2026-11-04T23:15:00Z`, task `mm-2f0a2f`) carried `harness_session: 3e73f29d-277f-470c-8962-97b2d0eeaf26` in `tasks/hq-1942a1.md`, resolving to Turn 1 (`lines 1–308`) of `~/.gemini/antigravity-cli/brain/3e73f29d-277f-470c-8962-97b2d0eeaf26/.system_generated/logs/transcript.jsonl`.
- **Five additional progressing human turns (`P1–P5`):** Selected deterministically from the `[2026-11-01T00:00:00Z, 2026-11-04T23:30:00Z)` window to cover:
  - Both other `Antigravity` turns in the window that reached **3 `CHECKPOINT` compactions** (`P1`: `hq-e72097` and `P2`: `obs-b0a3f3`, both on Nov 1 prior to the turn-pause rule, providing a natural counterfactual of what happens when a 3-compaction `agy` turn is allowed to finish).
  - The highest-call post-rule `Antigravity` turn in the window with **2 `CHECKPOINT` compactions** that completed its phase without stopping (`P3`: `atoms-c058c4`, which also had 2 subsequent cross-turn compactions in later turns).
  - The audited `Codex` turn (`P4`: `lore-3c26fa` Tasks 3–4, `codex:01a1a10b-15de-7a00-81ba-4469c83141b8` Turn 2) with **2 raw `type == "compacted"` events** (the first firing 3.43m into the turn from cross-turn carryover) and a self-reported `manual compactions 2/2` stop.
  - The highest-call `Claude Code` turn in the window with **1 hooked `PostCompact` compaction** and no spawn/call pause (`P5`: `claude:5282c675-0325-40f3-8c66-29d2983868d7` Turn `2026-11-01T01:25:51Z`).
- **Evidence that cannot be replayed by `tools/turn_pause/replay.py`:**
  1. `Antigravity (agy)` transcripts (`~/.gemini/antigravity-cli/brain/*/transcript.jsonl`) are not supported by `tools/turn_pause/replay.py` or hooked by `hq pause`. For `agy`, turn spans are measured from `USER_INPUT` to the last step before the next `USER_INPUT`, tool calls are counted from `PLANNER_RESPONSE.tool_calls`, spawns from `invoke_subagent`, and compactions from automatic `CHECKPOINT` steps. Because `agy` step timestamps are per-step (`created_at`) rather than paired `PreToolUse`/`PostToolUse` hook events, `agy` active duration is measured as turn step-span duration (`end_ts - start_ts`, verifying no idle user-wait gaps via `ask_question`).
  2. `Codex` `type == "compacted"` rollout events are not emitted to `Codex` hooks (`compact_events = null`) and are intentionally ignored by `replay.py` (`compactions = 0`); we measure them directly from the rollout JSONL alongside `replay.py`'s exact hooked `active`, `calls`, and `spawns` counters.
  3. Instruction-driven self-stops (where an agent reads `<RULE[user_global]>` or a `CHECKPOINT` continuation prompt and decides to park a task) are agent decisions in the transcript, not hook refusals; `replay.py` models only mechanical hook refusals (`counters.crossed`).

---

## 3. Case-by-Case Assessment & Counter Headroom Table

### 3.1 Summary Table Across All 8 Evaluated Turns (`R1–R2`, `P1–P5`, and Control `C1`)

Headroom percentages are relative to `limits.toml` (`active = 16h` / `960m`, `calls = 500`, `spawns = 30`, `compactions = 2`).

| Case ID | Harness & Session ID | Task & Turn Anchor (UTC) | Mechanism & Stop Type | Active Time (Actual vs Reported) | Root Calls (Actual vs Reported) | Spawns (Actual) | Compactions (Hook / Auto Transcript / Agent Est.) | Remaining Headroom (`Active` / `Calls` / `Spawns` / `Comp`) | Verdict |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| **R1** (Report 1) | `agy:99572651-1d10-4b2c-b19e-ff00a4b561cb` | `relay-587bf8` Turn 1 (`lines 1–157`, `2026-11-04T19:57:44Z`–`20:13:13Z`) | Unhooked instruction self-stop at `2/2` (`2 == 2` boundary misread + post-compaction call undercount) | `0.2580h` (`15.48m`) actual vs `~9m` reported | `112` (`107` pre-pause, `41` steps) vs `50` (`47`) reported | 0 (`0` rep.) | `0` hook / `2` `CHECKPOINT` (`lines 96, 144`) / `2` rep. | `98.39%` (`15.74h`) / `77.60%` (`388`) / `100.0%` (`30`) / `0%` (`0` of `2`) | **False-positive premature stop** (progressing Phase 1 recon) |
| **R2** (Report 2) | `agy:3e73f29d-277f-470c-8962-97b2d0eeaf26` | `mm-2f0a2f` Turn 1 (`lines 1–308`, `2026-11-04T22:01:12Z`–`22:55:59Z`) | Unhooked instruction hard stop at 3rd `CHECKPOINT` (`3 > 2`, `line 305`) | `0.9131h` (`54.78m`) actual vs `~54m` reported | `177` (`176` pre-pause, `125` steps) vs `~65` (`~66`) reported | 0 (`0` rep.) | `0` hook / `3` `CHECKPOINT` (`lines 89, 160, 305`) / `3` rep. | `94.29%` (`15.09h`) / `64.60%` (`323`) / `100.0%` (`30`) / **Crossed** (`3 > 2`) | **False-positive hard compaction stop** (mid-TDD, 10 dirty files) |
| **P1** (Sample 1) | `agy:9fdda05b-f5d8-42a5-af86-225203aeacd6` | `hq-e72097` Turn 1 (`lines 1–566`, `2026-11-01T01:40:35Z`–`03:35:00Z`) | Pre-rule counterfactual: hit 3rd `CHECKPOINT` at `line 509` (`297` calls), kept going, finished task | `1.9070h` (`114.42m`) | `327` (`297` at 3rd `CHECKPOINT`, `216` steps) | 1 | `0` hook / `3` `CHECKPOINT` (`lines 144, 305, 509`) / n/a | `88.08%` (`14.09h`) / `34.60%` (`173`) / `96.67%` (`29`) / **Crossed** (`3 > 2`) | **Progressing completion** (would have falsely paused at call `297`, `9.1m` before `done`) |
| **P2** (Sample 2) | `agy:6747abcf-460d-4551-a5ac-48769ca40f9b` | `obs-b0a3f3` Turn 1 (`lines 1–444`, `2026-11-01T01:37:34Z`–`03:20:35Z`) | Pre-rule counterfactual: hit 3rd `CHECKPOINT` at `line 356` (`213` calls), kept going, finished task | `1.7170h` (`103.02m`) | `260` (`213` at 3rd `CHECKPOINT`, `167` steps) | 3 | `0` hook / `3` `CHECKPOINT` (`lines 123, 218, 356`) / n/a | `89.27%` (`14.28h`) / `48.00%` (`240`) / `90.00%` (`27`) / **Crossed** (`3 > 2`) | **Progressing completion** (would have falsely paused at call `213`, `18.2m` before `done`) |
| **P3** (Sample 3) | `agy:ad714ee5-96ca-46e9-999f-2af3a256d889` | `atoms-c058c4` Turn 1 (`lines 1–276`, `2026-11-04T20:22:34Z`–`21:00:41Z`) | Post-rule progressing turn: hit `2/2` `CHECKPOINT` (`lines 82, 228`), finished spec at `line 276` | `0.6353h` (`38.12m`) | `175` (`141` at 2nd `CHECKPOINT`, `95` steps) | 1 | `0` hook / `2` `CHECKPOINT` in T1 (`4` in session) / n/a | `96.03%` (`15.36h`) / `65.00%` (`325`) / `96.67%` (`29`) / `0%` (`0` of `2`) | **Progressing completion on edge** (`2/2` spent in `38m`; T5 & T7 compacted `1.7m` & `7.2m` into turn) |
| **P4** (Sample 4) | `codex:01a1a10b-15de-7a00-81ba-4469c83141b8` | `lore-3c26fa` Turn 2 (`lines 4680–8095`, `2026-11-03T21:50:48Z`–`2026-11-04T01:32:39Z`) | Hooked `calls` warn (`375`) + unhooked `manual compactions 2/2` self-stop at task boundary | `3.3415h` (`200.49m`) | `445` root (`502` tree-wide with reviewer) | 3 | `0` hook / `2` `compacted` (`lines 4753, 6546`; `5` in session) / `2` rep. | `79.12%` (`12.66h`) / `11.00%` (`55`) / `90.00%` (`27`) / `0%` (`0` of `2` raw) | **Premature boundary self-stop** (1st compaction fired `3.43m` into Turn 2 from T1 carryover) |
| **P5** (Sample 5) | `claude:5282c675-0325-40f3-8c66-29d2983868d7` | Turn 1 (`2026-11-01T01:25:51Z`, `~/.claude/projects/.../5282c675...jsonl`) | Hooked `PostCompact` (`compactions = 1`), completed normally (`pause = None`) | `4.3807h` (`262.84m`) | `218` | 22 | `1` hook / `1` `PostCompact` / n/a | `72.62%` (`11.62h`) / `56.40%` (`282`) / `26.67%` (`8`) / `50.0%` (`1` of `2`) | **Progressing completion** (highest-call compacted Claude turn without spawn pause; Claude `max = 1`) |
| **C1** (Runaway Control) | `codex:01a18943-2b9d-7e50-926f-b74169571349` | `sun-fbaf80` Turn 3 (`2026-10-30T01:51:58Z`, whole turn `41.6430h`, `1,801` calls, `82` spawns) | Hooked replay pause by **`calls` (`501 > 500`)** at `2026-10-30T11:43:22Z` | `9.8567h` (`591.40m`) at pause (`41.6430h` whole) | `501` at pause (`1,801` whole) | 28 at pause (`82` whole) | `0` hook / `2` `compacted` before pause (`11` in session; 3rd in T3 at `12:56:46Z`) | `38.40%` (`6.14h`) / **Crossed** (`501 > 500`) / `6.67%` (`2`) / `100%` hook (`0%` raw at pause) | **True runaway caught by `calls = 501`** (`73.4m` before Turn 3's 3rd compaction!) |

---

### 3.2 Detailed Analysis of the Two Reported Cases (`R1` and `R2`)

#### Case R1: `relay-587bf8` (`agy:99572651-1d10-4b2c-b19e-ff00a4b561cb`, Turn 1)

- **Source anchors:**
  - Task record: `tasks/hq-1942a1.md` note at `2026-11-04T20:17:41Z`; target task record in `~/d/relay/tasks/relay-587bf8.md` (parked at `2026-11-04T20:12:41Z`, resumed at `20:16:33Z`, completed at `22:45:02Z`).
  - Transcript: `~/.gemini/antigravity-cli/brain/99572651-1d10-4b2c-b19e-ff00a4b561cb/.system_generated/logs/transcript.jsonl`, Turn 1 (`lines 1–157`, `2026-11-04T19:57:44Z` to `20:13:13Z`), and Turn 2 (`lines 158–232`, where line `185` at `20:17:26Z` ran `tasks feedback --project hq --category friction --recur hq-1942a1`).
- **Event timeline & token mechanics:**
  - `line 1` (`19:57:44Z`): User prompt `Let's take relay-587bf8`.
  - The agent performed normal Phase 1 read-only reconnaissance across `relay` and `hq` (`84 read_file` calls, `28 run_command` calls, many batched `3–6` per `PLANNER_RESPONSE` step).
  - `line 96` (`20:05:30Z`, `7.77m` elapsed, `66` tool calls across `27` steps): Automatic `CHECKPOINT` #1 (`input_tokens = 28,776`, `cache_read_tokens = 255,107`, total input `283,883`, `output_tokens = 7,196`).
  - `line 144` (`20:09:18Z`, `11.57m` elapsed, `106` tool calls across `34` steps): Automatic `CHECKPOINT` #2 (`input_tokens = 7,279`, `cache_read_tokens = 252,087`, total input `259,366`, `output_tokens = 8,020`).
  - `lines 149–156` (`20:10:03Z`–`20:12:42Z`): Seeing the second `CHECKPOINT` summary, the agent checked `hq pause limits`, recorded a pause note on `relay-587bf8` stating `"Manual unhooked counts for this turn: ~9m active time, ~47 root tool calls, 0 subagents spawned, 2 root compactions"`, and parked `relay-587bf8` (`--waiting-on user --reason decision`) before creating its worktree or writing its design spec.
- **Two distinct failure modes demonstrated by R1:**
  1. **Instruction-driven boundary stop at `2/2` (`2 == 2` vs `3 > 2`):** Both `tools/turn_pause/counters.py` (`crossed`: `getattr(state, name) > getattr(limits, name)`) and `<RULE[user_global]>` (`"two root compactions under an allowance of two is within range; the third crosses it"`) allow 2 compactions and stop on the 3rd. However, because `limits.toml` sets `warn_fraction = 0.75` (`ceil(2 * 0.75) = 2`), the 2nd compaction is simultaneously the warning threshold and the last allowed compaction, inducing the unhooked agent to self-stop prematurely upon resuming from `CHECKPOINT` #2.
  2. **Post-compaction manual counter distortion (`50` reported vs `112` actual calls):** Because `agy` has no `turn-pause` hook and `CHECKPOINT` replaces the earlier step history with a text summary, the agent had no way to know it had executed `106` tool calls across `34` planner steps prior to `line 144`; it estimated `~47–50` tool calls (roughly the `41` `PLANNER_RESPONSE` steps) and `~9m` (vs `15.48m` actual).
  3. **Subsequent cross-turn carryover in the same session:** After the user resumed `relay-587bf8` in Turn 2 (`20:15:20Z`), the same `agy` session compacted again in Turn 4 (`line 293` at `21:12:02Z`, after just **3 tool calls / 0.88 minutes** in Turn 4, `cache_read_tokens = 247,628`) and in Turn 8 (`line 411` at `22:32:52Z`, after **3 tool calls / 0.53 minutes** in Turn 8, `cache_read_tokens = 254,660`), proving that `CHECKPOINT` reflects session-cumulative cache size rather than current-turn work.

#### Case R2: `mm-2f0a2f` (`agy:3e73f29d-277f-470c-8962-97b2d0eeaf26`, Turn 1)

- **Source anchors:**
  - Task record: `tasks/hq-1942a1.md` note at `2026-11-04T23:15:00Z` (`harness_session: 3e73f29d-277f-470c-8962-97b2d0eeaf26`).
  - Transcript: `~/.gemini/antigravity-cli/brain/3e73f29d-277f-470c-8962-97b2d0eeaf26/.system_generated/logs/transcript.jsonl`, Turn 1 (`lines 1–308`, `2026-11-04T22:01:12Z` to `22:55:59Z`).
- **Event timeline & token mechanics:**
  - `line 1` (`22:01:12Z`): User prompt `Let's take mm-2f0a2f.` (planned 7-task TDD implementation in `multiple-myeloma`).
  - `line 89` (`22:07:52Z`, `6.67m` elapsed, `59` tool calls across `27` steps): Automatic `CHECKPOINT` #1 (`input_tokens = 31,923`, `cache_read_tokens = 234,003`, total input `265,926`, `output_tokens = 6,537`).
  - `line 160` (`22:24:30Z`, `23.30m` elapsed, `104` tool calls across `51` steps): Automatic `CHECKPOINT` #2 (`input_tokens = 9,511`, `cache_read_tokens = 255,468`, total input `264,979`, `output_tokens = 9,167`).
  - `line 305` (`22:54:44Z`, `53.53m` elapsed, `176` tool calls across `123` steps): Automatic `CHECKPOINT` #3 (`input_tokens = 4,068`, `cache_read_tokens = 254,455`, total input `258,523`, `output_tokens = 5,099`).
  - The `CHECKPOINT` #3 summary at `line 305` explicitly injected `"CRITICAL TURN-PAUSE ALERT (Compaction 3 of 2): Under <RULE[user_global]> (Decisions -> turn-pause rule): ... Do NOT start any new edits or test runs"`.
  - `line 306` (`22:55:41Z`): The agent executed one final `run_command` (`177` total calls) to record the pause note and park `mm-2f0a2f` (`--waiting-on user --reason decision`), leaving uncommitted edits across 10 files (`6` test files after verified RED and `4` of `7` production modules).
- **Verdict on R2:**
  - Unlike R1, **R2 is an exact 3rd-compaction (`3 > 2`) hard stop** under the current rule.
  - Yet at the moment of the 3rd compaction (`53.53m` elapsed, `176` actual tool calls, `0` spawns), the turn had **94.29% of its 16h active-time allowance (`15h05m`)**, **64.80% of its 500-call allowance (`324` calls)**, and **100% of its 30-spawn allowance (`30` spawns)** still available, and was actively progressing through verified RED->GREEN TDD tasks.
  - Again, because 3 compactions had truncated the transcript history, the agent's manual tool-call estimate (`~65–66` calls) undercounted the true transcript total (`177` calls) by `2.7x`.

---

## 4. Runaway-Control Result & False-Negative Trade-Off

### 4.1 Why Removing the Hard Compaction Cap Does Not Weaken Runaway Protection

1. **The October runaway control (`codex:01a18943-2b9d-7e50-926f-b74169571349`, `sun-fbaf80` Turn 3 at `2026-10-30T01:51:58Z`) is caught by `calls` (`501 > 500`) before its 3rd compaction even occurs:**
   - Under current hook wiring (`compact_events = null` for `Codex`), `tools/turn_pause/replay.py` records `compactions = 0` for the entire `41.6430h` runaway turn and pauses it at `2026-10-30T11:43:22Z` on **`calls = 501`** (`active = 9.8567h`, `spawns = 28`, `compactions = 0`).
   - Even if `Codex` hooked raw `type == "compacted"` rollout events, inspect the exact timestamps of `type == "compacted"` in `01a18943-2b9d-7e50-926f-b74169571349`:
     - Rollout line `2498` (`2026-10-30T00:53:33.033Z`): Occurred during **Turn 2** (`2026-10-30T00:42:54Z`–`01:51:58Z`), not the runaway Turn 3.
     - Rollout line `4600` (`2026-10-30T04:41:10.246Z`): **1st compaction** in Turn 3 (`2.82h` after Turn 3 start).
     - Rollout line `6927` (`2026-10-30T08:53:32.428Z`): **2nd compaction** in Turn 3 (`7.03h` after Turn 3 start).
     - **Hook pause point (`calls = 501 > 500`):** `2026-10-30T11:43:22Z` (`9.86h` active, `2` compactions in Turn 3).
     - Rollout line `8922` (`2026-10-30T12:56:46.449Z`): **3rd compaction** in Turn 3—occurring **73.4 minutes after** `calls = 501` had already paused the turn.
   - Therefore, making `compactions` advisory-only (or removing it as a hard limit) produces **zero change** in the runaway control's pause time, call count, or active duration (`9.8567h`, `501` calls, `28` spawns).
2. **False-negative trade-off analysis:**
   - For a runaway turn to evade `active > 16h`, `calls > 500`, and `spawns > 30` while being caught by `compactions > 2`, it would have to trigger 3 context-window compactions in `<= 500` calls, `<= 30` spawns, and `<= 16h` active time.
   - As `R1`, `R2`, `P1`, `P2`, and `P3` show, reaching 3 compactions in `176–297` calls (`54–105` minutes) happens when an agent reads or edits large volumes of repository files (`120–143 read_file` calls in a single turn on `agy`)—which is the signature of legitimate multi-file exploration and TDD implementation, **not** an infinite polling or retry loop (which consumes `calls` and `active` time with small outputs, like `sun-fbaf80`'s `1,801` calls and `41.6h`).
   - On `Claude Code` and `Codex` (where `turn-pause` hooks run), `calls = 500`, `spawns = 30` (or the calibrated `hq-704fe5` spawn policy), and `active = 16h` remain enforced mechanically on every tool call.
   - On `Antigravity (agy)`, `agy/hooks.json` currently routes lifecycle and `before-tool` events through `relay`, while `turn-pause` (`hq pause`) only wires `claude-code` and `codex` (`tools/turn_pause/adapters.py`). Until `turn-pause` hooks `agy` directly, removing the instruction-level hard compaction stop eliminates false-positive `CHECKPOINT` stops (`R1`, `R2`) while leaving `agy` governed by instruction-level `active`/`calls`/`spawns` limits; if mechanical enforcement on `agy` is desired, it should come from wiring `agy` `before-tool` into `turn-pause` (`calls`/`active`/`spawns`), not from using `CHECKPOINT` count as a proxy for tool-call counting.

---

## 5. Actionable Follow-Up Scope for `hq-2dd09b` and `hq-b9d356`

1. **In `hq` (`tools/turn_pause/`):**
   - Stop treating `compactions` as a hard refusal limit in `counters.crossed` / `limits.toml` (keep `state.compactions` recorded and displayed in `hq pause status` as informational telemetry, or remove `compactions` from `crossed`/`warned` refusal gating while preserving `active`, `calls`, and `spawns`).
2. **In `lore` (`instructions/AGENTS.md` `Decisions` turn-pause paragraph):**
   - Remove `root compactions` (`compactions 2`, `"two root compactions under an allowance of two is within range; the third crosses it"`) from the hard turn-pause triggers and stop requiring unhooked sessions to self-pause on automatic compactions or guess pre-compaction call counts from truncated context.
3. **In `hq-b9d356` (post-change review after `2026-11-11`):**
   - Verify that post-change progressing turns on `Antigravity`, `Codex`, and `Claude Code` experience zero compaction-triggered pauses while `active`, `calls`, and `spawns` remain enforced.
