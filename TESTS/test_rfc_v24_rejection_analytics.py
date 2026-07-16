import unittest
from datetime import datetime
from ENGINE.analytics.rejection_analytics import RejectionAnalytics, SignalRecord

class TestRejectionAnalytics(unittest.TestCase):
    def setUp(self):
        self.analytics = RejectionAnalytics(export_dir="/tmp/analytics_test")
        self.analytics.start_cycle(1)

    def test_record_approval(self):
        self.analytics.record_approval(symbol="BTCUSDT", timeframe="1h", direction="LONG")
        self.assertEqual(len(self.analytics.cycle_records), 1)
        self.assertEqual(self.analytics.cycle_records[0].result, "APPROVED")

    def test_record_rejection(self):
        self.analytics.record_rejection(gate="RVOL", symbol="BTCUSDT", found_value=0.4, expected_value=0.5)
        self.assertEqual(len(self.analytics.cycle_records), 1)
        self.assertEqual(self.analytics.cycle_records[0].result, "REJECTED")
        self.assertEqual(self.analytics.cycle_records[0].gate, "RVOL")
        self.assertEqual(self.analytics.cycle_records[0].difference, -0.1)

    def test_end_cycle_summary(self):
        self.analytics.record_approval(symbol="BTCUSDT", timeframe="1h")
        self.analytics.record_rejection(gate="RVOL", symbol="ETHUSDT", found_value=0.4, expected_value=0.5)
        summary = self.analytics.end_cycle()
        self.assertEqual(summary["total_analyzed"], 2)
        self.assertEqual(summary["total_approved"], 1)
        self.assertEqual(summary["total_rejected"], 1)
        self.assertEqual(summary["approval_rate"], 50.0)

    def test_threshold_analysis(self):
        self.analytics.record_rejection(gate="RVOL", symbol="ETHUSDT", found_value=0.4, expected_value=0.5)
        self.analytics.record_rejection(gate="RVOL", symbol="XRPUSDT", found_value=0.45, expected_value=0.5)
        summary = self.analytics.end_cycle()
        analysis = summary["threshold_analysis"]
        self.assertIn("RVOL", analysis)
        self.assertGreater(len(analysis["RVOL"]["simulations"]), 0)

if __name__ == '__main__':
    unittest.main()
