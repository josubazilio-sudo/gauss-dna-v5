import logging

logger = logging.getLogger('QuantOS.CORE.utils.TimeframeManager')

class TimeframeManager:
    ALLOWED_TIMEFRAMES = {'30m', '1h', '4h', '1d'}
    
    @classmethod
    def is_valid(cls, timeframe: str) -> bool:
        if timeframe in cls.ALLOWED_TIMEFRAMES:
            return True
        cls._log_invalid_access(timeframe)
        return False
    
    @classmethod
    def _log_invalid_access(cls, timeframe: str):
        logger.warning(f'[INSTITUTIONAL_ALERT] Tentativa de acesso a timeframe nao permitido ou depreciado: {timeframe}')
        
    @classmethod
    def get_allowed(cls) -> list:
        return sorted(list(cls.ALLOWED_TIMEFRAMES))
