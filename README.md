# ♟️ Baka Mitai Chess Engine 🤖

## 👋 Introduzione

Baka Mitai è un motore scacchistico sviluppato in Python. Implementa il protocollo UCI (Universal Chess Interface), rendendolo compatibile con la maggior parte delle interfacce grafiche di scacchi (GUI) 🖥️ come Arena, Cute Chess, o siti web come Lichess (tramite bridge UCI).

Il motore utilizza diverse tecniche di ricerca e valutazione per giocare a scacchi. 

**Questo è un progetto interamente italiano 🇮🇹.**

## 🌱 Nota dell'Autore e Contributi 🤝

Sono uno sviluppatore alle prime armi e questo progetto rappresenta uno dei miei primi tentativi nel creare un motore scacchistico. Ho implementato diverse funzionalità basandomi sullo studio di risorse online e altri motori open source.

Sebbene l'engine sia funzionante, **non è perfetto** e ci sono sicuramente molte aree che potrebbero essere ottimizzate o migliorate (sia in termini di forza di gioco che di pulizia del codice).

**Lo sviluppo iniziale è avvenuto nell'arco di circa 3 settimane 📅, durante le quali ho eseguito circa 100 partite di test 🧪 per verificarne il funzionamento di base.**

**Vi invito calorosamente a scaricare l'engine, provarlo nelle vostre GUI preferite e testarlo!**

**Accolgo con grande favore contributi dalla community!** Se avete suggerimenti, individuate bug, o volete proporre miglioramenti (come nuove tecniche di valutazione/ricerca, ottimizzazioni, refactoring), non esitate a:

* Effettuare un **Fork** del repository per sperimentare liberamente con le vostre idee.
* Aprire una **Issue** per discutere idee o segnalare problemi.
* Creare una **Pull Request** con le vostre modifiche e miglioramenti.

Sono desideroso di imparare e rendere Baka Mitai un progetto migliore con l'aiuto di altri appassionati! Qualsiasi feedback o contributo è prezioso. 🙏

---

## ✨ Caratteristiche Principali

* **📡 Protocollo UCI:** Piena compatibilità con le GUI che supportano UCI.
* **🧠 Ricerca Negamax:** Algoritmo di ricerca principale basato su Negamax con potatura Alpha-Beta.
* **🔄 Iterative Deepening:** La ricerca viene eseguita a profondità crescenti per migliorare la gestione del tempo e l'ordinamento delle mosse.
* **💾 Transposition Table:** Utilizza Zobrist Hashing per memorizzare posizioni già valutate e velocizzare la ricerca.
* **🤫 Quiescence Search:** Ricerca estesa oltre la profondità nominale per risolvere le catture e stabilizzare la valutazione.
* **📊 Ordinamento Mosse Avanzato:**
    * Most Valuable Victim - Least Valuable Attacker (MVV-LVA) per le catture.
    * Killer Moves: Memorizza le mosse che causano tagli beta a una data profondità.
    * History Heuristic: Preferisce mosse che sono state storicamente buone in rami simili dell'albero di ricerca.
* **✂️ Potature e Riduzioni:**
    * Null Move Pruning (NMP).
    * Late Move Reductions (LMR).
    * Futility Pruning (a profondità basse).
* **➕ Estensioni:**
    * Check Extensions: Estende la ricerca quando viene dato scacco.
    * (Potenzialmente) Singular Extensions: Riconosce e ricerca più a fondo mosse candidate molto promettenti.
* **⚖️ Valutazione Tapered:** La funzione di valutazione combina punteggi per il mediogioco e il finale, interpolati in base alla fase della partita. Include:
    * Valore Materiale.
    * Piece-Square Tables (PST) specifiche per mediogioco e finale (soprattutto per il Re 👑).
    * Struttura Pedonale (pedoni doppiati, isolati, arretrati, passati).
    * Piazzamento dei pezzi (es. torri su colonne aperte/semi-aperte ♖, sulla settima traversa).
    * Sicurezza del Re (scudo di pedoni, penalità per colonne aperte/semi-aperte vicino al re).
    * Mobilità dei pezzi ♘.
    * Bonus/Malus specifici (coppia alfieri ♗, coppia cavalli, coppia torri, bonus tempo ⏱️).
* **🔍 Static Exchange Evaluation (SEE):** Valuta la bontà di una sequenza di catture su una casa specifica prima di eseguire la ricerca completa.
* **📖 Supporto Libro Aperture (Polyglot):** (Opzionale) Può utilizzare libri di apertura in formato Polyglot (`.bin`) se il file `book_.bin` è presente e la libreria `python-chess` è installata.
* **✔️ Funzione Perft:** Include una funzione per testare la correttezza della generazione delle mosse.
* **🧪 Test SEE:** Include script per testare la funzione SEE.
* **⏱️ Setup Profiling:** Predisposizione in `main.py` per analizzare le performance del codice.

---

## 🚀 Come Eseguire

1.  **🐍 Ambiente Consigliato:** Per ottenere le migliori prestazioni, si consiglia l'utilizzo di **PyPy** (versione 3.11 o compatibile è raccomandata). PyPy è un'implementazione alternativa di Python con un Just-In-Time (JIT) compiler che può accelerare significativamente l'esecuzione. Puoi scaricarlo da [pypy.org](https://www.pypy.org/download.html). In alternativa, usa Python standard (CPython 3.x).
2.  **(Opzionale) 📖 Libro di Aperture:** Se vuoi usare il libro Polyglot, installa `python-chess`:
    ```bash
    # Se usi PyPy
    pypy3 -m pip install chess

    # Se usi Python standard
    # pip install chess
    ```
    Posiziona un file `book_.bin` valido nella directory principale del progetto.
3.  **▶️ Avvio Motore:** Esegui `main.py` con l'interprete scelto:
    ```bash
    # Usando PyPy (consigliato)
    pypy3 main.py

    # Usando Python standard
    # python main.py
    ```
4.  **⚙️ Configurazione GUI:** Il motore attenderà comandi UCI. Configura la tua GUI (Arena, Cute Chess, ecc.) per usare un motore UCI esterno, puntando al comando di avvio (es. `pypy3 /percorso/completo/a/main.py`). Consulta la documentazione della tua GUI.

---

## 🗺️ Struttura del Progetto

* `main.py` 📄: Punto di ingresso principale, avvia loop UCI/profiling.
* `uci.py` 📄: Gestisce comunicazione UCI.
* `board.py` 📄: Rappresentazione scacchiera, generazione mosse, make/unmake, stato, Perft.
* `move.py` 📄: Classe per rappresentare una mossa.
* `search.py` 📄: Algoritmi di ricerca (Negamax, Quiescence, ID), ordinamento, SEE, potature, estensioni.
* `evaluation.py` 📄: Funzione di valutazione (materiale, PST, struttura pedoni, ecc.).
* `pst.py` 📄: Tabelle Piece-Square Tables (PST).
* `constants.py` 📄: Costanti globali (valori pezzi, bonus, parametri, hash).
* `test_see.py` 📄: Script di test per SEE.
* (Opzionale) `book_.bin` 📖: File libro aperture Polyglot (non incluso).

---

## 👤 Autore

* Mani D'Amarena

---

## 📦 Dipendenze (`requirements.txt`)

Il motore usa principalmente Python standard. La dipendenza esterna è solo per il libro di aperture (opzionale).
# Necessario solo per il supporto al libro di aperture Polyglot (.bin) ⚠️
chess>=1.9.0,<2.0
