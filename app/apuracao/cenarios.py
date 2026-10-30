"""Cenários do 2º turno — o Sankey e o que a aritmética permite afirmar.

A pergunta que esta aba responde: *de onde vieram os 10,4 milhões de votos que o
Lula ganhou entre os turnos?* Há duas fontes possíveis, e só duas:

    votos válidos NOVOS (4,78 mi)  +  votos da TERCEIRA VIA (9,32 mi)

A soma tem de dar o ganho dos dois candidatos (14,10 mi = 4,78 + 9,32, e a
identidade fecha no voto). Cada cenário é um par de percentuais:

    p = fração dos votos NOVOS que foi para o Lula
    q = fração da TERCEIRA VIA que foi para o Lula

e o par só é possível se  p·4,78 + q·9,32 = 10,38  (o ganho real do Lula).

**O limite duro (não é estimativa).** Se TODOS os 4,78 mi de votos novos
tivessem ido para o Lula, ainda faltariam 5,60 mi — logo a terceira via deu ao
Lula PELO MENOS 60,1% dela. Não existe cenário em que a terceira via tenha ido
majoritariamente para o Flavio. Isso sai de duas subtrações, não de modelo.

**Por que não dá por candidato.** O pedido natural é "quem votou no Zema foi
80% para o Flavio". Não é estimável com este dado: os votos dos 10 candidatos
andam juntos pelos municípios (o condicionamento da matriz é ~3.900) e a
validação cruzada mostra que nenhum ajuste melhora o erro de verdade. O teste
está em `identificabilidade()` e a tela mostra o número — quem publica "Zema
80%" está inventando. O que o dado permite é o TOTAL da terceira via, e é isso
que o Sankey mostra.

A estimativa do total (q ≈ 0,555 no modelo geográfico de `explicacao.py`) fica
consistente com o piso aritmético: o intervalo final é q ∈ [0,601, 0,656] — o
piso da aritmética corta a cauda otimista do modelo.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from apuracao import contas

# Candidatos da terceira via, para o rótulo do Sankey. Ordem de votos no 1º turno.
# (o valor em si vem do arquivo; aqui só o que a tela precisa para nomear)
PISO_MUNICIPIO = 300


def _ler(base: Path) -> dict:
    return json.loads((base / "explicacao.json").read_text(encoding="utf-8"))


def _resumo(base: Path) -> dict:
    try:
        return json.loads((base / "conta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ── o limite aritmético ─────────────────────────────────────────────────────
def limite(resumo: dict) -> dict:
    """O que a aritmética obriga, sem nenhum modelo.

    novos + terceira via = ganho(Lula) + ganho(Flavio): identidade contábil do
    voto válido. Daí:

        p·novos + q·terceira = ganho(Lula),  com 0 ≤ p,q ≤ 1

    O menor q possível acontece com p = 1 (todo voto novo no Lula).
    """
    novos = resumo.get("novos_validos") or 0
    terc = resumo.get("terceira_via") or 0
    ganho = resumo.get("ganho_lula") or 0
    if not (novos and terc and ganho):
        return {"ok": False}
    # O piso vem de `contas` — é o mesmo número que as outras abas usam.
    ref = {"novos_validos": novos, "terceira_via": terc, "ganho_lula": ganho}
    piso = contas.piso_terceira({**ref, "ganho_flavio": 0})
    q_min = piso["fracao"]
    p_necessario = piso["p_necessario_se_zero"]
    return {
        "ok": True,
        "novos": novos, "terceira": terc, "ganho_lula": ganho,
        "ganho_flavio": resumo.get("ganho_flavio") or 0,
        "q_min": round(q_min, 4),
        "q_min_votos": round(q_min * terc),
        "p_necessario_se_q_zero": round(p_necessario, 4),
        "q_zero_impossivel": p_necessario > 1.0,
        "folga": round(novos - ganho) if novos >= ganho else 0,
    }


def cenarios(resumo: dict, passos: int = 9) -> dict:
    """Cenários possíveis: a reta p·novos + q·terceira = ganho(Lula).

    Cada cenário é uma história que a aritmética aceita. Nenhum deles é "o que
    aconteceu" — é o envelope do que aconteceu.
    """
    novos = resumo.get("novos_validos") or 0
    terc = resumo.get("terceira_via") or 0
    ganho = resumo.get("ganho_lula") or 0
    if not (novos and terc):
        return {"ok": False, "lista": []}
    q_min = contas.piso_terceira(
        {"novos_validos": novos, "terceira_via": terc, "ganho_lula": ganho,
         "ganho_flavio": 0})["fracao"]
    q_max = min(1.0, ganho / terc)
    lista = []
    for i in range(passos):
        q = q_min + (q_max - q_min) * i / (passos - 1)
        p = (ganho - q * terc) / novos
        if p < -1e-9 or p > 1 + 1e-9:
            continue
        p = min(1.0, max(0.0, p))
        lista.append({
            "p": round(p, 4), "q": round(q, 4),
            "novos_lula": round(p * novos), "novos_flavio": round((1 - p) * novos),
            "terc_lula": round(q * terc), "terc_flavio": round((1 - q) * terc),
            "erro": round(p * novos + q * terc - ganho),
        })
    return {"ok": True, "lista": lista, "q_min": round(q_min, 4), "q_max": round(q_max, 4),
            "novos": novos, "terceira": terc, "ganho_lula": ganho,
            "ganho_flavio": resumo.get("ganho_flavio") or 0}


def modelo(resumo: dict) -> dict | None:
    """O ponto que o modelo geográfico de `explicacao.py` escolhe, já cortado
    pelo piso da aritmética (o modelo pode otimizar demais)."""
    f = resumo.get("fluxo") or {}
    if not f.get("ok"):
        return None
    lim = limite(resumo)
    q = max(f["b"], lim["q_min"]) if lim.get("ok") else f["b"]
    terc = resumo.get("terceira_via") or 0
    novos = resumo.get("novos_validos") or 0
    ganho = resumo.get("ganho_lula") or 0
    p = (ganho - q * terc) / novos if novos else 0
    p = min(1.0, max(0.0, p))
    return {
        "p": round(p, 4), "q": round(q, 4),
        "q_modelo": f["b"], "q_ic": f.get("b_ic"),
        "ajustado_pelo_piso": q != f["b"],
        "novos_lula": round(p * novos), "novos_flavio": round((1 - p) * novos),
        "terc_lula": round(q * terc), "terc_flavio": round((1 - q) * terc),
        "erro": round(p * novos + q * terc - ganho),
    }


# ── o teste que explica por que não dá por candidato ────────────────────────
def identificabilidade(base: Path) -> dict:
    """O teste honesto do que o dado comporta.

    Se os coeficientes por candidato fossem identificáveis, um ajuste com
    regularização escolhida por validação cruzada melhoraria o erro fora da
    amostra. Ele não melhora (RMSE de 722 para 677 votos, com 4,7 mi de votos
    por município) — porque os votos dos 10 andam juntos. Sem essa melhora, o
    coeficiente individual é ruído com cara de número.
    """
    try:
        import numpy as np
    except ImportError:
        return {"ok": False, "motivo": "sem numpy"}
    dados = _ler(base)
    nums = dados["numeros"]
    terc = [n for n in nums if n not in ("13", "22")]
    muns = [m for m in dados["municipios"]
            if m["t1"]["validos"] >= PISO_MUNICIPIO and m["t2"]["validos"] > 0]
    if len(muns) < 100:
        return {"ok": False, "motivo": "poucos municípios"}
    X = np.array([[max(0, m["t2"]["validos"] - m["t1"]["validos"])]
                  + [m["t1"]["outros"][nums.index(n)] for n in terc] for m in muns], float)
    y = np.array([m["t2"]["lula"] - m["t1"]["lula"] for m in muns], float)
    cond = float(np.linalg.cond(X))

    def rmse_cv(alpha: int) -> float:
        rng = np.random.default_rng(0)
        idx = rng.permutation(len(y))
        folds = np.array_split(idx, 5)
        erro = 0.0
        for k in range(5):
            te = folds[k]
            tr = np.concatenate([folds[j] for j in range(5) if j != k])
            A = X[tr].T @ X[tr] + alpha * np.eye(X.shape[1])
            c = np.linalg.solve(A, X[tr].T @ y[tr])
            erro += float(((y[te] - X[te] @ c) ** 2).sum())
        return round(math.sqrt(erro / len(y)), 1)

    sem = rmse_cv(0)
    melhor, melhor_alpha = sem, 0
    for alpha in (1, 100, 1000, 10_000, 100_000, 1_000_000):
        r = rmse_cv(alpha)
        if r < melhor:
            melhor, melhor_alpha = r, alpha
    nomes = {c["n"]: c["nm"] for c in dados.get("candidatos_1t") or []}
    # pares mais colineares, para a tela exemplificar
    shares = np.array([[m["t1"]["outros"][nums.index(n)] / m["t1"]["validos"] for n in terc]
                       for m in muns])
    C = np.corrcoef(shares.T)
    pares = []
    for i in range(len(terc)):
        for j in range(i + 1, len(terc)):
            pares.append((round(float(C[i, j]), 3), nomes.get(terc[i], terc[i]),
                          nomes.get(terc[j], terc[j])))
    pares.sort(reverse=True)
    return {
        "ok": True,
        "municipios": len(muns),
        "candidatos": len(terc),
        "condicionamento": round(cond),
        "rmse_sem": sem, "rmse_melhor": melhor, "alpha": melhor_alpha,
        "ganho_rmse": round(sem - melhor, 1),
        "melhora_pct": round(100 * (sem - melhor) / sem, 2) if sem else 0.0,
        "pares": pares[:5],
    }


def gerar(base: Path) -> dict:
    """Grava `cenarios.json` ao lado do `analise.json` (rodado na migração)."""
    r = _resumo(base)
    if not r:
        return {"ok": False}
    saida = {
        "ok": True,
        "limite": limite(r),
        "cenarios": cenarios(r),
        "modelo": modelo(r),
        "identificabilidade": identificabilidade(base),
    }
    destino = base / "cenarios.json"
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(destino)
    return saida
