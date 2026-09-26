# Orchestratore run — <project>

status: active | parked | done
updated: <ISO 8601>
run: <run id, e.g. 20260926-1030>
base: <branch>@<sha>
integration: orch/<run> (tier 1-2)   orch/<run>-review (tier 3)
runtime: claude | codex
builder: <model>        verifier: <model, different>
gate: build=<cmd|none> test=<cmd|none> lint=<cmd|none>
exclusive: <commands that need a shared resource, run one at a time | none>
git: commit+push+PR automatic | read-only        auto-merge: merge-gate | off
next: <one action>

## Units

| ID | class | tier | write only | base | builder | state | hash | verdict |
|---|---|---|---|---|---|---|---|---|
| <ID> | FIX/BUILD/CHECK | 1-3 | <paths> | <sha> | <model> | queued/building/verifying/verified/merged/in production/waiting/parked | <sha> | <OK/KO + verifier model> |

States: queued → building → verifying → verified → merged → in production (pipeline green on
the merge SHA, or `pipeline: none`) | waiting (PR needs the user) | parked (evidence + resume
condition below).

## Decisions

<!-- technical, reversible choices made without asking: ID, choice, where it applies -->

## Questions for the user

<!-- ID, question, recommended answer, units blocked, status -->

## Log

<!-- KO findings per unit and attempt, engine failures, parked units with resume condition -->
