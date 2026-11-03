"""v2, Etapa 1: tabela padrão por disputa (vencedor/perdedor), para qualquer ano.

    venv/bin/python -m tools.migracoes.2026-11-03-v2-tabelas [pres-2010 pres-2014 ...]

Ver `docs/v2-plano-execucao.md` (Etapa 1) e `docs/preregistro/v2.md` (seção 2).

A v1 guardava 13 e 22 em colunas fixas. A v2 compara 2026 com várias eleições,
em que o vencedor muda de número (2018: 17), então a tabela passa a ter os
papéis: W = vencedor do 2º turno, P = perdedor, O = demais candidatos do 1º
turno, BN = brancos + nulos (+ anulados sub judice), C = comparecimento.

Grava `apuracao/cache/v2/{id}.pkl` com `chaves`, `local`, `A` (colunas
W1, P1, O1, BN1, C1, W2, P2, BN2, C2), `aptos`, `hora` (epoch, NaN se não
houver), `sem_bio` (NaN se não houver) e `meta`.
"""
from __future__ import annotations

import csv
import io
import pickle
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / "apuracao/cache"
REF = CACHE / "ref"
SAIDA = CACHE / "v2"
W1, P1, O1, BN1, C1, W2, P2, BN2, C2 = range(9)
COLUNAS = ("W1", "P1", "O1", "BN1", "C1", "W2", "P2", "BN2", "C2")

PRESIDENTE = {
    # ano: (vencedor, perdedor, votação por seção, detalhe, candidatos anulados no 1º turno)
    2010: ("13", "45", REF / "2010/votacao_secao_2010_BR.zip", REF / "2010/detalhe_votacao_secao_2010.zip", set()),
    2014: ("13", "45", REF / "2014/votacao_secao_2014_BR.zip", REF / "2014/detalhe_votacao_secao_2014.zip", set()),
    2018: ("17", "13", REF / "2018/votacao_secao_2018_BR.zip", REF / "2018/detalhe_votacao_secao_2018.zip", set()),
    2022: ("13", "22", CACHE / "votacao_secao_2022_BR.zip", REF / "2022/detalhe_votacao_secao_2022.zip", set()),
    # 2026: o 28 foi anulado sub judice no 1º turno (mesma regra da v1, ANULADOS no C1).
    2026: ("13", "22", CACHE / "votacao_secao_2026_BR.zip", CACHE / "detalhe_votacao_secao_2026.zip", {"28"}),
}
BU = {2022: CACHE / "bu_secao_2022.pkl", 2026: CACHE / "bu_secao_2026.pkl"}


def _csv(z: zipfile.ZipFile, nome: str):
    return csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";", quotechar='"')


def _chave(r) -> tuple:
    return (r["SG_UF"].lower(), r["CD_MUNICIPIO"].zfill(5), int(r["NR_ZONA"]), int(r["NR_SECAO"]))


def _int(v) -> int:
    try:
        return max(int(v), 0)
    except (TypeError, ValueError):
        return 0


def _hora(s: str) -> float:
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except (TypeError, ValueError):
            pass
    return float("nan")


def presidente(ano: int) -> dict:
    w, p, arq_vot, arq_det, anulados = PRESIDENTE[ano]
    idx: dict[tuple, int] = {}
    linhas: list[list[float]] = []
    local: list[int] = []
    z = zipfile.ZipFile(arq_vot)
    for r in _csv(z, next(n for n in z.namelist() if n.lower().endswith(".csv"))):
        if r["CD_CARGO"] != "1":
            continue
        k = _chave(r)
        if k[0] == "zz":
            continue
        i = idx.get(k)
        if i is None:
            i = idx[k] = len(linhas)
            linhas.append([0.0] * 9)
            local.append(_int(r["NR_LOCAL_VOTACAO"]))
        lin, nr, q = linhas[i], r["NR_VOTAVEL"], _int(r["QT_VOTOS"])
        if r["NR_TURNO"] == "1":
            lin[C1] += q
            if nr in ("95", "96") or nr in anulados:
                lin[BN1] += q
            elif nr == w:
                lin[W1] += q
            elif nr == p:
                lin[P1] += q
            else:
                lin[O1] += q
        else:
            lin[C2] += q
            if nr in ("95", "96"):
                lin[BN2] += q
            elif nr == w:
                lin[W2] += q
            elif nr == p:
                lin[P2] += q
    A = np.array(linhas)
    chaves = list(idx)
    # Aptos e hora do 2º turno: detalhe da votação por seção, Presidente (`_BR.csv`).
    zd = zipfile.ZipFile(arq_det)
    nome = next(n for n in zd.namelist() if n.endswith("_BR.csv"))
    aptos = np.full(len(chaves), np.nan)
    hora = np.full(len(chaves), np.nan)
    for r in _csv(zd, nome):
        if r["NR_TURNO"] != "2" or r["CD_CARGO"] != "1":
            continue
        i = idx.get(_chave(r))
        if i is not None:
            aptos[i] = _int(r["QT_APTOS"])
            if r.get("DT_RECEBIMENTO_BU_HOR_TSE"):
                hora[i] = _hora(r["DT_RECEBIMENTO_BU_HOR_TSE"])
    sem_bio = np.full(len(chaves), np.nan)
    if ano in BU:
        bu = pickle.loads(BU[ano].read_bytes())
        for i, k in enumerate(chaves):
            b = bu.get(k)
            if b is not None:
                sem_bio[i] = b["sem_bio"]
    # Amostra: nos dois turnos, com válidos nos dois.
    v1 = A[:, W1] + A[:, P1] + A[:, O1]
    v2 = A[:, W2] + A[:, P2]
    ok = (v1 > 0) & (v2 > 0)
    descartes = {"sem_validos_em_um_turno": int((~ok).sum())}
    return {"id": f"pres-{ano}", "cargo": "presidente", "ano": ano, "vencedor": w, "perdedor": p,
            "colunas": COLUNAS, "chaves": [k for k, b in zip(chaves, ok) if b], "local": np.array(local)[ok],
            "A": A[ok], "aptos": aptos[ok], "hora": hora[ok], "sem_bio": sem_bio[ok],
            "meta": {"descartes": descartes, "fontes": {"votos": arq_vot.name, "aptos_hora": arq_det.name,
                                                       "sem_bio": BU[ano].name if ano in BU else None}}}


def _arquivos_governador(ano: int, uf: str) -> tuple[Path, Path]:
    if ano == 2026:
        return CACHE / f"votacao_secao_2026_{uf.upper()}.zip", CACHE / "detalhe_votacao_secao_2026.zip"
    return (REF / f"{ano}/uf/votacao_secao_{ano}_{uf.upper()}.zip",
            REF / f"{ano}/detalhe_votacao_secao_{ano}.zip")


def governador(ano: int, uf: str) -> dict:
    """Disputa de governador em 2º turno: vencedor e perdedor saem do próprio dado."""
    arq_vot, arq_det = _arquivos_governador(ano, uf)
    z = zipfile.ZipFile(arq_vot)
    votos: dict[tuple, dict] = {}
    total2: dict[str, int] = {}
    loc: dict[tuple, int] = {}
    for r in _csv(z, next(n for n in z.namelist() if n.lower().endswith(".csv"))):
        if r["CD_CARGO"] != "3":
            continue
        k = _chave(r)
        t = r["NR_TURNO"]
        d = votos.setdefault(k, {"1": {}, "2": {}})
        nr, q = r["NR_VOTAVEL"], _int(r["QT_VOTOS"])
        d[t][nr] = d[t].get(nr, 0) + q
        loc[k] = _int(r["NR_LOCAL_VOTACAO"])
        if t == "2" and nr not in ("95", "96"):
            total2[nr] = total2.get(nr, 0) + q
    w, p = sorted(total2, key=total2.get, reverse=True)[:2]
    chaves = [k for k, d in votos.items() if d["1"] and d["2"]]
    A = np.zeros((len(chaves), 9))
    for i, k in enumerate(chaves):
        d1, d2 = votos[k]["1"], votos[k]["2"]
        bn1 = d1.get("95", 0) + d1.get("96", 0)
        A[i, W1], A[i, P1] = d1.get(w, 0), d1.get(p, 0)
        A[i, BN1], A[i, C1] = bn1, sum(d1.values())
        A[i, O1] = A[i, C1] - A[i, W1] - A[i, P1] - bn1
        A[i, W2], A[i, P2] = d2.get(w, 0), d2.get(p, 0)
        A[i, BN2] = d2.get("95", 0) + d2.get("96", 0)
        A[i, C2] = sum(d2.values())
    idx = {k: i for i, k in enumerate(chaves)}
    zd = zipfile.ZipFile(arq_det)
    nome = next(n for n in zd.namelist() if n.endswith(f"_{uf.upper()}.csv"))
    aptos = np.full(len(chaves), np.nan)
    hora = np.full(len(chaves), np.nan)
    for r in _csv(zd, nome):
        if r["NR_TURNO"] != "2" or r["CD_CARGO"] != "3":
            continue
        i = idx.get(_chave(r))
        if i is not None:
            aptos[i] = _int(r["QT_APTOS"])
            if r.get("DT_RECEBIMENTO_BU_HOR_TSE"):
                hora[i] = _hora(r["DT_RECEBIMENTO_BU_HOR_TSE"])
    v1 = A[:, W1] + A[:, P1] + A[:, O1]
    v2 = A[:, W2] + A[:, P2]
    ok = (v1 > 0) & (v2 > 0)
    return {"id": f"gov-{ano}-{uf.lower()}", "cargo": "governador", "ano": ano, "uf": uf.lower(),
            "vencedor": w, "perdedor": p, "colunas": COLUNAS,
            "chaves": [k for k, b in zip(chaves, ok) if b], "local": np.array([loc[k] for k in chaves])[ok],
            "A": A[ok], "aptos": aptos[ok], "hora": hora[ok], "sem_bio": np.full(int(ok.sum()), np.nan),
            "meta": {"descartes": {"sem_validos_em_um_turno": int((~ok).sum())},
                     "fontes": {"votos": arq_vot.name, "aptos_hora": arq_det.name, "sem_bio": None}}}


def main() -> int:
    SAIDA.mkdir(exist_ok=True)
    pedidos = sys.argv[1:] or [f"pres-{a}" for a in PRESIDENTE]
    for pid in pedidos:
        partes = pid.split("-")
        ano = int(partes[1])
        t = presidente(ano) if partes[0] == "pres" else governador(ano, partes[2])
        A = t["A"]
        print(f"{pid}: {len(A):,} seções · W2 {A[:, W2].sum():,.0f} P2 {A[:, P2].sum():,.0f} · "
              f"aptos {np.isfinite(t['aptos']).mean():.1%} · hora {np.isfinite(t['hora']).mean():.1%} · "
              f"biometria {np.isfinite(t['sem_bio']).mean():.1%} · descartes {t['meta']['descartes']}", flush=True)
        (SAIDA / f"{pid}.pkl").write_bytes(pickle.dumps(t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
