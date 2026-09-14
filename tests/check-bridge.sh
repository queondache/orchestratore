#!/usr/bin/env bash
# Gate eseguibile dei bridge dell'orchestratore. Nessuna chiamata reale ai modelli:
# ogni caso passa da --dry-run o da un errore di validazione.
set -uo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"
CX="$ROOT/bin/spawn-cx.sh"
CC="$ROOT/bin/spawn-cc.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/orchestratore-bridge.XXXXXX")"
cleanup() { [ -n "${TMP:-}" ] && [ -d "$TMP" ] && command rm -r -f -- "$TMP"; }
trap cleanup EXIT

PROMPT="$TMP/T-007.md"
printf 'contratto del task\n' > "$PROMPT"
VUOTO="$TMP/vuoto.md"; : > "$VUOTO"

failures=0
ok() { printf 'OK: %s\n' "$1"; }
ko() { printf 'KO: %s\n' "$1"; failures=$((failures + 1)); }

expect_exit() { # expect_exit <atteso> <label> <cmd...>
  local want="$1" label="$2"; shift 2
  "$@" >/dev/null 2>&1
  local got=$?
  if [ "$got" = "$want" ]; then ok "$label (exit $got)"; else ko "$label (atteso $want, ottenuto $got)"; fi
}

expect_stdout() { # expect_stdout <needle> <label> <cmd...>
  local needle="$1" label="$2"; shift 2
  local out; out="$("$@" 2>/dev/null)"
  if printf '%s' "$out" | grep -Fq -- "$needle"; then ok "$label"; else ko "$label — manca: $needle"; fi
}

[ -x "$CX" ] && ok "spawn-cx.sh eseguibile" || ko "spawn-cx.sh eseguibile"
[ -x "$CC" ] && ok "spawn-cc.sh eseguibile" || ko "spawn-cc.sh eseguibile"

# Riga di comando composta: il bridge non decide, riporta quello che gli è stato detto
expect_stdout 'codex exec --yolo -m gpt-5.6-terra -c model_reasoning_effort=medium' \
  "cx compone modello ed effort dichiarati" \
  "$CX" --dry-run gpt-5.6-terra medium "$TMP" "$PROMPT"
expect_stdout "-C $TMP" "cx passa il cwd del progetto" \
  "$CX" --dry-run gpt-5.6-sol high "$TMP" "$PROMPT"
expect_stdout "$TMP/.orchestratore/logs/T-007.log" "cx deriva il log dal task id" \
  "$CX" --dry-run gpt-5.6-sol high "$TMP" "$PROMPT"
expect_stdout 'claude -p --model opus --permission-mode bypassPermissions' \
  "cc compone modello e bypassPermissions" \
  "$CC" --dry-run opus "$TMP" "$PROMPT"
expect_stdout '--output-format json' "cc chiede output json" \
  "$CC" --dry-run sonnet "$TMP" "$PROMPT"
expect_stdout "$TMP/.orchestratore/logs/T-007.log" "cc deriva il log dal task id" \
  "$CC" --dry-run haiku "$TMP" "$PROMPT"

# Validazione: il bridge rifiuta prima di spendere credito
expect_exit 64 "cx rifiuta un numero di argomenti sbagliato" "$CX" --dry-run gpt-5.6-sol high "$TMP"
expect_exit 65 "cx rifiuta un modello non in routing" "$CX" --dry-run gpt-4o high "$TMP" "$PROMPT"
expect_exit 65 "cx rifiuta un effort non ammesso" "$CX" --dry-run gpt-5.6-sol estremo "$TMP" "$PROMPT"
expect_exit 65 "cx rifiuta Luna low" "$CX" --dry-run gpt-5.6-luna low "$TMP" "$PROMPT"
expect_exit 65 "cx rifiuta Terra low" "$CX" --dry-run gpt-5.6-terra low "$TMP" "$PROMPT"
expect_exit 0 "cx accetta Sol low" "$CX" --dry-run gpt-5.6-sol low "$TMP" "$PROMPT"
expect_exit 0 "cx accetta Astra low per escalation" "$CX" --dry-run gpt-6-astra low "$TMP" "$PROMPT"
expect_exit 66 "cx rifiuta un cwd inesistente" "$CX" --dry-run gpt-5.6-sol high "$TMP/assente" "$PROMPT"
expect_exit 66 "cx rifiuta un prompt vuoto" "$CX" --dry-run gpt-5.6-sol high "$TMP" "$VUOTO"
expect_exit 64 "cc rifiuta un numero di argomenti sbagliato" "$CC" --dry-run opus "$TMP"
expect_exit 65 "cc rifiuta un modello non in routing" "$CC" --dry-run fable "$TMP" "$PROMPT"
expect_exit 66 "cc rifiuta un prompt assente" "$CC" --dry-run opus "$TMP" "$TMP/mai-scritto.md"

# Nessuna esecuzione reale in dry-run
if [ -d "$TMP/.orchestratore" ]; then ko "dry-run non crea directory di log"; else ok "dry-run non crea directory di log"; fi

if [ "$failures" -gt 0 ]; then printf 'ROSSO: %d controlli bridge falliti\n' "$failures"; exit 1; fi
printf 'VERDE: bridge conformi\n'
