# Merge gate and post-merge check

Steps 5 and 6 of skill §6, and the deploy found at start (§1). Read this before the first
merge of a run.

## Find the deploy (at start)

Look for the post-merge deploy: a `.github/workflows/` job deploying the default branch,
`vercel.json`, a Git-connected host. Write it in `RUN.md` as `pipeline:` with a read-only
check: `gh run list --commit <sha> --workflow <deploy workflow>` for GitHub Actions, `gh api
repos/<owner>/<repo>/commits/<sha>/status` for hosts that post commit statuses. `pipeline:
none` if nothing deploys (CI that only tests is not a deploy).

Auto-merge is on by default: with no `auto_merge_globs` configured, every path outside the
sensitive list may merge on tier 1-2 with required checks green. `auto_merge_globs = []` in
`.orchestratore/config.toml` turns it off.

## Merge gate

Run it on the verified SHA of the tier 1-2 PR:

```bash
python3 <plugin>/bin/merge-gate.py --pr <n> --sha <sha> --tier <max tier> --merge
```

- Exit 0 with `"merged": true` = merged.
- Exit 0 with `"pending": true` = still open (for example a merge queue). Check again before
  counting it merged.
- Exit 1 = the PR waits for the user. Write the reasons in `RUN.md` and do not work around
  them. That lane is now blocked (skill §4) until the user acts.
- A private repository on a free GitHub plan cannot require checks: there the gate always
  needs `--no-required-checks-ok` (the final `OK` on this SHA, below) and, on top of it,
  every check reported on the PR must have passed or been skipped.
- No required checks and no checks on the PR: the final verifier's full gate on this exact
  SHA is the quality proof. When that verdict is `OK`, pass `--no-required-checks-ok`; this
  is the rule, not a loophole. Without that verdict, never pass it.

## Post-merge check

After a merge, follow the `pipeline:` recorded in skill §1.

- `pipeline: none` → the unit stays `merged`, final (report: merged, no deploy observed).
- Otherwise run the recorded check command on the merge SHA:
  - green on it, or on a later merge SHA that contains it (for example after a
    fix-forward) → `in production`;
  - red → open one FIX unit that fixes forward (never revert or force-push on your own). The
    original unit then takes the FIX unit's final state, with the red run as evidence. A red
    again after that fix → park both, no further FIX units;
  - running → check again;
  - no clear green or red within 30 minutes (no run, skipped, cancelled, status not
    observable) → `waiting` with "deploy to confirm".
- You never trigger a deploy yourself.
