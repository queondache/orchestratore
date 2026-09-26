"""Tests for bin/codex-task.sh, driven through a fake `codex` on PATH."""
from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "codex-task.sh"

# Fake codex: records argv, then applies $FAKE_CODEX_ACTION inside the -C dir.
FAKE_CODEX = textwrap.dedent("""\
    #!/usr/bin/env bash
    printf '%s\\n' "$@" > "$FAKE_CODEX_ARGS"
    cat > "$FAKE_CODEX_ARGS.stdin"
    dir=""; out=""
    while [ $# -gt 0 ]; do
      case "$1" in -C) dir="$2"; shift ;; -o) out="$2"; shift ;; esac
      shift
    done
    case "$FAKE_CODEX_ACTION" in
      write) echo "fixed" > "$dir/fix.txt" ;;
      modify) echo "tampered" >> "$dir/README" ;;
    esac
    [ -n "$out" ] && echo "DONE" > "$out"
    exit "${FAKE_CODEX_EXIT:-0}"
""")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


class CodexTaskTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "README").write_text("hello\n")
        git(self.repo, "add", "README")
        git(self.repo, "commit", "-qm", "init")
        self.brief = base / "briefs" / "U-1.md"
        self.brief.parent.mkdir()
        self.brief.write_text("# U-1\nFix it.\n")
        bin_dir = base / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "codex"
        fake.write_text(FAKE_CODEX)
        fake.chmod(0o755)
        self.args_file = base / "codex.args"
        self.env = dict(os.environ, FAKE_CODEX_ARGS=str(self.args_file),
                        PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_task(self, *args: str, action: str = "", exit_code: int = 0):
        env = dict(self.env, FAKE_CODEX_ACTION=action, FAKE_CODEX_EXIT=str(exit_code))
        return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True,
                              text=True, env=env)

    def test_build_commits_changes_and_reports_hash(self) -> None:
        before = git(self.repo, "rev-parse", "HEAD")
        proc = self.run_task("build", str(self.repo), str(self.brief), action="write")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        after = git(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(before, after)
        self.assertIn("hash=" + after, proc.stdout)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(self.args_file.with_suffix(".args.stdin").read_text(), "# U-1\nFix it.\n")

    def test_build_passes_model_effort_and_sandbox(self) -> None:
        proc = self.run_task("--model", "m-1", "--effort", "high", "--sandbox",
                             "danger-full-access", "build", str(self.repo), str(self.brief))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        argv = self.args_file.read_text().splitlines()
        self.assertEqual(argv[0], "exec")
        self.assertIn("m-1", argv)
        self.assertIn("model_reasoning_effort=high", argv)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", argv)

    def test_default_sandbox_is_workspace_write(self) -> None:
        self.run_task("build", str(self.repo), str(self.brief))
        argv = self.args_file.read_text().splitlines()
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")
        self.assertNotIn("-m", argv)

    def test_build_without_changes_keeps_head(self) -> None:
        before = git(self.repo, "rev-parse", "HEAD")
        proc = self.run_task("build", str(self.repo), str(self.brief))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), before)
        self.assertIn("no changes", proc.stdout)

    def test_codex_failure_is_propagated_without_commit(self) -> None:
        before = git(self.repo, "rev-parse", "HEAD")
        proc = self.run_task("build", str(self.repo), str(self.brief), action="write",
                             exit_code=5)
        self.assertEqual(proc.returncode, 5)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), before)

    def test_verify_that_modifies_tracked_files_is_a_violation(self) -> None:
        proc = self.run_task("verify", str(self.repo), str(self.brief), action="modify")
        self.assertEqual(proc.returncode, 3)
        self.assertIn("violation", proc.stdout + proc.stderr)

    def test_verify_clean_run_succeeds(self) -> None:
        proc = self.run_task("verify", str(self.repo), str(self.brief))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_dry_run_prints_command_without_running(self) -> None:
        proc = self.run_task("--dry-run", "build", str(self.repo), str(self.brief))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("codex exec", proc.stdout)
        self.assertFalse(self.args_file.exists())

    def test_rejects_dirty_worktree_before_running(self) -> None:
        (self.repo / "user-notes.txt").write_text("not mine\n")
        proc = self.run_task("build", str(self.repo), str(self.brief), action="write")
        self.assertEqual(proc.returncode, 65)
        self.assertFalse(self.args_file.exists())
        self.assertIn("user-notes.txt", git(self.repo, "status", "--porcelain"))

    def test_resume_accepts_task_owned_changes(self) -> None:
        (self.repo / "partial.txt").write_text("from a failed build\n")
        proc = self.run_task("--resume", "build", str(self.repo), str(self.brief), action="write")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertIn("partial.txt", git(self.repo, "show", "--name-only", "--format=", "HEAD"))

    def test_options_after_mode_are_accepted(self) -> None:
        proc = self.run_task("verify", "--model", "m-2", str(self.repo), str(self.brief))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("m-2", self.args_file.read_text().splitlines())

    def test_rejects_non_git_directory_and_bad_mode(self) -> None:
        self.assertEqual(self.run_task("build", self.tmp.name, str(self.brief)).returncode, 64)
        self.assertEqual(self.run_task("deploy", str(self.repo), str(self.brief)).returncode, 64)


if __name__ == "__main__":
    unittest.main()
