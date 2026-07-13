import pytest
from SERVICES.telegram.update_engine import UpdateEngine, OperationalImpact

# =============================================================================
# Tests for calculate_impact_score
# =============================================================================

class TestCalculateImpactScore:

    def test_direction_reversal_always_sends(self):
        old = {"direction": "LONG"}
        new = {"direction": "SHORT"}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score == 100
        assert result.is_send is True
        assert result.update_type == "🔄 REVERSÃO DE TENDÊNCIA"

    def test_setup_cancelled_always_sends(self):
        old = {"direction": "LONG"}
        new = {"direction": "LONG", "status": "cancelled"}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 80
        assert result.is_send is True
        assert result.update_type == "❌ SINAL CANCELADO"

    def test_trend_change_always_sends(self):
        old = {"trend": "trending_up"}
        new = {"trend": "trending_down"}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 80
        assert result.is_send is True
        assert result.update_type == "🔄 REVERSÃO DE TENDÊNCIA"

    def test_kalman_change_always_sends(self):
        old = {"kalman_direction": "UP"}
        new = {"kalman_direction": "DOWN"}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 80
        assert result.is_send is True
        assert result.update_type == "🔄 REVERSÃO DE TENDÊNCIA"

    def test_stop_change_above_2pct_always_sends(self):
        old = {"stop": 100.0}
        new = {"stop_loss": 103.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 80
        assert result.is_send is True
        assert result.update_type == "🛡 STOP AJUSTADO"

    def test_tp_change_above_2pct_always_sends(self):
        old = {"take_profit": 150.0}
        new = {"take_profit_1": 160.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 80
        assert result.is_send is True
        assert result.update_type == "🎯 TAKE PROFIT ATUALIZADO"

    def test_entry_change_above_1pct_always_sends(self):
        old = {"entry": 100.0}
        new = {"entry_price": 98.5}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 80
        assert result.is_send is True
        assert result.update_type == "🎯 ENTRADA AJUSTADA"

    def test_conviction_change_always_sends(self):
        old = {"conviction_level": "Alta"}
        new = {"conviction_level": "Baixa"}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 80
        assert result.is_send is True
        assert result.update_type == "📉 SETUP ENFRAQUECIDO"

    def test_large_score_change_sends(self):
        old = {"overall_score_value": 70.0}
        new = {"overall_score_value": 82.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 50
        assert result.is_send is True
        assert result.update_type == "📈 SETUP FORTALECIDO"

    def test_large_score_degradation_sends(self):
        old = {"overall_score_value": 80.0}
        new = {"overall_score_value": 68.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 50
        assert result.is_send is True
        assert result.update_type == "📉 SETUP ENFRAQUECIDO"

    def test_small_score_change_ignored(self):
        old = {"overall_score_value": 74.8}
        new = {"overall_score_value": 74.6}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 20
        assert result.is_send is False
        assert result.update_type is None

    def test_small_quality_change_ignored(self):
        old = {"quality_score": 79.0}
        new = {"quality_score": 78.9}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 20
        assert result.is_send is False

    def test_small_probability_change_ignored(self):
        old = {"probability": {"probability": 74.9}}
        new = {"probability": {"probability": 74.6}}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 20
        assert result.is_send is False

    def test_small_confidence_change_ignored(self):
        old = {"confidence": 78.7}
        new = {"confidence": 77.8}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 20
        assert result.is_send is False

    def test_small_consensus_change_ignored(self):
        old = {"consensus_score": 85.0}
        new = {"consensus_score": 84.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 20
        assert result.is_send is False

    def test_tiny_tp_change_ignored(self):
        old = {"take_profit_1": 0.016869}
        new = {"take_profit_1": 0.016864}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 20
        assert result.is_send is False

    def test_rfc_noise_example_all_ignored(self):
        old = {
            "overall_score_value": 74.8,
            "quality_score": 79.0,
            "probability": {"probability": 74.9},
            "confidence": 78.7,
            "consensus_score": 85.0,
            "take_profit_1": 0.016869,
        }
        new = {
            "overall_score_value": 74.6,
            "quality_score": 78.9,
            "probability": {"probability": 74.6},
            "confidence": 77.8,
            "consensus_score": 84.0,
            "take_profit_1": 0.016864,
        }
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 20
        assert result.is_send is False
        assert result.update_type is None

    def test_absolutely_no_change_ignored(self):
        old = {
            "direction": "LONG",
            "entry_price": 100.0,
            "stop_loss": 98.0,
            "take_profit_1": 104.0,
            "risk_reward": 2.0,
            "overall_score_value": 75.0,
            "quality_score": 70.0,
            "probability": {"probability": 65.0},
            "confidence": 80.0,
            "consensus_score": 75.0,
            "confluence_score": 70.0,
            "liquidity_score": 65.0,
            "flow_score": 60.0,
            "trend": "trending_up",
            "kalman_direction": "UP",
            "conviction_level": "Alta",
        }
        new = dict(old)
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score == 0
        assert result.is_send is False
        assert result.update_type is None

    def test_multiple_moderate_changes_cumulative_sends(self):
        old = {"overall_score_value": 70.0, "consensus_score": 50.0}
        new = {"overall_score_value": 74.0, "consensus_score": 56.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 50
        assert result.is_send is True
        assert result.update_type == "📈 SETUP FORTALECIDO"

    def test_rr_change_large_sends(self):
        old = {"risk_reward": 2.0, "overall_score_value": 70.0}
        new = {"risk_reward": 2.5, "overall_score_value": 74.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score >= 50
        assert result.is_send is True

    def test_rr_change_small_alone_ignored(self):
        old = {"risk_reward": 2.5}
        new = {"risk_reward": 2.7}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 50
        assert result.is_send is False

    def test_structure_change_alone_ignored(self):
        old = {"structure_score": 50.0}
        new = {"structure_score": 60.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 50
        assert result.is_send is False

    def test_risk_change_alone_ignored(self):
        old = {"risk_score": 50.0}
        new = {"risk_score": 60.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 50
        assert result.is_send is False

    def test_liquidity_change_alone_ignored(self):
        old = {"liquidity_score": 40.0}
        new = {"liquidity_score": 52.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 50
        assert result.is_send is False

    def test_flow_change_alone_ignored(self):
        old = {"flow_score": 80.0}
        new = {"flow_score": 69.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 50
        assert result.is_send is False

    def test_stop_below_2pct_no_other_change_ignored(self):
        old = {"stop": 100.0}
        new = {"stop_loss": 101.5}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 50
        assert result.is_send is False

    def test_entry_below_1pct_no_other_change_ignored(self):
        old = {"entry": 100.0}
        new = {"entry_price": 99.6}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert result.impact_score < 50
        assert result.is_send is False

    def test_score_3pts_alone_optional_ignored(self):
        old = {"overall_score_value": 70.0}
        new = {"overall_score_value": 73.0}
        result = UpdateEngine.calculate_impact_score(old, new)
        assert 20 <= result.impact_score < 50
        assert result.is_send is False


# =============================================================================
# Tests for get_update_type (convenience wrapper)
# =============================================================================

class TestGetUpdateType:

    def test_direction_reversal(self):
        old = {"direction": "LONG"}
        new = {"direction": "SHORT"}
        assert UpdateEngine.get_update_type(old, new) == "🔄 REVERSÃO DE TENDÊNCIA"

    def test_large_score_change_returns_label(self):
        old = {"overall_score_value": 70.0}
        new = {"overall_score_value": 82.0}
        assert UpdateEngine.get_update_type(old, new) == "📈 SETUP FORTALECIDO"

    def test_small_change_returns_none(self):
        old = {"overall_score_value": 74.8}
        new = {"overall_score_value": 74.6}
        assert UpdateEngine.get_update_type(old, new) is None

    def test_stop_above_2pct(self):
        old = {"stop": 100.0}
        new = {"stop_loss": 103.0}
        assert UpdateEngine.get_update_type(old, new) == "🛡 STOP AJUSTADO"

    def test_tp_above_2pct(self):
        old = {"take_profit": 150.0}
        new = {"take_profit_1": 160.0}
        assert UpdateEngine.get_update_type(old, new) == "🎯 TAKE PROFIT ATUALIZADO"

    def test_entry_above_1pct(self):
        old = {"entry": 100.0}
        new = {"entry_price": 98.5}
        assert UpdateEngine.get_update_type(old, new) == "🎯 ENTRADA AJUSTADA"

    def test_conviction_change(self):
        old = {"conviction_level": "Alta"}
        new = {"conviction_level": "Moderada"}
        assert UpdateEngine.get_update_type(old, new) == "📉 SETUP ENFRAQUECIDO"


# =============================================================================
# Tests for get_update_type_and_score
# =============================================================================

class TestGetUpdateTypeAndScore:

    def test_returns_tuple(self):
        old = {"overall_score_value": 70.0}
        new = {"overall_score_value": 82.0}
        label, score = UpdateEngine.get_update_type_and_score(old, new)
        assert label == "📈 SETUP FORTALECIDO"
        assert score >= 50

    def test_no_change_returns_none_and_zero(self):
        old = {"overall_score_value": 70.0}
        new = dict(old)
        label, score = UpdateEngine.get_update_type_and_score(old, new)
        assert label is None
        assert score == 0

    def test_small_change_returns_none_and_low_score(self):
        old = {"overall_score_value": 74.8}
        new = {"overall_score_value": 74.6}
        label, score = UpdateEngine.get_update_type_and_score(old, new)
        assert label is None
        assert score < 20
