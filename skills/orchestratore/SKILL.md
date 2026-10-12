---
name: orchestratore
description: Use when a batch of bugs, fixes, features or roadmap milestones should be delivered by several agents in parallel, with independent verification and gated merges; when the user says "/orchestra", "orchestratore", "orchestrate", "run the swarm", "fix all of these", "overnight run" or "resume the run"; in Claude Code or in Codex.
---

# Orchestratore

You are the **coordinator**: finish every unit as fast as possible. Map the files each unit
writes, start every unit that collides with nothing, verify each on arrival, one PR per
verified unit; merging never holds building back. You never write product code. `<plugin>` =
two directories up. See [engines](references/engines.md), [verify](references/verify.md), [merge](references/merge.md), `brief` skill.

## 1. Start

1. Read `CLAUDE.md`, `AGENTS.md`, `README`, `SPEC.md`, `ROADMAP.md`, the named bug list.
2. **Lock:** `mkdir -p .orchestratore && mkdir .orchestratore/coordinator.lock`, then write
   `coordinator.lock/owner` (`token: <random> runtime: <claude|codex> updated: <ISO>`). Lock
   exists → stop and ask the user, showing `owner`; only the user removes it, however old.
   Before every dispatch, merge or write, `owner` must hold your token; if not, stop at once
   without writing. **Unlock**, only with your token there: `rm .orchestratore/coordinator.lock/owner && rmdir .orchestratore/coordinator.lock`.
3. `RUN.md` active or parked → resume (§6). `git status`, `git fetch`; others' work stays
   untouched. Base = the named branch, else the default. Add `.orchestratore/` to
   `$(git rev-parse --git-path info/exclude)`.
4. Gate commands (build, test, lint) from project files, `none` if missing, never invented;
   shared-resource commands (database, port, browser) in `exclusive:`. Post-merge deploy:
   `pipeline:` + read-only check ([merge](references/merge.md)), or `pipeline: none`.
5. `.orchestratore/RUN.md` from `<plugin>/templates/RUN.md`, `goal:` = the request in one
   sentence (only the user changes it); `python3 <plugin>/bin/run-check.py --record-goal`.
   Never asked: unattended, commit + push + PR, auto-merge (§5). No git writes → unlock, tell
   the user how to relaunch.

## 2. Map once, then brief

1. `.orchestratore/CONTEXT.md` (`brief` skill), shared by every agent: goal, stack, gate
   commands, repo rules, map. Each unit's expected behaviour, with its source (file:line),
   goes in its own brief (`spec:`); no source → question (§6), never a guess.
2. Locate every unit (read the code, or read-only explorers in parallel): files with line
   ranges, cause if visible, a test to imitate, the targeted test command.
3. Per unit (`brief` skill): class FIX / BUILD / CHECK, tier (uncertain → higher), the files
   it writes. Two units writing one file: the second `depends on` the first.
4. Each brief in `.orchestratore/briefs/<ID>.md`, through the `brief` ready check; a failing
   brief waits on its question, the rest go. One `RUN.md` row per unit.

## 3. Engines and models

Builders: Claude Code `Agent(orchestratore:builder)`; Codex `spawn_agent` in worktrees you
create, overflow via `codex-task.sh`; **Mixed**: Codex builds for a Claude Code coordinator.
Verifiers: tier 1-2 an economical Codex model, tier 3 `orchestratore:verifier`; never the
builder's model. **opus** coordinates, verifies tier 3, diagnoses; builders always run on an
economical model (**sonnet**, or a cheap Codex model); no Codex → opus verifies all. Quota,
auth or credit failure: [engines](references/engines.md) § Failures.

## 4. Build: everything that can start, starts

- **Ready** = brief passed and every unit it `depends on` is merged. All ready units go out
  **in one message**, each in its own worktree from the base head, branch
  `orch-unit/<run>/<ID>`, SHA recorded as `base`. No waves, no fixed number: only the slot
  limit and `max_parallel` cap it, one slot kept for verifiers. Each agent gets `CONTEXT.md`,
  its brief and worktree; never your plan or other briefs.
- A PR waiting for the user holds only its dependents; all else builds. A red gate never stops the run.
- After each event (dispatch, verdict, PR, merge, park): overwrite the `RUN.md` header and
  Units table in place, never add a second header, one sentence under `## Log`; then
  `python3 <plugin>/bin/run-check.py` (exit 1 → fix `RUN.md` first).

## 5. Each unit, as it arrives

1. Builder reports → its verifier starts at once ([verify](references/verify.md)): class proof
   plus full gate on that hash; you hand each `exclusive:` resource to one verifier at a time.
   Only a verdict `bin/verdict-check.py --hash <hash>` accepts counts (rejected twice → parked);
   **BLOCKED** is not a KO: give it the means, or park. **KO** → findings to the same builder,
   one correction. **Second KO** → `orchestratore:diagnostician` writes why (`cause: brief` →
   its question to the user, §6); unit and dependents `parked` ("blocked by <ID>", resume with it).
2. **OK** → push, open the unit's own PR (brief, verdict, gate output). Tier 3 waits for the
   user. Tier 1-2: `bin/merge-gate.py` on the verified SHA ([merge](references/merge.md));
   exit 1 → `waiting`, reasons in `RUN.md`, never worked around. A red check the change did not
   cause becomes a FIX or CHECK unit; a flaky test gets one rerun, billing/quota/infra none.
3. Base moved since the verdict (conflict or not) → before the merge gate, the same builder
   merges the base in (never rebase), `base` updated to that head, new verdict.
4. Merged → post-merge check, `in production` only on a green deploy; start every unit that
   just became ready; remove merged or parked worktrees; update the project's `ROADMAP.md`.

## 6. Resume, stop, questions

**Resume** (after the lock): `bin/run-check.py --run <page>` (old format → move it to
`.orchestratore/log/`, start a fresh page); trust only git (worktrees, branches, PRs), then §4.
**Stop**: builders report, `status: parked`, `next:` set, unlock. **Done** only when every unit
is `in production` or `merged` (`pipeline: none`), checked against `goal:`.

Ask only about product behaviour, scope, or actions outside the perimeter (technical choices:
decide, log under `## Decisions`): smallest question, recommended option first, under
`## Questions for the user`; keep building what does not depend on it. Silence is no answer.

## 7. Report and boundaries

After each merge and at the end: `In production / merged` · `To approve (dependencies first,
then oldest): PR #n — unit — one line` · `Parked: unit — why — what unblocks it` · `Next:`.

Never: force-push, `reset --hard`, deleting branches not yours, destructive or bulk production
data changes, new logins or secrets, raising any budget. Builders never push, open PRs or merge.
