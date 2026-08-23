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

# ==== SOFT FILTERS MODE (RFC reequilibrio 22/08) ====
# Decisao explicita do usuario, CONTRA a evidencia do Shadow Tracking na
# data desta mudanca (270 candidatos bloqueados resolvidos: WR 18.5%,
# PF 0.45, Exp -0.447R -- toda categoria de bloqueio negativa). Default
# False preserva o comportamento estrito de sempre; so muda algo se
# explicitamente ligado no .env. Ver k10_engine.py para o que cada filtro
# soft faz (penalidade de score em vez de bloqueio duro) e o que continua
# HARD (SHORT, estrutura BOS/CHoCH, RR minimo, H4 contra tendencia FORTE,
# RVOL muito baixo, ADX/RSI extremos, K12 extensao/candle).
SOFT_FILTERS_MODE = os.getenv("SOFT_FILTERS_MODE", "False").strip().lower() in ("1", "true", "yes", "on")
# RFC frequencia-sinais 23/08: piso e cap recalibrados com dado real (51
# candidatos reais, 22h, symbols BNB/XLM/WLD/FIL/ONDO/FARTCOIN/SPX500 citados
# pelo usuario). Achado: penalidades soft empilham sem limite (EMA+MACD+
# zona+RVOL simultaneos = ate 45pts), o que matava candidatos de score
# 85-99 mesmo com toda estrutura real confirmada (BOS, RR>=3, RVOL bom) --
# um bloqueio silencioso via o piso agregado, nao um filtro individual.
# Cap de 25 + piso 60 testados contra os 51 candidatos reais: aprova 8/51,
# TODOS com score>=87, ZERO candidato fraco (score<70) passa. Antes (piso
# 70, sem cap): so 2/51 aprovavam.
QUALITY_FINAL_MIN = float(os.getenv("QUALITY_FINAL_MIN", "60"))
SOFT_PENALTY_MAX   = float(os.getenv("SOFT_PENALTY_MAX", "25"))   # teto da penalidade soft somada
RVOL_HARD_MIN      = float(os.getenv("RVOL_HARD_MIN", "0.50"))    # abaixo disso, bloqueia mesmo em soft mode

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

# ==== STOP DUPLO + RISCO ADAPTATIVO (RFC stop-duplo 23/08) ====
# STOP1 (tecnico, extremo recente + buffer pequeno) e STOP2 (estrutural,
# extremo mais amplo + buffer maior) sao SEMPRE calculados e registrados
# (observacao), mas so passam a determinar o `stop` real (o que efetivamente
# fecha o trade em verificar_resultados_automatico) e o position sizing
# quando STOP_DUPLO_ATIVO estiver ligado. Default OFF preserva 100% o
# comportamento atual (stop = extremo tecnico de sempre). Objetivo do
# periodo OFF: acumular REGISTRO OBRIGATORIO (stop1_tocado, salvo_por_stop2,
# mfe_apos_stop1) pra medir empiricamente quantas operacoes o STOP1 mata
# que teriam batido TP, antes de ligar de vez.
STOP_DUPLO_ATIVO  = os.getenv("STOP_DUPLO_ATIVO", "False").strip().lower() in ("1", "true", "yes", "on")
STOP2_ATR_BUFFER  = float(os.getenv("STOP2_ATR_BUFFER", "1.0"))   # buffer maior que o STOP1 (0.1x ATR) -- usado quando RISCO_ADAPTATIVO_ATIVO=False

# RFC protecao-liquidez 23/08 (2a rodada) — pedido explicito do usuario:
# "se o mercado estiver fraco, menos risco; se estiver forte, stop maior
# pra chance de alvo maior". O buffer do STOP2 passa a escalar com o mesmo
# regime de saude usado no risco adaptativo (tier_qualidade) em vez de ser
# fixo pra todo sinal. So tem efeito quando RISCO_ADAPTATIVO_ATIVO=True
# (mesma flag que já liga o resto do regime de saude); com ela desligada,
# usa STOP2_ATR_BUFFER fixo, igual sempre foi.
STOP2_BUFFER_MUITO_SAUDAVEL = float(os.getenv("STOP2_BUFFER_MUITO_SAUDAVEL", "1.5"))
STOP2_BUFFER_SAUDAVEL       = float(os.getenv("STOP2_BUFFER_SAUDAVEL",       "1.2"))
STOP2_BUFFER_NORMAL         = float(os.getenv("STOP2_BUFFER_NORMAL",         "1.0"))
STOP2_BUFFER_FRACO          = float(os.getenv("STOP2_BUFFER_FRACO",          "0.6"))

# Risco adaptativo por regime de saude — reaproveita a classificacao de
# qualidade ja existente (tier_qualidade: APEX/PRO/SETUP/ABAIXO, RFC
# reequilibrio 22/08), nao cria criterio novo. Default OFF: risco continua
# fixo em RISCO_PCT pra todo sinal, igual sempre foi.
RISCO_ADAPTATIVO_ATIVO = os.getenv("RISCO_ADAPTATIVO_ATIVO", "False").strip().lower() in ("1", "true", "yes", "on")
RISCO_MUITO_SAUDAVEL   = float(os.getenv("RISCO_MUITO_SAUDAVEL", "6.0"))  # tier_qualidade APEX  (🔥)
RISCO_SAUDAVEL         = float(os.getenv("RISCO_SAUDAVEL",       "4.0"))  # tier_qualidade PRO   (🟢)
RISCO_NORMAL           = float(os.getenv("RISCO_NORMAL",         "3.0"))  # tier_qualidade SETUP (🟡) = RISCO_PCT default
RISCO_FRACO            = float(os.getenv("RISCO_FRACO",          "1.0"))  # tier_qualidade ABAIXO(🔴)


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
