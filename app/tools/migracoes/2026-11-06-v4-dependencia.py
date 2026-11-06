"""v4, análise F: sensibilidade da leitura à dependência entre disputas.

    venv/bin/python -m tools.migracoes.2026-11-06-v4-dependencia

Ver `docs/preregistro/v4.md`. Nada aqui muda a leitura da v2.

Grava `apuracao/data/arquivo/2026-2t/v2/v4-dependencia.json`.
"""
from __future__ import annotations

import importlib
import json
import sys

import numpy as np
from scipy.optimize import minimize
from scipy.stats import t as t_dist

lei = importlib.import_module("tools.migracoes.2026-11-05-v2-leitura")
V2 = lei.V2


def reml_niveis(y, v, grupos):
    """REML com um efeito aleatório por grupo, mais o da disputa. Devolve μ, variâncias e se(μ)."""
    n = len(y)
    Zs = [(g[:, None] == g[None, :]).astype(float) for g in grupos] + [np.eye(n)]
    X = np.ones(n)
    escala = max(float(np.var(y)), 1e-10)

    def V(th):
        return np.diag(v) + sum(np.exp(a) * escala * Z for a, Z in zip(th, Zs))

    def menos_l(th):
        M = V(th)
        sinal, ld = np.linalg.slogdet(M)
        Mi = np.linalg.inv(M)
        w = X @ Mi @ X
        mu = (X @ Mi @ y) / w
        r = y - mu
        return 0.5 * (ld + np.log(w) + r @ Mi @ r)

    melhor = None
    for ini in (-1.0, -4.0, -12.0, -25.0):       # várias partidas: a verossimilhança pode ter ótimo em zero
        th0 = np.full(len(Zs), ini)
        f = minimize(menos_l, th0, method="L-BFGS-B", bounds=[(-25, 6)] * len(Zs))
        if melhor is None or f.fun < melhor.fun:
            melhor = f
    tau2 = np.exp(melhor.x) * escala
    Mi = np.linalg.inv(V(melhor.x))
    w = X @ Mi @ X
    return float((X @ Mi @ y) / w), [float(x) for x in tau2], float(np.sqrt(1 / w))



def componente(teste, nome, tirar, margem, direcao, refs, r26, modelo):
    t26, s26 = tirar(r26) if r26.get(teste) else (None, None)
    linhas = [(tirar(r), r) for r in refs if r.get(teste)]
    linhas = [(p, r) for p, r in linhas if p[0] is not None and p[1] is not None and p[1] > 0]
    y = np.array([p[0] for p, _ in linhas])
    v = np.array([p[1] ** 2 for p, _ in linhas])
    anos = np.array([r["ano"] for _, r in linhas])
    ufs = np.array([r["id"].split("-")[-1] if r["cargo"] == "governador" else "BR" for _, r in linhas])
    A = len(set(anos))
    if t26 is None or A < 3:
        return {"teste": teste, "componente": nome, "aplicavel": False, "k": len(y), "anos": int(A)}
    if modelo == "F1":
        mu, (ta, tb), se_mu = reml_niveis(y, v, [anos])
        tu = 0.0
    else:
        mu, (ta, tu, tb), se_mu = reml_niveis(y, v, [anos, ufs])
    sd = float(np.sqrt(ta + tu + tb + se_mu ** 2 + s26 ** 2))
    sd_d = float(np.sqrt(s26 ** 2 + se_mu ** 2))
    d = t26 - mu
    saida = {"teste": teste, "componente": nome, "aplicavel": True, "k": len(y), "anos": int(A), "mu": mu,
             "tau2_ano": ta, "tau2_uf": tu, "tau2_disputa": tb, "se_mu": se_mu,
             "fracao_ano": ta / (ta + tb) if ta + tb else 0.0,
             "equivalente": bool(margem[0] <= d - 1.645 * sd_d and d + 1.645 * sd_d <= margem[1])}
    for rot, gl in (("gl_K", len(y) - 2), ("gl_A", A - 2)):
        z, q = d / sd, float(t_dist.ppf(0.975, gl))
        saida[rot] = {"gl": gl, "pi": [mu - q * sd, mu + q * sd],
                      "p": float(t_dist.sf(z, gl)) if direcao == "cima" else float(2 * t_dist.sf(abs(z), gl)),
                      "fora": bool(z > q) if direcao == "cima" else bool(abs(z) > q)}
    return saida


def leitura(comps, rot):
    """Regra da §3 sobre os componentes aplicáveis."""
    testes = sorted({c["teste"] for c in comps if c["aplicavel"]})
    pt = {t: min(1.0, sum(c["teste"] == t for c in comps) * min(c[rot]["p"] for c in comps if c["teste"] == t))
          for t in testes}
    bh = dict(zip(testes, lei._ajuste_p([pt[t] for t in testes], "BH")))
    by = dict(zip(testes, lei._ajuste_p([pt[t] for t in testes], "BY")))
    out = {}
    for t in testes:
        cs = [c for c in comps if c["teste"] == t]
        if max(bh[t], by[t]) < 0.05 and any(c[rot]["fora"] for c in cs):
            out[t] = "atípico"
        else:
            out[t] = "equivalente" if all(c["equivalente"] for c in cs) else "inconclusivo"
    return out


def deixa_ano(refs, r26, ano):
    """A análise principal sem as disputas de um ano."""
    resto = [r for r in refs if r["ano"] != ano]
    comps = []
    for teste, nome, tirar, margem, direcao in lei.COMPONENTES:
        t26, s26 = tirar(r26) if r26.get(teste) else (None, None)
        pares = [tirar(r) for r in resto if r.get(teste)]
        pares = [(y, s) for y, s in pares if y is not None and s is not None and s > 0]
        if t26 is None or len(pares) < 3:
            comps.append({"teste": teste, "aplicavel": False})
            continue
        y, v = np.array([p[0] for p in pares]), np.array([p[1] ** 2 for p in pares])
        mu, tau2, se_mu = lei.reml(y, v)
        gl = len(y) - 2
        sd, q = float(np.sqrt(tau2 + se_mu ** 2 + s26 ** 2)), float(t_dist.ppf(0.975, gl))
        z = (t26 - mu) / sd
        d, sd_d = t26 - mu, float(np.sqrt(s26 ** 2 + se_mu ** 2))
        comps.append({"teste": teste, "componente": nome, "aplicavel": True, "k": len(y),
                      "pp": {"p": float(t_dist.sf(z, gl)) if direcao == "cima" else float(2 * t_dist.sf(abs(z), gl)),
                             "fora": bool(z > q) if direcao == "cima" else bool(abs(z) > q)},
                      "equivalente": bool(margem[0] <= d - 1.645 * sd_d and d + 1.645 * sd_d <= margem[1])})
    return leitura(comps, "pp"), comps


def main() -> int:
    ds = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in V2.glob("*.json")
          if p.stem.startswith(("pres-", "gov-")) and not p.stem.endswith("nivel1")}
    r26 = ds["pres-2026"]
    refs = [r for r in ds.values() if r["ano"] != 2026]
    principal = json.loads((V2 / "leitura.json").read_text(encoding="utf-8"))["disputas_2026"]["pres-2026"]["leitura"]
    out = {"preregistro": "docs/preregistro/v4.md, análise F (posterior aos resultados)", "principal": principal}
    for modelo in ("F1", "F2"):
        comps = [componente(t, n, f, m, d, refs, r26, modelo) for t, n, f, m, d in lei.COMPONENTES]
        out[modelo] = {"componentes": comps, "leitura_gl_K": leitura(comps, "gl_K"), "leitura_gl_A": leitura(comps, "gl_A")}
        print(modelo, "gl_K", out[modelo]["leitura_gl_K"], "\n   gl_A", out[modelo]["leitura_gl_A"], flush=True)
        for c in comps:
            if c["aplicavel"]:
                print(f"  {c['teste']} {c['componente'][:26]:26} k={c['k']} μ={c['mu']:.4g} τa={c['tau2_ano']**.5:.3g} "
                      f"τu={c['tau2_uf']**.5:.3g} τb={c['tau2_disputa']**.5:.3g} ano%={c['fracao_ano']:.2f} "
                      f"seμ={c['se_mu']:.3g} eq={c['equivalente']} pK={c['gl_K']['p']:.3g} pA={c['gl_A']['p']:.3g}", flush=True)
    out["F3"] = {}
    for ano in (2010, 2014, 2018, 2022):
        l, comps = deixa_ano(refs, r26, ano)
        out["F3"][str(ano)] = {"leitura": l, "componentes": comps}
        print("F3 sem", ano, l, flush=True)
    testes = sorted(principal)
    mudam = {}
    for rot, lt in (("F1", out["F1"]["leitura_gl_K"]), ("F2", out["F2"]["leitura_gl_K"]),
                    *[(f"F3 sem {a}", out["F3"][str(a)]["leitura"]) for a in (2010, 2014, 2018, 2022)]):
        m = {t: lt[t] for t in testes if t in lt and lt[t] != principal[t]}
        if m:
            mudam[rot] = m
    out["mudancas_contra_a_principal"] = mudam
    print("mudanças:", mudam, flush=True)
    (V2 / "v4-dependencia.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item()),
                                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
