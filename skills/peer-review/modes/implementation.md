# peer-review — mode: implementation

Independent iterative review of in-progress implementation changes against the
design/plan they were built from, before the work is merged. Read
[`../mechanics.md`](../mechanics.md) first for the engine; this file supplies
only the implementation-specific inputs, prompt, and acceptance criteria.

## Reusing an earlier design-review session

If you (the requesting agent) already ran a `design` peer review of the
design/plan these changes were built against, and that design doc has **not
changed** since, you probably want this implementation review to **continue that
same reviewer session** rather than start cold — the reviewer already holds the
design rationale and the points that were debated and settled. Use that session
id as the starting session in Step 1 of `mechanics.md`.

If the design doc has materially changed since that review, prefer a fresh
session so stale design context does not mislead the reviewer. This is in
addition to any `session_id` the user supplies explicitly.

## Inputs

| Argument | Required | Default | If omitted |
| --- | --- | --- | --- |
| `design_docs` | no | — | Path(s) to the design/plan doc(s) the changes were built against, passed to the reviewer as alignment context. If not given, ask the user whether one exists; if they point to none, check a suitable folder (e.g. `docs/plans/`, `docs/rfcs/`). If there genuinely is no design doc, proceed without one and tell the reviewer the review is correctness/quality-only with no design to check against. |
| `include_staged` | no | `false` | Review **unstaged tracked changes + untracked files only**. Staged-but-not-unstaged content is out of scope unless the user explicitly asks to include it. |

## Change scope — the reviewer derives it

The reviewer runs in the same `--workdir` and reads the live working tree, so it
determines the scope itself rather than being handed a diff. The initial prompt
must instruct it to enumerate the changes, and it **must include untracked
files** — a plain `git diff` will miss them. Tell it to use, e.g.:

- `git diff` for unstaged changes to tracked files, and
- `git status` / `git ls-files --others --exclude-standard` for new untracked
  files (then read those files in full).

Unless `include_staged` is true, the reviewer should ignore content that is only
staged (not also present in the working tree as unstaged/untracked).

## What "revise" means in this mode

You edit the **code** (the working tree). For each point with merit, make the
code change yourself. On re-review the reviewer **re-inspects the live working
tree** (re-running the git commands above) — it is not reviewing a frozen diff
from the first pass, so it picks up your edits and any newly added files.

## Initial prompt template (Step 1)

```
This is <your agent name>, making this request on behalf of the user. Please
statically review the current implementation changes in this working tree.
Determine the scope yourself: review the UNSTAGED changes to tracked files (e.g.
via `git diff`) AND any untracked new files (e.g. via `git status` /
`git ls-files --others --exclude-standard`, then read them). Do NOT review
content that is only staged. Do not run or modify any code.

[If design docs given:] These changes were built against <<design_doc_path(s)>>;
please also check the changes against that design for alignment and completeness.

Appraise the changes: Are they complete? Are they correct? Is test coverage
sufficient? [If design given:] Do they align with the design? Are they 'merge
ready'? Assume all existing tests pass unless I tell you otherwise. Please return
a written appraisal with actionable points, grouped by severity.
```

Replace `<<design_doc_path(s)>>` with the resolved design doc path(s), or omit
that sentence and the alignment question if there is no design doc.

## Acceptance criteria

A clean pass means the reviewer judges the changes complete (no parts of the scope of the design/plan are missing or have been deferred without explicit user permission), correct, sufficiently tested, aligned with the design (if one was provided), and "merge ready" — no points of merit left to address.
