"""Simulador de cadeiras na ALESC e ranking de nominata.

A parte determinística — transformar votos em cadeiras — é a lei, e está aqui
implementada como está no Código Eleitoral. A parte incerta — estimar os votos —
é explicitamente um CENÁRIO, montado a partir de um piso real (a votação de 2022)
mais ajustes que o usuário escolhe. O app nunca apresenta isso como previsão.

Referências: Código Eleitoral, arts. 106 a 109, com a redação da Lei 14.211/2021.

- Art. 106: quociente eleitoral = votos válidos ÷ lugares, "desprezada a fração
  se igual ou inferior a meio, equivalente a um se superior". É ARREDONDAMENTO,
  não truncamento — errar isso desloca o quociente em uma unidade e pode mover
  uma cadeira.
- Art. 107: quociente partidário = votos da legenda ÷ quociente eleitoral,
  desprezada a fração.
- Art. 108: eleitos os mais votados da legenda que tenham ao menos 10% do
  quociente eleitoral.
- Art. 109: sobras pelas maiores médias (votos ÷ cadeiras+1), disputadas pelas
  legendas com ao menos 80% do quociente eleitoral, e por candidatos com ao
  menos 20% dele. Se as vagas não se preenchem assim, o corte cai.
- 3ª fase (art. 109, III, como o STF leu nas ADIs 7228/7263/7325, valendo desde
  2024): o que sobra depois dos 80/20 vai pela maior média entre TODAS as
  legendas, sem piso nenhum. Até 2022 o TSE deixava só quem tinha 80%.
- Empate na média: leva a legenda mais votada.

Conferido em 04/10/2026 contra o resultado oficial de 302 eleições de vereador
de 2024 (os 295 municípios de SC e mais 7 capitais): cadeiras idênticas em
todas. Rio do Sul só bate com a 3ª fase aberta, e Cerro Negro só bate com o
desempate pela votação. As amostras ficam em `politicos/amostras_tse2024/` e o
teste em `tools.testar_politicos`.
"""
from __future__ import annotations

import math
import random
from math import floor

from politicos import calibracao

CADEIRAS_ALESC = 40


def quociente_eleitoral(validos: int, lugares: int = CADEIRAS_ALESC) -> int:
    """Art. 106: fração ≤ 0,5 despreza; > 0,5 vira um."""
    if lugares <= 0:
        return 0
    bruto = validos / lugares
    inteiro = floor(bruto)
    return inteiro + (1 if (bruto - inteiro) > 0.5 else 0)


def distribuir(votos: dict[str, int], lugares: int = CADEIRAS_ALESC,
               piso_sobras: float = 0.8,
               candidatos: dict[str, list[int]] | None = None,
               validos: int | None = None) -> dict:
    """Distribui as cadeiras. Devolve o resultado e o passo a passo.

    `votos` é {legenda: votos}. Federação conta como uma legenda só — é assim
    que a lei trata, e é por isso que PT/PCdoB/PV aparecem juntos em 2022.

    `candidatos` é {legenda: [votos de cada candidato]}, em qualquer ordem.
    Com ele valem os pisos individuais: o QP só elege quem tem 10% do QE
    (art. 108) e a 2ª fase só dá vaga a quem tem 20% (art. 109). Sem ele —
    cenário só por legenda — cada legenda é tratada como tendo candidatos
    acima dos pisos, que é o máximo que o dado permite dizer.

    `fases` diz, por legenda, por onde entrou cada cadeira ("QP", "média",
    "3ª fase"), na ordem em que os candidatos da lista as ocupam.
    """
    validos = sum(votos.values()) if validos is None else validos
    qe = quociente_eleitoral(validos, lugares)
    if qe <= 0:
        return {"qe": 0, "validos": validos, "cadeiras": {}, "sobras": [],
                "fases": {}}

    lista = (None if candidatos is None else
             {l: sorted((int(x) for x in candidatos.get(l, [])), reverse=True)
              for l in votos})

    cadeiras: dict[str, int] = {}
    for leg, v in votos.items():
        qp = floor(v / qe)
        if lista is not None:
            qp = min(qp, sum(1 for x in lista[leg] if x >= 0.10 * qe))
        cadeiras[leg] = qp
    fases = {l: ["QP"] * c for l, c in cadeiras.items()}
    # Uma legenda nunca leva mais lugares do que existem
    usadas = sum(cadeiras.values())
    if usadas > lugares:
        return {"qe": qe, "validos": validos, "cadeiras": cadeiras, "sobras": [],
                "fases": fases, "aviso": "quocientes partidários excedem os lugares"}

    def proximo_tem(leg: str, piso: float) -> bool:
        """O próximo da lista (o primeiro ainda não eleito) alcança o piso?"""
        if lista is None:
            return True
        c, k = lista[leg], cadeiras[leg]
        return k < len(c) and c[k] >= piso

    def media(leg: str) -> tuple[float, int]:
        return votos[leg] / (cadeiras[leg] + 1), votos[leg]   # empate: mais votada

    sobras = []
    livres = lugares - usadas
    for fase, aptos_de in (
        ("média", lambda: [l for l, v in votos.items()
                           if v >= piso_sobras * qe and proximo_tem(l, 0.20 * qe)]),
        ("3ª fase", lambda: [l for l, v in votos.items()
                             if v > 0 and proximo_tem(l, 0)]),
    ):
        while livres > 0:
            aptos = aptos_de()
            if not aptos:
                break
            leg = max(aptos, key=media)
            m = votos[leg] / (cadeiras[leg] + 1)
            cadeiras[leg] += 1
            fases[leg].append(fase)
            livres -= 1
            sobras.append({"legenda": leg, "media": round(m, 1),
                           "cadeira": cadeiras[leg], "fase": fase})

    return {
        "qe": qe,
        "validos": validos,
        "lugares": lugares,
        "cadeiras": {l: c for l, c in sorted(cadeiras.items(), key=lambda kv: -kv[1])},
        "por_quociente": usadas,
        "sobras": sobras,
        "fases": fases,
        "vagas_sem_dono": livres,
        "piso_candidato": round(qe * 0.10),   # art. 108
        "piso_sobra_candidato": round(qe * 0.20),   # art. 109 §1º
    }


def agremiacoes_do_tse(arquivo: dict) -> tuple[dict[str, int], dict[str, list[int]], int]:
    """Lê um arquivo `-u.json` do resultados.tse.jus.br para o `distribuir`.

    Devolve ({agremiação: votos válidos}, {agremiação: [votos dos candidatos
    elegíveis]}, votos válidos totais). Três pegadinhas, todas vistas em 2024:

    - `tvtn`/`tvtl` são nominal e legenda VÁLIDOS; `tvan`/`tval` são os
      APURADOS e incluem anulado (em Curitiba a diferença era de 84 mil votos);
    - partido com `dvt == "Anulado"` teve a chapa indeferida: nada dele conta;
    - candidato "Válido (legenda)" soma para o partido mas não pode ser eleito.
    """
    carg = arquivo["carg"][0]
    votos: dict[str, int] = {}
    cands: dict[str, list[int]] = {}
    for a in carg["agr"]:
        pars = [p for p in a["par"] if p.get("dvt", "") != "Anulado"]
        votos[a["nm"]] = sum(int(p.get("tvtn") or 0) + int(p.get("tvtl") or 0)
                             for p in pars)
        cands[a["nm"]] = [int(x.get("vap") or 0) for p in pars for x in p["cand"]
                          if x.get("dvt", "Válido") == "Válido"]
    return votos, cands, int(arquivo["v"]["vv"])


# ── base e cenários ──────────────────────────────────────────────────────────

# Federação conta como legenda única. Mapa para exibir e para casar com o
# cadastro de perfis, que guarda o partido isolado.
FEDERACOES = {
    "Federação Brasil da Esperança - FE BRASIL": ["PT", "PCDOB", "PV"],
    "Federação PSDB Cidadania": ["PSDB", "CIDADANIA"],
    "Federação PSOL REDE": ["PSOL", "REDE"],
    # Novas em 2026 (lista de deputado estadual de SC no TSE, 04/10/2026). Até
    # então o simulador tratava PP e UNIÃO como duas legendas, e federação
    # disputa o quociente como UMA lista só.
    "Federação União Progressista": ["UNIÃO", "PP"],
    "Federação Renovação Solidária": ["PRD", "SOLIDARIEDADE"],
}

# Legenda de 2022 → agremiação que herda o voto em 2026. As federações acima
# mais as fusões de 2023 (PTB + Patriota → PRD; PROS → Solidariedade; PSC →
# Podemos). Quem não tem lista de deputado estadual em SC em 2026 (PSB, DC,
# PRTB, PCO) sai: o voto dele vai para alguém, e a reescala ao total de válidos
# o reparte na proporção dos outros — o que é uma premissa, não um dado.
LEGENDA_2026_DE_2022 = {
    "PP": "Federação União Progressista",
    "UNIÃO": "Federação União Progressista",
    "PTB": "Federação Renovação Solidária",
    "PATRIOTA": "Federação Renovação Solidária",
    "PRD": "Federação Renovação Solidária",
    "SOLIDARIEDADE": "Federação Renovação Solidária",
    "PROS": "Federação Renovação Solidária",
    "PSC": "PODE",
    "PSB": None,
    "DC": None,
    "PRTB": None,
    "PCO": None,
}

# Partidos que tiveram cadeiras em 2022 mas NÃO existem como legendas
# independentes para deputado estadual em 2026. Isso NÃO é lacuna de coleta —
# a legenda não lançou chapa para o cargo ou fundiu-se com outra. Cada entrada
# mapeia a sigla 2022 → (status, rótulo explicativo curto).
#
# PSB: coligado com PT/PCdoB/PV/PSOL/Rede/PDT em 2026; lançou governador e
# federal, mas não estadual. O voto de legenda vai para a coligação, não para
# uma chapa própria de deputado estadual.
# PTB + PATRIOTA: fundiram-se em nov/2023 → PRD (Partido Renovação Democrática,
# número 25). O PRD já está no cadastro TSE (22 candidatos na fila) e herda o
# patrimônio eleitoral dos dois. Fonte: TSE, sessão de 09/11/2023.
LEGENDAS_EXTINTAS_2026: dict[str, tuple[str, str]] = {
    "PSB": ("sem chapa própria", "PSB concorre a governador e federal em SC, "
            "mas não tem chapa de deputado estadual em 2026."),
    "PTB": ("fundido no PRD", "PTB fundiu-se com Patriota → PRD (Partido "
            "Renovação Democrática) em nov/2023."),
    "PATRIOTA": ("fundido no PRD", "Patriota fundiu-se com PTB → PRD (Partido "
                 "Renovação Democrática) em nov/2023."),
}


# Rótulo curto de cada federação, para chip e tabela (o nome inteiro não cabe).
SIGLA_CURTA = {
    "Federação Brasil da Esperança - FE BRASIL": "PT/PCdoB/PV",
    "Federação PSDB Cidadania": "PSDB/Cidadania",
    "Federação PSOL REDE": "PSOL/Rede",
    "Federação União Progressista": "União/PP",
    "Federação Renovação Solidária": "PRD/Solidariedade",
}


def agremiacao_do_tse(nome_tse: str, siglas: list[str]) -> str:
    """O nome do TSE ("FEDERAÇÃO UNIÃO PROGRESSISTA") no vocabulário do app:
    federação pelo nome usado aqui, partido isolado pela sigla."""
    siglas = [s.upper() for s in siglas]
    for leg, membros in FEDERACOES.items():
        if set(siglas) & set(membros):
            return leg
    return siglas[0] if siglas else nome_tse


def sigla_para_legenda(sigla: str) -> str:
    for legenda, siglas in FEDERACOES.items():
        if sigla in siglas:
            return legenda
    return sigla


def base_2022(con) -> dict[str, int]:
    """A votação de 2022 como ela foi, nas legendas daquele ano."""
    return {r["legenda"]: r["votos"] for r in con.execute(
        "SELECT legenda, votos FROM eleicao_votos WHERE ano=2022 AND cargo='DEPUTADO ESTADUAL'")}


def em_2026(por_legenda_2022: dict[str, int]) -> dict[str, int]:
    """Reagrupa um dicionário por legenda de 2022 nas agremiações de 2026."""
    saida: dict[str, int] = {}
    for leg, n in por_legenda_2022.items():
        alvo = LEGENDA_2026_DE_2022.get(leg, leg)
        if alvo is not None:
            saida[alvo] = saida.get(alvo, 0) + (n or 0)
    return saida


def base_2022_em_2026(con) -> dict[str, int]:
    """O voto de 2022 nas listas que existem em 2026 — o ponto de partida dos
    cenários. Comparar 2026 com `base_2022` pura punha PP e UNIÃO como dois
    concorrentes num ano em que eles disputam juntos."""
    return em_2026(base_2022(con))


def cadeiras_2022_em_2026(con) -> dict[str, int]:
    """As cadeiras REAIS de 2022 somadas por agremiação de 2026 (para o delta)."""
    return em_2026(distribuir(base_2022(con))["cadeiras"])


# ── estimativas de votos por evidência ───────────────────────────────────────
#
# Três sinais independentes, todos rastreáveis a dado público. Nenhum é
# previsão: são CENÁRIOS de partida para o simulador, e a tela diz qual fonte
# alimentou cada legenda.

def _mediana(valores: list[float]) -> float | None:
    from statistics import median
    valores = [v for v in valores if v is not None]
    return float(median(valores)) if valores else None


def custo_voto_por_legenda(con) -> tuple[dict[str, float], float | None]:
    """R$ por voto em 2022 (receita declarada ÷ votos), mediana por legenda.

    Mediana, não média: um candidato autofinanciado não distorce o partido.
    """
    por_legenda: dict[str, list[float]] = {}
    geral: list[float] = []
    for r in con.execute("""
        SELECT p.partido, f.receita, MAX(v.votos) AS votos
          FROM v2_financeiro f
          JOIN v2_votos_candidato v ON v.perfil_id = f.perfil_id AND v.ano = 2022
          JOIN perfis p ON p.id = f.perfil_id
         WHERE f.ano = 2022 AND v.votos > 0
           AND UPPER(v.cargo) = 'DEPUTADO ESTADUAL'
         GROUP BY p.id
    """):
        razao = r["receita"] / r["votos"]
        geral.append(razao)
        por_legenda.setdefault(sigla_para_legenda(r["partido"]), []).append(razao)
    return ({l: round(_mediana(v), 2) for l, v in por_legenda.items()},
            round(_mediana(geral), 2) if geral else None)


def razao_votos_seguidor_por_legenda(con) -> tuple[dict[str, float], float | None]:
    """Votos por seguidor em 2022, mediana por legenda.

    O seguidor é o de HOJE — não temos a contagem de 2022. É um proxy, e a
    tela diz isso. Serve para estender a estimativa a quem nunca disputou.
    """
    por_legenda: dict[str, list[float]] = {}
    geral: list[float] = []
    for r in con.execute("""
        SELECT p.partido, p.seguidores, MAX(v.votos) AS votos
          FROM v2_votos_candidato v
          JOIN perfis p ON p.id = v.perfil_id
         WHERE v.ano = 2022 AND v.votos > 0 AND p.seguidores > 0
           AND UPPER(v.cargo) = 'DEPUTADO ESTADUAL'
         GROUP BY p.id
    """):
        razao = r["votos"] / r["seguidores"]
        geral.append(razao)
        por_legenda.setdefault(sigla_para_legenda(r["partido"]), []).append(razao)
    return ({l: round(_mediana(v), 4) for l, v in por_legenda.items()},
            round(_mediana(geral), 4) if geral else None)


def receita_2026_por_perfil(con) -> dict[int, float]:
    """A receita acumulada de cada perfil, monotônica: o MÁXIMO já declarado.

    O rank do DivulgaCandContas é instável — a "receita acumulada" de um
    candidato já caiu de uma semana para outra (ninguém desdeclara dinheiro).
    Pegar só a última semana deixava o sinal mais forte do modelo sujeito a
    essa oscilação, derrubando o cenário de receita inteiro de uma semana para
    a outra. O máximo histórico nunca regride.
    """
    return {r["perfil_id"]: r["receita"] for r in con.execute("""
        SELECT perfil_id, MAX(receita_acumulada) AS receita
          FROM v2_receitas_semana
         GROUP BY perfil_id
    """)}


def cadastro_por_legenda(con) -> dict[str, int]:
    """Quantos candidatos cada legenda registrou no TSE (job semanal)."""
    return {r["legenda"]: r["candidatos"] for r in con.execute(
        "SELECT legenda, candidatos FROM v2_cadastro_legenda")}


# Fallback do teto por candidato quando não há histórico carregado: a maior
# votação individual para deputado estadual em SC em 2022.
TETO_VOTOS_PADRAO = 200_000


def teto_votos_candidato(con) -> int:
    """Maior votação individual já registrada para o cargo.

    Existe porque a conversão seguidor→voto é linear e o Instagram não respeita
    fronteira de estado: uma candidata com 2,6 milhões de seguidores no país
    inteiro recebia 2,6 milhões de votos estimados num estado que teve 4,0
    milhões de votos válidos, treze vezes o recorde do cargo. O teto não torna
    a extrapolação certa; impede que ela vire absurdo aritmético.
    """
    r = con.execute(
        "SELECT MAX(votos) v FROM v2_votos_candidato WHERE UPPER(cargo)=?",
        ("DEPUTADO ESTADUAL",)).fetchone()
    return int(r["v"] or 0) or TETO_VOTOS_PADRAO


def teto_votos_por_legenda(con) -> dict[str, int]:
    """Maior votação individual por legenda (deputado estadual, qualquer ano).

    O teto global (`teto_votos_candidato`) impede uma celebridade nacional de
    extrapolar 2,6 milhões de votos, mas não captura a diferença entre um teto
    realista no PL (que elege campeões de voto) e no MISSÃO (que estreou). A
    conversão por seguidor/receita é o mesmo modelo para todos; calibra-la por
    legenda — cada uma com o seu próprio recorde — é o que evita que um partido
    pequeno receba uma estimativa que ele nunca realizou. Onde a legenda não
    tem histórico, cai no teto global.
    """
    por_legenda: dict[str, int] = {}
    for r in con.execute(
        """SELECT p.partido, MAX(v.votos) v FROM v2_votos_candidato v
            JOIN perfis p ON p.id = v.perfil_id
            WHERE UPPER(v.cargo)='DEPUTADO ESTADUAL'
            GROUP BY p.partido"""):
        leg = sigla_para_legenda(r["partido"])
        por_legenda[leg] = max(por_legenda.get(leg, 0), int(r["v"] or 0))
    return por_legenda


def estimar_votos_candidato(seguidores: int | None, razao: float | None,
                            receita: float | None, custo_voto: float | None,
                            voto_anterior: int | None, teto: int,
                            eleito_mesmo_cargo: bool = False) -> tuple:
    """Votos estimados de UM candidato e a fonte da estimativa.

    Hierarquia por força da evidência, da mais forte para a mais fraca:

    1. **Receita 2026 → voto por elasticidade** — dinheiro já declarado nesta
       eleição, convertido pela regressão calibrada em 2022 (retornos
       decrescentes: `calibracao.votos_por_receita`). Incumbente leva o prêmio
       da dummy de incumbência dentro da própria regressão.
    2. **Voto anterior no mesmo cargo** — é fato, não estimativa; para quem já
       disputou, nenhum proxy de rede social supera o próprio resultado. Quem
       foi ELEITO leva o multiplicador de incumbência (`calibracao`): reeleito
       tem vantagem documentada, e repetir o voto de 2022 em 2026 sem ela é
       subestimar justamente o candidato com mais chance.
    3. **Seguidores × razão da legenda**, limitado pelo teto do cargo.

    Devolve (votos, fonte) e a fonte é exibida na tela: as três não valem o
    mesmo e quem lê precisa saber qual sustenta cada linha.
    """
    if receita and receita > 0:
        voto = calibracao.votos_por_receita(
            receita, incumbente=eleito_mesmo_cargo)
        if voto is not None:
            return min(voto, teto), "receita"
    if voto_anterior:
        votos = int(voto_anterior)
        if eleito_mesmo_cargo:
            votos = round(votos * calibracao.BONUS_VOTO_ANTERIOR_ELEITO)
            return min(votos, teto), "voto anterior × incumbência"
        return int(voto_anterior), "voto anterior"
    if seguidores and razao:
        bruto = round(seguidores * razao)
        return (min(bruto, teto), "seguidores (no teto)" if bruto > teto else "seguidores")
    return None, None


def faixa_votos_candidato(receita: float | None,
                          voto_anterior: int | None,
                          eleito_mesmo_cargo: bool = False) -> tuple[int, int] | None:
    """Intervalo de ±1σ da estimativa, quando ela vem da receita.

    Só a receita tem dispersão calibrada (o resíduo em log do modelo). Voto
    anterior é fato — não tem banda — e seguidores é proxy sem dispersão
    estimada. A tela usa isto para mostrar "de X a Y" em vez de um número
    pontual que parece mais preciso do que é.
    """
    if receita and receita > 0:
        return calibracao.votos_por_receita_faixa(
            receita, incumbente=eleito_mesmo_cargo)
    return None


def estimativas(con) -> dict:
    """Por legenda: os sinais de voto, a cobertura de cada um e a confiança.

    Cobre também legendas sem 2022 (MISSÃO e cia.): elas entram com base zero
    e estimativa própria assim que houver perfis acompanhados.

    A CONFIANÇA é o que impede o simulador de mentir. Um sinal parcial não vale
    o mesmo que um sinal completo, e antes disto o cenário Receita trocava os
    136.632 votos do NOVO em 2022 pelos 84 votos que R$ 730 declarados compram
    — número real, conclusão absurda. Agora cada sinal entra na proporção do
    que ele de fato cobre:

    - Receita: quanto da campanha esperada já foi declarada, ou seja
      `receita_2026 / (votos_2022 × custo_voto)`. Legenda sem 2022 usa um
      quociente eleitoral como alvo, que é o que ela precisaria para uma
      cadeira. Sobe sozinho a cada semana de coleta.
    - Seguidores: quantos dos candidatos registrados no TSE naquela legenda
      são efetivamente acompanhados. Somar 33 perfis do PL e 2 do PSB e tratar
      os dois totais como comparáveis era o outro erro silencioso.
    """
    base = base_2022_em_2026(con)
    custos, custo_geral = custo_voto_por_legenda(con)
    razoes, razao_geral = razao_votos_seguidor_por_legenda(con)
    receitas = receita_2026_por_perfil(con)
    registrados = cadastro_por_legenda(con)

    # Alvo de receita para quem não disputou 2022: o custo de um quociente.
    qe_ref = quociente_eleitoral(sum(base.values()) or 0) or 0

    teto = teto_votos_candidato(con)
    teto_leg = teto_votos_por_legenda(con)
    votos_proprios = {r["perfil_id"]: r["votos"] for r in con.execute(
        """SELECT perfil_id, MAX(votos) votos FROM v2_votos_candidato
            WHERE UPPER(cargo)='DEPUTADO ESTADUAL' GROUP BY perfil_id""")}
    # Quem foi ELEITO deputado estadual (última disputa do cargo). A dummy de
    # incumbência da regressão de receita depende disto, e o bônus do voto
    # anterior também: reeleito não pode ser tratado como desafiante.
    _por_eleito: dict[int, bool] = {}
    for r in con.execute(
        """SELECT perfil_id, situacao, ano FROM v2_votos_candidato
            WHERE UPPER(cargo)='DEPUTADO ESTADUAL'
            ORDER BY perfil_id, ano DESC"""):
        if r["perfil_id"] not in _por_eleito:
            _por_eleito[r["perfil_id"]] = (
                "ELEITO" in (r["situacao"] or "").upper())
    eleito_mesmo_cargo = {pid for pid, eleito in _por_eleito.items() if eleito}

    seguidores: dict[str, int] = {}
    est_seg_leg: dict[str, int] = {}
    est_receita_leg: dict[str, int] = {}
    n_receita_leg: dict[str, int] = {}
    receita_leg: dict[str, float] = {}
    perfis_leg: dict[str, int] = {}
    acompanhados_leg: dict[str, int] = {}
    legendas = set(base) | set(registrados)
    for r in con.execute("""
        SELECT id, partido, acompanhar, COALESCE(seguidores, 0) AS seg
          FROM perfis
         WHERE partido IS NOT NULL AND descartado_em IS NULL
    """):
        leg = sigla_para_legenda(r["partido"])
        legendas.add(leg)
        perfis_leg[leg] = perfis_leg.get(leg, 0) + 1
        if not r["acompanhar"]:
            continue
        acompanhados_leg[leg] = acompanhados_leg.get(leg, 0) + 1
        teto_leg_atual = teto
        if r["seg"] > 0:
            seguidores[leg] = seguidores.get(leg, 0) + r["seg"]
            # A estimativa da legenda soma candidato a candidato, cada um com o
            # teto da própria legenda (cai no do cargo onde não há histórico).
            # Multiplicar a soma de seguidores pela razão dava a uma legenda com
            # um perfil de alcance nacional um total que nenhum partido de SC
            # jamais teve.
            bruto = round(r["seg"] * (razoes.get(leg, razao_geral) or 0))
            est_seg_leg[leg] = est_seg_leg.get(leg, 0) + min(bruto, teto_leg_atual)
        rec = receitas.get(r["id"])
        if rec:
            receita_leg[leg] = receita_leg.get(leg, 0.0) + rec
            # Voto por receita é candidato a candidato, não receita somada:
            # a elasticidade < 1 faz a soma das conversões diferir da conversão
            # da soma. Incumbente leva o prêmio dentro da própria regressão.
            v = calibracao.votos_por_receita(
                rec, incumbente=r["id"] in eleito_mesmo_cargo)
            if v is not None:
                est_receita_leg[leg] = est_receita_leg.get(leg, 0) + min(v, teto_leg_atual)
                n_receita_leg[leg] = n_receita_leg.get(leg, 0) + 1

    # Teto da SOMA por legenda: o teto individual (`teto_votos_por_legenda`)
    # limita CADA candidato; sem um limite do CONJUNTO, 30 candidatos no teto
    # somam 30× o recorde da legenda. A conversão por seguidor é linear e é
    # exatamente a que extrapola — a soma não pode superar o total que a
    # legenda já realizou (o de 2022). A receita já tem retornos decrescentes
    # (elasticidade 0,65) e não precisa deste teto.
    for leg in est_seg_leg:
        teto_soma = base.get(leg) or 0
        if teto_soma:
            est_seg_leg[leg] = min(est_seg_leg[leg], teto_soma)

    por_legenda: dict[str, dict] = {}
    for leg in sorted(legendas):
        custo = custos.get(leg, custo_geral)
        razao = razoes.get(leg, razao_geral)
        rec = receita_leg.get(leg, 0.0)
        seg = seguidores.get(leg, 0)
        votos22 = base.get(leg, 0)
        acomp = acompanhados_leg.get(leg, 0)
        reg = registrados.get(leg, 0)

        receita_esperada = (votos22 or qe_ref) * (custo or 0)
        conf_receita = (min(1.0, rec / receita_esperada)
                        if rec > 0 and receita_esperada > 0 else 0.0)
        conf_seguidores = (min(1.0, acomp / reg) if reg > 0 and seg > 0
                           else (1.0 if seg > 0 and not reg else 0.0))

        por_legenda[leg] = {
            "votos_2022": votos22,
            "seguidores": seg,
            "receita_2026": round(rec, 2),
            "custo_voto_2022": custo,
            # Quando a legenda não tem mediana própria de 2022, o custo/razão
            # exibidos vêm da média GERAL (todas as legendas). Isso precisa
            # estar marcado na tela: número idêntico em 15 legendas sem aviso
            # parece dado próprio de cada uma.
            "custo_voto_geral": leg not in custos,
            "razao_votos_seg_geral": leg not in razoes,
            # Partido extinto ou fundido em 2026: não lançou chapa para o cargo.
            # Rótulo e tooltip vêm de LEGENDAS_EXTINTAS_2026 (e ajudam a
            # explicar por que uma legenda com cadeira em 2022 não tem dado).
            "extinto_2026": LEGENDAS_EXTINTAS_2026.get(leg, (None, None))[0],
            # Estimativa por receita é a soma candidato a candidato da conversão
            # logarítmica (com o prêmio de incumbência de cada um). Não é mais
            # receita ÷ custo: dinheiro tem retorno decrescente.
            "est_receita": est_receita_leg.get(leg) or None,
            "n_receita": n_receita_leg.get(leg, 0),
            "razao_votos_seg": razao,
            "est_seguidores": est_seg_leg.get(leg) or None,
            "candidatos_tse": reg,
            "acompanhados": acomp,
            "conf_receita": round(conf_receita, 4),
            "conf_seguidores": round(conf_seguidores, 4),
        }

    selo = con.execute(
        "SELECT MAX(semana) s, MAX(coletado_em) c FROM v2_receitas_semana"
    ).fetchone()
    cadastro = con.execute(
        "SELECT MAX(atualizado_em) q FROM v2_cadastro_legenda").fetchone()
    return {
        "legendas": por_legenda,
        "custo_voto_geral": custo_geral,
        "razao_geral": razao_geral,
        # O total é o de 2022 INTEIRO, inclusive de quem não tem lista em 2026:
        # o eleitor do PSB continua votando, só que em outra legenda.
        "validos_2022": sum(base_2022(con).values()),
        "receitas_semana": selo["s"],
        "receitas_atualizado_em": selo["c"],
        "cadastro_atualizado_em": cadastro["q"],
    }


CENARIOS = {
    "base2022": "Votação de 2022",
    "unificado": "Unificado — receita + seguidores, o melhor sinal de cada legenda",
    "receita": "Receita declarada 2026 ÷ custo por voto de 2022",
    "seguidores": "Seguidores × votos por seguidor de 2022",
    "personalizado": "Votos digitados pelo usuário",
}

# Chave da estimativa e da confiança de cada cenário misturável.
_SINAIS = {
    "receita": ("est_receita", "conf_receita"),
    "seguidores": ("est_seguidores", "conf_seguidores"),
}


def _sinal_unificado(d: dict) -> tuple[float | None, float, float]:
    """O sinal combinado (receita + seguidores) de UMA legenda.

    Cada evidência entra na proporção do que ela cobre (`conf_*`) E do peso
    intrínseco que tem (`calibracao`): receita é evidência forte (regressão
    calibrada), seguidor é proxy fraco. O sinal final é a média ponderada das
    duas estimativas pelos pesos efetivos (peso × confiança).

    Devolve `(sinal, confianca_unificada, sinal_efetivo)`:

    - `sinal`: a estimativa combinada (None quando nenhuma das duas cobre);
    - `confianca_unificada`: `peso_receita·conf_receita + peso_seg·conf_seg`,
      limitada a 1.0 — é quanto do quadro o unificado substitui da votação 2022;
    - `sinal_efetivo`: `confianca_unificada × sinal`, a parcela ESTIMADA (o que
      o Monte Carlo pode oscilar), em oposição ao piso de 2022.
    """
    peso_rec = calibracao.PESO_RECEITA_UNIFICADO
    peso_seg = calibracao.PESO_SEGUIDORES_UNIFICADO

    est_rec = d.get("est_receita")
    est_seg = d.get("est_seguidores")
    conf_rec = d.get("conf_receita") or 0.0
    conf_seg = d.get("conf_seguidores") or 0.0

    # Peso efetivo = peso intrínseco × cobertura daquela evidência.
    w_rec = peso_rec * conf_rec if est_rec is not None else 0.0
    w_seg = peso_seg * conf_seg if est_seg is not None else 0.0

    conf_unif = min(1.0, w_rec + w_seg)
    if conf_unif <= 0:
        return None, 0.0, 0.0

    sinal = ((w_rec * (est_rec or 0.0) + w_seg * (est_seg or 0.0)) / (w_rec + w_seg)
             if (w_rec + w_seg) > 0 else None)
    if sinal is None:
        return None, conf_unif, 0.0
    return float(sinal), conf_unif, conf_unif * float(sinal)


def _cenario_votos(est: dict, cenario: str, ajustes: dict[str, float],
                   votos_absolutos: dict[str, int] | None) -> tuple[dict[str, float], dict[str, str], dict[str, float], dict[str, float]]:
    """Os votos do cenário por legenda (antes da reescala), mais fonte e confiança.

    Extraído de `simular` para que a simulação probabilística reutilize a mesma
    mistura — sem duplicar a regra de `conf × sinal + (1-conf) × 2022`.

    Devolve também `sinal_efetivo`: quanto de cada legenda é ESTIMATIVA (o
    sinal × confiança), em oposição à parcela repetida de 2022. É sobre essa
    parcela que o Monte Carlo aplica o ruído — o voto de 2022 é medido, não
    tem erro de estimativa.
    """
    fonte: dict[str, str] = {}
    confianca: dict[str, float] = {}
    misto: dict[str, float] = {}
    sinal_efetivo: dict[str, float] = {}

    if cenario == "personalizado" and votos_absolutos is not None:
        for leg in est["legendas"]:
            misto[leg] = max(0.0, float(votos_absolutos.get(leg, 0)))
            fonte[leg] = "manual"
            confianca[leg] = 1.0
            # Premissa do usuário: sem ruído de estimativa no Monte Carlo.
            sinal_efetivo[leg] = 0.0
    elif cenario == "unificado":
        for leg, d in est["legendas"].items():
            sinal, conf, sinal_ef = _sinal_unificado(d)
            confianca[leg] = round(conf, 4)
            if sinal is None or conf <= 0:
                fonte[leg] = "base2022"
                bruto = d["votos_2022"]
                sinal_ef = 0.0
            else:
                fonte[leg] = "unificado"
                bruto = conf * sinal + (1 - conf) * d["votos_2022"]
            misto[leg] = max(0.0, bruto * (1 + ajustes.get(leg, 0) / 100))
            sinal_efetivo[leg] = (max(0.0, sinal_ef
                                      * (1 + ajustes.get(leg, 0) / 100)))
    elif cenario in _SINAIS:
        chave, chave_conf = _SINAIS[cenario]
        for leg, d in est["legendas"].items():
            sinal = d.get(chave)
            conf = d.get(chave_conf) or 0.0
            if sinal is None or conf <= 0:
                conf = 0.0
                fonte[leg] = "base2022"
            else:
                fonte[leg] = cenario
            confianca[leg] = round(conf, 4)
            bruto = conf * sinal + (1 - conf) * d["votos_2022"] if conf else d["votos_2022"]
            misto[leg] = max(0.0, bruto * (1 + ajustes.get(leg, 0) / 100))
            sinal_efetivo[leg] = (max(0.0, conf * (sinal or 0.0)
                                      * (1 + ajustes.get(leg, 0) / 100)))
    else:
        for leg, d in est["legendas"].items():
            fonte[leg] = "base2022"
            confianca[leg] = 1.0 if d["votos_2022"] else 0.0
            misto[leg] = max(0.0, d["votos_2022"] * (1 + ajustes.get(leg, 0) / 100))
            sinal_efetivo[leg] = 0.0
    return misto, fonte, confianca, sinal_efetivo


def simular(con, ajustes: dict[str, float] | None = None,
            lugares: int = CADEIRAS_ALESC, cenario: str = "base2022",
            votos_absolutos: dict[str, int] | None = None,
            validos_esperados: int | None = None) -> dict:
    """Cenário de votos por legenda, transformado em cadeiras pela lei.

    Duas correções em relação à primeira versão, ambas de honestidade:

    1. **Mistura por confiança.** O sinal do cenário não substitui a votação de
       2022: entra na proporção do que cobre, `conf × sinal + (1-conf) × 2022`.
       Sinal quase vazio praticamente não move nada, em vez de derrubar uma
       legenda inteira.
    2. **Normalização ao eleitorado.** As estimativas viram pesos relativos e
       são reescaladas para o total de votos válidos esperado (padrão: os de
       2022). Sem isto o cenário Seguidores somava 8,5 milhões de votos num
       estado de 4,0 milhões e o quociente exibido virava ficção.

    `ajustes` é uma variação em % aplicada sobre o cenário escolhido, antes da
    reescala. Em "personalizado" os votos do usuário mandam e não passam por
    mistura nem por normalização — ali a premissa é dele, inclusive para dar
    votos a um partido que não existia em 2022.
    """
    est = estimativas(con)
    if not est["legendas"]:
        return {"erro": "base de 2022 não carregada"}
    ajustes = ajustes or {}
    alvo = int(validos_esperados or est["validos_2022"] or 0)

    misto, fonte, confianca, _ = _cenario_votos(est, cenario, ajustes, votos_absolutos)
    escala = 1.0
    soma = sum(misto.values())
    escala = (alvo / soma) if soma > 0 and alvo > 0 else 1.0
    votos = {leg: round(v * escala) for leg, v in misto.items()}

    r = distribuir(votos, lugares)
    r["base"] = base_2022_em_2026(con)
    r["votos_cenario"] = votos
    r["ajustes"] = ajustes
    r["cenario"] = cenario
    r["fonte_por_legenda"] = fonte
    r["confianca_por_legenda"] = confianca
    r["escala_aplicada"] = round(escala, 4)
    r["validos_esperados"] = alvo
    r["cobertura_cenario"] = sum(1 for f in fonte.values() if f == cenario)
    r["legendas_total"] = len(fonte)
    r["estimativas"] = est
    referencia = cadeiras_2022_em_2026(con)
    r["cadeiras_2022"] = referencia
    r["delta"] = {l: r["cadeiras"].get(l, 0) - referencia.get(l, 0)
                  for l in set(r["cadeiras"]) | set(referencia)}
    return r


# ── simulação probabilística (Monte Carlo) ───────────────────────────────────
#
# O `simular` determinístico dá UM número de cadeiras por legenda. Mas a
# estimativa de voto tem erro — o resíduo do modelo calibrado em 2022 é
# SIGMA_LOG_RESIDUAL, e ignorar isso é fingir que um cenário é certeza. A
# simulação sorteia o erro milhares de vezes e devolve a DISTRIBUIÇÃO: quantas
# vezes cada legenda ficou com 1, 2, 3... cadeiras. A tela mostra a mediana e
# a banda, não um ponto só.

# Número de sorteios padrão. Mil é o equilíbrio entre estabilidade da mediana
# e o tempo no Raspberry Pi: cada sorteio é uma distribuição completa (arts.
# 106-109), e mil já estabilizam a mediana na casa das unidades de voto.
MONTECARLO_PADRAO = 1000


def simular_probabilistico(con, ajustes: dict[str, float] | None = None,
                           cenario: str = "base2022",
                           votos_absolutos: dict[str, int] | None = None,
                           validos_esperados: int | None = None,
                           amostras: int = MONTECARLO_PADRAO,
                           semente: int | None = None,
                           lugares: int = CADEIRAS_ALESC) -> dict:
    """Distribuição de cadeiras por Monte Carlo, não um número pontual.

    Sobre o cenário misturado de `simular`, sorteia um ruído log-normal por
    legenda (σ = SIGMA_LOG_RESIDUAL, o erro do modelo de receita em 2022),
    reescala ao total de válidos e redistribui as cadeiras. Repete `amostras`
    vezes e agrega:

    - `mediana`: cadeiras medianas por legenda;
    - `frequencia`: quantas vezes cada legenda teve cada número de cadeiras
      (para desenhar a banda de incerteza);
    - `probabilidade_eleger`: fração dos sorteios em que a legenda ficou com
      ao menos 1 cadeira.

    O ruído é independente por legenda — a hipótese honesta, já que não temos
    matriz de correlação entre legendas em SC. Isso ALARGA a banda de cadeiras
    (o erro de uma legenda não compensa o da outra), a leitura conservadora.

    O ruído só atinge a parcela ESTIMADA de cada legenda (`sinal_efetivo`), não
    a votação de 2022, que é medida e não tem erro de estimativa. E o desvio
    encolhe com o número de candidatos que alimentam o sinal: a soma de n
    estimativas independentes tem erro relativo σ/√n, então uma legenda com um
    único candidato declarando receita é muito mais incerta do que uma com dez.
    """
    est = estimativas(con)
    if not est["legendas"]:
        return {"erro": "base de 2022 não carregada"}
    ajustes = ajustes or {}
    alvo = int(validos_esperados or est["validos_2022"] or 0)
    misto, fonte, confianca, sinal_efetivo = _cenario_votos(
        est, cenario, ajustes, votos_absolutos)

    legendas = list(misto.keys())
    rng = random.Random(semente)
    sigma = calibracao.SIGMA_LOG_RESIDUAL

    # Quantos candidatos alimentam o sinal de cada legenda: define o desvio do
    # sinal (σ/√n). Um candidato só = incerteza máxima; muitos = erros se
    # compensam.
    def _n_sinal(leg: str) -> int:
        d = est["legendas"].get(leg, {})
        if cenario == "receita":
            return d.get("n_receita") or 0
        if cenario == "seguidores":
            return d.get("acompanhados") or 0
        if cenario == "unificado":
            # Receita e seguidores vêm, em grande parte, do MESMO conjunto de
            # candidatos (o acompanhado que declara receita). Somar os dois
            # inflaria n e estreitaria a banda de forma enganosa. O teto é o
            # número de acompanhados, que é o maior conjunto independente real.
            return max(d.get("n_receita") or 0, d.get("acompanhados") or 0)
        return 0

    contagem = {leg: 0 for leg in legendas}          # quantas vezes teve ≥1 cadeira
    soma_cadeiras = {leg: 0 for leg in legendas}
    hist = {leg: {} for leg in legendas}             # {n_cadeiras: vezes}

    for _ in range(amostras):
        brutos: dict[str, float] = {}
        for leg, v in misto.items():
            parcela_sinal = sinal_efetivo.get(leg, 0.0)
            if parcela_sinal <= 0:
                # Sem parcela estimada (base2022 puro ou manual): não há ruído.
                brutos[leg] = max(0.0, v)
                continue
            n = max(1, _n_sinal(leg))
            sigma_sinal = sigma / math.sqrt(n)
            ruido = math.exp(rng.gauss(0.0, sigma_sinal))
            # Só a parcela estimada oscila; a base de 2022 fica fixa.
            base_fixa = v - parcela_sinal
            brutos[leg] = max(0.0, base_fixa + parcela_sinal * ruido)
        soma = sum(brutos.values())
        escala = (alvo / soma) if soma > 0 and alvo > 0 else 1.0
        votos = {leg: round(v * escala) for leg, v in brutos.items()}
        cadeiras = distribuir(votos, lugares)["cadeiras"]
        for leg in legendas:
            n = cadeiras.get(leg, 0)
            soma_cadeiras[leg] += n
            hist[leg][n] = hist[leg].get(n, 0) + 1
            if n >= 1:
                contagem[leg] += 1

    def _mediana_de_hist(h: dict[int, int]) -> int:
        metade = amostras / 2
        acu = 0
        for n in sorted(h):
            acu += h[n]
            if acu >= metade:
                return n
        return 0

    mediana = {leg: _mediana_de_hist(hist[leg]) for leg in legendas}

    por_legenda = {}
    for leg in legendas:
        freq = [{"cadeiras": n, "vezes": hist[leg].get(n, 0)}
                for n in range(0, lugares + 1) if hist[leg].get(n, 0)]
        d = {
            "mediana": mediana[leg],
            "media": round(soma_cadeiras[leg] / amostras, 2),
            "frequencia": freq,
            "probabilidade_eleger": round(contagem[leg] / amostras, 4),
        }
        # Banda agregada: percentis 5 e 95 da distribuição de cadeiras.
        total = amostras
        acu = 0
        p5 = p95 = None
        for n in range(0, lugares + 1):
            acu += hist[leg].get(n, 0)
            if p5 is None and acu >= total * 0.05:
                p5 = n
            if p95 is None and acu >= total * 0.95:
                p95 = n
        d["p5"] = p5 if p5 is not None else 0
        d["p95"] = p95 if p95 is not None else lugares
        por_legenda[leg] = d

    return {
        "cenario": cenario,
        "amostras": amostras,
        "validos_esperados": alvo,
        "legendas": por_legenda,
        "cadeiras_2022": cadeiras_2022_em_2026(con),
        "fonte_por_legenda": fonte,
        "confianca_por_legenda": confianca,
        "sigma_log": sigma,
    }


def momento_por_legenda(con, desde: str, ate: str) -> dict[str, dict]:
    """Crescimento de seguidores agregado por legenda, no período.

    É um INDÍCIO de momento, não uma conversão em voto. A tela mostra o número
    e deixa o usuário decidir quanto disso vira ajuste — de propósito.
    """
    linhas = con.execute("""
        SELECT p.partido,
               SUM(CASE WHEN s.semana = (SELECT MIN(semana) FROM snapshots
                                          WHERE perfil_id = p.id AND semana >= ?)
                        THEN s.seguidores ELSE 0 END) AS inicio,
               SUM(CASE WHEN s.semana = (SELECT MAX(semana) FROM snapshots
                                          WHERE perfil_id = p.id AND semana <= ?)
                        THEN s.seguidores ELSE 0 END) AS fim,
               COUNT(DISTINCT p.id) AS perfis
          FROM perfis p JOIN snapshots s ON s.perfil_id = p.id
         WHERE p.acompanhar = 1 AND p.partido IS NOT NULL
         GROUP BY p.partido
    """, (desde, ate)).fetchall()

    por_legenda: dict[str, dict] = {}
    for r in linhas:
        leg = sigla_para_legenda(r["partido"])
        d = por_legenda.setdefault(leg, {"inicio": 0, "fim": 0, "perfis": 0,
                                          "siglas": []})
        d["inicio"] += r["inicio"] or 0
        d["fim"] += r["fim"] or 0
        d["perfis"] += r["perfis"]
        d["siglas"].append(r["partido"])
    for d in por_legenda.values():
        d["crescimento_pct"] = (round((d["fim"] - d["inicio"]) / d["inicio"] * 100, 2)
                                if d["inicio"] else None)
    return por_legenda


# ── nominata ─────────────────────────────────────────────────────────────────

def enriquecer_financeiro(con, linhas: list[dict]) -> list[dict]:
    """Acrescenta o dinheiro e os votos estimados a linhas de qualquer partido.

    Cada linha usa o custo por voto e a razão votos/seguidor da SUA legenda —
    por isso serve tanto para a nominata de um partido quanto para o ranking
    geral, onde as linhas vêm misturadas.

    Estimativa por candidato: receita 2026 convertida pela elasticidade
    (retornos decrescentes) ou, sem receita, seguidores × razão da legenda —
    ambos limitados pelo teto da SUA legenda (cai no global onde não há
    histórico). A fonte fica gravada em `votos_estimados_fonte` porque as duas
    não valem o mesmo e a tela precisa dizer qual usou.
    """
    custos_leg, custo_geral = custo_voto_por_legenda(con)
    razoes_leg, razao_geral = razao_votos_seguidor_por_legenda(con)
    receitas = receita_2026_por_perfil(con)
    receita_2022 = {r["perfil_id"]: r["receita"] for r in con.execute(
        "SELECT perfil_id, receita FROM v2_financeiro WHERE ano=2022")}
    teto_geral = teto_votos_candidato(con)

    for d in linhas:
        legenda = sigla_para_legenda(d.get("partido") or "")
        custo_legenda = custos_leg.get(legenda, custo_geral)
        razao_legenda = razoes_leg.get(legenda, razao_geral)
        # Cap individual é o teto global do cargo — o máximo que UM candidato
        # a deputado estadual já teve em SC. O teto da legenda limita a SOMA
        # (em `estimativas()`), não cada candidato individualmente, para que
        # o bônus de incumbência e a conversão por seguidor não sejam anulados
        # pelo próprio recorde do partido.

        rec26 = receitas.get(d["id"], 0.0)
        rec22 = receita_2022.get(d["id"])
        hist = d.get("historico") or {}
        votos22 = hist.get("votos")
        mesmo_cargo = bool(hist.get("mesmo_cargo"))
        eleito_mesmo_cargo = (mesmo_cargo and
                              "ELEITO" in (hist.get("situacao") or "").upper())
        custo_proprio = (round(rec22 / votos22, 2)
                         if rec22 and votos22 else None)
        d["receita_2026"] = round(rec26, 2) if rec26 else 0.0
        d["receita_2022"] = rec22
        d["custo_voto_2022"] = custo_proprio
        d["eleito_mesmo_cargo"] = eleito_mesmo_cargo
        d["votos_estimados"], d["votos_estimados_fonte"] = estimar_votos_candidato(
            seguidores=d.get("seguidores"), razao=razao_legenda,
            receita=rec26, custo_voto=custo_proprio or custo_legenda,
            # Só o voto do MESMO cargo é evidência direta; o de prefeito não é.
            voto_anterior=votos22 if mesmo_cargo else None,
            teto=teto_geral, eleito_mesmo_cargo=eleito_mesmo_cargo)
        faixa = faixa_votos_candidato(
            rec26, votos22 if mesmo_cargo else None,
            eleito_mesmo_cargo=eleito_mesmo_cargo)
        if faixa and d["votos_estimados"] is not None:
            d["votos_estimados_min"] = faixa[0]
            d["votos_estimados_max"] = faixa[1]
    return linhas


def ranking_nominata(con, partido: str, desde: str | None = None) -> list[dict]:
    """Ordena os candidatos de UM partido pela chance de ficar no topo da lista.

    Dentro do partido a regra é só uma: mais votos, mais alto. Como não temos
    pesquisa de voto, o que existe aqui é um ordenamento por sinais — e a
    confiança de cada linha é marcada, porque para quem nunca disputou nada o
    único sinal é o Instagram, que é o previsor fraco.

    A ORDEM é por votos estimados, com desempate por voto anterior de deputado
    estadual e depois por seguidores. Antes a lista saía ordenada por
    seguidores enquanto o cabeçalho prometia votos: quem lia via um ranking de
    audiência acreditando estar vendo um ranking de urna.
    """
    from politicos import metricas

    linhas = metricas.resumo_perfis(con, desde=desde or "2026-01-01", partido=partido)
    linhas = metricas.com_cobertura(linhas)
    enriquecer_financeiro(con, linhas)

    for d in linhas:
        sinais = sum(x is not None for x in
                     (d["por_seguidor"], d["crescimento"], d["frequencia"]))
        if d["posts"] == 0:
            d["confianca"] = "sem dados"
        elif sinais >= 3 and d["posts"] >= 20:
            d["confianca"] = "média"
        else:
            d["confianca"] = "baixa"
        # Nunca "alta": sem histórico eleitoral não há previsor forte.

    return ordenar_nominata(linhas)


def ordenar_nominata(linhas: list[dict]) -> list[dict]:
    """Votos estimados, depois voto anterior de estadual, depois seguidores."""
    def chave(d: dict) -> tuple:
        h = d.get("historico") or {}
        anterior = h.get("votos") or 0 if h.get("mesmo_cargo") else 0
        return (-(d.get("votos_estimados") or 0), -anterior,
                -(d.get("seguidores") or 0))
    return sorted(linhas, key=chave)


# ── cores das legendas ───────────────────────────────────────────────────────
#
# NÃO são as cores de marca dos partidos. As de marca reprovam no teste de
# daltonismo — MDB verde ao lado do vermelho do PT fica indistinguível para
# deuteranopia, que é 6% dos homens. Esta sequência passou no validador
# (`scripts/validate_palette.js`, modo claro) na ORDEM em que o hemiciclo
# desenha, que é por número de cadeiras. Mexer na ordem exige revalidar.
#
# A cor nunca é a informação sozinha: cada bloco do hemiciclo tem rótulo direto
# e a tabela ao lado traz os números.
CORES = {
    "PL":                                        "#2a78d6",
    "MDB":                                       "#e34948",
    "Federação Brasil da Esperança - FE BRASIL": "#1baf7a",
    "PSD":                                       "#eda100",
    "PP":                                        "#e87ba4",
    "UNIÃO":                                     "#008300",
    "Federação PSDB Cidadania":                  "#4a3aa7",
    "NOVO":                                      "#eb6834",
    # Legendas com cadeira em 2022 que caíam todas no mesmo cinza, o que no
    # hemiciclo dava a impressão falsa de um bloco único. Matizes e claridades
    # separadas para continuarem distinguíveis em daltonismo.
    "PODE":                                      "#00767a",
    "REPUBLICANOS":                              "#8a6d3b",
    "PDT":                                       "#0aa3c2",
    "Federação PSOL REDE":                       "#5f0f40",
    "PTB":                                       "#4a4e69",
    "PSB":                                       "#7d4f50",
    "PATRIOTA":                                  "#57534e",
    "MISSÃO":                                    "#b5179e",
    # Federações de 2026 herdam a cor do maior sócio (UNIÃO e PTB→PRD), para a
    # ordem validada do hemiciclo mudar o mínimo possível.
    "Federação União Progressista":              "#008300",
    "Federação Renovação Solidária":             "#4a4e69",
}
COR_OUTROS = "#9ca3af"


def cor_da_legenda(legenda: str) -> str:
    return CORES.get(legenda, COR_OUTROS)
