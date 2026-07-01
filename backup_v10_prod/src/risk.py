"""Gestão de Risco."""

from config import (
    MAX_OPERACOES_SIMULTANEAS, STOP_CONSECUTIVO_LIMITE,
    CAPITAL, RISCO_POR_OPERACAO,
    ALAVANCAGEM_MIN, ALAVANCAGEM_MAX,
    SL_ATR_MULT, TP1_ATR_MULT, TP2_ATR_MULT, TP1_PERCENT,
)


class RiskManager:
    def __init__(self, capital=None):
        self.capital = capital or CAPITAL
        self.MAX_POSICOES = MAX_OPERACOES_SIMULTANEAS
        self.STOP_SEQUENCE_PAUSE = STOP_CONSECUTIVO_LIMITE
        self.positions = {}
        self.stop_streak = 0
        self.paused = False

    def calc_atr_levels(self, atr, preco, direction="long"):
        sl_dist = atr * SL_ATR_MULT
        tp1 = atr * TP1_ATR_MULT
        tp2 = atr * TP2_ATR_MULT
        if direction == "long":
            sl = preco - sl_dist
            tp1_preco = preco + tp1
            tp2_preco = preco + tp2
        else:
            sl = preco + sl_dist
            tp1_preco = preco - tp1
            tp2_preco = preco - tp2
        stop_pct = sl_dist / preco
        return {
            "stop_loss": round(sl, 8),
            "tp1": round(tp1_preco, 8),
            "tp2": round(tp2_preco, 8),
            "stop_pct": round(stop_pct * 100, 2),
            "tp1_pct": round(tp1 / preco * 100, 2),
            "tp2_pct": round(tp2 / preco * 100, 2),
            "tp1_quote_size": TP1_PERCENT,
        }

    def calc_position_size(self, stop_pct=0.01, leverage=5):
        risco_capital = self.capital * RISCO_POR_OPERACAO
        alav = max(ALAVANCAGEM_MIN, min(leverage, ALAVANCAGEM_MAX))
        distancia_stop = stop_pct / alav
        tamanho = risco_capital / distancia_stop if distancia_stop > 0 else 0
        return round(tamanho, 4), alav

    def can_enter(self, symbol):
        if self.paused:
            return False
        if len(self.positions) >= self.MAX_POSICOES:
            return False
        if symbol in self.positions:
            return False
        return True

    def enter(self, symbol, direction="long", classification=None):
        self.positions[symbol] = {
            "direction": direction,
            "classification": classification,
        }

    def exit(self, symbol, result):
        if result == "stop":
            self.stop_streak += 1
            if self.stop_streak >= self.STOP_SEQUENCE_PAUSE:
                self.paused = True
        elif result == "tp":
            self.stop_streak = 0
        self.positions.pop(symbol, None)

    async def refresh(self):
        if self.paused:
            self.stop_streak = 0
            self.paused = False
