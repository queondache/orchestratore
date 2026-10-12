"""Tests for bin/run-check.py: RUN.md stays one page with a fixed goal."""
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
SCRIPT = ROOT / "bin" / "run-check.py"

VALID = textwrap.dedent("""\
    # Orchestratore run — demo

    goal: fix the three login bugs
    status: active
    updated: 2026-09-30T18:00:00+02:00
    run: 20260930-1800
    builder: sonnet        verifier: gpt-6-luna (tier 1-2), opus (tier 3)
    next: verify U-2

    ## Units

    | ID | class | tier | write only | base | builder | state | hash | verdict | KO |
    |---|---|---|---|---|---|---|---|---|---|
    | U-1 | FIX | 2 | src/a.ts | abc1234 | sonnet | merged | def5678 | OK opus | 1 |
    | U-2 | FIX | 2 | src/b.ts | abc1234 | sonnet | verifying | 9876fed | | 0 |
    | U-3 | BUILD | 2 | src/c.ts | abc1234 | sonnet | parked | 1111111 | KO opus | 2 |

    ## Decisions

    ## Questions for the user

    ## Log

    18:01 U-1 merged as def5678 after one KO on a missing test.
    18:05 U-3 parked after its second KO; resume when the user picks a date format.
    """)


# 2026-09-30T18:00:00+02:00, the `updated:` of VALID: the page counts as written then.
VALID_WRITTEN = 1790784000


def run(text: str, *extra: str, goal_lock: str | None = None,
        written: float = VALID_WRITTEN) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "RUN.md"
        path.write_text(text, encoding="utf-8")
        os.utime(path, (written, written))
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

    def test_done_with_a_parked_unit_fails(self):
        code, out = run(VALID.replace("status: active", "status: done"))
        self.assertEqual(code, 1)
        self.assertIn("status is done", problems(out))
        self.assertIn("U-3", problems(out))

    def test_done_with_every_unit_merged_or_in_production_passes(self):
        text = (VALID.replace("status: active", "status: done\npipeline: none")
                .replace("| verifying | 9876fed | | 0 |", "| in production | 9876fed | OK opus | 0 |")
                .replace("| U-3 | BUILD | 2 | src/c.ts | abc1234 | sonnet | parked | 1111111 | KO opus | 2 |\n", ""))
        code, out = run(text)
        self.assertEqual(code, 0, out)

    def test_done_with_merged_unit_but_a_deploy_pipeline_fails(self):
        text = (VALID.replace("status: active", "status: done\npipeline: vercel   check: gh api x")
                .replace("| verifying | 9876fed | | 0 |", "| in production | 9876fed | OK opus | 0 |")
                .replace("| U-3 | BUILD | 2 | src/c.ts | abc1234 | sonnet | parked | 1111111 | KO opus | 2 |\n", ""))
        code, out = run(text)
        self.assertEqual(code, 1)
        self.assertIn("U-1", problems(out))

    def test_done_with_merged_unit_and_missing_or_placeholder_pipeline_fails(self):
        base = (VALID.replace("| verifying | 9876fed | | 0 |", "| in production | 9876fed | OK opus | 0 |")
                .replace("| U-3 | BUILD | 2 | src/c.ts | abc1234 | sonnet | parked | 1111111 | KO opus | 2 |\n", ""))
        for header in ("status: done", "status: done\npipeline: <post-merge deploy found at start | none>"):
            code, out = run(base.replace("status: active", header))
            self.assertEqual(code, 1, header)
            self.assertIn("U-1", problems(out))

    def test_done_with_merged_unit_and_no_pipeline_passes(self):
        text = (VALID.replace("status: active", "status: done\npipeline: none")
                .replace("| verifying | 9876fed | | 0 |", "| merged | 9876fed | OK opus | 0 |")
                .replace("| U-3 | BUILD | 2 | src/c.ts | abc1234 | sonnet | parked | 1111111 | KO opus | 2 |\n", ""))
        code, out = run(text)
        self.assertEqual(code, 0, out)

    def test_second_ko_must_be_parked(self):
        code, out = run(VALID.replace("| parked | 1111111 | KO opus | 2 |", "| building | 1111111 | KO opus | 2 |"))
        self.assertEqual(code, 1)
        self.assertIn("U-3", problems(out))

    def test_ko_above_two_fails(self):
        code, out = run(VALID.replace("| KO opus | 2 |", "| KO opus | 3 |"))
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

    def test_record_goal_writes_lock_even_with_other_problems(self):
        code, out = run(VALID.replace("status: active", "status: running"), "--record-goal")
        self.assertEqual(code, 1)
        self.assertTrue(out["goal_recorded"])
        self.assertEqual(out["_lock_after"].strip(), "fix the three login bugs")

    def test_record_goal_reports_when_it_cannot_record(self):
        code, out = run(VALID.replace("goal: fix the three login bugs", "goal: "), "--record-goal")
        self.assertEqual(code, 1)
        self.assertFalse(out["goal_recorded"])
        self.assertIsNone(out["_lock_after"])

    def test_parked_with_a_note_or_capitalised_is_parked(self):
        for state in ("parked (blocked by U-1)", "Parked"):
            code, out = run(VALID.replace("| parked | 1111111 | KO opus | 2 |", f"| {state} | 1111111 | KO opus | 2 |"))
            self.assertEqual(code, 0, (state, out))

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

    def test_unit_rows_outside_the_units_table_fail(self):
        text = VALID.replace("## Decisions\n", "## Decisions\n\n"
                             "| U-9 | FIX | 2 | src/z.ts | abc1234 | sonnet | verified | 2222222 | OK | 0 |\n")
        code, out = run(text)
        self.assertEqual(code, 1)
        self.assertIn("U-9", problems(out))

    def test_missing_verifier_line_fails(self):
        code, out = run(VALID.replace(
            "builder: sonnet        verifier: gpt-6-luna (tier 1-2), opus (tier 3)\n", ""))
        self.assertEqual(code, 1)
        self.assertIn("verifier", problems(out))

    def test_verifier_without_both_tiers_fails(self):
        code, out = run(VALID.replace("gpt-6-luna (tier 1-2), opus (tier 3)", "opus/verificatore"))
        self.assertEqual(code, 1)
        self.assertIn("(tier 1-2)", problems(out))

    def test_opus_unit_verifier_fails_unless_no_codex(self):
        code, out = run(VALID.replace("gpt-6-luna (tier 1-2)", "opus (tier 1-2)"))
        self.assertEqual(code, 1)
        self.assertIn("Codex", problems(out))
        code, out = run(VALID.replace("gpt-6-luna (tier 1-2)", "opus (tier 1-2, no codex)"))
        self.assertEqual(code, 0, problems(out))

    def test_stale_updated_fails(self):
        code, out = run(VALID, written=VALID_WRITTEN + 4 * 3600)
        self.assertEqual(code, 1)
        self.assertIn("updated", problems(out))
        code, out = run(VALID, written=VALID_WRITTEN + 3600)
        self.assertEqual(code, 0, problems(out))

    def test_updated_not_iso_fails(self):
        code, out = run(VALID.replace("2026-09-30T18:00:00+02:00", "ieri sera"))
        self.assertEqual(code, 1)
        self.assertIn("ISO", problems(out))

    def test_narrow_unit_row_outside_the_table_fails(self):
        text = VALID.replace("## Decisions\n", "## Decisions\n\n| U-8 | BUILD | 3 | src/y.ts | verified |\n")
        code, out = run(text)
        self.assertEqual(code, 1)
        self.assertIn("U-8", problems(out))

    def test_other_tables_in_decisions_pass(self):
        text = VALID.replace("## Decisions\n", "## Decisions\n\n| a | b | c | d | e | f | g | h | i | j |\n"
                             "|---|---|---|---|---|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |\n")
        code, out = run(text)
        self.assertEqual(code, 0, problems(out))

    def test_sonnet_or_qualified_opus_unit_verifier_fails(self):
        for model in ("sonnet", "claude-sonnet", "opus (max)"):
            code, out = run(VALID.replace("gpt-6-luna (tier 1-2)", f"{model} (tier 1-2)"))
            self.assertEqual(code, 1, model)
            self.assertIn("Claude model", problems(out), model)

    def test_template_columns_depends_on_and_pr_pass(self):
        text = (VALID.replace("| ID | class | tier | write only | base |", "| ID | class | tier | write only | depends on | base |")
                .replace("| verdict | KO |", "| verdict | PR | KO |")
                .replace("|---|---|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|---|---|---|---|---|")
                .replace("| U-1 | FIX | 2 | src/a.ts | abc1234 |", "| U-1 | FIX | 2 | src/a.ts | - | abc1234 |")
                .replace("| U-2 | FIX | 2 | src/b.ts | abc1234 |", "| U-2 | FIX | 2 | src/b.ts | U-1 | abc1234 |")
                .replace("| U-3 | BUILD | 2 | src/c.ts | abc1234 |", "| U-3 | BUILD | 2 | src/c.ts | - | abc1234 |")
                .replace("| OK opus | 1 |", "| OK opus | #4 | 1 |").replace("| | 0 |", "| | - | 0 |")
                .replace("| KO opus | 2 |", "| KO opus | - | 2 |"))
        code, out = run(text)
        self.assertEqual(code, 0, problems(out))
        code, out = run(text.replace("| sonnet | parked | 1111111 | KO opus | - | 2 |",
                                     "| sonnet | building | 1111111 | KO opus | - | 2 |"))
        self.assertEqual(code, 1)
        self.assertIn("second KO", problems(out))

    def test_verifier_only_read_from_the_header(self):
        text = VALID.replace("builder: sonnet        verifier: gpt-6-luna (tier 1-2), opus (tier 3)\n", "")
        text = text.replace("18:01 U-1", "builder sonnet verifier: gpt-6-luna (tier 1-2), opus (tier 3)\n18:01 U-1")
        code, out = run(text)
        self.assertEqual(code, 1)
        self.assertIn("header", problems(out))

    def test_verifier_after_a_multiline_comment_passes(self):
        text = VALID.replace("builder: sonnet", "<!-- template:\n  verifier: opus\n-->\nbuilder: sonnet")
        code, out = run(text)
        self.assertEqual(code, 0, problems(out))

    def test_updated_without_timezone_fails_and_compact_offset_passes(self):
        code, out = run(VALID.replace("2026-09-30T18:00:00+02:00", "2026-09-30T18:00:00"))
        self.assertEqual(code, 1)
        self.assertIn("timezone", problems(out))
        code, out = run(VALID.replace("2026-09-30T18:00:00+02:00", "2026-09-30T18:00:00+0200"))
        self.assertEqual(code, 0, problems(out))

    def test_updated_far_in_the_future_fails(self):
        code, out = run(VALID, written=VALID_WRITTEN - 2 * 24 * 3600)
        self.assertEqual(code, 1)
        self.assertIn("future", problems(out))

    def test_missing_run_file_is_an_error(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--run", "/nonexistent/RUN.md"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
