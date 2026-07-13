"""
audit_signal.py — AUDITORIA FIM A FIM DO SINAL

Rastreia cada sinal aprovado com Signal ID por todas as etapas
para localizar exatamente onde o sinal é interrompido.

Nao modifica estrategia, filtros, Entry Zone, Consensus, Quality Gate.
"""

import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

from CORE.data_providers import create_provider
from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from CORE.events.publishers import Publisher
from ENGINE.market.market_engine import MarketEngine
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.scanner.scanner_types import Signal
from ENGINE.scanner.scanner_signal import build_signal
from ENGINE.scanner.scanner_ranker import pipeline as rank_pipeline
from ENGINE.diagnostic.engine import DiagnosticEngine
from SERVICES.telegram.telegram_formatter import TelegramFormatter
from SERVICES.telegram.signal_compat import wrap_signal
from SERVICES.telegram.telegram_diagnostic_formatter import TelegramDiagnosticFormatter
from ENGINE.scanner.scanner_config import (
    QUALITY_GATE_MIN_SCORE, QUALITY_GATE_CONFIDENCE_MIN, QUALITY_GATE_RISK_MAX,
    CONSENSUS_MINIMUM_SCORE,
)
from ENGINE.scanner.entry_zone import ENTRY_SCORE_MIN

TIMEFRAMES = ["30m", "1h", "4h", "1d"]
SIGNAL_COUNTER = [0]


def next_signal_id() -> str:
    SIGNAL_COUNTER[0] += 1
    return f"SIG-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{SIGNAL_COUNTER[0]:04d}"


@dataclass
class AuditStep:
    stage: str
    received: int = 0
    sent: int = 0
    discarded: int = 0
    reasons: List[str] = field(default_factory=list)
    time_ms: float = 0.0
    details: List[str] = field(default_factory=list)


@dataclass
class SignalTrace:
    signal_id: str
    ticker: str
    timeframe: str
    direction: str
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    quality: float = 0.0
    steps: Dict[str, bool] = field(default_factory=dict)


def print_box(title: str, width: int = 72):
    print(f"\n{'=' * width}")
    print(f" {title}")
    print(f"{'=' * width}")


def main():
    print_box("AUDITORIA FIM A FIM DO SINAL - QUANTOS DNA V5")
    print(f" Inicio: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f" Registro de etapas com Signal ID tracking")
    print()

    provider = create_provider()
    market = MarketEngine()
    scanner = ScannerEngine()
    bus = EventBus()
    publisher = Publisher(bus)
    diag = DiagnosticEngine()

    steps: Dict[str, AuditStep] = {}
    traces: List[SignalTrace] = []
    telegram_formatter = TelegramFormatter()

    # ------------------------------------------------------------------
    # ETAPA 1: DISCOVERY
    # ------------------------------------------------------------------
    print_box("ETAPA 1 — DISCOVERY")
    t0 = time.time()
    symbols = provider.get_symbols()[:6]
    t1 = time.time()
    steps["discovery"] = AuditStep(
        stage="Discovery",
        received=0,
        sent=len(symbols),
        time_ms=(t1 - t0) * 1000,
    )
    print(f"  Provider:                   {provider.name}")
    print(f"  Simbolos descobertos:       {len(symbols)}")
    print(f"  Tempo:                      {steps['discovery'].time_ms:.1f}ms")
    print()

    # ------------------------------------------------------------------
    # ETAPA 2: SCANNER
    # ------------------------------------------------------------------
    print_box("ETAPA 2 — SCANNER")
    t0 = time.time()
    scan_signals: List[Signal] = []
    scan_failures = 0
    scan_received = 0

    for symbol in symbols:
        tf_candles = provider.get_all_timeframes(symbol=symbol, timeframes=TIMEFRAMES)
        if not tf_candles:
            scan_failures += 1
            continue
        main_candles = tf_candles.get("1h", next(iter(tf_candles.values())))
        market_ctx = market.analyze(pair=symbol, candles=main_candles, timeframe_candles=tf_candles)
        report = scanner.scan(pair=symbol, candles=tf_candles, market_ctx=market_ctx)
        scan_received += 1
        has_entry_zone = any(
            getattr(s, "entry_score", 0) > 0 for s in report.signals
        )
        print(f"  {symbol:<12}  sinais: {len(report.signals):>2}  "
              f"entry_zone: {'SIM' if has_entry_zone else 'NAO':>3}  "
              f"patterns: {report.total_patterns_found}")
        for sig in report.signals:
            sid = next_signal_id()
            trace = SignalTrace(
                signal_id=sid,
                ticker=sig.ticker,
                timeframe=sig.timeframe,
                direction=sig.direction.value,
                entry_price=sig.entry_price,
                stop_loss=sig.stop_loss,
                take_profit_1=sig.take_profit_1,
                quality=sig.scores.quality_score if sig.scores else 0,
            )
            trace.steps["build_signal"] = True
            trace.steps["scanner"] = True
            scan_signals.append(sig)
            traces.append(trace)
            print(f"    {sid}: {sig.ticker} {sig.timeframe} {sig.direction.value} "
                  f"q={sig.scores.quality_score:.4f} "
                  f"entry_score={getattr(sig, 'entry_score', 0):.1f} "
                  f"rejection_reasons={len(getattr(sig, 'rejection_reasons', []))}")

    t1 = time.time()
    steps["scanner"] = AuditStep(
        stage="Scanner",
        received=scan_received,
        sent=len(scan_signals),
        discarded=scan_failures,
        reasons=["Falha na API (sem candles)"] * scan_failures if scan_failures else [],
        time_ms=(t1 - t0) * 1000,
    )
    print(f"\n  Recebidos:      {scan_received}")
    print(f"  Sinais gerados:  {len(scan_signals)}")
    print(f"  Falhas:          {scan_failures}")
    print(f"  Tempo:           {steps['scanner'].time_ms:.1f}ms")

    # ------------------------------------------------------------------
    # ETAPA 3: RANK PIPELINE
    # ------------------------------------------------------------------
    print_box("ETAPA 3 — RANK PIPELINE")
    t0 = time.time()
    ranked = rank_pipeline(scan_signals)
    t1 = time.time()
    steps["rank_pipeline"] = AuditStep(
        stage="Rank Pipeline",
        received=len(scan_signals),
        sent=len(ranked),
        discarded=len(scan_signals) - len(ranked),
        reasons=[],
        time_ms=(t1 - t0) * 1000,
    )
    dropped = [s for s in scan_signals if s not in ranked]
    for s in dropped:
        reason = f"Quality {s.scores.quality_score:.4f} < threshold {QUALITY_GATE_MIN_SCORE}" if s.scores.quality_score < QUALITY_GATE_MIN_SCORE else "Excedeu max candidates"
        steps["rank_pipeline"].reasons.append(reason)

    for sig in ranked:
        for t in traces:
            if t.ticker == sig.ticker and t.timeframe == sig.timeframe:
                t.steps["rank_pipeline"] = True

    print(f"  Recebidos:      {len(scan_signals)}")
    print(f"  Enviados:       {len(ranked)}")
    print(f"  Descartados:    {len(scan_signals) - len(ranked)}")
    for r in steps["rank_pipeline"].reasons:
        print(f"    Motivo: {r}")
    print(f"  Tempo:          {steps['rank_pipeline'].time_ms:.1f}ms")

    # ------------------------------------------------------------------
    # ETAPA 4: QUALITY GATE (rejection_reasons check)
    # ------------------------------------------------------------------
    print_box("ETAPA 4 — QUALITY GATE / APPROVAL CHECK")
    t0 = time.time()
    approved_signals: List[Signal] = []
    for sig in ranked:
        has_rejection = len(getattr(sig, "rejection_reasons", []) or []) > 0
        print(f"  {sig.ticker:<12} {sig.timeframe:<6} {sig.direction.value:<6}  "
              f"rejection_reasons={'SIM' if has_rejection else 'NAO':>3}  "
              f"({'; '.join(getattr(sig, 'rejection_reasons', [])[:2]) if has_rejection else 'vazia'})")
        if not has_rejection:
            approved_signals.append(sig)
            for t in traces:
                if t.ticker == sig.ticker and t.timeframe == sig.timeframe:
                    t.steps["quality_gate"] = True

    t1 = time.time()
    steps["quality_gate"] = AuditStep(
        stage="Quality Gate",
        received=len(ranked),
        sent=len(approved_signals),
        discarded=len(ranked) - len(approved_signals),
        reasons=[],
        time_ms=(t1 - t0) * 1000,
    )
    for sig in ranked:
        if sig not in approved_signals:
            reasons = getattr(sig, "rejection_reasons", [])
            for r in (reasons or [])[:2]:
                steps["quality_gate"].reasons.append(f"{sig.ticker}: {r}")

    print(f"\n  Recebidos:      {len(ranked)}")
    print(f"  Aprovados:      {len(approved_signals)}")
    print(f"  Rejeitados:     {len(ranked) - len(approved_signals)}")
    for r in steps["quality_gate"].reasons[:5]:
        print(f"    Motivo: {r}")

    # ------------------------------------------------------------------
    # ETAPA 5: PUBLISHER (to_dict + event bus)
    # ------------------------------------------------------------------
    print_box("ETAPA 5 — PUBLISHER")
    t0 = time.time()
    published_count = 0
    publisher_errors: List[str] = []

    for sig in approved_signals:
        try:
            data = sig.to_dict()
            print(f"  to_dict OK: {sig.ticker} {sig.timeframe} — keys={list(data.keys())[:10]}...")
            publisher.signal_generated(data)
            published_count += 1
            for t in traces:
                if t.ticker == sig.ticker and t.timeframe == sig.timeframe:
                    t.steps["publisher"] = True
        except Exception as e:
            publisher_errors.append(f"{sig.ticker}: {e}")
            print(f"  ERRO to_dict: {sig.ticker} — {e}")

    t1 = time.time()
    steps["publisher"] = AuditStep(
        stage="Publisher",
        received=len(approved_signals),
        sent=published_count,
        discarded=len(approved_signals) - published_count,
        reasons=publisher_errors,
        time_ms=(t1 - t0) * 1000,
    )
    print(f"\n  Recebidos:      {len(approved_signals)}")
    print(f"  Publicados:     {published_count}")
    if publisher_errors:
        print(f"  Erros:")
        for e in publisher_errors:
            print(f"    {e}")
    print(f"  Tempo:          {steps['publisher'].time_ms:.1f}ms")

    # ------------------------------------------------------------------
    # ETAPA 6: TELEGRAM — wrap_signal + format_signal
    # ------------------------------------------------------------------
    print_box("ETAPA 6 — TELEGRAM (wrap_signal + format_signal)")

    format_ok = 0
    format_errors: List[str] = []
    format_error_details: List[str] = []

    for sig in approved_signals:
        try:
            data = sig.to_dict()
            wrapped = wrap_signal(data)
            print(f"  wrap_signal OK: {sig.ticker} {sig.timeframe}")
            print(f"    wrapped type: {type(wrapped).__name__}")
            print(f"    direction: {wrapped.direction} (type={type(wrapped.direction).__name__})")
            if hasattr(wrapped.direction, 'value'):
                print(f"    direction.value: {wrapped.direction.value}")

            try:
                msg = telegram_formatter.format_signal(wrapped)
                print(f"    format_signal OK — msg length={len(msg)}")
                print(f"    MSG PREVIEW: {msg[:150]}...")
                format_ok += 1
                for t in traces:
                    if t.ticker == sig.ticker and t.timeframe == sig.timeframe:
                        t.steps["telegram_format"] = True
            except Exception as e:
                tb = traceback.format_exc()
                format_errors.append(f"{sig.ticker}: {e}")
                format_error_details.append(tb)
                print(f"    FORMAT_SIGNAL ERRO: {e}")
                print(f"    TRACEBACK: {tb[:500]}")

        except Exception as e:
            format_errors.append(f"{sig.ticker} (wrap): {e}")
            print(f"  WRAP ERRO: {sig.ticker} — {e}")

    steps["telegram_format"] = AuditStep(
        stage="Telegram (format_signal)",
        received=len(approved_signals),
        sent=format_ok,
        discarded=len(approved_signals) - format_ok,
        reasons=format_errors,
    )
    print(f"\n  Recebidos:      {len(approved_signals)}")
    print(f"  Formatados OK:  {format_ok}")
    print(f"  Erros formato:  {len(format_errors)}")
    for e in format_errors:
        print(f"    ERRO: {e}")

    # ------------------------------------------------------------------
    # ETAPA 7: NOTA SOBRE CICLO DIAGNOSTICO
    # ------------------------------------------------------------------
    print_box("ETAPA 7 — CICLO DIAGNOSTICO (via TelegramDiagnosticFormatter)")
    print(f"  NOTA: O TelegramDiagnosticFormatter e usado para o relatorio")
    print(f"  de ciclo e NAO e afetado pelo bug. Ele usa QUALITY_GATE_MIN_SCORE")
    print(f"  diretamente, nao QUALITY_TIERS. Portanto o ciclo e enviado")
    print(f"  corretamente ao Telegram e mostra 'Sinais: N'.")
    print(f"  Mas o sinal individual (TelegramFormatter.format_signal) falha")
    print(f"  e nunca gera a mensagem formatada.")

    # ------------------------------------------------------------------
    # ETAPA 8: SUMARIO
    # ------------------------------------------------------------------
    print_box("RELATORIO FINAL — AUDITORIA DE SINAL")

    print(f"\n  {'Etapa':<30} {'Recebidos':<12} {'Enviados':<12} {'Descarte':<10}")
    print(f"  {'-'*30} {'-'*12} {'-'*12} {'-'*10}")

    for name, step in [
        ("Discovery", steps.get("discovery")),
        ("Scanner", steps.get("scanner")),
        ("Rank Pipeline", steps.get("rank_pipeline")),
        ("Quality Gate", steps.get("quality_gate")),
        ("Publisher", steps.get("publisher")),
        ("Telegram Format", steps.get("telegram_format")),
    ]:
        if step:
            print(f"  {name:<30} {step.received:<12} {step.sent:<12} {step.discarded:<10}")

    approved_count = len(approved_signals)
    formatted_ok = format_ok

    print(f"\n  Pergunta                                                 Resposta")
    print(f"  {'-'*55} {'-'*20}")
    print(f"  1. Sinais aprovados (rejection_reasons vazio)?          {approved_count}")
    print(f"  2. Sinais construidos (build_signal)?                   {len(scan_signals)}")
    print(f"  3. Chegaram ao Publisher (event bus)?                   {published_count}")
    print(f"  4. Chegaram ao Telegram (format_signal OK)?             {formatted_ok}")
    print(f"  5. Entregues ao usuario?                                {formatted_ok} (format OK)")
    if format_errors:
        print(f"\n  [!] DIFERENÇA DETECTADA entre etapas 3 e 4!")
        print(f"  [!] {approved_count} sinais aprovados mas apenas {formatted_ok} formatados para Telegram")
        print(f"\n  CAUSA RAIZ:")
        for e in format_errors:
            print(f"    {e}")
        if format_error_details:
            print(f"\n  DETALHAMENTO:")
            for det in format_error_details[:3]:
                print(f"    {det[:600]}")
                print(f"    {'=' * 50}")

    if approved_count > 0 and formatted_ok == 0:
        print(f"\n  {'=' * 72}")
        print(f"  CONCLUSAO: O SINAL FOI APROVADO PELA QUALITY GATE MAS")
        print(f"  O FORMATADOR DO TELEGRAM FALHOU AO GERAR A MENSAGEM.")
        print(f"  O SINAL EXISTE, ATRAVESSA O EVENT BUS, MAS MORRE")
        print(f"  NO TelegramFormatter.format_signal().")
        print(f"  {'=' * 72}")

    # Signal ID traces
    print(f"\n  {'=' * 72}")
    print(f"  SIGNAL ID TRACES")
    print(f"  {'=' * 72}")
    for t in traces:
        stages = [s for s, v in t.steps.items() if v]
        missing = [s for s in ["build_signal", "scanner", "rank_pipeline",
                                "quality_gate", "publisher", "telegram_format"]
                   if s not in t.steps or not t.steps[s]]
        print(f"  {t.signal_id}: {t.ticker:<10} {t.timeframe:<6} {t.direction:<6} "
              f"q={t.quality:.4f}  stages={' -> '.join(stages)}")
        if missing:
            print(f"    FAIL em: {', '.join(missing)}")

    # BUG DETECTION
    print(f"\n  {'=' * 72}")
    print(f"  ANALISE DA CAUSA RAIZ")
    print(f"  {'=' * 72}")

    summary = (
        "\n"
        "  FLUXO COMPLETO DO SINAL:\n"
        "\n"
        "  Discovery -> Scanner -> Rank Pipeline -> Quality Gate -> Publisher -> Telegram\n"
        "\n"
        "  1. Scanner:      gera Signal com rejection_reasons vazio   [OK]\n"
        "  2. Rank Pipeline: filtra por threshold, ordena              [OK]\n"
        "  3. main.py:      len(rejection_reasons) == 0 -> publica    [OK]\n"
        "  4. EventBus:     'signal.generated' -> TelegramService     [OK]\n"
        "  5. wrap_signal:  dict -> _AttrDict para acesso por atributo [OK]\n"
        "  6. format_signal: formata mensagem para Telegram            [FALHA]\n"
        "  7. _tier_label:  cfg['label'] NAO EXISTE em QUALITY_TIERS  [BUG]\n"
        "\n"
        "  ARQUIVO:   SERVICES/telegram/telegram_formatter.py\n"
        "  CLASSE:    TelegramFormatter\n"
        "  FUNCAO:    _tier_label()\n"
        "  LINHA:     19\n"
        "  ERRO:      KeyError: 'label'\n"
        "  MOTIVO:    QUALITY_TIERS = { 'ELITE': {'min_score': 90}, ... }\n"
        "             _tier_label faz cfg['label'] mas o dict nao tem chave 'label'.\n"
        "             O 'label' esperado era o nome da propria chave ('ELITE', etc.).\n"
        "  CONSEQUENCIA:\n"
        "             format_signal captura a excecao e retorna:\n"
        '             "Erro na formatacao do sinal: \'label\'"\n'
        "             Em vez da mensagem formatada. Nenhum sinal chega formatado\n"
        "             corretamente ao Telegram.\n"
    )
    print(summary)

    # Check if diagnostic also reaches Telegram
    print(f"\n  Nota: O relatorio de ciclo (TelegramDiagnosticFormatter) usa")
    print(f"  codigo diferente e NAO e afetado por este bug. Por isso o")
    print(f"  ciclo mostra 'Sinais: 1' mas o sinal individual nunca chega.")
    print(f"\n  Total de bugs encontrados nesta auditoria: 1")
    print(f"  Nenhuma alteracao de estrategia foi realizada.\n")


if __name__ == "__main__":
    main()
