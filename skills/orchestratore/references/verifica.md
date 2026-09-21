# Verifica: protocollo, oracolo, rischio di merge

Il verificatore riceve **solo** perimetro, branch, hash, comandi del `Gate verde` e aree
ammesse. Mai il piano, il ledger, il diff commentato o l'opinione del builder. Modello
diverso dal builder, runtime opposto quando il peso lo consente (routing regola 1).

## I quattro passi obbligatori

1. **Hash esatto**: lavora sull'hash consegnato e lo dimostra con `git rev-parse HEAD`.
2. **Gate verde**: esegue build, test e lint dichiarati in `RUN.md`, con output raw.
3. **Oracolo**: prova che i test nuovi provano qualcosa. Sui soli file **non di test** del
   diff applica il rovescio (`git checkout <base> -- <file di produzione toccati>`) e rilancia
   la suite mirata: deve diventare **rossa**. Se resta verde il test non copre il criterio di
   done → `KO: oracolo assente`. Poi ripristina l'hash.
4. **Perimetro**: `git diff --name-only <base>...<hash>` confrontato con le aree ammesse. Un
   file fuori area → `KO: fuori perimetro`.

Un verdetto senza gli output raw dei quattro passi non è un verdetto: il cervello lo tratta
come verifica non eseguita e la riassegna a un altro modello.

## Formato del verdetto

```text
VERIFICA <task|milestone> <id> hash <sha>
esito: OK | OK CON RISERVE | KO
hash confermato: <output di git rev-parse HEAD>
gate verde: <comando> → <esito raw>   (una riga per comando)
oracolo: <comando> → <rosso atteso: sì | no>
perimetro: <file fuori area | nessuno>
riserve o motivi: <max 3>
```

## Esiti

- `OK` → il task o la milestone avanza di stato.
- `OK CON RISERVE` → correzione dentro perimetro, un secondo giro, poi avanti con le riserve
  nel report.
- `KO` → applica il budget finito di lane.md: due tentativi per approccio e due approcci
  distinti; poi cambio prospettiva o parcheggio. `oracolo assente` e
  `fuori perimetro` sono KO pieni, mai riserve.

## Rischio di merge: regola fissa, nessuna discrezionalità

La classe si calcola **sul diff reale**, non sull'intenzione della milestone, e il gate
pre-merge la ricalcola sui file effettivamente toccati prima di rispondere.

| Classe | Cosa | Esito |
|---|---|---|
| Tier 1-2 | test, doc, tooling, refactor interno, UI senza dati sensibili, contenuti | **auto-merge** al gate di lane.md |
| Tier 3 o area sensibile | schema e migrazioni, auth e sessioni, pagamenti, multi-tenancy, PII e dati sanitari, segreti e chiavi, permessi, cancellazione di dati | **PR in attesa di Andrea** |

Aree sensibili di default, sovrascrivibili in `.orchestratore/config.toml` sotto `[rischio]`
con `aree_sensibili = [...]`: percorsi di schema e migrazioni, moduli di auth e sessione,
pagamenti, gestione di utenti e ruoli, file di configurazione con segreti.

Una PR in attesa resta in stato `pronta`, con verdetto e gate nel corpo, e la milestone conta
come 🟡 **bloccata da Andrea** nei contatori, non come mancante. Il cervello non promuove mai
una milestone da «in attesa» ad «auto-merge», e non declassa per prudenza una milestone
tier 1-2 con gate verde: la regola è fissa e verificabile a posteriori.
