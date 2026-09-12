# Project adapter

Use this reference when starting the orchestrator in a new repository or resuming it in a
later session.

## New repository

1. Discover and read instruction files from the workspace hierarchy.
2. Locate the product contract, roadmap, progress log and test commands. If they do not
   exist, create only the smallest project-local equivalents the user requested.
3. Initialize and persist the compute profile if the project does not have one.
4. Capture read-only Git state and external worktrees before assigning files.
5. Create one persistent task plan with task ID, milestone, status, owner, dependencies,
   write paths, result, contract, tests, compute-profile reference, workload class, any
   justified target override, completion and reason.
6. Validate the plan before spawning workers. If no validator exists, validate ownership,
   dependency cycles, active-milestone count and worker capacity directly.

Do not copy domain rules from the project that supplied this skill. The target repository's
instructions and product decisions always prevail.

## Resumed repository

1. Read the latest checkpoint and inspect current Git/worktree state.
2. List live agents using the session tool; reconcile that list with the persisted plan.
3. Initialize the compute profile only if it is absent; otherwise reuse it.
4. Compare the saved base revision and dirty-state fingerprint before any write.
5. Close verifiable deliveries and pending reviews before opening new fronts.
6. Reconfirm a runner only when it is unavailable or the workload class changes.
7. Continue from the recorded next action; do not repeat completed reconnaissance.

## Default statuses

- `queued`: dependencies incomplete.
- `ready`: dependencies complete, no worker started.
- `running`: an implementation or analysis worker is active.
- `review`: author stopped; independent reviewer active.
- `done`: contract verified with observed evidence.
- `blocked`: a named external condition prevents progress.
- `external`: owned by another lane or session and must not be duplicated.

Adapt status names to an existing project plan instead of introducing a second vocabulary.

## Provider and service choices

Treat hosting, database, storage, email and payment providers as architecture decisions.
Before changing one, compare the current product constraints, data region, DPA, networking,
backup/restore, operational burden, existing subscriptions and exit cost. An unused paid
subscription is evidence to investigate, not sufficient reason to move production.

Provider comparison is read-only. Login, provisioning, DNS, deployments, purchases and
secret rotation each require the authority applicable to that project.
