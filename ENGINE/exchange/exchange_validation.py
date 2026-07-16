"""RFC V18.5 — Exchange Validation Gate (MEXC Futures).

QuantOS descobre o universo de simbolos via CORE/data_providers/mexc_provider.py,
que usa exclusivamente a API de SPOT da MEXC (/api/v3/exchangeInfo). Isso
gerava sinais para pares que existem no spot mas nao tem contrato futuro
correspondente (ex.: ACNONUSDT, ATTONUSDT) — sinais impossiveis de operar,
ja que o restante do pipeline (leverage, margem, liquidacao) assume futuros.

Este modulo consulta a API oficial de Futuros da MEXC
(https://contract.mexc.com/api/v1/contract/detail) e mantem o conjunto de
simbolos realmente negociaveis como contrato perpetuo, com cache de 60min.
"""
import logging
import time
from threading import Lock
from typing import Optional, Set

import requests

log = logging.getLogger(__name__)

FUTURES_CONTRACT_URL = "https://contract.mexc.com/api/v1/contract/detail"
REFRESH_INTERVAL_SECONDS = 3600  # RFC V18.5: atualizar a cada 60 minutos
REQUEST_TIMEOUT_SECONDS = 15


class ExchangeValidation:
    """Fonte unica de verdade sobre quais simbolos existem como contrato
    perpetuo negociavel na MEXC Futures — usado para rejeitar, antes do
    Consensus, qualquer simbolo que nao exista de fato na exchange."""

    def __init__(
        self,
        contract_url: str = FUTURES_CONTRACT_URL,
        refresh_interval: float = REFRESH_INTERVAL_SECONDS,
        session: Optional[requests.Session] = None,
    ):
        self._contract_url = contract_url
        self._refresh_interval = refresh_interval
        self._session = session or requests.Session()
        self._lock = Lock()
        self._valid_symbols: Set[str] = set()
        self._last_refresh: float = 0.0
        self._last_rejected: Set[str] = set()
        self.refresh(force=True)

    @staticmethod
    def _normalize(symbol: str) -> str:
        return symbol.upper().replace("_", "").strip()

    def refresh(self, force: bool = False) -> None:
        with self._lock:
            if not force and (time.time() - self._last_refresh) < self._refresh_interval:
                return
            try:
                resp = self._session.get(self._contract_url, timeout=REQUEST_TIMEOUT_SECONDS)
                resp.raise_for_status()
                payload = resp.json()
                contracts = payload.get("data", []) if payload.get("success") else []
                loaded = {
                    self._normalize(c["symbol"])
                    for c in contracts
                    if c.get("apiAllowed", True) and c.get("symbol")
                }
                if not loaded:
                    raise ValueError("resposta da API sem contratos validos")
                self._valid_symbols = loaded
                self._last_refresh = time.time()
                log.info(
                    "[Exchange Validation] Loaded Futures Contracts: %d",
                    len(self._valid_symbols),
                )
            except Exception as e:
                # RFC V18.5: fail-safe deliberado — uma falha de rede na
                # API de futuros nunca deve zerar o universo de simbolos
                # (isso bloquearia TODOS os sinais, pior do que deixar
                # passar um simbolo invalido ocasional ate o proximo
                # refresh). Mantem o ultimo conjunto valido conhecido; se
                # nunca houve um, falha aberto (aceita tudo) com log
                # critico, ate o proximo refresh bem-sucedido.
                if self._valid_symbols:
                    log.warning(
                        "[Exchange Validation] Falha ao atualizar contratos futuros (%s). "
                        "Mantendo ultima lista valida (%d simbolos).",
                        e, len(self._valid_symbols),
                    )
                else:
                    log.critical(
                        "[Exchange Validation] Falha ao carregar contratos futuros (%s) "
                        "e nenhuma lista anterior disponivel — falhando aberto "
                        "(todos os simbolos temporariamente aceitos) ate o proximo refresh.",
                        e,
                    )

    def is_valid_symbol(self, symbol: str) -> bool:
        self.refresh()
        with self._lock:
            if not self._valid_symbols:
                return True  # fail-open: nenhuma lista carregada ainda
            return self._normalize(symbol) in self._valid_symbols

    def filter_valid(self, symbols) -> Set[str]:
        """Retorna o subconjunto de `symbols` que sao contratos futuros
        validos, e registra os rejeitados para diagnostico/relatorio."""
        self.refresh()
        with self._lock:
            if not self._valid_symbols:
                self._last_rejected = set()
                return set(symbols)
            approved = {s for s in symbols if self._normalize(s) in self._valid_symbols}
            rejected = {s for s in symbols if self._normalize(s) not in self._valid_symbols}
            self._last_rejected = rejected
        if rejected:
            log.info(
                "[Exchange Validation] Aprovados: %d | Rejeitados: %d | Motivos: %s",
                len(approved), len(rejected), ", ".join(sorted(rejected)[:20]) +
                (f" (+{len(rejected) - 20} outros)" if len(rejected) > 20 else ""),
            )
            for sym in sorted(rejected):
                log.info("[Exchange Validation] %s -> INVALID_SYMBOL -> REJECTED", sym)
        return approved

    @property
    def loaded_count(self) -> int:
        return len(self._valid_symbols)

    @property
    def last_rejected(self) -> Set[str]:
        return set(self._last_rejected)
