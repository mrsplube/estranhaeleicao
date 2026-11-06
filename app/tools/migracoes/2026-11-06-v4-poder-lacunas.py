"""v4, análise G: por que a detecção do enchimento falha em 2018 e com 50% das seções.

    venv/bin/python -m tools.migracoes.2026-11-06-v4-poder-lacunas pres-2010 pres-2018 ...

Ver `docs/preregistro/v4.md`. Não muda a curva de poder. Sementes do P1.
Grava `apuracao/data/arquivo/2026-2t/v2/v4-poder-{base}.json`.
"""
from __future__ import annotations

import importlib
import json
import sys

import numpy as np
from scipy.stats import t as t_dist

pod = importlib.import_module("tools.migracoes.2026-11-05-v2-poder")
lei = pod.lei
INDICES = {0.20: 24, 0.50: 29}
REPLICAS = 20


def detalhar(est, ref):
    linhas = {}
    for (teste, nome), (t, s) in est.items():
        rf = ref.get((teste, nome))
        if rf is None or t is None or s is None:
            continue
        gl = rf["k"] - 2
        sd = float(np.sqrt(rf["tau2"] + rf["se_mu"] ** 2 + s ** 2))
        z = (t - rf["mu"]) / sd
        q = float(t_dist.ppf(0.975, gl))
        linhas[f"{teste} {nome}"] = {"t": float(t), "s": float(s), "mu": rf["mu"], "tau": float(np.sqrt(rf["tau2"])),
                                     "z": float(z), "q": q, "fora": bool(z > q if rf["direcao"] == "cima" else abs(z) > q),
                                     "p": float(t_dist.sf(z, gl)) if rf["direcao"] == "cima" else float(2 * t_dist.sf(abs(z), gl))}
    return {"componentes": linhas, "detecta": pod.detecta(est, ref)}


def main() -> int:
    for base in sys.argv[1:]:
        b = pod.Base(base)
        ref = pod.referencia_sem(base)
        out = {"base": base, "preregistro": "docs/preregistro/v4.md, análise G", "sem_fraude": detalhar(pod.estatisticas(b, b.d.A), ref),
               "cenarios": []}
        for fr, i in INDICES.items():
            rng = np.random.default_rng(int(base[-4:]) * 1000 + i)
            reps = []
            for _ in range(REPLICAS):
                A, alvo, feito = pod.plantar(b, "enchimento", "aleatorio", fr, 0.0357, rng)
                reps.append(detalhar(pod.estatisticas(b, A), ref))
            out["cenarios"].append({"fracao": fr, "alvo": alvo, "replicas": reps})
            det = np.mean([r["detecta"]["qualquer"] for r in reps])
            med = {k: float(np.median([r["componentes"][k]["t"] for r in reps])) for k in ("C3 f_e", "C3 f_i")}
            print(f"{base} {fr}: detecção {det:.2f} {med}", flush=True)
            (pod.V2DIR / f"v4-poder-{base}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
