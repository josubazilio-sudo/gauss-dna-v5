import time
import pytest
from ENGINE.analytics.baseline_monitor import (
    BaselineRegistry, BaselineAnalyzer, BaselineReporter,
    CycleSnapshot, ParameterChange,
)


class TestBaselineRegistry:
    def test_record_cycle_updates_history(self):
        reg = BaselineRegistry()
        snap = CycleSnapshot(cycle=1, timestamp=time.time(),
                             total_analyzed=100, total_approved=5,
                             approval_rate=5.0,
                             gate_percentages={"CONSENSO": 40.0},
                             gate_counts={"CONSENSO": 38})
        reg.record_cycle(snap)
        assert len(reg.cycles) == 1
        assert reg.cycles[0].cycle == 1

    def test_cycles_24h_filters_by_time(self):
        reg = BaselineRegistry()
        old = time.time() - 90000
        reg.record_cycle(CycleSnapshot(cycle=1, timestamp=old,
                         gate_percentages={}, gate_counts={}))
        reg.record_cycle(CycleSnapshot(cycle=2, timestamp=time.time(),
                         gate_percentages={}, gate_counts={}))
        assert len(reg.cycles) == 2
        assert len(reg.cycles_24h) == 1
        assert reg.cycles_24h[0].cycle == 2

    def test_cycles_7d_respects_deque_maxlen(self):
        reg = BaselineRegistry(window_7d=10)
        for i in range(15):
            reg.record_cycle(CycleSnapshot(cycle=i, timestamp=time.time(),
                             gate_percentages={}, gate_counts={}))
        assert len(reg.cycles) == 10

    def test_get_gate_trend_normal(self):
        reg = BaselineRegistry()
        now = time.time()
        for i in range(10):
            reg.record_cycle(CycleSnapshot(cycle=i, timestamp=now + i,
                             gate_percentages={"CONSENSO": 30.0 + i * 0.5},
                             gate_counts={"CONSENSO": 10}))
        trend = reg.get_gate_trend("CONSENSO")
        assert trend["status"] == "normal"

    def test_get_gate_trend_anormal(self):
        reg = BaselineRegistry()
        now = time.time()
        for i in range(10):
            pct = 20.0 if i < 5 else 70.0
            reg.record_cycle(CycleSnapshot(cycle=i, timestamp=now + i,
                             gate_percentages={"EXAUSTAO": pct},
                             gate_counts={"EXAUSTAO": int(pct)}))
        trend = reg.get_gate_trend("EXAUSTAO")
        assert trend["status"] == "anormal"
        assert trend["delta_pp"] >= 25

    def test_get_gate_trend_sem_dados(self):
        reg = BaselineRegistry()
        trend = reg.get_gate_trend("NONE")
        assert trend["status"] == "sem_dados_suficientes"

    def test_record_change_appends(self):
        reg = BaselineRegistry()
        reg.record_change("THRESHOLD", 0.55, 0.50, "Test", "RFC V99", 1)
        assert len(reg.changes) == 1
        assert reg.changes[0].param_name == "THRESHOLD"
        assert reg.changes[0].validated == False

    def test_changes_pending_validation(self):
        reg = BaselineRegistry()
        reg.record_change("A", 1, 2, "T", "V1", 1)
        reg.changes[0].validated = True
        reg.record_change("B", 3, 4, "T", "V1", 2)
        assert len(reg.changes_pending_validation) == 1
        assert reg.changes_pending_validation[0].param_name == "B"

    def test_summary_stats_empty(self):
        reg = BaselineRegistry()
        stats = reg.get_summary_stats()
        assert stats == {}


class TestBaselineAnalyzer:
    def _registry_with_data(self):
        reg = BaselineRegistry()
        base = time.time()
        for i in range(10):
            consenso_pct = round(25.0 + i * (19.0 / 9), 2)
            exaustao_pct = round(35.0 - i * (15.0 / 9), 2)
            reg.record_cycle(CycleSnapshot(
                cycle=i, timestamp=base - 3000 + i * 333,
                total_analyzed=100, total_approved=3 if i < 7 else 8,
                total_rejected=97 if i < 7 else 92,
                approval_rate=3.0 if i < 7 else 8.0,
                avg_quality=0.55 if i < 7 else 0.65,
                avg_confidence=0.60, avg_consensus=0.45,
                avg_rr=2.2,
                gate_percentages={
                    "CONSENSO": consenso_pct,
                    "EXAUSTAO": exaustao_pct,
                    "QUALIDADE": 12.0,
                    "OUTROS": 3.0,
                },
                gate_counts={
                    "CONSENSO": int(consenso_pct),
                    "EXAUSTAO": int(exaustao_pct),
                    "QUALIDADE": 12,
                    "OUTROS": 3,
                },
            ))
        return reg

    def test_top_rejection_gates_ordered(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        top = analyzer.top_rejection_gates(reg)
        assert len(top) > 0
        assert top[0]["gate"] == "CONSENSO"

    def test_gate_greatest_growth(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        growth = analyzer.gate_with_greatest_growth(reg)
        assert growth is not None

    def test_gate_greatest_reduction(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        reduction = analyzer.gate_with_greatest_reduction(reg)
        assert reduction is not None

    def test_potential_bottlenecks(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        bottlenecks = analyzer.potential_bottlenecks(reg)
        assert any(b["gate"] == "CONSENSO" for b in bottlenecks)

    def test_potential_bugs_empty_with_small_deltas(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        bugs = analyzer.potential_bugs(reg)
        assert len(bugs) == 0

    def test_potential_bugs_detects_large_delta(self):
        reg = BaselineRegistry()
        now = time.time()
        for i in range(10):
            pct = 10.0 if i < 5 else 70.0
            reg.record_cycle(CycleSnapshot(
                cycle=i, timestamp=now + i,
                gate_percentages={"BUGADO": pct},
                gate_counts={"BUGADO": int(pct)},
            ))
        analyzer = BaselineAnalyzer()
        bugs = analyzer.potential_bugs(reg)
        assert len(bugs) >= 1
        assert bugs[0]["gate"] == "BUGADO"

    def test_change_impact_dados_insuficientes(self):
        reg = BaselineRegistry()
        change = ParameterChange(param_name="TEST", old_value=1, new_value=2,
                                 timestamp=time.time() - 43200, cycle_applied=1)
        analyzer = BaselineAnalyzer()
        result = analyzer.change_impact(reg, change)
        assert result["conclusion"] == "dados_insuficientes"


class TestBaselineReporter:
    def _setup(self):
        reg = BaselineRegistry()
        base = time.time()
        for i in range(10):
            reg.record_cycle(CycleSnapshot(
                cycle=i, timestamp=base - 3000 + i * 333,
                total_analyzed=100, total_approved=3,
                approval_rate=3.0,
                avg_quality=0.55, avg_confidence=0.60,
                avg_consensus=0.45, avg_rr=2.2,
                gate_percentages={"CONSENSO": 44.0, "EXAUSTAO": 29.0},
                gate_counts={"CONSENSO": 44, "EXAUSTAO": 29},
            ))
        reg.record_change("TEST", 0.55, 0.50, "Test", "RFC V99", 1)
        return reg

    def test_build_30min_report_structure(self):
        reg = self._setup()
        analyzer = BaselineAnalyzer()
        reporter = BaselineReporter(analyzer)
        report = reporter.build_30min_report(reg)
        assert "scanner_health" in report
        assert "total_analyzed_24h" in report
        assert "top_rejection_gates" in report
        assert "potential_bottlenecks" in report
        assert "potential_bugs" in report
        assert "pending_validations" in report

    def test_format_30min_log_includes_key_fields(self):
        reg = self._setup()
        analyzer = BaselineAnalyzer()
        reporter = BaselineReporter(analyzer)
        report = reporter.build_30min_report(reg)
        text = reporter.format_30min_log(report)
        assert "RELATORIO 30 MINUTOS" in text
        assert "CONSENSO" in text
        assert "EXAUSTAO" in text

    def test_format_30min_telegram_includes_emojis(self):
        reg = self._setup()
        analyzer = BaselineAnalyzer()
        reporter = BaselineReporter(analyzer)
        report = reporter.build_30min_report(reg)
        text = reporter.format_30min_telegram(report)
        assert "QuantOS" in text
        assert "Top Rejeicoes" in text

    def test_build_change_report_includes_conclusion(self):
        reg = self._setup()
        analyzer = BaselineAnalyzer()
        reporter = BaselineReporter(analyzer)
        change = reg.changes[0]
        impact = analyzer.change_impact(reg, change)
        text = reporter.build_change_report(change, impact)
        assert change.param_name in text
        assert "Conclusao" in text
