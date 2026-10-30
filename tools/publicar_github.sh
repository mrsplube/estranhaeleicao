#!/usr/bin/env bash
# Publica o código no GitHub (repositório público) SEM as notas internas.
#
# O branch local `publico` é uma linha de história separada: cada execução põe
# lá um commit com a árvore do HEAD menos `docs/historico/` (notas de trabalho com
# caminhos do homelab) e empurra para o `main` do remoto `github`.
#
#   tools/publicar_github.sh "mensagem do commit"
#
# O token fica em ~/.config/estranhaeleicao/github-token (600), nunca no git.
set -euo pipefail
cd "$(dirname "$0")/.."
MSG="${1:-Atualiza o código do estranhaeleicao.org}"
FORA=(docs/historico)

git diff --quiet HEAD || { echo "há mudanças sem commit; faça o commit antes" >&2; exit 1; }
idx=$(mktemp); trap 'rm -f "$idx"' EXIT
GIT_INDEX_FILE="$idx" git read-tree HEAD
for p in "${FORA[@]}"; do GIT_INDEX_FILE="$idx" git rm -r -q --cached --ignore-unmatch "$p"; done
arvore=$(GIT_INDEX_FILE="$idx" git write-tree)
pai=$(git rev-parse -q --verify refs/heads/publico || true)
if [ -n "$pai" ] && [ "$(git rev-parse "$pai^{tree}")" = "$arvore" ]; then echo "nada novo para publicar"; exit 0; fi
commit=$(git commit-tree "$arvore" ${pai:+-p "$pai"} -m "$MSG")
git update-ref refs/heads/publico "$commit"
git push github publico:main
