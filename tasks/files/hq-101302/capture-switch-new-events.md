| # | s | Event | Turn | `session_id` | `agent_id` / `agent_type` | codex | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0 | SessionStart | — | R | absent | P1 | source: startup; transcript: R's rollout |
| 2 | 0.2 | UserPromptSubmit | T1 | R | absent | P1 | transcript: R's rollout |
| 3 | 4.6 | PreToolUse | T1 | R | absent | P1 | tool: collaborationspawn_agent; transcript: R's rollout |
| 4 | 4.9 | PostToolUse | T1 | R | absent | P1 | tool: collaborationspawn_agent; transcript: R's rollout |
| 5 | 8.1 | Stop | T1 | R | absent | P1 | stop_hook_active: false; transcript: R's rollout |
| 6 | 9.2 | SubagentStart | T2 | R | W1 / `default` | P1 | transcript: W1's rollout |
| 7 | 16.0 | PreToolUse | T2 | R | W1 / `default` | P1 | tool: Bash; transcript: W1's rollout |
| — | 17.8 | *switch: /new* |  |  |  |  |  |
| 8 | 25.5 | SessionStart | — | R2 | absent | P1 | source: startup; transcript: R2's rollout |
| 9 | 25.7 | UserPromptSubmit | T3 | R2 | absent | P1 | transcript: R2's rollout |
| 10 | 29.7 | PreToolUse | T3 | R2 | absent | P1 | tool: Bash; transcript: R2's rollout |
| 11 | 30.0 | PostToolUse | T3 | R2 | absent | P1 | tool: Bash; transcript: R2's rollout |
| 12 | 31.3 | PostToolUse | T2 | R | W1 / `default` | P1 | tool: Bash; transcript: W1's rollout |
| 13 | 33.5 | Stop | T3 | R2 | absent | P1 | stop_hook_active: false; transcript: R2's rollout |
| 14 | 34.1 | SubagentStop | T2 | R | W1 / `default` | P1 | stop_hook_active: false; transcript: R's rollout; agent transcript: W1's rollout |
| 15 | 109.0 | SessionEnd | — | R2 | absent | P1 | reason: other; transcript: R2's rollout |
| 16 | 109.0 | SessionEnd | — | R | absent | P1 | reason: other; transcript: R's rollout |
