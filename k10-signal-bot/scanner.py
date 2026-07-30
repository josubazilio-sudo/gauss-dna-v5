"""
K10 Scanner — Varredura multi-timeframe em paralelo
Analisa 300-500 futuros USDT com rate limit respeitado
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from k10_engine import K10Engine
from watchlist import get_watchlist, WATCHLIST_FALLBACK

logger = logging.getLogger(__name__)


class K10Scanner:
    def __init__(self, max_workers: int = 8):
        self.engine     = K10Engine()
        self.max_workers = max_workers

    # ─────────────────────────────────────────────────────────────────────────
    # Análise de um único ativo (thread-safe)
    # ─────────────────────────────────────────────────────────────────────────
    def _analisar_safe(self, symbol: str) -> dict | None:
        try:
            result = self.engine.analisar(symbol)
            return result
        except Exception as e:
            logger.warning(f"Erro {symbol}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Scan completo
    # ─────────────────────────────────────────────────────────────────────────
    def scan(
        self,
        min_score: int = 60,
        min_volume: float = 1_000_000,
        max_ativos: int = 500,
        progress_callback=None,
    ) -> list:
        """
        Varre até max_ativos futuros USDT.
        Retorna lista de sinais aprovados ordenados por score.
        """
        logger.info("🔍 Buscando watchlist de futuros...")
        watchlist = get_watchlist(min_volume_usdt=min_volume)

        if not watchlist:
            watchlist = WATCHLIST_FALLBACK
            logger.warning("⚠️ Usando watchlist fallback")

        watchlist = watchlist[:max_ativos]
        total     = len(watchlist)
        logger.info(f"📋 {total} ativos para analisar")

        aprovados  = []
        analisados = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._analisar_safe, s): s for s in watchlist}

            for future in as_completed(futures):
                analisados += 1
                result = future.result()

                if progress_callback and analisados % 20 == 0:
                    progress_callback(analisados, total)

                if result and result.get("aprovado") and result.get("score", 0) >= min_score:
                    aprovados.append(result)

        aprovados.sort(key=lambda x: x.get("score", 0), reverse=True)
        logger.info(f"✅ Scan concluído: {len(aprovados)}/{total} aprovados")
        return aprovados

    # ─────────────────────────────────────────────────────────────────────────
    # Scan por timeframe específico
    # ─────────────────────────────────────────────────────────────────────────
    def scan_timeframe(self, tf: str = "30m", **kwargs) -> list:
        """Permite filtrar sinais de um timeframe específico"""
        results = self.scan(**kwargs)
        return [r for r in results if r.get("timeframe") == tf]

    # ─────────────────────────────────────────────────────────────────────────
    # Resumo formatado para Telegram
    # ─────────────────────────────────────────────────────────────────────────
    def formatar_resumo(self, aprovados: list, timeframe: str = "todos") -> str:
        if not aprovados:
            return (
                "🔎 *K10 SCAN CONCLUÍDO*\n\n"
                "Nenhum sinal aprovado no momento.\n"
                "Mercado sem confluência suficiente.\n\n"
                f"⏰ `{datetime.now().strftime('%d/%m/%Y %H:%M')}`"
            )

        sep = "━━━━━━━━━━━━━━━━━━━━"
        linhas = [
            f"🏆 *K10 SCAN — {len(aprovados)} SINAL(IS) APROVADO(S)*\n",
            f"⏰ `{datetime.now().strftime('%d/%m/%Y %H:%M')}` | TF: {timeframe}\n",
            sep,
        ]

        for i, r in enumerate(aprovados[:10], 1):  # top 10
            dir_emoji = "🟢" if r["direcao"] == "LONG" else "🔴"
            tier = "💎" if r["score"] >= 90 else "⭐" if r["score"] >= 80 else "✔️"
            linhas.append(
                f"\n{i}. {tier} *{r['symbol'].replace('/','').replace(':USDT','')}* "
                f"{dir_emoji} {r['direcao']}\n"
                f"   Setup: {r['setup_nome']}\n"
                f"   Score: {r['score']} | RR: {r['rr']}\n"
                f"   Entrada: `{r['entrada']}` | Stop: `{r['stop']}`\n"
                f"   TP1: `{r['tp1']}` | TP2: `{r.get('tp2','—')}`"
            )

        if len(aprovados) > 10:
            linhas.append(f"\n\n_...e mais {len(aprovados)-10} sinais. Use /analisar SYMBOL para detalhes._")

        linhas.append(f"\n\n{sep}")
        linhas.append("\nUse `/analisar SYMBOL` para o cartão completo.")
        return "\n".join(linhas)
