import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ENGINE.consensus.consensus_engine import ConsensusEngine
from ENGINE.scanner.scanner_types import SignalDirection

class TestConsensusHierarchy(unittest.TestCase):
    def test_hierarchy_enforcement(self):
        engine = ConsensusEngine()
        # 1D/4H for vs 30m against
        directions = {'1d': SignalDirection.LONG, '4h': SignalDirection.LONG, '1h': SignalDirection.SHORT, '30m': SignalDirection.SHORT}
        scores = {'1d': 0.9, '4h': 0.8, '1h': 0.7, '30m': 0.9}
        result = engine.compute(directions, scores)
        self.assertEqual(result.final_direction, SignalDirection.LONG)

if __name__ == '__main__':
    unittest.main()
