import logging
from typing import Optional

from .base import IDataProvider, TIMEFRAMES_MINUTES, DEFAULT_CANDLE_COUNTS
from .config import DEBUG_MODE, log_environment_banner
from .mock import MockDataProvider
from .historical import HistoricalDataProvider

log = logging.getLogger(__name__)


def create_provider(
    provider_type: Optional[str] = None,
    api_key: str = "",
    api_secret: str = "",
    data_dir: Optional[str] = None,
    mock_seed: Optional[int] = None,
) -> IDataProvider:
    if provider_type is None:
        if DEBUG_MODE:
            provider = MockDataProvider(seed=mock_seed)
            log_environment_banner("MockDataProvider")
            return provider
        provider_type = "mexc"

    pt = provider_type.lower()

    if pt == "mock":
        provider = MockDataProvider(seed=mock_seed)
        log_environment_banner("MockDataProvider")
        return provider

    if pt == "historical":
        provider = HistoricalDataProvider(data_dir=data_dir)
        log_environment_banner("HistoricalDataProvider")
        return provider

    if pt == "mexc":
        from .mexc_provider import MexcDataProvider
        provider = MexcDataProvider(api_key=api_key, api_secret=api_secret)
        log_environment_banner("MexcDataProvider")
        return provider

    if pt == "binance":
        from .binance_provider import BinanceDataProvider
        provider = BinanceDataProvider(api_key=api_key, api_secret=api_secret)
        log_environment_banner("BinanceDataProvider")
        return provider

    log.warning("Unknown provider '%s', falling back to Mock", provider_type)
    provider = MockDataProvider(seed=mock_seed)
    log_environment_banner("MockDataProvider (fallback)")
    return provider


__all__ = [
    "IDataProvider",
    "MockDataProvider",
    "HistoricalDataProvider",
    "MexcDataProvider",
    "BinanceDataProvider",
    "create_provider",
    "TIMEFRAMES_MINUTES",
    "DEFAULT_CANDLE_COUNTS",
    "DEBUG_MODE",
]
