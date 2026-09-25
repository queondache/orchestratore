#!/usr/bin/env bash
# Funzioni condivise dai bridge Codex e Claude Code.
# Il controller e' l'unico writer di RUN.md; i worker operano in worktree isolati.

bridge_fail() { printf '%s\n' "$1" >&2; exit "${2:-66}"; }

bridge_real_dir() {
  [ -d "$1" ] || return 1
  (CDPATH= cd -- "$1" && pwd -P)
}

bridge_prepare() {
  PROJECT_ROOT="$(bridge_real_dir "$PROJECT_ROOT")" || bridge_fail "project-root inesistente: $PROJECT_ROOT"
  TASK_CWD="$(bridge_real_dir "$TASK_CWD")" || bridge_fail "task-cwd inesistente: $TASK_CWD"
  case "$PROJECT_ROOT$TASK_CWD" in *$'\n'*) bridge_fail 'i percorsi non possono contenere newline' 65 ;; esac
  case "$TASK_ID" in ''|*[!A-Za-z0-9._-]*|.*|-*) bridge_fail "task-id non valido: $TASK_ID" 65 ;; esac
  case "$STAGE" in strategy|build|review|finalize) ;; *) bridge_fail "stage non valido: $STAGE (strategy|build|review|finalize)" 65 ;; esac
  command -v python3 >/dev/null 2>&1 || bridge_fail 'python3 necessario per validare ownership' 69
  python3 -c 'import json,sys
try: value=json.loads(sys.argv[1])
except Exception: raise SystemExit(1)
raise SystemExit(0 if isinstance(value,list) and value and all(isinstance(x,str) and x for x in value) else 1)' "$ALLOWLIST_JSON" || \
    bridge_fail 'allowlist deve essere una lista JSON non vuota' 65

  command -v git >/dev/null 2>&1 || bridge_fail 'git non installato' 69
  PROJECT_GIT_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null)" || bridge_fail "project-root non e un repository Git: $PROJECT_ROOT"
  PROJECT_GIT_ROOT="$(bridge_real_dir "$PROJECT_GIT_ROOT")" || bridge_fail 'git root non accessibile'
  [ "$PROJECT_GIT_ROOT" = "$PROJECT_ROOT" ] || bridge_fail "project-root deve essere il git root: $PROJECT_ROOT"
  TASK_GIT_ROOT="$(git -C "$TASK_CWD" rev-parse --show-toplevel 2>/dev/null)" || bridge_fail "task-cwd non e un worktree Git: $TASK_CWD"
  TASK_GIT_ROOT="$(bridge_real_dir "$TASK_GIT_ROOT")" || bridge_fail 'task git root non accessibile'
  [ "$TASK_GIT_ROOT" = "$TASK_CWD" ] || bridge_fail "task-cwd deve essere il root del worktree: $TASK_CWD"
  [ "$TASK_CWD" != "$PROJECT_ROOT" ] || bridge_fail 'task-cwd deve essere un worktree isolato, non il checkout di controllo'
  PROJECT_COMMON_DIR="$(git -C "$PROJECT_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || bridge_fail 'git common dir del project-root non accessibile'
  TASK_COMMON_DIR="$(git -C "$TASK_CWD" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || bridge_fail 'git common dir del task-cwd non accessibile'
  PROJECT_COMMON_DIR="$(bridge_real_dir "$PROJECT_COMMON_DIR")" || bridge_fail 'git common dir del project-root non valido'
  TASK_COMMON_DIR="$(bridge_real_dir "$TASK_COMMON_DIR")" || bridge_fail 'git common dir del task-cwd non valido'
  [ "$TASK_COMMON_DIR" = "$PROJECT_COMMON_DIR" ] || bridge_fail "task-cwd non appartiene ai worktree del project-root: $TASK_CWD"

  RUN="$PROJECT_ROOT/.orchestratore/RUN.md"
  if [ "$DRY_RUN" -eq 0 ] && [ ! -s "$RUN" ]; then bridge_fail "RUN.md assente o vuoto: $RUN"; fi
  LOG_DIR="$PROJECT_ROOT/.orchestratore/logs"
  LOG="$LOG_DIR/$TASK_ID.$STAGE.log"
}

bridge_prompt() {
  local role
  case "$STAGE" in
    strategy) role='Fase STRATEGY: lavora in sola lettura. Produci strategia delimitata, ownership dei file, dipendenze, rischi, test e criterio di pronto. Non modificare file, Git o stato esterno.' ;;
    build) role='Fase BUILD: implementa esclusivamente il task assegnato nel task worktree. Esegui i test pertinenti. Non fare merge o push. Restituisci diff, SHA/base, comandi ed esiti.' ;;
    review) role='Fase REVIEW: sei il revisore indipendente. Lavora in sola lettura, verifica diff e SHA esatti ed esegui soltanto test autorizzati. Non correggere, non committare e non fare merge. Restituisci OK oppure KO con evidenze e comandi.' ;;
    finalize) role='Fase FINALIZE: sei il gate pre-merge indipendente e lavori in sola lettura. Verifica SHA esatto, review finale, documentazione e almeno un check CI richiesto concluso con successo. Checks assenti, pendenti, falliti o cancellati sono KO. Non modificare, non fare push e non fare merge.' ;;
  esac
  PROMPT_TEXT="Task: $TASK_ID
Stage: $STAGE
Project root di controllo: $PROJECT_ROOT
Task worktree isolato: $TASK_CWD
RUN di controllo: $RUN

$role

Leggi SPEC.md, ROADMAP.md e RUN.md dal project root solo per il contesto necessario. RUN.md e' sola lettura: non modificarlo mai e non scrivere nella directory di controllo. Rispetta owner, perimetro e gate del task. Non delegare ad altri agenti. La risposta finale e' un report strutturato destinato al controller, unico writer seriale di RUN.md."
}

bridge_snapshot() {
  RUN_SNAPSHOT="$(cksum < "$RUN")" || bridge_fail "impossibile leggere RUN.md: $RUN" 74
  CONTROL_SNAPSHOT="$(python3 "$QUI/worktree-snapshot.py" "$PROJECT_ROOT" --exclude-prefix .orchestratore/logs)" || bridge_fail 'impossibile acquisire lo stato del checkout di controllo' 74
  BASE_HEAD="$(git -C "$TASK_CWD" rev-parse --verify 'HEAD^{commit}')" || bridge_fail 'impossibile acquisire HEAD del task worktree' 74
  python3 "$QUI/validate-ownership.py" preflight "$TASK_CWD" "$ALLOWLIST_JSON" || \
    bridge_fail 'task worktree non completamente pulito o non supportato' 74
}

bridge_validate_post() {
  local current
  current="$(cksum < "$RUN")" || bridge_fail 'RUN.md e stato rimosso dal worker' 74
  [ "$current" = "$RUN_SNAPSHOT" ] || bridge_fail 'violazione: il worker ha modificato RUN.md' 74
  current="$(python3 "$QUI/worktree-snapshot.py" "$PROJECT_ROOT" --exclude-prefix .orchestratore/logs)" || bridge_fail 'impossibile validare il checkout di controllo' 74
  [ "$current" = "$CONTROL_SNAPSHOT" ] || bridge_fail 'violazione: il worker ha modificato il checkout di controllo' 74
  if [ "$STAGE" = build ]; then
    python3 "$QUI/validate-ownership.py" postflight "$TASK_CWD" "$BASE_HEAD" "$ALLOWLIST_JSON" || \
      bridge_fail 'consegna build rifiutata dal gate di integrazione ownership' 74
  else
    python3 "$QUI/validate-ownership.py" postflight "$TASK_CWD" "$BASE_HEAD" "$ALLOWLIST_JSON" --read-only || \
      bridge_fail "violazione: lo stage $STAGE ha modificato il task worktree" 74
  fi
}

bridge_require_codex_guard() {
  [ -x "$QUI/../hooks/guard-run.sh" ] && [ -s "$QUI/../hooks/hooks.json" ] || \
    bridge_fail 'guard orchestratore assente dal plugin; dispatch Codex rifiutato' 69
  codex plugin list --json 2>/dev/null | python3 "$QUI/verify-hook-install.py" codex "$QUI/.." || \
    bridge_fail 'plugin orchestratore/hook esatto non abilitato in Codex; dispatch rifiutato' 69
}

bridge_require_claude_guard() {
  [ -x "$QUI/../hooks/guard-run.sh" ] && [ -s "$QUI/../hooks/hooks.json" ] || \
    bridge_fail 'guard orchestratore assente dal plugin; dispatch Claude rifiutato' 69
  claude plugin list --json 2>/dev/null | python3 "$QUI/verify-hook-install.py" claude "$QUI/.." || \
    bridge_fail 'plugin orchestratore/hook esatto non abilitato in Claude; dispatch rifiutato' 69
}
