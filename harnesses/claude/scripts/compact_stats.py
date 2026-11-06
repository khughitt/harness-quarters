#!/usr/bin/env python3
"""Analyze Claude Code transcripts: what fills context, and what compaction keeps.

Usage:
    compact_stats.py [--projects DIR] [--min-size BYTES] [--session PATH]

Reads the JSONL transcripts under ~/.claude/projects and reports:
  * compaction events (trigger, pre/post tokens, duration, chain depth)
  * what survives each compaction boundary
  * which tools consume the most context, split into args vs results
"""

import argparse
import json
import os
from collections import Counter
from glob import glob

CHARS_PER_TOKEN = 3.7  # rough; good enough for share-of-context comparisons


def load(path):
    rows = []
    with open(path, errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def pct(values, p):
    if not values:
        return 0
    values = sorted(values)
    return values[min(int(len(values) * p), len(values) - 1)]


def blocks(entry):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        return content
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


def analyze(paths):
    comp = []                       # one record per compaction boundary
    survivors = Counter()           # block types that survive a boundary
    calls = Counter()               # tool -> call count
    args_ch = Counter()             # tool -> chars of tool_use input
    res_ch = Counter()              # tool -> chars of tool_result content
    chain_depth = Counter()         # boundaries per session

    for path in paths:
        rows = load(path)
        if not rows:
            continue
        by_uuid = {r["uuid"]: r for r in rows if r.get("uuid")}

        bounds = [
            r for r in rows
            if r.get("type") == "system" and r.get("subtype") == "compact_boundary"
        ]
        chain_depth[len(bounds)] += 1

        for n, entry in enumerate(bounds, 1):
            meta = entry.get("compactMetadata", {}) or {}
            comp.append({
                "session": os.path.basename(path),
                "n": n,
                "trigger": meta.get("trigger"),
                "pre": meta.get("preTokens", 0),
                "post": meta.get("postTokens", 0),
                "dropped": meta.get("cumulativeDroppedTokens", 0),
                "ms": meta.get("durationMs", 0),
            })
            pm = meta.get("preservedMessages", {}) or {}
            for uuid in pm.get("allUuids") or pm.get("uuids") or []:
                kept = by_uuid.get(uuid)
                if kept is None:
                    survivors["<dropped-from-transcript>"] += 1
                    continue
                found = False
                for block in blocks(kept):
                    survivors[block.get("type", "?")] += 1
                    found = True
                if not found:
                    survivors["<metadata-record>"] += 1

        pending = {}
        for r in rows:
            if r.get("isSidechain"):
                continue                       # subagent traffic, not main context
            for b in blocks(r):
                kind = b.get("type")
                if kind == "tool_use":
                    name = b.get("name", "?")
                    calls[name] += 1
                    args_ch[name] += len(json.dumps(b.get("input", {})))
                    pending[b.get("id")] = name
                elif kind == "tool_result":
                    name = pending.get(b.get("tool_use_id"), "<unmatched>")
                    res_ch[name] += len(json.dumps(b.get("content", "")))
    return comp, survivors, calls, args_ch, res_ch, chain_depth


def report(comp, survivors, calls, args_ch, res_ch, chain_depth):
    print(f"== compactions ==  {len(comp)} boundaries")
    if comp:
        for field, label in (("pre", "preTokens"), ("post", "postTokens")):
            vals = [c[field] for c in comp]
            print(f"  {label:11s} median={pct(vals,.5):>8,d}  p90={pct(vals,.9):>8,d}  max={max(vals):>8,d}")
        secs = [c["ms"] / 1000 for c in comp]
        print(f"  {'duration s':11s} median={pct(secs,.5):>8.0f}  p90={pct(secs,.9):>8.0f}  max={max(secs):>8.0f}")
        trig = Counter(c["trigger"] for c in comp)
        print(f"  triggers: {dict(trig)}")
        print(f"  boundaries per session: {dict(sorted(chain_depth.items()))}")

    print("\n== what survives a compaction boundary ==")
    total = sum(survivors.values()) or 1
    for kind, n in survivors.most_common():
        print(f"  {kind:26s} {n:6,d}  {n/total*100:5.1f}%")

    print("\n== tool traffic in the main thread (pre-compaction context) ==")
    names = sorted(set(args_ch) | set(res_ch),
                   key=lambda n: -(args_ch[n] + res_ch[n]))
    grand = (sum(args_ch.values()) + sum(res_ch.values())) / CHARS_PER_TOKEN or 1
    print(f"  {'tool':22s} {'calls':>7s} {'args tok':>10s} {'result tok':>11s} {'total':>11s} {'share':>7s} {'per call':>9s}")
    for name in names:
        a = args_ch[name] / CHARS_PER_TOKEN
        r = res_ch[name] / CHARS_PER_TOKEN
        tot = a + r
        if tot / grand < 0.001:
            continue
        per = tot / max(calls[name], 1)
        print(f"  {name[:22]:22s} {calls[name]:7,d} {a:10,.0f} {r:11,.0f} {tot:11,.0f} {tot/grand*100:6.1f}% {per:9,.0f}")
    print(f"  {'TOTAL':22s} {sum(calls.values()):7,d} {'':10s} {'':11s} {grand:11,.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--min-size", type=int, default=300_000,
                    help="skip transcripts smaller than this (bytes)")
    ap.add_argument("--session", help="analyze a single transcript instead")
    args = ap.parse_args()

    if args.session:
        paths = [args.session]
    else:
        paths = [p for p in glob(os.path.join(args.projects, "*", "*.jsonl"))
                 if os.path.getsize(p) >= args.min_size]
    print(f"scanning {len(paths)} transcript(s)\n")
    report(*analyze(paths))


if __name__ == "__main__":
    main()
