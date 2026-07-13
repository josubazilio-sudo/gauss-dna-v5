import json
from ENGINE.common.paths import (
    TRADE_HISTORY_PATH, EVIDENCE_DIR, PAPER_TRADING_PATH,
    WEIGHTS_V7_PATH, LEARNING_DATA_PATH, METRICS_PATH
)
from ENGINE.scanner.scanner_config import LEARNING_MIN_SAMPLES, LEARNING_MIN_SAMPLES_PER_CLASSIFICATION
import os
import logging
from typing import List, Dict, Any

log = logging.getLogger(__name__)

class AutoCalibrationEngine:
    def __init__(self,
                 evidence_dir: str = str(EVIDENCE_DIR),
                 paper_trading_path: str = str(PAPER_TRADING_PATH),
                 weights_path: str = str(WEIGHTS_V7_PATH)):
        self.evidence_dir = evidence_dir
        self.paper_trading_path = paper_trading_path
        self.weights_path = weights_path
        
    def load_evidence(self) -> Dict[str, Dict[str, Any]]:
        evidence = {}
        if not os.path.exists(self.evidence_dir):
            return evidence
        for filename in os.listdir(self.evidence_dir):
            if filename.endswith(".json"):
                with open(os.path.join(self.evidence_dir, filename), "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        trace_id = data.get("decision", {}).get("trace_id")
                        if trace_id:
                            evidence[trace_id] = data
                    except Exception as e:
                        log.error(f"Error loading {filename}: {e}")
        return evidence

    def load_closed_trades(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.paper_trading_path):
            return []
        try:
            with open(self.paper_trading_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("closed_trades", [])
        except Exception as e:
            log.error(f"Error loading closed trades: {e}")
            return []

    def calibrate(self, force_mock: bool = False, approve: bool = False) -> str:
        trades = self.load_closed_trades()
        evidence_db = self.load_evidence()

        # V19.0: autoaprendizado apenas via Paper Trading, com amostragem minima
        if not force_mock and len(trades) < LEARNING_MIN_SAMPLES:
            return (
                f"Autoaprendizado: amostragem insuficiente.\n"
                f"Trades fechados: {len(trades)}/{LEARNING_MIN_SAMPLES}. "
                f"Minimo exigido: {LEARNING_MIN_SAMPLES} trades.\n"
                f"Fontes permitidas: Paper Trading apenas.\n"
                f"Evidencias registradas: {len(evidence_db)}."
            )

        # Verificar amostragem minima por classificacao
        if not force_mock:
            from collections import Counter
            classifications = Counter(t.get("setup", "unknown") for t in trades)
            for cls, count in classifications.most_common():
                if count < LEARNING_MIN_SAMPLES_PER_CLASSIFICATION and cls != "unknown":
                    log.info(
                        f"Autoaprendizado: classificacao {cls} tem {count} amostras "
                        f"(minimo {LEARNING_MIN_SAMPLES_PER_CLASSIFICATION}). "
                        "Resultados podem nao ser estatisticamente significativos."
                    )

        if force_mock:
            trades = self._generate_mock_trades()
            for t in trades:
                trace_id = t["id"]
                evidence_db[trace_id] = {
                    "decision": {
                        "trace_id": trace_id,
                        "symbol": t["pair"],
                        "timeframe": "1h",
                        "approved": True,
                        "quality": t["quality"],
                        "confidence": 0.6,
                        "institutional_score": 0.7,
                        "structural_score": 0.5,
                        "market_score": 0.6,
                        "liquidity_score": 0.8,
                        "consensus": 0.7,
                        "entry_score": 0.5,
                        "lateral_market_score": 0.2
                    }
                }

        # Analisar correlações de pesos
        # Queremos correlacionar os scores de entrada de cada trade com o PnL obtido
        feature_pnl_corr = {
            "quality": 0.0,
            "confidence": 0.0,
            "institutional_score": 0.0,
            "structural_score": 0.0,
            "market_score": 0.0,
            "liquidity_score": 0.0,
            "consensus": 0.0,
            "entry_score": 0.0,
            "lateral_market_score": 0.0
        }
        
        valid_samples = 0
        for t in trades:
            trace_id = t.get("id") or t.get("signal_id")
            pnl = t.get("pnl", 0.0)
            
            ev = evidence_db.get(trace_id)
            if not ev:
                continue
            
            dec = ev.get("decision", {})
            valid_samples += 1
            
            # Simple correlation logic: if PnL is positive, score gets +1 if high, -1 if low
            for feature in feature_pnl_corr.keys():
                val = dec.get(feature, 0.5)
                # Normalize val to 0.0 - 1.0 if needed
                if pnl > 0:
                    feature_pnl_corr[feature] += (val - 0.5)
                else:
                    feature_pnl_corr[feature] -= (val - 0.5)

        if valid_samples == 0:
            return "Nenhuma correspondência encontrada entre os trades fechados e o banco de evidências."

        # Média das correlações
        for f in feature_pnl_corr:
            feature_pnl_corr[f] /= valid_samples

        # Ler pesos atuais ou criar padrão
        current_weights = self._load_current_weights()
        
        # Ajuste inteligente e gradual dos pesos (Regra de Segurança: máximo de 0.02 de variação por ciclo)
        MAX_ADJUSTMENT = 0.02
        new_weights = json.loads(json.dumps(current_weights)) # Deep copy
        
        report = []
        report.append("==========================================")
        report.append("  QUANTOS V7.0 — RELATÓRIO DE AUTO-CALIBRAÇÃO")
        report.append("==========================================")
        report.append(f"Amostra Analisada: {valid_samples} trades válidos.")
        report.append("\nCorrelação de Indicadores (Scores vs PnL):")
        for f, corr in feature_pnl_corr.items():
            report.append(f"  - {f:<22}: {corr:+.4f}")

        report.append("\nAjustes Efetuados nos Pesos de Qualidade:")
        
        # Ajustar pesos da categoria 'quality_score'
        for f in new_weights["quality_score"]:
            corr_key = f
            if f == "structural": corr_key = "structural_score"
            elif f == "market": corr_key = "market_score"
            elif f == "liquidity": corr_key = "liquidity_score"
            elif f == "institutional": corr_key = "institutional_score"
            
            corr = feature_pnl_corr.get(corr_key, 0.0)
            adjustment = corr * 0.1 # Fator de aprendizado conservador
            adjustment = max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, adjustment))
            
            old_w = new_weights["quality_score"][f]
            new_weights["quality_score"][f] = round(max(0.05, old_w + adjustment), 4)
            report.append(f"  - {f:<15}: {old_w:.4f} -> {new_weights['quality_score'][f]:.4f} (Corr: {corr:+.4f})")

        # Normalizar pesos para somar 1.0
        total_w = sum(new_weights["quality_score"].values())
        for f in new_weights["quality_score"]:
            new_weights["quality_score"][f] = round(new_weights["quality_score"][f] / total_w, 4)

        # Salvar nova versao dos pesos — SOMENTE com aprovacao explicita.
        # Alterar pesos de estrategia de trading em producao sem RFC/aprovacao
        # e proibido pelo processo oficial do QuantOS (CLAUDE.md).
        if approve:
            self._save_weights(new_weights)
        else:
            pending_path = os.path.join(os.path.dirname(self.weights_path), "weights_v7_pending.json")
            with open(pending_path, "w", encoding="utf-8") as f:
                json.dump(new_weights, f, indent=4)

        report.append("\nPesos Normalizados Finais (Quality Score):")
        for f, w in new_weights["quality_score"].items():
            report.append(f"  - {f:<15}: {w:.4f}")

        if approve:
            report.append("\n[OK] Nova versao de calibracao gerada e APLICADA (approve=True).")
        else:
            report.append(
                "\n[PENDENTE] Calibracao calculada mas NAO aplicada — requer aprovacao manual. "
                f"Revise e chame calibrate(approve=True) para gravar em {self.weights_path}. "
                f"Proposta salva em weights_v7_pending.json."
            )
        report.append("==========================================")
        
        # Gravar relatório Markdown em MEMORY/audit/
        os.makedirs(os.path.dirname(self.weights_path), exist_ok=True)
        report_path = os.path.join(os.path.dirname(self.weights_path), "calibration_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report))
            
        return "\n".join(report)

    def _load_current_weights(self) -> Dict[str, Any]:
        if os.path.exists(self.weights_path):
            try:
                with open(self.weights_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # Default de fábrica
        return {
            'institutional': {'structural': 0.2, 'market': 0.2, 'momentum': 0.2, 'liquidity': 0.15, 'risk': 0.15, 'confidence': 0.1},
            'quality_score': {'institutional': 0.3, 'structural': 0.2, 'market': 0.1, 'momentum': 0.1, 'liquidity': 0.1, 'risk': 0.1, 'confidence': 0.1}
        }

    def _save_weights(self, weights: Dict[str, Any]):
        with open(self.weights_path, "w", encoding="utf-8") as f:
            json.dump(weights, f, indent=4)

    def _generate_mock_trades(self) -> List[Dict[str, Any]]:
        import random
        trades = []
        for i in range(300):
            is_win = random.random() > 0.4 # 60% win rate
            quality = random.uniform(0.5, 0.95) if is_win else random.uniform(0.3, 0.7)
            pnl = random.uniform(10, 50) if is_win else -random.uniform(10, 25)
            trades.append({
                "id": f"mock_{i}",
                "pair": random.choice(["BTCUSDT", "ETHUSDT", "SOLUSDT"]),
                "direction": random.choice(["LONG", "SHORT"]),
                "pnl": pnl,
                "status": "WIN" if is_win else "LOSS",
                "quality": quality
            })
        return trades
