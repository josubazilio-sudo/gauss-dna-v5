"""Backtest A/B — Compara versão atual com anterior"""

import json
import os
from datetime import datetime

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "state", "ab_state.json")


def _load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


class ComparadorAB:
    def __init__(self):
        self.state = _load_state()
        self.current = {
            "timestamp": datetime.now().isoformat(),
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0.0,
            "profit_factor": 0.0,
            "r_medio": 0.0,
            "total_r": 0.0,
            "drawdown": 0.0,
            "sinais_aprovados": 0,
            "sinais_bronze": 0,
            "sinais_prata": 0,
            "sinais_ouro": 0,
        }

    def registrar(self, trades, diag):
        self.current["trades"] = trades.total_trades
        self.current["wins"] = trades.wins
        self.current["losses"] = trades.losses
        self.current["winrate"] = trades.winrate
        self.current["profit_factor"] = trades.profit_factor
        self.current["r_medio"] = trades.avg_r
        self.current["total_r"] = trades.total_r
        self.current["drawdown"] = trades.drawdown_pct if hasattr(trades, "drawdown_pct") else 0
        self.current["sinais_aprovados"] = diag.total_aprovadas
        self.current["sinais_bronze"] = diag.bronze
        self.current["sinais_prata"] = diag.prata
        self.current["sinais_ouro"] = diag.ouro

    def comparar(self):
        anterior = self.state.get("anterior", {})
        if not anterior:
            return None
        diffs = {}
        for k in ("winrate", "profit_factor", "r_medio", "total_r", "drawdown", "trades", "sinais_aprovados"):
            v_ant = anterior.get(k, 0)
            v_cur = self.current.get(k, 0)
            if k in ("drawdown",):
                diffs[k] = v_cur - v_ant
            else:
                diffs[k] = v_cur - v_ant
        return diffs

    def salvar_como_anterior(self):
        self.state["anterior"] = self.current
        _save_state(self.state)

    def mensagem_relatorio(self):
        diffs = self.comparar()
        anterior = self.state.get("anterior", {})

        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            "📊 BACKTEST A/B — SINAIS TOP",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        if not anterior:
            lines.append("")
            lines.append("Primeira execução. Salvando como versão A...")
            lines.append("Execute novamente para ver a comparação A/B.")
            return "\n".join(lines)

        lines.append("")
        lines.append(f"          |  Versão A  |  Versão B  |  Diferença")
        lines.append(f"──────────┼────────────┼────────────┼────────────")

        labels = {
            "winrate": ("Win Rate", "%"),
            "profit_factor": ("Profit Factor", ""),
            "r_medio": ("R Médio", ""),
            "total_r": ("R Acumulado", ""),
            "drawdown": ("Drawdown", "%"),
            "trades": ("Trades", ""),
            "sinais_aprovados": ("Sinais Aprov", ""),
        }

        for k, (label, unit) in labels.items():
            v_ant = anterior.get(k, 0)
            v_cur = self.current.get(k, 0)
            diff = diffs.get(k, 0) if diffs else 0
            arrow = "🟢" if diff > 0 else ("🔴" if diff < 0 else "⚪")
            ant_s = f"{v_ant:.1f}{unit}" if unit else f"{v_ant:.1f}"
            cur_s = f"{v_cur:.1f}{unit}" if unit else f"{v_cur:.1f}"
            diff_s = f"{diff:+.1f}{unit}" if unit else f"{diff:+.1f}"
            lines.append(f"{label:14s} │ {ant_s:>10s} │ {cur_s:>10s} │ {arrow} {diff_s}")

        lines.append("")
        lines.append("📋 Distribuição dos Sinais:")
        lines.append(f"  Bronze: {anterior.get('sinais_bronze', 0)} → {self.current.get('sinais_bronze', 0)}")
        lines.append(f"  Prata:  {anterior.get('sinais_prata', 0)} → {self.current.get('sinais_prata', 0)}")
        lines.append(f"  Ouro:   {anterior.get('sinais_ouro', 0)} → {self.current.get('sinais_ouro', 0)}")

        if diffs:
            if diffs.get("profit_factor", 0) > 0 and diffs.get("winrate", 0) > 0:
                lines.append("")
                lines.append("✅ CONCLUSÃO: Versão B > Versão A (melhorou PF e WR)")
            elif diffs.get("profit_factor", 0) < 0 and diffs.get("winrate", 0) < 0:
                lines.append("")
                lines.append("⚠️ CONCLUSÃO: Versão A > Versão B (piorou PF e WR)")
            else:
                lines.append("")
                lines.append("📊 CONCLUSÃO: Resultados mistos — analisar métricas individuais")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
