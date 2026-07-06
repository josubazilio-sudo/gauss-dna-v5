"""
Validadores de entrada para o sistema de erros.
"""

from typing import Any, Optional


_ERROR_CODE_LENGTH = 6


def validate_error_code(code: str) -> bool:
    """Valida se o código de erro segue o formato oficial (XXXNNN).

    Args:
        code: Código de erro no formato 'XXXNNN' (3 letras + 3 dígitos).

    Returns:
        True se o código é válido.
    """
    if not isinstance(code, str):
        return False
    if len(code) != _ERROR_CODE_LENGTH:
        return False
    category = code[:3]
    number = code[3:]
    return category.isalpha() and category.isupper() and number.isdigit()


def validate_module_name(name: Any) -> bool:
    """Valida se o nome de módulo é uma string não vazia.

    Args:
        name: Nome do módulo.

    Returns:
        True se o nome é válido.
    """
    return isinstance(name, str) and len(name.strip()) > 0


def validate_context(context: Any) -> bool:
    """Valida se o contexto de erro é um dicionário.

    Args:
        context: Contexto adicional do erro.

    Returns:
        True se o contexto é um dict.
    """
    return isinstance(context, dict)
