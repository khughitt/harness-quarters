# Turn-boundary gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refuse, once, a turn end while the session holds a live tasks claim, with a reason that carries the turn-boundary rules; and put those rules in AGENTS.md and the flow skill.

**Architecture:** `tasks claims` (new, in the tasks CLI) reads every registered prefix's claim store and nothing else. `ops/hooks/claim-guard --harness <h>` is a Stop guard: a pure `decide(harness, text, read)` over the hook input and that read, and a thin entry that prints `{"decision":"block","reason":…}` or nothing. The ai repository wires the entry into Claude Code and Codex and carries the rules the reason points at.

**Tech Stack:** Rust (tasks: clap, serde, assert_cmd tests), Python 3 stdlib (ops hooks, unittest), JSON harness configs, Markdown rules.

**Spec:** `docs/specs/2026-09-24-turn-boundary-gate-design.md` (this worktree).

## Global Constraints

- Three repositories, one worktree each, all named `turn-boundary-gate`: ai at `.worktrees/turn-boundary-gate` (exists), tasks created in Task 1, ops in Task 3. Before each `git worktree add`: `work-link --ensure .worktrees`; after: `git worktree lock --reason "on WORK_ROOT storage (host: $(uname -n))" .worktrees/turn-boundary-gate`. Neither ops nor tasks defines `just setup`.
- `$SCRATCH` is the executing session's scratchpad directory; probe files live there and are never committed.
- Show every path relative to the main checkout of its repository, prefixed `.worktrees/turn-boundary-gate/`.
- tasks gates: `just test-fast [<name>]` while working, `just gate` before landing. Never `cargo test` directly.
- ops gates: `just test-fast` while working, `just gate` before landing.
- `tasks check` before every commit in every repository.
- Conventional commits; no attribution trailers of any kind.
- The guard never writes, logs, or indexes. Its exit code is always 0 except an argument error.
- `CHILD_WAKES` starts `{"claude-code": False, "codex": False}`; an entry becomes `True` only when both the subagent run and the background-command run of Task 10 pass for that harness.
- Session match: `claim.session` equals the input `session_id`, `claude-code:<id>`, or `codex:<id>`; only `live: true` claims count.
- Claim-read timeout: 10 s.
- `tasks claims` output has no `warnings` key; any unreadable registry or store exits 1.
- Live probes use a throwaway project registered in the **real** registry under prefix `tbgp` and unregistered at the end (a harness's Bash tool gets its environment from the login profile, so an `XDG_*` override does not reach the model's `tasks` calls — ai-80b836). Every probe's tmux session is killed on exit by a trap.
- `ops/cli.toml` changes only in the ops main checkout, in Task 5: `bin/vendored` publishes a source edit from the default branch's checkout before it is committed, and ops' pre-commit runs `check-vendored` against every project's copy, so a worktree edit to it can never be committed. Before publishing, every destination is preflighted and nothing but a clean or already-published copy is overwritten.
- Do not touch `codex/config.toml`, and do not commit into a main checkout that has uncommitted changes to a file this plan changes; stop and ask.

## Review Focus

1. **Relay identity on the host.** With `[identity] relay = true`, claims are keyed `claude-code:<sessionId>`; the guard must still match. Test in Task 3 (`test_a_tagged_claude_session_is_held`).
2. **`tasks` not on the hook's `PATH`.** The hook runs in the launcher's environment, which may lack `~/.cargo/bin`; it must block with a reason that says so, not crash or pass. Test in Task 4 (`test_no_tasks_on_path_blocks_and_says_so`); Task 9 checks the real launcher.
3. **A legitimate mid-task question to the user.** The session holds a claim and must ask; the block must offer `tasks park … --waiting-on user --reason decision`, not only "continue". Test in Task 3 (`test_reason_names_every_branch`).
4. **Several claims held at once** (a controller with step claims): the reason names each id and its worktree. Test in Task 3 (`test_reason_names_every_held_claim`).
5. **An unreadable registry.** A permission error on `projects.toml` or an ancestor must fail `tasks claims`, not read as "no projects" and allow every stop. Test in Task 1 (`an_unreadable_registry_fails_instead_of_reading_empty`).
6. **A crash inside the guard on the harness's retry.** A bug must not turn `stop_hook_active: true` into a loop. Test in Task 4 (`test_a_crash_on_the_retry_allows`).

---

### Task 1: Registry read fails on anything but an absent file (tasks)

`Registry::load_from` treats `!path.exists()` as "no registry". `exists()` is false when an ancestor directory is unreadable, so a permission error reads as an empty registry, and `tasks claims` would answer `{"claims": []}` and let every stop through. Only `NotFound` means absent.

**Files:**
- Modify: `src/registry.rs` (`Registry::load_from`, lines 39-45)
- Test: `tests/cli.rs` (append)

**Interfaces:**
- Produces: `Registry::load_from` returns `Ok(Registry::default())` only for `ErrorKind::NotFound`; every other read error is `Err(Error::Io(..))` (JSON `kind: "io"`, exit 1). Every command that loads the registry inherits this.

- [ ] **Step 1: Create the tasks worktree**

```bash
cd ~/d/tasks
work-link --ensure .worktrees
git worktree add .worktrees/turn-boundary-gate -b turn-boundary-gate
git worktree lock --reason "on WORK_ROOT storage (host: $(uname -n))" .worktrees/turn-boundary-gate
```

- [ ] **Step 2: Write the failing test** (append to `tests/cli.rs`)

```rust
#[test]
fn an_unreadable_registry_fails_instead_of_reading_empty() {
    use std::os::unix::fs::PermissionsExt;
    let mut env = TestEnv::new();
    let root = env.init("zz");
    let dir = env.home.path().join(".config/tasks");
    std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o000)).unwrap();
    // Root reads through any mode; the case cannot be staged there.
    let readable = std::fs::read_to_string(dir.join("projects.toml")).is_ok();
    let out = env.cmd(&root).args(["prime", "--all-projects"]).output().unwrap();
    std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o755)).unwrap();
    if readable {
        return;
    }
    assert_eq!(out.status.code(), Some(1), "stdout: {}", String::from_utf8_lossy(&out.stdout));
    let error: serde_json::Value = serde_json::from_slice(&out.stderr).unwrap();
    assert_eq!(error["error"]["kind"], "io");
}
```

(`prime --all-projects` is used because `tasks claims` does not exist until Task 2; Task 2 adds the same case for `claims`.)

- [ ] **Step 3: Run it to see it fail**

Run: `just test-fast an_unreadable_registry`
Expected: FAIL — exit code 0 (the registry read as empty).

- [ ] **Step 4: Fix `load_from`** (`src/registry.rs`), replacing

```rust
        if !path.exists() {
            return Ok(Registry::default());
        }
        let text = std::fs::read_to_string(path)?;
```

with

```rust
        // Only an absent registry is empty. `exists()` is false when an ancestor is
        // unreadable too, which would read a permission error as "no projects".
        let text = match std::fs::read_to_string(path) {
            Ok(text) => text,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                return Ok(Registry::default());
            }
            Err(error) => return Err(error.into()),
        };
```

- [ ] **Step 5: Run the test and the suite**

Run: `just test-fast an_unreadable_registry`, then `just test-fast`
Expected: PASS; no other test changes behaviour (a registry that does not exist still reads as empty).

- [ ] **Step 6: Commit**

```bash
cd ~/d/tasks/.worktrees/turn-boundary-gate
tasks check
git add src/registry.rs tests/cli.rs
git commit -m "fix(registry): an unreadable registry is an error, not an empty one"
```

### Task 2: `tasks claims` (tasks)

**Files:**
- Create: `src/commands/claims.rs`
- Modify: `src/claims.rs` (`impl ClaimSnapshot`, after `pub fn live`)
- Modify: `src/output.rs` (new structs after `ClaimInfo`'s impl; `Output` enum; `pretty`; `warnings_of`)
- Modify: `src/cli.rs` (new `Command::Claims` variant after `Quiet`)
- Modify: `src/commands/mod.rs` (`pub mod claims;`; dispatch arm next to `Command::Quiet`)
- Modify: `tools/cli.toml` (ops main's committed `cli.toml` plus the `claims` row; Task 5 publishes the same bytes from ops)
- Modify: `README.md` (one usage line after the `tasks quiet` line near 259)
- Test: `tests/cli.rs` (append)

**Interfaces:**
- Consumes: Task 1's registry read.
- Produces: `tasks claims [--all-projects]` → stdout `{"claims":[{"id","prefix","owner","session","host","pid"?,"worktree","started","seen","live"}…]}`, exit 0; exit 1 with the usual JSON error (`kind: "config"` for a corrupt store) when any store or the registry cannot be read. Task 3 parses exactly `id, prefix, session, live, host, worktree`. The inventory row is
  `path = ["claims"]`, summary `Every claim in the registry's claim stores, with liveness; opens no checkout`, options `[{ shared = "all_projects", value = "none" }]`; Task 5 adds the identical row to ops.

- [ ] **Step 1: Build the inventory copy**

The row goes after the `quiet` command block. Start from ops main's committed file so the bytes are exactly what Task 5 will publish:

```bash
cd ~/d/tasks/.worktrees/turn-boundary-gate
git -C ~/d/ops show main:cli.toml > tools/cli.toml
python3 - <<'EOF'
import pathlib
p = pathlib.Path("tools/cli.toml")
s = p.read_text()
anchor = 'path = ["quiet"]'
start = s.index(anchor)
end = s.index("\n]\n", start) + len("\n]\n")
row = ('\n[[cli.tasks.commands]]\npath = ["claims"]\n'
       'summary = "Every claim in the registry\'s claim stores, with liveness; opens no checkout"\n'
       'options = [\n  { shared = "all_projects", value = "none" },\n]\n')
p.write_text(s[:end] + row + s[end:])
EOF
git diff --stat tools/cli.toml
```

Expected: `tools/cli.toml` differs from the branch's committed copy by the new row, plus whatever ops main has published since tasks last committed its copy.

- [ ] **Step 2: Write the failing tests** (append to `tests/cli.rs`)

```rust
fn start_as(env: &TestEnv, dir: &std::path::Path, id: &str, session: &str) {
    env.cmd(dir)
        .env("TASKS_SESSION", session)
        .env("TASKS_SESSION_PID", std::process::id().to_string())
        .args(["start", id])
        .assert()
        .success();
}

#[test]
fn claims_lists_a_claim_whose_task_file_the_registered_checkout_lacks() {
    let mut env = TestEnv::new();
    let root = env.init("zz");
    let id = env.json(&root, &["add", "worktree only"])["id"]
        .as_str()
        .unwrap()
        .to_string();
    start_as(&env, &root, &id, "probe-session");
    // A task created on a worktree branch has no file in the registered checkout.
    std::fs::remove_file(root.join(format!("tasks/{id}.md"))).unwrap();
    let prime = env.json(&root, &["prime", "--all-projects"]);
    assert!(prime["doing"].as_array().unwrap().is_empty());

    let out = env.json(&root, &["claims"]);
    let claims = out["claims"].as_array().unwrap();
    assert_eq!(claims.len(), 1);
    assert_eq!(claims[0]["id"], id.as_str());
    assert_eq!(claims[0]["prefix"], "zz");
    assert_eq!(claims[0]["session"], "probe-session");
    assert_eq!(claims[0]["live"], true);
    assert!(claims[0]["host"].is_string());
    assert!(claims[0]["worktree"].is_string());
    assert!(out.get("warnings").is_none());
}

#[test]
fn claims_reads_the_store_of_a_project_whose_checkout_is_gone() {
    let mut env = TestEnv::new();
    let here = env.init("zz");
    let gone = env.init("yy");
    let id = env.json(&gone, &["add", "elsewhere"])["id"]
        .as_str()
        .unwrap()
        .to_string();
    start_as(&env, &gone, &id, "probe-session");
    std::fs::remove_dir_all(&gone).unwrap();

    let out = env.json(&here, &["claims", "--all-projects"]);
    let claims = out["claims"].as_array().unwrap();
    assert_eq!(claims.len(), 1);
    assert_eq!(claims[0]["id"], id.as_str());
    assert_eq!(claims[0]["prefix"], "yy");
}

#[test]
fn claims_fails_when_the_registry_is_unreadable() {
    use std::os::unix::fs::PermissionsExt;
    let mut env = TestEnv::new();
    let root = env.init("zz");
    let dir = env.home.path().join(".config/tasks");
    std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o000)).unwrap();
    let readable = std::fs::read_to_string(dir.join("projects.toml")).is_ok();
    let out = env.cmd(&root).args(["claims"]).output().unwrap();
    std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o755)).unwrap();
    if readable {
        return;
    }
    assert_eq!(out.status.code(), Some(1));
    assert!(out.stdout.is_empty());
}

#[test]
fn claims_is_empty_when_no_store_exists() {
    let mut env = TestEnv::new();
    let root = env.init("zz");
    let out = env.json(&root, &["claims"]);
    assert_eq!(out, serde_json::json!({ "claims": [] }));
}

#[test]
fn claims_fails_on_a_corrupt_store() {
    let mut env = TestEnv::new();
    let root = env.init("zz");
    let store = env.claim_store("zz");
    std::fs::create_dir_all(store.parent().unwrap()).unwrap();
    std::fs::write(&store, "claims = [not toml").unwrap();
    assert_eq!(env.fail(&root, &["claims"]), "config");
}

#[test]
fn claims_reports_a_stale_claim_as_not_live() {
    let mut env = TestEnv::new();
    let root = env.init("zz");
    let store = env.claim_store("zz");
    std::fs::create_dir_all(store.parent().unwrap()).unwrap();
    // No pid, seen long ago: the TTL path, stale.
    std::fs::write(
        &store,
        "[claims.\"zz-000001\"]\nowner = \"tester\"\nsession = \"old\"\nhost = \"h\"\n\
         worktree = \"/x\"\nstarted = \"2026-01-01T00:00:00Z\"\nseen = \"2026-01-01T00:00:00Z\"\n",
    )
    .unwrap();
    let out = env.json(&root, &["claims"]);
    assert_eq!(out["claims"][0]["id"], "zz-000001");
    assert_eq!(out["claims"][0]["live"], false);
}

#[test]
fn claims_agrees_with_prime_on_a_live_claim() {
    let mut env = TestEnv::new();
    let root = env.init("zz");
    let id = env.json(&root, &["add", "both see it"])["id"]
        .as_str()
        .unwrap()
        .to_string();
    start_as(&env, &root, &id, "probe-session");
    let prime = env.json(&root, &["prime", "--all-projects"]);
    let claims = env.json(&root, &["claims"]);
    assert_eq!(prime["doing"][0]["claim"]["live"], claims["claims"][0]["live"]);
    assert_eq!(prime["doing"][0]["claim"]["session"], claims["claims"][0]["session"]);
}
```

- [ ] **Step 3: Run them to see them fail**

Run: `just test-fast claims_`
Expected: FAIL — `tasks claims` is an unrecognized subcommand (exit 2), and `surface::tests::parser_surface_equals_table` fails because `tools/cli.toml` has a `claims` row the parser lacks.

- [ ] **Step 4: Add `ClaimSnapshot::iter`** (`src/claims.rs`, inside `impl ClaimSnapshot`, after `pub fn live`)

```rust
    /// Every claim with its liveness verdict, in id order.
    pub fn iter(&self) -> impl Iterator<Item = (&String, &(Claim, Liveness))> {
        self.by_id.iter()
    }
```

- [ ] **Step 5: Add the output types** (`src/output.rs`, after `impl ClaimInfo { … }`)

```rust
/// One row of `tasks claims`: the claim as `prime` shows it, plus the id and the prefix
/// whose store holds it.
#[derive(Serialize)]
pub struct ClaimRow {
    pub id: String,
    pub prefix: String,
    #[serde(flatten)]
    pub claim: ClaimInfo,
}

/// `tasks claims`. No `warnings`: every store is read or the command fails, so there is
/// nothing partial to warn about (ai docs/specs/2026-09-24-turn-boundary-gate-design.md
/// §3.1).
#[derive(Serialize)]
pub struct ClaimsOut {
    pub claims: Vec<ClaimRow>,
}
```

Add `Claims(ClaimsOut),` to `enum Output` after `Quiet(QuietOut),`. In `fn pretty`, add after the `Output::Quiet` arm:

```rust
        Output::Claims(o) => o
            .claims
            .iter()
            .map(|row| {
                let live = if row.claim.live { "live" } else { "stale" };
                format!("{}  {}  {}  {}", row.id, row.claim.session, live, row.claim.worktree)
            })
            .collect::<Vec<_>>()
            .join("\n"),
```

In `fn warnings_of`, add after the `Output::Quiet` arm: `Output::Claims(_) => Vec::new(),`

- [ ] **Step 6: Add the command** (`src/commands/claims.rs`)

```rust
//! `tasks claims`: every claim in every registered prefix's claim store, with its
//! liveness. It opens no checkout, so a claim on a task that exists only in a worktree is
//! listed and an unreachable checkout changes nothing. A store that cannot be read fails
//! the command: there is no partial answer (ai docs/specs/2026-09-24-turn-boundary-gate-design.md §3.1).

use crate::claims::ClaimSnapshot;
use crate::error::Result;
use crate::output::{ClaimInfo, ClaimRow, ClaimsOut, Output};
use crate::registry::Registry;

pub fn run() -> Result<Output> {
    let registry = Registry::load()?;
    let mut claims = Vec::new();
    // One prefix at a time so each row carries the prefix of the store that holds it.
    for prefix in registry.projects.keys() {
        let snapshot = ClaimSnapshot::load(std::iter::once(prefix.as_str()))?;
        for (id, (claim, live)) in snapshot.iter() {
            claims.push(ClaimRow {
                id: id.clone(),
                prefix: prefix.clone(),
                claim: ClaimInfo::of(claim, live),
            });
        }
    }
    Ok(Output::Claims(ClaimsOut { claims }))
}
```

In `src/commands/mod.rs`: add `pub mod claims;` after `pub mod check;`, and in `pub fn run`'s match, before the `Command::Quiet {` arm:

```rust
        Command::Claims { all_projects: _ } => claims::run(),
```

- [ ] **Step 7: Add the CLI variant** (`src/cli.rs`, after the `Quiet { … },` variant, before the enum's closing `}`)

```rust
    /// Every claim in the registry's claim stores, with liveness; opens no checkout.
    Claims {
        /// The default and only scope; accepted for consistency with other read commands.
        #[arg(long)]
        all_projects: bool,
    },
```

- [ ] **Step 8: Run the tests**

Run: `just test-fast claims_` then `just test-fast surface`
Expected: all PASS.

- [ ] **Step 9: README line** (after the `tasks quiet` usage line near `README.md:259`)

```
    tasks claims                     # every claim in every project's store, live or stale; what a Stop hook reads
```

- [ ] **Step 10: Gate and commit**

Run: `just gate`
Expected: PASS (format, clippy, `tasks check`, full suite).

```bash
git -C ~/d/tasks/.worktrees/turn-boundary-gate add src tests tools/cli.toml README.md
git -C ~/d/tasks/.worktrees/turn-boundary-gate commit -m "feat(claims): tasks claims reads every claim store without a checkout"
```

### Task 3: claim-guard decision core (ops)

**Files:**
- Create: `hooks/claim-guard` (executable)
- Test: `tests/test_claim_guard.py`

**Interfaces:**
- Consumes: Task 2's JSON shape (fields `id, prefix, session, live, host, worktree`).
- Produces (module functions Task 4 and later tasks use):
  - `HARNESSES = ("claude-code", "codex")`
  - `CHILD_WAKES: dict[str, bool]`
  - `class ReadFailed(Exception)`
  - `parse_claims(text: str) -> list[dict]` — raises `ReadFailed`
  - `held(claims: list[dict], session: str) -> list[dict]`
  - `reason(harness: str, claims: list[dict]) -> str`
  - `decide(harness: str, text: str, read: Callable[[], list[dict]]) -> str | None` — `None` allows, a string is the block reason. Never raises.

- [ ] **Step 0: Create the ops worktree**

```bash
cd ~/d/ops
work-link --ensure .worktrees
git worktree add .worktrees/turn-boundary-gate -b turn-boundary-gate
git worktree lock --reason "on WORK_ROOT storage (host: $(uname -n))" .worktrees/turn-boundary-gate
```

This branch never touches `cli.toml` (Global Constraints), so ops' pre-commit `check-vendored` passes on every commit here.

- [ ] **Step 1: Write the failing tests** (`tests/test_claim_guard.py`)

```python
"""The Stop guard on held claims: decide() over the hook input and a claim read."""
import json
import pathlib

from tests.test_tt import Sandbox, load

HOOKS = pathlib.Path(__file__).resolve().parent.parent / "hooks"
guard = load("claim-guard", HOOKS)

SESSION = "0f5c2d1e-1111-4222-8333-444455556666"


def claim(id="ai-000001", session=SESSION, live=True, worktree="/w/ai"):
    return {"id": id, "prefix": id.split("-")[0], "session": session, "live": live,
            "host": "host-a", "worktree": worktree}


def stop(**fields):
    return json.dumps({"session_id": SESSION, "stop_hook_active": False, **fields})


def reads(claims):
    return lambda: claims


def fails(message):
    def read():
        raise guard.ReadFailed(message)
    return read


class DecideTests(Sandbox):
    def test_own_live_claim_blocks(self):
        self.assertIn("ai-000001", guard.decide("claude-code", stop(), reads([claim()])))

    def test_another_sessions_claim_allows(self):
        self.assertIsNone(guard.decide("claude-code", stop(), reads([claim(session="other")])))

    def test_no_claim_allows(self):
        self.assertIsNone(guard.decide("claude-code", stop(), reads([])))

    def test_stale_claim_allows(self):
        self.assertIsNone(guard.decide("claude-code", stop(), reads([claim(live=False)])))

    def test_retry_allows_even_with_a_held_claim(self):
        self.assertIsNone(guard.decide("claude-code", stop(stop_hook_active=True), reads([claim()])))

    def test_retry_allows_even_when_the_read_fails(self):
        self.assertIsNone(guard.decide("codex", stop(stop_hook_active=True), fails("boom")))

    def test_retry_never_reads(self):
        def read():
            raise AssertionError("read on the retry")
        self.assertIsNone(guard.decide("codex", stop(stop_hook_active=True), read))

    def test_codex_tagged_claim_is_held(self):
        self.assertIsNotNone(guard.decide("codex", stop(), reads([claim(session=f"codex:{SESSION}")])))

    def test_a_tagged_claude_session_is_held(self):
        self.assertIsNotNone(guard.decide("claude-code", stop(), reads([claim(session=f"claude-code:{SESSION}")])))

    def test_unparseable_input_blocks(self):
        self.assertIn("could not be read", guard.decide("claude-code", "not json", reads([])))

    def test_input_without_a_session_blocks(self):
        text = json.dumps({"stop_hook_active": False})
        self.assertIn("session_id", guard.decide("claude-code", text, reads([])))

    def test_failed_read_blocks_with_the_error(self):
        result = guard.decide("claude-code", stop(), fails("tasks claims exited 1: corrupt"))
        self.assertIn("tasks claims exited 1: corrupt", result)

    def test_unexpected_exception_in_read_blocks(self):
        def read():
            raise KeyError("surprise")
        self.assertIn("surprise", guard.decide("claude-code", stop(), read))


class ParseTests(Sandbox):
    def test_well_formed(self):
        self.assertEqual(guard.parse_claims(json.dumps({"claims": [claim()]})), [claim()])

    def test_not_json(self):
        with self.assertRaises(guard.ReadFailed):
            guard.parse_claims("{")

    def test_no_claims_list(self):
        with self.assertRaises(guard.ReadFailed):
            guard.parse_claims(json.dumps({"doing": []}))

    def test_claim_missing_a_field(self):
        partial = claim()
        del partial["worktree"]
        with self.assertRaises(guard.ReadFailed):
            guard.parse_claims(json.dumps({"claims": [partial]}))

    def test_live_must_be_a_bool(self):
        with self.assertRaises(guard.ReadFailed):
            guard.parse_claims(json.dumps({"claims": [claim(live="yes")]}))


class ReasonTests(Sandbox):
    def test_reason_names_every_held_claim(self):
        text = guard.reason("claude-code", [claim("ai-000001", worktree="/w/a"), claim("ops-000002", worktree="/w/b")])
        for part in ("ai-000001", "/w/a", "ops-000002", "/w/b"):
            self.assertIn(part, text)

    def test_reason_names_every_branch(self):
        text = guard.reason("claude-code", [claim()])
        for part in ("Continue", "tasks park", "--waiting-on user", "tasks done",
                     "A child is running", "`&`", "subagent"):
            self.assertIn(part, text)

    def test_park_step_must_be_an_action(self):
        self.assertIn("never a state", guard.reason("codex", [claim()]))

    def test_subagent_exit_is_conditional(self):
        text = guard.reason("claude-code", [claim()])
        self.assertIn("only when the assignment is complete or blocked", text)
        self.assertIn("still running", text)
        self.assertNotIn("report your status to it and stop", text)

    def test_child_branch_follows_child_wakes(self):
        for harness in guard.HARNESSES:
            text = guard.reason(harness, [claim()])
            if guard.CHILD_WAKES[harness]:
                self.assertIn("its completion starts your next turn", text)
            else:
                self.assertIn("Do not end the turn", text)

    def test_both_harnesses_start_without_wake(self):
        self.assertEqual(guard.CHILD_WAKES, {"claude-code": False, "codex": False})

    def test_codex_wait_names_wait_agent(self):
        self.assertIn("wait_agent", guard.reason("codex", [claim()]))
```

- [ ] **Step 2: Run them to see them fail**

Run in the ops worktree: `python3 -m unittest tests.test_claim_guard -v`
Expected: ERROR — `FileNotFoundError` loading `hooks/claim-guard`.

- [ ] **Step 3: Write the core** (`hooks/claim-guard`; `chmod +x` it)

```python
#!/usr/bin/env python3
"""Stop guard: refuse a turn end, once, while this session holds a live tasks claim.

A guard in the functional-core sense (ai docs/specs/2026-09-21-functional-core-design.md
§3.4): `decide` maps the hook input and a claim read to allow (None) or a block reason,
and is total: its own failure is a block with that reason, never a pass. The harness
retries a refused stop with `stop_hook_active: true`, and that retry is always allowed,
so a block is a one-shot interruption, not a lock; the reason text is what the model acts
on (ai docs/specs/2026-09-24-turn-boundary-gate-design.md §3.2-3.3).

It never writes, logs, or indexes. The claim read is `tasks claims`, which reads every
registered prefix's claim store without opening a checkout and fails rather than answer
partially.
"""
import argparse
import json
import subprocess
import sys

HARNESSES = ("claude-code", "codex")
# Whether the harness starts a new controller turn when a child it runs finishes. True
# only when the controller-wake probe showed it for both a subagent and a background
# command on that harness (spec §3.3, §5); the safe text is the default.
CHILD_WAKES = {"claude-code": False, "codex": False}
CLAIM_FIELDS = ("id", "prefix", "session", "live", "host", "worktree")
TIMEOUT_S = 10
BOUNDED_WAIT = {
    "claude-code": "the harness's bounded wait (a foreground check with a timeout that covers it)",
    "codex": "the harness's bounded wait (`wait_agent` with a long timeout)",
}


class ReadFailed(Exception):
    """The claims could not be read completely; the message is for the model."""


def parse_claims(text):
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as error:
        raise ReadFailed(f"tasks claims printed something that is not JSON: {error}") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("claims"), list):
        raise ReadFailed("tasks claims printed no claims list")
    for entry in doc["claims"]:
        if not isinstance(entry, dict) or any(field not in entry for field in CLAIM_FIELDS):
            raise ReadFailed(f"tasks claims printed a claim without {', '.join(CLAIM_FIELDS)}")
        if not isinstance(entry["live"], bool) or not isinstance(entry["session"], str):
            raise ReadFailed(f"tasks claims printed a malformed claim for {entry['id']}")
    return doc["claims"]


def held(claims, session):
    wanted = {session, *(f"{harness}:{session}" for harness in HARNESSES)}
    return [entry for entry in claims if entry["live"] and entry["session"] in wanted]


def child_branch(harness):
    if CHILD_WAKES[harness]:
        return ("end the turn with a report naming the child, what it will produce, and who "
                "acts next; its completion starts your next turn.")
    return (f"Do not end the turn. Wait on the child with {BOUNDED_WAIT[harness]}, act on "
            "its result, and if the wait times out, check the child before waiting again.")


def reason(harness, claims):
    names = ", ".join(f"`{entry['id']}` in `{entry['worktree']}`" for entry in claims)
    return (
        f"You are ending a turn while this session holds a live task claim: {names}. "
        "Before the turn ends, do one: "
        "(1) Continue: the work is unblocked and yours; keep going. "
        "(2) Park: `tasks park <id> \"<next step>\"`, where the next step is an action and who "
        "takes it (\"rerun `just gate` in .worktrees/x, then dispatch the Task 6 review\"), "
        "never a state (\"waiting for next steps\"); add `--waiting-on user --reason "
        "review|decision|approval` only when a person must act. "
        "(3) Done: `tasks done <id> \"<what landed>\"` if it is finished. "
        f"(4) A child is running: {child_branch(harness)} A job detached with `&` or `nohup` "
        "is never a running child: nothing will re-invoke you. "
        "If you are a subagent, the claim is your controller's but the assignment is yours, "
        "and your turn's end is your final report: nothing wakes you again. Report and stop "
        "only when the assignment is complete or blocked on something only your controller "
        "or a person can resolve, and say which. If work remains or a check you started is "
        "still running, continue it, or wait on the check in the foreground or with the "
        "harness's bounded wait, then report."
    )


def decide(harness, text, read):
    """None to allow the stop, or the block reason. Never raises."""
    try:
        event = json.loads(text)
    except (json.JSONDecodeError, TypeError) as error:
        return f"claim-guard: the Stop input could not be read ({error}); if you hold a task claim, act on it before ending the turn."
    if not isinstance(event, dict):
        return "claim-guard: the Stop input could not be read (not a JSON object); if you hold a task claim, act on it before ending the turn."
    if event.get("stop_hook_active") is True:
        return None
    session = event.get("session_id")
    if not isinstance(session, str) or not session:
        return "claim-guard: the Stop input has no session_id, so held claims cannot be checked; if you hold a task claim, act on it before ending the turn."
    try:
        claims = read()
    except Exception as error:
        return (f"claim-guard: the claims could not be read ({error}). If you hold a task "
                "claim, park it with a next step or close it before ending the turn; "
                "otherwise say so and end.")
    mine = held(claims, session)
    return reason(harness, mine) if mine else None
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest tests.test_claim_guard -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/ops/.worktrees/turn-boundary-gate
tasks check
git add hooks/claim-guard tests/test_claim_guard.py
git commit -m "feat(hooks): claim-guard decision core for Stop on held claims"
```

### Task 4: claim-guard entry and shell tests (ops)

**Files:**
- Modify: `hooks/claim-guard` (append `read_claims`, `main`, `__main__`)
- Modify: `justfile` (`check_cmd`'s `py_compile` list gains `hooks/claim-guard`)
- Test: `tests/test_claim_guard.py` (append)

**Interfaces:**
- Consumes: Task 3's module.
- Produces: `read_claims(run=subprocess.run) -> list[dict]` (raises `ReadFailed`); `main(argv, stdin, stdout) -> int`; the executable `hooks/claim-guard --harness claude-code|codex` reading the Stop input on stdin.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_claim_guard.py`)

```python
import io
import stat
import subprocess
import sys

HOOK = HOOKS / "claim-guard"


class ReadTests(Sandbox):
    def test_timeout_is_a_read_failure(self):
        def run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="tasks", timeout=guard.TIMEOUT_S)
        with self.assertRaisesRegex(guard.ReadFailed, "within 10 s"):
            guard.read_claims(run)

    def test_nonzero_exit_is_a_read_failure_naming_stderr(self):
        def run(*args, **kwargs):
            return subprocess.CompletedProcess(args, 1, stdout="", stderr='{"error":{"kind":"config"}}')
        with self.assertRaisesRegex(guard.ReadFailed, "exited 1"):
            guard.read_claims(run)

    def test_reads_all_projects(self):
        seen = {}
        def run(argv, **kwargs):
            seen["argv"] = argv
            return subprocess.CompletedProcess(argv, 0, stdout='{"claims": []}', stderr="")
        self.assertEqual(guard.read_claims(run), [])
        self.assertEqual(seen["argv"], ["tasks", "claims", "--all-projects"])


class EntryTests(Sandbox):
    def stub(self, script):
        bin_dir = self.base / "bin"
        bin_dir.mkdir(exist_ok=True)
        tasks = bin_dir / "tasks"
        tasks.write_text("#!/bin/sh\n" + script)
        tasks.chmod(tasks.stat().st_mode | stat.S_IXUSR)
        return bin_dir

    def run_hook(self, path, payload, harness="claude-code"):
        env = {"PATH": f"{path}:/usr/bin:/bin", "HOME": str(self.base)}
        return subprocess.run([sys.executable, str(HOOK), "--harness", harness], input=payload,
                              env=env, capture_output=True, text=True)

    def test_held_claim_prints_a_block(self):
        body = json.dumps({"claims": [claim()]})
        result = self.run_hook(self.stub(f"echo '{body}'\n"), stop())
        self.assertEqual(result.returncode, 0, result.stderr)
        reply = json.loads(result.stdout)
        self.assertEqual(reply["decision"], "block")
        self.assertIn("ai-000001", reply["reason"])

    def test_no_claim_prints_nothing(self):
        result = self.run_hook(self.stub("echo '{\"claims\": []}'\n"), stop())
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_failing_tasks_blocks(self):
        result = self.run_hook(self.stub("echo boom >&2; exit 1\n"), stop())
        self.assertEqual(result.returncode, 0)
        self.assertIn("exited 1", json.loads(result.stdout)["reason"])

    def test_no_tasks_on_path_blocks_and_says_so(self):
        empty = self.base / "empty"
        empty.mkdir()
        env = {"PATH": str(empty), "HOME": str(self.base)}
        result = subprocess.run([sys.executable, str(HOOK), "--harness", "codex"], input=stop(),
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("tasks is not on PATH", json.loads(result.stdout)["reason"])

    def test_a_crash_on_the_retry_allows(self):
        def explode(*args):
            raise RuntimeError("bug")
        out = io.StringIO()
        original = guard.decide
        guard.decide = explode
        try:
            code = guard.main(["--harness", "claude-code"], io.StringIO(stop(stop_hook_active=True)), out)
        finally:
            guard.decide = original
        self.assertEqual((code, out.getvalue()), (0, ""))

    def test_a_crash_otherwise_blocks(self):
        def explode(*args):
            raise RuntimeError("bug")
        out = io.StringIO()
        original = guard.decide
        guard.decide = explode
        try:
            code = guard.main(["--harness", "claude-code"], io.StringIO(stop()), out)
        finally:
            guard.decide = original
        self.assertEqual(code, 0)
        self.assertIn("bug", json.loads(out.getvalue())["reason"])
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_claim_guard -v`
Expected: FAIL/ERROR — `guard.read_claims` and `guard.main` do not exist; the subprocess runs print nothing.

- [ ] **Step 3: Append the entry** (end of `hooks/claim-guard`)

```python
def read_claims(run=subprocess.run):
    try:
        done = run(["tasks", "claims", "--all-projects"], capture_output=True, text=True,
                   timeout=TIMEOUT_S)
    except FileNotFoundError:
        raise ReadFailed("tasks is not on PATH") from None
    except subprocess.TimeoutExpired:
        raise ReadFailed(f"tasks claims did not answer within {TIMEOUT_S} s") from None
    if done.returncode != 0:
        raise ReadFailed(f"tasks claims exited {done.returncode}: {done.stderr.strip()}")
    return parse_claims(done.stdout)


def _is_retry(text):
    try:
        event = json.loads(text)
    except Exception:
        return False
    return isinstance(event, dict) and event.get("stop_hook_active") is True


def main(argv, stdin, stdout):
    parser = argparse.ArgumentParser(prog="claim-guard")
    parser.add_argument("--harness", required=True, choices=HARNESSES)
    args = parser.parse_args(argv)
    text = stdin.read()
    try:
        verdict = decide(args.harness, text, read_claims)
    except Exception as error:
        # decide is total; this is a bug. Still never loop on the harness's retry.
        verdict = None if _is_retry(text) else (
            f"claim-guard failed ({error!r}); if you hold a task claim, act on it before "
            "ending the turn.")
    if verdict is not None:
        stdout.write(json.dumps({"decision": "block", "reason": verdict}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdin, sys.stdout))
```

In `justfile`, in `check_cmd`, after `hooks/claude-profile` in the `py_compile` list, add ` hooks/claim-guard`.

- [ ] **Step 4: Run the tests and the ops gate**

Run: `python3 -m unittest tests.test_claim_guard -v`, then `just gate`
Expected: all PASS (the full ops gate: `check-vendored`, `check`, and the suite).

- [ ] **Step 5: Commit**

```bash
cd ~/d/ops/.worktrees/turn-boundary-gate
git add hooks/claim-guard tests/test_claim_guard.py justfile
git commit -m "feat(hooks): claim-guard entry reads tasks claims and replies block or nothing"
```

### Task 5: Land tasks and ops, publish the inventory, reinstall, check against the real registry

This task changes main checkouts in ops, tasks, and (through publication) every project that vendors `cli.toml`. Stop and ask before any step whose preflight fails; never discard or overwrite an uncommitted change that is not an exact published copy.

**Files:**
- Modify (ops main checkout): `cli.toml` (the `claims` row)
- Written by publication: `tools/cli.toml` and `tools/cli_surface.py` in every vendoring project's main checkout

**Interfaces:**
- Consumes: the tasks branch (Tasks 1-2) and the ops branch (Tasks 3-4).
- Produces: `tasks claims` installed at `~/.cargo/bin/tasks`; `~/d/ops/hooks/claim-guard` on ops main; `cli.toml` with the `claims` row committed in ops and published everywhere.

- [ ] **Step 1: Gate both branches**

Run `just gate` in `~/d/tasks/.worktrees/turn-boundary-gate` and in `~/d/ops/.worktrees/turn-boundary-gate`.
Expected: PASS in both.

- [ ] **Step 2: Preflight every publication destination**

`vendored publish` copies `cli.toml` and `cli_surface.py` over every registered project's `tools/` copy without looking. A copy may be overwritten only if its working bytes equal the project's own `HEAD` (clean) or ops main's committed source (an earlier publication that project has not committed yet). Save as `$SCRATCH/preflight.py` and run it:

```python
import pathlib, subprocess, sys, tomllib
ops = pathlib.Path.home() / "d/ops"
sources = {"cli.toml": "cli.toml", "cli_surface.py": "bin/cli_surface.py"}
def show(root, rev_path):
    r = subprocess.run(["git", "-C", str(root), "show", rev_path], capture_output=True)
    return r.stdout if r.returncode == 0 else None
registry = tomllib.loads((pathlib.Path.home() / ".config/tasks/projects.toml").read_text())["projects"]
bad = []
for prefix, root in sorted(registry.items()):
    root = pathlib.Path(root.replace("~/", str(pathlib.Path.home()) + "/", 1))
    for name, src in sources.items():
        copy = root / "tools" / name
        if not copy.is_file():
            continue
        data = copy.read_bytes()
        if data == show(root, f"HEAD:tools/{name}") or data == show(ops, f"main:{src}"):
            continue
        bad.append(f"{prefix}: tools/{name} has local edits")
print("\n".join(bad) or "preflight: every destination is clean or an exact published copy")
sys.exit(1 if bad else 0)
```

Expected: the success line, exit 0. On exit 1: stop and ask the user, naming each project and file; do not publish.

- [ ] **Step 3: Add the row in ops main, publish, commit**

```bash
cd ~/d/ops
git status --short                      # expected: empty; otherwise stop and ask
python3 - <<'EOF'
import pathlib
p = pathlib.Path("cli.toml")
s = p.read_text()
start = s.index('path = ["quiet"]')
end = s.index("\n]\n", start) + len("\n]\n")
row = ('\n[[cli.tasks.commands]]\npath = ["claims"]\n'
       'summary = "Every claim in the registry\'s claim stores, with liveness; opens no checkout"\n'
       'options = [\n  { shared = "all_projects", value = "none" },\n]\n')
p.write_text(s[:end] + row + s[end:])
EOF
cmp cli.toml ~/d/tasks/.worktrees/turn-boundary-gate/tools/cli.toml   # prints nothing: the bytes Task 2 committed
just vendor-cli
just check
git add cli.toml
git commit -m "feat(cli): inventory row for tasks claims"
```

Expected: `cmp` silent; `vendor-cli` lists each `prefix: name` it wrote; `just check` and the pre-commit hook pass. Record the list of written projects: each now holds an uncommitted published copy, which is that project's to commit, as with every publication. Tell the user which ones in the end-of-task report.

- [ ] **Step 4: Land the ops hook branch**

```bash
cd ~/d/ops
git merge --ff-only turn-boundary-gate || git merge --no-edit turn-boundary-gate
just gate
```

Expected: PASS.

- [ ] **Step 5: Land tasks**

```bash
cd ~/d/tasks
git status --short
cmp tools/cli.toml .worktrees/turn-boundary-gate/tools/cli.toml
```

`tools/cli.toml` is now the copy Step 3 published, identical to the branch's (`cmp` silent): `git checkout -- tools/cli.toml`. Any other modified tracked file, or a `cmp` difference: stop and ask. Untracked files (such as a `tasks/*.md` feedback record) are left alone. Then:

```bash
git merge --ff-only turn-boundary-gate || git merge --no-edit turn-boundary-gate
just gate
cargo install --path .
tasks claims --all-projects | jq -e '(.claims | type == "array") and (has("warnings") | not)'
```

Expected: gate PASS; `jq` prints `true`.

- [ ] **Step 6: Real guard, real registry**

```bash
echo '{"session_id":"no-such-session","stop_hook_active":false}' | ~/d/ops/hooks/claim-guard --harness claude-code; echo "exit=$?"
echo "{\"session_id\":\"$CLAUDE_CODE_SESSION_ID\",\"stop_hook_active\":false}" | ~/d/ops/hooks/claim-guard --harness claude-code | jq -r .reason
```

Expected: the first prints nothing and `exit=0`. The second prints a reason naming `ai-21ea5d` when it is started in this session (start it first if it is parked), and nothing otherwise.

- [ ] **Step 7: Remove the landed worktrees**

For each of ops and tasks: check no host pointer resolves into the worktree (`readlink -f ~/bin/* ~/.local/bin/* 2>/dev/null | grep turn-boundary-gate` prints nothing), run `tt-report` there, then `git worktree unlock .worktrees/turn-boundary-gate && git worktree remove .worktrees/turn-boundary-gate && git branch -d turn-boundary-gate`.

### Task 6: Park next-step and continuation rules (ai)

**Files:**
- Modify: `AGENTS.md` (the "Decisions" section's last bullet, lines 59-65)
- Modify: `agents/skills/flow/SKILL.md` (rule 5, lines 35-49)

**Interfaces:**
- Produces: the text the guard's branch (2) repeats. The guard does not read these files.

- [ ] **Step 1: Extend the Decisions bullet**

In `.worktrees/turn-boundary-gate/AGENTS.md`, replace

```
  user: finish it, or `tasks park` the task with that step as the next action and resume
  it; hand it over only explicitly (`--waiting-on user --reason review`).
```

with

```
  user: finish it, or `tasks park` the task with that step as the next action and resume
  it; hand it over only explicitly (`--waiting-on user --reason review`). A park's next
  step is an action and who takes it ("rerun `just gate` in .worktrees/x, then dispatch
  the Task 6 review"), never a state ("waiting for next steps"). An unblocked task you
  hold is not parked between increments: continue until a blocker, a gate that needs a
  person, or the end of the session.
```

- [ ] **Step 2: Extend flow rule 5**

In `.worktrees/turn-boundary-gate/agents/skills/flow/SKILL.md`, replace

```
   reported as pending for the human; `--waiting-on user` is only for a human
   gate or an explicit handoff (`--reason review`).
```

with

```
   reported as pending for the human; `--waiting-on user` is only for a human
   gate or an explicit handoff (`--reason review`). The next step is an action
   and who takes it, never a state ("waiting for next steps"); an unblocked task
   is not parked between increments. Background work follows AGENTS.md
   "Processes": nothing the harness does not track is waited on across a turn.
```

- [ ] **Step 3: Check and commit**

```bash
cd ~/d/ai/.worktrees/turn-boundary-gate
grep -n "never a state" AGENTS.md agents/skills/flow/SKILL.md   # two hits
tasks done ai-c62995 "AGENTS.md Decisions and flow rule 5: a park's next step is an action with its actor; no parking between increments of unblocked work"
tasks check
git add AGENTS.md agents/skills/flow/SKILL.md tasks
git commit -m "docs(rules): a park names an action; no parking between increments"
```

### Task 7: Background-wait and worker rules (ai)

**Files:**
- Modify: `AGENTS.md` ("Processes" section: a new bullet after the existing one)

- [ ] **Step 1: Add the bullet**

In `.worktrees/turn-boundary-gate/AGENTS.md`, after the "Processes" section's first bullet (it ends with `its \`--kill\` is the user's decision, not yours.`), add:

```
- Never end a turn waiting on work the harness does not track. Run a long check in the
  foreground with a timeout that covers it, or through the harness's own background
  mechanism; a job detached with `&` or `nohup` never wakes you, so no turn ends waiting
  on a monitor of one. A controller with a running child ends its turn only where the
  harness is known to start its next turn when the child finishes (ops
  `hooks/claim-guard`'s `CHILD_WAKES`), and otherwise waits with the harness's bounded
  wait. A worker's turn end is its final report: it reports and stops only when its
  assignment is complete or blocked on its controller or a person, never with its own
  check still running. A child's "waiting on background work" is unverified until you
  check that the process or its output exists; after a wake-up, report what you observed,
  never a notification that did not arrive.
```

- [ ] **Step 2: Check and commit**

```bash
cd ~/d/ai/.worktrees/turn-boundary-gate
python3 tools/ops-docs check                              # identity regions untouched: prints nothing, exit 0
git diff --stat                                          # AGENTS.md only (plus tasks/)
tasks done ai-804671 "AGENTS.md Processes: no turn ends on untracked background work; controller waits unless CHILD_WAKES; a worker reports only when complete or blocked"
tasks check
git add AGENTS.md tasks
git commit -m "docs(rules): never end a turn on untracked background work"
```

### Task 8: Wire the guard into Claude Code and Codex (ai)

**Files:**
- Modify: `claude/settings.json` (`.hooks.Stop`)
- Modify: `codex/hooks.json` (`.hooks.Stop`)

**Interfaces:**
- Consumes: `~/d/ops/hooks/claim-guard` on ops main (Task 5).

- [ ] **Step 1: Add the entries**

```bash
cd ~/d/ai/.worktrees/turn-boundary-gate
python3 - <<'EOF'
import json, pathlib
for path, harness in (("claude/settings.json", "claude-code"), ("codex/hooks.json", "codex")):
    p = pathlib.Path(path)
    doc = json.loads(p.read_text())
    doc["hooks"]["Stop"].append({"hooks": [{"type": "command",
        "command": f"~/d/ops/hooks/claim-guard --harness {harness}"}]})
    p.write_text(json.dumps(doc, indent=2) + "\n")
EOF
git diff
```

Expected: each file gains exactly one `Stop` entry and no other change (if `json.dumps` reformats anything else, restore the file and add the entry by hand with the Edit tool instead).

- [ ] **Step 2: Validate**

```bash
jq -e '.hooks.Stop | map(.hooks[0].command) | index("~/d/ops/hooks/claim-guard --harness claude-code")' claude/settings.json
jq -e '.hooks.Stop | map(.hooks[0].command) | index("~/d/ops/hooks/claim-guard --harness codex")' codex/hooks.json
```

Expected: both print an index and exit 0.

- [ ] **Step 3: Commit**

```bash
tasks check
git add claude/settings.json codex/hooks.json
git commit -m "feat(hooks): wire claim-guard into Claude Code and Codex Stop"
```

The wiring takes effect when this branch lands on ai main (Task 11); Codex will then ask the user to trust the changed `hooks.json`.

### Task 9: Live checks — worktree regression and Stop cases

Runs against the real guard and real registry with a throwaway project `tbgp`. Every tmux session a step starts is killed by a trap. Results are notes on ai-21ea5d.

**Files:**
- Create (scratch, not committed): `$SCRATCH/tbgp/` project, `$SCRATCH/stop-settings.json`, `$SCRATCH/codex-home/`

- [ ] **Step 1: Throwaway project and worktree regression**

```bash
S=$(mktemp -d); cd "$S"; git init -q tbgp; cd tbgp; git commit -q --allow-empty -m init
tasks init --prefix tbgp; git add -A; git commit -q -m tasks
git worktree add -q "$S/tbgp-wt" -b wt; cd "$S/tbgp-wt"
ID=$(tasks add "worktree only" | jq -r .id)
TASKS_SESSION=tbgp-probe TASKS_SESSION_PID=$$ tasks start "$ID"
tasks prime --all-projects | jq --arg id "$ID" '[.doing[] | select(.id==$id)] | length'   # 0: the bug
echo '{"session_id":"tbgp-probe","stop_hook_active":false}' | ~/d/ops/hooks/claim-guard --harness claude-code | jq -r .decision
```

Expected: `0`, then `block`. Note: `tasks note ai-21ea5d "live: worktree-only claim $ID blocked by claim-guard; prime --all-projects did not list it"`.

- [ ] **Step 2: Claude Code, five cases**

Write `$S/stop-settings.json`:

```json
{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "~/d/ops/hooks/claim-guard --harness claude-code"}]}]}}
```

Run each case with `claude -p --settings "$S/stop-settings.json" --model claude-haiku-4-5-20251001 "<prompt>"` from `$S/tbgp`, prompts:
1. own claim: `Run: tasks add "case1" and tasks start <that id>. Then reply "done".` — expect the reply to show the block was acted on (a park with an action, continued work, or done).
2. other session: first `TASKS_SESSION=someone-else TASKS_SESSION_PID=$$ tasks start <new id>` from the shell, then prompt `Reply "ok".` — expect no block.
3. park: `Run tasks add "case3", tasks start it, then tasks park it "rerun case 3 in the probe" and reply "ok".` — expect no block.
4. retry: case 1's transcript shows a second Stop with `stop_hook_active: true` that passed (read it with `session-logs`).
5. subagent: `Dispatch a subagent that runs tasks add "case5" and tasks start <id>, then reports. When it reports, reply "ok".` — expect the controller blocked once; record whether the subagent was blocked too and what it did.

Record per case: blocked or not, and what the blocked turn did. `tasks note ai-21ea5d "live claude-code Stop cases: …"`.

- [ ] **Step 3: Codex, same five cases, native identity**

```bash
mkdir -p "$S/codex-home"; cp ~/.codex/auth.json "$S/codex-home/"
cat > "$S/codex-home/hooks.json" <<'EOF'
{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "~/d/ops/hooks/claim-guard --harness codex"}]}]}}
EOF
```

Run each case with `CODEX_HOME="$S/codex-home" codex exec --dangerously-bypass-hook-trust "<prompt>"` from `$S/tbgp`, **no** `TASKS_SESSION` in the environment. Case 5 uses Codex's subagent (`spawn_agent`); this is its first probe. Record as in Step 2: `tasks note ai-21ea5d "live codex Stop cases (native identity): …"`.

- [ ] **Step 4: Clean up**

```bash
tasks unregister tbgp
rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/tasks/claims/tbgp.toml" "${XDG_STATE_HOME:-$HOME/.local/state}/tasks/claims/tbgp.lock"
rm -rf "$S"
host-load --section session
```

Expected: `host-load` names nothing this session left running.

### Task 10: Wake judge (ai)

A wake is decided from the transcript, never the terminal. The judge fails closed: every input record must classify, the controller's turn must have ended (a final text-only reply of exactly WAITING, no tool call) before the child's completion arrives as a notification in a known form naming the child launched in that turn, the nonce appears nowhere before it, and a controller reply after it reports the nonce. No Codex completion form is known yet, so a Codex run cannot pass until one is added from a real transcript with its own test.

**Files:**
- Create: `agents/bin/wake-judge` (executable)
- Test: `agents/bin/test_wake_judge.py`

**Interfaces:**
- Produces: `wake-judge <claude-code|codex> <transcript.jsonl> <nonce> <prompt-file>` → prints `PASS` (exit 0) or `FAIL: <why>` (exit 1); module function `judge(harness, records, nonce, prompt) -> str`; the tables `CLAUDE_NOTIFICATION_PREFIX`, `CLAUDE_CONTEXT_PREFIXES`, `CLAUDE_NON_INPUT_TYPES`, `CODEX_CONTEXT_PREFIXES`, `CODEX_NOTIFICATION_PREFIXES` (empty), `CODEX_RECORD_TYPES`, `CODEX_NON_INPUT_EVENTS`, `CODEX_NON_INPUT_ITEMS`, which Task 11 may extend only by the rule in its Step 3.

- [ ] **Step 1: Write the failing tests** (`agents/bin/test_wake_judge.py`)

The two review cases (2026-09-24) are `test_claude_waiting_beside_a_tool_call_is_not_a_turn_end` and `test_codex_without_a_notification_fails`; the unclassified-input cases are `test_claude_unclassified_input_fails`, `test_claude_unknown_record_type_fails`, `test_codex_unclassified_input_fails`, `test_codex_unknown_record_type_fails`; the round-3 review cases are `test_claude_waiting_mentioned_but_not_the_final_reply_fails`, `test_codex_waiting_mentioned_but_not_the_final_reply_fails`, `test_codex_unknown_event_subtype_fails_even_with_a_known_form`, `test_codex_unknown_response_item_fails_even_with_a_known_form`.

```python
# agents/bin/test_wake_judge.py
import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("wake-judge")
spec = importlib.util.spec_from_loader("wake_judge", loader=None)
wj = importlib.util.module_from_spec(spec)
sys.modules["wake_judge"] = wj
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), wj.__dict__)

PROMPT = 'Start a background subagent whose only job is to run "sleep 60; cat /s/nonce". End your turn with WAITING.'
NONCE = "5f1c0ffee0dd1234"


def u(content, **extra):
    return {"type": "user", "message": {"role": "user", "content": content}, **extra}


def a(*blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def text(t):
    return {"type": "text", "text": t}


def use(tool_id, name="Agent"):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": {}}


def result(tool_id, t):
    return {"type": "tool_result", "tool_use_id": tool_id, "content": t}


def claude_wake():
    return [
        u(PROMPT),
        a(use("toolu_01A")),
        u([result("toolu_01A", "Async agent launched. agentId: a1b2c3d4")]),
        a(text("WAITING")),
        u(f"<task-notification><task-id>a1b2c3d4</task-id><result>{NONCE}</result></task-notification>"),
        a(text(NONCE)),
    ]


def verdict(harness, records):
    return wj.judge(harness, records, NONCE, PROMPT)


def test_claude_wake_passes():
    assert verdict("claude-code", claude_wake()) == "PASS"


def test_claude_waiting_beside_a_tool_call_is_not_a_turn_end():
    # Review 2026-09-24: WAITING in a record that also calls TaskOutput; the controller
    # never ended its turn, and the tool result must not count as a notification.
    records = [
        u(PROMPT),
        a(use("toolu_01A")),
        u([result("toolu_01A", "agentId: a1b2c3d4")]),
        a(text("WAITING"), use("toolu_02B", "TaskOutput")),
        u([result("toolu_02B", f"<task-notification>a1b2c3d4 {NONCE}</task-notification>")]),
        a(text(NONCE)),
    ]
    assert verdict("claude-code", records).startswith("FAIL: no completion notification")


def test_claude_notification_while_a_tool_runs_is_not_a_wake():
    records = claude_wake()
    records[3] = a(text("WAITING"), use("toolu_02B", "TaskOutput"))
    assert verdict("claude-code", records).startswith("FAIL: the controller's turn had not ended")


def test_claude_second_human_prompt_fails():
    records = claude_wake()
    records.insert(4, u(PROMPT))
    assert verdict("claude-code", records).startswith("FAIL: 2 human prompts")


def test_claude_unclassified_input_fails():
    records = claude_wake()
    records.insert(4, u("Did the subagent report?"))
    assert verdict("claude-code", records).startswith("FAIL: unclassified input")


def test_claude_unknown_record_type_fails():
    records = claude_wake()
    records.insert(4, {"type": "queue-operation", "operation": "enqueue"})
    assert verdict("claude-code", records).startswith("FAIL: unclassified record type")


def test_claude_nonce_before_notification_fails():
    records = claude_wake()
    records.insert(3, a(text(f"peeked: {NONCE}")))
    assert verdict("claude-code", records).startswith("FAIL: the nonce appeared before")


def test_claude_notification_for_another_child_fails():
    records = claude_wake()
    records[4] = u(f"<task-notification><task-id>zzzz9999</task-id><result>{NONCE}</result></task-notification>")
    assert verdict("claude-code", records).startswith("FAIL: the notification does not name")


def test_claude_no_reply_after_notification_fails():
    assert verdict("claude-code", claude_wake()[:-1]).startswith("FAIL: no controller reply")


def test_claude_context_records_are_allowed():
    records = claude_wake()
    records.insert(4, u("<system-reminder>ctx</system-reminder>"))
    records.insert(1, u("hook context", isMeta=True))
    assert verdict("claude-code", records) == "PASS"


def ev(kind, **extra):
    return {"type": "event_msg", "payload": {"type": kind, **extra}}


def msg(role, t):
    item = "output_text" if role == "assistant" else "input_text"
    return {"type": "response_item", "payload": {"type": "message", "role": role, "content": [{"type": item, "text": t}]}}


def call(call_id):
    return {"type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "call_id": call_id, "arguments": "{}"}}


def out(call_id, t):
    return {"type": "response_item", "payload": {"type": "function_call_output", "call_id": call_id, "output": t}}


def codex_first_turn():
    return [
        {"type": "session_meta", "payload": {"id": "x", "cwd": "/s"}},
        ev("task_started"), msg("developer", "permissions"), msg("user", "<environment_context>…"),
        msg("user", PROMPT), ev("user_message", message=PROMPT),
        call("call_1"), out("call_1", "agent_id: ag42"), ev("token_count"),
        {"type": "response_item", "payload": {"type": "reasoning", "summary": []}},
        msg("assistant", "WAITING"), ev("agent_message", message="WAITING"), ev("task_complete"),
    ]


def test_codex_without_a_notification_fails():
    # Review 2026-09-24: complete, start, and a later nonce are not a wake by themselves.
    records = codex_first_turn() + [ev("task_started"), msg("assistant", NONCE), ev("task_complete")]
    assert verdict("codex", records).startswith("FAIL: no completion notification")


def test_codex_unclassified_input_fails():
    records = codex_first_turn() + [msg("user", "child finished: ag42"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: unclassified input")


def test_codex_unknown_record_type_fails():
    records = codex_first_turn() + [{"type": "mystery", "payload": {}}]
    assert verdict("codex", records).startswith("FAIL: unclassified record type")


def test_codex_has_no_known_notification_form_yet():
    assert wj.CODEX_NOTIFICATION_PREFIXES == ()


def test_codex_wake_passes_once_a_form_is_known(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn() + [msg("user", "<agent_done>ag42</agent_done>"), ev("task_started"), msg("assistant", NONCE), ev("task_complete")]
    assert verdict("codex", records) == "PASS"


def test_codex_second_human_prompt_fails():
    records = codex_first_turn() + [msg("user", PROMPT)]
    assert verdict("codex", records).startswith("FAIL: 2 human prompts")


def test_codex_turn_ending_in_a_tool_call_fails(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn()
    records.insert(12, call("call_2"))
    records += [msg("user", "<agent_done>ag42</agent_done>"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: the first turn did not end with a reply of exactly WAITING")


def test_claude_waiting_mentioned_but_not_the_final_reply_fails():
    # Review 2026-09-24: a reply that only mentions WAITING is not the specified turn end.
    records = claude_wake()
    records[3] = a(text("I will say WAITING when done; I am still working"))
    assert verdict("claude-code", records).startswith("FAIL: the controller's turn did not end with a reply of exactly WAITING")


def test_codex_waiting_mentioned_but_not_the_final_reply_fails(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn()
    records[10] = msg("assistant", "I will say WAITING when done; I am still working")
    records += [msg("user", "<agent_done>ag42</agent_done>"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: the first turn did not end with a reply of exactly WAITING")


def test_codex_unknown_event_subtype_fails_even_with_a_known_form(monkeypatch):
    # Review 2026-09-24: an unknown event was skipped and the run still passed.
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn() + [ev("mystery_input", message="x"), msg("user", "<agent_done>ag42</agent_done>"),
                                     ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: unclassified event subtype 'mystery_input'")


def test_codex_unknown_response_item_fails_even_with_a_known_form(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn() + [{"type": "response_item", "payload": {"type": "mystery"}},
                                     msg("user", "<agent_done>ag42</agent_done>"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: unclassified response item 'mystery'")
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd ~/d/ai/.worktrees/turn-boundary-gate && python3 -m pytest agents/bin/test_wake_judge.py -q`
Expected: ERROR — `agents/bin/wake-judge` does not exist.

- [ ] **Step 3: Write the judge** (`agents/bin/wake-judge`; `chmod +x`)

```python
#!/usr/bin/env python3
"""Judge one controller-wake probe transcript: did the harness start a new controller
turn, without human input, because a child it was running finished?

wake-judge <claude-code|codex> <transcript.jsonl> <nonce> <prompt-file>

Prints PASS, or FAIL: <why>; exits 0 on PASS and 1 on FAIL. It fails closed. Every
input record must classify as the one human prompt (byte-equal to <prompt-file>, stripped),
known harness context, a tool result, or a completion notification in a known form; any
other input record, or a record type it does not know, is a FAIL. A completion counts
only if the controller's turn had ended first (its last record before the notification
is text with no tool call, and is exactly WAITING), the notification names the child launched
in that turn, the nonce appears nowhere before it, and a controller message after it
reports the nonce.

Known forms grow only from a real transcript and a test built from it (ai
docs/plans/2026-09-24-turn-boundary-gate.md Task 10). No Codex completion form is known
yet, so a Codex run cannot pass until one is added that way.
"""
import json
import re
import sys

CLAUDE_NOTIFICATION_PREFIX = "<task-notification>"
CLAUDE_CONTEXT_PREFIXES = ("<system-reminder>",)
# Claude Code record types that carry no model input.
CLAUDE_NON_INPUT_TYPES = frozenset({"summary", "file-history-snapshot", "system"})
CODEX_CONTEXT_PREFIXES = ("<environment_context>", "# AGENTS.md", "<INSTRUCTIONS>", "<user_instructions>")
CODEX_NOTIFICATION_PREFIXES = ()
CODEX_RECORD_TYPES = frozenset({"session_meta", "turn_context", "event_msg", "response_item"})
CODEX_TOOL_CALLS = frozenset({"function_call", "custom_tool_call", "local_shell_call"})
CODEX_TOOL_OUTPUTS = frozenset({"function_call_output", "custom_tool_call_output"})
# Subtypes known to carry no model input. Anything not listed, and not handled above, is
# unclassified and fails the run.
CODEX_NON_INPUT_EVENTS = frozenset({
    "agent_message", "agent_reasoning", "agent_reasoning_section_break", "token_count",
    "exec_command_begin", "exec_command_end", "exec_command_output_delta",
    "patch_apply_begin", "patch_apply_end", "mcp_tool_call_begin", "mcp_tool_call_end",
    "web_search_begin", "web_search_end", "turn_diff", "plan_update",
})
CODEX_NON_INPUT_ITEMS = frozenset({"reasoning"})
# An id a launching tool result hands back ("agentId: a1b2c3", "task_id=…").
ID_IN_RESULT = re.compile(r"(?i)\b(?:agent|task|shell|process)?[ _-]?id\s*[:=]\s*[\"']?([A-Za-z0-9_-]{4,})")


class Fail(Exception):
    """The transcript does not establish a wake; the message says why."""


def _blocks(content):
    return [{"type": "text", "text": content}] if isinstance(content, str) else list(content or [])


def _text(content):
    parts = []
    for block in _blocks(content):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif block.get("type") == "tool_result":
            inner = block.get("content")
            parts.append(inner if isinstance(inner, str) else _text(inner))
    return "".join(parts)


def _launch_ids(tool_ids, result_texts):
    ids = set(tool_ids)
    for text in result_texts:
        ids.update(ID_IN_RESULT.findall(text))
    return ids


def _claude_kind(record, prompt):
    kind = record.get("type")
    if kind in CLAUDE_NON_INPUT_TYPES or (kind in ("user", "assistant") and record.get("isSidechain")):
        return None
    if kind not in ("user", "assistant"):
        raise Fail(f"unclassified record type {kind!r}")
    content = record["message"]["content"]
    if kind == "assistant":
        return "assistant-tool" if any(b.get("type") == "tool_use" for b in _blocks(content)) else "assistant"
    if record.get("isMeta"):
        return "context"
    blocks = _blocks(content)
    if blocks and all(b.get("type") == "tool_result" for b in blocks):
        return "tool-result"
    text = _text(content).strip()
    if text == prompt:
        return "human"
    if text.startswith(CLAUDE_NOTIFICATION_PREFIX):
        return "notification"
    if text.startswith(CLAUDE_CONTEXT_PREFIXES):
        return "context"
    raise Fail(f"unclassified input: {text[:60]!r}")


def judge_claude(records, nonce, prompt):
    seq = [(k, r) for r in records if (k := _claude_kind(r, prompt)) is not None]
    kinds = [k for k, _ in seq]
    if kinds.count("human") != 1:
        raise Fail(f"{kinds.count('human')} human prompts; expected exactly one")
    first_human = kinds.index("human")
    if any(k.startswith("assistant") for k in kinds[:first_human]):
        raise Fail("the controller spoke before the prompt")
    if "notification" not in kinds:
        raise Fail("no completion notification")
    n = kinds.index("notification")
    before = [i for i in range(n) if kinds[i] != "context"]
    if not before or kinds[before[-1]] != "assistant":
        raise Fail("the controller's turn had not ended before the notification (last record is not a text-only reply)")
    # Claude Code writes one record per content block, so the final reply is the last record.
    if _text(seq[before[-1]][1]["message"]["content"]).strip() != "WAITING":
        raise Fail("the controller's turn did not end with a reply of exactly WAITING")
    if any(nonce in json.dumps(r) for _, r in seq[:n]):
        raise Fail("the nonce appeared before the notification")
    tool_ids = [b["id"] for k, r in seq[:n] if k == "assistant-tool"
                for b in _blocks(r["message"]["content"]) if b.get("type") == "tool_use"]
    results = [_text(r["message"]["content"]) for k, r in seq[:n] if k == "tool-result"]
    notification = _text(seq[n][1]["message"]["content"])
    if not any(i in notification for i in _launch_ids(tool_ids, results)):
        raise Fail("the notification does not name a child launched in the first turn")
    if not any(k.startswith("assistant") and nonce in _text(r["message"]["content"]) for k, r in seq[n + 1:]):
        raise Fail("no controller reply after the notification reports the nonce")


def _codex_text(payload):
    return "".join(c.get("text", "") for c in payload.get("content", []) if isinstance(c, dict))


def _codex_input(text, prompt):
    text = text.strip()
    if text == prompt:
        return "human"
    if CODEX_NOTIFICATION_PREFIXES and text.startswith(CODEX_NOTIFICATION_PREFIXES):
        return "notification"
    if text.startswith(CODEX_CONTEXT_PREFIXES):
        return "context"
    raise Fail(f"unclassified input: {text[:60]!r}")


def _codex_kind(record, prompt):
    kind, payload = record.get("type"), record.get("payload") or {}
    if kind not in CODEX_RECORD_TYPES:
        raise Fail(f"unclassified record type {kind!r}")
    sub = payload.get("type")
    if kind == "event_msg":
        if sub == "user_message":
            _codex_input(payload.get("message") or "", prompt)  # must classify; counted from response_item
            return None
        if sub in ("task_started", "task_complete"):
            return {"task_started": "start", "task_complete": "complete"}[sub]
        if sub in CODEX_NON_INPUT_EVENTS:
            return None
        raise Fail(f"unclassified event subtype {sub!r}")
    if kind != "response_item":
        return None
    if sub == "message":
        role = payload.get("role")
        if role == "assistant":
            return "assistant"
        if role == "developer":
            return "context"
        if role == "user":
            return _codex_input(_codex_text(payload), prompt)
        raise Fail(f"unclassified message role {role!r}")
    if sub in CODEX_TOOL_CALLS:
        return "tool-call"
    if sub in CODEX_TOOL_OUTPUTS:
        return "tool-output"
    if sub in CODEX_NON_INPUT_ITEMS:
        return None
    raise Fail(f"unclassified response item {sub!r}")


def judge_codex(records, nonce, prompt):
    seq = [(k, r["payload"]) for r in records if (k := _codex_kind(r, prompt)) is not None]
    kinds = [k for k, _ in seq]
    if kinds.count("human") != 1:
        raise Fail(f"{kinds.count('human')} human prompts; expected exactly one")
    if "complete" not in kinds:
        raise Fail("the first turn never completed")
    c = kinds.index("complete")
    last = [i for i in range(c) if kinds[i] in ("assistant", "tool-call")]
    if not last or kinds[last[-1]] != "assistant" or _codex_text(seq[last[-1]][1]).strip() != "WAITING":
        raise Fail("the first turn did not end with a reply of exactly WAITING")
    if "notification" not in kinds[c:]:
        raise Fail("no completion notification")
    n = kinds.index("notification", c)
    if any(nonce in json.dumps(p) for _, p in seq[:n]):
        raise Fail("the nonce appeared before the notification")
    call_ids = [p.get("call_id", "") for k, p in seq[:c] if k == "tool-call"]
    outputs = [json.dumps(p.get("output")) for k, p in seq[:c] if k == "tool-output"]
    if not any(i and i in _codex_text(seq[n][1]) for i in _launch_ids(call_ids, outputs)):
        raise Fail("the notification does not name a child launched in the first turn")
    starts = [i for i in range(c + 1, len(kinds)) if kinds[i] == "start"]
    if not starts:
        raise Fail("no new turn started after the first completed")
    after = max(n, starts[0])
    if not any(k == "assistant" and nonce in _codex_text(p) for k, p in seq[after + 1:]):
        raise Fail("no controller reply in the new turn reports the nonce")


def judge(harness, records, nonce, prompt):
    try:
        (judge_claude if harness == "claude-code" else judge_codex)(records, nonce, prompt.strip())
    except Fail as failure:
        return f"FAIL: {failure}"
    return "PASS"


def main(argv):
    if len(argv) != 4 or argv[0] not in ("claude-code", "codex"):
        print(__doc__.splitlines()[3], file=sys.stderr)
        return 2
    harness, path, nonce, prompt_file = argv
    with open(path) as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    with open(prompt_file) as handle:
        verdict = judge(harness, records, nonce, handle.read())
    print(verdict)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest agents/bin/test_wake_judge.py -q`
Expected: 21 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/d/ai/.worktrees/turn-boundary-gate
tasks check
git add agents/bin/wake-judge agents/bin/test_wake_judge.py
git commit -m "feat(agents): wake-judge decides a controller wake from transcript order, failing closed"
```

### Task 11: Controller-wake probe and `CHILD_WAKES`

**Files:**
- Modify (only if a harness passes both runs): `hooks/claim-guard` in ops (`CHILD_WAKES`), `tests/test_claim_guard.py` (`test_both_harnesses_start_without_wake`)

A wake passes only when `agents/bin/wake-judge` (Task 10) prints `PASS` for the run's transcript. The terminal pane is never evidence: it echoes the prompt.

- [ ] **Step 1: Run one probe** (repeat per harness and child kind)

```bash
S=$(mktemp -d); trap 'tmux kill-session -t cg-wake 2>/dev/null' EXIT INT TERM
N=$(openssl rand -hex 8); echo "$N" > "$S/nonce"
# claude-code:
tmux new-session -d -s cg-wake -x 200 -y 50 "cd $S && claude --model claude-haiku-4-5-20251001"
# codex (instead):
# tmux new-session -d -s cg-wake -x 200 -y 50 "cd $S && codex --model gpt-5.6-sol"
sleep 8
tmux capture-pane -t cg-wake -p | grep -qi "trust" && tmux send-keys -t cg-wake Enter && sleep 3
printf '%s' "$PROMPT" > "$S/prompt"
tmux send-keys -t cg-wake -l "$(cat "$S/prompt")"; tmux send-keys -t cg-wake Enter
sleep 180
```

`$PROMPT`, per child kind (the nonce itself is never in it):
- subagent: `Start a background subagent whose only job is to run "sleep 60; cat $S/nonce" and report the output. Do not read that file yourself. Then end your turn at once with the single word WAITING. When the subagent reports, reply with exactly the text it printed.` (Codex: "spawn a subagent with spawn_agent" in place of "start a background subagent".)
- background command: `Run "sleep 60; cat $S/nonce" in the background (Claude Code: run_in_background; Codex: its own background mechanism). Do not read that file yourself. Then end your turn at once with the single word WAITING. When it finishes, reply with exactly what it printed.` If Codex has no background mechanism, record "absent", which fails this run.

Then find the transcript and judge it:

```bash
# claude-code: the newest session file for cwd $S
T=$(ls -t ~/.claude/projects/$(echo "$S" | sed 's#[/.]#-#g')/*.jsonl | head -1)
# codex: the newest rollout whose session_meta cwd is $S
# T=$(grep -l "\"cwd\":\"$S\"" $(ls -t ~/.codex/sessions/*/*/*/rollout-*.jsonl | head -20) | head -1)
~/d/ai/.worktrees/turn-boundary-gate/agents/bin/wake-judge claude-code "$T" "$N" "$S/prompt"   # or codex
tmux kill-session -t cg-wake; rm -rf "$S"
```

Record each run: `tasks note ai-21ea5d "wake probe <harness> <subagent|background>: PASS|FAIL: <why> (transcript <T>)"`. Four runs in all.

- [ ] **Step 2: When the judge cannot classify**

A `FAIL: unclassified …` (input, record type, event subtype, or response item) means the transcript holds a form the judge does not know; the run is not a wake until that is settled. Read the named record. Only if it is plainly harness context, or the child's completion notification, extend the matching table in `agents/bin/wake-judge` by the narrowest prefix or type that covers it, add a test built from that record (ids and paths replaced) asserting the new classification, run `python3 -m pytest agents/bin/test_wake_judge.py -q`, commit `fix(agents): wake-judge knows <form>, from <harness> probe <date>`, and rerun the judge on the same transcript. Never change any other check to make a run pass. If the record is anything else (human input, an unexplained injection), the run is a FAIL as printed.

- [ ] **Step 3: Sanity-check the judge on a known non-wake**

For each harness, run the subagent probe once more, but send a second prompt yourself (`tmux send-keys -t cg-wake "Did the subagent report?" Enter`) before the child finishes. The judge must print a `FAIL` naming human input (`FAIL: unclassified input: 'Did the subagent report?'`). If it prints `PASS`, the judge is wrong: fix it and rerun Step 2 before trusting any result.

- [ ] **Step 4: Set `CHILD_WAKES`**

For each harness where **both** runs printed `PASS`, in a fresh ops worktree (`.worktrees/child-wakes`, created as in Task 3 Step 0): set its entry to `True` in `hooks/claim-guard`, update `test_both_harnesses_start_without_wake` to the new dict (rename it `test_child_wakes_matches_the_probe`), run `python3 -m unittest tests.test_claim_guard`, commit `feat(hooks): claim-guard child wake for <harness>, probed <date>`, and land it as in Task 5 Step 4. Where either run failed, change nothing. Note the outcome on ai-21ea5d either way.

- [ ] **Step 5: Clean up**

The trap kills `cg-wake`; run `host-load --section session` and confirm nothing is left.

### Task 12: Follow-ups, landing ai, close

- [ ] **Step 1: File the follow-ups**

```bash
cd ~/d/ai/.worktrees/turn-boundary-gate
tasks add "Relay entry for claim-guard over relay's turn-end guard" -p 2 --size s --complexity low --process direct --tag hooks --parent ai-756baa --source ai-21ea5d -b "Thin adapter over ops hooks/claim-guard decide(), in the idiom of relay-guard over claude-pretooluse; replaces the native Stop entries at the cutover. Spec docs/specs/2026-09-24-turn-boundary-gate-design.md §3.4."
tasks dep <that id> --on ai-539508
tasks add "Rollout judgment for claim-guard: sort Stop blocks by what the blocked turn did" -p 2 --size s --complexity mid --process direct --tag flow --tag obs --parent ai-756baa --source ai-21ea5d --defer 14d -b "Spec §6: read Stop blocks from session logs (session-logs), classify each as resumed work, park with an action, vacuous park, bounded wait, report-and-end, or bare end on retry; decide whether the reason text or ai-c62995's rule needs work."
tasks add "prime --all-projects omits tasks that exist only in a worktree branch" --project tasks --status idea -b "Found in the ai turn-boundary-gate spec review 2026-09-24: prime joins claims to the registered checkout's task files, so a live claim on a worktree-only task is invisible there with no warning. tasks claims answers the claim question; this is about prime's other readers." --source ai-21ea5d
```

- [ ] **Step 2: Land ai**

```bash
cd ~/d/ai
git status --short
```

If `claude/settings.json` or `codex/hooks.json` shows as modified in the main checkout, stop and ask the user: they carry uncommitted changes this merge would conflict with. Otherwise: `git merge --ff-only turn-boundary-gate`. Then tell the user that Codex will ask to trust the changed `hooks.json` on its next start.

- [ ] **Step 3: Close**

```bash
tasks done ai-21ea5d "claim-guard Stop guard live in Claude Code and Codex over tasks claims; rules in AGENTS.md and flow; CHILD_WAKES <values> per the wake probe"
tasks check
git add tasks && git commit -m "chore(tasks): close ai-21ea5d"
```

Then remove the ai worktree as in Task 5 Step 5, after the host-pointer check.
