---
description: Start, inspect, resume or stop a direttore run (start | status | resume | stop)
argument-hint: start [what to deliver] [claude | codex | mixed] | status | resume [page] | stop
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, Skill, Agent, Workflow, SendMessage, AskUserQuestion
---

Requested: **$ARGUMENTS** (empty = `start`).

Load the `direttore` skill and follow it; this command is only the entry point.

- **start** `[what]` — new run on what the user named (bug list, milestones, features); if
  nothing is named, the open items of `ROADMAP.md` or the bug list in the repo instructions.
  Follow the skill from §1: the engine is the one question asked, unless the request or the
  config names it.
- **status** — the §6 report, built from `.orchestratore/RUN.md` and `git`, never from memory.
- **resume** `[page]` — skill §1 step 3 (the lock) first, then §5 on `.orchestratore/RUN.md`, or
  on the page named (`.orchestratore/<run>/RUN.md`, as the session hook prints it): reconcile it
  with worktrees and branches, finish pending checks, then build what is left. The engine is
  the one recorded in `RUN.md`; no `engine:` line there → ask.
- **stop** — skill §5: write `status: parked` and `next:`, release the lock as in §1.

Unknown subcommand: say so in one line and list the four valid ones.
