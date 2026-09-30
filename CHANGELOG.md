# Changelog

## 0.9.2 — 2026-09-30

### Added
- `agents/diagnostician.md`: at a unit's third KO, before it is parked, a fresh read-only
  agent on a model none of its builders used reads the brief, the three verdicts and each
  attempt's hash and returns a fixed `DIAGNOSIS`: `cause: code | test | brief | environment`,
  up to three pieces of evidence, the pattern the three KOs share, one proposal and at most
  one question. The unit is parked with the diagnosis as its evidence; `cause: brief` puts the
  question under `## Questions for the user`. No fourth build attempt. Claude Code, Codex and
  mixed paths documented.

## 0.9.1 — 2026-09-30

Ideas adopted (no code copied) from VerifyAgentHQ/verify-agent (Apache-2.0: evidence
provenance, deterministic policy separate from evidence) and agtktID/skill-verify (MIT: a
blocked verdict distinct from failure).

### Added
- `bin/verdict-check.py`: deterministic acceptance of a verdict. Full 40-hex hash equal to
  the delivered one; result OK, KO or BLOCKED; every command with `→ exit <n>` and a
  provenance tag `[ran]`, `[ci <ref>]` or `[reused <what>]`; OK only with every exit 0, only
  `ran`/`ci` evidence, no scope violation, no findings. JSON, exit 0/1/2. The coordinator acts
  only on an accepted verdict; exit code and tag must close the command line, and a text with
  two verdicts or duplicate `result:`/`hash:` lines is rejected.
- `[ran expect-fail]`: a run that must fail (the FIX oracle with the fix undone); OK needs it
  non-zero. Tolerant where unambiguous: bulleted commands under `commands:`, words between
  the exit code and the tag, notes after the tag, `exit non-zero`. Tested on six verdicts
  written by real verifier agents (fixtures in `tests/fixtures/verdicts/`).
- Verdict result `BLOCKED` with a `blocked:` line: the proof cannot run here (missing
  database, service, memory, credentials). Not a KO, does not count against the unit; the
  coordinator provides the means (the project's checks on the exact hash) or sets `waiting`.

## 0.9.0 — 2026-09-30

Brings back "Claude Code coordinates, Codex builds" (default design up to 0.6, dropped in
0.7 for speed and portability) on top of the 0.7 engine, without the controller.

### Added
- Mixed mode (`[engines] mode = "mixed"` or on request, Claude Code coordinator only): Codex
  builds each unit through `bin/codex-task.sh` in a worktree, Claude verifies with
  `orchestratore:verifier`. Preflight `codex login status`; one background Bash call per
  unit so each result is verified on arrival; second KO switches to a Claude builder; Codex
  unavailable → Claude builders, no silent retry.
- `bin/codex-task.sh` prints `<id> model=<name>`: the model from this run's Codex header
  (`unknown` if absent), recorded as proof of which model ran.

## 0.8.1 — 2026-09-30

### Added
- `bin/run-check.py`: deterministic check of `RUN.md` (one title and one `goal:` / `status:`
  / `updated:` / `next:` line, goal unchanged against `goal.lock`, status value, KO column
  0-3 with a unit at 3 parked, `## Log` last with at most 100 entries). JSON output, exit
  0/1/2; `--record-goal` at start and after a resume migration (output `goal_recorded`). Run after every `RUN.md` write and before every merge.
- The session hook prints up to three `RUN.md check:` problems.
- Resume migrates an old-format `RUN.md` to `.orchestratore/log/<date>-RUN.md` and starts a
  fresh page carrying goal, units and `next:`.

## 0.8.0 — 2026-09-30

Keeps long runs on target. Found in two real 0.7.0 runs: the run page became an append-only
diary whose header went stale, review rounds on grouped units never reached the park rule,
and new waves kept stacking on one unmerged PR with a red gate.

### Changed
- `RUN.md` is a page, not a diary: new `goal:` field (the user's request, changed only by
  the user); header and Units table are overwritten in place, never a second header; history
  is one plain sentence per event under `## Log`, moved to `.orchestratore/log/` past 100 lines.
- KO cap per unit: the third KO parks the unit whatever the findings. New `KO` column; a new
  finding does not reset it; a review round on a group of units counts for each unit.
- Merge cadence: the lane PR opens as soon as its wave passes the full gate, one PR per wave.
  New units never go onto a lane whose full gate is red or whose PR waits for the user:
  dependents wait, independent units start a new lane from the base. When the user excludes
  merges, the coordinator says so once and keeps one PR per wave.
- Session hook also prints `goal:`; resume reads `goal:`, `next:` and the Units table first.

## 0.7.0 — 2026-09-26

Rewrite focused on speed and portability. **Breaking**; see "Upgrading from 0.6.x" in the
README.

### Added
- `brief` skill: FIX / BUILD / CHECK classification, one-owner-per-file splitting and a fixed
  brief format so agents start editing without re-planning. Usable on its own.
- Runs entirely in Claude Code (`Agent` sub-agents in worktrees) or entirely in Codex
  (native `spawn_agent` sub-agents, plus `bin/codex-task.sh` for waves larger than the slot
  limit).
- Tier 3 units integrate into a separate PR that waits for the user.
- `bin/merge-gate.py`: deterministic merge decision (tier, allowlist, sensitive paths
  including rename sources, every changed file via pagination, required checks from branch
  protection and rulesets, exact head SHA) with `--merge` via `gh pr merge
  --match-head-commit`; merge-queue aware; fail-closed when the config cannot be parsed.
- Post-merge check: a unit is `in production` only when the recorded deploy is green on its
  merge SHA; one bounded fix-forward on red; without a deploy pipeline it stays `merged`.
- MIT license; everything in English; tests for portability (no personal paths or names).

### Changed
- Verification happens on each delivery as it arrives; one full-gate pass on the integrated SHA.
- The pre-merge LLM agent is replaced by the merge gate script.
- Builder and verifier agents: `builder` (sonnet) and `verifier` (opus, read-only).

### Removed
- SQLite controller, lease and dispatch CLI, per-task strategy stage, review pool,
  global heavy-process lock, `spawn-cc.sh` / `spawn-cx.sh`, guard hooks, credit/weight commands,
  `orchestra-status` command, hardcoded model names, cross-runtime delegation.
