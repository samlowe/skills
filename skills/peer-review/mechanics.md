# peer-review — shared mechanics (the engine)

This file describes the mode-agnostic machinery of an iterative peer review:
how to invoke the reviewer, how to keep its session, the review→revise→re-review
loop, and when to stop. It applies to **every** mode. Read your mode file
(`modes/<mode>.md`) for the inputs, prompt template, what "revise" means, and the
acceptance criteria to apply.

The same reviewer session is reused across passes (via its session id) so the
reviewer keeps full context of how the work evolved and of your responses to its
earlier points.

## Invoking the stratacode CLI

The reviewer is a fresh stratacode agent invoked in headless one-shot mode.
`stratacode` is installed and on `PATH`, so invoke it directly as `stratacode`.

Flags used by this skill:

- `--model <reviewer_model>` — the reviewer model (required).
- `--message "<text>"` — the one-shot prompt for this turn.
- `--front-matter` — **always pass this.** It prepends a YAML block to stdout
  containing `session_id`, which you must capture to continue the same session.
- `--workdir <project_root>` — set to the root of the project the work lives in,
  so the reviewer can read the doc, the code, and run git. Just `.` if you are in
  the project root.
- `--resume <session_id>` — on follow-up passes only, to continue the same
  reviewer session. A concrete session id is required (a bare `--resume` is not
  valid in one-shot mode).
- `--thinking-level <level>` — include only if `reviewer_thinking_level` was given.
- `--service-tier <tier>` — include only if `reviewer_service_tier` was given.

stdout carries the reviewer's reply, preceded by the front-matter block:

```text
---
session_id: 01HXY...
model: <reviewer_model>
---

<the reviewer's appraisal>
```

Capture `session_id` from that block. Exit code `0` means success; non-zero
means the run failed — surface the stderr error to the user rather than looping.

You can use standard bash timeout commands, maybe 10 mins for the first pass,
5 mins for later passes.

## The review loop

### Step 0 — Resolve inputs

Resolve `reviewer_model` (ask the user if missing). Resolve the project root for
`--workdir`. Resolve the mode-specific inputs per your mode file. Resolve the
optional starting `session_id` (see Step 1). Set `passes = 0`.

### Step 1 — Initial review request

First decide whether the **first pass** starts a fresh session or resumes an
existing one:

- **Resume** if you have a session id with useful prior context for this review —
  either one the user supplied via `session_id`, or (see your mode file) one you
  yourself hold from an earlier related review session. Pass it as
  `--resume <session_id>` on this first pass, and word the message to acknowledge
  the continuation (e.g. "continuing from our earlier review of …").
- **Fresh** otherwise — send the request with no `--resume`.

**Precedence:** a `session_id` the user supplied takes priority over any session
you hold yourself — try the user's first. Only if it fails to resume (does not
exist or is otherwise unusable) do you fall back: to your own known session if you
have one for this review, otherwise to a fresh session.

If a `--resume <session_id>` on this first pass fails because the session does
not exist or is otherwise unusable, **fall back** as above by re-sending the
request (with your own session id via `--resume`, or with no `--resume` for a
fresh session). Do not loop on this.

Identify yourself as the requesting agent in the prompt (e.g. "Claude Code",
"stratakit", etc.) acting on the user's behalf. Build the message from your mode
file's initial-prompt template, then send:

```
stratacode --model <reviewer_model> [--resume <session_id>] [--thinking-level <level>] [--service-tier <tier>] \
  --workdir <project_root> --front-matter \
  --message "<mode-specific initial prompt>"
```

Capture `session_id` from the front-matter (use whatever id the front-matter
returns for all subsequent passes, even if you resumed a provided one).
Increment `passes`.

### Step 2 — Assess the appraisal and revise

Wait for the reviewer's response. Read the appraisal in full and assess **each**
point on its merits:

- For every point you judge to have merit, make the corresponding change. What
  "make the change" means is mode-specific (edit the doc, edit the code, etc.) —
  see your mode file.
- For points you judge to lack merit, do **not** change anything, but record the
  point and a short note on **why** you disagree — you will hand these back to
  the reviewer in the next pass.

If the reviewer returned no points with merit (an all-green pass), go to
**Termination — clean pass**.

### Step 3 — Follow-up re-review request (same session)

Resume the **same** reviewer session using the captured `session_id`, tell it the
updates have been made, and ask it to re-review the latest state. Include a
summary of any earlier points you did **not** apply, each with your reasoning, so
the reviewer can either make its case again or drop them:

```
stratacode --resume <session_id> --model <reviewer_model> [--thinking-level <level>] [--service-tier <tier>] \
  --workdir <project_root> --front-matter \
  --message "I've applied updates based on your review. Please re-review the latest state. Note: I did not apply the following points, for these reasons — please re-argue them if you still think they hold, otherwise we can set them aside: <numbered list of skipped points + your reasoning>. If there were no skipped points, omit that section."
```

Adapt the wording to the mode (re-reading a doc vs. re-inspecting the working
tree) per your mode file. Capture the (same) `session_id` again from the
front-matter. Increment `passes`.

### Step 4 — Repeat

Return to **Step 2** with the new appraisal. Continue until one of the
termination conditions is met.

## Termination

**Clean pass** — the reviewer returns a pass with no points of merit left to
address. Give the user a concise summary of what was changed across the passes
and the final state.

**Max passes reached** — `passes >= max_passes` and the reviewer still has open
points. Summarise for the user: what was addressed, what remains open (and why),
and the current state. Then ask the user for guidance: continue for more passes,
or stop here.

## Notes

- Always include `--front-matter`; without the captured `session_id` you cannot
  continue the same reviewer session and would lose review context.
- The review is **static only** — the reviewer should not run or modify code, and
  you make all the changes yourself.
- Be a fair but critical judge of the reviewer's points: apply the good ones,
  and give honest, specific reasons for the ones you set aside so the dialogue
  stays productive.
