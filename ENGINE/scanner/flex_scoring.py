import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

from ENGINE.market.market_types import Candle
from .scanner_types import Pattern, PatternType, SignalDirection, MarketStructure, StructureType

log = logging.getLogger(__name__)


def compute_flow_data_from_candles(
    patterns: List[Pattern],
    rvol: float,
    volume: float,
    avg_volume: float,
    direction: SignalDirection,
    closes: List[float],
    highs: List[float],
    lows: List[float],
    adx: float = 0.0,
) -> Dict[str, Any]:
    """Build flow data from candle data without requiring order book delta.

    Estima direcao do fluxo baseado em:
    - RVOL e volume crescente
    - Estrutura do candle (body ratio, wick)
    - Sequencia direcional
    - BOS/CHOCH patterns
    - Order Blocks e FVGs
    - Liquidity Sweeps (absorcao)
    """
    volume_crescente = volume > avg_volume * 1.2 if avg_volume > 0 else False

    smc_types = {p.type for p in patterns}
    has_bos = PatternType.BOS in smc_types
    has_choch = PatternType.CHOCH in smc_types
    has_sweep = PatternType.LIQUIDITY_SWEEP in smc_types
    has_ob = PatternType.ORDER_BLOCK in smc_types
    has_fvg = PatternType.FVG in smc_types

    absorcao = any(
        p.type == PatternType.LIQUIDITY_SWEEP
        and p.direction == direction
        for p in patterns
    )

    # Estima delta a partir de candle data
    estimated_delta = _estimate_delta(closes, highs, lows, direction, rvol, volume_crescente, has_bos, has_choch)

    # CVD estimado do candle body ratio e volume
    estimated_cvd = _estimate_cvd(closes, highs, lows, volume, avg_volume, direction)

    # Volume institucional: rvol alto + estrutura forte
    inst_vol = rvol >= 1.8 and volume_crescente and (has_bos or has_choch)

    flow_data = {
        "delta": estimated_delta,
        "rvol": rvol,
        "volume_crescente": volume_crescente,
        "absorcao": absorcao,
        "cvd": estimated_cvd,
        "volume_institucional": inst_vol,
        "bos_present": has_bos,
        "choch_present": has_choch,
        "ob_present": has_ob,
        "fvg_present": has_fvg,
    }
    return flow_data


def _estimate_delta(
    closes: List[float],
    highs: List[float],
    lows: List[float],
    direction: SignalDirection,
    rvol: float,
    volume_crescente: bool,
    has_bos: bool,
    has_choch: bool,
) -> float:
    """Estima delta (buying/selling pressure) sem order book.

    Usa: direcao do candle, body ratio, volume, BOS/CHOCH.
    Retorna valor entre -1.0 e 1.0 (similar a delta normalizado).
    """
    if len(closes) < 3 or len(highs) < 3 or len(lows) < 3:
        return 0.0

    dir_signal = 1.0 if direction == SignalDirection.LONG else -1.0
    score = 0.0
    factors = 0

    # Fator 1: Fechamento dos ultimos 3 candles
    recent_closes = closes[-3:]
    if recent_closes[-1] > recent_closes[-2] > recent_closes[-3]:
        score += 0.30 * dir_signal
        factors += 1
    elif recent_closes[-1] < recent_closes[-2] < recent_closes[-3]:
        score -= 0.30 * dir_signal
        factors += 1
    elif recent_closes[-1] > recent_closes[-2]:
        score += 0.15 * dir_signal
        factors += 1
    elif recent_closes[-1] < recent_closes[-2]:
        score -= 0.15 * dir_signal
        factors += 1

    # Fator 2: Body ratio do ultimo candle
    if len(highs) >= 1 and len(lows) >= 1:
        c_range = highs[-1] - lows[-1]
        if c_range > 0:
            body = abs(closes[-1] - (highs[-1] if direction == SignalDirection.SHORT else lows[-1]))
            body_ratio = body / c_range
            if body_ratio > 0.7:
                score += 0.25 * dir_signal
                factors += 1
            elif body_ratio > 0.5:
                score += 0.15 * dir_signal
                factors += 1

    # Fator 3: BOS/CHOCH confirmam fluxo
    if has_bos:
        score += 0.20 * dir_signal
        factors += 1
    if has_choch:
        score += 0.15 * dir_signal
        factors += 1

    # Fator 4: Volume + rvol
    if volume_crescente and rvol >= 1.5:
        rvol_boost = min(rvol / 5.0, 0.5) * dir_signal
        score += rvol_boost
        factors += 1
    elif volume_crescente:
        score += 0.10 * dir_signal
        factors += 1

    # Fator 5: Wick do ultimo candle (rejeicao)
    if len(highs) >= 1 and len(lows) >= 1:
        c_range = highs[-1] - lows[-1]
        if c_range > 0:
            if direction == SignalDirection.LONG:
                upper_wick = highs[-1] - max(closes[-1], (highs[-1] + lows[-1]) / 2)
                wick_ratio = upper_wick / c_range
            else:
                lower_wick = min(closes[-1], (highs[-1] + lows[-1]) / 2) - lows[-1]
                wick_ratio = lower_wick / c_range
            if wick_ratio < 0.15:
                score += 0.10 * dir_signal
                factors += 1
            elif wick_ratio > 0.5:
                score -= 0.10 * dir_signal
                factors += 1

    if factors == 0:
        return 0.0

    delta = score / factors
    return max(-1.0, min(1.0, round(delta, 4)))


def _estimate_cvd(
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volume: float,
    avg_volume: float,
    direction: SignalDirection,
) -> float:
    """Estima CVD (Cumulative Volume Delta) de candle data.

    Usa body ratio * volume como proxy do delta de volume.
    """
    if len(closes) < 1 or len(highs) < 1 or len(lows) < 1:
        return 0.0

    c_range = highs[-1] - lows[-1]
    if c_range <= 0 or volume <= 0:
        return 0.0

    body = abs(closes[-1] - (lows[-1] if closes[-1] > (highs[-1] + lows[-1]) / 2 else highs[-1]))
    body_ratio = body / c_range
    vol_ratio = volume / max(avg_volume, 1)

    cvd_signal = 1.0 if direction == SignalDirection.LONG else -1.0
    cvd = body_ratio * vol_ratio * cvd_signal * 0.5
    return round(cvd, 4)


def compute_flow_score(
    flow_data: Dict[str, Any],
    direction: SignalDirection,
) -> float:
    """Fluxo score 0-1 baseado em delta estimado, RVOL, absorcao, estrutura.

    Sem dependencia de order book delta — usa estimativas de candle.
    """
    delta = flow_data.get("delta", 0) or 0
    rvol = flow_data.get("rvol", 0) or 0
    vol_cres = flow_data.get("volume_crescente", False)
    absorcao = flow_data.get("absorcao", False)
    cvd = flow_data.get("cvd", 0) or 0
    inst_vol = flow_data.get("volume_institucional", False)
    has_bos = flow_data.get("bos_present", False)
    has_choch = flow_data.get("choch_present", False)

    dir_str = "long" if direction == SignalDirection.LONG else "short"
    flow_a_favor = (delta > 0.01 and dir_str == "long") or (delta < -0.01 and dir_str == "short")

    score = 0.0

    # Delta estimado (20%)
    if flow_a_favor:
        delta_abs = abs(delta)
        if delta_abs >= 0.50:
            score += 0.20
        elif delta_abs >= 0.25:
            score += 0.15
        elif delta_abs >= 0.10:
            score += 0.10
        else:
            score += 0.05

    # CVD estimado (15%)
    cvd_favor = (cvd > 0 and dir_str == "long") or (cvd < 0 and dir_str == "short")
    if cvd_favor and vol_cres:
        score += 0.15
    elif cvd_favor:
        score += 0.10

    # RVOL (20%)
    if rvol >= 2.5:
        score += 0.20
    elif rvol >= 2.0:
        score += 0.16
    elif rvol >= 1.5:
        score += 0.12
    elif rvol >= 1.2:
        score += 0.08
    elif rvol >= 1.0:
        score += 0.05

    # BOS/CHOCH como confirmacao de fluxo (15%)
    if has_bos and has_choch:
        score += 0.15
    elif has_bos:
        score += 0.10
    elif has_choch:
        score += 0.08

    # Absorcao (15%)
    if absorcao and flow_a_favor:
        score += 0.15
    elif absorcao:
        score += 0.10

    # Volume institucional (15%)
    if inst_vol:
        score += 0.15
    elif vol_cres and rvol >= 2.0:
        score += 0.10
    elif vol_cres:
        score += 0.05

    score = max(0.0, min(1.0, score))
    return round(score, 4)


def compute_timing_index(
    patterns: List[Pattern],
    structure: MarketStructure,
    rvol: float,
    volume_crescente: bool,
    kalman_dir: str = "SIDE",
    kalman_confidence: float = 0.0,
    velas_fortes: int = 0,
    current_price: Optional[float] = None,
    ema21: Optional[float] = None,
    rsi: float = 50.0,
) -> float:
    """Timing index 0-1.

    Measures how well-timed the entry is based on pattern confluence
    and market conditions. Includes EMA21 proximity, RSI neutrality,
    and Kalman confidence modulation.
    """
    score = 0.0

    smc_types = {p.type for p in patterns}
    has_bos = PatternType.BOS in smc_types
    has_choch = PatternType.CHOCH in smc_types
    has_ob = PatternType.ORDER_BLOCK in smc_types
    has_fvg = PatternType.FVG in smc_types
    has_sweep = PatternType.LIQUIDITY_SWEEP in smc_types

    if has_bos and has_choch:
        score += 0.20
    if has_ob or has_fvg:
        score += 0.10
    if has_sweep:
        score += 0.10
    if volume_crescente:
        score += 0.10
    if rvol >= 1.5:
        score += 0.10
    if velas_fortes >= 2:
        score += 0.10
    if kalman_dir in ("UP", "DOWN"):
        score += 0.10 * max(0.3, kalman_confidence)
    if structure.structure_strength >= 0.5:
        score += 0.10

    # EMA21 proximity — pullback saudavel perto da media
    if current_price is not None and ema21 is not None and ema21 > 0:
        dist_pct = abs(current_price - ema21) / current_price * 100
        if dist_pct < 0.5:
            score += 0.10
        elif dist_pct < 1.5:
            score += 0.08
        elif dist_pct < 3.0:
            score += 0.04

    # RSI neutrality — prefere RSI nao extremo
    if 45 <= rsi <= 55:
        score += 0.08
    elif 40 <= rsi <= 60:
        score += 0.05
    elif 35 <= rsi <= 65:
        score += 0.02

    # Baseline
    score += 0.20

    score = max(0.0, min(1.0, score))
    return round(score, 4)


def compute_follow_through(
    candles: List[Candle],
    direction: SignalDirection,
    smc_data: Dict[str, bool],
) -> Tuple[float, List[str]]:
    """Follow Through score 0-1.

    Evaluates post-breakout continuation quality:
    - Breakout confirmation (break of structure)
    - Close beyond structure
    - Post-breakout continuation
    - Absence of rejection
    - Candle body strength
    - Directional sequence

    Returns (score, explanation).
    """
    if len(candles) < 3:
        return 0.0, ["dados_insuficientes"]

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    opens = [c.open for c in candles]
    volumes = [c.volume for c in candles]

    ft_score = 0.0
    explicacao = []

    bos = smc_data.get("BOS", False)
    choch = smc_data.get("CHOCH", False)

    # 1. Rompimento confirmado (30% = 0.30)
    if bos or choch:
        ft_score += 0.30
        explicacao.append("rompimento_confirmado")
    elif len(closes) >= 3:
        last_body = abs(closes[-1] - opens[-1])
        prev_body = abs(closes[-2] - opens[-2])
        if last_body > prev_body * 1.3 and closes[-1] > closes[-2]:
            ft_score += 0.15
            explicacao.append("rompimento_parcial")

    # 2. Fechamento alem da estrutura (20% = 0.20)
    side = "long" if direction == SignalDirection.LONG else "short"
    if len(closes) >= 3:
        if side == "long":
            recent_high = max(highs[-4:-1]) if len(highs) >= 4 else highs[-2]
            if closes[-1] > recent_high:
                ft_score += 0.20
                explicacao.append("fechamento_alem_estrutura")
        else:
            recent_low = min(lows[-4:-1]) if len(lows) >= 4 else lows[-2]
            if closes[-1] < recent_low:
                ft_score += 0.20
                explicacao.append("fechamento_alem_estrutura")

    # 3. Continuidade pos-BOS (15% = 0.15)
    if len(closes) >= 5:
        if side == "long" and closes[-1] > closes[-2] > closes[-3]:
            ft_score += 0.15
            explicacao.append("continuidade")
        elif side == "short" and closes[-1] < closes[-2] < closes[-3]:
            ft_score += 0.15
            explicacao.append("continuidade")
        elif len(closes) >= 3:
            if side == "long" and closes[-1] > closes[-2]:
                ft_score += 0.08
                explicacao.append("continuidade_parcial")
            elif side == "short" and closes[-1] < closes[-2]:
                ft_score += 0.08
                explicacao.append("continuidade_parcial")

    # 4. Ausencia de rejeicao (10% = 0.10)
    if len(highs) >= 1 and len(lows) >= 1:
        candle_range = highs[-1] - lows[-1]
        if candle_range > 0:
            if side == "long":
                upper_w = highs[-1] - max(closes[-1], opens[-1])
                rej_ratio = upper_w / candle_range
            else:
                lower_w = min(closes[-1], opens[-1]) - lows[-1]
                rej_ratio = lower_w / candle_range
            if rej_ratio < 0.15:
                ft_score += 0.10
                explicacao.append("sem_rejeicao")
            elif rej_ratio < 0.30:
                ft_score += 0.05
                explicacao.append("rejeicao_leve")

    # 5. Corpo do candle (15% = 0.15)
    if len(highs) >= 1 and len(lows) >= 1 and len(closes) >= 1 and len(opens) >= 1:
        candle_range = highs[-1] - lows[-1]
        if candle_range > 0:
            body = abs(closes[-1] - opens[-1])
            body_ratio = body / candle_range
            if body_ratio >= 0.70:
                ft_score += 0.15
                explicacao.append("corpo_forte")
            elif body_ratio >= 0.55:
                ft_score += 0.10
                explicacao.append("corpo_medio")
            elif body_ratio >= 0.40:
                ft_score += 0.05
                explicacao.append("corpo_aceitavel")

    # 6. Sequencia direcional (10% = 0.10)
    if len(closes) >= 6:
        cons = 0
        if side == "long":
            for i in range(-1, -6, -1):
                if closes[i] > closes[i - 1]:
                    cons += 1
                else:
                    break
        else:
            for i in range(-1, -6, -1):
                if closes[i] < closes[i - 1]:
                    cons += 1
                else:
                    break
        if cons >= 4:
            ft_score += 0.10
            explicacao.append("sequencia_direcional")
        elif cons >= 2:
            ft_score += 0.05
            explicacao.append("sequencia_curta")

    ft_score = max(0.0, min(1.0, round(ft_score, 4)))
    return ft_score, explicacao


@dataclass
class ConvictionFactors:
    estrutura: float = 0.0
    fluxo: float = 0.0
    momentum: float = 0.0
    kalman: float = 0.0
    timing: float = 0.0
    volume: float = 0.0
    follow_through: float = 0.0
    risco: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "estrutura": self.estrutura,
            "fluxo": self.fluxo,
            "momentum": self.momentum,
            "kalman": self.kalman,
            "timing": self.timing,
            "volume": self.volume,
            "follow_through": self.follow_through,
            "risco": self.risco,
        }


def compute_conviction_score(
    flow_score: float,
    follow_through_score: float,
    timing_index: float,
    adx: float,
    rvol: float,
    volume_crescente: bool,
    patterns: List[Pattern],
    structure: MarketStructure,
    kalman_dir: str,
    kalman_confidence: float = 0.0,
    kalman_trend_state: str = "ranging",
    kalman_tendency: float = 0.0,
    atr_pct: Optional[float] = None,
    stop_pct: Optional[float] = None,
    rsi: float = 50.0,
    direction: Optional[SignalDirection] = None,
) -> Tuple[float, ConvictionFactors, List[str]]:
    """Conviction score 0-1 based on 8 weighted factors.

    Weights (100% total):
      Estrutura (SMC+Tendencia): 25%
      Fluxo: 20%
      Momentum (ADX+RSI): 15%
      Kalman Adaptativo: 15%
      Timing: 10%
      Volume: 5%
      Follow Through: 5%
      Risco: 5%

    Kalman Adaptativo — peso modulado por confidence/tendency/trend_state.
    Ported from gauss-dna-v5 V7.2 conviction engine.
    """
    fatores = ConvictionFactors()
    explicacao = []

    # 1. Estrutura SMC (25%)
    smc_raw = 0
    smc_types = {p.type for p in patterns}
    has_bos = PatternType.BOS in smc_types
    has_choch = PatternType.CHOCH in smc_types
    has_sweep = PatternType.LIQUIDITY_SWEEP in smc_types
    has_ob = PatternType.ORDER_BLOCK in smc_types
    has_fvg = PatternType.FVG in smc_types

    if has_bos:
        smc_raw += 8
    if has_choch:
        smc_raw += 5
    if has_sweep:
        smc_raw += 4
    if has_ob:
        smc_raw += 3
    if has_fvg:
        smc_raw += 3
    if has_choch and not has_bos and not has_sweep:
        smc_raw = max(0, smc_raw - 3)

    smc_pts = min(25, smc_raw)
    fatores.estrutura = round(smc_pts / 25.0, 4)
    if smc_pts >= 22:
        explicacao.append("Estrutura SMC completa")
    elif smc_pts >= 15:
        explicacao.append("Estrutura SMC forte")
    elif smc_pts >= 8:
        explicacao.append("Estrutura SMC confirmada")
    else:
        explicacao.append("Estrutura SMC insuficiente")

    # 2. Fluxo (20%)
    fluxo_pts = flow_score * 20.0
    fatores.fluxo = round(fluxo_pts / 20.0, 4)
    if fluxo_pts >= 16:
        explicacao.append("Fluxo institucional forte")
    elif fluxo_pts >= 10:
        explicacao.append("Fluxo favoravel")
    elif fluxo_pts < 6:
        explicacao.append("Fluxo insuficiente")

    # 3. Momentum ADX + RSI (15%)
    mom_pts = 0
    if adx >= 40:
        mom_pts += 7
    elif adx >= 35:
        mom_pts += 6
    elif adx >= 28:
        mom_pts += 5
    elif adx >= 22:
        mom_pts += 3
    elif adx >= 18:
        mom_pts += 2
    elif adx >= 15:
        mom_pts += 1

    if 40 <= rsi <= 65:
        mom_pts += 4
    elif rsi > 72 or rsi < 28:
        mom_pts += 0
    else:
        mom_pts += 2

    mom_pts = max(0, min(15, mom_pts))
    fatores.momentum = round(mom_pts / 15.0, 4)
    if mom_pts >= 12:
        explicacao.append("Momentum forte (ADX+RSI)")
    elif mom_pts >= 8:
        explicacao.append("Momentum moderado")

    # 4. Kalman Adaptativo (15%) — com confidence, tendency, trend_state
    dir_ok = kalman_dir in ("UP", "DOWN")
    tendency_ok = direction is not None and (
        (direction == SignalDirection.LONG and kalman_tendency > 0.1)
        or (direction == SignalDirection.SHORT and kalman_tendency < -0.1)
    )
    trend_boost = 0
    if kalman_trend_state == "continuing":
        trend_boost = 3
        explicacao.append("Kalman continuando")
    elif kalman_trend_state == "starting":
        trend_boost = 2
        explicacao.append("Kalman iniciando")
    elif kalman_trend_state == "reversing":
        trend_boost = -4
        explicacao.append("Kalman reversao — cautela")

    kalman_base = 0
    if dir_ok and tendency_ok:
        kalman_base = 12
    elif dir_ok:
        kalman_base = 8
    elif kalman_dir == "REVERSAL":
        kalman_base = 3
    elif kalman_dir == "SIDE":
        kalman_base = 2

    conf_mult = max(0.3, kalman_confidence) if dir_ok else 0.5
    kalman_pts = max(0, min(15, int(kalman_base * conf_mult + trend_boost)))
    fatores.kalman = round(kalman_pts / 15.0, 4)
    explicacao.append(f"Kalman {kalman_pts}/15 (conf {kalman_confidence:.2f})")

    # 5. Timing (10%)
    timing_pts = timing_index * 10.0
    fatores.timing = round(timing_pts / 10.0, 4)
    if timing_index >= 0.75:
        explicacao.append("Timing excelente")
    elif timing_index >= 0.65:
        explicacao.append("Timing bom")
    elif timing_index < 0.55:
        explicacao.append("Timing insuficiente")

    # 6. Volume (5%)
    vol_pts = 0
    if rvol >= 2.5:
        vol_pts = 5
    elif rvol >= 2.0:
        vol_pts = 4
    elif rvol >= 1.5:
        vol_pts = 3
    elif rvol >= 1.2:
        vol_pts = 2
    elif rvol >= 1.0:
        vol_pts = 1
    if volume_crescente and vol_pts > 0:
        vol_pts = min(5, vol_pts + 1)
    fatores.volume = round(vol_pts / 5.0, 4)
    if vol_pts >= 4:
        explicacao.append(f"Volume forte (RVOL {rvol}x)")

    # 7. Follow Through (5%)
    ft_pts = follow_through_score * 5.0
    fatores.follow_through = round(ft_pts / 5.0, 4)
    if follow_through_score >= 0.7:
        explicacao.append("Follow Through forte")
    elif follow_through_score >= 0.4:
        explicacao.append("Follow Through moderado")
    elif follow_through_score < 0.3:
        explicacao.append("Follow Through fraco")

    # 8. Risco (5%)
    risco_pts = 5
    if atr_pct is not None:
        if atr_pct > 4.0:
            risco_pts -= 3
        elif atr_pct > 3.0:
            risco_pts -= 2
        elif atr_pct > 2.5:
            risco_pts -= 1
        elif atr_pct < 0.4:
            risco_pts -= 1
    if stop_pct is not None:
        if stop_pct > 5.0:
            risco_pts -= 3
        elif stop_pct > 3.5:
            risco_pts -= 1
        elif stop_pct < 0.30:
            risco_pts -= 2
    risco_pts = max(0, risco_pts)
    fatores.risco = round(risco_pts / 5.0, 4)
    if risco_pts < 3:
        explicacao.append("Risco elevado")

    raw = sum([
        smc_pts, fluxo_pts, mom_pts, kalman_pts,
        timing_pts, vol_pts, ft_pts, risco_pts,
    ])
    raw = max(0, min(100, raw))

    conviction_norm = round(raw / 100.0, 4)

    if not explicacao and conviction_norm < 0.5:
        explicacao.append("Nenhum fator positivo significativo")

    return conviction_norm, fatores, explicacao


@dataclass
class ExaustaoData:
    score: float = 0.0
    penalty: int = 0
    reasons: List[str] = field(default_factory=list)
    bloquear: bool = False


def compute_exaustao(
    rsi: float,
    adx: float,
    atr_percent: float,
    rvol: float,
    kalman_tendency: float,
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
    direction: SignalDirection,
    current_price: float,
) -> ExaustaoData:
    """Detecta exaustão (0-100 score, -25 a 0 penalty).

    Fatores: RSI extremo, divergência, perda de momentum,
    volume climax, velas consecutivas alongadas.
    Ported from gauss-dna-v5 calcular_exaustao_v7.
    """
    ex = 0
    reasons = []
    side = "long" if direction == SignalDirection.LONG else "short"

    # 1. RSI extremo
    if side == "long":
        if rsi > 80:
            ex += 25; reasons.append("rsi_extremo_long")
        elif rsi > 75:
            ex += 18; reasons.append("rsi_muito_alto")
        elif rsi > 72:
            ex += 12; reasons.append("rsi_alto")
    else:
        if rsi < 20:
            ex += 25; reasons.append("rsi_extremo_short")
        elif rsi < 25:
            ex += 18; reasons.append("rsi_muito_baixo")
        elif rsi < 28:
            ex += 12; reasons.append("rsi_baixo")

    # 2. Momentum loss — ADX caindo + tendencia perde forca
    if adx < 18:
        ex += 10; reasons.append("adx_fraco_sem_tendencia")
    elif adx > 45:
        ex += 5; reasons.append("adx_muito_alto_possivel_exaustao")

    # 3. Volume climax — rvol alto + corpo pequeno
    if rvol > 2.5 and len(highs) >= 2 and len(lows) >= 2:
        last_range = (highs[-1] - lows[-1]) / current_price * 100 if current_price > 0 else 0
        if last_range < 0.5:
            ex += 12; reasons.append("volume_climax_vela_pequena")

    # 4. Velas alongadas consecutivas (2+ velas com range > 2.5x ATR)
    # c_range e atr_percent precisam estar na mesma escala (fracao, nao %) —
    # bug corrigido na RFC V25.4: c_range vinha multiplicado por 100 e
    # comparado contra atr_percent (fracao), tornando o threshold ~100x menor
    # que o pretendido e disparando esse fator em quase toda vela.
    if atr_percent > 0 and len(highs) >= 3 and len(lows) >= 3:
        big_candles = 0
        for i in range(-3, 0):
            if i >= -len(highs) and i >= -len(lows):
                c_range = (highs[i] - lows[i]) / current_price if current_price > 0 else 0
                if c_range > atr_percent * 2.5:
                    big_candles += 1
        if big_candles >= 2:
            ex += 15; reasons.append("velas_alongadas_consecutivas")

    # 5. Kalman perdendo forca — tendencia estagnando
    if abs(kalman_tendency) < 0.05:
        ex += 5; reasons.append("kalman_estagnado")

    # 6. Divergencia simples preco vs momentum
    if len(closes) >= 10:
        preco_subiu = closes[-1] > closes[-10]
        rsi_subiu = rsi > 50
        if side == "long" and not preco_subiu and not rsi_subiu:
            ex += 8; reasons.append("divergencia_baixista")
        elif side == "short" and preco_subiu and rsi_subiu:
            ex += 8; reasons.append("divergencia_altista")

    penalty = min(0, max(-25, -ex))
    ex_score = max(0.0, min(100.0, float(ex)))
    bloquear = ex >= 50

    return ExaustaoData(score=ex_score, penalty=penalty, reasons=reasons, bloquear=bloquear)
