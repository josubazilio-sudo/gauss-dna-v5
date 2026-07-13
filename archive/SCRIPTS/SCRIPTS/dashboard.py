"""Dashboard Analítico QuantOS — Métricas de desempenho em tempo real."""
import sys
import os
import io
from collections import Counter, defaultdict
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'quantos.log')


def parse_logs():
    metrics = {
        'total_assets_scanned': set(),
        'setups': 0,
        'signals_approved': 0,
        'signals_rejected': 0,
        'signals_sent': 0,
        'classification_dist': Counter(),
        'blockers': Counter(),
        'near_miss': Counter(),
        'cycle_times': [],
        'decisions': [],
        'trends': Counter(),
        'kalman_dirs': Counter(),
    }

    if not os.path.exists(LOG_FILE):
        return metrics

    lines = []
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    for line in lines:
        # --- Cycle detection ---
        if 'Ciclo de scan' in line:
            metrics['setups'] += 1

        # --- SD[ decisions ---
        if 'SD[' in line and 'aprov=' in line:
            parts = line.split('|')
            aprov = None
            qual = None
            direction = None
            reject = None

            for p in parts:
                p = p.strip()
                if p.startswith('aprov='):
                    aprov = p.split('=')[1].strip() == 'True'
                elif p.startswith('qual='):
                    try:
                        qual = float(p.split('=')[1].strip())
                    except:
                        pass
                elif p.startswith('dir='):
                    direction = p.split('=')[1].strip()
                elif 'Trend' in p or 'desfavor' in p:
                    reject = p.strip()

            # Extract ticker
            sd_match = line.split('SD[')
            if len(sd_match) > 1:
                ticker_part = sd_match[1].split(']')[0]
                ticker = ticker_part.split(' ')[0] if ' ' in ticker_part else ticker_part
                metrics['total_assets_scanned'].add(ticker)

            if aprov is not None:
                entry_data = {
                    'approved': aprov,
                    'quality': qual,
                    'direction': direction,
                    'reject_reason': reject,
                }
                metrics['decisions'].append(entry_data)

                if aprov:
                    metrics['signals_approved'] += 1
                else:
                    metrics['signals_rejected'] += 1
                    if reject:
                        bl = reject.split('(')[0].strip() if '(' in reject else reject
                        metrics['blockers'][bl] += 1

        # --- Approval reasons ---
        if 'Motivos:' in line or 'approval_reason' in line.lower():
            metrics['signals_sent'] += 1

        # --- Trends ---
        if 'TRACE[' in line and 'Trend:' in line:
            trend_part = line.split('Trend:')[1].split()[0] if 'Trend:' in line else ''
            if trend_part:
                metrics['trends'][trend_part] += 1

    return metrics


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def main():
    print()
    print("=" * 62)
    print("  QUANTOS — DASHBOARD ANALÍTICO")
    print("=" * 62)

    metrics = parse_logs()

    total_decisions = metrics['signals_approved'] + metrics['signals_rejected']
    approval_rate = (metrics['signals_approved'] / total_decisions * 100) if total_decisions > 0 else 0

    ts = datetime.now()
    if os.path.exists(LOG_FILE):
        mtime = os.path.getmtime(LOG_FILE)
        last_activity = datetime.fromtimestamp(mtime)
        delta = datetime.now() - last_activity
        activity_str = f"{format_duration(delta.total_seconds())} atrás" if delta.total_seconds() > 0 else "agora"
    else:
        activity_str = "N/A"

    print()
    print(f"  >> VISAO GERAL")
    print(f"  {'-' * 58}")
    print(f"  Ativos escaneados:          {len(metrics['total_assets_scanned'])}")
    print(f"  Setups processados:         {metrics['setups']}")
    print(f"  Decisoes totais:            {total_decisions}")
    print(f"  Sinais aprovados:           {metrics['signals_approved']}")
    print(f"  Sinais rejeitados:          {metrics['signals_rejected']}")
    print(f"  Taxa de aprovacao:          {approval_rate:.1f}%")
    print(f"  Ultima atividade:           {activity_str}")

    print()
    print(f"  >> RANKING DE BLOQUEADORES")
    print(f"  {'-' * 58}")
    if metrics['blockers']:
        for reason, count in metrics['blockers'].most_common(10):
            bar = "#" * min(count, 20)
            print(f"  {bar} {reason} ({count})")
    else:
        print(f"  (nenhum bloqueador registrado)")

    print()
    print(f"  >> DISTRIBUICAO DE TENDENCIA")
    print(f"  {'-' * 58}")
    for trend, count in metrics['trends'].most_common():
        pct = count / sum(metrics['trends'].values()) * 100 if metrics['trends'] else 0
        bar = "#" * int(pct / 5)
        print(f"  {bar} {trend:<15} {count:>4} ({pct:.0f}%)")

    print()
    print(f"  >> METRICAS AGREGADAS")
    print(f"  {'-' * 58}")

    decisions = metrics['decisions']
    if decisions:
        qualities = [d['quality'] for d in decisions if d['quality'] is not None]
        if qualities:
            avg_q = sum(qualities) / len(qualities)
            print(f"  Quality Score médio:        {avg_q:.4f}")

        approved_qs = [d['quality'] for d in decisions if d['approved'] and d['quality'] is not None]
        if approved_qs:
            avg_aq = sum(approved_qs) / len(approved_qs)
            print(f"  Quality Score (aprovados):  {avg_aq:.4f}")

        rejected_qs = [d['quality'] for d in decisions if not d['approved'] and d['quality'] is not None]
        if rejected_qs:
            avg_rq = sum(rejected_qs) / len(rejected_qs)
            print(f"  Quality Score (rejeitados): {avg_rq:.4f}")

    print()
    print(f"  >> RECOMENDACOES")
    print(f"  {'-' * 58}")

    if metrics['setups'] == 0:
        print(f"  [!] Nenhum ciclo de scan detectado. Execute o QuantOS para gerar dados.")
    elif approval_rate < 5:
        print(f"  [!] Taxa de aprovacao muito baixa ({approval_rate:.1f}%).")
        print(f"      Verifique filtros: QUALITY_GATE_MIN_SCORE, CONSENSUS_MINIMUM_SCORE")
        if metrics['blockers']:
            top = metrics['blockers'].most_common(1)[0]
            print(f"      Principal bloqueador: {top[0]} ({top[1]}x)")
    elif approval_rate > 80:
        print(f"  [!] Taxa de aprovacao muito alta ({approval_rate:.1f}%).")
        print(f"      Possivel excesso de sinais de baixa qualidade.")
        print(f"      Considere endurecer QUALITY_GATE_MIN_SCORE.")

    print()
    print("=" * 62)
    print()


if __name__ == "__main__":
    main()
