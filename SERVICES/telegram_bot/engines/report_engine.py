import logging
from ...trading.risk_manager import BotRiskManager

log = logging.getLogger(__name__)

class ReportEngine:
    def __init__(self, risk_manager: BotRiskManager):
        self._rm = risk_manager

    def generate_daily_report(self) -> str:
        stats = self._rm.get_daily_stats()
        if not stats:
            return "Nenhum dado para o relatório de hoje."
        return f"📊 RELATÓRIO DIÁRIO\nWR: {stats.winning_trades/max(stats.total_trades,1):.1%}\nPF: {stats.gross_profit/max(stats.gross_loss,1):.2f}"
