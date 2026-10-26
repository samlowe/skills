# agent-collab (for humans)

Lets two coding agents working in the same repo, such as Claude Code and StrataCode, message each other through a `.agent-collab/` folder at the repo root. The folder ignores itself with a `.gitignore` of `*`, so nothing is ever committed. `SKILL.md` is what the agents read; this file is for you.

Linux and macOS only. `collab.py` needs Python 3.11 or later and nothing else. If the repo has a virtualenv, you can use `.venv/bin/python` in place of `python3` in the commands below. Either works.

## Installing

Save the skills files into your user-wide skills folder, e.g. `~/.agents/skills/agent-collab`.

`npx skills` support will probably be added later.

## Starting

Tell each agent to use the skill and give it a name, e.g. `/agent-collab alice` in one session and `/agent-collab bob` in the other.

## Joining in yourself

From a terminal anywhere in the repo:

```sh
python3 <skill>/collab.py send --as user --to '*'
```

Type the message, then press Ctrl+D. The agents see it as coming from you. To follow the conversation:

```sh
python3 <skill>/collab.py log --follow
```

`who` lists who's present and whether each agent's watcher is running.

## Permission rules

An agent woken by its peer while you're away can't reply until its harness lets it run `collab.py`. To approve it once, allow the exact prefix every printed command starts with. `join` prints it, e.g.:

```
/usr/bin/python3 /home/<user>/.agents/skills/agent-collab/collab.py
```

- **Claude Code:** add `"Bash(<prefix>:*)"` to `permissions.allow` in `~/.claude/settings.json` to cover every repo, or in a repo's `.claude/settings.local.json` for just that one.
- **StrataCode:** add the same `"Bash(<prefix>:*)"` rule to `permissions.allow` in `.stratacode/settings.json`, or run in `ai_auto` mode.

The prefix is the interpreter and the script's absolute path, so the rule covers only this script.
