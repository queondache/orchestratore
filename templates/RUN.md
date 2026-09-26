# Orchestratore run — <project>

status: active | parked | done
updated: <ISO 8601>
run: <run id, e.g. 20260926-1030>
base: <branch>@<sha>
integration: orch/<run>
mode: claude | codex | mixed
builder: <engine/model>        verifier: <engine/model, different>
gate: build=<cmd|none> test=<cmd|none> lint=<cmd|none>
exclusive: <commands that need a shared resource, run one at a time | none>
git: commit+push+PR automatic | read-only        auto-merge: merge-gate | off
next: <one action>

## Units

| ID | class | tier | write only | builder | state | hash | verdict |
|---|---|---|---|---|---|---|---|
| <ID> | FIX/BUILD/CHECK | 1-3 | <paths> | <engine/model> | queued/building/verifying/verified/merged/waiting/parked | <sha> | <OK/KO + verifier model> |

States: queued → building → verifying → verified → merged | waiting (PR needs the user) |
parked (evidence + resume condition below).

## Decisions

<!-- technical, reversible choices made without asking: ID, choice, where it applies -->

## Questions for the user

<!-- ID, question, recommended answer, units blocked, status -->

## Log

<!-- KO findings per unit and attempt, engine failures, parked units with resume condition -->
