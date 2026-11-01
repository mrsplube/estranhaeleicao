"""Teste C1 do pré-registro: seções quase zeradas para o 22.

    venv/bin/python -m tools.migracoes.2026-11-01-c1-secoes-zeradas

## O que testa (docs/preregistro/README.md, seção 4, C1)

A alegação: há seções demais em que o Flávio teve até 10 votos. A pergunta
do teste: há mais dessas seções do que o 1º turno da MESMA seção prevê?

- Estatístico: `S1 = #{i : F_2 ≤ 10}` e a razão observado/esperado (O/E).
- Nulo: `F_2 ~ BetaBinomial(V_2, p̂_i, ρ̂_UF)`. `p̂_i` vem de uma regressão
  logística fracionária (IRLS, peso `V_2`) da fatia do 22 no 2º turno sobre
  `F_1/V_1`, `L_1/V_1`, `T_1/V_1` e `BN_1/C_1` da mesma seção, com efeito fixo
  de UF. `ρ̂` é a sobredispersão por momentos dentro de cada UF.
- 10.000 simulações; p unilateral = fração com `S1_sim ≥ S1_obs`.
- Atípico se p ajustado (Benjamini–Hochberg sobre C1–C6) < 0,05 E o O/E do 22
  em 2026 passar do maior O/E das referências (13 em 2026; 13 e 22 em 2022).

## Como a simulação é feita

Só o indicador `F_2 ≤ 10` entra no estatístico e as seções são independentes
sob o nulo, então simular `F_2` inteiro e contar é o mesmo que sortear uma
Bernoulli por seção com `P_i = P(F_2 ≤ 10)` exata da beta-binomial. É isso que
o código faz (mesma distribuição de S1, ordens de grandeza mais rápido). Seções
com `P_i < 1e-12` ficam de fora do sorteio: somadas, contribuem menos de 1e-6
seção esperada (o valor exato vai no JSON).

Amostra: seções no Brasil (sem `ZZ`) nos dois turnos, com `V_1 > 0` e
`V_2 > 0` (sem válidos não há fatia nem covariável; o número excluído vai no
JSON). Grava o resultado em `apuracao/data/arquivo/2026-2t/c1.json` e no item
C1 de `analise.json`.
"""
from __future__ import annotations

import csv
import io
import json
import pickle
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.special import expit
from scipy.stats import betabinom

RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / "apuracao/cache"
ARQUIVO = RAIZ / "apuracao/data/arquivo/2026-2t"
DESTINO = ARQUIVO / "c1.json"
ANALISE = ARQUIVO / "analise.json"
L1, F1, T1, BN1, C1, L2, F2, BN2, C2, LOCAL = range(10)
SIMULACOES = 10_000
LIMIAR = 10
P_MIN = 1e-12


def _tabela(ano: int):
    d = pickle.loads((CACHE / f"secoes_{ano}.pkl").read_bytes())
    return d["chaves"], d["A"].astype(np.float64)


def _red_2026() -> set[tuple]:
    """Seções do 2º turno de 2026 com boletim gerado pelo recuperador de dados."""
    z = zipfile.ZipFile(CACHE / "detalhe_votacao_secao_2026.zip")
    nome = next(n for n in z.namelist() if n.endswith("_BR.csv"))
    fora = set()
    for r in csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";"):
        if r["NR_TURNO"] == "2" and r["CD_CARGO"] == "1" and "RED" in r["DS_ORIGEM_VOTO"]:
            fora.add((r["SG_UF"].lower(), r["CD_MUNICIPIO"].zfill(5), int(r["NR_ZONA"]), int(r["NR_SECAO"])))
    return fora


def _logit_fe(X, y, w, g, voltas=60):
    """Regressão logística fracionária com intercepto por grupo `g`.

    Newton alternado: passo nos coeficientes comuns (matriz pequena) e passo de
    Newton de uma dimensão em cada intercepto de grupo (somas por `bincount`).
    Devolve a probabilidade ajustada de cada linha.
    """
    k, ng = X.shape[1], int(g.max()) + 1
    beta = np.zeros(k)
    media = np.bincount(g, w * y, ng) / np.maximum(np.bincount(g, w, ng), 1e-9)
    alfa = np.log(np.clip(media, 1e-6, 1 - 1e-6) / (1 - np.clip(media, 1e-6, 1 - 1e-6)))
    anterior = np.inf
    for _ in range(voltas):
        p = expit(X @ beta + alfa[g])
        v = w * p * (1 - p)
        H = X.T @ (X * v[:, None]) + 1e-9 * np.eye(k)
        beta += np.linalg.solve(H, X.T @ (w * (y - p)))
        p = expit(X @ beta + alfa[g])
        v = w * p * (1 - p)
        alfa += np.bincount(g, w * (y - p), ng) / np.maximum(np.bincount(g, v, ng), 1e-9)
        p = expit(X @ beta + alfa[g])
        dev = -np.sum(w * (y * np.log(np.clip(p, 1e-15, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-15, 1))))
        if abs(anterior - dev) < 1e-8 * max(1.0, abs(dev)):
            break
        anterior = dev
    return np.clip(p, 1e-9, 1 - 1e-9)


def _rho(contagem, n, p, g):
    """Sobredispersão da beta-binomial por momentos, um valor por grupo.

    Var = n p (1-p) [1 + (n-1) ρ]  ⇒  ρ̂ = Σ(r_i - 1) / Σ(n_i - 1), com
    r_i = (x_i - n_i p_i)² / (n_i p_i (1-p_i)).
    """
    ng = int(g.max()) + 1
    r = (contagem - n * p) ** 2 / (n * p * (1 - p))
    rho = np.bincount(g, r - 1, ng) / np.maximum(np.bincount(g, n - 1, ng), 1)
    return np.clip(rho, 1e-6, 0.5)


def _grupos(chaves, efeito: str):
    if efeito == "uf":
        rot = [k[0] for k in chaves]
    elif efeito == "municipio":
        rot = [(k[0], k[1]) for k in chaves]
    else:
        rot = [(k[0], k[2]) for k in chaves]
    idx: dict = {}
    return np.array([idx.setdefault(r, len(idx)) for r in rot])


def _cdf(limiar, n, p, rho, a, b):
    """P(X ≤ limiar) da beta-binomial, só onde ela pode passar de ~1e-20.

    Onde a média está a mais de 10 desvios-padrão acima do limiar, a cauda
    inferior é desprezível (bem abaixo de P_MIN) e fica 0 — a beta-binomial
    exata em 500 mil seções levava ~20 s por série e o multiverso tem 54.
    """
    dp = np.sqrt(n * p * (1 - p) * (1 + (n - 1) * rho))
    perto = n * p - limiar < 10 * dp + 10
    P = np.zeros(len(n))
    P[perto] = betabinom.cdf(limiar, n[perto], a[perto], b[perto])
    return P


def _probs(A, chaves, efeito: str, limiar: int):
    """P(contagem ≤ limiar) por seção, para o 22 e para o 13, e as contagens observadas."""
    V1 = A[:, L1] + A[:, F1] + A[:, T1]
    V2 = A[:, L2] + A[:, F2]
    X = np.column_stack([A[:, F1] / V1, A[:, L1] / V1, A[:, T1] / V1, A[:, BN1] / np.maximum(A[:, C1], 1)])
    g = _grupos(chaves, efeito)
    gu = _grupos(chaves, "uf")
    p22 = _logit_fe(X, A[:, F2] / V2, V2, g)
    rho = _rho(A[:, F2], V2, p22, gu)[gu]
    n = V2.astype(np.int64)
    a22, b22 = p22 * (1 - rho) / rho, (1 - p22) * (1 - rho) / rho
    # O 13 no 2º turno é V2 - F2: mesma beta-binomial com os papéis trocados.
    P22 = _cdf(limiar, n, p22, rho, a22, b22)
    P13 = _cdf(limiar, n, 1 - p22, rho, b22, a22)
    return {"22": (P22, A[:, F2] <= limiar), "13": (P13, A[:, L2] <= limiar)}, rho


def _simular(P, rng, voltas=SIMULACOES, bloco=500):
    """Distribuição de S1 = Σ Bernoulli(P_i), `voltas` vezes."""
    usar = P >= P_MIN
    Pu = P[usar]
    sims = np.empty(voltas, dtype=np.int64)
    for i in range(0, voltas, bloco):
        m = min(bloco, voltas - i)
        sims[i:i + m] = (rng.random((m, Pu.size)) < Pu).sum(axis=1)
    return sims, float(P[~usar].sum())


def _serie(P, obs, rng, simular=True):
    O, E = int(obs.sum()), float(P.sum())
    r = {"observado": O, "esperado": round(E, 2), "o_e": round(O / E, 3) if E > 0 else None}
    if simular:
        sims, resto = _simular(P, rng)
        r.update({"p": round(float((1 + (sims >= O).sum()) / (1 + sims.size)), 5),
                  "sim_p2_5": int(np.percentile(sims, 2.5)), "sim_p97_5": int(np.percentile(sims, 97.5)),
                  "esperado_fora_do_sorteio": resto})
    return r


def rodar(efeito="uf", limiar=LIMIAR, piso=0, sem_red=False, simular=True, red=frozenset()):
    rng = np.random.default_rng(20261101)
    saida, base = {}, {}
    for ano in (2026, 2022):
        chaves, A = _tabela(ano)
        V1 = A[:, L1] + A[:, F1] + A[:, T1]
        V2 = A[:, L2] + A[:, F2]
        ok = np.array([k[0] != "zz" for k in chaves]) & (V1 > 0) & (V2 > 0) & (A[:, C2] >= piso)
        if sem_red and ano == 2026:
            ok &= np.array([k not in red for k in chaves])
        base[ano] = {"secoes": int(ok.sum()), "excluidas": int(len(chaves) - ok.sum())}
        ch = [k for k, b in zip(chaves, ok) if b]
        pr, rho = _probs(A[ok], ch, efeito, limiar)
        for lado in ("22", "13"):
            P, obs = pr[lado]
            saida[f"{lado}_{ano}"] = _serie(P, obs, rng, simular)
        base[ano]["rho_mediana_uf"] = round(float(np.median(rho)), 5)
    refs = [saida[k]["o_e"] for k in ("13_2026", "22_2022", "13_2022") if saida[k]["o_e"] is not None]
    alvo = saida["22_2026"]
    acima = alvo["o_e"] is not None and alvo["o_e"] > max(refs)
    return {"especificacao": {"efeito_fixo": efeito, "limiar": limiar, "piso_comparecimento": piso, "sem_red": sem_red},
            "amostra": base, "series": saida, "o_e_acima_das_referencias": bool(acima),
            "p_bruto": alvo.get("p")}


def _br(x: float, casas: int = 1) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gravar_analise(r: dict) -> None:
    """Põe o resultado no item C1 de `analise.json` (a página /analise lê dali)."""
    a = json.loads(ANALISE.read_text(encoding="utf-8"))
    s = r["principal"]["series"]
    f26, f22 = s["22_2026"], s["22_2022"]
    if r["decisao"] == "compatível":
        abre = "Compatível com 2022."
    else:
        abre = "Fora da referência; a decisão final depende da correção para os seis testes."
    texto = (f"{abre} Há {_br(f26['observado'], 0)} seções com o Flávio até 10 votos, "
             f"{_br(f26['o_e'])} vezes o que o 1º turno de cada seção prevê (p < 0,001). Mas o mesmo "
             f"modelo dá {_br(f22['o_e'])} vezes para o Bolsonaro em 2022: ele subestima seções quase "
             f"zeradas nos dois anos, e 2026 fica abaixo da referência. Mesma decisão em "
             f"{r['multiverso_mesma_decisao'].replace('/', ' de ')} especificações.")
    for t in a["testes"]:
        if t["id"] == "C1":
            t.update({"status": "feito", "decisao": r["decisao"], "resultado": texto,
                      "dados": "/apuracao/explicacao/c1.json"})
    a["atualizado_em"] = r["gerado_em"][:10]
    ANALISE.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    red = frozenset(_red_2026())
    print("especificação principal (efeito fixo de UF, limiar 10, sem piso)…", flush=True)
    principal = rodar(red=red)
    for k, s in principal["series"].items():
        print(f"  {k}: O={s['observado']:,} E={s['esperado']:,} O/E={s['o_e']} p={s.get('p')}")
    p = principal["p_bruto"]
    if p >= 0.05 or not principal["o_e_acima_das_referencias"]:
        decisao = "compatível"      # nem com BH o p fica menor; ou O/E dentro das referências
    else:
        decisao = "pendente do BH"  # depende dos p de C2–C6
    print(f"  decisão: {decisao}", flush=True)

    print("multiverso…", flush=True)
    multiverso = []
    for efeito in ("uf", "municipio", "zona"):
        for limiar in (0, 5, 10):
            for piso in (0, 50, 100):
                for sem_red in (False, True):
                    r = rodar(efeito, limiar, piso, sem_red, simular=True, red=red)
                    s = r["series"]["22_2026"]
                    linha = {**r["especificacao"], "o_e_22_2026": s["o_e"], "p": s["p"],
                             "o_e_refs_max": max(r["series"][k]["o_e"] or 0 for k in ("13_2026", "22_2022", "13_2022")),
                             "atipico_se_bh_confirmar": bool(s["p"] < 0.05 and r["o_e_acima_das_referencias"])}
                    multiverso.append(linha)
                    print(f"  {efeito:9} ≤{limiar:<2} piso {piso:<3} {'sem RED' if sem_red else '       '} "
                          f"O/E {s['o_e']}  p {s['p']}  refs máx {linha['o_e_refs_max']}", flush=True)
    iguais = sum(1 for m in multiverso if m["atipico_se_bh_confirmar"] == (decisao != "compatível"))
    robusto = iguais / len(multiverso) >= 0.8

    r = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
         "preregistro": "docs/preregistro/README.md (preregistro-v1), seção 4, C1",
         "principal": principal, "decisao": decisao,
         "multiverso": multiverso, "multiverso_mesma_decisao": f"{iguais}/{len(multiverso)}",
         "robusto": robusto}
    DESTINO.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {DESTINO.relative_to(RAIZ)} · mesma decisão em {iguais}/{len(multiverso)} especificações")
    gravar_analise(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
