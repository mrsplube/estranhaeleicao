"""Coletor da apuração: baixa do TSE o que mudou e recalcula o estado.

Roda pelo cron, uma vez por minuto, fazendo `--ciclos` voltas espaçadas de
`--intervalo` segundos (4 × 15 s): o app oficial revalida a cada 30 s, então
assim chegamos antes ou junto dele.

    bin/cron-once.sh apuracao 58s venv/bin/python -m apuracao.coleta --ciclos 4 --intervalo 15

Por que não pesa no TSE nem no Pi:

- toda requisição é CONDICIONAL (`If-None-Match` com o ETag guardado): arquivo
  que não mudou volta 304, sem corpo. São 31 arquivos por volta;
- o estado só é recalculado quando algum arquivo mudou de verdade;
- a página pública nunca chama o TSE nem calcula nada: lê `data/estado.json`.

Arquivos em `apuracao/data/` (fora do git): `brutos/` (o último JSON de cada
fonte), `etags.json`, `estado.json`, `uf/{uf}.json`, `serie.jsonl` (a linha do
tempo da noite, um ponto por mudança) e `coleta.log`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import httpx

from apuracao import estado as est

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
# APURACAO_DADOS existe para o teste e o ensaio: apontam para uma pasta
# temporária com votos fictícios, sem tocar no estado de produção.
DADOS = Path(os.environ.get("APURACAO_DADOS") or Path(__file__).resolve().parent / "data")
BRUTOS = DADOS / "brutos"
POR_UF = DADOS / "uf"
ETAGS = DADOS / "etags.json"
ESTADO = DADOS / "estado.json"
SERIE = DADOS / "serie.jsonl"
MAJORITARIAS = DADOS / "majoritarias.json"
ELEITOS = DADOS / "eleitos.json"
PULSO = DADOS / "pulso.json"
HISTORICO = DADOS / "historico"
# A evolução da noite, arquivo por arquivo: só o que interessa à análise de SC
# (≈10 KB comprimido por versão). Sem isto sobra só a última foto e a série
# por partido, e a pergunta "quando fulano ficou garantido" não tem resposta.
GUARDAR_VERSOES = {"est_sc", "fed_sc", "gov_sc", "sen_sc", "pres_br", "ab_sc",
                   # 2º turno: o presidente por UF, para calibrar a previsão depois
                   *(f"pres_{uf}" for uf in est.UFS + ["zz"])}

FONTES = {
    "pres_br": "6257/dados/br/br-c0001-e006257-u.json",
    "gov_sc": "6259/dados/sc/sc-c0003-e006259-u.json",
    "sen_sc": "6259/dados/sc/sc-c0005-e006259-u.json",
    "est_sc": "6259/dados/sc/sc-c0007-e006259-u.json",
    **{f"fed_{uf}": f"6259/dados/{uf}/{uf}-c0006-e006259-u.json" for uf in est.UFS},
    # Acompanhamento: % apurado de cada município de SC e de cada UF, num arquivo
    # só (é o que o mapa do app oficial lê — `-ab.json`, achado no código dele).
    "ab_sc": "6259/dados/sc/sc-e006259-ab.json",
    "ab_br": "6259/dados/br/br-e006259-ab.json",
    # % apurado por município das outras UFs: a base por partido (2022) de cada
    # uma pesa contra ele para o esperado da Câmara inteira.
    **{f"ab_{uf}": f"6259/dados/{uf}/{uf}-e006259-ab.json" for uf in est.UFS if uf != "sc"},
    # Governador e Senado das outras 26 UFs (SC já está acima): aba de majoritárias.
    **{f"gov_{uf}": f"6259/dados/{uf}/{uf}-c0003-e006259-u.json" for uf in est.UFS if uf != "sc"},
    **{f"sen_{uf}": f"6259/dados/{uf}/{uf}-c0005-e006259-u.json" for uf in est.UFS if uf != "sc"},
}
PRAZO = httpx.Timeout(20.0, connect=5.0)

# 2º turno (25/10/2026): presidente e governador mudam de eleição (6258/6260);
# os arquivos de deputado já estão totalizados e saem da volta. Se SC não tiver
# 2º turno para governador, o TSE responde 404 e isso é "não há", não falha.
DIA_2T = "2026-10-25"
FONTES_2T = {
    "pres_br": "6258/dados/br/br-c0001-e006258-u.json",
    **{f"gov_{uf}": f"6260/dados/{uf}/{uf}-c0003-e006260-u.json" for uf in est.UFS},
    # Previsão do vencedor (apuracao/presidente.py): o presidente em cada UF (+ exterior)
    # e o % apurado de cada município, para projetar o que falta cidade a cidade.
    **{f"pres_{uf}": f"6258/dados/{uf}/{uf}-c0001-e006258-u.json" for uf in est.UFS + ["zz"]},
    **{f"abp_{uf}": f"6258/dados/{uf}/{uf}-e006258-ab.json" for uf in est.UFS + ["zz"]},
}
OPCIONAIS_2T = {f"gov_{uf}" for uf in est.UFS}
PRESIDENTE = DADOS / "presidente.json"
SERIE_PRES = DADOS / "serie_pres.jsonl"


def segundo_turno() -> bool:
    return os.environ.get("APURACAO_TURNO") == "2" or datetime.now().strftime("%Y-%m-%d") >= DIA_2T


def fontes_da_volta() -> dict[str, str]:
    """O que consultar nesta volta: no 2º turno, só os dois cargos que seguem,
    e nunca um arquivo que o TSE já marcou como totalizado."""
    if segundo_turno():
        return dict(FONTES_2T)
    volta = {}
    for chave, caminho in FONTES.items():
        d = _ler_json(BRUTOS / f"{chave}.json", None) if (BRUTOS / f"{chave}.json").exists() else None
        if d and d.get("tf") == "s":
            continue                      # totalização final: não muda mais
        volta[chave] = caminho
    return volta


def _gravar(caminho: Path, conteudo: str) -> None:
    """Escrita atômica: quem lê nunca pega o arquivo pela metade."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(conteudo, encoding="utf-8")
    os.replace(tmp, caminho)


def _ler_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def _guardar_versao(chave: str, texto: str) -> None:
    """Uma cópia comprimida por versão do TSE, nomeada pela hora DO ARQUIVO."""
    import gzip
    try:
        d = json.loads(texto)
        dg = "".join(reversed((d.get("dg") or "00/00/0000").split("/")))
        hg = (d.get("hg") or "00:00:00").replace(":", "")
        pasta = HISTORICO / chave
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{dg}-{hg}.json.gz"
        if not destino.exists():
            destino.write_bytes(gzip.compress(texto.encode("utf-8"), compresslevel=6))
    except (OSError, ValueError) as e:
        print(f"[{datetime.now():%H:%M:%S}] versão de {chave} não guardada: {e!r}", flush=True)


def baixar(cliente: httpx.Client, etags: dict) -> tuple[list[str], list[str]]:
    """Uma volta pelas fontes. Devolve (mudaram, falharam)."""
    fontes = fontes_da_volta()

    def um(chave: str):
        cab = {"User-Agent": "Mozilla/5.0 (apuracao projetoscaue.lol)"}
        if etags.get(chave) and (BRUTOS / f"{chave}.json").exists():
            cab["If-None-Match"] = etags[chave]
        try:
            r = cliente.get(f"{BASE}/{fontes[chave]}", headers=cab, timeout=PRAZO)
        except httpx.HTTPError as e:
            return chave, None, f"{type(e).__name__}"
        if r.status_code == 304:
            return chave, False, None
        if r.status_code in (403, 404) and segundo_turno() and chave in OPCIONAIS_2T:
            return chave, False, None     # cargo sem 2º turno nesta UF
        if r.status_code != 200:
            return chave, None, f"HTTP {r.status_code}"
        try:
            r.json()
        except ValueError:
            return chave, None, "JSON inválido"
        _gravar(BRUTOS / f"{chave}.json", r.text)
        etags[chave] = r.headers.get("etag", "")
        if chave in GUARDAR_VERSOES:
            _guardar_versao(chave, r.text)
        return chave, True, None

    mudaram, falharam = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for chave, mudou, erro in ex.map(um, fontes):
            if erro:
                falharam.append(f"{chave}: {erro}")
            elif mudou:
                mudaram.append(chave)
    _gravar(ETAGS, json.dumps(etags))
    return mudaram, falharam


def recalcular_2t() -> dict:
    """2º turno: só presidente e governadores mudam. As cadeiras de deputado
    (≈4 s de conta no Pi) ficam como o 1º turno deixou no estado.json."""
    from apuracao import presidente
    if not ESTADO.exists():
        return recalcular(completo=True)
    estado = _ler_json(ESTADO, {})
    brutos = {}
    for chave in FONTES_2T:
        d = _ler_json(BRUTOS / f"{chave}.json", None)
        if d:
            brutos[chave] = d
    for uf in est.UFS:                    # Senado e governador sem 2º turno: os do 1º
        for pref in ("gov", "sen"):
            if f"{pref}_{uf}" not in brutos:
                d = _ler_json(BRUTOS / f"{pref}_{uf}.json", None)
                if d:
                    brutos[f"{pref}_{uf}"] = d
    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    if "pres_br" in brutos:
        estado["presidente"] = est.majoritario(brutos["pres_br"])
    if "gov_sc" in brutos:
        estado["sc"]["governador"] = est.majoritario(brutos["gov_sc"])
    estado["gerado_em"] = agora
    estado.setdefault("fontes", {}).update(
        {k: f'{v.get("dg", "")} {v.get("hg", "")}'.strip() for k, v in brutos.items()
         if k == "pres_br" or k.startswith("gov_")})
    _gravar(ESTADO, json.dumps(estado, ensure_ascii=False, separators=(",", ":")))
    maj = est.extras(brutos, {})["majoritarias"]
    _gravar(MAJORITARIAS, json.dumps({"gerado_em": agora, **maj}, ensure_ascii=False, separators=(",", ":")))
    p = presidente.projetar(brutos)
    if p:
        p["gerado_em"] = agora
        _gravar(PRESIDENTE, json.dumps(p, ensure_ascii=False, separators=(",", ":")))
        ponto = presidente.ponto(p)
        ponto["ts"] = agora
        with SERIE_PRES.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ponto, ensure_ascii=False, separators=(",", ":")) + "\n")
    return estado


def recalcular(completo: bool = False) -> dict:
    """Lê os brutos, monta o estado, grava estado.json, uf/*.json e a série."""
    if segundo_turno() and not completo:
        return recalcular_2t()
    brutos = {}
    for chave in FONTES:
        d = _ler_json(BRUTOS / f"{chave}.json", None)
        if d:
            brutos[chave] = d
    estado, por_uf = est.montar(brutos)
    extra = est.extras(brutos, por_uf)
    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    estado["gerado_em"] = agora
    estado["fontes"] = {k: f'{v.get("dg", "")} {v.get("hg", "")}'.strip()
                        for k, v in brutos.items()}
    _gravar(ESTADO, json.dumps(estado, ensure_ascii=False, separators=(",", ":")))
    for uf, d in por_uf.items():
        _gravar(POR_UF / f"{uf}.json", json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    _gravar(MAJORITARIAS, json.dumps({"gerado_em": agora, **extra["majoritarias"]},
                                     ensure_ascii=False, separators=(",", ":")))
    _gravar(ELEITOS, json.dumps({"gerado_em": agora, "por_agremiacao": extra["eleitos"]},
                                ensure_ascii=False, separators=(",", ":")))
    ponto = est.ponto_da_serie(estado)
    ponto["ts"] = agora
    with SERIE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ponto, ensure_ascii=False, separators=(",", ":")) + "\n")
    return estado


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Coletor da apuração 2026")
    ap.add_argument("--ciclos", type=int, default=1)
    ap.add_argument("--intervalo", type=float, default=15.0)
    ap.add_argument("--forcar", action="store_true", help="recalcula mesmo sem mudança")
    a = ap.parse_args(argv)
    etags = _ler_json(ETAGS, {})
    with httpx.Client(http2=False, follow_redirects=False, timeout=PRAZO) as cliente:
        for i in range(a.ciclos):
            inicio = time.monotonic()
            mudaram, falharam = baixar(cliente, etags)
            # Pulso: a página distingue "nada mudou no TSE" de "o coletor parou".
            _gravar(PULSO, json.dumps({
                "conferido_em": datetime.now().astimezone().isoformat(timespec="seconds"),
                "falhas": len(falharam), "fontes": len(FONTES)}))
            if mudaram or a.forcar or not ESTADO.exists():
                e = recalcular()
                if segundo_turno():
                    p = _ler_json(PRESIDENTE, {})
                    resumo = " × ".join(f'{c["nm"]} {c["pct"]:.2f}% (proj. {c["proj"]:.2f}%, '
                                        f'{c["chance"]:.1f}%)' for c in p.get("candidatos", []))
                    resumo = f"presidente {(p.get('apuracao') or {}).get('pst', 0)}%: {resumo}"
                else:
                    sc = (e["sc"]["estadual"] or {}).get("apuracao", {})
                    resumo = f"ALESC {sc.get('pst', 0)}%"
                print(f"[{datetime.now():%H:%M:%S}] mudaram {len(mudaram)} "
                      f"({', '.join(mudaram[:6])}{'…' if len(mudaram) > 6 else ''}); "
                      f"{resumo} · falhas {len(falharam)}", flush=True)
                a.forcar = False
            if falharam:
                print(f"[{datetime.now():%H:%M:%S}] falhas: {'; '.join(falharam[:5])}",
                      flush=True)
            if i < a.ciclos - 1:
                time.sleep(max(0.0, a.intervalo - (time.monotonic() - inicio)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
