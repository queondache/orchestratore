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
  any source is BUILD. Each FIX source keeps its regression oracle as a named proof.
- **Shared interface first.** When units depend on a new type, schema or API signature, one
  short brief defines that interface; the consumers start after it is merged.
- **Independent causes, independent units.** Ten tickets with one root cause are one unit.
- Do not split work under ~30 minutes or confined to one file: coordination costs more.

## 3. Run context (once per run)

`.orchestratore/CONTEXT.md`, at most 60 lines, written before the first brief and sent in
front of every brief, to builders and verifiers alike:

- stack and versions; how to run one test file; env vars or services the tests need;
- the repo rules builders must obey, quoted from `CLAUDE.md` / `AGENTS.md` (comment language,
  naming, error logging, dependency policy);
- a map of the directories this run touches, one line each;
- glossary: words with a local meaning (e.g. "session" = one occurrence of a class);
- known traps: exclusive resources, slow suites, generated files never to edit.

## 4. Write the brief

Fill every field, in this order. Context is cheaper than a builder's search: quote the spec,
paste the few lines the change hinges on, name an existing example to copy, point to the
rest. Aim for 40-100 lines; do not repeat what `CONTEXT.md` already says.

```markdown
# <ID> — <one-line goal>
class: FIX | BUILD | CHECK        tier: 1 | 2 | 3
goal: <observable outcome: what a user or test sees when this is done>
spec: <the expected behaviour quoted from its source, with path:line | the user's words>
known: <facts already established: error text, repro steps, cause at file:line, data shapes>
code: |
  <the lines the change hinges on, each block headed `path:start-end`; at most ~40 lines>
pattern: <an existing file or test to imitate, path:lines — how this repo does it | none>
read first: <path:lines — why>   (at most 8 entries)
write only: <paths or globs this unit owns>
do not touch: <neighbouring areas, public interfaces, dependencies>
pitfalls: <traps already known: other callers, env vars a test needs, flaky fixtures | none>
proof: <each test + the wrong code it catches: fails on base (FIX) | fails if <key line> is reverted (BUILD) | checklist items>
commands: <targeted test command, no shared database/port/browser>; full gate runs later
done when: <proof passes + commands exit 0 + diff confined to write-only paths>
report: status | worktree + branch | hash | files | command → exit code | blockers
```

Rules every builder receives with its brief (paste verbatim; verifiers do not get them):

```text
Work only inside `write only`. Commit on your branch; do not push, open PRs or merge.
Do not ask the user: if blocked, stop and put the blocker in the report.
Stop when `done when` holds. No refactors, renames or dependencies outside the goal.
```

## 5. Ready check (before the brief goes out)

A brief goes out only when every line holds. Otherwise complete it, or turn the gap into a
question for the user; never send it hoping the builder will fill it in.

- `goal` is observable: a value, a screen state, a test result. Not "improve" or "fix".
- `known` holds what the builder would otherwise hunt for: error text, repro, and for a FIX
  the cause at `file:line` (cause unknown → a diagnosis unit first, §1).
- `CONTEXT.md` exists for the run; `spec` quotes its source or the user's words.
- `code` holds the lines the change hinges on; `pattern` names an existing example when the
  repo has one (a similar test, a sibling component).
- `read first` paths and line ranges exist on the base.
- `proof` names each test, what it asserts and the wrong code it catches (FIX: the base; BUILD:
  the key line reverted). A test that would stay green with the wrong code is not a proof.
  A BUILD has one test per acceptance criterion.
- `commands` were run on the base and behave as expected (the targeted suite runs).
- `write only` covers every file the change needs; no other unit owns them in this wave.
- The expected behaviour traces to a spec line or the user's request: no product decision
  is left to the builder.

## Example

```markdown
# B-3 — Checkout total ignores the discount on free shipping orders
class: FIX        tier: 2
goal: an order with code SAVE10 and free shipping shows total = subtotal × 0.9
spec: SPEC.md:88 "Discount codes apply to the subtotal, whatever the shipping method"
known: repro: cart 50€, SAVE10 → shows 50€. Cause: applyDiscount() returns early when shipping == 0
code: |
  src/cart/total.ts:52-56
    export function applyDiscount(cart: Cart, code: Discount): number {
      if (cart.shipping === 0) return cart.subtotal;   // the early return
      return cart.subtotal * (1 - code.rate);
    }
pattern: tests/cart/total.test.ts:10-24 — "applies discount with paid shipping": copy its setup
read first: src/cart/total.ts:40-72 — applyDiscount; tests/cart/total.test.ts — existing cases
write only: src/cart/total.ts, tests/cart/total.test.ts
do not touch: src/cart/shipping.ts, the Discount type
pitfalls: applyDiscount is also called by src/invoice/print.ts:31; keep its signature
proof: test "applies discount when shipping is free" fails on base, passes after
commands: npm test -- tests/cart/total.test.ts
done when: proof passes, command exits 0, diff only in the two files
report: status | worktree + branch | hash | files | command → exit code | blockers
```

## Common mistakes

| Mistake | Fix |
|---|---|
| Brief asks the agent to "investigate and plan" a known fix | Put the cause in `known`; the agent edits |
| Pasting whole files or the full spec | Paste only the hinge lines in `code`; the rest in `read first` |
| No example of how this repo writes tests | `pattern` with a sibling test to copy |
| Two briefs writing the same file in one wave | Merge them, or sequence them |
| `proof` says "add tests" | Name the test, what it shows and the wrong code that turns it red |
| Report asks for a narrative | Six fixed lines; details stay in the log |
