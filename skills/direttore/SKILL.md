---
name: direttore
description: Use when a batch of work must run unattended (overnight, long run) and enter the main branch on its own, so every delivery needs an independent check and a merge gate; when the user says "/dirigi", "direttore", "overnight run", "unattended run" or "resume the run"; in Claude Code or in Codex. Not for a small batch with the user present: there the runtime's own orchestration is enough.
---

# Direttore

You are the **director**. The runtime's own orchestration builds; you add what it lacks: a
check of every delivery by a different model, a gate that decides what merges without the
user, and a run page that survives the session. You never write product code and you never
re-implement dispatch. `<plugin>` = two directories up. See [engines](references/engines.md),
[verify](references/verify.md), [merge](references/merge.md), `brief` skill.

## 1. Start

1. Read `CLAUDE.md`, `AGENTS.md`, `README`, `SPEC.md`, `ROADMAP.md`, the named work list.
2. **Engine: ask the user, once.** `claude` (Claude builds, Claude checks), `codex` (Codex
   builds, Codex checks) or `mixed` (Claude builds, Codex checks); offer only the ones
   available here, recommended first ([engines](references/engines.md)). Skip the question
   only when the request or `.orchestratore/config.toml` names the engine. No answer → wait:
   never pick for the user. This is the only start question; unattended, commit + push + PR
   and auto-merge (§4) are never asked.
3. **Lock:** `mkdir -p .orchestratore && mkdir .orchestratore/coordinator.lock`, then write
   `coordinator.lock/owner` (`token: <random> runtime: <claude|codex> updated: <ISO>`). Lock
   exists → stop and ask the user, showing `owner`; only the user removes it, however old.
   Before every dispatch, merge or write, `owner` must hold your token; if not, stop at once
   without writing. **Unlock**, only with your token there: `python3 -c "import os; os.remove('.orchestratore/coordinator.lock/owner'); os.rmdir('.orchestratore/coordinator.lock')"`.
4. `RUN.md` active or parked → resume (§5). `git status`, `git fetch`; others' work stays
   untouched. Base = the named branch, else the default; your checkout sits on the base head.
   Add `.orchestratore/` to `$(git rev-parse --git-path info/exclude)`.
5. Gate commands (build, test, lint) from project files, `none` if missing, never invented;
   shared-resource commands (database, port, browser) in `exclusive:`. Post-merge deploy:
   `pipeline:` + read-only check ([merge](references/merge.md)), or `pipeline: none`.
6. `.orchestratore/RUN.md` from `<plugin>/templates/RUN.md`, `goal:` = the request in one
   sentence (only the user changes it); `python3 <plugin>/bin/run-check.py --record-goal`.

## 2. Units: only what the check needs

1. `.orchestratore/CONTEXT.md` (`brief` skill), shared by every agent: goal, stack, gate
   commands, repo rules.
2. One brief per unit in `.orchestratore/briefs/<ID>.md` (`brief` skill): class FIX / BUILD /
   CHECK, tier (uncertain → higher), `spec` with its source, `write only`, `proof`,
   `commands`. No source for the expected behaviour → a question (§5), never a guess.
3. Two units writing one file: the second `depends on` the first. One `RUN.md` row per unit.

## 3. Build and check: the runtime does it

**Ready** = brief written and every unit it `depends on` is merged. Hand **all ready units at
once** to the engine's own orchestration ([engines](references/engines.md)): each unit is
built in its own worktree from the base head and checked on arrival by a different model
(class proof plus full gate on that hash, [verify](references/verify.md)); a **KO** goes back
to the same builder once. You do not dispatch unit by unit and you do not watch: you wait for
the batch, then act on what came back.

- Only a verdict `bin/verdict-check.py --hash <hash>` accepts counts (rejected: one rerun on
  the same verifier model, then `parked` "unverifiable"). **BLOCKED** is not a KO: give it
  the means, or park.
- **Second KO** → `direttore:diagnostician` writes why (`cause: brief` → its question to the
  user, §5); unit and dependents `parked` ("blocked by <ID>", resume with it).
- A red gate never stops the run: the other units go on.

## 4. Merge: what passed the check, through the gate

1. **OK** → push the unit branch, open its own PR (brief, verdict, gate output). Tier 3 waits
   for the user. Tier 1-2: `bin/merge-gate.py` on the verified SHA
   ([merge](references/merge.md)); exit 1 → `waiting`, reasons in `RUN.md`, never worked
   around. A PR waiting for the user holds only its dependents.
2. Verified PRs merge one after the other without a new verdict: their files are disjoint. A
   conflict → the same builder merges the base in (never rebase), new verdict on the new SHA.
3. **Final gate**: once the batch is merged, run the gate commands yourself on the base head.
   Red → one FIX unit for it; a flaky test gets one rerun, billing/quota/infra none.
4. Post-merge check, `in production` only on a green deploy; remove merged or parked
   worktrees; update the project's `ROADMAP.md`; start the units that just became ready (§3).

After each step (batch back, PR, merge, park): overwrite the `RUN.md` header and Units table
in place, never add a second header, one sentence under `## Log`; then
`python3 <plugin>/bin/run-check.py` (exit 1 → fix `RUN.md` first).

## 5. Resume, stop, questions

**Resume** (after the lock): `bin/run-check.py --run <page>`; trust only git (worktrees,
branches, PRs), then §3 with the units not yet merged. **Stop**: `status: parked`, `next:`
set, unlock. **Done** only when every unit is `in production` or `merged` (`pipeline: none`)
and the final gate is green, checked against `goal:`.

Ask only about the engine (§1), product behaviour, scope, or actions outside the perimeter
(technical choices: decide, log under `## Decisions`): smallest question, recommended option
first, under `## Questions for the user`; keep building what does not depend on it.

## 6. Report and boundaries

After each batch and at the end: `In production / merged` · `To approve (dependencies first,
then oldest): PR #n — unit — one line` · `Parked: unit — why — what unblocks it` · `Next:`.

Never: force-push, `reset --hard`, deleting branches not yours, destructive or bulk production
data changes, new logins or secrets, raising any budget. Builders never push, open PRs or merge.
