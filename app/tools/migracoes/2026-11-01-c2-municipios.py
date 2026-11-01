"""Teste C2 do pré-registro: municípios fora do padrão.

    venv/bin/python -m tools.migracoes.2026-11-01-c2-municipios

## O que testa (docs/preregistro/README.md, seção 4, C2, e o desvio de 01/11)

A alegação (Silva Jardim e os "fora do padrão"): há municípios que viraram
mais do que o 1º turno explica. A pergunta: há mais desses municípios do que em
2022? E eles pendem para um lado mais do que pendiam em 2022?

- Modelo: regressão logística fracionária (a mesma do C1) da fatia do 13 no
  2º turno sobre `F_1/V_1`, `L_1/V_1`, `T_1/V_1` e `BN_1/C_1` do município, com
  efeito fixo de UF e peso `V_2`.
- Resíduo de Pearson dividido por `√φ̂` (quase-binomial, `φ̂ = Σr²/(n−k)`);
  p bilateral normal; Benjamini–Hochberg com q = 0,05 sobre os municípios.
- `N2` = municípios significativos; `D2` = fração deles a favor do 13.
- Atípico se a proporção significativa de 2026 passa a de 2022 (duas
  proporções, unilateral, p < 0,05) E a razão > 1,25; OU se `D2` de 2026 passa
  o de 2022 (Fisher exato, unilateral, p < 0,05). O vencedor de 2022 também foi
  o 13. O p do C2 para o BH entre testes é `min(1, 2·min(p_prop, p_Fisher))`.

Grava `apuracao/data/arquivo/2026-2t/c2.json` e o item C2 de `analise.json`.
"""
from __future__ import annotations

import importlib
import json
import pickle
import sys
from datetime import datetime

import numpy as np
from scipy.stats import fisher_exact, norm

c1 = importlib.import_module("tools.migracoes.2026-11-01-c1-secoes-zeradas")
L1, F1, T1, BN1, C1, L2, F2, BN2, C2 = c1.L1, c1.F1, c1.T1, c1.BN1, c1.C1, c1.L2, c1.F2, c1.BN2, c1.C2
DESTINO = c1.ARQUIVO / "c2.json"
ANALISE = c1.ANALISE
TABELAS = {ano: c1._tabela(ano) for ano in (2026, 2022)}


def _bh(p: np.ndarray, q: float) -> np.ndarray:
    """Quais hipóteses o Benjamini–Hochberg rejeita ao nível q."""
    n = p.size
    ordem = np.argsort(p)
    limite = q * np.arange(1, n + 1) / n
    abaixo = np.nonzero(p[ordem] <= limite)[0]
    rejeita = np.zeros(n, bool)
    if abaixo.size:
        rejeita[ordem[: abaixo.max() + 1]] = True
    return rejeita


def _municipios(ano: int, piso: int, sem_red: bool, red: frozenset):
    chaves, A = TABELAS[ano]
    ok = np.array([k[0] != "zz" for k in chaves]) & (A[:, C2] >= piso)
    if sem_red and ano == 2026:
        ok &= np.array([k not in red for k in chaves])
    idx: dict = {}
    g = np.array([idx.setdefault((k[0], k[1]), len(idx)) for k, b in zip(chaves, ok) if b])
    M = np.vstack([np.bincount(g, A[ok][:, c], len(idx)) for c in range(A.shape[1])]).T
    nomes = list(idx)
    return nomes, M


def _ajuste(nomes, M, efeito: str):
    V1 = M[:, L1] + M[:, F1] + M[:, T1]
    V2 = M[:, L2] + M[:, F2]
    ok = (V1 > 0) & (V2 > 0)
    nomes = [n for n, b in zip(nomes, ok) if b]
    M, V1, V2 = M[ok], V1[ok], V2[ok]
    X = np.column_stack([M[:, F1] / V1, M[:, L1] / V1, M[:, T1] / V1, M[:, BN1] / np.maximum(M[:, C1], 1)])
    if efeito == "uf":
        rot: dict = {}
        g = np.array([rot.setdefault(n[0], len(rot)) for n in nomes])
    else:
        g = np.zeros(len(nomes), dtype=np.int64)
    y = M[:, L2] / V2
    p = c1._logit_fe(X, y, V2, g)
    r = (M[:, L2] - V2 * p) / np.sqrt(V2 * p * (1 - p))
    k = X.shape[1] + int(g.max()) + 1
    phi = float((r ** 2).sum() / (len(r) - k))
    z = r / np.sqrt(phi)
    pv = 2 * norm.sf(np.abs(z))
    return nomes, z, pv, phi


def _um_ano(ano, efeito, q, piso, sem_red, red):
    nomes, M = _municipios(ano, piso, sem_red, red)
    nomes, z, pv, phi = _ajuste(nomes, M, efeito)
    sig = _bh(pv, q)
    a13 = int((sig & (z > 0)).sum())
    return {"municipios": len(nomes), "phi": round(phi, 2), "significativos": int(sig.sum()),
            "a_favor_13": a13, "a_favor_22": int(sig.sum()) - a13,
            "proporcao": sig.sum() / len(nomes),
            "_z": z, "_nomes": nomes, "_sig": sig}


def rodar(efeito="uf", q=0.05, piso=0, sem_red=False, red=frozenset()):
    a, b = (_um_ano(ano, efeito, q, piso, sem_red, red) for ano in (2026, 2022))
    # Duas proporções, unilateral (2026 > 2022), z com variância combinada.
    n1, n2, x1, x2 = a["municipios"], b["municipios"], a["significativos"], b["significativos"]
    pc = (x1 + x2) / (n1 + n2)
    zp = (x1 / n1 - x2 / n2) / np.sqrt(pc * (1 - pc) * (1 / n1 + 1 / n2)) if 0 < pc < 1 else 0.0
    p_prop = float(norm.sf(zp))
    razao = (x1 / n1) / (x2 / n2) if x2 else float("inf") if x1 else 1.0
    # Fisher: entre os significativos, a fatia a favor do 13 é maior em 2026?
    tab = [[a["a_favor_13"], a["a_favor_22"]], [b["a_favor_13"], b["a_favor_22"]]]
    p_fisher = float(fisher_exact(tab, alternative="greater")[1]) if x1 and x2 else 1.0
    cond1 = p_prop < 0.05 and razao > 1.25
    cond2 = p_fisher < 0.05
    limpo = lambda d: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in d.items() if not k.startswith("_")}
    return {"especificacao": {"efeito_fixo": efeito, "q": q, "piso_comparecimento": piso, "sem_red": sem_red},
            "2026": limpo(a), "2022": limpo(b),
            "razao_proporcoes": round(razao, 3), "p_proporcao": round(p_prop, 6),
            "d2_2026": round(a["a_favor_13"] / x1, 3) if x1 else None,
            "d2_2022": round(b["a_favor_13"] / x2, 3) if x2 else None,
            "p_fisher": round(p_fisher, 6),
            "p_c2": round(min(1.0, 2 * min(p_prop, p_fisher)), 6),
            "fora_da_referencia": bool(cond1 or cond2),
            "_a": a, "_b": b}


def _br(x, casas=1):
    return c1._br(x, casas)


def gravar_analise(r: dict) -> None:
    a = json.loads(ANALISE.read_text(encoding="utf-8"))
    p = r["principal"]
    s26, s22 = p["2026"], p["2022"]
    abre = "Compatível com 2022." if r["decisao"] == "compatível" else \
        "Fora da referência; a decisão final depende da correção para os seis testes."
    texto = (f"{abre} {s26['significativos']} de {_br(s26['municipios'], 0)} municípios ficam fora do que o "
             f"1º turno prevê (Benjamini–Hochberg, q = 0,05), contra {s22['significativos']} de "
             f"{_br(s22['municipios'], 0)} em 2022. Dos de 2026, {s26['a_favor_13']} pendem para o Lula e "
             f"{s26['a_favor_22']} para o Flávio; em 2022 eram {s22['a_favor_13']} e {s22['a_favor_22']}. "
             f"Silva Jardim, o município da alegação, fica em {_br(r['silva_jardim']['posicao'], 0)}º de "
             f"{_br(r['silva_jardim']['de'], 0)} (z = {_br(r['silva_jardim']['z'], 2)}). "
             f"Mesma decisão em {r['multiverso_mesma_decisao'].replace('/', ' de ')} especificações.")
    for t in a["testes"]:
        if t["id"] == "C2":
            t.update({"status": "feito", "decisao": r["decisao"], "resultado": texto,
                      "dados": "/apuracao/explicacao/c2.json"})
    a["atualizado_em"] = r["gerado_em"][:10]
    ANALISE.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    red = frozenset(c1._red_2026())
    principal = rodar(red=red)
    a, b = principal.pop("_a"), principal.pop("_b")
    print(f"2026: {principal['2026']}\n2022: {principal['2022']}")
    print(f"razão {principal['razao_proporcoes']} p_prop {principal['p_proporcao']} · D2 {principal['d2_2026']} × "
          f"{principal['d2_2022']} p_Fisher {principal['p_fisher']} · p_C2 {principal['p_c2']}")
    decisao = "pendente do BH" if principal["fora_da_referencia"] else "compatível"
    print(f"decisão: {decisao}")

    # Os municípios significativos de 2026 (e os 20 maiores |z|), para quem quiser olhar um por um.
    ordem = np.argsort(-np.abs(a["_z"]))
    mun_nome = pickle.loads((c1.CACHE / "secoes_2026.pkl").read_bytes())["mun"]
    lista = [{"uf": a["_nomes"][i][0], "municipio": mun_nome.get(a["_nomes"][i], a["_nomes"][i][1]),
              "z": round(float(a["_z"][i]), 2), "significativo": bool(a["_sig"][i])}
             for i in ordem[: max(20, int(a["_sig"].sum()))]]

    # O município da alegação (caso `silva-jardim`): onde ele cai na fila.
    i = next(j for j, n in enumerate(a["_nomes"]) if mun_nome.get(n) == "SILVA JARDIM" and n[0] == "rj")
    silva = {"z": round(float(a["_z"][i]), 2), "posicao": int((np.abs(a["_z"]) > abs(a["_z"][i])).sum()) + 1,
             "de": len(a["_z"]), "significativo": bool(a["_sig"][i])}
    print(f"Silva Jardim: {silva}")

    multiverso = []
    for efeito in ("uf", "nenhum"):
        for q in (0.05, 0.10):
            for piso in (0, 50, 100):
                for sem_red in (False, True):
                    m = rodar(efeito, q, piso, sem_red, red)
                    m.pop("_a"), m.pop("_b")
                    linha = {**m["especificacao"], "sig_2026": m["2026"]["significativos"],
                             "sig_2022": m["2022"]["significativos"], "razao": m["razao_proporcoes"],
                             "p_prop": m["p_proporcao"], "d2_2026": m["d2_2026"], "d2_2022": m["d2_2022"],
                             "p_fisher": m["p_fisher"], "fora_da_referencia": m["fora_da_referencia"]}
                    multiverso.append(linha)
                    print(f"  {efeito:6} q {q:.2f} piso {piso:<3} {'sem RED' if sem_red else '       '} "
                          f"sig {linha['sig_2026']}×{linha['sig_2022']} razão {linha['razao']} "
                          f"D2 {linha['d2_2026']}×{linha['d2_2022']} pF {linha['p_fisher']} "
                          f"{'FORA' if linha['fora_da_referencia'] else 'ok'}", flush=True)
    iguais = sum(1 for m in multiverso if m["fora_da_referencia"] == principal["fora_da_referencia"])
    r = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
         "preregistro": "docs/preregistro/README.md (preregistro-v1), seção 4, C2; esclarecimentos de 01/11 na seção 9",
         "principal": principal, "decisao": decisao, "municipios_2026": lista, "silva_jardim": silva,
         "multiverso": multiverso, "multiverso_mesma_decisao": f"{iguais}/{len(multiverso)}",
         "robusto": iguais / len(multiverso) >= 0.8}
    DESTINO.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    gravar_analise(r)
    print(f"→ {DESTINO.relative_to(c1.RAIZ)} · mesma decisão em {iguais}/{len(multiverso)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
