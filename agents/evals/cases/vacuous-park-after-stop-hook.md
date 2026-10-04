---
id: vacuous-park-after-stop-hook
title: A park induced by a Stop-hook refusal names no next step
subject:
  kind: hook
  name: Stop hook refusing a turn end on the session's live claim (probe stub)
  version: [claude-code 2.1.278, claude-haiku-4-5, probe stub hook (not committed; described in the ai-80b836 notes)]
inputs:
  - kind: fixture
    ref: park next step
    value: Waiting for next steps
  - kind: task
    ref: ai-80b836
expected:
  type: choice
  claim: what the park's next step gives the session that resumes the task
  choices: [actionable, handoff, vacuous]
  rubric: actionable names a step and who takes it; handoff names a person and what they must decide or inspect; vacuous names neither
  value: vacuous
observed:
  value: vacuous
  at: the subject version above
judge:
  kind: question
  question: Classify the park's next step as actionable, handoff, or vacuous using the rubric, and quote the words that decide it.
source: [ai-80b836, ai-c62995]
evidence: observed
---

In the Stop-hook probe, case 1 (the session's own unparked claim), the hook
refused the turn end and the model parked with the next step "Waiting for next
steps". The probe's review predicted this: a hook that refuses a turn end can
cause a park that satisfies the check and helps no one. obs's stall proxy
counts a park as handled, so it cannot tell this park from a real one.

The expected and observed values agree: the case pins the classification a
park-content rule must reject, not a pass for the hook.
