"""v2, Etapa 7: poder com fraude plantada nas disputas de referência.

    venv/bin/python -m tools.migracoes.2026-11-05-v2-poder pres-2018 [pres-2022 ...] [--validar]

Ver `docs/preregistro/v2.md` §6 e os desvios de 04/11 (§8).

- Base: uma disputa presidencial de referência (2010, 2014, 2018, 2022).
- Leitura: a regra da §3 (intervalo de predição + BH/BY), contra a distribuição
  de referência SEM a base (deixa-uma-fora), calculada uma vez.
- Desenhos: troca e enchimento ao acaso (fração das seções em cada UF); reduto
  (troca, municípios do decil mais favorável ao vencedor no 1º turno);
  comparecimento alto (troca, seções acima do p90); pouca fiscalização
  (enchimento, locais com uma seção só).
- Testes dentro da simulação: versão leve (C1 de um nível com partida no ajuste
  sem fraude; C3 sem reamostragem; erros-padrão da rodada sem fraude).
- `--validar`: os 4 cenários de validação da §6.5, com a versão leve e a
  "completa" do desvio de 04/11, 20 réplicas cada.

Grava `apuracao/data/arquivo/2026-2t/v2/poder-{base}.json` (parcial a cada cenário).
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime

import numpy as np
from scipy.special import expit
from scipy.stats import norm, t as t_dist

vt = importlib.import_module("tools.migracoes.2026-11-03-v2-testes")
lei = importlib.import_module("tools.migracoes.2026-11-05-v2-leitura")
c1, c2, c3, c5, c6, p1 = vt.c1, vt.c2, vt.c3, vt.c5, vt.c6, vt.p1
W1, P1, O1, BN1, C1, W2, P2, BN2, C2 = range(9)
V2DIR = vt.SAIDA

DESENHOS = (("troca", "aleatorio"), ("enchimento", "aleatorio"), ("troca", "reduto"),
            ("troca", "comparecimento_alto"), ("enchimento", "pouca_fiscalizacao"))
FRACOES = (0.05, 0.20, 0.50)
TAMANHOS = (0.0025, 0.005, 0.01, 0.018, 0.0357)
LOTE, MAXIMO = 20, 200
MEDIANA_PROPRIA = "--mediana-propria" in sys.argv
VALIDACAO = ((("troca", "aleatorio"), 0.05, 0.01), (("troca", "aleatorio"), 0.20, 0.01),
             (("enchimento", "aleatorio"), 0.05, 0.01), (("enchimento", "aleatorio"), 0.20, 0.01))


def referencia_sem(base: str) -> dict:
    """Distribuição de referência de cada componente, sem a base (deixa-uma-fora)."""
    disputas = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in V2DIR.glob("*.json")
                if p.stem.startswith(("pres-", "gov-")) and not p.stem.endswith("nivel1")}
    ref = [r for k, r in disputas.items() if r["ano"] != 2026 and k != base]
    out = {}
    for teste, nome, tirar, margem, direcao in lei.COMPONENTES:
        pares = [tirar(r) for r in ref if r.get(teste)]
        pares = [(y, s) for y, s in pares if y is not None and s is not None and s > 0]
        if len(pares) < 3:
            out[(teste, nome)] = None
            continue
        y = np.array([p[0] for p in pares])
        v = np.array([p[1] ** 2 for p in pares])
        mu, tau2, se_mu = lei.reml(y, v)
        out[(teste, nome)] = {"mu": mu, "tau2": tau2, "se_mu": se_mu, "k": len(pares), "direcao": direcao}
    return out


class Base:
    def __init__(self, ident: str):
        self.d = vt.Disputa(ident)
        self.r0 = json.loads((V2DIR / f"{ident}.json").read_text(encoding="utf-8"))
        d = self.d
        A = d.A
        # C1: ajuste sem fraude, ponto de partida (um nível, como na v1 leve).
        V2 = d.V2
        self.c1_beta, self.c1_alfa = self._logit(A[:, P2] / V2, V2, None, None, 80)
        # C3: centro do componente limpo no cenário sem fraude (v2.md §8, 05/11).
        ap0 = d.t["aptos"]
        ok0 = np.isfinite(ap0) & (ap0 > 0) & (A[:, C2] <= ap0)
        self.c3_centro = c3.centro_limpo(A[ok0, C2] / ap0[ok0], A[ok0, W2] / V2[ok0])
        # Conjuntos dos desenhos estratégicos.
        nm = d.mun.max() + 1
        w1m = np.bincount(d.mun, A[:, W1], nm) / np.maximum(np.bincount(d.mun, d.V1, nm), 1)
        self.reduto = np.flatnonzero(w1m[d.mun] >= np.quantile(w1m, 0.9))
        ap = d.t["aptos"]
        comp = np.where(np.isfinite(ap) & (ap > 0), A[:, C2] / np.where(ap > 0, ap, 1), np.nan)
        self.comp_alto = np.flatnonzero(comp >= np.nanquantile(comp, 0.9))
        nloc = np.bincount(d.local)
        self.uma_secao = np.flatnonzero(nloc[d.local] == 1)
        # C4 leve: hora por local fixa; só o Δ muda.
        h = d.t["hora"]
        self.tem_hora = np.isfinite(h).mean() >= 0.9
        if self.tem_hora:
            ok = np.isfinite(h)
            n = np.bincount(d.mun[ok], minlength=nm)
            keep = ok & (n[d.mun] >= 10)
            self.c4_idx = np.flatnonzero(keep)
            g = np.unique(d.mun[keep], return_inverse=True)[1]
            loc = np.unique(d.local[keep], return_inverse=True)[1]
            hora = h[keep]
            o = np.lexsort((hora, loc))
            ini = np.r_[0, np.flatnonzero(loc[o][1:] != loc[o][:-1]) + 1]
            fim = np.r_[ini[1:], len(o)]
            hl = np.array([hora[o][a:b][(b - a) // 2] for a, b in zip(ini, fim)])
            self.c4_g = g
            self.c4_n = np.bincount(g).astype(float)
            rh = p1.Base._postos(hl[loc], g)
            self.c4_ch = rh - (np.bincount(g, rh) / self.c4_n)[g]
            self.c4_sh = np.sqrt(np.bincount(g, self.c4_ch ** 2))

    def _logit(self, y, w, beta, alfa, voltas):
        d = self.d
        g, X = d.uf, d.X
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


def estatisticas(b: Base, A: np.ndarray) -> dict:
    """Os componentes da leitura (T, se), versão leve, sobre a matriz com fraude."""
    d, r0 = b.d, b.r0
    V1 = A[:, W1] + A[:, P1] + A[:, O1]
    V2 = A[:, W2] + A[:, P2]
    out = {}
    # C1
    beta, alfa = b._logit(A[:, P2] / V2, V2, b.c1_beta, b.c1_alfa, 4)
    p = np.clip(expit(d.X @ beta + alfa[d.uf]), 1e-9, 1 - 1e-9)
    rho = c1._rho(A[:, P2], V2, p, d.uf)[d.uf]
    P = c1._cdf(vt.LIMIAR, V2.astype(np.int64), p, rho, p * (1 - rho) / rho, (1 - p) * (1 - rho) / rho)
    O, E = (A[:, P2] <= vt.LIMIAR).sum(), P.sum()
    out[("C1", "log O/E")] = (float(np.log((O + 0.5) / (E + 0.5))), r0["C1"]["se"])
    # C2
    nm = d.mun.max() + 1
    M = np.vstack([np.bincount(d.mun, A[:, c], nm) for c in range(9)]).T
    V1m, V2m = M[:, W1] + M[:, P1] + M[:, O1], M[:, W2] + M[:, P2]
    X = np.column_stack([M[:, P1] / V1m, M[:, W1] / V1m, M[:, O1] / V1m, M[:, BN1] / np.maximum(M[:, C1], 1)])
    g = np.zeros(nm, dtype=np.int64)
    g[d.mun] = d.uf
    pm = c1._logit_fe(X, M[:, W2] / V2m, V2m, g)
    rr = (M[:, W2] - V2m * pm) / np.sqrt(V2m * pm * (1 - pm))
    z = rr / np.sqrt((rr ** 2).sum() / (nm - X.shape[1] - g.max() - 1))
    sig = c2._bh(2 * norm.sf(np.abs(z)), 0.05)
    k = int(sig.sum())
    out[("C2", "log proporção significativa")] = (float(np.log((k + 0.5) / (nm + 0.5))), r0["C2"]["se"])
    out[("C2", "fração a favor do vencedor")] = ((sig & (z > 0)).sum() / k if k else None, r0["C2"]["se_D2"])
    # C3
    ap = d.t["aptos"]
    ok = np.isfinite(ap) & (ap > 0) & (A[:, C2] <= ap)
    # `--mediana-propria` (v3.md, análise D): o procedimento real, sem o centro do limpo.
    fit = c3.ajustar(A[ok, C2] / ap[ok], A[ok, W2] / V2[ok], centro=None if MEDIANA_PROPRIA else b.c3_centro)
    out[("C3", "f_e")] = (fit["f_e"], r0["C3"]["se_f_e"])
    out[("C3", "f_i")] = (fit["f_i"], r0["C3"]["se_f_i"])
    # C4
    if b.tem_hora:
        delta = (A[:, W2] / V2 - A[:, W1] / V1)[b.c4_idx]
        rd = p1.Base._postos(delta, b.c4_g)
        cd = rd - (np.bincount(b.c4_g, rd) / b.c4_n)[b.c4_g]
        sd = np.sqrt(np.bincount(b.c4_g, cd * cd))
        val = (b.c4_sh > 0) & (sd > 0)
        rho4 = np.bincount(b.c4_g, b.c4_ch * cd) / np.where(val, b.c4_sh * sd, 1)
        w = np.where(val, b.c4_n, 0)
        out[("C4", "correlação hora × mudança")] = (float((w * rho4).sum() / w.sum()), r0["C4"]["se"])
    # C5
    s = d.t["sem_bio"]
    if np.isfinite(s).mean() >= 0.9:
        okb = np.isfinite(s) & (A[:, C2] > 0)
        x = s[okb] / A[okb, C2]
        keep = x <= 1
        idx = np.flatnonzero(okb)[keep]
        bb, se = c5.regressao((A[:, W2] / V2 - A[:, W1] / V1)[idx], x[keep], V2[idx], d.mun[idx], d.mun[idx])
        out[("C5", "β biometria")] = (bb, se)
    # C6
    phi = c6.phi_por_grupo(A[:, W2], V2, d.mun)
    out[("C6", "log mediana de φ")] = (float(np.log(np.median(phi))), r0["C6"]["se"])
    return out


def estatisticas_completas(b: Base, A: np.ndarray) -> dict:
    """Versão "completa" do desvio de 04/11 (só para a validação): C1 de um nível exato,
    C3 com 200 reamostragens, C4 com 500 permutações em blocos."""
    import copy
    d = copy.copy(b.d)
    d.A = A
    d.V1 = A[:, W1] + A[:, P1] + A[:, O1]
    d.V2 = A[:, W2] + A[:, P2]
    d.delta = A[:, W2] / d.V2 - A[:, W1] / d.V1
    r = {"C1": vt.teste_c1(d, nivel1=True), "C2": vt.teste_c2(d), "C3": vt.teste_c3(d, voltas=200),
         "C4": vt.teste_c4(d, voltas=500) if b.tem_hora else {}, "C5": vt.teste_c5(d), "C6": vt.teste_c6(d)}
    out = {}
    for teste, nome, tirar, margem, direcao in lei.COMPONENTES:
        if r.get(teste):
            out[(teste, nome)] = tirar(r)
    return out


def detecta(est: dict, ref: dict) -> dict:
    """Regra da §3 sobre os componentes: quais testes saem atípicos."""
    p_comp, fora = {}, {}
    for (teste, nome), (t, s) in est.items():
        rf = ref.get((teste, nome))
        if rf is None or t is None or s is None:
            continue
        gl = rf["k"] - 2
        sd = np.sqrt(rf["tau2"] + rf["se_mu"] ** 2 + s ** 2)
        q = t_dist.ppf(0.975, gl)
        zz = (t - rf["mu"]) / sd
        if rf["direcao"] == "cima":
            p, f = float(t_dist.sf(zz, gl)), zz > q
        else:
            p, f = float(2 * t_dist.sf(abs(zz), gl)), abs(zz) > q
        p_comp.setdefault(teste, []).append(p)
        fora.setdefault(teste, []).append(f)
    testes = sorted(p_comp)
    pt = [min(1.0, len(p_comp[t]) * min(p_comp[t])) for t in testes]
    bh = dict(zip(testes, lei._ajuste_p(pt, "BH")))
    by = dict(zip(testes, lei._ajuste_p(pt, "BY")))
    det = {t: bool(max(bh[t], by[t]) < 0.05 and any(fora[t])) for t in testes}
    det["qualquer"] = any(det.values())
    return det


def plantar(b: Base, modo: str, desenho: str, fracao: float, tamanho: float, rng):
    d = b.d
    A = d.A.copy()
    alvo = int(round(tamanho * (A[:, W2] + A[:, P2]).sum()))
    if desenho == "aleatorio":
        sel = np.concatenate([rng.choice(np.flatnonzero(d.uf == u), max(1, int(round(fracao * (d.uf == u).sum()))),
                                         replace=False) for u in range(d.uf.max() + 1)])
    else:
        pool = {"reduto": b.reduto, "comparecimento_alto": b.comp_alto, "pouca_fiscalizacao": b.uma_secao}[desenho]
        sel = rng.choice(pool, max(1, int(round(fracao * len(pool)))), replace=False)
    cota = alvo / len(sel)
    ap = np.nan_to_num(d.t["aptos"][sel], nan=0.0)
    cabe = np.maximum(ap - A[sel, C2], 0) if modo == "enchimento" else A[sel, P2]
    k = np.minimum(cabe, np.floor(cota) + (rng.random(len(sel)) < cota - np.floor(cota)))
    A[sel, W2] += k
    if modo == "enchimento":
        A[sel, C2] += k
    else:
        A[sel, P2] -= k
    return A, alvo, int(k.sum())


def cenario(b, ref, modo, desenho, fracao, tamanho, semente, completa=False, fixo=False):
    rng = np.random.default_rng(semente)
    cont: dict = {}
    n, plantado, alvo = 0, [], 0
    while n < MAXIMO:
        for _ in range(LOTE):
            A, alvo, feito = plantar(b, modo, desenho, fracao, tamanho, rng)
            det = detecta((estatisticas_completas if completa else estatisticas)(b, A), ref)
            plantado.append(feito)
            for t, v in det.items():
                cont[t] = cont.get(t, 0) + int(v)
            n += 1
        lo, hi = p1._cp(cont.get("qualquer", 0), n)
        if fixo or lo >= 0.95 or hi < 0.80 or (lo >= 0.80 and hi < 0.95):
            break                                    # validação: 20 réplicas fixas
    lo, hi = p1._cp(cont.get("qualquer", 0), n)
    cabe = float(np.mean(plantado)) / alvo if alvo else 1.0
    return {"modo": modo, "desenho": desenho, "fracao": fracao, "tamanho": tamanho, "replicas": n,
            "votos_alvo": alvo, "votos_plantados_media": round(float(np.mean(plantado))), "cabe": bool(cabe >= 0.9),
            "deteccao": {t: round(v / n, 3) for t, v in cont.items()}, "deteccao_ic": [round(lo, 3), round(hi, 3)]}


def main() -> int:
    validar = "--validar" in sys.argv
    for base in [a for a in sys.argv[1:] if not a.startswith("--")]:
        b = Base(base)
        ref = referencia_sem(base)
        det0 = detecta(estatisticas(b, b.d.A), ref)
        out = {"base": base, "gerado_em": datetime.now().isoformat(timespec="seconds"),
               "preregistro": "docs/preregistro/v2.md §6; desvios de 04/11 (§8)",
               "sem_fraude": det0, "cenarios": []}
        print(f"{base}: sem fraude {det0}", flush=True)
        sufixo = "-validacao" if validar else "-mediana" if MEDIANA_PROPRIA else ""
        destino = V2DIR / f"poder-{base}{sufixo}.json"
        lista = ([(m, d, f, t) for (m, d), f, t in VALIDACAO] if validar else
                 [(m, d, f, t) for m, d in DESENHOS for f in FRACOES for t in TAMANHOS
                  if not MEDIANA_PROPRIA or m == "enchimento"])
        for i, (m, d, f, t) in enumerate(lista):
            t0 = datetime.now()
            c = cenario(b, ref, m, d, f, t, semente=int(base[-4:]) * 1000 + i, fixo=validar)
            if validar:
                # Mesmas sementes, versão completa; a leve vale se a detecção diferir < 10 pontos.
                cc = cenario(b, ref, m, d, f, t, semente=int(base[-4:]) * 1000 + i, completa=True, fixo=True)
                c["completa"] = cc["deteccao"]
                c["diferenca_qualquer"] = round(abs(cc["deteccao"].get("qualquer", 0) - c["deteccao"].get("qualquer", 0)), 3)
            out["cenarios"].append(c)
            destino.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item()),
                               encoding="utf-8")
            print(f"  {base} {m:10} {d:20} {100 * f:4.0f}% {100 * t:5.2f}%: qualquer "
                  f"{c['deteccao'].get('qualquer', 0):.2f} ({c['replicas']} rép., {(datetime.now() - t0).seconds}s, "
                  f"cabe={c['cabe']}) {c['deteccao']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
