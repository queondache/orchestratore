#!/usr/bin/env python3
"""Local SQLite state machine for an external orchestrator controller.

The controller deliberately plans work; it does not invoke a provider.  A caller
may turn its JSON actions into bridge invocations, while dry-runs and tests never
consume model credit.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import datetime as dt
import fnmatch
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

if __package__:
    from .path_policy import canonical_path_glob, path_matches_glob
    from .transitions import Command, Decision, State, reduce_transition
else:
    from path_policy import canonical_path_glob, path_matches_glob
    from transitions import Command, Decision, State, reduce_transition

SCHEMA_VERSION = 8
STAGES = ("strategy", "build", "review", "finalize", "done", "parked")
ACTIVE = ("strategy", "build", "review", "finalize")
ROLE_DEFAULTS = {
    "strategy": ("claude", "sonnet", "medium"),
    "build": ("codex", "gpt-5.6-terra", "medium"),
    "review": ("claude", "sonnet", "medium"),
    "finalize": ("codex", "gpt-5.6-luna", "medium"),
}
PROVIDER_ROLE_DEFAULTS = {
    "codex": {
        "strategy": ("gpt-6-astra", "medium"),
        "build": ("gpt-5.6-terra", "medium"),
        "review": ("gpt-5.6-sol", "medium"),
        "finalize": ("gpt-5.6-luna", "medium"),
    },
    "claude": {
        "strategy": ("sonnet", "medium"),
        "build": ("sonnet", "medium"),
        "review": ("opus", "medium"),
        "finalize": ("haiku", "medium"),
    },
}
CODEX_EFFORTS = {
    "gpt-5.6-luna": frozenset(("medium", "high")),
    "gpt-5.6-terra": frozenset(("medium", "high")),
    "gpt-5.6-sol": frozenset(("low", "medium", "high")),
    "gpt-6-astra": frozenset(("low", "medium", "high")),
}
CLAUDE_STAGE_MODELS = frozenset(("opus", "sonnet", "haiku"))
CLAUDE_EFFORTS = frozenset(("medium",))
BUILTIN_TIER3_GLOBS = (
    "**/schema", "**/schema.*", "**/schema/**",
    "**/migration", "**/migrations", "**/migration/**", "**/migrations/**",
    "**/auth/**", "**/authentication/**", "**/session/**", "**/sessions/**",
    "**/payment/**", "**/payments/**", "**/billing/**",
    "**/tenant/**", "**/tenants/**", "**/tenancy/**", "**/multitenancy/**",
    "**/pii/**", "**/patient/**", "**/patients/**", "**/health/**",
    "**/secret/**", "**/secrets/**", "**/*secret*", "**/*credential*",
    "**/*.pem", "**/*.key", "**/.env", "**/.env.*",
    "**/permission/**", "**/permissions/**", "**/role/**", "**/roles/**",
    "**/user/**", "**/users/**", "**/delete/**", "**/deletion/**",
    "**/purge/**", "**/retention/**",
)
PROFILE_LIMITS = {
    "milestone": {"builders": 5, "reviews": 2},
    "bugfix": {"builders": 15, "reviews": 5},
}


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
      ,context_json TEXT NOT NULL DEFAULT '{}', evidence_json TEXT NOT NULL DEFAULT '{}',
      write_globs_json TEXT NOT NULL DEFAULT '[]',
      exclusive_keys_json TEXT NOT NULL DEFAULT '[]',
      worktree_path TEXT, generation INTEGER NOT NULL DEFAULT 0,
      risk_declared INTEGER CHECK(risk_declared BETWEEN 1 AND 3),
      base_sha TEXT, sensitive_paths_json TEXT NOT NULL DEFAULT '[]',
      target_branch TEXT, target_repository TEXT,
      auto_merge_paths_json TEXT NOT NULL DEFAULT '[]'
    );
    CREATE TABLE IF NOT EXISTS leases (
      name TEXT PRIMARY KEY, holder TEXT NOT NULL, expires_at TEXT NOT NULL,
      fence INTEGER NOT NULL DEFAULT 1
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
    CREATE TABLE IF NOT EXISTS assignments (
      id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
      run_id TEXT NOT NULL REFERENCES runs(id), stage TEXT NOT NULL,
      generation INTEGER NOT NULL, holder TEXT NOT NULL, fence INTEGER NOT NULL,
      provider TEXT NOT NULL, model TEXT NOT NULL, effort TEXT NOT NULL,
      worktree_path TEXT, status TEXT NOT NULL
        CHECK(status IN ('claimed','running','succeeded','failed','expired')),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(task_id,stage,generation)
    );
    """)
    # Small forward-only migration for databases made by an earlier controller.
    columns = {r[1] for r in db.execute("PRAGMA table_info(tasks)")}
    for name in ("context_json", "evidence_json"):
        if name not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN %s TEXT NOT NULL DEFAULT '{}'" % name)
    if "write_globs_json" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN write_globs_json TEXT NOT NULL DEFAULT '[]'")
    if "exclusive_keys_json" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN exclusive_keys_json TEXT NOT NULL DEFAULT '[]'")
    if "worktree_path" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN worktree_path TEXT")
    if "generation" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN generation INTEGER NOT NULL DEFAULT 0")
    if "risk_declared" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN risk_declared INTEGER")
    if "base_sha" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN base_sha TEXT")
    if "sensitive_paths_json" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN sensitive_paths_json TEXT NOT NULL DEFAULT '[]'")
    if "target_branch" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN target_branch TEXT")
    if "target_repository" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN target_repository TEXT")
    if "auto_merge_paths_json" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN auto_merge_paths_json TEXT NOT NULL DEFAULT '[]'")
    lease_columns = {r[1] for r in db.execute("PRAGMA table_info(leases)")}
    if "fence" not in lease_columns:
        db.execute("ALTER TABLE leases ADD COLUMN fence INTEGER NOT NULL DEFAULT 1")
    current = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    if current and int(current[0]) > SCHEMA_VERSION:
        raise ValueError("database schema is newer than this controller")
    db.execute("INSERT INTO meta(key,value) VALUES ('schema_version',?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))
    db.commit()


def event(db: sqlite3.Connection, run_id: str, kind: str, task_id: str | None = None, **data: Any) -> None:
    db.execute("INSERT INTO events(run_id,task_id,kind,data_json,created_at) VALUES (?,?,?,?,?)",
               (run_id, task_id, kind, json.dumps(data, sort_keys=True), utcnow()))


def config_for(row: sqlite3.Row) -> dict[str, Any]:
    config = json.loads(row["config_json"])
    if not isinstance(config, dict):
        raise ValueError("run config must be a JSON object")
    config.setdefault("brain_provider", "codex")
    config.setdefault("strategy_provider", "claude")
    config.setdefault("build_provider", "codex")
    config.setdefault("review_provider", "claude")
    config.setdefault("fallback_provider", "codex")
    config.setdefault("brain_model", "gpt-6-astra")
    config.setdefault("brain_effort", "medium")
    config.setdefault("work_profile", "milestone")
    config.setdefault("sensitive_paths", [])
    return config


def configured_sensitive_paths(config: dict[str, Any]) -> tuple[str, ...]:
    risk = config.get("rischio", {})
    if not isinstance(risk, dict):
        raise ValueError("rischio must be a JSON object")
    documented = risk.get("aree_sensibili", [])
    legacy = config.get("sensitive_paths", [])
    for name, value in (("rischio.aree_sensibili", documented),
                        ("sensitive_paths", legacy)):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("%s must be a JSON string list" % name)
    # The documented nested form is canonical.  Keep the old top-level key as
    # additive compatibility for already persisted callers, never as an override.
    return tuple(dict.fromkeys(
        canonical_path_glob(item) for item in (*documented, *legacy)))


def capacity(config: dict[str, Any]) -> dict[str, int]:
    profile = str(config.get("work_profile", "milestone"))
    if profile not in PROFILE_LIMITS:
        raise ValueError("work_profile must be milestone or bugfix")
    return PROFILE_LIMITS[profile]


def validate_ownership(
    task_or_globs: sqlite3.Row | list[str] | tuple[str, ...],
    keys: list[str] | tuple[str, ...] | None = None,
    *,
    allow_legacy_empty: bool,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return canonical ownership or fail closed on any malformed metadata."""
    if isinstance(task_or_globs, sqlite3.Row):
        try:
            globs_value = json.loads(task_or_globs["write_globs_json"])
            keys_value = json.loads(task_or_globs["exclusive_keys_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("ownership metadata must be valid JSON string lists") from exc
    else:
        globs_value = task_or_globs
        keys_value = [] if keys is None else keys
    if not isinstance(globs_value, (list, tuple)) or not all(
            isinstance(item, str) for item in globs_value):
        raise ValueError("write_globs_json must be a JSON string list")
    if not isinstance(keys_value, (list, tuple)) or not all(
            isinstance(item, str) for item in keys_value):
        raise ValueError("exclusive_keys_json must be a JSON string list")

    canonical_globs = tuple(dict.fromkeys(canonical_path_glob(item)
                                          for item in globs_value))
    canonical_keys_list: list[str] = []
    for item in keys_value:
        canonical = item.strip()
        if not canonical:
            raise ValueError("conflict key must not be empty or whitespace")
        if canonical not in canonical_keys_list:
            canonical_keys_list.append(canonical)
    canonical_keys = tuple(canonical_keys_list)
    if not canonical_globs and not canonical_keys and not allow_legacy_empty:
        raise ValueError("new tasks require --write-glob or --conflict-key ownership")
    return canonical_globs, canonical_keys


def static_prefix(pattern: str) -> str:
    positions = [pattern.find(char) for char in "*[?" if char in pattern]
    end = min(positions) if positions else len(pattern)
    return pattern[:end].rstrip("/")


def globs_conflict(left: str, right: str) -> bool:
    """Conservatively reject ownership whose concrete or wildcard roots overlap."""
    left = left.strip().lstrip("./")
    right = right.strip().lstrip("./")
    if not left or not right:
        return True
    if left == right or fnmatch.fnmatch(left, right) or fnmatch.fnmatch(right, left):
        return True
    left_wild = any(char in left for char in "*[?")
    right_wild = any(char in right for char in "*[?")
    if not left_wild and not right_wild:
        return left.startswith(right.rstrip("/") + "/") or right.startswith(left.rstrip("/") + "/")
    if left_wild != right_wild:
        concrete, pattern = (left, right) if not left_wild else (right, left)
        prefix = static_prefix(pattern)
        return (fnmatch.fnmatch(concrete, pattern) or not prefix or
                concrete == prefix or concrete.startswith(prefix.rstrip("/") + "/") or
                prefix.startswith(concrete.rstrip("/") + "/"))
    # Two wildcard languages are considered disjoint only when their fixed
    # directory roots are provably separate. Prefix characters within the same
    # directory are insufficient proof: e.g. src/a*bc and src/ab*c overlap.
    def fixed_directory(pattern: str) -> str:
        prefix = static_prefix(pattern)
        if pattern[:len(prefix) + 1].endswith("/"):
            return prefix
        return prefix.rsplit("/", 1)[0] if "/" in prefix else ""
    left_dir, right_dir = fixed_directory(left), fixed_directory(right)
    if not left_dir or not right_dir:
        return True
    related = (left_dir == right_dir or
               left_dir.startswith(right_dir.rstrip("/") + "/") or
               right_dir.startswith(left_dir.rstrip("/") + "/"))
    return related


def tasks_conflict(left: sqlite3.Row, right: sqlite3.Row) -> bool:
    left_ownership = validate_ownership(left, allow_legacy_empty=True)
    right_ownership = validate_ownership(right, allow_legacy_empty=True)
    left_globs, left_keys = left_ownership
    right_globs, right_keys = right_ownership
    if set(left_keys) & set(right_keys):
        return True
    # Legacy tasks predate ownership metadata. Keep them schedulable; every new
    # task with declared ownership gets the strict conflict check.
    if not left_globs or not right_globs:
        return False
    return any(globs_conflict(a, b) for a in left_globs for b in right_globs)


def review_capacity(rows: list[sqlite3.Row], review_cap: int) -> int:
    waiting_tasks = [task for task in rows if task["stage"] == "review"]
    if not waiting_tasks:
        return 0
    active_builders = sum(task["builder_count"] for task in rows if task["stage"] == "build")
    waiting_builders = sum(task["builder_count"] for task in waiting_tasks)
    builder_wave = active_builders + waiting_builders
    return min(review_cap, max(1, (builder_wave + 2) // 3))


def ensure_effort(model: str, effort: str) -> None:
    allowed = CODEX_EFFORTS.get(model)
    if allowed is None:
        raise ValueError("unsupported Codex model: %s" % model)
    if effort not in allowed:
        raise ValueError("unsupported effort %s for %s; allowed: %s" %
                         (effort, model, ", ".join(sorted(allowed))))


def role_route(stage: str, config: dict[str, Any]) -> tuple[str, str, str]:
    provider = str(config.get(stage + "_provider", ROLE_DEFAULTS[stage][0]))
    if provider not in PROVIDER_ROLE_DEFAULTS:
        raise ValueError("provider must be codex or claude")
    default_model, default_effort = PROVIDER_ROLE_DEFAULTS[provider][stage]
    model = str(config.get(stage + "_model", default_model))
    effort = str(config.get(stage + "_effort", default_effort))
    if provider == "codex":
        ensure_effort(model, effort)
    else:
        if model not in CLAUDE_STAGE_MODELS:
            raise ValueError("unsupported Claude stage model: %s" % model)
        if effort not in CLAUDE_EFFORTS:
            raise ValueError("unsupported Claude stage effort: %s" % effort)
    return provider, model, effort


def validate_routing(config: dict[str, Any]) -> None:
    brain_provider = str(config.get("brain_provider", "codex"))
    if brain_provider not in PROVIDER_ROLE_DEFAULTS:
        raise ValueError("brain_provider must be codex or claude")
    if brain_provider == "codex":
        brain_model = str(config.get("brain_model", "gpt-6-astra"))
        brain_effort = str(config.get("brain_effort", "medium"))
        ensure_effort(brain_model, brain_effort)
        if brain_model != "gpt-6-astra" or brain_effort != "medium":
            raise ValueError("Codex brain must use gpt-6-astra at medium effort")
    else:
        brain_model = str(config.get("brain_model", "sonnet"))
        if brain_model not in ("opus", "sonnet", "haiku", "fable"):
            raise ValueError("unsupported Claude brain model: %s" % brain_model)
        if str(config.get("brain_effort", "medium")) != "medium":
            raise ValueError("Claude brain effort must be medium")
    routes = {stage: role_route(stage, config) for stage in ACTIVE}
    build_identity = routes["build"][:2]
    review_identity = routes["review"][:2]
    finalize_identity = routes["finalize"][:2]
    if build_identity == review_identity:
        raise ValueError("review must use a provider/model identity different from builder")
    if finalize_identity in (build_identity, review_identity):
        raise ValueError("finalize must use a provider/model identity different from builder and reviewer")


def route(task: sqlite3.Row, config: dict[str, Any]) -> tuple[str, str, str]:
    return role_route(task["stage"], config)


def acquire(db: sqlite3.Connection, name: str, holder: str, seconds: int) -> tuple[bool, int | None]:
    if seconds <= 0:
        raise ValueError("lease duration must be positive")
    now = utcnow()
    expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)).replace(microsecond=0).isoformat()
    with db:
        row = db.execute("SELECT holder,expires_at,fence FROM leases WHERE name=?", (name,)).fetchone()
        if row and row["expires_at"] > now and row["holder"] != holder:
            return False, int(row["fence"])
        active_same_holder = bool(row and row["expires_at"] > now and row["holder"] == holder)
        fence = int(row["fence"]) if active_same_holder else (
            int(row["fence"]) + 1 if row else 1)
        db.execute("INSERT INTO leases(name,holder,expires_at,fence) VALUES(?,?,?,?) "
                   "ON CONFLICT(name) DO UPDATE SET holder=excluded.holder, "
                   "expires_at=excluded.expires_at, fence=excluded.fence",
                   (name, holder, expiry, fence))
    return True, fence


def release(db: sqlite3.Connection, name: str, holder: str) -> bool:
    with db:
        cur = db.execute(
            "UPDATE leases SET expires_at=? WHERE name=? AND holder=? AND expires_at>?",
            ("1970-01-01T00:00:00+00:00", name, holder, utcnow()))
    return cur.rowcount == 1


def require_lease(db: sqlite3.Connection, run_id: str, holder: str | None,
                  expected_fence: int | None = None) -> int:
    if not holder:
        raise ValueError("mutating command requires --holder with a valid run lease")
    row = db.execute("SELECT holder,expires_at,fence FROM leases WHERE name=?", (run_id,)).fetchone()
    if not row or row["holder"] != holder or row["expires_at"] <= utcnow():
        raise ValueError("no valid lease for run %s and holder %s" % (run_id, holder))
    fence = int(row["fence"])
    if expected_fence is not None and fence != expected_fence:
        raise ValueError("stale fencing token for run %s" % run_id)
    return fence


def renew_lease_same_fence(db: sqlite3.Connection, run_id: str, holder: str,
                           fence: int, seconds: int) -> bool:
    now = utcnow()
    expiry = (dt.datetime.now(dt.timezone.utc) +
              dt.timedelta(seconds=max(2, seconds))).replace(microsecond=0).isoformat()
    with db:
        cur = db.execute(
            "UPDATE leases SET expires_at=? WHERE name=? AND holder=? AND fence=? "
            "AND expires_at>?", (expiry, run_id, holder, fence, now))
    return cur.rowcount == 1


def expire_dispatch_claims(db: sqlite3.Connection, run_id: str, holder: str,
                           fence: int, commands: list[dict[str, Any]]) -> None:
    db.execute("BEGIN IMMEDIATE")
    try:
        lease = db.execute("SELECT holder,fence FROM leases WHERE name=?",
                           (run_id,)).fetchone()
        if lease and lease["holder"] == holder and int(lease["fence"]) == fence:
            now = utcnow()
            for item in commands:
                cur = db.execute(
                    "UPDATE assignments SET status='expired',updated_at=? WHERE id=? "
                    "AND status='running'", (now, item["assignment_id"]))
                if cur.rowcount:
                    db.execute(
                        "UPDATE tasks SET generation=generation+1,updated_at=? WHERE id=? "
                        "AND generation=?", (now, item["task"], item["generation"]))
        db.commit()
    except Exception:
        db.rollback()
        raise


def plan(db: sqlite3.Connection, run_id: str, dry_run: bool,
         holder: str | None = None, expected_fence: int | None = None) -> list[dict[str, Any]]:
    if not dry_run:
        db.execute("BEGIN IMMEDIATE")
        fence = require_lease(db, run_id, holder, expected_fence)
    else:
        fence = None
    run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        raise ValueError("unknown run: %s" % run_id)
    if run["status"] != "active":
        return []
    config = config_for(run)
    limits = capacity(config)
    rows = db.execute("SELECT * FROM tasks WHERE run_id=? AND stage IN ('strategy','build','review','finalize') ORDER BY updated_at,id", (run_id,)).fetchall()
    # Review work has priority but uses its own proportional pool. Finalize is
    # also separate; neither stage consumes a builder slot.
    stage_priority = {"review": 0, "finalize": 1, "strategy": 2, "build": 3}
    rows = sorted(rows, key=lambda row: (stage_priority[row["stage"]], row["updated_at"], row["id"]))
    # Validate every active record before considering capacity or conflicts. This
    # makes corrupt ownership fail closed even for the first or only task.
    for task in rows:
        validate_ownership(task, allow_legacy_empty=True)
    planned: list[dict[str, Any]] = []
    builder_slots = 0
    review_slots = 0
    selected_builds: list[sqlite3.Row] = []
    review_backlog = sum(task["stage"] == "review" for task in rows)
    available_reviews = review_capacity(rows, limits["reviews"])
    pause_new_builds = review_backlog >= available_reviews > 0
    for task in rows:
        generation = int(task["generation"])
        claimed = db.execute(
            "SELECT * FROM assignments WHERE task_id=? AND stage=? AND generation=? "
            "AND status IN ('claimed','running')",
            (task["id"], task["stage"], generation)).fetchone()
        if claimed:
            # A lease takeover fences every claim made by the previous brain.
            # Expire it durably and advance the task generation before issuing a
            # replacement assignment, so a late result can never be accepted.
            if (dry_run or
                    (claimed["holder"] == holder and int(claimed["fence"]) == fence)):
                continue
            now = utcnow()
            db.execute("UPDATE assignments SET status='expired',updated_at=? WHERE id=?",
                       (now, claimed["id"]))
            db.execute("UPDATE tasks SET generation=generation+1,updated_at=? WHERE id=?",
                       (now, task["id"]))
            generation += 1
        # Finalization is never skipped: it explicitly gates PR/merge/docs.
        # Corrupt/legacy state can exceed the configured builder pool. Dispatch
        # only the first fitting tasks instead of letting an overfull sum starve all.
        if task["stage"] == "build":
            if pause_new_builds:
                continue
            if builder_slots + task["builder_count"] > limits["builders"]:
                continue
            if any(tasks_conflict(task, selected) for selected in selected_builds):
                continue
            builder_slots += task["builder_count"]
            selected_builds.append(task)
        elif task["stage"] == "review":
            if review_slots >= available_reviews:
                continue
            review_slots += 1
        context = json.loads(task["context_json"])
        checkpoint_emitted = bool(context.get("checkpoint_emitted")) if isinstance(context, dict) else False
        if task["checkpoint"] >= 70:
            action = {"task": task["id"], "action": "rollover", "session": task["session"] + 1,
                      "reason": "checkpoint >= 70; start a fresh session"}
        elif task["checkpoint"] >= 50 and not checkpoint_emitted:
            action = {"task": task["id"], "action": "checkpoint", "reason": "checkpoint >= 50"}
        else:
            provider, model, effort = route(task, config)
            action = {"task": task["id"], "action": task["stage"], "stage": task["stage"],
                      "provider": provider, "model": model, "effort": effort,
                      "fallback": config["fallback_provider"], "generation": generation,
                      "worktree_path": task["worktree_path"], "assignment_id": None,
                      "fence": fence,
                      "write_globs": json.loads(task["write_globs_json"])}
        planned.append(action)
        if not dry_run:
            now = utcnow()
            db.execute("UPDATE tasks SET owner_provider=?,owner_model=?,owner_effort=?,updated_at=? WHERE id=?",
                       (action.get("provider"), action.get("model"), action.get("effort"), now, task["id"]))
            if action["action"] == "rollover":
                context.pop("checkpoint_emitted", None)
                db.execute("UPDATE tasks SET session=session+1,checkpoint=0,context_json=?,"
                           "updated_at=? WHERE id=?",
                           (json.dumps(context, sort_keys=True), now, task["id"]))
            elif action["action"] == "checkpoint":
                context["checkpoint_emitted"] = True
                db.execute("UPDATE tasks SET context_json=?,updated_at=? WHERE id=?",
                           (json.dumps(context, sort_keys=True), now, task["id"]))
            else:
                assignment_id = "asg-" + uuid.uuid4().hex
                action["assignment_id"] = assignment_id
                db.execute(
                    "INSERT INTO assignments(id,task_id,run_id,stage,generation,holder,fence,"
                    "provider,model,effort,worktree_path,status,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (assignment_id, task["id"], run_id, task["stage"], generation,
                     holder, fence, action["provider"], action["model"], action["effort"],
                     task["worktree_path"], "claimed", now, now))
            event(db, run_id, "planned", task["id"], **action)
    if not dry_run:
        db.commit()
    return planned


def parse_evidence(evidence: str) -> dict[str, Any]:
    try:
        value = json.loads(evidence)
    except json.JSONDecodeError as exc:
        raise ValueError("stage evidence must be a JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError("stage evidence must be a JSON object")
    return value


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def successful_command(value: Any) -> bool:
    return (isinstance(value, dict) and nonempty(value.get("command")) and
            value.get("exit_code") == 0 and nonempty(value.get("output")))


def worktree_head(assignment: sqlite3.Row) -> str:
    worktree = assignment["worktree_path"]
    if not nonempty(worktree):
        raise ValueError("assignment has no worktree for Git evidence")
    result = subprocess.run(["git", "-C", worktree, "rev-parse", "HEAD"],
                            capture_output=True, text=True)
    if result.returncode != 0 or not nonempty(result.stdout):
        raise ValueError("cannot verify task worktree HEAD")
    return result.stdout.strip()


def exact_commit(worktree: str, sha: str, label: str) -> str:
    if not nonempty(sha):
        raise ValueError("%s sha is missing" % label)
    result = subprocess.run(
        ["git", "-C", worktree, "rev-parse", "--verify", sha + "^{commit}"],
        capture_output=True, text=True)
    resolved = result.stdout.strip()
    if result.returncode != 0 or resolved != sha:
        raise ValueError("%s sha is not an exact Git commit" % label)
    return resolved


def github_repository(worktree: str) -> str:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        cwd=worktree, capture_output=True, text=True)
    repository = result.stdout.strip()
    if (result.returncode != 0 or not nonempty(repository) or
            repository.count("/") != 1 or any(part in {"", ".", ".."}
                                               for part in repository.split("/"))):
        raise ValueError("cannot resolve authoritative GitHub repository")
    return repository


def github_target_oid(worktree: str, repository: str, target_branch: str) -> str:
    if not nonempty(repository) or not nonempty(target_branch):
        raise ValueError("GitHub target identity is incomplete")
    endpoint = "repos/%s/git/ref/heads/%s" % (
        repository, quote(target_branch, safe=""))
    result = subprocess.run(
        ["gh", "api", endpoint, "--jq", ".object.sha"], cwd=worktree,
        capture_output=True, text=True)
    oid = result.stdout.strip()
    if (result.returncode != 0 or len(oid) != 40 or
            any(char not in "0123456789abcdefABCDEF" for char in oid)):
        raise ValueError("cannot resolve authoritative GitHub target OID")
    return exact_commit(worktree, oid.lower(), "remote base")


def risk_classification(task: sqlite3.Row, reviewed_sha: str,
                        worktree: str) -> dict[str, Any]:
    """Classify the immutable base..reviewed diff; uncertainty is manual-only."""
    base_sha = task["base_sha"]
    exact_commit(worktree, base_sha, "base")
    exact_commit(worktree, reviewed_sha, "reviewed")
    ancestor = subprocess.run(
        ["git", "-C", worktree, "merge-base", "--is-ancestor", base_sha,
         reviewed_sha], capture_output=True, text=True)
    if ancestor.returncode != 0:
        raise ValueError("base sha is not an ancestor of reviewed sha")
    changed_result = subprocess.run(
        ["git", "-C", worktree, "diff", "--name-only", "--no-renames", "-z",
         base_sha, reviewed_sha, "--"], capture_output=True)
    if changed_result.returncode != 0:
        raise ValueError("cannot classify the reviewed Git diff")
    try:
        changed = tuple(sorted(
            item.decode("utf-8") for item in changed_result.stdout.split(b"\0") if item))
        raw_paths = json.loads(task["sensitive_paths_json"])
        raw_auto_merge_paths = json.loads(task["auto_merge_paths_json"])
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("cannot prove risk classification metadata") from exc
    if not isinstance(raw_paths, list) or not all(isinstance(item, str) for item in raw_paths):
        raise ValueError("cannot prove risk classification metadata")
    if (not isinstance(raw_auto_merge_paths, list) or
            not all(isinstance(item, str) for item in raw_auto_merge_paths)):
        raise ValueError("cannot prove risk classification metadata")
    paths = tuple(dict.fromkeys(canonical_path_glob(item) for item in raw_paths))
    auto_merge_paths = tuple(dict.fromkeys(
        canonical_path_glob(item) for item in raw_auto_merge_paths))
    builtin_matches = tuple(sorted(path for path in changed
                                   if any(path_matches_glob(path, pattern)
                                          for pattern in BUILTIN_TIER3_GLOBS)))
    configured_matches = tuple(sorted(path for path in changed
                                      if any(path_matches_glob(path, pattern)
                                             for pattern in paths)))
    matches = tuple(sorted(set(builtin_matches) | set(configured_matches)))
    unclassified = tuple(sorted(path for path in changed
                                if not any(path_matches_glob(path, pattern)
                                           for pattern in auto_merge_paths)))
    declared = task["risk_declared"]
    proven = declared in (1, 2, 3)
    diff_tier = 3 if matches or unclassified else 1
    effective_tier = max(diff_tier, declared) if declared in (1, 2, 3) else diff_tier
    auto_merge = (declared in (1, 2) and effective_tier in (1, 2) and
                  bool(auto_merge_paths) and not matches and not unclassified)
    reason = None
    if declared not in (1, 2, 3):
        reason = "risk tier was not declared"
    elif matches:
        reason = "diff is tier 3 or touches a sensitive path"
    elif not auto_merge_paths:
        reason = "no explicit auto-merge allowlist was frozen"
    elif unclassified:
        reason = "diff contains paths outside the auto-merge allowlist"
    elif effective_tier == 3:
        reason = "diff is tier 3"
    return {
        "classifier": "controller-diff-v1",
        "base_sha": base_sha,
        "base_source": "github-target-ref",
        "target_repository": task["target_repository"],
        "target_branch": task["target_branch"],
        "sha": reviewed_sha,
        "declared_tier": declared,
        "risk_tier": effective_tier,
        "sensitive": bool(matches),
        "sensitive_paths": list(paths),
        "auto_merge_paths": list(auto_merge_paths),
        "builtin_tier3_paths": list(builtin_matches),
        "configured_sensitive_paths": list(configured_matches),
        "matched_sensitive_paths": list(matches),
        "changed_paths": list(changed),
        "unclassified_paths": list(unclassified),
        "proven": proven,
        "auto_merge": auto_merge,
        "reason": reason,
    }


def github_pr_snapshot(worktree: str, number: int, repository: str) -> dict[str, Any]:
    view = subprocess.run(
        ["gh", "pr", "view", str(number), "--repo", repository,
         "--json", "headRefOid,state,baseRefName"],
        cwd=worktree, capture_output=True, text=True)
    if view.returncode != 0:
        raise ValueError("cannot verify PR state with GitHub")
    try:
        pr = json.loads(view.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub PR verification returned invalid JSON") from exc
    return pr


def verify_github_finalize(worktree: str, number: int, sha: str,
                           repository: str, target_branch: str, merged: bool,
                           require_checks: bool = False) -> dict[str, Any]:
    pr = github_pr_snapshot(worktree, number, repository)
    if pr.get("headRefOid") != sha:
        raise ValueError("GitHub PR head does not match reviewed sha")
    if not nonempty(target_branch) or pr.get("baseRefName") != target_branch:
        raise ValueError("GitHub PR base does not match frozen target branch")
    if merged and pr.get("state") != "MERGED":
        raise ValueError("GitHub does not report the PR as merged")
    if not merged and pr.get("state") != "OPEN":
        raise ValueError("GitHub does not report an open PR awaiting merge")
    attestation: dict[str, Any] = {
        "provider": "github", "verified": True, "sha": sha,
        "verification_id": "pr-%d" % number, "verified_at": utcnow(),
        "base_ref": pr["baseRefName"], "required_checks": [],
    }
    if merged or require_checks:
        checks_result = subprocess.run(
            ["gh", "pr", "checks", str(number), "--required", "--json",
             "name,state,link", "--repo", repository], cwd=worktree,
            capture_output=True, text=True)
        if checks_result.returncode != 0:
            raise ValueError("cannot verify required GitHub checks or branch protection")
        try:
            checks = json.loads(checks_result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("GitHub required-check verification returned invalid JSON") from exc
        if (not isinstance(checks, list) or not checks or
                any(not isinstance(check, dict) or check.get("state") != "SUCCESS"
                    for check in checks)):
            raise ValueError("not all required GitHub checks passed")
        attestation["required_checks"] = checks
    return attestation


def validate_stage_evidence(db: sqlite3.Connection, task: sqlite3.Row,
                            assignment: sqlite3.Row, evidence: str) -> dict[str, Any]:
    value = parse_evidence(evidence)
    stage = task["stage"]
    if stage == "strategy":
        if not nonempty(value.get("summary")) or not nonempty(value.get("plan_hash")):
            raise ValueError("strategy evidence requires summary and plan_hash")
    elif stage == "build":
        if (not nonempty(value.get("sha")) or value.get("sha") != worktree_head(assignment) or
                not successful_command(value.get("gate"))):
            raise ValueError("build evidence requires worktree HEAD sha and successful gate evidence")
    elif stage == "review":
        prior = json.loads(task["evidence_json"])
        build = prior.get("build", {}) if isinstance(prior, dict) else {}
        reviewer = value.get("reviewer")
        if (value.get("verdict") != "OK" or not nonempty(value.get("sha")) or
                value.get("sha") != worktree_head(assignment) or
                value.get("sha") != build.get("sha") or
                not isinstance(reviewer, dict) or
                (reviewer.get("provider"), reviewer.get("model")) !=
                (assignment["provider"], assignment["model"]) or
                not successful_command(value.get("oracle")) or
                not nonempty(value.get("raw_output"))):
            raise ValueError("review evidence requires matching sha, independent reviewer, "
                             "OK verdict, oracle and raw_output")
        build_assignment = db.execute(
            "SELECT provider,model FROM assignments WHERE task_id=? AND stage='build' "
            "AND status='succeeded' ORDER BY generation DESC LIMIT 1", (task["id"],)).fetchone()
        if not build_assignment or (assignment["provider"], assignment["model"]) == (
                build_assignment["provider"], build_assignment["model"]):
            raise ValueError("review evidence is not independent from builder model")
    elif stage == "finalize":
        prior = json.loads(task["evidence_json"])
        review = prior.get("review", {}) if isinstance(prior, dict) else {}
        pr, merge = value.get("pr"), value.get("merge")
        if (not isinstance(pr, dict) or not isinstance(merge, dict) or
                value.get("docs") is not True or
                pr.get("state") not in ("merged", "open", "approved-wait") or
                not isinstance(pr.get("number"), int) or pr.get("number") <= 0 or
                merge.get("state") not in ("merged", "approved-wait") or
                not nonempty(pr.get("sha")) or pr.get("sha") != merge.get("sha") or
                pr.get("sha") != review.get("sha")):
            raise ValueError("finalize evidence requires coherent pr, merge, docs and reviewed sha")
        if review.get("sha") != worktree_head(assignment):
            raise ValueError("finalize reviewed sha no longer matches worktree HEAD")
        if merge["state"] == "merged":
            if pr["state"] != "merged":
                raise ValueError("finalize evidence cannot merge an unmerged PR")
        elif pr["state"] == "merged":
            raise ValueError("finalize approved-wait evidence cannot report a merged PR")
        if merge["state"] == "merged":
            raise ValueError("merged finalize evidence is accepted only by controller merge")
        value["risk_classification"] = risk_classification(
            task, review["sha"], assignment["worktree_path"])
        value["external_attestation"] = verify_github_finalize(
            assignment["worktree_path"], pr["number"], review["sha"],
            task["target_repository"], task["target_branch"], False)
    else:
        raise ValueError("task is not active")
    return value


def transition_for(db: sqlite3.Connection, task: sqlite3.Row, command: Command) -> Decision:
    """Read durable history, then delegate all replay/budget policy to the reducer."""
    seen_events = frozenset(row[0] for row in db.execute(
        "SELECT event_id FROM event_ids WHERE task_id=? AND kind=?",
        (task["id"], command.operation)))
    # Result idempotency is assignment/event scoped. Reusing a failure signature
    # in a new generation is a new failed attempt and must consume budget.
    seen_signatures: frozenset[tuple[str, str, str]] = frozenset()
    return reduce_transition(State(task["id"], task["stage"], task["approach"],
                                   task["attempts"], task["generation"]),
                             command, seen_events, seen_signatures)


def remember_event(db: sqlite3.Connection, task: sqlite3.Row, operation: str, identity: str) -> None:
    db.execute("INSERT OR IGNORE INTO event_ids(event_id,run_id,task_id,kind,created_at) VALUES(?,?,?,?,?)",
               (identity, task["run_id"], task["id"], operation, utcnow()))


def authenticated_assignment(db: sqlite3.Connection, task: sqlite3.Row,
                             assignment_id: str | None, expected_stage: str | None,
                             holder: str, fence: int) -> sqlite3.Row:
    if not assignment_id or not expected_stage:
        raise ValueError("completion requires assignment-id and expected-stage")
    assignment = db.execute("SELECT * FROM assignments WHERE id=?", (assignment_id,)).fetchone()
    if not assignment:
        raise ValueError("unknown or stale assignment")
    if (assignment["task_id"] != task["id"] or assignment["stage"] != expected_stage or
            assignment["holder"] != holder or assignment["fence"] != fence):
        raise ValueError("stale assignment result rejected")
    return assignment


def require_active_assignment(task: sqlite3.Row, assignment: sqlite3.Row,
                              expected_stage: str) -> None:
    if (task["stage"] != expected_stage or
            assignment["generation"] != task["generation"] or
            assignment["status"] not in ("claimed", "running")):
        raise ValueError("stale assignment result rejected")


def complete(db: sqlite3.Connection, task_id: str, evidence: str, event_id: str | None,
             assignment_id: str | None, expected_stage: str | None,
             holder: str, expected_fence: int | None) -> str:
    # BEGIN IMMEDIATE serializes admission decisions across controller processes:
    # cap/conflict checks and strategy->build become one atomic write decision.
    db.execute("BEGIN IMMEDIATE")
    try:
        task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not task:
            raise ValueError("unknown task: %s" % task_id)
        fence = require_lease(db, task["run_id"], holder, expected_fence)
        assignment = authenticated_assignment(
            db, task, assignment_id, expected_stage, holder, fence)
        decision = transition_for(
            db, task, Command("complete", evidence, event_id=event_id,
                              stage_intent=expected_stage,
                              generation=assignment["generation"]))
        if decision.result == "deduplicated":
            if assignment["status"] != "succeeded":
                raise ValueError("stale assignment result rejected")
            db.commit()
            return decision.result
        require_active_assignment(task, assignment, expected_stage)
        evidence_value = validate_stage_evidence(db, task, assignment, evidence)
        if task["stage"] == "strategy":
            run = db.execute("SELECT * FROM runs WHERE id=?", (task["run_id"],)).fetchone()
            limits = capacity(config_for(run))
            active_builders = db.execute("SELECT COALESCE(SUM(builder_count),0) FROM tasks WHERE run_id=? AND stage='build'", (task["run_id"],)).fetchone()[0]
            if active_builders + task["builder_count"] > limits["builders"]:
                raise ValueError("max %d active builders for this work profile; complete a build first" % limits["builders"])
            active_tasks = db.execute("SELECT * FROM tasks WHERE run_id=? AND stage='build'", (task["run_id"],)).fetchall()
            conflict = next((other for other in active_tasks if tasks_conflict(task, other)), None)
            if conflict:
                raise ValueError("ownership or incompatibility conflicts with active build task %s" % conflict["id"])
        stored = json.loads(task["evidence_json"])
        awaiting_merge = task["stage"] == "finalize"
        nxt = "finalize" if awaiting_merge else decision.state.stage
        implementation_done = 1 if task["stage"] == "build" else task["implementation_done"]
        finalized = task["finalized"]
        remember_event(db, task, "complete", decision.identity)
        db.execute("INSERT INTO attempts(task_id,approach,attempt,stage,provider,model,effort,result,evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (task_id, task["approach"], task["attempts"], task["stage"], task["owner_provider"] or "unknown", task["owner_model"] or "unknown", task["owner_effort"] or "unknown", "ok", evidence, utcnow()))
        stored[task["stage"]] = evidence_value
        now = utcnow()
        db.execute("UPDATE assignments SET status='succeeded',updated_at=? WHERE id=?",
                   (now, assignment["id"]))
        db.execute("UPDATE tasks SET stage=?,implementation_done=?,finalized=?,checkpoint=0,"
                   "evidence_json=?,updated_at=?,generation=generation+1,approach=1,attempts=0 "
                   "WHERE id=?",
                   (nxt, implementation_done, finalized, json.dumps(stored, sort_keys=True), now, task_id))
        event(db, task["run_id"], "completed", task_id, stage=task["stage"], next_stage=nxt, evidence=evidence)
        db.commit()
        return "approved-wait" if awaiting_merge else decision.result
    except Exception:
        db.rollback()
        raise


def fail(db: sqlite3.Connection, task_id: str, signature: str, evidence: str,
         event_id: str | None, assignment_id: str | None, expected_stage: str | None,
         holder: str, expected_fence: int | None) -> str:
    db.execute("BEGIN IMMEDIATE")
    try:
        task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not task:
            raise ValueError("unknown task: %s" % task_id)
        fence = require_lease(db, task["run_id"], holder, expected_fence)
        assignment = authenticated_assignment(
            db, task, assignment_id, expected_stage, holder, fence)
        decision = transition_for(
            db, task, Command("fail", evidence, signature, event_id,
                              stage_intent=expected_stage,
                              generation=assignment["generation"]))
        if decision.result == "deduplicated":
            if assignment["status"] in ("claimed", "running"):
                require_active_assignment(task, assignment, expected_stage)
                now = utcnow()
                db.execute("UPDATE assignments SET status='failed',updated_at=? WHERE id=?",
                           (now, assignment["id"]))
                db.execute("UPDATE tasks SET generation=generation+1,updated_at=? WHERE id=?",
                           (now, task_id))
            elif assignment["status"] != "failed":
                raise ValueError("stale assignment result rejected")
            db.commit()
            return "deduplicated"
        require_active_assignment(task, assignment, expected_stage)
        attempts = decision.state.attempts
        approach = decision.state.approach
        stage = decision.state.stage
        status = decision.result
        remember_event(db, task, "fail", decision.identity)
        db.execute("INSERT OR IGNORE INTO failure_signatures(task_id,stage,approach,signature) VALUES(?,?,?,?)", (task_id, task["stage"], task["approach"], signature))
        db.execute("INSERT INTO attempts(task_id,approach,attempt,stage,provider,model,effort,result,evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (task_id, task["approach"], decision.charged_attempt, task["stage"], task["owner_provider"] or "unknown", task["owner_model"] or "unknown", task["owner_effort"] or "unknown", status, evidence, utcnow()))
        now = utcnow()
        db.execute("UPDATE assignments SET status='failed',updated_at=? WHERE id=?",
                   (now, assignment["id"]))
        db.execute("UPDATE tasks SET stage=?,approach=?,attempts=?,last_error=?,updated_at=?,"
                   "generation=generation+1 WHERE id=?",
                   (stage, approach, attempts, signature, now, task_id))
        event(db, task["run_id"], status, task_id, signature=signature, approach=approach, attempts=attempts, evidence=evidence)
        db.commit()
        return status
    except Exception:
        db.rollback()
        raise


def merge_task(db: sqlite3.Connection, task_id: str,
               assignment_id: str | None, holder: str,
               expected_fence: int | None) -> str:
    db.execute("BEGIN IMMEDIATE")
    try:
        task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not task:
            raise ValueError("unknown task: %s" % task_id)
        fence = require_lease(db, task["run_id"], holder, expected_fence)
        assignment = authenticated_assignment(
            db, task, assignment_id, "finalize", holder, fence)
        require_active_assignment(task, assignment, "finalize")
        stored = json.loads(task["evidence_json"])
        review = stored.get("review", {}) if isinstance(stored, dict) else {}
        request = stored.get("finalize", {}) if isinstance(stored, dict) else {}
        pr = request.get("pr") if isinstance(request, dict) else None
        sha = review.get("sha")
        if (request.get("suggest_merge") is not True or request.get("docs") is not True or
                not isinstance(pr, dict) or not isinstance(pr.get("number"), int) or
                pr["number"] <= 0 or pr.get("sha") != sha or
                not nonempty(sha) or sha != worktree_head(assignment)):
            raise ValueError("merge requires suggest_merge, docs, PR number and reviewed HEAD sha")
        recorded_classification = request.get("risk_classification")
        current_classification = risk_classification(
            task, sha, assignment["worktree_path"])
        if recorded_classification != current_classification:
            raise ValueError("risk classification is missing or stale for reviewed sha")
        if not current_classification["auto_merge"]:
            raise ValueError("risk classification requires manual merge: %s" %
                             (current_classification["reason"] or "not eligible"))
        remote_base = github_target_oid(
            assignment["worktree_path"], task["target_repository"],
            task["target_branch"])
        if remote_base != task["base_sha"]:
            raise ValueError("GitHub target branch moved since risk classification")
        snapshot = github_pr_snapshot(
            assignment["worktree_path"], pr["number"], task["target_repository"])
        merge_stdout = "reconciled existing GitHub merge"
        if snapshot.get("headRefOid") != sha:
            raise ValueError("GitHub PR head does not match reviewed sha")
        if snapshot.get("baseRefName") != task["target_branch"]:
            raise ValueError("GitHub PR base does not match frozen target branch")
        if snapshot.get("state") == "MERGED":
            premerge = verify_github_finalize(
                assignment["worktree_path"], pr["number"], sha,
                task["target_repository"], task["target_branch"], True)
            postmerge = premerge
        elif snapshot.get("state") == "OPEN":
            premerge = verify_github_finalize(
                assignment["worktree_path"], pr["number"], sha,
                task["target_repository"], task["target_branch"], False,
                require_checks=True)
            remote_base = github_target_oid(
                assignment["worktree_path"], task["target_repository"],
                task["target_branch"])
            if remote_base != task["base_sha"]:
                raise ValueError("GitHub target branch moved before merge")
            merged = subprocess.run(
                ["gh", "pr", "merge", str(pr["number"]), "--squash",
                 "--match-head-commit", sha, "--repo", task["target_repository"]],
                cwd=assignment["worktree_path"],
                capture_output=True, text=True)
            try:
                postmerge = verify_github_finalize(
                    assignment["worktree_path"], pr["number"], sha,
                    task["target_repository"], task["target_branch"], True)
            except ValueError:
                if merged.returncode != 0:
                    raise ValueError("GitHub merge failed: %s" %
                                     (merged.stderr.strip() or merged.stdout.strip()))
                raise
            merge_stdout = merged.stdout.strip()
        else:
            raise ValueError("GitHub PR is neither open nor merged")
        final_evidence = {
            "pr": {"state": "merged", "number": pr["number"], "sha": sha},
            "merge": {"state": "merged", "sha": sha,
                      "stdout": merge_stdout},
            "docs": True, "suggest_merge": True,
            "risk_classification": current_classification,
            "premerge_attestation": premerge,
            "external_attestation": postmerge,
        }
        command = Command("complete", json.dumps(final_evidence, sort_keys=True),
                          stage_intent="finalize", generation=assignment["generation"])
        decision = transition_for(db, task, command)
        if decision.result == "deduplicated":
            raise ValueError("merge assignment result is stale")
        now = utcnow()
        remember_event(db, task, "complete", decision.identity)
        db.execute("INSERT INTO attempts(task_id,approach,attempt,stage,provider,model,"
                   "effort,result,evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (task_id, task["approach"], task["attempts"], "finalize",
                    assignment["provider"], assignment["model"], assignment["effort"],
                    "ok", json.dumps(final_evidence, sort_keys=True), now))
        stored["finalize"] = final_evidence
        db.execute("UPDATE assignments SET status='succeeded',updated_at=? WHERE id=?",
                   (now, assignment["id"]))
        db.execute("UPDATE tasks SET stage='done',finalized=1,checkpoint=0,evidence_json=?,"
                   "updated_at=?,generation=generation+1,approach=1,attempts=0 WHERE id=?",
                   (json.dumps(stored, sort_keys=True), now, task_id))
        event(db, task["run_id"], "merged", task_id, sha=sha,
              pr_number=pr["number"])
        db.commit()
        return "merged"
    except Exception:
        db.rollback()
        raise


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
    add = subs.add_parser("add-task"); add.add_argument("run_id"); add.add_argument("task_id"); add.add_argument("title"); add.add_argument("--builders", type=int, default=1); add.add_argument("--write-glob", action="append", default=[]); add.add_argument("--conflict-key", action="append", default=[]); add.add_argument("--auto-merge-glob", action="append", default=[]); add.add_argument("--worktree-path", required=True); add.add_argument("--target-branch", required=True); add.add_argument("--risk-tier", type=int, choices=(1, 2, 3)); add.add_argument("--holder", required=True); add.add_argument("--fence", type=int)
    schedule = subs.add_parser("schedule"); schedule.add_argument("run_id"); schedule.add_argument("--dry-run", action="store_true"); schedule.add_argument("--holder"); schedule.add_argument("--fence", type=int)
    done = subs.add_parser("complete"); done.add_argument("task_id"); done.add_argument("--evidence", required=True); done.add_argument("--event-id"); done.add_argument("--assignment-id", required=True); done.add_argument("--expected-stage", choices=ACTIVE, required=True); done.add_argument("--holder"); done.add_argument("--fence", type=int)
    bad = subs.add_parser("fail"); bad.add_argument("task_id"); bad.add_argument("signature"); bad.add_argument("--evidence", required=True); bad.add_argument("--event-id"); bad.add_argument("--assignment-id", required=True); bad.add_argument("--expected-stage", choices=ACTIVE, required=True); bad.add_argument("--holder"); bad.add_argument("--fence", type=int)
    merge = subs.add_parser("merge"); merge.add_argument("task_id"); merge.add_argument("--assignment-id", required=True); merge.add_argument("--holder"); merge.add_argument("--fence", type=int)
    checkpoint = subs.add_parser("checkpoint"); checkpoint.add_argument("task_id"); checkpoint.add_argument("percent", type=int); checkpoint.add_argument("--summary", default=""); checkpoint.add_argument("--head", default=""); checkpoint.add_argument("--fingerprint", default=""); checkpoint.add_argument("--holder"); checkpoint.add_argument("--fence", type=int)
    status = subs.add_parser("status"); status.add_argument("run_id")
    lock = subs.add_parser("acquire"); lock.add_argument("name"); lock.add_argument("holder"); lock.add_argument("--seconds", type=int, default=60)
    unlock = subs.add_parser("release"); unlock.add_argument("name"); unlock.add_argument("holder")
    dispatch = subs.add_parser("dispatch"); dispatch.add_argument("run_id"); mode = dispatch.add_mutually_exclusive_group(); mode.add_argument("--dry-run", action="store_true"); mode.add_argument("--execute", action="store_true"); dispatch.add_argument("--cwd"); dispatch.add_argument("--holder"); dispatch.add_argument("--fence", type=int)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    db = connect(args.db); initialize(db)
    try:
        if args.command == "init": print_json({"db": args.db, "schema_version": SCHEMA_VERSION})
        elif args.command == "start":
            config = json.loads(args.config)
            if not isinstance(config, dict): raise ValueError("run config must be a JSON object")
            capacity(config)
            validate_routing(config)
            configured_sensitive_paths(config)
            if args.seconds <= 0: raise ValueError("lease duration must be positive")
            # Run row and its lease are created in one transaction: a run must
            # never exist without an authoritative holder, even for one instant.
            now = utcnow()
            expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=args.seconds)).replace(microsecond=0).isoformat()
            with db:
                existing = db.execute("SELECT holder,expires_at,fence FROM leases WHERE name=?", (args.run_id,)).fetchone()
                if existing and existing["expires_at"] > now and existing["holder"] != args.holder:
                    raise ValueError("run lease %s held by another holder" % args.run_id)
                db.execute("INSERT INTO runs VALUES(?,?,?,?,?)", (args.run_id, "active", utcnow(), utcnow(), json.dumps(config)))
                active_same_holder = bool(
                    existing and existing["expires_at"] > now and
                    existing["holder"] == args.holder)
                fence = int(existing["fence"]) if active_same_holder else (
                    int(existing["fence"]) + 1 if existing else 1)
                db.execute("INSERT INTO leases(name,holder,expires_at,fence) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET holder=excluded.holder, expires_at=excluded.expires_at, fence=excluded.fence", (args.run_id, args.holder, expiry, fence))
            print_json({"run": args.run_id, "status": "active", "lease_holder": args.holder, "lease_expires_at": expiry, "fence": fence})
        elif args.command == "add-task":
            if args.builders not in (1, 2): raise ValueError("builders must be 1 or 2")
            canonical_globs, canonical_keys = validate_ownership(
                args.write_glob, args.conflict_key, allow_legacy_empty=False)
            auto_merge_paths = tuple(dict.fromkeys(
                canonical_path_glob(item) for item in args.auto_merge_glob))
            worktree = str(Path(args.worktree_path).resolve())
            if not Path(args.worktree_path).is_absolute():
                raise ValueError("worktree path must be absolute")
            if not Path(worktree).is_dir():
                raise ValueError("worktree path must exist")
            probe = subprocess.run(["git", "-C", worktree, "rev-parse", "--is-inside-work-tree"],
                                   capture_output=True, text=True)
            if probe.returncode != 0 or probe.stdout.strip() != "true":
                raise ValueError("worktree path must be a Git worktree")
            branch_check = subprocess.run(
                ["git", "check-ref-format", "--branch", args.target_branch],
                capture_output=True, text=True)
            if branch_check.returncode != 0:
                raise ValueError("target branch must be a valid explicit branch name")
            target_repository = github_repository(worktree)
            base_sha = github_target_oid(worktree, target_repository, args.target_branch)
            head_sha = subprocess.run(
                ["git", "-C", worktree, "rev-parse", "HEAD"], check=True,
                capture_output=True, text=True).stdout.strip()
            ancestor = subprocess.run(
                ["git", "-C", worktree, "merge-base", "--is-ancestor",
                 base_sha, head_sha], capture_output=True, text=True)
            if ancestor.returncode != 0:
                raise ValueError("authoritative GitHub target must be an ancestor of task HEAD")
            db.execute("BEGIN IMMEDIATE")
            require_lease(db, args.run_id, args.holder, args.fence)
            run = db.execute("SELECT * FROM runs WHERE id=?", (args.run_id,)).fetchone()
            if not run:
                raise ValueError("unknown run: %s" % args.run_id)
            sensitive_paths = configured_sensitive_paths(config_for(run))
            if db.execute("SELECT 1 FROM tasks WHERE run_id=? AND worktree_path=?",
                          (args.run_id, worktree)).fetchone():
                raise ValueError("worktree path is already owned by another task")
            db.execute("INSERT INTO tasks(id,run_id,title,stage,builder_count,updated_at,"
                       "write_globs_json,exclusive_keys_json,worktree_path,risk_declared,"
                       "base_sha,sensitive_paths_json,target_branch,target_repository,"
                       "auto_merge_paths_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (args.task_id,args.run_id,args.title,"strategy",args.builders,utcnow(),
                        json.dumps(canonical_globs),json.dumps(canonical_keys),worktree,
                        args.risk_tier, base_sha, json.dumps(sensitive_paths),
                        args.target_branch, target_repository,
                        json.dumps(auto_merge_paths)))
            db.commit()
            print_json({"task": args.task_id, "stage": "strategy"})
        elif args.command == "schedule":
            print_json({"dry_run": args.dry_run, "actions": plan(
                db, args.run_id, args.dry_run, args.holder, args.fence)})
        elif args.command == "complete":
            task = db.execute("SELECT run_id,stage FROM tasks WHERE id=?", (args.task_id,)).fetchone()
            if not task: raise ValueError("unknown task: %s" % args.task_id)
            print_json({"task":args.task_id,"result":complete(
                db,args.task_id,args.evidence,args.event_id,args.assignment_id,
                args.expected_stage,args.holder,args.fence)})
        elif args.command == "fail":
            task = db.execute("SELECT run_id,stage,approach FROM tasks WHERE id=?", (args.task_id,)).fetchone()
            if not task: raise ValueError("unknown task: %s" % args.task_id)
            print_json({"task":args.task_id,"result":fail(
                db,args.task_id,args.signature,args.evidence,args.event_id,args.assignment_id,
                args.expected_stage,args.holder,args.fence)})
        elif args.command == "merge":
            print_json({"task": args.task_id, "result": merge_task(
                db, args.task_id, args.assignment_id,
                args.holder, args.fence)})
        elif args.command == "checkpoint":
            if not 0 <= args.percent <= 100: raise ValueError("checkpoint must be 0..100")
            task = db.execute("SELECT stage,session FROM tasks WHERE id=?", (args.task_id,)).fetchone()
            if not task: raise ValueError("unknown task: %s" % args.task_id)
            require_lease(db, db.execute("SELECT run_id FROM tasks WHERE id=?", (args.task_id,)).fetchone()["run_id"], args.holder, args.fence)
            payload = {"summary": args.summary, "stage": task["stage"], "head": args.head, "fingerprint": args.fingerprint, "session": task["session"]}
            with db: db.execute("UPDATE tasks SET checkpoint=?,context_json=?,updated_at=? WHERE id=?",(args.percent,json.dumps(payload,sort_keys=True),utcnow(),args.task_id))
            print_json({"task":args.task_id,"checkpoint":args.percent,"context":payload})
        elif args.command == "status":
            run=db.execute("SELECT * FROM runs WHERE id=?",(args.run_id,)).fetchone();
            if not run: raise ValueError("unknown run: %s" % args.run_id)
            tasks = []
            for row in db.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY id", (args.run_id,)):
                item = dict(row); item.update(recovery(db, row)); tasks.append(item)
            print_json({"run":dict(run),"capacity":capacity(config_for(run)),"tasks":tasks,"events":[dict(x) for x in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY id",(args.run_id,))]})
        elif args.command == "acquire":
            acquired, fence = acquire(db,args.name,args.holder,args.seconds)
            print_json({"acquired":acquired,"fence":fence})
        elif args.command == "release": print_json({"released":release(db,args.name,args.holder)})
        elif args.command == "dispatch":
            if not args.dry_run and not args.cwd:
                raise ValueError("dispatch requires --cwd")
            project_root = Path(args.cwd).resolve() if args.cwd else None
            if project_root is not None and not project_root.is_dir():
                raise ValueError("dispatch cwd does not exist")
            project_common: Path | None = None
            if project_root is not None:
                probe = subprocess.run(["git", "-C", str(project_root), "rev-parse", "--git-common-dir"],
                                       capture_output=True, text=True)
                if probe.returncode != 0:
                    raise ValueError("dispatch cwd must be a Git checkout")
                common = Path(probe.stdout.strip())
                project_common = (project_root / common).resolve() if not common.is_absolute() else common.resolve()
            actions: list[dict[str, Any]] = []
            for planning_pass in range(2):
                wave = plan(db, args.run_id, args.dry_run, args.holder, args.fence)
                actions.extend(wave)
                administrative = any(
                    item["action"] in ("checkpoint", "rollover") for item in wave)
                if args.dry_run or not administrative or planning_pass == 1:
                    break
            root = Path(__file__).resolve().parents[1]
            commands = []
            seen_worktrees: set[str] = set()
            for action in actions:
                if action["action"] in ("checkpoint", "rollover"):
                    continue
                task_cwd = action.get("worktree_path")
                if not task_cwd:
                    raise ValueError("task %s has no isolated worktree path" % action["task"])
                resolved_task_cwd = str(Path(task_cwd).resolve())
                if project_root is not None and resolved_task_cwd == str(project_root):
                    raise ValueError("task worktree must differ from controller checkout")
                if resolved_task_cwd in seen_worktrees:
                    raise ValueError("parallel tasks cannot share a worktree")
                if not Path(resolved_task_cwd).is_dir():
                    raise ValueError("task worktree does not exist: %s" % resolved_task_cwd)
                task_probe = subprocess.run(
                    ["git", "-C", resolved_task_cwd, "rev-parse", "--git-common-dir"],
                    capture_output=True, text=True)
                if task_probe.returncode != 0:
                    raise ValueError("task cwd is not a Git worktree")
                task_common_raw = Path(task_probe.stdout.strip())
                task_common = ((Path(resolved_task_cwd) / task_common_raw).resolve()
                               if not task_common_raw.is_absolute() else task_common_raw.resolve())
                if project_common is not None and task_common != project_common:
                    raise ValueError("task worktree belongs to a different repository")
                seen_worktrees.add(resolved_task_cwd)
                bridge = root / "bin" / ("spawn-cx.sh" if action["provider"] == "codex" else "spawn-cc.sh")
                prefix = [] if args.execute else ["--dry-run"]
                cwd = str(project_root) if project_root else "<cwd>"
                allowlist_json = json.dumps(action["write_globs"], separators=(",", ":"))
                command = [str(bridge), *prefix, action["model"], action["effort"], cwd,
                           action["task"], action["stage"], resolved_task_cwd,
                           allowlist_json]
                commands.append({"task": action["task"], "action": action["stage"],
                                 "stage": action["stage"], "assignment_id": action["assignment_id"],
                                 "generation": action["generation"], "fence": action["fence"],
                                 "task_cwd": resolved_task_cwd, "bridge": command})
            if args.execute:
                db.execute("BEGIN IMMEDIATE")
                active_fence = require_lease(db, args.run_id, args.holder, args.fence)
                lease = db.execute("SELECT expires_at FROM leases WHERE name=?",
                                   (args.run_id,)).fetchone()
                expiry = dt.datetime.fromisoformat(lease["expires_at"])
                remaining = max(1, int((expiry - dt.datetime.now(dt.timezone.utc)).total_seconds()))
                heartbeat_seconds = max(2, remaining)
                heartbeat_interval = max(0.2, min(1.0, heartbeat_seconds / 3.0))
                now = utcnow()
                for item in commands:
                    cur = db.execute("UPDATE assignments SET status='running',updated_at=? "
                                     "WHERE id=? AND status='claimed'", (now, item["assignment_id"]))
                    if cur.rowcount != 1:
                        raise ValueError("assignment became stale before execution")
                db.commit()
                processes = []
                try:
                    for item in commands:
                        processes.append((item, subprocess.Popen(
                            item["bridge"], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)))
                except OSError as exc:
                    for _, process in processes:
                        process.terminate()
                    for _, process in processes:
                        process.communicate()
                    # All claims were marked running atomically. Charge each
                    # one as a failed attempt so no task is left permanently
                    # undispatchable after a partial spawn failure.
                    for item in commands:
                        fail(db, item["task"], "bridge-spawn-error",
                             str(exc), None, item["assignment_id"], item["stage"],
                             args.holder, args.fence)
                    raise ValueError("bridge spawn failed: %s" % exc) from exc
                failed = False
                with concurrent.futures.ThreadPoolExecutor(
                        max_workers=max(1, len(processes))) as pool:
                    drains = {process: pool.submit(process.communicate)
                              for _, process in processes}
                    next_heartbeat = time.monotonic() + heartbeat_interval
                    while any(not future.done() for future in drains.values()):
                        if time.monotonic() >= next_heartbeat:
                            if not renew_lease_same_fence(
                                    db, args.run_id, args.holder, active_fence,
                                    heartbeat_seconds):
                                for _, process in processes:
                                    if process.poll() is None:
                                        process.terminate()
                                for future in drains.values():
                                    future.result()
                                expire_dispatch_claims(
                                    db, args.run_id, args.holder, active_fence, commands)
                                raise ValueError(
                                    "lease heartbeat failed; worker results rejected")
                            next_heartbeat = time.monotonic() + heartbeat_interval
                        time.sleep(0.05)
                    outputs = {process: future.result()
                               for process, future in drains.items()}
                for item, process in processes:
                    stdout, stderr = outputs[process]
                    item["result"] = {"exit_code": process.returncode,
                                      "stdout": stdout, "stderr": stderr}
                    if process.returncode != 0:
                        failed = True
                        fail(db, item["task"], "bridge-exit-%d" % process.returncode,
                             stderr or stdout or "bridge failed without output", None,
                             item["assignment_id"], item["stage"], args.holder, args.fence)
                print_json({"dry_run": False, "commands": commands})
                if failed:
                    return 2
            else:
                print_json({"dry_run": args.dry_run, "commands": commands})
        return 0
    except (ValueError, sqlite3.IntegrityError, sqlite3.OperationalError,
            json.JSONDecodeError, OSError, TypeError) as exc:
        print("controller: " + str(exc), file=sys.stderr); return 2
    finally: db.close()


if __name__ == "__main__":
    raise SystemExit(main())
