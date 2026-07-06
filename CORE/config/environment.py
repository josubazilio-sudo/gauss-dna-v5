"""
Gerenciamento de ambiente.

Define ambiente atual (dev, staging, production)
e carrega variáveis de ambiente.
"""

import os
from enum import Enum


class EnvironmentType(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Environment:
    def __init__(self):
        self._type = EnvironmentType(
            os.getenv("QUANTOS_ENV", "development")
        )

    @property
    def type(self) -> EnvironmentType:
        return self._type

    def is_development(self) -> bool:
        return self._type == EnvironmentType.DEVELOPMENT

    def is_production(self) -> bool:
        return self._type == EnvironmentType.PRODUCTION
