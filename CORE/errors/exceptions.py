"""
Exceções padronizadas do QuantOS.

Hierarquia:
    QuantOSError
    ├── ConfigurationError
    ├── EngineError
    │   └── ScannerError
    ├── ValidationError
    ├── BaselineError
    └── InterfaceError
"""

from typing import Optional


class QuantOSError(Exception):
    """Erro base do sistema QuantOS.

    Attributes:
        message: Descrição do erro.
        code: Código de erro opcional (ex: CFG001).
    """

    def __init__(self, message: str, code: Optional[str] = None) -> None:
        self.code = code
        super().__init__(message)

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.args[0]}"
        return str(self.args[0])


class ConfigurationError(QuantOSError):
    """Erro relacionado a configuração do sistema."""
    pass


class EngineError(QuantOSError):
    """Erro no motor de processamento."""
    pass


class ScannerError(EngineError):
    """Erro no scanner de mercado."""
    pass


class ValidationError(QuantOSError):
    """Erro de validação de dados ou parâmetros."""
    pass


class BaselineError(QuantOSError):
    """Erro relacionado a operações com baselines."""
    pass


class InterfaceError(QuantOSError):
    """Erro de contrato de interface entre módulos."""
    pass
