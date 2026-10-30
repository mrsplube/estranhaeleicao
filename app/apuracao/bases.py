"""De onde vêm os votos de cada candidato de SC: a "base", município a município.

    venv/bin/python -m apuracao.bases        # gera apuracao/data/bases.json

Serve a uma pergunta da noite da apuração: dos votos que o candidato deve ter,
quanto já foi apurado? Capital e interior chegam em ritmos diferentes, e um
candidato do oeste pode parecer fraco às 19h só porque o oeste ainda não
contou. A base é a melhor pista de onde estão os votos dele:

1. quem disputou em 2022 (qualquer cargo) usa a SUA distribuição de 2022,
   casada pelo nome completo (o arquivo de 2026 traz o nome completo);
2. quem não disputou usa a distribuição da agremiação em 2022 (nas
   agremiações de 2026: PP + UNIÃO juntos, PTB + Patriota no PRD...);
3. sem nada disso, a distribuição do eleitorado.

É um chute com método, e a tela diz qual dos três sustenta cada número.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import datetime
from pathlib import Path

from politicos import eleicao
from politicos.importar_votos import URLS, _chave, baixar_uf

DADOS = Path(__file__).resolve().parent / "data"
DESTINO = DADOS / "bases.json"
CARGOS = {"est": ("DEPUTADO ESTADUAL", "est_sc"), "fed": ("DEPUTADO FEDERAL", "fed_sc")}
PISO_FATIA = 0.0005


def _normalizar(votos: dict[str, int]) -> dict[str, float]:
    total = sum(votos.values())
    if not total:
        return {}
    return {cd: round(v / total, 5) for cd, v in votos.items() if v / total >= PISO_FATIA}


def gerar() -> dict:
    cands_2022: dict[str, dict] = {}
    agr_2022: dict[str, dict[str, dict[str, int]]] = {"est": {}, "fed": {}}
    eleitorado: dict[str, int] = {}
    for r in csv.DictReader(io.StringIO(baixar_uf(URLS[2022], "SC").decode("latin-1")), delimiter=";"):
        cargo = r["DS_CARGO"].upper()
        tipo = next((t for t, (c, _) in CARGOS.items() if c == cargo), None)
        try:
            v = int(r.get("QT_VOTOS_NOMINAIS_VALIDOS") or 0)
        except ValueError:
            v = 0
        cd = r["CD_MUNICIPIO"].zfill(5)
        d = cands_2022.setdefault(r["SQ_CANDIDATO"], {"nome": r["NM_CANDIDATO"], "cargo": cargo, "mun": {},
                                                      "urna": r["NM_URNA_CANDIDATO"],
                                                      "partido": r["SG_PARTIDO"].upper().replace(" ", ""),
                                                      "eleito": r["DS_SIT_TOT_TURNO"].upper().startswith("ELEITO")})
        d["mun"][cd] = d["mun"].get(cd, 0) + v
        if tipo:
            sg = r["SG_PARTIDO"].upper().replace(" ", "")
            if sg in eleicao.LEGENDA_2026_DE_2022 and eleicao.LEGENDA_2026_DE_2022[sg] is None:
                agr = None
            else:
                agr = eleicao.LEGENDA_2026_DE_2022.get(sg) or eleicao.sigla_para_legenda(sg)
            if agr:
                m = agr_2022[tipo].setdefault(agr, {})
                m[cd] = m.get(cd, 0) + v
            if cargo == "DEPUTADO ESTADUAL":
                eleitorado[cd] = eleitorado.get(cd, 0) + v   # proxy do eleitorado: voto válido total

    por_nome: dict[tuple, list[dict]] = {}
    for d in cands_2022.values():
        por_nome.setdefault(_chave(d["nome"]), []).append(d)

    saida = {"gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
             "eleitorado": _normalizar(eleitorado), "agr": {}, "est": {}, "fed": {}}
    for tipo in CARGOS:
        saida["agr"][tipo] = {agr: _normalizar(m) for agr, m in agr_2022[tipo].items()}
    # Quem concorre a quê em 2026 (pelo nome completo), para dizer para onde foi
    # quem foi eleito em 2022 e não está na mesma disputa.
    cargos_26: dict[tuple, list[tuple[str, str]]] = {}
    for chave, rotulo in (("est_sc", "deputado estadual"), ("fed_sc", "deputado federal"),
                          ("gov_sc", "governador"), ("sen_sc", "senador")):
        try:
            arq = json.loads((DADOS / "brutos" / f"{chave}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for a in arq["carg"][0]["agr"]:
            for p in a["par"]:
                for c in p["cand"]:
                    cargos_26.setdefault(_chave(c["nm"]), []).append((rotulo, c["n"]))
    saida["mandato"] = {}
    for tipo, (cargo, chave) in CARGOS.items():
        rot = "deputado estadual" if tipo == "est" else "deputado federal"
        lista = []
        for d in cands_2022.values():
            if d["cargo"] != cargo or not d["eleito"]:
                continue
            onde = cargos_26.get(_chave(d["nome"]), [])
            mesmo = next((n for r_, n in onde if r_ == rot), None)
            outro = next((r_ for r_, _ in onde if r_ != rot), None)
            agr = eleicao.LEGENDA_2026_DE_2022.get(d["partido"]) or eleicao.sigla_para_legenda(d["partido"])
            lista.append({"nm": d["urna"], "p": d["partido"], "a": agr, "n26": mesmo, "outro": outro})
        saida["mandato"][tipo] = lista
    for tipo, (cargo, chave) in CARGOS.items():
        arquivo = json.loads((DADOS / "brutos" / f"{chave}.json").read_text(encoding="utf-8"))
        for a in arquivo["carg"][0]["agr"]:
            canon = eleicao.agremiacao_do_tse(a["nm"], [p["sg"] for p in a["par"]])
            for p in a["par"]:
                for c in p["cand"]:
                    achados = por_nome.get(_chave(c["nm"]), [])
                    # Homônimo em cargos diferentes de 2022 é a MESMA pessoa trocando de
                    # cargo; dois no mesmo cargo é ambíguo — melhor sem base própria.
                    if len({x["cargo"] for x in achados}) == len(achados) and achados:
                        mesmo = [x for x in achados if x["cargo"] == cargo]
                        melhor = (mesmo or sorted(achados, key=lambda x: -sum(x["mun"].values())))[0]
                        if sum(melhor["mun"].values()) > 0:
                            saida[tipo][c["n"]] = {"f": "2022" if melhor["cargo"] == cargo else "2022-outro-cargo",
                                                   "s": _normalizar(melhor["mun"]),
                                                   "e22": melhor["cargo"] == cargo and melhor["eleito"]}
                            continue
                    if saida["agr"][tipo].get(canon):
                        saida[tipo][c["n"]] = {"f": "partido", "a": canon}
                    else:
                        saida[tipo][c["n"]] = {"f": "eleitorado"}
    return saida


URL_PARTIDO_2022 = ("https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_partido_munzona/"
                    "votacao_partido_munzona_2022.zip")
DESTINO_BR = DADOS / "bases_br.json"


def gerar_br() -> dict:
    """A base das AGREMIAÇÕES de 2026 em cada UF, para deputado federal.

    Fora de SC não montamos base por candidato (seria baixar o arquivo de
    votação por candidato do Brasil inteiro, 556 MB); a votação por PARTIDO de
    2022 tem 25 MB e basta para o que importa no total da Câmara: onde cada
    partido é forte e quanto disso já foi apurado. Dentro do partido, a ordem
    dos candidatos fica a de agora.
    """
    import urllib.request
    import zipfile
    req = urllib.request.Request(URL_PARTIDO_2022, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        zf = zipfile.ZipFile(io.BytesIO(r.read()))
    saida: dict[str, dict] = {}
    for nome in zf.namelist():
        if not nome.lower().endswith(".csv") or "_BR" in nome.upper():
            continue
        por_agr: dict[str, dict[str, int]] = {}
        uf = None
        with zf.open(nome) as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";"):
                if r["DS_CARGO"].upper() != "DEPUTADO FEDERAL":
                    continue
                uf = r["SG_UF"].lower()
                sg = r["SG_PARTIDO"].upper().replace(" ", "")
                if sg in eleicao.LEGENDA_2026_DE_2022 and eleicao.LEGENDA_2026_DE_2022[sg] is None:
                    continue
                agr = eleicao.LEGENDA_2026_DE_2022.get(sg) or eleicao.sigla_para_legenda(sg)
                v = int(r.get("QT_VOTOS_NOMINAIS_VALIDOS") or 0) + int(r.get("QT_TOTAL_VOTOS_LEG_VALIDOS") or 0)
                cd = r["CD_MUNICIPIO"].zfill(5)
                m = por_agr.setdefault(agr, {})
                m[cd] = m.get(cd, 0) + v
        if uf:
            saida[uf] = {agr: _normalizar(m) for agr, m in por_agr.items()}
    return saida


def carregar_br() -> dict | None:
    try:
        return json.loads(DESTINO_BR.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def carregar(caminho: Path | None = None) -> dict | None:
    try:
        return json.loads((caminho or DESTINO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fatias(bases: dict, tipo: str, numero: str, agr: str | None = None) -> tuple[dict[str, float], str]:
    """A distribuição de um candidato (resolvendo o atalho do partido).

    Candidato sem entrada própria (todas as UFs fora SC) usa a do partido."""
    b = (bases.get(tipo) or {}).get(numero)
    if b is None:
        b = {"f": "partido", "a": agr} if agr and (bases.get("agr", {}).get(tipo) or {}).get(agr) else {"f": "eleitorado"}
    if b["f"] == "partido":
        return bases["agr"][tipo].get(b["a"], bases["eleitorado"]), "partido"
    if b["f"] == "eleitorado":
        return bases["eleitorado"], "eleitorado"
    return b["s"], b["f"]


def main() -> int:
    br = gerar_br()
    DESTINO_BR.write_text(json.dumps(br, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"bases por partido: {len(br)} UFs ({DESTINO_BR.stat().st_size // 1024} KB)")
    b = gerar()
    DESTINO.write_text(json.dumps(b, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for tipo in CARGOS:
        fontes: dict[str, int] = {}
        for x in b[tipo].values():
            fontes[x["f"]] = fontes.get(x["f"], 0) + 1
        print(f"{tipo}: {len(b[tipo])} candidatos · {fontes}")
    print(f"{DESTINO} ({DESTINO.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
