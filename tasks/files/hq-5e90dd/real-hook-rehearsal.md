# Real-hook receipt rehearsal

Task: hq-5e90dd; parent: hq-74f102. Verdict: PASS.

This is a recorded local rehearsal with full committed task records and the normal pre-commit hook. It adds no hosted test omission and makes no live-cutover or hosted-coverage claim.

## Frozen inputs

- hq: commit b5f88e231ab0a64c2ede833543b7be1a48dc117f
- ops: commit b9c336891a5dad6c666c36bb8898f46952f62c13
- lore: commit cd9c27a408eb2a2fbdc3ffbf956bdb0e775922e2

The hq candidate includes the main merge before this rehearsal. Hook, guide, manifest and checker inputs came from that candidate; no source hook was replaced and no --ci route was used. Copied Git configuration, HOME, registry and state were isolated. Retained-history branch refs were recreated inside the clone at their frozen source commits.

## Commands and observed results

- Unrenamed baseline: git commit --allow-empty -m "test: unrenamed normal-hook baseline"; exit 0.
- Rename: tasks --json rename hq hqprobe; exit 0.
- Receipt commit, before moving or editing guides: tasks --json commit --project hqprobe; exit 0.
- Normal .githooks/pre-commit invocation recorded in both baseline and renamed Git traces.
- Receipt absent, renamed records committed, working tree clean. The driver rechecked HEAD, ancestry, tracked commit paths, guide bytes and saved log/trace digests without rerunning the hook.
- Baseline commit: 544e5263abc64eb8ce7f35bf89b0c6f1312ea7a9
- Renamed commit: 7218f9acd27a5ece2dfe3d91c84b98acb31b7576
- Receipt commit paths: 1703; warnings: []

## Unchanged identity and guides

| File | SHA-256 before and after |
| --- | --- |
| identity.toml | 96b3a36863b58ca0de2db12e06d410f62d5cd5f79358f668dfa3a9bfc25f8fa3 |
| README.md | 2f0f1b8f7ab3a294184b81f650dac46c8b96e1cb7fc9537f7ad4cf169d338cf1 |
| AGENTS.md | 80505e9ba5b9fc6d5cbf58d044844e4f9c0bf2073c374bfe15b692c544e0a91e |

## Preparation failures and disposition

- Attempt 1 stopped at the unrenamed baseline: isolated registry lacked lore sources required by guide references. No rename ran; the next case added a pinned lore copy.
- Attempt 2 passed the unrenamed normal hook, then rename refused the missing retained local branch. The clone had the exact source commit as a remote-tracking ref. The next case faithfully recreated the named local refs; no history or validation was bypassed.
- Attempt 3 passed all gates. Raw commands, trace files, frozen driver and guide originals remained available to the independent reviewer in the parent execution workspace.

The production regression evidence is separate: 218 focused tests passed at code commit 091984c51971fa2685138f00f1ba00b04e208349; mandatory hygiene passed, automatic broad verification was deliberately omitted under checkout policy.
