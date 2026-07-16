"""RFC V25.5 — Diagnostico Rapido Inteligente (Fast Diagnostic).

Cobre a analise pura (build_fast_diagnostic), a baseline movel
(DiagnosticBaseline) e a formatacao de log — sem tocar em main.py
(integracao coberta por inspecao de codigo em um teste dedicado).
"""
import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.diagnostic.fast_diagnostic import (
    DiagnosticBaseline, build_fast_diagnostic, format_fast_diagnostic_log,
    GARGALO_PCT_THRESHOLD, BUG_DELTA_THRESHOLD, ZERO_SIGNAL_STREAK_ALERT,
    GATE_CRITICAL_PCT_OF_TOTAL, MIN_BASELINE_SAMPLES,
)


def _summary(total=100, approved=10, gate_pct=None, gate_counts=None):
    gate_pct = gate_pct or {}
    gate_counts = gate_counts or {}
    rejected = total - approved
    ranking = sorted(
        [(g, gate_counts.get(g, 0), p) for g, p in gate_pct.items()],
        key=lambda x: -x[2],
    )
    return {
        "total_analyzed": total, "total_approved": approved, "total_rejected": rejected,
        "approval_rate": round(approved / total * 100, 1) if total else 0.0,
        "gate_percentages": gate_pct, "gate_counts": gate_counts, "ranking": ranking,
    }


class TestDiagnosticBaseline:
    def test_no_average_before_min_samples(self):
        b = DiagnosticBaseline()
        b.update({"RVOL": 40.0}, 10.0)
        assert b.average_gate_pct("RVOL") is None
        assert b.average_approval_rate() is None

    def test_average_after_min_samples(self):
        b = DiagnosticBaseline()
        for _ in range(MIN_BASELINE_SAMPLES):
            b.update({"Kalman": 40.0}, 10.0)
        assert b.average_gate_pct("Kalman") == 40.0
        assert b.average_approval_rate() == 10.0

    def test_missing_gate_counts_as_zero(self):
        b = DiagnosticBaseline()
        b.update({"Kalman": 100.0}, 5.0)
        b.update({"Kalman": 100.0}, 5.0)
        b.update({}, 5.0)  # Kalman ausente neste ciclo -> conta como 0
        assert b.average_gate_pct("Kalman") == (100 + 100 + 0) / 3


class TestScannerSaudavel:
    def test_healthy_cycle_no_alert(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=100, approved=10, gate_pct={"RVOL": 20.0}, gate_counts={"RVOL": 18})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.scanner_saudavel
        assert result.alerta_imediato is None

    def test_gargalo_detected(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=100, approved=5, gate_pct={"Kalman": 60.0}, gate_counts={"Kalman": 57})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert not result.scanner_saudavel
        assert any("Kalman" in g for g in result.gargalos)


class TestTopMotivos:
    def test_top_5_limited(self):
        baseline = DiagnosticBaseline()
        gate_pct = {f"Gate{i}": float(30 - i) for i in range(8)}
        gate_counts = {k: 10 for k in gate_pct}
        summary = _summary(total=200, approved=20, gate_pct=gate_pct, gate_counts=gate_counts)
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert len(result.top_motivos) == 5


class TestBugDetection:
    def test_no_bug_without_baseline_history(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=100, approved=1, gate_pct={"Kalman": 97.0}, gate_counts={"Kalman": 99})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.bug_suspeito is None  # sem historico, nao ha baseline

    def test_bug_detected_after_baseline_established(self):
        baseline = DiagnosticBaseline()
        for _ in range(MIN_BASELINE_SAMPLES):
            baseline.update({"Kalman": 42.0}, 8.0)
        summary = _summary(total=100, approved=1, gate_pct={"Kalman": 97.0}, gate_counts={"Kalman": 99})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.bug_suspeito is not None
        assert result.bug_suspeito["gate"] == "Kalman"
        assert result.bug_suspeito["media_historica"] == 42.0
        assert result.bug_suspeito["confianca"] >= 90.0

    def test_small_deviation_not_flagged_as_bug(self):
        baseline = DiagnosticBaseline()
        for _ in range(MIN_BASELINE_SAMPLES):
            baseline.update({"RVOL": 30.0}, 10.0)
        summary = _summary(total=100, approved=10, gate_pct={"RVOL": 35.0}, gate_counts={"RVOL": 30})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.bug_suspeito is None


class TestAlertaImediato:
    def test_zero_signal_streak_triggers_alert(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=100, approved=0, gate_pct={"RVOL": 20.0}, gate_counts={"RVOL": 20})
        result = build_fast_diagnostic(
            summary, baseline, zero_signal_streak=ZERO_SIGNAL_STREAK_ALERT,
        )
        assert result.alerta_imediato is not None
        assert "ciclos consecutivos" in result.alerta_imediato

    def test_gate_above_90_of_total_triggers_alert(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=100, approved=1, gate_pct={"Kalman": 99.0}, gate_counts={"Kalman": 95})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.alerta_imediato is not None
        assert "Kalman" in result.alerta_imediato

    def test_approval_drop_triggers_alert(self):
        baseline = DiagnosticBaseline()
        for _ in range(MIN_BASELINE_SAMPLES):
            baseline.update({"RVOL": 20.0}, 20.0)
        summary = _summary(total=100, approved=1, gate_pct={"RVOL": 20.0}, gate_counts={"RVOL": 20})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.alerta_imediato is not None
        assert "aprovacao" in result.alerta_imediato.lower()

    def test_silent_drop_triggers_alert(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=100, approved=10, gate_pct={"RVOL": 10.0}, gate_counts={"RVOL": 10})
        result = build_fast_diagnostic(
            summary, baseline, zero_signal_streak=0, silent_drop_pct=20.0,
        )
        assert result.alerta_imediato is not None
        assert "API" in result.alerta_imediato or "candles" in result.alerta_imediato.lower()


class TestCicloVazioEAmostraInsuficiente:
    """RFC V26.1: ciclo vazio (0 ativos analisados) nunca gera alerta nem
    entra em comparacao com a baseline; amostra pequena (<30) nunca
    dispara alerta de queda abrupta/bug suspeito baseado em media
    historica."""

    def test_empty_cycle_never_alerts_even_with_established_baseline(self):
        baseline = DiagnosticBaseline()
        for _ in range(MIN_BASELINE_SAMPLES):
            baseline.update({"RVOL": 20.0}, 50.0)  # baseline com aprovacao alta
        summary = _summary(total=0, approved=0)
        result = build_fast_diagnostic(
            summary, baseline, zero_signal_streak=ZERO_SIGNAL_STREAK_ALERT,
        )
        assert result.ciclo_vazio is True
        assert result.alerta_imediato is None
        assert result.scanner_saudavel is True
        assert result.analisados == 0

    def test_empty_cycle_does_not_call_bug_detection(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=0, approved=0)
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.bug_suspeito is None
        assert result.gargalos == []

    def test_small_sample_skips_approval_drop_alert(self):
        baseline = DiagnosticBaseline()
        for _ in range(MIN_BASELINE_SAMPLES):
            baseline.update({"RVOL": 20.0}, 50.0)
        summary = _summary(total=5, approved=0, gate_pct={"RVOL": 20.0}, gate_counts={"RVOL": 4})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.amostra_insuficiente is True
        assert result.alerta_imediato is None or "aprovacao" not in result.alerta_imediato.lower()

    def test_small_sample_skips_bug_detection(self):
        baseline = DiagnosticBaseline()
        for _ in range(MIN_BASELINE_SAMPLES):
            baseline.update({"Kalman": 10.0}, 20.0)
        summary = _summary(total=10, approved=1, gate_pct={"Kalman": 90.0}, gate_counts={"Kalman": 8})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.bug_suspeito is None

    def test_sample_at_minimum_threshold_runs_normal_comparisons(self):
        baseline = DiagnosticBaseline()
        for _ in range(MIN_BASELINE_SAMPLES):
            baseline.update({"RVOL": 20.0}, 50.0)
        summary = _summary(total=MIN_BASELINE_SAMPLES + 27, approved=1,
                            gate_pct={"RVOL": 20.0}, gate_counts={"RVOL": 6})
        result = build_fast_diagnostic(summary, baseline, zero_signal_streak=0)
        assert result.amostra_insuficiente is False


class TestMarketClassification:
    def test_forte_high_adx_directional(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=50, approved=5)
        result = build_fast_diagnostic(summary, baseline, 0, avg_adx=30.0, regime_mode="uptrend")
        assert result.mercado == "Forte"

    def test_fraco_low_adx(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=50, approved=5)
        result = build_fast_diagnostic(summary, baseline, 0, avg_adx=10.0, regime_mode="ranging")
        assert result.mercado == "Fraco"

    def test_lateral_mid_adx(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=50, approved=5)
        result = build_fast_diagnostic(summary, baseline, 0, avg_adx=20.0, regime_mode="ranging")
        assert result.mercado == "Lateral"


class TestFormatLog:
    def test_log_includes_key_fields(self):
        baseline = DiagnosticBaseline()
        summary = _summary(total=100, approved=10, gate_pct={"RVOL": 20.0}, gate_counts={"RVOL": 18})
        result = build_fast_diagnostic(summary, baseline, 0)
        text = format_fast_diagnostic_log(result)
        assert "Scanner saudavel: SIM" in text
        assert "Ativos analisados: 100" in text
        assert "RVOL" in text


class TestMainPyIntegration:
    """Inspecao de codigo: confirma que o fast diagnostic roda a cada ciclo,
    nunca derruba o ciclo principal (fail-safe). RFC V26.X: alerta imediato
    fica so no log — Telegram recebe apenas o sinal e o diagnostico unico
    diario (RCDE), sem alertas avulsos."""

    def test_wired_into_cycle_end_with_failsafe(self):
        import main
        source = inspect.getsource(main)
        assert "build_fast_diagnostic(" in source
        assert "self._telegram.send_diagnostic(fast_diag.alerta_imediato)" not in source
        assert 'log.info("FASTDIAG| ALERTA (so log): %s"' in source
        # A chamada deve estar protegida por try/except (fail-safe).
        idx = source.index("RFC V25.5: Diagnostico Rapido Inteligente (Fast Diagnostic)")
        block = source[idx:idx + 4500]
        assert "except Exception as e" in block
        assert "FastDiagnostic: erro ao gerar diagnostico rapido" in block or "RFC_V25_6: erro ao gerar diagnostico" in block
