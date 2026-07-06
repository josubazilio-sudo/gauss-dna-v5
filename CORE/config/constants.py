"""
Constantes do sistema.

Valores fixos utilizados por todos os módulos.
"""


class Constants:
    PROJECT_NAME = "QuantOS"
    VERSION = "1.0.0"
    DEFAULT_CONFIG_PATH = "config.json"
    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    class Metrics:
        MIN_PROFIT_FACTOR = 2.50
        MIN_WIN_RATE = 60.0
        MAX_DRAWDOWN = 10.0

    class Paths:
        BASELINES = "baselines"
        MEMORY = "memory"
        REPORTS = "reports"
        CONFIG = "configs"
