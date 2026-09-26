# Verify: what counts as proof

The verifier receives only: worktree path, hash, base SHA, the unit brief. Never the
builder's report, reasoning or opinion. It runs on a different model from the builder,
on the other runtime in `mixed` mode.

## Checks by class

Every unit:

1. **Hash** — `git -C <worktree> rev-parse HEAD` equals the delivered hash.
2. **Scope** — `git diff --name-only <base>...<hash>`: every path is inside the brief's
   `write only`. One path outside → `KO: out of scope`.
3. **Commands** — the brief's `commands`, run by the verifier, exit 0, raw output kept.

Then by class:

| Class | Proof | KO when |
|---|---|---|
| **FIX** | Regression oracle: restore the base version of the changed non-test files (`git checkout <base> -- <files>`), run the new test, it must fail; restore the hash (`git checkout <hash> -- <files>`) and confirm `git status` is clean | the new test passes without the fix → `KO: no oracle` |
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

A verdict without command lines and exit codes is not a verdict: rerun it with another model.
`KO: no oracle` and `KO: out of scope` are full KOs, never "OK with notes".

## Model choice

- Builder on Codex → verifier on Claude (`claude_verifier`), and vice versa in `mixed` mode.
- Same runtime → a different, not smaller, model: the verifier must be able to find what the
  builder missed. Tier 3 units get the strongest available model as verifier.
- Record builder and verifier model per unit in `RUN.md`; report only models the runtime
  actually confirmed.
