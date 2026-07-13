import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ENGINE.scanner.scanner_types import Signal, ScannerScore, SignalDirection
from ENGINE.indicators.kalman import kalman_direction, kalman_confidence
from ENGINE.market.market_types import Candle

from .decision_brain_types import (
    DecisionBrainRecord, DecisionState, Judgment,
    OperationalThesis, CounterThesis, PESOS_PADRAO,
)
from .thesis_builder import build_thesis
from .counter_thesis import build_counter_thesis
from .judgment import make_judgment

log = logging.getLogger(__name__)


class DecisionBrain:
    PESOS_PADRAO = PESOS_PADRAO
    MAX_HISTORICO = 2000

    def __init__(self, pesos_iniciais: Optional[Dict[str, float]] = None):
        self._historico: List[DecisionBrainRecord] = []
        self._version = "11.0.0"
        self._pesos = dict(pesos_iniciais or self.PESOS_PADRAO)
        self._ajustes: List[Dict[str, Any]] = []

    def evaluate(
        self,
        signal: Signal,
        candles: Optional[List[Candle]] = None,
        rsi: float = 50.0,
        adx: float = 0.0,
        atr_percent: float = 0.0,
        rvol: float = 0.0,
        vwap_distance: float = 0.0,
    ) -> DecisionBrainRecord:
        scores = signal.scores

        closes = [c.close for c in candles] if candles else []
        kalman_dir = kalman_direction(closes) if closes else "ERRO"
        kalman_conf = kalman_confidence(closes) if closes else 0.0

        if kalman_dir == "ERRO":
            log.warning("DecisionBrain: Kalman ERRO para %s %s", signal.ticker, signal.timeframe)

        tese = build_thesis(signal, scores, kalman_dir, kalman_conf)

        contra_tese = build_counter_thesis(
            signal=signal, scores=scores,
            kalman_dir=kalman_dir,
            rsi=rsi, adx=adx, atr_percent=atr_percent,
            rvol=rvol, vwap_distance=vwap_distance,
        )

        judgment = make_judgment(tese, contra_tese, signal, pesos_override=self._pesos)

        trace_id = signal.signal_id or str(uuid.uuid4())[:12]

        pesos_utilizados = {
            "tese_score": getattr(judgment, 'probabilidade', 0),
            "contra_tese_score": contra_tese.score_contra,
            "conviccao": judgment.conviccao,
            "risco": judgment.risco,
        }

        motivos = []
        if judgment.recomendacao == DecisionState.EXECUTAR:
            motivos.append("Tese superior a contra-tese")
            motivos.append("Risco controlado")
            motivos.append("Alta probabilidade e conviccao")
        elif judgment.recomendacao == DecisionState.PRONTO:
            motivos.append("Potencial identificado, aguardar confirmacao")
        elif judgment.recomendacao == DecisionState.OBSERVACAO:
            motivos.append("Riscos ou contra-teses significativos")
        else:
            motivos.append("Contra-tese superior a tese")

        record = DecisionBrainRecord(
            trace_id=trace_id,
            symbol=signal.ticker,
            timeframe=signal.timeframe,
            direction=signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction),
            tese=tese,
            contra_tese=contra_tese,
            judgment=judgment,
            pesos_utilizados=pesos_utilizados,
            motivos=motivos,
            estado=judgment.recomendacao,
            justificativa_final=judgment.justificativa,
            engine_version=self._version,
        )

        self._historico.append(record)
        if len(self._historico) > self.MAX_HISTORICO:
            self._historico = self._historico[-self.MAX_HISTORICO:]
        log.info(
            "DecisionBrain[%s] %s %s %s | prob=%.2f conv=%.2f risco=%.2f estado=%s",
            trace_id, signal.ticker, signal.timeframe,
            signal.direction.value if hasattr(signal.direction, 'value') else signal.direction,
            judgment.probabilidade, judgment.conviccao, judgment.risco,
            judgment.recomendacao.value,
        )

        return record

    def update_weights(self, novos_pesos: Dict[str, float], motivo: str = "recalibracao_automatica") -> bool:
        peso_min = 0.30
        peso_max = 1.50
        ajustados = {}
        for chave, valor in novos_pesos.items():
            if chave not in self.PESOS_PADRAO:
                log.warning("DecisionBrain: peso desconhecido '%s' ignorado", chave)
                continue
            original = self._pesos.get(chave, self.PESOS_PADRAO[chave])
            delta_max = original * 0.20
            novo = max(original - delta_max, min(original + delta_max, valor))
            novo = max(peso_min, min(peso_max, novo))
            if abs(novo - original) > 0.001:
                ajustados[chave] = {"de": round(original, 4), "para": round(novo, 4)}
                self._pesos[chave] = novo

        if ajustados:
            registro = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "motivo": motivo,
                "ajustes": ajustados,
                "pesos_resultantes": dict(self._pesos),
            }
            self._ajustes.append(registro)
            log.info("DecisionBrain: pesos ajustados: %s", ajustados)
            return True
        return False

    def get_weights(self) -> Dict[str, float]:
        return dict(self._pesos)

    def get_ajustes(self) -> List[Dict[str, Any]]:
        return list(self._ajustes)

    def historico(self) -> List[DecisionBrainRecord]:
        return list(self._historico)

    def ultimo_registro(self) -> Optional[DecisionBrainRecord]:
        return self._historico[-1] if self._historico else None
