#!/usr/bin/env bash
# Depois do poder da v2: roda o multiverso e o C3 com a mediana própria (v3.md, análise D).
#
#   nohup tools/v3-cadeia.sh > v3-cadeia.log 2>&1 &
#
# Não commita nem publica.
set -uo pipefail
cd "$(dirname "$0")/../app"
PY=../venv/bin/python
echo "$(date '+%F %T') esperando o poder da v2"
while ps -eo args | grep -q "[v]2-poder pres"; do sleep 60; done
grep -q " fim$" ../v2-cadeia.log || sleep 120
echo "$(date '+%F %T') multiverso e mediana própria"
$PY -m tools.migracoes.2026-11-05-v2-multiverso > ../v2-multiverso.log 2>&1 &
$PY -m tools.migracoes.2026-11-05-v2-poder pres-2010 pres-2014 --mediana-propria > ../v3-poder-mediana-a.log 2>&1 &
wait
echo "$(date '+%F %T') fim"
