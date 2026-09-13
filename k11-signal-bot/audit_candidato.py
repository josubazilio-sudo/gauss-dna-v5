"""
Auditoria Preventiva — Rastrear candidato de "ok" até sinal

Objetivo: Descobrir EXATAMENTE onde MUSTOCK/XAU/ARB deixam de ser elegíveis
"""
import sys
import os
sys.path.insert(0, '/root/gauss-dna-v5/k11-signal-bot')

os.environ['SOFT_FILTERS_MODE'] = 'true'

from k10_engine import K10Engine
from datetime import datetime, timezone
import json

class AuditCandidato:
    def __init__(self, symbol):
        self.symbol = symbol
        self.eventos = []
        self.engine = K10Engine()
        self.resultado_final = None

    def log(self, etapa, dados):
        """Registrar evento no fluxo"""
        evento = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "etapa": etapa,
            "dados": dados
        }
        self.eventos.append(evento)
        print(f"\n[{self.symbol}] {etapa}")
        for k, v in dados.items():
            print(f"  {k}: {v}")

    def auditar(self):
        """Rastrear fluxo completo"""
        print(f"\n{'='*80}")
        print(f"AUDITORIA: {self.symbol}")
        print(f"{'='*80}")

        # ETAPA 1: K10Engine.analisar (scanner)
        self.log("ENTRADA_K10ENGINE", {
            "função": "K10Engine.analisar()",
            "status": "iniciando análise de timeframes"
        })

        # ETAPA 2: Análise por timeframe
        try:
            # 30m primeiro
            r_30m = self.engine._analisar_tf(self.symbol, "30m", tf_contexto="1h")
            if r_30m:
                self.log("RESULTADO_30M", {
                    "aprovado": r_30m.get("aprovado"),
                    "score": r_30m.get("score"),
                    "tier": r_30m.get("tier"),
                    "eq": r_30m.get("eq"),
                    "rr": r_30m.get("rr"),
                    "rvol": r_30m.get("rvol"),
                    "direcao": r_30m.get("direcao"),
                    "motivos_rejeicao": r_30m.get("motivos_rejeicao", [])[:3],
                    "bos_ok": r_30m.get("bos_ok"),
                    "sweep_ok": r_30m.get("sweep_ok"),
                })

            # 1h depois
            r_1h = self.engine._analisar_tf(self.symbol, "1h", tf_contexto="4h")
            if r_1h:
                self.log("RESULTADO_1H", {
                    "aprovado": r_1h.get("aprovado"),
                    "score": r_1h.get("score"),
                    "tier": r_1h.get("tier"),
                    "eq": r_1h.get("eq"),
                    "rr": r_1h.get("rr"),
                    "rvol": r_1h.get("rvol"),
                    "direcao": r_1h.get("direcao"),
                    "motivos_rejeicao": r_1h.get("motivos_rejeicao", [])[:3],
                    "bos_ok": r_1h.get("bos_ok"),
                    "sweep_ok": r_1h.get("sweep_ok"),
                })

            # ETAPA 3: Resultado consolidado
            resultados = [r_30m, r_1h]
            resultados = [r for r in resultados if r]

            if resultados:
                melhor = max(resultados, key=lambda x: x.get("score", 0))
                self.resultado_final = melhor

                self.log("MELHOR_RESULTADO", {
                    "timeframe": melhor.get("timeframe"),
                    "score": melhor.get("score"),
                    "tier": melhor.get("tier"),
                    "aprovado": melhor.get("aprovado"),
                    "eq": melhor.get("eq"),
                    "rr": melhor.get("rr"),
                    "rvol": melhor.get("rvol"),
                })

                # ETAPA 4: Verificar se aprovado
                if melhor.get("aprovado"):
                    self.log("APROVADO_K10", {
                        "status": "✅ Passou em K10Engine",
                        "score": melhor.get("score"),
                        "próximo_passo": "final_selector.py"
                    })
                else:
                    self.log("REJEITADO_K10", {
                        "status": "❌ Rejeitado em K10Engine",
                        "motivos": melhor.get("motivos_rejeicao", [])[:5],
                        "PONTO_DE_PARADA": "K10Engine._analisar_tf()"
                    })

            else:
                self.log("ERRO_NENHUM_RESULTADO", {
                    "status": "❌ Nenhum resultado válido",
                    "PONTO_DE_PARADA": "K10Engine.analisar()"
                })

        except Exception as e:
            self.log("EXCECAO_K10ENGINE", {
                "erro": str(e),
                "PONTO_DE_PARADA": "Exceção em K10Engine"
            })

        # ETAPA 5: Simular final_selector (se aprovado)
        if self.resultado_final and self.resultado_final.get("aprovado"):
            self.simular_final_selector()

    def simular_final_selector(self):
        """Simular o que faz o final_selector.py"""
        sinal = self.resultado_final

        self.log("ENTRADA_FINAL_SELECTOR", {
            "score": sinal.get("score"),
            "tier": sinal.get("tier"),
            "timeframe": sinal.get("timeframe"),
            "direcao": sinal.get("direcao"),
        })

        # Verificar se já estava em cache (anti-repetição)
        chave = f"{sinal['symbol']}_{sinal['direcao']}_{sinal['timeframe']}"

        self.log("ANTI_REPETICAO", {
            "chave": chave,
            "verificando_cache_2h": True,
            "status": "simulado (cache não disponível neste contexto)"
        })

        # Verificar correlação
        sym_base = sinal['symbol'].replace("/USDT:USDT", "")
        self.log("ANTI_CORRELACAO", {
            "símbolo_base": sym_base,
            "verificando_ativos_hoje": True,
            "status": "simulado"
        })

        # Verificar tier mínimo do selector
        self.log("GATE_TIER_MINIMO", {
            "tier_sinal": sinal.get("tier"),
            "tier_mínimo_selector": "PRATA (tipicamente)",
            "passa": sinal.get("tier") in ["OURO", "PRATA"]
        })

        # Verificar score
        self.log("GATE_SCORE", {
            "score": sinal.get("score"),
            "score_mínimo": 70,
            "passa": sinal.get("score", 0) >= 70
        })

        if sinal.get("score", 0) >= 70 and sinal.get("tier") in ["OURO", "PRATA"]:
            self.log("PRONTO_PARA_SINAL", {
                "status": "✅ Pronto para emissão",
                "próximo_passo": "formatar_cartao() e await enviar()"
            })
        else:
            self.log("REJEITADO_FINAL_SELECTOR", {
                "status": "❌ Rejeitado no final_selector",
                "motivos": [
                    f"tier={sinal.get('tier')}",
                    f"score={sinal.get('score')}"
                ],
                "PONTO_DE_PARADA": "final_selector.py"
            })

    def relatorio(self):
        """Gerar relatório"""
        print(f"\n{'='*80}")
        print(f"RELATÓRIO: {self.symbol}")
        print(f"{'='*80}")

        if not self.resultado_final:
            print("❌ Nenhum resultado para auditar")
            return

        print(f"\n📊 RESULTADO FINAL:")
        print(f"  Score: {self.resultado_final.get('score')}")
        print(f"  Tier: {self.resultado_final.get('tier')}")
        print(f"  Aprovado K10: {self.resultado_final.get('aprovado')}")
        print(f"  EQ: {self.resultado_final.get('eq')}")
        print(f"  RR: {self.resultado_final.get('rr')}")
        print(f"  RVOL: {self.resultado_final.get('rvol')}")

        print(f"\n🔍 EVENTOS ({len(self.eventos)} etapas):")
        for i, evt in enumerate(self.eventos, 1):
            print(f"  {i}. {evt['etapa']}")

        # Encontrar ponto de parada
        for evt in reversed(self.eventos):
            if "PONTO_DE_PARADA" in evt['dados']:
                print(f"\n⛔ PONTO DE PARADA:")
                print(f"  {evt['etapa']}")
                print(f"  {evt['dados']['PONTO_DE_PARADA']}")
                break

        print(f"\n{'='*80}\n")


def main():
    """Auditar MUSTOCK, XAU, ARB"""
    simbolos = ["MUSTOCK", "XAU", "ARB"]

    for sym in simbolos:
        audit = AuditCandidato(sym)
        audit.auditar()
        audit.relatorio()


if __name__ == "__main__":
    main()
