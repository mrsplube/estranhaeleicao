"""Gera a explicação do 2º turno de 2026 (aba nova do /apuracao).

    venv/bin/python -m tools.migracoes.2026-10-27-explicacao-2t

Roda UMA VEZ, à mão, e grava `apuracao/data/arquivo/2026-2t/explicacao.json`.
Depois disso a página pública lê só esse arquivo: nenhum pedido ao TSE, nenhuma
conta no Pi a cada visita.

De onde vêm os números, e por que desta fonte:

- **Votação por seção de 2026** (`votacao_secao_2026_BR.zip`, dados abertos do
  TSE) é a única fonte que traz os DOIS turnos — 1º e 2º — com o voto de cada
  candidato em cada seção. Passando uma vez por ela dá para montar, com o mesmo
  dado, o nacional, o estado e o município, e ainda conferir se a soma das
  seções fecha com o total que o TSE proclamou. É essa conferência que a aba
  mostra: comparecimento, válidos, brancos e nulos de cada estado somados seção
  a seção contra o arquivo oficial da UF.
- O `pres_{uf}.json` do 2º turno é o número OFICIAL de cada estado (é o arquivo
  que o app do TSE publica); ele entra como gabarito da conferência, nunca como
  fonte da conta.

Nada aqui é estimativa de intenção de voto: a "transferência" que a aba mostra é
aritmética — quantos votos apareceram entre um turno e o outro e para onde
foram. Quem votou em quem, individualmente, o voto secreto não diz.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))


ARQUIVO_1T = RAIZ / "apuracao" / "data" / "arquivo" / "2026-1t"
BRUTOS_2T = RAIZ / "apuracao" / "data" / "arquivo" / "2026-2t" / "brutos"  # 2026 já congelado
DESTINO = RAIZ / "apuracao" / "data" / "arquivo" / "2026-2t"
# Insumo descartável (o zip de 242 MB do TSE), FORA do arquivo congelado.
CACHE = RAIZ / "apuracao" / "cache"
URL_SECOES = ("https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/"
              "votacao_secao_2026_BR.zip")

UFS = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to".split()
NOMES_UF = {
    "ac": "Acre", "al": "Alagoas", "am": "Amazonas", "ap": "Amapá", "ba": "Bahia",
    "ce": "Ceará", "df": "Distrito Federal", "es": "Espírito Santo", "go": "Goiás",
    "ma": "Maranhão", "mg": "Minas Gerais", "ms": "Mato Grosso do Sul", "mt": "Mato Grosso",
    "pa": "Pará", "pb": "Paraíba", "pe": "Pernambuco", "pi": "Piauí", "pr": "Paraná",
    "rj": "Rio de Janeiro", "rn": "Rio Grande do Norte", "ro": "Rondônia", "rr": "Roraima",
    "rs": "Rio Grande do Sul", "sc": "Santa Catarina", "se": "Sergipe", "sp": "São Paulo",
    "to": "Tocantins", "zz": "Exterior",
}
BRANCO, NULO = "95", "96"
# Números que aparecem na seção mas NÃO são voto válido, mesmo não sendo 95/96.
# O 28 é o PRTB: Pablo Marçal teve o registro indeferido, o partido lançou
# Leonardo Avalanche ("LEONARDO ALVES DE ARAUJO"), ele renunciou em 01/10 e o TSE
# conta os votos dados ao 28 como NULOS (a Folha noticiou assim e o arquivo
# oficial confirma: nulos do 1º turno = 3.674.249, e a soma das seções só chega
# lá se esses 5.246 entrarem como nulo — sem isso a "terceira via" fica 5.246
# votos maior que a realidade). É a diferença que a conferência contra o TSE
# oficial pegou em 28/10/2026.
ANULADOS_DE_URNAS = {"28"}


def _i(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def linhas_secoes():
    """As linhas do CSV de votação por seção, do zip guardado em disco.

    O arquivo é de 242 MB comprimido e o TSE não gosta de ser varrido de novo por
    nada. Ele fica em `apuracao/cache/` — FORA do arquivo congelado, porque é
    insumo descartável: se sumir, este script baixa de novo. Guardá-lo dentro de
    `data/arquivo/` fazia o arquivo congelado pesar 279 MB em vez de 37 MB.
    """
    import zipfile

    local = CACHE / "votacao_secao_2026_BR.zip"
    if not local.exists():
        import httpx
        print("baixando a votação por seção de 2026 (≈240 MB, uma vez só)…", flush=True)
        local.parent.mkdir(parents=True, exist_ok=True)
        tmp = local.with_suffix(".part")
        with httpx.stream("GET", URL_SECOES, headers={"User-Agent": "Mozilla/5.0"},
                          timeout=httpx.Timeout(120.0, connect=15.0), follow_redirects=True) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                for pedaco in r.iter_bytes(1 << 20):
                    f.write(pedaco)
        os.replace(tmp, local)
        print(f"  {local.stat().st_size / 1e6:.0f} MB em {local}", flush=True)
    import csv
    import io
    with zipfile.ZipFile(local) as z:
        nome = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(nome) as bruto:
            yield from csv.DictReader(io.TextIOWrapper(bruto, encoding="latin-1"), delimiter=";")


def candidatos_1t() -> list[dict]:
    """Os 12 do 1º turno, com número, nome de urna e o voto de cada um no país."""
    d = json.loads((ARQUIVO_1T / "brutos" / "pres_br.json").read_text(encoding="utf-8"))
    out = []
    for a in d["carg"][0]["agr"]:
        for p in a["par"]:
            for c in p["cand"]:
                if c.get("dvt", "Válido") != "Válido":
                    continue
                out.append({"n": c["n"], "nm": c["nmu"], "p": p["sg"],
                            "a": a.get("com") or p["sg"], "v": _i(c.get("vap"))})
    out.sort(key=lambda c: -c["v"])
    return out


def _oficial(uf: str, turno: int) -> dict:
    """O número oficial da UF (gabarito): arquivo do TSE que a apuração já baixou."""
    caminho = BRUTOS_2T / f"pres_{uf}.json" if turno == 2 else None
    if caminho is None or not caminho.exists():
        return {}
    d = json.loads(caminho.read_text(encoding="utf-8"))
    e, v, s = d.get("e") or {}, d.get("v") or {}, d.get("s") or {}
    return {"eleitores": _i(e.get("te")), "comparecimento": _i(e.get("c")),
            "abstencao": _i(e.get("a")), "validos": _i(v.get("vv")),
            "brancos": _i(v.get("vb")), "nulos": _i(v.get("tvn")), "total": _i(v.get("tv")),
            "secoes": _i(s.get("st")), "secoes_total": _i(s.get("ts")),
            "dg": f'{d.get("dg", "")} {d.get("hg", "")}'.strip()}


def _oficial_1t_uf(uf: str) -> dict:
    """1º turno por UF: o TSE publica o mesmo formato na eleição 6257."""
    caminho = DESTINO / "oficial_1t" / f"{uf}.json"
    if not caminho.exists():
        import httpx
        url = f"https://resultados.tse.jus.br/oficial/ele2026/6257/dados/{uf}/{uf}-c0001-e006257-u.json"
        with httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = c.get(url)
        if r.status_code != 200:
            return {}
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(r.content)
    d = json.loads(caminho.read_text(encoding="utf-8"))
    e, v, s = d.get("e") or {}, d.get("v") or {}, d.get("s") or {}
    return {"eleitores": _i(e.get("te")), "comparecimento": _i(e.get("c")),
            "abstencao": _i(e.get("a")), "validos": _i(v.get("vv")),
            "brancos": _i(v.get("vb")), "nulos": _i(v.get("tvn")), "total": _i(v.get("tv")),
            "secoes": _i(s.get("st")), "secoes_total": _i(s.get("ts")),
            "dg": f'{d.get("dg", "")} {d.get("hg", "")}'.strip()}


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    cands = candidatos_1t()
    numeros = {c["n"] for c in cands}
    print(f"1º turno: {len(cands)} candidatos — {', '.join(c['nm'] + ' ' + c['n'] for c in cands)}")

    # ── uma passada pela votação por seção: os dois turnos, tudo junto ──────
    # mun[(turno, uf, cd)] = [validos, lula, flavio, brancos, nulos, comp, secoes?]
    # nome[(uf, cd)] = nome; e_uf[(turno, uf)] = [aptos, comp, validos, br, nu, votos]
    votos_mun: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    nomes: dict[tuple[str, str], str] = {}
    soma_uf: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    secoes_uf: dict[tuple[int, str], set] = defaultdict(set)
    vistos = set()
    total_linhas = 0
    votos_28 = 0
    for r in linhas_secoes():
        turno = _i(r.get("NR_TURNO"))
        uf = (r.get("SG_UF") or "").lower()
        if turno not in (1, 2) or uf not in NOMES_UF:
            continue
        total_linhas += 1
        cd = str(r.get("CD_MUNICIPIO") or "").zfill(5)
        vot = _i(r.get("QT_VOTOS"))
        num = str(r.get("NR_VOTAVEL") or "")
        if not vot:
            continue
        m = votos_mun[(turno, uf, cd)]
        m["comp"] += vot
        # 95 = branco; 96 = nulo digitado; 28 = voto em candidatura que o TSE
        # considera inapta (vira nulo no arquivo oficial).
        if num in (BRANCO, NULO) or (turno == 1 and num in ANULADOS_DE_URNAS):
            m["brancos" if num == BRANCO else "nulos"] += vot
            if turno == 1 and num in ANULADOS_DE_URNAS:
                votos_28 += vot
        else:
            m["validos"] += vot
            if num == "13":
                m["lula"] += vot
            elif num == "22":
                m["flavio"] += vot
            elif turno == 1 and num in numeros:
                m[f"c{num}"] += vot
        if num == "13" or num == "22" or num in (BRANCO, NULO) or (turno == 1 and num in numeros):
            nomes.setdefault((uf, cd), r.get("NM_MUNICIPIO") or "")
        s = soma_uf[(turno, uf)]
        s["comp"] += vot
        if num in (BRANCO, NULO) or (turno == 1 and num in ANULADOS_DE_URNAS):
            s["brancos" if num == BRANCO else "nulos"] += vot
        else:
            s["validos"] += vot
            if num == "13":
                s["lula"] += vot
            elif num == "22":
                s["flavio"] += vot
        secoes_uf[(turno, uf)].add((r.get("NR_ZONA"), r.get("NR_SECAO")))
        if total_linhas % 500_000 == 0:
            print(f"  … {total_linhas:,} linhas", flush=True)
    print(f"  lidas {total_linhas:,} linhas de seção")

    # ── nacional e estado ─────────────────────────────────────────────────
    def bloco(turno: int) -> dict:
        tot = defaultdict(int)
        for uf in NOMES_UF:
            for k, v in soma_uf[(turno, uf)].items():
                tot[k] += v
        return dict(tot)

    nac = {1: bloco(1), 2: bloco(2)}
    # Eleitorado: a soma dos aptos das UFs (o arquivo por seção traz o voto, não
    # o eleitorado apto; o oficial de cada UF traz). É o denominador da
    # abstenção — sem ele o Sankey não sabe quanto do eleitorado faltou.
    eleitores = 0
    for uf in NOMES_UF:
        o1, o2 = _oficial_1t_uf(uf), _oficial(uf, 2)
        eleitores += max(o1.get("eleitores") or 0, o2.get("eleitores") or 0)
    nac[1]["eleitores"] = eleitores
    nac[2]["eleitores"] = eleitores
    ufs_out = []
    for uf in UFS + ["zz"]:
        s1, s2 = soma_uf[(1, uf)], soma_uf[(2, uf)]
        ufs_out.append({
            "uf": uf, "nome": NOMES_UF[uf],
            "t1": dict(s1), "t2": dict(s2),
            "oficial_1t": _oficial_1t_uf(uf), "oficial_2t": _oficial(uf, 2),
            "secoes_1t": len(secoes_uf[(1, uf)]), "secoes_2t": len(secoes_uf[(2, uf)]),
        })

    # ── municípios (com o voto de cada um dos 12 do 1º turno) ─────────────
    municipios = []
    for (turno, uf, cd), m in list(votos_mun.items()):
        if turno != 1:
            continue
        t2 = votos_mun.get((2, uf, cd), {})
        d = {"uf": uf, "cd": cd, "nm": nomes.get((uf, cd), ""),
             "t1": {k: m.get(k, 0) for k in ("comp", "validos", "lula", "flavio", "brancos", "nulos")},
             "t2": {k: t2.get(k, 0) for k in ("comp", "validos", "lula", "flavio", "brancos", "nulos")}}
        d["t1"]["outros"] = [m.get(f"c{n}", 0) for n in sorted(numeros, key=int)]
        municipios.append(d)
    municipios.sort(key=lambda d: (d["uf"], d["nm"]))
    print(f"  {len(municipios):,} municípios")

    # ── conferência: a soma das seções × o arquivo oficial de cada UF ─────
    # E a conferência NACIONAL contra o arquivo do TSE, campo a campo. É esta
    # que pega erro de classificação (foi ela que achou os 5.246 votos do 28
    # sendo contados como válidos): as duas somas fecham por UF e divergiriam
    # só no total do país se a regra de "o que é voto válido" estivesse errada.
    conferencia = []
    for u in ufs_out:
        o1, o2 = u["oficial_1t"], u["oficial_2t"]
        conferencia.append({
            "uf": u["uf"], "nome": u["nome"],
            "t2": {
                "comp_soma": u["t2"].get("comp", 0), "comp_oficial": o2.get("comparecimento", 0),
                "val_soma": u["t2"].get("validos", 0), "val_oficial": o2.get("validos", 0),
                "br_soma": u["t2"].get("brancos", 0), "br_oficial": o2.get("brancos", 0),
                "nu_soma": u["t2"].get("nulos", 0), "nu_oficial": o2.get("nulos", 0),
                "eleitores": o2.get("eleitores", 0), "abstencao": o2.get("abstencao", 0),
                "secoes_soma": u["secoes_2t"], "secoes_oficial": o2.get("secoes", 0),
            },
            "t1": {
                "comp_soma": u["t1"].get("comp", 0), "comp_oficial": o1.get("comparecimento", 0),
                "val_soma": u["t1"].get("validos", 0), "val_oficial": o1.get("validos", 0),
                "br_soma": u["t1"].get("brancos", 0), "br_oficial": o1.get("brancos", 0),
                "nu_soma": u["t1"].get("nulos", 0), "nu_oficial": o1.get("nulos", 0),
                "eleitores": o1.get("eleitores", 0), "abstencao": o1.get("abstencao", 0),
            },
        })

    # Nacional: os 8 campos que o cartão mostra, nos dois turnos.
    oficial_nac = {}
    for turno, chave in ((1, "oficial_1t"), (2, "oficial_2t")):
        tot = {"comparecimento": 0, "validos": 0, "brancos": 0, "nulos": 0, "eleitores": 0}
        for u in ufs_out:
            for campo, valor in (u[chave] or {}).items():
                if campo in tot:
                    tot[campo] += valor
        oficial_nac[turno] = tot
    nacional_check = {}
    for turno, soma in ((1, nac[1]), (2, nac[2])):
        of = oficial_nac[turno]
        nacional_check[turno] = {
            "comparecimento": {"soma": soma.get("comp", 0), "oficial": of["comparecimento"]},
            "validos": {"soma": soma.get("validos", 0), "oficial": of["validos"]},
            "brancos": {"soma": soma.get("brancos", 0), "oficial": of["brancos"]},
            "nulos": {"soma": soma.get("nulos", 0), "oficial": of["nulos"]},
        }
    nacional_ok = all(v["soma"] == v["oficial"]
                      for t in nacional_check.values() for v in t.values())
    print("conferência nacional (soma das seções × TSE oficial):",
          "fecha" if nacional_ok else "DIVERGE")
    for turno, campos in nacional_check.items():
        for campo, v in campos.items():
            if v["soma"] != v["oficial"]:
                print(f"  ✗ {turno}º turno · {campo}: soma {v['soma']:,} × oficial {v['oficial']:,} "
                      f"({v['soma'] - v['oficial']:+,})")

    saida = {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fonte": {
            "secoes": URL_SECOES,
            "secoes_gerado_em": "26/10/2026",
            "oficial_2t": "resultados.tse.jus.br/oficial/ele2026/6258",
            "oficial_1t": "resultados.tse.jus.br/oficial/ele2026/6257",
        },
        "candidatos_1t": cands,
        "numeros": sorted(numeros, key=int),
        "eleitores": eleitores,
        "nacional": {"t1": nac[1], "t2": nac[2]},
        "ufs": ufs_out,
        "municipios": municipios,
        "conferencia": conferencia,
        "nacional_check": nacional_check,
        "nacional_ok": nacional_ok,
        "anulados_de_urnas": {"numeros": sorted(ANULADOS_DE_URNAS), "votos": votos_28},
        "linhas_secao": total_linhas,
    }
    tmp = DESTINO / "explicacao.json.tmp"
    tmp.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, DESTINO / "explicacao.json")

    n1, n2 = nac[1], nac[2]
    print(f"\nnacional 1º turno: válidos {n1['validos']:,} · Lula {n1['lula']:,} · "
          f"Flavio {n1['flavio']:,}")
    print(f"nacional 2º turno: válidos {n2['validos']:,} · Lula {n2['lula']:,} · "
          f"Flavio {n2['flavio']:,} · comparecimento {n2['comp']:,}")
    difs = [(c["uf"], c["t2"]["comp_soma"] - c["t2"]["comp_oficial"]) for c in conferencia]
    ruins = [d for d in difs if d[1]]
    print("conferência do 2º turno:", "todas as UFs fecham" if not ruins else ruins)
    print(f"gravado em {DESTINO / 'explicacao.json'} "
          f"({(DESTINO / 'explicacao.json').stat().st_size / 1e6:.1f} MB)")

    # Os números que a tela consome (transferência de votos, IC, conferência)
    # saem daqui já calculados: nenhuma visita ao /apuracao gasta CPU nisso.
    from apuracao import explicacao as ex
    print("calculando analise.json e municipios.json (bootstrap, ~11 s)…")
    r = ex.gerar_cache(DESTINO)
    print(f"  {r['n']:,} municípios em {r['municipios'].name}")

    # O Sankey e o limite aritmético: também calculados aqui, uma vez.
    from apuracao import cenarios
    c = cenarios.gerar(DESTINO)
    if c.get("ok"):
        lim = c["limite"]
        print(f"  cenarios.json: 3ª via deu ao Lula no mínimo {100 * lim['q_min']:.1f}% "
              f"({lim['q_min_votos']:,} votos) — limite aritmético")

    # A transição POR CANDIDATO da terceira via, com intervalo de cada um.
    from apuracao import transicao
    tr = transicao.gerar(DESTINO)
    if tr.get("ok"):
        print(f"  transicao.json: {tr['identificados']}/{tr['total']} candidatos com intervalo "
              f"estreito; troca Flavio->Lula = {tr['troca']['votos']:,} votos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
