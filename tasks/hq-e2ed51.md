---
id: hq-e2ed51
title: Stop the reviewer and Codex skill-path file-not-found streams
status: todo
priority: "2"
created: 2026-09-27T11:20:54Z
updated: 2026-09-27T13:05:55Z
depends: [obs-18b8eb]
tags: [obs, skills]
source: docs/notes/2026-09-27-path-mistakes-brief.md
agent: claude-code/claude-opus-5-5
---

Most file-not-found errors in the obs report (2026-09-26 §2–3) are not the working agent: in Claude Code they come from the security-guidance plugin's background reviewer starting in a worktree that finishing the branch has already removed; in Codex, from skill paths shown behind aliases over a nested agents/skills layout. Goal: neither produces a steady stream of failed reads, measured by obs-18b8eb's path-relation labels. Brief: docs/notes/2026-09-27-path-mistakes-brief.md. Research first; the settings or layout change is filed from its results.

## Notes

- 2026-09-27T12:07:13Z (main): security-guidance disabled in 8d701d6 (user decision after ai-3b2222); the plugin used ANTHROPIC_API_KEY auth, so its cost was most likely API-billed
- 2026-09-27T12:17:05Z (main): upstream (2026-09-27): findings-body bug is claude-plugins-official#4960 (dup claude-code#92987); invented roots are #4693; worktree-removal race unreported (59 of 64 own-worktree Read failures follow a git worktree remove by ~3 s; draft issue prepared); API-key preference is the flip side of claude-code#96860. Disable verified: a fresh session logs no plugin activity.
- 2026-09-27T12:20:56Z (main): filed claude-plugins-official#6320 (worktree-removal race); +1 on #4960 and #4693
- 2026-09-27T12:24:15Z (main): commented on claude-code#96860: reviews bill ANTHROPIC_API_KEY over the subscription when both exist
- 2026-09-27T13:05:55Z (main): Both fixes are in (reviewer disabled 8d701d6; skills flattened f4f1a94, 86c3c77). Verify and close when obs-18b8eb's path-relation labels show reviewer and Codex skill-path file-not-found near zero after 2026-09-27.
