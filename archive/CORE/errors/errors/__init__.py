"""
Sistema padronizado de erros do QuantOS.

Fornece exceções, códigos, handlers e recuperação.
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
from .error_codes import ErrorCodes
from .handlers import setup_global_handlers, global_exception_handler
from .recovery import Recovery
from .validators import validate_error_code, validate_module_name, validate_context

__all__ = [
    "QuantOSError",
    "ConfigurationError",
    "EngineError",
    "ScannerError",
    "ValidationError",
    "BaselineError",
    "InterfaceError",
    "ErrorCodes",
    "setup_global_handlers",
    "global_exception_handler",
    "Recovery",
    "validate_error_code",
    "validate_module_name",
    "validate_context",
]
