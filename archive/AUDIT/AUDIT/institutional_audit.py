import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

AUDIT_DIR = Path(__file__).parent / "data"


class InstitutionalAudit:
    HEADERS = [
        "timestamp", "pair", "timeframe", "direction",
        "entry_price", "stop_loss", "take_profit_1", "take_profit_2",
        "atr", "adx", "volume", "rvol_value",
        "ema50", "ema200", "vwap",
        "bos", "choch", "liquidity_sweep", "order_block", "fvg",
        "market_structure", "structure_strength",
        "institutional_score", "structural_score", "confidence", "quality_score",
        "classification", "regime", "trend",
        "risk_reward", "mtf_trends",
        "decision", "rejection_reasons", "approval_reasons",
        "result", "trade_duration_h", "profit_loss_pct",
        "mae_pct", "mfe_pct",
        "thesis_summary", "counter_thesis_summary", "decision_state",
        "probabilidade", "conviccao", "risco", "justificativa_final",
        "tese_score", "contra_score", "engine_version",
    ]

    def __init__(self, base_dir: Optional[Path] = None):
        self._dir = Path(base_dir) if base_dir else AUDIT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._records: List[Dict[str, Any]] = []
        self._csv_path = self._dir / "audit_log.csv"
        self._json_path = self._dir / "audit_log.json"
        self._csv_initialized = False

    def record_signal(
        self,
        pair: str,
        timeframe: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float,
        atr: float,
        adx: float,
        volume: float,
        rvol_value: float,
        ema50: float,
        ema200: float,
        vwap: float,
        patterns: List[str],
        market_structure: str,
        structure_strength: float,
        institutional_score: float,
        structural_score: float,
        confidence: float,
        quality_score: float,
        classification: str,
        regime: str,
        trend: str,
        risk_reward: float,
        mtf_trends: Any,
        decision: str,
        rejection_reasons: Optional[List[str]] = None,
        approval_reasons: Optional[List[str]] = None,
    ) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pair": pair,
            "timeframe": timeframe,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit_1": take_profit_1,
            "take_profit_2": take_profit_2,
            "atr": atr,
            "adx": adx,
            "volume": volume,
            "rvol_value": rvol_value,
            "ema50": ema50,
            "ema200": ema200,
            "vwap": vwap,
            "bos": 1 if "bos" in patterns else 0,
            "choch": 1 if "choch" in patterns else 0,
            "liquidity_sweep": 1 if "liquidity_sweep" in patterns else 0,
            "order_block": 1 if "order_block" in patterns else 0,
            "fvg": 1 if "fvg" in patterns else 0,
            "market_structure": market_structure,
            "structure_strength": structure_strength,
            "institutional_score": institutional_score,
            "structural_score": structural_score,
            "confidence": confidence,
            "quality_score": quality_score,
            "classification": classification,
            "regime": regime,
            "trend": trend,
            "risk_reward": risk_reward,
            "mtf_trends": json.dumps(mtf_trends) if mtf_trends else "",
            "decision": decision,
            "rejection_reasons": "; ".join(rejection_reasons) if rejection_reasons else "",
            "approval_reasons": "; ".join(approval_reasons) if approval_reasons else "",
            "result": "",
            "trade_duration_h": "",
            "profit_loss_pct": "",
            "mae_pct": "",
            "mfe_pct": "",
        }
        self._records.append(record)

    def record_decision_brain(
        self,
        pair: str,
        timeframe: str,
        direction: str,
        entry_price: float,
        brain_record,
    ) -> None:
        tese = brain_record.tese
        ct = brain_record.contra_tese

        thesis_lines = []
        thesis_lines.append(f"score={tese.score_total:.2f}")
        thesis_lines.append(f"regime={tese.regime}")
        thesis_lines.append(f"contexto={tese.contexto_macro}")
        thesis_lines.append(f"tendencia={tese.tendencia.valor:.2f}")
        thesis_lines.append(f"fluxo={tese.fluxo_institucional.valor:.2f}")
        thesis_lines.append(f"estrutura={tese.estrutura.valor:.2f}")

        ct_lines = []
        ct_lines.append(f"score_contra={ct.score_contra:.2f}")
        for f in ct.fatores:
            if f.ativo:
                ct_lines.append(f"{f.nome}(peso={f.peso:.2f}): {f.justificativa}")

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pair": pair,
            "timeframe": timeframe,
            "direction": direction,
            "entry_price": entry_price,
            "thesis_summary": " | ".join(thesis_lines),
            "counter_thesis_summary": " | ".join(ct_lines),
            "decision_state": brain_record.estado.value,
            "probabilidade": brain_record.judgment.probabilidade if brain_record.judgment else 0.0,
            "conviccao": brain_record.judgment.conviccao if brain_record.judgment else 0.0,
            "risco": brain_record.judgment.risco if brain_record.judgment else 0.0,
            "justificativa_final": brain_record.justificativa_final,
            "tese_score": tese.score_total,
            "contra_score": ct.score_contra,
            "engine_version": brain_record.engine_version,
        }
        self._records.append(record)

    def update_result(
        self,
        pair: str,
        timeframe: str,
        direction: str,
        timestamp: str,
        result: str,
        trade_duration_h: float,
        profit_loss_pct: float,
        mae_pct: float,
        mfe_pct: float,
    ) -> None:
        for rec in reversed(self._records):
            if (rec["pair"] == pair and rec["timeframe"] == timeframe
                    and rec["direction"] == direction and rec["timestamp"] == timestamp):
                rec["result"] = result
                rec["trade_duration_h"] = round(trade_duration_h, 4)
                rec["profit_loss_pct"] = round(profit_loss_pct, 4)
                rec["mae_pct"] = round(mae_pct, 4)
                rec["mfe_pct"] = round(mfe_pct, 4)
                break

    def flush(self) -> None:
        self._write_csv()
        self._write_json()
        log.info("InstitutionalAudit: flushed %d records to %s", len(self._records), self._dir)

    def _write_csv(self) -> None:
        mode = "a" if self._csv_path.exists() else "w"
        with open(self._csv_path, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS, extrasaction="ignore")
            if mode == "w":
                writer.writeheader()
            for rec in self._records:
                writer.writerow(rec)
        self._records.clear()

    def _write_json(self) -> None:
        existing = []
        if self._json_path.exists():
            try:
                with open(self._json_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, ValueError):
                existing = []
        existing.extend(self._records)
        with open(self._json_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def load_all(self) -> List[Dict[str, Any]]:
        if self._json_path.exists():
            try:
                with open(self._json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError):
                pass
        if self._csv_path.exists():
            return self._load_csv()
        return []

    def _load_csv(self) -> List[Dict[str, Any]]:
        records = []
        with open(self._csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
        return records
