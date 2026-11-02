---
name: bump-version
allowed-tools: Read, Write, Edit, Bash(git status:*), Bash(git diff:*), Bash(git show:*)
description: Increment the version of the software
argument-hint: [version-number-or-increment]
---

Increment the version of the software: `$ARGUMENTS`

## Instructions

Update the version number as per the argument. 

Increments:

- If the user specifies a specific version number, then update the version number to that.
- If the user specifies an increment, then increment the version number by that amount if it is a number
- Or it may be a string like "major" or "minor" or "patch" (for invrementing the 1st, 2nd, or 3rd digit accordingly).

Places to update the version number:

- Change:
  - project dependency files
    - E.g. for Python: pyproject.toml (and the associated in package lock files, like uv.lock [if uv is used]) or requirements.txt for a project still using old PIP (yuck)
    - E.g. for Typescript/Javascript: package.json (and the associated lock files) - be that Node/Deno/etc backends or frontends
  - any constants defined in the code (E.g. in constants.py, config.py or general.py)

For lock files, prefer to edit them as text files where possible rather than using tools to update them from the project deps. If editting them is not possible then use the tools, but editting is preferred. If updating them at all is not possible then inform the user.

Process

1. First check for any memories stored by previous runs of this skill in this repo as that may save you time
2. And decide whether this project has a separate backend (BE) and frontend (FE) that might be individually versioned (and/or any other subcomponents) for you to increment, or just one. If there are multiple separately versioned components, then the user may have told you to increment only one/some, or they may have said all (if they don't say then assume it is all).
3. You can use ripgrep (rg) to do a quick search for the old version number in the codebase
4. After the updates you can use ripgrep again to check you have found all places to update.
5. If there was no valid memory (in step 1 above) about using this skill, then maybe save one for next time. Obviously save time and don't both if there was a valid one already.

Finally propose a commit message to the user to use. Example: "Bump version to $VERSION"
