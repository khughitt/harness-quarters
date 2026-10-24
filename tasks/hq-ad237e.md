---
id: hq-ad237e
title: Reconcile retained relay release and adoption evidence
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-24T17:36:50Z
updated: 2026-10-24T17:38:12Z
depends: []
tags: []
source: "hq-536849:retained-evidence"
agent: codex
---

Retained canonical raw release and pinned-runtime adoption provenance remains on Titan after completed adoption. Inspect the retained-item notes carried here from hq-536849, verify their manifests, and give each raw file a disposition: attach still-needed small evidence using normal layout checks (preserving raw copies and portable derivatives where checks require), discard regenerable or already-preserved copies, and release directories only after every needed item is preserved. This is evidence housekeeping; no runtime, service, hook or home-link change is authorized or needed. Done: each carried item is preserved under an explicit owner or released with its verified disposition. No code changes or new installer are expected.

## Notes

- 2026-10-24T17:38:08Z (chore/hq-536849-relay-v020): retained: {"host": "titan", "kind": "evidence", "path": "$WORK_ROOT/relay/relay-adb97d/evidence", "purpose": "Canonical raw provenance retained after completed relay v0.2.0 adoption; reconcile per-file preservation and disposition", "cleanup_trigger": "When hq-ad237e reconciles attachment and retention of each raw evidence file", "manifest": "$WORK_ROOT/relay/relay-adb97d/evidence/manifest.sha256", "sha256": "4425bd846704a1d0bab99cb179788f6ac536016d8c7e35ca52f22ca705b193c8", "state": "kept", "verification": "verified", "next_owner": "task:hq-ad237e"}
- 2026-10-24T17:38:09Z (chore/hq-536849-relay-v020): retained: {"host": "titan", "kind": "scratch", "path": "$WORK_ROOT/relay/relay-adb97d", "purpose": "Canonical raw provenance retained after completed relay v0.2.0 adoption; reconcile per-file preservation and disposition", "cleanup_trigger": "When hq-ad237e reconciles attachment and retention of each raw evidence file", "manifest": "$WORK_ROOT/relay/relay-adb97d/manifest.sha256", "sha256": "0fb93deceea2514a11e811f391c56907b866ae1f330de5b7704cab1b93c28b77", "state": "kept", "verification": "verified", "next_owner": "task:hq-ad237e"}
- 2026-10-24T17:38:11Z (chore/hq-536849-relay-v020): retained: {"host": "titan", "kind": "evidence", "path": "$WORK_ROOT/hq/hq-536849/evidence", "purpose": "Canonical raw provenance retained after completed relay v0.2.0 adoption; reconcile per-file preservation and disposition", "cleanup_trigger": "When hq-ad237e reconciles attachment and retention of each raw evidence file", "manifest": "$WORK_ROOT/hq/hq-536849/evidence/manifest.sha256", "sha256": "a1923291666d34caae04797a1700d92519183974a42d85e6f4b19291b233a2f4", "state": "kept", "verification": "verified", "next_owner": "task:hq-ad237e"}
- 2026-10-24T17:38:12Z (chore/hq-536849-relay-v020): retained: {"host": "titan", "kind": "scratch", "path": "$WORK_ROOT/hq/hq-536849", "purpose": "Canonical raw provenance retained after completed relay v0.2.0 adoption; reconcile per-file preservation and disposition", "cleanup_trigger": "When hq-ad237e reconciles attachment and retention of each raw evidence file", "manifest": "$WORK_ROOT/hq/hq-536849/manifest.sha256", "sha256": "ada216b63a66e955d48cec4972d5a96297fb130154e598763d97d924863a5dd9", "state": "kept", "verification": "verified", "next_owner": "task:hq-ad237e"}
