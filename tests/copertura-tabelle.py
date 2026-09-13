# -*- coding: utf-8 -*-
"""Oracolo per le tabelle dell'analizzatore della guardia.

Ogni voce di WRAPPER, SHELL, PAROLE_CHIAVE, OPZIONI_CON_VALORE, ARGOMENTO_POSIZIONALE e
OPZIONE_SHELL_CON_VALORE deve avere un comando che la esercita davvero. Una voce senza
comando e' un pezzo che nessun test difende: sembra protezione e non lo e'. Qui le tabelle
si confrontano con i casi una a una, quindi aggiungere una voce senza il caso corrispondente
fa fallire il gate.

I casi delle opzioni con valore si generano dalla tabella stessa, con un valore fittizio:
se l'analisi non salta il valore, quel valore diventa il programma e il comando vietato non
viene visto, quindi il test va rosso. L'oracolo e' vero, non decorativo.

Stampa una riga TSV per caso: <atteso> <comando> <etichetta>. Il gate degli hook la
trasforma in un payload vero e controlla l'exit code.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
import guard_run  # noqa: E402

PF = "push -" + "f"
FORZA = "git %s origin main" % PF

# Wrapper: il comando vero viene dopo, con gli operandi che quel wrapper pretende.
CASI_WRAPPER = {
    "env": "env %s",
    "sudo": "sudo %s",
    "doas": "doas %s",
    "command": "command %s",
    "nice": "nice %s",
    "nohup": "nohup %s",
    "time": "time %s",
    "timeout": "timeout 30 %s",
    "ionice": "ionice -c2 %s",
    "xargs": "echo main | xargs %s",
    "exec": "exec %s",
    "builtin": "builtin %s",
    "stdbuf": "stdbuf -o0 %s",
    "setsid": "setsid %s",
    "flock": "flock /tmp/lock %s",
    "caffeinate": "caffeinate %s",
    "chroot": "chroot /mnt %s",
    "strace": "strace -f %s",
}

# Shell: il comando arriva come stringa dopo -c, e va analizzato a parte.
CASI_SHELL = {n: "%s -c '%s'" % (n, FORZA) for n in ("sh", "bash", "zsh", "dash", "ksh")}

# Parole chiave: ognuna deve stare subito prima del comando vietato, altrimenti non e'
# lei a permettere l'analisi e la voce non serve a niente.
CASI_PAROLE = {
    "do": "for b in main; do %s; done" % FORZA,
    "then": "if true; then %s; fi" % FORZA,
    "else": "if false; then true; else %s; fi" % FORZA,
    "elif": "if false; then true; elif %s; then true; fi" % FORZA,
    "!": "! %s" % FORZA,
    "if": "if %s; then true; fi" % FORZA,
    "while": "while %s; do true; done" % FORZA,
    "until": "until %s; do true; done" % FORZA,
}

# Operandi che stanno fra il wrapper e il comando: senza saltarli, l'operando diventa il
# programma e il comando vietato sparisce dall'analisi.
CASI_POSIZIONALE = {
    "timeout": "timeout 1.5 %s" % FORZA,
    "flock": "flock /tmp/lock %s" % FORZA,
    "chroot": "chroot /mnt %s" % FORZA,
}

# Lettere finali che portano un valore in un'opzione di shell: `bash -o pipefail -c`,
# `bash -euo pipefail -c`, `bash -O globstar -c`.
CASI_SHELL_VALORE = {
    "o": "bash -o pipefail -c '%s'" % FORZA,
    "O": "bash -O globstar -c '%s'" % FORZA,
}

# Prefisso con cui invocare ogni wrapper quando si prova una delle sue opzioni con valore.
# Gli operandi posizionali vengono dopo le opzioni, come vuole il wrapper.
CODA_WRAPPER = {"timeout": "30 ", "flock": "/tmp/lock ", "chroot": "/mnt "}


def casi_opzioni():
    """Un caso per ogni coppia programma-opzione, generato dalla tabella dell'analizzatore."""
    casi = {}
    for prog in sorted(guard_run.OPZIONI_CON_VALORE):
        for opz in sorted(guard_run.OPZIONI_CON_VALORE[prog]):
            prefisso = "echo main | " if prog == "xargs" else ""
            casi[(prog, opz)] = "%s%s %s X %s%s" % (
                prefisso, prog, opz, CODA_WRAPPER.get(prog, ""), FORZA)
    return casi


def coppie_attese():
    return {(p, o) for p, opzioni in guard_run.OPZIONI_CON_VALORE.items() for o in opzioni}


def main():
    tabelle = [
        ("WRAPPER", set(guard_run.WRAPPER),
         {k: v % FORZA for k, v in CASI_WRAPPER.items()}, "wrapper"),
        ("SHELL", set(guard_run.SHELL), CASI_SHELL, "shell"),
        ("PAROLE_CHIAVE", set(guard_run.PAROLE_CHIAVE), CASI_PAROLE, "parola chiave"),
        ("ARGOMENTO_POSIZIONALE", set(guard_run.ARGOMENTO_POSIZIONALE), CASI_POSIZIONALE,
         "operando del wrapper"),
        ("OPZIONE_SHELL_CON_VALORE_FINALE", set(guard_run.OPZIONE_SHELL_CON_VALORE_FINALE),
         CASI_SHELL_VALORE, "opzione di shell che finisce per"),
        ("OPZIONI_CON_VALORE", coppie_attese(), casi_opzioni(), "opzione con valore"),
    ]
    righe = []
    for nome, tabella, casi, etichetta in tabelle:
        senza_caso = sorted(str(v) for v in tabella - set(casi))
        senza_voce = sorted(str(v) for v in set(casi) - tabella)
        if senza_caso:
            sys.stderr.write("%s: voci senza oracolo: %s\n" % (nome, ", ".join(senza_caso)))
            return 1
        if senza_voce:
            sys.stderr.write("%s: casi senza voce: %s\n" % (nome, ", ".join(senza_voce)))
            return 1
        for voce in sorted(casi, key=str):
            nota = " ".join(voce) if isinstance(voce, tuple) else voce
            righe.append("2\t%s\tblocca il force-push con %s %s" % (casi[voce], etichetta, nota))
    sys.stdout.write("\n".join(righe) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
