#!/usr/bin/env bash
# Segunda cadeia da v2: espera a primeira (tools/v2-cadeia.sh) e roda o multiverso.
#
#   nohup tools/v2-cadeia-2.sh > v2-cadeia-2.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../app"
echo "$(date '+%F %T') esperando a primeira cadeia"
while ps -eo args | grep -q "[v]2-cadeia.sh"; do sleep 60; done
grep -q " fim$" ../v2-cadeia.log || { echo "a primeira cadeia não terminou bem; parando"; exit 1; }
echo "$(date '+%F %T') multiverso"
../venv/bin/python -m tools.migracoes.2026-11-05-v2-multiverso > ../v2-multiverso.log 2>&1 || { echo "multiverso falhou"; exit 1; }
echo "$(date '+%F %T') fim"
