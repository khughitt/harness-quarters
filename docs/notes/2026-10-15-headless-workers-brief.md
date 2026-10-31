# Headless and isolated harness runs

Scoping handoff, 2026-10-15. Goal: hq-40a8d0. Ideas: hq-7a69dc, hq-7c80a5, hq-305ede;
hq-dd66c1 reviewed in the same pass (drop proposed, covered by crew-9b4b47).

Updated 2026-10-30: worker-boundary reports hq-f678e7, hq-0806e7 and
hq-dc6f2e join this existing effort. Cross-session messaging hq-e15558 is
related context only and was left for its separate coordination effort.

## Problem

Workers and probes now run harnesses without a person at the terminal: crew starts pi
per attempt, probes and experiments start Claude Code in scratch homes, controllers
hand work to subagents. Each run needs, before launch, the home it starts from, the
facts that say how the harness behaves there, and what to check when a child ends
abnormally. Today each caller rediscovers these and some learn them by failure.
The new cases require preserving completed work after an error and proving a
fresh analyst cannot read private inputs through any of its tools.

## Current behaviour and evidence

- **pi agent directories.** crew's core design (crew `docs/specs/2026-10-13-crew-core-design.md`
  §6.2, §9) gives each attempt its own `PI_CODING_AGENT_DIR` and says hq owns the
  template it copies. The implemented `prepareAgentDir` (crew `src/agent-dir.ts`, crew
  `90f1c66`) needs no template: it writes `AGENTS.md` and returns the credential env,
  and `src/runtime/pi-rpc.ts` passes `--session-dir`, `--no-extensions`, `--no-skills`
  and `--no-prompt-templates`. pi 1.1.0's agent directory also reads `settings.json`,
  `models.json`, `auth.json`, `mcp.json`, `SYSTEM.md` and `APPEND_SYSTEM.md` (installed
  `docs/configuration.md`). A project's `.pi/settings.json` `sessionDir` is read before
  trust is resolved (`docs/security.md`).
- **pi facts.** `facts/capabilities.toml` records pi's MCP, headless controls,
  idempotent submission, child conversations, turn resumption and usage (hq-57132d). It
  has no entry for exit codes, the default session directory, the extension API, or
  context-file reporting, which crew §9 lists as unknown. lore-ba22f3's scope note
  expects hq's probe to settle context-file reporting. crew's `contextLookup` skips
  `AGENTS.md` when `AGENTS.override.md` exists but keeps `CLAUDE.md`; pi's docs say the
  override replaces both in the same directory.
- **Isolated Claude Code homes.** With `CLAUDE_CONFIG_DIR` set, Claude Code reads and
  writes `.claude.json` inside that directory (trans runbook `docs/runbooks/phone-inbox.md`
  on 2.1.296; hq's `docs/notes/2026-10-15-session-discovery-contract.md`). A preference
  seed at the sibling path is ignored, and cleanup of the sibling leaves the generated
  file and its backups behind. In one interactive run on 2.1.296 a fresh home showed
  theme, terms, directory trust and the permission-mode notice, and the command-line
  prompt never reached a conversation; typing it afterwards worked. trans records
  this as specific to that run. hq's own probes (hq-b2515c, hq-7b65dc) used isolated
  homes without recording an onboarding contract.
- **A child's abnormal end.** hq-7c80a5 (from prism, a Codex session, 2026-10-14): a
  subagent's model-capacity failure arrived after its check finished and before its
  cleanup and report; the controller reaped a named test process and reconciled the
  preserved work before reassigning it. The session was not read in this pass, so the
  harness's child mechanism and the process's owner are unknown.
- **Completed work behind an error.** hq-f678e7 has two matched filing events
  in Codex 0.165.0 session `01a18943-2b9d-7e50-926f-b74169571349`:
  calls/results at lines 2988/2992 and 6123/6126. The first controller inspection
  found the correction, checks, report and released claim already persisted;
  the second found completed operation/report evidence but an unreleased claim.
  An error alone establishes neither no effects nor a completed handoff.
- **Cleanup refusal.** hq-dc6f2e's worker session
  `01a18ab4-a56f-7341-8244-8b69059d7b4a` (Codex 0.165.0), lines 256/259,
  records a pre-execution rejection of the temporary-file wrapper's `rm -f`
  cleanup. The memory-capture call at 263 and result at 274 completed the sole
  authorized invocation: expected stdout, empty stderr, exit 0. Filing 295/299
  matches the record. Keep the case; no permission weakening is justified.
- **Analyst isolation.** hq-0806e7's Codex 0.166.0 session
  `01a18e07-0ba0-7632-8a9b-faf99870ecb8`, human line 15, explicitly asks for
  enforced key/source/world denial and says unrestricted children do not provide
  it; filing 192/195 matches. This is a user requirement, not just an agent's
  preferred safeguard. Autonomy at `e6b726a3a92dda597a0cf84b32c1f037673d7589`
  has `python/src/autonomy/sandbox/{spec,static,bwrap}.py`: isolated binds,
  overlap rejection and a denied-path `stat` probe. autonomy-c5c566 proved pi
  RPC through sandboxed stdio, but its old shared-network, actor-readable
  credential recipe is not today's approved recipe. autonomy-e4c0b5 subsequently
  landed model-only egress (`d00d744`, documented `2ef0c0e`). Applicability to
  this analyst and every tool remains unproven; no live analyst was launched.
  Qualified 2026-10-31 by hq-a99924: no supported launch yet; see
  "Analyst launch qualification" below.

## Constraints

hq owns homes, capability facts and their probes; crew owns attempts and their agent
directory; lore owns worker instructions (lore-ba22f3, lore-f800a1) and the subagent
skills; relay owns identity and events. Facts are read only through
`tools/harness-facts`; `unknown` is an answer. A pi version change is a new epoch
(README "Re-probing pi"). crew-ba0a02 already records process-exit and cleanup
evidence for one cross-harness review; hq-3be737's brief covers the inverse Codex case
(a process ended that should have lived). Related isolated-run feedback already
scoped: hq-96435f, hq-da1015.

The original cases above remain historical evidence. Fresh context and enforced
access are separate checks: the [official multi-agent documentation](https://developers.openai.com/api/docs/guides/agents-api/multi-agent)
says agents sharing an environment share its filesystem; that API statement does
not qualify the installed CLI's isolation. hq records the supported launch and
capability evidence; autonomy owns confinement and authority. No shared launcher,
permission setting, world state or live source may be changed by this scope pass.

Upstream screen, 2026-10-30: open/closed issue and PR searches for `capacity
subagent` and `"rm -f" permitted` returned no matches. Existing
[Codex #54884](https://github.com/openai/codex/issues/54884) remains open: failed
API turns omit end hooks; it is related, not proof of the same failure.
Default branch was `67f0994b532b8740f14b5b738af7b7b2a915b1d6`; its
CHANGELOG points to releases and notes command-lifecycle fix #44557. The
0.166.0 release notes establish no fix for these two observations. Commit
search `capacity subagent` returned none. `develop` and `development` lookups
returned 404; a full feature-branch scan was stopped. This is a limited screen,
not a claim no upstream fix exists. Recheck the exact failure before proposing
an upstream report, pin or workaround; publication remains separately authorized.

## Alternatives

pi template (hq-7a69dc):
1. **No hq template until a needed setting is shown — lean.** crew's flags and
   `prepareAgentDir` cover the first slice; record the facts first.
2. A checked-in template under `pi/` (settings, models) that crew copies.
3. An hq command that materializes a headless agent directory for a given pi pin.

A child's abnormal end (hq-7c80a5):
1. **Trace the one case first — lean**, then choose.
2. A controller recovery step in lore's subagent skills: after a child fails, list the
   processes and worktree state it left before reassigning.
3. An hq fact per harness, with a probe: does the harness stop a failed child's
   processes?

Restricted analyst (hq-0806e7):
1. **Qualify the existing autonomy/pi launch and denial route first — lean.**
2. Use an independently confined Codex executor if its current contract proves
   every analyst tool is inside the boundary.
3. Keep the live analyst blocked when neither route can prove the required denial.
   Fresh context or a confined numerical subprocess alone is insufficient.

For hq-f678e7, reuse hq-624fb9's recovery investigation and add persisted-effect
and claim reconciliation to its question. Do not add a competing investigation
or assume the upstream event fix alone would preserve the completed outcome.
For hq-dc6f2e, retain the successful bounded memory-capture route and shelve
permission-policy work until it cannot meet a concrete authorized capture need.

## Unanswered questions

- What exit codes, default session directory, extension surface and context-file
  report does pi 1.1.0 give, and does any make a template necessary? hq-f1aff0.
- Which harness and child mechanism left the process running, and who started it?
  hq-624fb9.
- Should the isolated-home onboarding behaviour become a typed fact with a probe? Not
  until a second observation; hq-305ede records it as guidance.
- Which persisted results and claim/process checks must a controller reconcile
  after an error, and what remains an upstream reporting gap? hq-624fb9, now
  including both hq-f678e7 cases without losing the original process-survival case.
- Which existing launch confines the fresh analyst and all its tools, with an
  allowed-read control and denied-read checks for key, source and world?
  Answered by hq-a99924 (below): none qualifies as a supported launch today; the
  smallest route and its check are named. Domain execution stays blocked.

## Analyst launch qualification (hq-a99924, 2026-10-31)

One read-only pass: code and records only. No model call, no launch, no private
input, key or world read. Every boundary statement below comes from reading code
and docs. The scripted check below has not run, and the earlier probes are not a
fresh end-to-end pass, so mm-62e2da's isolation gate stays closed.

**Verdict: unavailable as a supported launch.** No existing entry point starts a
fresh analyst under enforced denial with its inputs and outputs declared:

- `autonomy run` (autonomy `e6b726a`) never starts an actor. Its steps are
  `endpoint_side_unbuilt`, so every run closes `unwired` before launch, and it has
  no flag for read-only input binds, an output directory or extra denied paths.
- The only code that runs pi under the sandbox is `python/scripts/egress_live.py`
  (`just live-egress`): E21's live arm, a test script with one fixed prompt. It
  binds only node and pi, and its only denied entries are decision 13's three
  egress entries (`<config>`, the route file, the credential), from
  `egress_denied`. It is not an analyst launcher.
- hq's `pi/bin/pi` is a version-pinning wrapper with no confinement. pi's own
  `docs/security.md` says it has no tool boundary: tools run with the permissions
  of the pi process unless an OS boundary restricts them.

The missing piece is a launcher and its checks, not a kernel or harness feature.
It belongs with autonomy's sandbox, but §7 binds only toolchain paths and computes
its denied set from the world configuration, never from the spec. So
caller-declared input binds and extra denied paths need an envelope design
amendment, autonomy's decision. A confined Codex executor was not compared. The
brief leans to qualifying the pi route first, and the task compares Codex only
if the pi route cannot meet the requirement. Reading the code, the kernel
boundary covers every pi tool, so the gap is a launcher, which a Codex route
would also need. That reading is unproven until the scripted check passes.

**The smallest route: autonomy's sandbox and model route, as `egress_live.py`
composes them.** The contract to pin:

| Item | Value |
| --- | --- |
| Harness | pi 1.1.0 (`@earendil-works/pi-coding-agent`, hq `pi/package.json`), the pinned install run directly as `node_modules/.bin/pi`. Check its `package-lock.json` against hq's pin first, as `pi/bin/pi` does. Seen with node 26.5.0, bubblewrap 0.13.1, and rg 15.2.0 and fd 10.5.0 from `/usr/bin`, which pi's grep and find run and pi does not ship. A change in any of them is a new epoch for the check, as a pi version change is. |
| Confinement | autonomy `sandbox.bwrap` at `e6b726a`: `--unshare-all --die-with-parent --new-session --clearenv`, with a new `/proc` (its own PID namespace), `/dev` and `/tmp`. `/usr` and `/etc` are bound read-only, the `ro_binds` read-only, and one `scratch` read-write. Nothing else in the host filesystem exists in the namespace. The actor holds only fds 0-2. Resolve every bind source before building the argv (`egress_live.py` passes `pi_dir` unresolved), and run `prove` immediately before launch. |
| Fresh context | A new pi process per analysis, with a new `PI_CODING_AGENT_DIR` and `HOME` under `scratch`. Its `models.json` points the `anthropic` provider's `baseUrl` at the route listener (`http://127.0.0.1:4780`) with a placeholder `apiKey`. The prompt comes only over RPC from the caller. Flags as in `egress_live.py`: `--mode rpc --provider anthropic --model <listed model> --thinking off --session-dir <scratch>/sessions --no-approve --no-extensions --no-skills --no-prompt-templates --no-mcp`, with `PI_OFFLINE=1`, `PI_TELEMETRY=0` and `VERIFIABLY_MODEL_URL`. Addition not in `egress_live.py`: `--no-context-files`, so no `AGENTS.md` is loaded. (`PI_SKIP_VERSION_CHECK=1`, which `pi/bin/pi` sets, is already implied by `PI_OFFLINE=1` in pi 1.1.0.) |
| Tools | pi 1.1.0 built-ins: read, bash, edit, write, grep, find, ls. powershell throws on non-Windows platforms. The built-in extensions (`codemode`, `tool_search`) are off under `--no-extensions`. Fix the set with `--tools`, and launch the analyst with exactly the set the check tested. The `--tools` list only narrows what the model sees. The boundary is the mount and network namespace: bwrap runs autonomy's gate, which execs pi, so pi and every tool and child process start inside it. |
| Inputs | The staged analyst bundle only, bound read-only (`ro_binds`) from a fresh copy (mm Task 3's bundle). The static check refuses a bind root that is, contains or lies inside a denied path, by real path and by `(st_dev, st_ino)` ancestry. It checks bind roots only. bwrap's binds are understood to carry submounts, which this pass did not verify. So a pre-launch walk of each admitted tree is required, and does not exist yet. It must check three things. First, no mount below the root, detected by mount id (`statx` `STATX_MNT_ID` or `STATX_ATTR_MOUNT_ROOT`, or any `/proc/self/mountinfo` entry under it). A `st_dev` change misses a bind from the same filesystem. Second, no regular file with `st_nlink > 1`. Third, no file or directory inode equal to one under a denied root. The toolchain roots carry the same alias question. For the user-writable ones (node, pi), apply all three rules. For root-owned `/usr` and `/etc`, apply the mount and inode rules only, since system packages hold many hard-linked files. The walk skips a directory the user can neither list nor search: the analyst runs as the same uid and cannot reach it either. A directory that can be searched but not listed fails the walk. |
| Outputs | `scratch/outputs/` (scratch is the only writable bind). pi's agent dir and sessions are also in scratch. Release outputs by name on the host without following links (`openat2` with `RESOLVE_BENEATH` and `RESOLVE_NO_SYMLINKS`, or `O_NOFOLLOW` at each step). Open with `O_PATH` or `O_NONBLOCK` first and `fstat`, so a planted FIFO cannot stall the release. Accept regular files only, with `st_nlink == 1`. A symlink the analyst plants dangles inside the namespace but resolves on the host, so following it would read a denied path for the analyst. |
| Denied set | All of it must be supplied by the caller except decision 13's three egress entries. At `e6b726a`, nothing computes §7's world-derived roots (world and corpus roots, store, operations, `<state>`). The analyst's set is: those roots, the egress entries, the private key, the private config and receipts, and the source data roots. |
| Credential and network | The route credential stays with the proxy. It is a denied path and never bound; pi holds only the placeholder. The actor's network is its own loopback (abstract sockets included, with the network namespace unshared). The only way out is the route's listener, which forwards only the listed operations and models. This replaces autonomy-c5c566's recipe, which shared the host network and bound a readable `auth.json`. Whatever the analyst reads, the provider may receive, which is acceptable only for admitted inputs. |
| Other channels | Read-only `/etc` and the namespace's `/proc` and kernel interfaces stay readable (host configuration, kernel version). The requirement concerns paths, so this is low risk. The bound `/etc` must hold no denied material. The static check confirms only that no denied path lies under `/etc`, not that `/etc` holds no copy or link of denied content. |
| Cleanup | The caller owns all of it: `Sandboxed.close` (SIGKILL through the pidfd kills the namespace); `EgressSession.close`, or `kill` on failure; and the scratch and run directories, which `egress_live.py` leaves in place. Once the endpoint is built, `autonomy run` would own the run directory and disposition. |

**What `prove` establishes, and what it does not.** `prove(spec, denied)` runs the
static check, then `/usr/bin/python3 -I` in a separate namespace built from the
same spec. That process `stat`s each denied real path, which must give `ENOENT`,
and connects to two documentation addresses, which must give `ENETUNREACH`
(`EAFNOSUPPORT` is also accepted for the IPv6 one). The result shows the listed
denied paths are absent from a namespace built like the analyst's. It is not the
analyst's namespace or process. It does not exercise pi's tools, and it tests only
the listed path strings, not aliases inside an admitted tree. It is necessary, not
sufficient.

**The check to prepare: a scripted-upstream tool-denial run (not run).** It needs
no paid call. The model route's `upstream` is a local TLS server with a test CA.
That server answers `/v1/messages` with scripted `tool_use` turns and records every
`tool_result` pi sends back.

Preparation:
- Write a scripted Anthropic tool-use SSE stream. `FakeUpstream`'s `sse` mode in
  autonomy's `tests/egress_fixtures.py` sends only placeholder events. Serve it at
  `https://localhost:<port>`, with the certificate's SAN set and the route's
  `ca_file` pointing at the CA.
- Put the route under a temporary `XDG_CONFIG_HOME`, never the user's config, and
  base it on `pi_route`: `tools` in `fields`, `tool_use` and `tool_result` in
  `block_types`, and pi's `--model` in `models`. Its credential is a placeholder
  file that passes `check_credential`: owned by the user, mode 0600, one link.

Steps:
1. Build the fixture outside `scratch`, with a random suffix on each file name
   so a denied find cannot match an unrelated file in a bound tree.
   `F/key/private-key-<r>.json`, `F/source/series-<r>.txt` and
   `F/world/world-<r>.toml` each hold a fresh random sentinel (K, S, W).
   `F/bundle/allowed-<r>.tsv` holds sentinel A. (Steps 4 and 5 drop the suffix
   for brevity.) Record each file's sha256.
   Never put a sentinel literally in a tool input, or pi echoes it into request
   bodies, RPC events and session files. Search with a pattern that matches a
   sentinel without containing it (for a sentinel `abcdefgh`, the pattern
   `abcd[e]fgh`).
2. Spec: `ro_binds = (node, pi, F/bundle)`, all resolved. Denied = `F/key`,
   `F/source` and `F/world`, plus the egress entries. The bundle walk and `prove`
   must pass.
3. Launch pi as in the contract above, through `EgressSession` to the scripted
   upstream. The driver renews the lease throughout, and its deadline covers
   several greps over every bound tree; `egress_live.py`'s 240 s may not be
   enough. Use the exact `--tools` list the analyst will use (for example
   `read,bash,grep,find,ls,write`; add `edit` only if it is also tested).
4. Run an allowed control for each tool, with the same argument shape as that
   tool's denied calls. Each must return A, or name the file. Run the grep
   control first: once read and bash have put A into the session files in
   scratch, a small `limit` could cut the grep off before it reaches the
   bundle.
   - grep for A's pattern from `/` with `glob: "!{proc,etc,usr}"` and the
     same `limit` as the denied greps, and require `F/bundle/allowed.tsv` in
     the result;
   - read `F/bundle/allowed.tsv`;
   - bash `cat` it;
   - find `allowed.tsv` from `/`, with the same `limit` as the denied finds,
     and require it in the result;
   - ls `F/bundle`.
5. Run the denied checks for each of key, source and world. Each must give the
   expected OS-level result: `ENOENT`, an empty rg or fd result, `ls F` listing
   only `bundle` (inside the namespace, `F` is the parent directory bwrap
   creates for the bind), or a write judged on the host in step 7. A pi
   argument-validation error does not count.
   - read the file;
   - bash: `cat` the file, `ls -la` its directory, and `cat /proc/1/root/<path>`;
   - grep each sentinel's pattern from `/` with `glob: "!{proc,etc,usr}"` and an
     explicit `limit`.
     - The glob is required. rg exits 2 on any read error, and pi's grep
       reports any exit other than 0 or 1 as an error.
     - The namespace's new `/proc` holds unreadable files. So do the bound
       `/etc` and `/usr`: on this host, as the user, rg over `/etc` or `/usr`
       exits 2, and over the pi and node trees 1. So a grep from `/` that
       excludes less than these always fails.
     - The excluded system trees hold no denied path (the static check).
       Aliases there are the walk's to catch (its mount and inode rules).
       Content copies are the unchecked precondition under Other channels.
     - A slash-free negated glob excludes those names at any depth, so `F`
       must not sit under a directory named `proc`, `etc` or `usr`. rg 15's
       brace form was checked on a local tree.
     - `build_argv` mounts no `/sys`.
     - pi's grep and find stop at 100 matches, 1000 results or 50 KB, which is
       why step 4's controls run from `/` too.
     - A grep that returns an error makes the run inconclusive. pi's find
       hides traversal errors and needs no glob;
   - find files named like each fixture from `/`;
   - ls `F`;
   - write a file into each of `F/key`, `F/source` and `F/world`.
6. Run the escape checks:
   - bash connects to a non-loopback address, which must fail;
   - bash connects to the scripted upstream's port on loopback, which must give
     `ECONNREFUSED`, since the namespace has its own loopback;
   - write `scratch/outputs/result.txt`, which must appear on the host.
7. Judge the run. It passes when all of these hold:
   - every allowed control succeeds;
   - each denied call shows its expected OS-level result;
   - none of K, S or W appears in any tool result, upstream request body, pi's
     stdout or stderr, its session files or `scratch`, scanned on the host
     without following links (A is expected in the tool results, request
     bodies, RPC stdout and session files);
   - the host fixture is unchanged: same hashes and no new files under any
     `F/*` (inside the namespace, `F` is bwrap's own directory, so a write that
     succeeds there proves nothing);
   - the route closes `clean`.

   A tool that fails its allowed control makes the run inconclusive, not a pass:
   an unavailable tool is not evidence of denial.

The fixture run shows that pi's tools run inside the namespace and that unbound
paths are absent through each tested tool. The pre-launch walk covers aliases,
and the run does not, since the fixture plants none. The walk's own negative
tests plant a hard link, a same-filesystem bind submount and a tmpfs submount.
For the live analyst, the same spec takes the real denied set, and the walk and
`prove` run on it before launch. A tool-level run against real key, source or
world paths is a separate, authorized step, because a failed denial would copy
private bytes into the upstream log.

**Remaining owners.**
- autonomy: decide the design amendment (caller-declared input binds, output
  directory and extra denied paths), then build the supported analyst launch,
  the bundle walk, the no-follow output release and the scripted-upstream check.
  This pass authorizes none of it.
- mm: name the real denied paths and the bundle. Run Task 8's gate on that launch
  only after the check passes.
- hq: none beyond the pi pin. A pi version change is a new epoch for this check,
  as for the facts.

## Proposed decomposition

| Task | Next action | Ideas it wakes |
| --- | --- | --- |
| hq-f1aff0 | Probe the four pi facts and recommend template contents | hq-7a69dc (and a note on lore-ba22f3) |
| hq-624fb9 | Trace original and new capacity cases; reconcile effects, handoff, claims and processes | hq-7c80a5, hq-f678e7 |
| hq-305ede | Scoped: README guidance for isolated Claude Code homes | — |
| hq-a99924 | Qualify an existing confined analyst launch and prepare synthetic allowed/denied-read checks | hq-0806e7 |

hq-dc6f2e is shelved. Wake it when an authorized bounded diagnostic needs
file-backed capture that memory capture cannot satisfy, or refusal recurs with
no safe supported capture route. The other three original children and their
prior dispositions are unchanged; neither new idea is executable implementation.
