"""
K12 Runner — SMC Engine
"""
import asyncio, logging, os, httpx, traceback, json, time as t
from concurrent.futures import ThreadPoolExecutor, as_completed
from formatter import formatar_cartao, formatar_cartao_operavel
from config import BOT_TOKEN, ALLOWED_CHAT_IDS

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
CHAT_ID = ALLOWED_CHAT_IDS[0] if ALLOWED_CHAT_IDS else None

async def enviar(texto: str):
    if not CHAT_ID or not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"chat_id": CHAT_ID, "text": texto[:4096]})
        logger.info(f"TG: {r.status_code}")

async def main():
    logger.info("K12 SMC iniciado")
    try:
        from k10_engine import K10Engine
        from watchlist import get_watchlist, WATCHLIST_FALLBACK, WATCHLIST_PRIORITY
        from trade_tracker import registrar, verificar_resultados_automatico

        try:
            fechados_agora = verificar_resultados_automatico()
            if fechados_agora:
                logger.info(f"K12: {fechados_agora} trades fechados automaticamente")
        except Exception as e:
            logger.warning(f"Verificacao de resultados: {e}")

        # K11 SHADOW — resolve candidatos pendentes (RFC 21/08). Mesmo padrao
        # do verificar_resultados_automatico() acima, so que sobre o dataset
        # de candidatos bloqueados/aprovados, nao sobre trades reais.
        try:
            import shadow_tracker
            resolvidos_shadow = shadow_tracker.resolver_pendentes()
            if resolvidos_shadow:
                logger.info(f"K12 SHADOW: {resolvidos_shadow} candidato(s) resolvido(s)")
        except Exception as e:
            logger.warning(f"SHADOW resolver_pendentes: {e}")

        # Gestao de Posicao (2026-08-10) — Trailing pos-BE + Alerta de Saida
        # Estrutural (ver trade_tracker.verificar_gestao_avancada). Atras de
        # flag em config.py, default OFF. Nunca lanca — erro isolado por
        # simbolo dentro da propria funcao.
        try:
            from trade_tracker import verificar_gestao_avancada
            avisos_gestao = verificar_gestao_avancada()
            for aviso in avisos_gestao:
                await enviar(aviso)
            if avisos_gestao:
                logger.info(f"K12: {len(avisos_gestao)} aviso(s) de gestao de posicao enviado(s)")
        except Exception as e:
            logger.warning(f"Gestao de posicao avancada: {e}")

        engine = K10Engine()
        wl_geral = get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK
        wl_sem_dup = [p for p in wl_geral if p not in WATCHLIST_PRIORITY]
        wl = WATCHLIST_PRIORITY + wl_sem_dup[:490]  # 500 pares total

        aprovados = []
        todos_resultados = []  # p/ Shadow Outcome Tracking (RFC 21/08) — inclui bloqueados
        def analisar(sym):
            try: return engine.analisar(sym)
            except: return None

        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(analisar, sym): sym for sym in wl[:500]}
            for f in as_completed(futures):
                r = f.result()
                if r:
                    todos_resultados.append(r)
                if r and r.get("aprovado") and r.get("score",0) >= 70:
                    aprovados.append(r)

        aprovados.sort(key=lambda x: x.get("score",0), reverse=True)
        logger.info(f"K12: {len(aprovados)} aprovados")

        # K11 SHADOW OUTCOME TRACKING — captura observacional (RFC 21/08).
        # So registra e le valores ja calculados pelo engine acima; nunca
        # aprova/bloqueia/altera nada em `todos_resultados` ou `aprovados`.
        try:
            import shadow_tracker
            novos_shadow = shadow_tracker.capturar_lote(todos_resultados)
            if novos_shadow:
                logger.info(f"K12 SHADOW: {novos_shadow} candidato(s) novo(s) capturado(s)")
        except Exception as e:
            logger.warning(f"SHADOW capturar_lote: {e}")

        # K11 APEX — snapshot da lista COMPLETA aprovada pelo engine, antes do
        # Final Selector reduzir/reordenar. O APEX e uma lente independente,
        # nao depende da selecao do Final Selector (RFC APEX v1, shadow mode).
        aprovados_engine_full = list(aprovados)

        # FINAL SELECTOR — ATIVO
        try:
            from final_selector import selecionar, CFG
            fs_state = None
            fs_selecionados, fs_rejeitados, fs_contadores, fs_state = selecionar(aprovados, fs_state)
            logger.info(
                f"SELECTOR ATIVO | "
                f"Total:{fs_contadores['candidates_total']} "
                f"Sel:{fs_contadores['selected']} "
                f"Timing❌:{fs_contadores['timing_rejected']} "
                f"Watch:{fs_contadores['watching']} "
                f"Cooldown❌:{fs_contadores['cooldown_rejected']} "
                f"Corr❌:{fs_contadores['correlation_rejected']}"
            )
            aprovados = fs_selecionados  # usar só os selecionados; sem fallback para rejeitados
        except Exception as e:
            logger.warning(f"Final Selector: {e}")

        # K11 APEX — avaliação independente (shadow mode, RFC APEX v1 20/08).
        # Roda sobre TODOS os candidatos aprovados pelo engine, nao so os que
        # o Final Selector escolheu — o APEX pode discordar do selector.
        # Nao altera `aprovados`, nao interfere no fluxo normal de envio.
        apex_resultado = None
        try:
            import apex_engine
            apex_resultado = apex_engine.selecionar_apex(aprovados_engine_full)
            if apex_resultado:
                apex_sinal = apex_resultado["sinal"]
                apex_sinal["is_apex"]         = True
                apex_sinal["apex_tipo"]       = apex_resultado["apex_tipo"]
                apex_sinal["apex_score"]      = apex_resultado["apex_score"]
                apex_sinal["apex_componentes"]= apex_resultado["componentes"]
                logger.info(
                    f"K12 APEX candidato: {apex_sinal['symbol']} "
                    f"{apex_resultado['apex_tipo']} score={apex_resultado['apex_score']}"
                )
            else:
                logger.info("K12 APEX: nenhum candidato atingiu a barra neste ciclo")
        except Exception as e:
            logger.warning(f"APEX: {e}")
            apex_resultado = None

        # SHORT SHADOW — RFC short-shadow 26/08. Experiencia isolada,
        # roda DEPOIS do fluxo LONG (nunca atrasa o envio real). So
        # captura em short_shadow_candidates.jsonl, nunca aprova/envia/
        # registra trade real. Falha isolada nunca derruba o ciclo.
        try:
            from short_shadow_engine import ShortShadowEngine, capturar_lote as capturar_short, resolver_pendentes as resolver_short
            resolvidos_short = resolver_short()
            if resolvidos_short:
                logger.info(f"K12 SHORT_SHADOW: {resolvidos_short} candidato(s) resolvido(s)")

            short_engine = ShortShadowEngine()
            wl_short = wl[:150]  # subconjunto — nao pesa o ciclo principal
            def analisar_short(sym):
                candidatos_sym = []
                for tf_s in ("30m", "1h"):
                    try:
                        r = short_engine.analisar_tf(sym, tf_s)
                        if r:
                            candidatos_sym.append(r)
                    except Exception:
                        pass
                return candidatos_sym

            todos_short = []
            with ThreadPoolExecutor(max_workers=4) as ex_short:
                futures_short = {ex_short.submit(analisar_short, sym): sym for sym in wl_short}
                for f_short in as_completed(futures_short):
                    todos_short.extend(f_short.result())

            novos_short = capturar_short(todos_short)
            aprovados_short = [c for c in todos_short if c.get("aprovado_shadow")]
            if aprovados_short:
                logger.info(
                    f"K12 SHORT_SHADOW: {len(aprovados_short)} regime(s) bearish forte "
                    f"({', '.join(c['symbol'] for c in aprovados_short)}) | "
                    f"{novos_short} novo(s) capturado(s) no total"
                )
            elif novos_short:
                logger.info(f"K12 SHORT_SHADOW: {novos_short} candidato(s) novo(s) capturado(s), nenhum atingiu a barra")
        except Exception as e:
            logger.warning(f"SHORT_SHADOW: {e}")

    except Exception:
        logger.error(traceback.format_exc())
        return

    if not aprovados:
        logger.info("K12: nenhum sinal")

        # Verificar se passou mais de 30 minutos sem sinal
        cache_file = "/root/gauss-dna-v5/k11-signal-bot/k11_cache.json"
        diag_file  = "/tmp/k11_last_diag.json"
        try:
            now = t.time()
            # Último sinal enviado
            cache = json.load(open(cache_file)) if os.path.exists(cache_file) else {}
            if cache:
                ultimo_sinal = max(cache.values())
            else:
                # k11_cache.json só guarda os últimos 2h por design (anti-
                # repetição) — pode estar vazio mesmo com sinais no passado.
                # Cair pro último trade real registrado em vez de assumir
                # "nunca houve sinal" (produzia "há 29 milhões de minutos").
                ultimo_sinal = now  # sem historico = considera agora
                try:
                    from datetime import datetime as _datetime, timezone as _timezone, timedelta as _timedelta
                    from trade_tracker import _carregar as _carregar_trades
                    trades_hist = _carregar_trades()
                    if trades_hist:
                        ultimo_t = trades_hist[-1]
                        dt_ultimo = _datetime.strptime(f"{ultimo_t['data']} {ultimo_t['hora']}", "%d/%m/%Y %H:%M")
                        dt_ultimo = dt_ultimo.replace(tzinfo=_timezone(_timedelta(hours=-3)))  # trade_tracker grava em BRT
                        ultimo_sinal = dt_ultimo.timestamp()
                except Exception as e:
                    logger.warning(f"Diag automático: fallback ultimo_sinal falhou: {e}")
            # Último diagnóstico enviado
            diag_cache = json.load(open(diag_file)) if os.path.exists(diag_file) else {"ts": 0}
            ultimo_diag = diag_cache.get("ts", 0)

            sem_sinal_ha = (now - ultimo_sinal) / 60  # minutos
            sem_diag_ha  = (now - ultimo_diag) / 60

            # Enviar diagnóstico se: +30min sem sinal E +30min sem diagnóstico
            if sem_sinal_ha >= 30 and sem_diag_ha >= 30:
                # Pegar top 5 mais próximos de aprovação
                from k10_engine import K10Engine
                from watchlist import get_watchlist, WATCHLIST_FALLBACK, WATCHLIST_PRIORITY
                engine2 = K10Engine()
                # dedupe entre PRIORITY e a lista geral (mesmo padrao do scan
                # principal) -- sem isso um symbol em WATCHLIST_PRIORITY podia
                # ser analisado duas vezes e aparecer duplicado no TOP 5.
                wl2_geral = get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK
                wl2_sem_dup = [p for p in wl2_geral if p not in WATCHLIST_PRIORITY]
                wl2 = (WATCHLIST_PRIORITY + wl2_sem_dup)[:50]

                todos = []
                def analisar2(sym):
                    try: return engine2.analisar(sym)
                    except: return None

                with ThreadPoolExecutor(max_workers=6) as ex2:
                    futures2 = {ex2.submit(analisar2, s): s for s in wl2}
                    for f2 in as_completed(futures2):
                        r2 = f2.result()
                        if r2 and r2.get("score",0) > 0:
                            todos.append(r2)

                todos.sort(key=lambda x: x.get("score",0), reverse=True)
                top5 = todos[:5]

                # K11 SHADOW — captura tambem os candidatos deste mini-scan
                # (top-50) usado so pro diagnostico "SEM SINAL".
                try:
                    import shadow_tracker
                    shadow_tracker.capturar_lote(todos)
                except Exception as e:
                    logger.warning(f"SHADOW capturar_lote (diag): {e}")

                # Montar diagnóstico explicativo
                from datetime import datetime, timezone
                hora = datetime.now(timezone.utc).strftime("%H:%M UTC")
                linhas = [
                    f"📊 K12 — SEM SINAL há {sem_sinal_ha:.0f} minutos",
                    f"🕐 {hora} | Mercado em análise",
                    "━━━━━━━━━━━━━━",
                    "🔍 TOP ATIVOS MAIS PRÓXIMOS:",
                    ""
                ]
                for r2 in top5:
                    sym    = r2.get("symbol","").replace("/USDT:USDT","")
                    score  = r2.get("score", 0)
                    motivo = (r2.get("motivos_rejeicao") or ["ok"])[0][:40]
                    rvol   = r2.get("rvol", 0)
                    tf     = r2.get("timeframe","?")
                    falta  = "✅ Quase lá!" if score >= 65 else "⏳ Aguardando"
                    linhas.append(f"{falta} {sym} | s={score} | {tf} | RVOL {rvol:.2f}")
                    linhas.append(f"   → {motivo}")

                linhas += [
                    "",
                    "━━━━━━━━━━━━━━",
                    "💡 O mercado está:",
                ]
                # Diagnóstico geral
                scores = [r2.get("score",0) for r2 in todos]
                rvols  = [r2.get("rvol",0) for r2 in todos if r2.get("rvol",0) > 0]
                med_score = sum(scores)/len(scores) if scores else 0
                med_rvol  = sum(rvols)/len(rvols) if rvols else 0

                if med_rvol < 0.7:
                    linhas.append("📉 Volume baixo — institucional ausente")
                if med_score < 50:
                    linhas.append("😴 Sem momentum — aguardar movimento")

                # RFC frequencia-sinais 23/08 — DIAGNÓSTICO OBRIGATÓRIO. Reaproveita
                # audit_10of10 (já calculado pelo engine p/ cada candidato, nada
                # novo) em vez de reparsear texto de motivos_rejeicao. Separa
                # HARD (motivos_rejeicao, bloqueia sozinho) de SOFT (motivos_soft,
                # só penaliza — só existe quando SOFT_FILTERS_MODE=true).
                n = len(todos)
                _audits = [r2.get("audit_10of10") or {} for r2 in todos]
                n_estrutura = sum(1 for a in _audits if a.get("BOS/CHoCH") == "PASS" or a.get("Liquidity Sweep") == "PASS")
                n_sweep     = sum(1 for a in _audits if a.get("Liquidity Sweep") == "PASS")
                n_bos       = sum(1 for a in _audits if a.get("BOS/CHoCH") == "PASS")
                n_rvol_ok   = sum(1 for a in _audits if a.get("RVOL") == "PASS")
                n_tardia    = sum(1 for a in _audits if a.get("Entry Quality") == "FAIL")

                linhas += [
                    "━━━━━━━━━━━━━━",
                    f"📋 DIAGNÓSTICO ({n} candidatos analisados)",
                    f"Estrutura válida (BOS/Sweep): {n_estrutura}",
                    f"Sweep válido (com reclaim): {n_sweep}",
                    f"BOS/CHoCH: {n_bos}",
                    f"RVOL válido: {n_rvol_ok}",
                    f"Entrada tardia: {n_tardia}",
                ]

                motivos_hard_freq = {}
                motivos_soft_freq = {}
                for r2 in todos:
                    for m in (r2.get("motivos_rejeicao") or []):
                        chave = m[:40]
                        motivos_hard_freq[chave] = motivos_hard_freq.get(chave, 0) + 1
                    for m in (r2.get("motivos_soft") or []):
                        chave = m[:40]
                        motivos_soft_freq[chave] = motivos_soft_freq.get(chave, 0) + 1

                if motivos_hard_freq:
                    linhas.append("🚫 HARD BLOCK:")
                    for motivo, cnt in sorted(motivos_hard_freq.items(), key=lambda x: -x[1])[:3]:
                        linhas.append(f"→ {motivo} ({cnt}x)")
                if motivos_soft_freq:
                    linhas.append("🟡 SOFT FILTER (penaliza, não bloqueia sozinho):")
                    for motivo, cnt in sorted(motivos_soft_freq.items(), key=lambda x: -x[1])[:3]:
                        linhas.append(f"→ {motivo} ({cnt}x)")

                linhas.append("━━━━━━━━━━━━━━")
                # Estatísticas
                try:
                    from trade_tracker import stats_rapidas
                    stats = stats_rapidas()
                    linhas.append("")
                    linhas.append(stats)
                except:
                    pass
                linhas.append("K12 continua monitorando...")

                await enviar("\n".join(linhas))

                # Salvar timestamp do diagnóstico
                with open(diag_file, "w") as f:
                    json.dump({"ts": now}, f)
        except Exception as e:
            logger.warning(f"Diag automático: {e}")

        return

    # Anti-repetição 2h + limite diário + anti-correlação
    cache_file = "/root/gauss-dna-v5/k11-signal-bot/k11_cache.json"
    dia_file   = "/root/gauss-dna-v5/k11-signal-bot/k11_dia.json"

    def _salvar_cache_agora():
        # RFC anti-duplicata 24/08: antes o cache so era salvo em disco UMA
        # vez, no fim do ciclo inteiro (depois de processar todos os
        # aprovados + bloco APEX). Se o processo fosse morto no meio disso
        # (ex.: restart do bot durante um deploy) DEPOIS de enviar um sinal
        # mas ANTES de chegar nessa escrita final, a entrada no cache se
        # perdia -- o proximo ciclo via o candle 1h ainda fechado (mesma
        # entrada) e reenviava o MESMO sinal (caso real: ASTER 20:10,
        # dois cartoes pro mesmo candle). Agora salva imediatamente apos
        # cada envio, com escrita atomica (tmp+replace, igual trade_tracker).
        try:
            tmp = cache_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(cache, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, cache_file)
        except Exception as e:
            logger.warning(f"Cache anti-repeticao: falha ao salvar imediatamente ({e})")
    try:
        cache = json.load(open(cache_file)) if os.path.exists(cache_file) else {}
        now = t.time()
        cache = {k:v for k,v in cache.items() if now-v < 7200}
    except:
        cache = {}

    # Controle diário — máximo 20 sinais/dia
    from datetime import datetime, timezone, timedelta
    hoje = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%d/%m/%Y")
    try:
        dia_data = json.load(open(dia_file)) if os.path.exists(dia_file) else {}
        if dia_data.get("data") != hoje:
            dia_data = {"data": hoje, "count": 0, "ativos": []}
    except:
        dia_data = {"data": hoje, "count": 0, "ativos": []}

    MAX_DIA = 5

    # STRUCTURE WATCHER
    try:
        from structure_watcher import verificar_quebra_estrutura
        import ccxt as _ccxt
        _exch = _ccxt.mexc({"enableRateLimit": True, "options": {"defaultType": "swap"}})
        reversoes = verificar_quebra_estrutura(_exch)
        for rev in reversoes:
            if rev.get("aviso_apenas"):
                await enviar(rev["msg"])
            else:
                # formatar_cartao já vem do import de módulo (topo do arquivo).
                # NÃO reimportar aqui: um import local dentro de main() faz o
                # Python tratar o nome como variável local em TODA a função,
                # inclusive antes desta linha — foi exatamente isso que
                # causou o UnboundLocalError no envio normal (linha ~350),
                # assim que o primeiro sinal real desde 13/08 chegou lá.
                cartao_rev = formatar_cartao(rev, bot_name="K12")
                if cartao_rev:
                    await enviar(cartao_rev)
                    logger.info(f"K12 REVERSAO: {rev['symbol']} SHORT")
    except Exception as e:
        logger.warning(f"STRUCTURE_WATCHER: {e}")

    enviados = 0
    chaves_enviadas_normal = set()  # p/ dedupe do envio APEX logo abaixo
    for sinal in aprovados[:3]:
        # Limite diário
        if dia_data["count"] >= MAX_DIA:
            logger.info(f"K12: limite diário {MAX_DIA} atingido")
            break

        chave = f"{sinal['symbol']}_{sinal['direcao']}_{sinal['timeframe']}"
        sym_base = sinal['symbol'].replace("/USDT:USDT","")

        # Anti-repetição 2h
        if chave in cache:
            continue

        # Anti-correlação — não enviar LONG e SHORT do mesmo ativo no mesmo dia
        if sym_base in dia_data["ativos"]:
            logger.info(f"K12: {sym_base} já operado hoje — pulando correlação")
            continue

        # ── SIGNAL VALIDATOR — RFC Sync ─────────────────────────────────
        try:
            from signal_validator import validar
            sinal = validar(sinal)
            if not sinal.get("valido", True):
                reason = sinal.get("block_reason", "UNKNOWN")
                logger.warning(f"SIGNAL_VALIDATOR: {sinal['symbol']} BLOQUEADO — {reason}")
                continue
        except Exception as e:
            logger.warning(f"SIGNAL_VALIDATOR: erro na validação ({e}) — sinal liberado por fallback")
        # ─────────────────────────────────────────────────────────────────────

        # ── MODO OPERÁVEL REAL — RFC 29/08 ──────────────────────────────
        # Módulo FINAL de liberação. Roda depois de motor+Final
        # Selector+signal_validator já terem aprovado — se bloquear aqui,
        # o sinal NÃO é enviado nem registrado, só logado (motivos_bloqueio).
        avaliacao = None
        try:
            import modo_operavel
            avaliacao = modo_operavel.avaliar(sinal)
            if not avaliacao["operar"]:
                logger.info(
                    f"MODO_OPERAVEL: {sinal['symbol']} {sinal['direcao']} NAO OPERAVEL — "
                    + "; ".join(avaliacao["motivos_bloqueio"])
                )
                continue
        except Exception as e:
            logger.warning(f"MODO_OPERAVEL: erro na avaliação ({e}) — sinal bloqueado por segurança")
            continue

        # Sobrescreve os campos de risco do sinal com o risco% do modo
        # operavel (RFC 29/08), ANTES de registrar() — assim o trade
        # persistido reflete o risco real usado, nao o adaptativo antigo.
        sinal["risco_pct_aplicado"] = avaliacao["risco_pct_final"]
        sinal["risco_usdt"] = avaliacao["risco_usdt_final"]
        sinal["posicao"] = avaliacao["posicao_final"]
        sinal["classificacao_operavel"] = avaliacao["classificacao"]

        cartao = formatar_cartao_operavel(sinal, avaliacao)
        if cartao:
            # Auditoria GATE 10/10
            try:
                from datetime import datetime, timezone
                aud = sinal.get("audit_10of10") or {}
                linhas = ["===== GATE 10/10 =====", sinal.get("symbol",""), "="*21]
                if aud:
                    for k, v in aud.items():
                        linhas.append(f"{k:<18} {v}")
                else:
                    linhas.append("(auditoria indisponivel)")
                linhas.append("=====================")
                with open("/root/gauss-dna-v5/k11-signal-bot/gate_audit.log", "a", encoding="utf-8") as fa:
                    fa.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") + "\n" + "\n".join(linhas) + "\n\n")
            except Exception as e:
                logger.warning(f"Audit log: {e}")

            await enviar(cartao)
            cache[chave] = t.time()
            _salvar_cache_agora()
            chaves_enviadas_normal.add(chave)
            try:
                trade_id = registrar(sinal)
                logger.info(f"K12 #{trade_id}: {sinal['symbol']} {sinal['direcao']} score={sinal['score']}")
                try:
                    import shadow_tracker
                    shadow_tracker.marcar_aprovado_real(sinal, trade_id)
                except Exception as e:
                    logger.warning(f"SHADOW marcar_aprovado_real: {e}")
            except Exception as e:
                logger.warning(f"Tracker: {e}")
            enviados += 1
            await asyncio.sleep(2)

    # K11 APEX — envio do card especial (shadow mode, RFC APEX v1 20/08).
    # Se o mesmo sinal ja foi mandado pelo fluxo normal acima (mesma chave),
    # nao registra de novo — so complementa com o card especial. Se o APEX
    # achou algo que o fluxo normal NAO mandou (ex.: Final Selector rejeitou),
    # registra aqui pela primeira vez.
    if apex_resultado:
        apex_sinal = apex_resultado["sinal"]
        sym_apex_base = apex_sinal['symbol'].replace("/USDT:USDT", "").replace("/USDT", "")
        chave_apex = f"{apex_sinal['symbol']}_{apex_sinal['direcao']}_{apex_sinal['timeframe']}"

        # Anti-repetição do APEX: um mesmo symbol+direção não deve ser
        # reenviado enquanto já existir uma posição ABERTA registrada, nem
        # dentro do cache de 2h (mesma janela usada pelo fluxo normal).
        # Só gera um novo card quando a posição anterior fechar (TP/STOP/BE)
        # ou passarem as 2h.
        apex_ja_ativo = False
        try:
            from trade_tracker import _carregar as _carregar_trades_apex
            for tr in _carregar_trades_apex():
                if (tr.get("resultado") == "ABERTO" and tr.get("is_apex")
                        and tr.get("symbol") == sym_apex_base
                        and tr.get("direcao") == apex_sinal['direcao']):
                    apex_ja_ativo = True
                    break
        except Exception as e:
            logger.warning(f"APEX checar posição ativa: {e}")

        if apex_ja_ativo:
            logger.info(f"K12 APEX: {sym_apex_base} já tem posição ABERTA — não reenviando")
        elif chave_apex in cache:
            logger.info(f"K12 APEX: {sym_apex_base} já enviado nas últimas 2h — não reenviando")
        else:
            try:
                import apex_formatter
                cartao_apex = apex_formatter.formatar_apex_cartao(apex_sinal, apex_resultado)
                await enviar(cartao_apex)
                cache[chave_apex] = t.time()
                _salvar_cache_agora()
                if chave_apex not in chaves_enviadas_normal:
                    trade_id_apex = registrar(apex_sinal)
                    logger.info(
                        f"K12 APEX #{trade_id_apex}: {apex_sinal['symbol']} "
                        f"{apex_resultado['apex_tipo']} score={apex_resultado['apex_score']}"
                    )
                    try:
                        import shadow_tracker
                        shadow_tracker.marcar_aprovado_real(apex_sinal, trade_id_apex)
                    except Exception as e:
                        logger.warning(f"SHADOW marcar_aprovado_real (apex): {e}")
                else:
                    logger.info(
                        f"K12 APEX: {apex_sinal['symbol']} já registrado pelo fluxo normal deste ciclo"
                    )
            except Exception as e:
                logger.warning(f"APEX envio: {e}")

    # Escrita final removida — agora _salvar_cache_agora() ja persiste
    # imediatamente apos cada envio (ver comentario acima da funcao).

    logger.info(f"K12: {enviados} sinais enviados")

async def verificar_relatorios():
    """Envia relatório 2h e resumo diário às 23:30 BRT."""
    from trade_tracker import relatorio_2h, relatorio_diario, enviar_telegram
    from datetime import datetime, timezone, timedelta

    now_brt = datetime.now(timezone.utc) - timedelta(hours=3)
    h = now_brt.hour
    m = now_brt.minute

    # Relatório a cada 2h (00,02,04,06,08,10,12,14,16,18,20,22h)
    if m < 6 and h % 2 == 0:
        rel = relatorio_2h()
        enviar_telegram(rel)
        logger.info(f"Relatório 2h enviado — {h:02d}h BRT")
        # V58.1 FASE 1 — relatório interno de gestão pós-entrada (BE+TP1,
        # trailing OFF). Apenas log de auditoria; não vai ao Telegram.
        try:
            from trade_tracker import relatorio_fase1
            logger.info(relatorio_fase1())
        except Exception as e:
            logger.warning(f"Relatório FASE 1: {e}")

    # Resumo diário às 23:30 BRT
    if h == 23 and 29 <= m <= 34:
        rel = relatorio_diario()
        enviar_telegram(rel)
        logger.info("Resumo diário enviado — 23:30 BRT")
        # K11 APEX — progresso da coorte de validação (shadow mode, RFC APEX v1).
        try:
            from trade_tracker import relatorio_apex_progresso
            rel_apex = relatorio_apex_progresso()
            enviar_telegram(rel_apex)
            logger.info("Relatório APEX (progresso) enviado — 23:30 BRT")
        except Exception as e:
            logger.warning(f"Relatório APEX: {e}")
        # K11 SHADOW — relatorios de auditoria (RFC 21/08). So o dashboard
        # geral vai pro Telegram; a analise por motivo/combinacoes fica so
        # em log (texto longo, mais util revisado sob demanda que enviado
        # todo dia).
        try:
            import shadow_tracker
            enviar_telegram(shadow_tracker.relatorio_shadow())
            logger.info("Relatório SHADOW enviado — 23:30 BRT")
            logger.info(shadow_tracker.relatorio_por_motivo())
            logger.info(shadow_tracker.relatorio_combinacoes())
        except Exception as e:
            logger.warning(f"Relatório SHADOW: {e}")

if __name__ == "__main__":
    async def run():
        await main()
        await verificar_relatorios()
    asyncio.run(run())
