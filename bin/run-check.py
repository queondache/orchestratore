#!/usr/bin/env python3
"""Deterministic check that an Orchestratore RUN.md is still one page on one goal.

Answers one question with evidence: can the next coordinator trust the top of
RUN.md? The answer is "yes" only when every condition holds:

  * one title and exactly one `goal:`, `status:`, `updated:` and `next:` line
    (a second header block is the first sign a run is drifting);
  * `goal:` is not empty and, once recorded, has not changed;
  * `status:` is active, parked or done;
  * the Units table has a KO column; every KO is 0-3 and a unit at 3 is parked;
  * `## Log` is the last section and holds at most 100 entries.

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
from pathlib import Path
from typing import Dict, List

SINGLE_FIELDS = ("goal", "status", "updated", "next")
STATUSES = {"active", "parked", "done"}
MAX_LOG_ENTRIES = 100
MAX_KO = 3


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


def check_units(lines: List[str], problems: List[str]) -> None:
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
        ko = row[ko_i] if ko_i < len(row) else ""
        if not re.fullmatch(r"\d+", ko):
            problems.append(f"unit {unit}: KO must be a number 0-{MAX_KO}, found {ko!r}")
            continue
        if int(ko) > MAX_KO:
            problems.append(f"unit {unit}: KO {ko} exceeds {MAX_KO}; it should have been parked at {MAX_KO}")
        elif int(ko) == MAX_KO and state_i is not None:
            state = row[state_i] if state_i < len(row) else ""
            if not state.lower().startswith("parked"):
                problems.append(f"unit {unit}: third KO but state is {state!r}, must be parked")


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

    check_units(lines, problems)
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
