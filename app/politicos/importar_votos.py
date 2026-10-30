"""Importa a votação anterior de cada candidato, dos dados abertos do TSE.

É o melhor previsor que existe para a nominata — dentro do partido, quem senta
são os mais votados — e é de graça. O que faltava era um jeito de pegar: o
arquivo nacional de votos por candidato tem **556 MB** e o Pi não deve baixar
isso para usar 130.

Solução: o CDN do TSE aceita `Range`. Lê-se o fim do arquivo para achar o
diretório central do ZIP, o diretório para achar o membro de SC, e baixa-se só
esse membro. **7,2 MB em vez de 556** — 1,3% do arquivo.

    venv/bin/python -m politicos.importar_votos            # 2022 (estadual)
    venv/bin/python -m politicos.importar_votos --ano 2024 # municipal

Casamento por nome normalizado (sem acento, maiúsculas, ordenado): o CSV de
votação não traz CPF. Nome é frágil, então cada linha guarda o `nome_urna` que
casou, para conferência à mão quando algo parecer errado.
"""
from __future__ import annotations

import csv
import io
import re
import struct
import sys
import unicodedata
import urllib.request
import zlib
from collections import defaultdict

from politicos import db

UA = {"User-Agent": "Mozilla/5.0"}
URLS = {
    2022: "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/"
          "votacao_candidato_munzona_2022.zip",
    2024: "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/"
          "votacao_candidato_munzona_2024.zip",
}


def _faixa(url: str, ini: int, fim: int) -> bytes:
    req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={ini}-{fim}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _tamanho(url: str) -> int:
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Length"])


def baixar_uf(url: str, uf: str = "SC") -> bytes:
    """Devolve o CSV daquela UF, baixando só a fatia necessária do ZIP."""
    tam = _tamanho(url)
    cauda = _faixa(url, max(0, tam - 70000), tam - 1)
    i = cauda.rfind(b"PK\x05\x06")
    if i < 0:
        raise RuntimeError("EOCD não encontrado (arquivo mudou de formato?)")
    # EOCD: 4 assinatura | 2 disco | 2 disco-cd | 2 ent-disco | 2 ent-total
    #       | 4 tamanho-cd | 4 offset-cd
    _ent_disco, _ent_tot, cd_tam, cd_off = struct.unpack("<HHII", cauda[i + 8:i + 20])
    if cd_off == 0xFFFFFFFF:
        j = cauda.rfind(b"PK\x06\x06")
        if j < 0:
            raise RuntimeError("ZIP64 sem EOCD64")
        cd_tam = struct.unpack("<Q", cauda[j + 40:j + 48])[0]
        cd_off = struct.unpack("<Q", cauda[j + 48:j + 56])[0]

    cd = _faixa(url, cd_off, cd_off + cd_tam - 1)
    p, alvo = 0, None
    while p < len(cd) - 4 and cd[p:p + 4] == b"PK\x01\x02":
        csz, _usz = struct.unpack("<II", cd[p + 20:p + 28])
        nl, el, cl = struct.unpack("<HHH", cd[p + 28:p + 34])
        off = struct.unpack("<I", cd[p + 42:p + 46])[0]
        nome = cd[p + 46:p + 46 + nl].decode("latin-1")
        if nome.upper().endswith(f"_{uf}.CSV"):
            alvo = (nome, off, csz)
        p += 46 + nl + el + cl
    if not alvo:
        raise RuntimeError(f"membro de {uf} não encontrado no ZIP")

    _nome, off, csz = alvo
    bruto = _faixa(url, off, off + csz + 200)
    nl, el = struct.unpack("<HH", bruto[26:30])
    return zlib.decompress(bruto[30 + nl + el:30 + nl + el + csz], -15)


def _chave(nome: str) -> tuple:
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    return tuple(sorted(set(re.sub(r"[^A-Za-z ]", " ", s).upper().split())))


def importar(ano: int = 2022, uf: str = "SC", verbose: bool = True) -> dict:
    url = URLS.get(ano)
    if not url:
        raise ValueError(f"ano {ano} não mapeado")
    if verbose:
        print(f"→ baixando a fatia de {uf} do arquivo de {ano}…")
    dados = baixar_uf(url, uf)
    if verbose:
        print(f"  {len(dados)/1e6:.1f} MB de CSV")

    linhas = csv.DictReader(io.StringIO(dados.decode("latin-1")), delimiter=";")
    # Soma os votos do candidato por cargo (o arquivo é por município e zona).
    somas: dict[tuple, dict] = defaultdict(
        lambda: {"votos": 0, "situacao": "", "urna": "", "partido": "", "mun": set()})
    for r in linhas:
        if (r.get("NR_TURNO") or "1") != "1":
            continue
        cargo = (r.get("DS_CARGO") or "").upper()
        k = (_chave(r.get("NM_CANDIDATO", "")), cargo)
        d = somas[k]
        d["votos"] += int(r.get("QT_VOTOS_NOMINAIS") or 0)
        d["situacao"] = r.get("DS_SIT_TOT_TURNO") or d["situacao"]
        d["urna"] = r.get("NM_URNA_CANDIDATO") or d["urna"]
        d["partido"] = r.get("SG_PARTIDO") or d["partido"]
        if r.get("NM_MUNICIPIO"):
            d["mun"].add(r["NM_MUNICIPIO"])

    con = db.conectar()
    con.executescript(db.SCHEMA)
    perfis = con.execute(
        "SELECT id, nome, nome_completo FROM perfis WHERE acompanhar=1").fetchall()

    gravados = 0
    por_cargo: dict[str, int] = defaultdict(int)
    for p in perfis:
        ch = _chave(p["nome_completo"] or p["nome"])
        for (k_nome, cargo), d in somas.items():
            if k_nome != ch or d["votos"] <= 0:
                continue
            municipio = (next(iter(d["mun"])) if len(d["mun"]) == 1 else
                         f"{len(d['mun'])} municípios")
            con.execute(
                """INSERT OR REPLACE INTO v2_votos_candidato
                   (perfil_id, ano, cargo, votos, situacao, nome_urna, partido, municipio)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (p["id"], ano, cargo, d["votos"], d["situacao"], d["urna"],
                 d["partido"], municipio),
            )
            gravados += 1
            por_cargo[cargo] += 1
    con.commit()
    total = con.execute(
        "SELECT COUNT(DISTINCT perfil_id) n FROM v2_votos_candidato").fetchone()["n"]
    con.close()

    if verbose:
        print(f"  {gravados} registros gravados ({dict(por_cargo)})")
        print(f"  {total} dos {len(perfis)} candidatos acompanhados têm histórico")
    return {"gravados": gravados, "com_historico": total, "perfis": len(perfis)}


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Importa votação anterior do TSE")
    ap.add_argument("--ano", type=int, default=2022, choices=sorted(URLS))
    ap.add_argument("--uf", default="SC")
    a = ap.parse_args(argv)
    importar(a.ano, a.uf)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
