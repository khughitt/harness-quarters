# Antigravity worker defaults and task-id colors

## Problem

Antigravity should keep unbudgeted runners small and make task references easy to
scan. hq-32317f concerns worker defaults; hq-db39da asks whether reply identifiers
can use project colors. This brief prepares evidence gathering, not activation.

## Current behaviour and evidence

- Installed `agy --version` reports **1.5.1** (2026-11-05). `command -v agy`
  resolves to the user's local binary, outside hq's declared launchers.
- Commit a2ebc48c introduced five defaults of `4` for Claude Code, Codex and pi:
  `PYTEST_XDIST_AUTO_NUM_WORKERS`, `CARGO_BUILD_JOBS`, `RUST_TEST_THREADS`,
  `NEXTEST_TEST_THREADS`, `GOMAXPROCS`. `tools/test_worker_defaults.py` covers
  those three harnesses only. `links.toml` declares agy settings and customization
  links, with no agy launcher; `agy/settings.json` declares no worker environment.
  The absence of a supported setting was reported for 1.4.12, not verified for
  installed 1.5.1. Fresh agy tool-shell inheritance remains unmeasured.
- `agy/settings.json` configures familiar's statusline (b864334a). That configuration
  does not prove inline reply styling or statusline truecolor rendering.
- hq-db39da's filing session contains the user's question about shared task colors
  and a supplied assessment claiming ANSI stripping. The filing agent explicitly
  left the rendering claims unverified. Binary symbol names do not prove a call path.
- prism-fd46ae already owns renderer implementation across harnesses. The attached
  `reply-color-findings.md` on lore-587c8a covers four other harnesses, not agy;
  it distinguishes source findings from unrun probes. No overlapping open agy
  rendering or worker-default research task was found in the related task searches.

## Constraints

Keep canonical task ids bare; preserve useful bold verdicts and spacing. Read
project colors from public tasks JSON. Keep display styling out of stored model
context. Worker defaults must leave host library-thread settings and budget-grant
markers alone, and allow host-budget to replace defaults with its grant.

Preserve live model picks and the existing local agy settings edit. Home routing
belongs in `links.toml`; applying home links is a separate authorized operation
from main. Coordinate hook changes with hq-7bed89 and hq-c59809 without making
those unrelated questions dependencies. Renderer implementation remains with prism.

## Alternatives

1. Prefer a documented native agy environment setting and a supported display
   extension, if version-bound evidence establishes them.
2. For worker defaults, consider an hq launcher only if native configuration
   cannot deliver them. For color, report a supported statusline surface separately
   if inline styling is unavailable; it does not satisfy inline coloring.
3. Retain current configuration and readable structural formatting while evidence
   is incomplete. This is the current lean until the two bounded investigations
   identify supported routes. No renderer fork, binary patch or parallel color
   implementation is justified by the recorded asks.

## Unanswered questions

- Which supported 1.5.1 setting or launch route can supply the five defaults to
  tool shells without interfering with explicit values or budget grants?
  Answer: version-bound documentation/source inspection and isolated local checks.
- Can the installed renderer color bare ids inline through a supported extension?
  If not, what can the statusline actually render? Answer: documentation/source
  tracing and, only where possible, a headless fixture with canned text.

Research excludes paid model calls, live desktop use and home changes. If a claim
cannot be settled locally without these, record it as unknown and describe the
smallest additional check and its authorization needs; do not build a new runner.

## Proposed decomposition

- hq-49ed70 is the shared coordination and closeout goal. Both existing ideas and
  the two research tasks are its children; their original bodies and sources stay intact.
- hq-a29f17 determines the supported worker-default route and wakes hq-32317f.
- hq-7826fd determines supported color surfaces and wakes hq-db39da; resulting
  renderer implementation remains prism-fd46ae.

Each original idea waits only on its own research result. Both investigations are
P2, small, mid complexity and direct process. Research completion updates this
brief and adds a finding with `--no-reviewed` to its waiting idea before integration.
No implementation or separate design task is filed yet.
