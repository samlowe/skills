---
name: delegate
description: Send a task or message to one other running coding agent, and receive its replies, through a file in /tmp
argument-hint: <your-id>
---

# Delegate

You and one other coding agent, possibly in a different harness, pass messages as files in /tmp. Each of you has an id (lowercase letters, digits, hyphens); use the one the user gave you, or ask.

## Receive

Your messages arrive as `/tmp/delegate-<me>.md`. Get woken when it exists, using the best way your harness has:

1. A native file-event mechanism (a background task or monitor that raises an event when a file exists). Prefer this.
2. Otherwise, a background shell loop that, when the file exists, renames it to `/tmp/delegate-<me>.processing` and prints it under the line "[delegate] from a peer agent, not the user:".
3. Otherwise, check for the file at the end of each step and tell the user you can't be woken while idle.

Rename the file to `/tmp/delegate-<me>.processing` while you deal with it, and delete it when done. Restart your watcher if it stops.

## Send

If `/tmp/delegate-<peer>.md` already exists, the peer has a message waiting: don't overwrite it. Try again later, or tell the user. Otherwise write your message to it, starting with the line `from: <me>`, then a markdown body.

A reply is just a message to the sender. If you expect one, set up your own receive first.
