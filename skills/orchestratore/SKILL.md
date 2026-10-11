---
name: orchestratore
description: Use when a batch of bugs, fixes, features or roadmap milestones should be delivered by several agents in parallel, with independent verification and gated merges; when the user says "/orchestra", "orchestratore", "orchestrate", "run the swarm", "fix all of these", "overnight run" or "resume the run"; in Claude Code or in Codex.
---

# Orchestratore

You are the **coordinator**. You understand the work once, split it into independent units,
dispatch them all at once to sub-agents of your own runtime, verify each result the moment it
arrives, and merge only through a deterministic gate. You keep the logic of the whole run; you
do not write product code and you do not re-plan per unit.

`<plugin>` = two directories above this file (Claude Code: `${CLAUDE_PLUGIN_ROOT}`). Details:
[engines](references/engines.md), [verify](references/verify.md), [merge](references/merge.md), the `brief` skill.

## 1. Start (minutes, not hours)

1. Read the repo instructions (`CLAUDE.md`, `AGENTS.md`, `README`) and, if present, `SPEC.md`,
   `ROADMAP.md`, the bug list the user named. Product decisions in those files win.
2. **Lock first, always, for start and resume.** `mkdir -p .orchestratore && mkdir
   .orchestratore/coordinator.lock` is atomic: if it succeeds, write `coordinator.lock/owner`
   (`token: <random> runtime: <claude|codex> updated: <ISO time>`). If the lock exists, another
   coordinator may be live: stop and ask the user, showing `owner`; never take a lock over
   yourself, however old: only the user removes it. If `mkdir` fails for permissions, the repo
   is read-only: stop and tell the user. Before every state change, dispatch or merge, check
   `owner` still holds your token; if not, stop at once without writing. Refresh `updated` on
   every state change. Release at the end, only with your token there (`rm
   .orchestratore/coordinator.lock/owner && rmdir .orchestratore/coordinator.lock`). If
   `RUN.md` is `active` or `parked`, this is a resume (§7); never start over it unasked.
3. `git status` and `git fetch`. Work that is not yours stays untouched. Base = the branch
   the user named, else the default branch, at its current SHA.
4. Find the real gate commands (build, test, lint) from the project files. Write `none` for a
   missing one; never invent it. Commands needing an exclusive resource (shared database,
   fixed port, browser) run one at a time. Record the post-merge deploy as `pipeline:` with
   its read-only check, as in [merge](references/merge.md), or `pipeline: none`.
5. Pick the engine (§3), check you can write `.git` by creating the first worktree, and write
   `.orchestratore/RUN.md` from `<plugin>/templates/RUN.md`, with `goal:` = the user's request
   in one sentence (only the user changes it), then run `python3 <plugin>/bin/run-check.py
   --record-goal`. Add `.orchestratore/` to the file printed by `git rev-parse --git-path
   info/exclude`, so run files never get committed. If git writes are blocked, release the lock
   and tell the user how to relaunch with write access.

**Defaults, written, not asked:** unattended; commit + push + PR automatic; auto-merge through
§6; verification on every delivery. Merges excluded → one PR per wave: never let one PR grow across waves.

## 2. Plan once: a spec and precise tickets before any builder starts

1. Write `.orchestratore/SPEC.md`: the goal and, per unit the user asked for, the expected
   behaviour with its source (`SPEC.md`, `ROADMAP.md`, the bug list: file and line). A
   behaviour no source states is a question (§8), never a guess. Then the **run context**
   `.orchestratore/CONTEXT.md` (`brief` skill): stack, one-test command, repo rules, map.
2. Locate every unit before writing its brief: read the code yourself, or send read-only
   explorers in parallel, as many as the units need. Each returns files with line ranges,
   the cause if visible, a similar test to imitate, and the targeted test command it ran on
   the base with its exit code.
3. Classify and split with the `brief` skill: FIX / BUILD / CHECK, risk tier, one owner per
   file per wave, shared interfaces first. Dependent units go in a later wave and inherit a
   higher tier (built on tier 3 = tier 3); an uncertain tier → the higher one, logged.
4. Write every brief to `.orchestratore/briefs/<ID>.md` and run the `brief` skill's **ready
   check** on it. A brief that fails does not go out: complete it, or its unit waits on a
   question. Ready briefs go out without asking the user. One row per unit in `RUN.md`.

## 3. Engines

By default the whole run stays on your runtime. **Mixed** (`mode = "mixed"` or the user asks):
a Claude Code coordinator has Codex build and verify (opus: tier 3, final). Commands: [engines](references/engines.md).

| Runtime | Builders | Verifiers |
|---|---|---|
| **Claude Code** | `Agent` tool, `orchestratore:builder`, `isolation: "worktree"` | units: economical Codex model (`codex-task.sh verify`); tier 3, final: `orchestratore:verifier` |
| **Codex** | native sub-agents (`spawn_agent`) in worktrees you create; waves larger than the slot limit via `codex-task.sh` | sub-agents on a different model |
| **Mixed** (Claude Code) | one background `codex-task.sh build` per unit in worktrees you create; record its `model=` | as Claude Code, on a Codex model other than the builder's |

Builder and verifier models differ. Claude models: **opus** for the complex work
(coordinating, final and tier 3 verification, diagnosing), **sonnet** for the rest (building);
no other. Tier 1-2 units: an economical Codex verifier; no Codex → opus. `RUN.md` records
`verifier: <model> (unit), <model> (final)`, opus as `(unit, no codex)`; run-check enforces it.
Quota, auth or credit failure: retry once (Codex: another model; Claude Code: a fresh agent;
mixed: Claude builders); runtime exhausted → park the run (§7). Never fake a missing agent.

## 4. Dispatch the wave

- A lane is **blocked** while its full gate is red or its PR waits for the user (merge gate
  exit 1, merges excluded, and always the tier 3 review PR). A unit whose dependencies sit on
  a blocked lane stays `queued`, noted "blocked by PR #n"; an independent unit opens the next
  lane from the base (`orch/<run>-2`, `orch/<run>-review-2`, ...). Never stack onto it.
- Every unit whose dependencies are integrated (merged into its lane branch, §6; a PR merge is
  not needed while the lane is not blocked; a tier 3 unit's tier 1-2 dependencies are merged
  into the review lane too, never the other way) goes out **in one message**: `Agent` calls in
  Claude Code (mixed: background Bash calls); in Codex, back-to-back `spawn_agent` calls, or
  one `xargs -P` line for `codex-task.sh`. Its worktree starts from the lane head with those
  dependencies; record that SHA as the unit's `base`. Serial dispatch of independent units is
  the main failure this skill exists to prevent.
- Concurrency: no fixed number; you decide. Send every ready independent unit, capped only
  by the engine's slot limit and `max_parallel` if the user set one, keeping one slot free
  for verifiers (Codex, 3 slots: 2 builders + 1 verifier). Never split a unit to fill a slot.
- **Ship before you build more.** The run holds at most two unmerged tier 1-2 waves, all lanes
  together (one in its PR, one built on it); the next waits for that merge, on a new lane too.
  A red check the change did not cause becomes a FIX or CHECK unit first; a flaky test gets
  one rerun, a billing, quota or infrastructure failure none (record it; fix it or wait).
- Every agent you start (builder, fresh builder, verifier, diagnostician) gets `CONTEXT.md`
  first; a builder then its brief and worktree path (Codex: also `agents/builder.md`). Not
  your plan, not other units' briefs. Brief commands: targeted tests only (exclusive: §6).

## 5. Handle each result as it arrives

Do not wait for the wave to finish.

1. Builder reports → start its verifier at once ([verify](references/verify.md)). Only a verdict
   that `bin/verdict-check.py --hash <hash>` accepts moves a unit; the builder's report is a
   claim. Rejected: not a KO, rerun once with the rejection reasons, same verifier model;
   rejected again → `parked` "unverifiable". **BLOCKED** (proof cannot run here) is not
   a KO: give it the means (project checks on that hash) or `waiting` with what is missing.
2. **OK** → `verified`, queued for integration. **KO** → its findings go back to the **same**
   builder as one bounded correction (`SendMessage` / `followup_task` / a rerun in place).
3. Second KO → a fresh builder (Codex: another model; mixed: Claude), all findings, a different
   hypothesis. Third KO on the unit, whatever the findings: send `orchestratore:diagnostician`
   (Codex: a sub-agent with its body; a model no builder used) with the brief, the three
   verdicts and each hash, then `parked` with its DIAGNOSIS; `cause: brief` → its question goes
   under `## Questions for the user`. Free the slot, keep going. `KO` column: a new finding does
   not reset it; a review round counts one KO for each unit in the group. Dependents of a parked
   unit are parked too ("blocked by <ID>") and resume with it. A red gate never stops the run.
4. A blocker needing the user → record the question (§8); continue with units not depending on it.

Write every state change to `RUN.md` at once: header and Units table overwritten in place
(`updated:`, `next:` refreshed; never add a second header), every unit a row of that one
table, history one sentence per event under `## Log`. After each write and before each merge
run `python3 <plugin>/bin/run-check.py`: exit 1 → fix `RUN.md` first.

## 6. Integrate and merge

1. Lanes: tier 1-2 units into `orch/<run>`; tier 3 into `orch/<run>-review`, which always
   waits for the user, so tier 3 never holds back the safe ones (numbered when blocked, §4).
2. Merge verified branches into their lane in dependency order. A conflict goes back to the
   builder of the later branch as a correction; you do not resolve product code. Remove a
   unit's worktree once its branch is in its lane or it is parked, a lane's once its PR merges.
3. On each lane head a final verifier pass runs the **full gate once** (exclusive-resource
   commands one at a time), checks each unit's scope as `base...delivered hash` of that unit,
   and checks that the lane diff contains only files from the units' `write only` lists. Any
   fix after this verdict needs a new verdict on the new SHA.
4. Push and open the lane PR as soon as its wave passes the full gate: units, verdicts, gate
   output in the body. The next wave on that lane is a new PR once this one is merged.
5. Merge gate on the verified SHA of the tier 1-2 PR with `bin/merge-gate.py`, exactly as in
   [merge](references/merge.md). Exit 1 = the PR waits for the user: write the reasons in
   `RUN.md`, do not work around them; the lane is blocked (§4).
6. After a merge, the post-merge check in [merge](references/merge.md): `in production` only
   when the recorded deploy is green on the merge SHA; one bounded fix-forward on red;
   `pipeline: none` → stays `merged`. You never trigger a deploy yourself.
7. Update the project's own progress files if it has them (`ROADMAP.md`, changelog). Dispatch
   never waits for steps 4-6 on a lane that is not blocked (§4), within the two-wave cap; the
   post-merge check runs alongside.

## 7. Resume and stop

- **Resume** (after the lock in §1): `bin/run-check.py --run <page>`, the page being
  `.orchestratore/RUN.md` or the `.orchestratore/<run>/RUN.md` the user or the session hook named.
  An old-format page (several headers, no Units table) moves to `.orchestratore/log/`; a fresh
  page from the template carries over goal (from its objective, else ask the user), units and `next:`, then
  `--record-goal`. Read `goal:`, `next:`, the Units table, `git worktree list` and the
  branches: trust only what git shows. Set `status: active`, finish verifications, dispatch.
- **Stop** (user asks, context or runtime exhausted, deploy still running): let builders report,
  `status: parked`, `next:` (a deploy: its check command on that SHA), unlock (§1). Never `done`.
- **Done** only when the goal is reached: no deploy running, every unit `in production` or
  `merged` (`pipeline: none`), and `goal:` checked against them in the report. A unit still
  waiting or parked → `status: parked`, `next:` = what unblocks it; never `done`. Unlock.

## 8. Questions

Ask only about product behaviour, scope, or an action outside the authorised perimeter;
technical, reversible choices (names, layout, test shape) you decide and log under
`## Decisions`. One question at a time, the smallest that unblocks, recommended option first
(`AskUserQuestion`; Codex: a question that ends the turn). Silence is never an answer.

## 9. Report (after each merge and at the end)

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
- Builders never push, open PRs or merge; only you, through §6 (hooks stop mistakes, not malice).

## Red flags

| Thought | Reality |
|---|---|
| "I'll plan each unit first, then launch one by one" | The brief is the plan. One message, all independent units. |
| "Send it now, the builder will figure it out" | No ready check, no dispatch. A vague ticket burns turns. |
| "Wait for all builders, then review" | Verify each on arrival. |
| "The PR is stuck, start the next wave meanwhile" | Two unmerged waves per run at most, new lanes too. Unblock first. |
| "The builder says tests pass" / "same model can verify" | Only a different-model verifier's commands count. |
| "This red gate blocks the run" | It blocks one unit. Park it, continue. |
| "New finding, one more round" | Third KO: diagnose, then park. Count, don't judge. |
