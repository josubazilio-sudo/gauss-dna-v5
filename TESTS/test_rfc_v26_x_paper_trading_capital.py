"""RFC V26.X — Banca institucional fixa (ACCOUNT_SIZE) no PaperTradingEngine.

PaperTradingEngine hardcoded self._capital/self._initial_capital = 10000.0,
completamente desconectado de ACCOUNT_SIZE (200, configurado em .env e usado
em todo o resto do pipeline: Balance do bot, InstitutionalMathAuditor, curva
de equity). Isso distorcia o retorno % de toda operacao em paper trading
(dividido por um baseline que nunca foi real). Corrigido para usar
ACCOUNT_SIZE como default, com migracao automatica de arquivos antigos que
ainda tem o baseline de 10000 — sem descartar o historico de trades.
"""
import json
import os
import tempfile

from CORE.trading.paper_trading import PaperTradingEngine
from ENGINE.scanner.scanner_config import ACCOUNT_SIZE


def _tmp_db_path():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(path)
    return path


def test_default_initial_capital_is_account_size():
    path = _tmp_db_path()
    engine = PaperTradingEngine(db_path=path)
    assert engine._initial_capital == ACCOUNT_SIZE
    assert engine._capital == ACCOUNT_SIZE


def test_explicit_initial_capital_still_overridable():
    path = _tmp_db_path()
    engine = PaperTradingEngine(db_path=path, initial_capital=500.0)
    assert engine._initial_capital == 500.0


def test_migrates_old_10000_baseline_using_real_pnl():
    """Reproduz o cenario real encontrado em producao: arquivo persistido
    com initial_capital=10000 (o antigo hardcode) e trades fechados com
    PnL real. A migracao deve preservar o historico e recalcular o
    capital atual sobre o baseline correto (ACCOUNT_SIZE)."""
    path = _tmp_db_path()
    old_data = {
        "capital": 9822.15,
        "initial_capital": 10000.0,
        "closed_trades": [
            {
                "pair": "AGIUSDT", "direction": "long", "entry_price": 0.0041,
                "stop_loss": 0.0039, "take_profit": 0.0043,
                "entry_time": "2026-07-15T00:00:00+00:00", "cycle": 1,
                "pnl": 5.0, "pnl_percent": 2.5,
            },
            {
                "pair": "BTCUSDT", "direction": "short", "entry_price": 60000.0,
                "stop_loss": 61000.0, "take_profit": 58000.0,
                "entry_time": "2026-07-15T01:00:00+00:00", "cycle": 2,
                "pnl": -3.0, "pnl_percent": -1.5,
            },
        ],
    }
    with open(path, "w") as f:
        json.dump(old_data, f)

    try:
        engine = PaperTradingEngine(db_path=path)
        assert engine._initial_capital == ACCOUNT_SIZE
        # capital recalculado = ACCOUNT_SIZE + soma do PnL real dos
        # trades fechados (5.0 - 3.0 = 2.0), nunca o valor antigo (9822.15)
        assert engine._capital == round(ACCOUNT_SIZE + 2.0, 2)
        assert len(engine._closed_trades) == 2
    finally:
        os.remove(path)


def test_matching_baseline_keeps_persisted_capital_unchanged():
    """Quando o baseline persistido ja bate com ACCOUNT_SIZE, o capital
    atual persistido e usado como esta, sem recalcular."""
    path = _tmp_db_path()
    data = {
        "capital": ACCOUNT_SIZE + 10.0,
        "initial_capital": ACCOUNT_SIZE,
        "closed_trades": [],
    }
    with open(path, "w") as f:
        json.dump(data, f)

    try:
        engine = PaperTradingEngine(db_path=path)
        assert engine._capital == ACCOUNT_SIZE + 10.0
    finally:
        os.remove(path)
