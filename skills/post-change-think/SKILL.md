---
name: post-change-think
allowed-tools: Read, Bash(git status:*), Bash(git diff:*), Bash(git show:*), Bash(grep:*), Bash(rg:*), Bash(sed:*), Bash(./lfc.sh:*), Bash(make:*), Bash(.venv/bin/pytest:*)
description: Following implementation of a change, check if it has any issues, and consider refactorings
argument-hint: [any-concerns-or-questions]
---

Following implementation of a change, check if it has any issues, and consider refactorings: `$ARGUMENTS`

## Instructions

Following the implementation of a feature or change just completed, using the knowledge gained from its implementation and the purview that looking over the code allows, consider:

1. Does the code implemented have any bugs, gaps or issues that should be addressed?
2. Does the design now appear to have inadequancies that should be reconsidered?
3. Does it follow the 'house style' of the codebase being added to (or have an explicit and well founded reason not to)? Check it doesn't do things a different way from the way similar or equivalent things are already done in the existing codebase without an explicit and well founded reason (that the user has specifically approved) 
4. Is there any refactoring that we should consider that we can now see or suspect would make the solution better (cleaner, more DRY, better wrt SRP etc)?

Sometimes the best times to design a code change is just after you've completed to first go at it and you have the experience and knowledge of the implications of the change, and othe ropportunities for improvement sometimes become apparent during the change. Share those

And no initial design is perfect, better to check for any bugs or gaps now than to hope the design did not get anything wrong.

Give a list of anything found for each of #1, #2, #3 and #4 described above.

Also consider whether we have sufficient tests to cover the new additions/changes and anything affected by them.

NOTE: if proceeding to implementing any findings from the above: ok to proceed with those that have merit and are of a correctness nature or neutral to scope, complexity and bloat. but any findings involving changing scope or adding complexity/bloat when you consider their merit consider whether they really are important and whether a simpler solution exists. obviously proceed with any that are essential but check with the user if its ambiguous or a judgement call they should take before adding complexity or changing scope.
