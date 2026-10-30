"""O "chute" do 2º turno: os grupos de eleitor do 1º turno, a dica da pesquisa e
três cenários que fecham a conta.

    venv/bin/python -m tools.migracoes.2026-10-30-chute-2t

Roda UMA VEZ, à mão, e grava `apuracao/data/arquivo/2026-2t/chute.json`. A
página `/apuracao` (static/chute.js) e `/apuracao/cenarios` só leem esse arquivo.

**Os grupos.** Todo eleitor apto do 1º turno está em exatamente um grupo: votou
no Lula, no Flávio, num dos cinco blocos da terceira via, branco/nulo, ou não
foi votar. A soma dos grupos é o eleitorado (158,7 mi, `conta.json`
conferencia). Cada grupo se divide em três destinos no 2º turno: Lula, Flávio,
ou nenhum dos dois (branco, nulo ou não foi votar). Assim o "nenhum" do TSE é o
eleitorado menos os votos dos dois, e a conta fecha nos três destinos.

**A dica.** Quaest de 10 a 13/10/2026 (2.154 entrevistas, Exame, 14/10): o voto
no 2º turno por eleitor do 1º. Os indecisos são repartidos na proporção dos
outros três. A Quaest não abriu o Zema em outubro; para ele vale a de 3 a
6/09/2026 (Revista Oeste, 07/09). Retenção de Lula e Flávio não foi publicada.

**Os cenários.** Cada um fixa uma hipótese e o IPF (ajuste proporcional
iterativo) acha, partindo da pesquisa, o cenário mais parecido com ela que bate
com o TSE nos três destinos.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQ = RAIZ / "apuracao" / "data" / "arquivo" / "2026-2t"
DEST = ("lula", "flavio", "nenhum")

QUAEST_OUT = {"nome": "Quaest, 10 a 13/10/2026", "url": "https://exame.com/brasil/lula-ou-flavio-quaest-mostra-para-onde-vao-os-votos-de-cury-caiado-e-renan-santos/"}
QUAEST_SET = {"nome": "Quaest, 3 a 6/09/2026", "url": "https://revistaoeste.com/politica/maioria-dos-eleitores-de-cury-renan-caiado-e-zema-votaria-em-flavio-no-2o-turno/"}
ATLAS_OUT = {"nome": "AtlasIntel, 13 a 18/10/2026", "url": "https://www.infomoney.com.br/politica/atlasintel-para-onde-foram-os-votos-de-caiado-renan-zema-e-cury-no-2o-turno/"}
DATAFOLHA_SET = {"nome": "Datafolha, 8 a 17/09/2026", "url": "https://www.metropoles.com/brasil/datafolha-flavio-atrai-eleitores-de-zema-renan-caiado-e-cury-em-2o-turno"}
APOIOS = {"nome": "Apoios no 2º turno", "url": "https://acritica.net/eleicoes-2026/caiado-zema-e-cury-apoiam-flavio-no-2o-turno-renan-santos-libera-eleitores/"}
FOTOS = {  # /static/fotos/<id>.jpg, recortadas de Wikimedia Commons
    "lula": {"url": "https://commons.wikimedia.org/wiki/File:Foto_oficial_de_Luiz_In%C3%A1cio_Lula_da_Silva_(ombros)_denoise.jpg", "licenca": "CC BY 2.0"},
    "flavio": {"url": "https://commons.wikimedia.org/wiki/File:2026_FLAVIO_BOLSONARO_CANDIDATO_PRESIDENTE_TSE_(280002551544).jpg", "licenca": "CC BY 4.0, TSE"},
    "cury": {"url": "https://commons.wikimedia.org/wiki/File:2026_ESCRITOR_AUGUSTO_CURY_CANDIDATO_PRESIDENTE_TSE_(280002551547).jpg", "licenca": "CC BY 4.0, TSE"},
    "renan": {"url": "https://commons.wikimedia.org/wiki/File:2026_RENAN_SANTOS_CANDIDATO_PRESIDENTE_TSE_(280002540694).jpg", "licenca": "CC BY 4.0, TSE"},
    "caiado": {"url": "https://commons.wikimedia.org/wiki/File:2026_RONALDO_CAIADO_CANDIDATO_PRESIDENTE_TSE_(280002551932).jpg", "licenca": "CC BY 4.0, TSE"},
    "zema": {"url": "https://commons.wikimedia.org/wiki/File:2026_ZEMA_CANDIDATO_PRESIDENTE_TSE_(280002539826).jpg", "licenca": "CC BY 4.0, TSE"},
}


def dica(lula, flavio, nenhum, indecisos=0):
    t = lula + flavio + nenhum
    return {"lula": lula / t, "flavio": flavio / t, "nenhum": nenhum / t,
            "bruto": {"lula": lula, "flavio": flavio, "nenhum": nenhum, "indecisos": indecisos}}


def op(inst, fonte, lula, flavio, nenhum, indecisos=0, obs=None, texto=None):
    """Uma "opinião" (uma pesquisa) sobre um grupo, com os indecisos repartidos."""
    o = {"inst": inst, "fonte": fonte, **dica(lula, flavio, nenhum, indecisos)}
    if obs:
        o["obs"] = obs
    if texto:
        o["texto"] = texto
    return o


# Para onde cada grupo iria, segundo cada pesquisa (até três por grupo).
# Datafolha de setembro é de antes do 1º turno (2º turno hipotético); para Cury
# e Caiado ela não separou branco/nulo de indeciso, então "nenhum" é o resto.
OPINIOES = {
    "lula1": [op("Datafolha", DATAFOLHA_SET, 98, 1, 1, obs="antes do 1º turno", texto="98% mantêm o voto · 2% mudam"),
              op("Palpite clássico", None, 100, 0, 0, texto="Todo mundo repete o voto")],
    "flavio1": [op("Datafolha", DATAFOLHA_SET, 1, 99, 0, obs="antes do 1º turno", texto="99% mantêm o voto · 1% muda"),
                op("Palpite clássico", None, 0, 100, 0, texto="Todo mundo repete o voto")],
    "cury": [op("Quaest", QUAEST_OUT, 34, 30, 30, 6), op("AtlasIntel", ATLAS_OUT, 52.1, 42.4, 5.6),
             op("Datafolha", DATAFOLHA_SET, 35, 41, 24, obs="antes do 1º turno")],
    "renan": [op("Quaest", QUAEST_OUT, 14, 40, 43, 3), op("AtlasIntel", ATLAS_OUT, 31.9, 33.5, 34.6),
              op("Datafolha", DATAFOLHA_SET, 22, 43, 34, obs="antes do 1º turno")],
    "caiado": [op("Quaest", QUAEST_OUT, 23, 42, 33, 2), op("AtlasIntel", ATLAS_OUT, 24.5, 69.8, 5.7),
               op("Datafolha", DATAFOLHA_SET, 30, 43, 27, obs="antes do 1º turno")],
    "zema": [op("Quaest", QUAEST_SET, 4, 59, 37, obs="antes do 1º turno"), op("AtlasIntel", ATLAS_OUT, 30.7, 61.3, 8.0, obs="Zema junto com outros"),
             op("Datafolha", DATAFOLHA_SET, 25, 48, 27, obs="antes do 1º turno")],
    "outros": [op("Quaest", QUAEST_OUT, 33, 38, 22, 7), op("AtlasIntel", ATLAS_OUT, 30.7, 61.3, 8.0, obs="inclui o Zema")],
    "bn1": [op("Quaest", QUAEST_OUT, 43, 38, 17, 2, obs="junto com quem não votou"), op("AtlasIntel", ATLAS_OUT, 21.1, 38.7, 40.2),
            op("Datafolha", DATAFOLHA_SET, 20, 17, 62, obs="antes do 1º turno")],
    # Quem só foi votar no 2º turno: a pesquisa ouve quem faltou no 1º e pretende votar.
    "abst1": [op("Quaest", QUAEST_OUT, 43, 38, 17, 2, obs="junto com brancos e nulos"), op("AtlasIntel", ATLAS_OUT, 55.7, 40.2, 4.2)],
    "fora2": [],
}
FOTO = {"lula1": "lula", "flavio1": "flavio", "cury": "cury", "renan": "renan", "caiado": "caiado", "zema": "zema"}
APOIO = {"lula1": ("finalista", "lula"), "flavio1": ("finalista", "flavio"), "cury": ("apoiou o Flávio", "flavio"),
         "renan": ("liberou os eleitores", "neutro"), "caiado": ("apoiou o Flávio", "flavio"), "zema": ("apoiou o Flávio", "flavio")}
ICONE = {"outros": "👥", "bn1": "🗳️", "abst1": "🗳️", "fora2": "🏠"}
APOIOS_OUTROS = {"nome": "Terra, 13/10/2026", "url": "https://www.terra.com.br/noticias/brasil/politica/eleicoes-2026-pco-orienta-voto-nulo-no-2-turno-da-eleicao-presidencial,6ee240a310a2fcc3dc76f9e5b34db831libdjuze.html"}
# Os 6 de "outros": nome na urna (conta.json) → como mostrar, foto (TSE, CC BY 4.0) e posição no 2º turno.
OUTROS = {
    "SAMARA": ("Samara", "UP", "samara", "apoiou o Lula", "lula"),
    "HERTZ DIAS": ("Hertz Dias", "PSTU", "hertz", "apoiou o Lula", "lula"),
    "CLARIANA BARAO": ("Clariana Barão", "DC", "clariana", "apoiou o Flávio", "flavio"),
    "EDMILSON COSTA": ("Edmilson Costa", "PCB", "edmilson", "apoiou o Lula", "lula"),
    "VETERINÁRIO WILSON GRASSI": ("Wilson Grassi", "Democrata", "grassi", "ficou neutro", "neutro"),
    "RUI COSTA PIMENTA": ("Rui Costa Pimenta", "PCO", "rui", "pediu voto nulo", "neutro"),
}


def grupos(conta):
    n = conta["nacional"]
    cand = {c["nm"]: c["votos_1t"] for c in conta["transicao"]["candidatos"]}
    ufs = conta["conferencia"]["ufs"]
    eleitores1 = sum(u["t1_eleitores"] for u in ufs)
    outros = {k: v for k, v in cand.items() if k not in ("ESCRITOR AUGUSTO CURY", "RENAN SANTOS", "RONALDO CAIADO", "ZEMA")}
    g = [
        {"id": "lula1", "nome": "Votou no Lula", "v": n["lula1"], "fam": "finalistas",
         "dica": None, "dica_txt": "A pesquisa não publicou quantos mantêm o voto. Na prática, quase todo mundo mantém."},
        {"id": "flavio1", "nome": "Votou no Flávio", "v": n["flavio1"], "fam": "finalistas",
         "dica": None, "dica_txt": "A pesquisa não publicou quantos mantêm o voto. Na prática, quase todo mundo mantém."},
        {"id": "cury", "nome": "Votou no Augusto Cury", "v": cand["ESCRITOR AUGUSTO CURY"], "fam": "terceira",
         "dica": dica(34, 30, 30, 6), "fonte": QUAEST_OUT, "nota": "Cury declarou apoio ao Flávio em 08/10."},
        {"id": "renan", "nome": "Votou no Renan Santos", "v": cand["RENAN SANTOS"], "fam": "terceira",
         "dica": dica(14, 40, 43, 3), "fonte": QUAEST_OUT},
        {"id": "caiado", "nome": "Votou no Ronaldo Caiado", "v": cand["RONALDO CAIADO"], "fam": "terceira",
         "dica": dica(23, 42, 33, 2), "fonte": QUAEST_OUT},
        {"id": "zema", "nome": "Votou no Zema", "v": cand["ZEMA"], "fam": "terceira",
         "dica": dica(4, 59, 37), "fonte": QUAEST_SET, "nota": "Pesquisa de antes do 1º turno: a de outubro não separou o Zema."},
        {"id": "outros", "nome": "Votou em outro candidato", "v": sum(outros.values()), "fam": "terceira",
         "dica": dica(33, 38, 22, 7), "fonte": QUAEST_OUT, "membros": len(outros),
         "lista": [{"nome": OUTROS[k][0], "partido": OUTROS[k][1], "foto": "/static/fotos/" + OUTROS[k][2] + ".jpg",
                    "apoio": {"txt": OUTROS[k][3], "cor": OUTROS[k][4]}, "v": v}
                   for k, v in sorted(outros.items(), key=lambda kv: -kv[1])]},
        {"id": "bn1", "nome": "Votou branco ou nulo", "v": n["brancos1"] + n["nulos1"], "fam": "fora",
         "dica": dica(43, 38, 17, 2), "fonte": QUAEST_OUT, "nota": "A pesquisa junta quem anulou e quem não votou no 1º turno."},
        # Como na conta completa (/apuracao/detalhe, "Compareceram a mais"): quem
        # faltou no 1º turno entra só pelo SALDO do comparecimento, que é dado do
        # TSE, não escolha. O resto de quem faltou fica fora nos dois turnos.
        {"id": "abst1", "nome": "Foi votar só no 2º turno", "v": n["comp2"] - n["comp1"], "fam": "fora",
         "dica": {"lula": 43 / 81, "flavio": 38 / 81, "nenhum": 0.0}, "fonte": QUAEST_OUT},
        {"id": "fora2", "nome": "Faltou nos dois turnos", "v": eleitores1 - n["comp2"], "fam": "fixo",
         "dica": {"lula": 0.0, "flavio": 0.0, "nenhum": 1.0}},
    ]
    return g, eleitores1


def alvo(conta, eleitores):
    n = conta["nacional"]
    return {"lula": n["lula2"], "flavio": n["flavio2"], "nenhum": eleitores - n["lula2"] - n["flavio2"]}


def ipf(fs, semente, alvo_, voltas=5000):
    """Linhas = grupos (somam v), colunas = destinos (somam alvo_)."""
    m = [[max(semente[f["id"]][k], 1e-4) * f["v"] for k in DEST] for f in fs]
    tot = sum(f["v"] for f in fs)
    ta = sum(max(0, alvo_[k]) for k in DEST)
    A = [max(0, alvo_[k]) * tot / ta for k in DEST]
    for _ in range(voltas):
        for j in range(3):
            sc = sum(l[j] for l in m)
            if sc > 0:
                for l in m:
                    l[j] *= A[j] / sc
        desvio = 0
        for i, l in enumerate(m):
            sl = sum(l)
            desvio += abs(sl - fs[i]["v"])
            for j in range(3):
                l[j] *= fs[i]["v"] / sl
        if desvio < 1:
            break
    return {f["id"]: {k: m[i][j] / f["v"] for j, k in enumerate(DEST)} for i, f in enumerate(fs)}


def fechar(gs, fixos, semente, alvo_):
    """Fixa os grupos de `fixos` ({id: fatia}) e ajusta o resto partindo de `semente`."""
    resto = dict(alvo_)
    for f in gs:
        if f["id"] in fixos:
            for k in DEST:
                resto[k] -= fixos[f["id"]][k] * f["v"]
    livres = [f for f in gs if f["id"] not in fixos]
    if min(resto.values()) < 0:
        raise ValueError(f"cenário impossível: {resto}")
    out = dict(fixos)
    out.update(ipf(livres, semente, resto))
    return out


def resultado(gs, fatia):
    S = {k: sum(fatia[f["id"]][k] * f["v"] for f in gs) for k in DEST}
    S["pct_lula"] = 100 * S["lula"] / (S["lula"] + S["flavio"])
    return S


def main():
    conta = json.loads((ARQ / "conta.json").read_text())
    gs, eleitores = grupos(conta)
    A = alvo(conta, eleitores)
    n = conta["nacional"]
    fica = lambda k: {d: 1.0 if d == k else 0.0 for d in DEST}

    # O "chute da pesquisa": finalistas mantêm, cada grupo como a Quaest disse,
    # e quem não foi votar no 1º turno vota no 2º só no saldo do comparecimento
    # (com a dica de quem não votou ou anulou).
    dica_bn = next(f for f in gs if f["id"] == "bn1")["dica"]
    for f in gs:
        f["opinioes"] = OPINIOES[f["id"]]
        if f["id"] in FOTO:
            f["foto"] = {"src": "/static/fotos/" + FOTO[f["id"]] + ".jpg", **FOTOS[FOTO[f["id"]]]}
        else:
            f["icone"] = ICONE[f["id"]]
        if f["id"] in APOIO:
            f["apoio"] = {"txt": APOIO[f["id"]][0], "cor": APOIO[f["id"]][1]}
    pesquisa = {f["id"]: (fica(f["id"].replace("1", "")) if f["fam"] == "finalistas"
                          else {k: f["dica"][k] for k in DEST}) for f in gs}
    pesquisa["lula1"], pesquisa["flavio1"] = fica("lula"), fica("flavio")

    # Cenários EXTREMOS e redondos (30/10/2026): cada um põe um grupo inteiro
    # num lado ("todo branco/nulo virou Lula") e o resto se divide por igual,
    # na mesma proporção em todo grupo do "resto", na conta exata para fechar
    # com o TSE. Não são estimativa: servem para mostrar o tamanho da virada.
    fora = {"fora2": fica("nenhum")}   # quem faltou nos dois turnos não é escolha
    TERC = [f["id"] for f in gs if f["fam"] == "terceira"]
    V = {f["id"]: f["v"] for f in gs}
    br = lambda x, c=1: f"{x / 1e6:.{c}f}".replace(".", ",")
    pct = lambda x: f"{100 * x:.0f}%"

    def extremo(fixos, resto, eq=False):
        """Fixa `fixos` e divide `resto` por igual (mesma fatia em cada grupo) para fechar com o TSE."""
        fx = {**fora, **fixos}
        L = A["lula"] - sum(fx[i]["lula"] * V[i] for i in fx)
        F = A["flavio"] - sum(fx[i]["flavio"] * V[i] for i in fx)
        P = sum(V[i] for i in resto)
        sl, sf = L / P, F / P
        if min(sl, sf, 1 - sl - sf) < -1e-9:
            raise ValueError(f"extremo impossível: {sl:.3f} {sf:.3f}")
        out = dict(fx)
        for i in resto:
            out[i] = {"lula": sl, "flavio": sf, "nenhum": 1 - sl - sf}
        return out, sl, sf

    mant = {"lula1": fica("lula"), "flavio1": fica("flavio")}
    cen = []
    # 1. Todo branco/nulo do 1º turno foi para o Lula.
    f1, sl, sf = extremo({**mant, "bn1": fica("lula")}, TERC + ["abst1"])
    cen.append({"id": "bn-lula", "titulo": "Todo branco e nulo do 1º turno virou Lula", "tudo": ["bn1"], "fatia": f1,
                "resumo": f"Os {br(V['bn1'])} mi que votaram branco ou nulo no 1º turno foram todos de Lula. Ainda assim faltam {br(A['lula'] - V['lula1'] - V['bn1'])} mi: "
                          f"a terceira via e quem só votou no 2º turno teriam de dar {pct(sl)} ao Lula e {pct(sf)} ao Flávio."})
    # 2. Todo mundo que só votou no 2º turno foi de Lula.
    f2, sl, sf = extremo({**mant, "abst1": fica("lula")}, TERC + ["bn1"])
    cen.append({"id": "novos-lula", "titulo": "Todo mundo que só votou no 2º turno foi de Lula", "tudo": ["abst1"], "fatia": f2,
                "resumo": f"Os {br(V['abst1'])} mi a mais do 2º turno, todos no Lula. Não chega nem perto: faltam {br(A['lula'] - V['lula1'] - V['abst1'])} mi, "
                          f"e a terceira via e o branco/nulo teriam de dar {pct(sl)} ao Lula e {pct(sf)} ao Flávio."})
    # 3. A terceira via inteira virou Lula.
    f3, sl, sf = extremo({**mant, **{i: fica("lula") for i in TERC}}, ["bn1", "abst1"])
    vt = sum(V[i] for i in TERC)
    cen.append({"id": "terceira-lula", "titulo": "A terceira via inteira virou Lula", "tudo": TERC, "fatia": f3,
                "resumo": f"Os {br(vt)} mi de Cury, Renan, Caiado, Zema e outros, todos no Lula, mesmo com o Flávio apoiado por quatro deles. "
                          f"Aí o resto quase não precisa ajudar o Lula: {pct(sl)} do branco/nulo e de quem só votou no 2º turno, contra {pct(sf)} para o Flávio."})
    # 4. Só a virada: parte do eleitor do Flávio troca de lado e todo o resto se divide meio a meio.
    x = ((A["lula"] - A["flavio"]) - (V["lula1"] - V["flavio1"])) / 2
    resto4 = TERC + ["bn1", "abst1"]
    e = A["lula"] - V["lula1"] - x
    P4 = sum(V[i] for i in resto4)
    f4 = {**fora, "lula1": fica("lula"), "flavio1": {"lula": x / V["flavio1"], "flavio": 1 - x / V["flavio1"], "nenhum": 0.0}}
    for i in resto4:
        f4[i] = {"lula": e / P4, "flavio": e / P4, "nenhum": 1 - 2 * e / P4}
    cen.append({"id": "virada", "titulo": f"{round(100 * x / V['flavio1'])} em cada 100 eleitores do Flávio viraram Lula", "tudo": ["flavio1"], "fatia": f4,
                "resumo": f"{br(x)} mi trocaram de lado e todo o resto se dividiu meio a meio ({pct(e / P4)} para cada um). "
                          "É a virada sem nenhuma ajuda de fora."})
    # 5. Sem extremo: todo grupo de fora dos dois finalistas votou igual.
    f5, sl, sf = extremo(mant, TERC + ["bn1", "abst1"])
    cen.append({"id": "todos-igual", "titulo": "Todo eleitor de fora dos dois votou igual", "tudo": [], "fatia": f5,
                "resumo": f"Cada grupo que não votou em Lula nem Flávio no 1º turno deu {pct(sl)} ao Lula e {pct(sf)} ao Flávio. "
                          f"É o tamanho da virada: quase {sl / sf:.0f} votos para o Lula a cada 1 do Flávio."})

    for c in cen:
        c["resultado"] = resultado(gs, c["fatia"])
    saida = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "eleitorado": eleitores,
        "alvo": A,
        "tse": {"lula": n["lula2"], "flavio": n["flavio2"], "pct_lula": 100 * n["lula2"] / (n["lula2"] + n["flavio2"])},
        "grupos": gs,
        "pesquisa": {"fatia": pesquisa, "resultado": resultado(gs, pesquisa)},
        "cenarios": cen,
        "fontes": [QUAEST_OUT, QUAEST_SET, ATLAS_OUT, DATAFOLHA_SET, APOIOS, APOIOS_OUTROS],
    }
    (ARQ / "chute.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1))
    print("pesquisa:", {k: round(v / 1e6, 2) if k != "pct_lula" else round(v, 2) for k, v in saida["pesquisa"]["resultado"].items()})
    for c in cen:
        print(c["id"], {k: round(v / 1e6, 3) if k != "pct_lula" else round(v, 2) for k, v in c["resultado"].items()})
        for f in gs:
            x = c["fatia"][f["id"]]
            print(f"   {f['id']:8s} L {100*x['lula']:5.1f}  F {100*x['flavio']:5.1f}  N {100*x['nenhum']:5.1f}")


if __name__ == "__main__":
    main()
