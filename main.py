import asyncio
import concurrent.futures
import logging
import signal
import sys
import time
import traceback

from dotenv import load_dotenv
load_dotenv()  # precisa rodar antes de qualquer import de projeto: varios
# modulos (ENGINE/scanner/scanner_config.py, CORE/data_providers/mexc_provider.py)
# leem os.getenv(...) no nivel de modulo, no momento do import. Antes desta
# chamada estar aqui, o .env so era carregado dentro de BOTS/mexc/bot_config.py,
# que e importado DEPOIS desses modulos — entao QUANTOS_MAX_SCAN_PAIRS,
# QUANTOS_MEXC_MAX_CONCURRENT etc. do .env eram sempre ignorados (caiam no
# default hardcoded), mesmo definidos corretamente no arquivo.

from audit_engine import audit
from datetime import datetime, timezone
from typing import Dict, List, Optional

from CORE.execution.mode_manager import ExecutionModeManager
from CORE.bootstrap.startup import Startup
from CORE.data_providers import create_provider, IDataProvider, DEBUG_MODE
from ENGINE.scanner.scanner_config import DISCOVERY_MODE, MAX_SCAN_PAIRS, CUSTOM_PAIRS, SCAN_MAX_WORKERS, RR_IDEAL_RR
from ENGINE.scanner.scanner_config import SCANNER_VIP_PAIRS
from ENGINE.scanner.priority_score import reorder_pairs_by_priority
from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from CORE.events.publishers import Publisher
from ENGINE.market.market_engine import MarketEngine
from ENGINE.market.market_types import Candle
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.decision.decision_engine import DecisionEngine, SignalDecision
from BOTS.mexc.bot_engine import BotEngine
from BOTS.mexc.bot_config import BotConfig
from SERVICES.telegram.telegram_service import TelegramService
from ENGINE.diagnostic.engine import DiagnosticEngine
from ENGINE.diagnostics.decision_diagnostics import DecisionDiagnostics
from ENGINE.deduplication.signal_cache import SignalCacheEngine
from ENGINE.exchange.exchange_validation import ExchangeValidation
from ENGINE.diagnostic.cycle_profiler import CycleProfiler
from ENGINE.diagnostic import calibration_measurement
from ENGINE.diagnostic.advanced_report import build_advanced_report
from ENGINE.analytics import trade_storage as analytics_trade_storage
from ENGINE.analytics import statistics as analytics_statistics
from ENGINE.analytics import journal as analytics_journal
from ENGINE.analytics import equity as analytics_equity
from ENGINE.scanner.scanner_config import ACCOUNT_SIZE
from ENGINE.watchdog.watchdog_integration import WatchdogIntegration
from CORE.health.health_monitor import HealthMonitor
from CORE.trading.paper_trading import PaperTradingEngine
from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.signals.signal_tracker import SignalTracker
from ENGINE.analytics.trade_analytics import TradeAnalytics
from ENGINE.scanner.scanner_config import RR_MIN_RR, HARD_MIN_RVOL, HARD_MIN_ADX, CONSENSUS_MINIMUM_SCORE
from ENGINE.scanner.scanner_config import LEVERAGE_MAX_USER
from ENGINE.auditor.institutional_math_auditor import InstitutionalMathAuditor
from ENGINE.diagnostic.fast_diagnostic import (
    DiagnosticBaseline, build_fast_diagnostic, format_fast_diagnostic_log,
    format_detailed_diagnostic,
)
from ENGINE.diagnostic.rfc_v25_6_diagnostic import (
    build_v25_6_diagnostic, format_v25_6_report,
)
from ENGINE.analytics.root_cause_engine import (
    RootCauseDiagnosticEngine, format_rcde_report, format_rcde_telegram,
)
from ENGINE.exchange.execution_validator import (
    ExchangeExecutionValidator, ExchangeSymbolInfo, ExecutionValidationResult,
)
from ENGINE.scanner.scanner_config import (
    ENABLE_EXECUTION_VALIDATOR, EXECUTION_VALIDATION_TOLERANCE,
    AUTO_ROUND_PRICES, AUTO_ROUND_QUANTITY, BLOCK_INVALID_EXECUTION,
    EXECUTION_SLIPPAGE_RATE, EXECUTION_FUNDING_RATE_EST,
)
from ENGINE.watchlist.watchlist_manager import WatchlistManager, WATCHLIST_PRIORITY_BONUS
from ENGINE.scanner.scanner_config import WATCHLIST_PATH
from ENGINE.analytics.rejection_analytics import RejectionAnalytics, _classify_gate
from ENGINE.analytics.gate_calibration_engine import GateCalibrationEngine
from ENGINE.analytics.baseline_monitor import (
    BaselineRegistry, BaselineAnalyzer, BaselineReporter, CycleSnapshot,
)
from ENGINE.scanner.scanner_config import (
    ENABLE_REJECTION_ANALYTICS, REJECTION_ANALYTICS_EXPORT_DIR,
    CALIBRATION_MIN_SAMPLES, CALIBRATION_ENABLED,
)

from logging import StreamHandler, FileHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        StreamHandler(),
        FileHandler("quantos.log", mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger("QuantOS")

from CORE.config.settings import settings
log.info(f"Configuração carregada: modo={settings.mode}, qualidade_min={settings.min_quality_score}")

_blocked_log = logging.getLogger("BLOCKED_SIGNALS")
_blocked_log.setLevel(logging.WARNING)
_blocked_handler = logging.FileHandler("BLOCKED_SIGNALS.log", mode="a", encoding="utf-8")
_blocked_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(message)s"
))
_blocked_log.handlers.clear()
_blocked_log.addHandler(_blocked_handler)
_blocked_log.propagate = False

TIMEFRAMES = ["30m", "1h", "4h", "1d"]
QUOTE_ASSETS = ["USDT"]

from ENGINE.validation.health_check import run_health_check
from dataclasses import dataclass, field


def _cycle_rank(d: SignalDecision) -> float:
    """Criterio oficial unico de 'melhor sinal do ciclo' (RFC V18.4 Etapa 2).
    Antes existiam dois criterios independentes (envio real vs diagnostico),
    que podiam escolher timeframes diferentes do mesmo ativo. Agora e a
    UNICA funcao que determina o melhor sinal, usada tanto para o envio ao
    Telegram quanto para o registro de diagnostico."""
    rr_norm = min(d.risk_reward / RR_IDEAL_RR, 1.0) if d.risk_reward else 0.0
    return d.quality * 0.5 + d.consensus * 0.3 + rr_norm * 0.2


@dataclass
class CycleSignalResult:
    """Objeto oficial unico do resultado de um ciclo para um ativo (RFC V18.4
    Etapa 1). Nenhum modulo deve recalcular o 'melhor sinal' — todos
    consomem best_signal, calculado uma unica vez em _process_scan_result()."""
    pair: str
    all_decisions: List[SignalDecision] = field(default_factory=list)
    approved_signals: List[SignalDecision] = field(default_factory=list)
    best_signal: Optional[SignalDecision] = None
    best_is_approved: bool = False


def _resumir_motivos_sem_sinal(signals) -> tuple:
    sinais_com_motivo = [s for s in signals if s.rejection_reasons]
    if not sinais_com_motivo:
        return "Nenhum sinal", [], "Rejected: no signals generated"

    todos_motivos = [r for s in sinais_com_motivo for r in s.rejection_reasons]
    motivo_primario = todos_motivos[0]
    motivos_secundarios = list(dict.fromkeys(todos_motivos[1:]))
    return motivo_primario, motivos_secundarios, f"Rejected: {motivo_primario}"


def _should_record_paper_trade(sd: SignalDecision, data: Dict) -> bool:
    if data.get("_validation_blocked", False):
        return False
    return (
        sd.approved and
        sd.entry_price > 0 and
        sd.stop_loss > 0 and
        sd.take_profit_1 > 0 and
        sd.risk_reward > 0
    )


def _paper_trade_decisions(cycle_result: CycleSignalResult, data: Dict) -> List[SignalDecision]:
    best = cycle_result.best_signal
    if not best or not cycle_result.best_is_approved:
        return []
    if not _should_record_paper_trade(best, data):
        return []
    return [best]


def _run_health_check_sync(health: HealthMonitor):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(health.check())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def _build_default_symbol_info(symbol: str) -> ExchangeSymbolInfo:
    return ExchangeSymbolInfo(
        symbol=symbol,
        tick_size=0.001,
        step_size=0.001,
        min_qty=0.001,
        max_qty=1000000.0,
        min_notional=5.0,
        max_notional=0.0,
        price_precision=3,
        qty_precision=3,
        min_leverage=1,
        max_leverage=125,
        is_active=True,
        is_futures=True,
        contract_status="TRADING",
        maintenance_margin_rate=0.005,
        taker_fee_rate=0.0006,
        maker_fee_rate=0.0002,
    )


def _publish_validation_blocked(publisher: Publisher, data: Dict, reason: str) -> None:
    publisher.decision_rejected({
        "pair": data.get("symbol", "?"),
        "symbol": data.get("symbol", "?"),
        "timeframe": data.get("timeframe", "?"),
        "direction": data.get("direction", "?"),
        "reason": "VALIDATION BLOCKED: " + reason,
        "status": "REJECTED",
        "signal_id": data.get("signal_id", "?"),
    })


class QuantOSApp:
    def __init__(self, provider: IDataProvider):
        if not run_health_check():
            log.critical("Falha no Health Check. Encerrando.")
            sys.exit(1)
        self._provider = provider
        self._bus = EventBus()
        self._publisher = Publisher(self._bus)
        self._diag = DiagnosticEngine()
        self._decision_diag = DecisionDiagnostics()
        self._signal_cache = SignalCacheEngine()
        self._profiler = CycleProfiler()
        # RFC V18.5: Exchange Validation Gate — universo de simbolos vem
        # da API de SPOT da MEXC (CORE/data_providers/mexc_provider.py),
        # mas o pipeline inteiro assume futuros (leverage/margem/
        # liquidacao). Filtra aqui, antes de qualquer scan, simbolos sem
        # contrato futuro real (ex.: ACNONUSDT, ATTONUSDT).
        self._exchange_validation = ExchangeValidation()

        startup = Startup()
        startup.run()

        self._market = MarketEngine()
        self._scanner = ScannerEngine()
        mode = ExecutionModeManager()
        self._config = BotConfig(dry_run=not mode.is_live())
        self._bot = BotEngine(config=self._config, event_bus=self._bus,
                               market_engine=self._market, scanner_engine=self._scanner)
        self._telegram = TelegramService(self._bus)
        self._watchdog = WatchdogIntegration(self)
        self._health = HealthMonitor(ping_fn=self._async_ping)
        # RFC V26.X: banca institucional fixa — mesma fonte de verdade
        # (ACCOUNT_SIZE) usada por BotEngine.balance, InstitutionalMathAuditor
        # e a curva de equity, nunca um valor interno divergente.
        self._paper = PaperTradingEngine(initial_capital=ACCOUNT_SIZE)
        self._trade_registry = TradeRegistry()
        self._signal_tracker = SignalTracker()
        self._watchlist = WatchlistManager(path=WATCHLIST_PATH or None)
        self._trade_analytics = TradeAnalytics()
        self._rejection_analytics = RejectionAnalytics(
            export_dir=REJECTION_ANALYTICS_EXPORT_DIR or None,
        )
        self._rejection_analytics.set_enabled(ENABLE_REJECTION_ANALYTICS)
        self._calibration = GateCalibrationEngine(
            min_samples=CALIBRATION_MIN_SAMPLES,
            enabled=CALIBRATION_ENABLED,
        )
        self._running = False
        self._scan_count = 0
        self._last_heartbeat: float = 0.0
        self._loop_status = "STOPPED"
        # RFC V19.3: cache de indicadores do ciclo anterior por par, usado
        # SOMENTE para priorizar a ordem de varredura do proximo ciclo —
        # nao alimenta Decision Engine, gates, thresholds ou scoring.
        self._priority_cache: Dict[str, Dict] = {}
        # RFC V25.5: Fast Diagnostic — baseline movel + streak de ciclos
        # sem sinal aprovado, usados para detectar anomalias entre ciclos.
        self._diag_baseline = DiagnosticBaseline()
        self._baseline_registry = BaselineRegistry()
        self._baseline_analyzer = BaselineAnalyzer()
        self._baseline_reporter = BaselineReporter(self._baseline_analyzer)
        # RFC V26.X: Root Cause Diagnostic Engine — investiga gates em
        # crise e detecta regressoes, ao final de cada ciclo.
        self._rcde = RootCauseDiagnosticEngine()
        # RFC V26.X: diagnostico unico enviado ao Telegram uma vez por dia
        # as 18h (sem alertas avulsos) — data do ultimo envio, para nao
        # repetir no mesmo dia.
        self._last_daily_diagnostic_date = None
        self._zero_signal_streak = 0
        self._symbols = self._discover_symbols()
        self._config.pairs = list(self._symbols)

    def start(self):
        mode_label = "DEBUG" if DEBUG_MODE else "PRODUCTION"
        import os as _os
        import hashlib
        log.info("=" * 56)
        log.info("QUANTOS — ARQUITETURA SIMPLIFICADA")
        log.info("=" * 56)
        log.info("Versao:           V18.4")
        log.info("Engine Version:   V18.4")
        log.info("Modo:             %s | Provider: %s | Discovery: %s", mode_label, self._provider.name, DISCOVERY_MODE)
        log.info("Ativos:           %d descobertos | Limite: %s", len(self._symbols), MAX_SCAN_PAIRS if MAX_SCAN_PAIRS is not None else "ALL")
        import os as _os2
        log.info("PID:              %d", _os2.getpid())
        log.info("Inicio:           %s", datetime.now(timezone.utc).isoformat())
        git_commit = ""
        try:
            git_commit = _os.popen("git rev-parse --short HEAD 2>nul").read().strip()
            if git_commit:
                log.info("Git Commit:       %s", git_commit)
        except Exception:
            pass
        # RFC V25.3 (temporario): fingerprint de instancia para rastreabilidade
        # de origem dos sinais no Telegram — remover ou mover so para o log
        # apos a auditoria concluir.
        import socket as _socket
        _hostname = _socket.gethostname()
        _build_ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        self._fingerprint = {
            "server": _hostname,
            "pid": _os2.getpid(),
            "build": f"{git_commit or 'unknown'}-{_build_ts}",
        }
        log.info("Servidor:         %s", _hostname)
        log.info("Fingerprint:      %s", self._fingerprint["build"])
        try:
            _basedir = _os2.path.dirname(_os2.path.abspath(__file__))
            _core_files = [
                "main.py",
                "ENGINE/decision/decision_engine.py",
                "ENGINE/common/operational.py",
                "SERVICES/telegram/telegram_formatter.py",
                "ENGINE/scanner/scanner_config.py",
            ]
            for _rel in _core_files:
                _fp = _os2.path.join(_basedir, _rel)
                if _os2.path.exists(_fp):
                    _mtime = datetime.fromtimestamp(_os2.path.getmtime(_fp), tz=timezone.utc).isoformat()
                    _content = open(_fp, "rb").read()
                    _hash = hashlib.sha256(_content).hexdigest()[:16]
                    log.info("Arquivo:          %s | mtime=%s | SHA256=%.16s", _rel, _mtime, _hash)
                else:
                    log.warning("Arquivo NAO ENCONTRADO: %s", _fp)
        except Exception as _exc:
            log.warning("Nao foi possivel auditar arquivos: %s", _exc)
        log.info("=" * 56)
        self._running = True
        self._loop_status = "RUNNING"
        self._bus.publish(Event(EventTypes.SYSTEM_BOOT, {"mode": mode_label.lower()}))
        self._bot.start()
        self._watchdog.setup()
        self._watchdog.report_healthy("scanner")
        _run_health_check_sync(self._health)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self._scan_loop()

    async def _async_ping(self) -> bool:
        try:
            ticker = await self._provider.get_symbol_ticker_async("BTCUSDT")
            return ticker is not None
        except Exception:
            return False

    def _discover_symbols(self) -> List[str]:
        limit_label = MAX_SCAN_PAIRS if MAX_SCAN_PAIRS is not None else "ALL"
        if DISCOVERY_MODE == "CUSTOM":
            candidates = [s.upper() for s in CUSTOM_PAIRS if s.strip()]
            # RFC V18.5: mesmo em modo manual, nunca escanear simbolo sem
            # contrato futuro real na MEXC.
            valid = self._exchange_validation.filter_valid(candidates)
            discovered = sorted(valid, key=candidates.index)
            log.info("Discovery CUSTOM: %d pairs configurados manualmente", len(discovered))
        else:
            all_syms = self._provider.get_symbols()
            filtered = [s for s in all_syms if any(s.endswith(qa) for qa in QUOTE_ASSETS)]
            # RFC V18.5: Exchange Validation Gate — filtra ANTES de
            # truncar por MAX_SCAN_PAIRS, para nao desperdicar vagas de
            # scan com simbolos que existem no spot mas nao em futuros.
            valid = self._exchange_validation.filter_valid(filtered)
            valid_sorted = [s for s in filtered if s in valid]
            discovered = valid_sorted[:MAX_SCAN_PAIRS]
            mode_label = "DEBUG" if DISCOVERY_MODE == "DEBUG" else "AUTO"
            log.info(
                "Discovery %s: %d / %d USDT pairs validos em futuros (limit: %s)",
                mode_label, len(discovered), len(valid_sorted), limit_label,
            )
        if not discovered:
            log.warning("Nenhum simbolo descoberto! Fallback para BTCUSDT")
            discovered = ["BTCUSDT"]
        return sorted(discovered)

    def stop(self):
        log.info("QuantOS desligando...")
        self._running = False
        self._bot.stop()
        self._watchdog.stop()
        paper_stats = self._paper.get_stats()
        log.info(f"PaperTrading: {paper_stats.get('total_trades', 0)} trades, "
                 f"WinRate={paper_stats.get('win_rate', 0):.2%}, "
                 f"PF={paper_stats.get('profit_factor', 0):.2f}, "
                 f"Return={paper_stats.get('total_return_pct', 0):.2f}%")
        tel = self._trade_analytics.get_telemetry()
        log.info(
            "Telemetria: AdaptiveTP=%d Fallback=%d ScannerOK=%d ScannerFail=%d "
            "ResFound=%d ResIgnored=%d Partial=%d TrailingExit=%d BE=%d TPTooFar=%d",
            tel.get("adaptive_tp_used", 0), tel.get("fallback_tp", 0),
            tel.get("scanner_success", 0), tel.get("scanner_fail", 0),
            tel.get("resistance_found", 0), tel.get("resistance_ignored", 0),
            tel.get("partial_tp", 0), tel.get("trailing_exit", 0),
            tel.get("break_even_exit", 0), tel.get("tp_too_far", 0),
        )
        learning = self._trade_analytics.generate_learning_report()
        if learning:
            log.info(
                "Learning Report (%d trades): antes WR=%.2f%% PF=%.2f | "
                "depois WR=%.2f%% PF=%.2f | sugestoes: ATR=%.4f trailing=%.2f%%",
                learning["total_trades"],
                learning["antes"]["win_rate"] * 100, learning["antes"]["profit_factor"],
                learning["depois"]["win_rate"] * 100, learning["depois"]["profit_factor"],
                learning["sugestoes"]["atr_ideal"],
                learning["sugestoes"]["trailing_distancia_ideal_pct"],
            )
        self._bus.publish(Event(EventTypes.SYSTEM_SHUTDOWN, {"status": "shutdown"}))
        log.info("QuantOS finalizado.")

    def _signal_handler(self, sig, frame):
        log.info("Sinal recebido: %s", sig)
        self.stop()
        sys.exit(0)

    def _scan_loop(self):
        while self._running:
            try:
                self._scan_count += 1
                self._last_start_time = time.time()
                self._last_heartbeat = time.time()
                self._loop_status = "RUNNING"
                self._diag.start_cycle(self._scan_count)
                self._decision_diag.start_cycle(self._scan_count)
                self._profiler.start_cycle(self._scan_count)
                self._rejection_analytics.start_cycle(self._scan_count)
                self._calibration.start_cycle(self._scan_count)
                self._diag.record_step("Ativos monitorados", len(self._symbols))
                start_time = time.time()
                log.info("--- Ciclo de scan #%d ---", self._scan_count)

                self._funnel = {
                    "ativos_analisados": 0,
                    "api": 0,
                    "candles": 0,
                    "indicadores": 0,
                    "estrutura": 0,
                    "smart_money": 0,
                    "entry_zone": 0,
                    "consensus": 0,
                    "quality_gate": 0,
                    "decision_engine": 0,
                    "aprovados": 0,
                }

                fetch_start = time.time()
                results: Dict[str, Dict] = {}
                api_calls_cycle = 0

                # RFC V19.3: reordena uma COPIA local de self._symbols por
                # PRIORITY_SCORE (so a ordem de varredura muda — Decision
                # Engine, gates, thresholds e scoring permanecem intactos).
                # Fallback seguro: se o ticker snapshot falhar (rede), a
                # funcao devolve a lista original inalterada.
                try:
                    ticker_snapshot = self._provider.get_ticker_24h_snapshot()
                    recently_approved = self._signal_tracker.get_recently_approved_pairs()
                    scan_order = reorder_pairs_by_priority(
                        self._symbols, ticker_snapshot,
                        cached_scores=self._priority_cache,
                        vip_pairs=SCANNER_VIP_PAIRS,
                        recently_approved_pairs=recently_approved,
                    )
                    # RFC V23: Watchlist Prioritária — coloca moedas da
                    # watchlist no início da fila (após reordenação por
                    # priority_score), sem remover nem duplicar pares.
                    _wl_count = self._watchlist.count_in_list(scan_order)
                    if _wl_count > 0:
                        scan_order = self._watchlist.reorder_scan_queue(scan_order)
                        log.info(
                            "WATCHLIST: %d moedas prioritárias posicionadas no início da fila",
                            _wl_count,
                        )
                except Exception as e:
                    log.warning("PriorityScore: falha ao reordenar scanner, usando ordem padrao: %s", e)
                    scan_order = list(self._symbols)

                with concurrent.futures.ThreadPoolExecutor(max_workers=SCAN_MAX_WORKERS) as executor:
                    future_to_pair = {
                        executor.submit(self._fetch_and_scan, pair): pair
                        for pair in scan_order
                    }
                    for future in concurrent.futures.as_completed(future_to_pair):
                        pair = future_to_pair[future]
                        try:
                            results[pair] = future.result()
                            api_calls_cycle += 1
                            if api_calls_cycle % 25 == 0:
                                self._last_heartbeat = time.time()
                                self._watchdog.report_healthy("scanner")
                        except Exception as e:
                            log.error("Erro ao buscar/escanear %s: %s", pair, e)
                            results[pair] = {"pair": pair, "ok": False, "error": str(e)}
                self._last_heartbeat = time.time()
                self._watchdog.report_healthy("scanner")
                log.info(
                    "Fetch+scan paralelo (%d workers): %d/%d pares em %.1fs",
                    SCAN_MAX_WORKERS, len(results), len(self._symbols), time.time() - fetch_start,
                )

                _wl_scan_count = self._watchlist.count_in_list(results)
                _wl_log = logging.getLogger("WATCHLIST")
                _wl_log.setLevel(logging.INFO)
                if not _wl_log.handlers:
                    _wl_handler = logging.StreamHandler()
                    _wl_handler.setFormatter(logging.Formatter(
                        "%(asctime)s [%(name)s] %(message)s"
                    ))
                    _wl_log.handlers = [_wl_handler]
                _wl_log.info(
                    "MOEDAS PRIORITÁRIAS: %d escaneadas | Total watchlist: %d",
                    _wl_scan_count, len(self._watchlist.ordered),
                )

                for pair in scan_order:
                    try:
                        self._process_scan_result(results.get(pair, {"pair": pair, "ok": False, "error": "Sem resultado"}))
                    except Exception as e:
                        log.error("Erro ao processar %s: %s", pair, e)
                        tb = traceback.extract_tb(e.__traceback__)
                        origem = tb[-1] if tb else None
                        origem_txt = (
                            f"{origem.filename}:{origem.lineno} em {origem.name}"
                            if origem else "origem desconhecida"
                        )
                        self._diag.record_bug(
                            module="QuantOSApp",
                            function="_process_scan_result",
                            last_stage=pair,
                            probable_cause=f"{type(e).__name__}: {e} | origem: {origem_txt}",
                        )
                        self._diag.record_final_decision(
                            pair=pair, status="REJECTED",
                            primary_reason=f"Excecao: {type(e).__name__}",
                            final_decision=f"{type(e).__name__}: {e} | origem: {origem_txt}",
                        )

                self._diag.record_pipeline_funnel(self._funnel)
                self._diag.detect_silent_drops(self._symbols)
                report = self._diag.end_cycle((time.time() - start_time) * 1000)
                diag_report = self._decision_diag.end_cycle()
                self._profiler.end_cycle(len(self._symbols))
                try:
                    rejection_summary = self._rejection_analytics.end_cycle()
                    for _line in self._rejection_analytics.get_last_cycle_report_text().split("\n"):
                        log.info("ANALYTICS| %s", _line)
                except Exception as e:
                    log.warning("RejectionAnalytics: erro ao finalizar ciclo: %s", e)
                    rejection_summary = None

                try:
                    calibration_report = self._calibration.end_cycle()
                    if calibration_report:
                        for _line in calibration_report.split("\n"):
                            log.info("CALIB| %s", _line)
                except Exception as e:
                    log.warning("GateCalibrationEngine: erro ao finalizar ciclo: %s", e)

                try:
                    # RFC V26.1: ciclo vazio (nenhum ativo analisado) nunca
                    # entra no registro de baseline — senao dilui/zera as
                    # medias de 24h do relatorio de 30min e gera falso
                    # alerta de "queda abrupta" no proximo ciclo real.
                    if rejection_summary is not None and rejection_summary.get("total_analyzed", 0) > 0:
                        _recs = self._rejection_analytics.cycle_records
                        _qual = [r.quality for r in _recs if r.quality]
                        _conf = [r.confidence for r in _recs if r.confidence]
                        _cons = [r.consensus for r in _recs if r.consensus]
                        _snap = CycleSnapshot(
                            cycle=self._scan_count,
                            timestamp=time.time(),
                            total_analyzed=rejection_summary.get("total_analyzed", 0),
                            total_approved=rejection_summary.get("total_approved", 0),
                            total_rejected=rejection_summary.get("total_rejected", 0),
                            approval_rate=rejection_summary.get("approval_rate", 0.0),
                            avg_quality=round(sum(_qual) / max(len(_qual), 1), 4) if _qual else 0.0,
                            avg_confidence=round(sum(_conf) / max(len(_conf), 1), 4) if _conf else 0.0,
                            avg_consensus=round(sum(_cons) / max(len(_cons), 1), 4) if _cons else 0.0,
                            avg_rr=0.0,
                            gate_percentages=rejection_summary.get("gate_percentages", {}),
                            gate_counts=rejection_summary.get("gate_counts", {}),
                        )
                        self._baseline_registry.record_cycle(_snap)
                except Exception as e:
                    log.warning("BaselineRegistry: erro ao registrar ciclo: %s", e)

                try:
                    _now_ts = time.time()
                    if _now_ts - self._baseline_registry.last_30min_report >= 1800:
                        self._baseline_registry.last_30min_report = _now_ts
                        _report = self._baseline_reporter.build_30min_report(self._baseline_registry)
                        for _line in self._baseline_reporter.format_30min_log(_report).split("\n"):
                            log.info("30MIN| %s", _line)
                        # RFC V26.X: validacoes de calibracao permanecem so
                        # no log — o usuario pediu para o Telegram nao
                        # receber mais alertas avulsos, so o sinal e o
                        # diagnostico unico diario (ver bloco RCDE abaixo).
                        _impacts = self._baseline_analyzer.pending_impacts(
                            self._baseline_registry
                        )
                        for _v in _impacts:
                            _c = _v["change"]
                            _i = _v["impact"]
                            _c.validated = True
                            _c.impact = _i.get("classification", "desconhecida")
                            _c.impact_data = _i
                            _msg = self._baseline_reporter.build_change_report(_c, _i)
                            log.info("CHANGE_VALIDATION| %s", _msg.replace("\n", " | "))
                except Exception as e:
                    log.warning("30MIN: erro ao gerar relatorio: %s", e)

                # ============================================================
                # RFC V25.5: Diagnostico Rapido Inteligente (Fast Diagnostic)
                # Le apenas dados ja calculados (rejection_summary, health,
                # cycle_records) — nao recalcula nenhum indicador.
                # ============================================================
                try:
                    if rejection_summary is not None:
                        if rejection_summary.get("total_approved", 0) > 0:
                            self._zero_signal_streak = 0
                        else:
                            self._zero_signal_streak += 1

                        _records = self._rejection_analytics.cycle_records
                        _adx_vals = [r.adx for r in _records if r.adx]
                        _avg_adx = sum(_adx_vals) / len(_adx_vals) if _adx_vals else 0.0
                        _regimes = [r.regime for r in _records if r.regime]
                        _regime_mode = max(set(_regimes), key=_regimes.count) if _regimes else ""
                        _health = (report.health if report else {}) or {}
                        _silent_drops = _health.get("silent_drops", 0)
                        _total_assets = report.total_assets if report else 0
                        _silent_drop_pct = (
                            _silent_drops / _total_assets * 100 if _total_assets > 0 else 0.0
                        )

                        fast_diag = build_fast_diagnostic(
                            rejection_summary, self._diag_baseline,
                            self._zero_signal_streak,
                            avg_adx=_avg_adx, regime_mode=_regime_mode,
                            silent_drop_pct=_silent_drop_pct,
                        )
                        for _line in format_fast_diagnostic_log(fast_diag).split("\n"):
                            log.info("FASTDIAG| %s", _line)
                        # RFC V26.1: ciclo vazio nunca atualiza a baseline
                        # historica (senao contamina a media com 0% real).
                        if not fast_diag.ciclo_vazio:
                            self._diag_baseline.update(
                                rejection_summary.get("gate_percentages", {}) or {},
                                rejection_summary.get("approval_rate", 0.0),
                            )
                        # RFC V26.X: sem alertas avulsos no Telegram — o
                        # alerta imediato continua so no log; qualquer
                        # anomalia real reaparece no diagnostico unico
                        # diario via RCDE (mais completo: causa raiz,
                        # hipoteses e confianca, nao so o aviso isolado).
                        if fast_diag.alerta_imediato:
                            log.info("FASTDIAG| ALERTA (so log): %s",
                                      fast_diag.alerta_imediato.replace("\n", " | "))
                        # RFC V26.4: diagnostico detalhado (analisados/
                        # aprovados/rejeitados/ranking por timeframe) e log
                        # tecnico de rotina, nao informacao operacional —
                        # nunca vai ao Telegram. Permanece no log a cada
                        # ciclo, exatamente como antes.
                        for _line in format_detailed_diagnostic(rejection_summary).split("\n"):
                            log.info("DETAILEDDIAG| %s", _line)

                        try:
                            from dataclasses import asdict
                            _cycle_dicts = [asdict(r) for r in self._rejection_analytics.cycle_records]
                            _all_dicts = [asdict(r) for r in self._rejection_analytics.records]
                            v25_6 = build_v25_6_diagnostic(
                                rejection_summary, _cycle_dicts,
                                _cycle_dicts,
                                self._diag_baseline, _all_dicts,
                            )
                            for _line in format_v25_6_report(v25_6).split("\n"):
                                log.info("V25_6| %s", _line)
                        except Exception as e2:
                            log.warning("RFC_V25_6: erro ao gerar diagnostico: %s", e2)
                except Exception as e:
                    log.warning("FastDiagnostic: erro ao gerar diagnostico rapido: %s", e)
                if report:
                    try:
                        advanced = build_advanced_report(report)
                        log.info("DIAGNOSTICO AVANCADO| %s", advanced["resumo_executivo"].replace("\n", " | "))
                    except Exception as e:
                        log.warning("DiagnosticoAvancado: falha ao gerar relatorio: %s", e)

                if diag_report:
                    for _line in diag_report.report_text.split("\n"):
                        log.info("DIAG| %s", _line)

                # ============================================================
                # RFC V26.X: Root Cause Diagnostic Engine — investiga gates em
                # crise a cada ciclo (le report.decisions, ja populado acima,
                # sem recalcular nenhum indicador) e envia UM diagnostico
                # consolidado ao Telegram por dia, as 18h, sempre — sem
                # alertas avulsos (ver remocao de fast_diag.alerta_imediato
                # e do envio do relatorio de 30min acima).
                # ============================================================
                try:
                    if report is not None:
                        self._rcde.record_cycle(report.decisions)
                        rcde_report = self._rcde.investigate(
                            total_analyzed=rejection_summary.get("total_analyzed", 0) if rejection_summary else 0,
                            total_approved=rejection_summary.get("total_approved", 0) if rejection_summary else 0,
                            avg_adx=_avg_adx if rejection_summary else 0.0,
                            regime_mode=_regime_mode if rejection_summary else "",
                            silent_drop_pct=_silent_drop_pct if rejection_summary else 0.0,
                            calibration_data=self._calibration.last_data,
                            duplicates_blocked=self._signal_cache.duplicate_blocked_count,
                        )
                        for _line in format_rcde_report(rcde_report).split("\n"):
                            log.info("RCDE| %s", _line)

                        _now_dt = datetime.now()
                        if (
                            _now_dt.hour >= 18
                            and self._last_daily_diagnostic_date != _now_dt.date()
                        ):
                            self._last_daily_diagnostic_date = _now_dt.date()
                            log.info("RCDE| Telegram: diagnostico diario BLOQUEADO pelo usuario (so sinais)")
                            # Envio de diagnostico desativado pelo usuario
                            # self._telegram.send_diagnostic(format_rcde_telegram(rcde_report))
                except Exception as e:
                    log.warning("RCDE: erro ao gerar diagnostico de causa raiz: %s", e)

                # RFC V20.0: consolidacao de analytics (leitura de
                # TradeRegistry, nao registra nada novo). Fail-safe: erro
                # aqui nunca derruba o ciclo de scan.
                try:
                    analytics_trade_storage.export_trades_json(self._trade_registry)
                    analytics_statistics.persist_metrics(self._trade_registry)
                    analytics_journal.append_new_entries(self._trade_registry)
                    analytics_equity.persist_equity_curve(self._trade_registry, capital_inicial=ACCOUNT_SIZE)
                except Exception as e:
                    log.warning("Analytics: falha ao consolidar dados do ciclo: %s", e)
                delay = self._config.sync_interval_seconds
                if report:
                    self._diag.set_loop_status(self._loop_status, self._last_heartbeat, delay)

                    # Health check
                    health = _run_health_check_sync(self._health)
                    if not health.healthy:
                        log.warning(f"HealthMonitor: {'; '.join(health.errors)}")
                    self._watchdog.report_healthy("scanner")

                # Paper trading: check exits
                try:
                    current_prices = {}
                    for pair in self._symbols[:50]:
                        c = self._provider.get_symbol_ticker(pair)
                        if c:
                            current_prices[pair] = c
                    closed_trades = self._paper.check_exits(current_prices)
                    for t in closed_trades or []:
                        pnl_usdt = t.position_value * (t.pnl_percent / 100)
                        is_stop = t.exit_price <= t.stop_loss
                        time_to_exit = 0.0
                        if t.entry_time:
                            try:
                                from datetime import datetime as _dt
                                entry_dt = _dt.fromisoformat(t.entry_time)
                                exit_dt = _dt.fromisoformat(t.exit_time or _dt.now(timezone.utc).isoformat())
                                time_to_exit = (exit_dt - entry_dt).total_seconds() / 3600
                            except Exception:
                                pass
                        mfe_real = abs(t.highest_seen - t.entry_price) / t.entry_price * 100 if t.entry_price > 0 else 0
                        mae_real = abs(t.entry_price - t.lowest_seen) / t.entry_price * 100 if t.entry_price > 0 else 0
                        try:
                            self._trade_registry.close_trade(
                                signal_id=t.signal_id,
                                resultado=t.status,
                                exit_price=t.exit_price,
                                time_to_tp1=time_to_exit if not is_stop else 0,
                                time_to_stop=time_to_exit if is_stop else 0,
                                lucro_usdt=pnl_usdt if pnl_usdt > 0 else 0,
                                perda_usdt=abs(pnl_usdt) if pnl_usdt < 0 else 0,
                                retorno_pct=t.pnl_percent,
                                mae=mae_real,
                                mfe=mfe_real,
                                r_multiple=t.r_multiple,
                            )
                        except Exception as e:
                            log.warning("TradeRegistry: close_trade error: %s", e)
                        try:
                            self._trade_analytics.record_exit(
                                signal_id=t.signal_id,
                                exit_price=t.exit_price,
                                exit_reason=t.exit_reason,
                                mfe=mfe_real,
                                mae=mae_real,
                                max_profit_before_reversal=t.max_profit_before_reversal,
                                r_multiple=t.r_multiple,
                                pnl_percent=t.pnl_percent,
                                partial_filled=t.partial_filled,
                                trailing_active=t.trailing_active,
                            )
                        except Exception as e:
                            log.warning("TradeAnalytics: record_exit error: %s", e)
                        self._publisher.trade_closed({
                            "pair": t.pair,
                            "direction": t.direction,
                            "entry_price": t.entry_price,
                            "exit_price": t.exit_price,
                            "stop_loss": t.stop_loss,
                            "take_profit": t.take_profit,
                            "pnl_percent": t.pnl_percent,
                            "pnl": t.pnl,
                            "r": t.r_multiple,
                            "reason": t.exit_reason,
                            "status": t.status,
                            "signal_id": t.signal_id,
                        })
                except Exception as e:
                    log.debug(f"PaperTrading exit check: {e}")
                log.info("Scan concluido. Proximo em %ds", delay)

                for i in range(delay):
                    if not self._running:
                        break
                    if i % 30 == 0:
                        self._last_heartbeat = time.time()
                    time.sleep(1)
            except Exception as e:
                self._last_heartbeat = time.time()
                self._loop_status = "ERROR"
                log.exception("Erro no loop principal")
                log.error(f"Restarting loop in 5s (error: {e})")
                time.sleep(5)

    def _decision_has_valid_prices(self, sd: SignalDecision) -> bool:
        return (
            sd.entry_price > 0 and
            sd.stop_loss > 0 and
            sd.take_profit_1 > 0 and
            sd.risk_reward > 0
        )

    def _decision_ready_for_publication(self, sd: SignalDecision) -> bool:
        return sd.approved and self._decision_has_valid_prices(sd)

    def _fetch_and_scan(self, pair: str) -> Dict:
        import time as _time
        pair_start = _time.time()

        with self._profiler.stage("candles"):
            tf_candles = self._provider.get_all_timeframes(symbol=pair, timeframes=TIMEFRAMES)
        if not tf_candles:
            return {"pair": pair, "ok": False, "error": "Sem dados da API"}

        api_ms = (_time.time() - pair_start) * 1000
        tf_counts = {tf: len(c) for tf, c in tf_candles.items()}

        main_candles = tf_candles.get("1h", next(iter(tf_candles.values())))
        with self._profiler.stage("indicadores"):
            market_ctx = self._market.analyze(
                pair=pair, candles=main_candles, timeframe_candles=tf_candles,
            )
        with self._profiler.stage("scanner"):
            report = self._scanner.scan(pair=pair, candles=tf_candles, market_ctx=market_ctx)

        return {
            "pair": pair, "ok": True, "api_ms": api_ms, "tf_counts": tf_counts,
            "tf_candles": tf_candles, "market_ctx": market_ctx, "report": report,
        }

    def _process_scan_result(self, result: Dict):
        pair = result["pair"]
        self._decision_diag.increment_analyzed()
        if not result["ok"]:
            self._funnel["api"] = self._funnel.get("api", 0) + 1
            self._decision_diag.record_filter_rejection(
                filter_name="API", asset=pair,
                details=result.get("error", "Sem dados"),
            )
            self._decision_diag.increment_rejected()
            self._diag.record_market_data(pair, loaded=False, error=result.get("error", "Sem dados"))
            self._diag.record_final_decision(
                pair=pair, status="REJECTED",
                primary_reason="Sem dados",
                final_decision="Rejected at API: no candle data",
            )
            return

        self._funnel["candles"] = self._funnel.get("candles", 0) + 1
        self._diag.record_market_data(pair, loaded=True, api_ms=result["api_ms"])
        self._diag.record_candles(pair, result["tf_counts"])

        tf_candles = result["tf_candles"]
        market_ctx = result["market_ctx"]
        report = result["report"]

        main_candles_tf = tf_candles.get("1h", next(iter(tf_candles.values())))
        _highs_list = [c.high for c in main_candles_tf]
        _lows_list = [c.low for c in main_candles_tf]
        _closes_list = [c.close for c in main_candles_tf]

        if len(_closes_list) < 100:
            log.warning(
                "OHLC curto para %s: %d closes (min 100). TP adaptativo usara fixed fallback.",
                pair, len(_closes_list),
            )

        ind = market_ctx.indicators
        regime_value = market_ctx.regime.value if hasattr(market_ctx.regime, "value") else str(market_ctx.regime)
        self._diag.record_indicators(pair, {
            "atr_percent": ind.atr_percent,
            "adx": ind.adx,
            "rsi": ind.rsi,
            "rvol": ind.rvol,
            "volatility": ind.bb_width,
            "regime": regime_value,
            "regime_confidence": market_ctx.regime_confidence,
        })

        self._decision_diag.record_asset_indicators(pair, {
            "rvol": ind.rvol,
            "adx": ind.adx,
            "atr_percent": ind.atr_percent,
            "rsi": ind.rsi,
            "volatility": ind.bb_width,
            "regime_confidence": market_ctx.regime_confidence,
        })

        # RFC V19.3: atualiza o cache de priorizacao com indicadores JA
        # calculados neste ciclo (sem recalculo), para uso na ORDEM do
        # proximo ciclo de varredura — nao afeta Decision Engine/scoring.
        momentum_scores = [s.scores.momentum_score for s in report.signals if s.scores]
        self._priority_cache[pair] = {
            "rvol": ind.rvol,
            "adx": ind.adx,
            "atr_percent": ind.atr_percent,
            "momentum_score": (sum(momentum_scores) / len(momentum_scores)) if momentum_scores else 0.0,
        }

        self._diag.record_step("Ativos processados", 1)

        all_decisions: List[SignalDecision] = []
        approved_this_pair: List[SignalDecision] = []

        for sig in report.signals:
            if len(sig.rejection_reasons) > 0:
                _dir = sig.direction.value if hasattr(sig.direction, 'value') else str(sig.direction)
                # RFC V25.6: classificacao real por motivo (nao mais um binario
                # Exaustao/Consenso que jogava RVOL/Entry Zone/BOS-CHoCH dentro
                # de "Consenso"). O motivo primario (mesmo usado por
                # audit.log_blocker abaixo) define o gate do registro.
                for _rr in sig.rejection_reasons:
                    self._decision_diag.record_filter_rejection(
                        filter_name=_classify_gate(_rr), asset=pair,
                        timeframe=sig.timeframe, direction=_dir,
                        details=_rr,
                    )
                _gate = _classify_gate(sig.rejection_reasons[0])
                self._rejection_analytics.record_rejection(
                    gate=_gate, symbol=pair,
                    timeframe=sig.timeframe, direction=_dir,
                    found_value=0.0, expected_value=0.0,
                    rvol=sig.rvol or 0.0,
                    adx=sig.adx or 0.0,
                    quality=sig.quality or 0.0,
                    confidence=sig.confidence or 0.0,
                    consensus=sig.scores.consensus_score if sig.scores else 0.0,
                    entry_score=sig.scores.entry_score if sig.scores else 0.0,
                    structure=sig.structure_strength or 0.0,
                    liquidity=sig.scores.liquidity_score if sig.scores else 0.0,
                    flow=sig.scores.flow_score if sig.scores else 0.0,
                    trend=str(sig.structure.structure_type) if hasattr(sig.structure, 'structure_type') else "",
                    regime=sig.regime or "",
                    atr=sig.atr_value or 0.0,
                    reject_reason="; ".join(sig.rejection_reasons),
                )
                audit.log_blocker(sig.rejection_reasons[0], pair)
                continue

            self._funnel["decision_engine"] = self._funnel.get("decision_engine", 0) + 1

            entry_details = sig.entry_details if hasattr(sig, 'entry_details') else None
            log.info(
                "PIPELINE| sig_pre_decision sym=%s tf=%s dir=%s entry=%.8f atr=%.8f "
                "rvol=%.4f adx=%.2f regime=%s patterns=%d",
                pair, sig.timeframe,
                sig.direction.value if hasattr(sig.direction, 'value') else str(sig.direction),
                sig.entry_price, sig.atr_value, sig.rvol, sig.adx,
                sig.regime, len(sig.patterns),
            )

            with self._profiler.stage("decisao_risco"):
                sd = DecisionEngine.evaluate_signal(
                    sig,
                    entry_details=entry_details,
                    highs=_highs_list,
                    lows=_lows_list,
                    closes=_closes_list,
                )
            calibration_measurement.record(pair, sig.timeframe, sd, sig)
            self._calibration.record_signal_all_gates(
                symbol=pair, timeframe=sig.timeframe,
                direction=sd.direction,
                result="APPROVED" if sd.approved else "REJECTED",
                signal=sig, sd=sd,
            )

            log.info(
                "SD[%s] %s %s | aprov=%s entry=%.8f sl=%.8f tp1=%.8f rr=%.4f "
                "entry_score=%.4f quality=%.4f dir=%s ez=%s | %s",
                sd.trace_id, pair, sig.timeframe,
                sd.approved,
                sd.entry_price, sd.stop_loss, sd.take_profit_1, sd.risk_reward,
                sd.entry_score, sd.quality, sd.direction,
                sd.entry_zone_valid, sd.reject_reason,
            )

            if sd.approved:
                approved_this_pair.append(sd)
                self._funnel["aprovados"] = self._funnel.get("aprovados", 0) + 1
                self._rejection_analytics.record_approval(
                    symbol=pair, timeframe=sig.timeframe,
                    direction=sd.direction,
                    overall_score=(sd.quality * 0.5 + sd.consensus * 0.3 + sd.entry_score * 0.2) if sd.quality > 0 else 0.0,
                    quality=sd.quality, confidence=sd.confidence,
                    consensus=sd.consensus,
                    entry_score=sd.entry_score,
                    rvol=sig.rvol or 0.0, adx=sig.adx or 0.0,
                    atr=sig.atr_value or 0.0,
                    structure=sd.structural_score or 0.0,
                    liquidity=sd.liquidity_score or 0.0,
                    flow=sd.institutional_score or 0.0,
                    trend=sd.trend or "",
                    regime=sig.regime or "",
                )
            else:
                reject = (sd.reject_reason or "").lower()
                if "rvol" in reject:
                    self._funnel["candles"] = self._funnel.get("candles", 0) + 1
                elif "adx" in reject:
                    self._funnel["indicadores"] = self._funnel.get("indicadores", 0) + 1
                elif "bos" in reject or "choch" in reject or "estrutur" in reject:
                    self._funnel["estrutura"] = self._funnel.get("estrutura", 0) + 1
                elif "entry" in reject:
                    self._funnel["entry_zone"] = self._funnel.get("entry_zone", 0) + 1
                elif "quality" in reject:
                    self._funnel["quality_gate"] = self._funnel.get("quality_gate", 0) + 1
                elif "consensus" in reject:
                    self._funnel["consensus"] = self._funnel.get("consensus", 0) + 1
                elif "confian" in reject or "confidence" in reject or "descalibracao" in reject:
                    self._funnel["quality_gate"] = self._funnel.get("quality_gate", 0) + 1
                elif "kalman" in reject:
                    self._funnel["smart_money"] = self._funnel.get("smart_money", 0) + 1
                elif "lateral" in reject:
                    self._funnel["estrutura"] = self._funnel.get("estrutura", 0) + 1
                elif "rr" in reject:
                    self._funnel["entry_zone"] = self._funnel.get("entry_zone", 0) + 1
                else:
                    self._funnel["entry_zone"] = self._funnel.get("entry_zone", 0) + 1

                _rej_val, _rej_th = 0.0, 0.0
                if "rvol" in reject:
                    _rej_val, _rej_th = sig.rvol or 0.0, HARD_MIN_RVOL
                elif "adx" in reject:
                    _rej_val, _rej_th = sig.adx or 0.0, HARD_MIN_ADX
                elif "bos" in reject or "choch" in reject:
                    _rej_val, _rej_th = 0.0, 0.0
                elif "estrutur" in reject:
                    _rej_val, _rej_th = sd.structural_score or 0.0, 0.30
                elif "entry" in reject:
                    _rej_val, _rej_th = sd.entry_score or 0.0, 0.40
                elif "quality" in reject:
                    _rej_val, _rej_th = sd.quality or 0.0, 0.60
                elif "consensus" in reject:
                    _rej_val, _rej_th = sd.consensus or 0.0, CONSENSUS_MINIMUM_SCORE
                elif "confidence" in reject or "confian" in reject:
                    _rej_val, _rej_th = sd.confidence or 0.0, 0.75
                elif "descalibracao" in reject:
                    _rej_val, _rej_th = abs((sd.confidence or 0.0) - (sd.quality or 0.0)), 0.10
                elif "kalman" in reject:
                    _rej_val, _rej_th = 0.0, 0.0
                elif "lateral" in reject:
                    _rej_val, _rej_th = 0.0, 0.0
                elif "rr" in reject:
                    _rej_val, _rej_th = sd.risk_reward or 0.0, 2.0
                self._decision_diag.record_filter_rejection(
                    filter_name=sd.reject_reason or "Desconhecido",
                    asset=pair, timeframe=sig.timeframe,
                    direction=sd.direction,
                    value=_rej_val, threshold=_rej_th,
                    details=sd.reject_reason or "",
                )
                self._decision_diag.increment_rejected()
                self._rejection_analytics.record_rejection(
                    gate=sd.reject_reason or "Desconhecido",
                    symbol=pair, timeframe=sig.timeframe,
                    direction=sd.direction,
                    found_value=_rej_val, expected_value=_rej_th,
                    overall_score=(sd.quality * 0.5 + sd.consensus * 0.3 + sd.entry_score * 0.2) if sd.quality > 0 else 0.0,
                    quality=sd.quality, confidence=sd.confidence,
                    consensus=sd.consensus,
                    entry_score=sd.entry_score,
                    rvol=sig.rvol or 0.0, adx=sig.adx or 0.0,
                    atr=sig.atr_value or 0.0,
                    structure=sd.structural_score or 0.0,
                    liquidity=sd.liquidity_score or 0.0,
                    flow=sd.institutional_score or 0.0,
                    trend=sd.trend or "",
                    regime=sig.regime or "",
                    reject_reason=sd.reject_reason or "",
                )
                audit.log_blocker(sd.reject_reason, pair)
                log.info("DecisionEngine: %s %s — %s", pair, sig.timeframe, sd.reject_reason)
            self._diag.record_quality_gate(pair, sig.scores.to_dict() if sig.scores else {},
                                           sd.approved, [sd.reject_reason] if not sd.approved else [])
            self._diag.record_decision(sd.to_dict())
            all_decisions.append(sd)

        # CycleSignalResult (RFC V18.4 Etapa 1/2): objeto oficial unico do
        # ciclo para este ativo. O "melhor sinal" e calculado AQUI, uma unica
        # vez, com _cycle_rank() — nem o envio ao Telegram nem o registro de
        # diagnostico recalculam isso separadamente (antes usavam criterios
        # diferentes e podiam apontar para timeframes distintos do mesmo
        # ativo no mesmo ciclo).
        cycle_result = CycleSignalResult(pair=pair, all_decisions=all_decisions, approved_signals=approved_this_pair)
        _wl_bonus_cycle = WATCHLIST_PRIORITY_BONUS * 0.001
        if approved_this_pair:
            cycle_result.best_signal = max(
                approved_this_pair,
                key=lambda sd: _cycle_rank(sd) + (
                    _wl_bonus_cycle if self._watchlist.is_watchlist(sd.symbol) else 0.0
                ),
            )
            cycle_result.best_is_approved = True
        elif all_decisions:
            cycle_result.best_signal = max(
                all_decisions,
                key=lambda sd: _cycle_rank(sd) + (
                    _wl_bonus_cycle if self._watchlist.is_watchlist(sd.symbol) else 0.0
                ),
            )
            cycle_result.best_is_approved = False

        # Envio ao Telegram: so o melhor sinal aprovado do ciclo (RFC_RECALIBRACAO_
        # SINAIS_INSTITUCIONAL.md) — um scan() produz 1 Signal por timeframe
        # monitorado para o mesmo par; antes, cada timeframe aprovado era
        # enviado independentemente, gerando ate 4 sinais duplicados do
        # mesmo ativo no mesmo ciclo.
        if approved_this_pair:
            best_sd = cycle_result.best_signal
            if len(approved_this_pair) > 1:
                discarded = [d.timeframe for d in approved_this_pair if d is not best_sd]
                log.info(
                    "Dedup ciclo: %s venceu com timeframe %s (score=%.4f) sobre %s",
                    pair, best_sd.timeframe, _cycle_rank(best_sd), ", ".join(discarded),
                )

            from SERVICES.telegram.active_signal_manager import ActiveSignalManager
            asm = ActiveSignalManager()
            asm.cleanup_expired()

            res = asm.resolve(
                best_sd.symbol, best_sd.timeframe,
                best_sd.direction, best_sd.to_dict()
            )

            skip_telegram = res.action == "skip"
            if skip_telegram:
                if res.skip_reason == "cooldown":
                    log.info(
                        "Cooldown ativo para %s_%s. Impacto: %d/100",
                        best_sd.symbol, best_sd.timeframe, res.impact_score,
                    )
                else:
                    log.info(
                        "Update ignorado. Impacto operacional: %d/100. "
                        "Nenhuma alteracao relevante detectada.",
                        res.impact_score,
                    )

            data = best_sd.to_dict()
            data["_watchlist_priority"] = self._watchlist.is_watchlist(best_sd.symbol)
            data["message_type"] = "update"
            if res.action == "new":
                data["message_type"] = "new"
                asm.create(best_sd.symbol, best_sd.timeframe, best_sd.direction, data)
            elif res.action == "reversal":
                data["message_type"] = "update"
                asm.create(best_sd.symbol, best_sd.timeframe, best_sd.direction, data)
            data["update_label"] = res.update_label
            data["cycle_id"] = self._scan_count
            data["engine_version"] = "V18.4"
            data["fingerprint"] = self._fingerprint  # RFC V25.3 (temporario)


            # ============================================================
            # SCORE COMPUTATION (RFC V18.4/V19.1)
            # ============================================================
            from ENGINE.common.operational import (
                compute_overall_score, compute_conviction_level,
                compute_expectancy_level, estimate_time_to_tp1,
                compute_penalties, compute_confluence_score,
                compute_risk_decomposition, compute_main_reason,
                compute_probability, compute_coherence_audit,
                compute_institutional_coherence_score,
                compute_weighted_vote, compute_coarse_penalty_details,
            )
            os_data = compute_overall_score(data)
            data["overall_score"] = os_data
            data["overall_score_value"] = os_data["overall_score"]
            data["overall_score_bar"] = os_data["overall_bar"]
            data["overall_score_tier"] = os_data["overall_tier"]
            data["conviction_level"] = compute_conviction_level(
                data.get("confidence_score", data.get("confidence", 0)),
                data.get("quality_score", data.get("quality", 0)),
                data.get("consensus_score", data.get("consensus", 0)),
            )
            data["expectancy_level"] = compute_expectancy_level(data)
            data["time_to_tp1"] = estimate_time_to_tp1(
                data.get("timeframe", "1h"), data.get("structure_strength", 0.5),
            )
            data["penalty_reasons"] = [
                p for p in compute_penalties(data)
            ]
            data["penalty_texts"] = [
                f"{p.reason} (peso: {p.weight:.2f})" for p in data["penalty_reasons"]
            ]

            # V19.1: Confluencia, Risco, Motivo Principal, MTF Conflict
            data["confluence_score"] = compute_confluence_score(data)
            data["risk_decomposition"] = compute_risk_decomposition(data)
            data["main_reason"] = compute_main_reason(data)
            # RFC V26.8: detect_mtf_conflict() recebia all_decisions (TODAS
            # as decisoes avaliadas no ciclo para o par, aprovadas OU
            # rejeitadas). Uma direcao de um timeframe REJEITADO (por RVOL
            # fraco, consenso baixo, etc. — motivos sem relacao com o vies
            # direcional) nao e uma leitura validada do mercado; usar essa
            # leitura para vetar um sinal ja aprovado por todos os gates
            # tratava ruido de timeframes descartados como se fosse
            # divergencia real. Conflito MTF agora so considera timeframes
            # que TAMBEM foram aprovados nesse ciclo — discordancia entre
            # duas leituras validadas continua bloqueando (comportamento
            # do Hard Gate V25 preservado), mas ruido de rejeitados nao.
            mtf_results = DecisionEngine.detect_mtf_conflict(approved_this_pair)
            data["mtf_conflict"] = mtf_results.get(best_sd.timeframe, False) if mtf_results else False

            # V18.4: Probabilidade, Coerencia, Coherence Score, Weighted Vote
            data["probability"] = compute_probability(data)
            data["coherence_audit"] = compute_coherence_audit(data)
            data["coherence_score"] = compute_institutional_coherence_score(data)
            data["weighted_vote"] = compute_weighted_vote(data)
            data["penalty_details"] = compute_coarse_penalty_details(data)

            # ============================================================
            # FINAL VALIDATION BLOQUEANTE (V18.4)
            # ============================================================
            overall_tier = data.get("overall_score_tier", "")
            overall_val = data.get("overall_score_value", 0)
            dir_check = data.get("direction", "").upper()
            kalman_check = (data.get("kalman_direction", "") or "").upper()
            kalman_up = "UP" in kalman_check or "ALT" in kalman_check
            kalman_down = "DOWN" in kalman_check or "BAIX" in kalman_check
            regime_check = (data.get("trend", "") or "").lower()
            is_long = dir_check in ("LONG", "BUY")

            validation_errors = []
            if is_long and kalman_down:
                validation_errors.append("LONG + Kalman DOWN — REJEITADO")
            if not is_long and kalman_up:
                validation_errors.append("SHORT + Kalman UP — REJEITADO")
            if overall_tier == "OURO" and overall_val < 65:
                validation_errors.append(f"OURO com indice {overall_val} < 65 — REJEITADO")
            if overall_tier == "PLATINA" and overall_val < 75:
                validation_errors.append(f"PLATINA com indice {overall_val} < 75 — REJEITADO")
            if overall_tier == "DIAMANTE" and overall_val < 85:
                validation_errors.append(f"DIAMANTE com indice {overall_val} < 85 — REJEITADO")
            if regime_check in ("ranging", "lateral"):
                exp_level = data.get("expectancy_level", "")
                has_breakout = data.get("main_reason", "") and ("BOS" in data.get("main_reason", "") or "CHOCH" in data.get("main_reason", ""))
                if exp_level in ("Alta", "Muito Alta") and not has_breakout:
                    validation_errors.append(f"Mercado lateral + expectativa {exp_level} sem rompimento — REJEITADO")

            # V18.4 (Item 4): Classificacao deve obedecer ranges exatos
            _label = data.get("classification_label", "").upper()
            if _label in ("DIAMANTE", "PLATINA", "OURO", "PRATA", "BRONZE") and overall_val < 50:
                validation_errors.append(f"Classificacao {_label} com Overall {overall_val} < 50 — REJEITADO")
            if not _label or _label == "REPROVADO":
                if overall_val >= 50:
                    validation_errors.append(f"Overall Score {overall_val} >= 50 mas sem classificacao — REJEITADO")

            # V18.4: Coherence Score < 50 = bloquear
            cs = data.get("coherence_score", {})
            if isinstance(cs, dict) and cs.get("coherence_score", 100) < 50:
                validation_errors.append(f"Coherence Score {cs.get('coherence_score', 0)} < 50 — REJEITADO")

            # V18.4: Weighted Vote < 55% = bloquear
            wv = data.get("weighted_vote", {})
            if isinstance(wv, dict) and not wv.get("approved", True):
                validation_errors.append(
                    f"Votacao Ponderada {wv.get('concordance_pct', 0)}% < 55% — REJEITADO"
                )

            # V25 Hard Gate Estrutural: Conflito MTF sempre reprova
            is_mtf_conflict = data.get("mtf_conflict", False)
            if is_mtf_conflict:
                validation_errors.append("Conflito MTF entre timeframes — REJEITADO")

            data["final_validation_errors"] = validation_errors

            if validation_errors:
                for _ve in validation_errors:
                    _fv_gate = "Classificacao" if "OURO" in _ve or "PLATINA" in _ve or "DIAMANTE" in _ve or "Classificacao" in _ve else "Coherence" if "Coherence" in _ve else "Weighted Vote" if "Votacao" in _ve else "Kalman" if "Kalman" in _ve else "MTF Conflict" if "Conflito MTF" in _ve else "Lateral" if "lateral" in _ve.lower() else "Final Validation"
                    _fv_val, _fv_th = 0.0, 0.0
                    if "Kalman" in _ve:
                        _fv_val, _fv_th = 0.0, 0.0
                    elif "Conflito MTF" in _ve:
                        _fv_val, _fv_th = 1.0, 0.0
                    elif "OURO" in _ve:
                        _fv_val, _fv_th = data.get("overall_score_value", 0), 70.0
                    elif "PLATINA" in _ve:
                        _fv_val, _fv_th = data.get("overall_score_value", 0), 80.0
                    elif "DIAMANTE" in _ve:
                        _fv_val, _fv_th = data.get("overall_score_value", 0), 90.0
                    elif "Coherence" in _ve:
                        _cs_v = data.get("coherence_score", {})
                        _fv_val = _cs_v.get("coherence_score", 0) if isinstance(_cs_v, dict) else 0
                        _fv_th = 60.0
                    elif "Votacao" in _ve:
                        _wv_v = data.get("weighted_vote", {})
                        _fv_val = _wv_v.get("concordance_pct", 0) if isinstance(_wv_v, dict) else 0
                        _fv_th = 70.0
                    elif "Classificacao" in _ve:
                        _fv_val = data.get("overall_score_value", 0)
                        _fv_th = 50.0
                    self._decision_diag.record_filter_rejection(
                        filter_name=_fv_gate, asset=pair,
                        timeframe=data.get("timeframe", ""),
                        direction=data.get("direction", ""),
                        value=_fv_val, threshold=_fv_th,
                        details=_ve,
                    )
                    self._decision_diag.increment_rejected()
                    self._rejection_analytics.record_rejection(
                        gate=_fv_gate, symbol=pair,
                        timeframe=data.get("timeframe", ""),
                        direction=data.get("direction", ""),
                        found_value=_fv_val, expected_value=_fv_th,
                        overall_score=data.get("overall_score_value", 0.0),
                        quality=data.get("quality_score", 0.0),
                        confidence=data.get("confidence_score", 0.0),
                        consensus=data.get("consensus_score", 0.0),
                        reject_reason=_ve,
                    )

                # V18.5 Item 6: BLOCKED_SIGNALS.log
                _bsym = data.get("symbol", "?")
                _btf = data.get("timeframe", "?")
                _bdir = data.get("direction", "?")
                _bmotivo = "; ".join(validation_errors)
                _bcs = data.get("coherence_score", {})
                _bcs_val = _bcs.get("coherence_score", "N/A") if isinstance(_bcs, dict) else "N/A"
                _bwv = data.get("weighted_vote", {})
                _bwv_pct = _bwv.get("concordance_pct", "N/A") if isinstance(_bwv, dict) else "N/A"
                _bgates = []
                for _ve in validation_errors:
                    if "Kalman" in _ve:
                        _bgates.append("GATE12")
                    elif "Conflito MTF" in _ve:
                        _bgates.append("MTF_CONFLICT")
                    elif "OURO" in _ve or "PLATINA" in _ve or "DIAMANTE" in _ve:
                        _bgates.append("CLASSIFICATION")
                    elif "lateral" in _ve.lower():
                        _bgates.append("GATE11")
                    elif "Coherence" in _ve:
                        _bgates.append("COHERENCE")
                    elif "Votacao" in _ve:
                        _bgates.append("WEIGHTED_VOTE")
                    elif "Classificacao" in _ve:
                        _bgates.append("CLASSIFICATION")
                    else:
                        _bgates.append("FINAL_VALIDATION")
                _blocked_log.warning(
                    "%s | TF=%s | %s | motivo=%s | gates=%s | CS=%s | WV=%s%%",
                    _bsym, _btf, _bdir, _bmotivo,
                    ",".join(_bgates), _bcs_val, _bwv_pct,
                )
                log.warning(
                    "FINAL VALIDATION BLOCKED: %s | %s",
                    data.get("symbol", "?"), _bmotivo
                )
                # Nao envia ao Telegram — inconsistencia critica
                _publish_validation_blocked(self._publisher, data, _bmotivo)
                data["_validation_blocked"] = True

            # ============================================================
            # RFC V18.4 Etapa 3: quantidade e saldo (execucao real)
            # ============================================================
            real_balance = self._bot.balance.total
            real_quantity = self._bot.risk_manager.calculate_position_size(
                balance=real_balance,
                entry_price=best_sd.entry_price,
                stop_loss=best_sd.stop_loss,
                quality_score=best_sd.quality,
            )
            data["quantity"] = real_quantity
            data["balance"] = real_balance
            data["leverage"] = self._config.leverage

            # ============================================================
            # RFC V21: Institutional Math Auditor
            # ============================================================
            _audit_result = InstitutionalMathAuditor.audit(
                entry_price=best_sd.entry_price,
                stop_loss=best_sd.stop_loss,
                take_profit_1=best_sd.take_profit_1,
                quantity=real_quantity,
                balance=real_balance,
                leverage=data["leverage"],
                risk_reward_expected=best_sd.risk_reward,
                account_capital=ACCOUNT_SIZE,
                max_leverage=LEVERAGE_MAX_USER,
            )
            _audit_result.log_report()
            if not _audit_result.overall:
                _blocked_log.warning(
                    "MATH_VALIDATION_FAILED | %s TF=%s | motivo=%s",
                    best_sd.symbol, best_sd.timeframe,
                    _audit_result.hard_fail_reason,
                )
                log.warning(
                    "MATH AUDIT BLOCKED: %s — %s",
                    best_sd.symbol, _audit_result.hard_fail_reason,
                )
                data["_validation_blocked"] = True
                data["hard_fail_reason"] = _audit_result.hard_fail_reason

            # ============================================================
            # RFC V22: Exchange Execution Validator
            # ============================================================
            if ENABLE_EXECUTION_VALIDATOR and not data.get("_validation_blocked", False):
                _sym_info = _build_default_symbol_info(best_sd.symbol)
                _exec_val = ExchangeExecutionValidator(
                    symbol_info=_sym_info,
                    auto_round_prices=AUTO_ROUND_PRICES,
                    auto_round_quantity=AUTO_ROUND_QUANTITY,
                    block_invalid=BLOCK_INVALID_EXECUTION,
                    tolerance=EXECUTION_VALIDATION_TOLERANCE,
                    slippage_rate=EXECUTION_SLIPPAGE_RATE,
                    funding_rate_estimate=EXECUTION_FUNDING_RATE_EST,
                )
                _exec_result = _exec_val.validate(
                    entry_price=best_sd.entry_price,
                    stop_loss=best_sd.stop_loss,
                    take_profit_1=best_sd.take_profit_1,
                    take_profit_2=best_sd.take_profit_2,
                    quantity=real_quantity,
                    balance=real_balance,
                    leverage=data["leverage"],
                    direction=best_sd.direction,
                )
                _exec_result.log_report()
                if not _exec_result.overall:
                    _blocked_log.warning(
                        "EXCHANGE_VALIDATION_FAILED | %s TF=%s | motivo=%s",
                        best_sd.symbol, best_sd.timeframe,
                        _exec_result.hard_fail_reason,
                    )
                    log.warning(
                        "EXECUTION VALIDATOR BLOCKED: %s — %s",
                        best_sd.symbol, _exec_result.hard_fail_reason,
                    )
                    data["_validation_blocked"] = True
                    data["hard_fail_reason"] = _exec_result.hard_fail_reason
                elif AUTO_ROUND_PRICES or AUTO_ROUND_QUANTITY:
                    # RFC V26.7: quando o auto-round esta ativo, os checks
                    # de tick_size/step_size passam com o valor arredondado
                    # (ver ExchangeExecutionValidator._check_tick_size), mas
                    # a validacao em si nao alterava entry/stop/tp/quantity
                    # usados no resto do pipeline — Telegram e auditoria
                    # continuavam mostrando os precos brutos, nao alinhados
                    # ao exchange. Propaga os valores arredondados de volta
                    # para `data`, que e a fonte usada dali em diante.
                    if AUTO_ROUND_PRICES:
                        data["entry_price"] = _exec_val.round_price(best_sd.entry_price)
                        data["stop_loss"] = _exec_val.round_price(best_sd.stop_loss)
                        data["take_profit_1"] = _exec_val.round_price(best_sd.take_profit_1)
                        if best_sd.take_profit_2:
                            data["take_profit_2"] = _exec_val.round_price(best_sd.take_profit_2)
                    if AUTO_ROUND_QUANTITY:
                        data["quantity"] = _exec_val.round_quantity(real_quantity)

            data["audit"] = {
                "signal_id": best_sd.signal_id or best_sd.trace_id,
                "cycle_id": self._scan_count,
                "engine_version": "V18.4",
                "processing_time_ms": round((time.time() - self._last_start_time) * 1000, 1) if hasattr(self, '_last_start_time') else 0.0,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "scores": {
                    "quality": best_sd.quality,
                    "confidence": best_sd.confidence,
                    "consensus": best_sd.consensus,
                    "institutional": best_sd.institutional_score,
                    "structural": best_sd.structural_score,
                    "market": best_sd.market_score,
                    "liquidity": best_sd.liquidity_score,
                    "entry_score": best_sd.entry_score,
                },
                "gates": {
                    "rvol_ok": best_sd.rvol_ok,
                    "adx_ok": best_sd.adx_ok,
                    "structure_ok": best_sd.structure_ok,
                    "entry_zone_ok": best_sd.entry_zone_ok,
                    "quality_ok": best_sd.quality_ok,
                    "consensus_ok": best_sd.consensus_ok,
                    "confidence_ok": best_sd.confidence_ok,
                    "rr_ok": best_sd.rr_ok,
                },
                "penalty_reasons": data.get("penalty_reasons", []),
                "mtf_conflict": data.get("mtf_conflict", False),
                "confluence_score": data.get("confluence_score", 0),
                "main_reason": data.get("main_reason", ""),
                "probability": data.get("probability", {}),
                "coherence": data.get("coherence_audit", {}),
                "validation": data.get("final_validation_errors", []),
                "coherence_score": data.get("coherence_score", {}),
                "weighted_vote": data.get("weighted_vote", {}),
                "penalty_details": data.get("penalty_details", []),
            }

            if skip_telegram:
                pass
            elif not self._exchange_validation.is_valid_symbol(best_sd.symbol):
                # RFC V18.5: defesa em profundidade — o Discovery ja
                # filtra simbolos sem contrato futuro real, mas o
                # Telegram nunca deve enviar um sinal de ativo invalido,
                # independentemente de como o simbolo chegou ate aqui.
                log.warning(
                    "TELEGRAM BLOCKED (INVALID_SYMBOL): %s nao existe como "
                    "contrato futuro na MEXC.",
                    best_sd.symbol,
                )
            elif data.get("_validation_blocked", False):
                log.info(
                    "TELEGRAM BLOCKED (VALIDATION): %s_%s -> %s",
                    best_sd.symbol, best_sd.timeframe,
                    "; ".join(validation_errors),
                )
            else:
                _cs_disp = data.get("coherence_score", {})
                _cs_v = _cs_disp.get("coherence_score", "?") if isinstance(_cs_disp, dict) else "?"
                _wv_disp = data.get("weighted_vote", {})
                _wv_v = _wv_disp.get("concordance_pct", "?") if isinstance(_wv_disp, dict) else "?"

                if not self._signal_cache.can_send(
                    best_sd.symbol, best_sd.timeframe, best_sd.direction, data
                ):
                    log.info(
                        "[SIGNAL CACHE] %s %s %s — Ja enviado neste candle. Ignorando novo envio.",
                        best_sd.symbol, best_sd.timeframe, best_sd.direction,
                    )
                else:
                    self._decision_diag.increment_approved()
                    op_id = f"{best_sd.symbol.upper()}_{best_sd.timeframe}"
                    self._signal_cache.mark_sent(best_sd.symbol, best_sd.timeframe, best_sd.direction, data)
                    asm.mark_sent(op_id, data)
                    with self._profiler.stage("telegram"):
                        self._publisher.decision_made(data)
                    log.info(
                        "TELEGRAM SENT: %s -> %s",
                        op_id, res.update_label or "novo_sinal",
                    )

        has_signals = bool(report.signals)
        if has_signals:
            from ENGINE.scanner.scanner_types import PatternType
            first = report.signals[0]
            pats = first.patterns or []
            struct_data = {
                "trend": str(first.structure.structure_type) if hasattr(first.structure, "structure_type") else "unknown",
                "strength": first.structure.structure_strength if hasattr(first.structure, "structure_strength") else 0,
                "bos": sum(1 for p in pats if p.type == PatternType.BOS),
                "choch": sum(1 for p in pats if p.type == PatternType.CHOCH),
            }
            self._diag.record_structure(pair, struct_data)

            if not all_decisions:
                best_sig = max(report.signals, key=lambda s: s.scores.quality_score if s.scores else 0.0)
                motivo_primario, motivos_secundarios, decisao_final = _resumir_motivos_sem_sinal(report.signals)
                # RFC V25.6: o loop "for sig in report.signals" acima ja
                # registrou (com o gate correto via _classify_gate) cada
                # motivo de todo sinal com rejection_reasons — o mesmo
                # universo que _resumir_motivos_sem_sinal le. Recontar aqui
                # sob o rotulo generico "Scanner" duplicava essas contagens
                # (Consenso/RVOL/Estrutura apareciam infladas). So registrar
                # aqui quando NENHUM sinal teve rejection_reasons (ex.:
                # excecao no Decision Engine) — informacao genuinamente nova.
                _scanner_ja_registrou = any(s.rejection_reasons for s in report.signals)
                for _sr in motivos_secundarios + [motivo_primario]:
                    self._decision_diag.record_filter_rejection(
                        filter_name="Scanner", asset=pair,
                        timeframe=best_sig.timeframe if hasattr(best_sig, 'timeframe') else "",
                        direction=best_sig.direction.value if hasattr(best_sig.direction, 'value') else str(best_sig.direction) if hasattr(best_sig, 'direction') else "",
                        details=_sr,
                    )
                    self._decision_diag.increment_rejected()
                    if not _scanner_ja_registrou:
                        self._rejection_analytics.record_rejection(
                            gate=_classify_gate(_sr), symbol=pair,
                            timeframe=best_sig.timeframe if hasattr(best_sig, 'timeframe') else "",
                            direction=best_sig.direction.value if hasattr(best_sig.direction, 'value') else str(best_sig.direction) if hasattr(best_sig, 'direction') else "",
                            found_value=0.0, expected_value=0.0,
                            reject_reason=_sr,
                        )
                entry_score = best_sig.scores.entry_score if best_sig.scores else 0.0
                consensus_score = best_sig.scores.consensus_score if best_sig.scores else 0.0
                self._diag.record_entry_zone(
                    pair, zone_type="scanner_rejected",
                    score=round(entry_score * 100 if entry_score <= 1 else entry_score, 1),
                    approved=False,
                )
                self._diag.record_consensus(pair, {
                    "consensus_score": consensus_score,
                    "classification": "REJEITADO",
                    "votes": [],
                })
                self._diag.record_quality_gate(
                    pair, best_sig.scores.to_dict() if best_sig.scores else {},
                    False, [motivo_primario] + motivos_secundarios,
                )
                self._diag.record_final_decision(
                    pair=pair, status="REJECTED",
                    primary_reason=motivo_primario,
                    final_decision=decisao_final,
                    secondary_reasons=motivos_secundarios,
                )
                return

        if all_decisions:
            # RFC V18.4 Etapa 2: usa o mesmo best_signal ja calculado em
            # cycle_result — nao recalcula com um criterio diferente. Antes
            # este bloco usava max(all_decisions, key=lambda sd: sd.quality),
            # que podia escolher um timeframe diferente do que foi de fato
            # enviado ao Telegram (cuja selecao considerava apenas os
            # aprovados, ranqueados por quality+consensus+RR).
            best_sd = cycle_result.best_signal

            self._diag.record_smart_money(pair,
                order_blocks=best_sd.bos, fvgs=best_sd.fvg, sweeps=best_sd.liquidity_sweep,
            )
            self._diag.record_entry_zone(pair,
                zone_type=best_sd.entry_zone_status or "multi_tf",
                score=round(best_sd.entry_score * 100 if best_sd.entry_score < 1 else best_sd.entry_score, 1),
                approved=best_sd.entry_zone_valid,
            )

            decision_str = "APPROVED" if best_sd.approved else "REJECTED"
            self._diag.record_final_decision(
                pair=pair, status=decision_str,
                primary_reason=best_sd.reject_reason,
                final_decision=best_sd.reject_reason,
                direction=best_sd.direction,
                trace_id=best_sd.trace_id,
            )

            if self._decision_ready_for_publication(best_sd):
                if data.get("_validation_blocked", False):
                    log.info(
                        "PAPER TRADING BLOCKED (VALIDATION): %s_%s",
                        best_sd.symbol, best_sd.timeframe,
                    )
                    return
                for sig in report.signals:
                    if len(sig.rejection_reasons) == 0:
                        self._diag.record_signal(sig)
                for sd in _paper_trade_decisions(cycle_result, data):
                        sd_stop = sd.stop_loss if sd.stop_loss > 0 else sd.entry_price * 0.98
                        sd_tp = sd.take_profit_1 if sd.take_profit_1 > 0 else sd.entry_price * 1.03
                        tp2_val = 0.0
                        partial_val = 0.0
                        be_val = 0.0
                        try:
                            from ENGINE.risk.tp_adaptativo import calculate_adaptive_tp
                            _tp_data_ok = len(_closes_list) >= 100 and len(_highs_list) == len(_closes_list) and len(_lows_list) == len(_closes_list)
                            if not _tp_data_ok:
                                self._trade_analytics.increment_telemetry("fallback_tp")
                                log.info("TPAdaptativo: OHLC insuficiente (%d closes), fallback")
                                raise ValueError("OHLC insuficiente")
                            self._trade_analytics.increment_telemetry("adaptive_tp_used")
                            tp_res = calculate_adaptive_tp(
                                entry=sd.entry_price, stop_loss=sd_stop,
                                direction=sd.direction,
                                atr=sd.atr if hasattr(sd, 'atr') else 0,
                                closes=_closes_list, highs=_highs_list, lows=_lows_list,
                            )
                            tp2_val = tp_res.tp2
                            partial_val = tp_res.partial_tp
                            be_val = tp_res.break_even_price
                            if tp_res.resistance_used:
                                self._trade_analytics.increment_telemetry("resistance_found")
                            else:
                                self._trade_analytics.increment_telemetry("resistance_ignored")
                        except Exception:
                            self._trade_analytics.increment_telemetry("fallback_tp")
                        trade = self._paper.record_entry(
                            pair=sd.symbol, direction=sd.direction,
                            entry_price=sd.entry_price, stop_loss=sd_stop,
                            take_profit=sd_tp, cycle=self._scan_count,
                            quality=sd.quality, setup="decision_engine",
                            regime=regime_value, signal_id=sd.signal_id or sd.trace_id,
                            take_profit_2=tp2_val,
                            partial_tp=partial_val,
                            break_even_price=be_val,
                        )
                        if trade:
                            try:
                                self._trade_analytics.record_entry(
                                    signal_id=trade.signal_id,
                                    symbol=sd.symbol,
                                    direction=sd.direction,
                                    entry_price=sd.entry_price,
                                    stop_loss=sd_stop,
                                    tp1=sd_tp,
                                    tp2=tp2_val,
                                    partial_tp=partial_val,
                                    break_even_price=be_val,
                                    atr=sd.atr if hasattr(sd, 'atr') else 0,
                                    adx=sd.adx if hasattr(sd, 'adx') else 0,
                                    rvol=sd.rvol if hasattr(sd, 'rvol') else 0,
                                    consensus=sd.consensus if hasattr(sd, 'consensus') else 0,
                                    confidence=sd.confidence if hasattr(sd, 'confidence') else 0,
                                    quality=sd.quality if hasattr(sd, 'quality') else 0,
                                    entry_score=sd.entry_score if hasattr(sd, 'entry_score') else 0,
                                )
                            except Exception as e:
                                log.warning("TradeAnalytics: record_entry error: %s", e)
                            trading_data = {
                                "symbol": best_sd.symbol if hasattr(best_sd, 'symbol') else sd.symbol,
                                "timeframe": best_sd.timeframe if hasattr(best_sd, 'timeframe') else data.get("timeframe", ""),
                                "direction": best_sd.direction if hasattr(best_sd, 'direction') else sd.direction,
                                "entry_price": best_sd.entry_price if hasattr(best_sd, 'entry_price') else sd.entry_price,
                                "stop_loss": best_sd.stop_loss if hasattr(best_sd, 'stop_loss') else sd.stop_loss,
                                "take_profit_1": best_sd.take_profit_1 if hasattr(best_sd, 'take_profit_1') else sd.take_profit_1,
                                "take_profit_2": best_sd.take_profit_2 if hasattr(best_sd, 'take_profit_2') else 0,
                                "quality_score": best_sd.quality if hasattr(best_sd, 'quality') else sd.quality,
                                "confidence_score": best_sd.confidence if hasattr(best_sd, 'confidence') else 0,
                                "overall_score_value": data.get("overall_score_value", 0),
                                "consensus_score": best_sd.consensus if hasattr(best_sd, 'consensus') else 0,
                                "conviction_level": data.get("conviction_level", ""),
                                "expectancy_level": data.get("expectancy_level", ""),
                                "trend": best_sd.trend if hasattr(best_sd, 'trend') else "",
                                "kalman_direction": best_sd.kalman_direction if hasattr(best_sd, 'kalman_direction') else "",
                                "classification_label": best_sd.classification_label if hasattr(best_sd, 'classification_label') else "",
                                "risk_reward": best_sd.risk_reward if hasattr(best_sd, 'risk_reward') else sd.risk_reward,
                                "cycle_id": self._scan_count,
                                "signal_id": trade.signal_id,
                                "penalty_reasons": data.get("penalty_reasons", []),
                                "confluence_score": data.get("confluence_score", 0),
                                "risk_decomposition": data.get("risk_decomposition", {}),
                                "main_reason": data.get("main_reason", ""),
                                "mtf_conflict": data.get("mtf_conflict", False),
                                "probability": data.get("probability", {}),
                                "coherence_audit": data.get("coherence_audit", {}),
                                "final_validation_warnings": data.get("final_validation_warnings", []),
                                "quantity": data.get("quantity", 0),
                                "balance": data.get("balance", 0),
                                "leverage": data.get("leverage", 1),
                            }
                            try:
                                self._trade_registry.open_trade(trading_data)
                            except Exception as e:
                                log.warning("TradeRegistry: open_trade error: %s", e)
                            self._publisher.trade_opened({
                                "pair": trade.pair, "direction": trade.direction,
                                "entry_price": trade.entry_price, "stop_loss": trade.stop_loss,
                                "take_profit": trade.take_profit, "signal_id": trade.signal_id,
                                "status": "OPEN",
                            })
        else:
            self._decision_diag.record_filter_rejection(
                filter_name="Sem Sinal", asset=pair,
                details="Scanner nao gerou sinais para este ativo",
            )
            self._decision_diag.increment_rejected()
            self._rejection_analytics.record_rejection(
                gate="Sem Sinal", symbol=pair,
                timeframe="",
                direction="",
                found_value=0.0, expected_value=0.0,
                reject_reason="Scanner nao gerou sinais para este ativo",
            )
            self._diag.record_structure(pair, {
                "trend": str(market_ctx.trend.value) if hasattr(market_ctx.trend, "value") else str(market_ctx.trend),
                "strength": market_ctx.trend_strength,
                "bos": 0, "choch": 0,
            })
            self._diag.record_entry_zone(pair, zone_type="none", score=0, approved=False)
            self._diag.record_consensus(pair, {
                "consensus_score": 0, "classification": "Sem dados", "votes": [],
            })
            motivo_primario, motivos_secundarios, decisao_final = _resumir_motivos_sem_sinal(report.signals)
            self._diag.record_final_decision(
                pair=pair, status="REJECTED",
                primary_reason=motivo_primario,
                final_decision=decisao_final,
                secondary_reasons=motivos_secundarios,
            )


def main():
    provider = create_provider()
    app = QuantOSApp(provider)
    try:
        app.start()
    except KeyboardInterrupt:
        app.stop()

if __name__ == "__main__":
    main()
