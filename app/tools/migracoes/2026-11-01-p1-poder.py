"""P1 do pré-registro: que tamanho de fraude os seis testes encontram.

    venv/bin/python -m tools.migracoes.2026-11-01-p1-poder [--validar]

## O que faz (docs/preregistro/README.md, seção 6, e o desvio de 01/11 na seção 9)

Planta fraude a favor do 13 nos dados reais e roda os seis testes com a regra
de decisão de cada um. Se nenhum teste disparou nos dados reais, um cenário
detectado em ≥ 95% das réplicas fica **descartado ao nível de 5%**: a chance de
não ver nada, se ele tivesse acontecido, é de no máximo 5%.

- Desenhos: **enchimento** (votos novos para o 13, até o limite de aptos) e
  **troca** (votos do 22 viram 13).
- Fração de seções atingidas: 0,1% e 1% (concentrada), 5% e 20% (difusa),
  sorteadas na mesma fração em cada UF.
- Tamanho: 0,1%, 0,5%, 1% e 3,57% dos votos válidos (3,57% é a margem).
- Base: os dados de 2026 e os de 2022 (comparados com 2022 real).

Os testes entram na versão leve registrada no desvio de 01/11: mesma regra,
p e erros-padrão por aproximação onde o teste completo exigiria milhares de
reamostragens. `--validar` roda só o cenário sem fraude: a versão leve tem de
dar "compatível" nos seis, como deu a completa.

Grava `apuracao/data/arquivo/2026-2t/p1.json` (parcial a cada cenário) e o item
P1 de `analise.json`.
"""
from __future__ import annotations

import importlib
import json
import pickle
import sys
from datetime import datetime

import numpy as np
from scipy.special import expit
from scipy.stats import beta as beta_dist, fisher_exact, norm

c1 = importlib.import_module("tools.migracoes.2026-11-01-c1-secoes-zeradas")
c2 = importlib.import_module("tools.migracoes.2026-11-01-c2-municipios")
c3 = importlib.import_module("tools.migracoes.2026-11-01-c3-impressao-digital")
c5 = importlib.import_module("tools.migracoes.2026-11-01-c5-biometria")
c6 = importlib.import_module("tools.migracoes.2026-11-01-c6-dispersao")
L1, F1, T1, BN1, C1, L2, F2, C2 = c1.L1, c1.F1, c1.T1, c1.BN1, c1.C1, c1.L2, c1.F2, c1.C2
CACHE, ARQUIVO, ANALISE, RAIZ = c1.CACHE, c1.ARQUIVO, c1.ANALISE, c1.RAIZ
DESTINO = ARQUIVO / "p1.json"
LIMIAR = 10

DESENHOS = ("enchimento", "troca")
FRACOES = (0.001, 0.01, 0.05, 0.20)
TAMANHOS = (0.001, 0.005, 0.01, 0.0357)
LOTE, MAXIMO = 20, 200


def _ref():
    """Referências e erros-padrão da especificação principal de cada teste (c1..c6.json)."""
    j = {c: json.loads((ARQUIVO / f"{c}.json").read_text(encoding="utf-8"))["principal"]
         for c in ("c1", "c2", "c3", "c4", "c5", "c6")}
    s1 = j["c1"]["series"]
    s3 = j["c3"]["series"]
    s4 = j["c4"]["series"]
    se = lambda ic: (ic[1] - ic[0]) / 3.92
    return {
        "c1_refmax": max(s1["13_2026"]["o_e"], s1["22_2022"]["o_e"], s1["13_2022"]["o_e"]),
        "c2_2022": j["c2"]["2022"],
        "c3": {ano: {"f_i": s3[ano]["f_i"], "f_e": s3[ano]["f_e"],
                     "se_i": se(s3[ano]["f_i_ic"]), "se_e": se(s3[ano]["f_e_ic"])} for ano in ("2026", "2022")},
        "c4": {ano: {"r4": s4[ano]["r4"], "sd_nulo": (s4[ano]["nulo_p97_5"] - s4[ano]["nulo_p2_5"]) / 3.92}
               for ano in ("2026", "2022")},
        "c4_se_dif": se(j["c4"]["diferenca_ic"]),
        "c5_2022": j["c5"]["series"]["2022"],
        "c6_m6_2022": j["c6"]["series"]["2022"]["m6"],
        "c6_se_log": (np.log(j["c6"]["razao_ic"][1]) - np.log(j["c6"]["razao_ic"][0])) / 3.92,
    }


class Base:
    """Os dados de um ano, já alinhados por seção, e o que não muda entre réplicas."""

    def __init__(self, ano: int):
        self.ano = ano
        chaves, A = c1._tabela(ano)
        bu = pickle.loads((CACHE / f"bu_secao_{ano}.pkl").read_bytes())
        sel, extra = [], []
        for i, k in enumerate(chaves):
            b = bu.get(k)
            a = A[i]
            if (k[0] == "zz" or b is None or b["aptos"] <= 0 or b["recebido"] is None
                    or a[L1] + a[F1] + a[T1] <= 0 or a[L2] + a[F2] <= 0 or a[C2] > b["aptos"] or a[C2] <= 0):
                continue
            sel.append(i)
            extra.append((b["aptos"], b["recebido"], min(b["sem_bio"], a[C2]), k))
        self.A = A[sel].copy()
        self.aptos = np.array([e[0] for e in extra], float)
        self.hora = np.array([e[1] for e in extra], float)
        self.sem_bio = np.array([e[2] for e in extra], float)
        ks = [e[3] for e in extra]
        self.uf = np.unique([k[0] for k in ks], return_inverse=True)[1]
        self.mun = np.unique([f"{k[0]}{k[1]}" for k in ks], return_inverse=True)[1]
        self.zona = np.unique([f"{k[0]}{k[2]}" for k in ks], return_inverse=True)[1]
        self.mun_uf = np.zeros(self.mun.max() + 1, dtype=np.int64)
        self.mun_uf[self.mun] = self.uf
        V1 = self.A[:, L1] + self.A[:, F1] + self.A[:, T1]
        self.V1 = V1
        self.X = np.column_stack([self.A[:, F1] / V1, self.A[:, L1] / V1, self.A[:, T1] / V1,
                                  self.A[:, BN1] / np.maximum(self.A[:, C1], 1)])
        self.p1 = self.A[:, L1] / V1
        # C1: ajuste sem fraude, ponto de partida das réplicas.
        self.c1_beta, self.c1_alfa = self._logit(self.A[:, F2] / (self.A[:, L2] + self.A[:, F2]),
                                                 self.A[:, L2] + self.A[:, F2], None, None, 80)
        # C4: postos da hora dentro do município (não mudam com a fraude).
        n = np.bincount(self.mun)
        ok = n[self.mun] >= 10
        self.c4_ok = ok
        g = np.unique(self.mun[ok], return_inverse=True)[1]
        o = np.lexsort((self.hora[ok], g))
        self.c4_g, self.c4_ordem = g, o
        rh = self._postos(self.hora[ok], g)
        self.c4_n = np.bincount(g).astype(float)
        m = np.bincount(g, rh) / self.c4_n
        self.c4_ch = rh - m[g]
        self.c4_sh = np.sqrt(np.bincount(g, self.c4_ch ** 2))
        print(f"  base {ano}: {len(self.A):,} seções, {self.mun.max() + 1:,} municípios", flush=True)

    @staticmethod
    def _postos(x, g):
        """Posto dentro do grupo (empates no posto médio), vetorizado."""
        o = np.lexsort((x, g))
        xs, gs = x[o], g[o]
        novo = np.r_[True, (gs[1:] != gs[:-1]) | (xs[1:] != xs[:-1])]
        bloco = np.cumsum(novo) - 1
        inicio_g = np.r_[0, np.flatnonzero(gs[1:] != gs[:-1]) + 1]
        pos = np.arange(len(x)) - np.repeat(inicio_g, np.diff(np.r_[inicio_g, len(x)])) + 1.0
        media = np.bincount(bloco, pos) / np.bincount(bloco)
        r = np.empty(len(x))
        r[o] = media[bloco]
        return r

    def _logit(self, y, w, beta, alfa, voltas):
        g, X = self.uf, self.X
        k, ng = X.shape[1], g.max() + 1
        if beta is None:
            beta = np.zeros(k)
            m = np.clip(np.bincount(g, w * y, ng) / np.bincount(g, w, ng), 1e-6, 1 - 1e-6)
            alfa = np.log(m / (1 - m))
        beta, alfa = beta.copy(), alfa.copy()
        for _ in range(voltas):
            p = expit(X @ beta + alfa[g])
            v = w * p * (1 - p)
            beta += np.linalg.solve(X.T @ (X * v[:, None]) + 1e-9 * np.eye(k), X.T @ (w * (y - p)))
            p = expit(X @ beta + alfa[g])
            alfa += np.bincount(g, w * (y - p), ng) / np.maximum(np.bincount(g, w * p * (1 - p), ng), 1e-9)
        return beta, alfa


def testes(base: Base, A: np.ndarray, ref: dict) -> dict:
    """Os seis testes, versão leve, sobre a matriz `A` (com ou sem fraude)."""
    ano = str(base.ano)
    out = {}
    V2 = A[:, L2] + A[:, F2]
    # C1
    b, a = base._logit(A[:, F2] / V2, V2, base.c1_beta, base.c1_alfa, 4)
    p22 = np.clip(expit(base.X @ b + a[base.uf]), 1e-9, 1 - 1e-9)
    rho = c1._rho(A[:, F2], V2, p22, base.uf)[base.uf]
    P = c1._cdf(LIMIAR, V2.astype(np.int64), p22, rho, p22 * (1 - rho) / rho, (1 - p22) * (1 - rho) / rho)
    O, E, var = int((A[:, F2] <= LIMIAR).sum()), P.sum(), (P * (1 - P)).sum()
    out["C1"] = {"p": float(norm.sf((O - E) / np.sqrt(var))), "extra": O / E > ref["c1_refmax"], "o_e": O / E}
    # C2
    M = np.vstack([np.bincount(base.mun, A[:, c], base.mun.max() + 1) for c in range(A.shape[1])]).T
    V1m, V2m = M[:, L1] + M[:, F1] + M[:, T1], M[:, L2] + M[:, F2]
    Xm = np.column_stack([M[:, F1] / V1m, M[:, L1] / V1m, M[:, T1] / V1m, M[:, BN1] / np.maximum(M[:, C1], 1)])
    pm = c1._logit_fe(Xm, M[:, L2] / V2m, V2m, base.mun_uf)
    r = (M[:, L2] - V2m * pm) / np.sqrt(V2m * pm * (1 - pm))
    phi = (r ** 2).sum() / (len(r) - Xm.shape[1] - base.mun_uf.max() - 1)
    z = r / np.sqrt(phi)
    sig = c2._bh(2 * norm.sf(np.abs(z)), 0.05)
    x1, n1 = int(sig.sum()), len(z)
    a13 = int((sig & (z > 0)).sum())
    r22 = ref["c2_2022"]
    x2, n2 = r22["significativos"], r22["municipios"]
    pc = (x1 + x2) / (n1 + n2)
    p_prop = float(norm.sf((x1 / n1 - x2 / n2) / np.sqrt(pc * (1 - pc) * (1 / n1 + 1 / n2))))
    p_f = float(fisher_exact([[a13, x1 - a13], [r22["a_favor_13"], r22["a_favor_22"]]], alternative="greater")[1]) if x1 else 1.0
    razao = (x1 / n1) / (x2 / n2)
    out["C2"] = {"p": min(1.0, 2 * min(p_prop, p_f)), "extra": (p_prop < 0.05 and razao > 1.25) or p_f < 0.05,
                 "sig": x1}
    # C3 (comparecimento do BU = comparecimento da votação por seção, conferido na reconciliação)
    t = np.minimum(A[:, C2] / base.aptos, 1)
    fit = c3.ajustar(t, A[:, L2] / V2)
    r3, r22_3 = ref["c3"][ano], ref["c3"]["2022"]
    fi, fe = fit["f_i"], fit["f_e"]
    exclui0 = fi - 1.96 * r3["se_i"] > 0 or fe - 1.96 * r3["se_e"] > 0
    acima = ((fi - r22_3["f_i"]) - 1.96 * np.hypot(r3["se_i"], r22_3["se_i"]) > 0 or
             (fe - r22_3["f_e"]) - 1.96 * np.hypot(r3["se_e"], r22_3["se_e"]) > 0)
    # p registrado: chance de f_i* e f_e* irem os DOIS a zero no bootstrap ≈ produto
    # das duas caudas. (A primeira versão usava a soma com o erro do f_i, que
    # engolia um f_e 750 vezes acima do real.)
    p3 = float(norm.sf(fi / r3["se_i"]) * norm.sf(fe / r3["se_e"]))
    out["C3"] = {"p": p3, "extra": exclui0 and acima,
                 "f_i": fi, "f_e": fe}
    # C4
    ok = base.c4_ok
    d = (A[:, L2] / V2 - base.p1)[ok]
    rd = base._postos(d, base.c4_g)
    m = np.bincount(base.c4_g, rd) / base.c4_n
    cd = rd - m[base.c4_g]
    sd = np.sqrt(np.bincount(base.c4_g, cd ** 2))
    val = (base.c4_sh > 0) & (sd > 0)
    rho4 = np.bincount(base.c4_g, base.c4_ch * cd) / np.where(val, base.c4_sh * sd, 1)
    peso = np.where(val, base.c4_n, 0)
    r4 = float((peso * rho4).sum() / peso.sum())
    r4ref = ref["c4"]["2022"]["r4"]
    out["C4"] = {"p": float(norm.sf(r4 / ref["c4"][ano]["sd_nulo"])),
                 "extra": r4 > r4ref and (r4 - r4ref) - 1.96 * ref["c4_se_dif"] > 0, "r4": r4}
    # C5
    s = base.sem_bio / A[:, C2]
    b5, se5 = c5.regressao(A[:, L2] / V2 - base.p1, s, V2, base.mun, base.zona)
    r5 = ref["c5_2022"]
    out["C5"] = {"p": float(norm.sf(b5 / se5)),
                 "extra": b5 > 0 and (b5 - r5["beta"]) - 1.96 * np.hypot(se5, r5["se"]) > 0, "beta": b5}
    # C6
    m6 = float(np.median(c6.phi_por_grupo(A[:, L2], V2, base.mun)))
    lr = np.log(m6 / ref["c6_m6_2022"])
    lo, hi = np.exp(lr - 1.96 * ref["c6_se_log"]), np.exp(lr + 1.96 * ref["c6_se_log"])
    out["C6"] = {"p": float(2 * norm.sf(abs(lr) / ref["c6_se_log"])), "extra": lo > 1.25 or hi < 0.8, "m6": m6}
    # Benjamini–Hochberg sobre os seis p; C6 decide só pelo IC (como no pré-registro).
    ids = ["C1", "C2", "C3", "C4", "C5", "C6"]
    pv = np.array([out[i]["p"] for i in ids])
    ordem = np.argsort(pv)
    aj = np.empty(6)
    aj[ordem] = np.minimum.accumulate((pv[ordem] * 6 / np.arange(1, 7))[::-1])[::-1]
    for i, pa in zip(ids, aj):
        out[i]["p_bh"] = float(min(pa, 1))
        out[i]["detecta"] = bool(out[i]["extra"] and (i == "C6" or pa < 0.05))
    out["qualquer"] = any(out[i]["detecta"] for i in ids)
    return out


def plantar(base: Base, desenho: str, fracao: float, tamanho: float, rng) -> tuple[np.ndarray, int, int]:
    """Matriz com fraude; devolve (A, votos pedidos, votos plantados)."""
    A = base.A.copy()
    alvo = int(round(tamanho * (A[:, L2] + A[:, F2]).sum()))
    escolhidas = []
    for u in range(base.uf.max() + 1):
        idx = np.flatnonzero(base.uf == u)
        k = max(1, int(round(fracao * len(idx))))
        escolhidas.append(rng.choice(idx, k, replace=False))
    sel = np.concatenate(escolhidas)
    cota = alvo / len(sel)
    if desenho == "enchimento":
        cabe = base.aptos[sel] - A[sel, C2]
    else:
        cabe = A[sel, F2]
    # Arredondamento aleatório: floor(cota) + 1 com probabilidade igual à parte
    # fracionária, para o total bater com o alvo. (Até 01/11 era floor puro, e
    # com cota de 1,24 voto por seção só 80% do alvo era plantado.)
    k = np.minimum(cabe, np.floor(cota) + (rng.random(len(sel)) < cota - np.floor(cota)))
    A[sel, L2] += k
    if desenho == "enchimento":
        A[sel, C2] += k
    else:
        A[sel, F2] -= k
    return A, alvo, int(k.sum())


def _cp(x, n):
    lo = 0.0 if x == 0 else float(beta_dist.ppf(0.025, x, n - x + 1))
    hi = 1.0 if x == n else float(beta_dist.ppf(0.975, x + 1, n - x))
    return lo, hi


def cenario(base, ref, desenho, fracao, tamanho, semente):
    rng = np.random.default_rng(semente)
    det = {i: 0 for i in ("C1", "C2", "C3", "C4", "C5", "C6", "qualquer")}
    n, plantado, alvo = 0, [], 0
    while n < MAXIMO:
        for _ in range(LOTE):
            A, alvo, feito = plantar(base, desenho, fracao, tamanho, rng)
            r = testes(base, A, ref)
            plantado.append(feito)
            for i in det:
                det[i] += int(r[i]["detecta"] if i != "qualquer" else r["qualquer"])
            n += 1
        lo, hi = _cp(det["qualquer"], n)
        if lo >= 0.95 or hi < 0.80 or (lo >= 0.80 and hi < 0.95):
            break
    cabe = float(np.mean(plantado)) / alvo if alvo else 1.0
    lo, hi = _cp(det["qualquer"], n)
    return {"desenho": desenho, "fracao_secoes": fracao, "tamanho": tamanho, "votos_alvo": alvo,
            "votos_plantados_media": round(float(np.mean(plantado))), "cabe": bool(cabe >= 0.9),
            "replicas": n, "deteccao": {i: round(v / n, 3) for i, v in det.items()},
            "deteccao_ic": [round(lo, 3), round(hi, 3)],
            "leitura": "não cabe" if cabe < 0.9 else "descartado" if det["qualquer"] / n >= 0.95
            else "não descartado"}


def gravar(resultado: dict) -> None:
    # `default`: tipos do numpy (bool_, float64) viram os do Python.
    DESTINO.write_text(json.dumps(resultado, ensure_ascii=False, indent=1, default=lambda o: o.item()),
                       encoding="utf-8")


def _pct(x, casas=1):
    return c1._br(100 * x, casas) + "%"


def gravar_analise(resultado: dict) -> None:
    """Item P1 de `analise.json`: a tabela da base 2026 e a leitura de cada cenário.

    A conclusão usa a base de 2026: é sobre 2026 que a pergunta é feita. A base
    de 2022 vai junto como sensibilidade, com o aviso de que ali a referência é
    o próprio dado (o limiar fica colado nele e qualquer empurrão passa).
    """
    a = json.loads(ANALISE.read_text(encoding="utf-8"))
    cen = [c for c in resultado["cenarios"] if c["base"] == 2026]
    linhas = []
    for desenho in DESENHOS:
        for fracao in FRACOES:
            cel = []
            for tamanho in TAMANHOS:
                c = next(x for x in cen if x["desenho"] == desenho and x["fracao_secoes"] == fracao
                         and x["tamanho"] == tamanho)
                taxa = c["deteccao"]["qualquer"]
                classe = {"descartado": "d", "não descartado": "n", "não cabe": "x"}[c["leitura"]]
                cel.append({"leitura": c["leitura"], "taxa": _pct(taxa, 0), "classe": classe})
            linhas.append({"rotulo": f"{desenho.capitalize()} em {c1._br(100 * fracao, 1).replace(',0', '')}% das seções",
                           "celulas": cel})
    texto = ("Sem fraude plantada, nenhum teste dispara. Com fraude plantada nos dados de 2026, a tabela mostra a "
             "taxa de detecção e a leitura de cada cenário. \"Descartado\": detectado em pelo menos 95% das "
             "réplicas, então, como nada disparou no dado real, esse cenário fica descartado ao nível de 5%. "
             "\"Não cabe\": as seções sorteadas não têm eleitores ausentes (enchimento) ou votos do Flávio (troca) "
             "suficientes para receber a fraude inteira; a taxa é a da fraude parcial que coube.")
    for t in a["testes"]:
        if t["id"] == "P1":
            t.update({"status": "feito", "decisao": "poder", "resultado": texto,
                      "tabela": {"colunas": [f"{c1._br(100 * x, 2).rstrip('0').rstrip(',')}% dos votos" for x in TAMANHOS],
                                 "linhas": linhas},
                      "nota": ("Na base de 2022 (fraude plantada em 2022, comparada com 2022 real) os testes pegam bem "
                               "mais, até 0,1% dos votos. Não é poder de verdade: ali a referência é o próprio dado, o "
                               "limiar fica colado nele e qualquer empurrão na direção alegada passa. Os números estão "
                               "nos dados."),
                      "dados": "/apuracao/explicacao/p1.json"})
    a["atualizado_em"] = resultado["gerado_em"][:10]
    ANALISE.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    ref = _ref()
    validar = "--validar" in sys.argv
    resultado = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
                 "preregistro": "docs/preregistro/README.md (preregistro-v1), seção 6; desvio de 01/11 na seção 9",
                 "validacao": {}, "cenarios": []}
    for ano in (2026, 2022):
        base = Base(ano)
        r0 = testes(base, base.A, ref)
        resultado["validacao"][str(ano)] = {i: {k: (round(v, 6) if isinstance(v, float) else v)
                                                for k, v in r0[i].items()} for i in ("C1", "C2", "C3", "C4", "C5", "C6")}
        resultado["validacao"][str(ano)]["qualquer"] = r0["qualquer"]
        print(f"  validação {ano}: " + ", ".join(f"{i} {'DISPARA' if r0[i]['detecta'] else 'ok'}"
                                                for i in ("C1", "C2", "C3", "C4", "C5", "C6")), flush=True)
        if validar:
            continue
        semente = ano * 1000           # determinística: hash() de str muda a cada processo
        for desenho in DESENHOS:
            for fracao in FRACOES:
                for tamanho in TAMANHOS:
                    t0 = datetime.now()
                    semente += 1
                    c = cenario(base, ref, desenho, fracao, tamanho, semente)
                    c["base"] = ano
                    resultado["cenarios"].append(c)
                    gravar(resultado)
                    print(f"  {ano} {desenho:10} {100 * fracao:5.1f}% seções {100 * tamanho:5.2f}% votos: "
                          f"{c['leitura']:15} qualquer {c['deteccao']['qualquer']:.2f} ({c['replicas']} réplicas, "
                          f"{(datetime.now() - t0).seconds}s) {c['deteccao']}", flush=True)
    gravar(resultado)
    if not validar:
        gravar_analise(resultado)
    print(f"→ {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
