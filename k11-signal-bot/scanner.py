"""
K10 Scanner V11 — MEXC Futuros USDT
Escaneia 300-500 pares nos timeframes 30m | 1h | 4h | 1d
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from k10_engine import K10Engine
from watchlist import get_watchlist, WATCHLIST_FALLBACK

logger = logging.getLogger(__name__)

TIMEFRAMES = ["5m", "15m", "30m", "1h", "4h", "1d"]


class K10Scanner:
    def __init__(self, max_workers: int = 6):
        self.engine      = K10Engine()
        self.max_workers = max_workers

    def _analisar_safe(self, symbol: str, tf: str = None) -> dict | None:
        try:
            result = self.engine.analisar(symbol, tf)
            return result
        except Exception as e:
            logger.warning(f"Erro {symbol}: {e}")
            return None

    def _detectar_market_low_volume(self, resultados_rvol):
        """Detecta se >80% dos ativos estão com RVOL baixo"""
        if not resultados_rvol:
            return False
        baixos = sum(1 for r in resultados_rvol if r < 0.80)
        pct = baixos / len(resultados_rvol)
        return pct > 0.80

    def _gerar_auditoria_rvol(self, resultados):
        """Gera resumo de auditoria do RVOL"""
        rvols = [r.get("rvol", 0) for r in resultados if r.get("rvol", 0) > 0]
        if not rvols:
            return "Sem dados de RVOL"
        import statistics
        return (
            f"AUDITORIA RVOL ({len(rvols)} ativos):\n"
            f"Média: {sum(rvols)/len(rvols):.2f}\n"
            f"Mediana: {statistics.median(rvols):.2f}\n"
            f"Maior: {max(rvols):.2f}\n"
            f"Menor: {min(rvols):.2f}\n"
            f"RVOL < 0.8: {sum(1 for r in rvols if r < 0.8)/len(rvols)*100:.0f}%\n"
            f"RVOL > 1.2: {sum(1 for r in rvols if r > 1.2)/len(rvols)*100:.0f}%"
        )

    def scan(
        self,
        min_score: int  = 70,
        min_volume: float = 500_000,
        max_ativos: int = 500,
        timeframes: list = None,
        progress_callback=None,
    ) -> list:
        """
        Varre até max_ativos futuros USDT na MEXC.
        Para cada ativo analisa 30m, 1h, 4h e 1d.
        Retorna os melhores sinais aprovados por ativo, ordenados por score.
        """
        if timeframes is None:
            timeframes = TIMEFRAMES

        logger.info("🔍 Buscando watchlist MEXC futuros...")
        watchlist = get_watchlist(min_volume_usdt=min_volume)

        if not watchlist:
            watchlist = WATCHLIST_FALLBACK
            logger.warning("⚠️ Usando watchlist fallback")

        watchlist = watchlist[:max_ativos]
        total     = len(watchlist)
        logger.info(f"📋 {total} ativos × {len(timeframes)} TFs = {total*len(timeframes)} análises")

        # Para cada ativo, pega o melhor sinal entre os TFs
        aprovados  = []
        analisados = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._analisar_safe, s, None): s for s in watchlist}

            for future in as_completed(futures):
                analisados += 1
                result = future.result()

                if progress_callback and analisados % 20 == 0:
                    progress_callback(analisados, total)

                if result and result.get("aprovado") and result.get("score", 0) >= min_score:
                    aprovados.append(result)

        # Detectar MARKET_LOW_VOLUME
        todos_rvol = [r.get("rvol", 0) for r in aprovados]
        market_low_volume = self._detectar_market_low_volume(todos_rvol)
        if market_low_volume:
            logger.info("⚠️ MARKET_LOW_VOLUME ativo — limites de RVOL reduzidos 20%")

        # RFC V4: Priorização — Score > RVOL > Timing > Confluência
        def prioridade_v4(r):
            score     = r.get("score", 0)
            rvol      = r.get("rvol", 0)
            timing    = 100 - r.get("timing_pct", 0)  # menor % = melhor timing
            confluencia = r.get("confluencia", 0)
            # Pesos: score (40%) + rvol (30%) + timing (20%) + confluencia (10%)
            return score * 0.4 + min(rvol * 10, 30) * 0.3 + timing * 0.2 + confluencia * 0.1

        aprovados.sort(key=prioridade_v4, reverse=True)
        logger.info(f"✅ Scan concluído: {len(aprovados)}/{total} ativos aprovados")
        return aprovados

    def scan_tf(self, tf: str, min_score: int = 70, max_ativos: int = 500) -> list:
        """Scan em um timeframe específico"""
        watchlist = get_watchlist()[:max_ativos] or WATCHLIST_FALLBACK
        aprovados = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._analisar_safe, s, tf): s for s in watchlist}
            for future in as_completed(futures):
                result = future.result()
                if result and result.get("aprovado") and result.get("score", 0) >= min_score:
                    aprovados.append(result)

        # RFC V4: Priorização — Score > RVOL > Timing > Confluência
        def prioridade_v4(r):
            score     = r.get("score", 0)
            rvol      = r.get("rvol", 0)
            timing    = 100 - r.get("timing_pct", 0)  # menor % = melhor timing
            confluencia = r.get("confluencia", 0)
            # Pesos: score (40%) + rvol (30%) + timing (20%) + confluencia (10%)
            return score * 0.4 + min(rvol * 10, 30) * 0.3 + timing * 0.2 + confluencia * 0.1

        aprovados.sort(key=prioridade_v4, reverse=True)
        return aprovados

    def formatar_resumo(self, aprovados: list, timeframe: str = "multi-tf") -> str:
        if not aprovados:
            return (
                "🔎 *K10 SCAN MEXC — SEM SINAIS*\n\n"
                "Nenhum sinal aprovado no momento.\n"
                "Mercado sem confluência suficiente.\n\n"
                f"⏰ `{datetime.now().strftime('%d/%m/%Y %H:%M')}`"
            )

        sep = "━━━━━━━━━━━━━━━━━━━━"
        linhas = [
            f"🏆 *K10 SCAN MEXC — {len(aprovados)} SINAL(IS)*\n",
            f"⏰ `{datetime.now().strftime('%d/%m/%Y %H:%M')}` | TF: {timeframe}\n",
            sep,
        ]

        for i, r in enumerate(aprovados[:10], 1):
            dir_emoji = "🟢" if r["direcao"] == "LONG" else "🔴"
            tier = r.get("tier","BRONZE")
            tier_e = "💎" if tier=="DIAMANTE" else "🥇" if tier=="OURO" else "🥈" if tier=="PRATA" else "🥉"
            sym = r["symbol"].replace("/USDT:USDT","").replace("/USDT","")
            tf  = r.get("timeframe","30m")
            linhas.append(
                f"\n{i}. {tier_e} *{sym}* {dir_emoji} {r['direcao']} | {tf}\n"
                f"   Score: {r['score']} | RR: {r['rr']}\n"
                f"   Entrada: `{r['entrada']}` → TP1: `{r['tp1']}`"
            )

        if len(aprovados) > 10:
            linhas.append(f"\n\n_...e mais {len(aprovados)-10} sinais._")

        linhas.append(f"\n\n{sep}\nUse `/analisar SYMBOL` para o cartão completo.")
        return "\n".join(linhas)
