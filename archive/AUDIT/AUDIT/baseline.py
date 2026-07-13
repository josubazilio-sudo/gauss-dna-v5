import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

BASELINE_DIR = Path(__file__).parent.parent / "MEMORY" / "baseline"


def save_baseline(result, version: str = "V7", path: Optional[Path] = None) -> Path:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    dest = path or (BASELINE_DIR / f"baseline_{version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    data = {
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "win_rate": round(result.win_rate, 4),
            "profit_factor": round(result.profit_factor, 4),
            "expectancy": round(result.expectancy, 6),
            "max_drawdown": round(result.max_drawdown, 4),
            "sharpe_ratio": round(result.sharpe_ratio, 4),
            "sortino_ratio": round(result.sortino_ratio, 4),
            "calmar_ratio": round(result.calmar_ratio, 4),
            "avg_rr": round(result.avg_rr, 4),
            "net_pnl": round(result.net_pnl, 4),
            "gross_profit": round(result.gross_profit, 4),
            "gross_loss": round(result.gross_loss, 4),
            "avg_trade_duration_h": round(result.avg_trade_duration_h, 4),
        },
        "by_setup": {k: {"trades": v["trades"], "wins": v["wins"], "win_rate": round(v["win_rate"], 4)} for k, v in result.by_setup.items()},
        "by_regime": {k: {"trades": v["trades"], "wins": v["wins"], "win_rate": round(v["win_rate"], 4)} for k, v in result.by_regime.items()},
        "by_timeframe": {k: {"trades": v["trades"], "wins": v["wins"], "win_rate": round(v["win_rate"], 4)} for k, v in result.by_timeframe.items()},
        "by_asset": {k: {"trades": v["trades"], "wins": v["wins"], "win_rate": round(v["win_rate"], 4), "profit_factor": round(v.get("profit_factor", 0), 4)} for k, v in result.by_asset.items()},
    }

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    log.info("Baseline saved: %s", dest)
    return dest


def load_baseline(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        log.warning("Baseline not found: %s", path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_against_baseline(result, baseline: Dict[str, Any]) -> Dict[str, Any]:
    base = baseline.get("metrics", {})
    current = {
        "total_trades": result.total_trades,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "expectancy": result.expectancy,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "avg_rr": result.avg_rr,
        "net_pnl": result.net_pnl,
    }
    deltas = {}
    for key in current:
        b = base.get(key)
        c = current[key]
        if b is not None and b != 0:
            deltas[key] = {
                "baseline": b,
                "current": c,
                "diff": round(c - b, 4),
                "diff_pct": round((c - b) / abs(b) * 100, 2),
            }
        elif b is not None:
            deltas[key] = {"baseline": b, "current": c, "diff": round(c - b, 4), "diff_pct": None}
    return deltas


def list_baselines() -> list:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(BASELINE_DIR.glob("baseline_*.json"))
