# -*- coding: utf-8 -*-
import math
import time
import sys # Per debug print
import random
import constants
import move as m # Rinomina per evitare conflitti se usi 'move' come variabile
import evaluation # Importa il modulo di valutazione

# Variabili globali del modulo per statistiche (se preferisci non passarle ovunque)
# Altrimenti, passale come argomenti o mettile in un oggetto 'SearchStats'
nodes_searched = 0
q_nodes_searched = 0
tt_probes = 0
tt_hits = 0
nmp_cutoffs = 0
start_time = 0

# --- Funzioni di Ordinamento e SEE ---

def score_move(board_array, move_obj, killer_moves_ply, history_heuristic_color, ply, current_player_color):
    """ Assegna un punteggio alla mossa per l'ordinamento. """
    score = 0
    attacker_piece_char = board_array[move_obj.start_row][move_obj.start_col]
    # Gestione robusta se la casa di partenza fosse vuota (non dovrebbe succedere con mosse legali)
    if attacker_piece_char == '.': return -float('inf')
    attacker_type = attacker_piece_char.lower()

    captured_piece_char = board_array[move_obj.end_row][move_obj.end_col]
    captured_type = captured_piece_char.lower() if captured_piece_char != '.' else '.'

    # Catture (MVV-LVA)
    if captured_type != '.':
        score += constants.MVV_LVA_CAPTURE_BONUS
        victim_value = constants.PIECE_VALUES.get(captured_type, 0)
        attacker_value = constants.PIECE_VALUES.get(attacker_type, 0)
        score += victim_value * 100 - attacker_value # Pondera di più il valore della vittima

    # Promozioni
    if move_obj.promotion_piece:
        promotion_bonus = constants.PIECE_VALUES.get(move_obj.promotion_piece, 0)
        # Somma al bonus catture se è una promozione con cattura
        score += constants.PROMOTION_BONUS_OFFSET + promotion_bonus

    # Mosse Killer (se non cattura/promozione)
    if captured_type == '.' and not move_obj.promotion_piece:
        is_killer = False
        # Assicurati che killer_moves_ply sia una lista valida (potrebbe essere None fuori range)
        if killer_moves_ply is not None:
            if move_obj == killer_moves_ply[0]:
                score += constants.KILLER_MOVE_PRIMARY_BONUS
                is_killer = True
            elif move_obj == killer_moves_ply[1]:
                score += constants.KILLER_MOVE_SECONDARY_BONUS
                is_killer = True

        # History Heuristic (solo per mosse tranquille non killer)
        if not is_killer:
            start_sq = move_obj.start_row * 8 + move_obj.start_col
            end_sq = move_obj.end_row * 8 + move_obj.end_col
            # Assicurati che history_heuristic_color sia valido
            if history_heuristic_color is not None and 0 <= start_sq < 64 and 0 <= end_sq < 64:
                try:
                    history_score = history_heuristic_color[start_sq][end_sq]
                    # Applica un cap al bonus dell'history
                    score += min(history_score, constants.MAX_HISTORY_SCORE_BONUS)
                except IndexError: # Sicurezza extra
                    pass # Ignora se gli indici sono fuori range per qualche motivo
    return score


def order_moves(board_array, moves_list, killer_moves_ply, history_heuristic_color, ply, current_player_color):
    """ Ordina una lista di mosse. """
    # Potrebbe essere utile gestire None per killer_moves_ply e history_heuristic_color
    safe_killer_moves = killer_moves_ply if killer_moves_ply is not None else [None, None]
    safe_history = history_heuristic_color # Assumendo che sia sempre una lista valida o gestita in score_move
    return sorted(moves_list,
                  key=lambda mv: score_move(board_array, mv, safe_killer_moves, safe_history, ply, current_player_color),
                  reverse=True)

# --- Funzione Helper _get_least_valuable_attacker (Versione v5 - CORRETTA) ---
def _get_least_valuable_attacker(board_array, target_r, target_c, attacker_color, occupied_mask):
    """ Trova l'attaccante di minor valore per una data casa e colore. (DEBUG FINALE CAVALLO) """
    least_value_found = float('inf')
    best_attacker_info = (None, -1, -1)
    piece_order = {'p': 1, 'n': 2, 'b': 3, 'r': 4, 'q': 5, 'k': 6}

    # 1. Check Pawns (invariato)
    expected_pawn = 'P' if attacker_color == 'W' else 'p'
    possible_origins = []
    if attacker_color == 'W': possible_origins = [(target_r + 1, target_c - 1), (target_r + 1, target_c + 1)]
    else: possible_origins = [(target_r - 1, target_c - 1), (target_r - 1, target_c + 1)]
    for pr, pc in possible_origins:
        if 0 <= pr < 8 and 0 <= pc < 8:
            if (pr, pc) in occupied_mask and board_array[pr][pc] == expected_pawn: return ('p', pr, pc)

    current_best_type = None
    current_best_r, current_best_c = -1, -1

    # 2. Check Knights (CON DEBUG MIRATO)
    knight_moves = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
    expected_knight = 'N' if attacker_color == 'W' else 'n'
    # === INIZIO DEBUG SPECIFICO TEST 15 ===
    #is_test_15_case = (target_r == 4 and target_c == 3 and attacker_color == 'B') # Target d4, Attacker Black
    #if is_test_15_case: print(f"\n--- LVA KNIGHT DEBUG (Test 15 Specific) ---", file=sys.stderr)
    # === FINE DEBUG SPECIFICO TEST 15 ===
    for dr, dc in knight_moves:
        nr, nc = target_r + dr, target_c + dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            is_occupied = (nr, nc) in occupied_mask
            piece_on_sq = board_array[nr][nc] if is_occupied else '.'

            # === INIZIO DEBUG SPECIFICO TEST 15 ===
            # Stampa solo quando controlla la casa c6 (2,2) nel caso del Test 15
            #if is_test_15_case and nr == 2 and nc == 2:
            #    print(f"LVA Knight Debug (Test 15): Checking square ({nr},{nc})={ (nr,nc) }", file=sys.stderr)
            #    print(f"LVA Knight Debug (Test 15): is_occupied = {is_occupied}", file=sys.stderr)
            #    print(f"LVA Knight Debug (Test 15): piece_on_sq = '{piece_on_sq}'", file=sys.stderr)
            #    print(f"LVA Knight Debug (Test 15): expected_knight = '{expected_knight}'", file=sys.stderr)
            #    print(f"LVA Knight Debug (Test 15): Condition Check: (is_occupied and piece_on_sq == expected_knight) = {is_occupied and piece_on_sq == expected_knight}", file=sys.stderr)
            # === FINE DEBUG SPECIFICO TEST 15 ===

            if is_occupied and piece_on_sq == expected_knight:
                # Trovato Cavallo attaccante.
                if least_value_found > piece_order['n']:
                    least_value_found = piece_order['n']
                    current_best_type = 'n'
                    current_best_r, current_best_c = nr, nc
                    # === INIZIO DEBUG SPECIFICO TEST 15 ===
                    #if is_test_15_case and nr == 2 and nc == 2: print(f"LVA Knight Debug (Test 15): *** Knight FOUND and updated best_attacker! ***", file=sys.stderr)
                    # === FINE DEBUG SPECIFICO TEST 15 ===

    # 3. Check Bishops / Diagonal Queens (invariato)
    if least_value_found > piece_order['b']:
        directions_diag = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        expected_bishop = 'B' if attacker_color == 'W' else 'b'
        expected_queen = 'Q' if attacker_color == 'W' else 'q'
        for dr, dc in directions_diag:
            for i in range(1, 8):
                sr, sc = target_r + i * dr, target_c + i * dc
                if not (0 <= sr < 8 and 0 <= sc < 8): break
                if (sr, sc) in occupied_mask:
                    piece_on_sq = board_array[sr][sc]
                    piece_type_on_sq = piece_on_sq.lower()
                    if (piece_on_sq == expected_bishop or piece_on_sq == expected_queen):
                        if piece_order[piece_type_on_sq] < least_value_found:
                            least_value_found = piece_order[piece_type_on_sq]
                            current_best_type = piece_type_on_sq
                            current_best_r, current_best_c = sr, sc
                        break
                    else: break

    # 4. Check Rooks / Straight Queens (invariato)
    if least_value_found > piece_order['r']:
        directions_straight = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        expected_rook = 'R' if attacker_color == 'W' else 'r'
        expected_queen = 'Q' if attacker_color == 'W' else 'q'
        for dr, dc in directions_straight:
            for i in range(1, 8):
                sr, sc = target_r + i * dr, target_c + i * dc
                if not (0 <= sr < 8 and 0 <= sc < 8): break
                if (sr, sc) in occupied_mask:
                    piece_on_sq = board_array[sr][sc]
                    piece_type_on_sq = piece_on_sq.lower()
                    if (piece_on_sq == expected_rook or piece_on_sq == expected_queen):
                        if piece_order[piece_type_on_sq] < least_value_found:
                            least_value_found = piece_order[piece_type_on_sq]
                            current_best_type = piece_type_on_sq
                            current_best_r, current_best_c = sr, sc
                        break
                    else: break

    # 5. Check King (invariato)
    if least_value_found > piece_order['k']:
        king_moves = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        expected_king = 'K' if attacker_color == 'W' else 'k'
        for dr, dc in king_moves:
            kr, kc = target_r + dr, target_c + dc
            if 0 <= kr < 8 and 0 <= kc < 8:
                if (kr, kc) in occupied_mask and board_array[kr][kc] == expected_king:
                    if least_value_found == float('inf'):
                        least_value_found = piece_order['k']
                        current_best_type = 'k'
                        current_best_r, current_best_c = kr, kc
                    break

    best_attacker_info = (current_best_type, current_best_r, current_best_c)
    # === INIZIO DEBUG SPECIFICO TEST 15 ===
    #if is_test_15_case: print(f"LVA Knight Debug (Test 15): Returning best_attacker_info = {best_attacker_info}", file=sys.stderr)
    # === FINE DEBUG SPECIFICO TEST 15 ===
    return best_attacker_info


# --- Funzione SEE (Static Exchange Evaluation) ---
# (Versione corretta con swap_list e calcolo finale standard, senza debug)
def see(board_array, move_obj, en_passant_target):
    """
    Static Exchange Evaluation (SEE) - Stima il guadagno/perdita materiale di una cattura.
    Ritorna il punteggio dello scambio dal punto di vista del lato che cattura.
    Implementa l'algoritmo standard basato su ricatture del pezzo di minor valore.
    Versione con swap_list corretta e calcolo finale standard.
    """
    from_r, from_c = move_obj.start_row, move_obj.start_col
    to_r, to_c = move_obj.end_row, move_obj.end_col
    attacker_char = board_array[from_r][from_c]

    if attacker_char == '.': return 0

    victim_char = board_array[to_r][to_c]
    is_ep = False
    captured_ep_value = 0

    if victim_char == '.':
        if attacker_char.lower() == 'p' and en_passant_target == (to_r, to_c):
            try: attacker_color_local = evaluation.get_piece_color(attacker_char)
            except (NameError, AttributeError): attacker_color_local = 'W' if attacker_char.isupper() else 'B'
            victim_char = 'p' if attacker_color_local == 'W' else 'P'
            is_ep = True
            captured_ep_value = constants.PIECE_VALUES.get(victim_char.lower(), 0)
        else:
            return 0

    if victim_char.lower() == 'k':
        return constants.MATE_SCORE // 2

    # ---- Inizio Simulazione Scambi ----
    swap_list = [0] * 32
    swap_index = 0

    if not is_ep:
        initial_victim_value = constants.PIECE_VALUES.get(victim_char.lower(), 0)
    else:
        initial_victim_value = captured_ep_value
    swap_list[swap_index] = initial_victim_value

    sim_board = [row[:] for row in board_array]
    try: attacker_color = evaluation.get_piece_color(attacker_char)
    except (NameError, AttributeError): attacker_color = 'W' if attacker_char.isupper() else 'B'

    sim_board[to_r][to_c] = attacker_char
    sim_board[from_r][from_c] = '.'
    if is_ep:
        ep_victim_r = to_r + (1 if attacker_color == 'W' else -1)
        ep_victim_c = to_c
        if 0 <= ep_victim_r < 8 and 0 <= ep_victim_c < 8:
            if sim_board[ep_victim_r][ep_victim_c].lower() == 'p':
                sim_board[ep_victim_r][ep_victim_c] = '.'

    current_target_r, current_target_c = to_r, to_c
    piece_on_target_char = attacker_char
    current_attacker_color = attacker_color

    while True:
        swap_index += 1
        next_attacker_color = 'B' if current_attacker_color == 'W' else 'W'
        occupied_mask = set((r, c) for r in range(8) for c in range(8) if sim_board[r][c] != '.')

        next_attacker = _get_least_valuable_attacker(sim_board, current_target_r, current_target_c, next_attacker_color, occupied_mask)
        next_attacker_type, nr, nc = next_attacker

        if next_attacker_type is None:
            swap_index -= 1
            break

        value_of_piece_being_captured = constants.PIECE_VALUES.get(piece_on_target_char.lower(), 0)
        swap_list[swap_index] = value_of_piece_being_captured

        next_attacker_char_on_board = sim_board[nr][nc]
        sim_board[current_target_r][current_target_c] = next_attacker_char_on_board
        sim_board[nr][nc] = '.'

        piece_on_target_char = next_attacker_char_on_board
        current_attacker_color = next_attacker_color
    # ---- Fine Simulazione Scambi ----

    # --- Calcolo Punteggio SEE Finale (Algoritmo standard s[i] = v[i] - s[i+1]) ---
    num_valid_swaps = swap_index + 1

    if num_valid_swaps <= 0: return 0
    if num_valid_swaps == 1: return swap_list[0]

    final_see_score = 0
    for i in range(swap_index, -1, -1):
        final_see_score = swap_list[i] - final_see_score

    return final_see_score

# --- Funzioni Ricerca Principale ---

def _store_tt_entry(transposition_table, index, position_hash, depth, score, bound, best_move):
    """ Salva un'entry nella TT (Depth-Preferred). """
    existing_entry = transposition_table[index]
    should_store = False
    # Controlla se lo slot è vuoto o l'hash non corrisponde (collisione)
    if existing_entry is None or existing_entry['hash'] != position_hash:
        should_store = True
    # Se l'hash corrisponde, sovrascrivi solo se la nuova profondità è maggiore o uguale
    elif depth >= existing_entry['depth']:
        # Potresti aggiungere un check qui: se la profondità è uguale,
        # forse preferisci mantenere un EXACT bound rispetto a un LOWER/UPPER?
        # Per ora, sovrascrivi sempre se profondità >=
        should_store = True

    if should_store:
        # Crea il nuovo dizionario per l'entry
        new_entry = {
            'hash': position_hash, 'depth': depth, 'score': score,
            'bound': bound, 'best_move': best_move # Assicurati che best_move sia un oggetto Move o None
        }
        transposition_table[index] = new_entry


def quiescence_search(engine, alpha, beta, ply):
    """ Quiescence search. Ora ritorna (score, None). """
    global q_nodes_searched
    q_nodes_searched += 1

    board_array = engine.board
    current_player_color = engine.current_player
    en_passant_target = engine.en_passant_target

    stand_pat_score = evaluation.evaluate_board(board_array, current_player_color)

    best_move_q = None

    if stand_pat_score >= beta:
        return beta, best_move_q # Fail high
    alpha = max(alpha, stand_pat_score)

    moves = engine.get_pseudo_legal_moves(current_player_color)
    # Considera solo catture e promozioni in quiescenza
    candidate_moves = [mv for mv in moves if board_array[mv.end_row][mv.end_col] != '.' or mv.promotion_piece or
                      (board_array[mv.start_row][mv.start_col].lower() == 'p' and en_passant_target == (mv.end_row, mv.end_col))]

    qply = min(ply, constants.MAX_SEARCH_PLY - 1)
    killer_moves_ply = engine.killer_moves[qply] if qply < len(engine.killer_moves) else [None, None]
    color_index = 0 if current_player_color == 'W' else 1
    history_heuristic_color = engine.history_heuristic[color_index]
    # Ordina solo le mosse candidate (catture/promozioni)
    ordered_candidates = order_moves(board_array, candidate_moves, killer_moves_ply, history_heuristic_color, ply, current_player_color)

    current_best_score = stand_pat_score # Inizia con stand-pat

    for move_obj in ordered_candidates:
        # --- Controllo SEE ---
        # Solo per catture dirette (non promozioni su casa vuota)
        is_direct_capture = board_array[move_obj.end_row][move_obj.end_col] != '.' or \
                            (board_array[move_obj.start_row][move_obj.start_col].lower() == 'p' and en_passant_target == (move_obj.end_row, move_obj.end_col))

        if is_direct_capture:
            # Ottieni il valore del pezzo effettivamente catturato per Delta Pruning
            victim_char_delta = board_array[move_obj.end_row][move_obj.end_col]
            if victim_char_delta == '.': # Era EP
                victim_char_delta = 'p' if current_player_color == 'W' else 'P'
            captured_piece_val = constants.PIECE_VALUES.get(victim_char_delta.lower(), 0)

            # Delta Pruning: Se lo stand-pat + valore catturato + margine è ancora peggio di alpha, pota.
            if stand_pat_score + captured_piece_val + 200 < alpha:
                continue

            # SEE Pruning: Se lo scambio statico è negativo, pota.
            # Nota: Usiamo la funzione 'see' corretta
            see_score = see(board_array, move_obj, en_passant_target)
            if see_score < 0:
                continue
        # --- Fine Controllo SEE ---


        # Verifica legalità mossa (necessario perché partiamo da pseudo-legali)
        # Usare snapshot è più sicuro per lo stato complesso dell'engine
        original_state = engine.get_state_snapshot()
        engine.make_move(move_obj)
        # Il giocatore che ha mosso è l'avversario di current_player_color originale
        opponent_color_check = 'B' if current_player_color == 'W' else 'W'
        is_legal = not engine.is_in_check(current_player_color) # Controlla se il *proprio* re è in scacco
        engine.restore_state_snapshot(original_state) # Ripristina subito

        if is_legal:
            # Esegui la mossa di nuovo per la chiamata ricorsiva
            engine.make_move(move_obj)
            # Chiamata ricorsiva - prendi solo lo score, ignora la mossa ritornata
            score, _ = quiescence_search(engine, -beta, -alpha, ply + 1)
            score = -score # Nega lo score ritornato
            engine.unmake_move() # Annulla la mossa

            current_best_score = max(current_best_score, score) # Aggiorna il miglior score trovato finora

            if score >= beta:
                return beta, best_move_q # Fail high (Taglio Beta)
            alpha = max(alpha, score) # Aggiorna Alpha

    # Ritorna il miglior score trovato (o alpha se nessuna mossa ha migliorato) e None per la mossa
    return alpha, best_move_q

def negamax(engine, depth, alpha, beta, ply):
    """ Funzione di ricerca Negamax con IID e Singular Extensions. Ritorna (score, best_move_obj). """
    global nodes_searched, tt_probes, tt_hits, nmp_cutoffs
    nodes_searched += 1

    transposition_table = engine.transposition_table
    current_hash = engine.current_hash
    current_player_color = engine.current_player
    halfmove_clock = engine.halfmove_clock
    history = engine.history
    killer_moves = engine.killer_moves
    history_heuristic = engine.history_heuristic
    position_hash = current_hash

    if ply >= constants.MAX_SEARCH_PLY:
        eval_score = evaluation.evaluate_board(engine.board, current_player_color)
        return eval_score, None
    if ply > 0:
        history_len = len(history)
        if history_len >= 4:
            try:
                # Controllo ripetizione semplice (2 ripetizioni precedenti)
                # NOTA: questo è un check base, non copre tutte le ripetizioni a 3 posizioni
                if history[-2]['previous_hash'] == position_hash and history[-4]['previous_hash'] == position_hash:
                    return constants.DRAW_SCORE, None
            except IndexError: pass
        if halfmove_clock >= 100:
            return constants.DRAW_SCORE, None

    original_alpha = alpha
    original_beta = beta
    tt_move = None
    tt_score = None
    tt_bound = None
    tt_depth = -1
    tt_index = position_hash % constants.TT_SIZE
    cached_entry = transposition_table[tt_index]
    tt_probes += 1

    if cached_entry is not None and cached_entry['hash'] == position_hash:
        tt_hits += 1
        tt_depth = cached_entry['depth']
        tt_score = cached_entry['score']
        tt_bound = cached_entry['bound']
        # Verifica se la mossa cachata è un oggetto Move valido
        cached_move = cached_entry.get('best_move')
        if isinstance(cached_move, m.Move):
            tt_move = cached_move

        # Usa l'entry TT solo se la profondità è sufficiente
        if tt_depth >= depth:
            score = tt_score
            # Aggiusta score per mate distance
            if score >= constants.MATE_SCORE - constants.MAX_SEARCH_PLY: score -= ply
            elif score <= -constants.MATE_SCORE + constants.MAX_SEARCH_PLY: score += ply

            if tt_bound == constants.TT_BOUND_EXACT: return score, tt_move
            if tt_bound == constants.TT_BOUND_LOWER and score >= beta: return score, tt_move
            if tt_bound == constants.TT_BOUND_UPPER and score <= alpha: return score, tt_move

    is_in_check = engine.is_in_check(current_player_color)
    if depth <= 0:
        # Raggiunta profondità 0, passa a quiescence search
        return quiescence_search(engine, alpha, beta, ply)

    # Internal Iterative Deepening (IID)
    iid_move = None
    if tt_move is None and depth >= constants.IID_MIN_DEPTH:
        iid_depth = depth - constants.IID_REDUCTION
        # Esegui una ricerca a profondità ridotta senza aggiornare lo stato globale
        # Passa una copia temporanea dell'engine o usa snapshot (snapshot è più semplice qui)
        # NOTA: IID qui è semplificato, non passa TT o altre strutture complesse
        # Potrebbe essere meno efficace senza condividere informazioni tra ricerche
        _, iid_potential_move = negamax(engine, iid_depth, -constants.MATE_SCORE*2, constants.MATE_SCORE*2, ply) # Non incrementa ply qui? Dipende da implementazione
        if iid_potential_move is not None: iid_move = iid_potential_move

    # Null Move Pruning (NMP)
    can_do_nmp = not is_in_check and depth >= constants.NMP_MIN_DEPTH and ply > 0
    if can_do_nmp:
        # Verifica materiale minimo per evitare NMP in endgame con pochi pezzi
        own_material = 0
        player_piece_chars = 'PNBRQ' if current_player_color == 'W' else 'pnbrq'
        for r in range(8):
            for c in range(8):
                piece = engine.board[r][c]
                # Considera solo pezzi non pedoni per il threshold NMP
                if piece in player_piece_chars and piece.lower() != 'p':
                    own_material += constants.PIECE_VALUES.get(piece.lower(), 0)
                    if own_material >= constants.MIN_MATERIAL_FOR_NMP: break
            if own_material >= constants.MIN_MATERIAL_FOR_NMP: break

        if own_material >= constants.MIN_MATERIAL_FOR_NMP:
            # Salva stato, fai mossa nulla, cerca, ripristina stato
            original_state_nmp = engine.get_state_snapshot()
            # Fai la "null move": cambia solo turno e resetta EP
            engine.current_player = 'B' if current_player_color == 'W' else 'W'
            engine.current_hash = engine.calculate_zobrist_hash() # Ricalcola hash dopo cambio stato
            # Non resettare halfmove clock per null move

            nmp_depth = depth - 1 - constants.NMP_REDUCTION
            # Cerca con beta invertito (-beta + 1), se fallisce alto (>= -beta+1), allora la mossa nulla è >= beta originale
            score_nmp, _ = negamax(engine, nmp_depth, -beta, -beta + 1, ply + 1)
            score_nmp = -score_nmp # Ripristina prospettiva

            engine.restore_state_snapshot(original_state_nmp) # Ripristina stato

            if score_nmp >= beta:
                nmp_cutoffs += 1
                # Il punteggio è almeno beta, possiamo tagliare
                # Memorizza nella TT come lower bound
                score_to_store_nmp = beta # O score_nmp se vuoi essere più preciso? Beta è più sicuro.
                if score_to_store_nmp >= constants.MATE_SCORE - constants.MAX_SEARCH_PLY: score_to_store_nmp += ply
                elif score_to_store_nmp <= -constants.MATE_SCORE + constants.MAX_SEARCH_PLY: score_to_store_nmp -= ply
                # Usa la funzione helper per memorizzare
                _store_tt_entry(transposition_table, tt_index, position_hash, depth, score_to_store_nmp, constants.TT_BOUND_LOWER, None) # Non abbiamo una best move da null move
                return beta, None # Ritorna beta come lower bound

    # --- Generazione/Ordinamento Mosse ---
    moves = engine.get_legal_moves(current_player_color)
    if not moves:
        # Nessuna mossa legale
        score = (-constants.MATE_SCORE + ply) if is_in_check else constants.STALEMATE_SCORE
        bound = constants.TT_BOUND_EXACT
        _store_tt_entry(transposition_table, tt_index, position_hash, constants.MAX_SEARCH_PLY, score, bound, None) # Profondità massima per nodo terminale
        return score, None

    qply = min(ply, constants.MAX_SEARCH_PLY - 1)
    killer_moves_ply = killer_moves[qply] if qply < len(killer_moves) else [None, None]
    color_index = 0 if current_player_color == 'W' else 1
    history_heuristic_color = history_heuristic[color_index]

    # Ordina le mosse: priorità a TT move, IID move, poi catture (MVV/LVA), promozioni, killer, history
    ordered_moves = []
    processed_moves = set()
    # 1. TT Move (se legale)
    if tt_move and tt_move in moves:
        ordered_moves.append(tt_move)
        processed_moves.add(tt_move)
    # 2. IID Move (se diverso da TT move e legale)
    if iid_move and iid_move in moves and iid_move not in processed_moves:
        ordered_moves.append(iid_move)
        processed_moves.add(iid_move)
    # 3. Ordina le rimanenti
    remaining_moves = [mv for mv in moves if mv not in processed_moves]
    sorted_remaining = order_moves(engine.board, remaining_moves, killer_moves_ply, history_heuristic_color, ply, current_player_color)
    ordered_moves.extend(sorted_remaining)


    # --- Loop Mosse Principale ---
    best_score_at_node = -constants.MATE_SCORE * 2 # Inizializza a valore molto basso
    best_move_at_node = ordered_moves[0] # Inizializza con la prima mossa ordinata come fallback
    moves_searched_count = 0
    static_eval_done = False
    static_eval = 0
    did_beta_cutoff = False # Flag per sapere se c'è stato taglio beta

    for i, move_obj in enumerate(ordered_moves):
        is_capture = engine.board[move_obj.end_row][move_obj.end_col] != '.'
        if not is_capture and move_obj.promotion_piece: is_capture = True # Promozione conta come non-quiet
        if not is_capture and engine.board[move_obj.start_row][move_obj.start_col].lower() == 'p' and \
            engine.en_passant_target is not None and (move_obj.end_row, move_obj.end_col) == engine.en_passant_target:
            is_capture = True # Cattura EP conta come non-quiet
        is_quiet = not is_capture

        # --- Futility Pruning (solo a profondità basse) ---
        # Applica solo se non siamo in scacco, la mossa è tranquilla, e alpha non è già un matto
        can_futility_prune = not is_in_check and is_quiet and \
                            alpha < constants.MATE_SCORE - constants.MAX_SEARCH_PLY and \
                            beta < constants.MATE_SCORE - constants.MAX_SEARCH_PLY

        if can_futility_prune and depth == 1:
            if not static_eval_done:
                static_eval = evaluation.evaluate_board(engine.board, current_player_color)
                static_eval_done = True
            # Se la valutazione statica + margine non migliora alpha, salta la mossa
            if static_eval + constants.FUTILITY_MARGIN_DEPTH_1 <= alpha:
                continue # Salta questa mossa tranquilla

        # --- Make Move ---
        engine.make_move(move_obj)
        moves_searched_count += 1

        # --- Calcolo Profondità Ricerca e Estensioni ---
        # Estensione per scacco
        opponent_color_after_move = 'B' if current_player_color == 'W' else 'W'
        gives_check = engine.is_in_check(opponent_color_after_move)
        current_extension = constants.CHECK_EXTENSION if gives_check else 0
        # La profondità base per la chiamata ricorsiva
        current_search_depth = depth - 1 + current_extension

        # --- Ricerca PVS/LMR ---
        score = 0
        move_from_recursive_call = None # Traccia mossa da TT in ricorsione

        # Principal Variation Search (PVS)
        if i == 0: # Prima mossa (presumibilmente la migliore) -> Full Window Search
            score, move_from_recursive_call = negamax(engine, current_search_depth, -beta, -alpha, ply + 1)
            score = -score
        else: # Altre mosse -> Prova Zero Window Search (ZWS) prima
            reduction = 0
            # Late Move Reduction (LMR) - Riduci profondità per mosse tranquille "tardive"
            if current_extension == 0 and depth >= constants.LMR_MIN_DEPTH and i >= constants.LMR_MIN_MOVE_INDEX and is_quiet:
                # La riduzione potrebbe dipendere da profondità e indice 'i'
                reduction = constants.LMR_REDUCTION # Riduzione base
                # Si potrebbe rendere la riduzione più aggressiva per mosse molto tardive o profondità alte
                # reduction += int(math.log(depth) * math.log(i)) # Esempio

            reduced_depth = max(0, current_search_depth - reduction)

            # Zero Window Search (ZWS) con profondità ridotta (se LMR applicata)
            score, _ = negamax(engine, reduced_depth, -alpha - 1, -alpha, ply + 1) # Finestra (-(a+1), -a)
            score = -score

            # Se ZWS fallisce alto (score > alpha), significa che la mossa potrebbe essere migliore di alpha.
            # Dobbiamo rieseguire la ricerca con la finestra completa, ma *senza* riduzione LMR iniziale.
            if score > alpha and score < beta: # Se è potenzialmente dentro la finestra (alpha, beta)
                # Possiamo prima provare senza riduzione se c'era LMR
                if reduction > 0:
                    score, _ = negamax(engine, current_search_depth, -alpha - 1, -alpha, ply + 1)
                    score = -score

                # Se ancora > alpha (o se non c'era LMR), fai la ricerca con finestra piena
                if score > alpha:
                    score, move_from_recursive_call = negamax(engine, current_search_depth, -beta, -alpha, ply + 1)
                    score = -score

        # --- Unmake Move ---
        engine.unmake_move()

        # --- Controllo Tempo (Opzionale qui, più efficace nel loop ID) ---
        # if time_limit is not None and (time.time() - start_time) > time_limit: return alpha, best_move_at_node # O un valore speciale

        # --- Aggiorna Best Score & Alpha per questo nodo ---
        if score > best_score_at_node:
            best_score_at_node = score
            best_move_at_node = move_obj # Aggiorna la mossa migliore trovata a questo nodo

        # Aggiorna il limite inferiore (alpha)
        alpha = max(alpha, score)

        # --- Taglio Beta (Fail High) ---
        if alpha >= beta:
            did_beta_cutoff = True # Imposta flag taglio beta
            # Se la mossa che causa il taglio è tranquilla, aggiorna Killer e History
            if is_quiet:
                # Aggiorna Killer Moves
                if qply < len(killer_moves): # Assicura che l'indice sia valido
                    if move_obj != killer_moves_ply[0]: # Non inserire duplicati
                        killer_moves[qply][1] = killer_moves_ply[0] # Sposta il vecchio primario a secondario
                        killer_moves[qply][0] = move_obj          # Imposta nuovo primario
                # Aggiorna History Heuristic
                start_sq = move_obj.start_row * 8 + move_obj.start_col
                end_sq = move_obj.end_row * 8 + move_obj.end_col
                # Assicura che indici siano validi e incrementa
                if 0 <= start_sq < 64 and 0 <= end_sq < 64:
                    history_heuristic[color_index][start_sq][end_sq] += depth * depth # Incremento quadratico

            # Memorizza nella TT come Lower Bound (punteggio è almeno beta)
            score_to_store_cutoff = beta # Memorizza il limite inferiore che è stato superato
            if score_to_store_cutoff >= constants.MATE_SCORE - constants.MAX_SEARCH_PLY: score_to_store_cutoff += ply
            elif score_to_store_cutoff <= -constants.MATE_SCORE + constants.MAX_SEARCH_PLY: score_to_store_cutoff -= ply
            # Usa la mossa che ha causato il taglio
            _store_tt_entry(transposition_table, tt_index, position_hash, depth, score_to_store_cutoff, constants.TT_BOUND_LOWER, move_obj)
            return beta, move_obj # Ritorna il lower bound (beta) e la mossa

    # --- Fine Loop Mosse Principale ---

    # Se siamo qui, nessuna mossa ha causato un taglio beta (alpha < beta)

    # Verifica caso raro: nessuna mossa trovata valida nel loop (dovrebbe essere coperto da check iniziale 'if not moves')
    if best_move_at_node is None:
        # Questo non dovrebbe accadere se 'moves' non è vuoto all'inizio
        # Potrebbe indicare un problema se tutte le mosse sono state potate da Futility?
        if is_in_check: return -constants.MATE_SCORE + ply, None # Se in scacco e nessuna mossa, è matto
        else: return constants.DRAW_SCORE, None # Altrimenti stallo? O draw? Usiamo DRAW_SCORE.


    # --- Singular Extensions ---
    # (Logica Singular Extension rimane invariata rispetto alla tua ultima versione)
    # Verifica se la migliore mossa trovata è significativamente migliore delle altre
    # e corrisponde alla mossa TT, e se le condizioni di profondità/TT sono soddisfatte.
    singular_extension_to_apply = 0
    singular_candidate_move = best_move_at_node

    # Condizioni per considerare singular extension:
    # - Non alla radice (ply > 0)
    # - Non c'è stato taglio beta in questo nodo
    # - Non siamo in scacco
    # - Profondità sufficiente
    # - Il best score è significativamente sopra alpha originale
    # - Abbiamo una mossa dalla TT e la sua profondità è ragionevole
    can_check_singular = (ply > 0 and not did_beta_cutoff and not is_in_check and
                          depth >= constants.SINGULAR_MIN_DEPTH and
                          best_score_at_node > original_alpha + constants.SINGULAR_ALPHA_MARGIN and
                          tt_move is not None and tt_depth >= depth - 3 ) # tt_depth dalla TT lookup iniziale

    if can_check_singular:
        # Il punteggio TT (tt_score) dalla lookup iniziale serve come riferimento
        verification_beta = tt_score
        # Verifica se il nostro best_score è migliore del punteggio TT di un certo margine
        # e se la mossa migliore coincide con quella della TT
        if verification_beta is not None and \
            best_score_at_node >= verification_beta + constants.SINGULAR_MARGIN and \
            tt_move == best_move_at_node:
            # Sembra una mossa singolare, applichiamo estensione
            singular_extension_to_apply = constants.SINGULAR_EXTENSION_AMOUNT
            singular_candidate_move = tt_move # La mossa da ri-cercare è quella della TT
            # Potrebbe essere utile un re-search con finestra ridotta attorno a verification_beta
            # per confermare, ma per ora applichiamo solo estensione.

    # Se abbiamo deciso di estendere, riesegui la ricerca per quella mossa con profondità aumentata
    if singular_extension_to_apply > 0 and singular_candidate_move is not None:
        extended_depth = depth - 1 + singular_extension_to_apply # Profondità base + estensione
        # Esegui la ricerca solo per la mossa singolare
        engine.make_move(singular_candidate_move)
        # Cerca con la finestra originale (alpha, beta)
        extended_score, _ = negamax(engine, extended_depth, -original_beta, -original_alpha, ply + 1)
        extended_score = -extended_score
        engine.unmake_move()

        # Aggiorna lo score e la mossa *solo se* il re-search ha dato un risultato migliore
        # O semplicemente usa sempre il risultato del re-search? Usiamolo sempre.
        best_score_at_node = extended_score
        best_move_at_node = singular_candidate_move # Assicurati che sia ancora questa la best move

    # --- Determina Bound Finale e Salva in TT ---
    bound_to_store = constants.TT_BOUND_EXACT
    final_score = best_score_at_node

    # Se lo score finale è <= alpha originale, è un Upper Bound (fail low)
    if best_score_at_node <= original_alpha:
        bound_to_store = constants.TT_BOUND_UPPER
        # Non ritornare alpha originale, ma lo score trovato (potrebbe essere utile)
        final_score = best_score_at_node # O forse original_alpha? Manteniamo score trovato.
    # Se lo score finale è >= beta originale (dovrebbe essere gestito da taglio beta, ma ricontrolla), è un Lower Bound
    elif best_score_at_node >= original_beta:
        # Questo caso non dovrebbe accadere se il taglio beta funziona correttamente
        bound_to_store = constants.TT_BOUND_LOWER
        final_score = best_score_at_node # O forse original_beta? Manteniamo score trovato.
    # Altrimenti, è un punteggio esatto
    else:
        bound_to_store = constants.TT_BOUND_EXACT

    # Aggiusta score per mate distance prima di salvare
    score_to_store = best_score_at_node
    if score_to_store >= constants.MATE_SCORE - constants.MAX_SEARCH_PLY: score_to_store += ply
    elif score_to_store <= -constants.MATE_SCORE + constants.MAX_SEARCH_PLY: score_to_store -= ply

    # Salva nella TT (sovrascrivi solo se profondità è maggiore o uguale, gestito da _store_tt_entry)
    _store_tt_entry(transposition_table, tt_index, position_hash, depth, score_to_store, bound_to_store, best_move_at_node)

    # Ritorna lo score finale e la mossa migliore associata
    return final_score, best_move_at_node

# --- Funzione Principale di Ricerca (Iterative Deepening) ---

def allocate_time(time_ms, inc_ms, movestogo):
    """Calcola il tempo per la mossa corrente."""
    if time_ms is None: return None # No time control
    available_time = time_ms / 1000.0
    increment = inc_ms / 1000.0
    time_per_move = 0
    safety_margin_factor = 0.9 # Usa il 90% del tempo allocato

    if movestogo is not None and movestogo > 0:
        # Allocazione basata su mosse rimanenti
        time_per_move = (available_time / movestogo) + increment
    else:
        # Allocazione euristica (es. 1/30 del tempo + incremento)
        # Potresti usare frazioni diverse (es. 1/20, 1/40)
        time_per_move = (available_time / 30.0) + increment

    # Limita il tempo per mossa (es. non usare più del 20% del tempo rimanente)
    max_time_per_move = available_time * 0.20
    time_per_move = min(time_per_move, max_time_per_move)

    # Tempo minimo per mossa
    min_time = 0.05 # 50 millisecondi
    time_per_move = max(time_per_move, min_time)

    # Applica margine di sicurezza
    calculated_time = time_per_move * safety_margin_factor
    # Assicura che anche con margine, non sia meno del minimo assoluto
    return max(calculated_time, min_time * safety_margin_factor)


def search_move(engine, max_depth=constants.MAX_SEARCH_PLY, move_time=None, wtime=None, btime=None, winc=0, binc=0, movestogo=None):
    """
    Esegue la ricerca Iterative Deepening con Aspiration Windows.
    """
    global nodes_searched, q_nodes_searched, tt_probes, tt_hits, nmp_cutoffs, start_time
    nodes_searched = 0; q_nodes_searched = 0; tt_probes = 0; tt_hits = 0; nmp_cutoffs = 0
    start_time = time.time()

    overall_best_move = None
    overall_best_score = -constants.MATE_SCORE * 2 # Valore iniziale invalido
    pv_line_global = []
    time_out_occurred = False # Flag per uscita per tempo

    # Calcola tempo limite
    time_limit = None
    player_time = wtime if engine.current_player == 'W' else btime
    player_inc = winc if engine.current_player == 'W' else binc
    if move_time is not None:
        # Usa un margine di sicurezza anche per movetime fisso
        time_limit = (move_time / 1000.0) * 0.95
    else:
        time_limit = allocate_time(player_time, player_inc, movestogo)

    # Profondità massima effettiva
    effective_max_depth = max_depth if time_limit is None else constants.MAX_SEARCH_PLY

    # Valori per Aspiration Windows
    aspiration_alpha = -constants.MATE_SCORE * 2
    aspiration_beta = constants.MATE_SCORE * 2
    aspiration_delta = 35 # Finestra iniziale (circa 1/3 di pedone)

    # --- Iterative Deepening ---
    for current_depth in range(1, effective_max_depth + 1):
        # Imposta finestra di aspirazione se abbiamo uno score precedente valido
        if overall_best_score > -constants.MATE_SCORE * 2 + constants.MAX_SEARCH_PLY: # Usa score valido
            alpha = max(-constants.MATE_SCORE * 2, overall_best_score - aspiration_delta)
            beta = min(constants.MATE_SCORE * 2, overall_best_score + aspiration_delta)
        else: # Prima iterazione o fallimento precedente, usa finestra ampia
            alpha = -constants.MATE_SCORE * 2
            beta = constants.MATE_SCORE * 2

        # Loop per Aspiration Window (potrebbe richiedere re-search)
        research_count = 0
        while True:
            research_count += 1
            if research_count > 1:
                print(f"info string Re-searching depth {current_depth} with window ({alpha}, {beta})", file=sys.stderr, flush=True)
                # Aumenta delta per la prossima riesecuzione se fallisce di nuovo
                aspiration_delta = int(aspiration_delta * 1.8) # Aumenta finestra esponenzialmente

            # Esegui la ricerca Negamax alla radice per questa profondità e finestra
            # (Negamax internamente gestirà TT, NMP, LMR, ecc.)
            current_search_best_score, current_search_best_move = negamax(engine, current_depth, alpha, beta, 0) # ply = 0 alla radice

            # Controlla se il tempo è scaduto DOPO la chiamata a negamax
            elapsed_time_check = time.time() - start_time
            if time_limit is not None and elapsed_time_check > time_limit:
                print("info string Time limit reached during search (Aspiration)", file=sys.stderr, flush=True)
                time_out_occurred = True
                break # Esce dal while True

            # Verifica se la ricerca è fallita bassa (score <= alpha originale)
            if current_search_best_score <= alpha and research_count < 4: # Limita re-search
                print(f"info string Aspiration Fail Low (score {current_search_best_score} <= alpha {alpha}) at depth {current_depth}. Re-searching.", file=sys.stderr, flush=True)
                # Allarga la finestra verso il basso e ricerca di nuovo
                alpha = -constants.MATE_SCORE * 2 # Apri limite inferiore
                beta = current_search_best_score + aspiration_delta # Tieni beta vicino allo score trovato
                continue # Riesegui il while True

            # Verifica se la ricerca è fallita alta (score >= beta originale)
            if current_search_best_score >= beta and research_count < 4: # Limita re-search
                print(f"info string Aspiration Fail High (score {current_search_best_score} >= beta {beta}) at depth {current_depth}. Re-searching.", file=sys.stderr, flush=True)
                # Allarga la finestra verso l'alto e ricerca di nuovo
                beta = constants.MATE_SCORE * 2 # Apri limite superiore
                alpha = current_search_best_score - aspiration_delta # Tieni alpha vicino allo score trovato
                continue # Riesegui il while True

            # --- Ricerca Riuscita (o troppi re-search) ---
            # Aggiorna il risultato *generale* con quello di questa ricerca.
            # Solo se la ricerca non è fallita in modo irrecuperabile
            if current_search_best_move is not None:
                overall_best_move = current_search_best_move
                overall_best_score = current_search_best_score
                # Resetta delta per la prossima iterazione ID
                aspiration_delta = 35 # Resetta alla finestra iniziale

                # Ricostruzione PV (Principal Variation) dalla TT
                pv_line_global = []
                try:
                    import copy
                    temp_engine = copy.deepcopy(engine) # Lavora su una copia
                    current_pv_move = overall_best_move
                    for _pv_depth in range(current_depth): # Limita a profondità corrente
                        if current_pv_move is None: break
                        # Verifica legalità (dovrebbe essere legale se da negamax)
                        if current_pv_move not in temp_engine.get_legal_moves(temp_engine.current_player): break

                        pv_line_global.append(current_pv_move.to_uci_string())
                        temp_engine.make_move(current_pv_move)

                        # Cerca la prossima mossa PV nella TT
                        tt_idx_pv = temp_engine.current_hash % constants.TT_SIZE
                        tt_entry_pv = engine.transposition_table[tt_idx_pv] # Usa la TT originale aggiornata
                        next_move = None
                        if tt_entry_pv and tt_entry_pv['hash'] == temp_engine.current_hash:
                            pv_move_from_tt = tt_entry_pv.get('best_move')
                            if isinstance(pv_move_from_tt, m.Move):
                                next_move = pv_move_from_tt
                        current_pv_move = next_move # Prossima mossa o None
                except Exception as e:
                    # Fallback: usa solo la prima mossa se PV fallisce
                    pv_line_global = [overall_best_move.to_uci_string()] if overall_best_move else []
                # --- Fine Ricostruzione PV ---

            else:
                # Nessuna mossa trovata (matto/stallo?)
                print(f"WARN: No best move found for depth {current_depth}.", file=sys.stderr, flush=True)
                # Mantieni i risultati precedenti, esci dal loop ID?
                # Potrebbe essere che get_legal_moves fallisca o ritorni lista vuota
                # Controlla questo caso all'inizio di negamax
                # Se arriviamo qui, è strano. Forse uscire.
                time_out_occurred = True # Tratta come un problema e usa risultato precedente


            # Esci dal loop while True, abbiamo finito per questa profondità ID
            break
        # --- Fine Loop Aspiration Window (while True) ---

        # --- Stampa Info UCI ---
        elapsed_time = time.time() - start_time
        score_str = ""
        # Usa l'ultimo score valido 'overall_best_score' per la stampa
        if overall_best_score > -constants.MATE_SCORE * 2 + constants.MAX_SEARCH_PLY: # Score valido
            temp_score_for_print = overall_best_score
            if abs(temp_score_for_print) >= constants.MATE_SCORE - constants.MAX_SEARCH_PLY:
                mate_in_plies = constants.MATE_SCORE - abs(temp_score_for_print)
                mate_in_moves = (mate_in_plies + 1) // 2 # Arrotonda per eccesso
                mate_in_moves = max(1, mate_in_moves) # Almeno 1
                score_sign = "" if temp_score_for_print > 0 else "-" # Segno per mate negativi
                score_str = f"mate {score_sign}{int(mate_in_moves)}"
            else:
                score_str = f"cp {int(temp_score_for_print)}"
        else:
            score_str = "cp 0" # Default se non abbiamo score valido

        total_nodes = nodes_searched + q_nodes_searched
        nps = int(total_nodes / elapsed_time) if elapsed_time > 0 else 0
        pv_str = " ".join(pv_line_global) if pv_line_global else ""
        # Calcola hashfull (opzionale, può rallentare)
        # filled_count = sum(1 for entry in engine.transposition_table if entry is not None)
        # hashfull = (filled_count * 1000 // constants.TT_SIZE) # Permille
        # print(f"info depth {current_depth} score {score_str} nodes {total_nodes} nps {nps} hashfull {hashfull} time {int(elapsed_time * 1000)} pv {pv_str}", flush=True)
        # Stampa senza hashfull per performance
        print(f"info depth {current_depth} score {score_str} nodes {total_nodes} nps {nps} time {int(elapsed_time * 1000)} pv {pv_str}", flush=True)


        # --- Controlli Uscita Loop ID ---
        if time_out_occurred: # Se il tempo è scaduto durante la ricerca
            break
        # Controlla tempo di nuovo dopo la stampa
        if time_limit is not None and (time.time() - start_time) > time_limit:
            print("info string Exiting ID loop due to time limit after depth info.", file=sys.stderr, flush=True)
            break
        # Se abbiamo trovato un matto, fermati (controlla usando lo score numerico)
        if abs(overall_best_score) >= constants.MATE_SCORE - constants.MAX_SEARCH_PLY:
            print("info string Exiting ID loop due to mate found.", file=sys.stderr, flush=True)
            break

    # --- Fine Iterative Deepening ---

    # Se non abbiamo mai trovato una mossa (es. tempo scaduto alla prima iterazione)
    if overall_best_move is None:
        print("info string Fallback: No best move found during search, selecting first legal move.", file=sys.stderr, flush=True)
        final_legal_moves = engine.get_legal_moves(engine.current_player)
        overall_best_move = final_legal_moves[0] if final_legal_moves else None # Prendi la prima se esiste

    # Ritorna la mossa migliore trovata
    return overall_best_move