import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .backtest_audit import BacktestResult

log = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).parent / "data"


class PerformanceDashboard:
    def __init__(self):
        self._dir = DASHBOARD_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def generate(self, result: BacktestResult, filename: str = "dashboard.html") -> str:
        path = self._dir / filename
        html = self._build_html(result)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        log.info("PerformanceDashboard: generated %s", path)
        return str(path)

    def _build_html(self, result: BacktestResult) -> str:
        equity_json = str(result.equity_curve)
        dd_json = str(result.drawdown_curve)
        monthly_json = str(list(result.monthly_pnl.items())) if result.monthly_pnl else "[]"
        pnl_dist_json = str(result.pnl_distribution) if result.pnl_distribution else "[]"

        def _fmt(c, v):
            if isinstance(v, float):
                if c in ("win_rate", "profit_factor") and v < 10:
                    return f"{v:.1%}"
                return f"{v:.2f}"
            return str(v)

        def table_rows(data, cols):
            rows = ""
            for key, stats in sorted(data.items()):
                rows += "<tr>"
                for c in cols:
                    rows += f"<td>{_fmt(c, stats.get(c, 0))}</td>"
                rows += "</tr>\n"
            return rows

        by_asset_rows = table_rows(result.by_asset,
            ["trades", "wins", "win_rate", "avg_rr", "profit_factor", "net_pnl"])
        by_tf_rows = table_rows(result.by_timeframe, ["trades", "wins", "win_rate", "profit_factor"])
        by_class_rows = table_rows(result.by_classification, ["trades", "wins", "win_rate", "profit_factor"])
        by_regime_rows = table_rows(result.by_regime, ["trades", "wins", "win_rate", "profit_factor"])
        by_dir_rows = table_rows(result.by_direction, ["trades", "wins", "win_rate", "avg_rr"])

        trade_rows = ""
        for t in result.trades[-50:]:
            cls = "win" if t.result == "win" else "loss"
            trade_rows += f"""
            <tr class="{cls}">
                <td>{t.pair}</td>
                <td>{t.timeframe}</td>
                <td>{t.direction}</td>
                <td>{t.entry_price:.2f}</td>
                <td>{t.result}</td>
                <td>{t.profit_loss_pct:.2%}</td>
                <td>{t.classification}</td>
                <td>{t.rr:.2f}</td>
                <td>{t.duration_h:.1f}h</td>
            </tr>"""

        heatmap_asset_tf = ""
        for asset, stats in sorted(result.by_asset.items()):
            wr = stats.get("win_rate", 0)
            color = f"hsl({120 * wr}, 70%, {40 + 20 * (1 - wr)}%)"
            heatmap_asset_tf += f"<div class='hm-cell' style='background:{color}' title='{asset}: {wr:.1%}'>{asset}<br><small>{wr:.1%}</small></div>"

        heatmap_class = ""
        hierarchy = ["ouro_supremo", "ouro", "prata", "bronze", "reprovado"]
        for cl in hierarchy:
            if cl in result.by_classification:
                wr = result.by_classification[cl].get("win_rate", 0)
                color = f"hsl({120 * wr}, 70%, {40 + 20 * (1 - wr)}%)"
                heatmap_class += f"<div class='hm-cell' style='background:{color}' title='{cl}: {wr:.1%}'>{cl}<br><small>{wr:.1%}</small></div>"

        wf_html = ""
        if result.walk_forward_results:
            wf = result.walk_forward_results
            wf_html = f"""
            <h2>Walk Forward Validation</h2>
            <div class='chart-container'>
                <table>
                <tr><th>Período</th><th>Trades</th><th>Win Rate</th><th>Profit Factor</th><th>Avg RR</th></tr>
                <tr><td>In-Sample (treino)</td><td>{wf.get('in_sample', {}).get('trades', 0)}</td>
                    <td>{wf.get('in_sample', {}).get('win_rate', 0):.1%}</td>
                    <td>{wf.get('in_sample', {}).get('profit_factor', 0):.2f}</td>
                    <td>{wf.get('in_sample', {}).get('avg_rr', 0):.2f}</td></tr>
                <tr><td>Out-of-Sample (teste)</td><td>{wf.get('out_sample', {}).get('trades', 0)}</td>
                    <td>{wf.get('out_sample', {}).get('win_rate', 0):.1%}</td>
                    <td>{wf.get('out_sample', {}).get('profit_factor', 0):.2f}</td>
                    <td>{wf.get('out_sample', {}).get('avg_rr', 0):.2f}</td></tr>
                <tr><td colspan='5' style='border:0; padding:4px;'></td></tr>
                <tr><td><strong>Robustness Score</strong></td><td colspan='4'>{wf.get('robustness_score', 0):.2%}</td></tr>
                <tr><td><strong>Strategy Decay</strong></td><td colspan='4'>{wf.get('decay', 0):.2%}</td></tr>
                </table>
            </div>"""

        ranking_rows = ""
        for ranking in result.feature_ranking[:20]:
            ranking_rows += f"""
            <tr>
                <td>{ranking['feature']}</td>
                <td>{ranking['wins']}/{ranking['total']}</td>
                <td>{ranking['win_rate']:.1%}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QuantOS V2.1 — Performance Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:#0d1117; color:#c9d1d9; padding:20px; }}
h1 {{ color:#58a6ff; font-size:24px; margin-bottom:8px; }}
h2 {{ color:#f0f6fc; font-size:18px; margin:24px 0 12px; border-bottom:1px solid #30363d; padding-bottom:6px; }}
.subtitle {{ color:#8b949e; font-size:14px; margin-bottom:24px; }}
.metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
           gap:10px; margin-bottom:24px; }}
.card {{ background:#161b22; border:1px solid #30363d; border-radius:8px;
        padding:14px; text-align:center; }}
.card .value {{ font-size:22px; font-weight:600; color:#f0f6fc; }}
.card .label {{ font-size:11px; color:#8b949e; margin-top:4px; }}
.card.positive .value {{ color:#3fb950; }}
.card.negative .value {{ color:#f85149; }}
.card.warning .value {{ color:#d29922; }}
.chart-container {{ background:#161b22; border:1px solid #30363d; border-radius:8px;
                   padding:16px; margin-bottom:24px; }}
table {{ width:100%; border-collapse:collapse; margin-bottom:24px; font-size:12px; }}
th, td {{ padding:6px 10px; text-align:left; border-bottom:1px solid #30363d; }}
th {{ color:#8b949e; font-weight:500; text-transform:uppercase; font-size:10px; }}
tr:hover td {{ background:#1c2128; }}
tr.win td {{ border-left:3px solid #3fb950; background:#0f2d14; }}
tr.loss td {{ border-left:3px solid #f85149; background:#2d0f0f; }}
.heatmap {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:24px; }}
.hm-cell {{ width:120px; height:60px; border-radius:6px; display:flex;
            flex-direction:column; align-items:center; justify-content:center;
            font-size:12px; font-weight:500; color:#fff; text-shadow:0 1px 2px rgba(0,0,0,0.5); }}
.hm-cell small {{ font-weight:400; opacity:0.8; }}
.footer {{ text-align:center; color:#484f58; font-size:10px; margin-top:40px;
           border-top:1px solid #30363d; padding-top:16px; }}
.split {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
@media (max-width:768px) {{ .split {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>

<h1>QuantOS V2.1 — Performance Dashboard</h1>
<p class="subtitle">Gerado em {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | {result.total_trades} operações analisadas | PF={result.profit_factor:.2f} WR={result.win_rate:.1%}</p>

<div class="metrics">
    <div class="card {'positive' if result.win_rate >= 0.40 else 'negative'}">
        <div class="value">{result.win_rate:.1%}</div>
        <div class="label">Win Rate</div>
    </div>
    <div class="card {'positive' if result.profit_factor >= 1.5 else 'negative'}">
        <div class="value">{result.profit_factor:.2f}</div>
        <div class="label">Profit Factor</div>
    </div>
    <div class="card {'positive' if result.max_drawdown <= 0.10 else 'negative'}">
        <div class="value">{result.max_drawdown:.2%}</div>
        <div class="label">Max Drawdown</div>
    </div>
    <div class="card {'positive' if result.expectancy > 0 else 'negative'}">
        <div class="value">{result.expectancy:.4f}</div>
        <div class="label">Expectância</div>
    </div>
    <div class="card {'positive' if result.sharpe_ratio >= 1.2 else 'negative'}">
        <div class="value">{result.sharpe_ratio:.2f}</div>
        <div class="label">Sharpe</div>
    </div>
    <div class="card {'positive' if result.sortino_ratio >= 1.8 else 'negative'}">
        <div class="value">{result.sortino_ratio:.2f}</div>
        <div class="label">Sortino</div>
    </div>
    <div class="card {'positive' if result.calmar_ratio >= 1.0 else 'warning'}">
        <div class="value">{result.calmar_ratio:.2f}</div>
        <div class="label">Calmar</div>
    </div>
    <div class="card">
        <div class="value">{result.avg_rr:.2f}</div>
        <div class="label">Média RR</div>
    </div>
    <div class="card">
        <div class="value">{result.total_trades}</div>
        <div class="label">Total Trades</div>
    </div>
    <div class="card">
        <div class="value">{result.avg_trade_duration_h:.1f}h</div>
        <div class="label">Duração Média</div>
    </div>
    <div class="card {'positive' if result.net_pnl > 0 else 'negative'}">
        <div class="value">${result.net_pnl:.2f}</div>
        <div class="label">P&L Líquido</div>
    </div>
    <div class="card">
        <div class="value">{result.gross_profit:.0f}/{result.gross_loss:.0f}</div>
        <div class="label">Bruto G/P</div>
    </div>
</div>

<h2>Equity Curve</h2>
<div class="chart-container">
    <canvas id="equityChart" height="200"></canvas>
</div>

<h2>Drawdown</h2>
<div class="chart-container">
    <canvas id="ddChart" height="150"></canvas>
</div>

<div class="split">
<div>
<h2>P&L Mensal</h2>
<div class="chart-container">
    <canvas id="monthlyChart" height="200"></canvas>
</div>
</div>
<div>
<h2>Distribuição dos P&Ls</h2>
<div class="chart-container">
    <canvas id="distChart" height="200"></canvas>
</div>
</div>
</div>

{wf_html}

<div class="split">
<div>
<h2>Heatmap — Ativos</h2>
<div class="heatmap">{heatmap_asset_tf}</div>
</div>
<div>
<h2>Heatmap — Classes</h2>
<div class="heatmap">{heatmap_class}</div>
</div>
</div>

<div class="split">
<div>
<h2>Estatísticas por Ativo</h2>
<table>
<tr><th>Ativo</th><th>Trades</th><th>Wins</th><th>WR</th><th>Avg RR</th><th>PF</th><th>P&L</th></tr>
{by_asset_rows}
</table>
</div>
<div>
<h2>Estatísticas por Timeframe</h2>
<table>
<tr><th>TF</th><th>Trades</th><th>Wins</th><th>WR</th><th>PF</th></tr>
{by_tf_rows}
</table>
</div>
</div>

<div class="split">
<div>
<h2>Estatísticas por Classe</h2>
<table>
<tr><th>Classe</th><th>Trades</th><th>Wins</th><th>WR</th><th>PF</th></tr>
{by_class_rows}
</table>
</div>
<div>
<h2>Estatísticas por Regime</h2>
<table>
<tr><th>Regime</th><th>Trades</th><th>Wins</th><th>WR</th><th>PF</th></tr>
{by_regime_rows}
</table>
</div>
</div>

<div class="split">
<div>
<h2>Estatísticas por Direção</h2>
<table>
<tr><th>Direção</th><th>Trades</th><th>Wins</th><th>WR</th><th>Avg RR</th></tr>
{by_dir_rows}
</table>
</div>
<div>
<h2>Ranking de Features (Top 20)</h2>
<table>
<tr><th>Feature</th><th>Wins/Total</th><th>WR</th></tr>
{ranking_rows}
</table>
</div>
</div>

<h2>Últimas 50 Operações</h2>
<div style="overflow-x:auto;">
<table>
<tr><th>Par</th><th>TF</th><th>Dir</th><th>Entrada</th><th>Result</th><th>P&L</th><th>Classe</th><th>RR</th><th>Duração</th></tr>
{trade_rows}
</table>
</div>

<div class="footer">QuantOS V2.1 — Institutional Performance Dashboard | Metas: PF ≥ 1.50 · WR ≥ 40% · DD ≤ 10% · Sharpe ≥ 1.20</div>

<script>
const equityData = {equity_json};
const ddData = {dd_json};
const monthlyData = {monthly_json};
const pnlDistData = {pnl_dist_json};

function createChart(id, data, color, label, fill, inverted) {{
    const canvas = document.getElementById(id);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.parentElement.clientWidth - 32;
    const h = canvas.height;
    canvas.width = w;

    if (!data || data.length < 2) {{
        ctx.fillStyle = '#484f58';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Dados insuficientes', w/2, h/2);
        return;
    }}

    const max = Math.max(...data, 1);
    const min = Math.min(...data, 0);
    const range = max - min || 1;

    ctx.clearRect(0, 0, w, h);
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;

    data.forEach((v, i) => {{
        const x = (i / (data.length - 1)) * w;
        let y;
        if (inverted) {{
            y = ((v - min) / range) * (h - 20) + 10;
        }} else {{
            y = h - ((v - min) / range) * (h - 20) - 10;
        }}
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }});
    ctx.stroke();

    if (fill) {{
        ctx.fillStyle = color + '20';
        const lastX = ((data.length - 1) / (data.length - 1)) * w;
        ctx.lineTo(lastX, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        ctx.fill();
    }}

    ctx.fillStyle = '#8b949e';
    ctx.font = '10px sans-serif';
    ctx.fillText(label, 4, 12);
}}

function createBarChart(id, data, color) {{
    const canvas = document.getElementById(id);
    if (!canvas || !data || data.length < 1) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.parentElement.clientWidth - 32;
    const h = canvas.height;
    canvas.width = w;

    const values = data.map(d => d[1] || 0);
    const max = Math.max(...values.map(Math.abs), 1);
    const barW = Math.max(2, (w / data.length) - 2);

    ctx.clearRect(0, 0, w, h);
    const mid = h / 2;

    ctx.strokeStyle = '#30363d';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, mid);
    ctx.lineTo(w, mid);
    ctx.stroke();

    data.forEach((d, i) => {{
        const val = d[1] || 0;
        const barH = (Math.abs(val) / max) * (h / 2 - 10);
        const x = i * (barW + 2);
        ctx.fillStyle = val >= 0 ? '#3fb950' : '#f85149';
        if (val >= 0) {{
            ctx.fillRect(x, mid - barH, barW, barH);
        }} else {{
            ctx.fillRect(x, mid, barW, barH);
        }}
    }});
}}

function createDistChart(id, data, color) {{
    const canvas = document.getElementById(id);
    if (!canvas || !data || data.length < 5) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.parentElement.clientWidth - 32;
    const h = canvas.height;
    canvas.width = w;

    const min = Math.min(...data);
    const max = Math.max(...data);
    const bins = 30;
    const binW = (max - min) / bins || 1;
    const hist = new Array(bins).fill(0);
    data.forEach(v => {{
        const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / binW)));
        hist[idx]++;
    }});
    const histMax = Math.max(...hist, 1);
    const barW = w / bins;

    ctx.clearRect(0, 0, w, h);
    hist.forEach((count, i) => {{
        const barH = (count / histMax) * (h - 20);
        ctx.fillStyle = i < bins/2 ? '#f85149' : '#3fb950';
        ctx.fillRect(i * barW, h - barH - 10, barW - 1, barH);
    }});
}}

window.addEventListener('load', function() {{
    createChart('equityChart', equityData, '#58a6ff', 'Equity', true);
    createChart('ddChart', ddData, '#f85149', 'Drawdown', true, true);
    createBarChart('monthlyChart', monthlyData, '#58a6ff');
    createDistChart('distChart', pnlDistData, '#58a6ff');
}});
</script>
</body>
</html>"""
        return html
