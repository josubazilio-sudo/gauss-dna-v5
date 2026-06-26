"""Gestão de Risco."""

from config import MAX_OPERACOES_SIMULTANEAS, STOP_CONSECUTIVO_LIMITE


class RiskManager:
    def __init__(self, capital=1000):
        self.capital = capital
        self.MAX_POSICOES = MAX_OPERACOES_SIMULTANEAS
        self.STOP_SEQUENCE_PAUSE = STOP_CONSECUTIVO_LIMITE
        self.positions = {}
        self.stop_streak = 0
        self.paused = False

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
