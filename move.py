# -*- coding: utf-8 -*-

class Move:
    """Rappresenta una mossa di scacchi."""
    def __init__(self, start_row, start_col, end_row, end_col, promotion_piece=None, is_castle=False):
        self.start_row = start_row
        self.start_col = start_col
        self.end_row = end_row
        self.end_col = end_col
        self.promotion_piece = promotion_piece
        self.is_castle = is_castle

    def to_uci_string(self):
        start = f"{chr(ord('a') + self.start_col)}{8 - self.start_row}"
        end = f"{chr(ord('a') + self.end_col)}{8 - self.end_row}"
        promo = self.promotion_piece if self.promotion_piece else ""
        return start + end + promo

    def __eq__(self, other):
        if not isinstance(other, Move):
            return NotImplemented
        return (self.start_row == other.start_row and
                self.start_col == other.start_col and
                self.end_row == other.end_row and
                self.end_col == other.end_col and
                self.promotion_piece == other.promotion_piece and
                self.is_castle == other.is_castle)

    def __hash__(self):
        return hash((self.start_row, self.start_col, self.end_row, self.end_col,
                    self.promotion_piece, self.is_castle))

    def __str__(self):
        return self.to_uci_string()

    def __repr__(self):
        return f"Move({self.start_row},{self.start_col} -> {self.end_row},{self.end_col}, promo={self.promotion_piece}, castle={self.is_castle})"