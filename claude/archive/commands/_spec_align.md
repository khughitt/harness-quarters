/command _spec_align

## Overview

I would like to audit the codebase and assess alignment between:

1. Project specifications (@specs/)
2. Backend code (@backend/)
3. Frontend code (@frontend/src/)

Example `specs/` structure:

```bash
.
└── 001-spec-x
    ├── contracts                    // data contracts
    │   ├── analytics-api.yaml
    │   └── thoughts-api.yaml
    ├── data-model.md                // data model
    ├── plan.md                      // overall spec plan
    ├── quickstart.md
    ├── research.md                  // technical approach research and decisions
    ├── spec.md                      // requirements, user stories, etc.
    └── tasks.md
```

Goals:

1. to understand the current state of alignment and to use this understanding to plan adjustments or one or more of these, in order to bring the three into better alignment.
2. to identify "clutter" or additions added to the spec directories which whould be merge or removed
3. to "refine" the spec to be as close to the original concise form, without removing parts which
were present in the original formulation (except when they have been removed/replaced in the
codebase)

## Task

Focusing on data models / interfaces and data contracts, please create a detailed markdown report `doc/spec-alignment-<date>.md`, describing instances where ("FE" = frontend, "BE" = backend):

1. Spec, FE, and BE are all in agreement
2. FE and BE agree, but diverge from spec
3. FE and spec agree, but BE differs
4. BE and spec agree, but FE differs

In some cases, additional markdown files may be preset corresponding to later revisions or
extensions to the original spec.

Use `git` to determine which files were present in the initial spec commit, and for each, make
a note of what it contains (data model, contract, or other), and how it relates to the codebase.

If a CLI implementation is preset (typically in the backend, e,g. `backend/<proj>/cli`), include an
additional section assessing the alignment of the backend web API and the CLI API.

Then, create a second markdown file, `doc/spec-alignment-<date>-suggestions.md` with a list of
specific steps we can take to improve alignment, and to refine the spec to its core essence.

In cases where additional files were added over time:

1. If the new files describe legacy interfaces/data models, mark them for removal
2. If the new files describe data model, data contract or or requirements which _are_ used in the current codebase, which which are not preset in the 'base' data-model.md, etc. files, mark those to be "merged" into the relevant spec authority files.
3. if it is unclear what should be done with a newer file, mark these as "NEEDS CLARIFICATION" in the suggestions report.

Include a note at the bottom stating that, when making changes to the spec documents, care should be
taken to adopt a similar concise style as what is currently used, and the changes should not
include language relating to what was changed; it should just be a concise reflection of the current
state of the system.
