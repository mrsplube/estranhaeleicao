"""Voto de cada candidato de SC por MUNICÍPIO — o insumo do esperado fino.

    bin/cron-once.sh apuracao-mun 110s venv/bin/python -m apuracao.municipal

O esperado "pela base" dividia o total do candidato pela fração da base já
apurada, olhando o estado inteiro de uma vez. Com o voto por município dá para
fazer certo, cidade a cidade: onde já se apurou uma parte, projeta-se o voto
dele ali (votos ÷ fração apurada daquela cidade); onde nada se apurou, usa-se
a base de 2022 dele no ritmo que ele vem fazendo nas cidades já contadas.
Quando Joinville começa a contar, o candidato de Joinville passa a ser medido
pelo voto real de Joinville, e não mais pela base de 2022.

São 295 arquivos por cargo (`sc{município}-c000X-e006259-u.json`), por isso
roda num job à parte, a cada 2 minutos, com ETag (arquivo que não mudou volta
304 e não pesa). Grava `data/mun_votos_{cargo}.json`:

    {"gerado_em": ..., "mun": {código: {"frac": eleitores apurados / total,
                                         "c": {número: votos}, "l": {agremiação: legenda}}}}
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import httpx

from politicos import eleicao

DADOS = Path(os.environ.get("APURACAO_DADOS") or Path(__file__).resolve().parent / "data")
CARGOS = {"est": "c0007", "fed": "c0006"}
BASE = "https://resultados.tse.jus.br/oficial/ele2026/6259/dados/sc"
PRAZO = httpx.Timeout(15.0, connect=5.0)


def _municipios() -> list[str]:
    mapa = json.loads((Path(__file__).resolve().parent.parent / "static" / "apuracao" / "sc-mapa.json")
                      .read_text(encoding="utf-8"))
    return sorted(mapa["municipios"])


def _compacto(d: dict) -> dict:
    e = d.get("e") or {}
    te = int(e.get("te") or 0)
    votos, legenda = {}, {}
    for a in d["carg"][0]["agr"]:
        canon = eleicao.agremiacao_do_tse(a["nm"], [p["sg"] for p in a["par"]])
        for p in a["par"]:
            if p.get("dvt", "") == "Anulado":
                continue
            legenda[canon] = legenda.get(canon, 0) + int(p.get("tvtl") or 0)
            for c in p["cand"]:
                v = int(c.get("vap") or 0)
                if v:
                    votos[c["n"]] = v
    return {"frac": round(int(e.get("est") or 0) / te, 4) if te else 0.0, "te": te,
            "c": votos, "l": {k: v for k, v in legenda.items() if v}}


def coletar(cargo: str) -> tuple[int, int]:
    """Uma passada pelos 295 municípios. Devolve (mudaram, falharam)."""
    cache_dir = DADOS / "mun_cache" / cargo
    cache_dir.mkdir(parents=True, exist_ok=True)
    etags_arq = cache_dir / "_etags.json"
    try:
        etags = json.loads(etags_arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        etags = {}
    destino = DADOS / f"mun_votos_{cargo}.json"
    try:
        atual = json.loads(destino.read_text(encoding="utf-8"))["mun"]
    except (OSError, ValueError, KeyError):
        atual = {}

    def um(cliente: httpx.Client, cd: str):
        cab = {"User-Agent": "Mozilla/5.0 (apuracao projetoscaue.lol)"}
        if etags.get(cd) and cd in atual:
            cab["If-None-Match"] = etags[cd]
        try:
            r = cliente.get(f"{BASE}/sc{cd}-{CARGOS[cargo]}-e006259-u.json", headers=cab, timeout=PRAZO)
        except httpx.HTTPError:
            return cd, None, True
        if r.status_code == 304:
            return cd, None, False
        if r.status_code != 200:
            return cd, None, True
        try:
            return cd, (r.headers.get("etag", ""), _compacto(r.json())), False
        except (ValueError, KeyError, IndexError):
            return cd, None, True

    mudaram = falharam = 0
    with httpx.Client(timeout=PRAZO) as cliente, ThreadPoolExecutor(max_workers=8) as ex:
        for cd, novo, falhou in ex.map(lambda cd: um(cliente, cd), _municipios()):
            if falhou:
                falharam += 1
            elif novo:
                etags[cd], atual[cd] = novo
                mudaram += 1
    if mudaram:
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(json.dumps({"gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
                                   "mun": atual}, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, destino)
        etags_arq.write_text(json.dumps(etags), encoding="utf-8")
    return mudaram, falharam


def carregar(cargo: str) -> dict | None:
    try:
        return json.loads((DADOS / f"mun_votos_{cargo}.json").read_text(encoding="utf-8"))["mun"]
    except (OSError, ValueError, KeyError):
        return None


def main(argv: list[str]) -> int:
    for cargo in (argv or ["est", "fed"]):
        mudaram, falharam = coletar(cargo)
        print(f"[{datetime.now():%H:%M:%S}] municípios {cargo}: {mudaram} mudaram, {falharam} falharam", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
