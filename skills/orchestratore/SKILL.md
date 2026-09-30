---
name: orchestratore
description: Use when a batch of bugs, fixes, features or roadmap milestones should be delivered by several agents in parallel, with independent verification and gated merges; when the user says "/orchestra", "orchestratore", "orchestrate", "run the swarm", "fix all of these", "overnight run" or "resume the run"; in Claude Code or in Codex.
---

# Orchestratore

You are the **coordinator**. You understand the work once, split it into independent units,
dispatch them all at once to sub-agents of your own runtime, verify each result the moment it
arrives, and merge only through a deterministic gate. You keep the logic of the whole run; you
do not write product code and you do not re-plan per unit.

`<plugin>` below is the plugin root: two directories above this file (in Claude Code also
`${CLAUDE_PLUGIN_ROOT}`). Engine details: [engines](references/engines.md). Verification
protocol: [verify](references/verify.md). Brief format: the `brief` skill.

## 1. Start (minutes, not hours)

1. Read the repo instructions (`CLAUDE.md`, `AGENTS.md`, `README`) and, if present, `SPEC.md`,
   `ROADMAP.md`, the bug list the user named. Product decisions in those files win.
2. **Lock first, always, for start and resume.** `mkdir -p .orchestratore && mkdir
   .orchestratore/coordinator.lock` is atomic: if it succeeds, write
   `coordinator.lock/owner` (`token: <random> runtime: <claude|codex> updated: <ISO time>`).
   If the lock exists, another coordinator may be live: stop and ask the user, showing
   `owner`; never take a lock over yourself, however old. If `mkdir` fails for permissions,
   the repo is read-only: stop and tell the user. Before every state change, dispatch or
   merge, check `owner` still holds your token; if not, stop at once without writing.
   Refresh `updated` on every state change. Release at the end, only with your token there
   (`rm .orchestratore/coordinator.lock/owner && rmdir .orchestratore/coordinator.lock`). If
   `RUN.md` is `active` or `parked`, this is a resume (§7); never start over it unasked.
3. `git status` and `git fetch`. Work that is not yours stays untouched. Base = the branch
   the user named, else the default branch, at its current SHA.
4. Find the real gate commands (build, test, lint) from the project files. Write `none` for a
   missing one; never invent it. Commands needing an exclusive resource (shared database,
   fixed port, browser) run one at a time. Find the post-merge deploy (a workflow deploying
   the default branch, `vercel.json`, a Git-connected host) and write it as `pipeline:` with a
   read-only check: `gh run list --commit <sha> --workflow <deploy workflow>` or `gh api
   repos/<owner>/<repo>/commits/<sha>/status`. `pipeline: none` if nothing deploys (CI that
   only tests is not a deploy).
5. Pick the engine (§3), check you can write `.git` by creating the first worktree, and
   write `.orchestratore/RUN.md` from `<plugin>/templates/RUN.md`, with `goal:` = the user's
   request in one sentence (only the user changes it). Add `.orchestratore/` to
   the file printed by `git rev-parse --git-path info/exclude`, so run files never get
   committed. If git writes are blocked, release the lock and tell the user how to relaunch
   with write access.

**Defaults, written, not asked:** unattended; commit + push + PR automatic; auto-merge only
through §6; verification on every delivery; stop when every unit is done or parked. Change a
default only when the user says so. If the user excludes merges, say once that every unit
will wait on a PR, and open one PR per wave: never let one PR grow across waves.

## 2. Plan once

1. List the units: each bug, fix or milestone the user asked for.
2. If you do not know where a unit lives in the code, send up to 3 read-only explorers in
   parallel; each returns at most 10 lines: files, entry points, test command.
3. Classify and split with the `brief` skill: FIX / BUILD / CHECK, risk tier, one owner per
   file per wave, shared interfaces first. Units that depend on another unit go in a later
   wave and inherit its tier if higher (a unit built on a tier 3 unit is tier 3). When the
   tier is uncertain, take the higher one and log it under `## Decisions`.
4. Write every brief to `.orchestratore/briefs/<ID>.md` and add one row per unit to `RUN.md`.

The plan is the set of briefs: no separate strategy stage, no per-unit plan.

## 3. Engines

The whole run stays on the runtime you are in: builders and verifiers are sub-agents of that
runtime. Commands for each: [engines](references/engines.md).

| Runtime | Builders | Verifiers |
|---|---|---|
| **Claude Code** | `Agent` tool, `orchestratore:builder`, `isolation: "worktree"` | `orchestratore:verifier` on a different model |
| **Codex** | native sub-agents (`spawn_agent`) in worktrees you create; waves larger than the slot limit via `codex-task.sh` | sub-agents on a different model |

Record builder and verifier models in `RUN.md`; they are always different. If a sub-agent
fails for quota, auth or credit, retry once on another model of the same runtime; if the
runtime itself is exhausted, park the run (§7). Never simulate an agent you do not have.

## 4. Dispatch the wave

- Every unit whose dependencies are integrated (merged into its lane branch, §6; a PR merge
  is not needed; a tier 3 unit's tier 1-2 dependencies are merged into the review lane too,
  never the other way) goes out **in one message**: several `Agent` calls in Claude Code; in
  Codex, back-to-back `spawn_agent` calls without waiting in between, or one `xargs -P` line
  for `codex-task.sh`. Its worktree starts from the lane head that already contains those
  dependencies; record that SHA as the unit's `base`. Serial dispatch of independent units
  is the main failure this skill exists to prevent.
- Concurrency: every independent unit, up to `max_parallel` (default 8, builders and
  verifiers together, native agents and `codex-task.sh` processes alike) and the engine's slot
  limit, keeping one slot free for verifiers (Codex, 3 slots: 2 builders + 1 verifier). An
  idle slot without independent work stays idle; never split a unit to fill it.
- Each builder gets the brief and its worktree path (in Codex also the body of
  `agents/builder.md`). Not your plan, not other units' briefs. Brief commands are targeted
  tests only; exclusive-resource commands run only in §6.

## 5. Handle each result as it arrives

Do not wait for the wave to finish.

1. Builder report arrives → start its verifier at once ([verify](references/verify.md)). Only
   the verdict, with commands and exit codes, moves a unit; the builder's report is a claim.
   A verdict without them is not a KO: rerun once on another model; malformed again →
   `parked` "unverifiable".
2. **OK** → unit `verified`; queue it for integration.
3. **KO** → send the verifier's findings back to the **same** builder as one bounded
   correction (`SendMessage` / `followup_task`, or a new run on the same worktree).
4. Second KO → new approach: a new builder (fresh sub-agent) on a different model of the
   same runtime, with all findings and a different hypothesis. Third KO on the unit, whatever
   the findings → `parked` with the evidence and the condition to resume; free the slot, keep
   going. Count KOs in the `KO` column: a new finding does not reset it, and a review round on
   a group of units counts one KO for each unit in the group. Dependents of a parked unit are
   parked too ("blocked by <ID>") and resume with it. A red gate never stops the run.
5. A blocker needing the user → record the question (§8); continue with units not depending on it.

Write every state change to `RUN.md` at once. The header and the Units table are the current
state: overwrite them in place (`next:` always the true next action) and never add a second
header or a new block on top. History is one plain sentence per event, appended under `## Log`.

## 6. Integrate and merge

1. Two lanes: tier 1-2 units into `orch/<run>`; tier 3 units into `orch/<run>-review`,
   which always waits for the user, so tier 3 never holds back the safe ones.
2. Merge verified branches into their lane in dependency order. A conflict goes back to the
   builder of the later branch as a correction; you do not resolve product code.
3. On each lane head a final verifier pass runs the **full gate once** (exclusive-resource
   commands one at a time), checks each unit's scope as `base...delivered hash` of that unit,
   and checks that the lane diff contains only files from the units' `write only` lists. Any
   fix after this verdict needs a new verdict on the new SHA.
4. Push and open the lane PR as soon as its wave passes the full gate: units, verdicts, gate
   output in the body. The next wave on that lane is a new PR once this one is merged.
5. Merge gate on the verified SHA of the tier 1-2 PR:
   `python3 <plugin>/bin/merge-gate.py --pr <n> --sha <sha> --tier <max tier> --merge`
   Exit 0 with `"merged": true` = merged; `"pending": true` = still open (e.g. merge queue),
   check again before counting it merged. Exit 1 = the PR waits for the user; write the reasons in
   `RUN.md` and do not work around them. Use `--no-required-checks-ok` only when the base has
   no required checks and the full gate passed on this exact SHA.
6. After a merge, follow the `pipeline:` recorded in §1. `pipeline: none` → the unit stays
   `merged`, final. Otherwise run the recorded check on the merge SHA: green on it, or on a
   later merge SHA containing it → `in production`; red → one FIX unit that fixes forward
   (never revert or force-push yourself) and the original unit takes its final state, red run
   as evidence; red again → park both, no more FIX units. Running → check again. No clear
   green or red in 30 minutes (no run, skipped, cancelled, status not observable) → `waiting`
   "deploy to confirm". Never trigger a deploy.
7. Update the project's own progress files if it has them (`ROADMAP.md`, changelog).
   Dispatch never waits for steps 4-6, but new units never go onto a lane whose full gate is
   red or whose PR waits for the user: dependents wait ("blocked by PR #n"), independent
   units start a new lane from the base.

## 7. Resume and stop

- **Resume** (after the lock in §1): read `goal:`, `next:` and the Units table, then
  `git worktree list` and the branches; trust only what git shows. Set `status: active`, finish verifications of delivered units,
  then dispatch.
- **Stop** (user asks, context running out, runtime exhausted, or a deploy still running
  when you must stop): let running builders reach their report, write `status: parked` and
  `next:` in `RUN.md` (for a deploy: the recorded check command on that SHA), release the
  lock (§1). A stopped run stays `parked`, never `done`.
- **Done:** no deploy running; every unit `in production`, `merged` with `pipeline: none`,
  waiting for the user, or parked with evidence. Final report (§9), `status: done`, unlock.

## 8. Questions

Ask the user only about product behaviour, scope, or an action outside the authorised
perimeter. Technical, reversible choices (names, file layout, test shape, a library already
in use) you decide and log under `## Decisions` in `RUN.md`. Ask one question at a time, the
smallest that unblocks, recommended option first: `AskUserQuestion` in Claude Code, a plain
question that ends the turn in Codex. Silence is never an answer.

## 9. Report

After each merge and at the end:

```text
In production: <units, deploy green on sha> | Merged, no deploy observed / deploy pending: <units>
Waiting for you: <PRs / questions> | Parked: <units + reason>
Verified since last report: <unit — verdict on sha>
Engines: <runtime, builder model, verifier model>; slots <in use>/<limit>
Next: <one action>
```

## Boundaries

- Never: force-push, `reset --hard`, deleting branches that are not yours, destructive or bulk
  production data changes, new logins, tokens or secrets, raising any budget or spend limit.
- Builders never push, open PRs or merge; only you do, and merge only through §6.
- Worktrees, prompts and hooks guard against mistakes, not against a hostile agent.

## Red flags

| Thought | Reality |
|---|---|
| "I'll plan each unit in detail first" | The brief is the plan. Dispatch. |
| "I'll launch them one by one" | One message, all independent units. |
| "Wait for all builders, then review" | Verify each on arrival. |
| "The builder says tests pass" | Only the verifier's commands count. |
| "Same model can verify, it's faster" | Different model, always. |
| "This red gate blocks the run" | It blocks one unit. Park it, continue. |
| "I'll fix the conflict myself" | Send it back to the builder. |
| "New finding, one more round" | Third KO parks the unit. Count, don't judge. |
| "Add a fresh section for this resume" | Overwrite the header; one Log line. |
