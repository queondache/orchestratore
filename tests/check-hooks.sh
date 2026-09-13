#!/usr/bin/env bash
# Gate eseguibile degli hook dell'orchestratore. Nessun comando reale viene eseguito:
# si alimenta guard-run.sh con payload JSON e si controlla solo l'exit code.
set -uo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"
GUARD="$ROOT/hooks/guard-run.sh"
SESS="$ROOT/hooks/session-run-state.sh"
HOOKS_JSON="$ROOT/hooks/hooks.json"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/orchestratore-hooks.XXXXXX")"
cleanup() { [ -n "${TMP:-}" ] && [ -d "$TMP" ] && command rm -r -f -- "$TMP"; }
trap cleanup EXIT

CON_RUN="$TMP/con-run"
SENZA_RUN="$TMP/senza-run"
mkdir -p "$CON_RUN/.orchestratore" "$SENZA_RUN"
printf 'runtime=cc pid=1 session=test updated=ora\n' > "$CON_RUN/.orchestratore/brain.lock"

failures=0
ok() { printf 'OK: %s\n' "$1"; }
ko() { printf 'KO: %s\n' "$1"; failures=$((failures + 1)); }

payload() { # payload <cwd> <comando>
  python3 -c '
import json, sys
print(json.dumps({"tool_name": "Bash", "cwd": sys.argv[1], "tool_input": {"command": sys.argv[2]}}))
' "$1" "$2"
}

expect_guard() { # expect_guard <atteso> <cwd> <comando> <label>
  local want="$1" cwd="$2" cmd="$3" label="$4" body
  body="$(payload "$cwd" "$cmd")"
  printf '%s' "$body" | "$GUARD" >/dev/null 2>&1
  local got=${PIPESTATUS[1]}
  if [ "$got" = "$want" ]; then ok "$label (exit $got)"; else ko "$label (atteso $want, ottenuto $got)"; fi
}

[ -x "$GUARD" ] && ok "guard-run.sh eseguibile" || ko "guard-run.sh eseguibile"
[ -x "$SESS" ] && ok "session-run-state.sh eseguibile" || ko "session-run-state.sh eseguibile"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert 'PreToolUse' in d['hooks'] and 'SessionStart' in d['hooks']" "$HOOKS_JSON" \
  && ok "hooks.json dichiara PreToolUse e SessionStart" || ko "hooks.json dichiara PreToolUse e SessionStart"
grep -q 'CLAUDE_PLUGIN_ROOT' "$HOOKS_JSON" && ok "hooks.json usa CLAUDE_PLUGIN_ROOT" || ko "hooks.json usa CLAUDE_PLUGIN_ROOT"

# Con run attivo: i comandi vietati dalla skill vengono bloccati (exit 2)
expect_guard 2 "$CON_RUN" 'git push --force origin main' "blocca il force-push"
expect_guard 2 "$CON_RUN" 'git push --force-with-lease' "blocca il force-with-lease"
expect_guard 2 "$CON_RUN" 'git push -f origin main' "blocca il force-push con -f e argomenti"
expect_guard 2 "$CON_RUN" 'git push -f' "blocca il force-push corto, -f in fondo alla riga"
expect_guard 2 "$CON_RUN" 'cd sub && git push -f' "blocca il force-push corto in un comando composto"
expect_guard 2 "$CON_RUN" 'git reset --hard HEAD~3' "blocca il reset --hard"
expect_guard 2 "$CON_RUN" 'git clean -fdx' "blocca il clean distruttivo"
expect_guard 2 "$CON_RUN" 'git branch -D m/vecchia' "blocca la cancellazione di branch"
expect_guard 2 "$CON_RUN" 'gh pr merge 12 --squash --admin' "blocca il merge che scavalca i check"
expect_guard 2 "$CON_RUN" 'rm -rf build' "blocca la cancellazione ricorsiva forzata"

# Con run attivo: il lavoro normale passa
expect_guard 0 "$CON_RUN" 'git status --short' "lascia passare git status"
expect_guard 0 "$CON_RUN" 'git push origin m/nuova' "lascia passare un push normale"
expect_guard 0 "$CON_RUN" 'gh pr merge 12 --squash' "lascia passare il merge al gate"
expect_guard 0 "$CON_RUN" 'npm test' "lascia passare la suite"
expect_guard 0 "$CON_RUN" 'grep -f pattern.txt src/app.ts' "lascia passare grep -f, che non e un push"

# Senza run attivo: l'hook non interferisce mai
expect_guard 0 "$SENZA_RUN" 'git push --force origin main' "fuori da un run non blocca nulla"
expect_guard 0 "$SENZA_RUN" 'git reset --hard HEAD~1' "fuori da un run non blocca il reset"

# Payload malformato: il lavoro normale passa, ma il distruttivo non si infila
# approfittando di un parser che non ha capito niente.
printf 'non json' | "$GUARD" >/dev/null 2>&1
[ $? = 0 ] && ok "payload malformato non blocca il lavoro normale" || ko "payload malformato non blocca il lavoro normale"

# Senza python3 il guardrail non deve spegnersi in silenzio: cade sul testo grezzo.
SENZA_PY="$TMP/bin-vuoto"
mkdir -p "$SENZA_PY"
for c in sh bash cat printf grep sed; do
  src="$(command -v "$c" 2>/dev/null)"
  [ -n "$src" ] && ln -sf "$src" "$SENZA_PY/$c"
done
BODY_FORZA="$(payload "$CON_RUN" 'git push --force origin main')"
BODY_SANO="$(payload "$CON_RUN" 'git status --short')"
# Senza parser non si puo' leggere il campo cwd: vale la directory del processo,
# che nella sessione reale e' proprio quella del progetto. Il test la riproduce.
( cd "$CON_RUN" && printf '%s' "$BODY_FORZA" | env PATH="$SENZA_PY" "$GUARD" >/dev/null 2>&1; exit "${PIPESTATUS[1]}" )
[ $? = 2 ] && ok "senza python3 blocca comunque il force-push" || ko "senza python3 blocca comunque il force-push"
( cd "$CON_RUN" && printf '%s' "$BODY_SANO" | env PATH="$SENZA_PY" "$GUARD" >/dev/null 2>&1; exit "${PIPESTATUS[1]}" )
[ $? = 0 ] && ok "senza python3 lascia passare il lavoro normale" || ko "senza python3 lascia passare il lavoro normale"
( cd "$SENZA_RUN" && printf '%s' "$BODY_FORZA" | env PATH="$SENZA_PY" "$GUARD" >/dev/null 2>&1; exit "${PIPESTATUS[1]}" )
[ $? = 0 ] && ok "senza python3 e senza run non interferisce" || ko "senza python3 e senza run non interferisce"

# SessionStart: silenzioso senza run, informativo con run.
# Niente pipe verso grep -q: con pipefail il SIGPIPE falserebbe l'esito.
OUT_SENZA="$( cd "$SENZA_RUN" && "$SESS" )"
[ -z "$OUT_SENZA" ] && ok "session hook silenzioso senza run" || ko "session hook silenzioso senza run"
printf 'stato: attivo\ncervello: cc-fable\n' > "$CON_RUN/.orchestratore/run.md"
OUT_CON="$( cd "$CON_RUN" && "$SESS" )"
case "$OUT_CON" in *"stato: attivo"*) ok "session hook riporta lo stato del run" ;; *) ko "session hook riporta lo stato del run" ;; esac
case "$OUT_CON" in *"brain.lock"*) ok "session hook segnala il lock" ;; *) ko "session hook segnala il lock" ;; esac

if [ "$failures" -gt 0 ]; then printf 'ROSSO: %d controlli hook falliti\n' "$failures"; exit 1; fi
printf 'VERDE: hook conformi\n'
