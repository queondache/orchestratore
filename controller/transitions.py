"""Pure semantic identity and transition policy; no database or clock access.

An explicit event id identifies intent within a task and operation. Otherwise
the payload identifies completion intent; failure intent also includes its
original stage. A stored identity never includes the mutable approach/budget.
Failure signatures are a separate, stage-scoped set shared by both approaches.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any, FrozenSet, Tuple

NEXT_STAGE = {"strategy": "build", "build": "review", "review": "finalize", "finalize": "done"}
# (current approach, consumed attempts) -> (next approach, attempts, park)
FAILURE_BUDGET = {
    (1, 0): (1, 1, False),
    (1, 1): (2, 0, False),
    (2, 0): (2, 1, False),
    (2, 1): (2, 2, True),
}
SignatureKey = Tuple[str, str, str]


@dataclass(frozen=True)
class State:
    task_id: str
    stage: str
    approach: int = 1
    attempts: int = 0


@dataclass(frozen=True)
class Command:
    operation: str
    evidence: str
    signature: str = ""
    event_id: str | None = None
    stage_intent: str | None = None


@dataclass(frozen=True)
class Decision:
    identity: str
    result: str
    state: State
    signature_key: SignatureKey | None = None
    charged_attempt: int | None = None


def semantic_identity(task_id: str, command: Command) -> str:
    if command.operation not in ("complete", "fail"):
        raise ValueError("unsupported operation: %s" % command.operation)
    if command.event_id is not None:
        intent: Any = ["event-id", command.event_id]
    else:
        # Canonicalize JSON evidence so formatting/key order cannot create intent.
        try:
            evidence = ["json", json.loads(command.evidence)]
        except json.JSONDecodeError:
            evidence = ["text", command.evidence]
        intent = ["payload", evidence]
        if command.operation == "fail":
            if command.stage_intent not in NEXT_STAGE:
                raise ValueError("implicit fail requires an active stage intent")
            intent.extend([command.signature, command.stage_intent])
    encoded = json.dumps([task_id, command.operation, intent], sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "semantic-v1:" + hashlib.sha256(encoded).hexdigest()


def reduce_transition(state: State, command: Command,
                      seen_events: FrozenSet[str] = frozenset(),
                      seen_signatures: FrozenSet[SignatureKey] = frozenset()) -> Decision:
    commands = (command,)
    if command.operation == "fail" and command.event_id is None and command.stage_intent is None:
        # Capture active-stage intent once in an immutable command. Terminal
        # tasks have no new intent: only an identity recorded at an original
        # active stage can authorize replay, including the failure that parked.
        stages = (state.stage,) if state.stage in NEXT_STAGE else tuple(NEXT_STAGE)
        commands = tuple(replace(command, stage_intent=stage) for stage in stages)
    identities = tuple(semantic_identity(state.task_id, item) for item in commands)
    # Replay takes precedence over terminal-state rejection.
    for identity in identities:
        if identity in seen_events:
            return Decision(identity, "deduplicated", state)
    if state.stage not in NEXT_STAGE:
        raise ValueError("task is not active")
    identity = identities[0]
    if command.operation == "complete":
        return Decision(identity, "advanced", replace(state, stage=NEXT_STAGE[state.stage]))
    signature_key = (state.task_id, state.stage, command.signature)
    if signature_key in seen_signatures:
        return Decision(identity, "deduplicated", state)
    try:
        approach, attempts, park = FAILURE_BUDGET[(state.approach, state.attempts)]
    except KeyError as exc:
        raise ValueError("invalid failure budget state") from exc
    next_state = replace(state, stage="parked" if park else state.stage,
                         approach=approach, attempts=attempts)
    return Decision(identity, "parked" if park else "failed", next_state,
                    signature_key, state.attempts + 1)
