---
name: orchestratore
description: Coordinate multi-agent software delivery across sessions and projects with explicit task contracts, bounded or quality-gated unattended execution, independent review, context governance, model routing, and preserved authorization boundaries. Use when the user asks for an orchestrator, subagents, milestone execution, overnight development, or a reusable multi-agent development system.
---

# Delivery Orchestrator

Turn a product objective into verified deliveries. The plan is persistent state, not a
background service; use the session's real agent tools to start and govern workers.

## Start safely

1. Read the applicable repository instructions before planning or delegating.
2. Inspect working-tree changes, branch and worktrees. Preserve work that is not yours.
3. Read the current product contract, roadmap and progress evidence. Recent verified
   evidence may supersede historical status; it never silently changes product decisions.
4. Identify available toolchain, test environment, agent capacity and external lanes.
5. Separate missing product decisions from executable engineering work. Follow the
   project's decision log and escalation rules. If none exist, ask once; continue
   independent work unless every safe path is blocked.

For a new repository or a resumed session, read
[the project adapter](references/project-adapter.md).

## Autonomy contract

Before a multi-milestone or unattended run, turn the user's natural-language request into
an explicit autonomy contract and persist it in the project's existing plan:

```text
Run mode: milestone-budget | while-quality-high
Milestone budget: <positive integer, or not applicable>
Open-question ceiling: <positive integer>
Additional stop conditions: <observable conditions>
Unattended: yes | no
Context policy: checkpoint target 50%; hard ceiling 70% (or lower user/project limits)
```

In `milestone-budget` mode, stop after the requested number of milestones become verified
and ready for integration. Partial or blocked work does not count as a completed milestone.
In `while-quality-high` mode, there is no milestone-count target: continue only while every
quality gate below passes. Never interpret a request for autonomous work as permission to
complete the whole roadmap unless the user explicitly says so.

The quality gate passes only when the current slice has an unambiguous contract, ready
dependencies and test environment, focused verification, independent review with no
unresolved high-impact finding, and no open decision that can change the implementation or
acceptance criteria. Two failed approaches to the same gate, repeated inconclusive review,
or unverifiable behavior means quality is no longer high: checkpoint and stop instead of
burning the unattended window on retries.

Maintain separate counts for all open questions and questions that block named tasks. Before
opening each milestone, run a question-debt gate. Question debt is toxic when any unanswered
question from earlier work changes the next milestone's contract, architecture, security,
data model, user behavior, test oracle or definition of done; when a prior milestone would
need to be called verified by assumption; or when the configured open-question ceiling is
reached. Finish only a safe in-flight checkpoint, persist the questions with their impact,
and stop assigning new work. Questions isolated from the next slice may be reported and
bypassed without lowering the quality gate.

## Roles and model routing

- **Strategic tier:** strongest available reasoning model. It owns strategy, task
  contracts, shared files, dependency decisions, integration and final verification.
- **High-risk tier:** strong reasoning/coding model for security, data-model,
  authorization, concurrency and independent review.
- **Implementation tier:** general coding model for bounded backend or frontend work.
  When project instructions require an installed UI skill, apply it. Otherwise follow the
  approved design system; do not invent or install a missing skill without authorization.
- **Mechanical tier:** fastest suitable model for deterministic inventories and test work.

Escalate only when the task exposes ambiguity, two failed approaches, reviewer disagreement
or high-impact risk. If the runtime cannot select models, adjust reasoning effort and task
size instead. Read [runtime bridges](references/runtime-bridges.md) for current mappings.

Use at most six concurrent workers, excluding the orchestrator and including reviewers.
The effective worker cap is the lower of six and the runtime's available worker capacity;
when the runtime reports a total-agent limit, account for the orchestrator and any other
agents consuming those slots. Respect lower user, project or resource limits and record
the effective cap in the persistent plan. Never assume this skill increases runtime capacity.

Keep at most three milestones in development, review or verification combined. These are
ceilings, not utilization targets: the orchestrator chooses the actual concurrency. Open
parallel work only when contracts are frozen, dependencies are already satisfied, write
ownership does not overlap, and verification resources are ready. Milestones that depend
on one another's unfinished output must remain sequential. Do not fill slots without
independent critical-path work; shared-file integration and constrained resources remain
serialized.

An author never reviews their own code. As soon as a delivery is ready, assign an available
independent worker to review before opening more implementation work. If all workers are
busy, give review priority at the next eligible worker's safe checkpoint; do not interrupt
atomic work or bypass review to keep implementation slots occupied.

## Skill routing

In Codex, start with ADHD, this orchestrator, and OpenAI Docs only. Follow
[activation on demand](references/skill-activation.md): search the local Codex catalog's
metadata when a concrete need appears, ask Andrea before loading an optional skill, and
load only that skill after approval. Keep locally loaded instructions scoped to this
session; they do not enable plugin tools or change global defaults. An explicit instruction
to use a named skill already supplies the corresponding approval. Preserve separate
authorization for external operations and never infer consent from silence.

The Codex catalog and runtime availability are distinct. Do not use the Claude Code
snapshot to infer that Codex has a tool. In Claude Code, the canonical snapshot remains
`~/Dev/skills/cc-installed-plugins.md`, refreshed by Andrea with `/plugins-snapshot`.
Record the applicable catalog date in the existing plan; do not rescan all directories or
reload the entire catalog after each milestone.

A skill required by the user or repository remains required for the task it covers. If it
is optional in the Codex startup set, obtain activation approval before starting that part;
continue independent work while waiting. Follow the approved skill's workflow and pass its
name, exact local path, granted scope, and requirements to any assigned worker. Do not
promise native invocation or tool access merely because its cached files exist.

Skill availability never expands the user's requested scope, filesystem boundary or
authorization. Do not invent, install or modify a missing skill unless the user explicitly
requests or authorizes that separate action. If a relevant skill is unavailable, use the
best built-in workflow and record the limitation only when it affects acceptance criteria.

## Unit of delegation

Register each task in the project's existing plan before starting a worker. Include:

```text
Task and milestone:
Observable user result:
Completed dependencies and frozen contract:
Writable files:
Shared files for orchestrator integration:
Allowed verification and environment:
Required available skills and why:
Resource budget and execution location:
Compute-profile reference and workload class (`cpu-ram`, `gpu-capable`, or `gpu-required`):
Target override and reason, if different from the saved profile:
Completion criteria:
Open decisions and stop conditions:
Next checkpoint:
```

One owner per file. Only the orchestrator writes task state, the persistent plan and the
handoff. Give implementation workers isolated, complete bases when they write
in parallel. The orchestrator serializes shared files, database integration and external
state. Pass the repository's filesystem boundary in every assignment. Workers do not
delegate unless the project explicitly permits it.

## Visibility gate

Keep the user informed without turning coordination into a stream of activity logs. Publish
a concise visibility update:

- after initial reconnaissance and task assignment;
- whenever a delivery changes state or before opening another work front;
- immediately when a new question blocks a task or requires user authority;
- during a long-running turn, at least every 10 minutes even if the state is unchanged.

Each update must say:

```text
In progress: <current result, owner and present phase; run mode and milestone budget>
Verified since last update: <observable evidence, or "nothing new">
Questions: <open total / configured ceiling; blocking IDs, tasks and decision owner, or "none">
Context: <reported percentage, compactions and current action>
Next checkpoint: <next observable gate>
```

## Milestone celebration

Whenever a milestone becomes verified and closed, end that milestone's user-facing update
with one animated GIF from GIPHY, then the exact sentence `una milestone meno`, then this
three-line recap:

```markdown
<linked GIPHY GIF>

una milestone meno

🟢 <completed count> milestone completate
🟡 <user-blocked count> milestone bloccate da Andrea
🔴 <remaining count> milestone mancanti per finire
```

Alternate these exact Markdown images so consecutive milestone celebrations are not
identical; do not replace the image with a plain link or emoji:

- Dolphin jumping:
  `[![Delfino che salta](https://media.giphy.com/media/AhV2lfKBfEvcEqj6h3/giphy.gif)](https://giphy.com/gifs/guitarjamz-dolphin-jump-surfing-drone-shot-AhV2lfKBfEvcEqj6h3)`
- Whale spouting:
  `[![Balena che sbuffa](https://media.giphy.com/media/Q6rD2TLgqMiHf4a0Pt/giphy.gif)](https://giphy.com/gifs/whale-whales-savethewhales-Q6rD2TLgqMiHf4a0Pt)`

Make each image clickable to its GIPHY page. Count a milestone as completed only after the
normal verification and closure gates pass. `User-blocked` means it cannot advance without
Andrea's decision, input or authorization; technical and external blockers do not enter the
yellow count. `Remaining` is the accepted plan's total minus completed milestones, so it
includes user-blocked milestones until they are completed. Recompute all three counts from
the persistent plan at the time of the update; never infer them from the conversation. If
the plan has no finite milestone total yet, establish and persist that total before closing
the first milestone.

Only list questions that prevent a named task, verification or authorized action from
advancing. Keep non-blocking decisions in the project decision log rather than presenting
them as blockers. When one lane is blocked, report it and continue independent work within
the concurrency limit. When every safe path is blocked, surface the smallest decision the
user must make and stop assigning new work. Do not repeat an unchanged question unless its
impact changes or the user asks for a recap.

## Context governor

Treat 50% of each root or worker thread's context window as the checkpoint target and 70%
as the hard ceiling. This reserve lets an atomic delivery reach a safe checkpoint without a
quality-damaging compaction in the middle. Use lower project or user limits when present.

- Before unattended work, obtain the active context-window size and current usage from the
  runtime. If either is unavailable, do not claim compliance with the ceiling and do not run
  unattended; write a handoff and stop.
- At 50%, mark compaction pending and open no new task or milestone. Finish only the current
  atomic implementation, review or verification step, then persist the contract, question
  ledger, exact diff, evidence, owners and next action.
- At the first safe checkpoint after 50%, compact before continuing, preferably before 60%.
  Never interrupt an atomic edit, migration, test or review solely to hit the target.
- Configure automatic compaction near 65% when the runtime supports it. This is an emergency
  guard against crossing 70%, so it may compact mid-step only when no safe checkpoint was
  reached in the reserve window.
- After compaction, verify usage is below 50%, reload only the minimal persistent state and
  validate the saved filesystem fingerprint before continuing.
- If compaction is unavailable, fails, or does not restore the required headroom, end worker
  turns, write a complete handoff and stop the session. A fresh session may continue only
  when the runtime or supervising harness can start it from that handoff.
- At or above 70%, make no new implementation, test, delegation or external-action call.
  Preserve state with the smallest safe handoff and stop.

Keep bulk logs, inventories and test output in authorized files; pass digests and exact paths
through the conversation. Close finished worker threads and accept concise, evidence-based
deliveries rather than full transcripts. Runtime-native compaction is the default. A context
skill such as Caveman or CCO may assist only when already installed, reviewed for the active
runtime and compatible with the same ceiling; it is never a required dependency and never
replaces the persistent handoff.

Compaction may continue the same session. Clearing starts a different chat and is not assumed
to be callable by a skill during active work. Never promise automatic session rollover unless
the active runtime or supervising harness exposes and verifies that capability.

## Delivery loop

1. Choose the smallest slice that produces an observable result or closes a required gate.
2. Start only tasks whose dependencies and environment are ready.
3. At the checkpoint, collect exact diff, commands, observed results and residual limits.
4. Freeze author writes, then assign independent review against the contract and diff.
5. The orchestrator reads the diff and reruns risk-proportionate verification.
6. Mark separately: implemented, verified, ready to integrate, integrated and closed.

Do not run a broad suite when a focused gate proves the changed behavior, unless project
instructions require the broad gate. Database suites and external resources are serialized.

## Token-efficiency policy

Optimize for verified acceptance criteria per token, not activity or lines changed.

- Reuse current evidence and source maps. Read changed or doubtful areas, not every file.
- Pass a concise contract, relevant invariants, exact paths or sections and a declared
  base. Do not paste whole documents or make every worker repeat the same reconnaissance.
- Parallelize independent critical-path work, not overlapping exploration.
- Prefer deterministic tools for inventories, diffs and validation.
- End a worker turn at a concrete checkpoint: delivery, review finding or named blocker.
- Measure token/cost only when the harness exposes it. Never infer it from task size.
- Escalate model strength after a concrete trigger: high-risk decision, ambiguous contract,
  two failed approaches, or reviewer disagreement. De-escalate mechanical follow-up work.

If output grows without closing an acceptance criterion, narrow the slice, reuse an existing
artifact, or change the test path. Do not weaken the product contract to save tokens.

## Resource-load policy

Initialize one persistent compute profile when the skill is first used in a new or existing
project. Do not repeat this inventory for every task. Record:

1. Local machine and accelerator, with whether local heavy compute is allowed.
2. Dedicated remote CPU runners and GPUs that are actually reachable and authorized.
3. The GPU target for model/application inference, or `provider-managed-unknown` when a
   hosted API does not expose its hardware.
4. Default targets for `cpu-ram`, `gpu-capable`, and `gpu-required` workloads.
5. Fallback policy, expected local load and concurrency cap.

If no suitable external GPU exists for a GPU-capable or GPU-required workload, propose a
suitable option with region and cost boundary; do not provision it. Re-run discovery only
when the saved runner becomes unavailable, the workload needs a different accelerator, or
the user changes the resource policy.

Default to `external-first`: run model inference on the remote model provider and keep the
local machine to reading, editing, diffing and one lightweight validator at a time. Do not
overlap local builds, browser automation, container builds, database suites or other
CPU/RAM-heavy processes.

Send builds, tests, browsers, containers and databases to an authorized remote runner. Those
engineering tasks usually need remote CPU/RAM, not a GPU. If no remote runner is configured,
record the verification as blocked instead of silently consuming the local machine.

Remote execution does not authorize a provider, account access, uploads, secrets, spend or
deployment. Confirm the selected runner, data classification, region and cost boundary first.
Never upload production data or a dirty workspace snapshot unless explicitly authorized.

## Authorization boundary

A request to develop does not authorize commit, push, merge, deploy, schema reset, external
messages, production data access, purchases or cloud provisioning. Use read-only Git by
default. Ask immediately before a missing authorization is required. Resolve destructive
targets with read-only checks and prefer reversible operations.

Record questions in the project's existing decision log when one exists. Never turn silence
into a domain decision. After the user answers, record the exact answer and unblock only the
tasks it actually resolves.

## Session handoff

Persist the current objective, active tasks, owners, base revision plus a hash/manifest of
uncommitted changes, modified files, observed tests, blockers and one next action. Include:

```text
Autonomy contract and remaining milestone budget:
Open questions / ceiling and toxic-debt assessment:
Acceptance criteria verified:
Token input/output/total reported, or "not available":
Context window, usage percentage and compaction count:
Review rounds:
Repeated tests and reason:
Residual work:
Compute-profile reference:
Compute inventory timestamp, evidence and runner status:
```

On resume, verify live agents, the saved fingerprint and filesystem state; serialized plan
status alone does not prove a worker is running or work is complete.
