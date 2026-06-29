import logging
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)


class Diagnostics:
    def __init__(self):
        self.entries = []
        self.blockers = Counter()
        self.filter_blocks = Counter()
        self.candidates = []
        self.cycle_count = 0
        self.total_analises = 0
        self.trade_results = []
        self.sinais_pulados = 0

    def record(self, symbol, decision, detail=None, score=None):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "decision": decision,
            "detail": str(detail) if detail else None,
            "score": score,
        }
        self.entries.append(entry)

        if decision in ("OURO", "PRATA", "BRONZE"):
            logger.info("[%s] %s | Score: %s | Detalhe: %s", symbol, decision, score, detail)
        elif decision == "recusado":
            motivo = str(detail)
            if "score" in motivo:
                self.blockers["score baixo"] += 1
            elif "mercado lateral" in motivo.lower():
                self.blockers["mercado lateral"] += 1
            elif "rvol" in motivo.lower():
                self.blockers["RVOL baixo"] += 1
            elif "adx" in motivo.lower():
                self.blockers["ADX baixo"] += 1
            elif "tendencia" in motivo.lower():
                self.blockers["tendencia desfavoravel"] += 1
            elif "volatilidade" in motivo.lower():
                self.blockers["volatilidade alta"] += 1
            elif "liquidez" in motivo.lower():
                self.blockers["liquidez baixa"] += 1
            elif "spread" in motivo.lower():
                self.blockers["spread alto"] += 1
            else:
                self.blockers[motivo] += 1
            logger.debug("[%s] recusado: %s score=%s", symbol, detail, score)

    def record_filter_block(self, motivo):
        self.filter_blocks[motivo] += 1

    def record_result(self, symbol, result, r_multiple=0):
        self.trade_results.append({
            "symbol": symbol,
            "result": result,
            "r": r_multiple,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def add_candidate(self, symbol, direction, score, rsi, detalhes=""):
        self.candidates.append({
            "symbol": symbol,
            "direction": direction,
            "score": score,
            "rsi": rsi,
            "detalhes": detalhes,
        })

    def summary(self, top_n=8):
        if not self.entries:
            return None

        aprovados = [e for e in self.entries if e["decision"] in ("OURO", "PRATA", "BRONZE")]
        recusados = [e for e in self.entries if e["decision"] == "recusado"]
        bloqueados = [e for e in self.entries if e["decision"] == "bloqueado"]

        now = datetime.utcnow()
        ultimo_sinal = None
        for e in reversed(self.entries):
            if e["decision"] in ("OURO", "PRATA", "BRONZE"):
                ultimo_sinal = e["timestamp"]
                break
        tempo_sem_sinal = ""
        if ultimo_sinal:
            t = datetime.fromisoformat(ultimo_sinal)
            diff = (now - t).total_seconds()
            mins = int(diff // 60)
            tempo_sem_sinal = f"sem sinais ha {mins}min"
        else:
            tempo_sem_sinal = "sem historico de sinais"

        ordenados = sorted(
            [e for e in self.entries if e.get("score") is not None],
            key=lambda x: x["score"] or 0, reverse=True,
        )

        top_candidates = ordenados[:top_n]
        top_linhas = []
        for e in top_candidates:
            score = e.get("score", 0)
            direction = "LONG" if score >= 0 else "SHORT"
            rsi = ""
            detalhes = e.get("detail", "")
            top_linhas.append(f"  {direction:6s} {e['symbol']:10s} +{score:3d} RSI{rsi} → {detalhes}")

        top_str = "\n".join(top_linhas) if top_linhas else "  Nenhum candidato"

        bloqueadores = self.blockers.most_common(6)
        bloqueadores_str = "\n".join(
            f"  {i+1}. {motivo} — {count}x"
            for i, (motivo, count) in enumerate(bloqueadores)
        ) if bloqueadores else "  Nenhum"

        filtros_str = ""
        if self.filter_blocks:
            filtros_ordenados = self.filter_blocks.most_common(6)
            filtros_str = "\nSinais detectados mas bloqueados depois:\n" + "\n".join(
                f"  {i+1}. {motivo} — {count}x"
                for i, (motivo, count) in enumerate(filtros_ordenados)
            )

        winrate_str = ""
        if self.trade_results:
            total = len(self.trade_results)
            wins = sum(1 for r in self.trade_results if r["result"] == "tp")
            losses = sum(1 for r in self.trade_results if r["result"] == "stop")
            winrate = wins / total * 100 if total > 0 else 0
            avg_r = sum(r["r"] for r in self.trade_results) / total if total > 0 else 0
            winrate_str = f"\n\nResultados ({total} fechados) — STOP:{losses} TP:{wins} — winrate: {winrate:.0f}% — R medio: {avg_r:.2f}R"

        pulados = f" | ⏭ Pulados: {self.sinais_pulados}" if self.sinais_pulados else ""

        return (
            f"DIAGNOSTICO GAUSS+DNA — {tempo_sem_sinal}\n"
            f"Mercado neutro — Analisados: {len(self.entries)}\n"
            f"✅ Aprovados: {len(aprovados)} | 🔒 Bloqueados: {len(bloqueados)} | ❌ Recusados: {len(recusados)}\n\n"
            f"Bloqueadores mais frequentes:\n{bloqueadores_str}"
            f"{filtros_str}\n\n"
            f"Candidatos (por que nao disparou):\n{top_str}\n"
            f"{winrate_str}\n\n"
            f"Ciclos: {self.cycle_count} | Analises: {self.total_analises}{pulados}"
        )

    def reset_candidates(self):
        self.candidates = []
