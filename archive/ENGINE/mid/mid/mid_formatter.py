import logging
from typing import Dict, List, Any, Optional

log = logging.getLogger(__name__)


class MIDFormatter:
    def format_dashboard(self, snapshot: Dict[str, Any], analyzer: Dict[str, Any], alerts: List[Dict]) -> str:
        lines = ["\U0001f4ca *QUANTOS MARKET DASHBOARD*", ""]

        lines.extend(self._format_system(snapshot))
        lines.extend(self._format_market(snapshot))
        lines.extend(self._format_funnel(snapshot))
        lines.extend(self._format_rejection_ranking(snapshot))
        lines.extend(self._format_opportunities(snapshot))
        lines.extend(self._format_heatmap(analyzer))
        lines.extend(self._format_alerts(alerts))
        lines.extend(self._format_trends(analyzer))
        lines.append("")
        lines.append("\u200b")

        return "\n".join(lines)

    def _format_system(self, snapshot: Dict) -> List[str]:
        sys = snapshot.get("system", {})
        health = sys.get("health_score", 100)
        status = sys.get("loop_status", "STOPPED")
        status_emoji = "\U0001f7e2" if health >= 80 else "\U0001f7e1" if health >= 50 else "\U0001f534"
        loop_emoji = "\U0001f7e2" if status == "RUNNING" else "\U0001f534"
        lines = [
            f"*Sistema*",
            f"{status_emoji} Health `{health:.0f}%`",
            f"{loop_emoji} Loop `{status}`",
            f"\u23f1 Tempo `{sys.get('duration_ms', 0):.0f}ms`",
            f"\U0001f4be Memoria `{sys.get('memory', 'N/A')}`",
            f"\U0001f4a1 CPU `{sys.get('cpu', 'N/A')}`",
            f"\U0001f310 API `{sys.get('api_calls', 0)} chamadas`",
            f"\U0001f41b Bugs `{sys.get('bug_count', 0)}`",
            f"\u23f3 Prox ciclo `{sys.get('next_cycle_in', 0)}s`",
            "",
        ]
        return lines

    def _format_market(self, snapshot: Dict) -> List[str]:
        market = snapshot.get("market", {})
        total = market.get("total_assets", 0)
        approved = market.get("approved", 0)
        rejected = market.get("rejected", 0)
        lines = [
            f"*Mercado*",
            f"\U0001f4ca Ativos `{total}` | \u2705 `{approved}` Aprov | \u274c `{rejected}` Rej",
            "",
        ]
        dist = market.get("regime_distribution", {})
        up = dist.get("uptrend", 0)
        down = dist.get("downtrend", 0)
        range_ = dist.get("ranging", 0)
        trans = dist.get("transition", 0)
        denom = max(total, 1)
        lines.append(f"\U0001f7e2 Uptrend `{up} ({up/denom*100:.0f}%)`")
        lines.append(f"\U0001f534 Downtrend `{down} ({down/denom*100:.0f}%)`")
        lines.append(f"\U0001f7e1 Ranging `{range_} ({range_/denom*100:.0f}%)`")
        lines.append(f"\U0001f535 Transition `{trans} ({trans/denom*100:.0f}%)`")
        lines.append("")

        avg = market.get("avg_metrics", {})
        lines.append(f"ADX medio `{avg.get('adx_medio', 'N/A')}`")
        lines.append(f"RVOL medio `{avg.get('rvol_medio', 'N/A')}x`")
        lines.append(f"ATR medio `{avg.get('atr_medio', 'N/A')}%`")
        lines.append(f"Quality media `{avg.get('quality_media', 'N/A')}`")
        lines.append(f"Consensus medio `{avg.get('consensus_medio', 'N/A')}`")
        lines.append(f"Confidence media `{avg.get('confidence_media', 'N/A')}`")
        lines.append(f"Entry Score medio `{avg.get('entry_score_medio', 'N/A')}`")
        lines.append("")
        return lines

    def _format_funnel(self, snapshot: Dict) -> List[str]:
        funnel = snapshot.get("funnel", {})
        lines = ["*Funil do Scanner*", f"`{'Etapa':<18} {'Qtd':>5} {'%':>6}`"]
        lines.append(f"`{'-'*30}`")
        for stage in ["carregamento", "api", "candles", "indicadores", "estrutura",
                        "smart_money", "entry_zone", "consensus", "quality_gate", "decisao_final"]:
            info = funnel.get(stage, {})
            count = info.get("count", 0)
            pct = info.get("pct", 0)
            bar = self._bar(pct / 100)
            lines.append(f"`{stage:<18} {count:>5} {pct:>5.1f}% {bar}`")
        aprov = funnel.get("aprovados", {})
        rej = funnel.get("rejeitados", {})
        lines.append(f"`{'-'*30}`")
        lines.append(f"`{'Aprovados':<18} {aprov.get('count', 0):>5} {aprov.get('pct', 0):>5.1f}%`")
        lines.append(f"`{'Rejeitados':<18} {rej.get('count', 0):>5} {rej.get('pct', 0):>5.1f}%`")
        lines.append("")
        return lines

    def _format_rejection_ranking(self, snapshot: Dict) -> List[str]:
        ranking = snapshot.get("rejection_ranking", [])
        if not ranking:
            return []
        lines = ["*Principais Motivos de Rejeicao*"]
        emojis = ["\U0001f947", "\U0001f948", "\U0001f949"]
        for i, r in enumerate(ranking[:5]):
            emoji = emojis[i] if i < 3 else f"{i+1}."
            lines.append(f"{emoji} {r['motivo']}: `{r['count']} ({r['pct']:.0f}%)`")
        lines.append("")
        return lines

    def _format_opportunities(self, snapshot: Dict) -> List[str]:
        opps = snapshot.get("opportunities", [])
        if not opps:
            return []
        lines = ["*TOP Oportunidades*"]
        for opp in opps[:5]:
            quality = opp.get("quality", 0)
            status = "\u2705 Quase aprovado" if quality >= 0.4 else "\u274c Longe"
            lines.append(
                f"`{opp.get('asset', 'N/A'):<12}` Quality `{quality:.2f}`"
            )
            lines.append(f"`{'':12}` Motivo: `{opp.get('reason', 'N/A')}`")
            lines.append(f"`{'':12}` {status}")
        lines.append("")
        return lines

    def _format_heatmap(self, analyzer: Dict) -> List[str]:
        if not analyzer:
            return []
        heatmap = analyzer.get("heatmap", {})
        if not heatmap:
            return []
        lines = ["*Heatmap do Mercado*"]
        colors = {"Forte Tendencia": "\U0001f7e2", "Transicao": "\U0001f7e1", "Lateralizacao": "\U0001f534"}
        for label in ["Forte Tendencia", "Transicao", "Lateralizacao"]:
            pct = heatmap.get(label, 0)
            emoji = colors.get(label, "")
            bar = self._bar(pct / 100)
            lines.append(f"{emoji} {label}: `{pct:.0f}%` {bar}")
        lines.append("")
        return lines

    def _format_alerts(self, alerts: List[Dict]) -> List[str]:
        if not alerts:
            return []
        lines = ["*Alertas*"]
        for a in alerts:
            lines.append(f"\u26a0\ufe0f `{a.get('message', '')}`")
        lines.append("")
        return lines

    def _format_trends(self, analyzer: Dict) -> List[str]:
        trends = analyzer.get("trends", {})
        if not trends:
            return []
        lines = ["*Evolucao (ultimos 10 ciclos)*"]
        for key, label in [
            ("health_trend", "Health"),
            ("quality_trend", "Quality"),
            ("consensus_trend", "Consensus"),
            ("signal_count_trend", "Sinais"),
        ]:
            series = trends.get(key, [])
            if series:
                first = series[0]
                last = series[-1]
                arrow = "\u2197" if last > first else "\u2198" if last < first else "\u2192"
                lines.append(f"{arrow} {label}: `{first}` \u2192 `{last}`")
        if not lines:
            return []
        lines.append("")
        return lines

    @staticmethod
    def _bar(pct: float, width: int = 10) -> str:
        filled = max(0, min(width, int(pct * width)))
        empty = width - filled
        return "\u2588" * filled + "\u2591" * empty
