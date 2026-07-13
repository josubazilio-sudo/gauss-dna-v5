import unittest
from ENGINE.common.score_normalizer import scale_1_to_100, scale_100_to_1, normalize, clamp

class TestScoreNormalizer(unittest.TestCase):

    def test_scale_1_to_100(self):
        self.assertEqual(scale_1_to_100(0.0), 0.0)
        self.assertEqual(scale_1_to_100(0.5), 50.0)
        self.assertEqual(scale_1_to_100(1.0), 100.0)
        self.assertEqual(scale_1_to_100(1.5), 100.0)  # Should clamp

    def test_scale_100_to_1(self):
        self.assertEqual(scale_100_to_1(0.0), 0.0)
        self.assertEqual(scale_100_to_1(50.0), 0.5)
        self.assertEqual(scale_100_to_1(100.0), 1.0)
        self.assertEqual(scale_100_to_1(150.0), 1.0) # Should clamp

    def test_normalize(self):
        self.assertEqual(normalize(50, 0, 100), 0.5)
        self.assertEqual(normalize(0, 0, 100), 0.0)
        self.assertEqual(normalize(100, 0, 100), 1.0)

if __name__ == '__main__':
    unittest.main()
