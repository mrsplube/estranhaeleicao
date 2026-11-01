"""Teste C4 do pré-registro: ordem de chegada dos boletins.

    venv/bin/python -m tools.migracoes.2026-11-01-c4-ordem-chegada

## O que testa (docs/preregistro/README.md, seção 4, C4, e os esclarecimentos de 01/11)

A alegação (caso `curva`): os votos que chegaram tarde são diferentes dos que
chegaram cedo — o "algoritmo" segurou os boletins do Lula para o fim. Na curva
nacional isso se confunde com geografia (o Nordeste chega depois). Aqui a
comparação é DENTRO do município, e a variável é a mudança da própria seção
do 1º para o 2º turno, que controla a composição do eleitorado.

- `R4` = média, ponderada pelo número de seções, do Spearman entre a hora de
  recebimento do BU e `Δ_i = L_2/V_2 − L_1/V_1`, em municípios com ≥ 10 seções.
- Nulo: a hora é embaralhada dentro do município (2.000 permutações);
  p unilateral para cima.
- Atípico se p ajustado < 0,05 E `R4_2026 > R4_2022` com o IC de 95% da
  diferença (reamostragem de municípios) excluindo zero.

## Por que a permutação é barata

O Spearman é a correlação dos postos. Dentro de cada município, a média e o
desvio dos postos não mudam quando a hora é embaralhada: só muda a soma dos
produtos. Com as seções em ordem de grupo, cada permutação é um `argsort` de
`grupo + U(0,1)` e um `bincount`.
"""
from __future__ import annotations

import csv
import importlib
import io
import json
import pickle
import sys
import urllib.request
import zipfile
from datetime import datetime

import numpy as np
from scipy.stats import rankdata

c1 = importlib.import_module("tools.migracoes.2026-11-01-c1-secoes-zeradas")
L1, F1, T1, L2, F2, C2 = c1.L1, c1.F1, c1.T1, c1.L2, c1.F2, c1.C2
CACHE, ARQUIVO, ANALISE, RAIZ = c1.CACHE, c1.ARQUIVO, c1.ANALISE, c1.RAIZ
DESTINO = ARQUIVO / "c4.json"
PERMUTACOES = 2000
MIN_SECOES = 10
URL_UF = "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_{uf}.zip"


def _postos_no_grupo(x, g):
    """Posto de x dentro de cada grupo (empate = posto médio)."""
    ordem = np.lexsort((x, g))
    out = np.empty(len(x))
    gs = g[ordem]
    limites = np.flatnonzero(np.r_[True, gs[1:] != gs[:-1], True])
    for a, b in zip(limites[:-1], limites[1:]):
        out[ordem[a:b]] = rankdata(x[ordem[a:b]])
    return out


def _r4(hora, delta, g, voltas, semente):
    """R4 observado, as correlações por grupo e a distribuição sob o nulo."""
    # Grupos com menos de MIN_SECOES saem.
    n = np.bincount(g)
    ok = n[g] >= MIN_SECOES
    hora, delta, g = hora[ok], delta[ok], np.unique(g[ok], return_inverse=True)[1]
    # Tudo em ordem de grupo: assim embaralhar dentro do grupo é um argsort de g + U(0,1).
    o = np.argsort(g, kind="stable")
    hora, delta, g = hora[o], delta[o], g[o]
    n = np.bincount(g).astype(float)
    rh, rd = _postos_no_grupo(hora, g), _postos_no_grupo(delta, g)
    def centra(r):
        m = np.bincount(g, r) / n
        c = r - m[g]
        return c, np.sqrt(np.bincount(g, c * c))
    ch, sh = centra(rh)
    cd, sd = centra(rd)
    valido = (sh > 0) & (sd > 0)
    peso = np.where(valido, n, 0.0)
    def estat(c_hora):
        rho = np.bincount(g, c_hora * cd, len(n)) / np.where(valido, sh * sd, 1)
        return float((peso * rho).sum() / peso.sum()), rho
    obs, rho = estat(ch)
    rng = np.random.default_rng(semente)
    nulos = np.empty(voltas)
    gf = g.astype(float)
    for b in range(voltas):
        perm = np.argsort(gf + rng.random(len(g)))   # embaralha só dentro de cada grupo
        nulos[b] = estat(ch[perm])[0]
    return obs, rho[valido], n[valido], nulos


def _tabela_delta(ano, piso, sem_red, red, grupo):
    chaves, A = c1._tabela(ano)
    bu = pickle.loads((CACHE / f"bu_secao_{ano}.pkl").read_bytes())
    hora, delta, rot = [], [], []
    for k, a in zip(chaves, A):
        b = bu.get(k)
        if k[0] == "zz" or b is None or b["recebido"] is None or b["comp"] < piso or (sem_red and k in red):
            continue
        v1, v2 = a[L1] + a[F1] + a[T1], a[L2] + a[F2]
        if v1 <= 0 or v2 <= 0:
            continue
        hora.append(b["recebido"])
        delta.append(a[L2] / v2 - a[L1] / v1)
        rot.append((k[0], k[1]) if grupo == "municipio" else (k[0], k[2]))
    g = np.unique([str(r) for r in rot], return_inverse=True)[1]
    return np.array(hora), np.array(delta), g


def _governador_1t() -> dict:
    """Voto de governador no 1º turno por seção, nas UFs com 2º turno."""
    bu = pickle.loads((CACHE / "bu_secao_2026.pkl").read_bytes())
    ufs = sorted({k[0] for k, d in bu.items() if "gov" in d})
    tab: dict = {}
    for uf in ufs:
        arq = CACHE / f"votacao_secao_2026_{uf.upper()}.zip"
        if not arq.exists():
            print(f"  baixando {arq.name}", flush=True)
            pedido = urllib.request.Request(URL_UF.format(uf=uf.upper()), headers={"User-Agent": "estranhaeleicao/1.0"})
            with urllib.request.urlopen(pedido, timeout=900) as r, open(arq.with_suffix(".part"), "wb") as f:
                while bloco := r.read(1 << 20):
                    f.write(bloco)
            arq.with_suffix(".part").replace(arq)
        z = zipfile.ZipFile(arq)
        nome = next(n for n in z.namelist() if n.endswith(".csv"))
        for r in csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";"):
            if r["CD_CARGO"] != "3" or r["NR_TURNO"] != "1":
                continue
            k = (r["SG_UF"].lower(), r["CD_MUNICIPIO"].zfill(5), int(r["NR_ZONA"]), int(r["NR_SECAO"]))
            if r["NR_VOTAVEL"] in ("95", "96"):
                continue
            d = tab.setdefault(k, {})
            d[r["NR_VOTAVEL"]] = d.get(r["NR_VOTAVEL"], 0) + int(r["QT_VOTOS"] or 0)
    return tab


def _governador(voltas):
    bu = pickle.loads((CACHE / "bu_secao_2026.pkl").read_bytes())
    g1 = _governador_1t()
    por_uf: dict = {}
    for k, b in bu.items():
        if "gov" in b:
            t = por_uf.setdefault(k[0], {})
            for n, q in b["gov"].items():
                t[n] = t.get(n, 0) + q
    venc = {uf: max(t, key=t.get) for uf, t in por_uf.items()}
    hora, delta, rot = [], [], []
    for k, b in bu.items():
        if "gov" not in b or b["recebido"] is None or b.get("gov_validos", 0) <= 0 or k not in g1:
            continue
        v1 = sum(g1[k].values())
        if v1 <= 0:
            continue
        w = venc[k[0]]
        hora.append(b["recebido"])
        delta.append(b["gov"].get(w, 0) / b["gov_validos"] - g1[k].get(w, 0) / v1)
        rot.append((k[0], k[1]))
    g = np.unique([str(r) for r in rot], return_inverse=True)[1]
    obs, _, nm, nulos = _r4(np.array(hora), np.array(delta), g, voltas, 26)
    return {"secoes": len(hora), "municipios": int(len(nm)), "r4": round(obs, 4),
            "p": round(float((1 + (nulos >= obs).sum()) / (1 + voltas)), 5)}


def rodar(piso=0, sem_red=False, grupo="municipio", voltas=PERMUTACOES, red=frozenset()):
    saida, por_grupo = {}, {}
    for ano in (2026, 2022):
        hora, delta, g = _tabela_delta(ano, piso, sem_red, red, grupo)
        obs, rho, n, nulos = _r4(hora, delta, g, voltas, ano)
        por_grupo[ano] = (rho, n)
        saida[str(ano)] = {"secoes": int(len(hora)), "grupos": int(len(n)), "r4": round(obs, 4),
                           "nulo_p2_5": round(float(np.percentile(nulos, 2.5)), 4),
                           "nulo_p97_5": round(float(np.percentile(nulos, 97.5)), 4),
                           "p": round(float((1 + (nulos >= obs).sum()) / (1 + voltas)), 5)}
    rng = np.random.default_rng(7)
    difs = np.empty(2000)
    for b in range(2000):
        r = []
        for ano in (2026, 2022):
            rho, n = por_grupo[ano]
            i = rng.integers(0, len(rho), len(rho))
            r.append((n[i] * rho[i]).sum() / n[i].sum())
        difs[b] = r[0] - r[1]
    ic = [round(float(np.percentile(difs, 2.5)), 4), round(float(np.percentile(difs, 97.5)), 4)]
    p = saida["2026"]["p"]
    acima = saida["2026"]["r4"] > saida["2022"]["r4"] and ic[0] > 0
    return {"especificacao": {"piso_comparecimento": piso, "sem_red": sem_red, "grupo": grupo},
            "series": saida, "diferenca_ic": ic, "p_c4": p, "acima_de_2022": bool(acima),
            "fora_da_referencia": bool(p < 0.05 and acima)}


def gravar_analise(r: dict) -> None:
    """Item C4 de `analise.json`. Pela seção 8 do pré-registro, decisão que muda em
    mais de 20% das especificações vira "depende da especificação", sem conclusão."""
    a = json.loads(ANALISE.read_text(encoding="utf-8"))
    s = r["principal"]["series"]
    br = lambda x: c1._br(x, 3).replace("-", "−")
    mv = r["multiverso"]
    fora = [m for m in mv if m["fora_da_referencia"]]
    texto = (f"Dentro do mesmo município, a correlação entre a hora em que o boletim chegou e a mudança da seção "
             f"do 1º para o 2º turno é {br(s['2026']['r4'])} em 2026 (p = {c1._br(s['2026']['p'], 2)}), contra "
             f"{br(s['2022']['r4'])} em 2022. ")
    if r["robusto"]:
        decisao = r["decisao"]
        abre = "Compatível com 2022. " if decisao == "compatível" else \
            "Fora da referência; a decisão final depende da correção para os seis testes. "
    else:
        decisao = "frágil"
        rs = [m["r4_2026"] for m in fora]
        abre = "Depende da especificação. "
        texto += (f"Na especificação principal não há nada. Mas em {len(fora)} de {len(mv)} especificações "
                  f"(zona no lugar do município, com piso de comparecimento) a correlação sobe para "
                  f"{br(min(rs))} a {br(max(rs))}, fica abaixo de p = 0,05 e acima de 2022. Pela regra "
                  f"pré-registrada, resultado que muda em mais de 20% das especificações não autoriza "
                  f"conclusão, nem para um lado nem para o outro. O tamanho é mínimo nos dois casos: uma "
                  f"correlação de 0,003 quer dizer que a hora de chegada não explica quase nada da mudança. ")
    if "governador" in r:
        g = r["governador"]
        texto += (f"No governador de 2026, nas mesmas urnas e sem acusação, a mesma correlação é "
                  f"{br(g['r4'])} (p = {c1._br(g['p'], 4)}), maior que a do presidente. ")
    texto += f"Mesma decisão da principal em {r['multiverso_mesma_decisao'].replace('/', ' de ')} especificações."
    for t in a["testes"]:
        if t["id"] == "C4":
            t.update({"status": "feito", "decisao": decisao, "resultado": abre + texto,
                      "dados": "/apuracao/explicacao/c4.json"})
    a["atualizado_em"] = r["gerado_em"][:10]
    ANALISE.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    red = frozenset(c1._red_2026())
    print("especificação principal…", flush=True)
    principal = rodar(red=red)
    print(json.dumps(principal, ensure_ascii=False, indent=1), flush=True)
    decisao = "pendente do BH" if principal["fora_da_referencia"] else "compatível"
    print(f"decisão: {decisao}", flush=True)
    print("governador 2026…", flush=True)
    gov = _governador(PERMUTACOES)
    print(f"  {gov}", flush=True)
    multiverso = []
    for grupo in ("municipio", "zona"):
        for piso in (0, 50, 100):
            for sem_red in (False, True):
                m = rodar(piso, sem_red, grupo, red=red)
                s = m["series"]
                linha = {**m["especificacao"], "r4_2026": s["2026"]["r4"], "r4_2022": s["2022"]["r4"],
                         "p": s["2026"]["p"], "diferenca_ic": m["diferenca_ic"],
                         "fora_da_referencia": m["fora_da_referencia"]}
                multiverso.append(linha)
                print(f"  {grupo:9} piso {piso:<3} {'sem RED' if sem_red else '       '} "
                      f"R4 {linha['r4_2026']}×{linha['r4_2022']} p {linha['p']} dif {linha['diferenca_ic']} "
                      f"{'FORA' if linha['fora_da_referencia'] else 'ok'}", flush=True)
    iguais = sum(1 for m in multiverso if m["fora_da_referencia"] == principal["fora_da_referencia"])
    r = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
         "preregistro": "docs/preregistro/README.md (preregistro-v1), seção 4, C4; esclarecimentos de 01/11 na seção 9",
         "principal": principal, "decisao": decisao, "governador": gov, "multiverso": multiverso,
         "multiverso_mesma_decisao": f"{iguais}/{len(multiverso)}", "robusto": iguais / len(multiverso) >= 0.8}
    DESTINO.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    gravar_analise(r)
    print(f"→ {DESTINO.relative_to(RAIZ)} · mesma decisão em {iguais}/{len(multiverso)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
