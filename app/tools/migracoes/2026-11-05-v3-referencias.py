"""v3, análises A e B: poder do TOST e leitura por cargo (posteriores à v2).

    venv/bin/python -m tools.migracoes.2026-11-05-v3-referencias

Ver `docs/preregistro/v3.md`. Nada aqui muda a leitura da v2.

A. Poder do TOST: P(IC90 dentro da margem | T_2026 ~ N(μ̂, τ̂²)).
B. A regra da §3 da v2 com três referências (todas, governadores, presidenciais)
   e a heterogeneidade de cada grupo.

Grava `apuracao/data/arquivo/2026-2t/v2/v3-referencias.json`.
"""
from __future__ import annotations

import importlib
import json
import sys

import numpy as np
from scipy.stats import norm, t as t_dist

lei = importlib.import_module("tools.migracoes.2026-11-05-v2-leitura")
V2 = lei.V2


def poder_tost(tau2, sd_d, mhi):
    """Chance de o IC90 caber na margem, se 2026 fosse uma disputa sorteada da classe."""
    folga = mhi - 1.645 * sd_d
    if folga <= 0:
        return 0.0
    tau = np.sqrt(tau2)
    return 1.0 if tau == 0 else float(norm.cdf(folga / tau) - norm.cdf(-folga / tau))


def ler(pares, t26, s26, margem, direcao):
    y = np.array([p[0] for p in pares])
    v = np.array([p[1] ** 2 for p in pares])
    k = len(y)
    if k < 3:
        return {"k": k, "media": float(y.mean()) if k else None}
    mu, tau2, se_mu = lei.reml(y, v)
    gl = k - 2
    sd = float(np.sqrt(tau2 + se_mu ** 2 + s26 ** 2))
    q = float(t_dist.ppf(0.975, gl))
    z = (t26 - mu) / sd
    p = float(t_dist.sf(z, gl)) if direcao == "cima" else float(2 * t_dist.sf(abs(z), gl))
    fora = bool(z > q) if direcao == "cima" else bool(abs(z) > q)
    sd_d = float(np.sqrt(s26 ** 2 + se_mu ** 2))
    d = t26 - mu
    return {"k": k, "mu": mu, "tau2": tau2, "tau": float(np.sqrt(tau2)), "se_mu": se_mu,
            "pi": [mu - q * sd, mu + q * sd], "p": p, "fora_do_intervalo": fora,
            "percentil": float((y < t26).mean()), "diferenca": d,
            "equivalente": bool(margem[0] <= d - 1.645 * sd_d and d + 1.645 * sd_d <= margem[1]),
            "poder_tost": poder_tost(tau2, sd_d, margem[1])}


def main() -> int:
    ds = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in V2.glob("*.json")
          if p.stem.startswith(("pres-", "gov-")) and not p.stem.endswith("nivel1")}
    r26 = ds["pres-2026"]
    refs = {"todas": [r for r in ds.values() if r["ano"] != 2026],
            "governadores": [r for r in ds.values() if r["ano"] != 2026 and r["cargo"] == "governador"],
            "presidenciais": [r for r in ds.values() if r["ano"] != 2026 and r["cargo"] == "presidente"]}
    saida = []
    for teste, nome, tirar, margem, direcao in lei.COMPONENTES:
        t26, s26 = tirar(r26) if r26.get(teste) else (None, None)
        if t26 is None:
            continue
        linha = {"teste": teste, "componente": nome, "T_2026": t26, "se_2026": s26, "margem": list(margem)}
        for grupo, rs in refs.items():
            pares = [tirar(r) for r in rs if r.get(teste)]
            pares = [(y, s) for y, s in pares if y is not None and s is not None and s > 0]
            linha[grupo] = ler(pares, t26, s26, margem, direcao)
        g, pr = linha["governadores"], linha["presidenciais"]
        if g.get("mu") is not None and pr.get("mu") is not None:
            dif = pr["mu"] - g["mu"]
            sd = float(np.hypot(pr["se_mu"], g["se_mu"]))
            linha["presidente_menos_governador"] = {"diferenca": dif, "se": sd, "z": dif / sd if sd else None}
        saida.append(linha)
        f = lambda d: (f"k={d['k']} τ={d.get('tau', float('nan')):.3g} μ={d.get('mu', float('nan')):.3g} "
                       f"pct={d.get('percentil', float('nan')):.2f} p={d.get('p', float('nan')):.3g} "
                       f"fora={d.get('fora_do_intervalo')} eq={d.get('equivalente')} podTOST={d.get('poder_tost', float('nan')):.2f}")
        print(f"{teste} {nome[:24]:24} T26={t26:.4g}\n   todas {f(linha['todas'])}\n   gov   {f(g)}\n   pres  {f(pr)}", flush=True)
    (V2 / "v3-referencias.json").write_text(
        json.dumps({"preregistro": "docs/preregistro/v3.md, análises A e B (posteriores à v2)", "componentes": saida},
                   ensure_ascii=False, indent=1, default=lambda o: o.item()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
