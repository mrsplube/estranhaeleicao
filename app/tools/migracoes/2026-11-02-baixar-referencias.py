"""Baixa os arquivos da classe de referência do pré-registro v2, sem abri-los.

    venv/bin/python -m tools.migracoes.2026-11-02-baixar-referencias

O adendo v2 (docs/preregistro/v2.md, seção 1) diz que as eleições novas não são
abertas antes de o SHA-256 delas estar registrado. Este script só baixa e
calcula o hash: grava em `apuracao/cache/ref/` e acrescenta cada arquivo a
`docs/preregistro/insumos-v2.sha256`. Nenhum CSV é lido aqui.

Arquivos: votação por seção (BR) e detalhe da votação por seção de 2010, 2014,
2018 e 2022 (o detalhe de 2022 dá os aptos por seção do mesmo jeito que nos
outros anos), o Boletim de Urna do 2º turno de 2014 e 2018 e a votação por
seção por UF das disputas de governador em 2º turno (lista em GOVERNADOR).
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "apuracao/cache/ref"
HASHES = RAIZ.parent / "docs/preregistro/insumos-v2.sha256"
CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
API = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-{ano}-boletim-de-urna"
UA = {"User-Agent": "estranhaeleicao/1.0"}


# Disputas de governador em 2º turno com ≥ 2.000 seções (v2.md, seção 2), tiradas do
# detalhe da votação por seção (cargo 3, turno 2) em 03/11/2026.
GOVERNADOR = {
    2010: ("AL", "DF", "GO", "PA", "PB", "PI", "RO"),
    2014: ("AM", "CE", "DF", "GO", "MS", "PA", "PB", "RJ", "RN", "RO", "RS"),
    2018: ("AM", "DF", "MG", "MS", "PA", "RJ", "RN", "RO", "RS", "SC", "SE", "SP"),
    2022: ("AL", "AM", "BA", "ES", "MS", "PB", "PE", "RO", "RS", "SC", "SE", "SP"),
}


def _lista() -> list[tuple[str, str]]:
    """(caminho relativo em ref/, url)."""
    saida = []
    for ano in (2010, 2014, 2018):
        saida.append((f"{ano}/votacao_secao_{ano}_BR.zip", f"{CDN}/votacao_secao/votacao_secao_{ano}_BR.zip"))
    for ano in (2010, 2014, 2018, 2022):
        saida.append((f"{ano}/detalhe_votacao_secao_{ano}.zip", f"{CDN}/detalhe_votacao_secao/detalhe_votacao_secao_{ano}.zip"))
    for ano, ufs in GOVERNADOR.items():
        for uf in ufs:
            saida.append((f"{ano}/uf/votacao_secao_{ano}_{uf}.zip", f"{CDN}/votacao_secao/votacao_secao_{ano}_{uf}.zip"))
    for ano in (2014, 2018):
        pacote = json.load(urllib.request.urlopen(urllib.request.Request(API.format(ano=ano), headers=UA), timeout=60))
        for r in pacote["result"]["resources"]:
            nome = r.get("name", "")
            if "Segundo turno" in nome and "oletim de urna" in nome:
                saida.append((f"{ano}/bweb/{r['url'].rsplit('/', 1)[1]}", r["url"]))
    return saida


def _baixar(url: str, arq: Path) -> str:
    arq.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    tmp = arq.with_suffix(arq.suffix + ".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800) as r, open(tmp, "wb") as f:
        while bloco := r.read(1 << 20):
            f.write(bloco)
            h.update(bloco)
    tmp.replace(arq)
    return h.hexdigest()


def main() -> int:
    feitos = set()
    if HASHES.exists():
        feitos = {l.split()[1] for l in HASHES.read_text().splitlines() if l.strip()}
    for rel, url in _lista():
        if rel in feitos:
            continue
        print(f"  {rel}", flush=True)
        dig = _baixar(url, DESTINO / rel)
        with HASHES.open("a") as f:
            f.write(f"{dig}  {rel}\n")
    print(f"→ {HASHES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
