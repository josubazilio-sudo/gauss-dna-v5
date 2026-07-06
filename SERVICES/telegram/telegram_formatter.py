from typing import Any
from datetime import datetime

class TelegramFormatter:
    @staticmethod
    def format_signal(signal: Any) -> str:
        q = signal.quality * 100
        if q >= 95: cap, lev = 15, 20
        elif q >= 90: cap, lev = 12, 15
        elif q >= 85: cap, lev = 10, 10
        elif q >= 80: cap, lev = 8, 8
        else: cap, lev = 5, 5

        pos_val = cap * lev
        stop_dist = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
        stop_loss_usdt = pos_val * stop_dist
        tp1_usdt = pos_val * abs(signal.take_profit_1 - signal.entry_price) / signal.entry_price
        tp2_usdt = pos_val * abs(signal.take_profit_2 - signal.entry_price) / signal.entry_price

        return f"""🚨 *QUANTOS SIGNAL*

{ '🟢 LONG' if signal.direction.value == 'long' else '🔴 SHORT' }

━━━━━━━━━━━━━━
💎 *Ativo:* {signal.ticker}
🕐 *Time Frame:* {signal.timeframe}
📈 *Direção:* {signal.direction.value.upper()}
━━━━━━━━━━━━━━
💰 *Entrada:* {signal.entry_price:.2f}
🛑 *Stop Loss:* {signal.stop_loss:.2f}
🎯 *TP1:* {signal.take_profit_1:.2f}
🎯 *TP2:* {signal.take_profit_2:.2f}
📊 *Risk/Reward:* {signal.risk_reward:.2f}

━━━━━━━━━━━━━━
🏛 *Inst Score:* {signal.scores.institutional_score:.2f}
📈 *Struct Score:* {signal.scores.structural_score:.2f}
⚡ *Market Score:* {signal.scores.market_score:.2f}
🌊 *Liquidity Score:* {signal.scores.liquidity_score:.2f}
🎯 *Confidence:* {signal.confidence:.2f}
🏆 *Quality:* {q:.0f}

━━━━━━━━━━━━━━
📈 *Setup:* {signal.setup}
🌍 *Regime:* {signal.context}
📊 *Tendência:* {signal.structure.mm50_trend}
📦 *Volume:* {signal.scores.liquidity_score:.2f}

━━━━━━━━━━━━━━
📝 *Motivos:* {', '.join(signal.approval_reasons)}

━━━━━━━━━━━━━━
## 💼 SIMULAÇÃO (BANCA US$100)
💰 *Capital utilizado:* US${cap}
🚀 *Alavancagem:* {lev}x
📈 *Valor da posição:* US${pos_val}
🛑 *Perda no Stop:* US${stop_loss_usdt:.2f}
🎯 *Lucro TP1:* US${tp1_usdt:.2f}
🎯 *Lucro TP2:* US${tp2_usdt:.2f}
📊 *Retorno TP2:* +{tp2_usdt:.2f}% da banca

━━━━━━━━━━━━━━
🕒 *Horário:* {signal.timestamp.strftime('%H:%M:%S')}"""
