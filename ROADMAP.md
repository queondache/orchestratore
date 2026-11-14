# ROADMAP — direttore (formerly orchestratore)

Releases up to 0.6.0 (Italian protocol, SQLite controller) are tagged `v0.4.1`…`v0.6.0`.

| ID | Milestone | Status | Evidence |
|---|---|---|---|
| R07-1 | Portability: MIT, English, no personal paths, Claude-only default | DONE | `tests/check-structure.sh` hygiene checks |
| R07-2 | `brief` skill: FIX/BUILD/CHECK, one owner per file, fixed brief | DONE | `skills/brief/SKILL.md` |
| R07-3 | Coordinator on native sub-agents: all-Claude Code or all-Codex | DONE | `skills/direttore/` (then `skills/orchestratore/`), `bin/codex-task.sh`, `tests/test_codex_task.py` |
| R07-4 | Deterministic merge gate | DONE | `bin/merge-gate.py`, `tests/test_merge_gate.py` |
| R07-5 | Measure a real run against a baseline | DONE | 2026-11-13: same 5-unit batch, native 3.5 min vs 0.12.1 9 min, both 5/5 on a hidden exam (`CHANGELOG.md` 1.0.0) |
| R07-6 | Split CHECK into intent (FIX/BUILD) × proof (test / visual / checklist) | OPEN | idea from Codex review of 0.7.0 |
| R10-1 | Direttore: runtime builds, plugin checks and gates; engine asked at start | DONE | PR #18: `skills/direttore/`, `bin/build-verify.workflow.js`, `tests/check-structure.sh` |
| R10-2 | Measure direttore against the native run on a batch with traps (wrong code behind green tests) | OPEN | — |
