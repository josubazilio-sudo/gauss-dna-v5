import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

SEPARATOR = "\n" + "\u2501" * 30 + "\n"

RESULT_EMOJI = {
    "WIN": "\U0001f7e2",
    "LOSS": "\U0001f534",
    "BREAKEVEN": "\U0001f7e1",
}


def _pct(value: float) -> str:
    signal = "+" if value >= 0 else ""
    return f"{signal}{value:.2f}%"


def _usdt(value: float) -> str:
    signal = "+" if value >= 0 else ""
    return f"{signal}{value:.2f} USDT"


def _escape_markdown(text: str) -> str:
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, "\\" + ch)
    return text


class TelegramTradeFormatter:

    @staticmethod
    def format_trade_result(trade: Dict) -> str:
        resultado = trade.get("resultado", "UNKNOWN")
        emoji = RESULT_EMOJI.get(resultado, "\u2753")
        asset = trade.get("asset", "???")
        direction = trade.get("direction", "").upper()
        timeframe = trade.get("timeframe", "???")
        entry = trade.get("entry_price", 0)
        exit_p = trade.get("exit_price", 0)
        lucro = trade.get("lucro_usdt", 0) or 0
        perda = trade.get("perda_usdt", 0) or 0
        retorno = trade.get("retorno_pct", 0) or 0
        signal_id = trade.get("signal_id", "---")
        classification = trade.get("classification", "")
        overall = trade.get("overall_score", 0) or 0
        rr = trade.get("risk_reward", 0) or 0
        quality = trade.get("quality", 0) or 0
        confidence = trade.get("confidence", 0) or 0
        consensus = trade.get("consensus", 0) or 0
        conviction = trade.get("conviction", "")
        time_to_tp1 = trade.get("time_to_tp1", 0) or 0
        time_to_stop = trade.get("time_to_stop", 0) or 0
        mae = trade.get("mae", 0) or 0
        mfe = trade.get("mfe", 0) or 0
        r_mult = trade.get("r_multiple", 0) or 0
        leverage = trade.get("leverage", 1)
        pos_value = trade.get("position_value", 0) or 0

        lines = [
            f"{emoji} *RESULTADO* | {asset} {direction} ({timeframe})",
            SEPARATOR,
        ]

        lines.append(f"\U0001f4b0 Entrada: `${entry:.4f}`")
        if exit_p:
            lines.append(f"\U0001f4c9 Sa\u00edda: `${exit_p:.4f}`")
        lines.append("")

        pnl = lucro - perda
        pnl_emoji = "\U0001f7e2" if pnl >= 0 else "\U0001f534"
        lines.append(f"{pnl_emoji} P&L: {_usdt(pnl)} ({_pct(retorno)})")
        if r_mult:
            lines.append(f"\U0001f3b0 R-M\u00faltiplo: {r_mult:.2f}R")
        if pos_value > 0:
            lines.append(f"\U0001f4bc Posi\u00e7\u00e3o: {_usdt(pos_value)} ({leverage}x)")

        lines.append(SEPARATOR)
        lines.append("\U0001f50d *Detalhes do Setup*")

        if overall:
            lines.append(f"\U0001f3af Overall Score: {overall:.1f}")
        if classification:
            lines.append(f"\U0001f3c6 Classifica\u00e7\u00e3o: {classification.upper()}")
        if rr:
            lines.append(f"\u2696\ufe0f RR: {rr:.2f}")
        if quality:
            qpct = quality * 100 if quality < 1 else quality
            lines.append(f"\u2b50 Quality: {qpct:.1f}")
        if confidence:
            cpct = confidence * 100 if confidence < 1 else confidence
            lines.append(f"\U0001f9e0 Confidence: {cpct:.1f}")
        if consensus:
            cnpct = consensus * 100 if consensus < 1 else consensus
            lines.append(f"\U0001f91d Consensus: {cnpct:.1f}")
        if conviction:
            lines.append(f"\U0001f9e0 Convic\u00e7\u00e3o: {conviction}")

        if time_to_tp1 > 0:
            lines.append(f"\u23f1 Tempo at\u00e9 TP1: {time_to_tp1:.1f}h")
        if time_to_stop > 0:
            lines.append(f"\u23f1 Tempo at\u00e9 Stop: {time_to_stop:.1f}h")
        if mae > 0:
            lines.append(f"\U0001f4c9 MAE: {mae:.2f}%")
        if mfe > 0:
            lines.append(f"\U0001f4c8 MFE: {mfe:.2f}%")

        lines.append(SEPARATOR)
        lines.append(f"Signal ID: `{signal_id}`")

        return "\n".join(lines)

    @staticmethod
    def format_setup_ranking(setups: list) -> str:
        if not setups:
            return "Nenhum setup registrado ainda."

        lines = ["\U0001f3c6 *RANKING DE SETUPS*", SEPARATOR]
        for i, s in enumerate(setups[:10], 1):
            wr = s.get("win_rate", 0)
            wr_icon = "\U0001f7e2" if wr >= 60 else "\U0001f7e1" if wr >= 40 else "\U0001f534"
            pf = s.get("profit_factor")
            pf_str = f"{pf:.2f}" if pf else "N/A"
            lines.append(
                f"{i}\u00b0 {s['setup']}\n"
                f"   {wr_icon} WR: {wr:.1f}% | PF: {pf_str} | "
                f"Trades: {s['total']} (W:{s['wins']} L:{s['losses']})"
            )
        return "\n".join(lines)

    @staticmethod
    def format_loss_analysis(loss_data: Dict) -> str:
        if not loss_data.get("total_losses"):
            return "Nenhuma perda registrada."

        lines = ["\U0001f534 *AN\u00c1LISE DAS DERROTAS*", SEPARATOR]
        lines.append(f"Total de perdas: {loss_data['total_losses']}")

        ranking = loss_data.get("weak_gate_ranking", [])
        if ranking:
            lines.append("")
            lines.append("*Ranking dos motivos:*")
            for gate, count, pct in ranking[:5]:
                bar = "\u2588" * max(1, round(pct / 10))
                lines.append(f"\u2022 {gate}: {count}x ({pct:.1f}%) {bar}")

        analysis = loss_data.get("analysis", [])
        if analysis:
            lines.append("")
            lines.append("*\u00daltimas perdas:*")
            for a in analysis[:5]:
                os_val = a.get("overall_score", 0)
                ret = a.get("retorno_pct", 0)
                lines.append(f"\u2022 {a['asset']} (OS:{os_val:.0f}) {_pct(ret)} | {a['main_reason']}")

        return "\n".join(lines)

    @staticmethod
    def format_weekly_report(report: Dict) -> str:
        if report.get("status") == "no_trades":
            return "Nenhuma opera\u00e7\u00e3o registrada nos \u00faltimos 7 dias."

        lines = [
            "\U0001f4c5 *RELAT\u00d3RIO SEMANAL*",
            f"Per\u00edodo: {report.get('period', '7 dias')}",
            SEPARATOR,
        ]

        total = report.get("total", 0)
        wr = report.get("win_rate")
        pf = report.get("profit_factor")
        dd = report.get("drawdown")
        ret = report.get("retorno_total", 0)
        exp = report.get("expectancy")

        lines.append(f"\U0001f4ca *Opera\u00e7\u00f5es*: {total}")
        if wr is not None:
            wr_icon = "\U0001f7e2" if wr >= 60 else "\U0001f7e1" if wr >= 40 else "\U0001f534"
            lines.append(f"{wr_icon} Win Rate: {wr:.1f}%")
        if pf is not None:
            pf_icon = "\U0001f7e2" if pf >= 2.0 else "\U0001f7e1" if pf >= 1.5 else "\U0001f534"
            lines.append(f"{pf_icon} Profit Factor: {pf:.2f}")
        if dd is not None:
            lines.append(f"\U0001f4c9 Drawdown: {dd:.2f} USDT")
        ret_icon = "\U0001f7e2" if ret >= 0 else "\U0001f534"
        lines.append(f"{ret_icon} Retorno: {_usdt(ret)}")
        if exp is not None:
            exp_icon = "\U0001f7e2" if exp > 0 else "\U0001f534"
            lines.append(f"{exp_icon} Expectancy: {exp:.2f} USDT")

        lines.append(SEPARATOR)
        lines.append(f"\U0001f3c6 *Melhor Ativo*: {report.get('best_asset', 'N/A')} ({_usdt(report.get('best_asset_pnl', 0))})")
        lines.append(f"\U0001f534 *Pior Ativo*: {report.get('worst_asset', 'N/A')} ({_usdt(report.get('worst_asset_pnl', 0))})")
        lines.append(f"\u23f0 *Melhor TF*: {report.get('best_timeframe', 'N/A')} ({_usdt(report.get('best_timeframe_pnl', 0))})")
        lines.append(f"\u23f0 *Pior TF*: {report.get('worst_timeframe', 'N/A')} ({_usdt(report.get('worst_timeframe_pnl', 0))})")
        lines.append(f"\U0001f3c6 *Melhor Class.*: {report.get('best_classification', 'N/A')}")
        lines.append(f"\U0001f534 *Pior Class.*: {report.get('worst_classification', 'N/A')}")

        by_cls = report.get("by_classification", {})
        if by_cls:
            lines.append(SEPARATOR)
            lines.append("*Por Classifica\u00e7\u00e3o*")
            for cls_name, cls_data in sorted(by_cls.items(), key=lambda x: x[1].get("wins", 0), reverse=True):
                if cls_name in ("N/A", ""):
                    continue
                wr_cls = cls_data.get("win_rate", 0)
                lines.append(f"\u2022 {cls_name.upper()}: {cls_data['total']} trades | WR {wr_cls:.1f}% | Ret {_pct(cls_data.get('avg_retorno_pct', 0))}")

        by_tf = report.get("by_timeframe", {})
        if by_tf:
            lines.append(SEPARATOR)
            lines.append("*Por Timeframe*")
            for tf_name, tf_data in sorted(by_tf.items(), key=lambda x: x[1].get("wins", 0), reverse=True):
                lines.append(f"\u2022 {tf_name}: {tf_data['total']} trades | WR {tf_data.get('win_rate', 0):.1f}%")

        loss_analysis = report.get("loss_analysis", {})
        if loss_analysis.get("weak_gate_ranking"):
            lines.append(SEPARATOR)
            lines.append("\U0001f534 *Motivos das Perdas*")
            for gate, count, pct in loss_analysis["weak_gate_ranking"][:3]:
                lines.append(f"\u2022 {gate}: {count}x ({pct:.1f}%)")

        return "\n".join(lines)
