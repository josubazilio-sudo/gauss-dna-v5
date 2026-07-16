import unittest
import os
import tempfile
from unittest.mock import MagicMock, patch
from ENGINE.analytics.gate_calibration_engine import (
    GateCalibrationEngine, GateStats, GateObservation,
    GATES_CONFIGURATION, NUMERIC_GATES,
)


class MockSignal:
    def __init__(self, rvol=0.5, adx=25, atr_value=0.03,
                 structure_strength=0.5, kalman_confidence=0.7):
        self.rvol = rvol
        self.adx = adx
        self.atr_value = atr_value
        self.structure_strength = structure_strength
        self.kalman_confidence = kalman_confidence
        class MockScores:
            def __init__(self):
                self.flow_score = 0.5
                self.quality_score = 0.6
                self.institutional_score = 0.5
                self.liquidity_score = 0.7
                self.entry_score = 0.5
                self.consensus_score = 0.6
                self.conviction_score = 0.5
                self.timing_index = 0.5
        self.scores = MockScores()


class MockSignalDecision:
    def __init__(self, entry_score=0.6, quality=0.7, confidence=0.7,
                 consensus=0.6, liquidity_score=0.6, approved=True):
        self.entry_score = entry_score
        self.quality = quality
        self.confidence = confidence
        self.consensus = consensus
        self.liquidity_score = liquidity_score
        self.approved = approved
        self.direction = "LONG"
        self.structural_score = 0.5
        self.institutional_score = 0.5
        self.risk_reward = 2.5
        self.trend = "up"
        self.stop_loss = 0.0
        self.take_profit_1 = 0.0
        self.take_profit_2 = 0.0
        self.reject_reason = None


class TestGateCalibrationEngine(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.engine = GateCalibrationEngine(
            export_dir=self.tmpdir, min_samples=10, enabled=True,
        )

    def test_record_gate_observation(self):
        self.engine.start_cycle(1)
        self.engine.record_gate_observation(
            gate="RVOL", symbol="BTCUSDT", timeframe="1h",
            direction="LONG", value=0.45, threshold=0.50,
            result="REJECTED",
        )
        self.assertEqual(len(self.engine._observations["RVOL"]), 1)
        obs = self.engine._observations["RVOL"][0]
        self.assertEqual(obs.gate, "RVOL")
        self.assertEqual(obs.symbol, "BTCUSDT")
        self.assertEqual(obs.value, 0.45)
        self.assertTrue(obs.rejected)

    def test_record_signal_all_gates(self):
        self.engine.start_cycle(1)
        sig = MockSignal(rvol=0.48, adx=22)
        sd = MockSignalDecision(entry_score=0.5, quality=0.6, confidence=0.6,
                                 consensus=0.55, approved=False)
        self.engine.record_signal_all_gates(
            symbol="BTCUSDT", timeframe="1h", direction="LONG",
            result="REJECTED", signal=sig, sd=sd,
        )
        self.assertIn("RVOL", self.engine._observations)
        self.assertIn("ADX", self.engine._observations)
        self.assertIn("Entry Zone", self.engine._observations)
        self.assertGreaterEqual(len(self.engine._observations["RVOL"]), 1)

    def test_compute_stats_empty(self):
        stats = self.engine._compute_stats([])
        self.assertEqual(stats.total, 0)

    def test_compute_stats_basic(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = self.engine._compute_stats(values, threshold=3.0,
                                            total_signals=5, rejected_count=2)
        self.assertEqual(stats.total, 5)
        self.assertEqual(stats.mean, 3.0)
        self.assertEqual(stats.median, 3.0)
        self.assertEqual(stats.min_val, 1.0)
        self.assertEqual(stats.max_val, 5.0)
        self.assertEqual(stats.threshold, 3.0)
        self.assertEqual(stats.approved, 3)
        self.assertEqual(stats.rejected, 2)

    def test_compute_stats_percentiles(self):
        values = list(range(1, 101))
        stats = self.engine._compute_stats(values, threshold=50.0)
        self.assertAlmostEqual(stats.p10, 10.0, delta=1)
        self.assertAlmostEqual(stats.p25, 25.0, delta=1)
        self.assertAlmostEqual(stats.p50, 50.5, delta=1)
        self.assertAlmostEqual(stats.p75, 75.0, delta=1)
        self.assertAlmostEqual(stats.p90, 90.0, delta=1)
        self.assertAlmostEqual(stats.p95, 95.0, delta=1)

    def test_compute_stats_single_value(self):
        stats = self.engine._compute_stats([3.14], threshold=2.0,
                                            total_signals=1, rejected_count=0)
        self.assertEqual(stats.total, 1)
        self.assertEqual(stats.mean, 3.14)
        self.assertEqual(stats.median, 3.14)
        self.assertEqual(stats.min_val, 3.14)
        self.assertEqual(stats.max_val, 3.14)

    def test_simulate_thresholds(self):
        stats = GateStats(
            total=100, threshold=0.50, mean=0.35,
            rejected=80, rejection_rate=80.0,
        )
        values = [0.1, 0.2, 0.3, 0.4, 0.45, 0.48, 0.49, 0.51, 0.55, 0.6]
        sims = self.engine._simulate_thresholds("RVOL", stats, values)
        self.assertIn("Atual", sims)
        self.assertIn("-5%", sims)
        self.assertIn("-10%", sims)
        self.assertIn("+5%", sims)
        self.assertIn("+10%", sims)
        atual = sims["Atual"]
        self.assertEqual(atual.threshold, 0.50)
        dez_menos = sims["-10%"]
        self.assertAlmostEqual(dez_menos.threshold, 0.45, delta=0.01)

    def test_diagnose_low_volume_market(self):
        stats_by_gate = {
            "RVOL": GateStats(
                total=100, threshold=0.50, mean=0.28,
                p90=0.45, rejected=85, rejection_rate=85.0,
            ),
        }
        diagnoses = self.engine._diagnose_market(stats_by_gate)
        conditions = [d.condition for d in diagnoses]
        self.assertIn("Mercado com baixo volume", conditions)

    def test_diagnose_lateral_market(self):
        stats_by_gate = {
            "ADX": GateStats(
                total=100, threshold=20.0, mean=15.0,
                p75=18.0, rejected=60, rejection_rate=60.0,
            ),
        }
        diagnoses = self.engine._diagnose_market(stats_by_gate)
        conditions = [d.condition for d in diagnoses]
        self.assertIn("Mercado lateral (tendencia fraca)", conditions)

    def test_diagnose_restrictive_quality(self):
        stats_by_gate = {
            "Quality Gate": GateStats(
                total=100, threshold=0.55, mean=0.40,
                p75=0.38, p90=0.45, rejected=90, rejection_rate=90.0,
            ),
        }
        diagnoses = self.engine._diagnose_market(stats_by_gate)
        conditions = [d.condition for d in diagnoses]
        self.assertIn("Quality Gate excessivamente restritivo", conditions)

    def test_generate_recommendations(self):
        stats_by_gate = {
            "RVOL": GateStats(
                total=100, threshold=0.50, mean=0.30,
                p75=0.33, p90=0.45, rejected=85, rejection_rate=85.0,
                p25=0.20, p50=0.30, std=0.10,
            ),
        }
        sims = {
            "RVOL": {
                "-5%": MagicMock(threshold=0.475, would_pass=30,
                                 would_fail=70, approval_rate=30.0,
                                 pct_change=-5.0, win_rate_impact=1.5,
                                 profit_factor_impact=0.9, drawdown_impact=7.5,
                                 expectancy_impact=1.2),
            },
        }
        recs = self.engine._generate_recommendations(
            stats_by_gate, sims, [],
        )
        self.assertGreater(len(recs), 0)
        self.assertEqual(recs[0].gate, "RVOL")

    def test_end_cycle_min_samples(self):
        self.engine.start_cycle(1)
        report = self.engine.end_cycle(force=False)
        self.assertIsNone(report)

    def test_end_cycle_force(self):
        self.engine.start_cycle(1)
        sig = MockSignal(rvol=0.48, adx=22)
        sd = MockSignalDecision(approved=True)
        for i in range(15):
            self.engine.record_signal_all_gates(
                symbol=f"COIN{i}USDT", timeframe="1h", direction="LONG",
                result="APPROVED", signal=sig, sd=sd,
            )
        report = self.engine.end_cycle(force=False)
        self.assertIsNotNone(report)
        self.assertIn("RELATORIO DE CALIBRACAO", report)

    def test_calibration_report_format(self):
        self.engine.start_cycle(1)
        sig = MockSignal(rvol=0.30, adx=16)
        sd = MockSignalDecision(entry_score=0.35, quality=0.50,
                                 confidence=0.60, consensus=0.45,
                                 approved=False)
        for i in range(15):
            self.engine.record_signal_all_gates(
                symbol=f"COIN{i}USDT",
                timeframe="1h" if i % 2 == 0 else "4h",
                direction="LONG" if i % 2 == 0 else "SHORT",
                result="REJECTED" if i < 12 else "APPROVED",
                signal=sig, sd=sd,
            )
        report = self.engine.end_cycle(force=False)
        self.assertIsNotNone(report)
        self.assertIn("ESTATISTICAS POR GATE", report)
        self.assertIn("SIMULACOES DE THRESHOLD", report)
        self.assertIn("RECOMENDACOES", report)
        self.assertIn("FIM DO RELATORIO DE CALIBRACAO", report)

    def test_record_gate_observation_disabled(self):
        self.engine.set_enabled(False)
        self.engine.start_cycle(1)
        self.engine.record_gate_observation(
            gate="RVOL", symbol="BTCUSDT", timeframe="1h",
            direction="LONG", value=0.45, threshold=0.50,
            result="REJECTED",
        )
        self.assertEqual(len(self.engine._observations.get("RVOL", [])), 0)

    def test_compute_stats_rejection_rate(self):
        values = [0.3, 0.35, 0.4, 0.45, 0.5]
        stats = self.engine._compute_stats(values, threshold=0.5,
                                            total_signals=5, rejected_count=4)
        self.assertAlmostEqual(stats.rejection_rate, 80.0)

    def test_simulate_thresholds_no_values(self):
        stats = GateStats(threshold=0.5)
        sims = self.engine._simulate_thresholds("RVOL", stats, [])
        self.assertEqual(sims, {})

    def test_market_diagnosis_empty(self):
        diagnoses = self.engine._diagnose_market({})
        self.assertEqual(diagnoses, [])


if __name__ == '__main__':
    unittest.main()
