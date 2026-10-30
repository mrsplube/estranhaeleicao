"""Quem já está MATEMATICAMENTE eleito — ou fora — com a apuração parcial.

"Entra na projeção" diz o que acontece se a apuração parasse agora. Isto diz o
que já não muda mais, seja qual for o voto que falta. O que falta tem um teto
conhecido: os eleitores das seções ainda não totalizadas (todos votando, todos
válidos) mais os votos anulados sub judice, que ainda podem virar válidos.

**Eleito garantido** — o PIOR caso: todo o voto que falta vai contra ele.
Duas coisas têm de valer ao mesmo tempo, e cada uma é conferida como se o
adversário tivesse o voto restante inteiro para ela (a realidade é mais fácil
que isso, então a conta é conservadora):

1. A agremiação tem cadeiras garantidas suficientes. Pelo QP: `votos ÷ QE`
   com o maior QE possível, limitado a quem tem 10% dele. Pelas sobras: nenhum
   rival consegue ocupar mais que `vagas − s` lugares antes da s-ésima média
   dela — cada rival leva no máximo `votos ÷ QE` cadeiras pelo QP ou
   `votos × s ÷ V` pela média, o que for maior (conta de cima, sem os pisos);
   e ela precisa continuar disputando a 2ª fase (80% do QE, candidatos com 20%).
2. O candidato não pode ser empurrado para fora da lista: quantos colegas
   abaixo dele conseguem ultrapassá-lo, gastando o voto restante do jeito mais
   barato (a menor diferença primeiro).

**Fora garantido** — o MELHOR caso: todo o voto que falta vai para ele (o que
também soma na agremiação). Se nem assim ele entra, não entra mais. É
monótono dentro da lista — se um candidato não alcança, o de menos votos
também não —, então cada lista se resolve por busca binária.

Com a apuração encerrada (nada restante) as duas respostas são o próprio
resultado. A garantia de cadeira pela 3ª fase não é certificada: ali qualquer
lista concorre, e a conta conservadora não fecha.
"""
from __future__ import annotations

from politicos.eleicao import distribuir, quociente_eleitoral

ELEITO_QP = "eleito-qp"
ELEITO_SOBRAS = "eleito-sobras"
FORA = "fora"


def _cadeiras_garantidas(V: int, W: int, vagas: int, qe_min: int, qe_max: int,
                         lista: list[int]) -> tuple[int, int]:
    """(garantidas pelo QP, garantidas no total) para uma agremiação com V votos,
    contra W votos dos rivais (já com o restante inteiro somado a eles)."""
    if V <= 0 or qe_max <= 0:
        return 0, 0
    c10 = sum(1 for v in lista if v >= 0.10 * qe_max)
    c20 = sum(1 for v in lista if v >= 0.20 * qe_max)
    s_qp = min(V // qe_max, c10)
    s_media = 0
    if V >= 0.8 * qe_max:
        for s in range(1, vagas + 1):
            if W * max(1 / qe_min, s / V) < vagas - s + 1:
                s_media = s
            else:
                break
        s_media = min(s_media, c20)
    return s_qp, max(s_qp, s_media)


def _ultrapassagens(v: int, abaixo: list[int], restante: int) -> int:
    """Quantos colegas abaixo conseguem passar à frente com `restante` votos."""
    gasto = n = 0
    for falta in sorted(max(1, v - x + 1) for x in abaixo):
        if gasto + falta > restante:
            break
        gasto += falta
        n += 1
    return n


def _entra_no_melhor_caso(votos: dict[str, int], listas: dict[str, list[tuple[int, str]]],
                          agr: str, idx: int, vagas: int, validos: int, restante: int) -> bool:
    """Dando todo o restante ao candidato `idx` da lista `agr`, ele entra?"""
    v_novo = votos.copy()
    v_novo[agr] += restante
    meus = [v for v, _ in listas[agr]]
    alvo = meus[idx] + restante
    candidatos = {l: [v for v, _ in lst] for l, lst in listas.items()}
    candidatos[agr] = meus[:idx] + [alvo] + meus[idx + 1:]
    r = distribuir(v_novo, vagas, candidatos=candidatos, validos=validos + restante)
    cadeiras = r["cadeiras"].get(agr, 0)
    # Posição no melhor caso: empate a favor dele (é o caso mais generoso).
    acima = sum(1 for j, v in enumerate(candidatos[agr]) if j != idx and v > alvo)
    return acima < cadeiras


def situacoes(votos: dict[str, int], listas: dict[str, list[tuple[int, str]]],
              vagas: int, validos: int, restante: int,
              eleitos_agora: set[str]) -> dict[str, str]:
    """{id do candidato: ELEITO_QP | ELEITO_SOBRAS | FORA}; quem não está aqui
    ainda depende do voto que falta.

    `listas` é {agremiação: [(votos, id)]} já na ordem da lista (mais votado
    primeiro), só com quem pode ser eleito. `eleitos_agora` são os que a
    projeção atual põe nas cadeiras.
    """
    saida: dict[str, str] = {}
    if validos <= 0 or vagas <= 0:
        return saida
    if restante <= 0:
        for lst in listas.values():
            for _, cid in lst:
                saida[cid] = ELEITO_QP if cid in eleitos_agora else FORA
        return saida

    qe_min = quociente_eleitoral(validos, vagas)
    qe_max = quociente_eleitoral(validos + restante, vagas)
    for agr, lst in listas.items():
        V = votos.get(agr, 0)
        lista = [v for v, _ in lst]
        s_qp, s_total = _cadeiras_garantidas(V, validos - V + restante, vagas,
                                             qe_min, qe_max, lista)
        for k, (v, cid) in enumerate(lst, 1):
            if k > s_total:
                break
            pior = k + _ultrapassagens(v, lista[k:], restante)
            if pior <= s_qp and v >= 0.10 * qe_max:
                saida[cid] = ELEITO_QP
            elif pior <= s_total and v >= 0.20 * qe_max:
                saida[cid] = ELEITO_SOBRAS

        # Fora: só quem a projeção de agora deixa de fora; busca binária do
        # primeiro que não alcança nem no melhor caso.
        fora_idx = [i for i, (_, cid) in enumerate(lst) if cid not in eleitos_agora]
        if not fora_idx:
            continue
        if _entra_no_melhor_caso(votos, listas, agr, fora_idx[-1], vagas, validos, restante):
            continue                      # nem o último está fora: ninguém está
        lo, hi = 0, len(fora_idx) - 1     # hi já é "fora"
        while lo < hi:
            meio = (lo + hi) // 2
            if _entra_no_melhor_caso(votos, listas, agr, fora_idx[meio], vagas, validos, restante):
                lo = meio + 1
            else:
                hi = meio
        for i in fora_idx[lo:]:
            saida[lst[i][1]] = FORA
    return saida


def restante_de(arquivo: dict) -> int:
    """O teto do voto que ainda pode entrar: eleitores das seções não
    totalizadas mais os anulados sub judice."""
    e, v, s = arquivo.get("e") or {}, arquivo.get("v") or {}, arquivo.get("s") or {}

    def i(x):
        try:
            return int(x or 0)
        except (TypeError, ValueError):
            return 0

    te, est, esnt = i(e.get("te")), i(e.get("est")), i(e.get("esnt"))
    # Conferido em 04/10 antes do primeiro voto: est + esnt = te. Mesmo assim a
    # conta não confia num campo só — se eles não fecharem, ou se o TSE disser
    # que falta seção e nenhum eleitor, o teto vira o eleitorado inteiro e
    # ninguém é declarado garantido. Errar aqui seria dizer "garantido" à toa.
    restante = max(esnt, te - est)
    pst = str(s.get("pst") or "0").replace(",", ".")
    try:
        incompleta = float(pst) < 100.0
    except ValueError:
        incompleta = True
    if te and (est + esnt != te or (incompleta and restante == 0)):
        restante = te
    return restante + i(v.get("vansj"))
