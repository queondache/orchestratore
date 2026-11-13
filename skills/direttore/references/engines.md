# Engines: who builds, who checks

The user picks the engine at the start (SKILL.md §1). Record it in `RUN.md` (`engine:`) with
the models that really ran.

| Engine | Builds | Checks tier 1-2 | Checks tier 3, diagnoses | Available |
|---|---|---|---|---|
| `claude` | Claude (**sonnet**) | Claude (**opus**) | opus | Claude Code |
| `mixed` | Claude (**sonnet**) | an economical Codex model | opus | Claude Code with Codex logged in |
| `codex` | a Codex model | another, economical Codex model | the strongest Codex model | Codex; Claude Code with Codex logged in |

## The question

Ask once, before the lock. Offer only the engines available here; recommended first:
`mixed` when Codex is available (the cheapest independent check), else `claude`.

- **Claude Code:** `AskUserQuestion`, one question, one line per option saying who builds
  and who checks. Codex is available when `command -v codex` and `codex login status` both
  exit 0; otherwise offer `claude` alone and say why the other two are missing.
- **Codex:** only `codex` runs here. Say so in one line and ask the user to confirm it, or
  to relaunch from Claude Code for `claude` or `mixed`.

The request names the engine ("full Claude", "full Codex", "mixed"), or
`.orchestratore/config.toml` has `engine` set to one of the three → no question; write the
source under `## Decisions`. Everything else is a question, never a guess:

- `engine = "ask"`, no key, or an old `mode` key (0.12: its `"mixed"` meant something else);
- a configured or requested engine that is not available here;
- a resumed `RUN.md` without an `engine:` line: ask, then write the line. Never write
  `engine:` to make `run-check.py` pass.

Never fall back to another engine without asking: an engine that fails mid-run parks the run
(Failures, below).

## Configuration

Optional `.orchestratore/config.toml` (template: `<plugin>/templates/config.toml`). A missing
file or key means the default below. Model names are whatever your runtime exposes; the plugin
never hardcodes them.

```toml
[engines]
max_parallel = 0              # 0 = no cap; the runtime's slots still apply
engine = "ask"                # "ask" | "claude" | "codex" | "mixed"

[models]
claude_builder = "sonnet"
claude_verifier = "opus"      # must differ from claude_builder
codex_builder = ""            # "" = pick from the models your Codex session lists
codex_verifier = ""           # strongest model: tier 3 and diagnosis; must differ from codex_builder
codex_unit_verifier = ""      # economical model for tier 1-2 unit checks; "" = the director picks one
codex_effort = "medium"
codex_sandbox = "workspace-write"   # for codex-task.sh: read-only | workspace-write | danger-full-access
```

**Claude models.** Two only: **opus** for the complex work, **sonnet** for the rest. Run the
director session on **opus** (on another model, say so once and write it under
`## Decisions`). Builders run on sonnet. No other Claude model.

**Codex models.** With an empty key, pick by name from the models your Codex CLI offers and
write them in `RUN.md` before the first dispatch: an economical one to check tier 1-2 units,
different from every builder model of the run.
Never call `codex-task.sh verify` without `--model`: the Codex default may be the builder's
own model.

## Claude Code, engine `claude` or `mixed`: one workflow

Build and check are the runtime's job. One call for all ready units:

```text
Workflow(scriptPath="<plugin>/workflows/build-verify.js", args={
  plugin: "<plugin>", repo: "<abs path of this checkout>", base: "<base sha>",
  engine: "claude" | "mixed", context: <CONTEXT.md text>,
  units: [{ id, tier, brief: <brief text> }, ...],
  models: { builder: <claude_builder>, verifier: <claude_verifier>,
            codex_unit_verifier: <model, mixed only> } })
```

- This skill is the instruction that authorises the `Workflow` call. Your checkout must sit
  on the base head: each builder's worktree is cut from it.
- `mixed`: before the call, write one verify brief per tier 1-2 unit,
  `.orchestratore/briefs/verify/<ID>.md` = body of `<plugin>/agents/verifier.md` +
  `.orchestratore/CONTEXT.md` + the unit brief. The workflow adds `worktree: hash: base:`
  and runs `codex-task.sh --model "<codex_unit_verifier>" --effort low verify`; the verdict
  is the file `<ID>.r<n>.verify.last.md` next to it (`verdict_file` in the result). Check
  that file, not the text relayed to you.
- `claude`: the verdict comes back as text; save it to
  `.orchestratore/briefs/verify/<ID>.r<n>.verdict.md`, then check it.
- `tier` is the number 1, 2 or 3; anything else is refused before any agent starts.
- The result has one entry per unit: `state`, `built` (worktree, branch, hash), `verdicts`.
  Run `bin/verdict-check.py --verdict <file> --hash <built.hash>` on the last verdict of
  each unit before acting on it. By `state`:
  - `verified` → §4; `second KO` → the diagnostician, parked; `blocked` → give it the means
    and check again (single call below), or park;
  - `unverified` (the check returned nothing) → one verifier call on `built.hash`;
  - `correction missing` (KO, then no usable correction) → one builder call in
    `built.worktree` with the findings, then a verifier call; a KO there is the second KO;
  - `not delivered`, `failed` → one more workflow call with those units alone; the same
    result again → `parked` with the reason.
- A session that ends mid-workflow loses the batch in flight, not the run: on resume the
  worktrees and branches that exist are checked (the single calls below), the rest is rebuilt.

**Single calls** (a verdict rerun, a conflict after the check, the diagnostician, a resume):

```text
Agent(subagent_type="direttore:verifier", model=<claude_verifier>,
      prompt="worktree: <path>  hash: <sha>  base: <unit base sha>\n" + <CONTEXT.md>
             + <brief content>)
Agent(subagent_type="direttore:builder", model=<claude_builder>,
      prompt="workdir: <worktree>\n" + <CONTEXT.md> + <brief content> + <what to do>)
Agent(subagent_type="direttore:diagnostician", model=<claude_verifier>,
      prompt=<CONTEXT.md> + <brief content> + <the two verdicts> + <each attempt's hash>)
```

The diagnostician gets `CONTEXT.md`, the brief, the two verdicts and each attempt's hash on
every runtime. If the plugin agents are not available, use `general-purpose` and paste the
body of `<plugin>/agents/builder.md` or `verifier.md` at the top of the prompt.

## Worktrees you create

The workflow makes its own. Create one yourself only for the `codex` engine:

```bash
git worktree add -b orch-unit/<run>/<ID> .orchestratore/worktrees/<ID> <base-sha>
```

Remove a unit's worktree with `git worktree remove` as soon as its branch is merged or the
unit is parked, whoever created it: the branch keeps the commits, the disk gets its space
back. Before each batch, `git worktree prune`. Creating worktrees and committing need write
access to `.git`: if your sandbox denies it, stop at §1 and tell the user (Codex: relaunch
with a sandbox that allows git writes, e.g. `--sandbox danger-full-access` in a trusted repo).

## Codex, engine `codex`: native sub-agents

The session allows a fixed number of active agents including you (commonly 4, so 3
sub-agents; `list_agents` shows the live ones). Sub-agents share your directory, so create
the worktree first and put it in the message:

```text
spawn_agent(task_name="<ID>", fork_turns="none", model=<codex_builder>,
            reasoning_effort=<codex_effort>,
            message=<body of <plugin>/agents/builder.md> + "workdir: <abs worktree path>\n"
                    + <CONTEXT.md> + <brief content>)
```

`fork_turns="none"` is required for the model and effort overrides to apply; this skill is the
instruction that authorises the override. The sub-agent does not inherit your context: the
repository rules reach it through `CONTEXT.md` in the message. Issue the `spawn_agent` calls
back to back, `wait_agent`, and as each builder reports spawn its verifier the same way with
`<plugin>/agents/verifier.md` + `worktree: hash: base:` + `CONTEXT.md` + the brief:
`model=<codex_unit_verifier>` for tier 1-2, `model=<codex_verifier>` for tier 3. A correction
goes back with `followup_task(target=<ID>, message=<findings>)`. If a builder could not commit
(sandbox), commit its worktree yourself before the check. At the second KO the diagnostician
is spawned the same way with `<plugin>/agents/diagnostician.md`, `CONTEXT.md`, the brief, the
two verdicts and each attempt's hash, on a model none of the unit's builders used.

More ready units than slots: one Codex process per unit.

```bash
printf '%s\n' U-1 U-2 U-3 U-4 U-5 | xargs -P <free> -I{} \
  bash <plugin>/bin/codex-task.sh --model "<codex_builder>" --sandbox <codex_sandbox> \
  build .orchestratore/worktrees/{} .orchestratore/briefs/{}.md
```

## Claude Code, engine `codex`: Codex processes

1. **Preflight:** `command -v codex` and `codex login status` both exit 0 (else the engine
   was not offered).
2. **Brief file:** `.orchestratore/briefs/codex/<ID>.md` = body of `<plugin>/agents/builder.md`
   + `workdir: <abs worktree path>` + `.orchestratore/CONTEXT.md` + the unit brief. Brief
   commands must work offline under `workspace-write`; if they cannot, say so in the brief or
   set `codex_sandbox = "danger-full-access"` in a trusted repo.
3. **Build:** one Bash call per unit, all in **one message**, each with
   `run_in_background: true`, so each unit reports on its own:

   ```bash
   bash <plugin>/bin/codex-task.sh --model "<codex_builder>" --effort <codex_effort> \
     --sandbox <codex_sandbox> build .orchestratore/worktrees/<ID> .orchestratore/briefs/codex/<ID>.md
   ```

4. **Result:** read the `<ID> hash=` and `<ID> model=` lines. Write the `model=` value in the
   builder column: it is the model that ran, not the one requested. Exit 65 (dirty worktree)
   → inspect; the unit's own leftovers after a failure → rerun with `--resume`.
5. **Check**, the moment a unit reports, on a Codex model different from its `model=`:

   ```bash
   bash <plugin>/bin/codex-task.sh --model "<codex_unit_verifier>" --effort low \
     verify <worktree> .orchestratore/briefs/verify/<ID>.md
   ```

   The verify brief = body of `<plugin>/agents/verifier.md` + `worktree: <path>  hash: <sha>
   base: <unit base sha>` + `.orchestratore/CONTEXT.md` + the unit brief; tier 3:
   `--model "<codex_verifier>"`. Its verdict is `<ID>.verify.last.md` (a verify run that
   changes tracked files exits 3).
6. **KO:** a new `codex-task.sh build` on the same worktree with
   `.orchestratore/briefs/codex-fix1/<ID>.md` = the builder body + `workdir:` + `CONTEXT.md` +
   the brief + the findings. Second KO → the diagnostician on `<codex_verifier>`.

## Failures

Quota, authentication or credit errors on a model: retry the unit once, keeping builder and
verifier different (Claude Code: the same model in a fresh agent, never a third model; Codex:
another model of the session). Still failing, or Codex unavailable (exit 69): mark the engine
`unavailable` in `RUN.md`, `status: parked`, and ask the user whether to go on with another
engine. Do not retry a model that failed for credit or quota until the user says it is
restored, and never raise a budget.
