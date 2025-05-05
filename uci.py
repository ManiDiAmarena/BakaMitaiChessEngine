# -*- coding: utf-8 -*-
import sys
import time # Potrebbe servire per debug o altro
import constants
import board as b # Alias
import move as m # Alias
import search # Per accedere alle costanti o funzioni di search se necessario

# Import condizionale per Polyglot
try:
    import chess
    import chess.polyglot
    CHESS_POLYGLOT_AVAILABLE_UCI = True
except ImportError:
    CHESS_POLYGLOT_AVAILABLE_UCI = False
    chess = None # Definisci per evitare errori

def uci_loop(engine):
    """Gestisce il loop di comunicazione UCI."""
    print("Avvio UCI loop...", file=sys.stderr, flush=True)

    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            continue

        print(f"DEBUG UCI Received: {line}", file=sys.stderr, flush=True) # Debug

        if line == "quit":
            break
        elif line == "uci":
            # Usa una versione nel nome ID per tracciamento
            print(f"id name Baka Mitai", flush=True)
            print(f"id author Mani D'Amarena", flush=True)
            # Qui potresti aggiungere opzioni UCI se ne implementi (es. Hash size, UseBook)
            # print("option name Hash type spin default 128 min 1 max 1024")
            print("uciok", flush=True)
        elif line == "isready":
            # Qui l'engine dovrebbe assicurarsi di essere pronto (es. caricamento tabelle finito)
            # In questo caso, siamo sempre pronti dopo l'init.
            print("readyok", flush=True)
        elif line == "ucinewgame":
            # Resetta lo stato dell'engine alla posizione iniziale
            engine.parse_fen(constants.INITIAL_FEN)
            # Pulisci TT e history heuristic (potrebbe essere un metodo sull'engine)
            engine.transposition_table = [None] * constants.TT_SIZE
            engine.killer_moves = [[None, None] for _ in range(constants.MAX_SEARCH_PLY)]
            engine.history_heuristic = [[[0] * 64 for _ in range(64)] for _ in range(2)]
            engine.play_book_move_on_go = None # Resetta mossa libro
            print("DEBUG UCI: New game state reset.", file=sys.stderr, flush=True)
            
        elif line.startswith("perft"):
            parts = line.split()
            if len(parts) < 2:
                print("info string Usage: perft <depth>", file=sys.stderr, flush=True)
                continue
            try:
                depth = int(parts[1])
                if depth < 0: raise ValueError("Depth cannot be negative")

                # Imposta la FEN corrente prima di iniziare, per chiarezza
                current_fen_for_perft = engine.get_fen()
                print(f"info string Running Perft({depth}) on FEN: {current_fen_for_perft}", flush=True)

                # Chiama la funzione perft dell'engine
                # Usiamo divide=True di default per avere l'output dettagliato
                # Puoi cambiarlo a False se vuoi solo il totale: engine.perft(depth, divide=False)
                result_nodes = engine.perft(depth)

                # Il risultato numerico e i dettagli vengono già stampati da engine.perft()
                # Stampa un messaggio finale nel log UCI
                print(f"info string Perft calculation finished. Total nodes: {result_nodes}", flush=True)

            except ValueError as e:
                print(f"info string Invalid depth for perft: {e}", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"info string Error during perft execution: {e}", file=sys.stderr, flush=True)
                # Potrebbe essere utile stampare un traceback per errori inaspettati
                import traceback
                traceback.print_exc(file=sys.stderr)

        elif line.startswith("position"):
            engine.play_book_move_on_go = None # Resetta mossa libro
            parts = line.split()
            fen = None
            moves_start_index = -1

            # Parsing FEN o startpos
            if "startpos" in parts:
                fen = constants.INITIAL_FEN
                if "moves" in parts:
                    moves_start_index = parts.index("moves") + 1
            elif "fen" in parts:
                fen_start_index = parts.index("fen") + 1
                # Trova la fine della FEN (prima di 'moves' o alla fine)
                fen_end_index = len(parts)
                if "moves" in parts:
                    fen_end_index = parts.index("moves")
                    moves_start_index = fen_end_index + 1
                fen = " ".join(parts[fen_start_index:fen_end_index])
            else:
                print("ERROR UCI: Invalid position command", file=sys.stderr, flush=True)
                continue # Salta al prossimo comando

            # Imposta la posizione sull'engine
            if fen:
                engine.parse_fen(fen)
                # print(f"DEBUG UCI: Position set to FEN: {engine.get_fen()}", file=sys.stderr, flush=True)


            # Applica le mosse successive (se presenti)
            if moves_start_index != -1:
                moves_list = parts[moves_start_index:]
                for move_str in moves_list:
                    move_obj = engine.parse_move(move_str)
                    if move_obj and move_obj in engine.get_legal_moves(engine.current_player): # Verifica legalità base
                        engine.make_move(move_obj)
                        # print(f"DEBUG UCI: Applied move {move_str}. New FEN: {engine.get_fen()}", file=sys.stderr, flush=True)
                    else:
                        print(f"ERROR UCI: Illegal or unparseable move '{move_str}' in position sequence.", file=sys.stderr, flush=True)
                        # Potresti voler interrompere qui o segnalare errore diversamente
                        break

            # --- Consultazione Libro Polyglot ---
            if engine.use_book and CHESS_POLYGLOT_AVAILABLE_UCI:
                try:
                    python_chess_board = engine.to_python_chess()
                    if python_chess_board:
                        with chess.polyglot.open_reader(constants.BOOK_PATH) as reader:
                            # Usa find() invece di find_all() per ottenere la mossa 'migliore'
                            entry = reader.find(python_chess_board, minimum_weight=1) # Trova la prima entry con peso > 0
                            # Potresti usare find_all e scegliere casualmente o per peso:
                            # entries = list(reader.find_all(python_chess_board))
                            # if entries: best_entry = max(entries, key=lambda e: e.weight)

                            if entry is not None:
                                book_move_uci = entry.move.uci()
                                book_move_obj = engine.parse_move(book_move_uci)
                                # Verifica se la mossa libro è legale nella posizione attuale
                                temp_legal_moves = engine.get_legal_moves(engine.current_player)
                                if book_move_obj and book_move_obj in temp_legal_moves:
                                    print(f"info string Book move found: {book_move_uci}", file=sys.stderr, flush=True)
                                    engine.play_book_move_on_go = book_move_obj # Memorizza
                                # else: # Debug opzionale se la mossa libro non è legale
                                #     print(f"info string Book move {book_move_uci} is illegal, ignoring.", file=sys.stderr, flush=True)

                except FileNotFoundError:
                    print(f"info string Polyglot book not found at: {constants.BOOK_PATH}", file=sys.stderr, flush=True)
                    engine.use_book = False # Disabilita libro per questa sessione
                except Exception as e:
                    print(f"info string Error accessing Polyglot book: {e}", file=sys.stderr, flush=True)
                    # Potresti voler disabilitare il libro anche qui
            # --- Fine Consultazione Libro ---

        elif line.startswith("go"):
            print("DEBUG UCI: Received go command.", file=sys.stderr, flush=True)
            # Controlla se abbiamo una mossa libro memorizzata
            if engine.play_book_move_on_go is not None:
                print(f"info string Playing book move: {engine.play_book_move_on_go.to_uci_string()}", file=sys.stderr, flush=True)
                print(f"bestmove {engine.play_book_move_on_go.to_uci_string()}", flush=True)
                engine.play_book_move_on_go = None # Consuma la mossa libro
            else:
                # Nessuna mossa libro, avvia la ricerca
                print("info string No book move, starting search...", file=sys.stderr, flush=True)
                parts = line.split()
                search_params = {'depth': constants.MAX_SEARCH_PLY, 'movetime': None, 'wtime': None, 'btime': None, 'winc': 0, 'binc': 0, 'movestogo': None}
                param_map = {'wtime': int, 'btime': int, 'winc': int, 'binc': int, 'movestogo': int, 'depth': int, 'movetime': int}

                for i, part in enumerate(parts):
                    if part in param_map and i + 1 < len(parts):
                        try:
                            search_params[part] = param_map[part](parts[i+1])
                        except ValueError:
                            print(f"WARN UCI: Invalid value for param '{part}'.", file=sys.stderr, flush=True)
                            # Mantieni il default o imposta a None/0 ? Dipende dalla logica time management.
                            # search_params[part] = None # O gestisci errore

                # Chiama la funzione di ricerca nel modulo search, passando l'engine
                best_move_found = search.search_move(
                    engine,
                    max_depth=search_params['depth'],
                    move_time=search_params['movetime'],
                    wtime=search_params['wtime'],
                    btime=search_params['btime'],
                    winc=search_params['winc'],
                    binc=search_params['binc'],
                    movestogo=search_params['movestogo']
                )

                # Stampa la mossa migliore trovata dalla ricerca
                if best_move_found:
                    print(f"bestmove {best_move_found.to_uci_string()}", flush=True)
                else:
                    # Caso raro: ricerca non trova mosse (dovrebbe essere gestito da search_move?)
                    # O posizione iniziale è già matto/stallo
                    print("bestmove 0000", flush=True) # Notazione UCI per mossa nulla/partita finita

        elif line == "stop":
            # In un engine multithread, questo segnalerebbe al thread di ricerca di fermarsi.
            # Qui, non facciamo nulla attivamente, ma la logica di time limit in search_move
            # dovrebbe interrompere la ricerca se il tempo scade.
            print("info string Stop command received (currently no effect in single thread)", file=sys.stderr, flush=True)
            pass
        elif line == "ponderhit":
            # Se stessimo facendo pondering, questo direbbe che l'avversario ha giocato la mossa attesa.
            # Non implementato qui.
            pass
        # Aggiungi altri comandi UCI se necessario (es. setoption)

    print("UCI loop terminated.", file=sys.stderr, flush=True)