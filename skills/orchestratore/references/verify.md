# Verify: what counts as proof

The verifier receives only: worktree path, hash, the unit's base SHA, the unit brief. Never
the builder's report, reasoning or opinion. It runs on a different model from the builder.

## Checks by class

Every unit:

1. **Hash** — `git -C <worktree> rev-parse HEAD` equals the delivered hash.
2. **Scope** — `git diff --name-only <base>...<hash>`: every path is inside the brief's
   `write only`. One path outside → `KO: out of scope`.
3. **Commands** — the brief's `commands`, run by the verifier, exit 0, raw output kept.
   These are targeted tests; exclusive-resource commands belong to the final pass only.
   Untracked build artefacts are fine; tracked files in the reviewed worktree must not change.

Then by class:

| Class | Proof | KO when |
|---|---|---|
| **FIX** | Regression oracle in a throwaway worktree, never in the reviewed one (steps below) | the new test still passes without the fix → `KO: no oracle` |
| **BUILD** | Each acceptance criterion in `proof` maps to a named test that exists and passes | a criterion has no test, or a test does not assert it |
| **CHECK** | Each checklist item in `proof` has evidence: `file:line`, command output, or a rendered result | an item is unverified or contradicted |

**FIX oracle steps:**

1. `git worktree add --detach <tmp> <hash>` and prepare it the way the project needs
   (install dependencies, e.g. `npm ci`).
2. In `<tmp>`, run the new test: it must **pass**. This proves the environment works.
3. Undo the production change in `<tmp>` using `git diff --name-status <base> <hash>` on
   non-test files: modified (M) and deleted (D) → `git checkout <base> -- <file>`; added (A)
   → delete; renamed (R) → delete the new path and `git checkout <base> -- <old path>`.
4. Run the new test again: it must **fail on its assertion**. A setup, import or runner error
   is `unverifiable`, not a red oracle: fix the environment or report it.
5. `git worktree remove --force <tmp>`.

The final pass on a lane head (SKILL.md §6) runs the full gate (build, test, lint) instead of
the targeted commands, checks each unit's scope as `base...delivered hash` of that unit, and
checks that the lane diff holds only files from the units' `write only` lists.

## Verdict

Exactly this, nothing else:

```text
VERDICT <ID> <hash>
result: OK | KO
hash: <output of git rev-parse HEAD>
scope: <paths outside write-only | none>
commands: <command> → exit <code>   (one line each)
proof: <oracle red: yes/no | criteria covered: n/m | checklist: n/m>
findings: <max 3, each with file:line and what is wrong | none>
```

A verdict without command lines and exit codes is not a verdict and not a KO: rerun it once
with another model.
`KO: no oracle` and `KO: out of scope` are full KOs, never "OK with notes".

## Model choice

- A different model from the builder, and not a weaker one by the runtime's own model
  tiers: the verifier must be able to find what the builder missed. Tier 3 units get the
  strongest available model.
- Record builder and verifier model per unit in `RUN.md`; report only models the runtime
  actually confirmed.
