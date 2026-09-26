# SPEC — orchestratore 0.7

## Problem

Observed in real 0.6 runs: one milestone took 35 minutes of strictly serial agent processes
(strategy → build → review, repeated after each KO) with zero parallelism; a multi-day run
produced 150+ tasks and an unreadable state file. Causes: a planning stage per task, cold
processes per stage, an upfront file-disjointness proof that serialized shared files, a global
lock on test suites, a small review pool, and a protocol so heavy the coordinator spent its
time on paperwork. The plugin also depended on one user's machine, language and Codex setup.

## Goal

From "here is the work" to verified, merged or PR-ready changes as fast as the work's real
independence allows, on Claude Code alone, on Codex alone, or on both.

Success measures: time to first edit, time to first verified delivery, idle time waiting for
review, rework rounds, interruptions of the user.

## Invariants

| # | Invariant |
|---|---|
| I1 | Builder and verifier run on different models; the builder's report is never proof. |
| I2 | A unit advances only on a verdict with hash, commands and exit codes. |
| I3 | A FIX has a regression test that fails on the base. |
| I4 | One file has one owner per wave. |
| I5 | Auto-merge only through `bin/merge-gate.py`: tier 1-2, every path in the allowlist, no sensitive path, required checks green on the exact SHA. |
| I6 | A red gate parks one unit; it never stops the run. |
| I7 | Questions to the user only for product, scope or out-of-perimeter actions. |
| I8 | No force-push, destructive reset, new credentials or budget increases. |

## Non-goals

- A custom scheduler or persistent database: the runtimes' agent tools dispatch; `RUN.md`
  and git hold the state.
- A security sandbox against hostile agents.
