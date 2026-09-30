# Merge gate and post-merge check

Steps 5 and 6 of skill §6. Read this before the first merge of a run.

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
- Use `--no-required-checks-ok` only when the base has no required checks and the full gate
  passed on this exact SHA.

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
