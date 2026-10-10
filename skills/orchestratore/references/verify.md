# Verify: what counts as proof

The verifier receives only: worktree path, hash, the unit's base SHA, the run context
(`.orchestratore/CONTEXT.md`) and the unit brief. Never
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
| **FIX** | Regression oracle in a throwaway copy, never in the reviewed worktree (steps below) | the new test still passes without the fix → `KO: no oracle` |
| **BUILD** | Each acceptance criterion in `proof` maps to a named test that exists and passes | a criterion has no test, or a test does not assert it |
| **CHECK** | Each checklist item in `proof` has evidence: `file:line`, command output, or a rendered result | an item is unverified or contradicted |

A merged unit (several sources in one brief) runs the proof of every source: the oracle for
each FIX source, the tests for each BUILD criterion, the evidence for each CHECK item.

**FIX oracle steps** (a plain copy: no new worktree, no git writes, no reinstall):

1. Extract the tree at `<hash>` into an empty `<tmp>`: `git -C <worktree> archive <hash> |
   tar -x -C <tmp>` (tracked files only, exactly that commit). Link the installed
   dependencies back, each that exists: `ln -s <worktree>/node_modules <tmp>/node_modules`
   (same for `.venv`, `venv`). Install there only if the project has nothing installed. Tool
   caches written through the link (e.g. `node_modules/.cache`) land in the reviewed worktree
   as untracked files, which is allowed. **Do not link** dependencies that point back into
   the reviewed code: an editable install (`grep -rl "<worktree>"` finds a `.pth` or
   `__editable__` file in the venv) or a workspace package (a symlink in `node_modules`
   resolving inside `<worktree>` but outside `<worktree>/node_modules`; `.bin` and `.pnpm`
   links do not count). Then install in `<tmp>` instead, into a fresh environment created
   inside `<tmp>` (`npm ci`; `uv venv <tmp>/.venv` then `uv sync`, or `python3 -m venv
   <tmp>/.venv` then `<tmp>/.venv/bin/pip install -e .`), never into the reviewed worktree's
   or an already active environment: otherwise the test imports the reviewed code, not the
   copy. Run Python tests with `PYTHONDONTWRITEBYTECODE=1`, so no stale `.pyc` survives the
   undo. In `<tmp>`, run the new test: it must **pass**. This proves the environment works.
2. Undo the production change in `<tmp>` using `git -C <worktree> diff --name-status <base>
   <hash>` on non-test files: modified (M) and deleted (D) → `git -C <worktree> archive
   <base> -- <file> | tar -x -C <tmp>` (recreates folders and file modes); added (A) →
   delete; renamed (R) → delete the new path and extract the old one from `<base>` the same way.
3. Run the new test again: it must **fail on its assertion** (tag this line `[ran expect-fail]`). A setup, import or runner error
   is not a red oracle: fix the environment or answer `BLOCKED` with what is missing. If it
   still passes while dependencies are linked, repeat steps 1-3 once with them installed in
   `<tmp>` before answering `KO: no oracle`: a link can hide an editable install.
4. `rm -rf <tmp>`, always, also on KO or BLOCKED.

The final pass on a lane head (SKILL.md §6) runs the full gate (build, test, lint) instead of
the targeted commands, checks each unit's scope as `base...delivered hash` of that unit, and
checks that the lane diff holds only files from the units' `write only` lists.

## Verdict

Exactly this, nothing else:

```text
VERDICT <ID> <hash>
result: OK | KO | BLOCKED
hash: <full output of git rev-parse HEAD>
scope: <paths outside write-only | none>
commands: <command> → exit <code> [ran | ran expect-fail | ci <run url or id> | reused <what>]   (one line each)
proof: <oracle red: yes/no | criteria covered: n/m | checklist: n/m>
findings: <max 3, each with file:line and what is wrong | none>
blocked: <what is missing to run the proof | none>
```

One command per `commands:` line, exit code and tag right after it, notes after the tag:

```text
commands: npm test -- cart.spec.ts → exit 0 [ran]
commands: npm test -- cart.spec.ts (fix undone) → exit 1 [ran expect-fail]
commands: backend checks on this hash → exit 0 [ci https://github.com/o/r/actions/runs/123]
```

Provenance of every command line: `[ran]` = run by the verifier in this session on this
hash; `[ran expect-fail]` = a run that must fail (the FIX oracle with the fix undone: its
non-zero exit is the proof); `[ci <ref>]` = the project's own checks on this exact hash; `[reused <what>]` = an
earlier result. OK rests only on `ran` and `ci`; reused evidence may support a KO, never an
OK. **BLOCKED** = the proof cannot run here (missing database, service, memory, credentials):
say what is missing in `blocked:`; it is not a KO and does not count against the unit.

The coordinator acts only on a verdict that `python3 <plugin>/bin/verdict-check.py --hash
<delivered hash>` accepts (exit 0). A rejected verdict is not a verdict and not a KO: rerun
it once with the rejection reasons appended to the verifier's prompt, on the same verifier
model (never the builder's model); rejected again → the unit is `parked` "unverifiable".
`KO: no oracle` and `KO: out of scope` are full KOs, never "OK with notes".

## Model choice

- Always a different model from the builder. The proof is the commands the verifier ran and
  `verdict-check.py`, not the model's opinion, so a unit's verifier may be a cheaper model.
- **Unit verifier** (tier 1-2): an economical Codex model via `codex-task.sh verify`
  ([engines](engines.md)); Codex unavailable → `orchestratore:verifier` on opus.
- **Strong verifier** (opus in Claude Code, the strongest listed model in Codex): every
  tier 3 unit, the final pass on each lane head, and the diagnostician.
- Record builder and verifier model per unit in `RUN.md`; report only models the runtime
  actually confirmed.
