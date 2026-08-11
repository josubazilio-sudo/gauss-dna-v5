import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
_raw = os.getenv("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS = [int(x.strip()) for x in _raw.split(",") if x.strip()] if _raw else []

EXCHANGE = "mexc"
BANCA    = float(os.getenv("BANCA", "90.0"))
RISCO_PCT = float(os.getenv("RISCO_PCT", "3.0"))

ALAVANCAGEM_POR_REGIME = {
    "Bull Trend": 25, "Bear Trend": 25,
    "Transição": 15, "Range": 10,
    "Alta Volatilidade": 8, "Baixa Volatilidade": 12,
}

# Gate Entry Quality (EQ) — bloquear late entry
ENTRY_QUALITY_BLOCK = os.getenv("ENTRY_QUALITY_BLOCK", "True").strip().lower() in ("1", "true", "yes", "on")
ENTRY_QUALITY_MIN   = float(os.getenv("ENTRY_QUALITY_MIN", "75"))
K11_OURO_MIN_EQ     = float(os.getenv("K11_OURO_MIN_EQ", "85"))


# ==== GATE 10/10 (qualidade sobre quantidade) ====
MODO_10_10         = os.getenv("MODO_10_10", "False").strip().lower() in ("1", "true", "yes", "on")
RVOL_MIN_10        = float(os.getenv("RVOL_MIN_10", "1.80"))
SCORE_OURO_10      = float(os.getenv("SCORE_OURO_10", "90"))
SCORE_PRATA_10     = float(os.getenv("SCORE_PRATA_10", "80"))
RR_MIN_10          = float(os.getenv("RR_MIN_10", "2.50"))
EXIGE_ESTRUTURA_10 = os.getenv("EXIGE_ESTRUTURA_10", "True").strip().lower() in ("1", "true", "yes", "on")
EXIGE_TENDENCIA_10 = os.getenv("EXIGE_TENDENCIA_10", "True").strip().lower() in ("1", "true", "yes", "on")
EXIGE_FLOW_10      = os.getenv("EXIGE_FLOW_10", "True").strip().lower() in ("1", "true", "yes", "on")
EXIGE_MOMENTUM_10  = os.getenv("EXIGE_MOMENTUM_10", "True").strip().lower() in ("1", "true", "yes", "on")
EXIGE_ENTRY_50_10  = os.getenv("EXIGE_ENTRY_50_10", "True").strip().lower() in ("1", "true", "yes", "on")
ENTRY_50_PCT_10    = float(os.getenv("ENTRY_50_PCT_10", "0.50"))

# ==== GESTÃO DE POSIÇÃO (2026-08-10) — Trailing pós-BE + Alerta Estrutural ====
# Trailing só entra em ação DEPOIS que o BE já foi tocado (be_tocado=True) e
# nunca afrouxa o stop — só aperta a favor do trade. Se o preço voltar e
# bater no stop já trailado, fecha como "TRAIL" (positivo) em vez de "STOP".
# Default OFF — ligar só depois de acompanhar o formato em produção.
TRAILING_ATIVO          = os.getenv("TRAILING_ATIVO", "False").strip().lower() in ("1", "true", "yes", "on")
TRAILING_ATR_MULT       = float(os.getenv("TRAILING_ATR_MULT", "1.5"))
# Alerta (não fecha o trade) quando a estrutura que gerou o sinal virou
# contra (EMA10<EMA21 + MACD virou) antes de bater TP/Stop.
ESTRUTURAL_ALERTA_ATIVO = os.getenv("ESTRUTURAL_ALERTA_ATIVO", "False").strip().lower() in ("1", "true", "yes", "on")


# ==== V58.1 — GESTÃO DE TRADE PÓS-ENTRADA (fonte única de verdade) ===========
# Todas as regras de gestão (BE, TP1, trailing, BOS Age) centralizadas aqui.
# O módulo de gestão (gestao_trade.py / trade_tracker.py) importa estes
# valores. Suporte a env var com fallback centralizado — nada hardcoded.
BE_TRIGGER_R        = float(os.getenv("BE_TRIGGER_R", "1.5"))                      # só ativa BE com R >= 1.5
BE_EXIGE_H1_FECHADO = os.getenv("BE_EXIGE_H1_FECHADO", "True").strip().lower() in ("1", "true", "yes", "on")
TP1_FRACAO_VOLUME   = float(os.getenv("TP1_FRACAO_VOLUME", "0.30"))                # TP1 = 30%, restante 70% p/ TP2/trailing
BOS_AGE_MAX_CANDLES = int(os.getenv("BOS_AGE_MAX_CANDLES", "4"))                   # BOS/CHoCH real <= 4 candles

def _cfg_trailing(trigger, tf):
    return {"trigger_r": float(trigger), "timeframe": (tf or "").strip() or None}

# Trailing por família de setup. REVERSÃO: 2R / H1. TENDÊNCIA: 1.5R / 30M.
# BREAKOUT mantém a regra própria existente (ATR pós-BE): trigger 0 = só BE.
TRAILING_SETUPS = {
    "REVERSAO":  _cfg_trailing(os.getenv("TRAILING_TRIGGER_R_REVERSAO", "2.0"),  os.getenv("TRAILING_TIMEFRAME_REVERSAO", "1h")),
    "TENDENCIA": _cfg_trailing(os.getenv("TRAILING_TRIGGER_R_TENDENCIA", "1.5"), os.getenv("TRAILING_TIMEFRAME_TENDENCIA", "30m")),
    "BREAKOUT":  _cfg_trailing(os.getenv("TRAILING_TRIGGER_R_BREAKOUT", "0.0"),  os.getenv("TRAILING_TIMEFRAME_BREAKOUT", "")),
    "DEFAULT":   _cfg_trailing("0.0", ""),
}
