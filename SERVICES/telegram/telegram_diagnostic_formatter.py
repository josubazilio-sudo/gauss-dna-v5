from ENGINE.diagnostic.engine import DiagnosticReport, STAGES
from ENGINE.diagnostic.advanced_report import build_advanced_report
from ENGINE.scanner.scanner_config import (
    QUALITY_GATE_MIN_SCORE, QUALITY_GATE_CONFIDENCE_MIN, QUALITY_GATE_RISK_MAX,
    CONSENSUS_MINIMUM_SCORE, DISCOVERY_MODE, MAX_SCAN_PAIRS,
)
from ENGINE.scanner.entry_zone import ENTRY_SCORE_MIN
from CORE.execution.mode_manager import ExecutionModeManager

STAGE_LABELS = {
    "carregamento": "Carregados",
    "api": "API",
    "candles": "Candles",
    "indicadores": "Indicadores",
    "estrutura": "Estrutura",
    "smart_money": "Smart Money",
    "entry_zone": "Entry Zone",
    "consensus": "Consensus",
    "quality_gate": "Quality Gate",
    "decisao_final": "Decisao Final",
}


class TelegramDiagnosticFormatter:
    @staticmethod
    def format(report: DiagnosticReport) -> str:
        import os
        if os.getenv("TELEGRAM_SEND_DIAGNOSTICS", "false").lower() != "true":
            return ""

        lines = [
            f"\U0001f4ca *QUANTOS \u2014 VALIDAÇÃO DE FILTROS* (Ciclo #{report.cycle_number})",
            "",
        ]

        assets = list(report.final_decisions.keys()) if report.final_decisions else []
        if not assets:
            lines.append("Nenhum ativo processado neste ciclo.")
            return "\n".join(lines)

        for asset in assets:
            lines.extend(TelegramDiagnosticFormatter._format_asset_validation(asset, report))

        ez_fail_assets = [
            a for a in assets
            if report.entry_zone_analysis.get(a, {}).get("result") == "FAIL"
        ]
        if ez_fail_assets:
            lines.append("")
            lines.append("\U0001f50d *ENTRY ZONE ANALYSIS*")
            for asset in ez_fail_assets:
                lines.extend(TelegramDiagnosticFormatter._format_entry_zone_analysis(asset, report))

        try:
            mode_mgr = ExecutionModeManager()
            exec_mode = mode_mgr.mode_name
        except Exception:
            exec_mode = "unknown"

        debug_mode = TelegramDiagnosticFormatter._is_debug()
        if debug_mode:
            lines.append("")
            lines.append("\U00002699 *CONFIGURAÇÃO UTILIZADA*")
            lines.append(f"Quality Min:      `{QUALITY_GATE_MIN_SCORE}`")
            lines.append(f"Confidence Min:   `{QUALITY_GATE_CONFIDENCE_MIN}`")
            lines.append(f"Consensus Min:    `{CONSENSUS_MINIMUM_SCORE:.0%}`")
            lines.append(f"Risk Max:         `{QUALITY_GATE_RISK_MAX}`")
            lines.append(f"Entry Score Min:  `{ENTRY_SCORE_MIN}`")
            lines.append(f"Execution Mode:   `{exec_mode}`")
            lines.append(f"Scanner Version:  `2.2`")
            lines.append(f"Diagnostic Ver:   `2.2`")

        lines.append("")
        lines.append("\U0001f504 *RELATÓRIO DO CICLO*")
        TelegramDiagnosticFormatter._format_cycle_summary(lines, report)

        lines.append("")
        TelegramDiagnosticFormatter._format_dashboard_metrics(lines, report)

        if report.approved_signals:
            lines.append("")
            lines.append("\U0001f3c6 *TOP SSR*")
            sorted_signals = sorted(report.approved_signals, key=lambda s: s.get("ssr", 0), reverse=True)
            for i, sig in enumerate(sorted_signals[:10], 1):
                ssr = sig.get("ssr", 0)
                asset = sig.get("asset", "?")
                direction = sig.get("direction", "?")
                lines.append(f"{i}\u00b0 {asset} {direction.upper()} | SSR {ssr:.0f}")

        pipeline_lines, pipeline_total = TelegramDiagnosticFormatter._format_pipeline(report)
        if pipeline_lines:
            lines.append("")
            lines.append("*PIPELINE*")
            lines.extend(pipeline_lines)

        if report.bugs:
            lines.append("")
            lines.append("\U0001f6a8 *BUGS DETECTADOS*")
            for bug in report.bugs[:3]:
                lines.append(f"\u2022 {bug.get('module')}: {bug.get('probable_cause', 'N/A')}")

        lines.append("")
        lines.append(f"\u23f1 Tempo total: {report.duration_ms:.0f}ms")

        msg = "\n".join(lines)
        MAX_TG = 4000
        if len(msg) > MAX_TG:
            msg = msg[:MAX_TG] + "\n\n[truncated]"
        return msg

    @staticmethod
    def format_advanced(report: DiagnosticReport) -> str:
        """RFC Diagnostico Avancado V7.0: relatorio de auditoria institucional
        (10 blocos). Gated por TELEGRAM_SEND_ADVANCED_DIAGNOSTICS (default
        false) para nao inflar o chat principal sem opt-in explicito.
        Somente leitura sobre dados ja calculados — nao afeta sinais."""
        import os
        if os.getenv("TELEGRAM_SEND_ADVANCED_DIAGNOSTICS", "false").lower() != "true":
            return ""

        data = build_advanced_report(report)
        lines = [f"\U0001f50e *DIAGNOSTICO AVANCADO* (Ciclo #{report.cycle_number})", ""]

        rs = data["resumo_scanner"]
        lines.append("*1. Resumo do Scanner*")
        lines.append(f"Exchange: `{rs['exchange']}` | Moedas: `{rs['quantidade_moedas']}` "
                      f"| Tempo: `{rs['tempo_ms']:.0f}ms` | Erros: `{rs['erros']}`")
        lines.append("")

        lines.append("*2. Funil do Scanner*")
        for stage in data["funil_granular"]:
            lines.append(f"{stage['estagio']}: `{stage['quantidade']}` ({stage['perda']})")
        lines.append("")

        lines.append("*3. Top Quase Aprovados*")
        for cand in data["top_quase_aprovados"][:10]:
            lines.append(f"{cand['ativo']} — Score `{cand['score']:.0f}` | Faltou: {cand['faltou']}")
        lines.append("")

        lines.append("*5. Ranking dos Bloqueadores*")
        for i, b in enumerate(data["ranking_bloqueadores"][:5], 1):
            lines.append(f"{i}. {b['motivo']} — `{b['percentual']:.0f}%`")
        lines.append("")

        mh = data["saude_mercado"]
        lines.append("*6. Saude do Mercado*")
        lines.append(f"Classificacao: `{mh.get('classificacao', 'N/A')}` "
                      f"(health `{mh.get('health_score', 0):.0f}%`)")
        lines.append("")

        lines.append("*7. Recomendacao Automatica*")
        lines.append(data["recomendacao_automatica"])
        lines.append("")

        lines.append("*8. Resumo Executivo*")
        lines.append(data["resumo_executivo"])
        lines.append("")

        stats = data["estatisticas_gerais"]
        lines.append("*9. Estatisticas Gerais*")
        lines.append(f"Aprovacao: `{stats['taxa_aprovacao']:.1f}%` | "
                      f"Reprovacao: `{stats['taxa_reprovacao']:.1f}%` | "
                      f"Ativos/min: `{stats['ativos_por_minuto']:.1f}`")

        msg = "\n".join(lines)
        MAX_TG = 4000
        if len(msg) > MAX_TG:
            msg = msg[:MAX_TG] + "\n\n[truncated]"
        return msg

    @staticmethod
    def _format_asset_validation(asset: str, report: DiagnosticReport) -> list:
        lines = []
        fd = report.final_decisions.get(asset, {})
        status = fd.get("status", "REJECTED")
        is_approved = status == "APPROVED"
        final_msg = fd.get("final_decision", "")

        qg = report.quality_gates.get(asset, {})
        scores = qg.get("scores", {})
        qs = scores.get("quality_score", 0.0)
        conf = scores.get("confidence_score", 0.0)
        risk = scores.get("risk_score", 0.0)
        inst = scores.get("institutional_score", 0.0)

        entry_data = report.entry_zones.get(asset, {})
        entry_score = entry_data.get("score", 0.0)

        cons_data = report.consensus.get(asset, {})
        cons_score = cons_data.get("consensus_score", 0)
        cons_dir = cons_data.get("final_direction", "none")
        decision_dir = fd.get("direction", "")

        sig_dir = decision_dir.upper() if decision_dir else (cons_dir.upper() if cons_dir != "none" else fd.get("primary_reason", "N/A"))

        lines.append(f"\U0001f539 *{asset} \u2014 {sig_dir}*")
        lines.append("")

        entries = TelegramDiagnosticFormatter._build_filter_entries(
            quality=qs, confidence=conf, risk=risk,
            institutional=inst, entry_score=entry_score,
            consensus=cons_score,
        )
        for label, value, threshold, op, result, is_gate in entries:
            if result == "PASS":
                icon = "\u2705"
            elif result == "FAIL":
                icon = "\u274c"
            else:
                icon = "\u2139\ufe0f"
            if isinstance(value, float):
                val_str = f"{value:.4f}" if value < 1 else f"{value:.1f}"
            else:
                val_str = str(value)
            if isinstance(threshold, float):
                th_str = f"{threshold:.4f}" if threshold < 1 else f"{threshold:.1f}"
            else:
                th_str = str(threshold)
            if op == "\u2265":
                cond = f"\u2265 {th_str}"
            elif op == "\u2264":
                cond = f"\u2264 {th_str}"
            else:
                cond = th_str
            lines.append(f"{icon} {label:<16} {val_str:>8}  {cond:>8}")

        lines.append("")

        primary = fd.get("primary_reason", "")
        if is_approved:
            lines.append(f"*STATUS:* \u2705 APROVADO")
            lines.append(f"Motivo: `{final_msg}`")
        else:
            failed = fd.get("failed_filter", primary)
            lines.append(f"*STATUS:* \u274c REPROVADO")
            lines.append(f"Filtro: `{failed}`")
            if primary:
                lines.append(f"Motivo: {primary}")

        lines.append("")
        return lines

    @staticmethod
    def _format_entry_zone_analysis(asset: str, report: DiagnosticReport) -> list:
        lines = []
        az = report.entry_zone_analysis.get(asset, {})
        if not az:
            return lines

        lines.append(f"")
        lines.append(f"\U0001f539 *{asset}*")
        lines.append("")

        cp = az.get("current_price", 0)
        atr = az.get("atr", 0)

        lines.append(f"Preço Atual:           `{cp:.2f}`")
        lines.append(f"ATR:                   `{atr:.4f}`")

        zones = az.get("zone_patterns", [])
        obs = [z for z in zones if z.get("type") == "order_block"]
        fvgs = [z for z in zones if z.get("type") == "fvg"]

        if obs:
            ob = obs[0]
            lines.append(f"Order Block Superior:  `{ob['upper']:.2f}`")
            lines.append(f"Order Block Inferior:  `{ob['lower']:.2f}`")
            lines.append(f"Preço Ideal (OB):      `{ob['ideal_price']:.2f}`")
            lines.append(f"Distância até OB:      `{ob['distance']:.2f}` ({ob['distance_pct']:.2f}%)")
            lines.append(f"Distância (ATRs):      `{ob['distance_atr']:.2f}`")
            lines.append(f"Status:                `{ob['status']}`")

            lines.append("")
            lines.append(f"Preço Atual {cp:.2f}")
            if ob["status"] == "above":
                lines.append(f"\u2193")
            elif ob["status"] == "below":
                lines.append(f"\u2191")
            else:
                lines.append(f"\u2194 (dentro da zona)")
            lines.append(f"Order Block {ob['ideal_price']:.2f}")
            lines.append(f"Diferença: {ob['distance']:.2f} ({ob['distance_pct']:.2f}%)")
        elif fvgs:
            fvg = fvgs[0]
            lines.append(f"FVG Superior:          `{fvg['upper']:.2f}`")
            lines.append(f"FVG Inferior:          `{fvg['lower']:.2f}`")
            lines.append(f"Preço Ideal (FVG):     `{fvg['ideal_price']:.2f}`")
            lines.append(f"Distância até FVG:     `{fvg['distance']:.2f}` ({fvg['distance_pct']:.2f}%)")
            lines.append(f"Distância (ATRs):      `{fvg['distance_atr']:.2f}`")
            lines.append(f"Status:                `{fvg['status']}`")

            lines.append("")
            lines.append(f"Preço Atual {cp:.2f}")
            if fvg["status"] == "above":
                lines.append(f"\u2193")
            elif fvg["status"] == "below":
                lines.append(f"\u2191")
            else:
                lines.append(f"\u2194 (dentro do gap)")
            lines.append(f"FVG {fvg['ideal_price']:.2f}")
            lines.append(f"Diferença: {fvg['distance']:.2f} ({fvg['distance_pct']:.2f}%)")

        lines.append("")
        score = az.get("score", 0)
        score_min = az.get("score_min", 40)
        lines.append(f"Entry Score:           `{score:.1f}` / `{score_min}`")
        lines.append(f"Resultado:             `{az.get('result', 'N/A')}`")

        failure = az.get("failure_reason", "")
        if failure:
            lines.append("")
            lines.append(f"Motivo: {failure}")

        multizone = len(zones)
        if multizone > 1:
            lines.append("")
            lines.append(f"*Padrões disponíveis:* `{multizone}` "
                         f"({', '.join(z['type'] for z in zones[:3])})")
            lines.append(f"Usado o primeiro `{zones[0]['type']}` (simplificação do algoritmo)")

        lines.append("")
        return lines

    @staticmethod
    def _build_filter_entries(
        quality: float, confidence: float, risk: float,
        institutional: float, entry_score: float, consensus: float,
    ):
        results = []

        q_pass = quality >= QUALITY_GATE_MIN_SCORE
        results.append(("Quality", quality, QUALITY_GATE_MIN_SCORE, "\u2265", "PASS" if q_pass else "FAIL", True))

        c_pass = confidence >= QUALITY_GATE_CONFIDENCE_MIN
        results.append(("Confidence", confidence, QUALITY_GATE_CONFIDENCE_MIN, "\u2265", "PASS" if c_pass else "FAIL", True))

        r_pass = risk <= QUALITY_GATE_RISK_MAX
        results.append(("Risk", risk, QUALITY_GATE_RISK_MAX, "\u2264", "PASS" if r_pass else "FAIL", True))

        entry_threshold = ENTRY_SCORE_MIN / 100.0
        e_pass = entry_score >= entry_threshold
        results.append(("Entry Score", entry_score, entry_threshold, "\u2265", "PASS" if e_pass else "FAIL", True))

        inst_pass = institutional >= 0.0
        results.append(("Institutional", institutional, 0.0, "\u2265", "INFO", False))

        cns_pass = consensus >= CONSENSUS_MINIMUM_SCORE
        results.append(("Consensus", f"{consensus*100:.0f}%", f"{CONSENSUS_MINIMUM_SCORE*100:.0f}%", "\u2265", "PASS" if cns_pass else "FAIL", False))

        return results

    @staticmethod
    def _get_entry_zone_status(asset: str, report: DiagnosticReport) -> str:
        az = report.entry_zone_analysis.get(asset, {})
        result = az.get("result", "N/A")
        if result == "FAIL":
            return "FORA DA ZONA IDEAL"
        if result == "PASS":
            return "NA ZONA"
        return "AGUARDANDO RETORNO A ZONA"

    @staticmethod
    def _format_cycle_summary(lines: list, report: DiagnosticReport):
        health = report.health or {}
        rejected = health.get("rejected", 0)
        approved = health.get("approved", 0)

        total_assets = report.total_assets
        processed = len(report.final_decisions)

        q_scores = [g.get("scores", {}).get("quality_score", 0) for g in report.quality_gates.values()]
        c_scores = [g.get("scores", {}).get("confidence_score", 0) for g in report.quality_gates.values()]
        e_scores = [e.get("score", 0) for e in report.entry_zones.values()]
        cons_scores = [c.get("consensus_score", 0) for c in report.consensus.values()]

        avg_q = sum(q_scores) / len(q_scores) if q_scores else 0
        avg_c = sum(c_scores) / len(c_scores) if c_scores else 0
        avg_e = sum(e_scores) / len(e_scores) if e_scores else 0
        avg_cons = sum(cons_scores) / len(cons_scores) if cons_scores else 0

        lines.append(f"Ativos monitorados:   `{total_assets}`")
        lines.append(f"Discovery:            `{DISCOVERY_MODE} (max {MAX_SCAN_PAIRS if MAX_SCAN_PAIRS is not None else 'ALL'})`")
        lines.append(f"Ativos processados:  `{processed}`")
        lines.append(f"Ativos aprovados:    `{approved}`")
        lines.append(f"Ativos rejeitados:   `{rejected}`")

        if report.rejection_reasons:
            reasons = sorted(report.rejection_reasons.items(), key=lambda x: -x[1])
            parts = ", ".join(f"{r}: {c}" for r, c in reasons[:3])
            lines.append(f"Rejeições por filtro: `{parts}`")
        else:
            lines.append(f"Rejeições por filtro: `(nenhuma)`")

        lines.append(f"Quality média:       `{avg_q:.4f}`")
        lines.append(f"Confidence média:    `{avg_c:.4f}`")
        lines.append(f"Consensus médio:     `{avg_cons:.1f}%`")
        lines.append(f"Entry Score médio:   `{avg_e:.1f}`")
        lines.append(f"Tempo médio:         `{report.duration_ms:.0f}ms`")
        lines.append(f"Health Score:        `{health.get('health_score', 100):.0f}%`")

        loop_status = health.get('loop_status', 'STOPPED')
        icon = '\U0001f7e2' if loop_status == 'RUNNING' else '\U0001f534'
        lines.append(f"Loop Principal:      `{icon} {loop_status}`")
        hb = health.get('last_heartbeat_ago_s', 0)
        lines.append(f"Ultimo heartbeat:    `{hb}s atras`")
        nx = health.get('next_cycle_in_s', 0)
        lines.append(f"Proximo ciclo em:   `{nx}s`")

    @staticmethod
    def _format_dashboard_metrics(lines: list, report: DiagnosticReport):
        try:
            from ENGINE.diagnostic.engine import DiagnosticEngine
            eng = DiagnosticEngine()
            metrics = eng.get_dashboard_metrics()
        except Exception:
            metrics = {}

        if not metrics.get("total_trades"):
            lines.append("\U0001f4ca *Dashboard Metrics*")
            lines.append("Nenhum trade registrado ainda.")
            return

        lines.append("\U0001f4ca *Dashboard Metrics*")
        if metrics.get("win_rate") is not None:
            wr = metrics["win_rate"]
            wr_icon = "\U0001f7e2" if wr >= 60 else "\U0001f7e1" if wr >= 40 else "\U0001f534"
            lines.append(f"{wr_icon} Win Rate: {wr:.1f}%")
        if metrics.get("profit_factor") is not None:
            pf = metrics["profit_factor"]
            pf_icon = "\U0001f7e2" if pf >= 2.0 else "\U0001f7e1" if pf >= 1.5 else "\U0001f534"
            lines.append(f"{pf_icon} Profit Factor: {pf:.2f}")
        if metrics.get("drawdown") is not None:
            lines.append(f"\U0001f4c9 Drawdown: {metrics['drawdown']:.2f} USDT")
        if metrics.get("total_trades"):
            lines.append(f"\U0001f4ca Total Trades: {metrics['total_trades']} (W:{metrics.get('total_wins', 0)} L:{metrics.get('total_losses', 0)})")
        if metrics.get("net_pnl") is not None:
            npnl = metrics["net_pnl"]
            npnl_icon = "\U0001f7e2" if npnl >= 0 else "\U0001f534"
            lines.append(f"{npnl_icon} P&L L\u00edquido: {npnl:+.2f} USDT")
        if metrics.get("avg_overall_score") is not None:
            lines.append(f"\U0001f3af Overall Score M\u00e9dio: {metrics['avg_overall_score']:.1f}")
        if metrics.get("avg_quality") is not None:
            lines.append(f"\u2b50 Quality M\u00e9dia: {metrics['avg_quality']:.2%}")
        if metrics.get("avg_confidence") is not None:
            lines.append(f"\U0001f9e0 Confidence M\u00e9dia: {metrics['avg_confidence']:.2%}")
        if metrics.get("avg_consensus") is not None:
            lines.append(f"\U0001f91d Consensus M\u00e9dio: {metrics['avg_consensus']:.2%}")
        if metrics.get("avg_retorno_pct") is not None:
            lines.append(f"\U0001f4b0 Retorno M\u00e9dio: {metrics['avg_retorno_pct']:.2f}%")
        if metrics.get("total_cycles"):
            lines.append(f"\U0001f504 Ciclos Executados: {metrics['total_cycles']}")
        if metrics.get("expectancy") is not None:
            exp = metrics["expectancy"]
            exp_icon = "\U0001f7e2" if exp > 0 else "\U0001f534"
            lines.append(f"{exp_icon} Expectancy: {exp:.2f}")

    @staticmethod
    def _format_pipeline(report: DiagnosticReport) -> tuple:
        lines = []
        total = max(report.total_assets, 1)

        # V18.1: Usar pipeline_funnel quando disponivel (mais preciso)
        if report.pipeline_funnel:
            funnel = report.pipeline_funnel
            total_start = funnel.get("ativos_analisados", total)
            lines.append(f"\u2022 Ativos analisados: {total_start}")

            stage_map = {
                "api": "API",
                "candles": "Candles",
                "indicadores": "Indicadores",
                "estrutura": "Estrutura",
                "smart_money": "Smart Money",
                "entry_zone": "Entry Zone",
                "consensus": "Consensus",
                "quality_gate": "Quality Gate",
                "decision_engine": "Decision Engine",
                "aprovados": "Aprovados",
            }

            prev = total_start
            for key, label in stage_map.items():
                blocked = funnel.get(key, 0)
                remaining = max(prev - blocked, 0)
                pct = (remaining / total_start * 100) if total_start > 0 else 0
                bar = TelegramDiagnosticFormatter._bar(pct)
                if blocked > 0:
                    lines.append(f"\u2022 {label}: {remaining} ({blocked} bloqueados) {bar}")
                else:
                    lines.append(f"\u2022 {label}: {remaining} {bar}")
                prev = remaining
        else:
            for stage in STAGES:
                label = STAGE_LABELS.get(stage, stage)
                count = sum(1 for s in report.pipeline_audit.values() if stage in s)
                pct = count / total * 100
                if stage == "quality_gate" and report.quality_gates:
                    approved = sum(1 for g in report.quality_gates.values() if g.get("passed"))
                    rejected = sum(1 for g in report.quality_gates.values() if not g.get("passed"))
                    bar = TelegramDiagnosticFormatter._bar(approved / max(len(report.quality_gates), 1) * 100)
                    lines.append(f"\u2022 {label}: {approved} aprovados ({rejected} rejeitados) {bar}")
                else:
                    bar = TelegramDiagnosticFormatter._bar(pct)
                    lines.append(f"\u2022 {label}: {count}/{report.total_assets} {bar}")
        return lines, total

    @staticmethod
    def _bar(pct: float, width: int = 10) -> str:
        filled = round(pct / 100 * width)
        return f"[{'#' * filled}{'.' * (width - filled)}] {pct:.0f}%"

    @staticmethod
    def _is_debug() -> bool:
        import os
        return os.getenv("QUANTOS_DEBUG", "true").lower() in ("true", "1", "yes")
