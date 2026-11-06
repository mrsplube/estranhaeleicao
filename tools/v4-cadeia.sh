#!/usr/bin/env bash
# Depois da correção do REML (v2.md §8, 06/11): refaz o P1, a análise D, a validação e a análise G.
#
#   nohup tools/v4-cadeia.sh > v4-cadeia.log 2>&1 &
#
# Não commita nem publica.
set -uo pipefail
cd "$(dirname "$0")/../app"
PY=../venv/bin/python
echo "$(date '+%F %T') início"
(
  $PY -m tools.migracoes.2026-11-05-v2-poder pres-2010 pres-2014 > ../v4-p1-a.log 2>&1
  $PY -m tools.migracoes.2026-11-05-v2-poder pres-2010 pres-2014 --mediana-propria > ../v4-mediana.log 2>&1
) &
(
  $PY -m tools.migracoes.2026-11-05-v2-poder pres-2018 pres-2022 > ../v4-p1-b.log 2>&1
  $PY -m tools.migracoes.2026-11-05-v2-poder pres-2022 --validar > ../v4-validacao.log 2>&1
  $PY -m tools.migracoes.2026-11-06-v4-poder-lacunas pres-2010 pres-2014 pres-2018 pres-2022 > ../v4-lacunas.log 2>&1
) &
wait
echo "$(date '+%F %T') fim"
