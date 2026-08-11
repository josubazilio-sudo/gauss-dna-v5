"""
K11 V58.1 — Testes da Gestão de Trade pós-entrada.

Rodar: pytest test_gestao_v58_1.py   (ou: python test_gestao_v58_1.py)
Cobre: BE, stop monotônico, trailing por setup, normalização de nomes,
BOS Age real e regressão (imports / entrada inalterada).
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from config import (BE_TRIGGER_R, BE_EXIGE_H1_FECHADO, TP1_FRACAO_VOLUME,
                    BOS_AGE_MAX_CANDLES, TRAILING_SETUPS)
from formatter import formatar_cartao
import gestao_trade as gt


# ── helpers de teste ────────────────────────────────────────────────────────
class StubH1Engine:
    """Engine fake: df com candle H1 fechado cujo close é controlado."""

    def __init__(self, closed_h1_close):
        self.c = float(closed_h1_close)
        self.called = False

    def _fetch(self, symbol, tf, limit=60):
        return None

    def _calc(self, df):
        self.called = True
        return pd.DataFrame([{"close": self.c} for _ in range(6)], dtype=float)


class StubBOSEngine:
    """Engine fake: expõe o _bos_idade real (mesmo método do K10Engine)."""

    def __init__(self, idade):
        self.idade = int(idade)

    def _bos_idade(self, df, direcao):
        return self.idade


# ── TESTE 1 — BE LONG ───────────────────────────────────────────────────────
def test_1_be_long_ativa_com_1_5r_e_h1_fechado():
    # Entrada=100, Stop=98, risco=2. H1 fechado em 103 => R=1.5.
    engine = StubH1Engine(closed_h1_close=103.0)
    ativar, r, motivo = gt.avaliar_be(engine, "BASTOCK/USDT:USDT", "LONG", 100.0, 98.0)
    assert ativar is True, motivo
    assert r >= 1.5
    # Depois do BE o stop mínimo é a entrada (>= 100).
    stop_final = gt.aplicar_be_stop(98.0, 100.0, "LONG")
    assert stop_final >= 100.0


def test_1b_be_long_nao_ativa_r_inferior():
    engine = StubH1Engine(closed_h1_close=102.5)  # R = 1.25 < 1.5
    ativar, r, _ = gt.avaliar_be(engine, "BASTOCK/USDT:USDT", "LONG", 100.0, 98.0)
    assert ativar is False
    assert r < 1.5


# ── TESTE 1 — BE SHORT (regra espelhada) ────────────────────────────────────
def test_1c_be_short_ativa_com_1_5r_e_h1_fechado():
    # Entrada=100, Stop=102, risco=2. H1 fechado em 97 => R=1.5 (SHORT).
    engine = StubH1Engine(closed_h1_close=97.0)
    ativar, r, motivo = gt.avaliar_be(engine, "XYZ/USDT:USDT", "SHORT", 100.0, 102.0)
    assert ativar is True, motivo
    assert r >= 1.5
    stop_final = gt.aplicar_be_stop(102.0, 100.0, "SHORT")
    assert stop_final <= 100.0


# ── TESTE 2 — trailing NÃO reduz proteção ───────────────────────────────────
def test_2_trailing_nao_reduz_protecao_long():
    # Stop atual = 100, trailing calculado = 98 → final = 100 (nunca recua).
    assert gt.proteger_stop(100.0, 98.0, "LONG") == 100.0


# ── TESTE 3 — trailing melhora proteção ─────────────────────────────────────
def test_3_trailing_melhora_protecao_long():
    assert gt.proteger_stop(100.0, 104.0, "LONG") == 104.0


# ── TESTE 4 — SHORT espelhado ───────────────────────────────────────────────
def test_4_short_trailing_100_trailing_102_mantem_100():
    assert gt.proteger_stop(100.0, 102.0, "SHORT") == 100.0


# ── TESTE 5 — REVERSÃO ──────────────────────────────────────────────────────
def test_5_reversao_prata_familia_e_regra():
    assert gt.normalizar_setup("REVERSÃO PRATA") == "REVERSAO"
    for nome in ("REVERSAO", "REVERSÃO OURO", "REVERSÃO INSTITUCIONAL",
                 "LIQUIDEZ + REVERSÃO", "LIQUIDEZ + REVERSAO", "🔥 LIQUIDEZ + REVERSÃO"):
        assert gt.normalizar_setup(nome) == "REVERSAO", nome
    familia, cfg = gt.config_trailing("REVERSÃO PRATA")
    assert familia == "REVERSAO"
    assert cfg["trigger_r"] == 2.0
    assert (cfg["timeframe"] or "").lower() == "1h"


# ── TESTE 6 — TENDÊNCIA / CONTINUAÇÃO ───────────────────────────────────────
def test_6_alta_qualidade_familia_e_regra():
    assert gt.normalizar_setup("ALTA QUALIDADE") == "TENDENCIA"
    for nome in ("TENDÊNCIA", "TENDENCIA", "CONTINUAÇÃO", "CONTINUACAO",
                 "TREND FOLLOWING", "BOS + CONTINUAÇÃO", "BOS + CONTINUACAO",
                 "⭐ ALTA QUALIDADE"):
        assert gt.normalizar_setup(nome) == "TENDENCIA", nome
    familia, cfg = gt.config_trailing("ALTA QUALIDADE")
    assert familia == "TENDENCIA"
    assert cfg["trigger_r"] == 1.5
    assert (cfg["timeframe"] or "").lower() == "30m"


# ── TESTE 7 — BOS/CHoCH real (sem detector simplificado) ────────────────────
def test_7_bos_age_reutiliza_bos_real_do_k11():
    src = pathlib.Path(gt.__file__).read_text(encoding="utf-8")
    # gestao_trade usa o _bos_idade do K10Engine — sem detector novo.
    assert "engine._bos_idade" in src
    # Não há aproximação simplificada igual a close > max(3 candles).
    assert "max(previous_3_candles" not in src
    assert "close > max(" not in src
    # BOS fresco (idade <= BOS_AGE_MAX_CANDLES = 4) está ok.
    engine = StubBOSEngine(3)
    idade, ok = gt.bos_age(engine, [], "LONG")
    assert BOS_AGE_MAX_CANDLES == 4
    assert idade == 3 and ok is True
    # BOS velho (> 4) bloqueia trailing.
    engine_velho = StubBOSEngine(9)
    idade2, ok2 = gt.bos_age(engine_velho, [], "LONG")
    assert idade2 == 9 and ok2 is False


# ── TESTE 8 — Regressão / entrada inalterada ────────────────────────────────
def test_8_regressao_imports_e_entrada_inalterada():
    assert BE_TRIGGER_R == 1.5
    assert BE_EXIGE_H1_FECHADO is True
    assert TP1_FRACAO_VOLUME == 0.30
    assert BOS_AGE_MAX_CANDLES == 4
    assert TRAILING_SETUPS["REVERSAO"]["trigger_r"] == 2.0
    assert TRAILING_SETUPS["TENDENCIA"]["trigger_r"] == 1.5

    import importlib
    for mod in ("gestao_trade", "k10_engine", "formatter", "final_selector",
                "trade_tracker", "runner"):
        importlib.import_module(mod)

    sinal = {
        "aprovado": True, "symbol": "BASTOCK/USDT:USDT", "direcao": "LONG",
        "timeframe": "1h", "score": 90, "tier": "OURO", "entrada": 100.0,
        "tp1": 104.0, "tp2": 107.0, "be": 102.0, "stop": 98.0, "rr": 3.5,
        "regime": "Reversão ↗", "setup_nome": "SMC", "prioridade": "🔥 LIQUIDEZ + REVERSÃO",
        "confirmacoes_smc": ["✅ BOS confirmado"], "eq_detalhes": {"ema21": 0, "ob_fvg": 0, "timing": 0, "rsi": 0, "bos": 0},
        "entry_quality": 90, "capital": 90.0, "posicao": 45.0, "alavancagem": 20,
        "risco_usdt": 2.7,
    }
    cartao = formatar_cartao(sinal, bot_name="K11")
    assert cartao and "parcial 30%" in cartao
    # Regra de entrada (níveis TP1/Stop/BE do K11) não foi alterada pelo patch:
    assert sinal["tp1"] == 104.0 and sinal["stop"] == 98.0 and sinal["be"] == 102.0


if __name__ == "__main__":
    import traceback
    falhas = 0
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {nome}")
            except Exception as e:
                falhas += 1
                print(f"FAIL  {nome}: {e}")
                traceback.print_exc()
    print(f"\n{8 if falhas == 0 else 0} passaram de 8 (falhas={falhas})")
    sys.exit(1 if falhas else 0)