import json
import logging
import os
import sqlite3
import csv
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from statistics import mean, stdev

log = logging.getLogger(__name__)


class AnalyticsEngine:
    """Lê pipelines JSON existentes e gera estatísticas + persistência."""

    def __init__(self, audit_dir: str = "MEMORY/audit"):
        self._audit_dir = audit_dir
        self._pipelines: List[Dict] = []
        self._summary: Dict = {}
        self._all_final_decisions: List[Dict] = []

    def load_all(self):
        """Carrega todos os pipelines JSON + summary."""
        summary_path = os.path.join(self._audit_dir, "summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, encoding="utf-8") as f:
                self._summary = json.load(f)

        for fname in sorted(os.listdir(self._audit_dir)):
            if fname.startswith("pipeline_") and fname.endswith(".json"):
                path = os.path.join(self._audit_dir, fname)
                with open(path, encoding="utf-8") as f:
                    pipe = json.load(f)
                    self._pipelines.append(pipe)

        # Extract all final decisions with full context
        for pipe in self._pipelines:
            cycle = pipe.get("cycle", 0)
            for pair, decision in pipe.get("final_decisions", {}).items():
                entry = {
                    "cycle": cycle,
                    "pair": pair,
                    **decision,
                }
                # Add quality gate context
                qg = pipe.get("quality_gates", {}).get(pair, {})
                entry["quality_score"] = qg.get("scores", {}).get("quality_score")
                entry["confidence_score"] = qg.get("scores", {}).get("confidence_score")
                self._all_final_decisions.append(entry)

        log.info(f"Loaded {len(self._pipelines)} pipelines, {len(self._all_final_decisions)} decisions")

    # ---- REJECTION ANALYSIS ----

    def rejection_ranking(self) -> List[Dict]:
        """Ranking de motivos de rejeição."""
        counter = Counter()
        pair_by_reason = defaultdict(set)
        tf_by_reason = defaultdict(set)

        for decision in self._all_final_decisions:
            reason = decision.get("primary_reason", "unknown")
            counter[reason] += 1
            pair_by_reason[reason].add(decision["pair"])

        total = sum(counter.values()) or 1
        ranking = []
        for reason, count in counter.most_common():
            ranking.append({
                "motivo": reason,
                "quantidade": count,
                "percentual": round(count / total * 100, 1),
                "ativos_afetados": len(pair_by_reason[reason]),
                "exemplo_ativos": sorted(pair_by_reason[reason])[:5],
            })
        return ranking

    # ---- SIGNAL ANALYSIS ----

    def signal_analysis(self) -> Dict:
        """Análise detalhada dos sinais."""
        signals = []
        for decision in self._all_final_decisions:
            if decision.get("status") == "APPROVED":
                signals.append(decision)

        quality_scores = [s.get("quality_score", 0) or 0 for s in signals]
        conf_scores = [s.get("confidence_score", 0) or 0 for s in signals]

        return {
            "total_signals": len(self._all_final_decisions),
            "approved": len(signals),
            "rejected": len(self._all_final_decisions) - len(signals),
            "approval_rate": round(len(signals) / max(len(self._all_final_decisions), 1) * 100, 2),
            "avg_quality": round(mean(quality_scores), 4) if quality_scores else 0,
            "avg_confidence": round(mean(conf_scores), 4) if conf_scores else 0,
            "max_quality": round(max(quality_scores), 4) if quality_scores else 0,
            "min_quality": round(min(quality_scores), 4) if quality_scores else 0,
            "std_quality": round(stdev(quality_scores), 4) if len(quality_scores) > 1 else 0,
        }

    # ---- PERFORMANCE ANALYSIS ----

    def performance_analysis(self) -> Dict:
        """Métricas de performance do pipeline."""
        durations = [p.get("duration_ms", 0) for p in self._pipelines if p.get("duration_ms", 0) > 0]
        durations_uncached = durations[:1] if len(durations) > 1 else durations  # first cycle (uncached)

        return {
            "total_cycles": len(self._pipelines),
            "duration_ms": {
                "all_cycles": {
                    "mean": round(mean(durations), 1) if durations else 0,
                    "max": round(max(durations), 1) if durations else 0,
                    "min": round(min(durations), 1) if durations else 0,
                    "std": round(stdev(durations), 1) if len(durations) > 1 else 0,
                },
                "first_cycle_uncached": round(durations[0], 1) if durations else 0,
                "cached_cycles": {
                    "mean": round(mean(durations[1:]), 1) if len(durations) > 1 else 0,
                    "min": round(min(durations[1:]), 1) if len(durations) > 1 else 0,
                },
            },
            "total_assets_analyzed": self._summary.get("total_assets_analyzed", 0),
            "total_signals_approved": self._summary.get("total_signals_approved", 0),
            "total_signals_rejected": self._summary.get("total_signals_rejected", 0),
        }

    # ---- HEALTH ANALYSIS ----

    def health_analysis(self) -> Dict:
        """Análise de saúde do sistema."""
        health_scores = []
        bugs = []
        silent_drops = 0

        for p in self._pipelines:
            h = p.get("health", {})
            score = h.get("health_score")
            if score:
                health_scores.append(score)
            bugs.extend(p.get("bugs", []))
            silent_drops += h.get("silent_drops", 0)

        return {
            "health_scores": {
                "mean": round(mean(health_scores), 1) if health_scores else 0,
                "min": min(health_scores) if health_scores else 0,
                "max": max(health_scores) if health_scores else 0,
                "latest": health_scores[-1] if health_scores else 0,
                "below_threshold": sum(1 for s in health_scores if s < 90) if health_scores else 0,
            },
            "total_bugs": len(bugs),
            "total_silent_drops": silent_drops,
            "bugs_detail": bugs[:10],
        }

    # ---- PERSISTENCE ----

    def to_sqlite(self, db_path: str = "MEMORY/analytics.db"):
        """Exporta dados para SQLite."""
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # Decisions table
        c.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                cycle INTEGER, pair TEXT, status TEXT,
                primary_reason TEXT, final_decision TEXT,
                quality_score REAL, confidence_score REAL,
                timestamp TEXT
            )
        """)
        c.execute("DELETE FROM decisions")
        for d in self._all_final_decisions:
            c.execute("""
                INSERT INTO decisions (cycle, pair, status, primary_reason,
                    final_decision, quality_score, confidence_score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                d.get("cycle"), d.get("pair"), d.get("status"),
                d.get("primary_reason"), d.get("final_decision"),
                d.get("quality_score"), d.get("confidence_score"),
                datetime.now(timezone.utc).isoformat(),
            ))

        # Cycles table
        c.execute("""
            CREATE TABLE IF NOT EXISTS cycles (
                cycle INTEGER, duration_ms REAL, total_assets INTEGER,
                approved INTEGER, rejected INTEGER, health_score REAL
            )
        """)
        c.execute("DELETE FROM cycles")
        for p in self._pipelines:
            h = p.get("health", {})
            c.execute("""
                INSERT INTO cycles VALUES (?, ?, ?, ?, ?, ?)
            """, (
                p.get("cycle"), p.get("duration_ms"),
                p.get("total_assets"), p.get("approved_assets"),
                sum(p.get("rejection_reasons", {}).values()),
                h.get("health_score"),
            ))

        conn.commit()
        conn.close()
        log.info(f"SQLite export: {db_path}")

    def to_csv(self, output_dir: str = "MEMORY/audit"):
        """Exporta dados para CSV."""
        # Decisions CSV
        decisions_path = os.path.join(output_dir, "decisions.csv")
        with open(decisions_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["cycle", "pair", "status", "primary_reason",
                           "final_decision", "quality_score", "confidence_score"])
            for d in self._all_final_decisions:
                writer.writerow([
                    d.get("cycle"), d.get("pair"), d.get("status"),
                    d.get("primary_reason"), d.get("final_decision"),
                    d.get("quality_score"), d.get("confidence_score"),
                ])
        log.info(f"CSV export: {decisions_path}")

        # Rejection ranking CSV
        ranking = self.rejection_ranking()
        ranking_path = os.path.join(output_dir, "rejection_ranking.csv")
        with open(ranking_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["motivo", "quantidade", "percentual", "ativos_afetados"])
            for r in ranking:
                writer.writerow([r["motivo"], r["quantidade"], r["percentual"], r["ativos_afetados"]])
        log.info(f"CSV export: {ranking_path}")

        # Performance CSV
        perf_path = os.path.join(output_dir, "performance.csv")
        with open(perf_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["cycle", "duration_ms", "total_assets", "approved", "health_score"])
            for p in self._pipelines:
                h = p.get("health", {})
                writer.writerow([
                    p.get("cycle"), p.get("duration_ms"),
                    p.get("total_assets"), p.get("approved_assets"),
                    h.get("health_score"),
                ])
        log.info(f"CSV export: {perf_path}")

    def generate_report(self) -> Dict:
        """Gera relatório completo."""
        return {
            "summary": self._summary,
            "signals": self.signal_analysis(),
            "rejection_ranking": self.rejection_ranking(),
            "performance": self.performance_analysis(),
            "health": self.health_analysis(),
        }
