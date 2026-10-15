---
id: hq-8c2fe2
title: "Record pi 1.1.0's RPC extension-catalog behaviour as a capability fact, and check upstream for it"
status: todo
priority: 3
size: s
complexity: low
process: direct
created: 2026-10-15T16:46:09Z
updated: 2026-10-15T16:46:09Z
depends: []
tags: []
source: crew-c3eb4e
agent: claude-code/claude-opus-5-5
---

Probed by crew-c3eb4e (2026-10-15, pi 1.1.0, @charmland/pi-hyper-provider 0.4.2; findings in crew's docs/notes/2026-10-15-cheap-model-pilot-brief.md §2):
- An RPC start with --provider/--model naming an extension provider exits 1 ('Unknown provider "<id>"') on an agent dir with no persisted catalog: the startup model check (main.js, before runRpcMode) runs before the background catalog refresh.
- Only an RPC start that names no model reaches that refresh. It persists the catalog to models-store.json in about 3 s, swallows errors (.catch(() => {})), and an extension's own fetch timeout can leave the catalog empty silently.
- pi update --models refreshes only built-in catalogs (refreshModelCatalogs builds a ModelRuntime without extensions) and takes no -e.
- A persisted extension catalog is listed only when the extension is loaded again.
- Hyper's pi docs page says pi refreshes extension catalogs only when launched interactively; that is wrong for RPC in 1.1.0.

Do: record these as capability facts for the 1.1.0 epoch, with the probe that shows them. Then search pi's upstream issues, PRs, development branch and changelog for a report or fix of the start-before-refresh ordering and the swallowed refresh error. Note what was found. If nothing exists, prepare an issue (minimal repro: fresh PI_CODING_AGENT_DIR, -e <extension with fetchModels>, --mode rpc --provider <id> --model <m>) for the person to approve publishing. The same applies to a docs correction for Hyper's pi page.

Not blocking crew: crew-799319 avoids extensions via models.json.
