"""Contract tests: pure transition tables plus fresh-process CLI replay."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from controller.transitions import Command, State, reduce_transition, semantic_identity


class ReducerContract(unittest.TestCase):
    def test_identity_table(self):
        base = Command("complete", '{"a":1,"b":2}')
        cases = [
            ("task", Command("complete", '{ "b": 2, "a": 1 }'), True),
            ("other", base, False),
            ("task", Command("fail", base.evidence, "A", stage_intent="strategy"), False),
            ("task", Command("complete", '{"a":2,"b":2}'), False),
            ("task", Command("complete", base.evidence, event_id="intent"), False),
        ]
        for task, command, equal in cases:
            with self.subTest(task=task, command=command):
                self.assertEqual(semantic_identity("task", base) ==
                                 semantic_identity(task, command), equal)
        first = Command("complete", "same", event_id="first")
        for evidence, event_id, equal in [("different", "first", True),
                                          ("same", "second", False)]:
            self.assertEqual(semantic_identity("task", first) == semantic_identity(
                "task", Command("complete", evidence, event_id=event_id)), equal)

    def test_completion_and_terminal_replay_table(self):
        command = Command("complete", "report")
        identity = semantic_identity("task", command)
        for stage, next_stage in [("strategy", "build"), ("build", "review"),
                                  ("review", "finalize"), ("finalize", "done")]:
            with self.subTest(stage=stage):
                state = State("task", stage)
                result = reduce_transition(state, command)
                self.assertEqual(result.state.stage, next_stage)
                self.assertEqual(state.stage, stage)  # input stays immutable
        for stage in ("strategy", "build", "review", "finalize", "done", "parked"):
            with self.subTest(replay_stage=stage):
                state = State("task", stage)
                result = reduce_transition(state, command, frozenset([identity]))
                self.assertEqual((result.result, result.state), ("deduplicated", state))
        for stage in ("done", "parked"):
            for operation in ("complete", "fail"):
                with self.subTest(terminal=stage, operation=operation):
                    with self.assertRaisesRegex(ValueError, "not active"):
                        reduce_transition(State("task", stage), Command(operation, "new", "A"))

    def test_failure_budget_and_signature_table(self):
        state, events, signatures = State("task", "strategy"), frozenset(), frozenset()
        cases = [
            ("A", "first", "failed", 1, 1, 1),
            ("B", "second", "failed", 2, 0, 2),
            ("A", "third", "deduplicated", 2, 0, None),
            ("C", "fourth", "failed", 2, 1, 1),
            ("D", "fifth", "parked", 2, 2, 2),
        ]
        for signature, event_id, result, approach, attempts, charged in cases:
            with self.subTest(signature=signature):
                command = Command("fail", "evidence", signature, event_id)
                decision = reduce_transition(state, command, events, signatures)
                self.assertEqual((decision.result, decision.state.approach,
                                  decision.state.attempts, decision.charged_attempt),
                                 (result, approach, attempts, charged))
                events |= frozenset([decision.identity])
                if decision.signature_key:
                    signatures |= frozenset([decision.signature_key])
                state = decision.state
        self.assertEqual(state.stage, "parked")
        self.assertEqual(len(signatures), 4)
        for signature, event_id, *_ in cases:
            command = Command("fail", "changed evidence", signature, event_id)
            self.assertEqual(reduce_transition(state, command, events, signatures).result,
                             "deduplicated")

    def test_signature_scope_is_task_and_stage_not_approach(self):
        known = frozenset([("task", "strategy", "full:signature:A")])
        for task, stage, approach, signature, expected in [
            ("task", "strategy", 1, "full:signature:A", "deduplicated"),
            ("task", "strategy", 2, "full:signature:A", "deduplicated"),
            ("other", "strategy", 1, "full:signature:A", "failed"),
            ("task", "build", 1, "full:signature:A", "failed"),
            ("task", "strategy", 1, "full:signature:B", "failed"),
        ]:
            with self.subTest(task=task, stage=stage, approach=approach, signature=signature):
                result = reduce_transition(State(task, stage, approach),
                                           Command("fail", "e", signature),
                                           seen_signatures=known)
                self.assertEqual(result.result, expected)

    def test_failure_stage_intent_and_terminal_replay_table(self):
        command = Command("fail", "same", "A")
        first = reduce_transition(State("task", "strategy"), command)
        known = frozenset([first.identity])
        for stage, expected in [("strategy", "deduplicated"), ("build", "failed"),
                                ("review", "failed"), ("finalize", "failed"),
                                ("done", "deduplicated"), ("parked", "deduplicated")]:
            with self.subTest(stage=stage):
                result = reduce_transition(State("task", stage), command, known)
                self.assertEqual(result.result, expected)
        for stage in ("done", "parked"):
            with self.assertRaisesRegex(ValueError, "not active"):
                reduce_transition(State("task", stage), Command("fail", "new", "A"), known)
        self.assertIsNone(command.stage_intent)  # reducer never mutates its input


class CLIContract(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.db = str(Path(self.work.name) / "state.sqlite3")
        self.project = Path(self.work.name) / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run(["git", "-C", str(self.project), "config", "user.email",
                        "controller@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.project), "config", "user.name",
                        "Controller Tests"], check=True)
        (self.project / "seed").write_text("seed\n")
        subprocess.run(["git", "-C", str(self.project), "add", "seed"], check=True)
        subprocess.run(["git", "-C", str(self.project), "commit", "-qm", "seed"], check=True)
        subprocess.run(["git", "-C", str(self.project), "branch", "-M", "main"], check=True)
        fakebin = Path(self.work.name) / "fakebin"
        fakebin.mkdir(exist_ok=True)
        gh = fakebin / "gh"
        gh.write_text("""#!/usr/bin/env bash
set -eu
sha=$(git rev-parse HEAD)
if [ \"$1 $2\" = \"repo view\" ]; then
  printf 'example/orchestratore\\n'
elif [ \"$1\" = \"api\" ]; then
  git rev-parse refs/heads/main
elif [ \"$1 $2\" = \"pr view\" ]; then
  state=OPEN; [ ! -e .gh-merged ] || state=MERGED
  printf '{\"headRefOid\":\"%s\",\"state\":\"%s\",\"baseRefName\":\"main\"}\\n' \"$sha\" \"$state\"
elif [ \"$1 $2\" = \"pr checks\" ]; then
  printf '[{\"name\":\"unit\",\"state\":\"SUCCESS\",\"link\":\"https://ci.invalid/unit\"}]\\n'
elif [ \"$1 $2\" = \"pr merge\" ]; then
  : > .gh-merged; printf 'merged\\n'
else exit 64
fi
""")
        gh.chmod(0o755)
        previous_path = os.environ["PATH"]
        os.environ["PATH"] = str(fakebin) + os.pathsep + previous_path
        self.addCleanup(lambda: os.environ.__setitem__("PATH", previous_path))
        self.worktrees = Path(self.work.name) / "worktrees"
        self.worktrees.mkdir()
        self.cli = os.environ.get("CONTROLLER_UNDER_TEST", str(
            Path(__file__).resolve().parents[1] / "bin/orchestratore-controller"))
        self.call("start", "run", "--seconds", "3600", "--config",
                  json.dumps({"sensitive_paths": ["security/**"]}))
        self.call("add-task", "run", "task", "contract", "--conflict-key", "task",
                  "--risk-tier", "2", "--auto-merge-glob", "src/task.py")

    def call(self, *args, ok=True):
        args = list(args)
        if args and args[0] == "add-task" and "--worktree-path" not in args:
            task_id = args[2]
            path = self.worktrees / task_id
            subprocess.run(["git", "-C", str(self.project), "worktree", "add", "-q",
                            "-b", "unit/%s" % task_id, str(path)], check=True)
            args += ["--worktree-path", str(path)]
        if args and args[0] == "add-task" and "--target-branch" not in args:
            args += ["--target-branch", "main"]
        if args and args[0] in ("complete", "fail") and "--assignment-id" not in args:
            task_id = args[1]
            with sqlite3.connect(self.db) as db:
                db.row_factory = sqlite3.Row
                task = db.execute("SELECT run_id,stage,generation,evidence_json FROM tasks WHERE id=?",
                                  (task_id,)).fetchone()
                assignment = db.execute(
                    "SELECT * FROM assignments WHERE task_id=? AND stage=? AND generation=? "
                    "AND status IN ('claimed','running')", (task_id, task["stage"], task["generation"])).fetchone()
            if assignment is None:
                preview = subprocess.run(
                    [self.cli, "--db", self.db, "schedule", task["run_id"], "--dry-run"],
                    check=True, capture_output=True, text=True)
                action = next((item for item in json.loads(preview.stdout)["actions"]
                               if item["task"] == task_id), None)
                if action is None:
                    defaults = {"strategy": ("claude", "sonnet", "medium"),
                                "build": ("codex", "gpt-5.6-terra", "medium"),
                                "review": ("claude", "opus", "medium"),
                                "finalize": ("codex", "gpt-5.6-luna", "medium")}
                    provider, model, effort = defaults[task["stage"]]
                    action = {"provider": provider, "model": model, "effort": effort,
                              "worktree_path": str(self.worktrees / task_id)}
                with sqlite3.connect(self.db) as db:
                    db.row_factory = sqlite3.Row
                    fence = db.execute("SELECT fence FROM leases WHERE name=?",
                                       (task["run_id"],)).fetchone()[0]
                    assignment_id = "unit-%s-%s-%d" % (task_id, task["stage"], task["generation"])
                    db.execute(
                        "INSERT INTO assignments(id,task_id,run_id,stage,generation,holder,fence,"
                        "provider,model,effort,worktree_path,status,created_at,updated_at) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))",
                        (assignment_id, task_id, task["run_id"], task["stage"], task["generation"],
                         "owner", fence, action["provider"], action["model"], action["effort"],
                         action["worktree_path"], "claimed"))
                    assignment = db.execute(
                        "SELECT * FROM assignments WHERE task_id=? AND stage=? AND generation=? "
                        "AND status IN ('claimed','running')", (task_id, task["stage"], task["generation"])).fetchone()
            args += ["--assignment-id", assignment["id"], "--expected-stage", task["stage"]]
            if args[0] == "complete":
                evidence_index = args.index("--evidence") + 1
                supplied = args[evidence_index]
                try:
                    parsed = json.loads(supplied)
                except json.JSONDecodeError:
                    parsed = None
                if parsed is None or (task["stage"] == "finalize" and
                                      not isinstance(parsed.get("pr") if isinstance(parsed, dict) else None, dict) and
                                      set(parsed or {}) >= {"pr", "merge", "docs"}):
                    if task["stage"] == "strategy":
                        value = {"summary": supplied, "plan_hash": "plan-" + task_id}
                    elif task["stage"] == "build":
                        sha = subprocess.run(
                            ["git", "-C", assignment["worktree_path"], "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
                        value = {"sha": sha, "gate": {"command": "unit", "exit_code": 0,
                                                              "output": supplied}}
                    elif task["stage"] == "review":
                        previous = json.loads(task["evidence_json"])
                        value = {"sha": previous["build"]["sha"], "verdict": "OK",
                                 "reviewer": {"provider": assignment["provider"],
                                              "model": assignment["model"]},
                                 "oracle": {"command": "reverse", "exit_code": 0,
                                            "output": "expected red"},
                                 "raw_output": supplied}
                    else:
                        previous = json.loads(task["evidence_json"])
                        sha = previous["review"]["sha"]
                        value = {"pr": {"number": 1, "sha": sha},
                                 "suggest_merge": True, "docs": True}
                    args[evidence_index] = json.dumps(value)
                if task["stage"] == "finalize":
                    previous = json.loads(task["evidence_json"])
                    sha = previous["review"]["sha"]
                    approved = json.dumps({
                        "pr": {"state": "approved-wait", "number": 1, "sha": sha},
                        "merge": {"state": "approved-wait", "sha": sha},
                        "docs": True, "suggest_merge": True,
                    })
                    finalized = subprocess.run(
                        [self.cli, "--db", self.db, "complete", task_id,
                         "--evidence", approved, "--assignment-id", assignment["id"],
                         "--expected-stage", "finalize", "--holder", "owner"],
                        capture_output=True, text=True)
                    self.assertEqual(finalized.returncode, 0, finalized.stderr)
                    scheduled = subprocess.run(
                        [self.cli, "--db", self.db, "schedule", task["run_id"],
                         "--holder", "owner"], capture_output=True, text=True)
                    self.assertEqual(scheduled.returncode, 0, scheduled.stderr)
                    next_assignment = next(
                        item for item in json.loads(scheduled.stdout)["actions"]
                        if item.get("task") == task_id)
                    args = ["merge", task_id, "--assignment-id",
                            next_assignment["assignment_id"]]
        proc = subprocess.run([self.cli, "--db", self.db, *args, "--holder", "owner"],
                              capture_output=True, text=True)
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        return proc

    def rows(self, query):
        with sqlite3.connect(self.db) as db:
            return db.execute(query).fetchall()

    def state(self):
        return self.rows("SELECT stage,approach,attempts FROM tasks WHERE id='task'")[0]

    def test_implicit_complete_replay(self):
        self.call("complete", "task", "--evidence", "same")
        before = self.rows("SELECT * FROM tasks")
        failed = subprocess.run([self.cli, "--db", self.db, "complete", "task",
                                 "--evidence", json.dumps({"summary": "same", "plan_hash": "p"}),
                                 "--assignment-id", "unit-task-strategy-0",
                                 "--expected-stage", "strategy", "--holder", "owner"],
                                capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("stale", failed.stderr)
        self.assertEqual(self.rows("SELECT * FROM tasks"), before)
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 1)

    def test_explicit_ids_distinguish_intent_and_replay_done(self):
        for event_id in ("strategy", "build", "review"):
            self.call("complete", "task", "--evidence", "same", "--event-id", event_id)
        final = '{"pr":"merged","merge":"merged","docs":true}'
        self.call("complete", "task", "--evidence", final, "--event-id", "final")
        self.assertEqual(self.state(), ("done", 1, 0))
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 5)

    def test_global_signatures_and_exact_budget(self):
        cases = [
            ("A", "a", "failed", ("strategy", 1, 1)),
            ("B", "b", "failed", ("strategy", 2, 0)),
            ("A", "a-again", "failed", ("strategy", 2, 1)),
            ("C", "c", "parked", ("parked", 2, 2)),
        ]
        for signature, event_id, result, expected in cases:
            with self.subTest(signature=signature, event_id=event_id):
                reply = self.call("fail", "task", signature, "--evidence", event_id,
                                  "--event-id", event_id)
                self.assertEqual(reply["result"], result)
                self.assertEqual(self.state(), expected)
        self.assertEqual(self.rows("SELECT approach,attempt FROM attempts ORDER BY id"),
                         [(1, 1), (1, 2), (2, 1), (2, 2)])
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 4)

    def test_implicit_failure_replay_after_parking(self):
        for signature in ("A", "B", "C", "D"):
            self.call("fail", "task", signature, "--evidence", "failure")
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 4)

    def test_same_signature_in_another_stage_counts_with_new_intent(self):
        self.call("fail", "task", "A", "--evidence", "failure", "--event-id", "s1")
        self.call("complete", "task", "--evidence", "strategy")
        reply = self.call("fail", "task", "A", "--evidence", "failure", "--event-id", "s2")
        self.assertEqual(reply["result"], "failed")
        self.assertEqual(self.state(), ("build", 1, 1))

    def test_implicit_failure_replay_and_cross_stage_intent(self):
        reply = self.call("fail", "task", "A", "--evidence", "failure")
        self.assertEqual(reply["result"], "failed")
        self.assertEqual(self.state(), ("strategy", 1, 1))
        self.call("complete", "task", "--evidence", "strategy")
        self.assertEqual(self.state(), ("build", 1, 0))
        reply = self.call("fail", "task", "A", "--evidence", "failure")
        self.assertEqual(reply["result"], "failed")
        self.assertEqual(self.state(), ("build", 1, 1))
        self.assertEqual(self.rows("SELECT stage,approach,attempt FROM attempts WHERE result='failed' ORDER BY id"),
                         [("strategy", 1, 1), ("build", 1, 1)])

    def test_implicit_final_completion_replay(self):
        for evidence in ("strategy", "build", "review"):
            self.call("complete", "task", "--evidence", evidence)
        self.call("complete", "task", "--evidence",
                  '{"pr":"merged","merge":"merged","docs":true}')
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 5)

    def test_replay_still_requires_valid_lease(self):
        self.call("complete", "task", "--evidence", "same", "--event-id", "id")
        for holder in ([], ["--holder", "wrong"]):
            proc = subprocess.run([self.cli, "--db", self.db, "complete", "task",
                                   "--evidence", "same", "--event-id", "id", *holder],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.state(), ("build", 1, 0))

    def test_lease_takeover_expires_claim_and_fences_late_result(self):
        first = self.call("schedule", "run")["actions"][0]
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE leases SET expires_at='2000-01-01T00:00:00+00:00' "
                       "WHERE name='run'")
        takeover = subprocess.run(
            [self.cli, "--db", self.db, "acquire", "run", "replacement",
             "--seconds", "3600"], capture_output=True, text=True)
        self.assertEqual(takeover.returncode, 0, takeover.stderr)
        fence = json.loads(takeover.stdout)["fence"]
        replacement = subprocess.run(
            [self.cli, "--db", self.db, "schedule", "run", "--holder", "replacement",
             "--fence", str(fence)], capture_output=True, text=True)
        self.assertEqual(replacement.returncode, 0, replacement.stderr)
        action = json.loads(replacement.stdout)["actions"][0]
        self.assertEqual(action["generation"], first["generation"] + 1)
        self.assertNotEqual(action["assignment_id"], first["assignment_id"])
        self.assertEqual(self.rows(
            "SELECT status,generation FROM assignments ORDER BY generation"),
            [("expired", 0), ("claimed", 1)])
        late = subprocess.run(
            [self.cli, "--db", self.db, "complete", "task", "--evidence",
             json.dumps({"summary": "late", "plan_hash": "late"}),
             "--assignment-id", first["assignment_id"], "--expected-stage", "strategy",
             "--holder", "owner", "--fence", str(first["fence"])],
            capture_output=True, text=True)
        self.assertNotEqual(late.returncode, 0)

    def test_ids_are_scoped_by_task_and_operation(self):
        self.call("fail", "task", "A", "--evidence", "failed", "--event-id", "shared")
        self.call("complete", "task", "--evidence", "ok", "--event-id", "shared")
        self.call("add-task", "run", "other", "contract", "--conflict-key", "other")
        self.call("complete", "other", "--evidence", "ok", "--event-id", "shared")
        self.assertEqual(self.rows("SELECT id,stage FROM tasks ORDER BY id"),
                         [("other", "build"), ("task", "build")])

    def test_milestone_profile_admits_five_builders_and_rejects_sixth(self):
        self.call("start", "milestones", "--config", '{"work_profile":"milestone"}')
        for number in range(1, 7):
            task = "milestone-%d" % number
            self.call("add-task", "milestones", task, task,
                      "--write-glob", "pkg/%d.py" % number)
        for number in range(1, 6):
            self.call("complete", "milestone-%d" % number, "--evidence", "strategy")
        failed = self.call("complete", "milestone-6", "--evidence", "strategy", ok=False)
        self.assertIn("max 5 active builders", failed.stderr)
        scheduled = self.call("schedule", "milestones", "--dry-run")
        self.assertEqual(sum(action["action"] == "build" for action in scheduled["actions"]), 5)

    def test_bug_fix_profile_admits_fifteen_builders_and_rejects_sixteenth(self):
        self.call("start", "bugs", "--config", '{"work_profile":"bugfix"}')
        for number in range(1, 17):
            task = "bug-%02d" % number
            self.call("add-task", "bugs", task, task,
                      "--write-glob", "bugs/%02d.py" % number)
        for number in range(1, 16):
            self.call("complete", "bug-%02d" % number, "--evidence", "strategy")
        failed = self.call("complete", "bug-16", "--evidence", "strategy", ok=False)
        self.assertIn("max 15 active builders", failed.stderr)
        scheduled = self.call("schedule", "bugs", "--dry-run")
        self.assertEqual(sum(action["action"] == "build" for action in scheduled["actions"]), 15)

    def test_review_pool_is_separate_proportional_and_prioritized(self):
        for run_id, profile, review_backlog, review_limit in (
                ("review-m", "milestone", 3, 2),
                ("review-b", "bugfix", 14, 5)):
            with self.subTest(profile=profile):
                self.call("start", run_id, "--config", json.dumps({"work_profile": profile}))
                for number in range(1, review_backlog + 1):
                    task = "%s-%d" % (run_id, number)
                    self.call("add-task", run_id, task, task,
                              "--write-glob", "%s/%d.py" % (run_id, number))
                    self.call("complete", task, "--evidence", "strategy")
                    self.call("complete", task, "--evidence", "build")
                build_task = "%s-build" % run_id
                self.call("add-task", run_id, build_task, build_task,
                          "--write-glob", "%s/build.py" % run_id)
                self.call("complete", build_task, "--evidence", "strategy")
                actions = self.call("schedule", run_id, "--dry-run")["actions"]
                reviews = [action for action in actions if action["action"] == "review"]
                self.assertEqual(len(reviews), review_limit)
                self.assertTrue(all(action["action"] == "review"
                                    for action in actions[:review_limit]))
                self.assertEqual(sum(action["action"] == "build" for action in actions), 0)

    def test_review_capacity_never_falls_to_zero_with_waiting_delivery(self):
        self.call("start", "one-review", "--config", '{"work_profile":"bugfix"}')
        self.call("add-task", "one-review", "delivery", "delivery",
                  "--write-glob", "src/delivery.py")
        self.call("complete", "delivery", "--evidence", "strategy")
        self.call("complete", "delivery", "--evidence", "build")
        actions = self.call("schedule", "one-review", "--dry-run")["actions"]
        self.assertEqual([(action["task"], action["action"]) for action in actions],
                         [("delivery", "review")])

    def test_review_capacity_weights_builder_count_of_waiting_deliveries(self):
        self.call("start", "weighted-review")
        for task in ("review-two-a", "review-two-b"):
            self.call("add-task", "weighted-review", task, task, "--builders", "2",
                      "--write-glob", "weighted/%s.py" % task)
            self.call("complete", task, "--evidence", "strategy")
            self.call("complete", task, "--evidence", "build")
        actions = self.call("schedule", "weighted-review", "--dry-run")["actions"]
        self.assertEqual(sum(action["action"] == "review" for action in actions), 2)

    def test_finalize_pool_remains_separate_when_review_backlog_pauses_builds(self):
        self.call("start", "separate-pools")
        for task in ("final", "review-a", "review-b", "build"):
            self.call("add-task", "separate-pools", task, task,
                      "--write-glob", "separate/%s.py" % task)
            self.call("complete", task, "--evidence", "strategy")
        self.call("complete", "final", "--evidence", "build")
        self.call("complete", "final", "--evidence", "review")
        self.call("complete", "review-a", "--evidence", "build")
        self.call("complete", "review-b", "--evidence", "build")
        actions = self.call("schedule", "separate-pools", "--dry-run")["actions"]
        self.assertIn(("final", "finalize"),
                      [(action["task"], action["action"]) for action in actions])
        self.assertFalse(any(action["action"] == "build" for action in actions))

    def test_schema_v1_database_migrates_write_ownership_column(self):
        legacy = str(Path(self.work.name) / "legacy.sqlite3")
        with sqlite3.connect(legacy) as db:
            db.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, context_json TEXT NOT NULL DEFAULT '{}', evidence_json TEXT NOT NULL DEFAULT '{}')")
            db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT INTO meta VALUES ('schema_version','1')")
        proc = subprocess.run([self.cli, "--db", legacy, "init"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["schema_version"], 8)
        with sqlite3.connect(legacy) as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(tasks)")}
            version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        self.assertIn("write_globs_json", columns)
        self.assertIn("exclusive_keys_json", columns)
        self.assertIn("auto_merge_paths_json", columns)
        self.assertEqual(version, "8")

    def test_write_ownership_blocks_overlap_but_allows_disjoint_builds(self):
        self.call("start", "ownership")
        self.call("add-task", "ownership", "owner-a", "a",
                  "--write-glob", "src/**")
        self.call("add-task", "ownership", "owner-b", "b",
                  "--write-glob", "src/api/*.py")
        self.call("add-task", "ownership", "owner-c", "c",
                  "--write-glob", "tests/*.py")
        self.call("complete", "owner-a", "--evidence", "strategy")
        failed = self.call("complete", "owner-b", "--evidence", "strategy", ok=False)
        self.assertIn("ownership or incompatibility conflicts with active build task owner-a", failed.stderr)
        self.call("complete", "owner-c", "--evidence", "strategy")
        actions = self.call("schedule", "ownership", "--dry-run")["actions"]
        self.assertEqual({action["task"] for action in actions if action["action"] == "build"},
                         {"owner-a", "owner-c"})

    def test_declared_incompatibility_key_blocks_disjoint_files(self):
        self.call("start", "interfaces")
        for task, path in (("schema-a", "api/a.py"), ("schema-b", "tests/b.py")):
            self.call("add-task", "interfaces", task, task,
                      "--write-glob", path, "--conflict-key", "public-api-v2")
        self.call("complete", "schema-a", "--evidence", "strategy")
        failed = self.call("complete", "schema-b", "--evidence", "strategy", ok=False)
        self.assertIn("ownership or incompatibility conflicts with active build task schema-a", failed.stderr)

    def test_new_task_requires_explicit_ownership(self):
        failed = self.call("add-task", "run", "unowned", "unowned", ok=False)
        self.assertIn("require --write-glob or --conflict-key ownership", failed.stderr)

    def test_conflict_keys_are_canonicalized_and_whitespace_is_rejected(self):
        failed = self.call("add-task", "run", "blank-key", "blank",
                           "--conflict-key", "   ", ok=False)
        self.assertIn("conflict key must not be empty or whitespace", failed.stderr)
        self.call("add-task", "run", "canonical-key", "canonical",
                  "--conflict-key", " public-api ",
                  "--conflict-key", "public-api")
        stored = self.rows(
            "SELECT exclusive_keys_json FROM tasks WHERE id='canonical-key'")[0][0]
        self.assertEqual(json.loads(stored), ["public-api"])

    def test_scheduler_rejects_corrupt_ownership_on_only_build(self):
        self.call("complete", "task", "--evidence", "strategy")
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE tasks SET write_globs_json=?, exclusive_keys_json='[]' "
                       "WHERE id='task'", (json.dumps(["src//shared/**"]),))
        failed = self.call("schedule", "run", "--dry-run", ok=False)
        self.assertIn("path glob must not contain empty path segments", failed.stderr)

    def test_scheduler_keeps_completely_empty_legacy_ownership_compatible(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE tasks SET write_globs_json='[]', exclusive_keys_json='[]' "
                       "WHERE id='task'")
        self.call("complete", "task", "--evidence", "strategy")
        actions = self.call("schedule", "run", "--dry-run")["actions"]
        self.assertEqual([action["task"] for action in actions], ["task"])

    def test_ambiguous_wildcard_overlap_is_serialized(self):
        self.call("start", "ambiguous-globs")
        self.call("add-task", "ambiguous-globs", "glob-a", "a",
                  "--write-glob", "src/a*bc")
        self.call("add-task", "ambiguous-globs", "glob-b", "b",
                  "--write-glob", "src/ab*c")
        self.call("complete", "glob-a", "--evidence", "strategy")
        failed = self.call("complete", "glob-b", "--evidence", "strategy", ok=False)
        self.assertIn("ownership or incompatibility conflicts", failed.stderr)

    def test_write_glob_input_rejects_ambiguous_or_non_relative_paths(self):
        invalid = ("/src/shared/**", "src/a/../shared/**", "src//shared/**",
                   "src\\shared\\**", "C:/src/shared/**", "src/shared/**/")
        for number, pattern in enumerate(invalid):
            with self.subTest(pattern=pattern):
                failed = self.call("add-task", "run", "invalid-glob-%d" % number,
                                   "invalid", "--write-glob", pattern, ok=False)
                self.assertIn("path glob must", failed.stderr)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM tasks WHERE id LIKE 'invalid-glob-%'")[0][0], 0)

    def test_auto_merge_glob_is_canonicalized_and_rejects_path_escape(self):
        self.call("add-task", "run", "auto-canonical", "auto canonical",
                  "--conflict-key", "auto-canonical",
                  "--auto-merge-glob", "./docs/./**",
                  "--auto-merge-glob", "docs/**")
        stored = self.rows(
            "SELECT auto_merge_paths_json FROM tasks WHERE id='auto-canonical'")[0][0]
        self.assertEqual(json.loads(stored), ["docs/**"])
        failed = self.call("add-task", "run", "auto-escape", "auto escape",
                           "--conflict-key", "auto-escape",
                           "--auto-merge-glob", "../security/**", ok=False)
        self.assertIn("path glob must", failed.stderr)
        self.assertEqual(self.rows(
            "SELECT COUNT(*) FROM tasks WHERE id='auto-escape'")[0][0], 0)

    def test_write_glob_is_canonicalized_before_persistence_and_comparison(self):
        self.call("start", "canonical-globs")
        self.call("add-task", "canonical-globs", "canonical-a", "a",
                  "--write-glob", "./src/./shared/**",
                  "--write-glob", "src/shared/**")
        stored = self.rows("SELECT write_globs_json FROM tasks WHERE id='canonical-a'")[0][0]
        self.assertEqual(json.loads(stored), ["src/shared/**"])
        self.call("add-task", "canonical-globs", "canonical-b", "b",
                  "--write-glob", "src/shared/**")
        self.call("complete", "canonical-a", "--evidence", "strategy")
        failed = self.call("complete", "canonical-b", "--evidence", "strategy", ok=False)
        self.assertIn("ownership or incompatibility conflicts", failed.stderr)

    def test_strategy_admission_is_atomic_across_processes(self):
        self.call("start", "atomic")
        for number in range(1, 7):
            task = "atomic-%d" % number
            self.call("add-task", "atomic", task, task,
                      "--write-glob", "atomic/%d.py" % number)
        for number in range(1, 5):
            self.call("complete", "atomic-%d" % number, "--evidence", "strategy")
        actions = self.call("schedule", "atomic")["actions"]
        assigned = {action["task"]: action for action in actions}
        commands = [[self.cli, "--db", self.db, "complete", task,
                     "--evidence", json.dumps({"summary": "strategy", "plan_hash": task}),
                     "--assignment-id", assigned[task]["assignment_id"],
                     "--expected-stage", "strategy", "--holder", "owner"]
                    for task in ("atomic-5", "atomic-6")]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True)
                     for command in commands]
        results = [process.communicate() + (process.returncode,) for process in processes]
        self.assertEqual(sorted(result[2] for result in results), [0, 2])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM tasks WHERE run_id='atomic' AND stage='build'")[0][0], 5)

    def test_execute_dispatch_launches_all_bridges_in_parallel_and_reports_failures(self):
        self.call("start", "parallel-dispatch")
        for number in range(1, 4):
            task = "parallel-%d" % number
            self.call("add-task", "parallel-dispatch", task, task,
                      "--write-glob", "parallel/%d.py" % number)
            self.call("complete", task, "--evidence", "strategy")
        project = Path(self.work.name) / "project"
        fakebin = Path(self.work.name) / "fakebin"
        sync = Path(self.work.name) / "sync"
        (project / ".orchestratore").mkdir(parents=True)
        fakebin.mkdir(exist_ok=True)
        sync.mkdir()
        (project / ".orchestratore" / "RUN.md").write_text("# RUN\n")
        fake = fakebin / "codex"
        fake.write_text("\n".join([
            "#!/usr/bin/env bash", "set -eu",
            "if [ \"${1:-}\" = plugin ] && [ \"${2:-}\" = list ]; then",
            "  printf '%%s\\n' '{\"installed\":[{\"pluginId\":\"orchestratore@orchestratore\",\"enabled\":true,\"installed\":true,\"installPath\":\"%s\"}]}'" % Path(__file__).resolve().parents[1],
            "  exit 0", "fi",
            "payload=$(cat)", "task=${payload#*Task: }", "task=${task%%$'\\n'*}",
            "touch \"$SYNC_DIR/$task\"", "for _ in $(seq 1 100); do",
            "  [ \"$(find \"$SYNC_DIR\" -type f | wc -l | tr -d ' ')\" -ge 3 ] && break",
            "  sleep 0.02", "done",
            "[ \"$(find \"$SYNC_DIR\" -type f | wc -l | tr -d ' ')\" -ge 3 ] || exit 70",
            "[ \"$task\" != parallel-2 ] || exit 17",
            "printf 'worker %s done\\n' \"$task\"", "",
        ]))
        fake.chmod(0o755)
        env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ["PATH"],
                   SYNC_DIR=str(sync))
        proc = subprocess.run([self.cli, "--db", self.db, "dispatch", "parallel-dispatch",
                               "--execute", "--cwd", str(project), "--holder", "owner"],
                              capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        reply = json.loads(proc.stdout)
        self.assertEqual(len(reply["commands"]), 3)
        codes = {item["task"]: item["result"]["exit_code"] for item in reply["commands"]}
        self.assertEqual(codes, {"parallel-1": 0, "parallel-2": 17, "parallel-3": 0},
                         (reply, [path.name for path in sync.iterdir()]))
        self.assertEqual(len(list(sync.iterdir())), 3)

    def test_profile_validation_and_legacy_default(self):
        failed = self.call("start", "invalid", "--config", '{"work_profile":"unknown"}',
                           ok=False)
        self.assertIn("work_profile must be milestone or bugfix", failed.stderr)
        proc = subprocess.run([self.cli, "--db", self.db, "status", "run"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        status = json.loads(proc.stdout)
        self.assertEqual(status["capacity"], {"builders": 5, "reviews": 2})


if __name__ == "__main__":
    unittest.main()
