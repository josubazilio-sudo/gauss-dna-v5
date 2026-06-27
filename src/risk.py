"""Gestão de Risco."""

from config import (
    MAX_OPERACOES_SIMULTANEAS, STOP_CONSECUTIVO_LIMITE,
    CAPITAL, RISCO_POR_OPERACAO,
    ALAVANCAGEM_MIN, ALAVANCAGEM_MAX,
)


class RiskManager:
    def __init__(self, capital=None):
        self.capital = capital or CAPITAL
        self.MAX_POSICOES = MAX_OPERACOES_SIMULTANEAS
        self.STOP_SEQUENCE_PAUSE = STOP_CONSECUTIVO_LIMITE
        self.positions = {}
        self.stop_streak = 0
        self.paused = False

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
