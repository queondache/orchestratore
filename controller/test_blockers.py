"""Adversarial release blockers for the executable controller contract.

These are deliberately black-box CLI tests.  They describe the safety boundary
needed before the documented 5/15-way scheduler can be used with real Codex and
Claude processes.  A green transition-only suite is not enough: assignment,
isolation, evidence and routing must be enforced by the executable entrypoint.
"""
from __future__ import annotations

import json
import os
import datetime as dt
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from controller.path_policy import path_matches_glob


class BlockerContract(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.db = str(self.root / "controller.sqlite3")
        self.project = self.root / "project"
        (self.project / ".orchestratore").mkdir(parents=True)
        (self.project / ".orchestratore" / "RUN.md").write_text(
            "# Run\n\n## Registro task\n", encoding="utf-8")
        (self.project / "SPEC.md").write_text("# SPEC\n", encoding="utf-8")
        (self.project / "ROADMAP.md").write_text("# ROADMAP\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run(["git", "-C", str(self.project), "config", "user.email",
                        "blockers@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.project), "config", "user.name",
                        "Blocker Tests"], check=True)
        subprocess.run(["git", "-C", str(self.project), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.project), "commit", "-qm", "fixture"],
                       check=True)
        subprocess.run(["git", "-C", str(self.project), "branch", "-M", "main"],
                       check=True)
        fakebin = self.root / "fakebin"
        fakebin.mkdir()
        gh = fakebin / "gh"
        gh.write_text("""#!/usr/bin/env bash
set -eu
sha=$(git rev-parse HEAD)
if [ \"$1 $2\" = \"repo view\" ]; then
  printf 'example/orchestratore\\n'
elif [ \"$1\" = \"api\" ]; then
  git rev-parse refs/heads/main
elif [ \"$1 $2\" = \"pr view\" ]; then
  printf '{\"headRefOid\":\"%s\",\"state\":\"OPEN\",\"baseRefName\":\"main\"}\\n' \"$sha\"
elif [ \"$1 $2\" = \"pr checks\" ]; then
  printf '[{\"name\":\"unit\",\"state\":\"SUCCESS\",\"link\":\"https://ci.invalid/unit\"}]\\n'
else exit 64
fi
""")
        gh.chmod(0o755)
        previous_path = os.environ["PATH"]
        os.environ["PATH"] = str(fakebin) + os.pathsep + previous_path
        self.addCleanup(lambda: os.environ.__setitem__("PATH", previous_path))
        self.cli = os.environ.get(
            "CONTROLLER_UNDER_TEST",
            str(Path(__file__).resolve().parents[1] / "bin/orchestratore-controller"),
        )

    def raw(self, *args, holder=True, env=None, timeout=10):
        command = [self.cli, "--db", self.db, *args]
        if holder:
            command += ["--holder", "brain"]
        return subprocess.run(command, capture_output=True, text=True, env=env,
                              timeout=timeout)

    def call(self, *args, holder=True):
        result = self.raw(*args, holder=holder)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def reject(self, *args, holder=True):
        result = self.raw(*args, holder=holder)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def start(self, run_id="run", config=None):
        args = ["start", run_id, "--seconds", "3600"]
        if config is not None:
            args += ["--config", json.dumps(config)]
        return self.call(*args)

    def add(self, task_id, run_id="run", path=None, risk_tier=None,
            auto_merge_paths=None):
        worktree = self.root / "worktrees" / task_id
        worktree.parent.mkdir(exist_ok=True)
        subprocess.run(["git", "-C", str(self.project), "worktree", "add", "-q",
                        "-b", "test/%s" % task_id, str(worktree)], check=True)
        args = ["add-task", run_id, task_id, task_id,
                "--write-glob", path or "src/%s.py" % task_id,
                "--worktree-path", str(worktree), "--target-branch", "main"]
        if risk_tier is not None:
            args += ["--risk-tier", str(risk_tier)]
        for pattern in auto_merge_paths or ():
            args += ["--auto-merge-glob", pattern]
        return self.call(*args)

    def claim(self, task_id, run_id="run"):
        reply = self.call("dispatch", run_id, "--cwd", str(self.project))
        command = next(item for item in reply["commands"] if item["task"] == task_id)
        self.assertTrue(command.get("assignment_id"), command)
        self.assertIsInstance(command.get("generation"), int, command)
        self.assertTrue(command.get("fence"), command)
        return command

    def set_stage(self, task_id, stage):
        """Put routing tests at a stage without weakening completion tests."""
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE tasks SET stage=? WHERE id=?", (stage, task_id))

    def advance_to_merge(self, task_id, changed_path=None):
        worktree = self.root / "worktrees" / task_id
        if changed_path:
            target = worktree / changed_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("classified change\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(worktree), "add", changed_path], check=True)
            subprocess.run(["git", "-C", str(worktree), "commit", "-qm", "change"],
                           check=True)
        sha = subprocess.run(["git", "-C", str(worktree), "rev-parse", "HEAD"],
                             check=True, capture_output=True, text=True).stdout.strip()
        assignment = self.claim(task_id)
        self.call("complete", task_id, "--evidence", json.dumps({
            "summary": "plan", "plan_hash": "plan-v1",
        }), "--assignment-id", assignment["assignment_id"],
                  "--expected-stage", "strategy")
        assignment = self.claim(task_id)
        self.call("complete", task_id, "--evidence", json.dumps({
            "sha": sha, "gate": {"command": "unit", "exit_code": 0, "output": "ok"},
        }), "--assignment-id", assignment["assignment_id"],
                  "--expected-stage", "build")
        assignment = self.claim(task_id)
        with sqlite3.connect(self.db) as db:
            reviewer = db.execute(
                "SELECT provider,model FROM assignments WHERE id=?",
                (assignment["assignment_id"],)).fetchone()
        self.call("complete", task_id, "--evidence", json.dumps({
            "sha": sha, "verdict": "OK",
            "reviewer": {"provider": reviewer[0], "model": reviewer[1]},
            "oracle": {"command": "reverse", "exit_code": 0, "output": "red"},
            "raw_output": "independent review",
        }), "--assignment-id", assignment["assignment_id"],
                  "--expected-stage", "review")
        assignment = self.claim(task_id)
        self.call("complete", task_id, "--evidence", json.dumps({
            "pr": {"state": "approved-wait", "number": 7, "sha": sha},
            "merge": {"state": "approved-wait", "sha": sha},
            "docs": True, "suggest_merge": True,
        }), "--assignment-id", assignment["assignment_id"],
                  "--expected-stage", "finalize")
        return self.claim(task_id), sha

    def test_dry_run_and_execute_are_mutually_exclusive(self):
        self.start()
        self.add("t1")
        marker = self.root / "provider-was-run"
        fakebin = self.root / "fakebin"
        fakebin.mkdir(exist_ok=True)
        for executable in ("codex", "claude"):
            script = fakebin / executable
            script.write_text("#!/bin/sh\ntouch \"$BLOCKER_MARKER\"\nexit 0\n",
                              encoding="utf-8")
            script.chmod(0o755)
        env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ["PATH"],
                   BLOCKER_MARKER=str(marker))
        result = self.raw("dispatch", "run", "--dry-run", "--execute",
                          "--cwd", str(self.project), holder=False, env=env)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(marker.exists(), "invalid flag combination executed a provider")

    def test_dispatch_claim_is_idempotent(self):
        self.start()
        self.add("t1")
        first = self.call("dispatch", "run", "--cwd", str(self.project))
        second = self.call("dispatch", "run", "--cwd", str(self.project))
        self.assertEqual([item["task"] for item in first["commands"]], ["t1"])
        self.assertEqual(second["commands"], [],
                         "an unexpired assignment must not be dispatched twice")
        self.assertTrue(first["commands"][0].get("assignment_id"), first)

    def test_completion_without_assignment_is_rejected(self):
        self.start()
        self.add("t1")
        result = self.reject("complete", "t1", "--evidence", json.dumps({
            "stage": "strategy", "summary": "bounded strategy",
        }))
        self.assertIn("assignment", result.stderr.lower())

    def test_each_parallel_task_gets_a_distinct_worktree(self):
        self.start(config={"work_profile": "milestone"})
        for task in ("one", "two", "three"):
            self.add(task)
        reply = self.call("dispatch", "run", "--cwd", str(self.project))
        self.assertEqual(len(reply["commands"]), 3, reply)
        task_cwds = [item.get("task_cwd") for item in reply["commands"]]
        self.assertTrue(all(task_cwds), reply)
        self.assertEqual(len(set(task_cwds)), 3, task_cwds)
        self.assertNotIn(str(self.project), task_cwds,
                         "workers must not write in the controller checkout")
        for item in reply["commands"]:
            self.assertEqual(item["bridge"][-4:-1],
                             [item["task"], item["action"], item["task_cwd"]], item)
            self.assertEqual(json.loads(item["bridge"][-1]),
                             ["src/%s.py" % item["task"]], item)

    def test_same_worktree_cannot_be_owned_by_two_tasks(self):
        self.start()
        self.add("one")
        first_path = str(self.root / "worktrees" / "one")
        result = self.reject("add-task", "run", "two", "two",
                             "--write-glob", "src/two.py",
                             "--worktree-path", first_path,
                             "--target-branch", "main")
        self.assertIn("worktree", result.stderr.lower())

    def test_stale_assignment_result_is_rejected(self):
        self.start()
        self.add("t1")
        first = self.claim("t1")
        failed = self.call("fail", "t1", "transient", "--evidence", "worker failed",
                           "--assignment-id", first["assignment_id"],
                           "--expected-stage", "strategy")
        self.assertEqual(failed["result"], "failed")
        second = self.claim("t1")
        self.assertNotEqual(first["assignment_id"], second["assignment_id"])
        self.assertGreater(second["generation"], first["generation"])
        stale = self.reject("complete", "t1", "--evidence", json.dumps({
            "summary": "stale", "plan_hash": "plan-old",
        }), "--assignment-id", first["assignment_id"],
                            "--expected-stage", "strategy")
        self.assertIn("stale", stale.stderr.lower())
        with sqlite3.connect(self.db) as db:
            stage = db.execute("SELECT stage FROM tasks WHERE id='t1'").fetchone()[0]
        self.assertEqual(stage, "strategy")

    def test_stage_evidence_is_validated_before_every_transition(self):
        self.start(config={
            "brain_provider": "codex", "brain_model": "gpt-6-astra",
            "brain_effort": "medium",
            "strategy_provider": "claude", "strategy_model": "sonnet",
            "strategy_effort": "medium",
            "build_provider": "codex", "build_model": "gpt-5.6-terra",
            "build_effort": "medium",
            "review_provider": "claude", "review_model": "haiku",
            "review_effort": "medium",
            "finalize_provider": "codex", "finalize_model": "gpt-5.6-luna",
            "finalize_effort": "medium",
        })
        self.add("delivery")
        sha = subprocess.run(["git", "-C", str(self.project), "rev-parse", "HEAD"],
                             check=True, capture_output=True, text=True).stdout.strip()
        valid = {
            "strategy": {"summary": "bounded plan", "plan_hash": "plan-v1"},
            "build": {"sha": sha, "gate": {
                "command": "tests/unit", "exit_code": 0, "output": "12 passed",
            }},
            "review": {"sha": sha, "verdict": "OK",
                       "reviewer": {"provider": "claude", "model": "haiku"},
                       "oracle": {"command": "tests/unit --reverse", "exit_code": 0,
                                  "output": "expected red observed"},
                       "raw_output": "hash, gate, oracle and scope verified"},
            "finalize": {"pr": {"state": "approved-wait", "number": 7, "sha": sha},
                         "merge": {"state": "approved-wait", "sha": sha}, "docs": True,
                         "suggest_merge": True,
                         "external_attestation": {
                             "provider": "github", "verified": True, "sha": sha,
                             "verification_id": "check-run-7",
                             "verified_at": "2026-09-25T00:00:00Z",
                             "required_checks": [{"name": "ci", "status": "success",
                                                  "url": "https://ci.invalid/7"}]}},
        }
        for stage in ("strategy", "build", "review", "finalize"):
            with self.subTest(stage=stage):
                assignment = self.claim("delivery")
                self.assertEqual(assignment["action"], stage, assignment)
                invalid = self.reject("complete", "delivery", "--evidence", "{}",
                                      "--assignment-id", assignment["assignment_id"],
                                      "--expected-stage", stage)
                self.assertIn("evidence", invalid.stderr.lower())
                with sqlite3.connect(self.db) as db:
                    stored = db.execute(
                        "SELECT stage FROM tasks WHERE id='delivery'").fetchone()[0]
                self.assertEqual(stored, stage)
                reply = self.call("complete", "delivery", "--evidence",
                                  json.dumps(valid[stage]),
                                  "--assignment-id", assignment["assignment_id"],
                                  "--expected-stage", stage)
                self.assertIn(reply["result"], ("advanced", "completed", "approved-wait"), reply)

    def test_supported_runtime_matrices_route_every_stage(self):
        matrices = {
            "full-codex": {
                "brain_provider": "codex", "brain_model": "gpt-6-astra",
                "brain_effort": "medium",
                "strategy_provider": "codex", "strategy_model": "gpt-6-astra",
                "strategy_effort": "medium",
                "build_provider": "codex", "build_model": "gpt-5.6-terra",
                "build_effort": "medium",
                "review_provider": "codex", "review_model": "gpt-5.6-luna",
                "review_effort": "medium",
                "finalize_provider": "codex", "finalize_model": "gpt-5.6-sol",
                "finalize_effort": "low",
            },
            "full-claude": {
                "brain_provider": "claude", "brain_model": "fable",
                "brain_effort": "medium",
                "strategy_provider": "claude", "strategy_model": "sonnet",
                "strategy_effort": "medium",
                "build_provider": "claude", "build_model": "haiku",
                "build_effort": "medium",
                "review_provider": "claude", "review_model": "opus",
                "review_effort": "medium",
                "finalize_provider": "claude", "finalize_model": "sonnet",
                "finalize_effort": "medium",
            },
            "mixed": {
                "brain_provider": "codex", "brain_model": "gpt-6-astra",
                "brain_effort": "medium",
                "strategy_provider": "claude", "strategy_model": "sonnet",
                "strategy_effort": "medium",
                "build_provider": "codex", "build_model": "gpt-5.6-terra",
                "build_effort": "medium",
                "review_provider": "claude", "review_model": "haiku",
                "review_effort": "medium",
                "finalize_provider": "codex", "finalize_model": "gpt-5.6-luna",
                "finalize_effort": "medium",
            },
        }
        for run_id, config in matrices.items():
            with self.subTest(matrix=run_id):
                for stage in ("strategy", "build", "review", "finalize"):
                    stage_run = "%s-%s" % (run_id, stage)
                    self.start(stage_run, config)
                    task = "%s-%s" % (run_id, stage)
                    self.add(task, stage_run)
                    self.set_stage(task, stage)
                    actions = self.call("schedule", stage_run, "--dry-run")["actions"]
                    self.assertEqual(len(actions), 1, (stage_run, actions))
                    routed = actions[0]
                    self.assertEqual(routed["action"], stage)
                    self.assertEqual(routed["provider"],
                                     config[stage + "_provider"])
                    self.assertEqual(routed["model"], config[stage + "_model"])
                    self.assertEqual(routed["effort"], config[stage + "_effort"])

    def test_review_must_use_a_different_model_from_builder(self):
        same_model = {
            "brain_provider": "codex", "brain_model": "gpt-6-astra",
            "brain_effort": "medium",
            "strategy_provider": "codex", "strategy_model": "gpt-6-astra",
            "strategy_effort": "medium",
            "build_provider": "codex", "build_model": "gpt-5.6-terra",
            "build_effort": "medium",
            "review_provider": "codex", "review_model": "gpt-5.6-terra",
            "review_effort": "medium",
        }
        result = self.reject("start", "same-reviewer", "--seconds", "3600",
                             "--config", json.dumps(same_model))
        self.assertIn("review", result.stderr.lower())
        self.assertIn("model", result.stderr.lower())

    def test_fence_increments_after_expiry_even_for_same_holder(self):
        self.start()
        self.add("expiry")
        first = self.claim("expiry")
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE leases SET expires_at='2000-01-01T00:00:00+00:00' "
                       "WHERE name='run'")
        renewed = self.call("acquire", "run", "brain", "--seconds", "3600",
                            holder=False)
        self.assertGreater(renewed["fence"], first["fence"], renewed)
        replacement = self.claim("expiry")
        self.assertNotEqual(replacement["assignment_id"], first["assignment_id"])
        stale = self.reject(
            "complete", "expiry", "--evidence", json.dumps({
                "summary": "late result", "plan_hash": "old-plan",
            }), "--assignment-id", first["assignment_id"],
            "--expected-stage", "strategy", "--fence", str(renewed["fence"]),
        )
        self.assertIn("stale", stale.stderr.lower())

    def test_fence_survives_release_and_old_assignment_is_rejected(self):
        self.start()
        self.add("released")
        first = self.claim("released")
        released = self.call("release", "run", "brain", holder=False)
        self.assertTrue(released["released"])
        renewed = self.call("acquire", "run", "brain", "--seconds", "3600",
                            holder=False)
        self.assertGreater(renewed["fence"], first["fence"], renewed)
        replacement = self.claim("released")
        self.assertNotEqual(replacement["assignment_id"], first["assignment_id"])
        stale = self.reject(
            "complete", "released", "--evidence", json.dumps({
                "summary": "late result", "plan_hash": "old-plan",
            }), "--assignment-id", first["assignment_id"],
            "--expected-stage", "strategy", "--fence", str(renewed["fence"]),
        )
        self.assertIn("stale", stale.stderr.lower())

    def test_fable_is_brain_only_and_never_a_worker_route(self):
        valid = {
            "brain_provider": "claude", "brain_model": "fable",
            "brain_effort": "medium",
            "strategy_provider": "claude", "strategy_model": "sonnet",
            "strategy_effort": "medium",
            "build_provider": "claude", "build_model": "haiku",
            "build_effort": "medium",
            "review_provider": "claude", "review_model": "opus",
            "review_effort": "medium",
            "finalize_provider": "claude", "finalize_model": "sonnet",
            "finalize_effort": "medium",
        }
        self.start("fable-brain", valid)
        invalid = dict(valid, strategy_model="fable")
        result = self.reject("start", "fable-worker", "--seconds", "3600",
                             "--config", json.dumps(invalid))
        self.assertIn("stage", result.stderr.lower())
        self.assertIn("model", result.stderr.lower())

    def test_add_task_freezes_validated_risk_metadata(self):
        self.start()
        worktree = self.root / "worktrees" / "risk"
        worktree.parent.mkdir(exist_ok=True)
        subprocess.run(["git", "-C", str(self.project), "worktree", "add", "-q",
                        "-b", "test/risk", str(worktree)], check=True)
        self.call("add-task", "run", "risk", "risk", "--write-glob", "src/risk.py",
                  "--worktree-path", str(worktree), "--target-branch", "main",
                  "--risk-tier", "3")
        with sqlite3.connect(self.db) as db:
            row = db.execute(
                "SELECT risk_declared,target_branch,base_sha,target_repository,"
                "auto_merge_paths_json "
                "FROM tasks WHERE id='risk'").fetchone()
        self.assertEqual((row[0], row[1], row[3]),
                         (3, "main", "example/orchestratore"))
        self.assertRegex(row[2], r"^[0-9a-f]{40}$")
        self.assertEqual(json.loads(row[4]), [])
        worktree = self.root / "worktrees" / "bad-risk"
        subprocess.run(["git", "-C", str(self.project), "worktree", "add", "-q",
                        "-b", "test/bad-risk", str(worktree)], check=True)
        rejected = self.reject(
            "add-task", "run", "bad-risk", "bad-risk", "--write-glob", "src/x.py",
            "--worktree-path", str(worktree), "--target-branch", "main",
            "--risk-tier", "4")
        self.assertIn("invalid choice", rejected.stderr.lower())

    def test_sensitive_double_star_matches_root_and_nested_paths(self):
        self.assertTrue(path_matches_glob("secret.pem", "**/*.pem"))
        self.assertTrue(path_matches_glob("nested/deep/secret.pem", "**/*.pem"))
        self.assertFalse(path_matches_glob("nested/deep/secret.txt", "**/*.pem"))

    def test_declared_tier_can_only_raise_diff_risk(self):
        self.start(config={"sensitive_paths": ["security/**"]})
        self.add("declared-high", risk_tier=3)
        final, _ = self.advance_to_merge(
            "declared-high", changed_path="src/declared-high.py")
        rejected = self.reject(
            "merge", "declared-high", "--assignment-id", final["assignment_id"])
        self.assertIn("manual merge", rejected.stderr.lower())
        with sqlite3.connect(self.db) as db:
            evidence = json.loads(db.execute(
                "SELECT evidence_json FROM tasks WHERE id='declared-high'").fetchone()[0])
        classification = evidence["finalize"]["risk_classification"]
        self.assertEqual(classification["risk_tier"], 3)
        self.assertFalse(classification["sensitive"])

    def test_builtin_schema_and_migration_paths_are_always_tier_three(self):
        self.start(config={"sensitive_paths": ["custom-sensitive/**"]})
        self.add("migration", path="db/migrations/**", risk_tier=1)
        final, _ = self.advance_to_merge(
            "migration", changed_path="db/migrations/001_add_users.sql")
        rejected = self.reject(
            "merge", "migration", "--assignment-id", final["assignment_id"])
        self.assertIn("manual merge", rejected.stderr.lower())
        with sqlite3.connect(self.db) as db:
            evidence = json.loads(db.execute(
                "SELECT evidence_json FROM tasks WHERE id='migration'").fetchone()[0])
        classification = evidence["finalize"]["risk_classification"]
        self.assertEqual(classification["declared_tier"], 1)
        self.assertEqual(classification["risk_tier"], 3)
        self.assertEqual(classification["builtin_tier3_paths"],
                         ["db/migrations/001_add_users.sql"])

    def test_default_task_with_sensitive_diff_is_manual_only(self):
        self.start(config={"sensitive_paths": ["security/**"]})
        self.add("sensitive-default", path="security/secret.py")
        final, _ = self.advance_to_merge(
            "sensitive-default", changed_path="security/secret.py")
        rejected = self.reject(
            "merge", "sensitive-default", "--assignment-id", final["assignment_id"])
        self.assertIn("manual merge", rejected.stderr.lower())
        with sqlite3.connect(self.db) as db:
            evidence = json.loads(db.execute(
                "SELECT evidence_json FROM tasks WHERE id='sensitive-default'").fetchone()[0])
        classification = evidence["finalize"]["risk_classification"]
        self.assertFalse(classification["auto_merge"])
        self.assertTrue(classification["sensitive"])
        self.assertEqual(classification["matched_sensitive_paths"],
                         ["security/secret.py"])

    def test_documented_nested_sensitive_config_is_frozen_and_manual_only(self):
        self.start(config={
            "rischio": {"aree_sensibili": ["legal/**", "./legal/./**"]},
            "sensitive_paths": ["legacy-sensitive/**", "legal/**"],
        })
        self.add("nested-sensitive", path="legal/**", risk_tier=1,
                 auto_merge_paths=["legal/**"])
        final, _ = self.advance_to_merge(
            "nested-sensitive", changed_path="legal/contract.md")
        rejected = self.reject(
            "merge", "nested-sensitive", "--assignment-id", final["assignment_id"])
        self.assertIn("manual merge", rejected.stderr.lower())
        with sqlite3.connect(self.db) as db:
            row = db.execute(
                "SELECT sensitive_paths_json,evidence_json FROM tasks "
                "WHERE id='nested-sensitive'").fetchone()
        self.assertEqual(json.loads(row[0]), ["legal/**", "legacy-sensitive/**"])
        classification = json.loads(row[1])["finalize"]["risk_classification"]
        self.assertFalse(classification["auto_merge"])
        self.assertEqual(classification["matched_sensitive_paths"],
                         ["legal/contract.md"])

    def test_malformed_documented_sensitive_config_fails_closed(self):
        invalid = (
            {"rischio": []},
            {"rischio": {"aree_sensibili": "legal/**"}},
            {"rischio": {"aree_sensibili": ["legal/**", 7]}},
            {"rischio": {"aree_sensibili": ["../legal/**"]}},
            {"sensitive_paths": "legacy/**"},
        )
        for number, config in enumerate(invalid):
            with self.subTest(config=config):
                rejected = self.reject(
                    "start", "bad-sensitive-%d" % number, "--seconds", "3600",
                    "--config", json.dumps(config))
                self.assertTrue(
                    "must be" in rejected.stderr or "path glob must" in rejected.stderr,
                    rejected.stderr)

    def test_auto_merge_requires_explicit_frozen_path_allowlist(self):
        self.start()
        self.add("no-allowlist", path="src/no-allowlist.py", risk_tier=1)
        self.advance_to_merge(
            "no-allowlist", changed_path="src/no-allowlist.py")
        with sqlite3.connect(self.db) as db:
            evidence = json.loads(db.execute(
                "SELECT evidence_json FROM tasks WHERE id='no-allowlist'").fetchone()[0])
        classification = evidence["finalize"]["risk_classification"]
        self.assertFalse(classification["auto_merge"])
        self.assertEqual(classification["risk_tier"], 3)
        self.assertEqual(classification["auto_merge_paths"], [])
        self.assertEqual(classification["unclassified_paths"],
                         ["src/no-allowlist.py"])
        self.assertIn("no explicit auto-merge allowlist", classification["reason"])

    def test_auto_merge_allowlist_is_canonical_frozen_and_complete(self):
        self.start()
        self.add("allowlisted", path="src/allowed.py", risk_tier=2,
                 auto_merge_paths=["./src/./*.py", "src/*.py"])
        self.advance_to_merge("allowlisted", changed_path="src/allowed.py")
        with sqlite3.connect(self.db) as db:
            row = db.execute(
                "SELECT auto_merge_paths_json,evidence_json FROM tasks "
                "WHERE id='allowlisted'").fetchone()
        self.assertEqual(json.loads(row[0]), ["src/*.py"])
        classification = json.loads(row[1])["finalize"]["risk_classification"]
        self.assertTrue(classification["auto_merge"])
        self.assertEqual(classification["risk_tier"], 2)
        self.assertEqual(classification["unclassified_paths"], [])

    def test_any_path_outside_auto_merge_allowlist_forces_manual_tier_three(self):
        self.start()
        self.add("partial-allowlist", path="src/**", risk_tier=1,
                 auto_merge_paths=["src/allowed.py"])
        worktree = self.root / "worktrees" / "partial-allowlist"
        for relative in ("src/allowed.py", "docs/unclassified.md"):
            target = worktree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("change\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(worktree), "add", "src/allowed.py",
                        "docs/unclassified.md"], check=True)
        subprocess.run(["git", "-C", str(worktree), "commit", "-qm", "mixed"],
                       check=True)
        self.advance_to_merge("partial-allowlist")
        with sqlite3.connect(self.db) as db:
            evidence = json.loads(db.execute(
                "SELECT evidence_json FROM tasks WHERE id='partial-allowlist'").fetchone()[0])
        classification = evidence["finalize"]["risk_classification"]
        self.assertFalse(classification["auto_merge"])
        self.assertEqual(classification["risk_tier"], 3)
        self.assertEqual(classification["unclassified_paths"],
                         ["docs/unclassified.md"])

    def test_merge_rejects_classification_for_a_different_sha(self):
        self.start(config={"sensitive_paths": ["security/**"]})
        self.add("stale-classification", risk_tier=2)
        final, _ = self.advance_to_merge(
            "stale-classification", changed_path="src/stale-classification.py")
        with sqlite3.connect(self.db) as db:
            evidence = json.loads(db.execute(
                "SELECT evidence_json FROM tasks WHERE id='stale-classification'").fetchone()[0])
            evidence["finalize"]["risk_classification"]["sha"] = "f" * 40
            db.execute("UPDATE tasks SET evidence_json=? WHERE id='stale-classification'",
                       (json.dumps(evidence),))
        rejected = self.reject(
            "merge", "stale-classification", "--assignment-id", final["assignment_id"])
        self.assertIn("stale", rejected.stderr.lower())

    def test_controller_and_bridges_reject_the_same_invalid_efforts(self):
        codex = {
            "brain_provider": "codex", "brain_model": "gpt-6-astra",
            "brain_effort": "medium",
            "strategy_provider": "codex", "strategy_model": "gpt-6-astra",
            "strategy_effort": "xhigh",
            "build_provider": "codex", "build_model": "gpt-5.6-terra",
            "build_effort": "medium",
            "review_provider": "codex", "review_model": "gpt-5.6-sol",
            "review_effort": "low",
            "finalize_provider": "codex", "finalize_model": "gpt-5.6-luna",
            "finalize_effort": "medium",
        }
        self.assertIn("effort", self.reject(
            "start", "bad-codex-effort", "--seconds", "3600",
            "--config", json.dumps(codex)).stderr.lower())
        claude = {
            "brain_provider": "claude", "brain_model": "fable",
            "brain_effort": "medium",
            "strategy_provider": "claude", "strategy_model": "sonnet",
            "strategy_effort": "potato",
            "build_provider": "claude", "build_model": "haiku",
            "review_provider": "claude", "review_model": "opus",
            "finalize_provider": "claude", "finalize_model": "sonnet",
        }
        self.assertIn("effort", self.reject(
            "start", "bad-claude-effort", "--seconds", "3600",
            "--config", json.dumps(claude)).stderr.lower())

        self.start("bridge-efforts")
        self.add("bridge-efforts-task", "bridge-efforts")
        task_cwd = self.root / "worktrees" / "bridge-efforts-task"
        root = Path(__file__).resolve().parents[1]
        common = [str(self.project), "bridge-efforts-task", "build",
                  str(task_cwd), '["src/bridge-efforts-task.py"]']
        cx = subprocess.run(
            [str(root / "bin" / "spawn-cx.sh"), "--dry-run", "gpt-5.6-sol",
             "xhigh", *common], capture_output=True, text=True)
        cc = subprocess.run(
            [str(root / "bin" / "spawn-cc.sh"), "--dry-run", "haiku",
             "low", *common], capture_output=True, text=True)
        self.assertEqual(cx.returncode, 65, cx.stdout + cx.stderr)
        self.assertEqual(cc.returncode, 65, cc.stdout + cc.stderr)

    def test_finalize_model_differs_from_both_builder_and_reviewer(self):
        base = {
            "brain_provider": "codex", "brain_model": "gpt-6-astra",
            "brain_effort": "medium",
            "strategy_provider": "codex", "strategy_model": "gpt-6-astra",
            "strategy_effort": "medium",
            "build_provider": "codex", "build_model": "gpt-5.6-terra",
            "build_effort": "medium",
            "review_provider": "codex", "review_model": "gpt-5.6-sol",
            "review_effort": "low",
            "finalize_provider": "codex", "finalize_effort": "medium",
        }
        for run_id, model in (("finalize-builder", "gpt-5.6-terra"),
                              ("finalize-reviewer", "gpt-5.6-sol")):
            with self.subTest(run_id=run_id):
                result = self.reject(
                    "start", run_id, "--seconds", "3600", "--config",
                    json.dumps(dict(base, finalize_model=model)))
                self.assertIn("finalize", result.stderr.lower())

    def test_merged_finalize_reconciles_sha_and_required_checks_with_github(self):
        config = {
            "brain_provider": "codex", "brain_model": "gpt-6-astra",
            "brain_effort": "medium",
            "strategy_provider": "claude", "strategy_model": "sonnet",
            "strategy_effort": "medium",
            "build_provider": "codex", "build_model": "gpt-5.6-terra",
            "build_effort": "medium",
            "review_provider": "claude", "review_model": "opus",
            "review_effort": "medium",
            "finalize_provider": "codex", "finalize_model": "gpt-5.6-luna",
            "finalize_effort": "medium",
            "sensitive_paths": ["security/**"],
        }
        self.start(config=config)
        self.add("github", risk_tier=2,
                 auto_merge_paths=["src/github.py"])
        sha = subprocess.run(["git", "-C", str(self.project), "rev-parse", "HEAD"],
                             check=True, capture_output=True, text=True).stdout.strip()
        strategy = self.claim("github")
        self.call("complete", "github", "--evidence", json.dumps({
            "summary": "plan", "plan_hash": "plan-v1",
        }), "--assignment-id", strategy["assignment_id"],
                  "--expected-stage", "strategy")
        build = self.claim("github")
        self.call("complete", "github", "--evidence", json.dumps({
            "sha": sha, "gate": {"command": "unit", "exit_code": 0,
                                    "output": "ok"},
        }), "--assignment-id", build["assignment_id"], "--expected-stage", "build")
        review = self.claim("github")
        self.call("complete", "github", "--evidence", json.dumps({
            "sha": sha, "verdict": "OK",
            "reviewer": {"provider": "claude", "model": "opus"},
            "oracle": {"command": "reverse", "exit_code": 0, "output": "red"},
            "raw_output": "independent review",
        }), "--assignment-id", review["assignment_id"], "--expected-stage", "review")
        final = self.claim("github")
        invented = {
            "pr": {"state": "merged", "number": 7, "sha": "f" * 40},
            "merge": {"state": "merged", "sha": "f" * 40}, "docs": True,
            "external_attestation": {
                "provider": "github", "verified": True, "sha": "f" * 40,
                "verification_id": "invented", "verified_at": "now",
                "required_checks": [{"name": "ci", "status": "success",
                                     "url": "https://example.invalid/fake"}],
            },
        }
        rejected = self.reject(
            "complete", "github", "--evidence", json.dumps(invented),
            "--assignment-id", final["assignment_id"], "--expected-stage", "finalize")
        self.assertIn("sha", rejected.stderr.lower())
        approved = {
            "pr": {"state": "approved-wait", "number": 7, "sha": sha},
            "merge": {"state": "approved-wait", "sha": sha},
            "docs": True, "suggest_merge": True,
        }
        self.call("complete", "github", "--evidence", json.dumps(approved),
                  "--assignment-id", final["assignment_id"],
                  "--expected-stage", "finalize")
        final = self.claim("github")

        fakebin = self.root / "github-bin"
        fakebin.mkdir()
        marker = self.root / "gh-calls.log"
        gh = fakebin / "gh"
        gh.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$GH_MARKER\"\n"
            "if [ \"$1 $2\" = 'repo view' ]; then\n"
            "  printf 'example/orchestratore\\n'\n"
            "elif [ \"$1\" = api ]; then\n"
            "  printf '%s\\n' \"${GH_REMOTE_BASE:-$(git rev-parse refs/heads/main)}\"\n"
            "elif [ \"$1 $2\" = 'pr view' ]; then\n"
            "  state=OPEN; [ ! -e \"$GH_MERGED\" ] || state=MERGED\n"
            "  if [ \"$state\" = MERGED ] && [ -n \"${GH_FAIL_POST_ONCE:-}\" ] && [ ! -e \"$GH_FAILED_POST\" ]; then : > \"$GH_FAILED_POST\"; exit 1; fi\n"
            "  printf '{\"headRefOid\":\"%s\",\"state\":\"%s\",\"baseRefName\":\"%s\"}\\n' \"$GH_SHA\" \"$state\" \"${GH_BASE:-main}\"\n"
            "elif [ \"$1 $2\" = 'pr checks' ]; then\n"
            "  [ -z \"${GH_FAIL_CHECKS:-}\" ] || exit 1\n"
            "  printf '[{\"name\":\"ci\",\"state\":\"SUCCESS\",\"link\":\"https://ci.invalid/7\"}]\\n'\n"
            "elif [ \"$1 $2\" = 'pr merge' ]; then\n"
            "  : > \"$GH_MERGED\"; printf 'merged\\n'\n"
            "else exit 64; fi\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ["PATH"],
                   GH_MARKER=str(marker), GH_SHA=sha,
                   GH_MERGED=str(self.root / "merged.marker"),
                   GH_FAILED_POST=str(self.root / "failed-post.marker"))
        wrong_base = self.raw(
            "merge", "github", "--assignment-id", final["assignment_id"],
            env=dict(env, GH_BASE="attacker-branch"))
        self.assertNotEqual(wrong_base.returncode, 0)
        self.assertIn("base", wrong_base.stderr.lower())
        self.assertNotIn("pr merge", marker.read_text(encoding="utf-8"))
        marker.unlink()
        moved_oid = subprocess.run(
            ["git", "-C", str(self.project), "commit-tree", "HEAD^{tree}", "-p", "HEAD",
             "-m", "remote moved"], check=True, capture_output=True, text=True).stdout.strip()
        moved_target = self.raw(
            "merge", "github", "--assignment-id", final["assignment_id"],
            env=dict(env, GH_REMOTE_BASE=moved_oid))
        self.assertNotEqual(moved_target.returncode, 0)
        self.assertIn("target branch moved", moved_target.stderr.lower())
        self.assertNotIn("pr merge", marker.read_text(encoding="utf-8"))
        self.assertFalse(Path(env["GH_MERGED"]).exists())
        marker.unlink()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE tasks SET risk_declared=3 WHERE id='github'")
        high_risk = self.raw(
            "merge", "github", "--assignment-id", final["assignment_id"], env=env)
        self.assertNotEqual(high_risk.returncode, 0)
        self.assertIn("stale", high_risk.stderr.lower())
        self.assertFalse(marker.exists())
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE tasks SET risk_declared=2 WHERE id='github'")
        failed_env = dict(env, GH_FAIL_CHECKS="1")
        rejected = self.raw(
            "merge", "github", "--assignment-id", final["assignment_id"],
            env=failed_env)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertNotIn("pr merge", marker.read_text(encoding="utf-8"))
        marker.write_text("", encoding="utf-8")
        uncertain_env = dict(env, GH_FAIL_POST_ONCE="1")
        uncertain = self.raw(
            "merge", "github", "--assignment-id", final["assignment_id"],
            env=uncertain_env)
        self.assertNotEqual(uncertain.returncode, 0)
        self.assertTrue(Path(env["GH_MERGED"]).exists())
        result = self.raw(
            "merge", "github", "--assignment-id", final["assignment_id"],
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = marker.read_text(encoding="utf-8")
        self.assertIn("pr view 7", calls)
        self.assertIn("pr checks 7 --required", calls)
        self.assertIn("pr merge 7 --squash", calls)
        self.assertEqual(calls.count("pr merge 7 --squash"), 1)

    def test_rollover_resets_checkpoint_emission_for_the_next_session(self):
        self.start()
        self.add("context")
        self.call("checkpoint", "context", "50", "--summary", "first")
        first = self.call("schedule", "run")
        self.assertEqual(first["actions"][0]["action"], "checkpoint")
        self.call("checkpoint", "context", "70", "--summary", "rollover")
        rollover = self.call("schedule", "run")
        self.assertEqual(rollover["actions"][0]["action"], "rollover")
        self.call("checkpoint", "context", "50", "--summary", "second")
        second = self.call("schedule", "run")
        self.assertEqual(second["actions"][0]["action"], "checkpoint")
        with sqlite3.connect(self.db) as db:
            session = db.execute(
                "SELECT session FROM tasks WHERE id='context'").fetchone()[0]
        self.assertEqual(session, 2)

    def test_dispatch_replans_once_after_rollover(self):
        self.start()
        self.add("rollover-dispatch")
        self.call("checkpoint", "rollover-dispatch", "70", "--summary", "boundary")
        reply = self.call("dispatch", "run", "--cwd", str(self.project))
        self.assertEqual([item["task"] for item in reply["commands"]],
                         ["rollover-dispatch"])
        self.assertEqual(reply["commands"][0]["stage"], "strategy")
        with sqlite3.connect(self.db) as db:
            session = db.execute(
                "SELECT session FROM tasks WHERE id='rollover-dispatch'").fetchone()[0]
        self.assertEqual(session, 2)

    def test_execute_heartbeats_short_lease_while_worker_lives(self):
        config = {
            "brain_provider": "codex", "brain_model": "gpt-6-astra",
            "brain_effort": "medium",
            "strategy_provider": "codex", "strategy_model": "gpt-6-astra",
            "strategy_effort": "medium",
            "build_provider": "codex", "build_model": "gpt-5.6-terra",
            "build_effort": "medium",
            "review_provider": "codex", "review_model": "gpt-5.6-sol",
            "review_effort": "low",
            "finalize_provider": "codex", "finalize_model": "gpt-5.6-luna",
            "finalize_effort": "medium",
        }
        self.call("start", "heartbeat", "--seconds", "2",
                  "--config", json.dumps(config))
        self.add("slow", "heartbeat")
        renewed = self.raw("acquire", "heartbeat", "brain", "--seconds", "2",
                           holder=False)
        self.assertEqual(renewed.returncode, 0, renewed.stderr)
        fakebin = self.root / "heartbeat-bin"
        fakebin.mkdir()
        codex = fakebin / "codex"
        codex.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = plugin ]; then "
            "printf '%%s\\n' '{\"installed\":[{\"pluginId\":\"orchestratore@orchestratore\",\"enabled\":true,\"installed\":true,\"installPath\":\"%s\"}]}'; exit 0; fi\n" %
            Path(__file__).resolve().parents[1] +
            "sleep 3\ncat\n", encoding="utf-8")
        codex.chmod(0o755)
        before = dt.datetime.now(dt.timezone.utc)
        env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ["PATH"])
        result = self.raw("dispatch", "heartbeat", "--execute", "--cwd",
                          str(self.project), env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        with sqlite3.connect(self.db) as db:
            expiry = db.execute(
                "SELECT expires_at FROM leases WHERE name='heartbeat'").fetchone()[0]
        self.assertGreater(dt.datetime.fromisoformat(expiry), before + dt.timedelta(seconds=2))

    def test_successful_completion_replay_is_idempotent(self):
        self.start()
        self.add("replay")
        assignment = self.claim("replay")
        evidence = json.dumps({"summary": "plan", "plan_hash": "plan-v1"})
        args = ("complete", "replay", "--evidence", evidence,
                "--event-id", "strategy-result-1",
                "--assignment-id", assignment["assignment_id"],
                "--expected-stage", "strategy")
        first = self.call(*args)
        replay = self.call(*args)
        self.assertEqual(first["result"], "advanced")
        self.assertEqual(replay["result"], "deduplicated")
        with sqlite3.connect(self.db) as db:
            attempts = db.execute(
                "SELECT COUNT(*) FROM attempts WHERE task_id='replay'").fetchone()[0]
        self.assertEqual(attempts, 1)


if __name__ == "__main__":
    unittest.main()
