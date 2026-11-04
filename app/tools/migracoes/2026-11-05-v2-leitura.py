"""v2, Etapa 6: meta-análise de referência e leitura atípico/equivalente/inconclusivo.

    venv/bin/python -m tools.migracoes.2026-11-05-v2-leitura

Ver `docs/preregistro/v2.md` §3 e os desvios de 03 e 04/11 (§8).

Para cada componente de teste:
1. efeitos aleatórios por REML sobre as disputas de referência (2010–2022,
   presidente e governador): `μ̂`, `τ̂²`, `se_μ̂`;
2. intervalo de predição de 95% para 2026: `μ̂ ± t_{K−2}·√(τ̂² + se²_μ̂ + s²_2026)`;
3. p de atipicidade: posição de 2026 na distribuição preditiva (t, K−2 gl), na
   direção alegada (C6: bilateral);
4. TOST: IC de 90% de `T_2026 − μ̂` com `√(s²_2026 + se²_μ̂)` dentro da margem;
5. BH e BY sobre os seis p (vale o mais conservador);
6. leitura: atípico / equivalente / inconclusivo; "modelo não comparável"
   (Etapa 4) força inconclusivo.

C5 tem uma referência só (pres-2022): sem meta-análise; só equivalente ou
inconclusivo (desvio de 03/11).

Grava `apuracao/data/arquivo/2026-2t/v2/leitura.json`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import norm, t as t_dist

RAIZ = Path(__file__).resolve().parents[2]
V2 = RAIZ / "apuracao/data/arquivo/2026-2t/v2"
LOG08, LOG125 = float(np.log(0.8)), float(np.log(1.25))

# (teste, componente, como tirar (T, se) do JSON da disputa, margem (lo, hi), direção)
COMPONENTES = [
    ("C1", "log O/E", lambda r: (r["C1"].get("logT"), r["C1"].get("se")), (LOG08, LOG125), "cima"),
    ("C2", "log proporção significativa", lambda r: (r["C2"].get("logT"), r["C2"].get("se")), (LOG08, LOG125), "cima"),
    ("C2", "fração a favor do vencedor", lambda r: (r["C2"].get("D2"), r["C2"].get("se_D2")), (-0.10, 0.10), "cima"),
    ("C3", "f_e", lambda r: (r["C3"].get("f_e"), r["C3"].get("se_f_e")), (-0.001, 0.001), "cima"),
    ("C3", "f_i", lambda r: (r["C3"].get("f_i"), r["C3"].get("se_f_i")), (-0.10, 0.10), "cima"),
    ("C4", "correlação hora × mudança", lambda r: (r["C4"].get("T"), r["C4"].get("se")), (-0.01, 0.01), "cima"),
    ("C5", "β biometria", lambda r: (r["C5"].get("T"), r["C5"].get("se")), (-0.02, 0.02), "cima"),
    ("C6", "log mediana de φ", lambda r: (r["C6"].get("logT"), r["C6"].get("se")), (LOG08, LOG125), "ambos"),
]


def reml(y, v):
    """μ̂, τ̂², se(μ̂) por REML (efeitos aleatórios)."""
    def menos_l(tau2):
        w = 1 / (v + tau2)
        mu = (w * y).sum() / w.sum()
        return 0.5 * (np.log(v + tau2).sum() + np.log(w.sum()) + (w * (y - mu) ** 2).sum())
    tau2 = float(minimize_scalar(menos_l, bounds=(0, max(10 * np.var(y), 1e-8)), method="bounded").x)
    w = 1 / (v + tau2)
    mu = float((w * y).sum() / w.sum())
    return mu, tau2, float(np.sqrt(1 / w.sum()))


def _ajuste_p(p, metodo):
    p = np.asarray(p, float)
    n = len(p)
    c = np.sum(1 / np.arange(1, n + 1)) if metodo == "BY" else 1.0
    o = np.argsort(p)
    aj = np.empty(n)
    aj[o] = np.minimum.accumulate((p[o] * n * c / np.arange(1, n + 1))[::-1])[::-1]
    return np.minimum(aj, 1)


def main() -> int:
    disputas = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in V2.glob("*.json")
                if p.stem.startswith(("pres-", "gov-")) and not p.stem.endswith("nivel1")}
    calib = json.loads((V2 / "calibracao.json").read_text(encoding="utf-8"))["leitura_2026"]
    ref = {k: r for k, r in disputas.items() if r["ano"] != 2026}
    alvo = {k: r for k, r in disputas.items() if r["ano"] == 2026}
    resultado = {}
    for k26, r26 in sorted(alvo.items()):
        comps = []
        for teste, nome, tirar, (mlo, mhi), direcao in COMPONENTES:
            t26, s26 = tirar(r26) if r26.get(teste) else (None, None)
            pares = [(tirar(r)) for r in ref.values() if r.get(teste)]
            pares = [(y, s) for y, s in pares if y is not None and s is not None and s > 0]
            c = {"teste": teste, "componente": nome, "T_2026": t26, "se_2026": s26, "k": len(pares),
                 "margem": [mlo, mhi], "direcao": direcao}
            if t26 is None or s26 is None or not pares:
                c["leitura"] = "sem dado"
                comps.append(c)
                continue
            y = np.array([p[0] for p in pares])
            v = np.array([p[1] ** 2 for p in pares])
            if len(pares) >= 3:
                mu, tau2, se_mu = reml(y, v)
                gl = len(pares) - 2
                sd_pred = float(np.sqrt(tau2 + se_mu ** 2 + s26 ** 2))
                q = float(t_dist.ppf(0.975, gl))
                z = (t26 - mu) / sd_pred
                p = float(t_dist.sf(z, gl)) if direcao == "cima" else float(2 * t_dist.sf(abs(z), gl))
                c.update({"mu": mu, "tau2": tau2, "se_mu": se_mu, "pi": [mu - q * sd_pred, mu + q * sd_pred],
                          "p": p, "percentil": float((y < t26).mean())})
            else:
                # Referência única (C5): sem distribuição; só equivalência.
                mu, se_mu = float(y.mean()), float(np.sqrt(v.mean()))
                c.update({"mu": mu, "tau2": None, "se_mu": se_mu, "pi": None, "p": None, "percentil": None})
            d = t26 - mu
            sd_d = float(np.sqrt(s26 ** 2 + se_mu ** 2))
            ic90 = [d - 1.645 * sd_d, d + 1.645 * sd_d]
            c.update({"diferenca": d, "ic90": ic90, "equivalente": bool(mlo <= ic90[0] and ic90[1] <= mhi)})
            if c["pi"] is not None:
                fora = t26 > c["pi"][1] if direcao == "cima" else (t26 > c["pi"][1] or t26 < c["pi"][0])
                c["fora_do_intervalo"] = bool(fora)
            comps.append(c)
        # p por teste (Bonferroni interno quando há dois componentes) e ajuste entre testes.
        testes = sorted({c["teste"] for c in comps})
        p_teste = {}
        for t_ in testes:
            ps = [c["p"] for c in comps if c["teste"] == t_ and c.get("p") is not None]
            p_teste[t_] = min(1.0, len(ps) * min(ps)) if ps else None
        com_p = [t_ for t_ in testes if p_teste[t_] is not None]
        bh = dict(zip(com_p, _ajuste_p([p_teste[t_] for t_ in com_p], "BH")))
        by = dict(zip(com_p, _ajuste_p([p_teste[t_] for t_ in com_p], "BY")))
        leitura = {}
        for t_ in testes:
            cs = [c for c in comps if c["teste"] == t_]
            if any(c["leitura"] == "sem dado" for c in cs if "leitura" in c) and all(c.get("leitura") == "sem dado" for c in cs):
                leitura[t_] = "sem dado"
                continue
            p_aj = max(bh.get(t_, 1), by.get(t_, 1)) if t_ in bh else None
            nao_comp = calib.get(k26, {}).get(t_) == "modelo não comparável"
            atip = (p_aj is not None and p_aj < 0.05 and any(c.get("fora_do_intervalo") for c in cs))
            equiv = all(c.get("equivalente") for c in cs if c.get("leitura") != "sem dado")
            if nao_comp:
                leitura[t_] = "inconclusivo (modelo não comparável)"
            elif atip:
                leitura[t_] = "atípico"
            elif equiv:
                leitura[t_] = "equivalente"
            else:
                leitura[t_] = "inconclusivo"
            for c in cs:
                c["p_teste"], c["p_bh"], c["p_by"] = p_teste[t_], bh.get(t_), by.get(t_)
        resultado[k26] = {"leitura": leitura, "componentes": comps}
        print(f"{k26}: {leitura}", flush=True)
    out = {"preregistro": "docs/preregistro/v2.md §3; desvios de 03 e 04/11 (§8)",
           "referencias": sorted(ref), "disputas_2026": resultado}
    (V2 / "leitura.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item()),
                                     encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
