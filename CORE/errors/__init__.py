"""
Sistema minimo de erros do QuantOS.

Restaurado parcialmente em 2026-07-11: apenas exceptions e handlers,
que sao os unicos usados por CORE/bootstrap/startup.py. error_codes,
recovery e validators permanecem em archive/CORE/errors/ por nao
terem nenhum importador no caminho vivo do main.py.
"""

from .exceptions import (
    QuantOSError,
    ConfigurationError,
    EngineError,
    ScannerError,
    ValidationError,
    BaselineError,
    InterfaceError,
)
from .handlers import setup_global_handlers, global_exception_handler

__all__ = [
    "QuantOSError",
    "ConfigurationError",
    "EngineError",
    "ScannerError",
    "ValidationError",
    "BaselineError",
    "InterfaceError",
    "setup_global_handlers",
    "global_exception_handler",
]
