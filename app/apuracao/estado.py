"""O estado da apuração: dos arquivos do TSE ao JSON que a página lê.

Funções puras sobre os arquivos `-u.json` do resultados.tse.jus.br (os mesmos
que o app oficial baixa). Nada aqui vai à rede — quem baixa é `coleta.py`, que
chama `montar()` quando algum arquivo mudou e grava o resultado em disco. A
rota pública só serve o que já está pronto: o Pi calcula UMA vez por mudança
no TSE, não uma vez por visitante.

O que o app oficial não mostra e esta página mostra:

- cadeiras PROJETADAS durante a apuração, pela lei inteira (arts. 106–109 com
  os pisos de 10% e 20% por candidato e a 3ª fase aberta) — `politicos.eleicao`,
  conferida contra 302 eleições de 2024;
- por onde entra cada cadeira (QP, média, 3ª fase) e quem a ocupa;
- a cláusula de barreira de 2026 para todos os partidos e federações.

Toda projeção é sobre a apuração PARCIAL: capital e interior chegam em ritmos
diferentes, então o número vem sempre acompanhado das seções já totalizadas.
"""
from __future__ import annotations

import json

from apuracao import bases as bases_mod
from apuracao import municipal as municipal_mod
from apuracao import matematica
from politicos import eleicao

UFS = ["ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms", "mt",
       "pa", "pb", "pe", "pi", "pr", "rj", "rn", "ro", "rr", "rs", "sc", "se", "sp", "to"]

NOMES_UF = {
    "ac": "Acre", "al": "Alagoas", "am": "Amazonas", "ap": "Amapá", "ba": "Bahia",
    "ce": "Ceará", "df": "Distrito Federal", "es": "Espírito Santo", "go": "Goiás",
    "ma": "Maranhão", "mg": "Minas Gerais", "ms": "Mato Grosso do Sul",
    "mt": "Mato Grosso", "pa": "Pará", "pb": "Paraíba", "pe": "Pernambuco",
    "pi": "Piauí", "pr": "Paraná", "rj": "Rio de Janeiro", "rn": "Rio Grande do Norte",
    "ro": "Rondônia", "rr": "Roraima", "rs": "Rio Grande do Sul", "sc": "Santa Catarina",
    "se": "Sergipe", "sp": "São Paulo", "to": "Tocantins",
}

# Cláusula de barreira de 2026 (EC 97/2017, art. 3º, parágrafo único, III).
BARREIRA = {"pct_nacional": 2.5, "pct_uf": 1.5, "ufs": 9, "deputados": 13}

FOCO_PADRAO = ["NOVO", "MISSÃO"]

# Identidade de cor desta página: as 8 cores da paleta validada (dataviz) presas
# a uma entidade cada — nunca ao ranking. Validadas como conjunto no modo claro;
# com 8 cores nenhuma ordem passa em TODOS os pares, então toda marca tem rótulo
# direto, vão de 2 px entre blocos e a tabela ao lado. Quem não está aqui fica
# num de dois cinzas, escolhido pelo nome (fixo por entidade, não por posição).
CORES = {
    "PL": "#2a78d6",
    "NOVO": "#eb6834",
    "Federação Brasil da Esperança - FE BRASIL": "#e3364a",
    "PT": "#e3364a",
    "PSD": "#eda100",
    "MISSÃO": "#e87ba4",
    "Federação União Progressista": "#008300",
    "Federação PSDB Cidadania": "#4a3aa7",
    "MDB": "#1baf7a",
}
CINZAS = ("#9ca3af", "#6b7280")


def cor(entidade: str) -> str:
    if entidade in CORES:
        return CORES[entidade]
    return CINZAS[sum(map(ord, entidade)) % 2]


def _f(txt) -> float:
    """'12,34' → 12.34 (o TSE manda número com vírgula, como texto)."""
    try:
        return float(str(txt or "0").replace(",", "."))
    except ValueError:
        return 0.0


def _i(txt) -> int:
    try:
        return int(txt or 0)
    except (TypeError, ValueError):
        return 0


def _apuracao(d: dict) -> dict:
    """Seções totalizadas, eleitorado e o quadro dos votos."""
    s, v, e = d.get("s") or {}, d.get("v") or {}, d.get("e") or {}
    return {
        "pst": _f(s.get("pst")), "st": _i(s.get("st")), "ts": _i(s.get("ts")),
        "eleitores": _i(e.get("te")), "comparecimento": _i(e.get("c")),
        "abstencao": _i(e.get("a")),
        "validos": _i(v.get("vv")), "nominais": _i(v.get("vnom")),
        "legenda": _i(v.get("vl")), "brancos": _i(v.get("vb")),
        "nulos": _i(v.get("tvn")), "anulados_subjudice": _i(v.get("vansj")),
        "dg": f'{d.get("dg", "")} {d.get("hg", "")}'.strip(),
        "totalizado": d.get("tf") == "s",
    }


def _ordem_lista(c: dict) -> tuple:
    """Mais votado primeiro; no empate, o mais idoso (art. 110 do Código Eleitoral)."""
    dt = c.get("dt") or "01/01/2100"
    try:
        dia, mes, ano = dt.split("/")
        nasc = (int(ano), int(mes), int(dia))
    except ValueError:
        nasc = (2100, 1, 1)
    return (-_i(c.get("vap")), nasc)


def acompanhamento(ab: dict | None) -> dict[str, dict]:
    """{código: {pst, frac, te}} do arquivo `-ab.json` (município ou UF).

    `frac` é a fração dos ELEITORES já totalizados (est ÷ te), que pesa melhor
    que a fração de seções: seção de capital é maior que seção do interior.
    """
    saida = {}
    for a in (ab or {}).get("abr", []):
        e, s = a.get("e") or {}, a.get("s") or {}
        te = _i(e.get("te"))
        saida[str(a.get("cdabr", "")).lower()] = {
            "pst": _f(s.get("pst")), "te": te,
            "frac": round(_i(e.get("est")) / te, 4) if te else 0.0}
    return saida


def _base_apurada(fatias: dict[str, float], frac: dict[str, dict]) -> tuple[float | None, list]:
    """Quanto da base já foi apurado (0–1) e os 3 municípios que mais pesam."""
    tot = sum(fatias.values())
    if not tot or not frac:
        return None, []
    ba = sum(f * (frac.get(cd) or {}).get("frac", 0.0) for cd, f in fatias.items()) / tot
    top = sorted(fatias.items(), key=lambda kv: -kv[1])[:3]
    return round(ba, 4), [[cd, round(100 * f / tot, 1), round(100 * (frac.get(cd) or {}).get("frac", 0.0), 1)]
                          for cd, f in top]


# Abaixo disto a fração apurada da base é pequena demais para dividir por ela
# sem o número explodir (1 voto ÷ 0,1% = 1.000). É piso, não modelo.
BASE_MINIMA = 0.02


def _confianca(ba: float | None) -> str | None:
    if ba is None:
        return None
    return "alta" if ba >= 0.5 else "média" if ba >= 0.2 else "baixa"


# Cidade com menos que isto apurado ainda não diz nada confiável sobre o
# candidato ali: entra pela base de 2022, não pela divisão do voto real.
FRAC_MIN = 0.10


def _projetar_municipios(votos: dict[str, int], fatias: dict[str, float],
                         mun: dict[str, dict]) -> tuple[float, float]:
    """(voto esperado no fim, parte dele que vem de voto REAL já contado).

    Cidade com ao menos FRAC_MIN apurado: votos ali ÷ fração apurada ali.
    Cidade abaixo disso: a fatia da base nela × o ritmo que o candidato faz
    nas cidades já contadas (voto projetado ÷ fatia da base que elas somam) —
    nunca menos que o voto que ele já tem ali.
    """
    tot = sum(fatias.values()) or 1.0
    proj = s_cont = 0.0
    for cd, m in mun.items():
        if m.get("frac", 0) >= FRAC_MIN:
            proj += votos.get(cd, 0) / m["frac"]
            s_cont += fatias.get(cd, 0.0) / tot
    ritmo = proj / max(s_cont, 0.05)
    resto = 0.0
    for cd, m in mun.items():
        if m.get("frac", 0) < FRAC_MIN:
            resto += max(votos.get(cd, 0), fatias.get(cd, 0.0) / tot * ritmo)
    return proj + resto, proj


def _esperado_pela_base(agrs: list[dict], cands: list[dict], vagas: int,
                        mun_votos: dict | None = None, fatias_de: dict | None = None,
                        fatias_agr: dict | None = None) -> dict | None:
    """O resultado ESPERADO se o voto que falta vier no padrão da base de cada um.

    Cada candidato vale `votos ÷ fração da base apurada` (com piso), a legenda
    de cada agremiação idem com a base do partido, e a lei inteira roda sobre
    isso. Muda o quadro quando um candidato tem a base num lugar que ainda não
    contou (o de Joinville às 18h, com Joinville em 0%). É chute declarado: a
    base é a de 2022, e a confiança acompanha quanto dela já foi apurado.
    """
    votos_esp: dict[str, float] = {}
    listas: dict[str, list[tuple[float, str]]] = {}
    fino = bool(mun_votos) and fatias_de is not None
    if fino:
        # Voto de cada candidato por município (job apuracao.municipal).
        por_cand: dict[str, dict[str, int]] = {}
        por_leg: dict[str, dict[str, int]] = {}
        for cd, m in mun_votos.items():
            for n, v in m.get("c", {}).items():
                por_cand.setdefault(n, {})[cd] = v
            for agr, v in m.get("l", {}).items():
                por_leg.setdefault(agr, {})[cd] = v
    for c in cands:
        if c.get("dvt") not in ("", "Válido"):
            continue
        if fino:
            pe, obs = _projetar_municipios(por_cand.get(c["n"], {}), fatias_de.get(c["n"], {}), mun_votos)
            pe = max(pe, float(c["v"]))
            c["pc"] = "alta" if obs >= 0.75 * pe else "média" if obs >= 0.45 * pe else "baixa"
        else:
            ba = c.get("ba")
            pe = c["v"] / max(ba, BASE_MINIMA) if ba is not None else float(c["v"])
            c["pc"] = _confianca(ba)
        c["pe"] = round(pe)
        listas.setdefault(c["a"], []).append((pe, c["n"]))
        votos_esp[c["a"]] = votos_esp.get(c["a"], 0.0) + pe
    for a in agrs:
        if fino:
            legenda, _ = _projetar_municipios(por_leg.get(a["id"], {}), (fatias_agr or {}).get(a["id"], {}), mun_votos)
            legenda = max(legenda, float(a["legenda"]))
        else:
            ba = a.get("ba")
            legenda = a["legenda"] / max(ba, BASE_MINIMA) if ba is not None else a["legenda"]
        votos_esp[a["id"]] = votos_esp.get(a["id"], 0.0) + legenda
    if not sum(votos_esp.values()):
        return None
    r = eleicao.distribuir({l: round(v) for l, v in votos_esp.items()}, vagas,
                           candidatos={l: [round(v) for v, _ in x] for l, x in listas.items()})
    fase_de: dict[str, str] = {}
    for l, fases in r["fases"].items():
        ordem = sorted(listas.get(l, []), reverse=True)
        for (_, n), f in zip(ordem, fases):
            fase_de[n] = f
    for c in cands:
        if "pe" in c:
            c["pef"] = fase_de.get(c["n"])
    tot_esp = sum(votos_esp.values()) or 1
    for a in agrs:
        a["cad_esp"] = r["cadeiras"].get(a["id"], 0)
        a["pe"] = round(votos_esp.get(a["id"], 0))
        a["pct_esp"] = round(100 * a["pe"] / tot_esp, 2)
        a["qp_esp"] = round(a["pe"] / r["qe"], 3) if r["qe"] else 0.0
        fases = r["fases"].get(a["id"], [])
        a["fases_esp"] = {f: fases.count(f) for f in ("QP", "média", "3ª fase")}
    return {"qe": r["qe"], "validos": round(sum(votos_esp.values())),
            "metodo": "municipio" if fino else "base"}


def proporcional(d: dict, com_candidatos: bool = True, tipo_base: str | None = None,
                 mun: dict[str, dict] | None = None, bases: dict | None = None,
                 mun_votos: dict | None = None) -> dict:
    """Um cargo proporcional numa UF: agremiações, projeção e candidatos.

    Com `tipo_base` ("est"/"fed"), `mun` (acompanhamento por município) e
    `bases`, cada candidato e agremiação de SC ganham `ba` (quanto da base já
    foi apurado), `pf` (o voto final se o resto vier no mesmo ritmo) e `bm`
    (os 3 municípios que mais pesam na base, com o % apurado de cada um).
    """
    carg = d["carg"][0]
    nv = _i(carg.get("nv"))
    ap = _apuracao(d)
    votos, cands, vv = eleicao.agremiacoes_do_tse(d)
    proj = (eleicao.distribuir(votos, nv, candidatos=cands, validos=vv)
            if vv > 0 and nv > 0 else None)
    qe = proj["qe"] if proj else 0

    # Situação matemática: o que já não muda com o voto que falta.
    listas, eleitos_agora = {}, set()
    for a in carg["agr"]:
        pars = [p for p in a["par"] if p.get("dvt", "") != "Anulado"]
        ordem = sorted((c for p in pars for c in p["cand"]
                        if c.get("dvt", "Válido") == "Válido"), key=_ordem_lista)
        listas[a["nm"]] = [(_i(c.get("vap")), c["sqcand"]) for c in ordem]
        n_cad = len(proj["fases"].get(a["nm"], [])) if proj else 0
        eleitos_agora.update(c["sqcand"] for c in ordem[:n_cad])
    restante = matematica.restante_de(d)
    mat = (matematica.situacoes(votos, listas, nv, vv, restante, eleitos_agora)
           if proj else {})

    agrs, lista_cand = [], []
    fatias_de: dict[str, dict] = {}
    fatias_agr: dict[str, dict] = {}
    for a in carg["agr"]:
        siglas = [p["sg"].upper() for p in a["par"]]
        canon = eleicao.agremiacao_do_tse(a["nm"], siglas)
        pars = [p for p in a["par"] if p.get("dvt", "") != "Anulado"]
        nominais = sum(_i(p.get("tvtn")) for p in pars)
        legenda = sum(_i(p.get("tvtl")) for p in pars)
        total = votos.get(a["nm"], 0)
        fases = (proj["fases"].get(a["nm"], []) if proj else [])
        elegiveis = sorted((c for p in pars for c in p["cand"]
                            if c.get("dvt", "Válido") == "Válido"), key=_ordem_lista)
        fase_de = {c["sqcand"]: f for c, f in zip(elegiveis, fases)}
        contagem = {"QP": 0, "média": 0, "3ª fase": 0}
        for f in fases:
            contagem[f] = contagem.get(f, 0) + 1
        extra_agr = {}
        if tipo_base and bases and mun:
            fat = bases["agr"][tipo_base].get(canon) or bases["eleitorado"]
            fatias_agr[canon] = fat
            ba, bm = _base_apurada(fat, mun)
            extra_agr = {"ba": ba, "bm": bm,
                         "pf": round(total / ba) if ba and ba >= 0.1 and total else None}
        agrs.append({
            **extra_agr,
            "id": canon,
            "sigla": eleicao.SIGLA_CURTA.get(canon, canon),
            "nome": a["nm"].title(),
            "federacao": a.get("tp") == "f",
            "partidos": [{"sg": p["sg"], "votos": _i(p.get("tvtn")) + _i(p.get("tvtl")),
                          "legenda": _i(p.get("tvtl")),
                          "anulado": p.get("dvt", "") == "Anulado"} for p in a["par"]],
            "cor": cor(canon),
            "votos": total, "nominais": nominais, "legenda": legenda,
            "pct": round(100 * total / vv, 2) if vv else 0.0,
            "qp": round(total / qe, 3) if qe else 0.0,
            "cadeiras": len(fases), "fases": contagem,
            "cadeiras_tse": _i(a.get("vag")),
            "candidatos": sum(len(p["cand"]) for p in a["par"]),
        })
        if com_candidatos:
            for p in a["par"]:
                for c in p["cand"]:
                    extra = {}
                    if tipo_base and bases and mun:
                        fat, fonte = bases_mod.fatias(bases, tipo_base, c["n"], canon)
                        fatias_de[c["n"]] = fat
                        ba, bm = _base_apurada(fat, mun)
                        v = _i(c.get("vap"))
                        extra = {"ba": ba, "bm": bm, "bf": fonte,
                                 "e22": bool(((bases.get(tipo_base) or {}).get(c["n"]) or {}).get("e22")),
                                 "pf": round(v / ba) if ba and ba >= 0.1 and v else None}
                    lista_cand.append({
                        **extra,
                        "n": c["n"], "nm": c["nmu"], "p": p["sg"], "a": canon,
                        "v": _i(c.get("vap")), "pct": _f(c.get("pvap")),
                        "proj": fase_de.get(c["sqcand"]),
                        "mat": mat.get(c["sqcand"]),
                        "e": c.get("e") == "s", "st": c.get("st") or "",
                        "dvt": c.get("dvt") or "",
                    })
    esperado = (_esperado_pela_base(agrs, lista_cand, nv, mun_votos, fatias_de, fatias_agr)
                if (tipo_base and bases and mun and proj) else None)
    mandato = None
    if esperado and bases and (bases.get("mandato") or {}).get(tipo_base):
        por_n = {c["n"]: c for c in lista_cand}
        saem, voltam = [], 0
        for x in bases["mandato"][tipo_base]:
            c = por_n.get(x.get("n26") or "")
            if c and c.get("pef"):
                voltam += 1
                continue
            motivo = (f"concorre e fica fora no esperado (≈ {c['pe']:,} votos)".replace(",", ".") if c
                      else f"concorre a {x['outro']}" if x.get("outro") else "não concorre")
            saem.append({"nm": x["nm"], "p": x["p"], "motivo": motivo, "n": c["n"] if c else None})
        novos = [c["n"] for c in lista_cand if c.get("pef") and not c.get("e22")]
        comp22: dict[str, int] = {}
        for x in bases["mandato"][tipo_base]:
            comp22[x["a"]] = comp22.get(x["a"], 0) + 1
        # `lista22`: a legislatura inteira, para a tela refazer a conta no modo
        # "ao vivo" (quem volta/sai se a apuração parasse agora).
        mandato = {"eleitos_2022": len(bases["mandato"][tipo_base]), "voltam": voltam,
                   "novos": novos, "saem": saem, "composicao_2022": comp22,
                   "lista22": [{k: x.get(k) for k in ("nm", "p", "a", "n26", "outro")}
                               for x in bases["mandato"][tipo_base]]}
    agrs.sort(key=lambda x: (-x["cadeiras"], -x["votos"], x["sigla"]))
    lista_cand.sort(key=lambda c: -c["v"])
    saida = {
        "esperado": esperado,
        "mandato": mandato,
        "cargo": carg.get("nmn"), "vagas": nv, "qe": qe, "qe_tse": _i(carg.get("qe")),
        "piso_qp": round(qe * 0.10), "piso_media": round(qe * 0.20),
        "piso_legenda_media": round(qe * 0.80),
        "apuracao": ap, "agremiacoes": agrs, "restante": restante,
        "garantidos": sum(1 for x in mat.values() if x != matematica.FORA),
        "fase_seat": [s["fase"] for s in (proj["sobras"] if proj else [])],
    }
    # A margem precisa da lista de candidatos (piso de 20% do quociente) mesmo quando
    # a saída não a leva: sem ela, `margem_da_vaga` caía no caminho da série antiga
    # (só legenda ≥ 80%) e podia apontar como "1º de fora" uma lista sem candidato apto.
    com_lista = {**saida, "candidatos": lista_cand}
    saida["vaga"] = margem_da_vaga(com_lista)
    saida["vaga_esp"] = margem_da_vaga(com_lista, previsto=True)
    if com_candidatos:
        saida["candidatos"] = lista_cand
    return saida


def majoritario(d: dict) -> dict:
    """Presidente, governador, senador: candidato, partido, votos e %."""
    carg = d["carg"][0]
    cands = []
    for a in carg["agr"]:
        for p in a["par"]:
            for c in p["cand"]:
                cands.append({"n": c["n"], "nm": c["nmu"], "p": p["sg"],
                              "col": (a.get("com") or p["sg"]).replace(" / ", "/"),
                              "v": _i(c.get("vap")), "pct": _f(c.get("pvap")),
                              "e": c.get("e") == "s", "st": c.get("st") or "",
                              "cor": cor(p["sg"].upper())})
    cands.sort(key=lambda c: (-c["v"], c["nm"]))
    return {"cargo": carg.get("nmn"), "vagas": _i(carg.get("nv")) or 1, "turno": str(d.get("t") or "1"),
            "apuracao": _apuracao(d), "candidatos": cands}


def camara(federais: dict[str, dict]) -> dict:
    """A Câmara inteira: soma das 27 projeções e a cláusula de barreira.

    Federação conta como UMA agremiação também na barreira (Lei 14.208/2021):
    é o desempenho da federação que vale para todos os partidos dela.
    """
    total_validos = sum(f["apuracao"]["validos"] for f in federais.values())
    st = sum(f["apuracao"]["st"] for f in federais.values())
    ts = sum(f["apuracao"]["ts"] for f in federais.values())
    por: dict[str, dict] = {}
    for uf, f in federais.items():
        vv_uf = f["apuracao"]["validos"]
        for a in f["agremiacoes"]:
            d = por.setdefault(a["id"], {"id": a["id"], "sigla": a["sigla"], "cor": a["cor"],
                                         "federacao": a["federacao"], "votos": 0,
                                         "cadeiras": 0, "cad_esp": 0, "pe": 0, "por_uf": {}, "partidos": {}})
            d["votos"] += a["votos"]
            d["cadeiras"] += a["cadeiras"]
            d["cad_esp"] += a.get("cad_esp", a["cadeiras"]) or 0
            d["pe"] += a.get("pe", a["votos"]) or 0
            pe_uf = (f.get("esperado") or {}).get("validos") or vv_uf
            d["por_uf"][uf] = {"votos": a["votos"], "cadeiras": a["cadeiras"],
                               "cad_esp": a.get("cad_esp", a["cadeiras"]),
                               "pct": round(100 * a["votos"] / vv_uf, 2) if vv_uf else 0.0,
                               "pct_esp": round(100 * (a.get("pe") or a["votos"]) / pe_uf, 2) if pe_uf else 0.0}
            for p in a["partidos"]:
                d["partidos"][p["sg"]] = d["partidos"].get(p["sg"], 0) + p["votos"]
    linhas = []
    for d in por.values():
        pct = round(100 * d["votos"] / total_validos, 3) if total_validos else 0.0
        ufs_pct = sorted(uf for uf, x in d["por_uf"].items() if x["pct"] >= BARREIRA["pct_uf"])
        ufs_cad = sorted(uf for uf, x in d["por_uf"].items() if x["cadeiras"] >= 1)
        crit_a = pct >= BARREIRA["pct_nacional"] and len(ufs_pct) >= BARREIRA["ufs"]
        crit_b = d["cadeiras"] >= BARREIRA["deputados"] and len(ufs_cad) >= BARREIRA["ufs"]
        # A mesma barreira sobre o ESPERADO no fim (votos e cadeiras pela base).
        tot_esp = sum(sum(a.get("pe", a["votos"]) or 0 for a in f["agremiacoes"]) for f in federais.values())
        pct_e = round(100 * d["pe"] / tot_esp, 3) if tot_esp else 0.0
        ufs_pct_e = [uf for uf, x in d["por_uf"].items() if x["pct_esp"] >= BARREIRA["pct_uf"]]
        ufs_cad_e = [uf for uf, x in d["por_uf"].items() if (x["cad_esp"] or 0) >= 1]
        ea = pct_e >= BARREIRA["pct_nacional"] and len(ufs_pct_e) >= BARREIRA["ufs"]
        eb = d["cad_esp"] >= BARREIRA["deputados"] and len(ufs_cad_e) >= BARREIRA["ufs"]
        d.update({"pct": pct, "ufs_pct": ufs_pct, "ufs_cadeira": ufs_cad,
                  "barreira": {"a": crit_a, "b": crit_b, "passa": crit_a or crit_b},
                  "pct_esp": pct_e, "ufs_pct_esp": len(ufs_pct_e), "ufs_cadeira_esp": len(ufs_cad_e),
                  "barreira_esp": {"a": ea, "b": eb, "passa": ea or eb},
                  "partidos": dict(sorted(d["partidos"].items(), key=lambda kv: -kv[1]))})
        linhas.append(d)
    linhas.sort(key=lambda x: (-x["cad_esp"], -x["cadeiras"], -x["votos"]))
    return {"vagas": sum(f["vagas"] for f in federais.values()),
            "validos": total_validos,
            "pst": round(100 * st / ts, 2) if ts else 0.0,
            "barreira_regra": BARREIRA, "agremiacoes": linhas,
            "ufs": {uf: {"nome": NOMES_UF[uf], "vagas": f["vagas"], "qe": f["qe"],
                         "pst": f["apuracao"]["pst"], "validos": f["apuracao"]["validos"],
                         "cadeiras": {a["id"]: a["cadeiras"] for a in f["agremiacoes"]
                                      if a["cadeiras"]},
                         "cad_esp": {a["id"]: a.get("cad_esp") for a in f["agremiacoes"]
                                     if a.get("cad_esp")}}
                    for uf, f in sorted(federais.items())}}


def montar(brutos: dict[str, dict]) -> tuple[dict, dict[str, dict]]:
    """Estado principal + um arquivo por UF (a lista federal inteira da UF).

    `brutos` é {chave: json do TSE}, com as chaves de `coleta.FONTES`.
    """
    mun = acompanhamento(brutos.get("ab_sc"))
    bases = bases_mod.carregar()
    bases_br = bases_mod.carregar_br() or {}
    federais_det = {}
    for uf in UFS:
        if f"fed_{uf}" not in brutos:
            continue
        if uf == "sc":
            federais_det[uf] = proporcional(brutos[f"fed_{uf}"], tipo_base="fed", mun=mun, bases=bases,
                                            mun_votos=municipal_mod.carregar("fed"))
            continue
        mun_uf = acompanhamento(brutos.get(f"ab_{uf}"))
        if bases_br.get(uf) and mun_uf:
            # Fora de SC: base por PARTIDO (2022); o eleitorado vem do próprio -ab.json.
            te = {cd: m["te"] for cd, m in mun_uf.items() if cd.isdigit()}
            tot = sum(te.values()) or 1
            base_uf = {"fed": {}, "agr": {"fed": bases_br[uf]},
                       "eleitorado": {cd: v / tot for cd, v in te.items()}}
            federais_det[uf] = proporcional(brutos[f"fed_{uf}"], tipo_base="fed", mun=mun_uf, bases=base_uf)
        else:
            federais_det[uf] = proporcional(brutos[f"fed_{uf}"])
    federais = {uf: {k: v for k, v in f.items() if k != "candidatos"}
                for uf, f in federais_det.items()}
    estado = {
        "versao": 1,
        "foco_padrao": FOCO_PADRAO,
        "sc": {
            "estadual": (proporcional(brutos["est_sc"], tipo_base="est", mun=mun, bases=bases,
                                      mun_votos=municipal_mod.carregar("est"))
                         if "est_sc" in brutos else None),
            "federal": federais_det.get("sc"),
            "governador": majoritario(brutos["gov_sc"]) if "gov_sc" in brutos else None,
            "senador": majoritario(brutos["sen_sc"]) if "sen_sc" in brutos else None,
        },
        "presidente": majoritario(brutos["pres_br"]) if "pres_br" in brutos else None,
        "camara": camara(federais) if federais else None,
        "nomes_uf": NOMES_UF,
        # Mapa: {código TSE: [% de seções, % de eleitores já totalizados, eleitores]}.
        # (o arquivo traz também a linha da UF inteira, "sc" — só código numérico é município)
        "municipios_sc": {cd: [m["pst"], round(100 * m["frac"], 1), m["te"]] for cd, m in mun.items() if cd.isdigit()},
        "ufs_br": {uf: [m["pst"], round(100 * m["frac"], 1)]
                   for uf, m in acompanhamento(brutos.get("ab_br")).items()},
    }
    return estado, federais_det


def extras(brutos: dict[str, dict], federais_det: dict[str, dict]) -> dict:
    """O que só duas abas usam, em arquivos à parte (não engordam o estado.json).

    - `majoritarias`: governador e Senado das 27 UFs;
    - `eleitos`: quem cada agremiação elege AGORA para a Câmara, UF por UF —
      é o que responde "quais são os deputados federais do NOVO".
    """
    maj = {"governador": {}, "senador": {}}
    for uf in UFS:
        for cargo, pref in (("governador", "gov"), ("senador", "sen")):
            d = brutos.get(f"{pref}_{uf}")
            if d:
                maj[cargo][uf] = majoritario(d)
    eleitos: dict[str, list] = {}
    for uf, f in federais_det.items():
        sigla_de = {a["id"]: a["sigla"] for a in f["agremiacoes"]}
        for c in f.get("candidatos", []):
            if c.get("proj") or c.get("e") or c.get("pef"):
                eleitos.setdefault(c["a"], []).append({
                    "uf": uf, "n": c["n"], "nm": c["nm"], "p": c["p"], "sigla": sigla_de.get(c["a"], c["a"]),
                    "v": c["v"], "pct": c["pct"], "proj": c.get("proj"), "mat": c.get("mat"), "e": c.get("e"),
                    "pe": c.get("pe"), "pef": c.get("pef")})
    for lista in eleitos.values():
        lista.sort(key=lambda x: (x["uf"], -(x.get("pe") or x["v"])))
    # Senado: das 81 cadeiras, 54 estão em disputa (2 por UF). Quem fica com
    # elas se a ordem de agora se mantiver (ou o que o TSE já proclamou).
    senado: dict[str, dict] = {}
    governos: dict[str, int] = {}
    for uf, d in maj["senador"].items():
        eleitos_uf = [c for c in d["candidatos"] if c["e"]] or d["candidatos"][:2]
        for c in eleitos_uf[:2]:
            x = senado.setdefault(c["p"], {"sigla": c["p"], "cor": c["cor"], "n": 0, "nomes": []})
            x["n"] += 1
            x["nomes"].append(f'{c["nm"]} ({uf.upper()})')
    for uf, d in maj["governador"].items():
        if d["candidatos"]:
            governos[d["candidatos"][0]["p"]] = governos.get(d["candidatos"][0]["p"], 0) + 1
    maj["senado_disputa"] = sorted(senado.values(), key=lambda x: -x["n"])
    maj["governos_lideranca"] = dict(sorted(governos.items(), key=lambda kv: -kv[1]))
    return {"majoritarias": maj, "eleitos": eleitos}


def margem_da_vaga(cargo: dict | None, previsto: bool = False) -> dict | None:
    """Quem segura a última cadeira das sobras, e por quantos votos.

    A folga é o voto que o primeiro de fora (apto: legenda com 80% do quociente
    e próximo candidato com 20%) precisa para a média dele alcançar a de quem
    tem a vaga. O divisor é o da cadeira que ele disputaria. Sem candidato na
    lista, o piso de 20% não se aplica — é o caso da série antiga, que só
    guardou o voto da legenda.
    """
    if not cargo:
        return None
    qe = (cargo.get("esperado") or {}).get("qe") if previsto else cargo.get("qe")
    if not qe:
        return None
    listas: dict[str, list[int]] = {}
    for c in cargo.get("candidatos") or []:
        if c.get("dvt") not in ("", "Válido", None):
            continue
        voto = c.get("pe") if previsto and c.get("pe") is not None else c.get("v")
        if voto is None:
            continue
        listas.setdefault(c["a"], []).append(int(voto))
    for lista in listas.values():
        lista.sort(reverse=True)
    ganhas, fila = [], []
    for a in cargo.get("agremiacoes") or []:
        votos = (a.get("pe") if previsto else a.get("votos")) or 0
        if votos <= 0:
            continue
        fases = (a.get("fases_esp") if previsto else a.get("fases")) or {}
        qp = fases.get("QP") or 0
        sobras = (fases.get("média") or 0) + (fases.get("3ª fase") or 0)
        for i in range(1, sobras + 1):
            ganhas.append({"dono": a["id"], "cadeira": qp + i, "media": votos / (qp + i)})
        lista = listas.get(a["id"])
        if lista is None:
            # Série antiga: só o voto da legenda, sem a lista de candidatos.
            apto = votos >= 0.8 * qe
        else:
            prox_voto = lista[qp + sobras] if qp + sobras < len(lista) else 0
            apto = votos >= 0.8 * qe and prox_voto >= 0.2 * qe
        fila.append({"fora": a["id"], "cadeira": qp + sobras + 1,
                     "media": votos / (qp + sobras + 1), "apto": apto})
    if not ganhas:
        return None
    ultima = min(ganhas, key=lambda g: g["media"])
    aptos = [f for f in fila if f["apto"]]
    if not aptos:
        return {"dono": ultima["dono"], "cadeira": ultima["cadeira"],
                "fora": None, "cadeira_fora": None, "folga": None}
    primeiro = max(aptos, key=lambda f: f["media"])
    folga = int((ultima["media"] - primeiro["media"]) * primeiro["cadeira"] + 0.5)
    return {"dono": ultima["dono"], "cadeira": ultima["cadeira"],
            "fora": primeiro["fora"], "cadeira_fora": primeiro["cadeira"],
            "folga": max(folga, 0)}


def completar_vaga_na_serie(caminho) -> int:
    """Preenche `vaga` nos pontos antigos, que só têm o voto da legenda.

    A previsão (`vaga_esp`) não entra: a série não guardava o voto esperado.
    """
    from pathlib import Path
    caminho = Path(caminho)
    saida, n = [], 0
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        o = json.loads(linha)
        if "vaga" not in o and o.get("votos_estadual") and (o.get("pst") or {}).get("estadual"):
            o["vaga"] = margem_da_vaga(_cargo_da_serie(o["votos_estadual"]))
            n += 1
        saida.append(json.dumps(o, ensure_ascii=False, separators=(",", ":")))
    caminho.write_text("\n".join(saida) + "\n", encoding="utf-8")
    return n


def _cargo_da_serie(votos: dict) -> dict:
    """Um cargo só com legendas, para recomputar a folga de um ponto antigo."""
    r = eleicao.distribuir({k: int(v) for k, v in votos.items() if v})
    agrs = []
    for leg, fases in r["fases"].items():
        contagem = {"QP": 0, "média": 0, "3ª fase": 0}
        for f in fases:
            contagem[f] = contagem.get(f, 0) + 1
        agrs.append({"id": leg, "votos": int(votos[leg]), "fases": contagem})
    return {"qe": r["qe"], "agremiacoes": agrs}


def ponto_da_serie(estado: dict) -> dict:
    """O que a linha do tempo da noite guarda a cada mudança no TSE."""
    def cad(c):
        return {a["id"]: a["cadeiras"] for a in c["agremiacoes"]} if c else {}

    def vot(c):
        return {a["id"]: a["votos"] for a in c["agremiacoes"]} if c else {}

    est, fed, cam = estado["sc"]["estadual"], estado["sc"]["federal"], estado["camara"]
    return {
        "pst": {"estadual": est["apuracao"]["pst"] if est else 0,
                "federal": fed["apuracao"]["pst"] if fed else 0,
                "camara": cam["pst"] if cam else 0},
        "estadual": cad(est), "federal": cad(fed), "camara": cad(cam),
        "estadual_esp": {a["id"]: a.get("cad_esp", 0) for a in est["agremiacoes"]} if est else {},
        "federal_esp": {a["id"]: a.get("cad_esp", 0) for a in fed["agremiacoes"]} if fed else {},
        "camara_esp": {a["id"]: a.get("cad_esp", 0) for a in cam["agremiacoes"]} if cam else {},
        "votos_estadual": vot(est), "votos_federal": vot(fed),
        "vaga": margem_da_vaga(est) if est else None,
        "vaga_esp": margem_da_vaga(est, previsto=True) if est else None,
    }


def municipal(d: dict) -> dict:
    """Um cargo num município: só votos (cadeira não se decide por município).

    Agremiações com voto e fatia, e TODOS os candidatos de forma compacta — é
    o que deixa a página mostrar os seus ★ e o seu foco naquela cidade.
    """
    carg = d["carg"][0]
    ap = _apuracao(d)
    vv = ap["validos"]
    agrs, cands = [], []
    for a in carg["agr"]:
        siglas = [p["sg"].upper() for p in a["par"]]
        canon = eleicao.agremiacao_do_tse(a["nm"], siglas)
        pars = [p for p in a["par"] if p.get("dvt", "") != "Anulado"]
        total = sum(_i(p.get("tvtn")) + _i(p.get("tvtl")) for p in pars)
        agrs.append({"id": canon, "sigla": eleicao.SIGLA_CURTA.get(canon, canon), "cor": cor(canon),
                     "partidos": [p["sg"] for p in a["par"]], "votos": total,
                     "pct": round(100 * total / vv, 2) if vv else 0.0})
        for p in pars:
            for c in p["cand"]:
                cands.append({"n": c["n"], "nm": c["nmu"], "p": p["sg"], "a": canon,
                              "v": _i(c.get("vap")), "pct": _f(c.get("pvap"))})
    agrs.sort(key=lambda x: -x["votos"])
    cands.sort(key=lambda c: -c["v"])
    return {"cargo": carg.get("nmn"), "apuracao": ap, "agremiacoes": agrs, "candidatos": cands}
