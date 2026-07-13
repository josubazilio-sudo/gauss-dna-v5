#!/bin/bash
# Deploy manual do QuantOS para o VPS (vps-gauss).
# Uso: ./deploy_vps.sh
#
# Envia o codigo fonte local para /opt/QuantOS no VPS (via tar sobre SSH,
# ja que nao ha rsync disponivel no Git Bash local) e reinicia o processo
# via pm2. Nao envia venv/, __pycache__/, .git/, MEMORY/ (dados de runtime
# do VPS, nao devem ser sobrescritos), archive/, LOGS/, DATA/, *.pyc nem
# .env — o .env e especifico de cada ambiente (modo LIVE/DEVELOPMENT,
# tokens, account size podem ser diferentes do local) e NUNCA deve ser
# sobrescrito por um deploy de codigo. Editar o .env do VPS direto por
# ssh quando precisar mudar algo la.

set -e

VPS_HOST="vps-gauss"
VPS_PATH="/opt/QuantOS"

echo "==> Empacotando codigo local..."
tar czf - \
  --exclude='.git' \
  --exclude='venv' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='MEMORY' \
  --exclude='archive' \
  --exclude='LOGS' \
  --exclude='DATA' \
  --exclude='*.log' \
  --exclude='.pytest_cache' \
  --exclude='node_modules' \
  --exclude='.env' \
  . | ssh "$VPS_HOST" "cd $VPS_PATH && tar xzf -"

echo "==> Codigo enviado. Reiniciando pm2..."
ssh "$VPS_HOST" "pm2 restart quantos"

echo "==> Aguardando 5s e checando status..."
sleep 5
ssh "$VPS_HOST" "pm2 list"

echo "==> Deploy concluido. Para ver logs: ssh $VPS_HOST 'pm2 logs quantos'"
