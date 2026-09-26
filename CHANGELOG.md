# Changelog

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
