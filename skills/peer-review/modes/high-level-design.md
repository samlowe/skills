# peer-review — mode: high-level-design

Independent iterative review of an **early-stage, high-level (outline) design** —
a shaped idea or proposed approach whose implementation implications are not yet
worked out to code level. Where `design` mode asks "is this implementation-ready
plan oven-ready to build?", this mode steps back and challenges the approach
itself, before that detail exists.

This mode is **not** for an implementation-ready design-and-plan doc — use
`design` for that. If the document already carries code-level change detail and
the question is whether it is oven-ready to build, redirect to `design` mode.

Read [`../mechanics.md`](../mechanics.md) first for the engine; this file
supplies only the high-level-design-specific inputs, prompt, and acceptance
criteria.

## Inputs

| Argument | Required | Default | If omitted |
| --- | --- | --- | --- |
| `docs` | yes | — | The path(s) to the document(s) under review. The first/primary path is the high-level design to be reviewed; any further paths are supporting context. If no doc path is given, ask the user for it and stop until provided. |

The reviewer runs in `--workdir`, so it can and should read the **existing
codebase/architecture** to judge how the proposed direction fits — the
refactoring and architectural-integrity questions below depend on it.

## What "revise" means in this mode

You edit the **document** (the high-level design). Acting on a point of merit may
mean more than patching a flaw — it can mean reshaping the proposed approach,
recording a risk and its mitigation, or adopting a materially better alternative
the reviewer surfaced. On re-review the reviewer re-reads the latest version.

## Initial prompt template (Step 1)

```
This is <your agent name>, making this request on behalf of the user. Please
review the high-level design in <<doc_path>>. This is an early-stage outline, not
an implementation-ready plan, so review it at that level. Static review only — do
not run or modify code, though you may read the existing codebase to ground your
assessment. Specifically, challenge:

- Is the design well conceived? Is the chosen approach sound?
- Is the functional scope clear — is it unambiguous what is and isn't in scope?
- Are the risks acceptable, or acceptably mitigatable? Name them and say how.
- Is there a better way that should be considered? If so, make the case.
- What refactoring of the current design/codebase would this require — at a
  minimum to make it work, and what is additionally advisable so as not to damage
  the integrity of the architecture or codebase?

Please return a written appraisal with actionable points, grouped by severity.
```

Replace `<<doc_path>>` with the primary document path. If there are additional
supporting docs, name them in the message as context.

## Acceptance criteria

A clean pass means the reviewer judges that the approach is well conceived; the
functional scope is clear; the risks are acceptable or have credible mitigations;
no materially better alternative is being overlooked; and the
architectural/refactoring implications are understood and acceptable — no points
of merit left to address.
