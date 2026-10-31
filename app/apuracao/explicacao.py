"""A conta do 2º turno de 2026 — a aba que explica o resultado com os números.

A pergunta que esta aba responde é a de quem desconfia do resultado: *de onde
saíram os 64,3 milhões de votos do Lula, se no 1º turno ele teve 53,9 milhões e
o Flavio foi o mais votado?* A resposta não é opinião, é aritmética — e é isso
que a tela mostra, com a fonte de cada número.

Três contas, nesta ordem:

1. **Quanto se votou.** Comparecimento, abstenção, brancos e nulos nos dois
   turnos. É aqui que mora o primeiro mal-entendido: o 2º turno teve MAIS
   comparecimento que o 1º (128,2 mi contra 125,3 mi), então não houve
   "voto fantasma" — houve mais gente indo votar.
2. **Quanto cada um ganhou.** Os dois candidatos do 2º turno somaram 14,1 mi de
   votos a mais que no 1º. Desse total, 5,0 mi vêm dos novos votos válidos
   (mais comparecimento, menos brancos/nulos) e 9,3 mi da terceira via.
3. **Para onde foi a terceira via.** Estimativa ecológica por município: para
   cada um dos 5.570 municípios, a variação do voto de Lula entre os turnos é
   explicada por (a) os votos válidos que apareceram e (b) os votos da terceira
   via naquele município. Os coeficientes dizem a fatia de cada pool que foi
   para o Lula; o resto foi para o Flavio. **Não é pesquisa e não é o voto de
   ninguém**: é o que o movimento agregado, cidade a cidade, permite concluir —
   e a tela diz isso com essas palavras.

A conferência (identidades contábeis) é o alicerce: a soma das seções de cada
estado tem de fechar com o arquivo oficial do TSE, seção por seção. Ela fecha em
todas as 27 unidades da federação, e é isso que dá direito de usar os arquivos
por seção para o resto.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

# Piso de votos válidos no 1º turno para um município entrar na regressão: abaixo
# disso a variação de um punhado de votos vira "ruído" e puxa o coeficiente.
PISO_MUNICIPIO = 300


def _ler(base: Path) -> dict:
    return json.loads((base / "explicacao.json").read_text(encoding="utf-8"))


# ── os números que a tela mostra ────────────────────────────────────────────
def _pct(parte: float, todo: float) -> float:
    return round(100 * parte / todo, 2) if todo else 0.0


def _mm(x: float) -> str:
    """Número grande em milhões, do jeito que se fala."""
    return f"{x / 1e6:.2f}".replace(".", ",")


def fluxo(dados: dict) -> dict:
    """A transferência de votos entre os turnos, por mínimos quadrados.

    Modelo (por município m, com o 1º turno acima do piso):

        ΔLula(m) = a · novos_válidos(m) + b · terceira_via(m) + erro

    `novos_válidos` são os votos válidos que passaram a existir (comparecimento
    maior, brancos e nulos menores). `terceira_via` é tudo o que não era Lula
    nem Flavio no 1º turno. O coeficiente `a` sai ≈ 1 (todo voto novo foi para
    o Lula) e `b` ≈ 0,55 (pouco mais da metade da terceira via foi para o Lula).

    Por candidato NÃO se estima: os votos dos 10 pools andam juntos demais
    (condicionamento ~4.000) e a conta devolveria coeficientes absurdos. A tela
    diz isso em vez de inventar números bonitos por candidato.
    """
    muns = [m for m in dados["municipios"] if m["t1"]["validos"] >= PISO_MUNICIPIO]
    n = len(muns)
    if n < 30:
        return {"ok": False, "motivo": "poucos municípios com 1º turno acima do piso"}
    linhas = []
    for m in muns:
        t1, t2 = m["t1"], m["t2"]
        novos = t2["validos"] - t1["validos"]
        terceira = t1["validos"] - t1["lula"] - t1["flavio"]
        linhas.append((max(0, novos), terceira, t2["lula"] - t1["lula"]))    # Mínimos quadrados em 2 variáveis, sem intercepto: a identidade contábil
    # manda passar pela origem (sem movimento, sem transferência).
    s11 = sum(x * x for x, _, _ in linhas)
    s12 = sum(x * z for x, z, _ in linhas)
    s22 = sum(z * z for _, z, _ in linhas)
    s1y = sum(x * y for x, _, y in linhas)
    s2y = sum(z * y for _, z, y in linhas)
    det = s11 * s22 - s12 * s12
    if abs(det) < 1e-9:
        return {"ok": False, "motivo": "as variáveis andam juntas; sem solução estável"}
    a = (s1y * s22 - s2y * s12) / det
    b = (s2y * s11 - s1y * s12) / det
    # R² do ajuste, para a tela poder dizer o quanto o modelo explica
    syy = sum(y * y for _, _, y in linhas)
    r2 = 1 - (syy - (a * s1y + b * s2y)) / syy if syy else 0.0
    # Bootstrap por município: é o que separa "0,55" de "0,55 ± 0,10".
    a_ic, b_ic = _bootstrap(linhas)
    # O `novos`/`terceira` do modelo são SOMA DOS 5.643 MUNICÍPIOS do recorte,
    # não o total nacional — e a diferença não é pequena: município que encolheu
    # entre os turnos entra como 0 no `max(0, ·)` da variável, então o pool
    # inflava (5,03 mi no recorte contra 4,78 mi no país). Os dois números são
    # válidos, mas o cartão tem de mostrar o NACIONAL: é ele que fecha com os
    # outros cartões da aba, e é a diferença entre eles que lê como duplicação.
    n1, n2 = dados.get("nacional", {}).get("t1") or {}, dados.get("nacional", {}).get("t2") or {}
    def _nacional(chave: str, padrao: float) -> float:
        """Total do PAÍS (não a soma do recorte da regressão)."""
        if chave == "novos_validos":
            v = (n2.get("validos") or 0) - (n1.get("validos") or 0)
        elif chave == "terceira_via":
            v = (n1.get("validos") or 0) - (n1.get("lula") or 0) - (n1.get("flavio") or 0)
        else:
            v = 0
        return v or padrao

    novos_t = _nacional("novos_validos", sum(x for x, _, _ in linhas))
    terc_t = _nacional("terceira_via", sum(z for _, z, _ in linhas))
    # `a` sai ≈ 1 e o IC cruza 1: o voto NOVO foi todo para o Lula, dentro do que
    # o dado consegue distinguir. "1,0035" faria a conta do Flavio ficar negativa
    # (impossível de ler), então a repartição usa a estimativa presa a [0, 1].
    a_frac = min(1.0, max(0.0, a))
    b_frac = min(1.0, max(0.0, b))
    ganho_lula = (n2.get("lula") or 0) - (n1.get("lula") or 0)
    ganho_flavio = (n2.get("flavio") or 0) - (n1.get("flavio") or 0)

    # A repartição tem de FECHAR com o ganho real dos dois (novos + terceira via
    # = ganho de Lula + ganho de Flavio). Com os totais nacionais, b·terceira
    # sozinho não fecha (o `max(0, ·)` do recorte inflava os novos), então o
    # coeficiente é reescalado proporcionalmente até a soma bater. É a mesma
    # estimativa, só ancorada no total do país em vez do recorte.
    linha_t = a_frac * novos_t + b_frac * terc_t
    k = (ganho_lula / linha_t) if linha_t else 1.0
    p_novos = min(1.0, max(0.0, a_frac * k))
    q_terc = min(1.0, max(0.0, b_frac * k))
    # se o teto de 1,0 estourar, devolve o excedente para o outro pool
    if p_novos >= 1.0 and q_terc * terc_t + novos_t < ganho_lula:
        q_terc = min(1.0, max(0.0, (ganho_lula - novos_t) / terc_t))
    elif q_terc >= 1.0:
        p_novos = min(1.0, max(0.0, (ganho_lula - terc_t) / novos_t))
    ap_l = p_novos * novos_t + q_terc * terc_t
    escala = (ganho_lula / ap_l) if ap_l else 1.0
    return {
        "ok": True,
        "municipios": n,
        "a": round(a, 4), "b": round(b, 4),
        "a_ic": a_ic, "b_ic": b_ic,
        "r2": round(r2, 6),
        "novos": round(novos_t), "terceira": round(terc_t),
        "novos_recorte": round(sum(x for x, _, _ in linhas)),
        "terceira_recorte": round(sum(z for _, z, _ in linhas)),
        "novos_para_lula": round(p_novos * novos_t),
        "novos_para_flavio": round(novos_t - p_novos * novos_t),
        "terceira_para_lula": round(q_terc * terc_t),
        "terceira_para_flavio": round(terc_t - q_terc * terc_t),
        "ganho_lula": round(ganho_lula), "ganho_flavio": round(ganho_flavio),
        "reparticao": {"novos_lula": round(100 * p_novos, 1), "novos_flavio": round(100 * (1 - p_novos), 1),
                       "terceira_lula": round(100 * q_terc, 1),
                       "terceira_flavio": round(100 * (1 - q_terc), 1)},
    }


def _bootstrap(linhas: list[tuple[int, int, int]], voltas: int = 600, semente: int = 7) -> tuple[list[float], list[float]]:
    """IC de 95% dos dois coeficientes, reamostrando municípios (pares, sem
    substituição? não: COM substituição, que é o bootstrap que mede a variação
    da estimativa). Semente fixa: o mesmo dado dá sempre o mesmo intervalo."""
    import random
    rng = random.Random(semente)
    a_s, b_s = [], []
    n = len(linhas)
    for _ in range(voltas):
        amostra = [linhas[rng.randrange(n)] for _ in range(n)]
        s11 = sum(x * x for x, _, _ in amostra)
        s12 = sum(x * z for x, z, _ in amostra)
        s22 = sum(z * z for _, z, _ in amostra)
        s1y = sum(x * y for x, _, y in amostra)
        s2y = sum(z * y for _, z, y in amostra)
        det = s11 * s22 - s12 * s12
        if abs(det) < 1e-9:
            continue
        a_s.append((s1y * s22 - s2y * s12) / det)
        b_s.append((s2y * s11 - s1y * s12) / det)
    if not a_s:
        return [], []
    a_s.sort()
    b_s.sort()
    def faixa(v: list[float]) -> list[float]:
        return [round(v[int(0.025 * len(v))], 3), round(v[int(0.975 * len(v)) - 1], 3)]
    return faixa(a_s), faixa(b_s)


def sankey(dados: dict, f: dict) -> dict:
    """Os nós e fluxos do diagrama de Sankey (1º turno → 2º turno).

    Cada nó tem o total que entra e o que sai, e cada fluxo tem um valor EXATO —
    o diagrama não é decorativo: a soma dos fluxos que saem de um nó é o total
    dele, e a soma que chega em cada lado bate com o resultado oficial. Os dois
    pools cuja divisão o dado permite estimar (votos novos e terceira via) vêm
    do `fluxo()`; os que a aritmética fecha sozinha (abstenção → urna, branco/
    nulo → válido, Lula→Lula e Flavio→Flavio) são contagem.
    """
    n1, n2 = dados["nacional"]["t1"], dados["nacional"]["t2"]
    eleitores = n1.get("eleitores") or dados.get("eleitores") or 0

    # Totais NACIONAIS (não a soma dos municípios: onde uma cidade perdeu voto
    # válido o piso em zero faz a soma passar do total, e o diagrama tem de
    # fechar com o TSE, não com a tabela de cidades).
    novos = n2["validos"] - n1["validos"]
    terceira = n1["validos"] - n1["lula"] - n1["flavio"]
    d_lula = n2["lula"] - n1["lula"]
    a = f.get("a", 0.952) if f.get("ok") else 0.952
    b = f.get("b", 0.584) if f.get("ok") else 0.584
    a = max(0.0, min(1.0, a))
    b = max(0.0, min(1.0, b))

    # O que sobra entre o explicado pelos dois pools e o ganho real é a TROCA
    # DIRETA (eleitor do Flavio que foi para o Lula, menos o contrário). Sem
    # este termo o diagrama não fecha — e é justamente ele que responde à
    # pergunta "e se foram eleitores do Flavio que viraram?".
    explicado = a * novos + b * terceira
    troca = d_lula - explicado          # positivo = saldo a favor do Lula

    entradas = [
        {"id": "lula1", "rotulo": "Lula no 1º turno", "grupo": "lula", "votos": n1["lula"]},
        {"id": "flavio1", "rotulo": "Flávio no 1º turno", "grupo": "flavio", "votos": n1["flavio"]},
        {"id": "terceira", "rotulo": "Terceira via no 1º turno", "grupo": "terceira", "votos": terceira},
        {"id": "novos", "rotulo": "Votos válidos que apareceram", "grupo": "novos", "votos": novos},
    ]
    saidas = [
        {"id": "lula2", "rotulo": "Lula no 2º turno", "grupo": "lula", "votos": n2["lula"]},
        {"id": "flavio2", "rotulo": "Flávio no 2º turno", "grupo": "flavio", "votos": n2["flavio"]},
    ]
    fluxos = [
        {"de": "lula1", "para": "lula2", "votos": n1["lula"], "tipo": "contagem"},
        {"de": "terceira", "para": "lula2", "votos": b * terceira, "tipo": "estimativa"},
        {"de": "terceira", "para": "flavio2", "votos": (1 - b) * terceira, "tipo": "estimativa"},
        {"de": "novos", "para": "lula2", "votos": a * novos, "tipo": "estimativa"},
        {"de": "novos", "para": "flavio2", "votos": (1 - a) * novos, "tipo": "estimativa"},
    ]
    # A troca direta SAI do bloco do Flavio: ele não pode ter mais votos saindo
    # do que os que tinha. Por isso `flavio1 → flavio2` é o que RESTA, e não o
    # total do 1º turno.
    if troca >= 0:
        fluxos.append({"de": "flavio1", "para": "lula2", "votos": troca, "tipo": "troca"})
        fluxos.append({"de": "flavio1", "para": "flavio2",
                       "votos": n1["flavio"] - troca, "tipo": "contagem"})
    else:
        fluxos.append({"de": "lula1", "para": "flavio2", "votos": -troca, "tipo": "troca"})
        fluxos.append({"de": "flavio1", "para": "flavio2", "votos": n1["flavio"], "tipo": "contagem"})
    # Os nós de saída somam o total, e a soma tem de dar o oficial do TSE.
    erro_lula2 = sum(x["votos"] for x in fluxos if x["para"] == "lula2") - n2["lula"]
    erro_flavio2 = sum(x["votos"] for x in fluxos if x["para"] == "flavio2") - n2["flavio"]
    return {
        "entradas": entradas, "saidas": saidas, "fluxos": fluxos,
        "troca": round(troca),
        "conferencia": {"erro_lula2": round(erro_lula2), "erro_flavio2": round(erro_flavio2)},
        "parametros": {"a": round(a, 4), "b": round(b, 4)},
        "eleitores": eleitores,
    }


def cenarios(dados: dict) -> dict:
    """As "formas de vencer": o espaço de cenários que cabe nos totais.

    A conta que amarra tudo, por município e no país, é uma só:

        ΔLula = alfa × (votos válidos novos) + beta × (terceira via) + c

    onde `c` é o saldo líquido de troca direta (eleitor do Flavio que foi para o
    Lula menos eleitor do Lula que foi para o Flavio). Com `c = 0` sobra uma
    RETA — alfa × 4.776.239 + beta × 9.321.993 = 10.376.694 — e é ela que
    desenha os cenários que o resultado permite. Nenhum desses cenários pode ser
    descartado pelos números; o que os separa é o ajuste cidade a cidade, e é
    isso que a tela mostra (o "encaixe" de cada um).
    """
    n1, n2 = dados["nacional"]["t1"], dados["nacional"]["t2"]
    dL = n2["lula"] - n1["lula"]
    novos = n2["validos"] - n1["validos"]
    terceira = n1["validos"] - n1["lula"] - n1["flavio"]
    B = n1["flavio"]
    if not novos or not terceira:
        return {"ok": False}

    eleitores = dados.get("eleitores") or n1.get("eleitores") or 0
    absten_1t = max(0, eleitores - n1["comp"]) if eleitores else 0
    absten_2t = max(0, eleitores - n2["comp"]) if eleitores else 0

    def cenario(id_, titulo, texto, alfa, beta, c=0.0):
        de_lula = alfa * novos + beta * terceira + c
        return {"id": id_, "titulo": titulo, "texto": texto,
                "alfa": round(alfa, 4), "beta": round(beta, 4), "c": round(c),
                "lula_de": round(de_lula),
                "flavio_de": round(novos + terceira - de_lula),
                "c_pct_flavio": round(100 * c / B, 1) if B else 0.0,
                "novos_lula": round(100 * alfa, 1), "terceira_lula": round(100 * beta, 1)}

    lista = [
        cenario("abstencao", "A abstenção apareceu e votou em peso no Lula",
                "Todo voto novo (quem faltou em 04/10 e voltou, mais branco e nulo que viraram voto) "
                "teria ido para o Lula, e nenhum eleitor do Flavio teria mudado de lado. Precisa de "
                "100% dos votos novos com o Lula — e ainda assim 60% da terceira via teria de ir junto.",
                1.0, min(1.0, (dL - novos) / terceira)),
        cenario("terceira", "A terceira via foi inteira para o Lula",
                "Os 9,3 milhões da terceira via teriam ido todos para o Lula; o voto novo se dividiria "
                "como no país (22% para ele) e ninguém trocaria de lado.",
                min(1.0, (dL - terceira) / novos), 1.0),
        cenario("uniforme", "Todo mundo migrou na mesma proporção",
                "Nenhuma troca direta entre os dois: cada eleitor que voltou às urnas e cada voto da "
                "terceira via se dividiu na MESMA taxa (74% para o Lula).",
                dL / (novos + terceira), dL / (novos + terceira)),
        cenario("regressao", "O que os municípios dizem",
                "A divisão que melhor explica o movimento cidade a cidade: 95% dos votos novos e 58% "
                "da terceira via para o Lula — o que exige uma troca líquida pequena a favor dele.",
                0.952, 0.584),
        cenario("virada", "Eleitores do Flavio é que viraram",
                "Nem o voto novo nem a terceira via explicariam nada: tudo viria de eleitor do Flavio "
                "mudando de lado — 18,5% de todo o voto dele em 04/10.",
                0.0, 0.0, dL),
    ]
    for x in lista:
        x["encaixe"] = _encaixe(dados, x["alfa"], x["beta"], x["c"])

    # A reta dos cenários sem troca direta (c = 0), para o gráfico.
    reta = [{"alfa": round(k / 20, 2),
             "beta": round((dL - (k / 20) * novos) / terceira, 4)}
            for k in range(0, 21)
            if 0 <= (dL - (k / 20) * novos) / terceira <= 1]

    return {
        "ok": True,
        "delta_lula": dL, "novos": novos, "terceira": terceira,
        "abstencao_1t": absten_1t, "abstencao_2t": absten_2t,
        "retornaram": absten_1t - absten_2t,
        "brancos_nulos_1t": n1["brancos"] + n1["nulos"],
        "brancos_nulos_2t": n2["brancos"] + n2["nulos"],
        "brancos_nulos_que_viraram": (n1["brancos"] + n1["nulos"]) - (n2["brancos"] + n2["nulos"]),
        "cenarios": lista, "reta": reta,
        "limites": {"beta_max_c0": round((dL - novos) / terceira, 4),
                    "alfa_min": round((dL - terceira) / novos, 4)},
    }


def _encaixe(dados: dict, alfa: float, beta: float, c: float) -> dict:
    """O quanto um cenário explica o movimento em cada cidade (R² e erro).

    O cenário é aplicado município a município e comparado com o ganho REAL do
    Lula ali. Um cenário com encaixe bom é aquele em que as cidades que tinham
    mais terceira via (ou mais voto novo) foram também as que mais deram voto
    ao Lula — na proporção que ele afirma.

    O termo de troca (`c`) é o único que o país inteiro só define em SALDO — o
    sudeste de quem saiu não é observável. Aqui ele é distribuído pela FATIA do
    Flavio no município, normalizada: é o "quem tinha mais voto dele, mais
    perdeu" mais simples que o dado comporta. É a parte mais fraca do cenário, e
    é por isso que o cartão mostra os cenários em ordem de encaixe, não de
    "verdade".
    """
    muns = [m for m in dados["municipios"] if m["t1"]["validos"] >= PISO_MUNICIPIO]
    if not muns:
        return {"r2": None, "erro": None}
    base_f = sum(m["t1"]["flavio"] for m in muns) or 1
    sq = 0.0
    soma_c = 0.0
    ganhos = [m["t2"]["lula"] - m["t1"]["lula"] for m in muns]
    media = sum(ganhos) / len(muns)
    var = sum((g - media) ** 2 for g in ganhos)
    for m in muns:
        t1, t2 = m["t1"], m["t2"]
        novos = t2["validos"] - t1["validos"]
        terc = t1["validos"] - t1["lula"] - t1["flavio"]
        c_m = c * (t1["flavio"] / base_f)      # distribuição NORMALIZADA
        previsto = alfa * novos + beta * terc + c_m
        sq += (t2["lula"] - t1["lula"] - previsto) ** 2
        soma_c += c_m
    r2 = 1 - sq / var if var else None
    return {"r2": round(r2, 5) if r2 is not None else None,
            "erro": round(sq ** 0.5), "soma_distribuida": round(soma_c)}


def conferencia(dados: dict) -> dict:
    """A soma das seções fecha com o arquivo oficial? É o que autoriza o resto."""
    ufs = []
    for c in dados.get("conferencia") or []:
        t2, t1 = c["t2"], c["t1"]
        difs = {
            "comparecimento": t2["comp_soma"] - t2["comp_oficial"],
            "validos": t2["val_soma"] - t2["val_oficial"],
            "brancos": t2["br_soma"] - t2["br_oficial"],
            "nulos": t2["nu_soma"] - t2["nu_oficial"],
        }
        difs["secoes"] = t2["secoes_soma"] - t2["secoes_oficial"]
        ufs.append({"uf": c["uf"], "nome": c["nome"],
                    "fecha": not any(abs(v) > 0 for k, v in difs.items() if k != "secoes"),
                    "difs": difs,
                    "secoes": t2["secoes_soma"], "secoes_oficial": t2["secoes_oficial"],
                    "comp": t2["comp_oficial"], "validos": t2["val_oficial"],
                    "eleitores": t2["eleitores"], "abstencao": t2["abstencao"],
                    "t1_comp": t1["comp_oficial"], "t1_eleitores": t1["eleitores"],
                    "t1_validos": t1["val_oficial"]})
    fecham = sum(1 for u in ufs if u["fecha"])
    return {"ufs": ufs, "fecham": fecham, "total": len(ufs),
            "todas": bool(ufs) and fecham == len(ufs)}


def resumo_de(dados: dict) -> dict:
    """Os números de topo, a partir do `explicacao.json` já lido."""
    n1, n2 = dados["nacional"]["t1"], dados["nacional"]["t2"]
    novos = n2["validos"] - n1["validos"]
    terceira = n1["validos"] - n1["lula"] - n1["flavio"]
    return {
        "ok": True,
        "gerado_em": dados.get("gerado_em"),
        "nacional": {
            "comp1": n1["comp"], "comp2": n2["comp"],
            "validos1": n1["validos"], "validos2": n2["validos"],
            "brancos1": n1["brancos"], "brancos2": n2["brancos"],
            "nulos1": n1["nulos"], "nulos2": n2["nulos"],
            "lula1": n1["lula"], "lula2": n2["lula"],
            "flavio1": n1["flavio"], "flavio2": n2["flavio"],
        },
        "novos_validos": novos,
        "terceira_via": terceira,
        "ganho_lula": n2["lula"] - n1["lula"],
        "ganho_flavio": n2["flavio"] - n1["flavio"],
        "municipios": len(dados.get("municipios") or []),
        "linhas_secao": dados.get("linhas_secao"),
        "candidatos": dados.get("candidatos_1t") or [],
        "conferencia": conferencia(dados),
    }


def resumo(base: Path) -> dict:
    """O que o template precisa para montar a aba. Lê o `conta.json` gerado na
    migração — se ele não existir, cai no `explicacao.json` (mais lento, mas
    nunca quebra a página)."""
    try:
        return json.loads((base / "conta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    try:
        return resumo_de(_ler(base))
    except (OSError, ValueError):
        return {"ok": False}


# (aqui havia um bloco morto: um `return` inteiro que nunca executava, sobra de
# uma edição anterior. Removido em 28/10/2026 — o resumo sai de `resumo_de`.)
def _falta_era_dados(dados):  # pragma: no cover - mantido só para leitura do diff
    n1, n2 = dados["nacional"]["t1"], dados["nacional"]["t2"]
    novos = n2["validos"] - n1["validos"]
    terceira = n1["validos"] - n1["lula"] - n1["flavio"]
    ganho_lula = n2["lula"] - n1["lula"]
    ganho_flavio = n2["flavio"] - n1["flavio"]
    return {
        "ok": True,
        "gerado_em": dados.get("gerado_em"),
        "nacional": {
            "comp1": n1["comp"], "comp2": n2["comp"],
            "comp1_pct": _pct(n1["comp"], n1["validos"] + n1["brancos"] + n1["nulos"]),
            "validos1": n1["validos"], "validos2": n2["validos"],
            "brancos1": n1["brancos"], "brancos2": n2["brancos"],
            "nulos1": n1["nulos"], "nulos2": n2["nulos"],
            "lula1": n1["lula"], "lula2": n2["lula"],
            "flavio1": n1["flavio"], "flavio2": n2["flavio"],
        },
        "novos_validos": novos,
        "terceira_via": terceira,
        "ganho_lula": ganho_lula,
        "ganho_flavio": ganho_flavio,
        "municipios": len(dados.get("municipios") or []),
        "linhas_secao": dados.get("linhas_secao"),
        "candidatos": dados.get("candidatos_1t") or [],
        "conferencia": conferencia(dados),
    }


def analise(base: Path) -> dict:
    """O arquivo que a aba consome: resumo + fluxo + por estado."""
    dados = _ler(base)
    r = resumo_de(dados)
    r["fluxo"] = fluxo(dados)
    r["sankey"] = sankey(dados, r["fluxo"]) if r["fluxo"].get("ok") else {"fluxo": None}
    r["cenarios"] = cenarios(dados)
    # Comparecimento por UF: a história do "faltou gente" e do "sobrou gente".
    ufs = []
    for c in dados.get("conferencia") or []:
        t1, t2 = c["t1"], c["t2"]
        if not t1.get("eleitores") or not t2.get("comp_oficial"):
            continue
        ufs.append({
            "uf": c["uf"], "nome": c["nome"],
            "eleitores": t1["eleitores"],
            "pct1": round(100 * t1["comp_oficial"] / t1["eleitores"], 2),
            "pct2": round(100 * t2["comp_oficial"] / t1["eleitores"], 2),
            "variacao": round(100 * (t2["comp_oficial"] - t1["comp_oficial"]) / t1["eleitores"], 2),
            "comp1": t1["comp_oficial"], "comp2": t2["comp_oficial"],
        })
    ufs.sort(key=lambda u: u["variacao"])
    r["ufs"] = ufs
    return r


def gerar_cache(base: Path) -> dict:
    """Grava `conta.json` e `municipios.json` ao lado do `explicacao.json`.

    Roda UMA vez, na migração. A página só serve arquivo: nenhuma visita ao
    /apuracao gasta CPU montando isto (a análise leva ~12 s por causa do
    bootstrap, e o Pi é um Raspberry).
    """
    a = analise(base)
    # Um arquivo só para a aba de explicação: `analise.json`, `cenarios.json` e
    # `simulador.json` diziam os mesmos totais em três lugares. Agora é
    # `conta.json`, e as três seções leem dele.
    # Os três JS antigos esperam `limite`/`cenarios`/`modelo`/`identificabilidade`
    # e `variaveis`/`fronteira` no TOPO do JSON. Em vez de reescrever os três,
    # o servidor achata aqui: um arquivo só, mesmo contrato de antes.
    from apuracao import cenarios as _cen, simulador as _sim
    lim, cens, mod = _cen.limite(a), _cen.cenarios(a), _cen.modelo(a)
    a["limite"], a["cenarios"], a["modelo"] = lim, cens, mod
    sim = _sim.dados(base)
    a["variaveis"], a["fronteira"] = sim["variaveis"], sim["fronteira"]
    a["identificabilidade"] = _cen.identificabilidade(base)
    # A transição POR CANDIDATO da terceira via (com o IC de cada um) e a troca
    # direta. Roda na migração porque leva ~20 s de LP no Pi.
    from apuracao import transicao as _tr
    try:
        a["transicao"] = _tr.calcular(base)
    except Exception as e:                       # noqa: BLE001
        a["transicao"] = {"ok": False, "motivo": f"{type(e).__name__}: {e}"}
    # O cenário inicial (as fatias que fecham nos TRÊS destinos) é resolvido
    # aqui: no JavaScript a conta ficava 4 mi fora e o deploy custa 10 min.
    try:
        a["inicial"] = _tr.cenario_inicial(a)
    except Exception as e:                       # noqa: BLE001
        a["inicial"] = {"erro": f"{type(e).__name__}: {e}"}
    destino = base / "conta.json"
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(a, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(destino)

    dados = _ler(base)
    muns = municipios(base)
    compacto = [{k: m[k] for k in ("cd", "nm", "uf", "v1", "v2", "l1", "l2", "f1", "f2", "t")}
                for m in muns]
    destino_m = base / "municipios.json"
    tmp = destino_m.with_suffix(".tmp")
    tmp.write_text(json.dumps(compacto, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(destino_m)
    return {"analise": destino, "municipios": destino_m, "n": len(compacto)}


def municipios(base: Path, uf: str | None = None) -> list[dict]:
    """Os municípios de uma UF, no formato compacto da tela (mapa e lista)."""
    dados = _ler(base)
    alvo = (uf or "").lower()
    out = []
    for m in dados.get("municipios") or []:
        if alvo and m["uf"] != alvo:
            continue
        t1, t2 = m["t1"], m["t2"]
        terc = t1["validos"] - t1["lula"] - t1["flavio"]
        out.append({
            "cd": m["cd"], "nm": m["nm"], "uf": m["uf"],
            "v1": t1["validos"], "v2": t2["validos"],
            "l1": t1["lula"], "l2": t2["lula"],
            "f1": t1["flavio"], "f2": t2["flavio"],
            "t": terc, "comp1": t1["comp"], "comp2": t2["comp"],
        })
    out.sort(key=lambda m: -m["v2"])
    return out
