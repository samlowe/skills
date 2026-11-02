# skills

Agent skills for coding agents such as Claude Code, Codex, Cursor and StrataCode. 

| Skill | What it does | Install |
| --- | --- | --- |
| [agent-collab](skills/agent-collab/README.md) | Lets two or more coding agents working in the same repo message each other, possibly in different harnesses. | `npx skills add samlowe/skills --skill agent-collab -g` |
| [bump-version](skills/bump-version/SKILL.md) | Increments the project version in dependency files, lockfiles, and code constants (explicit version or major/minor/patch). | `npx skills add samlowe/skills --skill bump-version -g` |
| [create-design-md](skills/create-design-md/SKILL.md) | Produces a detailed, review-ready design/plan markdown doc under `docs/plans/`, closing open questions and iterating via subagent review. | `npx skills add samlowe/skills --skill create-design-md -g` |
| [docstrings](skills/docstrings/SKILL.md) | Ensures touched or scoped functions, methods, and classes have appropriate one-line or full docstrings. | `npx skills add samlowe/skills --skill docstrings -g` |
| [handoff](skills/handoff/SKILL.md) | Compacts the current conversation into a handoff document (saved outside the repo) for a fresh agent to continue. | `npx skills add samlowe/skills --skill handoff -g` |
| [implement-plan](skills/implement-plan/SKILL.md) | Implements a design/plan markdown file through tests, lint, post-change review, and optional design alignment checks. | `npx skills add samlowe/skills --skill implement-plan -g` |
| [peer-review](skills/peer-review/SKILL.md) | Runs an independent review→revise→re-review loop via the Stratacode headless CLI (high-level design, design doc, or implementation). | `npx skills add samlowe/skills --skill peer-review -g` |
| [post-change-think](skills/post-change-think/SKILL.md) | After a change lands, looks for bugs, design gaps, house-style drift, refactors, and test coverage before merge. | `npx skills add samlowe/skills --skill post-change-think -g` |

Leave out `--skill` to install them all.

## Development

Tests use pytest and need nothing else:

```sh
uv run pytest
```

## Licence

[MIT](LICENSE)
