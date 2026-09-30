# Orchestratore run — <project>

<!-- The header and the Units table are the current state: overwrite them in place.
     Never add a second header or a new block on top. History goes only under ## Log. -->

goal: <the user's request in one sentence; set at start, changed only by the user>
status: active | parked | done
updated: <ISO 8601>
run: <run id, e.g. 20260926-1030>
base: <branch>@<sha>
integration: orch/<run> (tier 1-2)   orch/<run>-review (tier 3)
runtime: claude | codex | mixed (Claude Code coordinator, Codex builders)
builder: <model>        verifier: <model, different>
gate: build=<cmd|none> test=<cmd|none> lint=<cmd|none>
pipeline: <post-merge deploy found at start | none>   check: <read-only command, e.g. gh run list --commit <sha> --workflow <deploy>>
exclusive: <commands that need a shared resource, run one at a time | none>
git: commit+push+PR automatic | read-only        auto-merge: merge-gate | off
next: <the true next action, rewritten on every state change>

## Units

| ID | class | tier | write only | base | builder | state | hash | verdict | KO |
|---|---|---|---|---|---|---|---|---|---|
| <ID> | FIX/BUILD/CHECK | 1-3 | <paths> | <sha> | <model> | queued/building/verifying/verified/merged/in production/waiting/parked | <sha> | <OK/KO + verifier model> | <0-3; 3 = parked> |

States: queued (note "blocked by PR #n" while its dependencies sit on a blocked lane) → building → verifying → verified → merged → in production (deploy green on
its merge SHA or a later one containing it; with `pipeline: none` the unit stays merged) | waiting (PR needs the user) | parked (evidence + resume
condition below).

## Decisions

<!-- technical, reversible choices made without asking: ID, choice, where it applies -->

## Questions for the user

<!-- ID, question, recommended answer, units blocked, status -->

## Log

<!-- Append only, oldest first. One plain sentence per event: time, unit, what happened,
     short SHA. KO findings per attempt, engine failures, parked units with resume condition.
     Past 100 lines, move it to .orchestratore/log/<date>.md and leave the link here. -->
