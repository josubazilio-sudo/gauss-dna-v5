"""RFC V20.0 Fase 8 — App QuantOS (camada de apresentacao).

Consome APENAS os dicts ja produzidos por dashboard.py, trade_storage.py,
statistics.py, equity.py, performance_insights.py e risk_manager.py. Nao
executa nenhuma logica operacional — apenas formata texto para exibicao.

Limitacao transparente: implementado aqui como formatacao de texto
(CLI/terminal), nao como app Android nativo — fora do escopo realista
deste ambiente de desenvolvimento. A camada de dados (Fases 1-7) ja fica
pronta para um app real consumir depois.
"""
from typing import Dict, List

MENU_ITEMS = [
    ("1", "\U0001f3e0 Dashboard"),
    ("2", "\U0001f4c8 Scanner"),
    ("3", "\U0001f4d2 Operacoes"),
    ("4", "\U0001f4ca Analytics"),
    ("5", "\U0001f4b0 Gestao"),
    ("6", "⚙ Configuracoes"),
]


def render_menu() -> str:
    lines = ["QUANTOS — MENU"]
    for key, label in MENU_ITEMS:
        lines.append(f"{key}. {label}")
    return "\n".join(lines)


def render_dashboard(dashboard_data: Dict) -> str:
    d = dashboard_data
    lines = [
        "\U0001f3e0 DASHBOARD",
        f"Scanner: {d.get('scanner_status', 'N/A')}",
        f"Mercado: {d.get('mercado', 'N/A')}",
        f"Operacoes hoje: {d.get('operacoes_hoje', 0)} "
        f"(W:{d.get('wins_hoje', 0)} L:{d.get('losses_hoje', 0)})",
        f"Win Rate: {d.get('win_rate')}",
        f"Profit Factor: {d.get('profit_factor')}",
        f"Drawdown: {d.get('drawdown')}",
        f"Lucro hoje: {d.get('lucro_hoje')}",
        f"Banca: {d.get('banca')}",
        f"Melhor ativo: {d.get('melhor_ativo')}",
        f"Pior ativo: {d.get('pior_ativo')}",
        f"Melhor horario: {d.get('melhor_horario')}",
        f"Melhor timeframe: {d.get('melhor_timeframe')}",
        f"Proximo ciclo em: {d.get('proximo_ciclo_em_s')}s",
    ]
    return "\n".join(lines)


def render_operacoes(trades: List[Dict], limit: int = 10) -> str:
    lines = ["\U0001f4d2 OPERACOES"]
    if not trades:
        lines.append("Nenhuma operacao registrada.")
        return "\n".join(lines)
    for t in trades[:limit]:
        lines.append(
            f"{t.get('data')} {t.get('hora')} | {t.get('ativo')} {t.get('direcao')} "
            f"{t.get('timeframe')} | {t.get('status')} {t.get('resultado') or ''}"
        )
    return "\n".join(lines)


def render_analytics(metrics: Dict, insights: Dict) -> str:
    lines = [
        "\U0001f4ca ANALYTICS",
        f"Win Rate: {metrics.get('win_rate')}",
        f"Profit Factor: {metrics.get('profit_factor')}",
        f"Maior sequencia WIN: {metrics.get('max_win_streak')}",
        f"Maior sequencia LOSS: {metrics.get('max_loss_streak')}",
        f"Melhor ativo: {insights.get('melhor_ativo')}",
        f"Pior ativo: {insights.get('pior_ativo')}",
        f"Melhor horario: {insights.get('melhor_horario')}",
        f"Melhor dia: {insights.get('melhor_dia')}",
        f"Melhor setup: {insights.get('melhor_setup')}",
    ]
    return "\n".join(lines)


def render_gestao(risk_result: Dict) -> str:
    lines = [
        "\U0001f4b0 GESTAO DE RISCO",
        f"Quantidade: {risk_result.get('quantidade')}",
        f"Valor da posicao: {risk_result.get('valor_posicao')}",
        f"Perda maxima: {risk_result.get('perda_maxima')}",
        f"Lucro esperado: {risk_result.get('lucro_esperado')}",
        f"RR: {risk_result.get('rr')}",
        f"Alavancagem sugerida: {risk_result.get('alavancagem_sugerida')}x",
    ]
    return "\n".join(lines)


def render_configuracoes(config: Dict) -> str:
    lines = ["⚙ CONFIGURACOES"]
    for key, value in config.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines)
