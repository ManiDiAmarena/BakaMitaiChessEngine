# -*- coding: utf-8 -*-
import constants
import pst

def get_piece_color(piece): # Funzione helper locale o importata da board? Mettiamola qui per ora.
    if piece == '.': return None
    return 'W' if piece.isupper() else 'B'

# --- NUOVA Funzione per Calcolare Fase Numerica ---
def calculate_game_phase(board_array):
    """Calcola la fase numerica della partita (0=EG puro, GAME_PHASE_MAX=MG pieno)."""
    current_phase_score = 0
    for r in range(8):
        for c in range(8):
            piece = board_array[r][c]
            if piece != '.':
                # Usa PIECE_PHASE_VALUES da constants
                current_phase_score += constants.PIECE_PHASE_VALUES.get(piece.lower(), 0)
    # Limita tra 0 e GAME_PHASE_MAX (importante se i valori non sono perfetti)
    phase = max(0, min(constants.GAME_PHASE_MAX, current_phase_score))
    return phase

# --- NUOVA Funzione Helper per Interpolazione Valori ---
def get_tapered_value(mg_eg_tuple, phase):
    """Calcola il valore interpolato da una tupla (mg_val, eg_val)."""
    mg_val, eg_val = mg_eg_tuple
    max_phase = constants.GAME_PHASE_MAX
    if max_phase == 0: # Evita divisione per zero se GAME_PHASE_MAX è 0
        return eg_val # O mg_val, a seconda di cosa ha più senso
    # Interpolazione: più alta è la fase, più pesa mg_val
    tapered = ((mg_val * phase) + (eg_val * (max_phase - phase))) / max_phase
    return int(tapered) # Ritorna un intero

# --- NUOVA Funzione Helper per Interpolazione PST ---
def get_tapered_pst_value(piece_char, square_index, phase):
    """Ottiene il valore PST. Interpola SOLO per il Re."""
    piece_type = piece_char.lower()
    max_phase = constants.GAME_PHASE_MAX
    if max_phase == 0: max_phase = 1 # Evita divisione per zero

    # Applica mirroring PRIMA di accedere alle tabelle
    lookup_index = square_index ^ 56 if piece_char.islower() else square_index
    if not (0 <= lookup_index < 64): return 0

    # --- Logica Modificata ---
    if piece_type == 'k':
        # Interpola SOLO per il Re
        mg_val = pst.KING_PST_MIDGAME[lookup_index]
        eg_val = pst.KING_PST_ENDGAME[lookup_index]
        tapered_val = ((mg_val * phase) + (eg_val * (max_phase - phase))) / max_phase
        return int(tapered_val)
    else:
        # Per TUTTI gli altri pezzi (P, N, B, R, Q): usa il valore PST standard (MG)
        # senza considerare la fase.
        table_key = piece_type
        table = pst._PST_TABLES.get(table_key) # Accede al dizionario interno di pst
        if table is None: return 0
        # Ritorna direttamente il valore dalla tabella MG
        return table[lookup_index]

def _estimate_game_phase(board_array):
    """Stima la fase della partita (MIDGAME o ENDGAME)."""
    white_material = 0
    black_material = 0
    for r in range(8):
        for c in range(8):
            piece = board_array[r][c]
            if piece != '.':
                piece_type = piece.lower()
                if piece_type != 'k':
                    value = constants.PIECE_VALUES_SIMPLE_FOR_PHASE.get(piece_type, 0)
                    if get_piece_color(piece) == 'W':
                        white_material += value
                    else:
                        black_material += value
    total_material = white_material + black_material
    return "ENDGAME" if total_material <= constants.ENDGAME_MATERIAL_THRESHOLD else "MIDGAME"

def _calculate_bishop_pair(white_bishops, black_bishops):
    """Calcola il bonus/malus per la coppia di alfieri."""
    score = 0
    if white_bishops >= 2: score += constants.BISHOP_PAIR_BONUS
    if black_bishops >= 2: score -= constants.BISHOP_PAIR_BONUS
    return score

def _calculate_pawn_structure(board_array, white_pawns_on_file_counts, black_pawns_on_file_counts, phase): # Aggiunto phase
    """Calcola i termini di valutazione relativi alla struttura pedonale (tapered)."""
    # Ottieni i valori tapered delle penalità
    penalty_doubled = get_tapered_value(constants.DOUBLED_PAWN_PENALTY, phase)
    penalty_isolated = get_tapered_value(constants.ISOLATED_PAWN_PENALTY, phase)
    penalty_backward = get_tapered_value(constants.BACKWARD_PAWN_PENALTY, phase)

    pawn_structure_score = 0
    white_pawn_positions = []
    black_pawn_positions = []
    white_pawn_on_file_exists = [False] * 8
    black_pawn_on_file_exists = [False] * 8

    for r in range(8):
        for c in range(8):
            piece = board_array[r][c]
            if piece == 'P':
                white_pawn_positions.append((r, c))
                white_pawn_on_file_exists[c] = True
            elif piece == 'p':
                black_pawn_positions.append((r, c))
                black_pawn_on_file_exists[c] = True

    # Penalità Pedoni Doppiati (usa valore tapered)
    for c in range(8):
        if white_pawns_on_file_counts[c] > 1:
            pawn_structure_score -= penalty_doubled * (white_pawns_on_file_counts[c] - 1)
        if black_pawns_on_file_counts[c] > 1:
            pawn_structure_score += penalty_doubled * (black_pawns_on_file_counts[c] - 1)

    # Penalità Pedoni Isolati E Arretrati (usa valori tapered)
    # Pedoni Bianchi
    for r_pawn, c_pawn in white_pawn_positions:
        is_isolated = True
        has_support_behind_left = False
        has_support_behind_right = False
        if c_pawn > 0:
            if white_pawn_on_file_exists[c_pawn - 1]: is_isolated = False
            for r_check in range(r_pawn + 1, 8):
                if board_array[r_check][c_pawn - 1] == 'P': has_support_behind_left = True; break
        if c_pawn < 7:
            if white_pawn_on_file_exists[c_pawn + 1]: is_isolated = False
            for r_check in range(r_pawn + 1, 8):
                if board_array[r_check][c_pawn + 1] == 'P': has_support_behind_right = True; break
        if is_isolated: pawn_structure_score -= penalty_isolated # Usa tapered
        is_backward = not has_support_behind_left and not has_support_behind_right
        if is_backward:
            is_semi_open = True
            for r_check in range(r_pawn - 1, -1, -1):
                if board_array[r_check][c_pawn] == 'P': is_semi_open = False; break
            if is_semi_open: pawn_structure_score -= penalty_backward # Usa tapered

    # Pedoni Neri (logica speculare)
    for r_pawn, c_pawn in black_pawn_positions:
        is_isolated = True
        has_support_behind_left = False
        has_support_behind_right = False
        if c_pawn > 0:
            if black_pawn_on_file_exists[c_pawn - 1]: is_isolated = False
            for r_check in range(r_pawn - 1, -1, -1):
                if board_array[r_check][c_pawn - 1] == 'p': has_support_behind_left = True; break
        if c_pawn < 7:
            if black_pawn_on_file_exists[c_pawn + 1]: is_isolated = False
            for r_check in range(r_pawn - 1, -1, -1):
                if board_array[r_check][c_pawn + 1] == 'p': has_support_behind_right = True; break
        if is_isolated: pawn_structure_score += penalty_isolated # Usa tapered
        is_backward = not has_support_behind_left and not has_support_behind_right
        if is_backward:
            is_semi_open = True
            for r_check in range(r_pawn + 1, 8):
                if board_array[r_check][c_pawn] == 'p': is_semi_open = False; break
            if is_semi_open: pawn_structure_score += penalty_backward # Usa tapered

    return pawn_structure_score

def _calculate_rook_placement(board_array, white_pawns_on_file_counts, black_pawns_on_file_counts, phase): # Aggiunto phase
    """Calcola i bonus per il posizionamento delle torri (tapered)."""
    # Ottieni i bonus tapered
    bonus_rook_open = get_tapered_value(constants.ROOK_OPEN_FILE_BONUS, phase)
    bonus_rook_semi_open = get_tapered_value(constants.ROOK_SEMI_OPEN_FILE_BONUS, phase)
    bonus_rook_seventh = get_tapered_value(constants.ROOK_ON_SEVENTH_BONUS, phase)

    rook_placement_score = 0
    for r in range(8):
        for c in range(8):
            piece = board_array[r][c]
            if piece.lower() == 'r':
                is_white_rook = (piece == 'R')
                is_open_file = (white_pawns_on_file_counts[c] == 0 and black_pawns_on_file_counts[c] == 0)
                is_semi_open_for_white = (white_pawns_on_file_counts[c] == 0 and black_pawns_on_file_counts[c] > 0) # Modificato per chiarezza
                is_semi_open_for_black = (black_pawns_on_file_counts[c] == 0 and white_pawns_on_file_counts[c] > 0) # Modificato per chiarezza

                if is_white_rook:
                    if is_open_file: rook_placement_score += bonus_rook_open # Usa tapered
                    elif is_semi_open_for_white: rook_placement_score += bonus_rook_semi_open # Usa tapered
                    if r == 1: # Riga 7 dal punto di vista del nero (indice 1)
                         rook_placement_score += bonus_rook_seventh # Usa tapered
                else: # Torre Nera
                    if is_open_file: rook_placement_score -= bonus_rook_open # Usa tapered
                    elif is_semi_open_for_black: rook_placement_score -= bonus_rook_semi_open # Usa tapered
                    if r == 6: # Riga 2 dal punto di vista del bianco (indice 6)
                         rook_placement_score -= bonus_rook_seventh # Usa tapered
    return rook_placement_score

def _count_pieces_between(board_array, r1, c1, r2, c2):
    """Conta i pezzi tra due case (esclusi gli estremi) su una linea retta o diagonale."""
    count = 0
    dr = 0 if r1 == r2 else (1 if r2 > r1 else -1)
    dc = 0 if c1 == c2 else (1 if c2 > c1 else -1)
    r, c = r1 + dr, c1 + dc
    while r != r2 or c != c2:
        if not (0 <= r < 8 and 0 <= c < 8): # Sicurezza extra, non dovrebbe servire
            break
        if board_array[r][c] != '.':
            count += 1
        r += dr
        c += dc
    return count

def _calculate_king_safety(board_array, white_king_pos, black_king_pos,
                           white_pawns_on_file_counts, black_pawns_on_file_counts, phase): # Aggiunto phase, rimosso game_phase
    """
    Calcola i termini di valutazione relativi alla sicurezza del Re (tapered).
    Ora combina logica MG ed EG usando valori interpolati.
    """
    king_safety_score = 0

    # Ottieni valori tapered una volta
    bonus_king_shield = get_tapered_value(constants.KING_SHIELD_BONUS, phase)
    penalty_king_open = get_tapered_value(constants.KING_OPEN_FILE_PENALTY, phase)
    penalty_king_semi_open = get_tapered_value(constants.KING_SEMI_OPEN_FILE_PENALTY, phase)
    penalty_eg_rook_open = get_tapered_value(constants.ENDGAME_KING_ROOK_ATTACK_OPEN, phase)
    penalty_eg_rook_semi = get_tapered_value(constants.ENDGAME_KING_ROOK_ATTACK_SEMI, phase)
    penalty_eg_queen_open = get_tapered_value(constants.ENDGAME_KING_QUEEN_ATTACK_OPEN, phase)
    penalty_eg_queen_semi = get_tapered_value(constants.ENDGAME_KING_QUEEN_ATTACK_SEMI, phase)

    # --- Termini relativi alla Sicurezza Re Bianco ---
    if white_king_pos:
        kr, kc = white_king_pos
        # 1. Scudo Pedoni Bianchi (vale più in MG, taper a 0 in EG)
        if bonus_king_shield != 0: # Ottimizzazione: non cercare se il bonus è 0
            shield_squares = []
            # ... (logica invariata per trovare shield_squares) ...
            if kr > 0:
                shield_squares.extend([(kr-1, kc)])
                if kc > 0: shield_squares.append((kr-1, kc-1))
                if kc < 7: shield_squares.append((kr-1, kc+1))
            # ... (altre case scudo, se necessario) ...
            for sr, sc in shield_squares:
                if 0 <= sr < 8 and 0 <= sc < 8 and board_array[sr][sc] == 'P':
                    king_safety_score += bonus_king_shield # Usa tapered

        # 2. Penalità Colonne Aperte/Semi-Aperte vicino al Re Bianco (vale più in MG, taper a ~0 in EG)
        if penalty_king_open != 0 or penalty_king_semi_open != 0:
            king_files_to_check = [kc] + ([kc - 1] if kc > 0 else []) + ([kc + 1] if kc < 7 else [])
            for file_c in king_files_to_check:
                is_open_file = (white_pawns_on_file_counts[file_c] == 0 and black_pawns_on_file_counts[file_c] == 0)
                is_semi_open_for_black = (white_pawns_on_file_counts[file_c] == 0 and black_pawns_on_file_counts[file_c] > 0) # Senza pedoni bianchi
                if is_open_file: king_safety_score -= penalty_king_open # Usa tapered
                elif is_semi_open_for_black: king_safety_score -= penalty_king_semi_open # Usa tapered

        # 3. Penalità Attacchi EG su Linee Aperte/Semi (vale 0 in MG, taper a valore pieno in EG)
        enemy_pieces_heavy = [] # Trova pezzi pesanti NERI
        for r in range(8):
            for c in range(8):
                piece = board_array[r][c]
                if piece == 'r' or piece == 'q':
                    enemy_pieces_heavy.append((piece, r, c))

        if penalty_eg_rook_open != 0 or penalty_eg_rook_semi != 0 or \
           penalty_eg_queen_open != 0 or penalty_eg_queen_semi != 0:
            for piece, pr, pc in enemy_pieces_heavy:
                piece_type = piece.lower()
                on_same_line = False
                is_diagonal = abs(kr - pr) == abs(kc - pc)
                is_straight = (kr == pr) or (kc == pc)
                if piece_type == 'r' and is_straight: on_same_line = True
                if piece_type == 'q' and (is_straight or is_diagonal): on_same_line = True

                if on_same_line:
                    pieces_between = _count_pieces_between(board_array, kr, kc, pr, pc)
                    if pieces_between == 0: # Linea aperta
                        penalty = penalty_eg_rook_open if piece_type == 'r' else penalty_eg_queen_open
                        king_safety_score -= penalty # Usa tapered
                    elif pieces_between == 1: # Linea semi-aperta
                        penalty = penalty_eg_rook_semi if piece_type == 'r' else penalty_eg_queen_semi
                        king_safety_score -= penalty # Usa tapered

    # --- Termini relativi alla Sicurezza Re Nero (logica speculare) ---
    if black_king_pos:
        kr, kc = black_king_pos
        # 1. Scudo Pedoni Neri
        if bonus_king_shield != 0:
            shield_squares = []
            # ... (logica invariata per trovare shield_squares per il nero) ...
            if kr < 7:
                shield_squares.extend([(kr+1, kc)])
                if kc > 0: shield_squares.append((kr+1, kc-1))
                if kc < 7: shield_squares.append((kr+1, kc+1))
            # ...
            for sr, sc in shield_squares:
                if 0 <= sr < 8 and 0 <= sc < 8 and board_array[sr][sc] == 'p':
                    king_safety_score -= bonus_king_shield # Bonus nero = malus bianco (usa tapered)

        # 2. Penalità Colonne Aperte/Semi-Aperte vicino al Re Nero
        if penalty_king_open != 0 or penalty_king_semi_open != 0:
            king_files_to_check = [kc] + ([kc - 1] if kc > 0 else []) + ([kc + 1] if kc < 7 else [])
            for file_c in king_files_to_check:
                is_open_file = (white_pawns_on_file_counts[file_c] == 0 and black_pawns_on_file_counts[file_c] == 0)
                is_semi_open_for_white = (black_pawns_on_file_counts[file_c] == 0 and white_pawns_on_file_counts[file_c] > 0) # Senza pedoni neri
                if is_open_file: king_safety_score += penalty_king_open # Penalità nero = bonus bianco (usa tapered)
                elif is_semi_open_for_white: king_safety_score += penalty_king_semi_open # Usa tapered

        # 3. Penalità Attacchi EG su Linee Aperte/Semi (da pezzi BIANCHI)
        enemy_pieces_heavy = [] # Trova pezzi pesanti BIANCHI
        for r in range(8):
            for c in range(8):
                piece = board_array[r][c]
                if piece == 'R' or piece == 'Q':
                    enemy_pieces_heavy.append((piece, r, c))

        if penalty_eg_rook_open != 0 or penalty_eg_rook_semi != 0 or \
           penalty_eg_queen_open != 0 or penalty_eg_queen_semi != 0:
            for piece, pr, pc in enemy_pieces_heavy:
                piece_type = piece.lower()
                on_same_line = False
                is_diagonal = abs(kr - pr) == abs(kc - pc)
                is_straight = (kr == pr) or (kc == pc)
                if piece_type == 'r' and is_straight: on_same_line = True
                if piece_type == 'q' and (is_straight or is_diagonal): on_same_line = True

                if on_same_line:
                    pieces_between = _count_pieces_between(board_array, kr, kc, pr, pc)
                    if pieces_between == 0: # Linea aperta
                        penalty = penalty_eg_rook_open if piece_type == 'r' else penalty_eg_queen_open
                        king_safety_score += penalty # Penalità nero = bonus bianco (usa tapered)
                    elif pieces_between == 1: # Linea semi-aperta
                        penalty = penalty_eg_rook_semi if piece_type == 'r' else penalty_eg_queen_semi
                        king_safety_score += penalty # Usa tapered

    return king_safety_score

def _calculate_passed_pawns(board_array, phase, tapered_rank_bonus_list): # Aggiunto phase e tapered_rank_bonus_list
    """Calcola il bonus/malus per i pedoni passati (tapered)."""
    passed_pawn_score = 0
    # Ottieni il bonus base tapered
    bonus_passed_base = get_tapered_value(constants.PASSED_PAWN_BONUS_BASE, phase)

    for r in range(1, 7): # Pedoni non possono essere passati sulla 1a/8a riga
        for c in range(8):
            piece = board_array[r][c]
            if piece.lower() == 'p':
                piece_color = get_piece_color(piece)
                is_passed = True
                # Direzione di avanzamento del pedone corrente
                advance_direction = -1 if piece_color == 'W' else 1
                # Righe davanti al pedone nella sua colonna e colonne adiacenti
                check_range_row = range(r + advance_direction, -1 if piece_color == 'W' else 8, advance_direction)
                enemy_pawn = 'p' if piece_color == 'W' else 'P'

                # Controlla pedoni nemici davanti nelle 3 colonne rilevanti
                for check_r in check_range_row:
                    # Colonna stessa
                    if board_array[check_r][c] == enemy_pawn: is_passed = False; break
                    # Colonna sinistra
                    if c > 0 and board_array[check_r][c - 1] == enemy_pawn: is_passed = False; break
                    # Colonna destra
                    if c < 7 and board_array[check_r][c + 1] == enemy_pawn: is_passed = False; break
                if not is_passed: continue # Se trovi un blocco, vai al prossimo pedone

                # È passato!
                # Usa la lista dei bonus di rango GIA' TAPERED passata come argomento
                rank_index = (7 - r) if piece_color == 'W' else r # Indice 0=vicino alla propria base, 7=vicino alla promozione
                rank_bonus = tapered_rank_bonus_list[rank_index]

                bonus = bonus_passed_base + rank_bonus # Somma base tapered + rank tapered
                passed_pawn_score += bonus if piece_color == 'W' else -bonus
    return passed_pawn_score

def _calculate_mobility(board_array):
    """Calcola il bonus/malus per la mobilità dei pezzi (esclusi Re e Pedoni)."""
    mobility_score = 0
    for r in range(8):
        for c in range(8):
            piece = board_array[r][c]
            if piece != '.' and piece.lower() not in ('p', 'k'):
                piece_char = piece
                piece_color = get_piece_color(piece_char)
                piece_type = piece.lower()
                square_index = r * 8 + c
                piece_mobility_value_sum = 0

                if piece_type == 'n':
                    knight_moves = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
                    multiplier = constants.MOBILITY_KNIGHT_MULTIPLIER
                    for dr, dc in knight_moves:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 8 and 0 <= nc < 8:
                            target_piece = board_array[nr][nc]
                            if target_piece == '.' or get_piece_color(target_piece) != piece_color:
                                target_square_index = nr * 8 + nc
                                piece_mobility_value_sum += constants.MOBILITY_SQUARE_BONUS[target_square_index]
                    mobility_score += piece_mobility_value_sum * multiplier * (1 if piece_color == 'W' else -1)

                elif piece_type in ('b', 'r', 'q'):
                    directions = []
                    multiplier = 0
                    if piece_type == 'b': directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]; multiplier = constants.MOBILITY_BISHOP_MULTIPLIER
                    elif piece_type == 'r': directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]; multiplier = constants.MOBILITY_ROOK_MULTIPLIER
                    elif piece_type == 'q': directions = [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]; multiplier = constants.MOBILITY_QUEEN_MULTIPLIER

                    for dr, dc in directions:
                        for i in range(1, 8):
                            sr, sc = r + i * dr, c + i * dc
                            if not (0 <= sr < 8 and 0 <= sc < 8): break
                            target_piece = board_array[sr][sc]
                            target_square_index = sr * 8 + sc
                            if target_piece == '.':
                                piece_mobility_value_sum += constants.MOBILITY_SQUARE_BONUS[target_square_index]
                            else:
                                if get_piece_color(target_piece) != piece_color:
                                    piece_mobility_value_sum += constants.MOBILITY_SQUARE_BONUS[target_square_index]
                                break
                    mobility_score += piece_mobility_value_sum * multiplier * (1 if piece_color == 'W' else -1)
    return mobility_score

def _calculate_pawn_rams(board_array, phase): # Aggiunto phase
    """Calcola la penalità per i pedoni bloccati frontalmente (rams) (tapered)."""
    penalty_ram = get_tapered_value(constants.PAWN_RAM_PENALTY, phase)
    pawn_ram_score = 0
    for c in range(8):
        for r in range(1, 7):
            if board_array[r][c] == 'P' and board_array[r-1][c] == 'p':
                pawn_ram_score -= penalty_ram # Usa tapered
    return pawn_ram_score

def _calculate_material_imbalance(board_array, phase): # Aggiunto phase
    """Calcola bonus/malus per coppie di Cavalli e Torri (tapered)."""
    # Ottieni valori tapered
    penalty_knight_pair = get_tapered_value(constants.KNIGHT_PAIR_PENALTY, phase)
    bonus_rook_pair = get_tapered_value(constants.ROOK_PAIR_BONUS, phase)

    imbalance_score = 0
    white_knights = 0; black_knights = 0
    white_bishops = 0; black_bishops = 0
    white_rooks = 0;   black_rooks = 0

    # ... (logica conteggio pezzi invariata) ...
    for r in range(8):
        for c in range(8):
            piece = board_array[r][c]
            if piece != '.':
                piece_color = get_piece_color(piece)
                piece_type = piece.lower()
                if piece_type == 'n':
                    if piece_color == 'W': white_knights += 1
                    else: black_knights += 1
                elif piece_type == 'b':
                    if piece_color == 'W': white_bishops += 1
                    else: black_bishops += 1
                elif piece_type == 'r':
                    if piece_color == 'W': white_rooks += 1
                    else: black_rooks += 1


    # 1. Penalità Coppia di Cavalli (usa valore tapered)
    if white_knights >= 2 and black_bishops >= 1:
        imbalance_score -= penalty_knight_pair
    if black_knights >= 2 and white_bishops >= 1:
        imbalance_score += penalty_knight_pair

    # 2. Bonus Coppia di Torri (usa valore tapered)
    if white_rooks >= 2:
        imbalance_score += bonus_rook_pair
    if black_rooks >= 2:
        imbalance_score -= bonus_rook_pair

    return imbalance_score

def evaluate_board(board_array, current_player_color):
    """
    Valuta la posizione usando Tapered Evaluation.
    Chiama le funzioni helper aggiornate che accettano il parametro 'phase'.
    """
    # --- Inizializzazione Punteggi ---
    material_score = 0
    positional_score = 0 # Accumula PST tapered
    pawn_structure_score = 0
    piece_placement_score = 0 # Accumula bonus/malus piazzamento (es. coppia alfieri, torri)
    king_safety_score = 0
    mobility_score = 0
    tempo_bonus_score = 0
    material_imbalance_score = 0

    # --- Calcola Fase Numerica ---
    phase = calculate_game_phase(board_array)

    # --- Raccolta Dati Iniziale e Calcolo Materiale/PST ---
    white_bishops = 0
    black_bishops = 0
    white_pawns_on_file_counts = [0] * 8
    black_pawns_on_file_counts = [0] * 8
    white_king_pos = None
    black_king_pos = None

    for r in range(8):
        for c in range(8):
            piece = board_array[r][c]
            if piece != '.':
                piece_char = piece
                piece_color = get_piece_color(piece_char)
                piece_type = piece.lower()
                square_index = r * 8 + c

                # 1. Materiale (non tapered per ora)
                value = constants.PIECE_VALUES.get(piece_type, 0)
                material_score += value if piece_color == 'W' else -value

                # 2. Punteggio Posizionale (da PST Tapered)
                pst_val = get_tapered_pst_value(piece_char, square_index, phase)
                # Aggiungi direttamente: get_tapered_pst_value dovrebbe già considerare il colore
                # tramite il mirroring dell'indice se necessario.
                positional_score += pst_val

                # 3. Raccolta dati per altre valutazioni
                if piece_type == 'b':
                    if piece_color == 'W': white_bishops += 1
                    else: black_bishops += 1
                elif piece_type == 'p':
                    if piece_color == 'W': white_pawns_on_file_counts[c] += 1
                    else: black_pawns_on_file_counts[c] += 1
                elif piece_type == 'k':
                    if piece_color == 'W': white_king_pos = (r, c)
                    else: black_king_pos = (r, c)

    # --- Calcolo Termini Aggiuntivi usando Funzioni Helper Aggiornate ---

    # Precalcola la lista dei bonus di rango tapered per i pedoni passati
    tapered_rank_bonus = [get_tapered_value(bonus_tuple, phase) for bonus_tuple in constants.PASSED_PAWN_RANK_BONUS]

    # Chiama le funzioni helper passando 'phase' (e 'tapered_rank_bonus' per i pedoni passati)
    # Assumiamo che queste funzioni siano state modificate come discusso
    pawn_structure_score += _calculate_pawn_structure(board_array, white_pawns_on_file_counts, black_pawns_on_file_counts, phase)
    pawn_structure_score += _calculate_passed_pawns(board_array, phase, tapered_rank_bonus)
    pawn_structure_score += _calculate_pawn_rams(board_array, phase)

    piece_placement_score += _calculate_rook_placement(board_array, white_pawns_on_file_counts, black_pawns_on_file_counts, phase)

    king_safety_score += _calculate_king_safety(board_array, white_king_pos, black_king_pos, white_pawns_on_file_counts, black_pawns_on_file_counts, phase)

    # La mobilità potrebbe essere resa tapered in futuro, per ora no
    mobility_score += _calculate_mobility(board_array)

    material_imbalance_score += _calculate_material_imbalance(board_array, phase)

    # Calcola qui i termini che non erano nelle funzioni helper dedicate
    # Bonus Coppia Alfieri (Tapered)
    bonus_bishop_pair = get_tapered_value(constants.BISHOP_PAIR_BONUS, phase)
    if white_bishops >= 2: piece_placement_score += bonus_bishop_pair
    if black_bishops >= 2: piece_placement_score -= bonus_bishop_pair

    # Bonus Tempo (Tapered)
    tapered_tempo = get_tapered_value(constants.TEMPO_BONUS, phase)
    if current_player_color == 'W':
        tempo_bonus_score = tapered_tempo
    else:
        tempo_bonus_score = -tapered_tempo

    # --- Combina Tutti i Punteggi ---
    total_score = (
        material_score +
        positional_score +
        pawn_structure_score +
        piece_placement_score +
        king_safety_score +
        mobility_score +
        tempo_bonus_score +
        material_imbalance_score
    )

    # --- Applica Prospettiva e Clipping ---
    # La prospettiva dipende da chi deve muovere, per allinearsi con Negamax
    perspective = 1 if current_player_color == 'W' else -1

    # Clipping per evitare valori eccessivi che si avvicinano a MATE_SCORE
    # Usiamo un cap un po' sotto il punteggio di matto per sicurezza
    eval_cap = constants.MATE_SCORE // 2 - 1 # Esempio di cap
    # Assicurati che MATE_SCORE sia significativamente più grande di qualsiasi possibile somma dei termini
    total_score_clipped = max(-eval_cap, min(eval_cap, total_score))

    # Applica la prospettiva *dopo* aver calcolato lo score assoluto
    final_eval = total_score_clipped * perspective

    # Debug (opzionale)
    # print(f"Eval details: Phase={phase}, Material={material_score*perspective}, Positional={positional_score*perspective}, "
    #       f"PawnStruct={pawn_structure_score*perspective}, PiecePlace={piece_placement_score*perspective}, "
    #       f"KingSafety={king_safety_score*perspective}, Mobility={mobility_score*perspective}, "
    #       f"Tempo={tempo_bonus_score*perspective}, Imbalance={material_imbalance_score*perspective}, "
    #       f"Total={total_score*perspective}, Final={final_eval}", file=sys.stderr)


    return final_eval