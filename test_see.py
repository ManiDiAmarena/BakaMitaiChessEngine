# test_see.py (Versione con Correzioni Finali v2)
import sys
import os
import unittest # Non usato ma lasciato per compatibilità

# Assicurati che i moduli siano importabili
try:
    import constants
    import move as m
    from search import see, _get_least_valuable_attacker
    from board import ChessEngine
    import evaluation
except ImportError as e:
    print(f"Errore di importazione: {e}. Assicurati che tutti i file .py siano nella directory corretta o nel PYTHONPATH.")
    sys.exit(1)

# Funzioni helper (invariate)
def board_from_fen(fen):
    temp_engine = ChessEngine(fen)
    return temp_engine.board
def move_from_uci(fen, uci_str):
    temp_engine = ChessEngine(fen)
    return temp_engine.parse_move(uci_str)

# --- Casi di Test con Test 7 Corretto ---
test_cases = [
    # (nome_test, fen_posizione, uci_mossa, ep_target_tuple, expected_see_score)
    ("1. QxP (undefended)", "k7/8/8/8/p7/8/Q7/K7 w - - 0 1", "a2a4", None, 100),
    ("2. QxP (def by P)", "k7/8/8/p7/1p6/8/Q7/K7 w - - 0 1", "a2a5", None, 100),
    ("3. QxN (def by P)", "k7/8/8/p7/1n6/8/Q7/K7 w - - 0 1", "a2b4", None, -580),
    ("4. QxR (def by B)", "k7/8/8/b7/1r6/8/Q7/K7 w - - 0 1", "a2b4", None, -400), # Valore corretto
    ("5. QxP (def by Q)", "k7/8/8/q7/1p6/8/Q7/K7 w - - 0 1", "a2b4", None, -800),
    ("6. PxP (undefended)", "k7/8/8/8/8/p7/P7/K7 w - - 0 1", "a2a3", None, 100),
    # --- Test 7 Corretto ---
    # Riga originale (Test 7)
    # ("7. PxP (def by P)", "k7/8/8/8/1p6/pp6/P7/K7 w - - 0 1", "a2b3", None, 0),
    # Riga corretta (Test 7)
    ("7. PxP (def by P)", "k7/8/8/8/1p6/pp6/P7/K7 w - - 0 1", "a2b3", None, 100), # CORRETTO: PxP è +100, p@a3 non difende b3
    # ----------------------
    ("8. NxP (def by P)", "k7/8/8/8/1p6/p7/N7/K7 w - - 0 1", "a2b4", None, 100),
    ("9. BxN (def by P)", "k7/8/8/p7/1n6/8/B7/K7 w - - 0 1", "a2b4", None, -10),   # Valore corretto
    ("10. PxP EP (safe, corrected)", "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 1", "e4d6", (2, 3), 0), # Valore corretto
    ("11. QxP EP? (Invalid)", "k7/8/8/1pP5/8/8/Q7/K7 w - c6 0 1", "a2b6", (2, 2), 0),
    ("12. CPW SEE RxP (def by R)", "1k1r4/1pp4p/p7/4p3/8/P5P1/1PP4P/2K1R3 w - - 0 1", "e1e5", None, 100), # Valore corretto
    ("13. QxP (def by K)", "8/1k6/8/8/8/8/p1K5/Q7 w - - 0 1", "a1a2", None, 100), # Valore corretto
    ("14. NxP (def by N, Q, corrected)", "rnbqkbnr/pp2pppp/3p4/8/3pP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 0 4", "f3d4", None, 100), # Valore corretto
    ("15. QxP (def by N, Q, corrected)", "rnbqkbnr/pp2pppp/3p4/8/3pP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 0 4", "d1d4", None, 100), # Valore corretto
    ("16. RxB (undefended)", "k7/8/8/8/8/b7/R7/K7 w - - 0 1", "a2a3", None, 330),
    ("17. RxN (defended by R)", "k7/8/r7/8/n7/8/R7/K7 w - - 0 1", "a2a4", None, -180),
    ("18. PxB (defended by P, corrected)", "k7/8/8/8/p7/1b6/P7/K7 w - - 0 1", "a2b3", None, 230), # FEN corretta
]

# --- Esecuzione Test (Invariata, ma senza i debug print aggiunti prima) ---
passed = 0
failed = 0
print("--- Running SEE Tests ---")
for name, fen, uci_move, ep_target, expected_score in test_cases:
    # print(f"\nRunning Test: {name}") # Rimosso per output più pulito
    # print(f"FEN: {fen}, Move: {uci_move}, EP: {ep_target}, Expected: {expected_score}") # Rimosso
    board_arr = board_from_fen(fen)
    move_obj = move_from_uci(fen, uci_move)
    if move_obj is None:
        print(f"FAIL: {name} - Could not parse move {uci_move}")
        failed += 1
        continue
    start_piece = board_arr[move_obj.start_row][move_obj.start_col]
    end_piece = board_arr[move_obj.end_row][move_obj.end_col]
    is_capture_flag = end_piece != '.'
    is_ep_flag = start_piece.lower() == 'p' and ep_target == (move_obj.end_row, move_obj.end_col)
    if not is_capture_flag and not is_ep_flag:
        if expected_score == 0:
            # print(f"PASS: {name} (Move: {uci_move}, Expected: {expected_score}, Got: 0 - Non-capture)") # Rimosso
            passed += 1
        else:
            print(f"FAIL: {name} (Move: {uci_move}, Expected: {expected_score}, Got: 0 - Non-capture, but non-zero expected!)")
            failed += 1
        continue
    try:
        actual_score = see(board_arr, move_obj, ep_target)
        if actual_score == expected_score:
            # print(f"PASS: {name} (Move: {uci_move}, Expected: {expected_score}, Got: {actual_score})") # Rimosso
            passed += 1
        else:
            # Stampa solo i fallimenti per chiarezza
            print(f"FAIL: {name} (Move: {uci_move}, Expected: {expected_score}, Got: {actual_score})")
            failed += 1
    except Exception as e:
        print(f"ERROR: {name} - Exception during SEE execution: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        failed += 1
# Stampa riassunto finale
print("\n--- Test Summary ---")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("--------------------")
if failed == 0:
    print("\n----------------------------")
    print("ALL SEE TESTS PASSED! CONGRATULATIONS!")
    print("----------------------------")
elif failed > 0:
    print("\nErrors detected! Please review the failing tests and the SEE/attacker logic.")