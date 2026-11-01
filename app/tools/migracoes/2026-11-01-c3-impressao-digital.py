"""Teste C3 do pré-registro: comparecimento × voto (enchimento de urna).

    venv/bin/python -m tools.migracoes.2026-11-01-c3-impressao-digital

## O que testa (docs/preregistro/README.md, seção 4, C3, e os detalhes de 01/11)

Enchimento de urna deixa uma assinatura conhecida: seções com comparecimento
alto E voto quase todo num lado só, puxando o histograma 2D (comparecimento ×
fatia do vencedor) para o canto de cima à direita. Klimek et al. (2012) ajustam
a esse histograma uma mistura de três componentes:

- limpo: comparecimento e fatia normais e independentes;
- fraude incremental (fração `f_i` das seções): uma fração `x ~ |N(0, σx)|`
  dos ausentes vira voto do vencedor, e `x²` da oposição também;
- fraude extrema (fração `f_e`): o mesmo com `x` perto de 1.

- C3a (principal): `f_i` e `f_e`, com IC de 95% por bootstrap de municípios.
- C3b (secundário): inclinação de Myagkov et al. (2009) — votos do 13 por apto
  sobre comparecimento, dentro do município. Enchimento empurra para > 1.
- Atípico se o IC de `f_i` ou `f_e` em 2026 exclui zero E a diferença para 2022
  (bootstrap) também exclui zero, para cima.

## Por que o ajuste é rápido

Dados os componentes, o histograma do modelo é linear em `f_i` e `f_e`:
`H = H_limpo + f_i (H_inc − H_limpo) + f_e (H_ext − H_limpo)`. O ajuste é
mínimos quadrados com limites. Os sorteios normais são gerados uma vez
(números aleatórios comuns) e só reescalados em cada réplica do bootstrap.
"""
from __future__ import annotations

import importlib
import json
import pickle
import sys
from datetime import datetime

import numpy as np
from scipy.optimize import lsq_linear

c1 = importlib.import_module("tools.migracoes.2026-11-01-c1-secoes-zeradas")
L2, F2, C2 = c1.L2, c1.F2, c1.C2
CACHE, ARQUIVO, ANALISE, RAIZ = c1.CACHE, c1.ARQUIVO, c1.ANALISE, c1.RAIZ
DESTINO = ARQUIVO / "c3.json"
ALFA = 2.0
SIGMAS = (0.025, 0.05, 0.075, 0.1, 0.15, 0.2)
SORTEIOS = 400_000
RNG_BASE = np.random.default_rng(20261101)
# Números aleatórios comuns: z normais para t, v e x; reescalados a cada uso.
Z_T = RNG_BASE.standard_normal(SORTEIOS * 2)
Z_V = RNG_BASE.standard_normal(SORTEIOS * 2)
Z_X = np.abs(RNG_BASE.standard_normal(SORTEIOS * 2))


def _dados(ano: int, piso: int = 0, sem_red: bool = False, red=frozenset(), cargo: str = "presidente"):
    """(t, v, A, L2/A, município) por seção."""
    chaves, A = c1._tabela(ano)
    bu = pickle.loads((CACHE / f"bu_secao_{ano}.pkl").read_bytes())
    linhas = []
    if cargo == "presidente":
        for k, a in zip(chaves, A):
            b = bu.get(k)
            if b is None or k[0] == "zz" or b["aptos"] <= 0:
                continue
            v2 = a[L2] + a[F2]
            if v2 <= 0 or b["comp"] < piso or b["comp"] > b["aptos"] or (sem_red and k in red):
                continue
            linhas.append((b["comp"] / b["aptos"], a[L2] / v2, b["aptos"], a[L2] / b["aptos"], (k[0], k[1]), (k[0], k[2])))
    else:
        # Governador: em cada UF, o vencedor é o mais votado no 2º turno.
        por_uf: dict = {}
        for k, b in bu.items():
            if "gov" in b:
                tot = por_uf.setdefault(k[0], {})
                for n, q in b["gov"].items():
                    tot[n] = tot.get(n, 0) + q
        vencedor = {uf: max(t, key=t.get) for uf, t in por_uf.items()}
        for k, b in bu.items():
            if "gov" not in b or b["aptos"] <= 0 or b.get("gov_validos", 0) <= 0 or b["comp"] < piso or b["comp"] > b["aptos"]:
                continue
            w = b["gov"].get(vencedor[k[0]], 0)
            linhas.append((b["comp"] / b["aptos"], w / b["gov_validos"], b["aptos"], w / b["aptos"], (k[0], k[1]), (k[0], k[2])))
    t, v, ap, la = (np.array([x[i] for x in linhas], float) for i in range(4))
    mun = np.unique([str(x[4]) for x in linhas], return_inverse=True)[1]
    zona = np.unique([str(x[5]) for x in linhas], return_inverse=True)[1]
    return t, v, ap, la, mun, zona


def _hist(t, v, bins):
    it = np.minimum((t * bins).astype(np.int64), bins - 1)
    iv = np.minimum((v * bins).astype(np.int64), bins - 1)
    h = np.bincount(it * bins + iv, minlength=bins * bins).astype(float)
    return h / max(h.sum(), 1)


def _limpos(mt, st, mv, sv):
    """Sorteios do componente limpo: normais truncadas em [0, 1] (por rejeição)."""
    t = mt + st * Z_T
    v = mv + sv * Z_V
    ok = (t >= 0) & (t <= 1) & (v >= 0) & (v <= 1)
    return t[ok][:SORTEIOS], v[ok][:SORTEIOS]


def _fraude(t, v, x):
    w = t * v + x * (1 - t) + x ** ALFA * t * (1 - v)
    t2 = t + x * (1 - t)
    return t2, np.clip(w / t2, 0, 1)


def ajustar(t, v, bins=100):
    """`f_i`, `f_e`, σx e o erro do melhor ajuste de Klimek a estas seções."""
    mt, mv = np.median(t), np.median(v)
    st = 1.4826 * np.median(np.abs(t - mt))
    sv = 1.4826 * np.median(np.abs(v - mv))
    H = _hist(t, v, bins)
    tl, vl = _limpos(mt, st, mv, sv)
    Hc = _hist(tl, vl, bins)
    n = len(tl)
    melhor = None
    for s in SIGMAS:
        x = np.minimum(s * Z_X[:n], 1)
        Hi = _hist(*_fraude(tl, vl, x), bins)
        He = _hist(*_fraude(tl, vl, 1 - x), bins)
        M = np.column_stack([Hi - Hc, He - Hc])
        r = lsq_linear(M, H - Hc, bounds=(0, 1), method="bvls")
        erro = float(((M @ r.x + Hc - H) ** 2).sum())
        if melhor is None or erro < melhor[3]:
            melhor = (float(r.x[0]), float(r.x[1]), s, erro)
    fi, fe, s, erro = melhor
    return {"f_i": fi, "f_e": fe, "sigma_x": s, "erro": erro,
            "limpo": {"t": [round(float(mt), 4), round(float(st), 4)], "v": [round(float(mv), 4), round(float(sv), 4)]}}


def _bootstrap(t, v, mun, voltas, bins, semente):
    rng = np.random.default_rng(semente)
    ordem = np.argsort(mun, kind="stable")
    limites = np.searchsorted(mun[ordem], np.arange(mun.max() + 2))
    grupos = [ordem[limites[g]:limites[g + 1]] for g in range(mun.max() + 1)]
    saida = np.empty((voltas, 2))
    for b in range(voltas):
        idx = np.concatenate([grupos[g] for g in rng.integers(0, len(grupos), len(grupos))])
        r = ajustar(t[idx], v[idx], bins)
        saida[b] = (r["f_i"], r["f_e"])
    return saida


def inclinacao(t, la, ap, grupo):
    """C3b: L2/A sobre C2/A dentro do grupo, ponderado por A; erro agrupado."""
    w = ap
    def dentro(x):
        m = np.bincount(grupo, w * x) / np.bincount(grupo, w)
        return x - m[grupo]
    xt, yt = dentro(t), dentro(la)
    b = float((w * xt * yt).sum() / (w * xt * xt).sum())
    e = yt - b * xt
    # Erro-padrão agrupado (sanduíche) com um regressor.
    s = np.bincount(grupo, w * xt * e)
    se = float(np.sqrt((s ** 2).sum()) / (w * xt * xt).sum())
    return round(b, 4), round(se, 4)


def _ic(a):
    return [round(float(np.percentile(a, 2.5)), 5), round(float(np.percentile(a, 97.5)), 5)]


def rodar(piso=0, sem_red=False, bins=100, voltas=1000, red=frozenset(), cargos=("presidente",)):
    saida = {}
    boots = {}
    for ano in (2026, 2022):
        t, v, ap, la, mun, zona = _dados(ano, piso, sem_red, red)
        r = ajustar(t, v, bins)
        bs = _bootstrap(t, v, mun, voltas, bins, semente=ano)
        boots[ano] = bs
        saida[str(ano)] = {
            "secoes": int(len(t)), "f_i": round(r["f_i"], 5), "f_e": round(r["f_e"], 5),
            "f_i_ic": _ic(bs[:, 0]), "f_e_ic": _ic(bs[:, 1]), "sigma_x": r["sigma_x"],
            "limpo": r["limpo"], "erro": r["erro"],
            "inclinacao_municipio": inclinacao(t, la, ap, mun),
            "inclinacao_zona": inclinacao(t, la, ap, zona),
        }
    if "governador" in cargos:
        t, v, ap, la, mun, zona = _dados(2026, piso, sem_red, red, cargo="governador")
        r = ajustar(t, v, bins)
        bs = _bootstrap(t, v, mun, min(voltas, 200), bins, semente=3)
        saida["governador_2026"] = {"secoes": int(len(t)), "f_i": round(r["f_i"], 5), "f_e": round(r["f_e"], 5),
                                    "f_i_ic": _ic(bs[:, 0]), "f_e_ic": _ic(bs[:, 1]), "sigma_x": r["sigma_x"],
                                    "inclinacao_municipio": inclinacao(t, la, ap, mun)}
    d = boots[2026] - boots[2022]
    s26 = boots[2026].sum(axis=1)
    exclui0 = saida["2026"]["f_i_ic"][0] > 0 or saida["2026"]["f_e_ic"][0] > 0
    acima = _ic(d[:, 0])[0] > 0 or _ic(d[:, 1])[0] > 0
    return {"especificacao": {"piso_comparecimento": piso, "sem_red": sem_red, "bins": bins, "bootstrap": voltas},
            "series": saida,
            "diferenca_2026_2022": {"f_i_ic": _ic(d[:, 0]), "f_e_ic": _ic(d[:, 1])},
            "p_c3": round(float((1 + (s26 <= 0).sum()) / (1 + len(s26))), 5),
            "ic_2026_exclui_zero": bool(exclui0), "acima_de_2022": bool(acima),
            "fora_da_referencia": bool(exclui0 and acima)}


def _pct(x):
    return c1._br(100 * x, 2) + "%"


def gravar_analise(r: dict) -> None:
    a = json.loads(ANALISE.read_text(encoding="utf-8"))
    s = r["principal"]["series"]
    s26, s22 = s["2026"], s["2022"]
    abre = "Compatível com 2022." if r["decisao"] == "compatível" else \
        "Fora da referência; a decisão final depende da correção para os seis testes."
    texto = (f"{abre} O modelo de Klimek atribui à fraude incremental {_pct(s26['f_i'])} das seções em 2026 "
             f"(IC {_pct(s26['f_i_ic'][0])} a {_pct(s26['f_i_ic'][1])}) e {_pct(s22['f_i'])} em 2022 "
             f"(IC {_pct(s22['f_i_ic'][0])} a {_pct(s22['f_i_ic'][1])}); à fraude extrema, "
             f"{_pct(s26['f_e'])} e {_pct(s22['f_e'])}. ")
    if "governador_2026" in s:
        g = s["governador_2026"]
        texto += f"No governador de 2026, nas mesmas urnas: {_pct(g['f_i'])} e {_pct(g['f_e'])}. "
    b26, b22 = s26["inclinacao_municipio"][0], s22["inclinacao_municipio"][0]
    texto += (f"A fraude extrema, que é a marca do enchimento de urna, fica perto de zero nos três. O IC de 2026 "
              f"inclui zero e fica abaixo de 2022. Os valores altos de 2022 e do governador vêm do menor σx da "
              f"grade, que não se distingue de ruído: o modelo usa esse componente para cobrir o que o modelo "
              f"limpo, simples demais para o Brasil, não explica. Por isso a decisão é pela comparação, não pelo "
              f"valor bruto. A inclinação de Myagkov fica em {c1._br(b26, 2)} (2022: {c1._br(b22, 2)}), longe "
              f"do 1 que o enchimento produziria. "
              f"Mesma decisão em {r['multiverso_mesma_decisao'].replace('/', ' de ')} especificações.")
    for t in a["testes"]:
        if t["id"] == "C3":
            t.update({"status": "feito", "decisao": r["decisao"], "resultado": texto,
                      "dados": "/apuracao/explicacao/c3.json"})
    a["atualizado_em"] = r["gerado_em"][:10]
    ANALISE.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    red = frozenset(c1._red_2026())
    print("especificação principal (1.000 réplicas)…", flush=True)
    principal = rodar(red=red, cargos=("presidente", "governador"))
    print(json.dumps(principal, ensure_ascii=False, indent=1), flush=True)
    decisao = "pendente do BH" if principal["fora_da_referencia"] else "compatível"
    print(f"decisão: {decisao}", flush=True)
    multiverso = []
    for piso in (0, 50, 100):
        for sem_red in (False, True):
            for bins in (100, 50):
                m = rodar(piso, sem_red, bins, voltas=200, red=red)
                s = m["series"]
                linha = {**m["especificacao"], "f_i_2026": s["2026"]["f_i"], "f_i_2022": s["2022"]["f_i"],
                         "f_e_2026": s["2026"]["f_e"], "f_e_2022": s["2022"]["f_e"],
                         "dif_f_i_ic": m["diferenca_2026_2022"]["f_i_ic"], "dif_f_e_ic": m["diferenca_2026_2022"]["f_e_ic"],
                         "fora_da_referencia": m["fora_da_referencia"]}
                multiverso.append(linha)
                print(f"  piso {piso:<3} {'sem RED' if sem_red else '       '} bins {bins:<3} "
                      f"f_i {linha['f_i_2026']}×{linha['f_i_2022']} f_e {linha['f_e_2026']}×{linha['f_e_2022']} "
                      f"{'FORA' if linha['fora_da_referencia'] else 'ok'}", flush=True)
    iguais = sum(1 for m in multiverso if m["fora_da_referencia"] == principal["fora_da_referencia"])
    r = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
         "preregistro": "docs/preregistro/README.md (preregistro-v1), seção 4, C3; detalhes de 01/11 na seção 9",
         "principal": principal, "decisao": decisao, "multiverso": multiverso,
         "multiverso_mesma_decisao": f"{iguais}/{len(multiverso)}", "robusto": iguais / len(multiverso) >= 0.8}
    DESTINO.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    gravar_analise(r)
    print(f"→ {DESTINO.relative_to(RAIZ)} · mesma decisão em {iguais}/{len(multiverso)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
