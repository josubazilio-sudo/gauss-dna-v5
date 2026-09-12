"""
TradingView Webhook Integration — K12 Melhores Sinais
Envia sinais de alta qualidade (OURO, Score ≥80) para TradingView
"""
import httpx
import logging
import json
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Configuração TradingView
TRADINGVIEW_WEBHOOK_URL = os.getenv("TRADINGVIEW_WEBHOOK_URL", "")

async def enviar_para_tradingview(sinal: dict) -> bool:
    """
    Envia sinal para TradingView via webhook

    Critérios de aprovação para envio TradingView:
    - tier == "OURO" (qualidade máxima)
    - score >= 80
    - rr >= 2.0
    - estrutura confirmada (bos_ok ou sweep_ok)
    """
    if not TRADINGVIEW_WEBHOOK_URL:
        logger.warning("TRADINGVIEW_WEBHOOK_URL não configurado")
        return False

    # Validar critérios
    tier = sinal.get("tier", "")
    score = sinal.get("score", 0)
    rr = sinal.get("rr", 0)
    bos_ok = sinal.get("bos_ok", False)
    sweep_ok = sinal.get("sweep_ok", False)

    if tier != "OURO" or score < 80 or rr < 2.0:
        logger.debug(
            f"{sinal['symbol']}: Não qualifica TradingView "
            f"(tier={tier}, score={score}, rr={rr})"
        )
        return False

    if not (bos_ok or sweep_ok):
        logger.debug(f"{sinal['symbol']}: Sem estrutura confirmada")
        return False

    # Montar payload para TradingView
    payload = {
        "time": datetime.now(timezone.utc).isoformat(),
        "symbol": sinal.get("symbol", "").replace("/USDT:USDT", "USDT"),
        "timeframe": sinal.get("timeframe", "?"),
        "direction": sinal.get("direcao", ""),
        "quality": "PREMIUM",
        "tier": "OURO",
        "score": score,
        "entry_quality": sinal.get("eq", 0),
        "rr_ratio": rr,
        "rvol": sinal.get("rvol", 0),
        "structure": "SWEEP" if sweep_ok else "BOS",
        "entry": sinal.get("entrada", 0),
        "tp1": sinal.get("tp1", 0),
        "tp2": sinal.get("tp2", 0),
        "stop": sinal.get("stop", 0),
        "source": "K12_SMC_ENGINE",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                TRADINGVIEW_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code in (200, 201, 202):
                logger.info(
                    f"✅ TradingView: {sinal['symbol']} enviado "
                    f"(score={score}, rr={rr:.2f}, tier=OURO)"
                )
                return True
            else:
                logger.warning(
                    f"TradingView webhook {response.status_code}: "
                    f"{sinal['symbol']} | {response.text[:200]}"
                )
                return False

    except Exception as e:
        logger.error(f"TradingView webhook error: {e}")
        return False


async def enviar_multiplos_tradingview(sinais: list) -> int:
    """
    Envia múltiplos sinais para TradingView
    Retorna quantidade de sinais enviados com sucesso
    """
    enviados = 0

    # Filtrar apenas os melhores (OURO, score ≥80)
    melhores = [
        s for s in sinais
        if s.get("tier") == "OURO" and s.get("score", 0) >= 80
    ]

    if not melhores:
        logger.info("Nenhum sinal OURO para TradingView neste ciclo")
        return 0

    logger.info(f"Enviando {len(melhores)} sinal(is) OURO para TradingView...")

    for sinal in melhores:
        sucesso = await enviar_para_tradingview(sinal)
        if sucesso:
            enviados += 1

    if enviados > 0:
        logger.info(f"✅ {enviados}/{len(melhores)} sinais enviados para TradingView")

    return enviados
