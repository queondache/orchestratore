"""Tests for bin/run-check.py: RUN.md stays one page with a fixed goal."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "run-check.py"

VALID = textwrap.dedent("""\
    # Orchestratore run — demo

    goal: fix the three login bugs
    status: active
    updated: 2026-09-30T18:00:00+02:00
    run: 20260930-1800
    next: verify U-2

    ## Units

    | ID | class | tier | write only | base | builder | state | hash | verdict | KO |
    |---|---|---|---|---|---|---|---|---|---|
    | U-1 | FIX | 2 | src/a.ts | abc1234 | sonnet | merged | def5678 | OK opus | 1 |
    | U-2 | FIX | 2 | src/b.ts | abc1234 | sonnet | verifying | 9876fed | | 0 |
    | U-3 | BUILD | 2 | src/c.ts | abc1234 | sonnet | parked | 1111111 | KO opus | 3 |

    ## Decisions

    ## Questions for the user

    ## Log

    18:01 U-1 merged as def5678 after one KO on a missing test.
    18:05 U-3 parked after its third KO; resume when the user picks a date format.
    """)


def run(text: str, *extra: str, goal_lock: str | None = None) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "RUN.md"
        path.write_text(text, encoding="utf-8")
        if goal_lock is not None:
            (Path(tmp) / "goal.lock").write_text(goal_lock, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(SCRIPT), "--run", str(path), *extra],
                              capture_output=True, text=True)
        out = json.loads(proc.stdout) if proc.stdout.strip() else {}
        out["_lock_after"] = ((Path(tmp) / "goal.lock").read_text(encoding="utf-8")
                              if (Path(tmp) / "goal.lock").exists() else None)
        return proc.returncode, out


def problems(out: dict) -> str:
    return " | ".join(out.get("problems", []))


class RunCheckTest(unittest.TestCase):
    def test_valid_page_passes(self):
        code, out = run(VALID)
        self.assertEqual(code, 0, out)
        self.assertTrue(out["ok"])

    def test_stacked_headers_fail(self):
        # The failure seen in real runs: a new header block prepended on each resume.
        stacked = VALID.replace("goal: fix", "status: parked\nnext: old step\n\n## Storico preservato\n\ngoal: fix", 1)
        code, out = run(stacked)
        self.assertEqual(code, 1)
        self.assertIn("status:", problems(out))
        self.assertIn("next:", problems(out))

    def test_second_title_fails(self):
        code, out = run(VALID + "\n# Orchestratore run — demo\n")
        self.assertEqual(code, 1)
        self.assertIn("title", problems(out))

    def test_missing_or_empty_goal_fails(self):
        code, out = run(VALID.replace("goal: fix the three login bugs\n", ""))
        self.assertEqual(code, 1)
        self.assertIn("goal:", problems(out))
        code, out = run(VALID.replace("goal: fix the three login bugs", "goal: "))
        self.assertEqual(code, 1)
        self.assertIn("goal:", problems(out))

    def test_unknown_status_fails(self):
        code, out = run(VALID.replace("status: active", "status: running"))
        self.assertEqual(code, 1)
        self.assertIn("status", problems(out))

    def test_third_ko_must_be_parked(self):
        code, out = run(VALID.replace("| parked | 1111111 | KO opus | 3 |", "| building | 1111111 | KO opus | 3 |"))
        self.assertEqual(code, 1)
        self.assertIn("U-3", problems(out))

    def test_ko_above_three_fails(self):
        code, out = run(VALID.replace("| KO opus | 3 |", "| KO opus | 4 |"))
        self.assertEqual(code, 1)
        self.assertIn("U-3", problems(out))

    def test_ko_not_a_number_fails(self):
        code, out = run(VALID.replace("| verifying | 9876fed | | 0 |", "| verifying | 9876fed | | many |"))
        self.assertEqual(code, 1)
        self.assertIn("U-2", problems(out))

    def test_missing_ko_column_fails(self):
        old = VALID.replace("| verdict | KO |", "| verdict |").replace("|---|---|---|---|---|---|---|---|---|---|",
                                                                    "|---|---|---|---|---|---|---|---|---|")
        code, out = run(old)
        self.assertEqual(code, 1)
        self.assertIn("KO column", problems(out))

    def test_log_must_be_last_section(self):
        code, out = run(VALID + "\n## 2026-09-30 — new block\n\nsomething\n")
        self.assertEqual(code, 1)
        self.assertIn("## Log", problems(out))

    def test_log_over_100_lines_fails(self):
        lines = "".join(f"18:{i % 60:02d} event {i}.\n" for i in range(101))
        code, out = run(VALID + lines)
        self.assertEqual(code, 1)
        self.assertIn("100", problems(out))

    def test_log_comments_and_blank_lines_do_not_count(self):
        filler = "<!-- note -->\n\n" * 120
        code, out = run(VALID + filler)
        self.assertEqual(code, 0, out)

    def test_record_goal_writes_lock(self):
        code, out = run(VALID, "--record-goal")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["_lock_after"].strip(), "fix the three login bugs")

    def test_goal_unchanged_against_lock_passes(self):
        code, out = run(VALID, goal_lock="fix the three login bugs\n")
        self.assertEqual(code, 0, out)

    def test_goal_changed_against_lock_fails(self):
        code, out = run(VALID.replace("fix the three login bugs", "ship everything"),
                        goal_lock="fix the three login bugs\n")
        self.assertEqual(code, 1)
        self.assertIn("goal changed", problems(out))

    def test_check_never_writes_the_lock(self):
        code, out = run(VALID)
        self.assertIsNone(out["_lock_after"])

    def test_missing_run_file_is_an_error(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--run", "/nonexistent/RUN.md"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
