import enum
import logging
import os

log = logging.getLogger("QuantOS.CORE.execution.ModeManager")


class ExecutionMode(enum.Enum):
    DEVELOPMENT = "DEVELOPMENT"
    PAPER_TRADING = "PAPER_TRADING"
    LIVE = "LIVE"


class ExecutionModeManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            raw = os.environ.get("QUANTOS_MODE", "DEVELOPMENT").upper()
            self._mode = self._resolve(raw)
            self._initialized = True

    @staticmethod
    def _resolve(raw: str) -> ExecutionMode:
        for m in ExecutionMode:
            if m.value == raw:
                return m
        log.warning("Modo invalido '%s' — usando DEVELOPMENT como fallback", raw)
        return ExecutionMode.DEVELOPMENT

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @property
    def mode_name(self) -> str:
        return self._mode.value

    def is_development(self) -> bool:
        return self._mode == ExecutionMode.DEVELOPMENT

    def is_paper_trading(self) -> bool:
        return self._mode == ExecutionMode.PAPER_TRADING

    def is_live(self) -> bool:
        return self._mode == ExecutionMode.LIVE

    def should_authenticate(self) -> bool:
        return self._mode == ExecutionMode.LIVE

    def can_trade(self) -> bool:
        return self._mode == ExecutionMode.LIVE

    def should_validate_keys(self) -> bool:
        return self._mode == ExecutionMode.LIVE

    def require_connection(self) -> bool:
        return self._mode == ExecutionMode.LIVE

    def get_balance_default(self) -> float:
        return 10000.0 if not self.is_live() else 0.0

    def show_startup_banner(self, exchange_name: str = "MEXC") -> str:
        dev = self.is_development()
        paper = self.is_paper_trading()
        live = self.is_live()

        lines = [
            "=" * 40,
            "  QUANTOS STARTUP",
            "=" * 40,
            f"  Modo............{self._mode.value}",
            f"  Exchange.........{exchange_name}",
            f"  Trading..........{'HABILITADO' if live else 'DESABILITADO'}",
            f"  Authentication...{'OBRIGATORIA' if live else 'IGNORADA'}",
            f"  Scanner..........ATIVO",
            f"  Consensus........ATIVO",
            f"  Entry Zone.......ATIVA",
            f"  Quality Gate.....ATIVO",
            f"  Telegram.........ATIVO",
            f"  Auditoria........ATIVA",
            f"  Status...........{'ONLINE' if live else 'SANDBOX'}",
            "=" * 40,
        ]
        banner = "\n".join(lines)
        log.info("\n" + banner)
        return banner
