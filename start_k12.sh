#!/bin/bash
cd /root/gauss-dna-v5 || exit 1
pkill -f runner.py 2>/dev/null
sleep 2
if screen -ls | grep -q .k11; then
  screen -S k11 -X quit
  sleep 2
fi
if screen -ls | grep -q .k12; then
  screen -S k12 -X quit
  sleep 2
fi
screen -dmS k12 bash -c 'cd /root/gauss-dna-v5; while true; do python3 k11-signal-bot/runner.py; sleep 300; done'
sleep 3
screen -ls
