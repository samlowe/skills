# skills

Agent skills for coding agents such as Claude Code, Codex, Cursor and StrataCode. 

| Skill | What it does | Install |
| --- | --- | --- |
| [agent-collab](skills/agent-collab/README.md) | Lets two or more coding agents working in the same repo message each other, possibly in different harnesses. | `npx skills add samlowe/skills --skill agent-collab -g` |

Leave out `--skill` to install them all.

## Development

Tests use pytest and need nothing else:

```sh
uv run pytest
```

## Licence

[MIT](LICENSE)
