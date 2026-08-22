"""
K12 Analista Sênior — IA raciocina como trader experiente
Analisa dados e decide como um operador vendo o gráfico
"""
import httpx, json, os

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

async def analisar_como_senior(dados: dict) -> dict:
    """
    Envia dados do mercado para Claude analisar como trader sênior.
    Retorna decisão: ENTRAR / AGUARDAR / IGNORAR + justificativa
    """
    if not ANTHROPIC_KEY:
        return {"decisao": "SEM_API", "justificativa": "API não configurada"}

    sym    = dados.get("symbol","").replace("/USDT:USDT","")
    dir    = dados.get("direcao","")
    tf     = dados.get("timeframe","")
    score  = dados.get("score", 0)
    rvol   = dados.get("rvol", 0)
    rsi    = dados.get("rsi", 50)
    adx    = dados.get("adx", 0)
    macd_h = dados.get("macd_hist", 0)
    e10    = dados.get("ema10", 0)
    e21    = dados.get("ema21", 0)
    e50    = dados.get("ema50", 0)
    e200   = dados.get("ema200", 0)
    sweep  = dados.get("sweep_ok", False)
    ob     = dados.get("ob_detectado", False)
    fvg    = dados.get("fvg_detectado", False)
    ctx    = dados.get("tf_contexto","")
    ctx_ok = dados.get("ctx_confirma", False)
    rr     = dados.get("rr", 0)
    entrada= dados.get("entrada", 0)
    stop   = dados.get("stop", 0)
    tp1    = dados.get("tp1", 0)
    sessao = dados.get("sessao","")
    confs  = dados.get("confirmacoes_smc", [])

    prompt = f"""Você é um trader sênior com 15 anos de experiência em futuros de criptomoedas e mercados financeiros. 
Analise este setup e decida como um profissional que está olhando o gráfico agora.

ATIVO: {sym} | DIREÇÃO: {dir} | TIMEFRAME: {tf}
SESSÃO: {sessao}

INDICADORES:
- MACD Histograma: {macd_h:.6f} ({'positivo ↑' if macd_h > 0 else 'negativo ↓'})
- RSI: {rsi:.1f} ({'sobrecomprado ⚠️' if rsi > 70 else 'sobrevendido ⚠️' if rsi < 30 else 'zona neutra ✓'})
- ADX: {adx:.1f} ({'tendência forte ✓' if adx > 25 else 'fraco'})
- RVOL: {rvol:.2f} ({'volume institucional ✓' if rvol >= 1.5 else 'volume normal' if rvol >= 0.8 else 'volume fraco ⚠️'})
- EMA10: {e10:.6f} | EMA21: {e21:.6f} | EMA50: {e50:.6f} | EMA200: {e200:.6f}
- EMAs: {'alinhadas ✓' if (e10>e21>e50>e200 and dir=='LONG') or (e10<e21<e50<e200 and dir=='SHORT') else 'parcial' if (e10>e21 and dir=='LONG') or (e10<e21 and dir=='SHORT') else 'desalinhadas ⚠️'}

SMC:
- Liquidez capturada: {'SIM ✓' if sweep else 'NÃO ⚠️'}
- Order Block: {'SIM ✓' if ob else 'NÃO'}
- Fair Value Gap: {'SIM ✓' if fvg else 'NÃO'}
- Contexto {ctx}: {'CONFIRMANDO ✓' if ctx_ok else 'NÃO CONFIRMA ⚠️'}

NÍVEIS:
- Entrada: {entrada} | Stop: {stop} | TP1: {tp1}
- RR: {rr} | Score: {score}/100

CONFIRMAÇÕES: {', '.join(confs) if confs else 'nenhuma'}

Como trader sênior, responda em JSON:
{{
  "decisao": "ENTRAR" ou "AGUARDAR" ou "IGNORAR",
  "confianca": 0-100,
  "justificativa": "máximo 2 linhas explicando sua decisão",
  "risco": "BAIXO" ou "MEDIO" ou "ALTO",
  "observacao": "1 dica importante para esta operação"
}}

Seja direto e honesto. Se não vale o risco, diga IGNORAR. Se precisa esperar confirmação, diga AGUARDAR."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            if r.status_code == 200:
                texto = r.json()["content"][0]["text"]
                # Extrair JSON da resposta
                inicio = texto.find("{")
                fim    = texto.rfind("}") + 1
                if inicio >= 0 and fim > inicio:
                    return json.loads(texto[inicio:fim])
    except Exception as e:
        pass

    return {"decisao": "ERRO", "justificativa": "Falha na análise IA"}
