"""Teste C5 do pré-registro: voto sem biometria.

    venv/bin/python -m tools.migracoes.2026-11-01-c5-biometria

## O que testa (docs/preregistro/README.md, seção 4, C5, e os esclarecimentos de 01/11)

A alegação (caso `biometria`): o voto de quem passou sem a digital
reconhecida é por onde a fraude entra — o mesário vota por quem faltou. Se
fosse assim, onde mais gente votou sem biometria a seção teria mudado mais
para o 13 do 1º para o 2º turno.

- `Δ_i = α_m + β · s_i + ε`, com `Δ_i = L_2/V_2 − L_1/V_1` e `s_i` = sem
  biometria / comparecimento (BU do 2º turno); efeito fixo de município, peso
  `V_2`, erro agrupado por zona; p unilateral (`β > 0`).
- Atípico se `β_2026 > 0` com p ajustado < 0,05 E o IC de 95% de
  `β_2026 − β_2022` excluir zero.
"""
from __future__ import annotations

import importlib
import json
import pickle
import sys
from datetime import datetime

import numpy as np
from scipy.stats import norm

c1 = importlib.import_module("tools.migracoes.2026-11-01-c1-secoes-zeradas")
L1, F1, T1, L2, F2 = c1.L1, c1.F1, c1.T1, c1.L2, c1.F2
CACHE, ARQUIVO, ANALISE, RAIZ = c1.CACHE, c1.ARQUIVO, c1.ANALISE, c1.RAIZ
DESTINO = ARQUIVO / "c5.json"


def _dados(ano, piso, sem_red, red, grupo):
    chaves, A = c1._tabela(ano)
    bu = pickle.loads((CACHE / f"bu_secao_{ano}.pkl").read_bytes())
    d, s, w, gr, zo = [], [], [], [], []
    for k, a in zip(chaves, A):
        b = bu.get(k)
        if k[0] == "zz" or b is None or b["comp"] <= 0 or b["comp"] < piso or (sem_red and k in red):
            continue
        v1, v2 = a[L1] + a[F1] + a[T1], a[L2] + a[F2]
        si = b["sem_bio"] / b["comp"]
        if v1 <= 0 or v2 <= 0 or si > 1:
            continue
        d.append(a[L2] / v2 - a[L1] / v1)
        s.append(si)
        w.append(v2)
        gr.append(str((k[0], k[1]) if grupo == "municipio" else (k[0], k[2])))
        zo.append(str((k[0], k[2])))
    g = np.unique(gr, return_inverse=True)[1]
    z = np.unique(zo, return_inverse=True)[1]
    return np.array(d), np.array(s), np.array(w, float), g, z


def regressao(y, x, w, g, cl):
    """β de y sobre x com efeito fixo g (within), peso w, erro agrupado em cl."""
    def dentro(v):
        m = np.bincount(g, w * v) / np.bincount(g, w)
        return v - m[g]
    xt, yt = dentro(x), dentro(y)
    sxx = (w * xt * xt).sum()
    b = float((w * xt * yt).sum() / sxx)
    e = yt - b * xt
    se = float(np.sqrt((np.bincount(cl, w * xt * e) ** 2).sum()) / sxx)
    return b, se


def rodar(piso=0, sem_red=False, grupo="municipio", red=frozenset()):
    out = {}
    for ano in (2026, 2022):
        y, x, w, g, z = _dados(ano, piso, sem_red, red, grupo)
        b, se = regressao(y, x, w, g, z)
        out[str(ano)] = {"secoes": int(len(y)), "beta": round(b, 5), "se": round(se, 5),
                         "p_unilateral": round(float(norm.sf(b / se)), 6),
                         "s_media": round(float(np.average(x, weights=w)), 4)}
    d = out["2026"]["beta"] - out["2022"]["beta"]
    sd = float(np.hypot(out["2026"]["se"], out["2022"]["se"]))
    ic = [round(d - 1.96 * sd, 5), round(d + 1.96 * sd, 5)]
    p = out["2026"]["p_unilateral"]
    cond = out["2026"]["beta"] > 0 and p < 0.05 and ic[0] > 0
    return {"especificacao": {"piso_comparecimento": piso, "sem_red": sem_red, "efeito_fixo": grupo},
            "series": out, "diferenca": round(d, 5), "diferenca_ic": ic, "p_c5": p,
            "fora_da_referencia": bool(cond)}


def gravar_analise(r: dict) -> None:
    a = json.loads(ANALISE.read_text(encoding="utf-8"))
    p = r["principal"]
    s26, s22 = p["series"]["2026"], p["series"]["2022"]
    # β é a mudança na fatia do 13 por 100% de eleitores sem biometria; o texto usa
    # pontos percentuais por 10 pontos de sem-biometria, que é a escala real.
    pp = lambda b: c1._br(b * 10, 2).replace("-", "−")
    if not r["robusto"]:
        decisao, abre = "frágil", "Depende da especificação. "
    elif r["decisao"] == "compatível":
        decisao, abre = "compatível", "Compatível com 2022. "
    else:
        decisao, abre = r["decisao"], "Fora da referência; a decisão final depende da correção para os seis testes. "
    if s26["beta"] < 0:
        efeito = (f"a seção mudou {pp(-s26['beta'])} ponto percentual a menos para o Lula do 1º para o 2º "
                  f"turno em 2026, o contrário do que a alegação prevê")
    else:
        efeito = (f"a seção mudou {pp(s26['beta'])} ponto percentual a mais para o Lula do 1º para o 2º turno "
                  f"em 2026 (p = {c1._br(s26['p_unilateral'], 3)})")
    texto = (f"{abre}Dentro do mesmo município, a cada 10 pontos a mais de eleitores sem biometria, {efeito}. "
             f"Em 2022 eram {pp(s22['beta'])} ponto a mais. Diferença 2026 − 2022: IC de "
             f"{pp(p['diferenca_ic'][0])} a {pp(p['diferenca_ic'][1])} ponto. "
             f"Mesma decisão em {r['multiverso_mesma_decisao'].replace('/', ' de ')} especificações.")
    for t in a["testes"]:
        if t["id"] == "C5":
            t.update({"status": "feito", "decisao": decisao, "resultado": texto,
                      "dados": "/apuracao/explicacao/c5.json"})
    a["atualizado_em"] = r["gerado_em"][:10]
    ANALISE.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    red = frozenset(c1._red_2026())
    principal = rodar(red=red)
    print(json.dumps(principal, ensure_ascii=False, indent=1), flush=True)
    decisao = "pendente do BH" if principal["fora_da_referencia"] else "compatível"
    print(f"decisão: {decisao}", flush=True)
    multiverso = []
    for grupo in ("municipio", "zona"):
        for piso in (0, 50, 100):
            for sem_red in (False, True):
                m = rodar(piso, sem_red, grupo, red)
                s = m["series"]
                linha = {**m["especificacao"], "beta_2026": s["2026"]["beta"], "beta_2022": s["2022"]["beta"],
                         "p": s["2026"]["p_unilateral"], "diferenca_ic": m["diferenca_ic"],
                         "fora_da_referencia": m["fora_da_referencia"]}
                multiverso.append(linha)
                print(f"  {grupo:9} piso {piso:<3} {'sem RED' if sem_red else '       '} β {linha['beta_2026']}×"
                      f"{linha['beta_2022']} p {linha['p']} dif {linha['diferenca_ic']} "
                      f"{'FORA' if linha['fora_da_referencia'] else 'ok'}", flush=True)
    iguais = sum(1 for m in multiverso if m["fora_da_referencia"] == principal["fora_da_referencia"])
    r = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
         "preregistro": "docs/preregistro/README.md (preregistro-v1), seção 4, C5; esclarecimentos de 01/11 na seção 9",
         "principal": principal, "decisao": decisao, "multiverso": multiverso,
         "multiverso_mesma_decisao": f"{iguais}/{len(multiverso)}", "robusto": iguais / len(multiverso) >= 0.8}
    DESTINO.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    gravar_analise(r)
    print(f"→ {DESTINO.relative_to(RAIZ)} · mesma decisão em {iguais}/{len(multiverso)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
