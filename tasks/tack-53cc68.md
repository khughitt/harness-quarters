---
id: tack-53cc68
title: Removal experiments for rules with no recorded failure
status: idea
priority: "2"
created: 2026-09-16T15:51:27Z
updated: 2026-09-22T00:31:56Z
depends: [ops-8fdaf6, ops-acd029]
parent: tack-9ec1eb
tags: [rules, obs]
source: "mindful:thought:8e45d49e001c4e5eb9b00f159dc60e87"
agent: "claude-code/claude-opus-5[1m]"
---

Stage (b) of the pruning idea. The audit lists rules with no incident behind them (core and refactoring rules A1–A5, project-switch A21, most of the tasks skill's imperatives). Dropping one is a hypothesis about current models, testable only against a measure: drop a rule, watch the measure over enough sessions, keep or restore. Needs the measure defined (ai-9dfba9) and the skills obs/evals infrastructure (ops-8fdaf6), and the hook block log with a model field (ops-acd029) for the per-model half. Not startable before those; shelve with them as the wake condition if they stall.

## Notes

- 2026-09-22T00:31:56Z (main): Dependency on ai-9dfba9 removed 2026-09-21: that idea is shelved because the measure it would define now lives in obs — charter §7 (verified gate before closure as the outcome; the stall proxy) and obs-a6c7d4 (cost per stage). A removal experiment measures against those; the A/B runner ai-9dfba9 still defers is what repeated controlled runs would need.
