# Engines: how to dispatch builders and verifiers

Three modes, one protocol. Pick the mode in SKILL.md §3 and record it in `RUN.md`.

## Configuration

Optional `.orchestratore/config.toml` (template: `<plugin>/templates/config.toml`). Missing
keys use the runtime's defaults. Model names are whatever your runtime exposes today; the
plugin never hardcodes them.

```toml
[engines]
mode = "auto"          # auto | claude | codex | mixed
max_parallel = 8

[models]
claude_builder = "sonnet"
claude_verifier = "opus"      # must differ from claude_builder
codex_builder = ""            # "" = Codex default model
codex_verifier = ""           # must differ from codex_builder in codex mode
codex_effort = "medium"
codex_sandbox = "workspace-write"   # read-only | workspace-write | danger-full-access
```

`auto`: in Claude Code → `claude` (or `mixed` if `codex` is installed and `codex_builder` is
set); in Codex → `codex` (or `mixed` if `claude` is installed and `claude_verifier` is set).
In `codex` mode with empty model keys, pick two different models from the ones your Codex
session lists and write both in `RUN.md` before the first dispatch.

## Worktrees

Every builder writes in its own worktree on its own branch, created from the run base:

```bash
git worktree add -b orch/<run>/<ID> .orchestratore/worktrees/<ID> <base-sha>
```

In Claude Code `isolation: "worktree"` does this for you; the builder reports its branch
and hash. Remove worktrees with `git worktree remove` only after their branch is merged or
parked.

## Mode `claude`

Builders, all in **one message**, `run_in_background: true`:

```text
Agent(subagent_type="orchestratore:builder", model=<claude_builder>,
      isolation="worktree", description="<ID>", prompt=<brief content + gate commands>)
```

Verifier, the moment a builder reports:

```text
Agent(subagent_type="orchestratore:verifier", model=<claude_verifier>,
      prompt="worktree: <path>  hash: <sha>  base: <base-sha>\n" + <brief content>)
```

A correction goes back to the same builder with `SendMessage` to its agent ID. If the
plugin agents are not available, use `general-purpose` and paste the body of
`<plugin>/agents/builder.md` or `verifier.md` at the top of the prompt.

## Mode `codex`

**Native sub-agents** (Codex `multi_agent`): the session allows a fixed number of active
agents including you (commonly 4, so 3 workers; `list_agents` shows the current ones). Sub-agents
share your directory, so the worktree goes in the message:

```text
spawn_agent(task_name="<ID>", fork_turns="none", model=<codex_builder>,
            reasoning_effort=<codex_effort>,
            message=<body of <plugin>/agents/builder.md> + "workdir: <abs worktree path>\n"
                    + "Run every command and edit only inside workdir.\n" + <brief content>)
```

`fork_turns="none"` is required for the model and effort overrides to apply, and it keeps
the sub-agent's context clean. Wait with `wait_agent`; send a correction with
`followup_task(target=<ID>, message=<findings>)`. Verifiers are spawned the same way with
`<plugin>/agents/verifier.md` and `model=<codex_verifier>`.

**Beyond the slot limit**, run each unit as its own Codex process. One line dispatches the
whole wave in parallel and prints `<ID> hash=<sha>` per unit as each finishes:

```bash
printf '%s\n' U-1 U-2 U-3 U-4 U-5 | xargs -P 8 -I{} \
  bash <plugin>/bin/codex-task.sh --model "<codex_builder>" --sandbox <codex_sandbox> \
  build .orchestratore/worktrees/{} .orchestratore/briefs/{}.md
```

The script commits the builder's changes itself (a sandboxed Codex may not be able to write
the shared `.git`). Verify with the same script in `verify` mode and `--model
<codex_verifier>`, passing a brief file that contains the verifier instructions, the hash
and the unit brief. A verify run that changes tracked files exits 3.

## Mode `mixed`

The cheaper engine builds, the other verifies, so builder and verifier differ by runtime.

- Claude Code coordinator, Codex builds: `codex-task.sh build` per unit (background Bash or
  one `xargs -P` line); verify with `Agent(orchestratore:verifier)`.
- Codex coordinator, Claude verifies: after each `hash=`, run
  `claude -p --model <claude_verifier> --permission-mode bypassPermissions --disallowed-tools Edit Write NotebookEdit < verify-brief.md`
  from the worktree, where `verify-brief.md` holds `agents/verifier.md`, the hash and the
  unit brief. Afterwards `git status --porcelain` must be empty and HEAD unchanged;
  otherwise discard the verdict.

## Runtime failure

Exit codes 69 (not installed), quota, authentication or credit errors: mark the engine
`unavailable` in `RUN.md`, move its queued units to the other engine or mode, and keep the
builder/verifier model difference. Both engines unavailable: `status: parked`, report, stop.
Do not retry an engine that failed for credit or quota until the user says it is restored.
