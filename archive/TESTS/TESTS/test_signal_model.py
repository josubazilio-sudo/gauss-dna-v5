import unittest
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dataclasses import fields as dc_fields

from ENGINE.scanner.scanner_types import (
    SignalDirection, SignalClassification, ScannerScore,
    Pattern, PatternType, MarketStructure, StructureType,
    SwingPoint, Signal, ScanReport,
)
from ENGINE.scanner.scanner_signal import build_signal, _next_signal_id
from SERVICES.telegram.signal_compat import wrap_signal
from SERVICES.telegram.telegram_formatter import TelegramFormatter


class TestScannerScore(unittest.TestCase):

    def test_default_values(self):
        s = ScannerScore()
        self.assertEqual(s.entry_score, 0.0)
        self.assertEqual(s.consensus_score, 0.0)
        self.assertEqual(s.quality_score, 0.0)

    def test_fields_count(self):
        f = [f.name for f in dc_fields(ScannerScore)]
        self.assertIn("entry_score", f)
        self.assertIn("consensus_score", f)
        self.assertIn("conviction_score", f)
        self.assertIn("flow_score", f)
        self.assertIn("follow_through", f)
        self.assertIn("timing_index", f)

    def test_to_dict_complete(self):
        s = ScannerScore(
            entry_score=75.0, consensus_score=85.0, quality_score=80.0,
            institutional_score=70.0, structural_score=65.0,
            market_score=60.0, momentum_score=55.0, liquidity_score=50.0,
            risk_score=30.0, confidence_score=72.0,
        )
        d = s.to_dict()
        self.assertEqual(d["entry_score"], 75.0)
        self.assertEqual(d["consensus_score"], 85.0)
        self.assertEqual(d["conviction_score"], 0.0)
        self.assertEqual(d["flow_score"], 0.0)
        self.assertEqual(d["follow_through"], 0.0)
        self.assertEqual(d["timing_index"], 0.0)


class TestSignalModel(unittest.TestCase):

    def setUp(self):
        self.score = ScannerScore(
            entry_score=75.0, consensus_score=85.0, quality_score=80.0,
            institutional_score=70.0, structural_score=65.0,
            market_score=60.0, momentum_score=55.0, liquidity_score=50.0,
            risk_score=30.0, confidence_score=72.0,
        )
        self.structure = MarketStructure(
            structure_type=StructureType.UPTREND,
            swing_highs=[], swing_lows=[],
            structure_strength=0.7,
            mm50=51000.0, mm200=49000.0, vwap=50500.0,
        )
        self.patterns = [
            Pattern(
                type=PatternType.BOS, direction=SignalDirection.LONG,
                price=50000.0, timeframe="1h", confidence=0.8,
                strength=0.7, description="BOS", metadata={},
            ),
            Pattern(
                type=PatternType.ORDER_BLOCK, direction=SignalDirection.LONG,
                price=49500.0, timeframe="1h", confidence=0.75,
                strength=0.6, description="OB", metadata={},
            ),
        ]

    def _make_signal(self, **kw) -> Signal:
        return Signal(
            ticker=kw.get("ticker", "BTCUSDT"),
            timeframe=kw.get("timeframe", "1h"),
            direction=kw.get("direction", SignalDirection.LONG),
            entry_price=kw.get("entry_price", 50000.0),
            stop_loss=kw.get("stop_loss", 49000.0),
            take_profit_1=kw.get("take_profit_1", 52000.0),
            take_profit_2=kw.get("take_profit_2", 54000.0),
            risk_reward=kw.get("risk_reward", 2.0),
            scores=kw.get("scores", self.score),
            classification=kw.get("classification", SignalClassification.OURO),
            patterns=kw.get("patterns", self.patterns),
            structure=kw.get("structure", self.structure),
            setup=kw.get("setup", "Setup test"),
            context=kw.get("context", "Context test"),
            approval_reasons=kw.get("approval_reasons", []),
            rejection_reasons=kw.get("rejection_reasons", []),
            confidence=kw.get("confidence", 0.80),
            quality=kw.get("quality", 0.80),
            signal_id=kw.get("signal_id", "SIG-TEST-0001"),
            entry_zone=kw.get("entry_zone", "ZONA DE ACUMULACAO"),
            order_block_distance=kw.get("order_block_distance", 500.0),
            fvg_distance=kw.get("fvg_distance", 250.0),
            validity=kw.get("validity", "4h"),
            regime=kw.get("regime", "trending"),
        )

    def test_signal_id_present(self):
        sig = self._make_signal(signal_id="SIG-TEST-9999")
        self.assertEqual(sig.signal_id, "SIG-TEST-9999")

    def test_signal_id_in_to_dict(self):
        sig = self._make_signal(signal_id="SIG-TEST-8888")
        d = sig.to_dict()
        self.assertEqual(d["signal_id"], "SIG-TEST-8888")

    def test_entry_zone_in_to_dict(self):
        sig = self._make_signal(entry_zone="ZONA DE ACUMULACAO")
        d = sig.to_dict()
        self.assertEqual(d["entry_zone"], "ZONA DE ACUMULACAO")

    def test_order_block_distance_in_to_dict(self):
        sig = self._make_signal(order_block_distance=500.0)
        d = sig.to_dict()
        self.assertEqual(d["order_block_distance"], 500.0)

    def test_fvg_distance_in_to_dict(self):
        sig = self._make_signal(fvg_distance=250.0)
        d = sig.to_dict()
        self.assertEqual(d["fvg_distance"], 250.0)

    def test_validity_in_to_dict(self):
        sig = self._make_signal(validity="4h")
        d = sig.to_dict()
        self.assertEqual(d["validity"], "4h")

    def test_approved_property(self):
        approved = self._make_signal(rejection_reasons=[])
        self.assertTrue(approved.approved)
        rejected = self._make_signal(rejection_reasons=["Entry Zone Score Too Low"])
        self.assertFalse(rejected.approved)

    def test_to_dict_complete_coverage(self):
        sig = self._make_signal()
        d = sig.to_dict()
        expected_keys = [
            "signal_id", "timestamp", "ticker", "pair", "timeframe",
            "direction", "entry_price", "stop_loss", "take_profit_1",
            "take_profit_2", "risk_reward", "scores", "classification",
            "patterns", "structure", "setup", "context", "confidence",
            "quality", "approval_reasons", "rejection_reasons", "regime",
            "entry_type", "entry_zone", "order_block_distance", "fvg_distance",
            "validity", "approved", "rvol", "adx", "atr", "volume",
            "ema50", "ema200", "vwap", "structure_strength", "market_context",
            "explanation",
            "kalman_direction", "kalman_confidence", "kalman_trend_state",
            "kalman_tendency", "classification_label",
            "false_breakout_clear", "traps_clear",
            "volume_above_avg", "rvol_confirmed", "no_absorption",
            "no_rejection", "structure_valid",
        ]
        for k in expected_keys:
            self.assertIn(k, d, f"Campo '{k}' ausente em to_dict()")
        self.assertEqual(len(d), len(expected_keys),
                         f"Esperado {len(expected_keys)} campos, obtido {len(d)}. "
                         f"Sobras: {set(d.keys()) - set(expected_keys)}")

    def test_scores_contains_entry_and_consensus(self):
        sig = self._make_signal()
        d = sig.to_dict()
        scores = d["scores"]
        self.assertIn("entry_score", scores)
        self.assertIn("consensus_score", scores)
        self.assertEqual(scores["entry_score"], 75.0)
        self.assertEqual(scores["consensus_score"], 85.0)

    def test_entry_score_not_direct_on_signal(self):
        sig = self._make_signal()
        self.assertFalse(hasattr(sig, 'entry_score') or 'entry_score' in sig.__dict__,
                         "entry_score deve estar em scores, nao diretamente no Signal")
        self.assertEqual(sig.scores.entry_score, 75.0)

    def test_regime_not_market_regime(self):
        sig = self._make_signal(regime="trending")
        self.assertEqual(sig.regime, "trending")
        self.assertFalse(hasattr(sig, 'market_regime'))

    def test_to_dict_json_serializable(self):
        sig = self._make_signal()
        d = sig.to_dict()
        json_str = json.dumps(d, default=str)
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["signal_id"], "SIG-TEST-0001")

    def test_approved_in_to_dict(self):
        sig = self._make_signal(rejection_reasons=[])
        self.assertTrue(sig.to_dict()["approved"])
        sig2 = self._make_signal(rejection_reasons=["fail"])
        self.assertFalse(sig2.to_dict()["approved"])

    def test_wrap_signal_preserves_fields(self):
        sig = self._make_signal()
        d = sig.to_dict()
        wrapped = wrap_signal(d)
        self.assertEqual(wrapped.ticker, "BTCUSDT")
        self.assertEqual(wrapped.entry_zone, "ZONA DE ACUMULACAO")
        self.assertEqual(wrapped.order_block_distance, 500.0)
        self.assertEqual(wrapped.fvg_distance, 250.0)
        self.assertEqual(wrapped.validity, "4h")
        self.assertEqual(wrapped.regime, "trending")
        self.assertTrue(wrapped.approved)

    def test_build_signal_creates_signal_id(self):
        sig = build_signal(
            ticker="BTCUSDT", timeframe="1h",
            direction=SignalDirection.LONG,
            patterns=[], structure=self.structure,
            scores=ScannerScore(quality_score=0.8),
            classification=SignalClassification.OURO,
            current_price=50000.0,
        )
        self.assertTrue(sig.signal_id.startswith("SIG-"), f"signal_id='{sig.signal_id}'")
        self.assertNotEqual(sig.signal_id, "")

    def test_build_signal_increments_signal_id(self):
        id1 = _next_signal_id()
        id2 = _next_signal_id()
        self.assertNotEqual(id1, id2)

    def test_build_signal_sets_entry_score_in_scores(self):
        sig = build_signal(
            ticker="BTCUSDT", timeframe="1h",
            direction=SignalDirection.LONG,
            patterns=[], structure=self.structure,
            scores=ScannerScore(quality_score=0.8),
            classification=SignalClassification.OURO,
            current_price=50000.0,
            entry_score=72.5,
        )
        self.assertEqual(sig.scores.entry_score, 72.5)
        self.assertFalse(hasattr(sig, 'entry_score'))

    def test_build_signal_consensus_score(self):
        sig = build_signal(
            ticker="BTCUSDT", timeframe="1h",
            direction=SignalDirection.LONG,
            patterns=[], structure=self.structure,
            scores=ScannerScore(quality_score=0.8),
            classification=SignalClassification.OURO,
            current_price=50000.0,
            consensus_score=88.0,
        )
        self.assertEqual(sig.scores.consensus_score, 88.0)

    def test_signal_decision_from_signal_copies_risk_reward(self):
        from ENGINE.decision.signal_decision import SignalDecision
        signal = self._make_signal(risk_reward=2.75)
        decision = SignalDecision.from_signal(signal)
        self.assertEqual(decision.risk_reward, 2.75)

    def test_build_signal_entry_zone_fields(self):
        sig = build_signal(
            ticker="BTCUSDT", timeframe="1h",
            direction=SignalDirection.LONG,
            patterns=[], structure=self.structure,
            scores=ScannerScore(quality_score=0.8),
            classification=SignalClassification.OURO,
            current_price=50000.0,
            entry_zone="ZONA DE ACUMULACAO",
            order_block_distance=350.0,
            fvg_distance=120.0,
            validity="4h",
        )
        self.assertEqual(sig.entry_zone, "ZONA DE ACUMULACAO")
        self.assertEqual(sig.order_block_distance, 350.0)
        self.assertEqual(sig.fvg_distance, 120.0)
        self.assertEqual(sig.validity, "4h")


class TestTelegramFormatterOfficialFields(unittest.TestCase):

    def setUp(self):
        self.fmt = TelegramFormatter()

    def _make_signal_dict(self):
        return {
            "signal_id": "SIG-TG-0001",
            "ticker": "ETHUSDT",
            "timeframe": "4h",
            "direction": "long",
            "entry_price": 3000.0,
            "stop_loss": 2900.0,
            "take_profit_1": 3200.0,
            "take_profit_2": 3400.0,
            "risk_reward": 2.0,
            "quality": 0.85,
            "confidence": 0.80,
            "regime": "trending",
            "entry_zone": "ZONA DE ACUMULACAO",
            "order_block_distance": 150.0,
            "fvg_distance": 75.0,
            "validity": "4h",
            "approval_reasons": ["Tendencia alinhada", "BOS confirmado"],
            "rejection_reasons": [],
            "scores": {
                "entry_score": 72.0,
                "consensus_score": 85.0,
                "institutional_score": 70.0,
                "structural_score": 65.0,
                "liquidity_score": 60.0,
                "market_score": 55.0,
                "confidence_score": 80.0,
                "quality_score": 0.85,
                "momentum_score": 50.0,
                "risk_score": 30.0,
            },
        }

    def test_format_signal_with_official_fields(self):
        data = self._make_signal_dict()
        wrapped = wrap_signal(data)
        msg = self.fmt.format_signal(wrapped)
        self.assertIn("LONG", msg)
        self.assertIn("ETHUSDT", msg)
        self.assertIn("4h", msg)
        self.assertIn("$3000.00", msg)
        self.assertIn("Qualidade: 85.0", msg)
        self.assertIn("Confian\u00e7a: 80.0", msg)
        self.assertIn("Tendencia alinhada", msg)
        self.assertNotIn("N/A", msg)

    def test_format_signal_no_fallback_needed(self):
        data = self._make_signal_dict()
        wrapped = wrap_signal(data)
        msg = self.fmt.format_signal(wrapped)
        self.assertNotIn("FALLBACK", msg.upper())
        self.assertNotIn("Erro na formatacao", msg)


if __name__ == '__main__':
    unittest.main()
