"""v2: multiverso — as variações da v1 em 2026 e nas 4 presidenciais de referência.

    venv/bin/python -m tools.migracoes.2026-11-05-v2-multiverso

Ver o desvio de 04/11 "Multiverso" em `docs/preregistro/v2.md` §8: em cada
variação o estatístico é recalculado; o erro-padrão é o da especificação
principal da mesma disputa; o C1 roda com um nível. A leitura de cada
variação usa a regra da §3 contra as 4 presidenciais naquela variação (K = 4,
t com 2 graus de liberdade). Sem BH entre testes aqui: cada variação é lida
teste a teste (Bonferroni só dentro do teste de dois componentes), o que torna
"atípico" mais fácil, e não mais difícil, de aparecer.

Grava `apuracao/data/arquivo/2026-2t/v2/multiverso.json`.
"""
from __future__ import annotations

import copy
import importlib
import json
import sys
from datetime import datetime

import numpy as np
from scipy.stats import norm, t as t_dist

vt = importlib.import_module("tools.migracoes.2026-11-03-v2-testes")
lei = importlib.import_module("tools.migracoes.2026-11-05-v2-leitura")
poder = importlib.import_module("tools.migracoes.2026-11-05-v2-poder")
c1, c2, c3, c5, c6, p1 = vt.c1, vt.c2, vt.c3, vt.c5, vt.c6, vt.p1
W1, P1, O1, BN1, C1, W2, P2, BN2, C2 = range(9)
DISPUTAS = ("pres-2026", "pres-2010", "pres-2014", "pres-2018", "pres-2022")
RED = None


def recortar(d, mask):
    e = copy.copy(d)
    e.A = d.A[mask]
    e.t = dict(d.t)
    for k in ("aptos", "hora", "sem_bio", "local"):
        e.t[k] = np.asarray(d.t[k])[mask]
    e.t["chaves"] = [k for k, m in zip(d.t["chaves"], mask) if m]
    for k in ("uf", "mun", "zona", "local", "V1", "V2", "X", "delta"):
        setattr(e, k, getattr(d, k)[mask])
    for k in ("uf", "mun", "zona", "local"):
        setattr(e, k, np.unique(getattr(e, k), return_inverse=True)[1])
    e.cluster = e.mun if e.mun.max() + 1 >= vt.MIN_GRUPOS else e.zona
    return e


def _grupo(d, nome):
    return {"uf": d.uf, "municipio": d.mun, "zona": d.zona}[nome]


def stat_c1(d, efeito, limiar):
    A, V2 = d.A, d.V2
    p = c1._logit_fe(d.X, A[:, P2] / V2, V2, _grupo(d, efeito))
    rho = c1._rho(A[:, P2], V2, p, d.uf)[d.uf]
    P = c1._cdf(limiar, V2.astype(np.int64), p, rho, p * (1 - rho) / rho, (1 - p) * (1 - rho) / rho)
    O = (A[:, P2] <= limiar).sum()
    return {"log O/E": float(np.log((O + 0.5) / (P.sum() + 0.5)))}


def stat_c2(d, efeito, q):
    A = d.A
    nm = d.mun.max() + 1
    M = np.vstack([np.bincount(d.mun, A[:, c], nm) for c in range(9)]).T
    V1, V2 = M[:, W1] + M[:, P1] + M[:, O1], M[:, W2] + M[:, P2]
    X = np.column_stack([M[:, P1] / V1, M[:, W1] / V1, M[:, O1] / V1, M[:, BN1] / np.maximum(M[:, C1], 1)])
    g = np.zeros(nm, dtype=np.int64)
    if efeito == "uf":
        g[d.mun] = d.uf
    pm = c1._logit_fe(X, M[:, W2] / V2, V2, g)
    r = (M[:, W2] - V2 * pm) / np.sqrt(V2 * pm * (1 - pm))
    z = r / np.sqrt((r ** 2).sum() / (nm - X.shape[1] - g.max() - 1))
    sig = c2._bh(2 * norm.sf(np.abs(z)), q)
    k = int(sig.sum())
    return {"log proporção significativa": float(np.log((k + 0.5) / (nm + 0.5))),
            "fração a favor do vencedor": float((sig & (z > 0)).sum() / k) if k else None}


def stat_c3(d, bins):
    ap = d.t["aptos"]
    ok = np.isfinite(ap) & (ap > 0) & (d.A[:, C2] <= ap)
    f = c3.ajustar(d.A[ok, C2] / ap[ok], d.A[ok, W2] / d.V2[ok], bins)
    return {"f_e": f["f_e"], "f_i": f["f_i"]}


def stat_c4(d, grupo):
    h = d.t["hora"]
    if np.isfinite(h).mean() < 0.9:
        return {}
    g0 = _grupo(d, grupo)
    ok = np.isfinite(h)
    n = np.bincount(g0[ok], minlength=g0.max() + 1)
    keep = ok & (n[g0] >= 10)
    g = np.unique(g0[keep], return_inverse=True)[1]
    loc = np.unique(d.local[keep], return_inverse=True)[1]
    hora, delta = h[keep], d.delta[keep]
    o = np.lexsort((hora, loc))
    ini = np.r_[0, np.flatnonzero(loc[o][1:] != loc[o][:-1]) + 1]
    fim = np.r_[ini[1:], len(o)]
    hl = np.array([hora[o][a:b][(b - a) // 2] for a, b in zip(ini, fim)])
    ng = np.bincount(g).astype(float)
    rh, rd = p1.Base._postos(hl[loc], g), p1.Base._postos(delta, g)
    ch, cd = rh - (np.bincount(g, rh) / ng)[g], rd - (np.bincount(g, rd) / ng)[g]
    sh, sd = np.sqrt(np.bincount(g, ch * ch)), np.sqrt(np.bincount(g, cd * cd))
    val = (sh > 0) & (sd > 0)
    rho = np.bincount(g, ch * cd) / np.where(val, sh * sd, 1)
    w = np.where(val, ng, 0)
    return {"correlação hora × mudança": float((w * rho).sum() / w.sum())}


def stat_c5(d, grupo):
    s = d.t["sem_bio"]
    if np.isfinite(s).mean() < 0.9:
        return {}
    ok = np.isfinite(s) & (d.A[:, C2] > 0)
    x = s[ok] / d.A[ok, C2]
    keep = x <= 1
    idx = np.flatnonzero(ok)[keep]
    g = _grupo(d, grupo)
    b, _ = c5.regressao(d.delta[idx], x[keep], d.V2[idx], g[idx], d.mun[idx])
    return {"β biometria": b}


def stat_c6(d, grupo):
    phi = c6.phi_por_grupo(d.A[:, W2], d.V2, _grupo(d, grupo))
    return {"log mediana de φ": float(np.log(np.median(phi)))} if len(phi) else {}


VARIACOES = {
    "C1": [((e, l), lambda d, e=e, l=l: stat_c1(d, e, l)) for e in ("uf", "municipio", "zona") for l in (0, 5, 10)],
    "C2": [((e, q), lambda d, e=e, q=q: stat_c2(d, e, q)) for e in ("uf", "nenhum") for q in (0.05, 0.10)],
    "C3": [((b,), lambda d, b=b: stat_c3(d, b)) for b in (100, 50)],
    "C4": [((g,), lambda d, g=g: stat_c4(d, g)) for g in ("municipio", "zona")],
    "C5": [((g,), lambda d, g=g: stat_c5(d, g)) for g in ("municipio", "zona")],
    "C6": [((g,), lambda d, g=g: stat_c6(d, g)) for g in ("municipio", "zona")],
}
SE = {("C1", "log O/E"): ("C1", "se"), ("C2", "log proporção significativa"): ("C2", "se"),
      ("C2", "fração a favor do vencedor"): ("C2", "se_D2"), ("C3", "f_e"): ("C3", "se_f_e"),
      ("C3", "f_i"): ("C3", "se_f_i"), ("C4", "correlação hora × mudança"): ("C4", "se"),
      ("C5", "β biometria"): ("C5", "se"), ("C6", "log mediana de φ"): ("C6", "se")}
MARGEM = {(t, n): (m, dr) for t, n, _, m, dr in lei.COMPONENTES}


def ler_variacao(teste, valores, principais):
    """Leitura de um teste numa variação: valores[disputa][componente]."""
    comps, ps, foras, equivs = [], [], [], []
    for (t_, nome), (mg, dr) in MARGEM.items():
        if t_ != teste:
            continue
        a, campo = SE[(t_, nome)]
        y26 = valores["pres-2026"].get(nome)
        s26 = principais["pres-2026"].get(a, {}).get(campo)
        pares = [(valores[k].get(nome), principais[k].get(a, {}).get(campo)) for k in DISPUTAS[1:]]
        pares = [(y, s) for y, s in pares if y is not None and s]
        if y26 is None or not s26 or not pares:
            continue
        y = np.array([p[0] for p in pares])
        v = np.array([p[1] ** 2 for p in pares])
        if len(pares) >= 3:
            mu, tau2, se_mu = lei.reml(y, v)
            gl = len(pares) - 2
            sd = np.sqrt(tau2 + se_mu ** 2 + s26 ** 2)
            z = (y26 - mu) / sd
            q = t_dist.ppf(0.975, gl)
            ps.append(float(t_dist.sf(z, gl)) if dr == "cima" else float(2 * t_dist.sf(abs(z), gl)))
            foras.append(bool(z > q) if dr == "cima" else bool(abs(z) > q))
        else:
            mu, se_mu = float(y.mean()), float(np.sqrt(v.mean()))
        dd, sdd = y26 - mu, np.sqrt(s26 ** 2 + se_mu ** 2)
        equivs.append(bool(mg[0] <= dd - 1.645 * sdd and dd + 1.645 * sdd <= mg[1]))
        comps.append(nome)
    if not comps:
        return "sem dado"
    p = min(1.0, len(ps) * min(ps)) if ps else None
    if p is not None and p < 0.05 and any(foras):
        return "atípico"
    return "equivalente" if all(equivs) else "inconclusivo"


def main() -> int:
    global RED
    RED = frozenset(c1._red_2026())
    principais = {k: json.loads((vt.SAIDA / f"{k}.json").read_text(encoding="utf-8")) for k in DISPUTAS}
    base = {k: vt.Disputa(k) for k in DISPUTAS}
    linhas = []
    for piso in (0, 50, 100):
        for sem_red in (False, True):
            recorte = {}
            for k, d in base.items():
                m = d.A[:, C2] >= piso
                if sem_red and k == "pres-2026":
                    m &= np.array([c not in RED for c in d.t["chaves"]])
                recorte[k] = recortar(d, m)
            for teste, vs in VARIACOES.items():
                for params, f in vs:
                    t0 = datetime.now()
                    valores = {k: f(e) for k, e in recorte.items()}
                    leitura = ler_variacao(teste, valores, principais)
                    linhas.append({"teste": teste, "piso": piso, "sem_red": sem_red, "parametros": list(params),
                                   "valores": valores, "leitura": leitura})
                    print(f"  {teste} piso {piso:<3} {'sem RED' if sem_red else '       '} {params}: {leitura} "
                          f"({(datetime.now() - t0).seconds}s)", flush=True)
                    (vt.SAIDA / "multiverso.json").write_text(
                        json.dumps({"gerado_em": datetime.now().isoformat(timespec="seconds"), "variacoes": linhas},
                                   ensure_ascii=False, indent=1, default=lambda o: o.item()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
