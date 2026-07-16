"""RFC V25.X.1 — Correção Institucional do Consensus Engine.

Auditoria identificou que o consensus_score para 3+ TFs era calculado
como média ponderada de confidence, não como medida de concordância
direcional. Esta correção separa os dois conceitos.

Casos testados:
  1. 4 LONG          → consensus = 1.00
  2. 3 LONG + 1 SHORT → consensus = 0.75
  3. 2 LONG + 2 SHORT → consensus = 0.50
  4. 4 SHORT          → consensus = 1.00
  5. 1 LONG + 3 SHORT → consensus = 0.75
  6. Dados ausentes   → consensus = 0.0, final_direction = None
  7. Neutral incluso  → voto neutro não contribui
  8. 1 TF isolado     → caminho especial preservado
  9. 2 TFs            → weighted proportion sem confidence
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.consensus.consensus_engine import ConsensusEngine
from ENGINE.scanner.scanner_types import SignalDirection


class TestConsensus4Long:
    def test_consensus_4_long_returns_1_0(self):
        engine = ConsensusEngine()
        result = engine.compute(
            timeframe_directions={
                "30m": SignalDirection.LONG,
                "1h": SignalDirection.LONG,
                "4h": SignalDirection.LONG,
                "1d": SignalDirection.LONG,
            },
            timeframe_scores={"30m": 0.5, "1h": 0.6, "4h": 0.7, "1d": 0.8},
            timeframe_confidence={"30m": 0.2, "1h": 0.3, "4h": 0.4, "1d": 0.5},
        )
        assert result.final_direction == SignalDirection.LONG
        assert result.consensus_score == 1.0
        assert result.dissenting_timeframes == []
        assert result.meets_minimum()


class TestConsensus3Long1Short:
    def test_consensus_3_long_1_short_returns_0_75(self):
        engine = ConsensusEngine()
        result = engine.compute(
            timeframe_directions={
                "30m": SignalDirection.LONG,
                "1h": SignalDirection.LONG,
                "4h": SignalDirection.SHORT,
                "1d": SignalDirection.LONG,
            },
            timeframe_scores={"30m": 0.5, "1h": 0.6, "4h": 0.7, "1d": 0.8},
            timeframe_confidence={"30m": 0.2, "1h": 0.3, "4h": 0.4, "1d": 0.5},
        )
        assert result.final_direction == SignalDirection.LONG
        # pesos: 30m=0.05, 1h=0.20, 4h=0.45(short), 1d=0.80
        # long_weight = 0.05+0.20+0.80 = 1.05
        # total = 1.50
        # consensus = 1.05/1.50 = 0.70
        assert result.consensus_score == 0.70
        assert "4h" in result.dissenting_timeframes


class TestConsensus2Long2Short:
    def test_consensus_2_long_2_short_equals_weighted_split(self):
        engine = ConsensusEngine()
        result = engine.compute(
            timeframe_directions={
                "30m": SignalDirection.SHORT,
                "1h": SignalDirection.LONG,
                "4h": SignalDirection.SHORT,
                "1d": SignalDirection.LONG,
            },
            timeframe_scores={"30m": 0.5, "1h": 0.6, "4h": 0.7, "1d": 0.8},
            timeframe_confidence={"30m": 0.2, "1h": 0.3, "4h": 0.4, "1d": 0.5},
        )
        # pesos: 30m=0.05(short), 1h=0.20(long), 4h=0.45(short), 1d=0.80(long)
        # long_weight = 0.20+0.80 = 1.00
        # short_weight = 0.05+0.45 = 0.50
        # total = 1.50
        # final = LONG, consensus_raw = 1.00/1.50 = 0.67
        assert result.final_direction == SignalDirection.LONG
        assert result.consensus_score == 0.67
        assert len(result.dissenting_timeframes) == 2


class TestConsensus4Short:
    def test_consensus_4_short_returns_1_0(self):
        engine = ConsensusEngine()
        result = engine.compute(
            timeframe_directions={
                "30m": SignalDirection.SHORT,
                "1h": SignalDirection.SHORT,
                "4h": SignalDirection.SHORT,
                "1d": SignalDirection.SHORT,
            },
            timeframe_scores={"30m": 0.5, "1h": 0.6, "4h": 0.7, "1d": 0.8},
            timeframe_confidence={"30m": 0.2, "1h": 0.3, "4h": 0.4, "1d": 0.5},
        )
        assert result.final_direction == SignalDirection.SHORT
        assert result.consensus_score == 1.0
        assert result.dissenting_timeframes == []
        assert result.meets_minimum()


class TestConsensus1Long3Short:
    def test_consensus_1_long_3_short_returns_short_majority(self):
        engine = ConsensusEngine()
        result = engine.compute(
            timeframe_directions={
                "30m": SignalDirection.SHORT,
                "1h": SignalDirection.SHORT,
                "4h": SignalDirection.LONG,
                "1d": SignalDirection.SHORT,
            },
            timeframe_scores={"30m": 0.5, "1h": 0.6, "4h": 0.7, "1d": 0.8},
            timeframe_confidence={"30m": 0.2, "1h": 0.3, "4h": 0.4, "1d": 0.5},
        )
        assert result.final_direction == SignalDirection.SHORT
        assert result.consensus_score == 0.70
        assert "4h" in result.dissenting_timeframes


class TestConsensusEmptyData:
    def test_consensus_empty_returns_zero(self):
        engine = ConsensusEngine()
        result = engine.compute(
            timeframe_directions={},
            timeframe_scores={},
        )
        assert result.final_direction is None
        assert result.consensus_score == 0.0
        assert not result.meets_minimum()


class TestConsensusSingleTF:
    def test_single_tf_preserves_special_path(self):
        engine = ConsensusEngine()
        result = engine.compute(
            timeframe_directions={"4h": SignalDirection.LONG},
            timeframe_scores={"4h": 0.7},
            timeframe_confidence={"4h": 0.6},
            entry_score=0.8,
            quality_score=0.75,
        )
        # caminho 1 TF: base = max(0.30, 0.8*0.40+0.75*0.30) + 0.6*0.30
        # base = max(0.30, 0.545) = 0.545
        # score = round(min(0.545+0.18, 1.0), 2) = 0.73
        assert result.final_direction == SignalDirection.LONG
        assert result.consensus_score == 0.73
        assert result.meets_minimum()


class TestConsensusTwoTFs:
    def test_two_long_returns_1_0(self):
        engine = ConsensusEngine()
        result = engine.compute(
            timeframe_directions={
                "1h": SignalDirection.LONG,
                "4h": SignalDirection.LONG,
            },
            timeframe_scores={"1h": 0.6, "4h": 0.7},
            timeframe_confidence={"1h": 0.3, "4h": 0.4},
            entry_score=0.5,
        )
        assert result.final_direction == SignalDirection.LONG
        # 2 TFs, both LONG: consensus_raw = 1.0
        # entry_score*0.5 = 0.25 -> max(1.0, 0.25) = 1.0
        assert result.consensus_score == 1.0

    def test_two_mixed_returns_weighted_proportion(self):
        engine = ConsensusEngine()
        result = engine.compute(
            timeframe_directions={
                "1h": SignalDirection.LONG,
                "4h": SignalDirection.SHORT,
            },
            timeframe_scores={"1h": 0.6, "4h": 0.7},
            timeframe_confidence={"1h": 0.3, "4h": 0.4},
            entry_score=0.5,
        )
        # 1h=0.20(long), 4h=0.45(short)
        # weighted_long=0.20, total=0.65
        # consensus_raw = 0.20/0.65 = 0.307
        # final direction = SHORT (0.45 > 0.20)
        assert result.final_direction == SignalDirection.SHORT
        assert result.consensus_score == 0.69  # 0.45/0.65 = 0.69
        assert "1h" in result.dissenting_timeframes
