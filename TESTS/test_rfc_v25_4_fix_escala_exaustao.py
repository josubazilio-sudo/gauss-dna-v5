"""RFC V25.4 — Correcao do bug de escala no filtro de Exaustao.

`compute_exaustao` comparava o range da vela (calculado em porcentual, ex.
0.42 para 0.42%) contra `atr_percent * 2.5`, onde `atr_percent` e uma fracao
(ex. 0.0057 para 0.57%) — nunca convertida para a mesma escala. Isso tornava
o threshold ~100x menor que o pretendido, fazendo o fator
"velas_alongadas_consecutivas" (+15 pontos) disparar em praticamente
qualquer vela, real ou nao. Corrigido para comparar ambos em fracao.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.scanner.flex_scoring import compute_exaustao
from ENGINE.scanner.scanner_types import SignalDirection


def _make_candles(ranges_pct, base_price=100.0):
    """Gera velas sinteticas com o range percentual dado (lista de %, ex. 0.4 = 0.4%)."""
    highs, lows, closes = [], [], []
    price = base_price
    for r in ranges_pct:
        half = price * (r / 100.0) / 2.0
        highs.append(price + half)
        lows.append(price - half)
        closes.append(price)
    return highs, lows, closes


class TestVelasAlongadasEscalaCorreta:
    """RFC V25.4: velas normais (dentro da volatilidade real do ativo) nao
    devem mais disparar 'velas_alongadas_consecutivas' falsamente."""

    def test_velas_normais_nao_disparam_com_atr_realista(self):
        # Replica o cenario real observado (BTCUSDT 1h): ATR% ~0.57%,
        # velas com range ~0.3-0.4% (bem menores que 2.5x ATR = ~1.43%).
        atr_percent = 0.0057
        highs, lows, closes = _make_candles([0.43, 0.31, 0.41])
        volumes = [100.0] * 10
        result = compute_exaustao(
            rsi=50.0, adx=30.0, atr_percent=atr_percent, rvol=1.0,
            kalman_tendency=0.5, closes=closes * 4, highs=highs, lows=lows,
            volumes=volumes, direction=SignalDirection.LONG, current_price=closes[-1],
        )
        assert "velas_alongadas_consecutivas" not in result.reasons

    def test_velas_genuinamente_alongadas_ainda_disparam(self):
        # Velas com range real > 2.5x o ATR% devem continuar disparando —
        # o fix nao deve eliminar deteccoes legitimas de exaustao.
        atr_percent = 0.0057
        # 2.5x ATR em % = 1.4331%; usamos ranges bem acima disso.
        highs, lows, closes = _make_candles([3.0, 3.2, 0.2])
        volumes = [100.0] * 10
        result = compute_exaustao(
            rsi=50.0, adx=30.0, atr_percent=atr_percent, rvol=1.0,
            kalman_tendency=0.5, closes=closes * 4, highs=highs, lows=lows,
            volumes=volumes, direction=SignalDirection.LONG, current_price=closes[-1],
        )
        assert "velas_alongadas_consecutivas" in result.reasons

    def test_bug_antigo_teria_disparado_para_velas_normais(self):
        """Documenta o comportamento do bug: com o threshold antigo
        (atr_percent tratado como se already estivesse em %), qualquer
        vela > 0.05%-ish disparava. Este teste apenas fixa o valor de
        referencia usado no relato da RFC V25.3/V25.4 para futura consulta."""
        atr_percent = 0.0057
        threshold_bugado = atr_percent * 2.5          # 0.01425 (escala errada)
        threshold_correto = atr_percent * 2.5         # 0.01425 em fracao == 1.425% em %
        # O bug comparava c_range em % (ex. 0.43) contra threshold_bugado (0.01425) -> sempre True.
        assert 0.43 > threshold_bugado  # comportamento antigo (bugado)
        # O fix compara c_range em fracao (0.0043) contra o mesmo threshold -> False.
        assert not (0.0043 > threshold_correto)


class TestExaustaoScoreDistribution:
    def test_condicoes_normais_nao_bloqueiam(self):
        """Sinal em condicoes de mercado normais (sem RSI extremo, ADX ok,
        velas normais) nao deve ser bloqueado por exaustao apenas por causa
        do bug de escala."""
        atr_percent = 0.0057
        highs, lows, closes = _make_candles([0.4, 0.35, 0.3])
        volumes = [100.0] * 10
        result = compute_exaustao(
            rsi=55.0, adx=30.0, atr_percent=atr_percent, rvol=1.0,
            kalman_tendency=0.5, closes=closes * 4, highs=highs, lows=lows,
            volumes=volumes, direction=SignalDirection.LONG, current_price=closes[-1],
        )
        assert not result.bloquear
        assert result.score < 25
