---
description: Start, inspect, resume or stop an orchestratore run (start | status | resume | stop)
argument-hint: start [what to deliver] | status | resume | stop
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, Skill, Agent, SendMessage, AskUserQuestion
---

Requested: **$ARGUMENTS** (empty = `start`).

Load the `orchestratore` skill and follow it; this command is only the entry point.

- **start** `[what]` — new run on what the user named (bug list, milestones, features); if
  nothing is named, the open items of `ROADMAP.md` or the bug list in the repo instructions.
  Follow the skill from §1 without asking for its defaults.
- **status** — the §9 report, built from `.orchestratore/RUN.md` and `git`, never from memory.
- **resume** — skill §1 step 2 (the lock) first, then §7: reconcile `RUN.md` with worktrees
  and branches, finish pending verifications, then dispatch.
- **stop** — skill §7: let running builders report, write `status: parked` and `next:`,
  release the lock as in §1.

Unknown subcommand: say so in one line and list the four valid ones.
