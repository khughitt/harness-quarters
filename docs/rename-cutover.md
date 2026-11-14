# Project rename cutover

Type: guide; document types 1. Operate the currently unversioned reusable
rename-cutover command and its snapshot/receipt boundaries. See [home links](home-links.md)
for link ownership and the tasks project's lifecycle guide for rename authority.

## Scope and preparation

The tool supports in-tree and detached records layouts; linked overlays are
refused. A rename is a live multi-project/host operation, not a documentation
maintenance command. A reviewed project-specific packet supplies old/new prefixes,
paths, repositories to retarget and actual frozen revisions. Names below are
placeholders, never defaults inferred from the current machine.

Read `tools/rename-cutover --help` and the selected subcommand help for arguments.
Save all needed snapshots on task-owned persistent storage. Confirm source and
records ownership/cleanliness, host resource state and an approved recovery window
before apply. A missing tasks checkout/registry or ambiguous records layout stops
rather than falling back to code-root records.

## Command sequence

| Command | Contract |
| --- | --- |
| save | Snapshot original code/records state, live unfiltered configuration, private selections and required ownership metadata; refuse existing conflicting rename receipt |
| apply | Run tasks rename, commit through its receipt before moving the checkout, then move/repoint storage and commit detached config relocation |
| retarget --repo | Repair references in a named snapshot participant; refuse deferred record commits |
| retarget --forward | Update projects outside the rollback set; ends the bounded rollback window |
| link | Apply declared home links from the renamed main checkout |
| verify | Check names, owner paths, links and absence of an unfinished rename receipt |
| rollback | Restore only the recorded owned state, stopping at the first failed guard |

Tasks owns alias registration, receipt validation/consumption and record-commit
locking. Hq calls that interface; it never unlinks a rename receipt or duplicates
its internal digest rules. A receipt commit failure stops before moving. A detached
config commit failure stops after moving/repointing, preserving the recoverable
state and printing the actual failed boundary. Successful command warnings remain
visible; malformed JSON/warnings output is a failure to establish completion.

The other host adopts only after sync has delivered the renamed checkout and
committed records: use tasks rename OLD NEW --adopt in the new checkout. Do not
substitute an init call for adoption. Host-local storage links need their own
registered route and actual target; inspect the packet instead of assuming every
host has the same physical path.

## Snapshot and rollback boundaries

Snapshot meta.json identifies the source checkout, participant repositories,
original heads/branches and storage/record paths. Live file patches are kept
unfiltered: committed filtered blobs do not contain the user's picks/trust.
Other projects' records in a shared records repository are never a whole-repo
reset target. Rollback restores only the owned old/new prefix and participant
record paths, leaving independent projects' work untouched.

Untracked/ignored owned-prefix input, staged records elsewhere and changed/new
foreign inventories have distinct guards. An unchanged original inventory is
original state, not proof of an intervening write. A changed inventory must still
name the expected source/target/root. Preserve user edits rather than making a
snapshot appear valid by dropping them.

Rollback reverses the tasks rename and restores original code/config through the
saved ownership map. It can recreate empty owned directories and restore captured
records without touching detached participant code checkouts unnecessarily.
A guard failure leaves a partial state for inspection; do not report completion
or run an automatic new apply. After forward retargeting, use a fresh reviewed
recovery decision rather than claiming the original bounded rollback still applies.

## Failure diagnosis

A remaining rename-commit receipt means the operation did not finish its commit
boundary. A later bare tasks commit can validate a stale receipt against moved
paths and refuse; do not blindly retry after relocation. Inspect the stopped
apply boundary and use the snapshot's supported rollback before a fresh apply.

Deferred/failed record commits, dirty owned input, changed foreign state or
unreachable participant checkouts are not successful retargeting. Check actual
heads and committed records after failures: a commit may have succeeded before a
later report/cleanup error. Keep source snapshots and branch refs until their
owner has verified both adoption and evidence disposition. No command in this
guide authorizes Git history rewriting, remote publication or backup deletion.
