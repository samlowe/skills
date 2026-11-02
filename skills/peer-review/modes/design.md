# peer-review — mode: design

Independent iterative review of a combined **design-and-plan** document before
implementation — i.e. a design that has been worked through to implementation
level: concrete enough to build from, including the code-level change detail,
file/component touch-points, and sequencing. This mode pressure-tests whether
that design/plan is sound and "oven ready" to implement.

This is **not** for reviewing an earlier-stage outline design — a shaped idea
whose implementation implications are not yet part of the document. That broader,
earlier-lifecycle review is a separate modality. If the
document under review is only an outline/concept without implementation detail,
say so and check with the user before proceeding in this mode.

Read [`../mechanics.md`](../mechanics.md) first for the engine; this file
supplies only the design-specific inputs, prompt, and acceptance criteria.

When applying any review findings from the peer, be aware that peer revierer, even 
really good ones, can 'over-engineer'. So:

- implement anything that it finds that you confirm has merit and is of a correctness
  nature or is neutral to scope, complexity and bloat.
- But for any findings it comes back with that imply changing scope or adding 
  complexity/bloat, when you consider their merit consider as part of that 
  - whether they really are important enough to warrant the complexity, and 
  - whether a simpler acceptable solution exists. 
- No need to check with the user (it's preferable to not disturb them) if the change
  is essential or clearly worth the complexity, but check with the user if its 
  ambiguous or requires a judgement call.
- An anti-pattern of the peer-review process is lots of unwarranted complexity being
  added driven by a reviewer and then the PR then failing review becuase of excessive
  complexity, and all the work and time and tokens being wasted. It's your
  responsibility to avoid this!
- Take the opportunity after the reviewer gives the all clear on the design to take
  a moment to take a step back and consider whether, in retrospect, any area of what's
  been designed has inadvertantly become over-engineered. For any significant areas
  where it has, propose simplifications of them back to the user. Make the
  simplifications for any that they agree to and then do another pass with the
  reviewer to double-check doing so has not introduced any issues.

## Inputs

| Argument | Required | Default | If omitted |
| --- | --- | --- | --- |
| `docs` | yes | — | The path(s) to the document(s) under review. The first/primary path is the design/plan doc to be reviewed; any further paths are supporting context. If no doc path is given, ask the user for it and stop until provided. |

## What "revise" means in this mode

You edit the **document**. For each point with merit, update or amend the doc
(add detail, fix the flaw, clarify, etc.). On re-review the reviewer re-reads the
latest version of the doc.

## Initial prompt template (Step 1)

```
This is <your agent name>, making this request on behalf of the user. Please review the design/plan <<doc_path>> - is it well conceived? Is it consistent with the 'house style' of codebase its adding to (or have a explicit and well founded reason not to be)? Is it 'oven ready'?
Static review only please. Please return a written appraisal with actionable points, grouped by severity. Stick to the scope of the design and for any suggestions you consider making that would add complexity, bloat or increase scope - balance them with the value they add, whether they are in keeping with the existing codebase and its precedents and whether a simnpler solution exists. Avoid use of subagents unless they are really necessary.
```

Replace `<<doc_path>>` with the primary document path. If there are additional supporting docs, name them in the message as context.

## Acceptance criteria

A clean pass means the reviewer judges the design/plan well conceived and "oven ready" — no points of merit left to address.
