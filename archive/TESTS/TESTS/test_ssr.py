import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.scanner.ssr import (
    compute_ssr, ssr_from_scores, classify_ssr, ssr_alert,
    SSR_WEIGHTS, SSR_TIERS,
)


class TestSSRCompute(unittest.TestCase):

    def test_perfect_scores(self):
        ssr = compute_ssr(quality=1.0, confidence=1.0, consensus=100,
                          entry_score=100, institutional=1.0,
                          structural=1.0, liquidity=1.0, market=1.0)
        self.assertAlmostEqual(ssr, 100.0, delta=0.1)

    def test_zero_scores(self):
        ssr = compute_ssr()
        self.assertEqual(ssr, 0.0)

    def test_mid_range(self):
        ssr = compute_ssr(quality=0.8, confidence=0.7, consensus=75,
                          entry_score=70, institutional=0.6,
                          structural=0.5, liquidity=0.4, market=0.3)
        self.assertGreater(ssr, 50)
        self.assertLess(ssr, 90)

    def test_quality_weighs_most(self):
        high_quality = compute_ssr(quality=1.0, confidence=0.5, consensus=50,
                                   entry_score=50, institutional=0.5,
                                   structural=0.5, liquidity=0.5, market=0.5)
        low_quality = compute_ssr(quality=0.1, confidence=0.5, consensus=50,
                                  entry_score=50, institutional=0.5,
                                  structural=0.5, liquidity=0.5, market=0.5)
        self.assertGreater(high_quality, low_quality)

    def test_clamps_above_100(self):
        ssr = compute_ssr(quality=200.0, confidence=200.0, consensus=200,
                          entry_score=200, institutional=200.0,
                          structural=200.0, liquidity=200.0, market=200.0)
        self.assertEqual(ssr, 100.0)

    def test_clamps_below_0(self):
        ssr = compute_ssr(quality=-1.0, confidence=-1.0, consensus=-50,
                          entry_score=-50, institutional=-1.0,
                          structural=-1.0, liquidity=-1.0, market=-1.0)
        self.assertEqual(ssr, 0.0)

    def test_normalized_weights(self):
        total_w = sum(SSR_WEIGHTS.values())
        self.assertAlmostEqual(total_w, 1.0, places=2)


class TestSSRFromScores(unittest.TestCase):

    def test_ssr_from_scores(self):
        ssr = ssr_from_scores(
            quality_score=0.85,
            confidence_score=0.75,
            consensus_score=80.0,
            entry_score=70.0,
            institutional_score=0.60,
            structural_score=0.55,
            liquidity_score=0.50,
            market_score=0.45,
        )
        self.assertGreater(ssr, 60)
        self.assertLess(ssr, 85)


class TestSSRClassification(unittest.TestCase):

    def test_institucional(self):
        name, stars = classify_ssr(96)
        self.assertEqual(name, "INSTITUCIONAL")
        self.assertIn("\u2b50", stars)

    def test_elite(self):
        name, stars = classify_ssr(90)
        self.assertEqual(name, "ELITE")

    def test_alta_qualidade(self):
        name, stars = classify_ssr(80)
        self.assertEqual(name, "ALTA QUALIDADE")

    def test_oportunidade(self):
        name, stars = classify_ssr(70)
        self.assertEqual(name, "OPORTUNIDADE")

    def test_observacao(self):
        name, stars = classify_ssr(40)
        self.assertEqual(name, "OBSERVACAO")

    def test_boundary_95(self):
        name, _ = classify_ssr(95)
        self.assertEqual(name, "INSTITUCIONAL")

    def test_boundary_94(self):
        name, _ = classify_ssr(94)
        self.assertEqual(name, "ELITE")

    def test_boundary_85(self):
        name, _ = classify_ssr(85)
        self.assertEqual(name, "ELITE")

    def test_boundary_84(self):
        name, _ = classify_ssr(84)
        self.assertEqual(name, "ALTA QUALIDADE")


class TestSSRAlert(unittest.TestCase):

    def test_prioridade_maxima(self):
        alert = ssr_alert(96)
        self.assertIsNotNone(alert)
        self.assertIn("PRIORIDADE", alert)

    def test_sinal_premium(self):
        alert = ssr_alert(93)
        self.assertIsNotNone(alert)
        self.assertIn("PREMIUM", alert)

    def test_no_alert_below_90(self):
        alert = ssr_alert(85)
        self.assertIsNone(alert)

    def test_boundary_95(self):
        alert = ssr_alert(95.1)
        self.assertIn("PRIORIDADE", alert)

    def test_boundary_90(self):
        alert = ssr_alert(90.1)
        self.assertIn("PREMIUM", alert)


if __name__ == '__main__':
    unittest.main()
