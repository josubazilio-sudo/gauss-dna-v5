import logging
from typing import List

from .backtest_types import (
    BacktestResult, Trade, TradeStatus, AIRecommendation,
)
from .backtest_config import TARGET_WIN_RATE, TARGET_PROFIT_FACTOR, TARGET_MAX_DRAWDOWN

log = logging.getLogger(__name__)


def generate_recommendations(result: BacktestResult) -> List[AIRecommendation]:
    recs: List[AIRecommendation] = []

    if result.win_rate < TARGET_WIN_RATE:
        recs.append(AIRecommendation(
            category="win_rate",
            description=f"Win Rate ({result.win_rate:.1%}) abaixo da meta ({TARGET_WIN_RATE:.0%})",
            evidence=f"Winning trades: {result.winning_trades}/{result.total_trades}",
            impact="Reduz consistência dos resultados",
            confidence=0.8,
            priority="high",
        ))

    if result.profit_factor < TARGET_PROFIT_FACTOR:
        recs.append(AIRecommendation(
            category="profit_factor",
            description=f"Profit Factor ({result.profit_factor:.2f}) abaixo da meta ({TARGET_PROFIT_FACTOR:.1f})",
            evidence=f"Gross profit: {result.gross_profit:.2f}, Gross loss: {result.gross_loss:.2f}",
            impact="Reduz eficiência de capital",
            confidence=0.85,
            priority="high",
        ))

    if result.max_drawdown_pct > TARGET_MAX_DRAWDOWN:
        recs.append(AIRecommendation(
            category="drawdown",
            description=f"Max Drawdown ({result.max_drawdown_pct:.1%}) acima do limite ({TARGET_MAX_DRAWDOWN:.0%})",
            evidence=f"Max DD: {result.max_drawdown:.2f}, Avg DD: {result.avg_drawdown:.4%}",
            impact="Risco de exposição excessiva",
            confidence=0.9,
            priority="critical",
        ))

    if result.expectancy <= 0:
        recs.append(AIRecommendation(
            category="expectancy",
            description="Expectativa não positiva — estratégia perde dinheiro",
            evidence=f"Expectancy: {result.expectancy:.4f}",
            impact="Sistema não é lucrativo no longo prazo",
            confidence=0.95,
            priority="critical",
        ))

    if result.sharpe_ratio < 1.0:
        recs.append(AIRecommendation(
            category="sharpe_ratio",
            description=f"Sharpe Ratio ({result.sharpe_ratio:.2f}) abaixo de 1.0",
            evidence="Retornos ajustados ao risco insuficientes",
            impact="Relação risco/retorno abaixo do ideal",
            confidence=0.7,
            priority="medium",
        ))

    if result.robustness_score < 0.5:
        recs.append(AIRecommendation(
            category="robustez",
            description="Robustez abaixo do esperado",
            evidence=f"Robustness: {result.robustness_score:.2f}",
            impact="Estratégia pode não generalizar bem",
            confidence=0.65,
            priority="medium",
        ))

    best_setup = _best_category(result.profit_by_setup)
    if best_setup:
        recs.append(AIRecommendation(
            category="setup_otimo",
            description=f"Melhor setup: {best_setup}",
            evidence=f"Lucro: {result.profit_by_setup.get(best_setup, 0):.2f}",
            impact="Focar neste setup pode melhorar resultados",
            confidence=0.7,
            priority="low",
        ))

    worst_setup = _worst_category(result.profit_by_setup)
    if worst_setup:
        recs.append(AIRecommendation(
            category="setup_descartar",
            description=f"Pior setup: {worst_setup}",
            evidence=f"Prejuízo: {result.profit_by_setup.get(worst_setup, 0):.2f}",
            impact="Remover este setup reduz perdas",
            confidence=0.75,
            priority="medium",
        ))

    improving = _detect_improving(result)
    if improving:
        recs.append(AIRecommendation(
            category="tendencia",
            description="Estratégia mostra tendência de melhora",
            evidence="Profit factor crescente ao longo do tempo",
            impact="Sinal positivo para continuar",
            confidence=0.5,
            priority="low",
        ))

    return recs


def _best_category(cat: dict) -> str:
    if not cat:
        return ""
    return max(cat, key=cat.get)


def _worst_category(cat: dict) -> str:
    if not cat:
        return ""
    return min(cat, key=cat.get)


def _detect_improving(result: BacktestResult) -> bool:
    if len(result.trades) < 20:
        return False
    n = len(result.trades)
    first = result.trades[:n // 2]
    second = result.trades[n // 2:]
    pf1 = sum(t.pnl for t in first if t.pnl > 0) / max(abs(sum(t.pnl for t in first if t.pnl < 0)), 0.001)
    pf2 = sum(t.pnl for t in second if t.pnl > 0) / max(abs(sum(t.pnl for t in second if t.pnl < 0)), 0.001)
    return pf2 > pf1
