"""Tests for bin/merge-gate.py, driven through a fake `gh` on PATH."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "merge-gate.py"
SHA = "a" * 40

FAKE_GH = textwrap.dedent("""\
    #!/usr/bin/env python3
    # Fake gh: answers from JSON fixtures in $FAKE_GH_DIR and logs every call.
    import json, os, sys
    d = os.environ["FAKE_GH_DIR"]
    args = sys.argv[1:]
    with open(os.path.join(d, "calls.log"), "a") as log:
        log.write(json.dumps(args) + "\\n")
    def emit(name):
        path = os.path.join(d, name)
        if not os.path.exists(path):
            sys.stderr.write("gh: Not Found (HTTP 404)\\n")
            sys.exit(1)
        sys.stdout.write(open(path).read())
    if args[:2] == ["pr", "view"]:
        emit("pr.json")
    elif args[:2] == ["repo", "view"]:
        sys.stdout.write("owner/repo\\n")
    elif args[:1] == ["api"]:
        emit("protection.json")
    elif args[:2] == ["pr", "checks"]:
        emit("checks.json")
        sys.exit(int(open(os.path.join(d, "checks.exit")).read()) if os.path.exists(os.path.join(d, "checks.exit")) else 0)
    elif args[:2] == ["pr", "merge"]:
        sys.stdout.write("merged\\n")
    else:
        sys.stderr.write("fake gh: unexpected call\\n")
        sys.exit(3)
""")


class MergeGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        self.env = dict(os.environ, FAKE_GH_DIR=str(self.dir),
                        PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
        self.write("pr.json", {"headRefOid": SHA, "baseRefName": "main", "state": "OPEN",
                               "isDraft": False,
                               "files": [{"path": "src/app/button.ts"},
                                         {"path": "tests/button.test.ts"}]})
        self.write("protection.json", {"contexts": ["ci"], "checks": [{"context": "ci"}]})
        self.write("checks.json", [{"name": "ci", "bucket": "pass"}])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, value: object) -> None:
        (self.dir / name).write_text(json.dumps(value))

    def run_gate(self, *extra: str) -> tuple[int, dict]:
        cmd = [sys.executable, str(SCRIPT), "--pr", "7", "--sha", SHA, "--tier", "2",
               "--allow", "src/**", "--allow", "tests/**", "--config", "/nonexistent", *extra]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=self.env, cwd=self.dir)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"not JSON (exit {proc.returncode}): {proc.stdout!r} {proc.stderr!r}")
        return proc.returncode, payload

    def calls(self) -> list[list[str]]:
        log = self.dir / "calls.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def test_all_conditions_met_says_merge(self) -> None:
        code, out = self.run_gate()
        self.assertEqual(code, 0, out)
        self.assertTrue(out["merge"])
        self.assertEqual(out["reasons"], [])
        self.assertFalse(any(c[:2] == ["pr", "merge"] for c in self.calls()))

    def test_merge_flag_merges_with_head_match(self) -> None:
        code, out = self.run_gate("--merge")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["merged"])
        merge = [c for c in self.calls() if c[:2] == ["pr", "merge"]]
        self.assertEqual(len(merge), 1)
        self.assertIn("--match-head-commit", merge[0])
        self.assertIn(SHA, merge[0])
        self.assertIn("--squash", merge[0])

    def test_head_differs_from_verified_sha(self) -> None:
        self.write("pr.json", {"headRefOid": "b" * 40, "baseRefName": "main", "state": "OPEN",
                               "isDraft": False, "files": [{"path": "src/a.ts"}]})
        code, out = self.run_gate("--merge")
        self.assertEqual(code, 1)
        self.assertFalse(out["merge"])
        self.assertTrue(any("head" in r for r in out["reasons"]))
        self.assertFalse(any(c[:2] == ["pr", "merge"] for c in self.calls()))

    def test_tier_three_never_merges(self) -> None:
        cmd_code, out = self.run_gate("--tier", "3")
        self.assertEqual(cmd_code, 1)
        self.assertTrue(any("tier 3" in r for r in out["reasons"]))

    def test_builtin_sensitive_path_blocks(self) -> None:
        self.write("pr.json", {"headRefOid": SHA, "baseRefName": "main", "state": "OPEN",
                               "isDraft": False,
                               "files": [{"path": "src/db/migrations/0042_add.sql"}]})
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(out["sensitive_paths"], ["src/db/migrations/0042_add.sql"])

    def test_configured_sensitive_path_blocks(self) -> None:
        code, out = self.run_gate("--sensitive", "src/app/**")
        self.assertEqual(code, 1)
        self.assertIn("src/app/button.ts", out["sensitive_paths"])

    def test_path_outside_allowlist_blocks(self) -> None:
        self.write("pr.json", {"headRefOid": SHA, "baseRefName": "main", "state": "OPEN",
                               "isDraft": False, "files": [{"path": "scripts/deploy.sh"}]})
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(out["unclassified_paths"], ["scripts/deploy.sh"])

    def test_empty_allowlist_blocks(self) -> None:
        cmd = [sys.executable, str(SCRIPT), "--pr", "7", "--sha", SHA, "--tier", "1",
               "--config", "/nonexistent"]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=self.env, cwd=self.dir)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any("allowlist" in r for r in json.loads(proc.stdout)["reasons"]))

    def test_config_file_supplies_allowlist_and_sensitive(self) -> None:
        cfg = self.dir / "config.toml"
        cfg.write_text('[merge]\nauto_merge_globs = ["src/**", "tests/**"]\n'
                       'sensitive_globs = ["tests/**"]\n')
        cmd = [sys.executable, str(SCRIPT), "--pr", "7", "--sha", SHA, "--tier", "1",
               "--config", str(cfg)]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=self.env, cwd=self.dir)
        out = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(out["sensitive_paths"], ["tests/button.test.ts"])

    def test_no_required_checks_blocks_by_default(self) -> None:
        (self.dir / "protection.json").unlink()
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertTrue(any("required" in r for r in out["reasons"]))

    def test_no_required_checks_allowed_with_explicit_flag(self) -> None:
        (self.dir / "protection.json").unlink()
        code, out = self.run_gate("--no-required-checks-ok")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["merge"])

    def test_failing_required_check_blocks(self) -> None:
        self.write("checks.json", [{"name": "ci", "bucket": "fail"}])
        (self.dir / "checks.exit").write_text("1")
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertTrue(any("ci" in r for r in out["reasons"]))

    def test_missing_required_check_blocks(self) -> None:
        self.write("checks.json", [{"name": "lint", "bucket": "pass"}])
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertTrue(any("ci" in r for r in out["reasons"]))

    def test_pending_required_check_blocks(self) -> None:
        self.write("checks.json", [{"name": "ci", "bucket": "pending"}])
        (self.dir / "checks.exit").write_text("8")
        code, out = self.run_gate()
        self.assertEqual(code, 1)

    def test_draft_or_closed_pr_blocks(self) -> None:
        self.write("pr.json", {"headRefOid": SHA, "baseRefName": "main", "state": "OPEN",
                               "isDraft": True, "files": [{"path": "src/a.ts"}]})
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertTrue(any("draft" in r for r in out["reasons"]))

    def test_invalid_glob_is_an_error(self) -> None:
        code, out = self.run_gate("--allow", "../escape/**")
        self.assertEqual(code, 2)
        self.assertFalse(out["merge"])


if __name__ == "__main__":
    unittest.main()
