"""v2, Etapa 3: os seis testes para qualquer disputa (vencedor/perdedor).

    venv/bin/python -m tools.migracoes.2026-11-03-v2-testes pres-2022 [gov-2010-ro ...] [--nivel1]

Ver `docs/v2-plano-execucao.md` (Etapa 3) e `docs/preregistro/v2.md` (seções 3, 5 e 8).

Cada teste devolve o estatístico `T`, o erro-padrão na escala usada pela
meta-análise (`se`) e extras. Razões (C1, C2, C6) vão para a meta-análise em
log, que é a escala em que as margens [0,8; 1,25] são simétricas.

Unidade de reamostragem: município, ou zona quando a disputa tem menos de 30
municípios (o DF tem um só). `--nivel1` roda o C1 com um nível só, como na v1:
serve para conferir que pres-2022 e pres-2026 reproduzem a v1 (aceite da Etapa 3).

Grava `apuracao/data/arquivo/2026-2t/v2/{id}.json`.
"""
from __future__ import annotations

import importlib
import json
import pickle
import sys
from datetime import datetime

import numpy as np
from scipy.special import expit, logit
from scipy.stats import betabinom, norm

c1 = importlib.import_module("tools.migracoes.2026-11-01-c1-secoes-zeradas")
c2 = importlib.import_module("tools.migracoes.2026-11-01-c2-municipios")
c3 = importlib.import_module("tools.migracoes.2026-11-01-c3-impressao-digital")
c5 = importlib.import_module("tools.migracoes.2026-11-01-c5-biometria")
c6 = importlib.import_module("tools.migracoes.2026-11-01-c6-dispersao")
p1 = importlib.import_module("tools.migracoes.2026-11-01-p1-poder")
CACHE, ARQUIVO = c1.CACHE, c1.ARQUIVO
SAIDA = ARQUIVO / "v2"
W1, P1, O1, BN1, C1, W2, P2, BN2, C2 = range(9)
LIMIAR = 10
BOOT = 1000
PERM = 2000
SIM_C1 = 1000
MIN_GRUPOS = 30


class Disputa:
    def __init__(self, ident: str):
        t = pickle.loads((CACHE / f"v2/{ident}.pkl").read_bytes())
        self.id, self.t = ident, t
        self.A = t["A"]
        ch = t["chaves"]
        self.uf = np.unique([k[0] for k in ch], return_inverse=True)[1]
        self.mun = np.unique([f"{k[0]}{k[1]}" for k in ch], return_inverse=True)[1]
        self.zona = np.unique([f"{k[0]}{k[2]}" for k in ch], return_inverse=True)[1]
        self.local = np.unique([f"{k[0]}{k[1]}{k[2]}-{l}" for k, l in zip(ch, t["local"])], return_inverse=True)[1]
        nm = self.mun.max() + 1
        # Unidade de reamostragem (v2.md §8): município, ou zona se houver poucos municípios.
        self.cluster = self.mun if nm >= MIN_GRUPOS else self.zona
        self.cluster_nome = "município" if nm >= MIN_GRUPOS else "zona"
        A = self.A
        self.V1 = A[:, W1] + A[:, P1] + A[:, O1]
        self.V2 = A[:, W2] + A[:, P2]
        self.X = np.column_stack([A[:, P1] / self.V1, A[:, W1] / self.V1, A[:, O1] / self.V1,
                                  A[:, BN1] / np.maximum(A[:, C1], 1)])
        self.delta = A[:, W2] / self.V2 - A[:, W1] / self.V1


def _boot_razao(num, den, cl, rng, voltas=BOOT):
    """Erro-padrão de log(Σnum/Σden) reamostrando grupos (somas por grupo fixas)."""
    n, d = np.bincount(cl, num), np.bincount(cl, den)
    g = len(n)
    r = np.empty(voltas)
    for b in range(voltas):
        i = rng.integers(0, g, g)
        r[b] = np.log(max(n[i].sum(), 1e-9) / max(d[i].sum(), 1e-9))
    return float(np.std(r, ddof=1))


# ── C1 ───────────────────────────────────────────────────────────────────
def teste_c1(d: Disputa, nivel1=False):
    A, V2 = d.A, d.V2
    p = c1._logit_fe(d.X, A[:, P2] / V2, V2, d.uf)
    rho = c1._rho(A[:, P2], V2, p, d.uf)[d.uf]
    n = V2.astype(np.int64)
    obs = A[:, P2] <= LIMIAR
    rng = np.random.default_rng(1)
    if nivel1:
        P = c1._cdf(LIMIAR, n, p, rho, p * (1 - rho) / rho, (1 - p) * (1 - rho) / rho)
        E_secao = P
        sims = np.array([(rng.random(P.size) < P).sum() for _ in range(SIM_C1)])
        sigma2 = 0.0
    else:
        # Efeito de local (v2.md §5 e §8): variância por momentos, em logit.
        r = A[:, P2] - n * p
        v = n * p * (1 - p)
        S, V = np.bincount(d.local, r), np.bincount(d.local, v)
        sigma2 = max(float(((S ** 2 - V).sum()) / max((V ** 2).sum(), 1e-9)), 0.0)
        sd = np.sqrt(sigma2)
        lp = logit(p)
        # Seções que podem chegar perto do limiar com um efeito de até 4 desvios.
        pmin = expit(lp - 4 * sd)
        perto = n * pmin - LIMIAR < 10 * np.sqrt(n * pmin * (1 - pmin) * (1 + (n - 1) * rho)) + 10
        idx = np.flatnonzero(perto)
        E_secao = np.zeros(len(n))
        sims = np.empty(SIM_C1)
        loc_idx = d.local[idx]
        for s in range(SIM_C1):
            u = rng.normal(0, sd, d.local.max() + 1) if sd > 0 else np.zeros(d.local.max() + 1)
            pp = expit(lp[idx] + u[loc_idx])
            rr = rho[idx]
            P = betabinom.cdf(LIMIAR, n[idx], pp * (1 - rr) / rr, (1 - pp) * (1 - rr) / rr)
            E_secao[idx] += P / SIM_C1
            sims[s] = (rng.random(P.size) < P).sum()
    O, E = int(obs.sum()), float(E_secao.sum())
    return {"T": O / E, "logT": float(np.log(O / E)), "se": _boot_razao(obs.astype(float), E_secao, d.cluster, rng),
            "O": O, "E": round(E, 2), "p_sim": float((1 + (sims >= O).sum()) / (1 + SIM_C1)),
            "sigma2_local": round(sigma2, 5), "rho_mediana": float(np.median(rho)),
            "calib": {"p": p, "E_secao": E_secao, "obs": obs}}


# ── C2 ───────────────────────────────────────────────────────────────────
def teste_c2(d: Disputa):
    A = d.A
    nm = d.mun.max() + 1
    if nm < MIN_GRUPOS:
        return {"T": None, "motivo": f"só {nm} municípios"}
    M = np.vstack([np.bincount(d.mun, A[:, c], nm) for c in range(9)]).T
    V1, V2 = M[:, W1] + M[:, P1] + M[:, O1], M[:, W2] + M[:, P2]
    X = np.column_stack([M[:, P1] / V1, M[:, W1] / V1, M[:, O1] / V1, M[:, BN1] / np.maximum(M[:, C1], 1)])
    g = np.zeros(nm, dtype=np.int64)
    g[d.mun] = d.uf
    pm = c1._logit_fe(X, M[:, W2] / V2, V2, g)
    r = (M[:, W2] - V2 * pm) / np.sqrt(V2 * pm * (1 - pm))
    phi = float((r ** 2).sum() / (nm - X.shape[1] - g.max() - 1))
    z = r / np.sqrt(phi)
    sig = c2._bh(2 * norm.sf(np.abs(z)), 0.05)
    k = int(sig.sum())
    prop = k / nm
    favor = int((sig & (z > 0)).sum())
    rng = np.random.default_rng(2)
    props, fracs = np.empty(BOOT), np.empty(BOOT)
    for b in range(BOOT):
        i = rng.integers(0, nm, nm)
        props[b] = sig[i].mean()
        fracs[b] = (sig[i] & (z[i] > 0)).sum() / max(sig[i].sum(), 1)
    lp = np.log(np.maximum(props, 0.5 / nm))
    return {"T": prop, "logT": float(np.log(max(prop, 0.5 / nm))), "se": float(np.std(lp, ddof=1)),
            "municipios": nm, "significativos": k, "a_favor_vencedor": favor,
            "D2": favor / k if k else None, "se_D2": float(np.std(fracs, ddof=1)) if k else None, "phi": phi,
            "calib": {"z": z}}


# ── C3 ───────────────────────────────────────────────────────────────────
def teste_c3(d: Disputa, voltas=BOOT):
    ok = np.isfinite(d.t["aptos"]) & (d.t["aptos"] > 0) & (d.A[:, C2] <= d.t["aptos"])
    t = d.A[ok, C2] / d.t["aptos"][ok]
    v = d.A[ok, W2] / d.V2[ok]
    cl = np.unique(d.cluster[ok], return_inverse=True)[1]
    fit = c3.ajustar(t, v)
    bs = c3._bootstrap(t, v, cl, voltas, 100, semente=3)
    la = d.A[ok, W2] / d.t["aptos"][ok]
    b, se = c3.inclinacao(t, la, d.t["aptos"][ok], np.unique(d.mun[ok], return_inverse=True)[1])
    return {"f_i": fit["f_i"], "f_e": fit["f_e"], "se_f_i": float(np.std(bs[:, 0], ddof=1)),
            "se_f_e": float(np.std(bs[:, 1], ddof=1)), "sigma_x": fit["sigma_x"], "erro_ajuste": fit["erro"],
            "myagkov": b, "myagkov_se": se, "secoes": int(ok.sum())}


# ── C4 ───────────────────────────────────────────────────────────────────
def teste_c4(d: Disputa, voltas=PERM):
    h = d.t["hora"]
    ok = np.isfinite(h)
    if ok.mean() < 0.9:
        return {"T": None, "motivo": "sem hora de recebimento"}
    mun, loc, hora, delta = d.mun[ok], d.local[ok], h[ok], d.delta[ok]
    n = np.bincount(mun)
    keep = n[mun] >= 10
    mun, loc, hora, delta = mun[keep], loc[keep], hora[keep], delta[keep]
    g = np.unique(mun, return_inverse=True)[1]
    ng = np.bincount(g).astype(float)
    # Hora do local = mediana das suas seções; o local é o bloco permutado (v2.md §8).
    lu, li = np.unique(loc, return_inverse=True)
    o = np.lexsort((hora, li))
    hs, ls = hora[o], li[o]
    ini = np.r_[0, np.flatnonzero(ls[1:] != ls[:-1]) + 1]
    fim = np.r_[ini[1:], len(ls)]
    hora_loc = np.array([hs[a:b][(b - a) // 2] for a, b in zip(ini, fim)])
    g_loc = np.zeros(len(lu), dtype=np.int64)
    g_loc[li] = g
    rd = p1.Base._postos(delta, g)
    cd = rd - (np.bincount(g, rd) / ng)[g]
    sd = np.sqrt(np.bincount(g, cd * cd))

    def r4(hl):
        rh = p1.Base._postos(hl[li], g)
        ch = rh - (np.bincount(g, rh) / ng)[g]
        sh = np.sqrt(np.bincount(g, ch * ch))
        val = (sh > 0) & (sd > 0)
        rho = np.bincount(g, ch * cd) / np.where(val, sh * sd, 1)
        w = np.where(val, ng, 0)
        return float((w * rho).sum() / w.sum()), rho[val], ng[val]

    obs, rho_g, n_g = r4(hora_loc)
    rng = np.random.default_rng(4)
    gl = g_loc.astype(float)
    nulos = np.empty(voltas)
    for b in range(voltas):
        perm = np.argsort(gl + rng.random(len(gl)))     # embaralha locais dentro do município
        hl = np.empty(len(gl))
        hl[np.argsort(gl, kind="stable")] = hora_loc[perm]
        nulos[b] = r4(hl)[0]
    bs = np.empty(BOOT)
    for b in range(BOOT):
        i = rng.integers(0, len(rho_g), len(rho_g))
        bs[b] = (n_g[i] * rho_g[i]).sum() / n_g[i].sum()
    return {"T": obs, "se": float(np.std(bs, ddof=1)), "p_perm": float((1 + (nulos >= obs).sum()) / (1 + voltas)),
            "nulo_sd": float(np.std(nulos, ddof=1)), "municipios": int(len(n_g))}


# ── C5 ───────────────────────────────────────────────────────────────────
def teste_c5(d: Disputa):
    s = d.t["sem_bio"]
    ok = np.isfinite(s) & (d.A[:, C2] > 0)
    if ok.mean() < 0.9:
        return {"T": None, "motivo": "sem biometria por seção"}
    x = s[ok] / d.A[ok, C2]
    keep = x <= 1
    idx = np.flatnonzero(ok)[keep]
    b, se = c5.regressao(d.delta[idx], x[keep], d.V2[idx], d.mun[idx], d.mun[idx])
    return {"T": b, "se": se}


# ── C6 ───────────────────────────────────────────────────────────────────
def teste_c6(d: Disputa):
    phi = c6.phi_por_grupo(d.A[:, W2], d.V2, d.mun)
    if len(phi) == 0:
        return {"T": None, "motivo": "nenhum município com 10 seções"}
    m6 = float(np.median(phi))
    rng = np.random.default_rng(6)
    bs = np.array([np.log(np.median(phi[rng.integers(0, len(phi), len(phi))])) for _ in range(BOOT)])
    return {"T": m6, "logT": float(np.log(m6)), "se": float(np.std(bs, ddof=1)), "grupos": int(len(phi))}


def rodar(ident: str, nivel1=False) -> dict:
    d = Disputa(ident)
    out = {"id": ident, "cargo": d.t["cargo"], "ano": d.t["ano"], "vencedor": d.t["vencedor"],
           "perdedor": d.t["perdedor"], "secoes": int(len(d.A)), "municipios": int(d.mun.max() + 1),
           "unidade_reamostragem": d.cluster_nome, "gerado_em": datetime.now().isoformat(timespec="seconds")}
    calib = {}
    for nome, f in (("C1", lambda: teste_c1(d, nivel1)), ("C2", lambda: teste_c2(d)), ("C3", lambda: teste_c3(d)),
                    ("C4", lambda: teste_c4(d)), ("C5", lambda: teste_c5(d)), ("C6", lambda: teste_c6(d))):
        t0 = datetime.now()
        r = f()
        if "calib" in r:
            calib[nome] = r.pop("calib")
        r["segundos"] = (datetime.now() - t0).seconds
        out[nome] = r
        print(f"  {ident} {nome}: " + ", ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}"
                                              for k, v in r.items()), flush=True)
    # Insumos da calibração (Etapa 4), fora do JSON público.
    (CACHE / "v2" / f"{ident}-calib{'-nivel1' if nivel1 else ''}.pkl").write_bytes(pickle.dumps(calib))
    return out


def main() -> int:
    SAIDA.mkdir(exist_ok=True)
    nivel1 = "--nivel1" in sys.argv
    for ident in [a for a in sys.argv[1:] if not a.startswith("--")]:
        r = rodar(ident, nivel1)
        nome = f"{ident}{'-nivel1' if nivel1 else ''}.json"
        (SAIDA / nome).write_text(json.dumps(r, ensure_ascii=False, indent=1, default=lambda o: o.item()),
                                  encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
