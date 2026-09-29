# Topics

1. context
2. prompting
3. vibe-ish
4. markdown
5. silent fallbacks
6. ideation
7. iteration
8. model choice
9. review
10. unified
11. self-healing
12. starting over
13. tooling

## 1. Context

Context is the #1 limitation still..

- break things up into manageable chunks
- favor modular designs
- don't use claude's compaction
    - codex is a bit better; it seems to compact earlier (so less chance it's summary will be
      affected by context limitations) and more frequently, so it ends up feeling more continuous.
    - for claude: stop ~70% and have create/update markdown plans, wipe session, and provide the doc
      (plus small set of other key context) and a short prompt to orient it / have it resume the
      effort.

## 2. Prompting

Spend more time crafting clear descriptions of the problem/goals;
even if it takes a couple hours, you will be much more likely to get the desired outcome

_Save your prompts_: often, we end up having the solve the same types of problems across different
contexts and across different projects. If you are already taking the same to draft quality prompts
with clear and explicit guidance, there is a good chance that those same prompts can be adapted
later when encountering that same problem (or when our forgetful friends helpers have completely
forgotten the super important information that we so elegantly conveyed earlier on, and we need to
re-educate them..)

## 3. "Vibe-ish"

Pure yolo mode and pounding "continue" can _sometimes_ work, but chances are you will end up with
something that is 60-70% what you actually wanted.

For large existing codebases, it can also make a mess.

You don't have to read every single line of code written, but take time to skim the summaries / code
changes for each push, and make sure it is actually in line with you want.. If not, ask it to revert
the changes and tell explain more clearly what you have in mind.

Sometimes it _can_ also be fun, e.g. at the end of some implementation, to ask the LLM if it has any
suggestions for other things to to improve on what you just did, or that would complement that
effort, etc. Have it throw out some ideas, and sometimes it can come up with some cool ideas that
you would not have thought of yourself.

## 4. Markdown

Markdown is a good way to communicate intent back-and-forth with an LLM and to ensure that you and
it are aligned on how to approach things.

It's _also_ a good way to take control over "compaction" and ensure that subsequent LLMs picking up an
effort start with the right understanding..

It's _also_ a good way to craft useful bits of context (concise architecture docs, code cheatsheets,
etc.) to inject into / "seed" different conversations..

It's _also_ an (okay) way to formulate tasks and track progress.

Take some time to devise a organization system that works for both you and the LLM.

E.g.:

```
doc/
    planning/
        feat1/
    ref/          <- actual project docs from github repos
        r3f/
        vitest/
        xstate/
    tldr/         <- hand-crafted or llm-generated "cheatsheets" with most useful patterns
        r3f.md
        vitest.md
        xstate.md
```

Templates + metadata can also be useful in cases where you want to create multiple docs with
a similar structure.

Creating a CLI API endpoint to help with scaffolding can similarly help increase consistency when
you want to create multiple docs for some topic with the same structure and feel.

## 5. Iteration

Following an implementation step, as long as context is <= ~70%:

> Please carefully review our recent code implementations; check to make sure that everything has
> been properly implemented and that we didn't miss anything.

This can also be done using a second model, e.g.:

1. implement (claude)
2. check for gaps (claude)
3. "carefully review the code implementation corresponding to xx-plan.md; check to make sure that everything has been implemented as
   intended and that there are no remaining gaps" (codex)

Claude will tend to make fixes directly, which is usually a good thing.

This also works really well for drafting an implementation plan, e.g.:

1. write a prompt describing the task and requirements, have the model create an implementation plan
   and save it as a markdown file
2. then, either ask the same model to review the doc and check for gaps / elaborate on and refine
   the plan, or, have a second model do this.

Codex tends to write terse but well-scoped plans. Claude adds a lot more detail, but is sometimes
less reliable for getting the scoping right or misses important ways in which the tasks should be
integrated with the existing codebase, so having codex do a first pass, and then having opus assess
and refine the plan can be a good way to go.

# Review

7. review & modify in between steps
    - markdown plan
    - data model
    - data contracts

# Self-healing

"health" (static / dynamic)
    - modular health check system
        - cli (npm)
        - web ui
    - graphical system representation
    - JSON serialization of multiscale system state


