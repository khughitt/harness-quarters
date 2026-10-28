# Plan revision 3 correction ledger

Input: hq 50282b9, docs/plans/2026-09-30-session-archive.md, Tasks 18–19.
Correction frozen at hq 0154323a7b076c62490b205a3b9c85df45a54bf7. Scoped
self-review round 3: accept, no findings; reviewer codex/gpt-6.1-sol; full report
in plan-round-3-self-review-report.md. Human plan approval remains outstanding.
Review round 2: revise; important 1, minor 2; claude-code/claude-opus-5-5,
full text relayed by the user and saved in plan-round-2-report.md.
The user also agrees with inline execution and deferring obs task filing to
execution. Those choices stay in force; plan approval is still outstanding.

Ruling: I1 fixed in plan revision 3, Task 18 Files, Interfaces and Step 2. Extend scope to tools/conftest.py and the probe environment regression. Make stub_codex depend on the fake home fixture and replace the contents of os.environ with explicit minimal values before any in-process stub child, synchronizing the native environment through monkeypatch.delenv/setenv rather than swapping in a plain dict; preserve control overrides and automatic restoration. Why: run_tool cannot isolate children launched by production helpers inside pytest, while the shared fixture can do so without changing production behavior. Cost: the fixture's explicit key list must evolve when a stub gains a new environment input; the regression covers both subprocess.run and Popen paths.

Ruling: M2 fixed in plan revision 3, Task 19 Step 5. Integrate the hq branch with git merge --no-ff, preserve the tested consumer commit, check ancestry and consumer-tree equality, and rerun paired acceptance against a new committed/landed reader whenever its bytes change. Why: acceptance evidence must identify code that remains reachable and matches the integrated reader. Cost: merge resolution or later reader fixes require another paired probe and affected gates.

Ruling: M3 fixed in plan revision 3, Task 18 Interfaces and Step 2. Use tuple[str, ...] for reasons/conflicts, empty (), update the expected reason tuple and verify hashing. JSON still uses arrays; conversion happens at the validated boundary. Why: frozen ObsFile must not expose mutable sequence fields or fail generated hashing. Cost: two tuple conversions per parsed record.

minor (deferred): none. This correction changes the plan only; no implementation
or new child-environment regression has been executed yet.
