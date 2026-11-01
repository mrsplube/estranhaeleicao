"""Teste C6 do pré-registro: homogeneidade entre seções do mesmo município.

    venv/bin/python -m tools.migracoes.2026-11-01-c6-dispersao

## O que testa (docs/preregistro/README.md, seção 4, C6, e os esclarecimentos de 01/11)

Várias acusações dizem, sem usar a palavra, que o resultado é "uniforme
demais" (todas as urnas iguais, como se viessem de uma fórmula) ou "disperso
demais" (urnas vizinhas com resultados que não combinam). As duas coisas se
medem pela dispersão das seções do município em torno da fatia municipal,
comparada com a que uma binomial daria.

- `φ_m` = qui-quadrado de Pearson / (seções − 1), da fatia do 13 no 2º turno,
  em municípios com ≥ 10 seções; `M6` = mediana dos `φ_m`.
- Atípico se a razão `M6_2026 / M6_2022`, com IC de 95% por reamostragem de
  municípios, ficar inteira fora de [0,8; 1,25].
"""
from __future__ import annotations

import importlib
import json
import pickle
import sys
from datetime import datetime

import numpy as np

c1 = importlib.import_module("tools.migracoes.2026-11-01-c1-secoes-zeradas")
L2, F2 = c1.L2, c1.F2
CACHE, ARQUIVO, ANALISE, RAIZ = c1.CACHE, c1.ARQUIVO, c1.ANALISE, c1.RAIZ
DESTINO = ARQUIVO / "c6.json"
MIN_SECOES = 10
VOLTAS = 2000
FAIXA = (0.8, 1.25)


def phi_por_grupo(x, n, g):
    """φ de cada grupo com ≥ MIN_SECOES seções."""
    k = np.bincount(g)
    p = np.bincount(g, x) / np.bincount(g, n)
    pg = p[g]
    ok = (pg > 0) & (pg < 1)
    chi = np.bincount(g[ok], (x[ok] - n[ok] * pg[ok]) ** 2 / (n[ok] * pg[ok] * (1 - pg[ok])), len(k))
    usar = (k >= MIN_SECOES) & (p > 0) & (p < 1)
    return chi[usar] / (k[usar] - 1)


def _presidente(ano, piso, sem_red, red, grupo):
    chaves, A = c1._tabela(ano)
    x, n, rot = [], [], []
    for k, a in zip(chaves, A):
        v2 = a[L2] + a[F2]
        if k[0] == "zz" or v2 <= 0 or a[c1.C2] < piso or (sem_red and k in red):
            continue
        x.append(a[L2]); n.append(v2)
        rot.append(str((k[0], k[1]) if grupo == "municipio" else (k[0], k[2])))
    return np.array(x, float), np.array(n, float), np.unique(rot, return_inverse=True)[1]


def _governador():
    bu = pickle.loads((CACHE / "bu_secao_2026.pkl").read_bytes())
    por_uf: dict = {}
    for k, b in bu.items():
        if "gov" in b:
            t = por_uf.setdefault(k[0], {})
            for nr, q in b["gov"].items():
                t[nr] = t.get(nr, 0) + q
    venc = {uf: max(t, key=t.get) for uf, t in por_uf.items()}
    x, n, rot = [], [], []
    for k, b in bu.items():
        if "gov" in b and b.get("gov_validos", 0) > 0:
            x.append(b["gov"].get(venc[k[0]], 0)); n.append(b["gov_validos"]); rot.append(str((k[0], k[1])))
    return np.array(x, float), np.array(n, float), np.unique(rot, return_inverse=True)[1]


def _boot_mediana(phi, rng):
    return np.array([np.median(phi[rng.integers(0, len(phi), len(phi))]) for _ in range(VOLTAS)])


def rodar(piso=0, sem_red=False, grupo="municipio", red=frozenset()):
    rng = np.random.default_rng(20261101)
    phis, out = {}, {}
    for ano in (2026, 2022):
        phi = phi_por_grupo(*_presidente(ano, piso, sem_red, red, grupo))
        phis[ano] = phi
        out[str(ano)] = {"grupos": int(len(phi)), "m6": round(float(np.median(phi)), 4),
                         "p25": round(float(np.percentile(phi, 25)), 4), "p75": round(float(np.percentile(phi, 75)), 4)}
    razao = out["2026"]["m6"] / out["2022"]["m6"]
    b = _boot_mediana(phis[2026], rng) / _boot_mediana(phis[2022], rng)
    ic = [round(float(np.percentile(b, 2.5)), 4), round(float(np.percentile(b, 97.5)), 4)]
    p = float(min(1.0, 2 * min((b <= 1).mean(), (b >= 1).mean())))
    fora = ic[0] > FAIXA[1] or ic[1] < FAIXA[0]
    return {"especificacao": {"piso_comparecimento": piso, "sem_red": sem_red, "grupo": grupo},
            "series": out, "razao": round(razao, 4), "razao_ic": ic, "p_c6": round(p, 5),
            "dentro_da_faixa": bool(FAIXA[0] <= ic[0] and ic[1] <= FAIXA[1]),
            "fora_da_referencia": bool(fora)}


def gravar_analise(r: dict) -> None:
    a = json.loads(ANALISE.read_text(encoding="utf-8"))
    p = r["principal"]
    s26, s22 = p["series"]["2026"], p["series"]["2022"]
    br = lambda x, c=2: c1._br(x, c)
    if not r["robusto"]:
        decisao, abre = "frágil", "Depende da especificação. "
    elif r["decisao"] == "compatível":
        decisao, abre = "compatível", "Compatível com 2022. "
    else:
        decisao, abre = r["decisao"], "Fora da referência; a decisão final depende da correção para os seis testes. "
    texto = (f"{abre}As seções de um mesmo município variam {br(s26['m6'])} vezes o que uma binomial daria em 2026 "
             f"(mediana de {br(s26['grupos'], 0)} municípios), contra {br(s22['m6'])} em 2022. A razão é "
             f"{br(p['razao'])} (IC de {br(p['razao_ic'][0])} a {br(p['razao_ic'][1])}); a faixa de equivalência é "
             f"de 0,8 a 1,25. ")
    if p["dentro_da_faixa"]:
        texto += "O intervalo fica inteiro dentro da faixa: a dispersão de 2026 é equivalente à de 2022. "
    if "governador" in r:
        texto += f"No governador de 2026, nas mesmas urnas: {br(r['governador']['m6'])}. "
    texto += f"Mesma decisão em {r['multiverso_mesma_decisao'].replace('/', ' de ')} especificações."
    for t in a["testes"]:
        if t["id"] == "C6":
            t.update({"status": "feito", "decisao": decisao, "resultado": texto,
                      "dados": "/apuracao/explicacao/c6.json"})
    a["atualizado_em"] = r["gerado_em"][:10]
    ANALISE.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    red = frozenset(c1._red_2026())
    principal = rodar(red=red)
    print(json.dumps(principal, ensure_ascii=False, indent=1), flush=True)
    decisao = "pendente do BH" if principal["fora_da_referencia"] else "compatível"
    print(f"decisão: {decisao}", flush=True)
    pg = phi_por_grupo(*_governador())
    gov = {"grupos": int(len(pg)), "m6": round(float(np.median(pg)), 4)}
    print(f"governador: {gov}", flush=True)
    multiverso = []
    for grupo in ("municipio", "zona"):
        for piso in (0, 50, 100):
            for sem_red in (False, True):
                m = rodar(piso, sem_red, grupo, red)
                linha = {**m["especificacao"], "m6_2026": m["series"]["2026"]["m6"], "m6_2022": m["series"]["2022"]["m6"],
                         "razao": m["razao"], "razao_ic": m["razao_ic"], "fora_da_referencia": m["fora_da_referencia"]}
                multiverso.append(linha)
                print(f"  {grupo:9} piso {piso:<3} {'sem RED' if sem_red else '       '} M6 {linha['m6_2026']}×"
                      f"{linha['m6_2022']} razão {linha['razao']} IC {linha['razao_ic']} "
                      f"{'FORA' if linha['fora_da_referencia'] else 'ok'}", flush=True)
    iguais = sum(1 for m in multiverso if m["fora_da_referencia"] == principal["fora_da_referencia"])
    r = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
         "preregistro": "docs/preregistro/README.md (preregistro-v1), seção 4, C6; esclarecimentos de 01/11 na seção 9",
         "principal": principal, "decisao": decisao, "governador": gov, "multiverso": multiverso,
         "multiverso_mesma_decisao": f"{iguais}/{len(multiverso)}", "robusto": iguais / len(multiverso) >= 0.8}
    DESTINO.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    gravar_analise(r)
    print(f"→ {DESTINO.relative_to(RAIZ)} · mesma decisão em {iguais}/{len(multiverso)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
