---
name: peer-review
description: Get an independent, multi-pass peer review from a second coding agent via the stratacode headless CLI, driven as a review→revise→re-review loop until the reviewer is satisfied or max passes is hit. Supports review of an early-stage high-level/outline design (mode=high-level-design), an implementation-ready design-and-plan doc (mode=design), or in-progress implementation changes (mode=implementation). Use when you want work pressure-tested by an independent agent.
tags: [review, design, planning, implementation, peer-review]
---

# peer-review

Run an independent, multi-iteration peer review by delegating to a second coding
agent running through the stratacode headless CLI one-shot interface. You (the
requesting agent) stay in control: you receive each appraisal, decide which
points have merit, make the changes, and feed your reasoning back to the same
reviewer session so it can either re-argue rejected points or move on. The loop
repeats until the reviewer returns a clean pass or `max_passes` is reached.

Be aware that although the peer reviewers are strong it is known they sometimes
over-engineer resulting in undesirable and unwarranted complexity getting added
which ends up whith PRs getting rejected later (very bad outcome). So make changes
for its points where they are warranted when you check them, but any that would
increase complexity/scope/bloat and which are non essential (or have a simpler
solution) you can and should push back on, or refer to the user.

This skill is **modal**. The iterative-external-reviewer machinery is identical
across modalities; only the inputs, the prompt wording, what "revise" means, and
the acceptance criteria differ per mode.

## How to use this skill

1. Resolve the `mode` argument (see the table below).
2. Read [`mechanics.md`](mechanics.md) — the shared engine: CLI invocation,
   session reuse, the review loop, and termination conditions. This applies to
   **every** mode.
3. Read the mode file for the resolved mode and follow it for the
   mode-specific inputs, prompt template, and acceptance criteria:
   - `high-level-design` → [`modes/high-level-design.md`](modes/high-level-design.md)
     — an early-stage outline design (a shaped idea, no code-level detail yet);
     challenges the approach, risks, alternatives, and architectural impact.
   - `design` → [`modes/design.md`](modes/design.md) — an implementation-ready
     design-and-plan doc (carries code-level change detail), not an early-stage
     outline.
   - `implementation` → [`modes/implementation.md`](modes/implementation.md)
4. Run the loop from `mechanics.md`, substituting the mode file's inputs,
   prompt, and acceptance criteria.

## Arguments

Parse these from how the skill was invoked. Where an argument is omitted, apply
the rule in the "If omitted" column. Individual mode files may add their own
arguments — read the mode file for those.

| Argument | Required | Default | If omitted |
| --- | --- | --- | --- |
| `mode` | no | `design` | Use `design`. Supported modes: `high-level-design`, `design`, `implementation`. If an unsupported mode is requested, tell the user which modes exist and stop. |
| `max_passes` | no | `3` | Use `3`. Counts full review passes (each pass = one reviewer appraisal). |
| `reviewer_model` | yes | — | **Ask the user which model the reviewer should use, and wait for their answer before proceeding.** Do not guess a default. |
| `reviewer_thinking_level` | no | — | Omit the `--thinking-level` flag entirely so the CLI default applies. |
| `reviewer_service_tier` | no | — | Omit the `--service-tier` flag entirely so the CLI default applies. |
| `session_id` | no | — | Start a fresh reviewer session on the first pass. If the user supplies a session id they believe has useful prior context for this review (e.g. an earlier design-review session the requesting agent is unaware of), resume that session on the first pass instead — falling back to a fresh session if it does not exist. See `mechanics.md`, Step 1. |

Mode-specific inputs (e.g. the document path for `design`, or change scope for `implementation`) are defined in the mode files, not here.
