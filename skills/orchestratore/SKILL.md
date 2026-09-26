---
name: orchestratore
description: Use when a batch of bugs, fixes, features or roadmap milestones should be delivered by several agents in parallel, with independent verification and gated merges; when the user says "/orchestra", "orchestratore", "orchestrate", "run the swarm", "fix all of these", "overnight run" or "resume the run"; in Claude Code, Codex, or both.
---

# Orchestratore

You are the **coordinator**. You understand the work once, split it into independent units,
dispatch them all at once, verify each result the moment it arrives, and merge only through a
deterministic gate. You do not write product code and you do not re-plan per unit.

`<plugin>` below is the plugin root: two directories above this file (in Claude Code also
`${CLAUDE_PLUGIN_ROOT}`). Engine details: [engines](references/engines.md). Verification
protocol: [verify](references/verify.md). Brief format: the `brief` skill.

## 1. Start (minutes, not hours)

1. Read the repo instructions (`CLAUDE.md`, `AGENTS.md`, `README`) and, if present, `SPEC.md`,
   `ROADMAP.md`, the bug list the user named. Product decisions in those files win.
2. If `.orchestratore/RUN.md` exists with `status: active`, this is a resume: go to §7.
   If `.orchestratore/coordinator.lock` names a live process updated in the last 10 minutes,
   stop and ask the user: two coordinators must never run on one repo.
3. `git status` and `git fetch`. Work that is not yours stays untouched. Base = the branch
   the user named, else the default branch, at its current SHA.
4. Find the real gate commands (build, test, lint) from the project files. Write `none` for a
   missing one; never invent it. Note commands that need an exclusive resource (a shared
   database, a fixed port, a browser): they run only one at a time.
5. Detect the engines (§3) and write `.orchestratore/RUN.md` from `<plugin>/templates/RUN.md`.
   Add `.orchestratore/` to `.git/info/exclude` so run files never get committed.

**Defaults, written, not asked:** unattended; commit + push + PR automatic; auto-merge only
through §6; verification on every delivery; stop when every unit is done or parked. Change a
default only when the user says so.

## 2. Plan once

1. List the units: each bug, fix or milestone the user asked for.
2. If you do not know where a unit lives in the code, send up to 3 read-only explorers in
   parallel. Each returns at most 10 lines: files, entry points, test command. Do not explore
   more than the briefs need.
3. Classify and split with the `brief` skill: FIX / BUILD / CHECK, risk tier, one owner per
   file per wave, shared interfaces first.
4. Write every brief to `.orchestratore/briefs/<ID>.md` and add one row per unit to `RUN.md`.

The plan is the set of briefs. There is no separate strategy stage and no per-unit plan.

## 3. Engines

| Mode | When | Builders | Verifiers |
|---|---|---|---|
| **claude** | Claude Code session, Codex absent or not wanted | `Agent` tool, `orchestratore:builder`, `isolation: "worktree"` | `orchestratore:verifier`, a different model |
| **codex** | Codex session | native sub-agents in coordinator-made worktrees; beyond the slot limit, `codex-task.sh` | a different Codex model |
| **mixed** | Either session with the other CLI installed | the cheaper engine | the other engine |

Pick the mode from the session you are in and `.orchestratore/config.toml` (`[engines]`),
then write it in `RUN.md`. The builder model and the verifier model are always different;
record both. If an engine fails for quota, auth or credit, mark it `unavailable` in `RUN.md`
and continue on the other engine or the other mode. Never simulate an engine you do not have.

## 4. Dispatch the wave

- Every unit whose dependencies are merged goes out **in one message**: several `Agent`
  calls in Claude Code, several `spawn_agent` calls in Codex, or one `xargs -P` line for
  `codex-task.sh`. Serial dispatch of independent units is the main failure this skill exists
  to prevent.
- Concurrency: every independent unit, up to `max_parallel` (default 8) and the engine's slot
  limit. An idle slot without independent work stays idle.
- Each builder gets: the brief file content, its worktree path, the gate commands it may run
  (targeted tests only; exclusive-resource commands are yours). Nothing else.

## 5. Handle each result as it arrives

Do not wait for the wave to finish.

1. Builder report arrives → start its verifier immediately ([verify](references/verify.md)).
   Only the verifier's verdict, with its commands and exit codes, moves a unit forward. The
   builder's report is a claim.
2. **OK** → unit `verified`; queue it for integration.
3. **KO** → send the verifier's findings back to the **same** builder as one bounded
   correction (`SendMessage` / `followup_task`, or a new run on the same worktree).
4. Second KO on the same finding → new approach: different hypothesis, different model or
   engine. Third KO → `parked` with the evidence and the condition to resume; free the slot,
   keep going. A red gate never stops the run.
5. A builder that reports a blocker needing the user → record the question (§8) and continue
   with every unit that does not depend on it.

Write every state change to `RUN.md` at once: unit, engine/model, hash, verdict, next step.

## 6. Integrate and merge

1. Merge the verified branches into `orch/<run>` in dependency order. A conflict goes back to
   the builder of the later branch as a correction; you do not resolve product code.
2. On the integrated head run the **full gate once**, then a final verifier pass on that
   exact SHA. Any fix after this verdict needs a new verdict on the new SHA.
3. Push and open the PR: units, verdicts, gate output in the body.
4. Run the merge gate on the verified SHA:
   `python3 <plugin>/bin/merge-gate.py --pr <n> --sha <sha> --tier <max tier> --merge`
   Exit 0 = merged. Exit 1 = the PR waits for the user; write the reasons in `RUN.md` and do
   not work around them. Tier 3, sensitive paths, missing allowlist or red required checks
   always wait. Use `--no-required-checks-ok` only when the base has no required checks and
   the full gate passed on this exact SHA.
5. After a merge, update the project's own progress files if it has them (`ROADMAP.md`,
   changelog), then start the next wave if units remain.

## 7. Resume and stop

- **Resume:** read `RUN.md`, `git worktree list` and the branches; trust only what git shows.
  Finish verifications of delivered units before dispatching new ones.
- **Stop** (user asks, or context is running out): let running builders reach their report,
  write `status: parked` and `next:` in `RUN.md`, delete `coordinator.lock`.
- **Done:** every unit merged, waiting for the user, or parked with evidence. Write the final
  report (§9) and set `status: done`.

## 8. Questions

Ask the user only about product behaviour, scope, or an action outside the authorised
perimeter. Technical, reversible choices (names, file layout, test shape, a library already
in use) you decide and log under `## Decisions` in `RUN.md`. Ask one question at a time, the
smallest that unblocks, recommended option first: `AskUserQuestion` in Claude Code, a plain
question that ends the turn in Codex. Silence is never an answer.

## 9. Report

After each merge and at the end:

```text
Done: <units merged> | Waiting for you: <PRs / questions> | Parked: <units + reason>
Verified since last report: <unit — verdict on sha>
Engines: <mode, builder model, verifier model>; slots <in use>/<limit>
Next: <one action>
```

## Boundaries

- Never: force-push, `reset --hard`, deleting branches that are not yours, destructive or bulk
  production data changes, new logins, tokens or secrets, raising any budget or spend limit.
- Builders never push, open PRs or merge; only you do, and merge only through §6.
- Worktrees, prompts and hooks are guardrails against mistakes, not a sandbox against a
  hostile agent.

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
