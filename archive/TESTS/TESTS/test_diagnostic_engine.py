import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ENGINE.diagnostic.engine import DiagnosticEngine


class TestDetectSilentDrops(unittest.TestCase):
    """Regressao: detect_silent_drops() marcava como 'bug' qualquer ativo
    que nao tocasse as 10 etapas do pipeline, mas smart_money/quality_gate
    so sao registrados quando ha uma decisao candidata (ver main.py). Isso
    gerava falso-positivo em quase 100% dos ativos legitimamente rejeitados
    sem sinal (MEMORY/audit/summary.json real: total_bugs=5123 de
    total_assets_analyzed=5164)."""

    def setUp(self):
        self.diag = DiagnosticEngine()
        self.diag.start_cycle(1)

    def test_pair_with_final_decision_is_not_flagged_as_bug(self):
        self.diag.record_market_data("BTCUSDT", loaded=True, api_ms=10)
        self.diag.record_candles("BTCUSDT", {"1h": 200})
        self.diag.record_indicators("BTCUSDT", {"rsi": 50})
        self.diag.record_structure("BTCUSDT", {"trend": "up"})
        self.diag.record_entry_zone("BTCUSDT", zone_type="none", score=0, approved=False)
        self.diag.record_consensus("BTCUSDT", {"consensus_score": 0})
        self.diag.record_final_decision(
            pair="BTCUSDT", status="REJECTED",
            primary_reason="Nenhum sinal", final_decision="Rejected: no signals",
        )
        # nunca tocou smart_money nem quality_gate — mas tem decisao final real
        self.diag.detect_silent_drops(["BTCUSDT"])
        self.assertEqual(self.diag._current_report.bugs, [])

    def test_pair_without_final_decision_is_still_flagged(self):
        self.diag.record_market_data("ETHUSDT", loaded=True, api_ms=10)
        self.diag.record_candles("ETHUSDT", {"1h": 200})
        # interrompido aqui (ex.: excecao) — nunca chegou a final_decision
        self.diag.detect_silent_drops(["ETHUSDT"])
        self.assertEqual(len(self.diag._current_report.bugs), 1)
        self.assertIn("ETHUSDT", self.diag._current_report.bugs[0]["probable_cause"])

    def test_pair_never_seen_is_flagged(self):
        self.diag.detect_silent_drops(["SOLUSDT"])
        self.assertEqual(len(self.diag._current_report.bugs), 1)


if __name__ == "__main__":
    unittest.main()
