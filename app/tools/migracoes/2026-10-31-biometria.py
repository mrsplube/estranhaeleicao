"""Eleitores com biometria que não foram habilitados por ela, por UF e eleição.

    venv/bin/python -m tools.migracoes.2026-10-31-biometria

Fonte: "Boletim de Urna" (BU na Web), dadosabertos.tse.jus.br — o único arquivo
público que traz a contagem por seção de eleitores COM biometria cadastrada que
votaram sem ela (digital não reconhecida, liberado por documento com foto).

O campo mudou de nome: `QT_ELEITORES_BIOMETRIA_NH` em 2022 e
`QT_ELEI_BIOM_SEM_HABILITACAO` em 2026 (leia-me de cada pacote). Só conta a linha
do cargo 1 (Presidente), porque o BU repete os totais em cada cargo.

Grava apuracao/data/arquivo/2026-2t/biometria.json:
    {"fonte": ..., "eleicoes": [{"ano", "turno", "uf", "aptos", "votaram",
      "sem_bio", "secoes", "fonte_arquivo"}], ...}

Baixa para um zip temporário e apaga em seguida: o 1º turno de SP sozinho tem
1,4 GB. Nada de guardar os brutos.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "apuracao/data/arquivo/2026-2t/biometria.json"
API = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-{ano}-boletim-de-urna"
CAMPOS = ("QT_ELEITORES_BIOMETRIA_NH", "QT_ELEI_BIOM_SEM_HABILITACAO")


def recursos(ano: int) -> list[tuple[str, int, str, str]]:
    """(uf, turno, nome, url) de cada Boletim de Urna do ano."""
    pedido = urllib.request.Request(API.format(ano=ano), headers={"User-Agent": "estranhaeleicao/1.0"})
    pacote = json.load(urllib.request.urlopen(pedido, timeout=60))["result"]
    saida = []
    for r in pacote["resources"]:
        nome = r.get("name", "")
        if "boletim de urna" not in nome.lower() or "hash" in nome.lower():
            continue
        uf = nome.split(" - ")[0].strip()
        turno = 1 if "rimeiro turno" in nome else 2 if "egundo turno" in nome else 0
        if turno:
            saida.append((uf, turno, nome, r["url"]))
    return saida


def somar(zip_path: Path) -> tuple[int, int, int, int, int]:
    """(aptos, votaram, sem_bio, seções, linhas_ignoradas) de um zip de BU."""
    z = zipfile.ZipFile(zip_path)
    dentro = [n for n in z.namelist() if n.lower().endswith(".csv")]
    if not dentro:
        raise SystemExit(f"sem CSV em {zip_path}")
    leitor = csv.DictReader(io.TextIOWrapper(z.open(dentro[0]), encoding="latin-1"), delimiter=";", quotechar='"')
    campo = next((c for c in CAMPOS if c in (leitor.fieldnames or [])), None)
    secoes: dict[tuple[str, str, str], tuple[int, int, int]] = {}
    for row in leitor:
        if row.get("CD_CARGO_PERGUNTA") != "1":
            continue
        chave = (row["CD_MUNICIPIO"], row["NR_ZONA"], row["NR_SECAO"])
        bruto = (row.get(campo) or "0") if campo else "0"
        # #NULO/-1 e #NE/-3 não são contagem: viram zero. (Nos arquivos do exterior
        # o campo vem assim e, sem isso, o total nacional saía negativo.)
        sem = max(int(bruto.replace("#NULO#", "0").replace("#NE#", "0") or 0), 0)
        secoes[chave] = (int(row["QT_APTOS"] or 0), int(row["QT_COMPARECIMENTO"] or 0), sem)
    aptos = sum(v[0] for v in secoes.values())
    votaram = sum(v[1] for v in secoes.values())
    sem_bio = sum(v[2] for v in secoes.values())
    return aptos, votaram, sem_bio, len(secoes), (0 if campo else 1)


def baixar(url: str, destino: Path) -> None:
    pedido = urllib.request.Request(url, headers={"User-Agent": "estranhaeleicao/1.0"})
    with urllib.request.urlopen(pedido, timeout=900) as r, open(destino, "wb") as f:
        while True:
            bloco = r.read(1 << 20)
            if not bloco:
                break
            f.write(bloco)


def main() -> int:
    anos = [int(a) for a in sys.argv[1:]] or [2022, 2026]
    registros = []
    for ano in anos:
        for uf, turno, nome, url in recursos(ano):
            with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
                arq = Path(tmp) / "bu.zip"
                print(f"  {ano} {turno}º {uf} …", flush=True)
                baixar(url, arq)
                aptos, votaram, sem_bio, secoes, faltou = somar(arq)
            if faltou:
                print(f"    {uf}: sem o campo de biometria (não entra)", flush=True)
                continue
            registros.append({"ano": ano, "turno": turno, "uf": uf, "aptos": aptos, "votaram": votaram,
                              "sem_bio": sem_bio, "secoes": secoes, "fonte_arquivo": nome})
            print(f"    {votaram:,} votaram, {sem_bio:,} sem biometria ({100*sem_bio/max(votaram,1):.3f}%)", flush=True)
    # Mescla com o que já existe: rodar só um ano não apaga o outro.
    antigos = []
    if DESTINO.exists():
        antigos = json.loads(DESTINO.read_text(encoding="utf-8")).get("eleicoes", [])
    novos = {(r["ano"], r["turno"], r["uf"]): r for r in antigos}
    for r in registros:
        novos[(r["ano"], r["turno"], r["uf"])] = r
    tudo = [novos[k] for k in sorted(novos)]
    DESTINO.write_text(json.dumps({"fonte": "Boletim de Urna (BU na Web), dadosabertos.tse.jus.br",
                                   "gerado_em": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                                   "eleicoes": tudo}, ensure_ascii=False), encoding="utf-8")
    print(f"ok — {len(registros)} registros em {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
