---
name: docstrings
description: Ensure docstring coverage
argument-hint: [scope_to_check]
---
# Ensure docstring coverage

Please check the files that have been touched by the scope of activity referred to by the user.

Take the opportunity to ensure:
- all functions, methods and classes at least have one line docstrings,
- and that significant public functions/methods have full docstrings (inc args, retruns and raises).
- implementation of dunder methods and simple conversions (E.g. `def to_dict()`) only need one line docstrings even though public, but public methods or functions with significant size, params, exceptions, or nuanced functionality need full docstrings

The scope of files to inspect and potentially update could be indicated by the user to be one of:
1. files touched in the PR - diff of current branch with the base_branch (maybe main - check with the user if they havn't confirmed)
2. files touched by changes in the unstaged and/or staged changes
3. specific files or folders indicated

If the user has not specifed which of the above to work on, ask them to indicate (if possible give them options so they can quickly choose)

Ensure the line length of any docstrings you add does not exceed the conventions of the project/repo (often 88 chars). Do not use `` (double backticks) in docstring, a single backtick is preferred.

Scope: $ARGUMENTS
