# SPEC — direttore 1.0 (formerly orchestratore)

## Problem

Observed in real 0.6 runs: one milestone took 35 minutes of strictly serial agent processes
(strategy → build → review, repeated after each KO) with zero parallelism; a multi-day run
produced 150+ tasks and an unreadable state file. Causes: a planning stage per task, cold
processes per stage, an upfront file-disjointness proof that serialized shared files, a global
lock on test suites, a small review pool, and a protocol so heavy the coordinator spent its
time on paperwork. The plugin also depended on one user's machine, language and Codex setup.

## Goal

From "here is the work" to verified, merged or PR-ready changes as fast as the work's real
independence allows, with the whole run in Claude Code, the whole run in Codex, or (mixed,
0.9) a Claude Code coordinator with Codex builders and Claude verifiers.

Success measures: time to first edit, time to first verified delivery, idle time waiting for
review, rework rounds, interruptions of the user.

## Invariants

| # | Invariant |
|---|---|
| I1 | Builder and verifier run on different models; the builder's report is never proof. |
| I2 | A unit advances only on a verdict with hash, commands and exit codes. |
| I3 | A FIX has a regression test that fails on the base. |
| I4 | One file has one owner at a time: a unit writing a file another open unit writes depends on it. |
| I5 | Auto-merge only through `bin/merge-gate.py`: tier 1-2, every path in the allowlist, no sensitive path, required checks green on the exact SHA. |
| I6 | A red gate parks one unit; it never stops the run. |
| I7 | Questions to the user only for product, scope or out-of-perimeter actions. |
| I8 | No force-push, destructive reset, new credentials or budget increases. |

## Non-goals

- A custom scheduler or persistent database: the runtimes' agent tools dispatch; `RUN.md`
  and git hold the state.
- A security sandbox against hostile agents.

## 1.0: direttore

The runtimes now orchestrate on their own (parallel sub-agents, worktrees, workflow scripts).
A measured run (5 small units: 3.5 minutes native, 9 minutes with 0.12.1, same score) showed
the dispatch half of this plugin had become a slower duplicate. What the runtimes still lack
is the reason to keep it: I1, I2, I3 (the check), I5 (the gate) and the run page.

- The plugin is for unattended runs that merge on their own; with the user present on a
  small batch, the runtime alone is the right tool.
- Dispatch belongs to the runtime: one workflow in Claude Code, native sub-agents in Codex.
- The user chooses the engine at start: all Claude, all Codex, or mixed (Claude builds,
  Codex checks). The director never chooses or switches it alone.
- I4 still holds, and is what lets verified PRs merge one after the other with a single
  final gate on the base head instead of a new verdict per merge.

