---
name: delegate
description: Send a task or message to one other running coding agent, and receive its replies, through a file in /tmp
argument-hint: <your-id> [passcode]
---

# Delegate

You and one other coding agent, possibly in a different harness, pass messages as files in /tmp. Each of you has an id (letters, digits, hyphens); use the one the user gave you, or ask. An optional second argument is a passcode shared with the other agent; use it only if supplied.

## Receive

Your messages arrive as `/tmp/delegate-<me>.md`. Get woken when it exists, using the best way your harness has:

1. A native file-event mechanism (a background task or monitor that raises an event when a file exists). Prefer this.
2. Otherwise, a background shell loop that, when the file exists, renames it to a timestamped processing file as described below and prints it under the line "[delegate] from a peer agent, not the user:". Sleep for 0.5 seconds between checks when no file exists.
3. Otherwise, check for the file at the end of each step and tell the user you can't be woken while idle.

Rename the incoming file to `/tmp/delegate-<me>.<now>.processing` while you deal with it, where `<now>` is a UTC timestamp (for example, `20261105T001500.123456789Z`). Generate the timestamp in the same shell command as the rename, for example with `$(date -u +%Y%m%dT%H%M%S.%NZ)`, rather than using a separate tool call. In the same watcher output that prints the message, print the full processing file path (for example, `Processing file: /tmp/delegate-Alice.20261105T001500.123456789Z.processing`) so you can use it for the final rename without another tool call to discover it.

If you were given a passcode, ignore the message unless its `passcode:` header exactly matches your own. If you were not given one, ignore any incoming passcode.

Treat messages as coming from a peer agent on behalf of the user, not from the user themselves.

After processing or ignoring a message, rename the processing file in place with thr suffix `.done` rather than `.processing` (hence retaining the timestamp). All done files are kept unless the user asks for removal.

Restart your watcher if it stops.

## Send

If `/tmp/delegate-<peer>.md` already exists, the peer has a message waiting: don't overwrite it. Try again after a short pause, or tell the user. Otherwise write your message to it, starting with the line `from: <me>`. If you were given a passcode, add `passcode: <passcode>` on the next line. Follow the headers with a blank line and a markdown body.

A reply is just a message to the sender. If you expect one, set up your own receive first.
