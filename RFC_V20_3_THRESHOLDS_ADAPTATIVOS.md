# RFC V20.3 — Thresholds Adaptativos por Regime

Data: 2026-07-12

## Objetivo
Eliminar dias com zero sinais causados por thresholds fixos, tornando RVOL, ADX e Score adaptativos conforme o regime atual do mercado.

## Diagnóstico
O sistema utiliza thresholds fixos (RVOL 0.70, ADX 22, Score 70) que, em dias de baixa liquidez ou volatilidade, bloqueiam todos os sinais legítimos. Precisamos de uma gradação baseada no regime de mercado (Excelente, Bom, Fraco, Muito Fraco).

## Arquivos Afetados
- `ENGINE/common/operational.py`: Lógica de classificação de regime.
- `ENGINE/scanner/scanner_config.py`: Configuração dos thresholds adaptativos.
- `main.py`: Execução da classificação no início do ciclo.
- `ENGINE/diagnostic/advanced_report.py`: Diagnóstico Avançado.

## Critérios de Aceitação
- Thresholds adaptados dinamicamente no início de cada ciclo.
- Diagnóstico Avançado exibindo o regime detectado e os thresholds aplicados.
- Logs registrando o regime e os thresholds utilizados.
- Nenhuma alteração em: Scanner, Decision Engine, Risk Management.

## Plano de Rollback
Reversão dos commits em `scanner_config.py` e `main.py`.
