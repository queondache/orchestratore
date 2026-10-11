# Engines: dispatching builders and verifiers

By default the run stays on the runtime that hosts the coordinator: Claude Code sub-agents in
Claude Code, Codex sub-agents in Codex. **Mixed mode** (Claude Code coordinator, Codex
builders, verifiers as in "Who verifies") is described below. Record the runtime and both models in `RUN.md`.

## Configuration

Optional `.orchestratore/config.toml` (template: `<plugin>/templates/config.toml`). A missing
file or key means the default below. Model names are whatever your runtime exposes; the plugin
never hardcodes them.

```toml
[engines]
max_parallel = 0              # 0 = no cap; the runtime's slots still apply
mode = "single"               # "mixed": Claude Code coordinates, Codex builds

[models]
claude_builder = "sonnet"
claude_verifier = "opus"      # must differ from claude_builder
codex_builder = ""            # "" = pick from the models your Codex session lists
codex_verifier = ""           # strongest model: tier 3 and final lane pass; must differ from codex_builder
codex_unit_verifier = ""      # economical model for tier 1-2 unit checks; "" = the coordinator picks one
codex_effort = "medium"
codex_sandbox = "workspace-write"   # for codex-task.sh: read-only | workspace-write | danger-full-access
```

In Codex with empty model keys, pick two different models from your session's list and write
both in `RUN.md` before the first dispatch.

**Claude models.** Two only: **opus** for the complex work, **sonnet** for the rest. Run the
coordinator session on **opus** (`/model opus` before `/orchestra start`; on another model, say
so once and write it under `## Decisions`). Builders run on sonnet. No other Claude model.

**Who verifies.** Unit verification (tier 1-2) is the cheap part: an economical Codex model
(`codex_unit_verifier`, low effort), in every runtime, different from the unit's builder
model. Opus (Codex runtime: the strongest listed model) only for tier 3 units, the final pass
on each lane head and the diagnostician. Codex CLI not installed or not logged in → unit
verification falls back to opus; write it under `## Decisions`. With `codex_unit_verifier`
empty, pick an economical model by name from the models your Codex CLI offers, different from
every builder model of the run (a builder's `model=` included), and write it in `RUN.md`
before the first check. Never call `codex-task.sh verify` without `--model`: the Codex default
may be the builder's own model.

**Unit verify command** (Claude Code and mixed: one background Bash call per delivered unit):

```bash
bash <plugin>/bin/codex-task.sh --model "<codex_unit_verifier>" --effort low \
  verify <worktree> .orchestratore/briefs/verify/<ID>.md
```

The verify brief = body of `<plugin>/agents/verifier.md` + `worktree: <path>  hash: <sha>
base: <unit base sha>` + `.orchestratore/CONTEXT.md` + the unit brief. Its verdict is
`.orchestratore/briefs/verify/<ID>.verify.last.md`; pass it to `bin/verdict-check.py
--verdict <file> --hash <sha>` like every verdict.

## Worktrees

Every builder writes in its own worktree on its own branch, created from the unit's base
(the run base, or the integration head that contains the unit's dependencies):

```bash
git worktree add -b orch-unit/<run>/<ID> .orchestratore/worktrees/<ID> <base-sha>
```

Unit branches live under `orch-unit/`, never below the lane name: git cannot hold both
`orch/<run>` (the lane) and a branch inside `orch/<run>/`.

Remove a unit's worktree with `git worktree remove` as soon as its branch is merged into its
lane or the unit is parked, and the lane's worktree once its PR is merged: the branch keeps
the commits, the disk gets its space back. Before
each wave, `git worktree prune` and remove any leftover `.orchestratore/worktrees/*` whose
unit is no longer building or verifying.
Creating worktrees and committing need write access to `.git`: if your sandbox denies it,
stop at §1 and tell the user (Codex: relaunch with a sandbox that allows git writes, e.g.
`--sandbox danger-full-access` in a trusted repo).

## Claude Code

Builders, all in **one message**, `run_in_background: true`:

```text
Agent(subagent_type="orchestratore:builder", model=<claude_builder>,
      isolation="worktree", description="<ID>", prompt=<CONTEXT.md> + <brief content>)
```

`isolation: "worktree"` creates the worktree from the current checkout, so use it only for
the first wave. For later waves create the worktree yourself from the lane head (above) and
pass `workdir: <path>` in the prompt without `isolation`; never check out branches in the
user's own checkout. The builder reports worktree, branch and hash.

Verifier, the moment a builder reports: the unit verify command above for tier 1-2; for
tier 3, a final lane pass, or Codex unavailable:

```text
Agent(subagent_type="orchestratore:verifier", model=<claude_verifier>,
      prompt="worktree: <path>  hash: <sha>  base: <unit base sha>\n" + <CONTEXT.md>
             + <brief content>)
```

A correction goes back to the same builder with `SendMessage` to its agent ID. The second KO
goes to a fresh sonnet builder (new agent: `CONTEXT.md`, the brief, all findings, a different
hypothesis); the verifier
stays as above. If the plugin
agents are not available, use `general-purpose` and paste the body of
`<plugin>/agents/builder.md` or `verifier.md` at the top of the prompt.

## Codex

**Native sub-agents** (`multi_agent`). The session allows a fixed number of active agents
including you (commonly 4, so 3 sub-agents; `list_agents` shows the live ones). Sub-agents
share your directory, so create the worktree first and put it in the message:

```text
spawn_agent(task_name="<ID>", fork_turns="none", model=<codex_builder>,
            reasoning_effort=<codex_effort>,
            message=<body of <plugin>/agents/builder.md> + "workdir: <abs worktree path>\n"
                    + <CONTEXT.md> + <brief content>)
```

`fork_turns="none"` is required for the model and effort overrides to apply and keeps the
sub-agent's context clean; this skill is the instruction that authorises the override. Since
the sub-agent does not inherit your context, the repository rules reach it through
`CONTEXT.md` in the message; the brief holds only the unit's own limits (`do not touch`).
Issue the `spawn_agent` calls back to back, then wait
with `wait_agent` and handle
whichever agent reports first; send a correction with
`followup_task(target=<ID>, message=<findings>)`. A model change needs a new sub-agent:
`followup_task` keeps the old model. Verifiers are spawned the same way with
`<plugin>/agents/verifier.md`: `model=<codex_unit_verifier>` (economical, not the builder's)
for tier 1-2 units, `model=<codex_verifier>` (the strongest) for tier 3 and the final lane
pass. If a builder could not commit
(sandbox), commit its worktree yourself before verifying. At a unit's third KO the
diagnostician is spawned the same way with `<plugin>/agents/diagnostician.md`, `CONTEXT.md`,
the brief, the three verdicts and each attempt's hash, on a model none of the unit's builders used.

**Waves larger than the slot limit**: run each unit as its own Codex process. One line
dispatches them in parallel and prints `<ID> hash=<sha>` as each finishes:

```bash
printf '%s\n' U-1 U-2 U-3 U-4 U-5 | xargs -P <free> -I{} \
  bash <plugin>/bin/codex-task.sh --model "<codex_builder>" --sandbox <codex_sandbox> \
  build .orchestratore/worktrees/{} .orchestratore/briefs/{}.md
```

`<free>` is the free slots (the runtime's limit, or `max_parallel` when set) minus the
builders and verifiers already running, keeping one for verification. The script refuses a dirty worktree, commits the builder's changes itself and never pushes.
After a failed run, retry the same unit with `--resume` so its own leftover changes are kept.
Verify each delivered hash with a sub-agent as above, or with `codex-task.sh --model
<codex_unit_verifier> verify <worktree> <verify-brief.md>` (tier 3 and the final lane pass:
`<codex_verifier>`), where the brief file holds
`agents/verifier.md`, the hash, `CONTEXT.md` and the unit brief (a verify run that changes tracked files
exits 3). Its verdict is `<ID>.verify.last.md`: pass it to `bin/verdict-check.py --verdict
<file> --hash <hash>` before acting on it, like every verdict. These processes need the Codex CLI logged in; they share the session's credit.

## Mixed: Claude Code coordinates, Codex builds

Use it when `mode = "mixed"` or the user asks for Codex builders, only with a Claude Code
coordinator. Tier 1-2 checks run on another Codex model; tier 3 and the final lane pass on opus.

1. **Preflight (§1):** `command -v codex` and `codex login status` both exit 0. Otherwise
   write under `## Decisions` "mixed unavailable: <reason>" and run single-runtime.
2. **Worktrees:** create each one yourself (section Worktrees above); no `isolation`.
3. **Brief file:** `.orchestratore/briefs/codex/<ID>.md` (the file name is the unit ID the script
   prints: `<ID> hash=`) = body of `<plugin>/agents/builder.md`
   + `workdir: <abs worktree path>` + `.orchestratore/CONTEXT.md` + the unit brief. Brief commands must work offline under
   `workspace-write` (no network); if they cannot, say so in the brief or set
   `codex_sandbox = "danger-full-access"` in a trusted repo.
4. **Dispatch:** one Bash call per unit, all in **one message**, each with
   `run_in_background: true`, so each unit reports on its own and is verified on arrival:

   ```bash
   bash <plugin>/bin/codex-task.sh --model "<codex_builder>" --effort <codex_effort> \
     --sandbox <codex_sandbox> build .orchestratore/worktrees/<ID> .orchestratore/briefs/codex/<ID>.md
   ```

   Never one `xargs -P` line here: it reports only when the whole wave ends.
5. **Result:** read the `<ID> hash=` and `<ID> model=` lines. Write the `model=` value in the
   builder column: it is the model that ran, not the one requested. `model=unknown` → log it.
   Exit 65 (dirty worktree) → inspect; the unit's own leftovers after a failure → rerun with
   `--resume`.
6. **Verify:** the unit verify command (Who verifies, above) on a Codex model different from
   the builder's `model=`; tier 3 and the final lane pass: `Agent(orchestratore:verifier,
   model=<claude_verifier>)`. Then `bin/verdict-check.py --hash <hash>` on the verdict.
7. **KO:** first KO → a new `codex-task.sh build` on the same worktree with
   `.orchestratore/briefs/codex-fix1/<ID>.md` = the builder body + `workdir:` + `CONTEXT.md` +
   the brief + the verifier's findings.
   Second KO → new approach on the
   other runtime: `Agent(orchestratore:builder, model=<claude_builder>)` on the same worktree
   with `CONTEXT.md`, the brief and all findings (the verifier stays a model different from
   it). Third KO → `Agent(orchestratore:diagnostician, model=<claude_verifier>)` with
   `CONTEXT.md`, the brief, the three
   verdicts and each attempt's hash, then parked with its DIAGNOSIS (SKILL.md §5).
8. **Codex unavailable** (exit 69, quota, auth or credit): mark it `unavailable` in `RUN.md`,
   send its queued and correction work to Claude builders, and do not call Codex again until
   the user says it is restored.

## Failures

Quota, authentication or credit errors on a model: retry the unit once, keeping builder and
verifier different. Claude Code: the same model in a fresh agent, never a third model. Codex:
another model of the session. Mixed mode: Mixed step 8. Runtime exhausted: `status: parked`,
report, stop. Do not retry a model that failed for credit or quota until the user says it is
restored.
