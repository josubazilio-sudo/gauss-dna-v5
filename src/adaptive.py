"""
IA Adaptativa — Ajusta pesos dinâmicos por símbolo baseado em
estatísticas históricas de cada ativo.
"""

from config import (
    PESO_TENDENCIA, PESO_FLUXO, PESO_VOLUME, PESO_LIQUIDEZ,
    PESO_ESTRUTURA, PESO_MOMENTUM, PESO_VOLATILIDADE,
    PESO_MULTI_TIMEFRAME, PESO_CONFIANCA, PESO_ATIVO,
)


class AdaptiveWeights:
    def __init__(self):
        self._stats = {}

    def get_weights(self, symbol):
        """
        Retorna pesos ajustados para o símbolo.
        Se não há histórico, retorna os pesos padrão.
        """
        if symbol not in self._stats:
            return {
                "PESO_TENDENCIA": PESO_TENDENCIA,
                "PESO_FLUXO": PESO_FLUXO,
                "PESO_VOLUME": PESO_VOLUME,
                "PESO_LIQUIDEZ": PESO_LIQUIDEZ,
                "PESO_ESTRUTURA": PESO_ESTRUTURA,
                "PESO_MOMENTUM": PESO_MOMENTUM,
                "PESO_VOLATILIDADE": PESO_VOLATILIDADE,
                "PESO_MULTI_TIMEFRAME": PESO_MULTI_TIMEFRAME,
                "PESO_CONFIANCA": PESO_CONFIANCA,
                "PESO_ATIVO": PESO_ATIVO,
            }

        stats = self._stats[symbol]
        weights = {}

        if stats.get("winrate", 0) > 0.5:
            weights["PESO_TENDENCIA"] = PESO_TENDENCIA + 5
            weights["PESO_FLUXO"] = PESO_FLUXO + 5
        else:
            weights["PESO_VOLUME"] = PESO_VOLUME + 5
            weights["PESO_LIQUIDEZ"] = PESO_LIQUIDEZ + 5

        weights["PESO_MOMENTUM"] = PESO_MOMENTUM
        weights["PESO_ESTRUTURA"] = PESO_ESTRUTURA
        weights["PESO_VOLATILIDADE"] = PESO_VOLATILIDADE
        weights["PESO_MULTI_TIMEFRAME"] = PESO_MULTI_TIMEFRAME
        weights["PESO_CONFIANCA"] = PESO_CONFIANCA
        weights["PESO_ATIVO"] = PESO_ATIVO

        return weights

    def get_confianca(self, symbol, score):
        stats = self._stats.get(symbol, {})
        winrate = stats.get("winrate", 0.5)
        confianca_base = score
        if winrate > 0.6:
            confianca_base = min(confianca_base + 10, 100)
        elif winrate < 0.3:
            confianca_base = max(confianca_base - 15, 0)
        return int(confianca_base)

    def update(self, symbol, result):
        if symbol not in self._stats:
            self._stats[symbol] = {
                "operacoes": 0, "vitorias": 0, "derrotas": 0,
                "winrate": 0.5, "profit_factor": 0.0,
            }
        s = self._stats[symbol]
        s["operacoes"] += 1
        if result == "win":
            s["vitorias"] += 1
        elif result == "loss":
            s["derrotas"] += 1
        if s["operacoes"] > 0:
            s["winrate"] = s["vitorias"] / s["operacoes"]
