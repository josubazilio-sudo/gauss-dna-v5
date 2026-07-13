"""
Comparação entre versões e identificação de diferenças.
"""

from typing import Dict, Any, Optional


class BaselineComparator:
    def compare(self, b1: Optional[Dict[str, Any]], b2: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not b1 or not b2:
            return {"error": "Uma ou ambas baselines nao encontradas"}
        return {
            "baseline_a": b1.get("version"),
            "baseline_b": b2.get("version"),
            "snapshot_a": b1.get("snapshot_id"),
            "snapshot_b": b2.get("snapshot_id"),
            "match": b1.get("snapshot_id") == b2.get("snapshot_id"),
        }
