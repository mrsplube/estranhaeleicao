"""Simulador de cenários do 2º turno — os eixos que a pessoa pode mover.

A pergunta que ele serve: *o que teria acontecido se os votos tivessem vindo de
outro lugar?* A tentação é fazer um slider para cada candidato da terceira via
("o Zema deu 80% ao Flavio, o Cury 30%..."). Isso NÃO funciona:

**Por que não dá um slider por candidato.** O universo de votos que entrou no
2º turno é a soma de duas fontes:

    votos válidos novos (4.781.485)  +  terceira via (9.316.747)  =  14.098.232

Esses 14,1 milhões se dividem entre DOIS destinos. Com 16 incógnitas (cada
candidato da 3ª via, cada origem do voto novo) e uma única equação, todo
conjunto de sliders por candidato teria 1 grau de liberdade REAL: quem mexe num
número tem de devolver o voto para outro, e o dado não diz para quem. Um
controle que parece ter 14 sliders livres é a receita para achar o número que
se quer achar.

**O que funciona: 3 eixos independentes.** Eles são os que o dado sustenta, e
cada um tem um efeito próprio no resultado:

1. `novos_lula` — a fatia dos votos válidos NOVOS que foi para o Lula. É a
   menor alavanca: são 4,78 mi.
2. `terceira_lula` — a fatia da TERCEIRA VIA que foi para o Lula. É a maior
   alavanca: são 9,32 mi, quase o dobro.
3. `troca` — votos que migraram diretamente do Flavio para o Lula. Aqui o
   universo cresce: é voto que já era do Flavio e mudou de lado.

O que vai para o Flavio é sempre o que sobra — nunca um slider. Assim cada
cenário fecha por construção, e a tela pode mostrar o placar final de cada um.

Os votos novos têm três origens EXATAS (identidade contábil, não estimativa), e
a tela mostra a decomposição para a pessoa ver o que está movendo:

    abstenção que voltou 2.960.239 + branco 870.302 + nulo 950.944 = 4.781.485

**O cenário real é o ponto de partida:** 100% dos novos para o Lula, 60,06% da
terceira via para o Lula e 0 de troca. É o único que reproduz os números do
TSE, e a tela marca isso.
"""
from __future__ import annotations

import json
from pathlib import Path

from apuracao import contas


def _ler(base: Path) -> dict:
    return json.loads((base / "conta.json").read_text(encoding="utf-8"))


def variaveis(res: dict) -> dict:
    """Os totais fixos e os limites dos três eixos."""
    n = res.get("nacional") or {}
    novos = res.get("novos_validos") or 0
    terc = res.get("terceira_via") or 0
    gl = res.get("ganho_lula") or 0
    gf = res.get("ganho_flavio") or 0
    # As identidades vêm de `apuracao.contas`, que é o único lugar onde elas
    # moram. Antes esta função recalculava tudo por conta própria, e era assim
    # que os módulos podiam divergir.
    ref = contas.totais({"nacional": {"t1": {"lula": n.get("lula1"), "flavio": n.get("flavio1"),
                                            "validos": n.get("validos1"), "comp": n.get("comp1"),
                                            "brancos": n.get("brancos1"), "nulos": n.get("nulos1")},
                                      "t2": {"lula": n.get("lula2"), "flavio": n.get("flavio2"),
                                            "validos": n.get("validos2"), "comp": n.get("comp2"),
                                            "brancos": n.get("brancos2"), "nulos": n.get("nulos2")}}})
    origens = ref["novos_origens"]
    piso = contas.piso_terceira(ref)
    q_real = piso["fracao"]
    # Teto da troca: o ganho do Flavio. Ele terminou com MAIS votos que no 1º
    # turno; falar em "perder" mais do que isso não tem lastro nos números.
    c_max = max(0, min(gf, n.get("flavio1") or gf))
    return {
        "novos": novos, "terceira": terc,
        "ganho_lula": gl, "ganho_flavio": gf,
        "flavio1": n.get("flavio1") or 0, "lula1": n.get("lula1") or 0,
        "lula2": n.get("lula2") or 0, "flavio2": n.get("flavio2") or 0,
        "novos_origens": dict(origens),
        "c_max": c_max,
        "real": {"novos_lula": 100.0, "terceira_lula": 100 * q_real, "troca": 0},
        "universo": novos + terc,
    }


def calcular(res: dict, p: float, q: float, c: float) -> dict:
    """O cenário com os três eixos dados (% e votos). O resto é o que sobra."""
    v = variaveis(res)
    novos, terc = v["novos"], v["terceira"]
    p = min(1.0, max(0.0, float(p) / 100))
    q = min(1.0, max(0.0, float(q) / 100))
    c = max(0.0, min(float(v["c_max"]), float(c)))

    lula_novos, lula_terc = p * novos, q * terc
    lula_total = lula_novos + lula_terc + c
    flavio_novos, flavio_terc = (1 - p) * novos, (1 - q) * terc
    flavio_total = flavio_novos + flavio_terc - c

    lula_fim = v["lula1"] + lula_total
    flavio_fim = v["flavio1"] + flavio_total
    tot = lula_fim + flavio_fim
    margem = lula_fim - flavio_fim
    # Compara com o resultado que de fato aconteceu.
    real = res.get("nacional") or {}
    margem_real = (real.get("lula2") or 0) - (real.get("flavio2") or 0)
    return {
        "novos_lula_pct": round(100 * p, 1), "terceira_lula_pct": round(100 * q, 1),
        "troca": round(c),
        "novos_lula": round(lula_novos), "novos_flavio": round(flavio_novos),
        "terc_lula": round(lula_terc), "terc_flavio": round(flavio_terc),
        "lula_total": round(lula_total), "flavio_total": round(flavio_total),
        "lula_fim": round(lula_fim), "flavio_fim": round(flavio_fim),
        "lula_pct": round(100 * lula_fim / tot, 2) if tot else 0.0,
        "flavio_pct": round(100 * flavio_fim / tot, 2) if tot else 0.0,
        "margem": round(margem),
        "vencedor": "LULA" if margem > 0 else "FLAVIO" if margem < 0 else "EMPATE",
        # É o cenário real? (tolerância de 1 voto por arredondamento)
        "e_real": abs((margem) - margem_real) <= 2,
        "dif_margem": round(margem - margem_real),
    }


def mover(res: dict, eixo: str, valor: float) -> dict:
    """O cenário com UM eixo no valor dado e os outros como estão no real.

    É o que a tela usa: cada slider é independente (o usuário pode mexer em
    um e ver o efeito isolado daquele eixo), e o servidor não tenta adivinhar
    os outros. Quem quiser combinar, mexe nos três.
    """
    v = variaveis(res)
    p = v["real"]["novos_lula"]
    q = v["real"]["terceira_lula"]
    c = v["real"]["troca"]
    if eixo == "novos_lula":
        p = min(100.0, max(0.0, float(valor)))
    elif eixo == "terceira_lula":
        q = min(100.0, max(0.0, float(valor)))
    elif eixo == "troca":
        c = max(0.0, float(valor))
    else:
        raise ValueError(f"eixo desconhecido: {eixo}")
    return calcular(res, p, q, c)


def fronteira(res: dict, passos: int = 11) -> dict:
    """A curva de vitória: para cada fatia do voto novo, o mínimo da 3ª via.

    É o que transforma o slider em mapa: a pessoa vê onde fica a linha em que o
    resultado vira, e onde o ponto real está em relação a ela. Como o voto novo
    é a menor alavanca (4,78 mi contra 9,32 mi), a curva é bem inclinada — e o
    ponto real fica MUITO longe dela.
    """
    v = variaveis(res)
    pontos = []
    for i in range(passos):
        p = 100 * i / (passos - 1)
        lo, hi = 0.0, 1.0
        # busca binária: menor q que faz o Lula vencer com este p e c=0
        if calcular(res, p, 100.0, 0)["margem"] <= 0:
            pontos.append({"p": round(p, 1), "q_min": None})
            continue
        if calcular(res, p, 0.0, 0)["margem"] > 0:
            pontos.append({"p": round(p, 1), "q_min": 0.0})
            continue
        for _ in range(50):
            mid = (lo + hi) / 2
            if calcular(res, p, 100 * mid, 0)["margem"] > 0:
                hi = mid
            else:
                lo = mid
        pontos.append({"p": round(p, 1), "q_min": round(100 * hi, 2)})
    return {"pontos": pontos,
            "real": {"p": 100.0, "q": round(v["real"]["terceira_lula"], 2)}}


def dados(base: Path) -> dict:
    """Os dados do simulador (usado pelo `conta.json`)."""
    res = _ler(base)
    v = variaveis(res)
    inicial = calcular(res, v["real"]["novos_lula"], v["real"]["terceira_lula"],
                       v["real"]["troca"])
    return {"ok": True, "variaveis": v, "inicial": inicial, "fronteira": fronteira(res)}


def gerar(base: Path) -> dict:
    """Grava `simulador.json` (arquivo próprio, para quem quiser isolado)."""
    saida = dados(base)
    destino = base / "simulador.json"
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(destino)
    return saida
