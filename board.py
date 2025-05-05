# -*- coding: utf-8 -*-
import sys
import copy
import time # Necessario per il timer interno? Forse no se spostato in search
import random # Necessario per fallback in search? Forse no
import os # Per Polyglot path

# Importa i moduli creati
import constants
import move as m # Alias per evitare conflitti
import pst
import evaluation # Per chiamare evaluate_board (anche se ora è in search?) -> Manteniamo evaluate qui per ora
import search # Per chiamare le funzioni di ricerca -> Le chiamate saranno da UCI/main

# Import condizionale per Polyglot
try:
    import chess
    import chess.polyglot
    CHESS_POLYGLOT_AVAILABLE = True
except ImportError:
    CHESS_POLYGLOT_AVAILABLE = False
    chess = None # Definisci per evitare errori se non importato

class ChessEngine:
    """Classe principale per la gestione della scacchiera e dello stato."""

    def __init__(self, fen=constants.INITIAL_FEN):
        self.board = [['.' for _ in range(8)] for _ in range(8)]
        self.current_player = 'W'
        self.castling_rights = {'W': {'K': True, 'Q': True}, 'B': {'k': True, 'q': True}}
        self.en_passant_target = None
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self.history = [] # Lista di dizionari per unmake
        self.current_hash = 0

        # Strutture dati per ricerca (gestite qui ma usate da search.py)
        self.transposition_table = [None] * constants.TT_SIZE
        self.killer_moves = [[None, None] for _ in range(constants.MAX_SEARCH_PLY)]
        self.history_heuristic = [[[0] * 64 for _ in range(64)] for _ in range(2)] # [color][from][to]

        # Flag per libro Polyglot
        self.use_book = CHESS_POLYGLOT_AVAILABLE and constants.BOOK_PATH is not None
        self.play_book_move_on_go = None # Mossa libro memorizzata

        # Inizializza
        self.parse_fen(fen) # Questo calcolerà anche l'hash iniziale

    # --- Funzioni Ausiliarie Colore/Pezzo ---
    def get_piece_color(self, piece):
        if piece == '.': return None
        return 'W' if piece.isupper() else 'B'

    # --- Gestione Hash Zobrist ---
    def calculate_zobrist_hash(self):
        """Calcola l'hash Zobrist completo per la posizione corrente."""
        h = 0
        # Pezzi
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.':
                    piece_index = constants.PIECE_TO_ZOBRIST_INDEX[piece]
                    h ^= constants.ZOBRIST_PIECES[r][c][piece_index]
        # Turno
        if self.current_player == 'B':
            h ^= constants.ZOBRIST_SIDE
        # Arrocco
        castling_index = 0
        if self.castling_rights['W']['K']: castling_index |= 1
        if self.castling_rights['W']['Q']: castling_index |= 2
        if self.castling_rights['B']['k']: castling_index |= 4
        if self.castling_rights['B']['q']: castling_index |= 8
        h ^= constants.ZOBRIST_CASTLING[castling_index]
        # En Passant
        if self.en_passant_target is not None:
            ep_col = self.en_passant_target[1]
            h ^= constants.ZOBRIST_EP_FILE[ep_col]
        return h

    def _update_hash_piece(self, current_hash, piece, r, c):
        """Aggiorna hash per aggiunta/rimozione pezzo."""
        if piece != '.':
             piece_index = constants.PIECE_TO_ZOBRIST_INDEX[piece]
             return current_hash ^ constants.ZOBRIST_PIECES[r][c][piece_index]
        return current_hash

    def _update_hash_castling(self, current_hash, old_rights_tuple, new_rights_tuple):
        """Aggiorna hash per cambio diritti arrocco."""
        old_index = 0
        if old_rights_tuple[0]: old_index |= 1 # WK
        if old_rights_tuple[1]: old_index |= 2 # WQ
        if old_rights_tuple[2]: old_index |= 4 # BK
        if old_rights_tuple[3]: old_index |= 8 # BQ
        new_index = 0
        if new_rights_tuple[0]: new_index |= 1 # WK
        if new_rights_tuple[1]: new_index |= 2 # WQ
        if new_rights_tuple[2]: new_index |= 4 # BK
        if new_rights_tuple[3]: new_index |= 8 # BQ
        return current_hash ^ constants.ZOBRIST_CASTLING[old_index] ^ constants.ZOBRIST_CASTLING[new_index]

    def _update_hash_ep(self, current_hash, old_ep_target, new_ep_target):
        """Aggiorna hash per cambio target en passant."""
        if old_ep_target is not None:
            current_hash ^= constants.ZOBRIST_EP_FILE[old_ep_target[1]]
        if new_ep_target is not None:
            current_hash ^= constants.ZOBRIST_EP_FILE[new_ep_target[1]]
        return current_hash

    def _update_hash_side(self, current_hash):
        """Aggiorna hash per cambio turno."""
        return current_hash ^ constants.ZOBRIST_SIDE

    # --- Parsing FEN e UCI Move ---
    def parse_fen(self, fen_string):
        """Imposta la scacchiera da una stringa FEN."""
        try:
            parts = fen_string.split()
            self.board = [['.' for _ in range(8)] for _ in range(8)]
            row, col = 0, 0
            piece_placement = parts[0]
            for char in piece_placement:
                if char == '/': row += 1; col = 0
                elif char.isdigit(): col += int(char)
                else: self.board[row][col] = char; col += 1

            self.current_player = parts[1].upper()
            castling = parts[2]
            self.castling_rights = {
                'W': {'K': 'K' in castling, 'Q': 'Q' in castling},
                'B': {'k': 'k' in castling, 'q': 'q' in castling}
            }
            ep_square = parts[3]
            if ep_square != '-':
                ep_col = ord(ep_square[0]) - ord('a')
                ep_row = 8 - int(ep_square[1])
                # Validazione EP target (opzionale ma robusto)
                # Un target EP è valido solo se è sulla 3a/6a traversa e
                # il pedone avversario è sulla 4a/5a.
                # Per semplicità, qui accettiamo la FEN com'è.
                self.en_passant_target = (ep_row, ep_col)
            else:
                self.en_passant_target = None

            self.halfmove_clock = int(parts[4])
            self.fullmove_number = int(parts[5])
            self.history = [] # Resetta history quando imposti nuova posizione
            self.current_hash = self.calculate_zobrist_hash() # Calcola hash iniziale
            # Resetta anche TT e altre strutture di ricerca? Dipende dal comando UCI (ucinewgame vs position)
            # Lo gestiamo nel loop UCI. Qui parse_fen imposta solo lo stato.

        except Exception as e:
            print(f"Error parsing FEN '{fen_string}': {e}", file=sys.stderr)
            # Potresti voler resettare a INITIAL_FEN o sollevare l'errore
            self.parse_fen(constants.INITIAL_FEN) # Fallback a posizione iniziale


    def parse_move(self, move_str):
        """Converte una stringa UCI (es. 'e2e4') in un oggetto Move."""
        try:
            if len(move_str) < 4: return None
            start_col = ord(move_str[0]) - ord('a')
            start_row = 8 - int(move_str[1])
            end_col = ord(move_str[2]) - ord('a')
            end_row = 8 - int(move_str[3])
            promotion_piece = move_str[4].lower() if len(move_str) == 5 else None

            if not (0 <= start_row < 8 and 0 <= start_col < 8 and 0 <= end_row < 8 and 0 <= end_col < 8):
                return None # Coordinate fuori scacchiera

            # Verifica se è arrocco
            piece = self.board[start_row][start_col]
            is_castle = False
            if piece.lower() == 'k' and abs(start_col - end_col) == 2:
                is_castle = True

            return m.Move(start_row, start_col, end_row, end_col, promotion_piece, is_castle)
        except (ValueError, IndexError):
            return None

    def get_fen(self):
        """Genera la stringa FEN per la posizione corrente."""
        fen = ""; empty_count = 0
        for r in range(8):
            empty_count = 0
            for c in range(8):
                piece = self.board[r][c]
                if piece == '.': empty_count += 1
                else:
                    if empty_count > 0: fen += str(empty_count); empty_count = 0
                    fen += piece
            if empty_count > 0: fen += str(empty_count)
            if r < 7: fen += '/'

        fen += f" {self.current_player.lower()}" # Turno

        castling_str = "" # Arrocco
        if self.castling_rights['W']['K']: castling_str += 'K'
        if self.castling_rights['W']['Q']: castling_str += 'Q'
        if self.castling_rights['B']['k']: castling_str += 'k'
        if self.castling_rights['B']['q']: castling_str += 'q'
        fen += f" {castling_str if castling_str else '-'}"

        # En Passant
        if self.en_passant_target:
            ep_r, ep_c = self.en_passant_target
            fen += f" {chr(ord('a') + ep_c)}{8 - ep_r}"
        else: fen += " -"

        # Contatori
        fen += f" {self.halfmove_clock} {self.fullmove_number}"
        return fen

    # --- Generazione Mosse ---
    def _get_pawn_moves(self, r, c, color):
        """Genera mosse pseudo-legali per un pedone."""
        moves = []
        direction = -1 if color == 'W' else 1
        start_rank = 6 if color == 'W' else 1
        promotion_rank = 0 if color == 'W' else 7

        # Movimento avanti di uno
        target_r, target_c = r + direction, c
        if 0 <= target_r < 8 and self.board[target_r][target_c] == '.':
            if target_r == promotion_rank: # Promozione
                for promo in ['q', 'r', 'b', 'n']:
                    moves.append(m.Move(r, c, target_r, target_c, promo))
            else:
                moves.append(m.Move(r, c, target_r, target_c))

            # Doppio passo iniziale (solo se il passo singolo era possibile)
            if r == start_rank:
                double_target_r = r + 2 * direction
                # Non serve check 0 <= double_target_r < 8 perché promotion_rank lo impedisce
                if self.board[double_target_r][c] == '.':
                    moves.append(m.Move(r, c, double_target_r, c))

        # Catture diagonali
        for dc in [-1, 1]:
            target_r, target_c = r + direction, c + dc
            if 0 <= target_r < 8 and 0 <= target_c < 8:
                target_piece = self.board[target_r][target_c]
                target_color = self.get_piece_color(target_piece)

                # Cattura normale
                if target_color is not None and target_color != color:
                    if target_r == promotion_rank: # Promozione con cattura
                        for promo in ['q', 'r', 'b', 'n']:
                            moves.append(m.Move(r, c, target_r, target_c, promo))
                    else:
                        moves.append(m.Move(r, c, target_r, target_c))
                # Cattura en passant
                elif (target_r, target_c) == self.en_passant_target:
                    # Verifica aggiuntiva (opzionale): pedone sulla giusta traversa per EP?
                    # (Il pedone attaccante deve essere sulla 5a traversa per il bianco, 4a per il nero)
                    correct_ep_rank = 3 if color == 'W' else 4
                    if r == correct_ep_rank:
                        moves.append(m.Move(r, c, target_r, target_c)) # EP flag non serve qui, è implicito
        return moves

    def _get_knight_moves(self, r, c):
        """Genera mosse pseudo-legali per un cavallo."""
        moves = []
        knight_moves = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
        current_color = self.get_piece_color(self.board[r][c]) # Determina colore una volta
        for dr, dc in knight_moves:
            target_r, target_c = r + dr, c + dc
            if 0 <= target_r < 8 and 0 <= target_c < 8:
                target_piece = self.board[target_r][target_c]
                target_color = self.get_piece_color(target_piece)
                if target_color != current_color: # Cattura o casa vuota
                    moves.append(m.Move(r, c, target_r, target_c))
        return moves

    def _get_sliding_moves(self, r, c, directions):
        """Genera mosse pseudo-legali per pezzi scorrevoli (B, R, Q)."""
        moves = []
        current_color = self.get_piece_color(self.board[r][c])
        for dr, dc in directions:
            for i in range(1, 8):
                target_r, target_c = r + i * dr, c + i * dc
                if not (0 <= target_r < 8 and 0 <= target_c < 8): break # Fuori scacchiera

                target_piece = self.board[target_r][target_c]
                if target_piece == '.': # Casa vuota
                    moves.append(m.Move(r, c, target_r, target_c))
                else: # Casa occupata
                    target_color = self.get_piece_color(target_piece)
                    if target_color != current_color: # Cattura
                        moves.append(m.Move(r, c, target_r, target_c))
                    break # Blocca sliding (amico o nemico)
        return moves

    def _get_king_moves(self, r, c, color):
        """Genera mosse pseudo-legali per il Re (incluso arrocco)."""
        moves = []
        king_moves = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        # Mosse normali
        for dr, dc in king_moves:
            target_r, target_c = r + dr, c + dc
            if 0 <= target_r < 8 and 0 <= target_c < 8:
                target_piece = self.board[target_r][target_c]
                target_color = self.get_piece_color(target_piece)
                if target_color != color:
                    moves.append(m.Move(r, c, target_r, target_c))

        # Arrocco (condizioni base)
        if not self.is_in_check(color): # Non si può arroccare sotto scacco
            opponent_color = 'B' if color == 'W' else 'W'
            if color == 'W':
                # Arrocco Corto (Kingside)
                if self.castling_rights['W']['K'] and \
                   self.board[7][5] == '.' and self.board[7][6] == '.' and \
                   not self.is_square_attacked(7, 5, opponent_color) and \
                   not self.is_square_attacked(7, 6, opponent_color):
                    # Nota: is_square_attacked(7, 4) è già coperto da not is_in_check
                    moves.append(m.Move(7, 4, 7, 6, is_castle=True))
                # Arrocco Lungo (Queenside)
                if self.castling_rights['W']['Q'] and \
                   self.board[7][1] == '.' and self.board[7][2] == '.' and self.board[7][3] == '.' and \
                   not self.is_square_attacked(7, 3, opponent_color) and \
                   not self.is_square_attacked(7, 2, opponent_color):
                    moves.append(m.Move(7, 4, 7, 2, is_castle=True))
            else: # color == 'B'
                 # Arrocco Corto (Kingside)
                if self.castling_rights['B']['k'] and \
                   self.board[0][5] == '.' and self.board[0][6] == '.' and \
                   not self.is_square_attacked(0, 5, opponent_color) and \
                   not self.is_square_attacked(0, 6, opponent_color):
                    moves.append(m.Move(0, 4, 0, 6, is_castle=True))
                # Arrocco Lungo (Queenside)
                if self.castling_rights['B']['q'] and \
                    self.board[0][1] == '.' and self.board[0][2] == '.' and self.board[0][3] == '.' and \
                    not self.is_square_attacked(0, 3, opponent_color) and \
                    not self.is_square_attacked(0, 2, opponent_color):
                    moves.append(m.Move(0, 4, 0, 2, is_castle=True))
        return moves

    def get_pseudo_legal_moves(self, player_color):
        """Genera tutte le mosse pseudo-legali per il giocatore."""
        moves = []
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                color = self.get_piece_color(piece)
                if color == player_color:
                    piece_type = piece.lower()
                    if piece_type == 'p': moves.extend(self._get_pawn_moves(r, c, color))
                    elif piece_type == 'n': moves.extend(self._get_knight_moves(r, c))
                    elif piece_type == 'b': moves.extend(self._get_sliding_moves(r, c, [(-1, -1), (-1, 1), (1, -1), (1, 1)]))
                    elif piece_type == 'r': moves.extend(self._get_sliding_moves(r, c, [(-1, 0), (1, 0), (0, -1), (0, 1)]))
                    elif piece_type == 'q': moves.extend(self._get_sliding_moves(r, c, [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]))
                    elif piece_type == 'k': moves.extend(self._get_king_moves(r, c, color))
        return moves

    def is_square_attacked(self, r, c, attacker_color):
        """Controlla se la casa (r, c) è attaccata da attacker_color."""
        # Attacchi Pedone
        pawn_direction = 1 if attacker_color == 'W' else -1
        expected_pawn = 'P' if attacker_color == 'W' else 'p'
        for dc in [-1, 1]:
            pr, pc = r + pawn_direction, c + dc # Pedone attaccante sarebbe QUI
            if 0 <= pr < 8 and 0 <= pc < 8 and self.board[pr][pc] == expected_pawn:
                return True

        # Attacchi Cavallo
        knight_moves = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
        expected_knight = 'N' if attacker_color == 'W' else 'n'
        for dr, dc in knight_moves:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8 and self.board[nr][nc] == expected_knight: return True

        # Attacchi Scorrevoli (B, R, Q)
        piece_checks = [
            ('b', [(-1, -1), (-1, 1), (1, -1), (1, 1)]),
            ('r', [(-1, 0), (1, 0), (0, -1), (0, 1)]),
        ]
        expected_queen = 'Q' if attacker_color == 'W' else 'q'
        for p_type, directions in piece_checks:
            expected_piece = p_type.upper() if attacker_color == 'W' else p_type
            for dr, dc in directions:
                for i in range(1, 8):
                    sr, sc = r + i * dr, c + i * dc
                    if not (0 <= sr < 8 and 0 <= sc < 8): break
                    piece = self.board[sr][sc]
                    if piece != '.':
                        if piece == expected_piece or piece == expected_queen: return True
                        break # Pezzo bloccante

        # Attacchi Re
        king_moves = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        expected_king = 'K' if attacker_color == 'W' else 'k'
        for dr, dc in king_moves:
            kr, kc = r + dr, c + dc
            if 0 <= kr < 8 and 0 <= kc < 8 and self.board[kr][kc] == expected_king: return True

        return False

    def is_in_check(self, player_color):
        """Controlla se player_color è sotto scacco."""
        king_char = 'K' if player_color == 'W' else 'k'
        king_pos = None
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == king_char: king_pos = (r, c); break
            if king_pos: break
        if not king_pos: return False # Dovrebbe essere impossibile

        opponent_color = 'B' if player_color == 'W' else 'W'
        return self.is_square_attacked(king_pos[0], king_pos[1], opponent_color)

    def get_legal_moves(self, player_color):
        """Genera mosse legali filtrando le pseudo-legali."""
        pseudo_legal_moves = self.get_pseudo_legal_moves(player_color)
        legal_moves = []
        # Salva stato PRIMA del loop
        original_state = self.get_state_snapshot()

        for move_obj in pseudo_legal_moves:
            self.make_move(move_obj)
            # Controlla se il *proprio* re è sotto scacco dopo la mossa
            if not self.is_in_check(player_color):
                legal_moves.append(move_obj)
            # Ripristina sempre allo stato PRIMA della mossa specifica
            self.restore_state_snapshot(original_state)

        return legal_moves

    # --- Make/Unmake Move ---
    def get_state_snapshot(self):
        """Salva lo stato per unmake_move."""
        # Usa una tupla per i diritti di arrocco per renderli immutabili/hashable
        castling_tuple = (
            self.castling_rights['W']['K'], self.castling_rights['W']['Q'],
            self.castling_rights['B']['k'], self.castling_rights['B']['q']
        )
        # La board è una lista di liste, una copia superficiale va bene per il restore
        # perché sovrascriviamo le singole celle. Se modificassimo liste interne, servirebbe deepcopy.
        return {
            'board': [row[:] for row in self.board],
            'current_player': self.current_player,
            'castling_tuple': castling_tuple,
            'en_passant_target': self.en_passant_target, # Tupla è immutabile
            'halfmove_clock': self.halfmove_clock,
            'fullmove_number': self.fullmove_number,
            'current_hash': self.current_hash,
            'history_len': len(self.history) # Per troncamento history in restore
        }

    def restore_state_snapshot(self, snapshot):
        """Ripristina lo stato da uno snapshot."""
        self.board = [row[:] for row in snapshot['board']] # Ripristina board
        self.current_player = snapshot['current_player']
        # Ripristina diritti dalla tupla
        ct = snapshot['castling_tuple']
        self.castling_rights = {'W': {'K': ct[0], 'Q': ct[1]}, 'B': {'k': ct[2], 'q': ct[3]}}
        self.en_passant_target = snapshot['en_passant_target']
        self.halfmove_clock = snapshot['halfmove_clock']
        self.fullmove_number = snapshot['fullmove_number']
        self.current_hash = snapshot['current_hash']
        # Tronca history se necessario (make_move aggiunge, restore non deve rimuovere se non necessario)
        if len(self.history) > snapshot['history_len']:
             self.history = self.history[:snapshot['history_len']]

    def make_move(self, move_obj):
        """Esegue una mossa sulla scacchiera e aggiorna lo stato."""
        start_r, start_c = move_obj.start_row, move_obj.start_col
        end_r, end_c = move_obj.end_row, move_obj.end_col
        piece = self.board[start_r][start_c]
        piece_color = self.get_piece_color(piece)
        piece_type = piece.lower()
        captured_piece = self.board[end_r][end_c]
        is_capture = captured_piece != '.'

        # --- Salva info per unmake ---
        original_hash = self.current_hash
        current_castling_tuple = (self.castling_rights['W']['K'], self.castling_rights['W']['Q'],
                                   self.castling_rights['B']['k'], self.castling_rights['B']['q'])
        current_ep_target = self.en_passant_target
        current_halfmove = self.halfmove_clock
        captured_piece_ep = '.' # Default
        rook_move_castle_info = None # Per unmake arrocco

        # --- Aggiornamento Hash Incrementale ---
        new_hash = original_hash
        # 1. Rimuovi pezzo mosso da casa iniziale
        new_hash = self._update_hash_piece(new_hash, piece, start_r, start_c)
        # 2. Rimuovi pezzo catturato (se esiste) da casa finale
        if is_capture:
            new_hash = self._update_hash_piece(new_hash, captured_piece, end_r, end_c)

        # --- Modifiche Scacchiera Base ---
        # Pezzo mosso arriva a destinazione
        final_piece = piece
        if move_obj.promotion_piece:
            final_piece = move_obj.promotion_piece.upper() if piece_color == 'W' else move_obj.promotion_piece.lower()
        self.board[end_r][end_c] = final_piece
        self.board[start_r][start_c] = '.'

        # 3. Aggiungi pezzo (eventualmente promosso) a casa finale
        new_hash = self._update_hash_piece(new_hash, final_piece, end_r, end_c)

        # --- Gestione En Passant ---
        new_ep_target = None
        if piece_type == 'p':
            # *** CORREZIONE: Definisci direction qui ***
            direction = -1 if piece_color == 'W' else 1
            # ******************************************

            # Imposta nuovo target EP se doppio passo
            if abs(start_r - end_r) == 2:
                new_ep_target = (start_r + direction, start_c) # Ora direction è definito
            # Se la mossa è una cattura EP
            elif (end_r, end_c) == current_ep_target:
                captured_ep_r = start_r # Riga del pedone attaccante
                captured_ep_c = end_c   # Colonna del pedone catturato
                captured_piece_ep = self.board[captured_ep_r][captured_ep_c] # Dovrebbe essere 'p' o 'P'
                # 4. Rimuovi pedone catturato EP dall'hash
                new_hash = self._update_hash_piece(new_hash, captured_piece_ep, captured_ep_r, captured_ep_c)
                # Rimuovi pedone catturato EP dalla scacchiera
                self.board[captured_ep_r][captured_ep_c] = '.'
                is_capture = True # Conta come cattura per halfmove clock

        # 5. Aggiorna hash per cambio EP target
        new_hash = self._update_hash_ep(new_hash, current_ep_target, new_ep_target)
        self.en_passant_target = new_ep_target # Aggiorna stato

        # --- Gestione Arrocco ---
        if move_obj.is_castle:
            rook_start_c, rook_end_c = (7, 5) if end_c == 6 else (0, 3) # Corto vs Lungo
            rook_r = start_r # Stessa riga del Re
            rook = self.board[rook_r][rook_start_c]
            # Salva info per unmake
            rook_move_castle_info = (rook_r, rook_start_c, rook_r, rook_end_c, rook) # (r1,c1, r2,c2, piece)

            # Muovi torre sulla scacchiera
            self.board[rook_r][rook_end_c] = rook
            self.board[rook_r][rook_start_c] = '.'
            # 6. Aggiorna hash per movimento torre
            new_hash = self._update_hash_piece(new_hash, rook, rook_r, rook_start_c) # Rimuovi da start
            new_hash = self._update_hash_piece(new_hash, rook, rook_r, rook_end_c)   # Aggiungi a end

        # --- Aggiorna Contatori ---
        if piece_type == 'p' or is_capture: # Cattura include EP qui
             self.halfmove_clock = 0
        else:
             self.halfmove_clock += 1
        # NOTA: l'incremento di fullmove_number dovrebbe avvenire DOPO che il NERO ha mosso.
        # Lo spostiamo dopo il cambio giocatore.

        # --- Aggiorna Diritti Arrocco ---
        # Copia superficiale è ok, modifichiamo i booleani interni
        new_castling_rights_dict = {
             'W': self.castling_rights['W'].copy(),
             'B': self.castling_rights['B'].copy()
        }
        wk, wq = new_castling_rights_dict['W']['K'], new_castling_rights_dict['W']['Q']
        bk, bq = new_castling_rights_dict['B']['k'], new_castling_rights_dict['B']['q']

        # Se il Re si muove
        if piece_type == 'k':
            if piece_color == 'W': wk = wq = False
            else: bk = bq = False
        # Se la Torre si muove dalla casa iniziale
        if start_r == 7 and start_c == 0: wq = False # A1
        if start_r == 7 and start_c == 7: wk = False # H1
        if start_r == 0 and start_c == 0: bq = False # A8
        if start_r == 0 and start_c == 7: bk = False # H8
        # Se la Torre viene catturata sulla casa finale
        if end_r == 7 and end_c == 0: wq = False # Torre A1 catturata
        if end_r == 7 and end_c == 7: wk = False # Torre H1 catturata
        if end_r == 0 and end_c == 0: bq = False # Torre A8 catturata
        if end_r == 0 and end_c == 7: bk = False # Torre H8 catturata

        # Crea nuova tupla per hash e aggiorna dizionario stato
        new_castling_tuple = (wk, wq, bk, bq)
        new_castling_rights_dict['W']['K'], new_castling_rights_dict['W']['Q'] = wk, wq
        new_castling_rights_dict['B']['k'], new_castling_rights_dict['B']['q'] = bk, bq

        # 7. Aggiorna hash per cambio diritti arrocco (solo se sono cambiati)
        if new_castling_tuple != current_castling_tuple:
             new_hash = self._update_hash_castling(new_hash, current_castling_tuple, new_castling_tuple)
        self.castling_rights = new_castling_rights_dict # Aggiorna stato arrocco

        # --- Cambia Giocatore ---
        original_player = self.current_player # Salva giocatore prima del cambio
        self.current_player = 'B' if piece_color == 'W' else 'W'
        # 8. Aggiorna hash per cambio turno
        new_hash = self._update_hash_side(new_hash)

        # --- Aggiorna Fullmove Number (ora che sappiamo chi ha mosso) ---
        if original_player == 'B': # Se era il turno del Nero a muovere
            self.fullmove_number += 1

        # --- Aggiorna Hash Finale e History ---
        self.current_hash = new_hash
        self.history.append({
            'move': move_obj, # Oggetto Move
            'captured_piece': captured_piece, # Carattere pezzo catturato (o '.')
            'captured_piece_ep': captured_piece_ep, # Carattere pezzo catturato EP (o '.')
            'castling_tuple_before': current_castling_tuple, # Diritti prima
            'en_passant_target_before': current_ep_target, # EP target prima
            'halfmove_clock_before': current_halfmove, # Clock prima
            'previous_hash': original_hash, # Hash prima della mossa
            'rook_move_castle_info': rook_move_castle_info # Info per annullare mossa torre
        })

    def unmake_move(self):
        """Annulla l'ultima mossa eseguita."""
        if not self.history: return
        last_move_info = self.history.pop()

        move_obj = last_move_info['move']
        start_r, start_c = move_obj.start_row, move_obj.start_col
        end_r, end_c = move_obj.end_row, move_obj.end_col

        # Pezzo mosso (considera promozione)
        moved_piece_type = self.board[end_r][end_c].lower() # Tipo pezzo che è arrivato
        original_piece_char = moved_piece_type.upper() if self.current_player == 'B' else moved_piece_type.lower() # Determina pezzo originale
        if moved_piece_type != 'p' and move_obj.promotion_piece is not None:
            original_piece_char = 'P' if self.current_player == 'B' else 'p' # Era un pedone prima della promo

        # Ripristina pezzo mosso e pezzo catturato
        self.board[start_r][start_c] = original_piece_char
        self.board[end_r][end_c] = last_move_info['captured_piece'] # Ripristina pezzo catturato (o '.')

        # Annulla cattura En Passant
        captured_piece_ep = last_move_info['captured_piece_ep']
        if captured_piece_ep != '.':
            ep_capture_r = start_r # Riga del pedone attaccante originale
            ep_capture_c = end_c   # Colonna della cattura
            self.board[ep_capture_r][ep_capture_c] = captured_piece_ep # Rimetti pedone catturato
            self.board[end_r][end_c] = '.' # La casa di arrivo EP era vuota

        # Annulla Arrocco (muovi torre indietro)
        rook_info = last_move_info['rook_move_castle_info']
        if rook_info:
            rook_r1, rook_c1, rook_r2, rook_c2, rook_piece = rook_info
            self.board[rook_r1][rook_c1] = rook_piece # Torre torna a casa iniziale
            self.board[rook_r2][rook_c2] = '.'        # Casa finale torre diventa vuota

        # Ripristina stato partita dal dizionario history
        ct = last_move_info['castling_tuple_before']
        self.castling_rights = {'W': {'K': ct[0], 'Q': ct[1]}, 'B': {'k': ct[2], 'q': ct[3]}}
        self.en_passant_target = last_move_info['en_passant_target_before']
        self.halfmove_clock = last_move_info['halfmove_clock_before']
        self.current_hash = last_move_info['previous_hash'] # Ripristina hash!

        # Cambia giocatore indietro
        self.current_player = 'W' if self.current_player == 'B' else 'B'
        # Aggiusta numero mossa se il nero ha appena annullato
        if self.current_player == 'B':
             self.fullmove_number -= 1
    
    def _perft_recursive(self, depth):
        """Funzione ricorsiva helper per Perft."""
        if depth == 0:
            return 1 # Siamo arrivati a una foglia

        nodes = 0
        legal_moves = self.get_legal_moves(self.current_player)

        for move_obj in legal_moves:
            # Nota: Stiamo usando la versione di get_legal_moves con make/unmake implicito
            # per il check di legalità. Questo è meno efficiente per Perft ma usa
            # il codice che già hai. Se Perft risulta troppo lento, potremmo
            # ottimizzare get_legal_moves come discusso in precedenza.

            # Salva lo stato PRIMA di make_move per il perft ricorsivo
            # (make/unmake sono già usati da get_legal_moves, ma qui li usiamo
            # per scendere nell'albero di Perft)
            # Usiamo make_move/unmake_move invece di get_state_snapshot/restore
            # perché sono le funzioni che vogliamo testare implicitamente.
            # L'hash viene aggiornato da make_move/unmake_move.

            # --- Esegui la mossa ---
            self.make_move(move_obj)

            # --- Chiamata ricorsiva ---
            nodes += self._perft_recursive(depth - 1)

            # --- Annulla la mossa ---
            self.unmake_move() # Ripristina lo stato precedente

        return nodes

    def perft(self, depth, divide=True):
        """
        Calcola il numero di nodi Perft per una data profondità.
        Se divide=True, mostra anche il conteggio per ogni mossa alla radice.
        """
        if depth < 0:
            return 0
        if depth == 0:
            return 1

        print(f"--- Starting Perft({depth}) ---")
        start_time = time.time()

        total_nodes = 0
        legal_moves = self.get_legal_moves(self.current_player)
        # Ordina le mosse per un output più consistente/leggibile
        sorted_moves = sorted(legal_moves, key=lambda m: m.to_uci_string())

        # Memorizza lo stato iniziale FEN per riferimento
        initial_fen = self.get_fen()
        print(f"Position: {initial_fen}")


        for move_obj in sorted_moves:
            self.make_move(move_obj)
            nodes_for_move = self._perft_recursive(depth - 1)
            self.unmake_move() # Ripristina stato per la prossima mossa radice

            if divide:
                print(f"{move_obj.to_uci_string()}: {nodes_for_move}")
            total_nodes += nodes_for_move

        end_time = time.time()
        elapsed_time = end_time - start_time
        nps = int(total_nodes / elapsed_time) if elapsed_time > 0 else 0

        print(f"\nTotal Nodes: {total_nodes}")
        print(f"Time: {elapsed_time:.3f} seconds")
        print(f"Nodes/Second: {nps}")
        print(f"--- Perft({depth}) Finished ---")

        # Assicurati che lo stato finale sia identico a quello iniziale
        final_fen = self.get_fen()
        if initial_fen != final_fen:
             print(f"ERROR: FEN mismatch after Perft! Initial: {initial_fen} Final: {final_fen}", file=sys.stderr)
        # Potresti aggiungere anche un check sull'hash
        # initial_hash = self.calculate_zobrist_hash() # Calcola all'inizio
        # final_hash = self.current_hash # Hash corrente alla fine
        # if initial_hash != final_hash: print("ERROR: Hash mismatch!")

        return total_nodes

    # --- Funzione per Polyglot ---
    def to_python_chess(self):
        """Converte lo stato interno in un oggetto chess.Board."""
        if not CHESS_POLYGLOT_AVAILABLE: return None
        try:
            board_pc = chess.Board(fen=None) # Crea board vuota
            board_pc.clear_board()
            # Imposta pezzi
            for r in range(8):
                for c in range(8):
                    piece_char = self.board[r][c]
                    if piece_char != '.':
                        piece_pc = chess.Piece.from_symbol(piece_char)
                        square_pc = chess.square(c, 7 - r) # Conversione coordinate
                        board_pc.set_piece_at(square_pc, piece_pc)
            # Imposta turno
            board_pc.turn = chess.WHITE if self.current_player == 'W' else chess.BLACK
            # Imposta diritti arrocco (usa FEN part)
            castling_fen_part = ""
            if self.castling_rights['W']['K']: castling_fen_part += 'K'
            if self.castling_rights['W']['Q']: castling_fen_part += 'Q'
            if self.castling_rights['B']['k']: castling_fen_part += 'k'
            if self.castling_rights['B']['q']: castling_fen_part += 'q'
            board_pc.set_castling_fen(castling_fen_part if castling_fen_part else "-")
            # Imposta En Passant
            if self.en_passant_target:
                ep_r, ep_c = self.en_passant_target
                board_pc.ep_square = chess.square(ep_c, 7 - ep_r)
            else:
                board_pc.ep_square = None
            # Imposta contatori
            board_pc.halfmove_clock = self.halfmove_clock
            board_pc.fullmove_number = self.fullmove_number

            # Validazione (opzionale ma utile per debug)
            # if not board_pc.is_valid():
            #     print(f"Warning: Generated python-chess board is invalid! FEN: {board_pc.fen()}", file=sys.stderr)

            return board_pc
        except Exception as e:
            print(f"Error in to_python_chess conversion: {e}", file=sys.stderr)
            return None

    # --- Metodi Wrapper per chiamare valutazione/ricerca ---
    # Questi potrebbero non essere necessari se UCI chiama direttamente search.py
    # Ma li teniamo per ora se vuoi un punto di accesso unificato tramite l'engine

    def evaluate(self):
         """Wrapper per chiamare la funzione di valutazione."""
         # Nota: evaluate_board in evaluation.py prende board e player
         return evaluation.evaluate_board(self.board, self.current_player)

    def find_best_move(self, max_depth=constants.MAX_SEARCH_PLY, move_time=None, wtime=None, btime=None, winc=0, binc=0, movestogo=None):
         """Wrapper per chiamare la funzione di ricerca principale."""
         # Passa l'istanza corrente dell'engine a search_move
         return search.search_move(self, max_depth, move_time, wtime, btime, winc, binc, movestogo)