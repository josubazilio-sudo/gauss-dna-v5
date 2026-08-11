"""
K11 V58.1 — Gestão de Trade pós-entrada.

Fonte única de verdade: config.py. Este módulo centraliza as regras de
gestão (BE, proteção monotônica de stop, trailing por setup e BOS Age)
e não altera nada na lógica de entrada do K11.
"""
import logging

from config import (BE_TRIGGER_R, BE_EXIGE_H1_FECHADO, BOS_AGE_MAX_CANDLES,
                    TRAILING_ATR_MULT, TRAILING_SETUPS)

logger = logging.getLogger(__name__)

_ACENTOS = {
    "Á": "A", "Â": "A", "Ã": "A", "À": "A",
    "É": "E", "Ê": "E",
    "Í": "I",
    "Ó": "O", "Ô": "O", "Õ": "O",
    "Ú": "U",
    "Ç": "C",
}

_PALAVRAS_REVERSAO  = ("REVERSA", "SWEEP", "LIQUIDEZ", "LIQUIDADE")
_PALAVRAS_TENDENCIA = ("TENDENC", "CONTINUAC", "TREND FOLLOW", "QUALIDADE")
_PALAVRAS_BREAKOUT  = ("BREAKOUT", "ROMPIMENT")


def _sem_acentos(texto: str) -> str:
    for k, v in _ACENTOS.items():
        texto = texto.replace(k, v)
    return texto


def normalizar_setup(setup_nome) -> str:
    """Normaliza o nome do setup para a família canônica (REVERSAO,
    TENDENCIA, BREAKOUT). Uppercase, remove acentos e espaços duplicados,
    e reconhece variações equivalentes sem depender de igualdade exata."""
    if not setup_nome:
        return ""
    nome = _sem_acentos(str(setup_nome).upper())
    nome = " ".join(nome.split())
    if any(k in nome for k in _PALAVRAS_REVERSAO):
        return "REVERSAO"
    if any(k in nome for k in _PALAVRAS_TENDENCIA):
        return "TENDENCIA"
    if any(k in nome for k in _PALAVRAS_BREAKOUT):
        return "BREAKOUT"
    return nome


def config_trailing(setup_nome):
    """Retorna (familia, config de trailing) para o setup dado."""
    familia = normalizar_setup(setup_nome)
    cfg = TRAILING_SETUPS.get(familia) or TRAILING_SETUPS["DEFAULT"]
    return familia, cfg


def proteger_stop(stop_anterior, novo_stop, lado):
    """Regra fundamental do stop: só anda a favor da operação, nunca recua.
    LONG: nunca menor que o anterior. SHORT: nunca maior que o anterior."""
    if lado == "SHORT":
        return min(stop_anterior, novo_stop)
    return max(stop_anterior, novo_stop)


def aplicar_be_stop(stop_atual, entrada, lado):
    """Depois do BE ativado, o stop mínimo é a entrada (protegido)."""
    return proteger_stop(stop_atual, entrada, lado)


def calcular_r(entrada, stop, preco, lado) -> float:
    risco = abs(entrada - stop)
    if not risco:
        return 0.0
    if lado == "LONG":
        return (preco - entrada) / risco
    return (entrada - preco) / risco


def tf_display(tf) -> str:
    if not tf:
        return ""
    return "H1" if str(tf).lower().startswith("1h") else str(tf).upper()


def avaliar_be(engine, symbol, direcao, entrada, stop, df=None):
    """BE V58.1: só ativa com R >= BE_TRIGGER_R calculado sobre o candle
    H1 JÁ FECHADO (confirmação de fechamento H1 quando BE_EXIGE_H1_FECHADO).
    Retorna (ativar, r, motivo)."""
    if df is None:
        try:
            df = engine._calc(engine._fetch(symbol, "1h", limit=60))
        except Exception as e:
            return False, 0.0, f"erro fetch: {e}"
    if df is None or len(df) < 3:
        return False, 0.0, "df insuficiente"
    r_h1 = float(df.iloc[-2]["close"])
    r = calcular_r(entrada, stop, r_h1, direcao)
    if not BE_EXIGE_H1_FECHADO:
        if r >= BE_TRIGGER_R:
            return True, r, "BE ATIVADO (H1 nao exigido)"
        return False, r, "R insuficiente"
    if r >= BE_TRIGGER_R:
        return True, r, "BE ATIVADO\nH1 CONFIRMADO\nSTOP=ENTRY"
    return False, r, "R insuficiente"


def candidato_trailing(df, cfg, entrada, stop_original, direcao):
    """Trailing por setup: calcula R atual (candle fechado do TF da família)
    e o candidato de stop (múltiplo de ATR). Se o trigger de R da família
    ainda não foi atingido, retorna None (não mexe no stop)."""
    if df is None or len(df) < 3:
        return None, 0.0
    r = df.iloc[-2]
    close = float(r["close"])
    atr = float(r["atr"])
    r_atual = calcular_r(entrada, stop_original, close, direcao)
    trigger_r = float(cfg.get("trigger_r", 0.0) or 0.0)
    if trigger_r > 0 and r_atual < trigger_r:
        return None, r_atual
    trail_dist = TRAILING_ATR_MULT * atr
    candidato = (close - trail_dist) if direcao == "LONG" else (close + trail_dist)
    return candidato, r_atual


def bos_age(engine, df, direcao, max_age=None):
    """Idade do BOS/CHoCH REutilizando a detecção real já existente no K11
    (engine._bos_idade). NÃO cria detector simplificado novo.
    Retorna (idade, ok): ok = idade <= max_age."""
    limite = BOS_AGE_MAX_CANDLES if max_age is None else max_age
    try:
        idade = int(engine._bos_idade(df, direcao))
    except Exception:
        idade = 0
    return idade, (idade <= limite)