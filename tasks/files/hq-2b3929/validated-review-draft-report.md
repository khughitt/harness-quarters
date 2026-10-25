# Validated review drafts

hq-2b3929, 2026-10-25. Question: can an explicit target selection, validated inside
the helper, produce an accurate, editable review draft from the retained examples,
with missing, conflicting and stale handoffs made visible? Is a narrow production
preview worth designing?

Answer: yes for the three retained examples, all historical. Once the review kind,
repository, task, artifact and frozen revision were selected explicitly, each
observed case produced a validated draft. Each controlled variant was blocked for
the reason frozen in advance. The prior run's two misbindings came from resolving
the wrong task. The task that linked the artifact, and had parked a review of it,
was the right one.

Recommendation: design a narrow, print-only preview that starts from what requests
already contain, an artifact path. Pre-filling from a task's latest review handoff
is not supported: it held the full selection in only 1 of 3 cases. This result
does not authorize a launcher, a shared schema or an external write.

## Method

One throwaway script, kept local with its manifest, inputs and previews, covers
validation, drafting and evaluation. It reads task snapshots, a frozen project
registry snapshot, the frozen dataset and the repositories, all read-only. Its git
calls use an environment built key by key, with no host git configuration. It
collects no sessions, launches no harness and writes to no store.

Both retained checkpoints were verified before use: the six-file inspection
manifest (`ab51fa82…`, 6/6 files match) and the hq-268cc2 bundle (`72e971e4…`,
18/18 match, none unlisted). The per-case manifest was frozen before the script
was written. Its SHA-256 (`406ba8db…`) was noted on the task and is asserted by
the evaluator. It records, for each case: the dataset row and session locator,
observed or derived provenance for each selected field, the review kind,
repository, task, artifact or code scope, commit plus blob or out-of-tree SHA-256,
historical or current state, the expected outcome, and the required human
corrections.

The helper checks these, in order. Any failure blocks the draft:

- **Kind:** spec, plan, brief or implementation is supported. Other kinds return
  `unsupported` with a reason, never a spec or plan fallback.
- **Repository:** the project prefix resolves through the registry snapshot to a
  checkout at its own top level.
- **Task:** it belongs to the selected project and existed before the request
  opened.
- **Revision:** a commit is required. A task id, path or note SHA is not a revision.
  The commit must exist and predate the request.
- **Blobs:** every target and context blob must exist at that commit. Its SHA-256
  must equal any selected hash; an out-of-tree artifact must equal its selected
  hash.
- **Stale:** no later commit, descended from the selection, revises the artifact
  before the as-of time.
- **Already reviewed:** no verdict note of the same kind falls between the commit
  time and the as-of time.

Historical cases are judged as of the request's opening minute and current cases
as of evaluation. The task snapshots are current, so historical state comes from
filtering notes and commits by time, not from historical records. "Agreement" with
the frozen expectations means the same status and reasons, plus required strings
present and forbidden strings absent in the draft. It is a string comparison. The
meaning comparison below is the investigator's reading of the local previews.

## Cases and outcomes

Denominators: 3 observed cases and 3 derived variants. The observed cases are the
mappings hq-268cc2 could recover, chosen by the original report as differing
examples. They are not a sample of the reported 44 and estimate no coverage. The 41
unavailable identities stay unavailable.

| Case | Provenance | Kind, state | Selection | Outcome | Matches frozen expectation |
| --- | --- | --- | --- | --- | --- |
| C01 | observed | spec, historical | fam-6e8321, relay consumer design at 8e54216 (derived) | ready | yes |
| C02 | observed | implementation, historical | beliefs-f24fe9 at b923277, spec, plan and ledger as context | ready | yes |
| C03 | observed | spec, historical | hq-c411df, session evidence reader design at 87b7fcb with recorded hash | ready | yes |
| V04 | derived from C01 | spec, historical | C01's handoff as recorded, no revision | blocked: missing_revision | yes |
| V05 | derived from C03 | spec, historical | 87b7fcb paired with revision 5's hash (constructed) | blocked: hash_mismatch | yes |
| V06 | derived from C03 | spec, current | C03's selection evaluated now | blocked: already_reviewed, stale_revision | yes |

Observed: 3/3 produced ready historical drafts. Derived: 3/3 were blocked for the
expected reasons. All six agreed with the frozen expectations.

- **C01** opened 09:17Z. The handoff park at 09:13:42Z names only a worktree path.
  The revision is derived: 8e54216 ("draft for review", 09:13:35Z) is the only commit
  touching the artifact before the opening minute. The next commit, "revise after
  round-1 review" at 09:27Z, and the round-1 verdict at 09:25Z are consistent with it.
  The draft labels the revision as derived and asks for confirmation. A note just
  before the park carries an unrelated SHA, 3ec35ee: the task-start commit, which
  does not contain the spec. The draft does not use it.
- **C02:** the request and two merge notes name b923277. All three context blobs
  match the hashes from hq-268cc2. The kind comes from the request text, not the
  task. The task's spec and plan fields point at plan or spec review, and its latest
  review handoff before the request was the plan round-3 park at ddcb955.
- **C03:** the 14:45Z handoff notes name 87b7fcb and the artifact's SHA-256. The
  blob matches. Revision 5 (ae0f8ee) followed the round-4 review at 15:03Z and is
  absent from the draft.
- **V05** is a constructed conflict. Its hash comes from a note written after the
  request, so it exercises the check rather than reproducing a recorded handoff.
- **V06** is the realistic hazard. As a current review, C03's handoff is stale:
  ae0f8ee revises the artifact and two spec verdicts follow 87b7fcb. A copied path
  would silently read revision 5. As a historical reconstruction it is ready.

On meaning, the two spec drafts keep the request's intent and add the frozen
revision. C02's does not keep it fully; see the correction found at evaluation
below.

## Manual corrections

These are the corrections a person had to supply, frozen with the manifest:

- **Task identity, 2 of 3 observed:** C01 relay-fe38b1 became fam-6e8321, and C03
  hq-bb90ca became hq-c411df. Neither request named a task, only an artifact path
  under a worktree. The right task was found by reading which task linked the
  artifact and parked a review handoff for it.
- **Revision, 1 of 3:** C01's handoff names no revision. The investigator derived it
  from git history.
- **Kind, 1 of 3:** C02 needed implementation selected over its spec and plan fields.
- **Review round and worktree:** not confirmed in any draft. The C01 and C03 handoffs
  name the worktree. Their notes imply round 1 for C01 and round 4 for C03. Each
  draft asks for confirmation rather than asserting either.

Two observations come from evaluation and were not frozen:

- **C02's pasted report:** the request pasted the closing report, and the draft
  points to the execution ledger at the merge commit instead. That ledger carries
  the rulings R1–R17, the baseline test count and the corrective fix, but not the
  final verification counts. A person who wants those in the review must add them.
- **C02's earlier acceptance:** implementation round 2 accepted the work at 13:23Z,
  before the 13:28Z merge commit. Round 3 followed the request. The already-reviewed
  check is keyed to the commit time, so it does not report that earlier accept.
  Ready is still right, since the request asked for a further review, but a preview
  should show the prior verdicts.

## Self-checks

The self-checks use 16 fixture cases in two temporary repositories:

- the valid historical target, with a later revision present and not selected;
- missing revision;
- conflicting hash;
- stale revision;
- already reviewed;
- wrong repository: a commit from another repository, and a task from another
  project;
- unregistered repository;
- absent commit;
- absent blob;
- revision after the request;
- task after the request;
- out-of-tree hash match, mismatch and absence;
- unsupported kind;
- implementation with context.

All 16 pass. A mutation run first requires the intact suite to pass, then disables
each of the 11 checks in turn and records what the case aimed at that check
produces:

- **Unsafe ready draft, 5:** task time, revision time, hash, stale and
  already-reviewed. Each check alone stands between its fixture and a wrong draft.
- **Blocked by an overlapping check, 2:** repository and task repository. The wrong
  or unregistered repository is still refused, by the task-project or commit check.
- **Crash, 4:** kind, missing revision, commit and blob. With the check disabled,
  drafting fails on the absent data rather than emitting a draft.

No disabled check yielded a passing target case, so none went unnoticed. Only the
five "unsafe ready" results show a check that is sole protection.

During development, a fixture error (a task created before rather than after its
request) made the first mutation run count every mutation as caught. The run now
requires an all-passing baseline and reports each target's actual outcome. Fixture
variants are not observed cases.

## Supported kinds and limits

| Kind | Validated on observed data | Fixtures |
| --- | --- | --- |
| spec | C01, C03 | yes |
| implementation | C02 | yes |
| plan | no | shares the in-tree artifact path with spec |
| brief, out-of-tree hash | no | yes |
| fixes, ledger, PR, pasted-report | no | explicit `unsupported` result |

Limits:

- Three historical cases establish that the checks behave; they say nothing about
  how often handoffs carry enough information.
- C01's revision is an inference from commit timing. Uncommitted worktree edits at
  request time cannot be ruled out.
- Opening times have minute precision. No commit or verdict note falls inside an
  opening minute here.
- The stale check reads today's refs and committer dates. In historical mode it
  cannot see commits on branches deleted since then; every relevant history here is
  still reachable.
- "Already reviewed" reads the outcome-measure note shape (`review: <kind> round
  …`) after the selected commit's time. Tasks that do not write it pass vacuously,
  and verdicts given before the commit, such as C02's, are not reported.
- Staleness covers a single artifact. An implementation review relies on the
  verdict check alone.
- The drafts are local text files that a person can edit before use. No interactive
  editor or launch was tested.

## Recommendation

Design a narrow, print-only preview; do not stop. Explicit selection with built-in
validation produced correct drafts. Variants built from the recorded handoffs show
what it adds: V04 refuses a revision-less handoff, and V06 flags a superseded one
that a copied path would silently use. But typing a full selection by hand costs
more than today's one-line request, so the preview pays off only if it proposes the
selection itself.

Where the proposal comes from matters. Two candidate sources were compared:

- **The task's latest review handoff (rejected).** It held the full selection only
  for C03. C01's handoff lacked the revision. C02's latest handoff was a superseded
  plan review, which would have proposed the wrong kind and revision. Neither C01
  nor C03 named a task, so this source also needs an input those requests lacked.
- **The artifact path the request already gives (recommended).** A post-hoc check,
  not a frozen-manifest result, and only partly independent:
  - **Revision.** In both spec cases, the latest commit on any ref touching the path
    before the request opened is 8e54216 for C01 and 87b7fcb for C03. Only C03
    independently confirms that this is the revision reviewed: its handoff recorded
    the commit and hash. C01's revision was derived by this same rule, so it cannot
    confirm the rule.
  - **Task.** Both corrected tasks are the only ones in their projects that named
    the path before the request. fam-6e8321 named it in its `spec:` field, set at
    09:13Z. hq-c411df named it only in notes, its 13:05Z draft note and 14:45Z park;
    it gained the `spec:` field at 15:15Z, after the request. A lookup on the spec
    field alone would have found no task for C03 at request time; one over the
    field and notes finds each uniquely.
  - **Kind.** It follows from where the artifact lives.

  Support for this source is 1 of 2 spec cases for the revision. For the task it is
  2 of 2, partly by construction: the corrected tasks were themselves found by the
  path. The independent basis is the review verdict each task recorded just after
  its request, plus the match being unique. That is thin. It is not much stronger than the 1 of 3 behind the
  rejected source; the difference is that it uses an input the requests already
  supply.

The recommended preview should:

- take an artifact path, or a task id plus commit for an implementation review;
- propose the revision: the latest commit touching the path on the HEAD of the
  checkout or worktree the path names, not on whatever branch the main checkout has;
- propose the linking task from the spec field and notes, and say which matched;
- refuse when the working file differs from that blob;
- show prior verdicts and later revisions;
- print an editable draft and launch nothing.

An implementation review still needs its commit stated, as C02's request did.

Two questions belong to the design, not this experiment:

- whether handoffs should record the reviewed revision in a stable shape;
- which project owns that (flows writes the handoff and tasks exposes it).

No shared schema is established as a prerequisite. The rejected alternative,
stopping here, would keep today's path-only requests, which name no revision and
cannot detect a superseded one.
