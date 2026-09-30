"""Tests for bin/verdict-check.py: a verdict moves a unit only if its facts support it."""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "verdict-check.py"
H = "a" * 40

OK = textwrap.dedent(f"""\
    VERDICT U-1 {H[:7]}
    result: OK
    hash: {H}
    scope: none
    commands: npm test -- login.spec.ts → exit 0 [ran]
    commands: backend CI → exit 0 [ci https://github.com/o/r/actions/runs/1]
    proof: oracle red: yes
    findings: none
    blocked: none
    """)


def check(text: str, *extra: str) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(SCRIPT), *extra], input=text,
                          capture_output=True, text=True)
    return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip() else {})


def problems(out: dict) -> str:
    return " | ".join(out.get("problems", []))


class VerdictCheckTest(unittest.TestCase):
    def test_valid_ok(self):
        code, out = check(OK, "--hash", H)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["result"], "OK")

    def test_hash_must_match_the_delivered_one(self):
        code, out = check(OK, "--hash", "b" * 40)
        self.assertEqual(code, 1)
        self.assertIn("hash", problems(out))

    def test_hash_line_must_be_full(self):
        code, out = check(OK.replace(f"hash: {H}", f"hash: {H[:7]}"))
        self.assertEqual(code, 1)
        self.assertIn("40", problems(out))

    def test_header_hash_must_prefix_the_full_hash(self):
        code, out = check(OK.replace(f"VERDICT U-1 {H[:7]}", "VERDICT U-1 bbbbbbb"))
        self.assertEqual(code, 1)
        self.assertIn("header", problems(out))

    def test_unknown_result_fails(self):
        code, out = check(OK.replace("result: OK", "result: OK with notes"))
        self.assertEqual(code, 1)
        self.assertIn("result", problems(out))

    def test_ok_needs_at_least_one_command(self):
        text = "\n".join(l for l in OK.splitlines() if not l.startswith("commands:"))
        code, out = check(text)
        self.assertEqual(code, 1)
        self.assertIn("command", problems(out))

    def test_ok_with_a_failing_command_fails(self):
        code, out = check(OK.replace("→ exit 0 [ran]", "→ exit 1 [ran]"))
        self.assertEqual(code, 1)
        self.assertIn("exit 1", problems(out))

    def test_command_without_exit_code_fails(self):
        code, out = check(OK.replace("npm test -- login.spec.ts → exit 0 [ran]", "npm test passed [ran]"))
        self.assertEqual(code, 1)
        self.assertIn("exit", problems(out))

    def test_command_without_provenance_fails(self):
        code, out = check(OK.replace("→ exit 0 [ran]", "→ exit 0"))
        self.assertEqual(code, 1)
        self.assertIn("provenance", problems(out))

    def test_ok_cannot_rest_on_reused_proof(self):
        code, out = check(OK.replace("→ exit 0 [ran]", "→ exit 0 [reused run of 29/09]"))
        self.assertEqual(code, 1)
        self.assertIn("reused", problems(out))

    def test_ci_provenance_needs_a_reference(self):
        code, out = check(OK.replace("[ci https://github.com/o/r/actions/runs/1]", "[ci]"))
        self.assertEqual(code, 1)
        self.assertIn("ci", problems(out))

    def test_ok_with_scope_violation_fails(self):
        code, out = check(OK.replace("scope: none", "scope: src/other.ts"))
        self.assertEqual(code, 1)
        self.assertIn("scope", problems(out))

    def test_ok_with_open_blocked_fails(self):
        code, out = check(OK.replace("blocked: none", "blocked: no database"))
        self.assertEqual(code, 1)
        self.assertIn("blocked", problems(out))

    def test_ascii_arrow_is_accepted(self):
        code, out = check(OK.replace("→", "->"), "--hash", H)
        self.assertEqual(code, 0, out)

    def test_valid_ko_needs_findings(self):
        ko = OK.replace("result: OK", "result: KO").replace("→ exit 0 [ran]", "→ exit 1 [ran]")
        code, out = check(ko.replace("findings: none", "findings: src/a.ts:12 wrong status code"))
        self.assertEqual(code, 0, out)
        code, out = check(ko)
        self.assertEqual(code, 1)
        self.assertIn("findings", problems(out))

    def test_ko_may_rest_on_reused_evidence(self):
        ko = (OK.replace("result: OK", "result: KO").replace("[ran]", "[reused earlier log]")
              .replace("findings: none", "findings: src/a.ts:3 missing test"))
        code, out = check(ko)
        self.assertEqual(code, 0, out)

    def test_blocked_needs_a_reason(self):
        blocked = OK.replace("result: OK", "result: BLOCKED")
        code, out = check(blocked)
        self.assertEqual(code, 1)
        self.assertIn("blocked", problems(out))
        code, out = check(blocked.replace("blocked: none", "blocked: local suites denied, 651 MB free"))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["result"], "BLOCKED")

    def test_exit_text_inside_the_command_does_not_hide_the_real_code(self):
        code, out = check(OK.replace("npm test -- login.spec.ts → exit 0 [ran]",
                                     "echo '-> exit 0' → exit 1 [ran]"))
        self.assertEqual(code, 1)
        self.assertIn("exit 1", problems(out))

    def test_expected_failure_of_the_oracle_supports_ok(self):
        # FIX proof: the new test must fail once the fix is undone. That red run is the proof.
        red = OK.replace("[ci https://github.com/o/r/actions/runs/1]\n",
                         "[ci https://github.com/o/r/actions/runs/1]\n"
                         "commands: fix undone, npm test -- login.spec.ts → exit 1 [ran expect-fail]\n")
        code, out = check(red, "--hash", H)
        self.assertEqual(code, 0, out)

    def test_expected_failure_that_passes_is_not_ok(self):
        green = OK.replace("[ci https://github.com/o/r/actions/runs/1]\n",
                           "[ci https://github.com/o/r/actions/runs/1]\n"
                           "commands: fix undone, npm test → exit 0 [ran expect-fail]\n")
        code, out = check(green)
        self.assertEqual(code, 1)
        self.assertIn("expected to fail", problems(out))

    def test_unknown_qualifier_on_ran_is_rejected(self):
        code, out = check(OK.replace("→ exit 0 [ran]", "→ exit 0 [ran mostly]"))
        self.assertEqual(code, 1)
        self.assertIn("qualifier", problems(out))

    def test_expect_fail_only_on_ran(self):
        code, out = check(OK.replace("[ci https://github.com/o/r/actions/runs/1]",
                                     "[reused expect-fail]").replace("→ exit 0 [reused", "→ exit 1 [reused"))
        self.assertEqual(code, 1)

    def test_two_commands_on_one_line_are_rejected(self):
        code, out = check(OK.replace("npm test -- login.spec.ts → exit 0 [ran]",
                                     "npm test → exit 1 [ran]; npm run lint → exit 0 [ran]"))
        self.assertEqual(code, 1)
        self.assertIn("one command per line", problems(out))

    def test_two_verdicts_in_one_text_are_rejected(self):
        ko = OK.replace("result: OK", "result: KO").replace("findings: none", "findings: src/a.ts:1 bug")
        code, out = check(OK + "\nCorrection:\n" + ko)
        self.assertEqual(code, 1)
        self.assertIn("one VERDICT", problems(out))

    def test_duplicate_result_or_hash_lines_are_rejected(self):
        code, out = check(OK.replace("result: OK\n", "result: OK\nresult: KO\n"))
        self.assertEqual(code, 1)
        self.assertIn("result:", problems(out))
        code, out = check(OK.replace(f"hash: {H}\n", f"hash: {H}\nhash: {'b' * 40}\n"))
        self.assertEqual(code, 1)
        self.assertIn("hash:", problems(out))

    def test_missing_verdict_header_fails(self):
        code, out = check(OK.replace(f"VERDICT U-1 {H[:7]}\n", ""))
        self.assertEqual(code, 1)
        self.assertIn("VERDICT", problems(out))

    def test_verdict_inside_prose_is_found(self):
        code, out = check("Here is my verdict.\n\n```text\n" + OK + "```\nThanks.\n", "--hash", H)
        self.assertEqual(code, 0, out)

    def test_reads_a_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(OK)
        proc = subprocess.run([sys.executable, str(SCRIPT), "--verdict", f.name, "--hash", H],
                              capture_output=True, text=True)
        Path(f.name).unlink()
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_missing_file_is_an_error(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--verdict", "/nonexistent/v.txt"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


class ToleranceHolesTest(unittest.TestCase):
    """Holes the tolerant parser must not open (found by the independent verifier)."""

    def test_bullet_under_a_non_empty_commands_line_is_read(self):
        text = OK.replace("[ci https://github.com/o/r/actions/runs/1]\n",
                          "[ci https://github.com/o/r/actions/runs/1]\n- lint → exit 1 [ran]\n")
        code, out = check(text)
        self.assertEqual(code, 1)
        self.assertIn("exit 1", problems(out))

    def test_exit_line_outside_commands_is_reported(self):
        for stray in ("proof: oracle red: yes\n- lint → exit 1 [ran]\n", "-lint → exit 1 [ran]\n",
                      "some prose\n- lint → exit 1 [ran]\n"):
            text = OK.replace("proof: oracle red: yes\n", stray if stray.startswith("proof") else
                              "proof: oracle red: yes\n" + stray)
            code, out = check(text)
            self.assertEqual(code, 1, (stray, out))
            self.assertIn("outside", problems(out))

    def test_ok_cannot_rest_on_expect_fail_alone(self):
        text = "\n".join(l for l in OK.splitlines() if not l.startswith("commands:"))
        text = text.replace("proof:", "commands: npm test → exit 1 [ran expect-fail]\nproof:")
        code, out = check(text)
        self.assertEqual(code, 1)
        self.assertIn("passing", problems(out))

    def test_bulleted_findings_and_blocked_are_read(self):
        ko = (OK.replace("result: OK", "result: KO").replace("→ exit 0 [ran]", "→ exit 1 [ran]")
              .replace("findings: none", "findings:\n- src/a.ts:3 missing test"))
        code, out = check(ko)
        self.assertEqual(code, 0, out)
        blocked = OK.replace("result: OK", "result: BLOCKED").replace("blocked: none", "blocked:\n- no database")
        code, out = check(blocked)
        self.assertEqual(code, 0, out)

    def test_exit_quoted_in_prose_fields_is_allowed(self):
        text = OK.replace("proof: oracle red: yes", "proof: oracle red: yes (test → exit 1 on assertion)")
        code, out = check(text, "--hash", H)
        self.assertEqual(code, 0, out)
        ko = (OK.replace("result: OK", "result: KO").replace("→ exit 0 [ran]", "→ exit 1 [ran]")
              .replace("findings: none", "findings:\n- a.py:1 script -> exit 2 instead of 0"))
        code, out = check(ko, "--hash", H)
        self.assertEqual(code, 0, out)

    def test_bracket_note_before_the_tag(self):
        code, out = check(OK.replace("→ exit 0 [ran]", "→ exit 0 (see [log]) [ran]"), "--hash", H)
        self.assertEqual(code, 0, out)


class RealVerdictsTest(unittest.TestCase):
    """Verdicts written by real verifier agents on scratch FIX units: all three are correct."""
    FIX = ROOT / "tests" / "fixtures" / "verdicts"

    def run_fixture(self, name):
        hash_ = (self.FIX / f"{name}.hash").read_text().strip()
        proc = subprocess.run([sys.executable, str(SCRIPT), "--verdict", str(self.FIX / f"{name}.txt"),
                               "--hash", hash_], capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def test_real_ok_with_bulleted_commands(self):
        code, out = self.run_fixture("real-A")
        self.assertEqual((code, out["result"]), (0, "OK"), out)

    def test_real_ko_with_words_between_exit_and_tag(self):
        code, out = self.run_fixture("real-B")
        self.assertEqual((code, out["result"]), (0, "KO"), out)

    def test_real_blocked_with_notes_after_tag_and_exit_non_zero(self):
        code, out = self.run_fixture("real-C")
        self.assertEqual((code, out["result"]), (0, "BLOCKED"), out)


    def test_second_round_real_verdicts(self):
        for name, expected in (("real2-A", "OK"), ("real2-B", "KO"), ("real2-C", "BLOCKED")):
            code, out = self.run_fixture(name)
            self.assertEqual((code, out["result"]), (0, expected), (name, out))


class TolerantFormatTest(unittest.TestCase):
    def test_notes_after_the_tag_are_allowed(self):
        code, out = check(OK.replace("→ exit 0 [ran]", "→ exit 0 [ran] (12 tests)"), "--hash", H)
        self.assertEqual(code, 0, out)

    def test_exit_non_zero_counts_as_a_failure(self):
        code, out = check(OK.replace("→ exit 0 [ran]", "→ exit non-zero [ran]"))
        self.assertEqual(code, 1)
        self.assertIn("failing", problems(out))

    def test_bulleted_commands_are_read(self):
        bulleted = OK.replace("commands: npm test -- login.spec.ts → exit 0 [ran]\n",
                              "commands:\n- npm test -- login.spec.ts → exit 1 [ran]\n")
        code, out = check(bulleted)
        self.assertEqual(code, 1)
        self.assertIn("exit 1", problems(out))


if __name__ == "__main__":
    unittest.main()
