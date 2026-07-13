import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ENGINE.diagnostics.decision_diagnostics import (
    DecisionDiagnostics,
    FilterRecord,
    IndicatorValidation,
    DecisionDiagnosticsReport,
    _classify_rejection,
    _extract_value,
    FILTER_MAP,
    INDICATOR_RANGES,
)


class TestClassifyRejection:
    def test_rvol(self):
        assert _classify_rejection("RVOL 0.46 < 0.7") == "RVOL"
        assert _classify_rejection("rvol too low") == "RVOL"

    def test_adx(self):
        assert _classify_rejection("ADX 17.8 < 25") == "ADX"
        assert _classify_rejection("adx_insufficient") == "ADX"

    def test_exaustao(self):
        assert _classify_rejection("Exaustao detectada (score=25)") == "Exaustão"

    def test_entry_zone(self):
        assert _classify_rejection("Entry Zone FAIL (score 0.00 < 0.4)") == "Entry Zone"

    def test_consensus(self):
        assert _classify_rejection("Consenso multi-TF insuficiente (0.46 < 0.70)") == "Consenso"

    def test_kalman(self):
        assert _classify_rejection("Kalman DOWN incompativel com LONG") == "Kalman"

    def test_confidence(self):
        assert _classify_rejection("Confidence 0.60 < 0.75") == "Confiança"
        assert _classify_rejection("Descalibracao Confianca-Qualidade") == "Descalibração"

    def test_rr(self):
        assert _classify_rejection("RR 1.5 abaixo do minimo 2.0") == "RR"

    def test_bos_choch(self):
        assert _classify_rejection("Sem BOS ou CHoCH confirmado") == "BOS/CHoCH"

    def test_estrutura(self):
        assert _classify_rejection("Forca estrutural 0.20 < 0.30") == "Estrutura"

    def test_quality(self):
        assert _classify_rejection("Quality 0.45 < 0.60") == "Quality Gate"

    def test_unknown(self):
        assert _classify_rejection("Algum motivo desconhecido") == "Outros"

    def test_none(self):
        assert _classify_rejection("") == "Desconhecido"


class TestExtractValue:
    def test_simple_number(self):
        assert _extract_value("RVOL 0.46 < 0.7") == 0.46

    def test_percentage(self):
        v = _extract_value("Votacao Ponderada 65% < 70%")
        assert v == 65.0 or v == 65

    def test_no_number(self):
        assert _extract_value("Sem BOS ou CHoCH confirmado") is None

    def test_multiple_numbers(self):
        assert _extract_value("Exaustao detectada (score=25): adx_fraco") == 25.0


class TestIndicatorValidation:
    def test_valid_indicator(self):
        iv = IndicatorValidation(
            name="rvol", value=1.5, expected_min=0.0, expected_max=10.0,
            status="OK"
        )
        assert iv.status == "OK"
        assert iv.name == "rvol"

    def test_suspeito(self):
        iv = IndicatorValidation(
            name="rvol", value=-0.1, expected_min=0.0, expected_max=10.0,
            status="Suspeito", note="Abaixo do minimo (0.0)"
        )
        assert iv.status == "Suspeito"


class TestDecisionDiagnostics:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.diag = DecisionDiagnostics(audit_dir=self.tmpdir)

    def test_start_cycle(self):
        self.diag.start_cycle(42)
        assert self.diag._cycle_number == 42
        assert len(self.diag._cycle_filters) == 0

    def test_record_filter_rejection(self):
        self.diag.start_cycle(1)
        self.diag.record_filter_rejection(
            filter_name="RVOL 0.46 < 0.7",
            asset="BTCUSDT", timeframe="1h", direction="LONG",
            value=0.46, threshold=0.70,
        )
        assert self.diag._cycle_filters["RVOL"] == 1

    def test_record_multiple_rejections(self):
        self.diag.start_cycle(1)
        for _ in range(5):
            self.diag.record_filter_rejection("Exaustao detectada", "BTCUSDT")
        for _ in range(3):
            self.diag.record_filter_rejection("RVOL 0.5 < 0.7", "ETHUSDT")
        assert self.diag._cycle_filters["Exaustão"] == 5
        assert self.diag._cycle_filters["RVOL"] == 3

    def test_record_indicator(self):
        self.diag.start_cycle(1)
        self.diag.record_indicator("rvol", 1.5, 0.0, 10.0)
        self.diag.record_indicator("adx", 15.0, 0.0, 100.0)
        sups = [iv for iv in self.diag._indicator_validations if iv.status == "Suspeito"]
        assert len(sups) == 0

        self.diag.record_indicator("rvol", -0.1, 0.0, 10.0)
        sups = [iv for iv in self.diag._indicator_validations if iv.status == "Suspeito"]
        assert len(sups) == 1
        assert sups[0].name == "rvol"

    def test_increment_analyzed(self):
        self.diag.start_cycle(1)
        self.diag.increment_analyzed()
        assert self.diag._total_analyzed == 1

    def test_increment_approved(self):
        self.diag.start_cycle(1)
        self.diag.increment_approved()
        assert self.diag._total_approved == 1

    def test_increment_rejected(self):
        self.diag.start_cycle(1)
        self.diag.increment_rejected()
        assert self.diag._total_rejected == 1

    def test_record_asset_indicators(self):
        self.diag.start_cycle(1)
        self.diag.record_asset_indicators("BTCUSDT", {
            "rvol": 1.5, "adx": 30.0, "atr_percent": 0.02,
            "rsi": 55.0, "volatility": 0.1,
        })
        assert "BTCUSDT" in self.diag._indicators_per_asset
        assert self.diag._indicators_per_asset["BTCUSDT"]["rvol"] == 1.5
        ok_count = sum(1 for iv in self.diag._indicator_validations if iv.status == "OK")
        assert ok_count > 0

    def test_end_cycle_report(self):
        self.diag.start_cycle(5)
        self.diag.increment_analyzed()
        self.diag.increment_analyzed()
        self.diag.increment_analyzed()
        self.diag.increment_approved()
        self.diag.record_filter_rejection("RVOL 0.3 < 0.7", "XRPUSDT", value=0.3, threshold=0.70)
        self.diag.record_filter_rejection("Exaustao detectada", "ADAUSDT", value=25.0, threshold=25.0)
        self.diag.record_filter_rejection("Exaustao detectada", "DOTUSDT", value=30.0, threshold=25.0)

        report = self.diag.end_cycle()

        assert report.cycle_number == 5
        assert report.total_analyzed == 3
        assert report.total_approved == 1
        assert report.total_rejected == 3
        assert report.filter_counts["RVOL"] == 1
        assert report.filter_counts["Exaustão"] == 2

    def test_ranking_order(self):
        self.diag.start_cycle(1)
        for _ in range(10):
            self.diag.record_filter_rejection("Exaustao", "A")
        for _ in range(5):
            self.diag.record_filter_rejection("RVOL", "B")
        for _ in range(2):
            self.diag.record_filter_rejection("Consenso", "C")

        report = self.diag.end_cycle()
        assert report.ranking[0][0] == "Exaustão"
        assert report.ranking[0][1] == 10
        assert report.ranking[1][0] == "RVOL"
        assert report.ranking[1][1] == 5

    def test_percentages(self):
        self.diag.start_cycle(1)
        for _ in range(6):
            self.diag.record_filter_rejection("Exaustao", "A")
        for _ in range(3):
            self.diag.record_filter_rejection("RVOL", "B")
        for _ in range(1):
            self.diag.record_filter_rejection("Consenso", "C")

        report = self.diag.end_cycle()
        assert report.filter_percentages["Exaustão"] == 60.0
        assert report.filter_percentages["RVOL"] == 30.0
        assert report.filter_percentages["Consenso"] == 10.0

    def test_report_text_generated(self):
        self.diag.start_cycle(1)
        self.diag.increment_analyzed()
        self.diag.increment_analyzed()
        self.diag.record_filter_rejection("RVOL 0.3 < 0.7", "BTCUSDT", value=0.3, threshold=0.70)

        report = self.diag.end_cycle()
        assert "QUANTOS DECISION REPORT" in report.report_text
        assert "CICLO 1" in report.report_text
        assert "RVOL" in report.report_text
        assert "60.0" in report.report_text or "100.0" in report.report_text

    def test_report_persisted_to_disk(self):
        self.diag.start_cycle(99)
        self.diag.increment_analyzed()
        self.diag.record_filter_rejection("Test", "BTCUSDT")

        report = self.diag.end_cycle()
        json_path = os.path.join(self.tmpdir, "decision_cycle_99.json")
        assert os.path.exists(json_path)
        with open(json_path) as f:
            data = json.load(f)
        assert data["cycle"] == 99
        assert data["total_analyzed"] == 1

    def test_get_last_report_text(self):
        assert "Nenhum relatorio" in self.diag.get_last_report_text()
        self.diag.start_cycle(1)
        self.diag.end_cycle()
        assert "QUANTOS DECISION REPORT" in self.diag.get_last_report_text()

    def test_get_summary_stats(self):
        assert self.diag.get_summary_stats() == {}
        self.diag.start_cycle(1)
        self.diag.increment_analyzed()
        self.diag.increment_analyzed()
        self.diag.increment_approved()
        self.diag.record_filter_rejection("Exaustao", "A")
        self.diag.end_cycle()
        stats = self.diag.get_summary_stats()
        assert stats["cycle"] == 1
        assert stats["analyzed"] == 2
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["approval_rate"] == 50.0

    def test_indicator_ranges(self):
        assert INDICATOR_RANGES["rvol"] == (0.0, 10.0)
        assert INDICATOR_RANGES["adx"] == (0.0, 100.0)
        assert INDICATOR_RANGES["rsi"] == (0.0, 100.0)
        assert INDICATOR_RANGES["consensus_score"] == (0.0, 1.0)

    def test_empty_cycle(self):
        self.diag.start_cycle(0)
        report = self.diag.end_cycle()
        assert report.total_analyzed == 0
        assert report.total_approved == 0
        assert report.total_rejected == 0

    def test_high_rejection_rate(self):
        self.diag.start_cycle(1)
        self.diag.increment_analyzed()
        self.diag.increment_analyzed()
        self.diag.increment_analyzed()
        self.diag.increment_analyzed()
        self.diag.increment_analyzed()
        self.diag.increment_approved()
        for _ in range(4):
            self.diag.record_filter_rejection("Exaustao", "A")

        report = self.diag.end_cycle()
        assert report.total_rejected == 4
        assert report.total_approved == 1
        assert "20.0%" in report.report_text or "20.0" in report.report_text


class TestFilterMap:
    def test_all_keys_exist(self):
        for key, label in FILTER_MAP:
            assert isinstance(key, str)
            assert isinstance(label, str)


class TestDecisionDiagnosticsReport:
    def test_default_values(self):
        r = DecisionDiagnosticsReport()
        assert r.total_analyzed == 0
        assert r.total_approved == 0
        assert r.total_rejected == 0
        assert r.filter_counts == {}
        assert r.ranking == []
