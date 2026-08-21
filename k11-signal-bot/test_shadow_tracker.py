"""
K11 Shadow Outcome Tracking V1 — testes obrigatórios (RFC 21/08, secao 21).

Rodar: python3 test_shadow_tracker.py
Usa um arquivo temporário para ARQUIVO_SHADOW — nunca toca nos dados reais
de produção (shadow_candidates.jsonl / k11_trades.json).
"""
import copy
import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import shadow_tracker as st

RESULTS = []


def _run(nome, fn):
    try:
        fn()
        RESULTS.append((nome, True, ""))
    except AssertionError as e:
        RESULTS.append((nome, False, str(e)))
    except Exception as e:
        RESULTS.append((nome, False, f"{type(e).__name__}: {e}"))


def _sinal_aprovado(symbol="TEST", tf="30m", candle_ts=1700000000.0, score=90):
    return {
        "symbol": f"{symbol}/USDT:USDT", "timeframe": tf, "direcao": "LONG",
        "score": score, "tier": "OURO", "regime": "Tendência Alta ↑",
        "entrada": 1.0, "stop": 0.97, "tp1": 1.05, "tp2": 1.08, "rr": 3.0,
        "rvol": 2.2, "adx": 30.0, "rsi": 60.0,
        "ema10": 1.02, "ema21": 1.00, "ema50": 0.98, "ema200": 0.9,
        "macd_hist": 0.001, "vwap": 0.99, "atr": 0.02,
        "entry_quality": 90, "candle_ts": candle_ts, "aprovado": True,
        "motivos_rejeicao": [], "confirmacoes_smc": ["EMAs 4 alinhadas", "✅ Tendência forte"],
        "not_extended": True, "bull_candle": True, "pullback_long": True,
        "h1_quality_long": 90, "dist_ema50_atr": 0.3,
    }


def _sinal_bloqueado(symbol="BLK", tf="30m", candle_ts=1700000100.0, score=60):
    s = _sinal_aprovado(symbol, tf, candle_ts, score)
    s["aprovado"] = False
    s["motivos_rejeicao"] = [
        "Volume insuficiente RVOL 0.60",
        "Entry Quality 60 < 75.0 (late entry)",
        "❌ H4 contra tendência forte",
    ]
    s["rvol"] = 0.60
    s["entry_quality"] = 60
    return s


def setup_tmp():
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tmp.close()
    st.ARQUIVO_SHADOW = tmp.name
    return tmp.name


def teardown_tmp(path):
    try:
        os.remove(path)
    except OSError:
        pass


# ── Teste 1: candidato bloqueado não gera ordem real ────────────────────────
def test_1_bloqueado_nao_gera_ordem_real():
    path = setup_tmp()
    try:
        bloqueado = _sinal_bloqueado()
        novos = st.capturar_lote([bloqueado])
        assert novos == 1
        # capturar_lote so retorna um inteiro -- nao ha nenhum objeto "ordem"
        # sendo produzido ou retornado que pudesse ser enviado como trade real.
        estado = st._dobrar_estado(st._carregar_eventos())
        cand = list(estado.values())[0]
        assert cand["aprovado"] is False
        assert cand.get("real_trade_id") is None
    finally:
        teardown_tmp(path)


# ── Teste 2: shadow não modifica o sinal ────────────────────────────────────
def test_2_shadow_nao_modifica_sinal():
    path = setup_tmp()
    try:
        original = _sinal_aprovado()
        copia_antes = copy.deepcopy(original)
        st.capturar_lote([original])
        assert original == copia_antes, "capturar_lote alterou o dict do sinal in-place"
    finally:
        teardown_tmp(path)


# ── Teste 3: erro de leitura não vira lista vazia silenciosa ────────────────
def test_3_erro_leitura_nao_silencioso():
    path = setup_tmp()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("{isso nao e json valido\n")
        import logging
        capturado = []

        class _Handler(logging.Handler):
            def emit(self, record):
                capturado.append(record.getMessage())

        h = _Handler()
        st.logger.addHandler(h)
        try:
            eventos = st._carregar_eventos()
        finally:
            st.logger.removeHandler(h)

        assert eventos == []
        assert any("corrompida" in m for m in capturado), "nenhum warning foi logado"
    finally:
        teardown_tmp(path)


# ── Teste 4: dois ciclos no mesmo candle não duplicam ───────────────────────
def test_4_sem_duplicata_entre_ciclos():
    path = setup_tmp()
    try:
        sinal = _sinal_aprovado()
        n1 = st.capturar_lote([sinal])
        n2 = st.capturar_lote([sinal])  # "segundo ciclo", mesmo candle
        assert n1 == 1
        assert n2 == 0, "capturou o mesmo candidato de novo no segundo ciclo"
        eventos = st._carregar_eventos()
        capturados = [e for e in eventos if e.get("evento") == "captured"]
        assert len(capturados) == 1
    finally:
        teardown_tmp(path)


# ── Teste 5: TP/SL respeitam ordem temporal correta ─────────────────────────
def test_5_ordem_temporal_tp_sl():
    class FakeExchange:
        def __init__(self, velas):
            self.velas = velas

        def fetch_ohlcv(self, symbol, tf, since=None, limit=None):
            return self.velas

    cand = {
        "symbol": "TEST/USDT:USDT", "timeframe": "30m", "direcao": "LONG",
        "entrada": 1.0, "stop": 0.97, "tp1": 1.05, "candle_ts": 1700000000.0,
    }

    # Caso A: SL bate ANTES do TP (vela 1 toca stop, vela 2 tocaria TP) -> STOP
    velas_stop_primeiro = [
        [1700000060000, 1.0, 1.01, 0.96, 0.97, 100],   # low <= stop
        [1700000120000, 0.97, 1.06, 0.97, 1.05, 100],  # high >= tp1 (mas ja devia ter parado)
    ]
    r = st._resolver_um(cand, FakeExchange(velas_stop_primeiro))
    assert r["status"] == "STOP", f"esperado STOP, veio {r}"

    # Caso B: TP bate ANTES do SL -> TP1
    velas_tp_primeiro = [
        [1700000060000, 1.0, 1.06, 0.99, 1.05, 100],   # high >= tp1
        [1700000120000, 1.05, 1.05, 0.90, 0.95, 100],  # low <= stop (mas ja devia ter fechado)
    ]
    r2 = st._resolver_um(cand, FakeExchange(velas_tp_primeiro))
    assert r2["status"] == "TP1", f"esperado TP1, veio {r2}"

    # Caso C: ambos na MESMA vela -> AMBIGUOUS (nunca assume TP por ser favoravel)
    velas_ambiguo = [
        [1700000060000, 1.0, 1.06, 0.96, 1.0, 100],  # high>=tp1 E low<=stop na mesma vela
    ]
    r3 = st._resolver_um(cand, FakeExchange(velas_ambiguo))
    assert r3["status"] == "AMBIGUOUS", f"esperado AMBIGUOUS, veio {r3}"
    assert r3.get("ambiguous") is True


# ── Teste 6: shadow não altera configuração ─────────────────────────────────
def test_6_nao_altera_configuracao():
    import config
    antes = (config.MODO_10_10, config.RVOL_MIN_10, config.SCORE_PRATA_10,
             config.RR_MIN_10, config.ENTRY_QUALITY_MIN, config.RISCO_PCT, config.BANCA)
    path = setup_tmp()
    try:
        st.capturar_lote([_sinal_aprovado(), _sinal_bloqueado()])
        st.relatorio_shadow()
        st.relatorio_por_motivo()
    finally:
        teardown_tmp(path)
    depois = (config.MODO_10_10, config.RVOL_MIN_10, config.SCORE_PRATA_10,
              config.RR_MIN_10, config.ENTRY_QUALITY_MIN, config.RISCO_PCT, config.BANCA)
    assert antes == depois, f"configuracao mudou: {antes} -> {depois}"


# ── Teste 7: restart não perde candidatos (persistência sobrevive) ─────────
def test_7_restart_nao_perde_candidatos():
    path = setup_tmp()
    try:
        st.capturar_lote([_sinal_aprovado(symbol="A"), _sinal_bloqueado(symbol="B")])
        # Simula "restart": novo processo leria o arquivo do zero.
        eventos_novos = st._carregar_eventos()
        estado = st._dobrar_estado(eventos_novos)
        assert len(estado) == 2
    finally:
        teardown_tmp(path)


# ── Teste 8: arquivo corrompido não destrói histórico anterior ─────────────
def test_8_corrupcao_nao_destroi_historico():
    path = setup_tmp()
    try:
        st.capturar_lote([_sinal_aprovado(symbol="BOM1")])
        st.capturar_lote([_sinal_aprovado(symbol="BOM2", candle_ts=1700000200.0)])
        with open(path, "a", encoding="utf-8") as f:
            f.write("{linha corrompida, nao fecha\n")
        st.capturar_lote([_sinal_aprovado(symbol="BOM3", candle_ts=1700000300.0)])

        estado = st._dobrar_estado(st._carregar_eventos())
        assert len(estado) == 3, f"esperava 3 candidatos bons preservados, veio {len(estado)}"
    finally:
        teardown_tmp(path)


# ── Teste 9: candidato aprovado tem snapshot completo ───────────────────────
def test_9_aprovado_snapshot_completo():
    path = setup_tmp()
    try:
        st.capturar_lote([_sinal_aprovado()])
        estado = st._dobrar_estado(st._carregar_eventos())
        cand = list(estado.values())[0]
        for campo in st.CAMPOS_SNAPSHOT:
            assert campo in cand, f"campo {campo} ausente no snapshot do aprovado"
        assert cand["outcome_simulable"] is True
    finally:
        teardown_tmp(path)


# ── Teste 10: candidato bloqueado tem TODOS os motivos, não só o primeiro ──
def test_10_bloqueado_todos_motivos():
    path = setup_tmp()
    try:
        bloqueado = _sinal_bloqueado()  # 3 motivos simultaneos
        st.capturar_lote([bloqueado])
        estado = st._dobrar_estado(st._carregar_eventos())
        cand = list(estado.values())[0]
        reasons = cand["block_reasons"]
        assert "RVOL_LOW" in reasons
        assert "ENTRY_QUALITY_LOW" in reasons
        assert "H4_COUNTER_TREND" in reasons
        assert len(reasons) == 3, f"esperava 3 motivos, veio {reasons}"
    finally:
        teardown_tmp(path)


if __name__ == "__main__":
    testes = [
        ("1_bloqueado_nao_gera_ordem_real", test_1_bloqueado_nao_gera_ordem_real),
        ("2_shadow_nao_modifica_sinal", test_2_shadow_nao_modifica_sinal),
        ("3_erro_leitura_nao_silencioso", test_3_erro_leitura_nao_silencioso),
        ("4_sem_duplicata_entre_ciclos", test_4_sem_duplicata_entre_ciclos),
        ("5_ordem_temporal_tp_sl", test_5_ordem_temporal_tp_sl),
        ("6_nao_altera_configuracao", test_6_nao_altera_configuracao),
        ("7_restart_nao_perde_candidatos", test_7_restart_nao_perde_candidatos),
        ("8_corrupcao_nao_destroi_historico", test_8_corrupcao_nao_destroi_historico),
        ("9_aprovado_snapshot_completo", test_9_aprovado_snapshot_completo),
        ("10_bloqueado_todos_motivos", test_10_bloqueado_todos_motivos),
    ]
    for nome, fn in testes:
        _run(nome, fn)

    ok = sum(1 for _, passou, _ in RESULTS if passou)
    for nome, passou, erro in RESULTS:
        status = "PASS" if passou else "FAIL"
        linha = f"{status}  test_{nome}"
        if erro:
            linha += f"  -- {erro}"
        print(linha)
    print(f"\n{ok} passaram de {len(RESULTS)} (falhas={len(RESULTS)-ok})")
