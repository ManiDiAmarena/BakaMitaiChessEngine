# -*- coding: utf-8 -*-
import random
import os

# --- Costanti Generali ---
INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
PIECE_VALUES = {'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 20000}
MATE_SCORE = 1000000 # Punteggio per lo scacco matto
DRAW_SCORE = 0      # Punteggio per patta (usato globalmente)
STALEMATE_SCORE = 0 # Punteggio per stallo (usato globalmente)
MAX_SEARCH_PLY = 64 # Limite massimo di profondità per evitare errori/loop

# --- Costanti Transposition Table (TT) ---
TT_SIZE = 1048576 # Dimensione della Transposition Table (2^20, circa 1M entry)
TT_BOUND_EXACT = 0
TT_BOUND_LOWER = 1
TT_BOUND_UPPER = 2

# --- Costanti Ricerca ---
NMP_MIN_DEPTH = 3
NMP_REDUCTION = 2
CHECK_EXTENSION = 1
LMR_MIN_DEPTH = 3
LMR_MIN_MOVE_INDEX = 4
LMR_REDUCTION = 1
FUTILITY_MARGIN_DEPTH_1 = 200 # Margine per Futility Pruning a depth 1
MIN_MATERIAL_FOR_NMP = PIECE_VALUES['n'] + PIECE_VALUES['p'] # Valore minimo per NMP

# --- Costanti Valutazione ---
BISHOP_PAIR_BONUS = (60, 60) # Era (60, 60)
DOUBLED_PAWN_PENALTY = (10, 10) # Era (10, 10)
ISOLATED_PAWN_PENALTY = (15, 15) # Era (15, 15)
ROOK_OPEN_FILE_BONUS = (20, 15) # Meno decisivo in EG puri?
PASSED_PAWN_BONUS_BASE = (20, 30) # Era (20, 30)
PASSED_PAWN_RANK_BONUS = [(0, 0), (5, 5), (15, 15), (30, 30), (50, 50), (75, 75), (100, 100), (0, 0)] #Era (0, 0), (5, 5), (15, 15), (30, 30), (50, 50), (75, 75), (100, 100), (0, 0)
BACKWARD_PAWN_PENALTY = (8, 8) # Era (8, 8)
ROOK_OPEN_FILE_BONUS = (20, 20) # Era (20, 20)
ROOK_SEMI_OPEN_FILE_BONUS = (10, 8) # Era (10, 10)
ROOK_ON_SEVENTH_BONUS = (25, 30) # Era (25, 25)
KING_SHIELD_BONUS = (8, 4) # Era (8, 4)
KING_OPEN_FILE_PENALTY = (12, 12) # Era (12, 12)
KING_SEMI_OPEN_FILE_PENALTY = (6, 6) # Era (6, 6)
GAME_PHASE_MAX = 24 # Somma dei valori di fase iniziali (escl. pedoni/re)
PIECE_PHASE_VALUES = {'q': 4, 'r': 2, 'b': 1, 'n': 1, 'p': 0, 'k': 0} # Valori per calcolo fase

# --- Costanti Ricerca: Singular Extensions ---
SINGULAR_MIN_DEPTH = 6       # Profondità minima per considerare estensioni singolari
SINGULAR_MARGIN = 25         # Margine (cp): best_score deve superare verification_score di questo valore
SINGULAR_EXTENSION_AMOUNT = 1 # Di quanto estendere la profondità (solitamente 1)
# Margine sopra alpha per attivare il check (evita check se score è vicino ad alpha)
SINGULAR_ALPHA_MARGIN = 50

# --- Valutazione: Sicurezza Re nel Finale ---
ENDGAME_KING_ROOK_ATTACK_OPEN = (0, 0) # Era (0, 0) -> Annulla bonus EG
ENDGAME_KING_ROOK_ATTACK_SEMI = (0, 0) # Era (0, 0)
ENDGAME_KING_QUEEN_ATTACK_OPEN = (0, 0) # Era (0, 0)
ENDGAME_KING_QUEEN_ATTACK_SEMI = (0, 0) # Era (0, 0)

# Valori semplificati per stima fase gioco
PIECE_VALUES_SIMPLE_FOR_PHASE = {'q': 9, 'r': 5, 'b': 3, 'n': 3, 'p': 1}
ENDGAME_MATERIAL_THRESHOLD = 20 # Soglia materiale per definire ENDGAME
TEMPO_BONUS = (10, 10) # Era (10, 10)
PAWN_RAM_PENALTY = (6, 6) # Era (6, 6)
KNIGHT_PAIR_PENALTY = (15, 15) # Era (15, 15)
ROOK_PAIR_BONUS = (15, 15) # Era (15, 15)
IID_REDUCTION = 2  # Di quanto ridurre la profondità per la ricerca IID
IID_MIN_DEPTH = 4  # Profondità minima per eseguire IID

# --- Costanti Mobilità ---
MOBILITY_KNIGHT_MULTIPLIER = 2
MOBILITY_BISHOP_MULTIPLIER = 1
MOBILITY_ROOK_MULTIPLIER   = 1
MOBILITY_QUEEN_MULTIPLIER  = 1
MOBILITY_SQUARE_BONUS = [ # Bonus per casa raggiungibile
    0, 1, 1, 1, 1, 1, 1, 0,
    1, 2, 2, 2, 2, 2, 2, 1,
    1, 2, 3, 3, 3, 3, 2, 1,
    1, 2, 3, 4, 4, 3, 2, 1,
    1, 2, 3, 4, 4, 3, 2, 1,
    1, 2, 3, 3, 3, 3, 2, 1,
    1, 2, 2, 2, 2, 2, 2, 1,
    0, 1, 1, 1, 1, 1, 1, 0
]

# --- Costanti Ordinamento Mosse ---
MVV_LVA_CAPTURE_BONUS = 1000000 # Bonus base catture
PROMOTION_BONUS_OFFSET = 50000 # Bonus aggiuntivo per promozioni sopra le catture
KILLER_MOVE_PRIMARY_BONUS = 90000
KILLER_MOVE_SECONDARY_BONUS = 80000
MAX_HISTORY_SCORE_BONUS = 70000 # Limite massimo per bonus da history heuristic

# --- Tabelle Zobrist ---
ZOBRIST_PIECES = [[[random.getrandbits(64) for _ in range(12)] for _ in range(8)] for _ in range(8)]
ZOBRIST_SIDE = random.getrandbits(64)
ZOBRIST_CASTLING = [random.getrandbits(64) for _ in range(16)]
ZOBRIST_EP_FILE = [random.getrandbits(64) for _ in range(8)]
PIECE_TO_ZOBRIST_INDEX = {'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5, 'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11}

# --- Costanti Libro Aperture (Polyglot) ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # Potrebbe servire aggiustarlo in base a dove esegui main.py
BOOK_FILENAME = "book_.bin"
BOOK_PATH = os.path.join(SCRIPT_DIR, BOOK_FILENAME)
# CHESS_POLYGLOT_AVAILABLE verrà definito in base all'import in altri moduli