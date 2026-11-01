"""Tabela por seção tirada do Boletim de Urna do 2º turno (2026 e 2022).

    venv/bin/python -m tools.migracoes.2026-11-01-bu-secao

Os testes C3–C6 do pré-registro precisam do que só o BU traz por seção: aptos
(para o comparecimento), hora de recebimento no TSE, eleitores sem biometria e
o voto de governador nas UFs com 2º turno. Este script lê os 28 zips de cada
ano uma vez e grava `apuracao/cache/bu_secao_{ano}.pkl`, com a mesma chave das
tabelas de votação por seção: `(uf minúscula, município com 5 dígitos, zona,
seção)`.

Conteúdo de cada entrada:
`{"aptos", "comp", "recebido" (epoch, s), "sem_bio", "gov": {número: votos},
"gov_validos"}` — `gov` só existe onde houve 2º turno de governador.
"""
from __future__ import annotations

import csv
import io
import pickle
import sys
import zipfile
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / "apuracao/cache"
PASTAS = {2026: CACHE / "bweb2026_2t", 2022: CACHE / "bweb2022"}
BIO = ("QT_ELEI_BIOM_SEM_HABILITACAO", "QT_ELEITORES_BIOMETRIA_NH")


def _hora(s: str) -> float | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            pass
    return None


def _int(v: str) -> int:
    try:
        return max(int(v), 0)
    except (TypeError, ValueError):
        return 0


def ler(ano: int) -> dict:
    tab: dict[tuple, dict] = {}
    for arq in sorted(PASTAS[ano].glob("*.zip")):
        z = zipfile.ZipFile(arq)
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        leitor = csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";")
        bio = next((c for c in BIO if c in (leitor.fieldnames or [])), None)
        for r in leitor:
            cargo = r["CD_CARGO_PERGUNTA"]
            if cargo not in ("1", "3"):
                continue
            k = (r["SG_UF"].lower(), r["CD_MUNICIPIO"].zfill(5), int(r["NR_ZONA"]), int(r["NR_SECAO"]))
            d = tab.get(k)
            if d is None:
                d = tab[k] = {"aptos": 0, "comp": 0, "recebido": None, "sem_bio": 0}
            if cargo == "1":
                d["aptos"], d["comp"] = _int(r["QT_APTOS"]), _int(r["QT_COMPARECIMENTO"])
                d["recebido"] = _hora(r["DT_BU_RECEBIDO"])
                d["sem_bio"] = _int(r[bio]) if bio else 0
            elif r["DS_TIPO_VOTAVEL"] in ("Nominal", "NOMINAL"):
                gov = d.setdefault("gov", {})
                gov[r["NR_VOTAVEL"]] = gov.get(r["NR_VOTAVEL"], 0) + _int(r["QT_VOTOS"])
        print(f"  {ano} {arq.name}: {len(tab):,} seções até aqui", flush=True)
    for d in tab.values():
        if "gov" in d:
            d["gov_validos"] = sum(d["gov"].values())
    return tab


def main() -> int:
    for ano in (2026, 2022):
        tab = ler(ano)
        com_gov = sum(1 for d in tab.values() if "gov" in d)
        (CACHE / f"bu_secao_{ano}.pkl").write_bytes(pickle.dumps(tab))
        print(f"{ano}: {len(tab):,} seções, {com_gov:,} com 2º turno de governador → bu_secao_{ano}.pkl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
