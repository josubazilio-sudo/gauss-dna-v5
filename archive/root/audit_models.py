from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
from datetime import datetime

@dataclass
class AuditResult:
    # Versões para compatibilidade
    schema_version: str = "1.0"
    engine_version: str = "V6.1"
    
    # Identificação
    cycle_id: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    ativo: str = "UNKNOWN"
    timeframe: str = "1h"
    direcao: str = "NEUTRAL"
    
    # Decisão
    aprovado: bool = False
    motivo_principal: str = ""
    lista_de_bloqueadores: List[str] = field(default_factory=list)
    
    # Dados Estruturados
    filtros_avaliados: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Métricas de Performance
    quality: float = 0.0
    confidence: float = 0.0
    risk: float = 0.0
    consensus: float = 0.0
    entry_score: float = 0.0
    institutional_score: float = 0.0
    structural_score: float = 0.0
    lateral_market_score: float = 0.0
    
    def validate(self):
        """Auditoria automática de integridade do objeto."""
        # Verificar se campos essenciais não são None (mesmo se padrão for setado)
        if self.ativo is None or self.cycle_id is None:
             raise ValueError("Campos essenciais inválidos")
        return True

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Reconstrução segura do objeto."""
        return cls(**data)
