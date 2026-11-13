# direttore

A director for **unattended runs** in **Claude Code** and **Codex** (formerly
*orchestratore*). The runtime's own orchestration builds; direttore adds what it lacks: a
check of every delivery by a different model, a deterministic merge gate, and a run page
that survives the session.

Use it when nobody is watching and the work merges on its own (an overnight run, a long
batch on a production app). With you present on a small batch, the runtime alone is faster:
on five small units it took 3.5 minutes against 9 with the previous version of this plugin,
same result.

## What it does

| Step | What happens |
|---|---|
| Ask the engine | One question at start: `claude` (Claude builds, Claude checks), `codex` (Codex builds, Codex checks) or `mixed` (Claude builds, Codex checks). Named in the request or in the config → no question. |
| Describe the units | One run context shared by every agent and one brief per unit (FIX, BUILD or CHECK): the expected behaviour with its source, the files it owns, the proof required. Two units writing one file run one after the other. |
| Build and check | The runtime does it. In Claude Code one workflow (`workflows/build-verify.js`) builds every ready unit in its own worktree and has a different model check each delivery on arrival: hash, scope, commands, the full gate and a class-specific proof (for a FIX: the new test must fail without the fix). A KO goes back to the builder once. In Codex: native sub-agents. |
| Accept only proven verdicts | `bin/verdict-check.py` accepts a verdict only if its facts support it: exact hash, exit codes, each proof tagged as run now, from CI on that hash, or reused (never enough for OK). A proof that cannot run is `BLOCKED`, not a failure. |
| Diagnose before giving up | After a unit's second failed check, a fresh read-only agent says whether the cause is the code, the test, the request or the environment, with one proposal; the unit is parked, the run goes on. |
| Merge through the gate | Each verified unit gets its own PR. `bin/merge-gate.py` merges tier 1-2 changes that touch no sensitive path (schema, auth, payments, tenancy, personal data, secrets, permissions), with required CI checks green on the exact verified SHA. Everything else waits for you. Then one final gate on the base head. |
| Keep the run on one page | `bin/run-check.py` checks after every write that `RUN.md` is still one page: one header, the recorded goal unchanged, at most 2 KO per unit. A new session resumes from it and from git. |

## Install

Claude Code:

```text
/plugin marketplace add queondache/orchestratore
/plugin install direttore@direttore
```

Codex: add the marketplace in `.agents/plugins/marketplace.json` of this repository, or clone
the repository and point Codex at `./skills/`.

Requirements: `git`, `python3` (3.9+; a `.orchestratore/config.toml` needs 3.11+ or the
`tomli` package), `gh` (authenticated) for PRs and merges. In Codex,
a sandbox that allows git writes (worktrees and commits).

## Use

Claude Code: `/direttore:dirigi start fix issues #12 #15 #19 mixed` — or ask for an
"unattended run" on a list. Codex: "Use direttore for an unattended run on these bugs: …".
Without an engine in the request, it asks.

Other subcommands: `status`, `resume`, `stop`. The run state lives in
`.orchestratore/RUN.md` (excluded from git automatically).

## Configure

Optional `.orchestratore/config.toml`; see [templates/config.toml](templates/config.toml).
The main keys:

- `[engines] engine` — `"ask"` (default), `"claude"`, `"codex"` or `"mixed"`; `max_parallel` —
  optional cap on concurrent agents, default 0 = the runtime's own limit.
- `[models]` — builder and verifier model per runtime (they must differ).
  In Claude Code only two models: opus for the complex work (director, tier 3 checks,
  diagnostician), sonnet builds. With engine `mixed`, tier 1-2 units are checked by an
  economical Codex model (`codex_unit_verifier`); with `claude`, by opus. Start the director
  session on opus.
- `[merge] auto_merge_globs` — the paths allowed to auto-merge. **Default `["**"]`:
  everything outside the sensitive paths, on tier 1-2 with required checks green (a private repository on a free plan: the final full gate on that SHA plus every check on the PR).** `[]`
  turns auto-merge off. `sensitive_globs` adds to the built-in list (schema, migrations,
  auth, login, payments, tenancy, personal/health data, secrets, permissions, deletion).

## Engine notes

- **Claude Code, `claude` or `mixed`:** one `Workflow` call per batch of ready units; the
  builders are `direttore:builder` agents in their own worktrees, the verifier is read-only.
- **Codex:** native sub-agents (`spawn_agent`) up to the session's slot limit, each told to
  work in a director-made worktree; beyond that, `bin/codex-task.sh` runs one Codex
  process per unit and commits its changes.
- **Claude Code, `codex`:** one `bin/codex-task.sh` process per unit, checked by another
  Codex model.
- Tier 3 PRs always wait for you; only the units that depend on them wait too.
- Worktrees, prompts and sandboxes are guardrails against mistakes, not a security boundary
  against a hostile agent.

## Upgrading from orchestratore 0.12

The plugin is now `direttore`: uninstall `orchestratore@orchestratore`, install
`direttore@direttore`. The command is `/direttore:dirigi`. Run folders (`.orchestratore/`)
and `RUN.md` pages are unchanged, so an open run resumes; add an `engine:` line to it.
The config key is now `engine`; an old `mode` key is ignored and the director asks
(0.12 `"single"` → `engine = "claude"`, 0.12 `"mixed"`, Codex builds → `engine = "codex"`).

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
