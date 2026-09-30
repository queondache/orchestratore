# Engines: dispatching builders and verifiers

By default the run stays on the runtime that hosts the coordinator: Claude Code sub-agents in
Claude Code, Codex sub-agents in Codex. **Mixed mode** (Claude Code coordinator, Codex
builders, Claude verifiers) is described below. Record the runtime and both models in `RUN.md`.

## Configuration

Optional `.orchestratore/config.toml` (template: `<plugin>/templates/config.toml`). A missing
file or key means the default below. Model names are whatever your runtime exposes; the plugin
never hardcodes them.

```toml
[engines]
max_parallel = 8
mode = "single"               # "mixed": Claude Code coordinates, Codex builds, Claude verifies

[models]
claude_builder = "sonnet"
claude_verifier = "opus"      # must differ from claude_builder
codex_builder = ""            # "" = pick from the models your Codex session lists
codex_verifier = ""           # must differ from codex_builder
codex_effort = "medium"
codex_sandbox = "workspace-write"   # for codex-task.sh: read-only | workspace-write | danger-full-access
```

In Codex with empty model keys, pick two different models from your session's list and write
both in `RUN.md` before the first dispatch.

## Worktrees

Every builder writes in its own worktree on its own branch, created from the unit's base
(the run base, or the integration head that contains the unit's dependencies):

```bash
git worktree add -b orch/<run>/<ID> .orchestratore/worktrees/<ID> <base-sha>
```

Remove a worktree with `git worktree remove` only after its branch is merged or parked.
Creating worktrees and committing need write access to `.git`: if your sandbox denies it,
stop at §1 and tell the user (Codex: relaunch with a sandbox that allows git writes, e.g.
`--sandbox danger-full-access` in a trusted repo).

## Claude Code

Builders, all in **one message**, `run_in_background: true`:

```text
Agent(subagent_type="orchestratore:builder", model=<claude_builder>,
      isolation="worktree", description="<ID>", prompt=<brief content>)
```

`isolation: "worktree"` creates the worktree from the current checkout, so use it only for
the first wave. For later waves create the worktree yourself from the lane head (above) and
pass `workdir: <path>` in the prompt without `isolation`; never check out branches in the
user's own checkout. The builder reports worktree, branch and hash.

Verifier, the moment a builder reports:

```text
Agent(subagent_type="orchestratore:verifier", model=<claude_verifier>,
      prompt="worktree: <path>  hash: <sha>  base: <unit base sha>\n" + <brief content>)
```

A correction goes back to the same builder with `SendMessage` to its agent ID. If the plugin
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
                    + <brief content>)
```

`fork_turns="none"` is required for the model and effort overrides to apply and keeps the
sub-agent's context clean; this skill is the instruction that authorises the override. Since
the sub-agent does not inherit your context, put the repository rules it must follow in the
brief (`do not touch`, `read first`). Issue the `spawn_agent` calls back to back, then wait
with `wait_agent` and handle
whichever agent reports first; send a correction with
`followup_task(target=<ID>, message=<findings>)`. A model change needs a new sub-agent:
`followup_task` keeps the old model. Verifiers are spawned the same way with
`<plugin>/agents/verifier.md` and `model=<codex_verifier>`. If a builder could not commit
(sandbox), commit its worktree yourself before verifying.

**Waves larger than the slot limit**: run each unit as its own Codex process. One line
dispatches them in parallel and prints `<ID> hash=<sha>` as each finishes:

```bash
printf '%s\n' U-1 U-2 U-3 U-4 U-5 | xargs -P <free> -I{} \
  bash <plugin>/bin/codex-task.sh --model "<codex_builder>" --sandbox <codex_sandbox> \
  build .orchestratore/worktrees/{} .orchestratore/briefs/{}.md
```

`<free>` is `max_parallel` minus the builders and verifiers already running, keeping one
for verification. The script refuses a dirty worktree, commits the builder's changes itself and never pushes.
After a failed run, retry the same unit with `--resume` so its own leftover changes are kept.
Verify each delivered hash with a sub-agent as above, or with `codex-task.sh --model
<codex_verifier> verify <worktree> <verify-brief.md>`, where the brief file holds
`agents/verifier.md`, the hash and the unit brief (a verify run that changes tracked files
exits 3). These processes need the Codex CLI logged in; they share the session's credit.

## Mixed: Claude Code coordinates, Codex builds

Use it when `mode = "mixed"` or the user asks for Codex builders, only with a Claude Code
coordinator. Builder and verifier then differ by runtime, not only by model.

1. **Preflight (§1):** `command -v codex` and `codex login status` both exit 0. Otherwise
   write under `## Decisions` "mixed unavailable: <reason>" and run single-runtime.
2. **Worktrees:** create each one yourself (section Worktrees above); no `isolation`.
3. **Brief file:** `.orchestratore/briefs/codex/<ID>.md` (the file name is the unit ID the script
   prints: `<ID> hash=`) = body of `<plugin>/agents/builder.md`
   + `workdir: <abs worktree path>` + the unit brief. Brief commands must work offline under
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
6. **Verify:** `Agent(orchestratore:verifier, model=<claude_verifier>)` on the hash, as in the
   Claude Code section.
7. **KO:** first KO → a new `codex-task.sh build` on the same worktree with
   `.orchestratore/briefs/codex-fix1/<ID>.md` = the brief + the verifier's findings.
   Second KO → new approach on the
   other runtime: `Agent(orchestratore:builder, model=<claude_builder>)` on the same worktree
   with all findings (verifier stays `<claude_verifier>`, which must differ). Third KO → parked.
8. **Codex unavailable** (exit 69, quota, auth or credit): mark it `unavailable` in `RUN.md`,
   send its queued and correction work to Claude builders, and do not call Codex again until
   the user says it is restored.

## Failures

Quota, authentication or credit errors on a model: retry the unit once on another model of the
same runtime (mixed mode: Mixed step 8), keeping builder and verifier different. Runtime exhausted: `status: parked`,
report, stop. Do not retry a model that failed for credit or quota until the user says it is
restored.
