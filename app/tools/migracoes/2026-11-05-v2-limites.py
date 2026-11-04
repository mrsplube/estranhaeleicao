"""v2, Etapa 8: limites (identificação parcial) para o voto da terceira via em 2026.

    venv/bin/python -m tools.migracoes.2026-11-05-v2-limites

Ver `docs/preregistro/v2.md` §7: a transição sai do corpo do artigo e vira
apêndice, como identificação parcial (Duncan e Davis, 1953; Manski, 2003).

Pergunta: que fração λ dos votos da terceira via no 1º turno (O1) foi para o
vencedor no 2º? Em cada município, com G = W2 − W1 (o ganho do vencedor):

    G = λ·O1 + c·P1 + β·BN1 + π·N − saídas

onde c, β, π ∈ [0, 1] são as frações do perdedor, de brancos e nulos e dos
eleitores novos (N = max(0, C2 − C1)) que foram ao vencedor. Sem mais
hipóteses, o dado só dá um intervalo para λ. Duas hipóteses, cada uma com o
seu intervalo:

- H1: quem votou no vencedor no 1º turno votou nele de novo (saídas = 0).
  λ ∈ [max(0, (G − P1 − BN1 − N)/O1), min(1, G/O1)].
- H1 + H2: além disso, ninguém trocou o perdedor pelo vencedor (c = 0).
  λ ∈ [max(0, (G − BN1 − N)/O1), min(1, G/O1)].

O intervalo nacional é a média dos limites municipais ponderada por O1. Não é
teste de nenhuma acusação: mostra o que o dado identifica sem modelo.

Grava `apuracao/data/arquivo/2026-2t/v2/limites.json`.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / "apuracao/cache/v2"
SAIDA = RAIZ / "apuracao/data/arquivo/2026-2t/v2/limites.json"
W1, P1, O1, BN1, C1, W2, P2, BN2, C2 = range(9)


def limites(ident: str) -> dict:
    t = pickle.loads((CACHE / f"{ident}.pkl").read_bytes())
    ch = t["chaves"]
    mun = np.unique([f"{k[0]}{k[1]}" for k in ch], return_inverse=True)[1]
    nm = mun.max() + 1
    M = np.vstack([np.bincount(mun, t["A"][:, c], nm) for c in range(9)]).T
    ok = M[:, O1] > 0
    M = M[ok]
    G = M[:, W2] - M[:, W1]
    N = np.maximum(M[:, C2] - M[:, C1], 0)
    o1 = M[:, O1]
    hi = np.clip(G / o1, 0, 1)
    lo_h1 = np.clip((G - M[:, P1] - M[:, BN1] - N) / o1, 0, 1)
    lo_h2 = np.clip((G - M[:, BN1] - N) / o1, 0, 1)
    # Municípios em que H1 é incompatível com o dado (o vencedor perdeu votos).
    incompat = int((G < 0).sum())
    w = o1 / o1.sum()
    larg_h1, larg_h2 = hi - lo_h1, hi - lo_h2
    return {"disputa": ident, "municipios": int(ok.sum()), "votos_terceira_via": int(o1.sum()),
            "municipios_onde_vencedor_perdeu_votos": incompat,
            "H1": {"nacional": [float((w * lo_h1).sum()), float((w * hi).sum())],
                   "largura_mediana": float(np.median(larg_h1)),
                   "municipios_com_intervalo_estreito": int((larg_h1 <= 0.5).sum())},
            "H1_H2": {"nacional": [float((w * lo_h2).sum()), float((w * hi).sum())],
                      "largura_mediana": float(np.median(larg_h2)),
                      "municipios_com_intervalo_estreito": int((larg_h2 <= 0.5).sum())}}


def main() -> int:
    out = {"preregistro": "docs/preregistro/v2.md §7",
           "hipoteses": {"H1": "quem votou no vencedor no 1º turno votou nele de novo",
                         "H2": "ninguém trocou o perdedor pelo vencedor"},
           "disputas": [limites(k) for k in ("pres-2026", "pres-2022", "pres-2018", "pres-2014", "pres-2010")]}
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for d in out["disputas"]:
        print(f"  {d['disputa']}: H1 {np.round(d['H1']['nacional'], 3)}  H1+H2 {np.round(d['H1_H2']['nacional'], 3)}  "
              f"incompatíveis {d['municipios_onde_vencedor_perdeu_votos']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
