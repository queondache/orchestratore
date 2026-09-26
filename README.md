# orchestratore

A multi-agent coordinator for **Claude Code** and **Codex**. Give it a batch of bugs, fixes,
features or roadmap milestones; it plans once, dispatches every independent unit in parallel,
verifies each delivery with a different model the moment it arrives, and merges only through a
deterministic gate.

Works all-Claude, all-Codex, or mixed (one runtime builds, the other verifies).

## Why

Most multi-agent setups are slow for the wrong reasons: a planning stage per task, one agent
at a time, reviews that wait for the whole batch, and a builder's "tests pass" taken as proof.
Orchestratore removes each of those:

| Step | What happens |
|---|---|
| Plan once | The coordinator writes one short brief per unit (FIX, BUILD or CHECK) with files, constraints and the proof required. No per-unit planning. |
| Dispatch | All independent units go out in one message, each in its own git worktree. |
| Verify on arrival | A different model checks hash, scope, commands and a class-specific proof (for a FIX: the new test must fail without the fix). |
| Correct or park | A KO goes back to the same builder once; then a new approach; then the unit is parked with evidence. The run keeps going. |
| Gate the merge | `bin/merge-gate.py` merges only tier 1-2 changes fully inside an explicit allowlist, with required CI checks green on the exact verified SHA. Everything else waits for you. |

## Install

Claude Code:

```text
/plugin marketplace add queondache/orchestratore
/plugin install orchestratore@orchestratore
```

Codex: add the marketplace in `.agents/plugins/marketplace.json` of this repository, or clone
the repository and point Codex at `./skills/`.

Requirements: `git`, `python3` (3.9+), `gh` (authenticated) for PRs and merges. Optional:
the other CLI (`codex` or `claude`) for mixed mode.

## Use

Claude Code: `/orchestratore:orchestra start fix issues #12 #15 #19` — or just ask
"orchestrate these fixes in parallel". Codex: "Use orchestratore to fix these bugs: …".

Other subcommands: `status`, `resume`, `stop`. The run state lives in
`.orchestratore/RUN.md` (excluded from git automatically).

## Configure

Optional `.orchestratore/config.toml`; see [templates/config.toml](templates/config.toml).
The main keys:

- `[engines] mode` — `auto`, `claude`, `codex`, `mixed`; `max_parallel` (default 8).
- `[models]` — builder and verifier model per runtime (they must differ).
- `[merge] auto_merge_globs` — the paths allowed to auto-merge. **Empty by default: nothing
  auto-merges until you list paths.** `sensitive_globs` adds to the built-in list (schema,
  migrations, auth, payments, tenancy, personal/health data, secrets, permissions, deletion).

## Engine notes

- **Claude Code:** builders are `Agent` sub-agents with `isolation: "worktree"`; the
  verifier agent is read-only.
- **Codex:** native sub-agents (`spawn_agent`) up to the session's slot limit, each told to
  work in a coordinator-made worktree; beyond that, `bin/codex-task.sh` runs one Codex
  process per unit (`xargs -P` for the whole wave) and commits its changes.
- Worktrees, prompts and sandboxes are guardrails against mistakes, not a security boundary
  against a hostile agent.

## Upgrading from 0.6.x

0.7.0 is a rewrite. The SQLite controller, the Italian-language protocol and the
`spawn-cc.sh` / `spawn-cx.sh` bridges are gone.

- Finish or stop any 0.6 run before upgrading; 0.7 does not read the 0.6 database.
- To keep 0.6, install from the tag `v0.6.0`.
- `/orchestra peso` and `/orchestra credito` no longer exist: models go in
  `[models]`, and an engine that runs out of credit is marked unavailable for the run.

## Development

```bash
bash tests/check-structure.sh
python3 -m unittest discover -s tests
```

CI runs both on every pull request.

## License

MIT — see [LICENSE](LICENSE).
