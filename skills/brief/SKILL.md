---
name: brief
description: Use when handing a coding task to another agent (subagent, Codex, worker, parallel swarm) and it must start immediately without re-exploring the repo, re-planning, or asking questions; also when splitting a list of bugs, fixes or features into independent units for parallel agents.
---

# Brief

A brief is the complete contract for one unit of work. A good brief lets an agent go from
reading to editing in one step: the planning already happened, so the agent executes.

## 1. Classify the unit

| Class | Signal | Proof the agent must produce |
|---|---|---|
| **FIX** | Error, regression, failing test, behaviour contrary to the spec | A regression test that fails on the base and passes after the fix |
| **BUILD** | New feature, new contract, intentional change of behaviour | Tests for each acceptance criterion, passing |
| **CHECK** | No practical automated assertion: visual design, tone of copy, docs, config | A checklist from the brief, each item with evidence (`file:line`, command output) |

If a cheap test can assert the outcome (a wrong label, a wrong number), it is FIX or BUILD,
not CHECK. Diff size never picks the class: a hard bug is still a FIX. If the cause of a FIX is unknown,
the unit is a short diagnosis first (`class: FIX`, goal starting with "diagnose"): `proof` =
a failing reproduction test plus the cause at `file:line`. A diagnosis is not verified or
merged: its test and cause become the `proof` and `known` of the fix brief, which is. If a FIX turns out to
need a product decision, it becomes BUILD or a question for the user.

Risk tier is a separate axis. Tier 1 = tests, docs, tooling, internal scripts. Tier 2 =
product code outside tier 3 areas. Tier 3 = schema/migrations, auth, payments, multi-tenancy,
personal or health data, secrets, permissions, data deletion. Tier 3 is never auto-merged.
When unsure whether a unit touches one of these, pick the higher tier. A unit that depends
on a tier 3 unit is tier 3 too.

## 2. Split into units

- **One file, one owner per wave.** Units that must edit the same file merge into one brief.
  The merged brief keeps every source's `proof`; its tier is the highest, its class BUILD if
  any source is BUILD.
- **Shared interface first.** When units depend on a new type, schema or API signature, one
  short brief defines that interface; the consumers start after it is merged.
- **Independent causes, independent units.** Ten tickets with one root cause are one unit.
- Do not split work under ~30 minutes or confined to one file: coordination costs more.

## 3. Write the brief

Fill every field, in this order. Point to files instead of pasting them; keep it under
40 lines.

```markdown
# <ID> — <one-line goal>
class: FIX | BUILD | CHECK        tier: 1 | 2 | 3
goal: <observable outcome: what a user or test sees when this is done>
known: <facts already established: error text, repro steps, cause if found, spec rule>
read first: <path:lines — why>   (at most 5 entries)
write only: <paths or globs this unit owns>
do not touch: <neighbouring areas, public interfaces, dependencies>
proof: <the failing test to write | acceptance criteria as tests | checklist items>
commands: <targeted test command, no shared database/port/browser>; full gate runs later
done when: <proof passes + commands exit 0 + diff confined to write-only paths>
report: status | hash | files | command → exit code | blockers (5 lines, nothing else)
```

Rules every builder receives with its brief (paste verbatim; verifiers do not get them):

```text
Work only inside `write only`. Commit on your branch; do not push, open PRs or merge.
Do not ask the user: if blocked, stop and put the blocker in the report.
Stop when `done when` holds. No refactors, renames or dependencies outside the goal.
```

## Example

```markdown
# B-3 — Checkout total ignores the discount on free shipping orders
class: FIX        tier: 2
goal: an order with code SAVE10 and free shipping shows total = subtotal × 0.9
known: repro: cart 50€, SAVE10 → shows 50€. Cause: applyDiscount() returns early when shipping == 0
read first: src/cart/total.ts:40-72 — applyDiscount; tests/cart/total.test.ts — existing cases
write only: src/cart/total.ts, tests/cart/total.test.ts
do not touch: src/cart/shipping.ts, the Discount type
proof: test "applies discount when shipping is free" fails on base, passes after
commands: npm test -- tests/cart/total.test.ts
done when: proof passes, command exits 0, diff only in the two files
report: status | hash | files | command → exit code | blockers
```

## Common mistakes

| Mistake | Fix |
|---|---|
| Brief asks the agent to "investigate and plan" a known fix | Put the cause in `known`; the agent edits |
| Pasting whole files or the full spec | `read first` with path and line range |
| Two briefs writing the same file in one wave | Merge them, or sequence them |
| `proof` says "add tests" | Name the test and what it must show |
| Report asks for a narrative | Five fixed lines; details stay in the log |
