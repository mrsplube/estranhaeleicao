"""v3, análise E: comparação pareada presidente × governador nas mesmas seções.

    venv/bin/python -m tools.migracoes.2026-11-05-v3-pareada

Ver `docs/preregistro/v3.md`, análise E (exploratória, posterior à v2). Eleitor,
urna e dia são os mesmos, e o contexto de UF e ano se cancela na diferença
`D = T_presidente − T_governador`, calculada para C1 (log O/E, um nível), C3 (f_e)
e C6 (log mediana de φ), com vencedor e perdedor de cada cargo.

Critério de utilidade, fixado antes: a pareada só ajuda se o desvio-padrão de D
entre as referências for menor que o τ̂ do estatístico sem parear
(`v3-referencias.json`).

Grava `apuracao/data/arquivo/2026-2t/v2/v3-pareada.json`.
"""
from __future__ import annotations

import importlib
import json
import sys

import numpy as np
from scipy.stats import t as t_dist

mv = importlib.import_module("tools.migracoes.2026-11-05-v2-multiverso")
vt = mv.vt
V2 = vt.SAIDA
TAU = {"C1": ("C1", "log O/E"), "C3": ("C3", "f_e"), "C6": ("C6", "log mediana de φ")}


def stats(d) -> dict:
    return {"C1": mv.stat_c1(d, "uf", 10)["log O/E"], "C3": mv.stat_c3(d, 100)["f_e"],
            "C6": mv.stat_c6(d, "municipio").get("log mediana de φ")}


def main() -> int:
    govs = sorted(p.stem for p in (vt.CACHE / "v2").glob("gov-*.pkl") if not p.stem.endswith(("calib", "nivel1")))
    pres = {}
    linhas = {}
    for g in govs:
        ano, uf = int(g.split("-")[1]), g.split("-")[2]
        if ano not in pres:
            pres[ano] = vt.Disputa(f"pres-{ano}")
        p = pres[ano]
        dg = vt.Disputa(g)
        kp, kg = {k: i for i, k in enumerate(p.t["chaves"])}, {k: i for i, k in enumerate(dg.t["chaves"])}
        comuns = sorted(set(kp) & set(kg))
        if len(comuns) < 1000:
            print(f"  {g}: só {len(comuns)} seções em comum; fora", flush=True)
            continue
        mp, mg = np.zeros(len(kp), bool), np.zeros(len(kg), bool)
        mp[[kp[k] for k in comuns]] = True
        mg[[kg[k] for k in comuns]] = True
        tp, tg = stats(mv.recortar(p, mp)), stats(mv.recortar(dg, mg))
        linhas[g] = {"secoes": len(comuns), "presidente": tp, "governador": tg,
                     "D": {c: (tp[c] - tg[c]) if tp[c] is not None and tg[c] is not None else None for c in TAU}}
        print(f"  {g}: {len(comuns)} seções D={linhas[g]['D']}", flush=True)
    v3 = {(c["teste"], c["componente"]): c
          for c in json.loads((V2 / "v3-referencias.json").read_text(encoding="utf-8"))["componentes"]}
    resumo = {}
    for c, chave in TAU.items():
        ref = np.array([l["D"][c] for k, l in linhas.items() if "-2026-" not in k and l["D"][c] is not None])
        alvo = {k: l["D"][c] for k, l in linhas.items() if "-2026-" in k and l["D"][c] is not None}
        m, dp, n = float(ref.mean()), float(ref.std(ddof=1)), len(ref)
        q = float(t_dist.ppf(0.975, n - 1))
        h = q * dp * np.sqrt(1 + 1 / n)
        vals = list(alvo.values())
        media = float(np.mean(vals))
        h_media = q * dp * np.sqrt(1 / len(vals) + 1 / n)
        tau = v3[chave]["todas"]["tau"]
        resumo[c] = {"k": n, "media_D": m, "dp_D": dp, "tau_sem_parear": tau, "ajuda": bool(dp < tau),
                     "intervalo": [m - h, m + h], "uf_2026": alvo,
                     "uf_fora": [k for k, v in alvo.items() if not m - h <= v <= m + h],
                     "media_2026": media, "intervalo_media": [m - h_media, m + h_media],
                     "media_fora": bool(not m - h_media <= media <= m + h_media)}
        print(f"{c}: {resumo[c]}", flush=True)
    (V2 / "v3-pareada.json").write_text(json.dumps(
        {"preregistro": "docs/preregistro/v3.md, análise E (exploratória)", "resumo": resumo, "disputas": linhas},
        ensure_ascii=False, indent=1, default=lambda o: o.item()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
