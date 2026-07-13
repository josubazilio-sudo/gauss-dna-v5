from ..bot_types import Signal
from datetime import datetime

class TelegramFormatter:
    @staticmethod
    def format_signal(signal: Signal) -> str:
        return f"""🟢 *NOVO SINAL*

💎 *Ativo:* {signal.ticker}
🕐 *Time Frame:* {signal.timeframe}
📈 *Direção:* {signal.direction.value.upper()}

━━━━━━━━━━━━━━━━━━
💰 Entrada: {signal.entry_price:.2f}
🛑 Stop Loss: {signal.stop_loss:.2f}
🎯 TP1: {signal.take_profit_1:.2f}
🏆 TP2: {signal.take_profit_2:.2f}
⚖️ RR: {signal.risk_reward:.2f}

━━━━━━━━━━━━━━━━━━
📊 Inst Score: {signal.scores.institutional_score:.2f}
🏗 Struct Score: {signal.scores.structural_score:.2f}
🔥 Confidência: {signal.confidence:.2%}
💎 Qualidade: {signal.quality:.2%}

━━━━━━━━━━━━━━━━━━
⚙️ Setup: {signal.setup}
🔄 Contexto: {signal.context}

━━━━━━━━━━━━━━━━━━
📝 Motivos: {", ".join(signal.approval_reasons)}
⏰ Horário: {datetime.now().strftime('%H:%M:%S')}
🆔 ID: {signal.timestamp.timestamp()}
"""
