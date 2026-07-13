# PROMPT OFICIAL — RFC V18.5.1
QUANTOS — ELIMINAÇÃO DE ATUALIZAÇÕES DUPLICADAS
Status: APROVADO
Prioridade: CRÍTICA
Compatível: V18.4+

==================================================================
OBJETIVO
==================================================================

Atualmente o QuantOS envia uma atualização a cada ciclo do scanner mesmo quando praticamente nada mudou.

Isso gera:

- excesso de mensagens no Telegram;
- repetição de informações;
- dificuldade para acompanhar operações;
- perda de impacto dos sinais realmente importantes.

A partir desta RFC o sistema deverá enviar apenas atualizações relevantes.

Nenhum cálculo institucional poderá ser alterado.

O motor de decisão permanece exatamente igual.

==================================================================
CRIAR UM UPDATE ENGINE
==================================================================

Criar um módulo responsável por comparar:

Sinal anterior
vs
Sinal atual

Caso nenhuma mudança relevante tenha ocorrido:

NÃO enviar atualização.

==================================================================
REGRAS PARA ENVIAR UMA NOVA ATUALIZAÇÃO
==================================================================

Enviar atualização SOMENTE quando ocorrer pelo menos UMA das condições abaixo.

1)

Score variar

>= 2.0 pontos

2)

Qualidade variar

>= 2.0 pontos

3)

Probabilidade variar

>= 3%

4)

Confiança variar

>= 3%

5)

Consenso variar

>= 5%

6)

Confluência variar

>= 5%

7)

Liquidez variar

>= 10%

8)

Fluxo mudar significativamente.

9)

Mudança de Tendência

Exemplo

Trending Up
↓

Trending Down

10)

Mudança do Kalman

UP
↓

DOWN

11)

Mudança da Convicção

Alta
↓

Média

ou

Alta
↓

Baixa

12)

Stop alterado.

13)

Take Profit alterado.

14)

Entrada recalculada.

15)

Mudança do RR.

16)

Mudança da direção

LONG

↓

SHORT

ou

SHORT

↓

LONG

==================================================================
NÃO ENVIAR UPDATE QUANDO
==================================================================

Ignorar atualizações quando ocorrer apenas:

variação pequena do score
pequena mudança de liquidez
tempo de processamento
novo ciclo
pequenas oscilações estatísticas
mudanças inferiores aos thresholds definidos

==================================================================
CLASSIFICAÇÃO DA ATUALIZAÇÃO
==================================================================

Caso o setup melhore:

📈 SETUP FORTALECIDO

Caso o setup enfraqueça:

📉 SETUP ENFRAQUECIDO

Caso apenas TP seja alterado:

🎯 TAKE PROFIT ATUALIZADO

Caso apenas Stop seja alterado:

🛡 STOP AJUSTADO

Caso a direção mude:

🔄 REVERSÃO DE TENDÊNCIA

==================================================================
CANCELAMENTO DO SINAL
==================================================================

Caso o setup deixe de atender o Quality Gate.

Enviar:

❌ SINAL CANCELADO

Motivos possíveis:

• Score abaixo do mínimo
• Consenso perdido
• Estrutura rompida
• Tendência invalidada
• Fluxo institucional desapareceu
• Risco elevado

Após cancelar:

Não enviar novas atualizações até surgir um novo sinal válido.

==================================================================
ENCERRAMENTO AUTOMÁTICO
==================================================================

Quando TP for atingido:

✅ OPERAÇÃO ENCERRADA

Resultado:

🟢 TAKE PROFIT ATINGIDO

Lucro:
XX %

==================================================================

Quando Stop for atingido:

🔴 OPERAÇÃO ENCERRADA

Resultado:

Stop Loss

Perda:
XX %

==================================================================
HISTÓRICO DA OPERAÇÃO
==================================================================

Cada Signal ID deverá possuir um ciclo de vida.

NOVO SINAL

↓

ATUALIZAÇÕES RELEVANTES

↓

TP

ou

STOP

ou

CANCELADO

Nunca criar novo Signal ID enquanto for a mesma operação.

==================================================================
COMPATIBILIDADE
==================================================================

Esta RFC NÃO pode alterar:

Decision Engine
Quality Gate
Confluence Engine
Risk Engine
Entry Engine
Take Profit Engine
Scanner
Filtros institucionais
Cálculo de Score
Cálculo de Probabilidade
Cálculo de Confiança

A alteração deve ocorrer exclusivamente na camada de gerenciamento
e envio das notificações.

==================================================================
OBJETIVO FINAL
==================================================================

Transformar o Telegram do QuantOS em um painel profissional.

Cada mensagem deve representar um evento importante.

Eliminar completamente mensagens duplicadas.

Eliminar spam.

Preservar o histórico limpo da operação.

Nenhuma lógica institucional poderá ser alterada.

Scanner, Decision Engine, Quality Gate, Risk Engine,
Confluence Engine e demais módulos permanecem exatamente iguais.

A alteração deve ocorrer exclusivamente na camada de gerenciamento
e envio das notificações.
