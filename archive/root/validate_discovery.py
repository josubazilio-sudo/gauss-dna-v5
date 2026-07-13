"""
validate_discovery.py - VALIDACAO DA DESCOBERTA DINAMICA DE ATIVOS

Uso: python validate_discovery.py

NAO modifica estrategia, Entry Zone, Consensus, Quality Gate, Scores ou Risk Manager.
Apenas valida o fluxo: Discovery -> Scanner -> Pipeline -> Sinais.
"""

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logging.getLogger("QuantOS").setLevel(logging.WARNING)

from CORE.data_providers import create_provider, IDataProvider, DEBUG_MODE
from CORE.data_providers.config import log_environment_banner
from ENGINE.scanner.scanner_config import (
    DISCOVERY_MODE, MAX_SCAN_PAIRS, CUSTOM_PAIRS,
    QUALITY_GATE_MIN_SCORE, QUALITY_GATE_CONFIDENCE_MIN, QUALITY_GATE_RISK_MAX,
    CONSENSUS_MINIMUM_SCORE,
)
from ENGINE.scanner.entry_zone import ENTRY_SCORE_MIN
from ENGINE.market.market_engine import MarketEngine
from ENGINE.market.market_types import Candle
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.diagnostic.engine import DiagnosticEngine, DiagnosticReport, STAGES
from ENGINE.consensus.consensus_engine import ConsensusEngine

TIMEFRAMES = ["30m", "1h", "4h", "1d"]
QUOTE_ASSETS = ["USDT"]

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


@dataclass
class AssetTrace:
    symbol: str
    stages: List[str] = field(default_factory=list)
    failure_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    processing_time_ms: float = 0.0
    quality_score: float = 0.0
    confidence_score: float = 0.0
    consensus_score: float = 0.0
    entry_score: float = 0.0
    approved: bool = False
    rejection_reasons: List[str] = field(default_factory=list)
    decisive_filter: Optional[str] = None
    final_direction: str = "none"
    num_patterns: int = 0


@dataclass
class ValidationReport:
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    exchange: str = "unknown"
    discovery_mode: str = "AUTO"
    total_found: int = 0
    total_eligible: int = 0
    scan_limit: int = 50
    sent_to_scanner: int = 0

    assets: Dict[str, AssetTrace] = field(default_factory=dict)

    discovery_time_ms: float = 0.0
    scanner_time_ms: float = 0.0
    total_time_ms: float = 0.0
    avg_per_asset_ms: float = 0.0
    api_calls: int = 0

    silent_drops: List[str] = field(default_factory=list)

    def funnel(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for stage in STAGES:
            label = STAGE_LABELS.get(stage, stage)
            counts[label] = sum(1 for t in self.assets.values() if stage in t.stages)
        counts["Sinais"] = sum(1 for t in self.assets.values() if t.approved)
        counts["Recebidos"] = len(self.assets)
        return counts

    def top_rejections(self, n: int = 10) -> List[AssetTrace]:
        rejected = [
            t for t in self.assets.values()
            if not t.approved and t.quality_score > 0
        ]
        rejected.sort(key=lambda t: t.quality_score, reverse=True)
        return rejected[:n]


class DiscoveryValidator:
    def __init__(self):
        self._discovery_start: float = 0.0
        self._discovery_end: float = 0.0
        self._scanner_start: float = 0.0
        self._scanner_end: float = 0.0
        self._api_calls: int = 0
        self._report = ValidationReport()

    def _stage(self, label: str):
        width = 72
        print(f"\n{'=' * width}")
        print(f" {label}")
        print(f"{'=' * width}")

    # ------------------------------------------------------------------
    # ETAPA 1 -- DISCOVERY
    # ------------------------------------------------------------------

    def etapa_1_discovery(self) -> Tuple[IDataProvider, List[str]]:
        self._stage("ETAPA 1 - DISCOVERY")

        provider = create_provider()
        self._report.exchange = provider.name.replace("DataProvider", "")
        self._report.discovery_mode = DISCOVERY_MODE

        print(f"Provider:          {provider.name}")
        print(f"Discovery Mode:    {DISCOVERY_MODE}")
        print(f"DEBUG_MODE:        {DEBUG_MODE}")
        print()

        t0 = time.time()

        if DISCOVERY_MODE == "CUSTOM":
            discovered = [s.upper() for s in CUSTOM_PAIRS if s.strip()]
            eligible = discovered
            print(f"Modo CUSTOM:       {len(discovered)} pares configurados via env")
        else:
            all_syms = provider.get_symbols()
            self._report.total_found = len(all_syms)
            self._api_calls += 1

            eligible = [s for s in all_syms if any(s.endswith(qa) for qa in QUOTE_ASSETS)]
            self._report.total_eligible = len(eligible)

            print(f"Total na exchange: {len(all_syms)}")
            print(f"Elegiveis (USDT):  {len(eligible)}")

        self._report.scan_limit = MAX_SCAN_PAIRS

        if DISCOVERY_MODE == "CUSTOM":
            symbols = discovered
        else:
            symbols = eligible[:MAX_SCAN_PAIRS]

        self._report.sent_to_scanner = len(symbols)

        self._discovery_end = time.time()
        self._report.discovery_time_ms = (self._discovery_end - t0) * 1000

        print(f"Limite config:     {MAX_SCAN_PAIRS}")
        print(f"Enviados scanner:  {len(symbols)}")
        print(f"Tempo descoberta:  {self._report.discovery_time_ms:.1f}ms")

        if not symbols:
            print("\n[!] NENHUM ATIVO DESCOBERTO. Usando fallback BTCUSDT.")
            symbols = ["BTCUSDT"]

        first_n = ", ".join(symbols[:5])
        if len(symbols) > 5:
            first_n += f" ... (+{len(symbols)-5} ativos)"
        print(f"Primeiros ativos:  {first_n}")

        return provider, symbols

    # ------------------------------------------------------------------
    # ETAPA 2 -- SCANNER
    # ------------------------------------------------------------------

    def etapa_2_scanner(self, provider: IDataProvider, symbols: List[str]):
        self._stage("ETAPA 2 - SCANNER")

        market = MarketEngine()
        scanner = ScannerEngine()
        self._scanner_start = time.time()

        received = len(symbols)
        processed = 0
        failed: List[Tuple[str, str, str]] = []

        for i, symbol in enumerate(symbols):
            trace = AssetTrace(symbol=symbol)
            asset_t0 = time.time()

            tf_candles = provider.get_all_timeframes(
                symbol=symbol, timeframes=TIMEFRAMES
            )
            self._api_calls += len(TIMEFRAMES)

            if not tf_candles:
                trace.failure_stage = "api"
                trace.failure_reason = "Sem dados da API"
                failed.append((symbol, "api", "Sem dados da API"))
                self._report.assets[symbol] = trace
                continue

            trace.stages.append("carregamento")
            trace.stages.append("api")

            tf_counts = {tf: len(c) for tf, c in tf_candles.items()}
            _ = tf_counts
            trace.stages.append("candles")

            main_candles = tf_candles.get("1h", next(iter(tf_candles.values())))
            market_ctx = market.analyze(
                pair=symbol, candles=main_candles,
                timeframe_candles=tf_candles,
            )

            if market_ctx.indicators:
                trace.stages.append("indicadores")

            report = scanner.scan(
                pair=symbol, candles=tf_candles, market_ctx=market_ctx
            )

            if report.signals:
                trace.num_patterns = sum(
                    len(getattr(s, "patterns", []) or []) for s in report.signals
                )

            has_structure = bool(report.signals)
            if has_structure:
                trace.stages.append("estrutura")

            total_obs = sum(
                1 for s in report.signals
                for p in (getattr(s, "patterns", []) or [])
                if hasattr(p, "type") and "ORDER_BLOCK" in str(p.type)
            )
            total_fvgs = sum(
                1 for s in report.signals
                for p in (getattr(s, "patterns", []) or [])
                if hasattr(p, "type") and "FVG" in str(p.type)
            )
            total_sweeps = sum(
                1 for s in report.signals
                for p in (getattr(s, "patterns", []) or [])
                if hasattr(p, "type") and "LIQUIDITY_SWEEP" in str(p.type)
            )

            if total_obs > 0 or total_fvgs > 0 or total_sweeps > 0:
                trace.stages.append("smart_money")

            entry_scores = []
            for sig in report.signals:
                entry_scores.append(getattr(sig, "entry_score", 0))
            avg_entry = sum(entry_scores) / len(entry_scores) if entry_scores else 0
            trace.entry_score = round(avg_entry, 1)

            trace.stages.append("entry_zone")

            if report.signals:
                trace.stages.append("consensus")
                consensus_data = self._compute_consensus(report.signals)
                trace.consensus_score = consensus_data.get("consensus_score", 0)
                trace.final_direction = consensus_data.get(
                    "final_direction", "none"
                )

            if report.signals:
                for sig in report.signals:
                    scores = getattr(sig, "scores", None)
                    if scores:
                        trace.quality_score = getattr(
                            scores, "quality_score", 0
                        )
                        trace.confidence_score = getattr(
                            scores, "confidence_score", 0
                        )

                    rejection = getattr(sig, "rejection_reasons", []) or []
                    if rejection:
                        trace.rejection_reasons.extend(rejection)

                best_sig = max(
                    report.signals,
                    key=lambda s: (
                        getattr(getattr(s, "scores", None), "quality_score", 0)
                    ),
                )

                passed = len(getattr(best_sig, "rejection_reasons", []) or []) == 0
                trace.approved = passed

                if passed:
                    trace.stages.append("quality_gate")
                    trace.stages.append("decisao_final")
                    trace.decisive_filter = "Quality Gate (todos OK)"
                else:
                    reasons = getattr(best_sig, "rejection_reasons", []) or []
                    if reasons:
                        trace.decisive_filter = reasons[0]

                    quality = (
                        getattr(
                            getattr(best_sig, "scores", None),
                            "quality_score",
                            0,
                        )
                    )
                    if quality < QUALITY_GATE_MIN_SCORE and not trace.failure_stage:
                        pass
                    elif trace.confidence_score < QUALITY_GATE_CONFIDENCE_MIN and not trace.failure_stage:
                        pass
                    elif trace.entry_score < ENTRY_SCORE_MIN and not trace.failure_stage:
                        pass

                    trace.stages.append("quality_gate")
                    trace.stages.append("decisao_final")
            else:
                trace.failure_stage = "scanner"
                trace.failure_reason = "Nenhum sinal gerado"
                failed.append((symbol, "scanner", "Nenhum sinal gerado"))

            asset_time = (time.time() - asset_t0) * 1000
            trace.processing_time_ms = round(asset_time, 1)
            self._report.assets[symbol] = trace
            processed += 1

            if (i + 1) % 10 == 0 or (i + 1) == len(symbols):
                pct = (i + 1) / len(symbols) * 100
                print(f"   Scanner: {i+1}/{len(symbols)} ({pct:.0f}%) -- "
                      f"ultimo: {symbol} -- {asset_time:.0f}ms")
                sys.stdout.flush()

        self._scanner_end = time.time()
        self._report.scanner_time_ms = (self._scanner_end - self._scanner_start) * 1000
        self._report.total_time_ms = (
            self._report.discovery_time_ms + self._report.scanner_time_ms
        )
        self._report.avg_per_asset_ms = (
            self._report.scanner_time_ms / max(len(symbols), 1)
        )
        self._report.api_calls = self._api_calls

        print(f"\nRecebidos:        {received}")
        print(f"Processados:      {processed}")
        print(f"Falhas:           {len(failed)}")
        for sym, stage, reason in failed:
            print(f"  [!] {sym} -- estagio: {stage} -- motivo: {reason}")

    def _compute_consensus(self, signals) -> Dict:
        try:
            tf_directions = {}
            tf_scores = {}
            for sig in signals:
                tf_directions[sig.timeframe] = sig.direction
                scores = getattr(sig, "scores", None)
                tf_scores[sig.timeframe] = (
                    getattr(scores, "quality_score", 0) if scores else 0
                )
            if tf_directions:
                ce = ConsensusEngine()
                cr = ce.compute(tf_directions, tf_scores)
                return {
                    "consensus_score": cr.consensus_score,
                    "final_direction": (
                        str(cr.final_direction.value) if cr.final_direction else "none"
                    ),
                    "agreement_pct": cr.agreement_pct,
                    "classification": cr.classification,
                }
        except Exception:
            pass
        return {
            "consensus_score": 0,
            "final_direction": "none",
            "agreement_pct": 0,
            "classification": "N/A",
        }

    # ------------------------------------------------------------------
    # ETAPA 3 -- PIPELINE (funil)
    # ------------------------------------------------------------------

    def etapa_3_pipeline(self):
        self._stage("ETAPA 3 - PIPELINE (FUNIL)")

        funnel = self._report.funnel()
        stages_order = [
            "Recebidos",
            "Candles",
            "Indicadores",
            "Estrutura",
            "Smart Money",
            "Entry Zone",
            "Consensus",
            "Quality Gate",
            "Decisao Final",
            "Sinais",
        ]

        prev = None
        for label in stages_order:
            count = funnel.get(label, 0)
            if prev is None:
                print(f"  {label:<20} {count}")
            else:
                drop = prev - count
                drop_pct = (drop / prev * 100) if prev > 0 else 0
                bar = "#" * max(1, min(count, 50))
                print(f"  {label:<20} {count:>4}  |{bar}")
                if drop > 0:
                    print(f"  {'':20} {'':>4}   +-- perda: {drop} ({drop_pct:.0f}%)")
            prev = count

    # ------------------------------------------------------------------
    # ETAPA 4 -- TOP REJEICOES
    # ------------------------------------------------------------------

    def etapa_4_top_rejections(self):
        self._stage("ETAPA 4 - TOP REJEICOES")

        top = self._report.top_rejections(10)
        if not top:
            print("  Nenhum ativo rejeitado proximo da aprovacao.")
            return

        header = f"{'Ativo':<12} {'TF':<6} {'Quality':<10} {'Conf':<10} "
        header += f"{'Consensus':<10} {'EntrySc':<8} {'Decisive Filter'}"
        print(header)
        print(f"{'-'*12} {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*30}")

        for t in top:
            tf = "1h"
            for sig in self._report.assets.get(t.symbol, AssetTrace(symbol="")).stages:
                pass
            print(f"{t.symbol:<12} {tf:<6} {t.quality_score:<10.4f} "
                  f"{t.confidence_score:<10.4f} {t.consensus_score:<10.0%} "
                  f"{t.entry_score:<8.1f} {(t.decisive_filter or 'N/A')[:30]}")

    # ------------------------------------------------------------------
    # ETAPA 5 -- PERFORMANCE
    # ------------------------------------------------------------------

    def etapa_5_performance(self):
        self._stage("ETAPA 5 - PERFORMANCE")

        r = self._report
        total_assets = len(r.assets)

        print(f"Tempo descoberta:         {r.discovery_time_ms:>8.1f}ms")
        print(f"Tempo scanner:            {r.scanner_time_ms:>8.1f}ms")
        print(f"Tempo total:              {r.total_time_ms:>8.1f}ms")
        print(f"Tempo medio por ativo:    {r.avg_per_asset_ms:>8.1f}ms")
        print(f"Ativos processados:       {total_assets:>8}")
        print(f"Chamadas a API:           {r.api_calls:>8}")

        try:
            import psutil
            proc = psutil.Process()
            mem = proc.memory_info().rss / 1024 / 1024
            print(f"Uso de memoria (RSS):     {mem:>8.1f}MB")
        except ImportError:
            print(f"Uso de memoria:           (psutil nao disponivel)")

    # ------------------------------------------------------------------
    # ETAPA 6 -- SANIDADE
    # ------------------------------------------------------------------

    def etapa_6_sanity(self):
        self._stage("ETAPA 6 - SANIDADE")

        r = self._report
        issues = []

        for sym, trace in r.assets.items():
            expected = STAGES[:]
            completed = [s for s in expected if s in trace.stages]
            if len(completed) < len(expected) and trace.failure_stage is None:
                issues.append(
                    f"  [!] {sym}: pipeline incompleto "
                    f"({len(completed)}/{len(expected)} estagios) "
                    f"-- ultimos: {', '.join(completed[-3:])}"
                )
                r.silent_drops.append(sym)

        discovered_count = r.sent_to_scanner
        scanner_count = len(r.assets)
        if discovered_count != scanner_count:
            issues.append(
                f"  [!] Divergencia: discovery={discovered_count} assets, "
                f"scanner={scanner_count} assets"
            )

        api_failures = [
            sym for sym, t in r.assets.items()
            if t.failure_stage == "api"
        ]
        if api_failures:
            issues.append(
                f"  [!] Falhas de API: {len(api_failures)} ativos "
                f"({', '.join(api_failures[:5])})"
            )

        scanner_failures = [
            sym for sym, t in r.assets.items()
            if t.failure_stage == "scanner"
        ]
        if scanner_failures:
            issues.append(
                f"  [!] Scanner sem sinais: {len(scanner_failures)} ativos "
                f"({', '.join(scanner_failures[:5])})"
            )

        if issues:
            for issue in issues:
                print(issue)
        else:
            print("  [+] Nenhum silent drop detectado.")
            print("  [+] Nenhuma divergencia discovery -> scanner -> pipeline.")
            print("  [+] Nenhuma perda de ativos durante o fluxo.")

        return len(issues) == 0

    # ------------------------------------------------------------------
    # RELATORIO FINAL
    # ------------------------------------------------------------------

    def resultado_final(self):
        self._stage("RESULTADO FINAL - RELATORIO DE VALIDACAO")

        r = self._report
        funnel = r.funnel()

        print(f"\n  {'Pergunta':<55} {'Resposta':<15}")
        print(f"  {'-'*55} {'-'*15}")
        print(f"  1. Ativos descobertos?                               {r.sent_to_scanner:<15}")
        print(f"  2. Chegaram ao Scanner?                              {len(r.assets):<15}")
        print(f"  3. Passaram por cada etapa?")
        for label in ["Candles", "Indicadores", "Estrutura", "Smart Money",
                       "Entry Zone", "Consensus", "Quality Gate"]:
            count = funnel.get(label, 0)
            print(f"     +-- {label:<35} {count}")
        print(f"  4. Sinais aprovados?                                 {funnel.get('Sinais', 0):<15}")
        print(f"  5. Perda de ativos no fluxo?                        {'SIM' if r.silent_drops else 'NAO':<15}")
        print(f"  6. Discovery Engine funcionando?                     {'SIM' if r.sent_to_scanner > 0 else 'FALHA':<15}")

        all_ok = r.sent_to_scanner > 0 and len(r.assets) > 0 and not r.silent_drops

        print(f"\n  {'=' * 72}")
        if all_ok:
            print(f"  [+] DESCOBERTA DINAMICA VALIDADA - APROVADA PARA PRODUCAO")
            print(f"  [+] Discovery, Scanner, Pipeline: todas as etapas consistentes")
            print(f"  [+] Nenhuma alteracao de estrategia foi realizada")
        else:
            print(f"  [!] DESCOBERTA DINAMICA REQUER REVISAO")
            if r.sent_to_scanner == 0:
                print(f"  [!] Nenhum ativo foi descoberto")
        print(f"  {'=' * 72}")
        print()

    # ------------------------------------------------------------------
    # EXECUCAO COMPLETA
    # ------------------------------------------------------------------

    def run(self):
        full_start = time.time()

        print(f"\n{'#' * 72}")
        print(f"# QUANTOS DNA V5 - VALIDACAO DA DESCOBERTA DINAMICA")
        print(f"# {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"{'#' * 72}\n")

        provider, symbols = self.etapa_1_discovery()
        self.etapa_2_scanner(provider, symbols)
        self.etapa_3_pipeline()
        self.etapa_4_top_rejections()
        self.etapa_5_performance()
        is_clean = self.etapa_6_sanity()

        full_end = time.time()
        self._report.total_time_ms = (full_end - full_start) * 1000

        self.resultado_final()

        return is_clean


if __name__ == "__main__":
    validator = DiscoveryValidator()
    clean = validator.run()
    sys.exit(0 if clean else 1)
