"""
Função helper para obter logger.

Em vez de usar um singleton, cada módulo cria seu próprio logger
via logging.getLogger(__name__). Este arquivo existe apenas como
atalho de compatibilidade com código legado.

Uso preferencial (em todos os módulos novos):
    import logging
    log = logging.getLogger(__name__)
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado.

    Args:
        name: Nome do logger (normalmente __name__ do módulo).

    Returns:
        logging.Logger configurado com o sistema QuantOS.
    """
    return logging.getLogger(name)
