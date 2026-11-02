---
name: create-design-md
description: Create a detailed design/plan as a markdown doc
---
Please create a detailed design/plan for implementation in a md doc in docs/plans/ that can go through a review process.

Ensure you close all open design/plan questions, and scope questions, in the doc (a design doc with open design questions is not really a design doc). If you can close them from reviewing the codebase and reasoning then do so, if you need the users steer or approval then ask them questions (one at a time, each with options that have pros and cons and a recommendation). Do not add an author's (person or agent) name to the document.

When you've finished the document please kick off a subagent (use Sonnet if you are running inside Claude Code, otherwise use the default) to:

1. do an extensive review of the design/plan doc in the hope it can find issues, gaps, inconsistencies or refactoring opportunities that we can resolve before implementation rather than tripping over them later.
2. when it's given you its findings please add to and/or ammend the design/plan doc to mitigate and incorporate all those of the findings that warrant doing so. but don't fall into the trap of scope-creep or adding excessive complexity just because a reviewer suggests something - their job is to find and suggest things, but you need to balance complexity vs value and check with the user before allowing significant scope creep from review findings (e.g. introducing new subsystems)
