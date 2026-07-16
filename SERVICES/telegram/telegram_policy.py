"""RFC V26.4 — Politica de envio para o Telegram.

O Telegram do QuantOS e um canal operacional (sinais + alertas com acao),
nao um console de logs. Mensagens sem utilidade operacional devem ser
canceladas antes do envio e permanecer apenas no log interno.

Este modulo cobre a unica categoria de mensagem que e "rotina, mas as
vezes relevante": o relatorio periodico (ex.: 30min). As demais
categorias ja sao inerentemente condicionais no ponto onde sao geradas
(novo sinal aprovado, alerta imediato do Fast Diagnostic, validacao de
mudanca de parametro do Calibration Engine) e nao passam por aqui.
"""
from typing import Any, Dict, Optional, Tuple


def should_send_telegram(
    report: Dict[str, Any], previous_report: Optional[Dict[str, Any]],
) -> Tuple[bool, str]:
    """Decide se um relatorio periodico deve ser enviado ao Telegram.

    So autoriza o envio quando ha mudanca operacionalmente relevante
    desde o relatorio anterior (saude do scanner, bug novo, gargalo novo,
    crescimento anormal de gate, nova validacao de calibracao pendente).
    Nunca autoriza como heartbeat de rotina. Retorna (deve_enviar, motivo).
    """
    if previous_report is None:
        return True, "primeiro relatorio da sessao"

    health = report.get("scanner_health")
    prev_health = previous_report.get("scanner_health")
    if health != prev_health:
        return True, f"saude do scanner mudou: {prev_health} -> {health}"

    bugs = report.get("potential_bugs") or []
    prev_bugs = previous_report.get("potential_bugs") or []
    prev_bug_gates = {b.get("gate") for b in prev_bugs}
    novos_bugs = [b for b in bugs if b.get("gate") not in prev_bug_gates]
    if novos_bugs:
        return True, f"novo bug suspeito detectado: {novos_bugs[0].get('gate')}"

    growth = report.get("gate_greatest_growth")
    if growth and growth.get("status") == "anormal":
        prev_growth = previous_report.get("gate_greatest_growth") or {}
        if prev_growth.get("gate") != growth.get("gate"):
            return True, (
                f"gate {growth.get('gate')} com crescimento anormal "
                f"({growth.get('delta_pp', 0):+.1f}pp)"
            )

    curr_bottlenecks = {b["gate"] for b in report.get("potential_bottlenecks", [])}
    prev_bottlenecks = {b["gate"] for b in previous_report.get("potential_bottlenecks", [])}
    novos_gargalos = curr_bottlenecks - prev_bottlenecks
    if novos_gargalos:
        return True, f"novo gargalo detectado: {', '.join(sorted(novos_gargalos))}"

    pending = report.get("pending_validations") or []
    prev_pending = previous_report.get("pending_validations") or []
    if len(pending) > len(prev_pending):
        return True, "nova validacao de parametro de calibracao pendente"

    return False, "sem mudanca operacional relevante desde o ultimo relatorio"
