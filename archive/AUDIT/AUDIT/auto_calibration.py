import logging
from collections import defaultdict
from typing import Any, Dict, List, Tuple

log = logging.getLogger(__name__)


class AutoCalibration:
    def __init__(self):
        self._feature_impact: Dict[str, Dict[str, float]] = {}

    def analyze(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not records:
            return []
        suggestions = []

        suggestions.extend(self._analyze_adx(records))
        suggestions.extend(self._analyze_volume(records))
        suggestions.extend(self._analyze_patterns(records))
        suggestions.extend(self._analyze_ema(records))
        suggestions.extend(self._analyze_classification(records))
        suggestions.extend(self._analyze_regime(records))
        suggestions.extend(self._analyze_rvol(records))
        suggestions.extend(self._analyze_rr(records))
        suggestions.extend(self._analyze_structural_score(records))
        suggestions.extend(self._analyze_confidence(records))
        suggestions.extend(self._analyze_quality(records))
        suggestions.extend(self._analyze_direction(records))

        suggestions.sort(key=lambda s: s.get("priority", 0), reverse=True)
        log.info("AutoCalibration: %d suggestions generated", len(suggestions))
        return suggestions

    def wr(self, records: List[Dict], key: str, threshold: float,
           higher: bool = True) -> Tuple[int, int, float]:
        matched_wins = 0
        matched_total = 0
        for r in records:
            val = r.get(key, 0)
            if val <= 0:
                continue
            matched_total += 1
            cond = val >= threshold if higher else val <= threshold
            if cond and r.get("result") == "win":
                matched_wins += 1
        if matched_total == 0:
            return 0, 0, 0.0
        return matched_wins, matched_total, matched_wins / matched_total

    def wr_binary(self, records: List[Dict], pred) -> Tuple[int, int, float]:
        matched = [r for r in records if pred(r)]
        wins = sum(1 for r in matched if r.get("result") == "win")
        total = len(matched)
        wr = wins / total if total > 0 else 0
        return wins, total, wr

    def _suggestion(self, feature: str, wins: int, total: int, wr: float,
                    text: str, priority: int) -> Dict:
        return {
            "feature": feature, "wins": wins, "total": total,
            "win_rate": round(wr, 4), "suggestion": text, "priority": priority,
        }

    def _analyze_adx(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        adx_vals = [r.get("adx", 0) for r in records if r.get("adx", 0) > 0]
        if not adx_vals:
            return suggestions

        for th in [20, 25, 30]:
            wins, total, wr = self.wr(records, "adx", th, True)
            if total >= 3:
                suggestions.append(self._suggestion(f"ADX >= {th}", wins, total, wr, "", 0))

        for th in [15, 20]:
            wins, total, wr_low = self.wr(records, "adx", th, False)
            if total >= 3:
                suggestions.append(self._suggestion(f"ADX < {th}", wins, total, wr_low, "", 0))

        wins_25, total_25, wr_25 = self.wr(records, "adx", 25, True)
        wins_20l, total_20l, wr_20l = self.wr(records, "adx", 20, False)

        if total_25 >= 5 and wr_25 < 0.4:
            suggestions.append(self._suggestion("ADX >= 25 (baixo WR)", wins_25, total_25, wr_25,
                "Peso do ADX muito alto — reduzir threshold ou diminuir peso no scoring", 8))
        if total_20l >= 5 and wr_20l < 0.3:
            suggestions.append(self._suggestion("ADX < 20 (baixo WR)", wins_20l, total_20l, wr_20l,
                "ADX baixo tem WR baixo — reforçar filtro de tendência fraca", 7))
        if total_20l >= 5 and wr_20l > 0.6:
            suggestions.append(self._suggestion("ADX < 20 (alto WR)", wins_20l, total_20l, wr_20l,
                "ADX baixo tem alta taxa de acerto — revisar threshold de rejeição", 5))
        return suggestions

    def _analyze_volume(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        for th in [1.0, 1.5, 2.0, 3.0]:
            wins, total, wr = self.wr(records, "rvol_value", th, True)
            if total >= 3:
                suggestions.append(self._suggestion(f"RVOL >= {th}x", wins, total, wr, "", 0))
        wins_15, total_15, wr_15 = self.wr(records, "rvol_value", 1.5, True)
        if total_15 >= 5 and wr_15 > 0.65:
            suggestions.append(self._suggestion("RVOL >= 1.5x (alto WR)", wins_15, total_15, wr_15,
                "RVOL alto melhora significativamente WR — aumentar peso no scoring", 8))
        return suggestions

    def _analyze_patterns(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        pattern_fields = ["choch", "bos", "liquidity_sweep", "order_block", "fvg"]

        for pat in pattern_fields:
            wins_p, total_p, wr_p = self.wr_binary(records, lambda r, p=pat: r.get(p, 0) == 1)
            if total_p < 3:
                continue
            impact_field = f"{pat}_impact"
            impact = wr_p - 0.18
            text = ""
            prio = 0
            if pat == "choch" and wr_p < 0.15:
                text = "CHoCH tem WR muito baixo — aumentar confidence mínima ou filtrar"
                prio = 9
            elif pat == "liquidity_sweep" and wr_p > 0.25:
                text = "Liquidity Sweep melhora WR — considerar aumentar peso"
                prio = 8
            elif pat == "order_block" and wr_p > 0.22:
                text = "Order Blocks melhoram precisão — manter peso"
                prio = 6
            elif pat == "bos" and wr_p < 0.15:
                text = "BOS gera entradas prematuras — revisar threshold de confirmação"
                prio = 7
            elif pat == "fvg" and wr_p < 0.12:
                text = "FVG sozinho tem WR baixo — exigir confirmação adicional"
                prio = 5
            suggestions.append({
                "feature": f"Pattern: {pat}", "wins": wins_p, "total": total_p,
                "win_rate": round(wr_p, 4), "impact": round(impact, 4),
                "suggestion": text, "priority": prio,
            })
        return suggestions

    def _analyze_ema(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        aligned_wins = 0
        aligned_total = 0
        for r in records:
            ema50 = r.get("ema50", 0)
            ema200 = r.get("ema200", 0)
            entry = r.get("entry_price", 0)
            direction = r.get("direction", "")
            if ema50 <= 0 or ema200 <= 0 or entry <= 0:
                continue
            aligned_total += 1
            if direction == "long" and ema50 > ema200 and entry > ema50:
                if r.get("result") == "win":
                    aligned_wins += 1
            elif direction == "short" and ema50 < ema200 and entry < ema50:
                if r.get("result") == "win":
                    aligned_wins += 1
            else:
                if r.get("result") == "win":
                    aligned_wins += 1

        if aligned_total >= 5:
            wr_a = aligned_wins / aligned_total
            recommendations = (
                "EMA filter reduz perdas — manter no quality gate"
                if wr_a > 0.5 else
                "EMA filter remove trades lucrativos — revisar lógica de alinhamento"
            )
            suggestions.append(self._suggestion(
                "EMA 50/200 aligned", aligned_wins, aligned_total, wr_a,
                recommendations, 6 if wr_a > 0.5 else 4,
            ))
        return suggestions

    def _analyze_classification(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        groups = defaultdict(list)
        for r in records:
            cl = r.get("classification", "")
            if cl:
                groups[cl].append(r)
        hierarchy = ["ouro_supremo", "ouro", "prata", "bronze", "reprovado"]
        for cl in hierarchy:
            if cl in groups:
                ts = groups[cl]
                wins = sum(1 for t in ts if t.get("result") == "win")
                total = len(ts)
                wr = wins / total if total > 0 else 0
                text = ""
                prio = 0
                if cl in ("ouro_supremo", "ouro") and total >= 3 and wr < 0.3:
                    text = f"{cl} tem WR abaixo do esperado — revisar critérios de classificação"
                    prio = 9
                elif cl == "prata" and total >= 5 and wr > 0.3:
                    text = "PRATA tem WR consistente — threshold mínimo está adequado"
                    prio = 5
                elif cl == "bronze" and total >= 5 and wr < 0.15:
                    text = "BRONZE tem WR muito baixo — considerar aumentar threshold mínimo para PRATA"
                    prio = 8
                suggestions.append(self._suggestion(
                    f"Class: {cl}", wins, total, wr, text, prio,
                ))
        return suggestions

    def _analyze_regime(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        groups = defaultdict(list)
        for r in records:
            rg = r.get("regime", "")
            if rg:
                groups[rg].append(r)
        for rg, ts in sorted(groups.items()):
            wins = sum(1 for t in ts if t.get("result") == "win")
            total = len(ts)
            wr = wins / total if total > 0 else 0
            text = ""
            prio = 0
            if rg in ("ranging", "lateral") and total >= 5 and wr < 0.25:
                text = "Ranging tem WR muito baixo — reforçar filtro de regime ou aumentar structural_score mínimo para 60"
                prio = 9
            elif rg == "trending_up" and total >= 5 and wr > 0.4:
                text = "Trending_up tem WR superior — considerar aumentar exposição em tendências"
                prio = 7
            elif rg == "trending_down" and total >= 5 and wr > 0.4:
                text = "Trending_down tem WR superior — manter filtro de tendência"
                prio = 6
            elif rg in ("volatile",) and total >= 5 and wr < 0.2:
                text = "Volátil tem WR muito baixo — bloques sinais em volatilidade alta"
                prio = 8
            suggestions.append(self._suggestion(f"Regime: {rg}", wins, total, wr, text, prio))
        return suggestions

    def _analyze_rvol(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        thresholds = [0.5, 1.0, 1.5, 2.0, 3.0]
        for th in thresholds:
            wins, total, wr = self.wr(records, "rvol_value", th, True)
            if total >= 3:
                suggestions.append(self._suggestion(f"RVOL >= {th}x", wins, total, wr, "", 0))
        return suggestions

    def _analyze_rr(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        thresholds = [1.5, 2.0, 2.5, 3.0, 4.0]
        for th in thresholds:
            wins, total, wr = self.wr(records, "risk_reward", th, True)
            if total >= 3:
                text = ""
                prio = 0
                if th >= 3.0 and total >= 5 and wr > 0.3:
                    text = "RR >= 3:1 mantém WR saudável — aumentar RR mínimo para 2.5 para OURO"
                    prio = 7
                elif th == 2.0 and total >= 10 and wr < 0.2:
                    text = "RR 2:1 tem WR baixo — aumentar RR mínimo para 2.5"
                    prio = 6
                suggestions.append(self._suggestion(f"RR >= {th}:1", wins, total, wr, text, prio))
        return suggestions

    def _analyze_structural_score(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        thresholds = [40, 50, 60, 70]
        for th in thresholds:
            matched = [r for r in records if r.get("structural_score", 0) >= th]
            wins = sum(1 for r in matched if r.get("result") == "win")
            total = len(matched)
            wr = wins / total if total > 0 else 0
            if total >= 3:
                text = ""
                prio = 0
                if th == 60 and total >= 5 and wr < 0.25:
                    text = "Structural >= 60 tem WR baixo — threshold precisa ser revisado"
                    prio = 8
                elif th == 50 and total >= 10 and wr > 0.25:
                    text = "Structural >= 50 mostra WR consistente — threshold mínimo adequado"
                    prio = 6
                suggestions.append(self._suggestion(
                    f"Structural >= {th}", wins, total, wr, text, prio,
                ))
        return suggestions

    def _analyze_confidence(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        thresholds = [0.4, 0.5, 0.6, 0.7, 0.8]
        for th in thresholds:
            wins, total, wr = self.wr(records, "confidence", th, True)
            if total >= 3:
                suggestions.append(self._suggestion(f"Confidence >= {th:.1f}", wins, total, wr, "", 0))
        return suggestions

    def _analyze_quality(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        thresholds = [0.5, 0.6, 0.7, 0.8]
        for th in thresholds:
            wins, total, wr = self.wr(records, "quality", th, True)
            if total >= 3:
                suggestions.append(self._suggestion(f"Quality >= {th:.1f}", wins, total, wr, "", 0))
        return suggestions

    def _analyze_direction(self, records: List[Dict]) -> List[Dict]:
        suggestions = []
        for direction in ["long", "short"]:
            wins, total, wr = self.wr_binary(records, lambda r, d=direction: r.get("direction") == d)
            if total >= 3:
                text = ""
                prio = 0
                if direction == "short" and total >= 5 and wr > 0.3:
                    text = "SHORT tem WR superior — considerar filtro direcional mais permissivo"
                    prio = 6
                elif direction == "long" and total >= 5 and wr < 0.15:
                    text = "LONG tem WR baixo — revisar critérios para entradas longas"
                    prio = 7
                suggestions.append(self._suggestion(f"Direction: {direction}", wins, total, wr, text, prio))
        return suggestions
