"""RFC V6.7 — testes unitarios dos 11 blocos + market statistics.

Somente leitura sobre dados ja calculados (sd.to_dict()) — nenhum destes
testes exercita Decision Engine, gates, thresholds ou scoring reais.
"""
from ENGINE.diagnostic.engine import DiagnosticReport
from ENGINE.diagnostic import advanced_report as ar


def _decision(symbol="BTCUSDT", approved=False, quality=0.5, quality_score=0.5,
              confidence=0.5, consensus=0.5, entry_score=0.5,
              classification_label="reprovado", reject_reason="",
              rvol_ok=None, adx_ok=None, structure_ok=None,
              entry_zone_ok=None, quality_ok=None, consensus_ok=None,
              confidence_ok=None, kalman_ok=None, rr_ok=None,
              rvol=1.0, adx=30.0, structure_strength=0.5,
              liquidity_score=0.6, risk_score=0.4, market_score=0.5,
              take_profit_1=0.0, timeframe="1h"):
    return {
        "symbol": symbol, "timeframe": timeframe, "approved": approved,
        "quality": quality, "quality_score": quality_score,
        "confidence": confidence, "consensus": consensus,
        "entry_score": entry_score, "classification_label": classification_label,
        "reject_reason": reject_reason,
        "rvol_ok": rvol_ok, "adx_ok": adx_ok, "structure_ok": structure_ok,
        "entry_zone_ok": entry_zone_ok, "quality_ok": quality_ok,
        "consensus_ok": consensus_ok, "confidence_ok": confidence_ok,
        "kalman_ok": kalman_ok, "rr_ok": rr_ok,
        "rvol": rvol, "adx": adx, "structure_strength": structure_strength,
        "liquidity_score": liquidity_score, "risk_score": risk_score,
        "market_score": market_score, "take_profit_1": take_profit_1,
    }


def _report_with(decisions, total_assets=None, duration_ms=1000.0):
    r = DiagnosticReport()
    r.decisions = decisions
    r.total_assets = total_assets if total_assets is not None else len(decisions)
    r.duration_ms = duration_ms
    r.health = {"health_score": 80.0, "candles": len(decisions), "api": 100}
    r.bugs = []
    return r


def test_scanner_summary_reads_existing_fields_only():
    r = _report_with([_decision()], duration_ms=5000.0)
    summary = ar.build_scanner_summary(r)
    assert summary["exchange"] == "MEXC"
    assert summary["quantidade_moedas"] == 1
    assert summary["tempo_ms"] == 5000.0
    assert summary["erros"] == 0


def test_granular_funnel_is_a_true_funnel_non_increasing():
    decisions = [
        _decision(rvol_ok=True, adx_ok=True, structure_ok=True, entry_zone_ok=True, quality_ok=False),
        _decision(rvol_ok=True, adx_ok=False),
        _decision(rvol_ok=False),
    ]
    r = _report_with(decisions)
    funnel = ar.build_granular_funnel(decisions)
    counts = [stage["quantidade"] for stage in funnel]
    assert counts == sorted(counts, reverse=True), "funil deve ser nao-crescente"
    assert funnel[0]["estagio"] == "RVOL"
    assert funnel[0]["quantidade"] == 2  # 2 decisions com rvol_ok != None


def test_granular_funnel_aprovados_stage_present():
    decisions = [_decision(approved=True, rvol_ok=True, adx_ok=True, structure_ok=True,
                            entry_zone_ok=True, quality_ok=True, consensus_ok=True,
                            confidence_ok=True, kalman_ok=True, rr_ok=True)]
    funnel = ar.build_granular_funnel(decisions)
    assert funnel[-1]["estagio"] == "Aprovados"
    assert funnel[-1]["quantidade"] == 1


def test_top_near_approved_returns_up_to_min_count_sorted_by_quality():
    decisions = [_decision(symbol=f"A{i}USDT", quality=0.9 - i * 0.05, quality_ok=False)
                 for i in range(15)]
    result = ar.build_top_near_approved(decisions, min_count=10)
    assert len(result) == 10
    scores = [c["score"] for c in result]
    assert scores == sorted(scores, reverse=True)


def test_top_near_approved_excludes_approved_signals():
    decisions = [_decision(symbol="WINUSDT", approved=True, quality=0.99)]
    result = ar.build_top_near_approved(decisions)
    assert result == []


def test_delta_to_pass_finds_closest_failed_gate():
    d = _decision(quality_ok=False, quality=0.58, consensus_ok=False, consensus=0.3)
    near = ar._delta_to_pass(d)
    assert near is not None
    assert near[0] == "Quality"  # 0.60 - 0.58 = 0.02, menor que Consensus (0.70-0.3=0.4)


def test_per_asset_diagnostics_checklist_has_all_gates():
    d = _decision(rvol_ok=True, adx_ok=False)
    out = ar.build_per_asset_diagnostics([d])
    assert len(out) == 1
    checklist = out[0]["checklist"]
    assert checklist["RVOL"] is True
    assert checklist["ADX"] is False
    assert out[0]["status"] == "REPROVADO"


def test_per_asset_diagnostics_status_approved():
    d = _decision(approved=True)
    out = ar.build_per_asset_diagnostics([d])
    assert out[0]["status"] == "APROVADO"


def test_blocker_ranking_orders_by_frequency():
    decisions = [
        _decision(rvol_ok=False),
        _decision(rvol_ok=False),
        _decision(rvol_ok=True, adx_ok=False),
    ]
    ranking = ar.build_blocker_ranking(decisions)
    assert ranking[0]["motivo"] == "RVOL"
    assert ranking[0]["quantidade"] == 2
    assert ranking[0]["percentual"] == round(2 / 3 * 100, 1)


def test_blocker_ranking_empty_when_no_rejections():
    decisions = [_decision(approved=True)]
    assert ar.build_blocker_ranking(decisions) == []


def test_market_health_classification_thresholds():
    r = _report_with([_decision()])
    r.health = {"health_score": 90.0}
    mh = ar.build_market_health(r.decisions, r)
    assert mh["classificacao"] == "Excelente"

    r.health = {"health_score": 20.0}
    mh = ar.build_market_health(r.decisions, r)
    assert mh["classificacao"] == "Critica"


def test_auto_recommendation_mentions_top_blocker():
    ranking = [{"motivo": "Quality", "quantidade": 5, "percentual": 80.0}]
    rec = ar.build_auto_recommendation(ranking, {"classificacao": "Boa"})
    assert "Quality" in rec


def test_auto_recommendation_healthy_when_no_blockers():
    rec = ar.build_auto_recommendation([], {"classificacao": "Excelente"})
    assert "saudavel" in rec.lower()


def test_executive_summary_max_five_lines():
    scanner_summary = {"quantidade_moedas": 300, "exchange": "MEXC", "erros": 0}
    market_health = {"classificacao": "Boa", "health_score": 75.0}
    blockers = [{"motivo": "Quality", "quantidade": 10, "percentual": 90.0}]
    summary = ar.build_executive_summary(scanner_summary, market_health, blockers)
    assert len(summary.split("\n")) <= 5


def test_general_stats_approval_rate():
    decisions = [_decision(approved=True), _decision(approved=False), _decision(approved=False)]
    r = _report_with(decisions, total_assets=3, duration_ms=3000.0)
    stats = ar.build_general_stats(decisions, r)
    assert stats["taxa_aprovacao"] == round(1 / 3 * 100, 2)
    assert stats["taxa_reprovacao"] == round(2 / 3 * 100, 2)
    assert stats["ativos_por_minuto"] > 0


def test_general_stats_empty_decisions_no_crash():
    r = _report_with([], total_assets=0, duration_ms=0.0)
    stats = ar.build_general_stats([], r)
    assert stats["taxa_aprovacao"] == 0.0


def test_build_advanced_report_returns_all_eleven_blocks():
    decisions = [_decision(rvol_ok=True, adx_ok=False), _decision(approved=True, rvol_ok=True,
                 adx_ok=True, structure_ok=True, entry_zone_ok=True, quality_ok=True,
                 consensus_ok=True, confidence_ok=True, kalman_ok=True, rr_ok=True)]
    r = _report_with(decisions)
    data = ar.build_advanced_report(r)
    expected_keys = {
        "resumo_ciclo", "resumo_scanner", "funil_granular", "top_quase_aprovados",
        "diagnostico_por_ativo", "ranking_bloqueadores", "saude_mercado",
        "recomendacao_automatica", "resumo_executivo", "estatisticas_gerais",
        "mercado_estatisticas",
    }
    assert expected_keys.issubset(data.keys())


def test_build_advanced_report_does_not_mutate_input_decisions():
    d = _decision(rvol_ok=True)
    original = dict(d)
    r = _report_with([d])
    ar.build_advanced_report(r)
    assert d == original, "modulo de diagnostico deve ser somente-leitura"


def test_diagnostic_engine_record_decision_appends_to_report():
    from ENGINE.diagnostic.engine import DiagnosticEngine
    eng = DiagnosticEngine()
    eng.start_cycle(1)
    eng.record_decision({"symbol": "ETHUSDT", "approved": True})
    report = eng.end_cycle(100.0)
    assert len(report.decisions) == 1
    assert report.decisions[0]["symbol"] == "ETHUSDT"


# =============================================================================
# RFC V6.7 — Diagnóstico Baseado Apenas nas Moedas Escaneadas
# =============================================================================

def test_cycle_summary_has_all_fields():
    r = _report_with([_decision(approved=True, quality=0.85)])
    r.pipeline_funnel = {"candles": 10, "decision_engine": 5}
    r.total_assets = 10
    cs = ar.build_cycle_summary(r)
    assert cs["exchange"] == "MEXC"
    assert cs["validas"] == 10
    assert cs["escaneadas"] == 1
    assert cs["aprovadas"] == 1
    assert cs["reprovadas"] == 0
    assert cs["taxa_aprovacao"] == 100.0
    assert "score_medio" in cs
    assert "qualidade_media" in cs
    assert "conviccao_media" in cs
    assert "eficiencia_scanner" in cs
    assert "taxa_conversao" in cs
    assert "taxa_rejeicao" in cs


def test_cycle_summary_empty_decisions_returns_message():
    r = _report_with([])
    cs = ar.build_cycle_summary(r)
    assert "mensagem" in cs
    assert "suficientes" in cs["mensagem"].lower()


def test_cycle_summary_approval_rate():
    decisions = [
        _decision(approved=True, quality=0.85),
        _decision(approved=True, quality=0.75),
        _decision(approved=False, quality=0.50),
    ]
    r = _report_with(decisions, total_assets=100)
    cs = ar.build_cycle_summary(r)
    assert cs["validas"] == 100
    assert cs["escaneadas"] == 3
    assert cs["aprovadas"] == 2
    assert cs["reprovadas"] == 1
    assert cs["taxa_aprovacao"] == round(2 / 3 * 100, 1)
    assert cs["eficiencia_scanner"] == round(3 / 100 * 100, 1)


def test_cycle_summary_efficiency_metrics():
    r = _report_with(
        [_decision(approved=True), _decision(approved=False), _decision(approved=False)],
        total_assets=50,
    )
    cs = ar.build_cycle_summary(r)
    assert cs["eficiencia_scanner"] == round(3 / 50 * 100, 1)
    assert cs["taxa_conversao"] == round(1 / 3 * 100, 1)
    assert cs["taxa_rejeicao"] == round(2 / 3 * 100, 1)


def test_cycle_summary_averages_use_decisions_only():
    decisions = [
        _decision(approved=True, quality=0.90, quality_score=0.85, confidence=0.80),
        _decision(approved=False, quality=0.70, quality_score=0.65, confidence=0.60),
    ]
    r = _report_with(decisions, total_assets=100)
    cs = ar.build_cycle_summary(r)
    # quality: 0.90*100=90, 0.70*100=70 => avg=(90+70)/2=80.0
    # quality_score: 0.85*100=85, 0.65*100=65 => avg=(85+65)/2=75.0
    # confidence: 0.80*100=80, 0.60*100=60 => avg=(80+60)/2=70.0
    assert cs["score_medio"] == 80.0
    assert cs["qualidade_media"] == 75.0
    assert cs["conviccao_media"] == 70.0


def test_general_stats_denominator_is_decisions_not_total_assets():
    """RFC V6.7: tempo_medio_por_ativo_ms e ativos_por_minuto usam
    len(decisions), nao report.total_assets."""
    decisions = [_decision(approved=True) for _ in range(10)]
    r = _report_with(decisions, total_assets=100, duration_ms=60000.0)
    stats = ar.build_general_stats(decisions, r)
    # tempo_medio = 60000/10 = 6000.0 (nao 60000/100=600.0)
    assert stats["tempo_medio_por_ativo_ms"] == 6000.0
    # duration_min=1.0, ativos_por_min=10/1.0=10.0
    assert stats["ativos_por_minuto"] == 10.0


def test_market_statistics_computes_averages_from_scanned_pairs():
    decisions = [_decision(symbol="BTCUSDT"), _decision(symbol="ETHUSDT")]
    r = _report_with(decisions)
    r.indicators = {
        "BTCUSDT": {"rsi": 55.0, "adx": 30.0, "rvol": 1.5, "atr_percent": 2.0},
        "ETHUSDT": {"rsi": 45.0, "adx": 25.0, "rvol": 0.8, "atr_percent": 1.5},
        "SOLUSDT": {"rsi": 60.0, "adx": 35.0, "rvol": 2.0, "atr_percent": 3.0},  # nao escaneado
    }
    ms = ar.build_market_statistics(r)
    assert ms["rsi_medio"] == round((55.0 + 45.0) / 2, 1)
    assert ms["adx_medio"] == round((30.0 + 25.0) / 2, 1)
    assert ms["rvol_medio"] == round((1.5 + 0.8) / 2, 1)
    assert ms["atr_medio"] == round((2.0 + 1.5) / 2, 1)


def test_market_statistics_empty_decisions_returns_message():
    r = _report_with([])
    ms = ar.build_market_statistics(r)
    assert "mensagem" in ms


def test_market_statistics_no_indicators_for_scanned_pairs():
    decisions = [_decision(symbol="BTCUSDT")]
    r = _report_with(decisions)
    r.indicators = {"SOLUSDT": {"rsi": 50.0}}
    ms = ar.build_market_statistics(r)
    assert "mensagem" in ms


def test_advanced_report_empty_decisions_returns_minimal_structure():
    r = _report_with([], total_assets=100, duration_ms=5000.0)
    data = ar.build_advanced_report(r)
    assert "resumo_ciclo" in data
    assert "mensagem" in data["resumo_ciclo"]
    assert "resumo_scanner" in data
    assert data["resumo_scanner"]["quantidade_moedas"] == 100
    assert "mercado_estatisticas" in data


# =============================================================================
# RFC V26.2 — Contrato estavel de build_advanced_report() + flow_trace
# =============================================================================

_FULL_CONTRACT_KEYS = {
    "resumo_ciclo", "resumo_scanner", "funil_granular", "top_quase_aprovados",
    "diagnostico_por_ativo", "ranking_bloqueadores", "saude_mercado",
    "recomendacao_automatica", "resumo_executivo", "estatisticas_gerais",
    "mercado_estatisticas", "flow_trace", "metadata", "timestamp",
}


def test_advanced_report_empty_decisions_has_full_contract_no_keyerror():
    """Regressao do bug original: main.py acessa advanced['resumo_executivo']
    incondicionalmente — isso nao pode lancar KeyError quando decisions
    esta vazio, e o contrato deve ser identico ao caso com candidatos."""
    r = _report_with([], total_assets=592, duration_ms=5000.0)
    data = ar.build_advanced_report(r)
    assert _FULL_CONTRACT_KEYS.issubset(data.keys())
    assert isinstance(data["resumo_executivo"], str) and data["resumo_executivo"]


def test_advanced_report_non_empty_decisions_also_has_full_contract():
    decisions = [_decision(rvol_ok=True, adx_ok=False), _decision(approved=True, rvol_ok=True,
                 adx_ok=True, structure_ok=True, entry_zone_ok=True, quality_ok=True,
                 consensus_ok=True, confidence_ok=True, kalman_ok=True, rr_ok=True)]
    r = _report_with(decisions)
    data = ar.build_advanced_report(r)
    assert _FULL_CONTRACT_KEYS.issubset(data.keys())


def test_advanced_report_empty_decisions_executive_summary_is_accurate():
    """RFC V26.2: proibido usar mensagens genericas ('Scanner saudavel',
    'Nenhum bloqueador dominante') quando na verdade nenhum candidato
    chegou ao Decision Engine."""
    r = _report_with([], total_assets=592, duration_ms=5000.0)
    data = ar.build_advanced_report(r)
    resumo = data["resumo_executivo"].lower()
    assert "saudavel" not in resumo
    assert "nenhum bloqueador dominante" not in resumo
    assert "decision engine" in resumo
    assert "592" in data["resumo_executivo"]


def test_build_flow_trace_marks_stage_as_blocked_when_funnel_drops_to_zero():
    r = _report_with([], total_assets=100, duration_ms=1000.0)
    r.pipeline_funnel = {"candles": 100, "indicadores": 100, "estrutura": 0}
    trace = ar.build_flow_trace(r)
    by_stage = {t["estagio"]: t for t in trace}
    assert by_stage["Candles/API"]["status"] == "executado"
    assert by_stage["Estrutura"]["status"] == "bloqueado"
    assert by_stage["Entry Zone"]["status"] == "nao_executado"


def test_advanced_report_empty_decisions_names_interruption_stage():
    r = _report_with([], total_assets=100, duration_ms=1000.0)
    r.pipeline_funnel = {"candles": 100, "indicadores": 100, "estrutura": 0}
    data = ar.build_advanced_report(r)
    assert "Estrutura" in data["resumo_executivo"]
    assert "Estrutura" in data["recomendacao_automatica"]


def test_advanced_report_metadata_and_timestamp_present():
    r = _report_with([_decision()], total_assets=1)
    r.cycle_number = 42
    data = ar.build_advanced_report(r)
    assert data["metadata"]["cycle_number"] == 42
    assert data["metadata"]["decisions_count"] == 1
    assert data["timestamp"]
