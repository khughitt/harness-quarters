# Archive native-environment diagnosis

Task: hq-36f6c6. Repair: hq-4c5506. Controller: hq-d33cdc.

The producer is GNU readline initialization, imported by pytest capture's
`_readline_workaround`. The fixture clears keys from Python's cached `os.environ`
mapping, but readline's native writes are absent from that mapping. A native child
launched with `env=None` inherits those hidden COLUMNS/LINES keys.

## Evidence

- `archive-terminal-trace.jsonl` records presence only, never terminal dimensions or
  credential values. At plugin import neither key exists in the mapping or libc.
  The first observed native change is return from importlib `create_dynamic`, in
  `_readline_workaround` (`_pytest/capture.py:95`). At native-child launch the mapping
  still lacks both keys, libc has both, and the test passes no explicit environment.
- `trace_terminal.py` is the audit/profile plugin. The controlled focused commands
  used `just test-one tools/test_session_archive_probe.py::test_codex_stub_children_use_minimal_environment -q`
  with that plugin loaded for the diagnostic runs; corresponding raw logs are
  `archive-environment-trace-run.log` and `archive-environment-profile-run.log`.
- `archive-readline-backends.log` isolates the import with each interpreter:
  managed CPython 3.13.12 reports editline and introduces neither key; system CPython
  3.14.9 reports readline and introduces both keys into libc but not `os.environ`.
  This is an observed backend difference, not evidence of a new subprocess contract
  in Python 3.14.
- Current tools: uv 0.13.7, just 1.59.0, pytest 9.2.0, pytest-xdist 3.8.0.
  The documented focused route pins `/usr/bin/python3` (3.14.9) and uses host-budget.
- Before repair the focused command fails one test in 0.10s
  (`archive-environment-red.log`). Strengthening the subprocess spy to reject
  `env=None` fails the same test in 0.08s
  (`archive-environment-explicit-red.log`). After supplying the explicit dictionary,
  `just test-one tools/test_session_archive_probe.py -q` passes all 8 tests in 9.52s
  (`archive-environment-green.log`).
- The broader interpreter verification had 268 agent tests pass, then 2048 hook/tool
  tests pass and this one fail; relay stages were not reached. This was a failed run,
  not a passing baseline (`prereq-interpreter-verification.log`). The original
  managed-interpreter baseline passed 2709 tests before the explicit system pin.

## Contract and disposition

Use a key-by-key dictionary at this test's native-child and version-call boundaries:
temporary HOME, fixed PATH/locale/user, fake API credentials and fake stub version.
Reject absent environments in the existing spy. Preserve the allowed-key set,
private-HOME, fake-credential, probe and prune assertions. Neither terminal key is
needed by this fixture, so adding fixed dimensions or widening its allowlist would
hide its accidental inheritance. No production archive change is needed.

The concrete repair is hq-4c5506. The combined prerequisite full-suite verification
and independent review are separate checks and remain pending at report creation.
No live archive store, real Codex probe, credentials or host configuration was read
or changed. No dependency patch is proposed.

The upstream search checked CPython issue 113119 and merged PR 113120, plus Python's
os.environ/subprocess documentation and both local subprocess implementations.
These support native inheritance with `env=None`; they do not identify an external
defect requiring a patch. Sources:
https://github.com/python/cpython/issues/113119
https://github.com/python/cpython/pull/113120
https://docs.python.org/3/library/os.html#os.environ
https://docs.python.org/3/library/subprocess.html#subprocess.Popen

The trace establishes this fixture's producing boundary. It does not claim all
possible native environment writers or readline backends were surveyed.
