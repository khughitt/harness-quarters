# Home links

Type: guide, data model; document types 1. The links.toml format is currently
unversioned. This covers home routing and adoption by tools/harness-links;
[live state](live-state.md) defines the settings it preserves, and
[adding a harness](runbooks/adding-a-harness.md) is the integration checklist.

## Preview, apply and verify

Run from the main checkout:

```sh
just link
just link-check
just link --apply
```

The first reports planned changes; the second fails on drift; the third applies
only after checking every applicable target and refusing conflicting entries.
Applying changes a live host and needs the authorization for that operation.
The tool refuses linked worktrees: temporary paths must never become home targets.

Required entries apply on every host. A harness group applies only if its home is
a real directory, so an absent work home does not require its private settings.
An applicable target must already exist; setup is not a private-settings generator.
Missing local/ inputs require the named setup-created directory or a copy of the
private file from a configured host.

## Manifest records

| Table or field | Meaning |
| --- | --- |
| directories | Home path -> former target within hq; convert only a link still owned by that declaration into a real directory before installing children |
| required | Home path -> target; applies without a harness-home condition |
| harness.NAME.home | Real harness home whose presence activates that group's links |
| harness.NAME.links | Home-relative link name -> target |
| harness.NAME.adopt | Optional list of links allowed to adopt a regular settings file; each must also be declared in links |
| harness.NAME.anchors | Optional list of other declared home links into hq proving ownership; default is the group's non-adopted links |
| retired | Home path -> former target; remove only a matching owned link |

Home paths expand the user's home syntax. Targets are checkout-relative, or
PREFIX:relative/path resolved through tasks projects --paths. Target paths cannot
be absolute or contain parent traversal. Directory-conversion targets and adopted
settings must belong to this hq checkout; another owner's settings are not adopted.

An anchor must be a different non-adopted declared link into hq. An adopt list
requires at least one anchor. Duplicate managed paths, managed links containing
other managed homes/entries, homes that are managed links, parent traversal and
an entry declared both live and retired are refused. The tool does not impose a
blanket rule on unmanaged home files; undeclared paths remain untouched.

## Ownership and first-run adoption

An ok link matches its immediate declared target, permitting aliases in parent
directories. Reaching the right file through an obsolete intermediate skill link
is drift. Foreign directory links cannot be converted, and real files/directories
are refused except for explicitly adopted regular settings files.

When one anchor already points into hq, an agy settings file that replaced its
home symlink is an owned detached save. Apply synchronizes its tracked settings
and picks through live-picks, then restores the link. Hook-time restoration follows
the same ownership check.

Before any anchor exists, a first-run file can be adopted only if the same apply
would create every anchor, with nothing already at those paths. The tracked config
remains the base; picks merge, but an unknown non-live setting refuses the whole
apply. A running agy also refuses first-run adoption. Preserve the file and stop
the relevant sessions before an authorized retry; never delete settings to make
link-check green.

## Diagnosis

A refused entry prevents apply. Read the named path and owner mismatch first.
An absent owner checkout requires registration/availability through tasks; a
missing private work file requires its private source. A foreign anchor or changed
real directory is a manual ownership decision, not permission to overwrite it.

On a new host initialize required owner submodules, create the real harness homes,
then apply declared links before launching a harness that writes first-run files.
After a manifest change, convergence is checked on each host that applies it.
Settings, hooks and session tools target hq; instructions/profiles/general skills
and task/flow skills target their registered owners directly.

## Current home groups

Claude Code and Codex have personal and private work homes. Agy's settings home
is .gemini/antigravity-cli and its hook/skill home is .gemini/config; both are one
session-store integration, not personal/work session adapters. Its skills.json
uses a relative path to .agents/skills because agy does not expand home syntax
in that file. Pi reads .agents/skills natively. The OpenCode group activates only
when its declared .config/opencode.local home exists.

External Ponytail defaults live in external/ponytail/config.json with defaultMode
off: skills are available without automatic session/worker footer injection.
Installed plugin caches stay harness-managed rather than becoming hq inputs.
