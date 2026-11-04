# User-supplied reliability design review

Type: review. Owners: hq-c58737, hq-704fe5, hq-e10b76.
Source: the user's review message following the initial design handoff.
This record preserves its verdict, evidence and implementation guardrails using
checkout-relative references in place of the message's host-specific file URLs.
No originating reviewer harness/model identity was supplied; the review is
recorded as user-provided, not as another verified agent review.

## Verdict and approval state

Recommend approval of hq commit
`95773e6eb742a3a4884126de9b93538be3676d84`,
`docs/specs/2026-11-04-turn-pause-reliability-design.md`, for writing-plans.
SHA256: `be56c498086b686844e793caf6c9cdbe03282555e61d4552f5bc241b9a005214`.
No spec revision is requested. No blocking findings were reported.

The message explicitly says that the next action is to reply approving the spec.
It is an approval recommendation, not an explicit grant to proceed. Human design
approval remains pending. Direct hq/lore fixes remain unmerged and need separate
live activation approval; approval of this design does not supply that grant.

## Review verification

The review checked the frozen spec against the worktree code, task records and
the replay attachments. Safe-reader scope agrees with `protect.touches_protected`,
`Judge.__call__` and `allowlist.shell`. Keeping the protected-path matcher as a
fast pre-check lets `allowlist`/`shlex` remain lazily loaded for paused or matching
protected-path calls. Excluding `tasks attach` matters because that paused-read
classification still copies files and runs record hooks.

The script, pilot and full measurement on hq-704fe5 agree with the audit and
`limits.with_budget`: seven roots, 217 files, eight snapshots; 12h gives45 spawns,
48h gives180; limits changes retain their cutover pause. Cap60 gives the audited
workflow headroom and preserves the control's first refusal at call501 after
9.8567 active hours. Larger legitimate plans can still stop at61, and a low-call
runaway gains30 more spawns. Replay does not prove completion of work prevented
by the observed interruptions.

The review checked the history proposal against `Store.locked`, hook lifecycle,
`notify.send` and the existing pause CLI. A co-located 128-event/128-KiB buffer
avoids cross-file crash skew. Directory scans used to resolve status sessions are
CLI work rather than hook work.

## Guardrails to carry into the implementation plan

1. Protected Bash reads must allow the real metadata shape, not just command-only
   test helpers: `command`, optional `description` as str and optional `timeout`
   as int excluding bool. Reject unknown or execution-altering fields including
   shell, login, tty, workdir, run_in_background and dangerouslyDisableSandbox.
   The recorded Claude fixture contains command plus description. Preserve the
   command scanner and the lazy-import invariant; add focused fixture coverage
   for accepted metadata and refused execution fields.
2. Recovery text and pointer-audit guidance must use concrete expanded absolute
   paths or checkout-relative paths with the allowed reader programs. The
   protected matcher recognizes tilde paths, but the shell scanner rejects tilde
   syntax. Do not recommend tilde, globs, or composed commands. The programs are
   cat/head/tail/wc/ls and literal `readlink -f`.
3. The history reason vocabulary includes limits-changed as well as active,
   calls, spawns and compactions. Record turn_start on genuine prompts and on
   lazy initialization when the hook sees no turn. Seven-day idle-state clearing
   rewrites only envelopes with non-null active state; it must not refresh an
   already-ended record's mtime or repeat clearing on each SessionEnd. Ended
   history keeps the separate30-day retention behavior.

## Controller verification and disposition

Re-read the cited fixture, shell validator, lazy initialization and current prune
implementation; the guardrails address real input-shape and lifecycle edges.
Verified the current spec equals the frozen Git blob and matches the full hash
above. Accept all three as plan details under the existing design, without
changing the frozen spec or writing planned feature code.

Additional planning consequence: lazy initialization immediately followed by a
genuine prompt must not fabricate two user turns or duplicate turn_start events.
Preserve distinct implicit and genuine starts while representing the actual turn
boundary once.

No tests or replay were rerun for this review-record update. No threshold,
instruction activation, branch integration, service or host pointer changed.
