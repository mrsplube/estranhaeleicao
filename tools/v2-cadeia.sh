#!/usr/bin/env bash
# Cadeia da v2 que roda sozinha depois dos testes de governador (Etapas 4 a 7).
#
#   nohup tools/v2-cadeia.sh > v2-cadeia.log 2>&1 &
#
# Espera os dois processos `v2-testes gov-…` terminarem e roda, em ordem:
# calibração → leitura (meta-análise) → validação do poder → poder nas 4 bases
# (dois processos). Não commita nem publica: quem retomar confere os logs e os
# JSON e decide (ver docs/v2-plano-execucao.md). Cada etapa grava o seu log.
set -uo pipefail
cd "$(dirname "$0")/../app"
PY=../venv/bin/python
LOG=..

echo "$(date '+%F %T') esperando os testes de governador"
while ps -eo args | grep -q "[v]2-testes gov"; do sleep 60; done
n=$(ls apuracao/data/arquivo/2026-2t/v2/ | grep -cE '^gov-[0-9]{4}-[a-z]{2}\.json$')
echo "$(date '+%F %T') governadores: $n de 48 JSON"
[ "$n" -eq 48 ] || { echo "faltam disputas; parando"; exit 1; }

echo "$(date '+%F %T') calibração"
$PY -m tools.migracoes.2026-11-04-v2-calibracao > $LOG/v2-calibracao.log 2>&1 || { echo "calibração falhou"; exit 1; }
echo "$(date '+%F %T') leitura"
$PY -m tools.migracoes.2026-11-05-v2-leitura > $LOG/v2-leitura.log 2>&1 || { echo "leitura falhou"; exit 1; }
echo "$(date '+%F %T') validação do poder (pres-2022)"
$PY -m tools.migracoes.2026-11-05-v2-poder pres-2022 --validar > $LOG/v2-poder-validacao.log 2>&1 || { echo "validação falhou"; exit 1; }
echo "$(date '+%F %T') poder nas 4 bases"
$PY -m tools.migracoes.2026-11-05-v2-poder pres-2010 pres-2018 > $LOG/v2-poder-a.log 2>&1 &
$PY -m tools.migracoes.2026-11-05-v2-poder pres-2014 pres-2022 > $LOG/v2-poder-b.log 2>&1 &
wait
echo "$(date '+%F %T') fim"
