#!/usr/bin/env bash
# Deterministic controller invariants.  No command here invokes Codex or Claude.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CTL="$ROOT/bin/orchestratore-controller"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
DB="$WORK/state.sqlite3"

need() {
  local argv=("$@")
  case " ${argv[*]} " in
    *" complete "*|*" fail "*|*" checkpoint "*|*" start "*|*" add-task "*) argv+=(--holder owner-a) ;;
    *" schedule "*) [[ " ${argv[*]} " == *" --dry-run "* ]] || argv+=(--holder owner-a) ;;
  esac
  "${argv[@]}" >/dev/null
}
has() { rg -q "$2" <<<"$1"; }

need "$CTL" --db "$DB" init
need "$CTL" --db "$DB" start run-a --config '{"brain_model":"gpt-6-astra","brain_effort":"medium"}'
need "$CTL" --db "$DB" add-task run-a task-a 'persistent flow' --builders 2
need "$CTL" --db "$DB" acquire run-a owner-a --seconds 60

# Strategy is Claude and an inspection plan cannot mutate state or spend credit.
OUT="$($CTL --db "$DB" schedule run-a --dry-run)"
has "$OUT" '"action": "strategy"'
has "$OUT" '"provider": "claude"'
has "$($CTL --db "$DB" status run-a)" '"owner_provider": null'

# The state machine must retain finalization after an implementation succeeds.
need "$CTL" --db "$DB" schedule run-a
need "$CTL" --db "$DB" complete task-a --evidence strategy-ok
OUT="$($CTL --db "$DB" schedule run-a --dry-run)"
has "$OUT" '"action": "build"'
has "$OUT" '"model": "gpt-5.6-terra"'
has "$OUT" '"effort": "medium"'
need "$CTL" --db "$DB" complete task-a --evidence build-ok
need "$CTL" --db "$DB" complete task-a --evidence review-ok
OUT="$($CTL --db "$DB" schedule run-a --dry-run)"
has "$OUT" '"action": "finalize"'
has "$($CTL --db "$DB" status run-a)" '"implementation_done": 1'
# Review is proven but finalize was never actually attempted (no `fail` at
# finalize stage yet): D, not E. E is reserved for an attempted-but-incomplete
# finalize, asserted separately below with task-e.
has "$($CTL --db "$DB" status run-a)" '"recovery_case": "D"'
need "$CTL" --db "$DB" complete task-a --evidence '{"pr":"approved-wait","merge":"approved-wait","docs":true}'
has "$($CTL --db "$DB" status run-a)" '"stage": "done"'
has "$($CTL --db "$DB" status run-a)" '"finalized": 1'

# Checkpoint and rollover are explicit at 50 and 70; compacting a runtime is irrelevant.
need "$CTL" --db "$DB" add-task run-a task-b rollover
need "$CTL" --db "$DB" checkpoint task-b 50 --summary 'safe boundary' --head abc123 --fingerprint 'worktree:123'
has "$($CTL --db "$DB" schedule run-a --dry-run)" '"action": "checkpoint"'
has "$($CTL --db "$DB" status run-a)" 'safe boundary'
has "$($CTL --db "$DB" status run-a)" 'worktree:123'
need "$CTL" --db "$DB" checkpoint task-b 70 --summary 'fresh session needed' --head def456
has "$($CTL --db "$DB" schedule run-a --dry-run)" '"action": "rollover"'

# A lease prevents a second brain, and retries park after two attempts per two approaches.
need "$CTL" --db "$DB" acquire brain owner-a --seconds 60
OUT="$($CTL --db "$DB" acquire brain owner-b --seconds 60)"; has "$OUT" 'false'
need "$CTL" --db "$DB" release brain owner-a
need "$CTL" --db "$DB" fail task-b same-gate --evidence 'failure-duplicate'
has "$($CTL --db "$DB" fail task-b same-gate --evidence 'failure-duplicate' --holder owner-a)" 'deduplicated'
for n in 1 2 3; do need "$CTL" --db "$DB" fail task-b "gate-$n" --evidence "failure-$n"; done
has "$($CTL --db "$DB" status run-a)" '"stage": "parked"'

# A failure signature is global to task+stage, across both approaches.
# A,B,A consumes only two failures; C,D exhaust the remaining two attempts.
need "$CTL" --db "$DB" add-task run-a task-d aba-dedup
need "$CTL" --db "$DB" fail task-d A --evidence e1
need "$CTL" --db "$DB" fail task-d B --evidence e2
has "$($CTL --db "$DB" status run-a)" '"id": "task-d"'
[[ "$(rg -c '"approach": 2' <<<"$($CTL --db "$DB" status run-a)")" -ge 1 ]]
OUT="$($CTL --db "$DB" fail task-d A --evidence e3 --holder owner-a)"
has "$OUT" '"result": "deduplicated"'
OUT="$($CTL --db "$DB" fail task-d A --evidence e4 --holder owner-a)"
has "$OUT" '"result": "deduplicated"'
need "$CTL" --db "$DB" fail task-d C --evidence e5
need "$CTL" --db "$DB" fail task-d D --evidence e6
has "$($CTL --db "$DB" status run-a)" '"stage": "parked"'

# Recovery classification A-E is frozen behavior, not incidental phrasing:
# A/B/C follow missing strategy/build/review evidence; D is review-proven with
# finalize never attempted; E is finalize attempted (a real `fail` recorded at
# that stage) but still incomplete; done means no recovery case at all.
need "$CTL" --db "$DB" add-task run-a task-e recovery-freeze
has "$($CTL --db "$DB" status run-a)" '"recovery_case": "A"'
need "$CTL" --db "$DB" complete task-e --evidence strategy
has "$($CTL --db "$DB" status run-a)" '"recovery_case": "B"'
need "$CTL" --db "$DB" complete task-e --evidence build
has "$($CTL --db "$DB" status run-a)" '"recovery_case": "C"'
need "$CTL" --db "$DB" complete task-e --evidence review
has "$($CTL --db "$DB" status run-a)" '"recovery_case": "D"'
need "$CTL" --db "$DB" fail task-e pr-blocked --evidence 'pr opened, checks red'
has "$($CTL --db "$DB" status run-a)" '"recovery_case": "E"'
need "$CTL" --db "$DB" complete task-e --evidence '{"pr":"merged","merge":"merged","docs":true}'
has "$($CTL --db "$DB" status run-a)" '"recovery_case": null'

# An interrupted finalizer reopens from finalize, and incomplete final evidence
# cannot create DONE.  Separate CLI invocations simulate a controller restart.
need "$CTL" --db "$DB" add-task run-a task-c partial-finalize
need "$CTL" --db "$DB" complete task-c --evidence strategy
need "$CTL" --db "$DB" complete task-c --evidence build
need "$CTL" --db "$DB" complete task-c --evidence review
if "$CTL" --db "$DB" complete task-c --evidence '{"pr":"#3"}' >/dev/null 2>&1; then
  echo "incomplete final evidence created DONE" >&2; exit 1
fi
has "$($CTL --db "$DB" schedule run-a --dry-run)" '"task": "task-c"'
has "$($CTL --db "$DB" schedule run-a --dry-run)" '"action": "finalize"'
need "$CTL" --db "$DB" complete task-c --evidence '{"pr":"merged","merge":"merged","docs":true}'

# A stale lease expires safely; configuration can route build to the other provider.
need "$CTL" --db "$DB" acquire stale owner-a --seconds -1
has "$($CTL --db "$DB" acquire stale owner-b --seconds 60)" 'true'
need "$CTL" --db "$DB" start run-config --config '{"build_provider":"codex","build_model":"gpt-5.6-terra","build_effort":"medium"}'
need "$CTL" --db "$DB" add-task run-config task-config configured
need "$CTL" --db "$DB" acquire run-config owner-a --seconds 60
need "$CTL" --db "$DB" complete task-config --evidence strategy
OUT="$($CTL --db "$DB" dispatch run-config --dry-run)"
has "$OUT" 'spawn-cx.sh'
has "$OUT" '"gpt-5.6-terra"'
has "$OUT" '"task": "task-config"'
has "$OUT" 'Esegui solo la sezione task task-config'
if has "$OUT" 'prompt-file'; then echo "dispatch retained prompt-file" >&2; exit 1; fi

# Every action receives its own task id and deterministic stdin contract.
need "$CTL" --db "$DB" add-task run-config task-config-2 configured-2
need "$CTL" --db "$DB" complete task-config-2 --evidence strategy
OUT="$($CTL --db "$DB" dispatch run-config --dry-run --cwd "$WORK")"
has "$OUT" 'Esegui solo la sezione task task-config'
has "$OUT" 'Esegui solo la sezione task task-config-2'
[[ "$(rg -c 'Esegui solo la sezione task task-config' <<<"$OUT")" -ge 2 ]]
if "$CTL" --db "$DB" dispatch run-config --execute --holder owner-a >/dev/null 2>&1; then
  echo "dispatch execute accepted missing cwd" >&2; exit 1
fi
mkdir -p "$WORK/.orchestratore" "$WORK/fakebin"
printf '# RUN\n' > "$WORK/.orchestratore/RUN.md"
printf '#!/usr/bin/env bash\ncat\n' > "$WORK/fakebin/codex"
chmod +x "$WORK/fakebin/codex"
PATH="$WORK/fakebin:$PATH" "$CTL" --db "$DB" dispatch run-config --execute --cwd "$WORK" --holder owner-a >/dev/null
has "$(cat "$WORK/.orchestratore/logs/task-config.log")" 'sezione task task-config.'
has "$(cat "$WORK/.orchestratore/logs/task-config-2.log")" 'sezione task task-config-2.'
if has "$(cat "$WORK/.orchestratore/logs/task-config.log")" 'sezione task task-config-2.'; then
  echo "task-config reused another task prompt" >&2; exit 1
fi

# Three ready builders never dispatch more than two global slots.
need "$CTL" --db "$DB" start run-builders
need "$CTL" --db "$DB" acquire run-builders owner-a --seconds 60
for n in 1 2 3; do need "$CTL" --db "$DB" add-task run-builders "builder-$n" builder; done
need "$CTL" --db "$DB" complete builder-1 --evidence strategy
need "$CTL" --db "$DB" complete builder-2 --evidence strategy
if "$CTL" --db "$DB" complete builder-3 --evidence strategy --holder owner-a >/dev/null 2>&1; then
  echo "third builder exceeded global cap" >&2; exit 1
fi
OUT="$($CTL --db "$DB" schedule run-builders --dry-run)"
[[ "$(rg -c '"action": "build"' <<<"$OUT")" -eq 2 ]]

# The SQLite lease is authoritative for every mutation, not just a projection:
# start/add-task without --holder must fail, a wrong holder must fail, and an
# expired lease must be recoverable by a new holder via `acquire`, never stuck.
if "$CTL" --db "$DB" start run-nolease >/dev/null 2>&1; then
  echo "start accepted without --holder" >&2; exit 1
fi
need "$CTL" --db "$DB" start run-lease
if "$CTL" --db "$DB" add-task run-lease task-nolease solo >/dev/null 2>&1; then
  echo "add-task accepted without --holder" >&2; exit 1
fi
if "$CTL" --db "$DB" add-task run-lease task-wrong solo --holder owner-x >/dev/null 2>&1; then
  echo "add-task accepted a holder without a valid lease" >&2; exit 1
fi
need "$CTL" --db "$DB" add-task run-lease task-lease solo

need "$CTL" --db "$DB" start run-expired --holder owner-a --seconds -1
if "$CTL" --db "$DB" add-task run-expired task-expired solo --holder owner-a >/dev/null 2>&1; then
  echo "add-task accepted an expired lease" >&2; exit 1
fi
need "$CTL" --db "$DB" acquire run-expired owner-b --seconds 60
"$CTL" --db "$DB" add-task run-expired task-recovered solo --holder owner-b >/dev/null

# Cheapest-capable lower bounds are enforced (a mutation to the routing floor goes red).
if "$CTL" --db "$WORK/bad.sqlite3" start bad --config '{"brain_model":"gpt-6-astra","brain_effort":"low"}' --holder owner-a >/dev/null 2>&1; then
  echo "brain Astra medium invariant accepted low effort" >&2; exit 1
fi

(cd "$ROOT" && python3 -m unittest controller.test_transitions -v)

echo "check-controller: ok"
