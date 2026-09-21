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
        self.call("add-task", "run", "task", "contract")

    def call(self, *args, ok=True):
        proc = subprocess.run([self.cli, "--db", self.db, *args, "--holder", "owner"],
                              capture_output=True, text=True)
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, 0, proc.stdout)

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
        self.call("add-task", "run", "other", "contract")
        self.call("complete", "other", "--evidence", "ok", "--event-id", "shared")
        self.assertEqual(self.rows("SELECT id,stage FROM tasks ORDER BY id"),
                         [("other", "build"), ("task", "build")])


if __name__ == "__main__":
    unittest.main()
