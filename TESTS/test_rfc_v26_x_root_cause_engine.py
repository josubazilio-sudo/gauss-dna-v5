"""RFC V26.X — Root Cause Diagnostic Engine (RCDE).

Testa exclusivamente logica pura sobre dados sinteticos — nao recalcula
indicadores, nao toca em Decision Engine/Scanner reais.
"""
import inspect

from ENGINE.analytics.root_cause_engine import (
    RootCauseDiagnosticEngine, GateOutcomeTracker, format_rcde_report,
    format_rcde_telegram, INVESTIGATION_STREAK, REGRESSION_DELTA_PCT,
)


def _decision(**gate_flags):
    fields = (
        "rvol_ok", "adx_ok", "structure_ok", "entry_zone_ok",
        "quality_ok", "consensus_ok", "confidence_ok", "kalman_ok", "rr_ok",
    )
    return {f: gate_flags.get(f) for f in fields}


def _cycle_all_pass(n=10):
    return [_decision(
        rvol_ok=True, adx_ok=True, structure_ok=True, entry_zone_ok=True,
        quality_ok=True, consensus_ok=True, confidence_ok=True,
        kalman_ok=True, rr_ok=True,
    ) for _ in range(n)]


def _cycle_adx_fails(n=10):
    return [_decision(rvol_ok=True, adx_ok=False) for _ in range(n)]


class TestGateOutcomeTracker:
    def test_record_cycle_returns_current_rate_per_gate(self):
        tracker = GateOutcomeTracker()
        rates = tracker.record_cycle(_cycle_all_pass(10))
        assert rates["ADX"] == 100.0

    def test_gate_never_evaluated_is_skipped_not_counted_as_fail(self):
        tracker = GateOutcomeTracker()
        decisions = [_decision(rvol_ok=False)]  # adx_ok=None: early exit no RVOL
        rates = tracker.record_cycle(decisions)
        assert "ADX" not in rates
        assert rates["RVOL"] == 0.0

    def test_historical_avg_none_without_data(self):
        tracker = GateOutcomeTracker()
        assert tracker.historical_avg("ADX") is None

    def test_crisis_streak_requires_consecutive_bad_cycles(self):
        tracker = GateOutcomeTracker()
        for _ in range(INVESTIGATION_STREAK - 1):
            tracker.record_cycle(_cycle_adx_fails())
        assert tracker.in_crisis_streak("ADX") is False
        tracker.record_cycle(_cycle_adx_fails())
        assert tracker.in_crisis_streak("ADX") is True

    def test_one_good_cycle_breaks_the_streak(self):
        tracker = GateOutcomeTracker()
        tracker.record_cycle(_cycle_adx_fails())
        tracker.record_cycle(_cycle_adx_fails())
        tracker.record_cycle(_cycle_all_pass())
        assert tracker.in_crisis_streak("ADX") is False


class TestRootCauseDiagnosticEngine:
    def test_no_investigation_when_gate_healthy(self):
        engine = RootCauseDiagnosticEngine()
        for _ in range(5):
            engine.record_cycle(_cycle_all_pass())
        report = engine.investigate(total_analyzed=50, total_approved=50)
        assert report.investigations == []
        assert report.overall_health_score == 100.0

    def test_investigation_triggers_after_streak(self):
        engine = RootCauseDiagnosticEngine()
        for _ in range(5):
            engine.record_cycle(_cycle_all_pass())
        for _ in range(INVESTIGATION_STREAK):
            engine.record_cycle(_cycle_adx_fails())
        report = engine.investigate(total_analyzed=10, total_approved=0)
        adx_investigations = [i for i in report.investigations if i.gate == "ADX"]
        assert len(adx_investigations) == 1
        inv = adx_investigations[0]
        assert inv.status == "ANORMAL"
        assert len(inv.hypotheses) == 5
        assert 0.0 <= inv.confidence <= 99.0
        assert inv.recommended_actions

    def test_hypotheses_ranked_by_stars_descending(self):
        engine = RootCauseDiagnosticEngine()
        for _ in range(5):
            engine.record_cycle(_cycle_all_pass())
        for _ in range(INVESTIGATION_STREAK):
            engine.record_cycle(_cycle_adx_fails())
        report = engine.investigate(total_analyzed=10, total_approved=0)
        inv = next(i for i in report.investigations if i.gate == "ADX")
        stars = [h.stars for h in inv.hypotheses]
        assert stars == sorted(stars, reverse=True)

    def test_lateral_market_boosts_market_hypothesis_for_adx(self):
        engine = RootCauseDiagnosticEngine()
        for _ in range(5):
            engine.record_cycle(_cycle_all_pass())
        for _ in range(INVESTIGATION_STREAK):
            engine.record_cycle(_cycle_adx_fails())
        report = engine.investigate(
            total_analyzed=10, total_approved=0, regime_mode="Lateral",
        )
        inv = next(i for i in report.investigations if i.gate == "ADX")
        market_hyp = next(h for h in inv.hypotheses if "mercado atipica" in h.cause.lower())
        default_report_investigation = engine.investigate(
            total_analyzed=10, total_approved=0, regime_mode="",
        )
        inv2 = next(i for i in default_report_investigation.investigations if i.gate == "ADX")
        market_hyp2 = next(h for h in inv2.hypotheses if "mercado atipica" in h.cause.lower())
        assert market_hyp.weight > market_hyp2.weight

    def test_regression_detected_when_drop_exceeds_threshold(self):
        engine = RootCauseDiagnosticEngine()
        for _ in range(10):
            engine.record_cycle(_cycle_all_pass())
        engine.record_cycle(_cycle_adx_fails())
        report = engine.investigate(total_analyzed=10, total_approved=0)
        regression = next((r for r in report.regressions if r.gate == "ADX"), None)
        assert regression is not None
        assert abs(regression.delta_pct) >= REGRESSION_DELTA_PCT
        assert regression.suspected_since

    def test_health_scores_reflect_current_cycle_rate(self):
        engine = RootCauseDiagnosticEngine()
        engine.record_cycle(_cycle_adx_fails())
        report = engine.investigate(total_analyzed=10, total_approved=0)
        assert report.health_scores["ADX"] == 0.0
        assert report.health_scores["RVOL"] == 100.0

    def test_low_sample_yields_lower_confidence_than_high_sample(self):
        engine_small = RootCauseDiagnosticEngine()
        engine_small.record_cycle(_cycle_all_pass(n=3))
        for _ in range(INVESTIGATION_STREAK):
            engine_small.record_cycle(_cycle_adx_fails(n=3))
        report_small = engine_small.investigate(total_analyzed=3, total_approved=0)

        engine_big = RootCauseDiagnosticEngine()
        engine_big.record_cycle(_cycle_all_pass(n=100))
        for _ in range(INVESTIGATION_STREAK):
            engine_big.record_cycle(_cycle_adx_fails(n=100))
        report_big = engine_big.investigate(total_analyzed=100, total_approved=0)

        inv_small = next(i for i in report_small.investigations if i.gate == "ADX")
        inv_big = next(i for i in report_big.investigations if i.gate == "ADX")
        assert inv_big.confidence >= inv_small.confidence


class TestFormatting:
    def test_format_report_includes_health_score_and_no_investigations_message(self):
        engine = RootCauseDiagnosticEngine()
        for _ in range(3):
            engine.record_cycle(_cycle_all_pass())
        report = engine.investigate(total_analyzed=30, total_approved=30)
        text = format_rcde_report(report)
        assert "HEALTH SCORE" in text
        assert "Sistema Geral" in text
        assert "Nenhum gate em investigacao" in text

    def test_format_report_includes_investigation_block(self):
        engine = RootCauseDiagnosticEngine()
        for _ in range(5):
            engine.record_cycle(_cycle_all_pass())
        for _ in range(INVESTIGATION_STREAK):
            engine.record_cycle(_cycle_adx_fails())
        report = engine.investigate(total_analyzed=10, total_approved=0)
        text = format_rcde_report(report)
        assert "ROOT CAUSE ANALYSIS" in text
        assert "ADX" in text
        assert "★" in text
        assert "ACAO RECOMENDADA" in text

    def test_telegram_format_is_healthy_when_no_investigations(self):
        engine = RootCauseDiagnosticEngine()
        for _ in range(3):
            engine.record_cycle(_cycle_all_pass())
        report = engine.investigate(total_analyzed=30, total_approved=30)
        text = format_rcde_telegram(report)
        assert "Diagnostico Diario" in text
        assert "Nenhum gate em investigacao" in text
        assert "SUSPEITA DE BUG" not in text

    def test_telegram_format_shows_investigation_summary(self):
        engine = RootCauseDiagnosticEngine()
        for _ in range(5):
            engine.record_cycle(_cycle_all_pass())
        for _ in range(INVESTIGATION_STREAK):
            engine.record_cycle(_cycle_adx_fails())
        report = engine.investigate(total_analyzed=10, total_approved=0)
        text = format_rcde_telegram(report)
        assert "Investigacoes ativas" in text
        assert "ADX" in text
        assert "Confianca" in text


class TestMainPyIntegration:
    """Inspecao de codigo: confirma que o RCDE roda a cada ciclo, que o
    Telegram so recebe o diagnostico consolidado uma vez por dia as 18h,
    e que nenhum resquicio do mecanismo antigo de alerta/envio condicional
    ficou para tras."""

    def test_rcde_wired_into_cycle_end(self):
        import main
        source = inspect.getsource(main)
        assert "self._rcde.record_cycle(report.decisions)" in source
        assert "self._rcde.investigate(" in source
        assert "format_rcde_report(rcde_report)" in source

    def test_telegram_diagnostic_gated_to_18h_once_per_day(self):
        import main
        source = inspect.getsource(main)
        idx = source.index("self._rcde.record_cycle(report.decisions)")
        block = source[idx:idx + 2000]
        assert "_now_dt.hour >= 18" in block
        assert "self._last_daily_diagnostic_date != _now_dt.date()" in block
        assert "send_diagnostic(format_rcde_telegram(rcde_report))" in block

    def test_rcde_block_is_failsafe(self):
        import main
        source = inspect.getsource(main)
        idx = source.index("self._rcde.record_cycle(report.decisions)")
        block = source[max(0, idx - 400):idx + 1700]
        assert "except Exception as e" in block
        assert "RCDE: erro ao gerar diagnostico de causa raiz" in block

    def test_no_dangling_should_send_telegram_usage(self):
        """RFC V26.X substituiu o envio condicional do relatorio de 30min
        (RFC V26.4) pelo diagnostico unico diario as 18h — should_send_telegram
        nao deve mais aparecer referenciado em main.py."""
        import main
        source = inspect.getsource(main)
        assert "should_send_telegram" not in source

    def test_no_standalone_change_validation_telegram_send(self):
        """Validacoes de mudanca de parametro (Calibration Engine)
        continuam so no log — nao viram mensagem avulsa no Telegram."""
        import main
        source = inspect.getsource(main)
        idx = source.index("CHANGE_VALIDATION|")
        block = source[max(0, idx - 300):idx + 100]
        assert "self._telegram.send_diagnostic(_msg)" not in block

    def test_duplicates_blocked_wired_from_signal_cache(self):
        import main
        source = inspect.getsource(main)
        idx = source.index("self._rcde.investigate(")
        block = source[idx:idx + 800]
        assert "duplicates_blocked=self._signal_cache.duplicate_blocked_count" in block


class TestDuplicatesBlockedField:
    def test_report_default_duplicates_blocked_is_zero(self):
        engine = RootCauseDiagnosticEngine()
        engine.record_cycle(_cycle_all_pass())
        report = engine.investigate(total_analyzed=10, total_approved=10)
        assert report.duplicates_blocked == 0

    def test_report_carries_duplicates_blocked_count(self):
        engine = RootCauseDiagnosticEngine()
        engine.record_cycle(_cycle_all_pass())
        report = engine.investigate(total_analyzed=10, total_approved=10, duplicates_blocked=4)
        assert report.duplicates_blocked == 4

    def test_log_format_shows_duplicates_blocked(self):
        engine = RootCauseDiagnosticEngine()
        engine.record_cycle(_cycle_all_pass())
        report = engine.investigate(total_analyzed=10, total_approved=10, duplicates_blocked=3)
        text = format_rcde_report(report)
        assert "Duplicados bloqueados: 3" in text

    def test_telegram_format_shows_duplicates_blocked(self):
        engine = RootCauseDiagnosticEngine()
        engine.record_cycle(_cycle_all_pass())
        report = engine.investigate(total_analyzed=10, total_approved=10, duplicates_blocked=7)
        text = format_rcde_telegram(report)
        assert "Duplicados bloqueados: 7" in text
