---
name: implement-plan
description: Implement a previously created design/plan from a markdown file
argument-hint: [target_plan_md_filepath]
---
The provided detailed design/plan markdown file is: $ARGUMENTS

## Assessment

Review this document

- If no document has been provided, stop and ask the user how to proceed
- If the document provided does not constitute a detailed design/plan (that ideally appears to have been through review and iteration)
  - then check with the user whether you should proceed,
    - offering instead to help flesh out the design/plan first if that seems necessary, and/or
    - to launch into implementation anyway with the design/plan as it stands.
- If it is a detailed design/plan, or they instruct you to proceed, go to the implementation phase below.

## Implementation

1. Start the implementation of the design/plan. Follow the instructions in AGENTS.md where they are relevant to the scope of the changes needed.
2. Continue until the implementation is complete against the design/plan, tests pass, lints are clean and test coverage is good. If pre-existing issues are found, resolve them if they are in files touched by the changes for the design/plan (and advise the user that you are doing so) unless there is significant risk or scope expansion from addressing them (in which case document the fixes needed) or the user has told you not to or to ignore them
3. When implementation is complete, double check that nothing in the design/plan doc is missing or deferred - you may only defer items that were in scope in the design/plan doc with explicit agreement from the user
4. When you are complete with the changes please kick off a subagent (use Sonnet if you are running in Claude Code, else use `self` or the default model) and have it use the post-change-think skill to review the changes with fresh and critical eyes in the hope it can find any issues, risks or opportunities that we should resolve early rather than tripping over them later
5. Decide which of the post-change-think subagent's findings have merit and implement any mitigations or additions needed for them. But see the note in the post-change-think about avoiding adding unwarranted complexity.
6. When that is complete, if the user specified it, kick off another subagent (wait for step 5 to be complete, do not do this in parallel) and have it use the check-against-design skill to ensure everything in the design is complete without gaps and that any differences are improvements identified since the design was done and will not cause issues. If the user did not request this then skip to stage 8 instead..
7. Decide which of any findings from the check-against-design subagent have merit and implement mitigations or additions needed for them.
8. Ensure the whole test suite passes, and that any touched files pass the linting, formatting and type checking (E.g. `./lfc.sh`)
9. Give a summary to the user. And offer to the user to
   a) move the input plan md doc into the done subfolder (under the docs/plans/ folder or another suitable place if a different precedent exists in the repo), and update its status and any links to/from it (use `git mv` if statged, or `mv` if not, do NOT try to write a new file and delete the old one)
   b) offer also to create a short set of release notes (a short md document inside docs/release-notes/ or another suitable location if one exists already that has a paragraph or two on each feature or significant change made and how to see it in action or test it if relevant)

## Obligations

- you should always follow the instructions in AGENTS.md, and the implementation should follow the 'house style' of the codebase you are adding to unless otherwise agreed or otherwise explicitly stated in the design
- docstrings should always be as required - refer to the docstrings skill if available
- you must implement the complete scope of the design/plan unless you have or get explicit agreement from the user to defer aspects
- unless there is a specific explicit reason not to, before triggering a review stage or handing back to the user:
  - run the whole test suite
  - run the linting and type checking script or commands (E.g. `./lfc.sh`) on all touched files
  - check to ensure that that you have implemented all aspects of the design/plan given
  - it is obviously bad form for a user to check these things when you hand back to them and for then find they are not done and green
- never offer to commit, as per AGENTS.md git write ops are blocked
