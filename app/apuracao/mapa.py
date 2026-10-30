"""Gera o mapa dos municípios de SC para a página da apuração (roda uma vez).

    venv/bin/python -m apuracao.mapa

A malha vem do IBGE (API de malhas, qualidade intermediária, ~450 KB de GeoJSON
com os 295 municípios) e sai como caminhos SVG já projetados, com o código do
TSE como chave — o TSE e o IBGE numeram municípios de jeitos diferentes, e o
config de municípios do TSE traz os dois (`cd` e `cdi`). O arquivo resultante
(`static/apuracao/sc-mapa.json`) é estático: o navegador baixa uma vez e
guarda; o que muda durante a noite (o % apurado) vem no estado.json.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import httpx

URL_MALHA = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/42"
             "?formato=application/vnd.geo%2Bjson&qualidade=intermediaria&intrarregiao=municipio")
URL_MUNICIPIOS = "https://resultados.tse.jus.br/oficial/ele2026/6259/config/mun-e006259-cm.json"
DESTINO = Path(__file__).resolve().parent.parent / "static" / "apuracao" / "sc-mapa.json"
LARGURA = 640


def gerar() -> dict:
    malha = httpx.get(URL_MALHA, timeout=60).json()
    config = httpx.get(URL_MUNICIPIOS, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).json()
    sc = next(a for a in config["abr"] if a["cd"].lower() == "sc")
    tse_de_ibge = {m["cdi"]: (m["cd"], m["nm"]) for m in sc["mu"]}

    aneis = []
    for f in malha["features"]:
        g = f["geometry"]
        poligonos = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        aneis.append((f["properties"]["codarea"], poligonos))
    xs = [p[0] for _, pol in aneis for poly in pol for anel in poly for p in anel]
    ys = [p[1] for _, pol in aneis for poly in pol for anel in poly for p in anel]
    lon0, lon1, lat0, lat1 = min(xs), max(xs), min(ys), max(ys)
    fx = math.cos(math.radians((lat0 + lat1) / 2))       # equirretangular corrigida
    k = LARGURA / ((lon1 - lon0) * fx)
    altura = round((lat1 - lat0) * k, 1)

    def ponto(p):
        return round((p[0] - lon0) * fx * k, 1), round((lat1 - p[1]) * k, 1)

    saida = {}
    for ibge, poligonos in aneis:
        cd, nome = tse_de_ibge.get(ibge, (None, None))
        if cd is None:
            continue
        partes, cx, cy, n = [], 0.0, 0.0, 0
        for poly in poligonos:
            for anel in poly:
                pts, ultimo = [], None
                for p in anel:
                    q = ponto(p)
                    if q != ultimo:
                        pts.append(q)
                        ultimo = q
                if len(pts) < 3:
                    continue
                partes.append("M" + " L".join(f"{x:g} {y:g}" for x, y in pts) + "Z")
                for x, y in pts:
                    cx, cy, n = cx + x, cy + y, n + 1
        saida[cd] = {"nm": nome, "d": "".join(partes),
                     "c": [round(cx / n, 1), round(cy / n, 1)] if n else [0, 0]}
    return {"largura": LARGURA, "altura": altura, "municipios": saida}


URL_MALHA_BR = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
                "?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=UF")
DESTINO_BR = DESTINO.parent / "br-mapa.json"
SIGLA_IBGE = {"11": "ro", "12": "ac", "13": "am", "14": "rr", "15": "pa", "16": "ap", "17": "to",
              "21": "ma", "22": "pi", "23": "ce", "24": "rn", "25": "pb", "26": "pe", "27": "al",
              "28": "se", "29": "ba", "31": "mg", "32": "es", "33": "rj", "35": "sp", "41": "pr",
              "42": "sc", "43": "rs", "50": "ms", "51": "mt", "52": "go", "53": "df"}


def _projetar(feicoes: list[tuple[str, list]], largura: int) -> tuple[dict, float]:
    """Caminhos SVG (equirretangular corrigida) e o centro de cada feição."""
    xs = [p[0] for _, pol in feicoes for poly in pol for anel in poly for p in anel]
    ys = [p[1] for _, pol in feicoes for poly in pol for anel in poly for p in anel]
    lon0, lon1, lat0, lat1 = min(xs), max(xs), min(ys), max(ys)
    fx = math.cos(math.radians((lat0 + lat1) / 2))
    k = largura / ((lon1 - lon0) * fx)
    saida = {}
    for chave, poligonos in feicoes:
        partes, cx, cy, n = [], 0.0, 0.0, 0
        for poly in poligonos:
            for anel in poly:
                pts, ultimo = [], None
                for p in anel:
                    q = (round((p[0] - lon0) * fx * k, 1), round((lat1 - p[1]) * k, 1))
                    if q != ultimo:
                        pts.append(q)
                        ultimo = q
                if len(pts) < 3:
                    continue
                partes.append("M" + " L".join(f"{x:g} {y:g}" for x, y in pts) + "Z")
                for x, y in pts:
                    cx, cy, n = cx + x, cy + y, n + 1
        saida[chave] = {"d": "".join(partes), "c": [round(cx / n, 1), round(cy / n, 1)] if n else [0, 0]}
    return saida, round((lat1 - lat0) * k, 1)


def gerar_br() -> dict:
    malha = httpx.get(URL_MALHA_BR, timeout=60).json()
    feicoes = []
    for f in malha["features"]:
        g = f["geometry"]
        sigla = SIGLA_IBGE.get(str(f["properties"]["codarea"]))
        if sigla:
            feicoes.append((sigla, [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]))
    ufs, altura = _projetar(feicoes, LARGURA)
    return {"largura": LARGURA, "altura": altura, "ufs": ufs}


def main() -> int:
    mapa = gerar()
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(mapa['municipios'])} municípios, {DESTINO.stat().st_size // 1024} KB → {DESTINO}")
    br = gerar_br()
    DESTINO_BR.write_text(json.dumps(br, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(br['ufs'])} UFs, {DESTINO_BR.stat().st_size // 1024} KB → {DESTINO_BR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
