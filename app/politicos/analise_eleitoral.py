"""Leitura do resultado: o raio-x de um candidato, de um município e de um partido.

Tudo sai de `politicos/data/eleicoes.db` (ver `microdados.py`) e é calculado
na hora — o dado é estático depois da totalização, então cada cálculo pesado
fica em memória por (ano, cargo) e não se refaz.

O que cada número quer dizer, para não virar opinião:

- **Força na cidade** é o voto do candidato ÷ votos válidos da cidade para o
  cargo. É o que o mapa pinta: mostra onde ele é FORTE, não onde tem mais voto
  (Joinville sempre tem mais voto).
- **Peso da cidade** é o voto do candidato ali ÷ o total dele. É o que diz de
  onde vem o mandato.
- **Sobreposição** entre dois candidatos é Σ min(pᵢ, qᵢ) sobre as cidades, com
  p e q os pesos de cada um: 70% quer dizer que 70% do voto de cada um vem das
  mesmas cidades, na mesma proporção. É o concorrente direto por eleitor.
- **Votos que faltaram** é a MESMA conta de cadeiras que reproduziu o TSE
  (`eleicao.distribuir`), refeita com votos a mais até a cadeira mudar de
  dono. Não é estimativa: com aqueles votos, a lei dava a vaga.
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache

from politicos import eleicao, microdados

PROPORCIONAIS = (6, 7)
VAGAS = {7: 40, 6: 16}


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{microdados.BANCO}?mode=ro", uri=True, timeout=10, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


_con: sqlite3.Connection | None = None


def _c() -> sqlite3.Connection:
    global _con
    if _con is None:
        _con = conectar()
    return _con


def disponivel() -> bool:
    return microdados.BANCO.exists()


def limpar_cache() -> None:
    global _con
    for f in (_base, _municipios, _secoes_disponiveis, _margens, _anteriores_cache, _composicao_geral):
        f.cache_clear()
    _con = None


# ── base em memória, por (ano, cargo) ───────────────────────────────────────
@lru_cache(maxsize=1)
def _municipios() -> dict[int, dict]:
    return {r["cd"]: {"cd": r["cd"], "nome": r["nome"], "ibge": r["ibge"]}
            for r in _c().execute("SELECT cd, nome, ibge FROM municipio")}


@lru_cache(maxsize=16)
def _base(ano: int, cargo: int, turno: int = 1) -> dict:
    c = _c()
    cands = {r["numero"]: dict(r) for r in c.execute(
        "SELECT * FROM candidato WHERE ano = ? AND turno = ? AND cargo = ?", (ano, turno, cargo))}
    validos = {r["cd"]: r["validos"] for r in c.execute(
        "SELECT cd, validos FROM apuracao_mun WHERE ano = ? AND turno = ? AND cargo = ?", (ano, turno, cargo))}
    por_cand: dict[int, dict[int, int]] = {}
    legenda: dict[int, dict[int, int]] = {}
    for r in c.execute("SELECT numero, cd, votos FROM voto_mun WHERE ano = ? AND turno = ? AND cargo = ?",
                       (ano, turno, cargo)):
        if r["numero"] in cands:
            por_cand.setdefault(r["numero"], {})[r["cd"]] = r["votos"]
        elif r["numero"] < 100:
            legenda.setdefault(r["numero"], {})[r["cd"]] = r["votos"]
    # posição de cada candidato em cada cidade (entre os de voto válido)
    por_cidade: dict[int, list[tuple[int, int]]] = {}
    for n, mun in por_cand.items():
        if not cands[n]["valido"]:
            continue
        for cd, v in mun.items():
            por_cidade.setdefault(cd, []).append((v, n))
    posicao: dict[tuple[int, int], int] = {}
    lider: dict[int, int] = {}
    for cd, lst in por_cidade.items():
        lst.sort(reverse=True)
        lider[cd] = lst[0][1]
        for i, (_v, n) in enumerate(lst):
            posicao[(cd, n)] = i + 1
    partidos = {r["numero"]: (r["sigla"], r["agremiacao"]) for r in c.execute(
        "SELECT numero, sigla, agremiacao FROM partido WHERE ano = ? AND turno = ? AND cargo = ?", (ano, turno, cargo))}
    for n, x in cands.items():
        partidos.setdefault(_numero_partido(n, cargo), (x["partido"], x["agremiacao"]))
    return {"cands": cands, "validos": validos, "votos": por_cand, "legenda": legenda, "partidos": partidos,
            "posicao": posicao, "lider": lider, "n_cidade": {cd: len(l) for cd, l in por_cidade.items()}}


def _numero_partido(numero: int, cargo: int) -> int:
    return numero // (1000 if cargo == 7 else 100) if cargo in PROPORCIONAIS else numero


def _agremiacao_do_partido(b: dict, cargo: int) -> dict[int, str]:
    """número do partido → agremiação, tirado dos próprios candidatos."""
    return {p: a for p, (_sg, a) in _partido_do_numero(b, cargo).items()}


def _partido_do_numero(b: dict, cargo: int) -> dict[int, tuple[str, str]]:
    """número do partido → (sigla, agremiação). Vem da tabela `partido`, não dos
    candidatos: partido sem candidato também recebe voto de legenda (o PV teve
    290 na ALESC em 2026 sem lançar ninguém)."""
    return b["partidos"]


def em_2026(partido: str) -> str:
    """A agremiação de 2026 onde foi parar um partido de 2022 (PP e UNIÃO → União/PP…)."""
    if partido in eleicao.LEGENDA_2026_DE_2022 and eleicao.LEGENDA_2026_DE_2022[partido]:
        return eleicao.LEGENDA_2026_DE_2022[partido]
    return eleicao.sigla_para_legenda(partido)


def curta(agremiacao: str | None) -> str:
    return eleicao.SIGLA_CURTA.get(agremiacao or "", agremiacao or "")


def cor(agremiacao: str | None) -> str | None:
    return eleicao.CORES.get(agremiacao or "")


def _pesos(mun: dict[int, int]) -> dict[int, float]:
    tot = sum(mun.values())
    return {cd: v / tot for cd, v in mun.items()} if tot else {}


# ── cadeiras: a lei, refeita com votos a mais ──────────────────────────────
def _quadro(ano: int, cargo: int) -> tuple[dict[str, int], dict[str, list[int]], int]:
    b = _base(ano, cargo)
    agr_de = _agremiacao_do_partido(b, cargo)
    votos: dict[str, int] = {}
    listas: dict[str, list[int]] = {}
    for n, c in b["cands"].items():
        if not c["valido"]:
            continue
        v = sum(b["votos"].get(n, {}).values())
        votos[c["agremiacao"]] = votos.get(c["agremiacao"], 0) + v
        listas.setdefault(c["agremiacao"], []).append(v)
    for p, mun in b["legenda"].items():
        a = agr_de.get(p)
        if a:
            votos[a] = votos.get(a, 0) + sum(mun.values())
    return votos, listas, sum(votos.values())


def _cadeiras(votos, listas, validos, vagas) -> dict[str, int]:
    return eleicao.distribuir(votos, lugares=vagas, candidatos=listas, validos=validos)["cadeiras"]


@lru_cache(maxsize=8)
def _margens(ano: int, cargo: int) -> dict:
    """Por agremiação: cadeiras, votos para a próxima e votos que podia perder."""
    if cargo not in PROPORCIONAIS:
        return {}
    votos, listas, validos = _quadro(ano, cargo)
    vagas = VAGAS[cargo]
    base = _cadeiras(votos, listas, validos, vagas)
    saida = {}
    for a, v in votos.items():
        k = base.get(a, 0)
        ordenada = sorted(listas.get(a, []), reverse=True)

        def com(x: int) -> int:
            vv = dict(votos)
            vv[a] = v + x
            ls = dict(listas)
            lista = list(ordenada)
            # o voto a mais vai para quem ocuparia a cadeira seguinte (os pisos
            # de 10% e 20% do quociente são individuais)
            if x > 0 and len(lista) > k:
                lista[k] += x
            ls[a] = lista
            return _cadeiras(vv, ls, validos + x, vagas).get(a, 0)

        falta = None
        if len(ordenada) > k:
            lo, hi = 0, max(2 * validos // vagas, 1)
            if com(hi) > k:
                while hi - lo > 1:
                    meio = (lo + hi) // 2
                    if com(meio) > k:
                        hi = meio
                    else:
                        lo = meio
                falta = hi
        folga = None
        if k > 0:
            lo, hi = 0, v
            while hi - lo > 1:
                meio = (lo + hi) // 2
                vv = dict(votos)
                vv[a] = v - meio
                if _cadeiras(vv, listas, validos - meio, vagas).get(a, 0) < k:
                    hi = meio
                else:
                    lo = meio
            folga = lo
        saida[a] = {"votos": v, "cadeiras": k, "falta_proxima": falta, "folga": folga}
    return {"qe": eleicao.quociente_eleitoral(validos, vagas), "validos": validos, "agr": saida}


# ── candidatos ──────────────────────────────────────────────────────────────
def lista_candidatos(ano: int, cargo: int) -> list[dict]:
    b = _base(ano, cargo)
    anteriores = _anteriores(ano)
    saida = []
    for n, c in b["cands"].items():
        ant = anteriores.get(c["pessoa"]) if c["pessoa"] else None
        saida.append({"n": n, "nm": c["urna"], "p": c["partido"], "a": c["agremiacao"], "ac": curta(c["agremiacao"]),
                      "cor": cor(c["agremiacao"]), "v": c["votos"],
                      "st": c["situacao"], "e": c["eleito"], "ok": c["valido"],
                      "v22": ant["votos"] if ant else None, "c22": ant["cargo"] if ant else None})
    saida.sort(key=lambda x: -(x["v"] or 0))
    return saida


@lru_cache(maxsize=4)
def _anteriores_cache(ano: int) -> dict[str, dict]:
    """A candidatura de cada pessoa na eleição geral anterior (a de mais voto)."""
    m: dict[str, dict] = {}
    for r in _c().execute("SELECT * FROM candidato WHERE ano = ? AND turno = 1 AND pessoa != ''", (ano - 4,)):
        if r["pessoa"] not in m or (r["votos"] or 0) > (m[r["pessoa"]]["votos"] or 0):
            m[r["pessoa"]] = dict(r)
    return m


def _anteriores(ano: int) -> dict[str, dict]:
    return _anteriores_cache(ano)


def _concentracao(pesos: dict[int, float], b: dict, numero: int) -> dict:
    ordem = sorted(pesos.values(), reverse=True)
    hhi = sum(p * p for p in ordem)
    cidades_1o = sum(1 for cd, n in b["lider"].items() if n == numero)
    fortes = sum(1 for cd, v in b["votos"].get(numero, {}).items()
                 if b["validos"].get(cd) and v / b["validos"][cd] >= 0.05)
    return {"municipios": len(pesos), "n_efetivo": round(1 / hhi, 1) if hhi else 0,
            "top1": round(ordem[0] * 100, 1) if ordem else 0,
            "top5": round(sum(ordem[:5]) * 100, 1), "top10": round(sum(ordem[:10]) * 100, 1),
            "em_1o": cidades_1o, "acima_5pct": fortes}


def concorrentes(ano: int, cargo: int, numero: int, n: int = 10) -> list[dict]:
    b = _base(ano, cargo)
    meu = _pesos(b["votos"].get(numero, {}))
    if not meu:
        return []
    eu = b["cands"][numero]
    lista = []
    for outro, mun in b["votos"].items():
        c = b["cands"][outro]
        if outro == numero or not c["valido"] or (c["votos"] or 0) < 1000:
            continue
        p = _pesos(mun)
        sob = sum(min(w, p.get(cd, 0.0)) for cd, w in meu.items())
        lista.append({"n": outro, "nm": c["urna"], "p": c["partido"], "a": c["agremiacao"], "ac": curta(c["agremiacao"]),
                      "cor": cor(c["agremiacao"]), "v": c["votos"],
                      "e": c["eleito"], "st": c["situacao"], "sobreposicao": round(sob * 100, 1),
                      "mesma_lista": c["agremiacao"] == eu["agremiacao"]})
    lista.sort(key=lambda x: -x["sobreposicao"])
    return lista[:n]


def _margem(ano: int, cargo: int, numero: int) -> dict | None:
    if cargo not in PROPORCIONAIS:
        return None
    b = _base(ano, cargo)
    c = b["cands"][numero]
    m = _margens(ano, cargo)
    agr = m["agr"].get(c["agremiacao"])
    if not agr:
        return None
    lista = sorted(((x["votos"] or 0, n) for n, x in b["cands"].items()
                    if x["agremiacao"] == c["agremiacao"] and x["valido"]), reverse=True)
    pos = next((i + 1 for i, (_v, n) in enumerate(lista) if n == numero), None)
    k = agr["cadeiras"]
    saida = {"qe": m["qe"], "posicao_lista": pos, "tamanho_lista": len(lista), "cadeiras_lista": k,
             "falta_proxima_lista": agr["falta_proxima"], "folga_lista": agr["folga"],
             "piso_10": round(m["qe"] * 0.10), "piso_20": round(m["qe"] * 0.20)}
    if pos is None:
        return saida
    if pos <= k and len(lista) > k:
        prox = lista[k]
        saida["sobre_1o_suplente"] = (c["votos"] or 0) - prox[0]
        saida["primeiro_suplente"] = b["cands"][prox[1]]["urna"]
    elif pos > k and k >= 1:
        ult = lista[k - 1]
        saida["para_passar_ultimo"] = ult[0] - (c["votos"] or 0) + 1
        saida["ultimo_eleito"] = b["cands"][ult[1]]["urna"]
    saida["seria_o_proximo"] = pos == k + 1
    return saida


def _previsao_e_redes(sq: str | None) -> dict:
    """O que o /politicos sabia antes da eleição (previsão congelada, receita, Instagram)."""
    if not sq:
        return {}
    from politicos import db
    con = db.conectar()
    try:
        prev = con.execute(
            """SELECT pc.*, p.criado_em AS previsao_em FROM v2_previsao_candidato pc
                 JOIN v2_previsao p ON p.id = pc.previsao_id
                WHERE pc.sq = ? ORDER BY pc.previsao_id DESC LIMIT 1""", (sq,)).fetchone()
        perfil = con.execute(
            "SELECT id, username, seguidores, total_posts FROM perfis WHERE sq_candidato = ? AND descartado_em IS NULL",
            (sq,)).fetchone()
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    saida = {}
    if prev:
        saida["previsao"] = {"p_eleito": prev["p_eleito"], "receita": prev["receita_2026"],
                             "em": prev["previsao_em"], "fonte": prev["fonte"]}
    if perfil:
        saida["instagram"] = {"perfil_id": perfil["id"], "username": perfil["username"],
                              "seguidores": perfil["seguidores"], "posts": perfil["total_posts"]}
    return saida


def raio_x(ano: int, cargo: int, numero: int) -> dict | None:
    b = _base(ano, cargo)
    c = b["cands"].get(numero)
    if not c:
        return None
    mun = b["votos"].get(numero, {})
    pesos = _pesos(mun)
    nomes = _municipios()
    ant = _anteriores(ano).get(c["pessoa"]) if c["pessoa"] else None
    mun_ant: dict[int, int] = {}
    if ant:
        for r in _c().execute("SELECT cd, votos FROM voto_mun WHERE ano = ? AND turno = 1 AND cargo = ? AND numero = ?",
                              (ant["ano"], ant["cargo"], ant["numero"])):
            mun_ant[r["cd"]] = r["votos"]
    validos_uf = sum(b["validos"].values())
    validos_cand = sorted(((x["votos"] or 0, n) for n, x in b["cands"].items() if x["valido"]), reverse=True)
    rank = next((i + 1 for i, (_v, n) in enumerate(validos_cand) if n == numero), None)
    cidades = []
    for cd in set(mun) | set(mun_ant):
        v = mun.get(cd, 0)
        val = b["validos"].get(cd) or 0
        cidades.append({"cd": cd, "nm": nomes.get(cd, {}).get("nome", str(cd)), "v": v,
                        "forca": round(v / val * 100, 2) if val else 0,
                        "peso": round(pesos.get(cd, 0) * 100, 2),
                        "pos": b["posicao"].get((cd, numero)), "de": b["n_cidade"].get(cd),
                        "lider": b["cands"][b["lider"][cd]]["urna"] if cd in b["lider"] and b["lider"][cd] != numero else None,
                        "v_ant": mun_ant.get(cd) if ant else None})
    cidades.sort(key=lambda x: -x["v"])
    saida = {
        "ano": ano, "cargo": cargo, "cargo_nome": microdados.CARGOS[cargo], "n": numero,
        "nm": c["urna"], "nome": c["nome"], "partido": c["partido"], "agremiacao": c["agremiacao"],
        "ac": curta(c["agremiacao"]), "cor": cor(c["agremiacao"]),
        "situacao": c["situacao"], "eleito": c["eleito"], "valido": c["valido"], "votos": c["votos"],
        "pct": round((c["votos"] or 0) / validos_uf * 100, 2) if validos_uf and cargo != 1 else None,
        "posicao": rank, "candidatos": len(validos_cand),
        "concentracao": _concentracao(pesos, b, numero),
        "cidades": cidades,
        "anterior": {"ano": ant["ano"], "cargo": ant["cargo"], "cargo_nome": microdados.CARGOS.get(ant["cargo"]),
                     "votos": ant["votos"], "situacao": ant["situacao"], "partido": ant["partido"],
                     "nm": ant["urna"]} if ant else None,
        "tem_anterior": bool(_anteriores(ano)),
        "margem": _margem(ano, cargo, numero),
        "concorrentes": concorrentes(ano, cargo, numero),
        "secoes": _secoes_disponiveis(ano),
    }
    saida.update(_previsao_e_redes(c["sq"]))
    return saida


# ── município e partido ────────────────────────────────────────────────────
def municipio(ano: int, cargo: int, cd: int) -> dict | None:
    nomes = _municipios()
    if cd not in nomes:
        return None
    b = _base(ano, cargo)
    a = _c().execute("SELECT * FROM apuracao_mun WHERE ano = ? AND turno = 1 AND cargo = ? AND cd = ?",
                     (ano, cargo, cd)).fetchone()
    cands = sorted(((m.get(cd, 0), n) for n, m in b["votos"].items() if m.get(cd) and b["cands"][n]["valido"]),
                   reverse=True)
    val = b["validos"].get(cd) or 0
    agr_de = _agremiacao_do_partido(b, cargo)
    por_agr: dict[str, int] = {}
    for v, n in cands:
        ag = b["cands"][n]["agremiacao"]
        por_agr[ag] = por_agr.get(ag, 0) + v
    for p, m in b["legenda"].items():
        if m.get(cd) and agr_de.get(p):
            por_agr[agr_de[p]] = por_agr.get(agr_de[p], 0) + m[cd]
    ant = _por_agremiacao_mun(ano - 4, cargo, cd)
    return {
        "cd": cd, "nm": nomes[cd]["nome"], "ano": ano, "cargo": cargo,
        "aptos": a["aptos"] if a else None, "comparecimento": a["comparecimento"] if a else None,
        "abstencao": a["abstencao"] if a else None, "validos": val,
        "brancos": a["brancos"] if a else None, "nulos": a["nulos"] if a else None,
        "candidatos": [{"n": n, "nm": b["cands"][n]["urna"], "p": b["cands"][n]["partido"],
                        "a": b["cands"][n]["agremiacao"], "v": v, "pct": round(v / val * 100, 2) if val else 0,
                        "e": b["cands"][n]["eleito"]} for v, n in cands[:60]],
        "agremiacoes": [{"a": ag, "ac": curta(ag), "cor": cor(ag), "v": v, "pct": round(v / val * 100, 2) if val else 0,
                         "pct_ant": ant.get(ag)} for ag, v in sorted(por_agr.items(), key=lambda kv: -kv[1])],
        "secoes": _secoes_disponiveis(ano),
    }


def _por_agremiacao_mun(ano: int, cargo: int, cd: int) -> dict[str, float]:
    """% de cada agremiação de HOJE na cidade, na eleição anterior (partidos de então somados)."""
    try:
        b = _base(ano, cargo)
    except sqlite3.Error:
        return {}
    val = b["validos"].get(cd) or 0
    if not val:
        return {}
    soma: dict[str, int] = {}
    sg_de = _partido_do_numero(b, cargo)
    for n, m in b["votos"].items():
        c = b["cands"][n]
        if c["valido"] and m.get(cd):
            hoje = em_2026(c["partido"])
            soma[hoje] = soma.get(hoje, 0) + m[cd]
    for p, m in b["legenda"].items():
        if m.get(cd) and p in sg_de:
            hoje = em_2026(sg_de[p][0])
            soma[hoje] = soma.get(hoje, 0) + m[cd]
    return {a: round(v / val * 100, 2) for a, v in soma.items()}


def _resolver_agremiacao(b: dict, pedido: str) -> str | None:
    """Aceita a agremiação, a sigla de um partido dela, ou — numa eleição antiga —
    a agremiação de HOJE (fica com a maior das que a formaram)."""
    agrs = {c["agremiacao"] for c in b["cands"].values()}
    if pedido in agrs:
        return pedido
    alvo = pedido.upper()
    for c in b["cands"].values():
        if (c["partido"] or "").upper() == alvo or curta(c["agremiacao"]).upper() == alvo:
            return c["agremiacao"]
    votos: dict[str, int] = {}
    for c in b["cands"].values():
        if c["valido"] and em_2026(c["partido"]) == pedido:
            votos[c["agremiacao"]] = votos.get(c["agremiacao"], 0) + (c["votos"] or 0)
    return max(votos, key=votos.get) if votos else None


def partido(ano: int, cargo: int, pedido: str) -> dict | None:
    b = _base(ano, cargo)
    opcoes = [{"a": a, "ac": curta(a)} for a in sorted({c["agremiacao"] for c in b["cands"].values()}, key=curta)]
    agremiacao = _resolver_agremiacao(b, pedido)
    membros = [n for n, c in b["cands"].items() if c["agremiacao"] == agremiacao and c["valido"]]
    if not membros:
        return {"ausente": True, "pedido": pedido, "agremiacoes": opcoes}
    agr_de = _agremiacao_do_partido(b, cargo)
    mun: dict[int, int] = {}
    for n in membros:
        for cd, v in b["votos"].get(n, {}).items():
            mun[cd] = mun.get(cd, 0) + v
    leg = 0
    for p, m in b["legenda"].items():
        if agr_de.get(p) == agremiacao:
            for cd, v in m.items():
                mun[cd] = mun.get(cd, 0) + v
                leg += v
    total = sum(mun.values())
    nomes = _municipios()
    margens = _margens(ano, cargo).get("agr", {}).get(agremiacao) if cargo in PROPORCIONAIS else None
    cands = sorted(membros, key=lambda n: -(b["cands"][n]["votos"] or 0))
    antes = forca_anterior(ano, cargo, agremiacao)
    validos_uf = sum(b["validos"].values())
    total_antes = None
    if antes:
        ba = _base(ano - 4, cargo)
        total_antes = round(sum(antes[cd] * ba["validos"][cd] / 100 for cd in antes) / sum(ba["validos"].values()) * 100, 2)
    return {
        "ano": ano, "cargo": cargo, "agremiacao": agremiacao, "ac": curta(agremiacao), "cor": cor(agremiacao),
        "votos": total, "legenda": leg,
        "pct": round(total / validos_uf * 100, 2) if validos_uf else None, "pct_ant": total_antes,
        "margem": margens,
        "cidades": sorted(({"cd": cd, "nm": nomes.get(cd, {}).get("nome", str(cd)), "v": v,
                            "forca": round(v / b["validos"][cd] * 100, 2) if b["validos"].get(cd) else 0,
                            "forca_ant": antes.get(cd)}
                           for cd, v in mun.items()), key=lambda x: -x["v"]),
        "candidatos": [{"n": n, "nm": b["cands"][n]["urna"], "p": b["cands"][n]["partido"],
                        "v": b["cands"][n]["votos"], "e": b["cands"][n]["eleito"], "st": b["cands"][n]["situacao"],
                        "peso": round((b["cands"][n]["votos"] or 0) / total * 100, 1) if total else 0}
                       for n in cands],
        "agremiacoes": opcoes, "pedido": pedido,
    }


# ── dentro da cidade: locais de votação e bairros ──────────────────────────
@lru_cache(maxsize=4)
def _secoes_disponiveis(ano: int) -> bool:
    return _c().execute("SELECT 1 FROM voto_secao WHERE ano = ? LIMIT 1", (ano,)).fetchone() is not None


def locais(ano: int, cargo: int, numero: int | None, cd: int, agremiacao: str | None = None) -> dict | None:
    """Voto por local de votação numa cidade: do candidato, ou da agremiação inteira."""
    if not _secoes_disponiveis(ano):
        return None
    c = _c()
    b = _base(ano, cargo)
    if agremiacao:
        nums = [n for n, x in b["cands"].items() if x["agremiacao"] == agremiacao and x["valido"]]
        nums += [p for p, a in _agremiacao_do_partido(b, cargo).items() if a == agremiacao]
    else:
        nums = [numero]
    marcas = ",".join("?" * len(nums))
    meus: dict[tuple[int, int], int] = {}
    for r in c.execute(f"""SELECT v.zona, s.local, SUM(v.votos) v FROM voto_secao v
                            JOIN secao s ON s.ano = v.ano AND s.cd = v.cd AND s.zona = v.zona AND s.secao = v.secao
                           WHERE v.ano = ? AND v.turno = 1 AND v.cargo = ? AND v.cd = ? AND v.numero IN ({marcas})
                           GROUP BY v.zona, s.local""", (ano, cargo, cd, *nums)):
        meus[(r["zona"], r["local"])] = r["v"]
    total: dict[tuple[int, int], int] = {}
    for r in c.execute("""SELECT t.zona, s.local, SUM(t.validos) v FROM total_secao t
                           JOIN secao s ON s.ano = t.ano AND s.cd = t.cd AND s.zona = t.zona AND s.secao = t.secao
                          WHERE t.ano = ? AND t.turno = 1 AND t.cargo = ? AND t.cd = ?
                          GROUP BY t.zona, s.local""", (ano, cargo, cd)):
        total[(r["zona"], r["local"])] = r["v"]
    info = {(r["zona"], r["local"]): dict(r) for r in c.execute(
        "SELECT * FROM local_votacao WHERE ano = ? AND cd = ?", (ano, cd))}
    lista, bairros = [], {}
    for k, tot in total.items():
        v = meus.get(k, 0)
        i = info.get(k, {})
        bairro = i.get("bairro") or "—"
        lista.append({"zona": k[0], "local": k[1], "nm": i.get("nome") or f"Local {k[1]}", "bairro": bairro,
                      "lat": i.get("lat"), "lon": i.get("lon"), "v": v, "validos": tot,
                      "forca": round(v / tot * 100, 2) if tot else 0})
        bb = bairros.setdefault(bairro, {"bairro": bairro, "v": 0, "validos": 0, "locais": 0})
        bb["v"] += v
        bb["validos"] += tot
        bb["locais"] += 1
    for bb in bairros.values():
        bb["forca"] = round(bb["v"] / bb["validos"] * 100, 2) if bb["validos"] else 0
    lista.sort(key=lambda x: -x["v"])
    return {"ano": ano, "cd": cd, "nm": _municipios().get(cd, {}).get("nome"), "locais": lista,
            "bairros": sorted(bairros.values(), key=lambda x: -x["v"]),
            "total": sum(meus.values())}


# ── quem vota nele: perfil do eleitorado das seções, ponderado pelo voto ────
DIMENSOES = [("fem", "Mulheres"), ("i16_24", "16 a 24 anos"), ("i25_34", "25 a 34"), ("i35_44", "35 a 44"),
             ("i45_59", "45 a 59"), ("i60", "60 ou mais"), ("esc_fund", "Até o fundamental"),
             ("esc_medio", "Ensino médio"), ("esc_sup", "Ensino superior"), ("preta_parda", "Pretos e pardos")]


def _composicao(sql: str, args: tuple) -> tuple[dict[str, float], float]:
    """Σ peso × fração de cada dimensão nas seções, e Σ peso."""
    cols = [d for d, _ in DIMENSOES]
    soma = dict.fromkeys(cols, 0.0)
    total = 0.0
    for r in _c().execute(sql, args):
        el, peso = r["eleitores"] or 0, r["peso"] or 0
        if not el or not peso:
            continue
        for x in cols:
            base = (r["cor_inf"] or 0) if x == "preta_parda" else el
            if base:
                soma[x] += peso * r[x] / base
        total += peso
    return soma, total


@lru_cache(maxsize=16)
def _composicao_geral(ano: int, cargo: int, ano_perfil: int) -> tuple[dict[str, float], float]:
    return _composicao("""
            SELECT p.*, t.validos peso FROM total_secao t
              JOIN perfil_secao p ON p.ano = ? AND p.cd = t.cd AND p.zona = t.zona AND p.secao = t.secao
             WHERE t.ano = ? AND t.turno = 1 AND t.cargo = ?""", (ano_perfil, ano, cargo))


def perfil(ano: int, cargo: int, numero: int) -> dict | None:
    """Composição do eleitorado das seções onde ele teve voto, pesada pelo voto,
    contra a mesma composição pesada pelo voto válido de todo mundo.

    É inferência ECOLÓGICA: diz que ele é forte em seções mais jovens, não que
    jovens votaram nele. A tela fala nesses termos.
    """
    if not _secoes_disponiveis(ano):
        return None
    ano_perfil = _c().execute("SELECT MAX(ano) a FROM perfil_secao WHERE ano <= ?", (ano,)).fetchone()["a"]
    if ano_perfil is None:
        return None
    soma_c, vc = _composicao(f"""
            SELECT p.*, v.votos peso FROM voto_secao v
              JOIN perfil_secao p ON p.ano = ? AND p.cd = v.cd AND p.zona = v.zona AND p.secao = v.secao
             WHERE v.ano = ? AND v.turno = 1 AND v.cargo = ? AND v.numero = ?""", (ano_perfil, ano, cargo, numero))
    if not vc:
        return None
    soma_t, vt = _composicao_geral(ano, cargo, ano_perfil)
    dims = []
    for x, rot in DIMENSOES:
        meu = soma_c[x] / vc
        geral = soma_t[x] / vt if vt else 0
        if not geral:
            continue       # o TSE não publicou essa dimensão naquele ano (raça/cor em 2022)
        dims.append({"dim": x, "rotulo": rot, "meu": round(meu * 100, 1), "geral": round(geral * 100, 1),
                     "indice": round(meu / geral * 100)})
    return {"ano_perfil": ano_perfil, "votos_cobertos": int(vc), "dimensoes": dims}


# ── mapas de SC inteira ────────────────────────────────────────────────────
def lideres(ano: int, cargo: int) -> dict:
    """Em cada cidade: a agremiação e o candidato mais votados (o mapa de "quem ganhou onde")."""
    b = _base(ano, cargo)
    agr_de = _agremiacao_do_partido(b, cargo)
    por_cd: dict[int, dict[str, int]] = {}
    for n, m in b["votos"].items():
        c = b["cands"][n]
        if not c["valido"]:
            continue
        for cd, v in m.items():
            d = por_cd.setdefault(cd, {})
            d[c["agremiacao"]] = d.get(c["agremiacao"], 0) + v
    for p, m in b["legenda"].items():
        a = agr_de.get(p)
        if a:
            for cd, v in m.items():
                d = por_cd.setdefault(cd, {})
                d[a] = d.get(a, 0) + v
    saida = {}
    for cd, d in por_cd.items():
        a, v = max(d.items(), key=lambda kv: kv[1])
        val = b["validos"].get(cd) or sum(d.values())
        n = b["lider"].get(cd)
        saida[str(cd)] = {"a": a, "ac": curta(a), "cor": cor(a), "pct": round(v / val * 100, 1) if val else 0,
                          "cand": b["cands"][n]["urna"] if n else None,
                          "cand_pct": round(b["votos"][n][cd] / val * 100, 1) if n and val else None}
    legenda = {}
    for x in saida.values():
        legenda.setdefault(x["a"], {"a": x["a"], "ac": x["ac"], "cor": x["cor"], "cidades": 0})["cidades"] += 1
    return {"ano": ano, "cargo": cargo, "cidades": saida,
            "legenda": sorted(legenda.values(), key=lambda x: -x["cidades"])}


def forca_anterior(ano: int, cargo: int, agremiacao: str) -> dict[int, float]:
    """% da agremiação de HOJE em cada cidade na eleição anterior (partidos de então somados)."""
    try:
        b = _base(ano - 4, cargo)
    except sqlite3.Error:
        return {}
    if not b["cands"]:
        return {}
    sg_de = _partido_do_numero(b, cargo)
    soma: dict[int, int] = {}
    for n, m in b["votos"].items():
        c = b["cands"][n]
        if c["valido"] and em_2026(c["partido"]) == agremiacao:
            for cd, v in m.items():
                soma[cd] = soma.get(cd, 0) + v
    for p, m in b["legenda"].items():
        if p in sg_de and em_2026(sg_de[p][0]) == agremiacao:
            for cd, v in m.items():
                soma[cd] = soma.get(cd, 0) + v
    return {cd: round(v / b["validos"][cd] * 100, 2) for cd, v in soma.items() if b["validos"].get(cd)}
