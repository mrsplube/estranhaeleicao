"""As acusações que circularam depois do 2º turno de 2026, conferidas no dado.

    venv/bin/python -m tools.migracoes.2026-10-29-acusacoes-2t
    venv/bin/python -m tools.migracoes.2026-10-29-acusacoes-2t --so-zonas   # só a acusação de 30/10

Roda UMA VEZ, à mão, e grava `apuracao/data/arquivo/2026-2t/acusacoes.json`.
A página pública (`static/apuracao_acusacoes.js`) só lê esse arquivo.

Cada acusação vira um bloco de NÚMEROS; o texto que a página escreve em volta
mora no JS. A régua é a da página inteira: o número da acusação é conferido
primeiro (quando ele confere, a página diz que confere), e só depois vem o que
o número quer dizer.

Fontes, todas públicas:

- `votacao_secao_2026_BR.zip` (dados abertos do TSE): voto de cada candidato em
  cada uma das 499.206 seções, nos dois turnos. É a única fonte que permite
  conferir afirmações do tipo "na mesma seção" e "em 3.042 seções". Fica em
  `apuracao/cache/` (fora do git e do arquivo congelado); a tabela compacta por
  seção é guardada em `apuracao/cache/secoes_2026.pkl` para não reler 1,6 GB.
- `explicacao.json` e `conta.json` (gerados pelas migrações de 27–28/10): o
  município e a estimativa por candidato da terceira via.
- `serie_pres.jsonl`: a noite da apuração, como o painel registrou.
"""
from __future__ import annotations

import csv
import io
import json
import pickle
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
ARQ = RAIZ / "apuracao" / "data" / "arquivo" / "2026-2t"
CACHE = RAIZ / "apuracao" / "cache"
URL_SECOES = "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_{ano}_BR.zip"
# Números que aparecem na seção mas o TSE conta como NULO. Em 2026, o 28 (PRTB,
# candidatura que renunciou) — mesma regra de `2026-10-27-explicacao-2t.py`.
# Em 2022 não houve (o 14 trocou de candidato antes da eleição e valeu).
ANULADOS = {2026: {"28"}, 2022: set()}
# 2022 entra como régua: os mesmos lugares já se comportavam assim? A soma das
# seções tem de bater com o oficial de 2022 antes de qualquer comparação.
OFICIAL_2022 = {"lula1": 57259504, "flavio1": 51072345, "lula2": 60345999, "flavio2": 58206354}

NOMES_UF = {
    "ac": "Acre", "al": "Alagoas", "am": "Amazonas", "ap": "Amapá", "ba": "Bahia",
    "ce": "Ceará", "df": "Distrito Federal", "es": "Espírito Santo", "go": "Goiás",
    "ma": "Maranhão", "mg": "Minas Gerais", "ms": "Mato Grosso do Sul", "mt": "Mato Grosso",
    "pa": "Pará", "pb": "Paraíba", "pe": "Pernambuco", "pi": "Piauí", "pr": "Paraná",
    "rj": "Rio de Janeiro", "rn": "Rio Grande do Norte", "ro": "Rondônia", "rr": "Roraima",
    "rs": "Rio Grande do Sul", "sc": "Santa Catarina", "se": "Sergipe", "sp": "São Paulo",
    "to": "Tocantins", "zz": "Exterior",
}

_MINUSC = {"de", "da", "do", "das", "dos", "e"}


def titulo(nome: str) -> str:
    """"FOZ DO IGUAÇU" → "Foz do Iguaçu" (o .title() do Python dá "Foz Do Iguaçu")."""
    return " ".join(p if i and p in _MINUSC else p[:1].upper() + p[1:]
                    for i, p in enumerate((nome or "").lower().split()))


# Colunas da tabela por seção.
L1, F1, T1, BN1, C1, L2, F2, BN2, C2, LOCAL = range(10)


def tabela_secoes(ano: int = 2026) -> dict:
    """Uma passada no CSV do TSE → uma linha por seção com os dois turnos.

    Em 2022 a coluna "F" é o Bolsonaro (o 22 de então): a tabela guarda o
    candidato do número 22, para a comparação ser do mesmo lado.
    """
    ZIP, TABELA = CACHE / f"votacao_secao_{ano}_BR.zip", CACHE / f"secoes_{ano}.pkl"
    anulados = ANULADOS.get(ano, set())
    if TABELA.exists():
        return pickle.loads(TABELA.read_bytes())
    if not ZIP.exists():
        import httpx
        print(f"baixando a votação por seção de {ano} (≈250 MB)…", flush=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", URL_SECOES.format(ano=ano), headers={"User-Agent": "Mozilla/5.0"},
                          timeout=httpx.Timeout(120.0, connect=15.0), follow_redirects=True) as r:
            r.raise_for_status()
            with ZIP.with_suffix(".part").open("wb") as f:
                for pedaco in r.iter_bytes(1 << 20):
                    f.write(pedaco)
        ZIP.with_suffix(".part").replace(ZIP)
    col = {1: (L1, F1, T1, BN1, C1), 2: (L2, F2, None, BN2, C2)}
    idx, chaves, linhas, mun, local = {}, [], [], {}, {}
    with zipfile.ZipFile(ZIP) as z:
        nome = next(x for x in z.namelist() if x.endswith(".csv"))
        with z.open(nome) as bruto:
            leitor = csv.reader(io.TextIOWrapper(bruto, encoding="latin-1"), delimiter=";")
            h = {c: i for i, c in enumerate(next(leitor))}
            iT, iUF, iCM, iNM, iZ, iS, iN, iQ, iL, iNL = (h[c] for c in (
                "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
                "NR_VOTAVEL", "QT_VOTOS", "NR_LOCAL_VOTACAO", "NM_LOCAL_VOTACAO"))
            for r in leitor:
                turno, uf = int(r[iT]), r[iUF].lower()
                k = (uf, r[iCM].zfill(5), int(r[iZ]), int(r[iS]))
                j = idx.get(k)
                if j is None:
                    j = idx[k] = len(chaves)
                    chaves.append(k)
                    linhas.append([0] * 10)
                    mun[(uf, k[1])] = r[iNM]
                lin = linhas[j]
                lin[LOCAL] = int(r[iL] or 0)
                local[(uf, k[1], k[2], lin[LOCAL])] = r[iNL]
                q, num = int(r[iQ] or 0), r[iN]
                cl, cf, ct, cb, cc = col[turno]
                lin[cc] += q
                if num in ("95", "96") or (turno == 1 and num in anulados):
                    lin[cb] += q
                elif num == "13":
                    lin[cl] += q
                elif num == "22":
                    lin[cf] += q
                elif ct is not None:
                    lin[ct] += q
    dados = {"chaves": chaves, "A": np.array(linhas, dtype=np.int32), "mun": mun, "local": local}
    TABELA.write_bytes(pickle.dumps(dados))
    return dados


def _conferir_totais(A: np.ndarray, nac: dict) -> None:
    """A soma das seções tem de bater com o nacional oficial ao voto."""
    pares = [(L1, "lula1"), (F1, "flavio1"), (L2, "lula2"), (F2, "flavio2")]
    for c, k in pares:
        if int(A[:, c].sum()) != nac[k]:
            raise SystemExit(f"soma das seções ≠ oficial em {k}: {int(A[:, c].sum())} × {nac[k]}")


# ── 1. "3.042 seções com Flávio até 10 votos" e "106 urnas zeradas" ─────────
def secoes_ate_10(A: np.ndarray, chaves: list, local: dict) -> dict:
    tem1, tem2 = A[:, C1] > 0, A[:, C2] > 0

    def faixa(cand, outro, tem):
        return {
            "por_voto": [int((tem & (A[:, cand] == v)).sum()) for v in range(11)],
            "secoes": int((tem & (A[:, cand] <= 10)).sum()),
            "outro_somou": int(A[tem & (A[:, cand] <= 10), outro].sum()),
            "zeradas": int((tem & (A[:, cand] == 0)).sum()),
            "outro_nas_zeradas": int(A[tem & (A[:, cand] == 0), outro].sum()),
        }

    sel = tem2 & (A[:, F2] <= 10)
    uf = np.array([k[0] for k in chaves])
    ambos = tem1 & tem2

    def somas(m):
        return {c: int(A[m, i].sum()) for c, i in (("l1", L1), ("f1", F1), ("t1", T1), ("bn1", BN1), ("c1", C1),
                                                    ("l2", L2), ("f2", F2), ("bn2", BN2), ("c2", C2))} | {"secoes": int(m.sum())}

    # O voto do Lula NAS MESMAS seções, nos dois turnos, faixa a faixa (0 a 10
    # votos do Flávio no 2º turno) — a comparação que o post não faz.
    faixas = []
    for v in range(11):
        m = ambos & (A[:, F2] == v)
        faixas.append({"voto": v, **somas(m)})
    # Que lugar é esse: o nome do local de votação diz aldeia, povoado,
    # assentamento, comunidade… (é o NOME, não um cadastro — conta por baixo).
    rx = re.compile(r"ALDEIA|IND[IÍ]GEN|QUILOMB|POVOADO|ASSENTAMENTO|COMUNIDADE|RIBEIRINH|RURAL|S[IÍ]TIO|FAZENDA|VILA ", re.I)
    ald = re.compile(r"ALDEIA|IND[IÍ]GEN", re.I)

    def nome_local(j):
        k = chaves[j]
        return local.get((k[0], k[1], k[2], int(A[j, LOCAL])), "") or ""

    def conta(mask, regex):
        return sum(1 for j in np.where(mask)[0] if regex.search(nome_local(j)))

    margem = int(A[:, L2].sum() - A[:, F2].sum())
    tot = somas(sel & tem1)
    return {
        "faixas_2t": faixas,
        "total": tot,
        "ja_eram": somas(sel & tem1 & (A[:, F1] <= 10)),
        "entraram": somas(sel & tem1 & (A[:, F1] > 10)),
        "margem": margem,
        "margem_sem_elas": margem - (tot["l2"] - tot["f2"]),
        "comparecimento_medio": [round(tot["c2"] / max(tot["secoes"], 1)), round(int(A[tem2, C2].sum()) / int(tem2.sum()))],
        "local_rural": [conta(sel, rx), int(sel.sum())],
        "local_rural_pais": [conta(tem2, rx), int(tem2.sum())],
        "zeradas_em_aldeia": [conta(tem2 & (A[:, F2] == 0), ald), int((tem2 & (A[:, F2] == 0)).sum())],
        "flavio_2t": faixa(F2, L2, tem2),
        "flavio_1t": faixa(F1, L1, tem1),
        "lula_2t": faixa(L2, F2, tem2),
        "lula_1t": faixa(L1, F1, tem1),
        "ja_eram_ate_10_no_1t": int((sel & tem1 & (A[:, F1] <= 10)).sum()),
        "ja_eram_ate_20_no_1t": int((sel & tem1 & (A[:, F1] <= 20)).sum()),
        "flavio_nelas_1t": int(A[sel, F1].sum()),
        "flavio_nelas_2t": int(A[sel, F2].sum()),
        "lula_nelas_1t": int(A[sel, L1].sum()),
        "lula_nelas_2t": int(A[sel, L2].sum()),
        "ufs": [{"uf": u, "nome": NOMES_UF.get(u, u), "secoes": n}
                for u, n in Counter(uf[sel].tolist()).most_common(8)],
        "secoes_total": int(tem2.sum()),
    }


# ── 2. "700 votos no 1º turno e 8 ou 9 no 2º, na mesma seção" ──────────────
def mesma_secao(A: np.ndarray, chaves: list, mun: dict, local: dict) -> dict:
    tem1, tem2 = A[:, C1] > 0, A[:, C2] > 0
    ambos = tem1 & tem2
    queda = np.where(ambos, A[:, F1] - A[:, F2], -10**9)
    maiores = []
    for j in np.argsort(-queda)[:8]:
        k = chaves[j]
        maiores.append({
            "uf": k[0], "municipio": titulo(mun[(k[0], k[1])]), "zona": k[2], "secao": k[3],
            "local": titulo(local.get((k[0], k[1], k[2], int(A[j, LOCAL])), "")),
            "flavio": [int(A[j, F1]), int(A[j, F2])], "lula": [int(A[j, L1]), int(A[j, L2])],
            "comparecimento": [int(A[j, C1]), int(A[j, C2])],
        })
    return {
        "secoes_nos_dois_turnos": int(ambos.sum()),
        "so_1t": int((tem1 & ~tem2).sum()), "so_2t": int((~tem1 & tem2).sum()),
        "max_flavio": [int(A[:, F1].max()), int(A[:, F2].max())],
        "max_comparecimento": [int(A[:, C1].max()), int(A[:, C2].max())],
        "de_100_para_ate_10": int((ambos & (A[:, F1] >= 100) & (A[:, F2] <= 10)).sum()),
        "de_700_para_ate_10": int((ambos & (A[:, F1] >= 700) & (A[:, F2] <= 10)).sum()),
        "maiores_quedas": maiores,
    }


# ── 2b. "Repetindo em cada zona o mesmo número" (vídeo de 30/10/2026) ───────
# O vídeo filma o app Resultados do TSE trocando de zona dentro da mesma cidade.
# Cada linha: as zonas abertas, em ordem, e a zona DONA do número que a tela
# mostrou nelas (lido quadro a quadro, à mão). "papel" é a folha que a autora
# mostra no começo, com as zonas que ela anotou de outra vez — a zona 9 de
# Brasília está nos dois, com números diferentes.
VIDEO_ZONAS = [
    ("df", "97012", "Brasília", [8], 8, "tela"),
    ("df", "97012", "Brasília", [1, 2, 3, 5, 6, 9], 1, "tela"),
    ("ba", "38490", "Salvador", [1, 2, 3], 1, "tela"),
    ("mg", "41238", "Belo Horizonte", [30, 32], 30, "tela"),
    ("sp", "71072", "São Paulo", [4, 5], 4, "tela"),
    ("df", "97012", "Brasília", [1, 2, 3, 5, 6], 1, "papel"),
    ("df", "97012", "Brasília", [9, 10, 11], 9, "papel"),
]


def zonas_repetidas(A: np.ndarray, chaves: list) -> dict:
    """O placar de cada zona (município × zona) no 2º turno, e as do vídeo."""
    z: dict = {}
    for j in np.where(A[:, C2] > 0)[0]:
        uf, cm, zona, _ = chaves[j]
        t = z.setdefault((uf, cm, zona), [0, 0, 0])
        t[0] += int(A[j, L2])
        t[1] += int(A[j, F2])
        t[2] += 1
    placares = Counter((v[0], v[1]) for v in z.values())
    por_cidade = Counter(k[:2] for k in z)

    def zona(uf, cm, n):
        l, f, sec = z[(uf, cm, n)]
        return {"zona": n, "l": l, "f": f, "secoes": sec}

    cidades = {}
    for uf, cm, nm, *_ in VIDEO_ZONAS:
        lin = [v for k, v in z.items() if k[:2] == (uf, cm)]
        cidades[nm] = {"uf": uf, "zonas": len(lin), "l": sum(v[0] for v in lin), "f": sum(v[1] for v in lin)}
    return {
        "zonas_pais": len(z),
        "placares_repetidos": sum(1 for c in placares.values() if c > 1),
        "cidades_varias_zonas": sum(1 for c in por_cidade.values() if c > 1),
        "zonas_nessas_cidades": sum(c for c in por_cidade.values() if c > 1),
        "video": [{"uf": uf, "nm": nm, "onde": onde, "dona": zona(uf, cm, dona),
                   "zonas": [zona(uf, cm, n) for n in zonas]}
                  for uf, cm, nm, zonas, dona, onde in VIDEO_ZONAS],
        "cidades": cidades,
    }


# ── 3. Silva Jardim e o "10^-468" ───────────────────────────────────────────
def silva_jardim(expl: dict, conta: dict) -> dict:
    nums = expl["numeros"]
    nomes = {c["n"]: c["nm"] for c in expl["candidatos_1t"]}
    lam = {c["n"]: c["estimativa"] for c in conta["transicao"]["candidatos"]}
    linhas, alvo = [], None
    for m in expl["municipios"]:
        if m["uf"] == "zz" or "t2" not in m:
            continue
        t1, t2 = m["t1"], m["t2"]
        terc = sum(v for n, v in zip(nums, t1["outros"]) if n not in ("13", "22"))
        # o que a estimativa por candidato da terceira via + o voto novo diriam
        esperado = sum(lam.get(n, 0.8) * v for n, v in zip(nums, t1["outros"]) if n not in ("13", "22")) \
            + max(t2["validos"] - t1["validos"], 0)
        d_l, d_f = t2["lula"] - t1["lula"], t2["flavio"] - t1["flavio"]
        linha = {"nm": m["nm"], "uf": m["uf"], "cd": m["cd"], "v1": t1["validos"], "d_l": d_l, "d_f": d_f, "terc": terc,
                 "f2_pct": 100 * t2["flavio"] / t2["validos"] if t2["validos"] else 0,
                 "residuo": (d_l - esperado) / t1["validos"] if t1["validos"] else 0}
        linhas.append(linha)
        if m["nm"] == "SILVA JARDIM" and m["uf"] == "rj":
            alvo = {"t1": t1, "t2": t2, "esperado_lula": round(esperado),
                    "terceira": sorted(({"nm": nomes[n], "v": v} for n, v in zip(nums, t1["outros"])
                                        if n not in ("13", "22") and v), key=lambda x: -x["v"])}
    res = np.array([x["residuo"] for x in linhas])
    sj = next(x for x in linhas if x["nm"] == "SILVA JARDIM" and x["uf"] == "rj")
    med = float(np.median(res))
    ganho = [x for x in linhas if x["d_l"] + x["d_f"] > 0]
    quase_tudo = [x for x in ganho if x["d_l"] / (x["d_l"] + x["d_f"]) >= 0.99]
    venceu = sorted([x for x in quase_tudo if x["f2_pct"] >= 60], key=lambda x: -x["v1"])
    return {
        "municipio": alvo,
        "municipios": len(linhas),
        "flavio_ganho_ate_zero": sum(1 for x in linhas if x["d_f"] <= 0),
        "lula_ganho_negativo": sum(1 for x in linhas if x["d_l"] < 0),
        "quase_tudo_lula": len(quase_tudo),
        "quase_tudo_lula_com_flavio_60": len(venceu),
        "exemplos": [{"nm": titulo(x["nm"]), "uf": x["uf"], "cd": x["cd"], "d_f": x["d_f"], "d_l": x["d_l"], "terc": x["terc"],
                      "f2_pct": round(x["f2_pct"], 1)} for x in venceu[:6]],
        "residuo_pct": round(100 * sj["residuo"], 2),
        "residuo_votos": round(sj["residuo"] * sj["v1"]),
        "acima": int((res > sj["residuo"]).sum()),
        "do_outro_lado": int((res < 2 * med - sj["residuo"]).sum()),
        "percentis": [round(float(x), 2) for x in 100 * np.percentile(res, [5, 25, 50, 75, 95])],
    }


# ── 4. "A curva da apuração tem um padrão" ──────────────────────────────────
def curvas(A: np.ndarray, chaves: list, com_noite: bool = True) -> dict:
    """A participação do Lula ao longo da contagem, de três jeitos.

    - a noite real (o painel guardou % apurado × % do Lula);
    - as MESMAS seções somadas em ordem sorteada, oito vezes;
    - as mesmas seções em ordem de região (Sul primeiro, Nordeste por último),
      para mostrar que a ordem de chegada, sozinha, desenha uma "virada".
    """
    tem = A[:, C2] > 0
    l, f = A[tem, L2].astype(np.int64), A[tem, F2].astype(np.int64)
    uf = np.array([k[0] for k in chaves])[tem]
    pontos = np.unique(np.concatenate([np.linspace(0.005, 0.05, 10), np.linspace(0.05, 1, 96)]))

    def curva(ordem):
        cl, cv = np.cumsum(l[ordem]), np.cumsum(l[ordem] + f[ordem])
        js = np.maximum((pontos * len(ordem)).astype(int) - 1, 0)
        return [[round(100 * p, 2), round(100 * cl[j] / cv[j], 3)] for p, j in zip(pontos, js)]

    rng = np.random.default_rng(2026)
    sorteadas = [curva(rng.permutation(len(l))) for _ in range(8)]
    REGIAO = {**dict.fromkeys(["pr", "sc", "rs"], 0), **dict.fromkeys(["sp", "rj", "mg", "es"], 1),
              **dict.fromkeys(["go", "mt", "ms", "df"], 2),
              **dict.fromkeys(["ac", "am", "ap", "pa", "ro", "rr", "to"], 3),
              **dict.fromkeys(["al", "ba", "ce", "ma", "pb", "pe", "pi", "rn", "se"], 4), "zz": 1}
    reg = np.array([REGIAO.get(u, 2) for u in uf])
    por_regiao = curva(np.lexsort((rng.random(len(l)), reg)))
    noite = []
    for linha in ((ARQ / "serie_pres.jsonl").read_text(encoding="utf-8").splitlines() if com_noite else []):
        if linha.strip():
            p = json.loads(linha)
            noite.append([p["pst"], p["agora"]])
    final = round(100 * l.sum() / (l.sum() + f.sum()), 3)
    return {"final": final, "noite": noite, "sorteadas": sorteadas, "por_regiao": por_regiao,
            "faixa_sorteio_5pct": [min(x[1] for c in sorteadas for x in c if abs(x[0] - 5) < 0.6),
                                   max(x[1] for c in sorteadas for x in c if abs(x[0] - 5) < 0.6)]}


# ── 2022 como régua ─────────────────────────────────────────────────────────
# A pergunta de cada cartão: os mesmos lugares já se comportavam assim na
# eleição passada? O código de município do TSE é o mesmo nas duas eleições,
# então a cidade casa exata. A SEÇÃO é renumerada entre eleições, então para
# seção a comparação é do padrão (quantas, onde, de que tamanho), nunca da
# mesma seção. Em 2022 a coluna F é o Bolsonaro (o 22 de então).
COLS = (L1, F1, T1, BN1, C1, L2, F2, BN2, C2)


def por_municipio(A: np.ndarray, chaves: list) -> dict:
    ids: dict = {}
    cod = np.array([ids.setdefault((k[0], k[1]), len(ids)) for k in chaves])
    M = np.zeros((len(ids), len(COLS)), dtype=np.int64)
    np.add.at(M, cod, A[:, list(COLS)].astype(np.int64))
    return {k: M[i] for k, i in ids.items()}


def _mun_resumo(v) -> dict:
    l1, f1, t1, bn1, c1, l2, f2, bn2, c2 = (int(x) for x in v)
    return {"l1": l1, "f1": f1, "t1": t1, "bn1": bn1, "c1": c1, "l2": l2, "f2": f2, "bn2": bn2, "c2": c2,
            "v1": l1 + f1 + t1, "v2": l2 + f2}


def regua_municipios(M: dict, exemplos: list[tuple[str, str]]) -> dict:
    """Quantos municípios tiveram saldo do 22 ≤ 0, e os exemplos, na eleição dada."""
    lin = [_mun_resumo(v) | {"uf": k[0], "cd": k[1]} for k, v in M.items() if k[0] != "zz" and v[4] and v[8]]
    ganho = [x for x in lin if (x["l2"] - x["l1"]) + (x["f2"] - x["f1"]) > 0]
    quase = [x for x in ganho if (x["l2"] - x["l1"]) / ((x["l2"] - x["l1"]) + (x["f2"] - x["f1"])) >= 0.99]
    return {
        "municipios": len(lin),
        "f_ganho_ate_zero": sum(1 for x in lin if x["f2"] - x["f1"] <= 0),
        "quase_tudo_lula": len(quase),
        "quase_tudo_lula_com_f60": sum(1 for x in quase if x["v2"] and x["f2"] / x["v2"] >= 0.6),
        "exemplos": {f"{uf}-{cd}": _mun_resumo(M[(uf, cd)]) for uf, cd in exemplos if (uf, cd) in M},
    }


def regua_secoes(A: np.ndarray, chaves: list) -> dict:
    """O padrão por seção numa eleição: máximos, quedas na mesma seção e as ≤ 10."""
    tem1, tem2 = A[:, C1] > 0, A[:, C2] > 0
    ambos = tem1 & tem2
    sel = tem2 & (A[:, F2] <= 10)
    uf = np.array([k[0] for k in chaves])

    def s(m, c):
        return int(A[m, c].sum())
    return {
        "secoes": int(tem2.sum()),
        "max_f": [int(A[:, F1].max()), int(A[:, F2].max())],
        "max_comparecimento": [int(A[:, C1].max()), int(A[:, C2].max())],
        "maior_queda_f": int(np.where(ambos, A[:, F1] - A[:, F2], 0).max()),
        "de_100_para_ate_10": int((ambos & (A[:, F1] >= 100) & (A[:, F2] <= 10)).sum()),
        "f_ate_10": {"t1": int((tem1 & (A[:, F1] <= 10)).sum()), "t2": int(sel.sum()),
                     "zeradas": [int((tem1 & (A[:, F1] == 0)).sum()), int((tem2 & (A[:, F2] == 0)).sum())],
                     "por_voto_2t": [int((tem2 & (A[:, F2] == v)).sum()) for v in range(11)],
                     "lula_nelas": [s(sel & tem1, L1), s(sel, L2)], "f_nelas": [s(sel & tem1, F1), s(sel, F2)],
                     "ja_eram": int((sel & tem1 & (A[:, F1] <= 10)).sum()),
                     "ufs": [{"uf": u, "nome": NOMES_UF.get(u, u), "secoes": n}
                             for u, n in Counter(uf[sel].tolist()).most_common(6)]},
        "lula_ate_10": [int((tem1 & (A[:, L1] <= 10)).sum()), int((tem2 & (A[:, L2] <= 10)).sum())],
    }


def teste_do_grok(M: dict) -> dict:
    """O modelo do post aplicado a TODAS as cidades, não só à escolhida.

    Modelo: o saldo dos dois (ΔLula + Δ22) seriam votos sorteados um a um, cada
    um com a chance da fatia do 22 na cidade no 2º turno. Conta quantas cidades
    esse modelo chama de "impossíveis" (chance < 1 em 1 milhão), de cada lado.
    Se ele acusa quase o país inteiro, o que ele mede é o modelo, não fraude.
    """
    import math
    from scipy.stats import binom
    contra22 = contra13 = avaliados = 0
    for (uf, _cd), v in M.items():
        if uf == "zz":
            continue
        l1, f1, _t1, _b1, _c1, l2, f2, _b2, _c2 = (int(x) for x in v)
        n = (l2 - l1) + (f2 - f1)
        if n <= 0 or not (l2 + f2):
            continue
        avaliados += 1
        p, k = f2 / (l2 + f2), min(max(f2 - f1, 0), n)
        if binom.logcdf(k, n, p) / math.log(10) < -6:
            contra22 += 1
        if binom.logsf(k - 1, n, p) / math.log(10) < -6:
            contra13 += 1
    return {"avaliados": avaliados, "impossivel_a_favor_do_13": contra22, "impossivel_a_favor_do_22": contra13}


# ── Precisou eleitor do 22 virar Lula (ou o contrário)? ──────────────────────
# O que um candidato ganhou entre os turnos só pode ter vindo de: terceira via,
# branco/nulo do 1º turno, quem não votou no 1º turno, ou eleitor do outro
# finalista. Se o ganho passa da soma das três primeiras fontes, a diferença é
# troca OBRIGATÓRIA. Duas réguas:
#   estrita     — "quem não votou no 1º turno" = todo o eleitorado que faltou
#                 (o cadastro é o mesmo nos dois turnos). Só aritmética.
#   mesma gente — supõe que votou a mesma gente nos dois turnos, mais a
#                 diferença de comparecimento. Hipótese forte (ignora quem
#                 faltou num turno e foi no outro), útil para medir o MÁXIMO
#                 de troca que um lugar poderia exigir.
def aptos_mun_2026() -> dict:
    """{(uf, município): eleitorado} do 2º turno de 2026, do arquivo da apuração."""
    out = {}
    for f in (ARQ / "brutos").glob("abp_*.json"):
        uf = f.name[4:6]
        for m in json.loads(f.read_text(encoding="utf-8")).get("abr", []):
            if m.get("tpabr") == "mun":
                out[(uf, m["cdabr"].zfill(5))] = int(m["e"]["te"])
    return out


def aptos_mun_2022() -> dict:
    """{(uf, município): eleitorado} de 2022, somando o QT_APTOS de cada boletim."""
    destino = CACHE / "aptos2022.pkl"
    if destino.exists():
        return pickle.loads(destino.read_bytes())
    boletins_2022()                      # garante os zips (com SHA-512 conferido)
    secao: dict = {}
    for arq in sorted((CACHE / "bweb2022").glob("bweb_2t_*.zip")):
        with zipfile.ZipFile(arq) as z:
            nome = next(x for x in z.namelist() if x.lower().endswith(".csv"))
            with z.open(nome) as bruto:
                leitor = csv.reader(io.TextIOWrapper(bruto, encoding="latin-1"), delimiter=";")
                h = {c: i for i, c in enumerate(next(leitor))}
                iUF, iCM, iZ, iS, iCG, iA = (h[c] for c in ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO",
                                                            "CD_CARGO_PERGUNTA", "QT_APTOS"))
                for r in leitor:
                    if r[iCG] == "1":
                        secao.setdefault((r[iUF].lower(), r[iCM].zfill(5), int(r[iZ]), int(r[iS])), int(r[iA] or 0))
    out: dict = {}
    for k, v in secao.items():
        out[(k[0], k[1])] = out.get((k[0], k[1]), 0) + v
    destino.write_bytes(pickle.dumps(out))
    return out


def troca_minima(A: np.ndarray, chaves: list, aptos: dict, mascara=None) -> dict:
    tem = (A[:, C1] > 0) & (A[:, C2] > 0)
    if mascara is not None:
        tem = tem & mascara
    l1, f1, t1, b1, c1, l2, f2, _b2, c2 = (A[:, c].astype(np.int64) for c in COLS)
    disp = t1 + b1 + np.maximum(0, c2 - c1)
    p13 = np.where(tem, np.maximum(0, (l2 - l1) - disp), 0)
    p22 = np.where(tem, np.maximum(0, (f2 - f1) - disp), 0)
    out = {"secoes": int(tem.sum()),
           "secoes_mesma_gente": {"para_13": [int((p13 > 0).sum()), int(p13.sum())],
                                  "para_22": [int((p22 > 0).sum()), int(p22.sum())]}}
    if mascara is not None:
        return out
    M = por_municipio(A, chaves)
    m13 = m22 = s13 = s22 = e13 = e22 = 0
    for k, v in M.items():
        if k[0] == "zz":
            continue
        L1_, F1_, T1_, B1_, C1_, L2_, F2_, _B2, C2_ = (int(x) for x in v)
        d = T1_ + B1_ + max(0, C2_ - C1_)
        a13, a22 = max(0, (L2_ - L1_) - d), max(0, (F2_ - F1_) - d)
        m13 += a13 > 0; s13 += a13; m22 += a22 > 0; s22 += a22
        ap = aptos.get(k)
        if ap:
            de = T1_ + B1_ + max(0, ap - C1_)
            e13 += (L2_ - L1_) > de
            e22 += (F2_ - F1_) > de
    tot = A[tem].astype(np.int64).sum(0)
    sobra = lambda g: int(tot[T1] + tot[BN1] + max(0, tot[C2] - tot[C1]) - g)  # noqa: E731
    out.update({
        "municipios_estrito": {"para_13": e13, "para_22": e22, "com_eleitorado": sum(1 for k in M if k in aptos and k[0] != "zz")},
        "municipios_mesma_gente": {"para_13": [m13, s13], "para_22": [m22, s22]},
        "nacional_sobra": {"para_13": sobra(int(tot[L2] - tot[L1])), "para_22": sobra(int(tot[F2] - tot[F1]))},
    })
    return out


# ── Cidades fora do padrão ──────────────────────────────────────────────────
# Régua igual para as duas eleições: quanto a fatia do 22 (Bolsonaro/Flávio) nos
# válidos mudou do 1º para o 2º turno NA CIDADE, menos quanto mudou no PAÍS.
# Para cada cidade da ponta: o que aconteceu em 2022 e se a mudança se espalha
# pelas seções (cidade inteira mudando) ou se concentra em poucas (o que uma
# adulteração de urna deixaria) — "pior seção" = fatia da perda (ou do ganho)
# do 22 que veio da seção em que ele mais perdeu (ou ganhou).
def _desvios(A: np.ndarray, chaves: list) -> tuple[dict, float, dict]:
    idx: dict = {}
    for j, k in enumerate(chaves):
        if k[0] != "zz":
            idx.setdefault((k[0], k[1]), []).append(j)
    cid, V1, V2, F1, F2 = {}, 0, 0, 0, 0
    for k, js in idx.items():
        s = A[js][:, list(COLS)].astype(np.int64).sum(0)
        l1, f1, t1, _b1, c1, l2, f2, _b2, c2 = (int(x) for x in s)
        v1, v2 = l1 + f1 + t1, l2 + f2
        if v1 < 1 or v2 < 1:
            continue
        V1 += v1; V2 += v2; F1 += f1; F2 += f2
        cid[k] = {"v1": v1, "f1": f1, "f2": f2, "l1": l1, "l2": l2, "c1": c1, "c2": c2, "t1": t1,
                  "muda": 100 * f2 / v2 - 100 * f1 / v1}
    nac = 100 * F2 / V2 - 100 * F1 / V1
    for x in cid.values():
        x["desvio"] = x["muda"] - nac
    return cid, nac, idx


def fora_do_padrao(A: np.ndarray, chaves: list, mun: dict, A22: np.ndarray, chaves22: list, n: int = 6) -> dict:
    cid, nac, idx = _desvios(A, chaves)
    cid22, nac22, _ = _desvios(A22, chaves22)
    dev = np.array([x["desvio"] for x in cid.values()])
    dev22 = np.array([x["desvio"] for x in cid22.values()])
    ordem = sorted(cid, key=lambda k: cid[k]["desvio"])

    def caso(k, lado):
        x = cid[k]
        secs = A[idx[k]].astype(np.int64)
        mov = secs[:, F2] - secs[:, F1]                 # mudança do 22 em cada seção
        alvo = np.maximum(0, -mov) if lado < 0 else np.maximum(0, mov)
        y = cid22.get(k)
        return {"nm": titulo(mun.get(k, "?")), "uf": k[0], "validos": x["v1"], "secoes": len(idx[k]),
                "f": [x["f1"], x["f2"]], "l": [x["l1"], x["l2"]], "c": [x["c1"], x["c2"]],
                "pct": [round(100 * x["f1"] / x["v1"], 1), round(100 * x["f2"] / (x["l2"] + x["f2"]), 1)],
                "desvio": round(x["desvio"], 1), "terceira_pct": round(100 * x["t1"] / x["v1"], 1),
                "secoes_no_sentido": int((mov < 0).sum() if lado < 0 else (mov > 0).sum()),
                "pior_secao": round(float(alvo.max() / max(alvo.sum(), 1)), 3),
                "em_2022": None if not y else {"f": [y["f1"], y["f2"]], "l": [y["l1"], y["l2"]], "c": [y["c1"], y["c2"]],
                                               "desvio": round(y["desvio"], 1)}}
    contra, favor = ordem[:50], ordem[::-1][:50]
    go = [x["desvio"] for k, x in cid.items() if k[0] == "go"]
    return {
        "nacional": [round(nac, 2), round(nac22, 2)],
        "dp": [round(float(dev.std()), 2), round(float(dev22.std()), 2)],
        "p5_p95": [[round(float(np.percentile(dev, 5)), 1), round(float(np.percentile(dev, 95)), 1)],
                   [round(float(np.percentile(dev22, 5)), 1), round(float(np.percentile(dev22, 95)), 1)]],
        "contra_o_22": [caso(k, -1) for k in contra[:n]],
        "a_favor_do_22": [caso(k, +1) for k in favor[:n]],
        "ufs_contra": [{"uf": u, "nome": NOMES_UF.get(u, u), "cidades": q} for u, q in Counter(k[0] for k in contra).most_common(4)],
        "ufs_favor": [{"uf": u, "nome": NOMES_UF.get(u, u), "cidades": q} for u, q in Counter(k[0] for k in favor).most_common(3)],
        "goias": {"desvio_medio": round(float(np.mean(go)), 1), "resto": round(float(np.mean([x["desvio"] for k, x in cid.items() if k[0] != "go"])), 1),
                  "terceira_media": round(float(np.mean([x["t1"] / x["v1"] for k, x in cid.items() if k[0] == "go"])) * 100, 1)},
        "cidades": len(cid),
    }


def trocas_de_lideranca(A: np.ndarray, voltas: int = 200) -> dict:
    """A conta que o vídeo diz ter feito: as mesmas seções em ordens sorteadas.

    Para cada ordem, quantas vezes a liderança troca de mão na soma acumulada e
    em que ponto (% das seções) acontece a ÚLTIMA troca.
    """
    tem = A[:, C2] > 0
    dif = (A[tem, L2].astype(np.int64) - A[tem, F2].astype(np.int64))
    n = len(dif)
    rng = np.random.default_rng(472)
    trocas, ultima = [], []
    for _ in range(voltas):
        acum = np.cumsum(dif[rng.permutation(n)])
        sinal = np.sign(acum)
        sinal = sinal[sinal != 0]
        mudou = np.nonzero(np.diff(sinal))[0]
        trocas.append(len(mudou))
        ultima.append(100 * (mudou[-1] + 1) / n if len(mudou) else 0.0)
    trocas, ultima = np.array(trocas), np.array(ultima)
    return {"voltas": voltas, "secoes": n, "trocas_mediana": int(np.median(trocas)),
            "trocas_max": int(trocas.max()), "sem_troca": int((trocas == 0).sum()),
            "ultima_troca_p95": round(float(np.percentile(ultima, 95)), 3),
            "ultima_troca_max": round(float(ultima.max()), 3)}


# ── A noite de 2022, na ordem em que os boletins chegaram ───────────────────
# O vídeo "Fomos roubados" (republicado em 28/10/2026) é uma análise da noite de
# 2022: os gráficos são a fatia acumulada do Bolsonaro com os boletins de urna
# na ORDEM DE CHEGADA ao TSE. Essa ordem está no próprio boletim (coluna
# DT_BU_RECEBIDO) — 28 arquivos, ~70 MB, cada um com SHA-512 publicado. Com eles
# o gráfico do vídeo se refaz ponto a ponto (entre a seção 70 mil e a 85 mil o
# Bolsonaro fica em 0,5163–0,5167, o eixo do vídeo).
CKAN_BU_2022 = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2022-boletim-de-urna"
JANELA_VIDEO = (70000, 85000)


def boletins_2022() -> dict:
    """{(uf, município, zona, seção): [lula, bolsonaro, 'dd/mm/aaaa hh:mm:ss']} do 2º turno de 2022."""
    destino = CACHE / "bweb2022_2t.pkl"
    if destino.exists():
        return pickle.loads(destino.read_bytes())
    import hashlib
    import urllib.request
    pasta = CACHE / "bweb2022"
    pasta.mkdir(parents=True, exist_ok=True)

    def pedir(url, prazo=60):
        return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=prazo).read()
    pacote = json.loads(pedir(CKAN_BU_2022, 40))["result"]
    urls = [r["url"] for r in pacote["resources"] if re.search(r"bweb_2t_[A-Z]{2}_\d+\.zip$", r.get("url") or "")]
    secoes: dict = {}
    for u in urls:
        arq = pasta / u.rsplit("/", 1)[1]
        if not arq.exists():
            arq.write_bytes(pedir(u, 600))
        sha = pedir(u + ".sha512").decode().split()[0].lower()
        if hashlib.sha512(arq.read_bytes()).hexdigest() != sha:
            raise SystemExit(f"SHA-512 não confere: {arq.name}")
        with zipfile.ZipFile(arq) as z:
            nome = next(x for x in z.namelist() if x.lower().endswith(".csv"))
            with z.open(nome) as bruto:
                leitor = csv.reader(io.TextIOWrapper(bruto, encoding="latin-1"), delimiter=";")
                h = {c: i for i, c in enumerate(next(leitor))}
                iUF, iCM, iZ, iS, iCG, iN, iQ, iT = (h[c] for c in (
                    "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO_PERGUNTA", "NR_VOTAVEL", "QT_VOTOS", "DT_BU_RECEBIDO"))
                for r in leitor:
                    if r[iCG] != "1":          # só presidente
                        continue
                    k = (r[iUF].lower(), r[iCM].zfill(5), int(r[iZ]), int(r[iS]))
                    s = secoes.setdefault(k, [0, 0, r[iT]])
                    if r[iN] == "13":
                        s[0] += int(r[iQ])
                    elif r[iN] == "22":
                        s[1] += int(r[iQ])
    destino.write_bytes(pickle.dumps(secoes))
    return secoes


def noite_2022(mun: dict) -> dict:
    S = boletins_2022()
    ks = list(S.keys())
    quando = [datetime.strptime(S[k][2], "%d/%m/%Y %H:%M:%S") for k in ks]
    o = sorted(range(len(ks)), key=lambda i: (quando[i], ks[i]))
    L = np.array([S[ks[i]][0] for i in o], dtype=np.int64)
    B = np.array([S[ks[i]][1] for i in o], dtype=np.int64)
    if int(L.sum()) != OFICIAL_2022["lula2"] or int(B.sum()) != OFICIAL_2022["flavio2"]:
        raise SystemExit("boletins de 2022 não somam o oficial")
    n = len(L)
    cb = np.cumsum(B) / np.maximum(np.cumsum(L + B), 1)
    hora = lambda j: quando[o[j]].strftime("%H:%M")  # noqa: E731
    # a noite inteira (x em % das seções), mais densa no começo
    xs = np.unique(np.concatenate([np.linspace(0.002, 0.05, 25), np.linspace(0.05, 1, 120)]))
    curva = [[round(100 * x, 2), round(100 * float(cb[max(int(x * n) - 1, 0)]), 3)] for x in xs]
    a, b = JANELA_VIDEO
    zoom = [[int(x), round(float(cb[x]), 5)] for x in range(a, b + 1, 50)]

    def lote(x, w):
        from collections import Counter as C
        lb, bb = int(L[x:x + w].sum()), int(B[x:x + w].sum())
        c = C((ks[o[i]][0], ks[o[i]][1]) for i in range(x, x + w))
        return {"de": x, "ate": x + w, "hora": quando[o[x]].strftime("%H:%M:%S"),
                "variacao_pp": round(100 * float(cb[x + w] - cb[x]), 4), "bolsonaro_no_lote": round(100 * bb / (lb + bb), 1),
                "lugares": [f"{titulo(mun.get(k, '?'))}/{k[0].upper()}" for k, _ in c.most_common(3)]}
    w = 400
    lotes = [lote(x, w) for x in range(a, b - w + 1, w)]
    lotes.sort(key=lambda z: z["variacao_pp"])
    d = np.cumsum(L - B)
    s = np.sign(d)
    nz = np.nonzero(s)[0]
    mud = nz[1:][np.diff(s[nz]) != 0]
    trocas = [{"pct": round(100 * float(m) / n, 2), "hora": hora(int(m))} for m in mud]

    def recorte(tam):
        k = n // tam
        Lb, Bb = L[:k * tam].reshape(k, tam).sum(1), B[:k * tam].reshape(k, tam).sum(1)
        antes = np.concatenate([[0.5], (np.cumsum(Bb) / np.maximum(np.cumsum(Lb + Bb), 1))[:-1]])
        sobe = (Bb / np.maximum(Lb + Bb, 1)) > antes
        return {"tamanho": tam, "bolsonaro_so_subidas": round(100 * Bb[sobe].sum() / (Lb[sobe] + Bb[sobe]).sum(), 1),
                "lula_so_quedas": round(100 * Lb[~sobe].sum() / (Lb[~sobe] + Bb[~sobe]).sum(), 1)}
    from collections import Counter as C
    vira = int(mud[-1]) if len(mud) else n
    inicio = C(ks[o[i]][0] for i in range(0, int(0.2 * n)))
    fim = C(ks[o[i]][0] for i in range(vira, n))
    return {
        "secoes": n, "primeiro": quando[o[0]].strftime("%d/%m %H:%M"), "ultimo": quando[o[-1]].strftime("%d/%m %H:%M"),
        "final": round(100 * float(cb[-1]), 3), "curva": curva,
        "janela": {"de": a, "ate": b, "hora": [hora(a), hora(b)], "min": round(float(cb[a:b + 1].min()), 5),
                   "max": round(float(cb[a:b + 1].max()), 5), "zoom": zoom},
        "quedas": lotes[:3], "subidas": lotes[-3:][::-1], "trocas": trocas,
        "ufs_inicio": [{"uf": u, "nome": NOMES_UF.get(u, u), "secoes": q} for u, q in inicio.most_common(5)],
        "ufs_fim": [{"uf": u, "nome": NOMES_UF.get(u, u), "secoes": q} for u, q in fim.most_common(6)],
        "recorte": [recorte(t) for t in (1, 10, 100, 400)],
    }


def main() -> int:
    expl = json.loads((ARQ / "explicacao.json").read_text(encoding="utf-8"))
    conta = json.loads((ARQ / "conta.json").read_text(encoding="utf-8"))
    nac = conta["nacional"]
    t = tabela_secoes()
    A, chaves = t["A"], t["chaves"]
    _conferir_totais(A, nac)
    print(f"{len(chaves)} seções; somas conferidas com o oficial", flush=True)
    if "--so-zonas" in sys.argv:
        # A acusação de 30/10 chegou depois: acrescenta só o bloco dela, sem
        # refazer 2022, os boletins e o Monte Carlo.
        destino = ARQ / "acusacoes.json"
        saida = json.loads(destino.read_text(encoding="utf-8"))
        saida["zonas"] = zonas_repetidas(A, chaves)
        destino.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        zr = saida["zonas"]
        print(f"gravado {destino}: {zr['zonas_pais']} zonas, {zr['placares_repetidos']} placares repetidos")
        return 0
    lim = conta["limite"]
    saida = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "fonte": {"secoes": URL_SECOES.format(ano=2026), "secoes_gerado_em": "26/10/2026"},
        "nacional": {"lula1": nac["lula1"], "lula2": nac["lula2"], "flavio1": nac["flavio1"], "flavio2": nac["flavio2"],
                     "margem": nac["lula2"] - nac["flavio2"]},
        "silva_jardim": silva_jardim(expl, conta),
        "mesma_secao": mesma_secao(A, chaves, t["mun"], t["local"]),
        "zonas": zonas_repetidas(A, chaves),
        "secoes_ate_10": secoes_ate_10(A, chaves, t["local"]),
        "curva": curvas(A, chaves),
    }
    saida["trocas_2026"] = trocas_de_lideranca(A)

    t22 = tabela_secoes(2022)
    A22 = t22["A"]
    _conferir_totais(A22, OFICIAL_2022)
    print(f"2022: {len(t22['chaves'])} seções; somas conferidas com o oficial", flush=True)
    sj = saida["silva_jardim"]
    exemplos = [("rj", "59110")] + [(e["uf"], e["cd"]) for e in sj["exemplos"]]
    c22 = curvas(A22, t22["chaves"], com_noite=False)
    M22 = por_municipio(A22, t22["chaves"])
    saida["teste_do_grok"] = {"2026": teste_do_grok(por_municipio(A, chaves)), "2022": teste_do_grok(M22)}
    saida["fora_do_padrao"] = fora_do_padrao(A, chaves, t["mun"], A22, t22["chaves"])
    ap26 = aptos_mun_2026()
    sel10 = (A[:, C2] > 0) & (A[:, F2] <= 10)
    saida["troca_minima"] = {
        "2026": troca_minima(A, chaves, ap26),
        "2022": troca_minima(A22, t22["chaves"], aptos_mun_2022()),
        "secoes_ate_10": troca_minima(A, chaves, ap26, mascara=sel10),
        "silva_jardim": {"eleitorado": ap26.get(("rj", "59110"))},
    }
    saida["regua_2022"] = {
        "nacional": OFICIAL_2022,
        "municipios": regua_municipios(M22, exemplos),
        "secoes": regua_secoes(A22, t22["chaves"]),
        "secoes_2026": regua_secoes(A, chaves),
        "trocas": trocas_de_lideranca(A22),
        "curva": {"final": c22["final"], "por_regiao": c22["por_regiao"], "faixa_sorteio_5pct": c22["faixa_sorteio_5pct"]},
        "noite": noite_2022(t22["mun"]),
        # A noite de 2022 não está no arquivo deste site; o ponto da virada é o
        # que a imprensa registrou ao vivo.
        "virada_noite": {"pct_apurado": 66, "fonte": "Correio Braziliense, 30/10/2022",
                         "url": "https://www.correiobraziliense.com.br/politica/2022/10/5048141-lula-vira-e-fica-com-vantagem-nas-urnas-acompanhe-apuracao.html"},
    }
    destino = ARQ / "acusacoes.json"
    destino.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"gravado {destino} ({destino.stat().st_size / 1e3:.0f} KB)")
    s = saida["secoes_ate_10"]
    print(f"Flávio ≤ 10: {s['flavio_2t']['secoes']} seções (1º t.: {s['flavio_1t']['secoes']}), "
          f"zeradas {s['flavio_2t']['zeradas']}; mesma seção ≥100→≤10: {saida['mesma_secao']['de_100_para_ate_10']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
