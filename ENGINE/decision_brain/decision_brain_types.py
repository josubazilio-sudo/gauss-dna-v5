from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# Fonte unica dos pesos padrao de julgamento — usado por DecisionBrain e
# por judgment.py. Nao duplicar este dicionario em outro lugar.
PESOS_PADRAO = {
    "tese_score": 0.60,
    "contra_tese_score": 0.40,
    "conviccao_min": 0.50,
    "probabilidade_base": 0.50,
}


class DecisionState(Enum):
    REJEITADO = "rejeitado"
    OBSERVACAO = "observacao"
    PRONTO = "pronto"
    EXECUTAR = "executar"


class RegimeType(Enum):
    TENDENCIA_FORTE = "tendencia_forte"
    TENDENCIA = "tendencia"
    TRANSICAO = "transicao"
    LATERAL = "lateral"


class KalmanState(Enum):
    UP = "UP"
    DOWN = "DOWN"
    SIDE = "SIDE"
    ERRO = "ERRO"


@dataclass
class ThesisFactor:
    nome: str
    valor: float
    justificativa: str
    peso: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {"nome": self.nome, "valor": self.valor, "justificativa": self.justificativa, "peso": self.peso}


@dataclass
class OperationalThesis:
    contexto_macro: str
    regime: str
    tendencia: ThesisFactor
    fluxo_institucional: ThesisFactor
    estrutura: ThesisFactor
    liquidez: ThesisFactor
    momentum: ThesisFactor
    volatilidade: ThesisFactor
    timing: ThesisFactor
    risco: ThesisFactor
    multi_timeframe: str
    expectativa_continuidade: ThesisFactor
    score_total: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contexto_macro": self.contexto_macro,
            "regime": self.regime,
            "tendencia": self.tendencia.to_dict(),
            "fluxo_institucional": self.fluxo_institucional.to_dict(),
            "estrutura": self.estrutura.to_dict(),
            "liquidez": self.liquidez.to_dict(),
            "momentum": self.momentum.to_dict(),
            "volatilidade": self.volatilidade.to_dict(),
            "timing": self.timing.to_dict(),
            "risco": self.risco.to_dict(),
            "multi_timeframe": self.multi_timeframe,
            "expectativa_continuidade": self.expectativa_continuidade.to_dict(),
            "score_total": self.score_total,
        }


@dataclass
class CounterThesisFactor:
    nome: str
    ativo: bool
    peso: float
    justificativa: str

    def to_dict(self) -> Dict[str, Any]:
        return {"nome": self.nome, "ativo": self.ativo, "peso": self.peso, "justificativa": self.justificativa}


@dataclass
class CounterThesis:
    fatores: List[CounterThesisFactor] = field(default_factory=list)
    score_contra: float = 0.0
    peso_total: float = 0.0

    def adicionar(self, nome: str, ativo: bool, peso: float, justificativa: str):
        self.fatores.append(CounterThesisFactor(nome=nome, ativo=ativo, peso=peso, justificativa=justificativa))

    def calcular_score(self) -> float:
        if not self.fatores:
            self.score_contra = 0.0
            self.peso_total = 0.0
            return 0.0
        ativos = [f for f in self.fatores if f.ativo]
        if not ativos:
            self.score_contra = 0.0
            return 0.0
        total = sum(f.peso * 1.0 for f in ativos)
        max_possivel = sum(f.peso for f in self.fatores)
        self.peso_total = max_possivel
        self.score_contra = total / max_possivel if max_possivel > 0 else 0.0
        return self.score_contra

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fatores": [f.to_dict() for f in self.fatores],
            "score_contra": self.score_contra,
            "peso_total": self.peso_total,
        }


@dataclass
class Judgment:
    probabilidade: float
    conviccao: float
    risco: float
    expectancy: float
    recomendacao: DecisionState
    justificativa: str
    tese: Optional[OperationalThesis] = None
    contra_tese: Optional[CounterThesis] = None
    trace_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probabilidade": self.probabilidade,
            "conviccao": self.conviccao,
            "risco": self.risco,
            "expectancy": self.expectancy,
            "recomendacao": self.recomendacao.value,
            "justificativa": self.justificativa,
            "tese": self.tese.to_dict() if self.tese else None,
            "contra_tese": self.contra_tese.to_dict() if self.contra_tese else None,
            "trace_id": self.trace_id,
        }


@dataclass
class DecisionBrainRecord:
    trace_id: str
    symbol: str
    timeframe: str
    direction: str
    tese: OperationalThesis
    contra_tese: CounterThesis
    judgment: Judgment
    pesos_utilizados: Dict[str, float]
    motivos: List[str]
    estado: DecisionState
    justificativa_final: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    engine_version: str = "11.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "tese": self.tese.to_dict(),
            "contra_tese": self.contra_tese.to_dict(),
            "judgment": self.judgment.to_dict(),
            "pesos_utilizados": self.pesos_utilizados,
            "motivos": self.motivos,
            "estado": self.estado.value,
            "justificativa_final": self.justificativa_final,
            "timestamp": self.timestamp.isoformat(),
            "engine_version": self.engine_version,
        }
