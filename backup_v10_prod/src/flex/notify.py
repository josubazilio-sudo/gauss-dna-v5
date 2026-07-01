"""SINAIS TOP — Notificações Telegram + Diagnóstico Avançado"""

import logging
import aiohttp
from datetime import datetime, timezone
from collections import Counter

from flex.config import TG_TOKEN, TG_CHATID, CAPITAL, TP1_ATR_MULT, TP2_ATR_MULT, SL_ATR_MULT, SCORE_BRONZE_MIN
from flex.score import calcular_gestao_operacao

logger = logging.getLogger(__name__)


def _fmt(v):
    if v is None:
        return "0"
    v = float(v)
    if abs(v) < 0.01:
        return f"{v:.6f}"
    if abs(v) < 1:
        return f"{v:.4f}"
    return f"{v:.2f}"


def _html(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fluxo_desc(flow_data, direction):
    delta = flow_data.get("DELTA", 0)
    rvol = flow_data.get("RVOL", 1.0)
    vol_crescente = flow_data.get("VOLUME_CRESCENTE", False)
    if direction == "long" and delta > 0:
        if vol_crescente and rvol > 2.0:
            return "🟢 Muito Forte"
        return "🟢 Forte" if vol_crescente else "🟢 Moderado"
    if direction == "short" and delta < 0:
        if vol_crescente and rvol > 2.0:
            return "🔴 Muito Forte"
        return "🔴 Forte" if vol_crescente else "🔴 Moderado"
    if abs(delta) > 0:
        return "⚪ Neutro"
    return "⚪ Fraco"


def _rvol_band(rvol):
    if rvol < 0.80:
        return "🔴 REPROVADO"
    if rvol < 1.20:
        return "⚪ Neutro"
    if rvol < 2.00:
        return "🟢 Bom"
    if rvol < 3.00:
        return "🟢 Muito Bom"
    return "🟢 Excelente"


def _adx_band(adx):
    if adx < 18:
        return "🔴 REPROVADO"
    if adx < 25:
        return "⚪ Neutro"
    if adx < 35:
        return "🟢 Bom"
    if adx < 50:
        return "🟢 Muito Bom"
    return "🟢 Excelente"


async def send_signal(session, symbol, direction, preco, score,
                      classificacao, confianca, rsi, adx, rvol,
                      trend_text, flow_data, kalman_dir,
                      stop_loss, stop_pct, tp1, funding_rate,
                      timeframe, velas_fortes,
                      setup=None,
                      timing_index=None, atr_pct=0, tp2=None,
                      regime_data=None, prioridade=None, atr_regime=None,
                      sl_atr_mult=None, conviction_score=None):
    if not TG_TOKEN or not TG_CHATID:
        logger.warning("TG_TOKEN ou TG_CHATID nao configurados")
        return False

    agora = datetime.now(timezone.utc).strftime("%H:%M UTC — %d/%m/%Y")
    dir_emoji = "🟢" if direction == "LONG" else "🔴"
    grade_emoji = {"OURO_SUPREMO": "💎", "OURO": "🥇", "PRATA": "🥈", "BRONZE": "🥉"}.get(classificacao, "📊")
    fluxo = _fluxo_desc(flow_data, direction.lower())

    sl_pct_str = _fmt(stop_pct)
    tp1_ganho = float(TP1_ATR_MULT) / float(SL_ATR_MULT) if SL_ATR_MULT else 0
    gestao = calcular_gestao_operacao(
        score, classificacao, adx, rvol, timing_index,
        flow_data, direction, kalman_dir, stop_pct
    )
    gestao_lote = gestao["perfil"]

    funding_str = f"{float(funding_rate) * 100:.4f}%" if funding_rate is not None else "—"

    stars = _star_rating(score, classificacao)
    alavancagem = gestao["alavancagem"]
    risco_pct = gestao["risco_pct"]
    colateral = float(CAPITAL * risco_pct * gestao["mult_entrada"])
    posicao_total = colateral * alavancagem
    prob = min(50 + score // 2, 95)
    regime_data = regime_data or {}
    regime = regime_data.get("regime", "—")
    prioridade = prioridade or classificacao
    ctx = regime_data.get("context_scores", {})
    
    conviction_label = "Fraca"
    if conviction_score >= 95: conviction_label = "Extrema"
    elif conviction_score >= 85: conviction_label = "Muito Alta"
    elif conviction_score >= 75: conviction_label = "Alta"
    elif conviction_score >= 65: conviction_label = "Moderada"
    
    # Setup V9.0
    setup_name = setup.get("name", "N/A") if setup else "Desconhecido"
    setup_quality = "★" * setup.get("quality", 3) if setup else "★★★"
    setup_prob = f"{setup.get('prob', 0) * 100:.0f}%" if setup else "N/A"
    
    tp2_ganho = float(TP2_ATR_MULT) / float(SL_ATR_MULT) if float(SL_ATR_MULT) else 0
    half_pos = posicao_total / 2
    if direction == "LONG":
        tp1_gain_dol = half_pos * (tp1 - preco) / preco if preco > 0 and tp1 else 0
        tp2_gain_dol = half_pos * (tp2 - preco) / preco if preco > 0 and tp2 else 0
        breakeven_gain = half_pos * (preco - preco) / preco
    else:
        tp1_gain_dol = half_pos * (preco - tp1) / preco if preco > 0 and tp1 else 0
        tp2_gain_dol = half_pos * (preco - tp2) / preco if preco > 0 and tp2 else 0
        breakeven_gain = half_pos * (preco - preco) / preco
    ganho_total = tp1_gain_dol + tp2_gain_dol
    trailing_label = f"→ TP1 fecha 50%, saldo vai p/ BE, restante trailing até TP Final"

    lines = [
        f"🚨 ⚡ SINAIS TOP",
        "",
        f"{dir_emoji} {direction}",
        f"💎 {_html(symbol)} | 🕐 {_html(timeframe)}",
        f"{stars}",
        "",
        f"📊 Setup: {setup_name}",
        f"⭐ Qualidade: {setup_quality}",
        f"📈 Probabilidade: {setup_prob}",
        f"🏛 Score Institucional: {score}/100",
        "",
        f"🏆 {grade_emoji} {classificacao}",
        f"🏛 Regime: {_html(regime)} | Prioridade: {_html(prioridade)}",
        f"🎯 Confiança: {confianca}%",
        f"💎 Convicção: {conviction_score}/100 ({conviction_label})",
        "",
        f"💰 Entrada: ${_fmt(preco)}",
        f"🛑 Stop: ${_fmt(stop_loss)} ({_fmt(sl_pct_str)}%)",
        f"🎯 TP1 (50%): ${_fmt(tp1)} (+{_fmt(tp1_ganho)}R / +${_fmt(tp1_gain_dol)})",
        f"🎯 TP Final (50%): ${_fmt(tp2)} (+{_fmt(tp2_ganho)}R / +${_fmt(tp2_gain_dol)})",
        f"💵 Ganho Total Esperado: +${_fmt(ganho_total)}",
        f"📋 Estratégia: {trailing_label}",
        "",
        f"📊 RSI: {rsi:.0f}",
        f"📈 RVOL: {rvol:.2f}x ({_rvol_band(rvol)})",
        f"📉 ADX: {adx:.0f} ({_adx_band(adx)})",
        f"📦 Fluxo: {fluxo}",
        f"🧭 Kalman: {_html(kalman_dir)}",
        f"📍 Tendência: {_html(trend_text)}",
        f"🔥 Velas Fortes: {velas_fortes}",
        f"⏱ Timing: {timing_index}/100" if timing_index is not None else "",
        f"📊 ATR: {atr_pct*100:.1f}% ({_html(atr_regime or 'ATR')}) | Stop: {sl_atr_mult or SL_ATR_MULT} ATR",
        f"🎲 Probabilidade: {prob}%",
        f"🧬 Contexto: Trend {ctx.get('trend', 0)} | Vol {ctx.get('volume', 0)} | Mom {ctx.get('momentum', 0)} | SMC {ctx.get('smart_money', 0)} | Risk {ctx.get('risk', 0)}",
        "",
        f"📐 Gestão (lote {gestao_lote})",
        f"Risco: {_fmt(risco_pct * 100)}% | Colateral: ${_fmt(colateral)} | Posição: ${_fmt(posicao_total)} | {alavancagem}x",
        f"TP1: ${_fmt(tp1_gain_dol)} | TP Final: ${_fmt(tp2_gain_dol)}",
        f"💹 Funding: {funding_str}",
        f"⏰ {agora}",
    ]
    texto = "\n".join(lines)

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        async with session.post(url, json={"chat_id": TG_CHATID, "text": texto},
                                timeout=aiohttp.ClientTimeout(total=10)) as r:
            data = await r.json()
            if data.get("ok"):
                logger.info("Sinal enviado: %s %s %s Score:%s", direction, symbol, classificacao, score)
                return True
            logger.error("Telegram REJEITOU o sinal: %s | Resp: %s", data.get("description"), data)
            return False
    except Exception as e:
        logger.error("Falha CRÍTICA ao enviar para Telegram: %s", e)
        return False


async def send_diagnostic(session, diag):
    """Envia diagnóstico avançado ao final do ciclo (dividido se necessário)."""
    if not TG_TOKEN or not TG_CHATID:
        return
    texto = diag.build_diagnostic_message()
    logger.info("=== DIAGNOSTICO ===\n%s", texto.encode("ascii", "replace").decode())
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    limite = 4096
    partes = [texto[i:i+limite] for i in range(0, len(texto), limite)]
    for parte in partes:
        try:
            async with session.post(url, json={"chat_id": TG_CHATID, "text": parte},
                                    timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json()
                if not data.get("ok"):
                    logger.warning("Diagnostico Telegram: %s", data.get("description"))
        except Exception as e:
            logger.warning("Diagnostico falhou: %s", e)


class Diagnostics:
    def __init__(self):
        self.total_analisadas = 0
        self.total_aprovadas = 0
        self.total_recusadas = 0
        self.ouro_supremo = 0
        self.bronze = 0
        self.prata = 0
        self.ouro = 0
        self.sinais = []
        self.recusados = []
        self.todos_resultados = []
        self.bloqueadores = Counter()
        self.motivos_recusa = Counter()
        self.inicio = None
        self.fim = None
        self.score_list = []
        self.rvol_aprovados = []
        self.adx_aprovados = []
        self.rsi_aprovados = []
        self.atr_aprovados = []
        self.velas_list = []
        self.rsi_medio_geral = []
        self.adx_medio_geral = []
        self.rvol_medio_geral = []
        self.volume_medio_geral = []
        self.funding_list = []
        self.fluxo_forte_count = 0
        self.kalman_counts = Counter()
        self.direcao_count = Counter()
        self.btc_trend = ""
        self.eth_trend = ""
        self.trades = None
        self.timing_list = []
        self.dados_simulacao = []
        self.kalman_alinhado_count = 0
        self.fluxo_forte_count_diag = 0
        self.entradas_contra_tendencia = 0
        self.lateralizacao_bloqueios = 0
        self.quase_aprovados_detalhes = []
        self.presinais = []
        self.kalman_side_aprovados = 0
        self.kalman_bloqueios_totais = 0
        self.qualidade_sem_kalman = []
        self.only_rvol_blocked = 0
        self.score_stage = []  # (symbol, direction, score, motivo) - moedas que chegaram ao Score
        self.score_penalizados = []  # (symbol, direction, penalty, motivos, score_original, score_final)

        # Debug do Scanner
        self.moedas_carregadas = 0
        self.moedas_validas = 0
        self.candles_recebidos = 0
        self.candles_invalidos = 0
        self.sem_volume = 0
        self.sem_atr = 0
        self.sem_rsi = 0
        self.sem_adx = 0
        self.sem_rvol = 0
        self.sem_funding = 0
        self.erros_api = 0
        self.tempo_scanner = 0.0

        self.funil_exchange = 0
        self.funil_liquidez = 0
        self.funil_volume = 0
        self.funil_atr = 0
        self.funil_rsi = 0
        self.funil_adx = 0
        self.funil_rvol = 0
        self.funil_tendencia = 0
        self.funil_fluxo = 0
        self.funil_kalman = 0
        self.funil_score = 0
        self.funil_aprovadas = 0
        self.funil_recusadas = 0

        self.bloqueador_liquidez = 0
        self.bloqueador_rvol = 0
        self.bloqueador_adx = 0
        self.bloqueador_rsi = 0
        self.bloqueador_score = 0
        self.bloqueador_kalman = 0
        self.bloqueador_fluxo = 0
        self.bloqueador_tendencia = 0
        self.bloqueador_atr = 0
        self.bloqueador_funding = 0
        self.bloqueador_exaustao = 0
        self.bloqueador_multi_timeframe = 0
        self.bloqueador_tp1_minimo = 0
        self.bloqueador_mm200 = 0

        self.scanner_ok = True
        self.scanner_motivo = ""
        self.scan_erros_lista = []

    def start(self):
        self.inicio = datetime.now(timezone.utc)

    def finish(self):
        self.fim = datetime.now(timezone.utc)

    def record_analise(self, symbol, direction, score, aprovado,
                       motivo=None, rsi=None, adx=None, rvol=None,
                       volume=None, atr=None, velas=None, fluxo_forte=None,
                       kalman_dir=None, timing_index=None, tendencia=None):
        self.total_analisadas += 1
        self.todos_resultados.append({
            "symbol": symbol, "direction": direction, "score": score,
            "aprovado": aprovado, "motivo": motivo,
            "rsi": rsi, "adx": adx, "rvol": rvol, "volume": volume,
            "atr": atr, "velas": velas,
        })
        if rsi is not None:
            self.rsi_medio_geral.append(rsi)
        if adx is not None:
            self.adx_medio_geral.append(adx)
        if rvol is not None:
            self.rvol_medio_geral.append(rvol)
        if volume is not None:
            self.volume_medio_geral.append(volume)
        if aprovado:
            self.total_aprovadas += 1
            self.score_list.append(score)
            if rsi is not None:
                self.rsi_aprovados.append(rsi)
            if adx is not None:
                self.adx_aprovados.append(adx)
            if rvol is not None:
                self.rvol_aprovados.append(rvol)
            if atr is not None:
                self.atr_aprovados.append(atr)
            if velas is not None:
                self.velas_list.append(velas)
            if fluxo_forte:
                self.fluxo_forte_count += 1
                self.fluxo_forte_count_diag += 1
            if kalman_dir:
                self.kalman_counts[kalman_dir] += 1
                k = kalman_dir if isinstance(kalman_dir, str) else "SIDE"
                if (direction == "LONG" and k == "UP") or (direction == "SHORT" and k == "DOWN"):
                    self.kalman_alinhado_count += 1
                    self.qualidade_sem_kalman.append(max(0, score - 13))
                if k == "SIDE":
                    self.kalman_side_aprovados += 1
                    self.qualidade_sem_kalman.append(min(100, score + 3))
                if (direction == "LONG" and k == "DOWN") or (direction == "SHORT" and k == "UP"):
                    self.qualidade_sem_kalman.append(min(100, score + 5))
            if direction in ("LONG", "SHORT"):
                self.direcao_count[direction] += 1
            if timing_index is not None:
                self.timing_list.append(timing_index)
            if tendencia and direction:
                dir_lower = direction.lower()
                if (dir_lower == "long" and tendencia in ("baixa", "baixa_moderada")) or \
                   (dir_lower == "short" and tendencia in ("alta", "alta_moderada")):
                    self.entradas_contra_tendencia += 1
        else:
            self.total_recusadas += 1
            if motivo and "kalman" in motivo:
                self.kalman_bloqueios_totais += 1
            if motivo:
                self.motivos_recusa[motivo] += 1
                self.recusados.append((symbol, score, motivo))

    def record_sinal(self, classificacao, symbol, direction, score, motivo):
        self.sinais.append({
            "classificacao": classificacao,
            "symbol": symbol,
            "direction": direction,
            "score": score,
            "motivo": motivo,
        })
        if classificacao == "OURO_SUPREMO":
            self.ouro_supremo += 1
        elif classificacao == "OURO":
            self.ouro += 1
        elif classificacao == "PRATA":
            self.prata += 1
        elif classificacao == "BRONZE":
            self.bronze += 1

    def record_bloqueio(self, motivo):
        self.bloqueadores[motivo] += 1

    def record_funding(self, rate):
        if rate is not None:
            self.funding_list.append(float(rate))

    def record_scanner_debug(self, carregadas, validas, candles_ok, candles_inv,
                              erros_api, tempo):
        self.moedas_carregadas = carregadas
        self.moedas_validas = validas
        self.candles_recebidos = candles_ok
        self.candles_invalidos = candles_inv
        self.erros_api = erros_api
        self.tempo_scanner = tempo

    def record_sem_indicador(self, tipo):
        if tipo == "volume":
            self.sem_volume += 1
        elif tipo == "atr":
            self.sem_atr += 1
        elif tipo == "rsi":
            self.sem_rsi += 1
        elif tipo == "adx":
            self.sem_adx += 1
        elif tipo == "rvol":
            self.sem_rvol += 1
        elif tipo == "funding":
            self.sem_funding += 1

    def record_funil(self, etapa):
        if etapa == "exchange":
            self.funil_exchange += 1
        elif etapa == "liquidez":
            self.funil_liquidez += 1
        elif etapa == "volume":
            self.funil_volume += 1
        elif etapa == "atr":
            self.funil_atr += 1
        elif etapa == "rsi":
            self.funil_rsi += 1
        elif etapa == "adx":
            self.funil_adx += 1
        elif etapa == "rvol":
            self.funil_rvol += 1
        elif etapa == "tendencia":
            self.funil_tendencia += 1
        elif etapa == "fluxo":
            self.funil_fluxo += 1
        elif etapa == "kalman":
            self.funil_kalman += 1
        elif etapa == "score":
            self.funil_score += 1
        elif etapa == "aprovada":
            self.funil_aprovadas += 1
        elif etapa == "recusada":
            self.funil_recusadas += 1

    def record_bloqueador(self, tipo):
        if tipo == "liquidez":
            self.bloqueador_liquidez += 1
        elif tipo == "rvol":
            self.bloqueador_rvol += 1
        elif tipo == "adx":
            self.bloqueador_adx += 1
        elif tipo == "rsi":
            self.bloqueador_rsi += 1
        elif tipo == "score":
            self.bloqueador_score += 1
        elif tipo == "kalman":
            self.bloqueador_kalman += 1
        elif tipo == "fluxo":
            self.bloqueador_fluxo += 1
        elif tipo == "tendencia":
            self.bloqueador_tendencia += 1
        elif tipo == "atr":
            self.bloqueador_atr += 1
        elif tipo == "funding":
            self.bloqueador_funding += 1
        elif tipo == "mm200":
            self.bloqueador_mm200 += 1
        elif tipo == "exaustao":
            self.bloqueador_exaustao += 1
        elif tipo == "multi_timeframe":
            self.bloqueador_multi_timeframe += 1
        elif tipo == "tp1_minimo":
            self.bloqueador_tp1_minimo += 1

    def record_erro_api(self, msg):
        self.scanner_ok = False
        self.scanner_motivo = msg
        self.scan_erros_lista.append(msg)

    def _avg(self, lst):
        return round(sum(lst) / len(lst), 1) if lst else 0

    def _pct(self, part, total):
        return round(part / total * 100, 1) if total else 0

    def _distribuicao_scores(self):
        if not self.score_list:
            return "  (sem dados)"
        faixas = {"60-66": 0, "67-72": 0, "73-79": 0, "80+"  : 0}
        for s in self.score_list:
            if s < 67: faixas["60-66"] += 1
            elif s < 73: faixas["67-72"] += 1
            elif s < 80: faixas["73-79"] += 1
            else: faixas["80+"] += 1
        return "\n".join(f"  {k}: {'█' * v}{v}" for k, v in faixas.items() if v > 0)

    def _tempo_ultimo_sinal(self, cls):
        for s in reversed(self.sinais):
            if s["classificacao"] == cls:
                return "neste ciclo"
        return "—"

    def _format_falta(self, motivo):
        if motivo.startswith("rvol_"):
            v = motivo.split("_")
            return f"+RVOL ({v[-1]})" if len(v) > 1 else "+RVOL"
        if motivo.startswith("adx_"):
            v = motivo.split("_")
            return f"+ADX ({v[-1]})" if len(v) > 1 else "+ADX"
        if motivo.startswith("timing_"):
            v = motivo.split("_")
            return f"+Timing ({v[-1]})" if len(v) > 1 else "+Timing"
        if motivo == "sem_categoria":
            return "+Score/ADX/RVOL"
        if "kalman" in motivo:
            return "+Kalman"
        if "score_baixo" in motivo:
            return "+Score"
        return motivo

    def _safety_checks(self):
        erros = []
        if self.moedas_carregadas == 0:
            erros.append("ERRO: Lista de ativos vazia")
        if self.candles_recebidos == 0 and self.moedas_carregadas > 0:
            erros.append("ERRO: Histórico insuficiente — candles não recebidos")
        if self.sem_volume > self.moedas_validas * 0.5:
            erros.append("ERRO: Volume não recebido da Exchange (>50% sem volume)")
        if self.sem_rvol > self.moedas_validas * 0.5:
            erros.append("ERRO: RVOL não calculado para >50% dos ativos")
        if self.sem_rsi > self.moedas_validas * 0.5:
            erros.append("ERRO: RSI não calculado para >50% dos ativos")
        if self.sem_adx > self.moedas_validas * 0.5:
            erros.append("ERRO: ADX não calculado para >50% dos ativos")
        if self.total_analisadas == 0 and self.moedas_validas > 0:
            erros.append("ERRO: Nenhum ativo passou pelos filtros")
        return erros

    def _build_grade_report(self):
        if not self.trades:
            return []
        lines = []
        grades_map = {"OURO_SUPREMO": "💎", "OURO": "🥇", "PRATA": "🥈", "BRONZE": "🥉"}
        exit_labels = {"stop": "🛑 Stop", "be": "⚪ BE", "tp1_trail": "🔷 TP1+Trail", "tp_final": "🟢 TP Final"}
        report = self.trades.grade_report()
        for grade, emoji in grades_map.items():
            g = report.get(grade)
            if not g:
                continue
            lines.append(f"  {emoji} {grade} ({g['total']} ops)")
            lines.append(f"    WR: {g['winrate']}% | PF: {g['pf']} | R médio: {g['r_medio']}")
            exits_list = sorted(g["exits"].items(), key=lambda x: -x[1]["count"])
            for er, data in exits_list:
                er_label = exit_labels.get(er, er)
                wr_exit = round(data["wins"] / data["count"] * 100, 1) if data["count"] > 0 else 0
                lines.append(f"    {er_label}: {data['count']}x (WR {wr_exit}%, R {data['total_r']:.2f})")
        return lines

    def build_diagnostic_message(self):
        dur = (self.fim - self.inicio).total_seconds() if self.fim and self.inicio else 0
        analises_por_min = round(self.total_analisadas / (dur / 60), 1) if dur > 0 else 0

        top_aprov = sorted(self.sinais, key=lambda s: s["score"], reverse=True)[:5] if self.sinais else []
        piores = sorted(self.recusados, key=lambda r: r[1])[:5] if self.recusados else []
        piores_ativos = [(r[0], r[2]) for r in piores]
        quase_aprov = sorted(
            [r for r in self.recusados if r[1] >= SCORE_BRONZE_MIN - 5],
            key=lambda r: r[1], reverse=True
        )[:5] if self.recusados else []

        safety_erros = self._safety_checks()
        self.scanner_ok = len(safety_erros) == 0
        self.scanner_motivo = "; ".join(safety_erros[:2])

        blockers_top = self.motivos_recusa.most_common(10)
        funding_medio = self._avg(self.funding_list)
        total = max(self.total_analisadas, 1)

        follow_through = self._pct(self.total_aprovadas, self.total_analisadas)
        vol_liq = min(25, round(self._avg(self.volume_medio_geral) / 2_000_000 * 10)) if self.volume_medio_geral else 0
        adx_score = min(20, round(self._avg(self.adx_medio_geral) * 0.5)) if self.adx_medio_geral else 0
        rvol_score = min(20, round(self._avg(self.rvol_medio_geral) * 8)) if self.rvol_medio_geral else 0
        mom_rsi = abs(50 - (self._avg(self.rsi_medio_geral) if self.rsi_medio_geral else 50))
        mom_score = min(20, max(0, 20 - round(mom_rsi * 0.8)))
        flow_ft = min(15, round(follow_through * 0.15))
        indice = min(100, vol_liq + adx_score + rvol_score + mom_score + flow_ft)
        vol_medio = self._avg(self.volume_medio_geral)
        liq_text = _qualidade_liquidez(vol_medio)
        rsi_medio = self._avg(self.rsi_medio_geral)
        adx_medio = self._avg(self.adx_medio_geral)
        mom_text = _qualidade_momentum(rsi_medio, adx_medio)
        fluxo_text = _fluxo_geral(self.direcao_count)
        sinais_total = len(self.sinais)

        if indice >= 75: mkt_quality = "Excelente"
        elif indice >= 55: mkt_quality = "Bom"
        elif indice >= 35: mkt_quality = "Normal"
        else: mkt_quality = "Fraco"

        aggr = _agressividade(sinais_total, mkt_quality)
        ideal_qty = _qtde_ideal(sinais_total, mkt_quality)
        prob_media = min(50 + self._avg(self.score_list) // 2, 95) if self.score_list else 0

        n_aprov = max(self.total_aprovadas, 1)
        fluxo_forte_pct = self._pct(self.fluxo_forte_count, n_aprov)
        kalman_up_pct = self._pct(self.kalman_counts.get("UP", 0), n_aprov)
        kalman_down_pct = self._pct(self.kalman_counts.get("DOWN", 0), n_aprov)
        kalman_side_pct = self._pct(self.kalman_counts.get("SIDE", 0), n_aprov)
        qualidade_sem_kalman = self._avg(self.qualidade_sem_kalman)
        velas_media = round(self._avg(self.velas_list), 1) if self.velas_list else 0
        rsi_medio_geral = self._avg(self.rsi_medio_geral)
        adx_medio_geral = self._avg(self.adx_medio_geral)
        rvol_medio_geral = self._avg(self.rvol_medio_geral)

        lines = []

        # ── STATUS / CHECKLIST ──
        if not self.scanner_ok:
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("❌ SCANNER COM FALHA")
            for e in safety_erros[:5]:
                lines.append(f"  • {e}")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        else:
            ok_items = []
            if self.moedas_carregadas > 0: ok_items.append("✓ API conectada")
            if self.moedas_validas > 0: ok_items.append("✓ Exchange conectada")
            if self.candles_recebidos > 0: ok_items.append("✓ Candles recebidos")
            if rsi_medio_geral > 0: ok_items.append("✓ Indicadores calculados")
            if rvol_medio_geral > 0: ok_items.append("✓ RVOL calculado")
            if vol_medio > 0: ok_items.append("✓ Liquidez válida")
            ok_items.append("✓ Scanner funcionando")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("✅ RESUMO DO SCANNER")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            for item in ok_items:
                lines.append(f"  {item}")

        lines.append("")
        lines.append("===== DEBUG SCANNER =====")
        lines.append(f"Moedas carregadas: {self.moedas_carregadas}")
        lines.append(f"Moedas válidas: {self.moedas_validas}")
        lines.append(f"Candles recebidos: {self.candles_recebidos}")
        lines.append(f"Candles inválidos: {self.candles_invalidos}")
        lines.append(f"Sem volume: {self.sem_volume}")
        lines.append(f"Sem ATR: {self.sem_atr}")
        lines.append(f"Sem RSI: {self.sem_rsi}")
        lines.append(f"Sem ADX: {self.sem_adx}")
        lines.append(f"Sem RVOL: {self.sem_rvol}")
        lines.append(f"Sem Funding: {self.sem_funding}")
        lines.append(f"Erros de API: {self.erros_api}")
        lines.append(f"Tempo total scanner: {self.tempo_scanner:.1f}s")
        lines.append("========================")

        lines.append("")
        lines.append("===== ETAPAS DO SCANNER =====")
        lines.append(f"Moedas da Exchange........: {self.funil_exchange}")
        lines.append(f"Após filtro de liquidez...: {self.funil_liquidez}")
        lines.append(f"Após Volume...............: {self.funil_volume}")
        lines.append(f"Após ATR..................: {self.funil_atr}")
        lines.append(f"Após RSI..................: {self.funil_rsi}")
        lines.append(f"Após ADX..................: {self.funil_adx}")
        lines.append(f"Após RVOL.................: {self.funil_rvol}")
        lines.append(f"Após Tendência............: {self.funil_tendencia}")
        lines.append(f"Após Fluxo................: {self.funil_fluxo}")
        lines.append(f"Após Kalman...............: {self.funil_kalman}")
        lines.append(f"Após Score................: {self.funil_score}")
        lines.append(f"Aprovadas................: {self.funil_aprovadas}")
        lines.append(f"Recusadas................: {self.funil_recusadas}")
        lines.append("==============================")

        lines.append("")
        lines.append("===== TOP BLOQUEADORES =====")
        lines.append(f"Liquidez: {self.bloqueador_liquidez}")
        lines.append(f"RVOL: {self.bloqueador_rvol}")
        lines.append(f"ADX: {self.bloqueador_adx}")
        lines.append(f"RSI: {self.bloqueador_rsi}")
        lines.append(f"Score: {self.bloqueador_score}")
        lines.append(f"Kalman: {self.bloqueador_kalman}")
        lines.append(f"Fluxo: {self.bloqueador_fluxo}")
        lines.append(f"Tendência: {self.bloqueador_tendencia}")
        lines.append(f"ATR: {self.bloqueador_atr}")
        lines.append(f"Funding: {self.bloqueador_funding}")
        lines.append(f"Exaustão: {self.bloqueador_exaustao}")
        lines.append(f"Multi TF: {self.bloqueador_multi_timeframe}")
        lines.append(f"TP1 <$1: {self.bloqueador_tp1_minimo}")
        lines.append(f"MM200: {self.bloqueador_mm200}")
        lines.append("=============================")

        lines.append("")
        lines.append("===== MÉDIAS DO MERCADO =====")
        lines.append(f"RSI médio: {rsi_medio_geral}")
        lines.append(f"ADX médio: {adx_medio_geral}")
        lines.append(f"RVOL médio: {rvol_medio_geral}")
        lines.append(f"ATR médio: {self._avg(self.atr_aprovados)*100:.2f}%" if self.atr_aprovados else "ATR médio: —")
        lines.append(f"Volume médio: ${vol_medio:,.0f}")
        lines.append(f"Funding médio: {funding_medio:.4f}%" if funding_medio else "Funding médio: —")
        lines.append("==============================")

        # ── Original sections ──
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 DIAGNÓSTICO AVANÇADO — SINAIS TOP")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("🌍 QUALIDADE DO MERCADO")
        lines.append(f"Índice Institucional: {indice}/100")
        lines.append(f"")
        lines.append(f"Liquidez ({liq_text}) — Vol médio ${vol_medio:,.0f}")
        lines.append(f"Momentum: {mom_text}")
        lines.append(f"Fluxo Geral: {fluxo_text}")
        lines.append(f"Follow Through: {follow_through}%")
        lines.append(f"")
        lines.append(f"Mercado do dia: {mkt_quality}")
        lines.append(f"Agressividade sugerida: {aggr}")
        lines.append(f"Qtde ideal de operações: {ideal_qty}")
        lines.append(f"Probabilidade média: {prob_media}%")
        lines.append("")
        lines.append("📈 MERCADO GERAL")
        lines.append(f"RSI médio: {rsi_medio}")
        lines.append(f"ADX médio: {adx_medio}")
        lines.append(f"RVOL médio: {rvol_medio_geral}")
        lines.append(f"Volume médio: ${vol_medio:,.0f}")
        lines.append(f"Funding médio: {funding_medio:.4f}%" if funding_medio else "Funding médio: —")
        lines.append(f"BTC: {self.btc_trend}" if self.btc_trend else "")
        lines.append(f"ETH: {self.eth_trend}" if self.eth_trend else "")
        lines.append("")
        lines.append("📊 SCANNER")
        lines.append(f"Analisados: {self.total_analisadas}")
        lines.append(f"Aprovados: {self.total_aprovadas}")
        lines.append(f"Recusados: {self.total_recusadas}")
        lines.append(f"💎 Ouro Supremo: {self.ouro_supremo}")
        lines.append(f"🥇 Ouro: {self.ouro}")
        lines.append(f"🥈 Prata: {self.prata}")
        lines.append(f"🥉 Bronze: {self.bronze}")
        lines.append("")
        lines.append("📊 QUALIDADE DOS SINAIS")
        lines.append(f"  Kalman alinhado: {self._pct(self.kalman_alinhado_count, n_aprov)}%")
        lines.append(f"  Fluxo forte: {fluxo_forte_pct}%")
        lines.append(f"  Entradas contra tendência: {self._pct(self.entradas_contra_tendencia, n_aprov)}%")
        lines.append(f"  Sinais bloqueados por Kalman: {self.kalman_bloqueios_totais}")
        lines.append(f"  Sinais recuperados: {self.kalman_side_aprovados}")
        lines.append(f"  Qualidade sem Kalman: {qualidade_sem_kalman}")
        lines.append("")
        lines.append("📈 TRADES")
        total_trades = self.trades.total_trades if self.trades else 0
        lines.append(f"Total: {total_trades}")
        lines.append(f"Wins: {self.trades.wins if self.trades else 0}")
        lines.append(f"Losses: {self.trades.losses if self.trades else 0}")
        lines.append(f"Winrate: {self.trades.winrate if self.trades else 0}%")
        lines.append(f"R médio: {self.trades.avg_r if self.trades else 0}")
        lines.append(f"Profit Factor: {self.trades.profit_factor if self.trades else 0}")
        lines.append(f"R acumulado: {self.trades.total_r:.2f}" if self.trades else "R acumulado: 0")
        lines.append(f"Drawdown: {self.trades.drawdown_pct if self.trades else 0}%")
        if self.trades:
            criteria = [
                ("PF ≥ 2.20", self.trades.profit_factor, 2.20),
                ("WR ≥ 42%", self.trades.winrate, 42.0),
                ("R médio ≥ 0.60", self.trades.avg_r, 0.60),
                ("DD ≤ 15%", self.trades.drawdown_pct, 15.0, True),
            ]
            lines.append("")
            lines.append("📋 V6.6 CRITÉRIOS")
            for label, actual, target, *opts in criteria:
                invert = opts[0] if opts else False
                ok = (actual <= target) if invert else (actual >= target)
                mark = "✅" if ok else "❌"
                actual_str = f"{actual:.2f}" if isinstance(actual, float) else str(actual)
                target_str = f"{target:.2f}" if isinstance(target, float) else str(target)
                lines.append(f"  {mark} {label}: {actual_str} (meta: {target_str})")
        grade_lines = self._build_grade_report()
        if grade_lines:
            lines.append("")
            lines.append("📊 GRADES (histórico completo)")
            lines.extend(grade_lines)
        lines.append("")
        lines.append("⏱ PERFORMANCE")
        lines.append(f"Tempo análise: {dur:.1f}s")
        lines.append(f"Moedas/min: {analises_por_min}")
        lines.append(f"Eficiência: {self.total_analisadas / max(dur, 0.1):.0f} moedas/s")
        lines.append("")
        lines.append("🏆 TOP 5 SETUPS")

        for i, s in enumerate(top_aprov[:5], 1):
            stars = _star_rating(s["score"], s["classificacao"])
            lines.append(f"  {i}. {stars} {s['symbol']} {s['direction']} — Score: {s['score']} ({s['classificacao']})")

        lines.append("")
        lines.append("⛔ TOP 5 PIORES ATIVOS")
        for i, (sym, motivo) in enumerate(piores_ativos[:5], 1):
            lines.append(f"  {i}. {sym} — {motivo}")

        lines.append("")
        lines.append("🔒 TOP BLOQUEADORES")
        for motivo, count in blockers_top:
            pct = self._pct(count, self.total_recusadas)
            lines.append(f"  • {motivo}: {count} ({pct}%)")

        lines.append("")
        lines.append("📊 REPROVADOS POR FILTRO")
        for filtro, attr in [("Exaustão", "bloqueador_exaustao"), ("Multi TF", "bloqueador_multi_timeframe"),
                                ("TP1 <$1", "bloqueador_tp1_minimo"),
                                ("RVOL", "bloqueador_rvol"), ("Kalman", "bloqueador_kalman"),
                                ("RSI", "bloqueador_rsi"), ("ADX", "bloqueador_adx"),
                                ("Score", "bloqueador_score"), ("MM200", "bloqueador_mm200")]:
            count = getattr(self, attr, 0)
            lines.append(f"  • {filtro}: {count}")

        if self.score_penalizados:
            lines.append("")
            lines.append("⚠️ PENALIZADOS (RSI/Kalman)")
            for sym, direc, pen, motivos, score_orig, score_final in self.score_penalizados:
                lines.append(f"  • {sym} Score {score_orig} → -{pen} ({', '.join(motivos)}) = {score_final}")
                if score_final >= 75:
                    lines.append(f"    → Aprovariam se RSI/Kalman fossem apenas penalidades")

        if quase_aprov:
            lines.append("")
            lines.append("⚠️ QUASE APROVADOS")
            for sym, score, motivo in quase_aprov:
                falta = self._format_falta(motivo)
                lines.append(f"  • {sym} Score {score}")
                lines.append(f"    Faltou: {falta}")

        if self.presinais:
            lines.append("")
            lines.append("🟡 PRÉ-SINAL")
            for item in sorted(self.presinais, key=lambda x: -x.get("score", 0))[:10]:
                lines.append(f"  • {item.get('symbol')} Score {item.get('score')}")
                lines.append(f"    Regime: {item.get('regime')} | Faltando: {self._format_falta(str(item.get('faltando', '')))}")
                lines.append(f"    Chance estimada: {item.get('chance')}%")

        if self.score_stage:
            lines.append("")
            lines.append("🔍 REPROVADOS NO SCORE (detalhes)")
            for sym, direc, score, motivo in self.score_stage:
                lines.append(f"  • {sym} → Reprovado: {motivo}")

        lines.append("")
        lines.append("📋 MÉDIAS DOS APROVADOS")
        lines.append(f"  Score médio: {self._avg(self.score_list)}")
        lines.append(f"  RVOL médio: {self._avg(self.rvol_aprovados)}")
        lines.append(f"  ADX médio: {self._avg(self.adx_aprovados)}")
        lines.append(f"  ATR médio: {self._avg(self.atr_aprovados)*100:.1f}%" if self.atr_aprovados else "  ATR médio: —")
        lines.append(f"  Timing médio: {self._avg(self.timing_list)}")
        lines.append(f"  Fluxo Forte: {fluxo_forte_pct}%")
        lines.append(f"  Kalman UP: {kalman_up_pct}%")
        lines.append(f"  Kalman DOWN: {kalman_down_pct}%")
        lines.append(f"  Kalman SIDE: {kalman_side_pct}%")
        lines.append(f"  Velas Fortes média: {velas_media}")

        lines.append("")
        lines.append("📊 DISTRIBUIÇÃO DOS SCORES (aprovados)")
        lines.append(self._distribuicao_scores())

        if self.dados_simulacao:
            lines.append("")
            lines.append("📊 REQUISITOS POR CATEGORIA")
            lines.append(f"  Base: {len(self.dados_simulacao)} ativos")
            lines.append("")
            rvol_vals = [d["rvol"] for d in self.dados_simulacao]
            adx_vals = [d["adx"] for d in self.dados_simulacao]
            score_vals = [d["score"] for d in self.dados_simulacao]
            timing_vals = [d.get("timing", 0) for d in self.dados_simulacao]
            rvol_ths = [0.90, 1.00, 1.10, 1.20, 1.35, 1.50]
            rvol_line = "  RVOL: " + " ".join(f"≥{th:.2f}:{sum(1 for v in rvol_vals if v>=th)}" for th in rvol_ths)
            lines.append(rvol_line)
            adx_ths = [18, 20, 22, 25, 28, 30, 35]
            adx_line = "  ADX:  " + " ".join(f"≥{th}:{sum(1 for v in adx_vals if v>=th)}" for th in adx_ths)
            lines.append(adx_line)
            score_ths = [60, 65, 70, 75, 80, 85]
            score_line = "  Score:" + " ".join(f"≥{th}:{sum(1 for v in score_vals if v>=th)}" for th in score_ths)
            lines.append(score_line)
            timing_ths = [60, 65, 70, 75, 80]
            timing_line = "  Timing:" + " ".join(f"≥{th}:{sum(1 for v in timing_vals if v>=th)}" for th in timing_ths)
            lines.append(timing_line)

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)


def _star_rating(score, classificacao):
    if classificacao == "OURO_SUPREMO":
        return "💎💎💎💎💎💎"
    if classificacao == "OURO":
        return "⭐⭐⭐⭐⭐"
    if classificacao == "PRATA":
        if score >= 80:
            return "⭐⭐⭐⭐"
        return "⭐⭐⭐"
    if score >= 71:
        return "⭐⭐"
    return "⭐"


def _qualidade_liquidez(vol):
    if vol >= 50_000_000: return "Excelente"
    if vol >= 10_000_000: return "Boa"
    if vol >= 5_000_000: return "Normal"
    if vol >= 2_000_000: return "Baixa"
    return "Muito Baixa"


def _qualidade_momentum(rsi, adx):
    if adx >= 35 and 45 <= rsi <= 65:
        return "Forte"
    if adx >= 25:
        return "Moderado"
    return "Fraco"


def _qualidade_volatilidade(atr_ratio):
    if atr_ratio is None: return "—"
    if atr_ratio >= 1.2: return "Alta"
    if atr_ratio >= 0.7: return "Ideal"
    return "Baixa"


def _fluxo_geral(direcao_count):
    long_pct = direcao_count.get("LONG", 0)
    short_pct = direcao_count.get("SHORT", 0)
    total = long_pct + short_pct
    if total == 0: return "Neutro"
    if long_pct / total > 0.55: return "Comprador"
    if short_pct / total > 0.55: return "Vendedor"
    return "Neutro"


def _agressividade(sinais_count, mkt_quality):
    if sinais_count <= 2 and mkt_quality in ("Fraco", "Normal"):
        return "Conservadora"
    if sinais_count <= 5:
        return "Moderada"
    return "Agressiva"


def _qtde_ideal(sinais_count, mkt_quality):
    if mkt_quality in ("Fraco",):
        return min(sinais_count, 2)
    if mkt_quality in ("Normal",):
        return min(sinais_count, 4)
    return sinais_count
