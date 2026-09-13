# -*- coding: utf-8 -*-
"""Analizzatore della guardia dell'orchestratore.

Legge il payload PreToolUse su stdin e decide se il comando e' fra quelli che la skill
vieta in modo assoluto durante un run. Esce 2 per bloccare, 0 per lasciar passare.

Perche' in Python e non in shell: la versione in bash e' stata bocciata cinque volte, e
sempre per lo stesso motivo di fondo. Un confronto a pattern non sa distinguere un comando
da una stringa che parla di quel comando, quindi o lascia passare le varianti o blocca i
messaggi di commit e le righe scritte in lessons.md. Qui la riga di comando viene tokenizzata
rispettando le virgolette, i documenti inline vengono trattati come dato e non come codice, e
l'analisi guarda il programma e il suo sottocomando invece di cercare sottostringhe.

MODELLO DI MINACCIA
Chi sbaglia per fretta, non chi vuole aggirare di proposito. Copre le forme che un worker
scrive davvero, anche distratto: flag lunghi e corti anche combinati, abbreviazioni che git
accetta, refspec forzate, wrapper come sudo, env, timeout e xargs, comandi annidati in una
sostituzione o in `sh -c`, e comandi su piu' righe.

Limiti noti e accettati: un comando costruito a runtime non e' leggibile. `$G push -f` con G
assegnata altrove, un flag che arriva dallo stdin (`echo -f | xargs git push`), un alias
definito in una sessione precedente. Per saperlo bisognerebbe eseguire il comando. Chi scrive
queste forme sta aggirando la guardia di proposito: la barriera vera e' il permission mode
del runtime, non questo file.
"""
import json
import re
import shlex
import sys

# Caratteri che chiudono un comando. shlex li aggrega ("&&", ";\n"), quindi non si
# confronta il token intero ma si guarda se e' fatto solo di questi.
CARATTERI_SEPARATORE = set(";&|()<>{}`\n")

# Programmi che eseguono un altro comando: si saltano per arrivare a quello vero.
WRAPPER = {
    "env", "sudo", "command", "nice", "nohup", "time", "timeout", "ionice",
    "xargs", "exec", "builtin", "stdbuf", "setsid",
}
SHELL = {"sh", "bash", "zsh", "dash", "ksh"}
# Parole chiave di shell che stanno subito prima del comando in un costrutto composto.
# `for` e `in` non ci sono: non precedono mai un comando, quindi saltarle non cambia
# niente, e una voce che non cambia niente e' protezione finta.
PAROLE_CHIAVE = {"do", "then", "else", "elif", "!", "if", "while", "until"}
# Opzioni dei wrapper che portano un valore separato: si salta anche quello.
OPZIONE_CON_VALORE = {"-s", "-k", "-u", "-n", "-I", "-P", "--signal", "--user"}


def esci(motivo):
    sys.stderr.write(
        "orchestratore: comando vietato durante un run attivo (%s).\n" % motivo)
    sys.stderr.write(
        "La skill lo esclude sempre: chiudi il checkpoint e chiedi ad Andrea.\n")
    sys.exit(2)


def togli_documenti_inline(cmd):
    """Il corpo di un heredoc e' dato, non codice: un messaggio di commit multi-riga o una
    lezione scritta in lessons.md puo' nominare qualunque comando senza eseguirlo."""
    righe = cmd.split("\n")
    tenute = []
    i = 0
    while i < len(righe):
        riga = righe[i]
        tenute.append(riga)
        aperture = re.findall(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", riga)
        if aperture:
            fine = aperture[-1][1]
            i += 1
            while i < len(righe) and righe[i].strip() != fine:
                i += 1
        i += 1
    return "\n".join(tenute)


def unisci_continuazioni(cmd):
    """La barra rovesciata a fine riga e' una continuazione: la shell la toglie prima di
    leggere il comando, e finche' non la togliamo anche noi il comando della riga dopo
    resta attaccato al programma della riga prima."""
    return cmd.replace("\\\n", " ")


def tokenizza(cmd):
    """Token che rispettano le virgolette: una stringa quotata resta un token solo, quindi
    non puo' essere scambiata per una sequenza di comandi."""
    try:
        # L'a capo separa due comandi quanto il punto e virgola: senza questo shlex lo
        # tratta come spazio e un comando su piu' righe diventa un segmento solo.
        lex = shlex.shlex(cmd, posix=True, punctuation_chars="();<>|&`\n")
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        # virgolette non bilanciate: meglio non inventarsi una lettura del comando
        return []


def e_separatore(tok):
    return bool(tok) and all(c in CARATTERI_SEPARATORE for c in tok)


def segmenta(token):
    segmento = []
    for t in token:
        if e_separatore(t):
            if segmento:
                yield segmento
            segmento = []
        else:
            segmento.append(t)
    if segmento:
        yield segmento


def pulisci(tok):
    return tok.lstrip("$(\\").rstrip(")")


def flag_corto_con(tok, lettera):
    return tok.startswith("-") and not tok.startswith("--") and lettera in tok[1:]


def salta_prefissi(tok):
    """Salta wrapper, parole chiave, assegnazioni e opzioni dei wrapper. Ritorna l'indice
    del programma vero, oppure None. Se incontra una shell con -c, o eval, ritorna il
    comando annidato da analizzare a parte."""
    i = 0
    while i < len(tok):
        t = tok[i]
        # Per riconoscere wrapper e shell conta il nome del programma, non il path
        # scritto: /usr/bin/timeout vale quanto timeout. Per tutto il resto serve il
        # token intero, altrimenti un assegnazione come PATH=/x diventa irriconoscibile.
        nome = t.rsplit("/", 1)[-1] if "/" in t else t
        if nome in SHELL:
            j = i + 1
            while j < len(tok) and tok[j].startswith("-"):
                # `bash -c`, `bash -lc`, `sh -xc`: dopo l'opzione con la c viene il comando
                if "c" in tok[j][1:] and not tok[j].startswith("--"):
                    if j + 1 < len(tok):
                        return ("annidato", tok[j + 1])
                    return (None, None)
                j += 1
            i = j
            continue
        if nome == "eval":
            return ("annidato", " ".join(tok[i + 1:]))
        if nome in WRAPPER or nome in PAROLE_CHIAVE:
            i += 1
            continue
        if "=" in t and not t.startswith("-") and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            i += 1
            continue
        if t.startswith("-"):
            if t in OPZIONE_CON_VALORE:
                i += 2
            else:
                i += 1
            continue
        if re.match(r"^[0-9]+[smhd]?$", t):
            i += 1
            continue
        return ("programma", i)
    return (None, None)


def analizza_push(args):
    for a in args:
        if a.startswith("--"):
            if a.startswith("--for") or a == "--mirror":
                esci("force-push")
            if a.startswith("--de") or a == "--prune":
                esci("cancellazione di branch remoto")
            continue
        if a.startswith("+"):
            esci("force-push")
        if a.startswith(":"):
            esci("cancellazione di branch remoto")
        if a.startswith("-"):
            if flag_corto_con(a, "f"):
                esci("force-push")
            if flag_corto_con(a, "d"):
                esci("cancellazione di branch remoto")


def analizza_git(tok, i):
    for t in tok[i + 1:]:
        if re.match(r"^alias\.[^=]*=.*push", t) or re.match(r"^remote\..*\.push=\+", t):
            esci("force-push nascosto in una configurazione")
    j = i + 1
    while j < len(tok):
        t = tok[j]
        if t in ("-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
            j += 2
        elif t.startswith("-"):
            j += 1
        else:
            break
    if j >= len(tok):
        return
    sub, args = tok[j], tok[j + 1:]
    if sub == "push":
        analizza_push(args)
    elif sub == "reset":
        for a in args:
            if a.startswith("--h") and a != "--help":
                esci("reset --hard")
    elif sub == "clean":
        forza = any(a == "--force" or flag_corto_con(a, "f") for a in args)
        ricorsiva = any(a == "--directories" or flag_corto_con(a, "d") for a in args)
        if forza and ricorsiva:
            esci("git clean distruttivo")
    elif sub == "branch":
        canc = any(a.startswith("--de") or flag_corto_con(a, "d") or flag_corto_con(a, "D")
                   for a in args)
        forz = any(a == "--force" or flag_corto_con(a, "f") or flag_corto_con(a, "D")
                   for a in args)
        if canc and forz:
            esci("cancellazione forzata di branch")


def analizza_rm(args):
    forza = any(a == "--force" or flag_corto_con(a, "f") for a in args)
    ricorsiva = any(a == "--recursive" or flag_corto_con(a, "r") or flag_corto_con(a, "R")
                    for a in args)
    if forza and ricorsiva:
        esci("cancellazione ricorsiva forzata")


def analizza_find(args):
    for k, a in enumerate(args):
        if a == "-delete":
            esci("cancellazione ricorsiva forzata")
        if a in ("-exec", "-execdir") and k + 1 < len(args):
            if args[k + 1].rsplit("/", 1)[-1] == "rm":
                esci("cancellazione ricorsiva forzata")


def analizza_gh(args):
    metodo = ""
    for k, a in enumerate(args):
        if a == "--admin":
            esci("merge che scavalca i check")
        if a.startswith("-X") and len(a) > 2:
            metodo = a[2:]
        elif a == "-X" and k + 1 < len(args):
            metodo = args[k + 1]
        elif a.startswith("--method="):
            metodo = a.split("=", 1)[1]
        elif a == "--method" and k + 1 < len(args):
            metodo = args[k + 1]
    if metodo.upper() == "DELETE" and "api" in args:
        esci("cancellazione via API GitHub")


def analizza_comando(cmd, profondita=0):
    if profondita > 3:
        return
    token = [t if e_separatore(t) else pulisci(t)
             for t in tokenizza(unisci_continuazioni(togli_documenti_inline(cmd)))]
    for segmento in segmenta(token):
        segmento = [t for t in segmento if t]
        if not segmento:
            continue
        if "#" in segmento:
            segmento = segmento[:segmento.index("#")]
        if not segmento:
            continue
        esito, valore = salta_prefissi(segmento)
        if esito == "annidato":
            analizza_comando(valore, profondita + 1)
            continue
        if esito != "programma":
            continue
        i = valore
        prog = segmento[i].rsplit("/", 1)[-1]
        if prog == "git":
            analizza_git(segmento, i)
        elif prog == "rm":
            analizza_rm(segmento[i + 1:])
        elif prog == "find":
            analizza_find(segmento[i + 1:])
        elif prog == "gh":
            analizza_gh(segmento[i + 1:])


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    cmd = payload.get("tool_input", {}).get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        sys.exit(0)
    analizza_comando(cmd)
    sys.exit(0)


if __name__ == "__main__":
    main()
