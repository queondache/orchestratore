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
        self.cli = os.environ.get("CONTROLLER_UNDER_TEST", str(
            Path(__file__).resolve().parents[1] / "bin/orchestratore-controller"))
        self.call("start", "run", "--seconds", "3600")
        self.call("add-task", "run", "task", "contract", "--conflict-key", "task")

    def call(self, *args, ok=True):
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
        self.call("complete", "task", "--evidence", "same")
        self.assertEqual(self.rows("SELECT * FROM tasks"), before)
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 1)

    def test_explicit_ids_distinguish_intent_and_replay_done(self):
        for event_id in ("strategy", "build", "review"):
            self.call("complete", "task", "--evidence", "same", "--event-id", event_id)
        final = '{"pr":"merged","merge":"merged","docs":true}'
        self.call("complete", "task", "--evidence", final, "--event-id", "final")
        for event_id in ("strategy", "build", "review", "final"):
            self.call("complete", "task", "--evidence", final, "--event-id", event_id)
        self.assertEqual(self.state(), ("done", 1, 0))
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 4)
        self.call("complete", "task", "--evidence", final, "--event-id", "new", ok=False)

    def test_global_signatures_and_exact_budget(self):
        cases = [
            ("A", "a", "failed", ("strategy", 1, 1)),
            ("B", "b", "failed", ("strategy", 2, 0)),
            ("A", "a-again", "deduplicated", ("strategy", 2, 0)),
            ("C", "c", "failed", ("strategy", 2, 1)),
            ("D", "d", "parked", ("parked", 2, 2)),
        ]
        for signature, event_id, result, expected in cases:
            with self.subTest(signature=signature, event_id=event_id):
                reply = self.call("fail", "task", signature, "--evidence", event_id,
                                  "--event-id", event_id)
                self.assertEqual(reply["result"], result)
                self.assertEqual(self.state(), expected)
        self.assertEqual(self.rows("SELECT approach,attempt FROM attempts ORDER BY id"),
                         [(1, 1), (1, 2), (2, 1), (2, 2)])
        for signature, event_id, _, _ in cases:
            reply = self.call("fail", "task", signature, "--evidence", "replay",
                              "--event-id", event_id)
            self.assertEqual(reply["result"], "deduplicated")
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 4)

    def test_implicit_failure_replay_after_parking(self):
        for signature in ("A", "B", "C", "D"):
            self.call("fail", "task", signature, "--evidence", "failure")
        for signature in ("A", "B", "C", "D"):
            reply = self.call("fail", "task", signature, "--evidence", "failure")
            self.assertEqual(reply["result"], "deduplicated")
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 4)

    def test_same_signature_in_another_stage_counts_with_new_intent(self):
        self.call("fail", "task", "A", "--evidence", "failure", "--event-id", "s1")
        self.call("complete", "task", "--evidence", "strategy")
        reply = self.call("fail", "task", "A", "--evidence", "failure", "--event-id", "s2")
        self.assertEqual(reply["result"], "failed")
        self.assertEqual(self.state(), ("build", 2, 0))

    def test_implicit_failure_replay_and_cross_stage_intent(self):
        for stage, expected in [("strategy", ("strategy", 1, 1)),
                                ("build", ("build", 2, 0))]:
            with self.subTest(stage=stage):
                reply = self.call("fail", "task", "A", "--evidence", "failure")
                self.assertEqual(reply["result"], "failed")
                self.assertEqual(self.state(), expected)
                before = self.rows("SELECT * FROM tasks")
                reply = self.call("fail", "task", "A", "--evidence", "failure")
                self.assertEqual(reply["result"], "deduplicated")
                self.assertEqual(self.rows("SELECT * FROM tasks"), before)
            if stage == "strategy":
                self.call("complete", "task", "--evidence", "strategy")
                self.call("complete", "task", "--evidence", "strategy")
                self.assertEqual(self.state(), ("build", 1, 1))
        self.assertEqual(self.rows("SELECT stage,approach,attempt FROM attempts WHERE result='failed' ORDER BY id"),
                         [("strategy", 1, 1), ("build", 1, 2)])

    def test_implicit_final_completion_replay(self):
        for evidence in ("strategy", "build", "review"):
            self.call("complete", "task", "--evidence", evidence)
        self.call("complete", "task", "--evidence",
                  '{"pr":"merged","merge":"merged","docs":true}')
        reply = self.call("complete", "task", "--evidence",
                          '{ "docs": true, "merge": "merged", "pr": "merged" }')
        self.assertEqual(reply["result"], "deduplicated")
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 4)

    def test_replay_still_requires_valid_lease(self):
        self.call("complete", "task", "--evidence", "same", "--event-id", "id")
        for holder in ([], ["--holder", "wrong"]):
            proc = subprocess.run([self.cli, "--db", self.db, "complete", "task",
                                   "--evidence", "same", "--event-id", "id", *holder],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.state(), ("build", 1, 0))

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
        self.assertEqual(json.loads(proc.stdout)["schema_version"], 2)
        with sqlite3.connect(legacy) as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(tasks)")}
            version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        self.assertIn("write_globs_json", columns)
        self.assertIn("exclusive_keys_json", columns)
        self.assertEqual(version, "2")

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
        self.assertIn("write glob must not contain empty path segments", failed.stderr)

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
                self.assertIn("write glob must", failed.stderr)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM tasks WHERE id LIKE 'invalid-glob-%'")[0][0], 0)

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
        commands = [[self.cli, "--db", self.db, "complete", task,
                     "--evidence", "strategy", "--holder", "owner"]
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
        fakebin.mkdir()
        sync.mkdir()
        (project / ".orchestratore" / "RUN.md").write_text("# RUN\n")
        fake = fakebin / "codex"
        fake.write_text("\n".join([
            "#!/usr/bin/env bash", "set -eu", "payload=$(cat)",
            "task=${payload#*sezione task }", "task=${task%%.*}",
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
