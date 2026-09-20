#!/usr/bin/env python3
"""Local SQLite state machine for an external orchestrator controller.

The controller deliberately plans work; it does not invoke a provider.  A caller
may turn its JSON actions into bridge invocations, while dry-runs and tests never
consume model credit.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Iterator

if __package__:
    from .transitions import Command, Decision, State, reduce_transition
else:
    from transitions import Command, Decision, State, reduce_transition

SCHEMA_VERSION = 1
STAGES = ("strategy", "build", "review", "finalize", "done", "parked")
ACTIVE = ("strategy", "build", "review", "finalize")
ROLE_DEFAULTS = {
    "strategy": ("claude", "sonnet", "medium"),
    "build": ("codex", "gpt-5.6-terra", "medium"),
    "review": ("claude", "sonnet", "medium"),
    "finalize": ("codex", "gpt-5.6-luna", "medium"),
}
MIN_EFFORT = {
    "gpt-5.6-luna": "medium", "gpt-5.6-terra": "medium",
    "gpt-5.6-sol": "low", "gpt-6-astra": "low",
}
EFFORT_RANK = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4, "ultra": 5}


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def connect(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    return db


def initialize(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS runs (
      id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('active','paused','done')),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, config_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), title TEXT NOT NULL,
      stage TEXT NOT NULL CHECK(stage IN ('strategy','build','review','finalize','done','parked')),
      builder_count INTEGER NOT NULL DEFAULT 1 CHECK(builder_count BETWEEN 1 AND 2),
      approach INTEGER NOT NULL DEFAULT 1 CHECK(approach BETWEEN 1 AND 2),
      attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 2),
      checkpoint INTEGER NOT NULL DEFAULT 0 CHECK(checkpoint BETWEEN 0 AND 100),
      session INTEGER NOT NULL DEFAULT 1, implementation_done INTEGER NOT NULL DEFAULT 0,
      finalized INTEGER NOT NULL DEFAULT 0, owner_provider TEXT, owner_model TEXT,
      owner_effort TEXT, last_error TEXT, updated_at TEXT NOT NULL
      ,context_json TEXT NOT NULL DEFAULT '{}', evidence_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE TABLE IF NOT EXISTS leases (
      name TEXT PRIMARY KEY, holder TEXT NOT NULL, expires_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS attempts (
      id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(id),
      approach INTEGER NOT NULL, attempt INTEGER NOT NULL, stage TEXT NOT NULL,
      provider TEXT NOT NULL, model TEXT NOT NULL, effort TEXT NOT NULL,
      result TEXT NOT NULL CHECK(result IN ('planned','ok','failed','parked')),
      evidence TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id),
      task_id TEXT, kind TEXT NOT NULL, data_json TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS event_ids (
      event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), task_id TEXT,
      kind TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS failure_signatures (
      task_id TEXT NOT NULL REFERENCES tasks(id), stage TEXT NOT NULL, approach INTEGER NOT NULL,
      signature TEXT NOT NULL, PRIMARY KEY(task_id, stage, approach, signature)
    );
    INSERT OR REPLACE INTO meta(key,value) VALUES ('schema_version','1');
    """)
    # Small forward-only migration for databases made by an earlier controller.
    columns = {r[1] for r in db.execute("PRAGMA table_info(tasks)")}
    for name in ("context_json", "evidence_json"):
        if name not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN %s TEXT NOT NULL DEFAULT '{}'" % name)
    db.commit()


def event(db: sqlite3.Connection, run_id: str, kind: str, task_id: str | None = None, **data: Any) -> None:
    db.execute("INSERT INTO events(run_id,task_id,kind,data_json,created_at) VALUES (?,?,?,?,?)",
               (run_id, task_id, kind, json.dumps(data, sort_keys=True), utcnow()))


def config_for(row: sqlite3.Row) -> dict[str, Any]:
    config = json.loads(row["config_json"])
    config.setdefault("strategy_provider", "claude")
    config.setdefault("build_provider", "codex")
    config.setdefault("review_provider", "claude")
    config.setdefault("fallback_provider", "codex")
    config.setdefault("brain_model", "gpt-6-astra")
    config.setdefault("brain_effort", "medium")
    return config


def ensure_effort(model: str, effort: str) -> None:
    minimum = MIN_EFFORT.get(model)
    if minimum is None:
        raise ValueError("unsupported Codex model: %s" % model)
    if EFFORT_RANK.get(effort, -1) < EFFORT_RANK[minimum]:
        raise ValueError("%s requires effort >= %s" % (model, minimum))


def route(task: sqlite3.Row, config: dict[str, Any]) -> tuple[str, str, str]:
    stage = task["stage"]
    provider, model, effort = ROLE_DEFAULTS[stage]
    provider = str(config.get(stage + "_provider", provider))
    if provider == "codex":
        model = str(config.get(stage + "_model", model if model.startswith("gpt") else "gpt-5.6-terra"))
        effort = str(config.get(stage + "_effort", effort))
        ensure_effort(model, effort)
    elif provider == "claude":
        model = str(config.get(stage + "_model", model if not model.startswith("gpt") else "sonnet"))
        effort = str(config.get(stage + "_effort", "medium"))
    else:
        raise ValueError("provider must be codex or claude")
    return provider, model, effort


def acquire(db: sqlite3.Connection, name: str, holder: str, seconds: int) -> bool:
    now = utcnow()
    expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)).replace(microsecond=0).isoformat()
    with db:
        row = db.execute("SELECT holder,expires_at FROM leases WHERE name=?", (name,)).fetchone()
        if row and row["expires_at"] > now and row["holder"] != holder:
            return False
        db.execute("INSERT INTO leases(name,holder,expires_at) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET holder=excluded.holder, expires_at=excluded.expires_at", (name, holder, expiry))
    return True


def release(db: sqlite3.Connection, name: str, holder: str) -> bool:
    with db:
        cur = db.execute("DELETE FROM leases WHERE name=? AND holder=?", (name, holder))
    return cur.rowcount == 1


def require_lease(db: sqlite3.Connection, run_id: str, holder: str | None) -> None:
    if not holder:
        raise ValueError("mutating command requires --holder with a valid run lease")
    row = db.execute("SELECT holder,expires_at FROM leases WHERE name=?", (run_id,)).fetchone()
    if not row or row["holder"] != holder or row["expires_at"] <= utcnow():
        raise ValueError("no valid lease for run %s and holder %s" % (run_id, holder))


def plan(db: sqlite3.Connection, run_id: str, dry_run: bool) -> list[dict[str, Any]]:
    run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        raise ValueError("unknown run: %s" % run_id)
    if run["status"] != "active":
        return []
    config = config_for(run)
    rows = db.execute("SELECT * FROM tasks WHERE run_id=? AND stage IN ('strategy','build','review','finalize') ORDER BY updated_at,id", (run_id,)).fetchall()
    planned: list[dict[str, Any]] = []
    builder_slots = 0
    for task in rows:
        # Finalization is never skipped: it explicitly gates PR/merge/docs.
        # Corrupt/legacy state can contain more than two build tasks.  Dispatch
        # only the first fitting tasks instead of letting an overfull sum starve all.
        if task["stage"] == "build":
            if builder_slots + task["builder_count"] > 2:
                continue
            builder_slots += task["builder_count"]
        if task["checkpoint"] >= 70:
            action = {"task": task["id"], "action": "rollover", "session": task["session"] + 1,
                      "reason": "checkpoint >= 70; start a fresh session"}
        elif task["checkpoint"] >= 50:
            action = {"task": task["id"], "action": "checkpoint", "reason": "checkpoint >= 50"}
        else:
            provider, model, effort = route(task, config)
            action = {"task": task["id"], "action": task["stage"], "provider": provider,
                      "model": model, "effort": effort, "fallback": config["fallback_provider"]}
        planned.append(action)
        if not dry_run:
            now = utcnow()
            db.execute("UPDATE tasks SET owner_provider=?,owner_model=?,owner_effort=?,updated_at=? WHERE id=?",
                       (action.get("provider"), action.get("model"), action.get("effort"), now, task["id"]))
            if action["action"] == "rollover":
                db.execute("UPDATE tasks SET session=session+1,checkpoint=0,updated_at=? WHERE id=?", (now, task["id"]))
            event(db, run_id, "planned", task["id"], **action)
    if not dry_run:
        db.commit()
    return planned


def final_evidence(evidence: str) -> dict[str, Any]:
    try:
        value = json.loads(evidence)
    except json.JSONDecodeError as exc:
        raise ValueError("finalize evidence must be JSON with pr, merge, and docs") from exc
    if not isinstance(value, dict):
        raise ValueError("finalize evidence must be an object")
    if value.get("pr") not in ("created", "open", "merged", "approved-wait"):
        raise ValueError("finalize pr must be created, open, merged, or approved-wait")
    if value.get("merge") not in ("merged", "approved-wait"):
        raise ValueError("finalize merge must be merged or approved-wait")
    if value.get("docs") is not True:
        raise ValueError("finalize docs must be aligned=true")
    return value


def transition_for(db: sqlite3.Connection, task: sqlite3.Row, command: Command) -> Decision:
    """Read durable history, then delegate all replay/budget policy to the reducer."""
    seen_events = frozenset(row[0] for row in db.execute(
        "SELECT event_id FROM event_ids WHERE task_id=? AND kind=?",
        (task["id"], command.operation)))
    seen_signatures = frozenset(tuple(row) for row in db.execute(
        "SELECT task_id,stage,signature FROM failure_signatures WHERE task_id=? AND stage=?",
        (task["id"], task["stage"])))
    return reduce_transition(State(task["id"], task["stage"], task["approach"], task["attempts"]),
                             command, seen_events, seen_signatures)


def remember_event(db: sqlite3.Connection, task: sqlite3.Row, operation: str, identity: str) -> None:
    db.execute("INSERT OR IGNORE INTO event_ids(event_id,run_id,task_id,kind,created_at) VALUES(?,?,?,?,?)",
               (identity, task["run_id"], task["id"], operation, utcnow()))


def complete(db: sqlite3.Connection, task_id: str, evidence: str, event_id: str | None) -> str:
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        raise ValueError("unknown task: %s" % task_id)
    decision = transition_for(db, task, Command("complete", evidence, event_id=event_id))
    if decision.result == "deduplicated":
        return decision.result
    if task["stage"] == "strategy":
        active_builders = db.execute("SELECT COALESCE(SUM(builder_count),0) FROM tasks WHERE run_id=? AND stage='build'", (task["run_id"],)).fetchone()[0]
        if active_builders + task["builder_count"] > 2:
            raise ValueError("max two active builders; complete a build first")
    evidence_value: Any = final_evidence(evidence) if task["stage"] == "finalize" else evidence
    stored = json.loads(task["evidence_json"])
    nxt = decision.state.stage
    implementation_done = 1 if task["stage"] == "build" else task["implementation_done"]
    finalized = 1 if task["stage"] == "finalize" else task["finalized"]
    with db:
        remember_event(db, task, "complete", decision.identity)
        db.execute("INSERT INTO attempts(task_id,approach,attempt,stage,provider,model,effort,result,evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (task_id, task["approach"], task["attempts"], task["stage"], task["owner_provider"] or "unknown", task["owner_model"] or "unknown", task["owner_effort"] or "unknown", "ok", evidence, utcnow()))
        stored[task["stage"]] = evidence_value
        db.execute("UPDATE tasks SET stage=?,implementation_done=?,finalized=?,checkpoint=0,evidence_json=?,updated_at=? WHERE id=?",
                   (nxt, implementation_done, finalized, json.dumps(stored, sort_keys=True), utcnow(), task_id))
        event(db, task["run_id"], "completed", task_id, stage=task["stage"], next_stage=nxt, evidence=evidence)
    return decision.result


def fail(db: sqlite3.Connection, task_id: str, signature: str, evidence: str, event_id: str | None) -> str:
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        raise ValueError("unknown task: %s" % task_id)
    decision = transition_for(db, task, Command("fail", evidence, signature, event_id))
    if decision.result == "deduplicated":
        with db:
            # A newly seen event can share an existing signature. Remember it
            # too, so its replay remains valid after the task becomes terminal.
            remember_event(db, task, "fail", decision.identity)
        return "deduplicated"
    attempts = decision.state.attempts
    approach = decision.state.approach
    stage = decision.state.stage
    status = decision.result
    with db:
        remember_event(db, task, "fail", decision.identity)
        db.execute("INSERT INTO failure_signatures(task_id,stage,approach,signature) VALUES(?,?,?,?)", (task_id, task["stage"], task["approach"], signature))
        db.execute("INSERT INTO attempts(task_id,approach,attempt,stage,provider,model,effort,result,evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (task_id, task["approach"], decision.charged_attempt, task["stage"], task["owner_provider"] or "unknown", task["owner_model"] or "unknown", task["owner_effort"] or "unknown", status, evidence, utcnow()))
        db.execute("UPDATE tasks SET stage=?,approach=?,attempts=?,last_error=?,updated_at=? WHERE id=?",
                   (stage, approach, attempts, signature, utcnow(), task_id))
        event(db, task["run_id"], status, task_id, signature=signature, approach=approach, attempts=attempts, evidence=evidence)
    return status


def print_json(value: Any) -> None:
    print(json.dumps(value, sort_keys=True, indent=2, default=dict))


def recovery(db: sqlite3.Connection, task: sqlite3.Row) -> dict[str, str | None]:
    """A-E recovery classification is derived from durable evidence, never RAM.

    D and E both mean "review is proven, finalize is not done", split by whether
    finalize was ever actually attempted: an `attempts` row with stage='finalize'
    only exists after a real `fail` call, not after a `complete` rejected for
    incomplete evidence (that raises before writing anything).
    """
    evidence = json.loads(task["evidence_json"])
    for phase, case in (("strategy", "A"), ("build", "B"), ("review", "C")):
        if phase not in evidence:
            return {"recovery_case": case, "first_missing_evidence": phase}
    if "finalize" not in evidence:
        attempted = db.execute(
            "SELECT 1 FROM attempts WHERE task_id=? AND stage='finalize' LIMIT 1", (task["id"],)
        ).fetchone()
        return {"recovery_case": "E" if attempted else "D", "first_missing_evidence": "finalize"}
    return {"recovery_case": None, "first_missing_evidence": None}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=".orchestratore/controller.sqlite3", help="SQLite state path")
    subs = p.add_subparsers(dest="command", required=True)
    subs.add_parser("init")
    start = subs.add_parser("start"); start.add_argument("run_id"); start.add_argument("--config", default="{}"); start.add_argument("--holder", required=True); start.add_argument("--seconds", type=int, default=60)
    add = subs.add_parser("add-task"); add.add_argument("run_id"); add.add_argument("task_id"); add.add_argument("title"); add.add_argument("--builders", type=int, default=1); add.add_argument("--holder", required=True)
    schedule = subs.add_parser("schedule"); schedule.add_argument("run_id"); schedule.add_argument("--dry-run", action="store_true"); schedule.add_argument("--holder")
    done = subs.add_parser("complete"); done.add_argument("task_id"); done.add_argument("--evidence", required=True); done.add_argument("--event-id"); done.add_argument("--holder")
    bad = subs.add_parser("fail"); bad.add_argument("task_id"); bad.add_argument("signature"); bad.add_argument("--evidence", required=True); bad.add_argument("--event-id"); bad.add_argument("--holder")
    checkpoint = subs.add_parser("checkpoint"); checkpoint.add_argument("task_id"); checkpoint.add_argument("percent", type=int); checkpoint.add_argument("--summary", default=""); checkpoint.add_argument("--head", default=""); checkpoint.add_argument("--fingerprint", default=""); checkpoint.add_argument("--holder")
    status = subs.add_parser("status"); status.add_argument("run_id")
    lock = subs.add_parser("acquire"); lock.add_argument("name"); lock.add_argument("holder"); lock.add_argument("--seconds", type=int, default=60)
    unlock = subs.add_parser("release"); unlock.add_argument("name"); unlock.add_argument("holder")
    dispatch = subs.add_parser("dispatch"); dispatch.add_argument("run_id"); dispatch.add_argument("--dry-run", action="store_true"); dispatch.add_argument("--execute", action="store_true"); dispatch.add_argument("--cwd"); dispatch.add_argument("--prompt-file"); dispatch.add_argument("--holder")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    db = connect(args.db); initialize(db)
    try:
        if args.command == "init": print_json({"db": args.db, "schema_version": SCHEMA_VERSION})
        elif args.command == "start":
            config = json.loads(args.config); ensure_effort(config.get("brain_model", "gpt-6-astra"), config.get("brain_effort", "medium"))
            if config.get("brain_model", "gpt-6-astra") != "gpt-6-astra" or config.get("brain_effort", "medium") != "medium":
                raise ValueError("brain must use gpt-6-astra at medium effort")
            if config.get("strategy_provider", "claude") != "claude":
                raise ValueError("strategy_provider must be claude")
            if config.get("build_provider", "codex") != "codex":
                raise ValueError("build_provider must be codex")
            if config.get("review_provider", "claude") != "claude":
                raise ValueError("review_provider must be claude")
            # Run row and its lease are created in one transaction: a run must
            # never exist without an authoritative holder, even for one instant.
            now = utcnow()
            expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=args.seconds)).replace(microsecond=0).isoformat()
            with db:
                existing = db.execute("SELECT holder,expires_at FROM leases WHERE name=?", (args.run_id,)).fetchone()
                if existing and existing["expires_at"] > now and existing["holder"] != args.holder:
                    raise ValueError("run lease %s held by another holder" % args.run_id)
                db.execute("INSERT INTO runs VALUES(?,?,?,?,?)", (args.run_id, "active", utcnow(), utcnow(), json.dumps(config)))
                db.execute("INSERT INTO leases(name,holder,expires_at) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET holder=excluded.holder, expires_at=excluded.expires_at", (args.run_id, args.holder, expiry))
            print_json({"run": args.run_id, "status": "active", "lease_holder": args.holder, "lease_expires_at": expiry})
        elif args.command == "add-task":
            if args.builders not in (1, 2): raise ValueError("builders must be 1 or 2")
            require_lease(db, args.run_id, args.holder)
            with db: db.execute("INSERT INTO tasks(id,run_id,title,stage,builder_count,updated_at) VALUES(?,?,?,?,?,?)", (args.task_id,args.run_id,args.title,"strategy",args.builders,utcnow()))
            print_json({"task": args.task_id, "stage": "strategy"})
        elif args.command == "schedule":
            if not args.dry_run: require_lease(db, args.run_id, args.holder)
            print_json({"dry_run": args.dry_run, "actions": plan(db, args.run_id, args.dry_run)})
        elif args.command == "complete":
            task = db.execute("SELECT run_id,stage FROM tasks WHERE id=?", (args.task_id,)).fetchone()
            if not task: raise ValueError("unknown task: %s" % args.task_id)
            require_lease(db, task["run_id"], args.holder)
            print_json({"task":args.task_id,"result":complete(db,args.task_id,args.evidence,args.event_id)})
        elif args.command == "fail":
            task = db.execute("SELECT run_id,stage,approach FROM tasks WHERE id=?", (args.task_id,)).fetchone()
            if not task: raise ValueError("unknown task: %s" % args.task_id)
            require_lease(db, task["run_id"], args.holder)
            print_json({"task":args.task_id,"result":fail(db,args.task_id,args.signature,args.evidence,args.event_id)})
        elif args.command == "checkpoint":
            if not 0 <= args.percent <= 100: raise ValueError("checkpoint must be 0..100")
            task = db.execute("SELECT stage,session FROM tasks WHERE id=?", (args.task_id,)).fetchone()
            if not task: raise ValueError("unknown task: %s" % args.task_id)
            require_lease(db, db.execute("SELECT run_id FROM tasks WHERE id=?", (args.task_id,)).fetchone()["run_id"], args.holder)
            payload = {"summary": args.summary, "stage": task["stage"], "head": args.head, "fingerprint": args.fingerprint, "session": task["session"]}
            with db: db.execute("UPDATE tasks SET checkpoint=?,context_json=?,updated_at=? WHERE id=?",(args.percent,json.dumps(payload,sort_keys=True),utcnow(),args.task_id))
            print_json({"task":args.task_id,"checkpoint":args.percent,"context":payload})
        elif args.command == "status":
            run=db.execute("SELECT * FROM runs WHERE id=?",(args.run_id,)).fetchone();
            if not run: raise ValueError("unknown run: %s" % args.run_id)
            tasks = []
            for row in db.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY id", (args.run_id,)):
                item = dict(row); item.update(recovery(db, row)); tasks.append(item)
            print_json({"run":dict(run),"tasks":tasks,"events":[dict(x) for x in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY id",(args.run_id,))]})
        elif args.command == "acquire": print_json({"acquired":acquire(db,args.name,args.holder,args.seconds)})
        elif args.command == "release": print_json({"released":release(db,args.name,args.holder)})
        elif args.command == "dispatch":
            if not args.dry_run: require_lease(db, args.run_id, args.holder)
            actions = plan(db, args.run_id, args.dry_run)
            root = Path(__file__).resolve().parents[1]
            commands = []
            for action in actions:
                if action["action"] in ("checkpoint", "rollover"):
                    continue
                bridge = root / "bin" / ("spawn-cx.sh" if action["provider"] == "codex" else "spawn-cc.sh")
                prefix = [] if args.execute else ["--dry-run"]
                command = [str(bridge), *prefix, action["model"], action["effort"], args.cwd, args.prompt_file] if action["provider"] == "codex" and args.cwd and args.prompt_file else [str(bridge), *prefix, action["model"], args.cwd, args.prompt_file] if args.cwd and args.prompt_file else [str(bridge), *prefix, action["model"]]
                commands.append({"task": action["task"], "bridge": command})
            if args.execute:
                if not args.cwd or not args.prompt_file:
                    raise ValueError("dispatch --execute requires --cwd and --prompt-file")
                for item in commands:
                    subprocess.run(item["bridge"], check=True)
            print_json({"dry_run": args.dry_run, "commands": commands})
        return 0
    except (ValueError, sqlite3.IntegrityError, json.JSONDecodeError) as exc:
        print("controller: " + str(exc), file=sys.stderr); return 2
    finally: db.close()


if __name__ == "__main__":
    raise SystemExit(main())
