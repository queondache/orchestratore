# Engines: dispatching builders and verifiers

The run stays on the runtime that hosts the coordinator: Claude Code sub-agents in Claude
Code, Codex sub-agents in Codex. Record the runtime and both models in `RUN.md`.

## Configuration

Optional `.orchestratore/config.toml` (template: `<plugin>/templates/config.toml`). A missing
file or key means the default below. Model names are whatever your runtime exposes; the plugin
never hardcodes them.

```toml
[engines]
max_parallel = 8

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
printf '%s\n' U-1 U-2 U-3 U-4 U-5 | xargs -P <max_parallel> -I{} \
  bash <plugin>/bin/codex-task.sh --model "<codex_builder>" --sandbox <codex_sandbox> \
  build .orchestratore/worktrees/{} .orchestratore/briefs/{}.md
```

The script refuses a dirty worktree, commits the builder's changes itself and never pushes.
After a failed run, retry the same unit with `--resume` so its own leftover changes are kept.
Verify each delivered hash with a sub-agent as above, or with `codex-task.sh --model
<codex_verifier> verify <worktree> <verify-brief.md>`, where the brief file holds
`agents/verifier.md`, the hash and the unit brief (a verify run that changes tracked files
exits 3). These processes need the Codex CLI logged in; they share the session's credit.

## Failures

Quota, authentication or credit errors on a model: retry the unit once on another model of the
same runtime, keeping builder and verifier different. Runtime exhausted: `status: parked`,
report, stop. Do not retry a model that failed for credit or quota until the user says it is
restored.
