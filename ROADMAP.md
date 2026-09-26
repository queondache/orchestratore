# ROADMAP — orchestratore

Releases up to 0.6.0 (Italian protocol, SQLite controller) are tagged `v0.4.1`…`v0.6.0`.

| ID | Milestone | Status | Evidence |
|---|---|---|---|
| R07-1 | Portability: MIT, English, no personal paths, Claude-only default | DONE | `tests/check-structure.sh` hygiene checks |
| R07-2 | `brief` skill: FIX/BUILD/CHECK, one owner per file, fixed brief | DONE | `skills/brief/SKILL.md` |
| R07-3 | Coordinator on native engines: claude, codex, mixed | DONE | `skills/orchestratore/`, `bin/codex-task.sh`, `tests/test_codex_task.py` |
| R07-4 | Deterministic merge gate | DONE | `bin/merge-gate.py`, `tests/test_merge_gate.py` |
| R07-5 | Measure a real run against the 0.6 baseline (time to first edit, to verified delivery) | OPEN | — |
