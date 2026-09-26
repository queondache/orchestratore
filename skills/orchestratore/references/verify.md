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

Then by class:

| Class | Proof | KO when |
|---|---|---|
| **FIX** | Regression oracle in a throwaway worktree, never in the reviewed one: `git worktree add --detach <tmp> <hash>`, then in `<tmp>` `git checkout <base> -- <changed non-test files>` and run the new test: it must fail. Finally `git worktree remove --force <tmp>` | the new test passes without the fix → `KO: no oracle` |
| **BUILD** | Each acceptance criterion in `proof` maps to a named test that exists and passes | a criterion has no test, or a test does not assert it |
| **CHECK** | Each checklist item in `proof` has evidence: `file:line`, command output, or a rendered result | an item is unverified or contradicted |

The final pass on the integrated SHA (SKILL.md §6) runs the full gate (build, test, lint)
instead of the targeted commands, plus the checks above across all units.

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

- A different, not smaller, model than the builder: the verifier must be able to find what
  the builder missed. Tier 3 units get the strongest available model as verifier.
- Record builder and verifier model per unit in `RUN.md`; report only models the runtime
  actually confirmed.
