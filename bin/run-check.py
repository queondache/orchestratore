#!/usr/bin/env python3
"""Deterministic check that an Orchestratore RUN.md is still one page on one goal.

Answers one question with evidence: can the next coordinator trust the top of
RUN.md? The answer is "yes" only when every condition holds:

  * one title and exactly one `goal:`, `status:`, `updated:` and `next:` line
    (a second header block is the first sign a run is drifting);
  * `goal:` is not empty and, once recorded, has not changed;
  * `status:` is active, parked or done;
  * the Units table has a KO column; every KO is 0-2 and a unit at 2 is parked;
  * `status: done` only when every unit is in production, or merged with
    `pipeline: none` (the goal is reached); anything else keeps the run parked;
  * `## Log` is the last section and holds at most 100 entries;
  * every unit is a row of the one Units table (no unit rows in other sections);
  * `verifier:` names the tier 1-2 and the tier 3 verifier, as
    `<model> (tier 1-2), <model> (tier 3)`; opus checks tier 1-2 only as `(tier 1-2, no codex)`;
  * `updated:` is ISO 8601 and not hours older than the file's last write.

With --record-goal a valid goal is written to goal.lock next to RUN.md (at
start, after a resume migration, or when the user changes the goal), even if
other problems remain; `goal_recorded` in the output says whether it was. A
plain check never writes anything.

Exit codes: 0 page OK, 1 problems found, 2 error (no RUN.md).
Output: one JSON object on stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

SINGLE_FIELDS = ("goal", "status", "updated", "next")
STATUSES = {"active", "parked", "done"}
MAX_LOG_ENTRIES = 100
MAX_KO = 2
# States in which a unit has reached the goal; only then may the run be `done`.
# `merged` is final only when nothing deploys (`pipeline: none`).
FINAL_STATES = ("merged", "in production")
# A page written later than this after its `updated:` time means `updated:` was not refreshed.
STALE_UPDATED_SECONDS = 3 * 3600
# Claude models that must not verify tier 1-2 units while a Codex verifier is available.
CLAUDE_UNIT_VERIFIERS = ("opus", "sonnet", "claude")
UNIT_CLASSES = ("FIX", "BUILD", "CHECK", "RELEASE")


def field_lines(lines: List[str], name: str) -> List[str]:
    prefix = f"{name}:"
    return [line[len(prefix):].strip() for line in lines if line.startswith(prefix)]


def table_rows(lines: List[str]) -> List[List[str]]:
    """Rows of the first Markdown table after `## Units`, header included."""
    rows: List[List[str]] = []
    in_units = False
    for line in lines:
        if line.startswith("## "):
            if in_units:
                break
            in_units = line.strip() == "## Units"
            continue
        if in_units and line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
                continue
            rows.append(cells)
    return rows


def check_units(lines: List[str], problems: List[str], status: str = "",
                deploys: bool = False) -> None:
    rows = table_rows(lines)
    if not rows:
        problems.append("no Units table under `## Units`")
        return
    header = [c.lower() for c in rows[0]]
    if "ko" not in header:
        problems.append("Units table has no KO column (count KO verdicts per unit)")
        return
    ko_i, state_i = header.index("ko"), header.index("state") if "state" in header else None
    for row in rows[1:]:
        unit = row[0] if row else "?"
        if unit.startswith("<"):
            continue  # template placeholder row
        state = row[state_i] if state_i is not None and state_i < len(row) else ""
        final = ("in production",) if deploys else FINAL_STATES
        if status == "done" and not state.lower().startswith(final):
            problems.append(f"unit {unit}: state is {state!r} but status is done; the goal is "
                            "reached only when every unit is in production (merged with "
                            "`pipeline: none`): keep the run parked with what unblocks it")
        ko = row[ko_i] if ko_i < len(row) else ""
        if not re.fullmatch(r"\d+", ko):
            problems.append(f"unit {unit}: KO must be a number 0-{MAX_KO}, found {ko!r}")
            continue
        if int(ko) > MAX_KO:
            problems.append(f"unit {unit}: KO {ko} exceeds {MAX_KO}; it should have been parked at {MAX_KO}")
        elif int(ko) == MAX_KO and state_i is not None:
            if not state.lower().startswith("parked"):
                problems.append(f"unit {unit}: second KO but state is {state!r}, must be parked")


def header_lines(lines: List[str]) -> List[str]:
    """Lines above the first `## ` section, outside HTML comments."""
    out: List[str] = []
    in_comment = False
    for line in lines:
        if line.startswith("## "):
            break
        text = line.strip()
        if in_comment:
            in_comment = "-->" not in text
            continue
        if text.startswith("<!--"):
            in_comment = "-->" not in text
            continue
        out.append(line)
    return out


def check_stray_unit_rows(lines: List[str], problems: List[str]) -> None:
    """Unit rows written as a second table somewhere else drop out of every check.
    A unit row is recognised by its content (a class and a tier 1-3), whatever its width."""
    section = ""
    for line in lines:
        if line.startswith("## "):
            section = line.strip()
            continue
        if section == "## Units" or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        is_header = [c.lower() for c in cells[:3]] == ["id", "class", "tier"]
        is_unit = cells[1].upper() in UNIT_CLASSES and re.fullmatch(r"[1-3]", cells[2])
        if is_header or is_unit:
            what = "a second Units table" if is_header else f"unit row {cells[0]!r}"
            problems.append(f"{what} under {section or 'the header'}: every unit "
                            "is a row of the one Units table")


def check_verifier(lines: List[str], problems: List[str]) -> None:
    found = [line.split("verifier:", 1)[1].strip() for line in header_lines(lines)
             if "verifier:" in line]
    if not found:
        problems.append("no `verifier:` line in the header: record "
                        "`verifier: <model> (tier 1-2), <model> (tier 3)`")
        return
    value = found[0]
    unit = re.search(r"(?:^|,)\s*([^,]*?)\s*\((tier 1-2[^)]*)\)", value)
    if not unit or "(tier 3" not in value:
        problems.append(f"verifier {value!r}: write `<model> (tier 1-2), <model> (tier 3)`")
        return
    model, label = unit.group(1).strip().lower(), unit.group(2).lower()
    if any(word in model for word in CLAUDE_UNIT_VERIFIERS) and "no codex" not in label:
        problems.append(f"tier 1-2 verifier {model!r} is a Claude model: tier 1-2 units go to an "
                        "economical Codex model; write `(tier 1-2, no codex)` only when Codex is missing")


def check_updated(lines: List[str], run_path: Path, problems: List[str]) -> None:
    values = field_lines(lines, "updated")
    if len(values) != 1:
        return
    # Python 3.9 reads neither `Z` nor `+0200`: normalise both to `+HH:MM`.
    text = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", values[0].replace("Z", "+00:00"))
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        problems.append(f"updated {values[0]!r} is not ISO 8601")
        return
    if when.tzinfo is None:
        problems.append(f"updated {values[0]!r} has no timezone: write it as UTC (`Z`) or with "
                        "its offset")
        return
    gap = run_path.stat().st_mtime - when.timestamp()
    if gap > STALE_UPDATED_SECONDS:
        problems.append(f"updated {values[0]} is hours older than the last write of RUN.md: "
                        "refresh `updated:` on every state change")
    elif gap < -24 * 3600:
        problems.append(f"updated {values[0]} is in the future: write the current time")


def check_log(lines: List[str], problems: List[str]) -> None:
    sections = [i for i, line in enumerate(lines) if line.startswith("## ")]
    if not sections or lines[sections[-1]].strip() != "## Log":
        last = lines[sections[-1]].strip() if sections else "none"
        problems.append(f"`## Log` must be the last section (last is {last!r}); "
                        "history goes into the Log, never a new block")
        return
    entries, in_comment = 0, False
    for line in lines[sections[-1] + 1:]:
        text = line.strip()
        if in_comment:
            in_comment = "-->" not in text
            continue
        if text.startswith("<!--"):
            in_comment = "-->" not in text
            continue
        if text:
            entries += 1
    if entries > MAX_LOG_ENTRIES:
        problems.append(f"Log has {entries} entries, over {MAX_LOG_ENTRIES}: "
                        "move it to .orchestratore/log/<date>.md and leave the link")


def evaluate(run_path: Path, record_goal: bool) -> Dict[str, object]:
    text = run_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    problems: List[str] = []

    titles = [line for line in lines if line.startswith("# ")]
    if len(titles) != 1:
        problems.append(f"expected one title line, found {len(titles)}")
    for name in SINGLE_FIELDS:
        values = field_lines(lines, name)
        if len(values) != 1:
            problems.append(f"expected exactly one `{name}:` line, found {len(values)} "
                            "(overwrite the header in place)")
    goals = field_lines(lines, "goal")
    goal = goals[0] if len(goals) == 1 else ""
    if len(goals) == 1 and (not goal or goal.startswith("<")):
        problems.append("`goal:` is empty: write the user's request in one sentence")
    statuses = field_lines(lines, "status")
    if len(statuses) == 1 and statuses[0] not in STATUSES:
        problems.append(f"status {statuses[0]!r} is not one of {sorted(STATUSES)}")

    lock = run_path.parent / "goal.lock"
    goal_ok = len(goals) == 1 and bool(goal) and not goal.startswith("<")
    goal_recorded = False
    if record_goal:
        if goal_ok:
            lock.write_text(goal + "\n", encoding="utf-8")
            goal_recorded = True
        else:
            problems.append("--record-goal: no valid goal to record")
    elif lock.exists() and goal and lock.read_text(encoding="utf-8").strip() != goal:
        problems.append("goal changed since it was recorded; only the user changes it "
                        "(if they did, rerun with --record-goal)")

    pipelines = field_lines(lines, "pipeline")
    # Only an explicit `pipeline: none` makes `merged` final; a missing line or the
    # template placeholder may hide a deploy still to confirm.
    deploys = not (len(pipelines) == 1 and pipelines[0].lower().split()[:1] == ["none"])
    check_units(lines, problems, statuses[0] if len(statuses) == 1 else "", deploys)
    check_stray_unit_rows(lines, problems)
    check_verifier(lines, problems)
    check_updated(lines, run_path, problems)
    check_log(lines, problems)
    result: Dict[str, object] = {"ok": not problems, "run": str(run_path), "goal": goal,
                                 "problems": problems}
    if record_goal:
        result["goal_recorded"] = goal_recorded
    return result


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", default=".orchestratore/RUN.md", help="path to RUN.md")
    parser.add_argument("--record-goal", action="store_true",
                        help="write the current goal to goal.lock (start of run, or goal changed by the user)")
    args = parser.parse_args(argv)
    run_path = Path(args.run)
    if not run_path.is_file():
        print(json.dumps({"ok": False, "run": str(run_path), "error": "RUN.md not found"}))
        return 2
    result = evaluate(run_path, args.record_goal)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
