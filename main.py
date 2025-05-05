# -*- coding: utf-8 -*-
import sys
import os

# Importa le classi/funzioni necessarie dai moduli creati
from board import ChessEngine # Importa la classe engine
from uci import uci_loop      # Importa la funzione del loop UCI
# Importa constants se serve direttamente qui (es. per path libro se non gestito altrove)
# import constants

# (Opzionale) Setup per profiling se vuoi mantenerlo separato
import cProfile
import pstats

def run_with_profiling(fen_to_profile, depth_to_profile):
    """Esegue una ricerca singola con profiling."""
    engine = ChessEngine(fen=fen_to_profile)
    print(f"--- Profiling Engine ---", file=sys.stderr)
    print(f"FEN: {fen_to_profile}", file=sys.stderr)
    print(f"Depth: {depth_to_profile}", file=sys.stderr)

    profiler = cProfile.Profile()
    profiling_command = f"engine.find_best_move(max_depth={depth_to_profile})"

    print("Starting profiling...", file=sys.stderr)
    # Esegui il comando nel contesto corretto
    profiler.runctx(profiling_command, {'engine': engine}, {}) # Passa engine al contesto locale
    print("Profiling finished.", file=sys.stderr)

    stats_filename = "engine_profile.prof"
    profiler.dump_stats(stats_filename)
    print(f"Profiling stats saved to: {stats_filename}", file=sys.stderr)

    # Stampa riassunto
    print("\n--- Top 25 Functions (Cumulative Time) ---", file=sys.stderr)
    stats = pstats.Stats(profiler, stream=sys.stderr).sort_stats('cumulative')
    stats.print_stats(25)


# --- Blocco Esecuzione Principale ---
if __name__ == "__main__":

    # Se vuoi eseguire il profiling, decommenta e modifica:
    #profile_fen = "rnbqkb1r/pp2pp1p/3p1np1/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6" # Esempio
    #profile_depth = 5
    #run_with_profiling(profile_fen, profile_depth)

    # Esecuzione normale con loop UCI:
    # Crea l'istanza dell'engine
    print("Creating Chess Engine instance...", file=sys.stderr)
    main_engine = ChessEngine()
    print("Starting UCI loop...", file=sys.stderr)
    # Avvia il loop UCI passando l'istanza dell'engine
    uci_loop(main_engine)

    print("Exiting main program.", file=sys.stderr)
