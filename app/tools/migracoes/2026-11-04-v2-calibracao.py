"""v2, Etapa 4: calibração dos modelos nulos em todas as disputas.

    venv/bin/python -m tools.migracoes.2026-11-04-v2-calibracao

Ver `docs/preregistro/v2.md` §4 e o desvio de 04/11 (§8): a comparabilidade usa
só estatísticas de FORMA, que não são o estatístico do teste.

- C1: inclinação da reta de calibração — regressão logística da indicadora
  "perdedor ≤ 10" sobre o logit da probabilidade prevista da seção. Modelo bem
  calibrado: inclinação 1.
- C2: distância de Kolmogorov-Smirnov entre os resíduos municipais padronizados
  e a N(0, 1).
- C3: log do erro quadrático do ajuste de Klimek.

Intervalo de predição empírico sobre as disputas de referência (todas, menos
2026): `média ± t_{K−1} · dp · √(1 + 1/K)`. Disputa de 2026 fora dele → o teste
correspondente é "modelo não comparável" nela.

Grava `apuracao/data/arquivo/2026-2t/v2/calibracao.json`.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
from scipy.special import expit, logit
from scipy.stats import kstest, t as t_dist

RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / "apuracao/cache/v2"
SAIDA = RAIZ / "apuracao/data/arquivo/2026-2t/v2"


def inclinacao_calibracao(prob, obs) -> float | None:
    """Inclinação b de logit P(obs) = a + b·logit(prob), por IRLS."""
    ok = (prob > 1e-8) & (prob < 1 - 1e-8)
    if ok.sum() < 100 or obs[ok].sum() < 5:
        return None
    x = logit(prob[ok])
    y = obs[ok].astype(float)
    X = np.column_stack([np.ones_like(x), x])
    beta = np.array([0.0, 1.0])
    for _ in range(50):
        p = expit(X @ beta)
        w = p * (1 - p)
        passo = np.linalg.solve(X.T @ (X * w[:, None]) + 1e-9 * np.eye(2), X.T @ (y - p))
        beta += passo
        if np.abs(passo).max() < 1e-8:
            break
    return float(beta[1])


def _intervalo(valores):
    v = np.array([x for x in valores if x is not None and np.isfinite(x)])
    k = len(v)
    if k < 3:
        return None
    m, dp = float(v.mean()), float(v.std(ddof=1))
    h = float(t_dist.ppf(0.975, k - 1) * dp * np.sqrt(1 + 1 / k))
    return {"k": k, "media": m, "dp": dp, "lo": m - h, "hi": m + h}


def main() -> int:
    disputas = sorted(p.stem for p in SAIDA.glob("*.json")
                      if p.stem.startswith(("pres-", "gov-")) and not p.stem.endswith("nivel1"))
    linhas = {}
    for d in disputas:
        r = json.loads((SAIDA / f"{d}.json").read_text(encoding="utf-8"))
        cal = pickle.loads((CACHE / f"{d}-calib.pkl").read_bytes())
        l = {"C1": None, "C2": None, "C3": None}
        if "C1" in cal:
            l["C1"] = inclinacao_calibracao(cal["C1"]["E_secao"], cal["C1"]["obs"])
        if "C2" in cal:
            l["C2"] = float(kstest(cal["C2"]["z"], "norm").statistic)
        if r.get("C3", {}).get("erro_ajuste"):
            l["C3"] = float(np.log(r["C3"]["erro_ajuste"]))
        linhas[d] = l
    ref = [d for d in linhas if not d.endswith("2026") and "-2026" not in d]
    intervalos = {c: _intervalo([linhas[d][c] for d in ref]) for c in ("C1", "C2", "C3")}
    leitura = {}
    for d in linhas:
        if "2026" not in d:
            continue
        leitura[d] = {}
        for c, iv in intervalos.items():
            v = linhas[d][c]
            leitura[d][c] = ("sem dado" if v is None or iv is None else
                             "comparável" if iv["lo"] <= v <= iv["hi"] else "modelo não comparável")
    out = {"preregistro": "docs/preregistro/v2.md §4 e desvio de 04/11 (§8)",
           "estatisticas": {"C1": "inclinação da calibração", "C2": "KS dos resíduos contra N(0,1)",
                            "C3": "log do erro do ajuste de Klimek"},
           "referencias": ref, "intervalos": intervalos, "por_disputa": linhas, "leitura_2026": leitura}
    (SAIDA / "calibracao.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for d, l in leitura.items():
        print(f"  {d}: {l}")
    for c, iv in intervalos.items():
        print(f"  {c}: {iv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
