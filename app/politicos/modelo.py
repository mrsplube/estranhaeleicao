"""Algoritmo v2 da previsão de votos (deputado estadual SC) — aprendido com 2026.

    venv/bin/python -m politicos.modelo comparar   # validação cruzada de cada variante
    venv/bin/python -m politicos.modelo treinar    # ajusta no conjunto inteiro e grava (v2_modelo)
    venv/bin/python -m politicos.modelo proxima    # aplica o modelo de hoje à próxima eleição

**O conjunto de treino é honesto por construção.** A previsão congelada de
04/10/2026 (`v2_previsao` #1) guardou, de cada um dos 398 candidatos, o que se
sabia ANTES da apuração: receita declarada ao TSE até aquela manhã, Instagram,
voto de 2022, mandato. O resultado vem de `politicos/data/eleicoes.db`. Nenhuma
variável aqui conhece o resultado.

**Cada variante é medida fora da amostra.** Validação cruzada (10 partes × 5
repetições): o voto de cada candidato é previsto por um modelo que não o viu.
Daí saem R² e postos (Spearman) do voto, e — o que importa para quem contrata —
quantos dos 40 eleitos cada variante acerta e quantas cadeiras erra por lista,
rodando a lei inteira (`eleicao.distribuir`) sobre os votos previstos, com o voto
de legenda de cada lista no tamanho de 2022 (o que se sabia antes). A
probabilidade de eleição sai de um Monte Carlo com o erro medido fora da
amostra, e é julgada pelo Brier.

**Duas variantes servem a dois momentos.** Perto da eleição a receita existe e
manda (`completo`); nos quatro anos antes dela não existe, e o que há é o voto da
eleição anterior, o mandato e o monitor de redes (`sem_receita`). É a segunda que
alimenta a previsão contínua da próxima eleição (`proxima`).

Variável faltante não é zero: candidato sem coleta de posts recebe a média e uma
marca (`sem_posts`), porque a coleta de posts foi comprada só para os perfis
prioritários — e ser prioritário já diz algo.
"""
from __future__ import annotations

import json
import math
import random
import sqlite3
import sys
from datetime import date, timedelta
from statistics import correlation

from politicos import db, eleicao, microdados

ANO_TREINO = 2026
PARTE_LEGENDA_PADRAO = 0.055        # 2022: 220.062 de 4.004.036 válidos

# ── variáveis ───────────────────────────────────────────────────────────────
def _log(x) -> float:
    return math.log1p(max(0.0, float(x or 0)))


TRANSFORMACOES = {
    "log_receita": lambda c: _log(c.get("receita")),
    "sem_receita": lambda c: 1.0 if (c.get("receita") or 0) < 1000 else 0.0,
    "incumbente": lambda c: 1.0 if c.get("incumbente") else 0.0,
    "log_voto_anterior": lambda c: _log(c.get("voto_anterior")),
    "estreante": lambda c: 0.0 if (c.get("voto_anterior") or 0) > 0 else 1.0,
    "log_voto_outro_cargo": lambda c: _log(c.get("voto_outro_cargo")),
    "log_seguidores": lambda c: _log(c.get("seguidores")),
    "sem_perfil": lambda c: 0.0 if c.get("seguidores") else 1.0,
    "log_posts": lambda c: _log(c.get("posts")),
    "sem_posts": lambda c: 0.0 if c.get("posts") else 1.0,
    "engajamento": lambda c: min(float(c.get("engajamento") or 0), 8.0),
    "crescimento": lambda c: max(-50.0, min(float(c.get("crescimento") or 0), 100.0)) / 100,
    "log_lista_anterior": lambda c: _log(c.get("lista_anterior")),
    "fatia_receita_lista": lambda c: float(c.get("fatia_receita_lista") or 0),
    "fatia_voto_lista": lambda c: float(c.get("fatia_voto_lista") or 0),
}
ROTULOS = {
    "log_receita": "Receita de campanha (log)", "sem_receita": "Sem receita declarada",
    "incumbente": "Deputado em exercício", "log_voto_anterior": "Voto na eleição anterior (log)",
    "estreante": "Estreante no cargo", "log_voto_outro_cargo": "Voto anterior em outro cargo (log)",
    "log_seguidores": "Seguidores no Instagram (log)", "sem_perfil": "Sem Instagram acompanhado",
    "log_posts": "Posts no ano (log)", "sem_posts": "Sem coleta de posts",
    "engajamento": "Engajamento por seguidor", "crescimento": "Crescimento de seguidores",
    "log_lista_anterior": "Voto da lista na eleição anterior (log)",
    "fatia_receita_lista": "Fatia da receita da própria lista",
    "fatia_voto_lista": "Fatia do voto anterior da própria lista",
}
_REDES = ["log_seguidores", "sem_perfil", "log_posts", "sem_posts", "engajamento", "crescimento"]
_HISTORICO = ["incumbente", "log_voto_anterior", "estreante", "log_voto_outro_cargo"]
_LISTA = ["log_lista_anterior"]
VARIANTES = {
    "receita": ["log_receita", "sem_receita", "incumbente"],
    "receita_historico": ["log_receita", "sem_receita"] + _HISTORICO,
    "completo": ["log_receita", "sem_receita"] + _HISTORICO + _REDES,
    "completo_lista": ["log_receita", "sem_receita", "fatia_receita_lista"] + _HISTORICO + _REDES + _LISTA,
    "sem_receita": _HISTORICO + _REDES,
    "sem_receita_lista": _HISTORICO + _REDES + _LISTA + ["fatia_voto_lista"],
    "so_historico": _HISTORICO,
    "so_redes": ["incumbente"] + _REDES,
}
DESCRICAO = {
    "receita": "Só receita e mandato (a regressão de 2022 refeita)",
    "receita_historico": "Receita + voto anterior + mandato",
    "completo": "Receita + voto anterior + mandato + Instagram",
    "sem_receita": "Voto anterior + mandato + Instagram (serve longe da eleição)",
    "so_historico": "Só voto anterior e mandato",
    "so_redes": "Só Instagram e mandato",
    "completo_lista": "Completo + tamanho da lista e fatia do candidato na receita dela",
    "sem_receita_lista": "Sem receita + tamanho da lista e fatia do candidato no voto anterior dela",
}


# ── dados ───────────────────────────────────────────────────────────────────
def receitas_mais_recentes() -> tuple[str | None, dict[int, float]]:
    """A foto semanal mais recente da prestação de contas 2026 (perfil_id → R$).

    O cron `tse-financeiro` grava uma por semana (segunda, 06h40). Até 03/11/2026
    ela ainda cresce; dali em diante é a prestação FINAL."""
    con = db.conectar()
    try:
        r = con.execute("""SELECT MAX(semana) s FROM v2_receitas_semana
                            WHERE fonte = 'tse-prestacao-2026'""").fetchone()
        if not r or not r["s"]:
            return None, {}
        return r["s"], {x["perfil_id"]: x["receita_acumulada"] or 0.0 for x in con.execute(
            "SELECT perfil_id, receita_acumulada FROM v2_receitas_semana WHERE semana = ?", (r["s"],))}
    finally:
        con.close()


PRESTACAO_FINAL = "2026-11-04"     # 30 dias depois da eleição (prazo da prestação final)


def dados_treino(receita: str = "vespera") -> tuple[list[dict], dict[str, float]]:
    """Os candidatos da foto congelada, com o resultado ao lado.

    `receita="vespera"` (padrão) é a declarada até a manhã de 04/10 — a única que
    existe antes de uma eleição, e por isso a que treina o modelo de produção.
    `receita="atual"` troca pela foto semanal mais recente (a final, depois de
    03/11): serve para medir o custo real do voto, não para prever."""
    con = db.conectar()
    try:
        prev = con.execute("SELECT id, resumo_json FROM v2_previsao ORDER BY id LIMIT 1").fetchone()
        partes = json.loads(prev["resumo_json"]).get("premissas", {}).get("parte_legenda_2022", {})
        foto = [dict(r) for r in con.execute("SELECT * FROM v2_previsao_candidato WHERE previsao_id = ?", (prev["id"],))]
    finally:
        con.close()
    md = microdados.conectar(leitura=True)
    try:
        res = {r["sq"]: dict(r) for r in md.execute(
            "SELECT sq, votos, eleito, valido, agremiacao FROM candidato WHERE ano = ? AND cargo = 7", (ANO_TREINO,))}
    finally:
        md.close()
    atual = receitas_mais_recentes()[1] if receita == "atual" else {}
    linhas = []
    for f in foto:
        r = res.get(f["sq"])
        if not r or not r["valido"]:
            continue
        linhas.append({"sq": f["sq"], "nome": f["nome_urna"], "agremiacao": r["agremiacao"],
                       "perfil_id": f["perfil_id"],
                       "receita": atual.get(f["perfil_id"], f["receita_2026"]) if atual else f["receita_2026"],
                       "incumbente": f["incumbente"],
                       "voto_anterior": f["votos_2022"], "voto_outro_cargo": f["votos_2022_outro_cargo"],
                       "seguidores": f["seguidores"], "posts": f["posts"], "engajamento": f["engaj_seguidor"],
                       "crescimento": f["crescimento"], "votos": r["votos"] or 0, "eleito": bool(r["eleito"])})
    _contexto_da_lista(linhas, listas_anteriores(ANO_TREINO - 4))
    return linhas, partes


def listas_anteriores(ano: int, cargo: int = 7) -> dict[str, int]:
    """Votos de cada lista (agremiação de HOJE) na eleição de `ano` — o que se sabe antes."""
    from politicos import analise_eleitoral as ae
    b = ae._base(ano, cargo)
    soma: dict[str, int] = {}
    for n, c in b["cands"].items():
        if c["valido"]:
            a = ae.em_2026(c["partido"])
            soma[a] = soma.get(a, 0) + sum(b["votos"].get(n, {}).values())
    for p, mun in b["legenda"].items():
        if p in b["partidos"]:
            a = ae.em_2026(b["partidos"][p][0])
            soma[a] = soma.get(a, 0) + sum(mun.values())
    return soma


def _contexto_da_lista(linhas: list[dict], anteriores: dict[str, int]) -> None:
    """Tamanho da lista na eleição anterior e a fatia do candidato dentro dela."""
    rec: dict[str, float] = {}
    ant: dict[str, float] = {}
    for c in linhas:
        rec[c["agremiacao"]] = rec.get(c["agremiacao"], 0) + float(c.get("receita") or 0)
        ant[c["agremiacao"]] = ant.get(c["agremiacao"], 0) + float(c.get("voto_anterior") or 0)
    for c in linhas:
        a = c["agremiacao"]
        c["lista_anterior"] = anteriores.get(a, 0)
        c["fatia_receita_lista"] = (float(c.get("receita") or 0) / rec[a]) if rec.get(a) else 0.0
        c["fatia_voto_lista"] = (float(c.get("voto_anterior") or 0) / ant[a]) if ant.get(a) else 0.0


def _matriz(linhas: list[dict], variaveis: list[str]):
    import numpy as np
    return np.array([[TRANSFORMACOES[v](c) for v in variaveis] for c in linhas], dtype=float)


# ── ajuste: regressão ridge sobre variáveis padronizadas ────────────────────
def ajustar(X, y, lam: float) -> dict:
    import numpy as np
    media = X.mean(axis=0)
    dp = X.std(axis=0)
    dp[dp == 0] = 1.0
    Z = (X - media) / dp
    A = np.column_stack([np.ones(len(y)), Z])
    pen = lam * np.eye(A.shape[1])
    pen[0, 0] = 0.0
    beta = np.linalg.solve(A.T @ A + pen, A.T @ y)
    res = y - A @ beta
    return {"beta": beta, "media": media, "dp": dp, "sigma": float(res.std(ddof=A.shape[1]) if len(y) > A.shape[1] else res.std())}


def prever(m: dict, X):
    import numpy as np
    Z = (X - m["media"]) / m["dp"]
    return np.column_stack([np.ones(len(Z)), Z]) @ m["beta"]


# ── a lei sobre votos previstos ─────────────────────────────────────────────
def cadeiras_e_eleitos(linhas: list[dict], votos: list[float], partes: dict[str, float],
                       vagas: int = eleicao.CADEIRAS_ALESC) -> tuple[dict[str, int], set[str]]:
    listas: dict[str, list[tuple[float, str]]] = {}
    for c, v in zip(linhas, votos):
        listas.setdefault(c["agremiacao"], []).append((max(0.0, v), c["sq"]))
    totais = {a: sum(v for v, _ in l) / (1 - min(0.5, partes.get(a, PARTE_LEGENDA_PADRAO)))
              for a, l in listas.items()}
    r = eleicao.distribuir({a: round(t) for a, t in totais.items()}, vagas,
                           candidatos={a: [round(v) for v, _ in l] for a, l in listas.items()},
                           validos=round(sum(totais.values())))
    eleitos = set()
    for a, l in listas.items():
        eleitos.update(sq for _v, sq in sorted(l, reverse=True)[:r["cadeiras"].get(a, 0)])
    return r["cadeiras"], eleitos


def _na_lista(linhas: list[dict], votos: list[float], nominal: dict[str, int]) -> list[float]:
    """Reescala os votos previstos para que cada lista some o voto nominal dado."""
    soma: dict[str, float] = {}
    for c, v in zip(linhas, votos):
        soma[c["agremiacao"]] = soma.get(c["agremiacao"], 0) + max(0.0, v)
    return [max(0.0, v) * nominal.get(c["agremiacao"], 0) / soma[c["agremiacao"]] if soma.get(c["agremiacao"]) else 0.0
            for c, v in zip(linhas, votos)]


# ── tamanho das listas: meio a meio ─────────────────────────────────────────
# A soma das previsões individuais acerta melhor que qualquer sinal isolado o
# tamanho de cada lista (1,44 p.p. de erro médio em 2026), mas exagera quem tem
# muitos nomes fortes (PL 21 cadeiras; foram 16). O voto da lista na eleição
# anterior erra para o outro lado (PL 10). Meio a meio: 1,00 p.p. e 6 cadeiras
# erradas em vez de 12, PL 16. O peso foi fixado ANTES de olhar — o melhor
# medido em 2026 (60/40 geométrico, 4 cadeiras erradas) seria ajuste ao acaso.
PESO_LISTA_ANTERIOR = 0.5


def fatias_das_listas(linhas: list[dict], votos: list[float], anteriores: dict[str, float]) -> dict[str, float]:
    """Fatia de cada lista: metade pela soma dos seus candidatos previstos, metade
    pelo voto que a lista teve na eleição anterior. Lista nova (sem anterior) fica
    só com a soma."""
    soma: dict[str, float] = {}
    for c, v in zip(linhas, votos):
        soma[c["agremiacao"]] = soma.get(c["agremiacao"], 0.0) + max(0.0, v)
    tot_s = sum(soma.values()) or 1.0
    tot_a = sum(max(0.0, anteriores.get(a, 0)) for a in soma) or 0.0
    f = {}
    for a, s in soma.items():
        ant = max(0.0, anteriores.get(a, 0))
        f[a] = ((1 - PESO_LISTA_ANTERIOR) * s / tot_s + PESO_LISTA_ANTERIOR * ant / tot_a) if tot_a and ant else s / tot_s
    t = sum(f.values()) or 1.0
    return {a: x / t for a, x in f.items()}


def com_tamanho_de_lista(linhas: list[dict], votos: list[float], anteriores: dict[str, float] | None,
                         total: float | None = None) -> list[float]:
    """Votos reescalados: cada lista com a fatia meio a meio; dentro dela, a
    proporção prevista entre os candidatos. Sem `anteriores`, devolve como veio."""
    if not anteriores:
        return votos
    f = fatias_das_listas(linhas, votos, anteriores)
    tot = total if total is not None else sum(max(0.0, v) for v in votos)
    return _na_lista(linhas, votos, {a: x * tot for a, x in f.items()})


def monte_carlo(linhas, log_pred, sigma: float, partes, amostras: int = 600, semente: int = 7,
                anteriores: dict[str, float] | None = None, total: float | None = None) -> list[float]:
    rnd = random.Random(semente)
    conta = [0] * len(linhas)
    for _ in range(amostras):
        votos = [math.expm1(lp + rnd.gauss(0, sigma)) for lp in log_pred]
        votos = com_tamanho_de_lista(linhas, votos, anteriores, total)
        _cad, eleitos = cadeiras_e_eleitos(linhas, votos, partes)
        for i, c in enumerate(linhas):
            if c["sq"] in eleitos:
                conta[i] += 1
    return [k / amostras for k in conta]


# ── validação cruzada ───────────────────────────────────────────────────────
def validar(linhas, partes, variaveis: list[str], lam: float, partes_cv: int = 10, reps: int = 5,
            com_mc: bool = True, anteriores: dict[str, float] | None = None) -> dict:
    """Métricas fora da amostra. `eleitos_certos`/`cadeiras_erradas`/`brier` são do
    método de produção — listas meio a meio quando há `anteriores`; as `*_soma`
    são as de antes (tamanho da lista = soma dos candidatos), para comparar."""
    import numpy as np
    X = _matriz(linhas, variaveis)
    y = np.array([math.log1p(c["votos"]) for c in linhas])
    n = len(linhas)
    soma = np.zeros(n)
    residuos = []
    for rep in range(reps):
        idx = list(range(n))
        random.Random(100 + rep).shuffle(idx)
        oof = np.zeros(n)
        for k in range(partes_cv):
            teste = idx[k::partes_cv]
            treino = [i for i in idx if i not in set(teste)]
            m = ajustar(X[treino], y[treino], lam)
            oof[teste] = prever(m, X[teste])
        soma += oof
        residuos.extend((y - oof).tolist())
    pred = soma / reps
    sigma = float(np.std(residuos))
    r2 = 1 - float(((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())
    votos_prev = [math.expm1(p) for p in pred]
    cad_real: dict[str, int] = {}
    for c in linhas:
        if c["eleito"]:
            cad_real[c["agremiacao"]] = cad_real.get(c["agremiacao"], 0) + 1
    eleitos_real = {c["sq"] for c in linhas if c["eleito"]}

    def placar(votos):
        cad, eleitos = cadeiras_e_eleitos(linhas, votos, partes)
        return (len(eleitos & eleitos_real),
                sum(abs(cad.get(a, 0) - cad_real.get(a, 0)) for a in set(cad) | set(cad_real)), cad)
    e_soma, c_soma, _ = placar(votos_prev)
    e_lista, c_lista, cad_lista = placar(com_tamanho_de_lista(linhas, votos_prev, anteriores))
    saida = {"variaveis": variaveis, "lambda": lam, "r2": round(r2, 3),
             "spearman": round(correlation(pred.tolist(), y.tolist(), method="ranked"), 3),
             "erro_tipico": round(math.exp(float(np.median(np.abs(y - pred)))), 2),
             "sigma": round(sigma, 3),
             "eleitos_certos": e_lista, "cadeiras_erradas": c_lista,
             "eleitos_certos_soma": e_soma, "cadeiras_erradas_soma": c_soma,
             "cadeiras_previstas": cad_lista}
    if com_mc:
        ys = [1.0 if c["eleito"] else 0.0 for c in linhas]
        ps_soma = monte_carlo(linhas, pred.tolist(), sigma, partes)
        ps = monte_carlo(linhas, pred.tolist(), sigma, partes, anteriores=anteriores) if anteriores else ps_soma
        saida["brier_soma"] = round(sum((p - y_) ** 2 for p, y_ in zip(ps_soma, ys)) / n, 4)
        saida["brier"] = round(sum((p - y_) ** 2 for p, y_ in zip(ps, ys)) / n, 4)
        saida["_ps"] = ps                 # para a recalibração (não vai para o banco)
    return saida


# ── recalibração das probabilidades (Platt) ─────────────────────────────────
FAIXAS_PROB = ((0, .05), (.05, .2), (.2, .4), (.4, .6), (.6, .8), (.8, .95), (.95, 1.01))


def _logit(p: float) -> float:
    p = min(max(p, 0.002), 0.998)
    return math.log(p / (1 - p))


def ajustar_platt(ps: list[float], ys: list[float]) -> tuple[float, float]:
    """y ~ σ(a + b·logit(p)), por Newton-Raphson. Dois números, nada além."""
    import numpy as np
    X = np.column_stack([np.ones(len(ps)), [_logit(p) for p in ps]])
    y = np.array(ys, dtype=float)
    w = np.array([0.0, 1.0])
    for _ in range(50):
        mu = 1 / (1 + np.exp(-(X @ w)))
        g = X.T @ (y - mu)
        H = X.T @ (X * (mu * (1 - mu))[:, None]) + 1e-6 * np.eye(2)
        passo = np.linalg.solve(H, g)
        w = w + passo
        if float(np.abs(passo).max()) < 1e-8:
            break
    return float(w[0]), float(w[1])


def recalibracao_vale(cal: dict | None) -> bool:
    """A correção só entra se melhorou o Brier FORA da amostra. Em 2026 piorou
    (0,0454 → 0,0479 no completo): as chances do v2 já saem calibradas, e a faixa
    do meio subestimada era da foto congelada, que usava outro modelo."""
    return bool(cal) and cal["brier_depois"] < cal["brier_antes"]


def _platt(p: float, a: float, b: float) -> float:
    return 1 / (1 + math.exp(-(a + b * _logit(p))))


def calibrar(p: float, cal: dict | None) -> float:
    """A chance que vai para a tela: corrigida só se a correção provou que ajuda."""
    return _platt(p, cal["a"], cal["b"]) if recalibracao_vale(cal) else p


def faixas(ps: list[float], ys: list[float]) -> list[dict]:
    saida = []
    for lo, hi in FAIXAS_PROB:
        dentro = [(p, y) for p, y in zip(ps, ys) if lo <= p < hi]
        if dentro:
            saida.append({"faixa": f"{round(lo * 100)}–{min(100, round(hi * 100))}%", "candidatos": len(dentro),
                          "media_prevista": round(100 * sum(p for p, _ in dentro) / len(dentro), 1),
                          "eleitos_pct": round(100 * sum(y for _, y in dentro) / len(dentro), 1)})
    return saida


def recalibracao(ps: list[float], ys: list[float], partes_cv: int = 10) -> dict:
    """Recalibra e mede FORA da amostra: cada candidato recebe a correção ajustada
    nos outros 90%. Os dois números finais (a, b) são ajustados em todos."""
    idx = list(range(len(ps)))
    random.Random(11).shuffle(idx)
    cal_oof = [0.0] * len(ps)
    for k in range(partes_cv):
        teste = set(idx[k::partes_cv])
        a, b = ajustar_platt([ps[i] for i in idx if i not in teste], [ys[i] for i in idx if i not in teste])
        for i in teste:
            cal_oof[i] = _platt(ps[i], a, b)
    a, b = ajustar_platt(ps, ys)
    brier = lambda xs: round(sum((p - y) ** 2 for p, y in zip(xs, ys)) / len(ys), 4)
    return {"a": round(a, 4), "b": round(b, 4), "brier_antes": brier(ps), "brier_depois": brier(cal_oof),
            "faixas_antes": faixas(ps, ys), "faixas_depois": faixas(cal_oof, ys)}


RECALIBRADAS = ("completo", "sem_receita")      # as duas que servem à produção


def comparar(lambdas=(0.0, 1.0, 5.0, 20.0)) -> dict:
    linhas, partes = dados_treino()
    anteriores = listas_anteriores(ANO_TREINO - 4)
    ys = [1.0 if c["eleito"] else 0.0 for c in linhas]
    variantes = []
    for nome, vs in VARIANTES.items():
        melhor = None
        for lam in lambdas:
            r = validar(linhas, partes, vs, lam, com_mc=False)
            if melhor is None or r["r2"] > melhor["r2"]:
                melhor = r
        melhor = validar(linhas, partes, vs, melhor["lambda"], com_mc=True, anteriores=anteriores)
        ps = melhor.pop("_ps")
        if nome in RECALIBRADAS:
            melhor["calibracao"] = recalibracao(ps, ys)
        variantes.append({"nome": nome, "descricao": DESCRICAO[nome], **melhor})
    variantes.sort(key=lambda v: (-v["eleitos_certos"], v["cadeiras_erradas"], -v["r2"]))
    cad_real: dict[str, int] = {}
    for c in linhas:
        if c["eleito"]:
            cad_real[c["agremiacao"]] = cad_real.get(c["agremiacao"], 0) + 1
    return {"n": len(linhas), "eleitos": sum(1 for c in linhas if c["eleito"]), "variantes": variantes,
            "foto_congelada": _foto_congelada(), "listas": _sinais_de_lista(linhas, anteriores),
            "cadeiras_reais": cad_real, "peso_lista_anterior": PESO_LISTA_ANTERIOR}


def _sinais_de_lista(linhas: list[dict], anteriores: dict[str, float]) -> list[dict]:
    """Cada sinal de tamanho de lista sozinho, contra o real — a tabela que justifica o meio a meio."""
    import numpy as np
    from politicos import analise_eleitoral as ae
    votos_reais, _l, _v = ae._quadro(ANO_TREINO, 7)
    listas = sorted({c["agremiacao"] for c in linhas})

    def fat(d):
        t = sum(max(0.0, d.get(a, 0)) for a in listas) or 1.0
        return {a: max(0.0, d.get(a, 0)) / t for a in listas}

    def soma(chave):
        s: dict[str, float] = {}
        for c in linhas:
            s[c["agremiacao"]] = s.get(c["agremiacao"], 0) + float(c.get(chave) or 0)
        return fat(s)
    X = _matriz(linhas, VARIANTES["completo"])
    y = np.array([math.log1p(c["votos"]) for c in linhas])
    oof = np.zeros(len(linhas))
    idx = list(range(len(linhas)))
    random.Random(100).shuffle(idx)
    for k in range(10):
        te = idx[k::10]
        tr = [i for i in idx if i not in set(te)]
        oof[te] = prever(ajustar(X[tr], y[tr], 0.0), X[te])
    cand = fat({a: sum(math.expm1(p) for c, p in zip(linhas, oof) if c["agremiacao"] == a) for a in listas})
    real = fat(votos_reais)
    tot = sum(votos_reais.get(a, 0) for a in listas)
    cad_real = eleicao.distribuir({a: round(real[a] * tot) for a in listas}, eleicao.CADEIRAS_ALESC)["cadeiras"]
    sinais = [("Voto da lista na eleição anterior", fat(anteriores)), ("Receita somada da lista", soma("receita")),
              ("Seguidores somados da lista", soma("seguidores")), ("Soma das previsões individuais", cand),
              ("Meio a meio: soma + eleição anterior", fat({a: (1 - PESO_LISTA_ANTERIOR) * cand[a] + PESO_LISTA_ANTERIOR * fat(anteriores)[a]
                                                             if anteriores.get(a) else cand[a] for a in listas}))]
    saida = []
    for nome, f in sinais:
        cad = eleicao.distribuir({a: round(f[a] * tot) for a in listas}, eleicao.CADEIRAS_ALESC)["cadeiras"]
        saida.append({"sinal": nome, "erro_fatia_pp": round(100 * sum(abs(f[a] - real[a]) for a in listas) / len(listas), 2),
                      "cadeiras_erradas": sum(abs(cad.get(a, 0) - cad_real.get(a, 0)) for a in listas),
                      "pl": cad.get("PL", 0), "pl_real": cad_real.get("PL", 0)})
    return saida


def _receita_comparada() -> dict:
    """A receita da véspera (a que treina) contra a foto semanal mais recente (a final, depois de 03/11)."""
    semana, atual = receitas_mais_recentes()
    saida = {"semana_atual": semana, "final": bool(semana and semana >= PRESTACAO_FINAL),
             "prestacao_final_em": PRESTACAO_FINAL}
    anteriores = listas_anteriores(ANO_TREINO - 4)
    for rotulo in ("vespera", "atual"):
        if rotulo == "atual" and not semana:
            continue
        linhas, partes = dados_treino(receita=rotulo)
        r = validar(linhas, partes, VARIANTES["completo"], 0.0, com_mc=False, anteriores=anteriores)
        pares = [(math.log(c["receita"]), 1.0 if c["incumbente"] else 0.0, math.log(c["votos"]))
                 for c in linhas if (c["receita"] or 0) >= 1000 and c["votos"] > 0]
        import numpy as np
        A = np.column_stack([np.ones(len(pares)), [p[0] for p in pares], [p[1] for p in pares]])
        Y = np.array([p[2] for p in pares])
        b, *_ = np.linalg.lstsq(A, Y, rcond=None)
        res = Y - A @ b
        saida[rotulo] = {"total": round(sum(float(c["receita"] or 0) for c in linhas)),
                         "com_receita": sum(1 for c in linhas if (c["receita"] or 0) >= 1000),
                         "r2_cv": r["r2"], "spearman_cv": r["spearman"], "eleitos_certos": r["eleitos_certos"],
                         "elasticidade": round(float(b[1]), 3), "incumbencia": round(float(b[2]), 3),
                         "r2_receita": round(1 - float(res.var() / Y.var()), 3), "n": len(pares)}
    return saida


def _foto_congelada() -> dict | None:
    """O que a previsão de 04/10 fez (avaliação gravada), para a mesma régua."""
    con = db.conectar()
    try:
        r = con.execute("SELECT resultado_json FROM v2_avaliacao WHERE pst >= 100 ORDER BY id DESC LIMIT 1").fetchone()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    if not r:
        return None
    a = json.loads(r["resultado_json"])
    princ = next((c for c in a["cenarios"] if c["principal"]), a["cenarios"][0])
    return {"cenario": princ["nome"], "eleitos_certos": princ["eleitos_certos"],
            "cadeiras_erradas": princ["cadeiras_erradas"], "spearman": princ["spearman_candidatos"],
            "brier": a["probabilidade"]["brier"], "brier_ingenuo": a["probabilidade"]["brier_ingenuo"]}


# ── o modelo gravado ────────────────────────────────────────────────────────
ESQUEMA = """
CREATE TABLE IF NOT EXISTS v2_modelo (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    versao     TEXT,
    criado_em  TEXT,
    json       TEXT
);
"""


def treinar() -> dict:
    """Ajusta cada variante no conjunto inteiro (λ da validação) e grava tudo junto."""
    comp = comparar()
    linhas, _partes = dados_treino()
    import numpy as np
    y = np.array([math.log1p(c["votos"]) for c in linhas])
    modelos = {}
    for v in comp["variantes"]:
        X = _matriz(linhas, v["variaveis"])
        m = ajustar(X, y, v["lambda"])
        modelos[v["nome"]] = {
            "variaveis": v["variaveis"], "lambda": v["lambda"],
            "intercepto": float(m["beta"][0]), "padronizado": [float(b) for b in m["beta"][1:]],
            "media": m["media"].tolist(), "dp": m["dp"].tolist(),
            # faixa vista no treino: aplicar fora dela é extrapolar (a Ana Campagnolo
            # de 2026 tem o dobro do maior voto anterior de 2022)
            "minimo": X.min(axis=0).tolist(), "maximo": X.max(axis=0).tolist(),
            "sigma_cv": v["sigma"], "metricas_cv": {k: v.get(k) for k in (
                "r2", "spearman", "erro_tipico", "eleitos_certos", "cadeiras_erradas", "brier",
                "eleitos_certos_soma", "cadeiras_erradas_soma", "brier_soma")},
            "calibracao": v.get("calibracao"),
            "pesos": sorted(({"variavel": ROTULOS[n], "chave": n, "padronizado": round(float(b), 3)}
                             for n, b in zip(v["variaveis"], m["beta"][1:])), key=lambda x: -abs(x["padronizado"])),
        }
    receita = _receita_comparada()
    pacote = {"versao": f"v2-{ANO_TREINO}", "treino": f"ALESC {ANO_TREINO}: previsão congelada × resultado",
              "n": comp["n"], "comparacao": comp, "modelos": modelos, "receita": receita,
              "receita_semana": receita.get("semana_atual")}
    con = db.conectar()
    try:
        con.executescript(ESQUEMA)
        cur = con.execute("INSERT INTO v2_modelo (versao, criado_em, json) VALUES (?,?,?)",
                          (pacote["versao"], db.agora(), json.dumps(pacote, ensure_ascii=False)))
        con.commit()
        pacote["id"] = cur.lastrowid
    finally:
        con.close()
    return pacote


def carregar(con=None) -> dict | None:
    fechar = con is None
    con = con or db.conectar()
    try:
        con.executescript(ESQUEMA)
        r = con.execute("SELECT id, versao, criado_em, json FROM v2_modelo ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        if fechar:
            con.close()
    if not r:
        return None
    d = json.loads(r["json"])
    d.update(id=r["id"], criado_em=r["criado_em"])
    return d


def aplicar(modelo: dict, candidatos: list[dict]) -> list[float]:
    """log1p(votos) previsto para cada candidato (dicionários no formato de `dados_treino`)."""
    import numpy as np
    X = _matriz(candidatos, modelo["variaveis"])
    if modelo.get("minimo"):
        X = np.clip(X, np.array(modelo["minimo"]), np.array(modelo["maximo"]))
    m = {"beta": np.array([modelo["intercepto"]] + modelo["padronizado"]),
         "media": np.array(modelo["media"]), "dp": np.array(modelo["dp"])}
    return prever(m, X).tolist()


# ── a próxima eleição, com o que se sabe hoje ───────────────────────────────
def proxima(variante: str = "sem_receita", janela_dias: int = 270, amostras: int = 600) -> dict | None:
    """ALESC na próxima eleição se ela fosse hoje, entre os candidatos de 2026.

    Voto anterior = voto de 2026; mandato = eleito em 2026; Instagram = o que o
    monitor coletou nos últimos `janela_dias` (o treino usou jan–out do ano da
    eleição, ~270 dias).

    **Tamanho de cada lista: meio a meio** entre a soma dos seus candidatos
    previstos e o voto que ela teve em 2026 (`PESO_LISTA_ANTERIOR`) — o método
    que, medido em 2026, errou 6 cadeiras por lista em vez de 12. Dentro da
    lista, a ordem é a do modelo; por cima, a lei inteira (pisos de 10% e 20%).
    A chance de cada um sai de um Monte Carlo com o erro medido fora da amostra
    e passa pela recalibração ajustada no resultado de 2026.

    É um ponto de partida que o monitor de redes move semana a semana — não uma
    pesquisa: quem ainda não é candidato não aparece.
    """
    pacote = carregar()
    if not pacote or variante not in pacote["modelos"]:
        return None
    mod = pacote["modelos"][variante]
    from politicos import metricas
    con = db.conectar()
    try:
        perfis = {r["sq_candidato"]: dict(r) for r in con.execute(
            "SELECT id, sq_candidato, seguidores, acompanhar FROM perfis WHERE sq_candidato IS NOT NULL AND descartado_em IS NULL")}
        desde = (date.today() - timedelta(days=janela_dias)).isoformat()
        ig = {d["id"]: d for d in metricas.com_cobertura(metricas.resumo_perfis(con, desde=desde))}
    finally:
        con.close()
    md = microdados.conectar(leitura=True)
    try:
        cands = [dict(r) for r in md.execute(
            "SELECT * FROM candidato WHERE ano = ? AND cargo = 7 AND turno = 1 AND valido = 1", (ANO_TREINO,))]
        legenda = {}
        for r in md.execute("""SELECT p.agremiacao, SUM(v.votos) v FROM voto_mun v
                                 JOIN partido p ON p.ano = v.ano AND p.turno = v.turno AND p.cargo = v.cargo AND p.numero = v.numero
                                WHERE v.ano = ? AND v.cargo = 7 GROUP BY p.agremiacao""", (ANO_TREINO,)):
            legenda[r["agremiacao"]] = r["v"]
    finally:
        md.close()
    nominal: dict[str, int] = {}
    for c in cands:
        nominal[c["agremiacao"]] = nominal.get(c["agremiacao"], 0) + (c["votos"] or 0)
    partes = {a: legenda.get(a, 0) / (legenda.get(a, 0) + n) for a, n in nominal.items() if n}
    linhas = []
    for c in cands:
        p = perfis.get(c["sq"]) or {}
        m = ig.get(p.get("id")) or {}
        linhas.append({"sq": c["sq"], "nome": c["urna"], "numero": c["numero"], "partido": c["partido"],
                       "agremiacao": c["agremiacao"], "receita": 0, "incumbente": bool(c["eleito"]),
                       "voto_anterior": c["votos"], "voto_outro_cargo": 0,
                       "seguidores": p.get("seguidores") or 0, "posts": m.get("posts") or 0,
                       "engajamento": m.get("por_seguidor_ajustado") or m.get("por_seguidor"),
                       "crescimento": m.get("crescimento"), "perfil_id": p.get("id"),
                       "monitorado": bool(p.get("acompanhar") and p.get("seguidores")),
                       "votos": c["votos"], "eleito": bool(c["eleito"])})
    _contexto_da_lista(linhas, {a: nominal.get(a, 0) + legenda.get(a, 0) for a in nominal})
    pred = aplicar(mod, linhas)
    # Quem não está no monitor de redes não é "quem não tem Instagram": no treino,
    # sem perfil era quase sempre candidato pequeno, e o modelo aprendeu isso — a
    # Luciane Carminatti (124.590 votos, sem Instagram declarado ao TSE) caía para
    # 13ª do PT. Para esses, a previsão é a do modelo que não usa redes.
    usa_redes = any(v in _REDES for v in mod["variaveis"])
    reserva = pacote["modelos"].get("so_historico")
    if usa_redes and reserva:
        sem = [i for i, c in enumerate(linhas) if not c["monitorado"]]
        alt = aplicar(reserva, [linhas[i] for i in sem]) if sem else []
        for i, v in zip(sem, alt):
            pred[i] = v
    cad_2026: dict[str, int] = {}
    for c in cands:
        if c["eleito"]:
            cad_2026[c["agremiacao"]] = cad_2026.get(c["agremiacao"], 0) + 1
    anteriores = {a: nominal.get(a, 0) + legenda.get(a, 0) for a in nominal}
    total = float(sum(nominal.values()))
    votos = com_tamanho_de_lista(linhas, [math.expm1(x) for x in pred], anteriores, total)
    cad, eleitos = cadeiras_e_eleitos(linhas, votos, partes)
    brutos = monte_carlo(linhas, pred, mod["sigma_cv"], partes, amostras=amostras, anteriores=anteriores, total=total)
    ps = [calibrar(p, mod.get("calibracao")) for p in brutos]
    fatias = _na_lista(linhas, [math.expm1(x) for x in pred], {a: 1 for a in nominal})
    posicao: dict[str, int] = {}
    por_lista: dict[str, list] = {}
    for c, lp in zip(linhas, pred):
        por_lista.setdefault(c["agremiacao"], []).append((lp, c["sq"]))
    for lst in por_lista.values():
        for i, (_lp, sq) in enumerate(sorted(lst, reverse=True)):
            posicao[sq] = i + 1
    for c, f, p, pb, v in zip(linhas, fatias, ps, brutos, votos):
        c.update(fatia_lista=round(100 * f, 1), posicao_lista=posicao[c["sq"]], p_eleito=round(p, 3),
                 p_bruto=round(pb, 3), entra=c["sq"] in eleitos, previsto=round(v))
    linhas.sort(key=lambda c: (-c["p_eleito"], c["posicao_lista"]))
    fatia_lista = fatias_das_listas(linhas, [math.expm1(x) for x in pred], anteriores)
    return {"modelo": {"versao": pacote["versao"], "variante": variante, "descricao": DESCRICAO.get(variante),
                       "metricas_cv": mod["metricas_cv"], "pesos": mod["pesos"]},
            "janela_redes_desde": desde, "cadeiras": cad, "cadeiras_2026": cad_2026,
            "recalibrada": recalibracao_vale(mod.get("calibracao")),
            "fatias": {a: round(100 * f, 2) for a, f in fatia_lista.items()},
            "fatias_2026": {a: round(100 * v / (sum(anteriores.values()) or 1), 2) for a, v in anteriores.items()},
            "candidatos": [{k: c[k] for k in ("sq", "nome", "numero", "partido", "agremiacao", "votos", "eleito",
                                              "previsto", "fatia_lista", "posicao_lista", "p_eleito", "p_bruto", "entra",
                                              "seguidores", "posts", "perfil_id", "monitorado")}
                           for c in linhas],
            "fora_do_monitor": [{"nome": c["nome"], "partido": c["partido"], "votos": c["votos"], "eleito": c["eleito"],
                                 "numero": c["numero"]} for c in sorted(linhas, key=lambda x: -x["votos"])
                                if not c["monitorado"] and (c["eleito"] or c["votos"] >= 10000)]}


def main(argv: list[str]) -> int:
    passo = argv[0] if argv else "comparar"
    if passo == "comparar":
        c = comparar()
        print(f"n = {c['n']} candidatos, {c['eleitos']} eleitos · validação cruzada 10×5")
        f = c["foto_congelada"]
        if f:
            print(f"  foto congelada 04/10 ({f['cenario']}): eleitos {f['eleitos_certos']}/40 · cadeiras erradas "
                  f"{f['cadeiras_erradas']} · Brier {f['brier']} (sem modelo {f['brier_ingenuo']})")
        for v in c["variantes"]:
            print(f"  {v['nome']:18} eleitos {v['eleitos_certos']:2}/40 (soma {v['eleitos_certos_soma']}) · cadeiras erradas "
                  f"{v['cadeiras_erradas']:2} (soma {v['cadeiras_erradas_soma']}) · R² {v['r2']:.3f} · Spearman {v['spearman']:.3f} · "
                  f"Brier {v.get('brier')} (soma {v.get('brier_soma')}) · λ {v['lambda']}")
            if v.get("calibracao"):
                k = v["calibracao"]
                print(f"      recalibrada: Brier {k['brier_antes']} → {k['brier_depois']} (fora da amostra) · a {k['a']} b {k['b']}")
        for s in c["listas"]:
            print(f"  lista por {s['sinal']:40} erro {s['erro_fatia_pp']} pp · cadeiras erradas {s['cadeiras_erradas']} · PL {s['pl']}")
    elif passo == "treinar":
        if "--se-mudou" in argv:
            semana, _ = receitas_mais_recentes()
            atual = carregar()
            if atual and atual.get("receita_semana") == semana:
                print(f"receita sem foto nova (semana {semana}); modelo #{atual['id']} segue valendo")
                return 0
        p = treinar()
        print(f"modelo #{p['id']} {p['versao']} gravado")
        for nome, m in p["modelos"].items():
            print(f"  {nome:18}", [(x["variavel"], x["padronizado"]) for x in m["pesos"][:5]])
    elif passo == "proxima":
        r = proxima()
        if not r:
            print("sem modelo treinado")
            return 1
        print(r["modelo"]["versao"], r["modelo"]["variante"], "· redes desde", r["janela_redes_desde"])
        print("  cadeiras:", {eleicao.SIGLA_CURTA.get(a, a): n for a, n in sorted(r["cadeiras"].items(), key=lambda kv: -kv[1]) if n})
        print("  2026:    ", {eleicao.SIGLA_CURTA.get(a, a): n for a, n in sorted(r["cadeiras_2026"].items(), key=lambda kv: -kv[1]) if n})
        for c in r["candidatos"][:45]:
            print(f"  {c['nome']:28} {c['partido']:12} 2026 {c['votos']:>7}  {c['posicao_lista']:>2}º da lista ({c['fatia_lista']:>4}%)"
                  f"  p {c['p_eleito']:.2f} (bruto {c['p_bruto']:.2f}){'  ENTRA' if c['entra'] else ''}{'  (eleito 2026)' if c['eleito'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
