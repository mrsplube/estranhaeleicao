"""A geografia da virada: os três posts de 31/10 que perguntam a mesma coisa.

    venv/bin/python -m tools.migracoes.2026-10-31-geografia-da-virada

Os três posts ("Região dos Lagos" do @direitaraiiz, "toda a vantagem do Lula
foi construída nas urnas sem biometria" do @hendelsmx e a reportagem da
@metropolespolitica sobre as 70 cidades de prefeito do PL) fazem a mesma
pergunta por caminhos diferentes: **a virada se concentrou em algum lugar?**

Este arquivo responde com três recortes, cada um contado do arquivo do TSE:

- `lagos`: as seis cidades do carrossel, no 2º turno, seção a seção
  (`apuracao/cache/secoes_2026.pkl`). Confere o que o post publicou e mostra o
  que ele não mostra: a terceira via e o branco/nulo do 1º turno naquelas
  cidades, que é de onde saíram os votos do Lula.
- `biometria`: o resultado por seção cruzado com o Boletim de Urna
  (`QT_ELEI_BIO_SEM_HABILITACAO`), nas faixas de falha que o vídeo usa. Responde
  ao "Flávio teve 52%" e ao "97% da margem" com o número medido, e mostra que
  naquelas seções o Lula já ganhava no 1º turno e que a virada ali foi menor.
- `prefeitos`: quantos municípios viraram para cada lado, por partido do
  prefeito eleito em 2024 (`consulta_cand_2024`), com o critério da reportagem
  (prefeito filiado ao partido ou eleito por coligação que o inclui). É o
  recálculo da reportagem: 70 cidades na Metrópoles, 75 aqui.

Grava `static/casos/virada.json` (lido pela página) e uma cópia em
`apuracao/data/arquivo/2026-2t/virada.json` (o arquivo congelado).

Os brutos não entram no git: o Boletim de Urna de cada estado e o cadastro de
candidatos de 2024 ficam em cache temporário (`/tmp`), porque são 200 MB.
"""
from __future__ import annotations

import csv
import io
import json
import os
import pickle
import re
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
ARQ = RAIZ / "apuracao" / "data" / "arquivo" / "2026-2t"
CSS = RAIZ / "static" / "casos"
CACHE = Path(os.environ.get("TMPDIR", "/tmp")) / "tse-geografia"
CACHE.mkdir(parents=True, exist_ok=True)

BU_2T = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_2t_{uf}_261020260742.zip"
CAND_2024 = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2024.zip"
UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE",
       "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ"]
L1, F1, T1, BN1, C1, L2, F2, BN2, C2 = range(9)
# nome como sai no site (a chave é a do arquivo do TSE, em maiúsculas)
LAGOS = [("CABO FRIO", "Cabo Frio"), ("ARARUAMA", "Araruama"),
         ("SÃO PEDRO DA ALDEIA", "São Pedro da Aldeia"), ("ARMAÇÃO DOS BÚZIOS", "Armação dos Búzios"),
         ("SAQUAREMA", "Saquarema"), ("ARRAIAL DO CABO", "Arraial do Cabo")]
REGIAO = {"sp": "Sudeste", "rj": "Sudeste", "mg": "Sudeste", "es": "Sudeste",
          "pr": "Sul", "sc": "Sul", "rs": "Sul",
          "go": "Centro-Oeste", "mt": "Centro-Oeste", "ms": "Centro-Oeste", "df": "Centro-Oeste",
          "ba": "Nordeste", "pe": "Nordeste", "ce": "Nordeste", "ma": "Nordeste", "pb": "Nordeste",
          "rn": "Nordeste", "al": "Nordeste", "se": "Nordeste", "pi": "Nordeste",
          "ac": "Norte", "am": "Norte", "ap": "Norte", "pa": "Norte", "ro": "Norte",
          "rr": "Norte", "to": "Norte"}


def baixar(url: str, destino: Path) -> Path:
    if destino.exists() and destino.stat().st_size > 10000:
        return destino
    pedido = urllib.request.Request(url, headers={"User-Agent": "estranhaeleicao/1.0"})
    with urllib.request.urlopen(pedido, timeout=900) as r, open(destino, "wb") as f:
        while True:
            bloco = r.read(1 << 20)
            if not bloco:
                break
            f.write(bloco)
    return destino


def bu_sem_bio(uf: str) -> dict[tuple[str, int, int], int]:
    """{(município, zona, seção): eleitores com biometria que votaram sem ela}."""
    z = zipfile.ZipFile(baixar(BU_2T.format(uf=uf), CACHE / f"{uf}.zip"))
    nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
    leitor = csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";", quotechar='"')
    saida = {}
    for row in leitor:
        if row.get("CD_CARGO_PERGUNTA") != "1":
            continue
        bruto = row.get("QT_ELEI_BIOM_SEM_HABILITACAO") or "0"
        sem = int(bruto.replace("#NULO#", "0").replace("#NE#", "0") or 0)
        chave = (str(row["CD_MUNICIPIO"]).zfill(5), int(row["NR_ZONA"]), int(row["NR_SECAO"]))
        saida[chave] = max(sem, 0)
    return saida


def prefeitos_2024() -> dict[tuple[str, str], dict]:
    """{(uf, código do município): prefeito eleito} em 2024."""
    z = zipfile.ZipFile(baixar(CAND_2024, CACHE / "cand2024.zip"))
    leitor = csv.DictReader(io.TextIOWrapper(z.open("consulta_cand_2024_BRASIL.csv"), encoding="latin-1"),
                            delimiter=";", quotechar='"')
    saida = {}
    for row in leitor:
        if row["CD_CARGO"] != "11":          # prefeito
            continue
        if row["DS_SIT_TOT_TURNO"] not in ("ELEITO", "2º TURNO"):
            continue
        chave = (row["SG_UF"].lower(), row["SG_UE"])
        # "ELEITO" no 1º turno vale; "2º TURNO" só marca que a decisão foi depois
        if row["DS_SIT_TOT_TURNO"] == "ELEITO" or chave not in saida:
            saida[chave] = {"partido": row["SG_PARTIDO"], "coligacao": row["DS_COMPOSICAO_COLIGACAO"] or ""}
    return saida


def na_chapa(prefeito: dict | None, sigla: str) -> bool:
    """O critério da reportagem: prefeito do partido ou eleito por coligação que o inclui."""
    if not prefeito:
        return False
    if prefeito["partido"] == sigla:
        return True
    return bool(re.search(r"(?<![A-Za-z])%s(?![A-Za-z])" % sigla, prefeito["coligacao"]))


def pct(a: float, b: float) -> float:
    return round(100 * a / b, 2) if b else 0.0


def main() -> None:
    t = pickle.load(open(RAIZ / "apuracao" / "cache" / "secoes_2026.pkl", "rb"))
    A, ch, mun = t["A"].astype(np.int64), t["chaves"], t["mun"]

    # ── 1. as seis cidades da Região dos Lagos ────────────────────────────
    lagos = []
    for chave, nome in LAGOS:
        ks = {k for k, v in mun.items() if v == chave and k[0] == "rj"}
        idx = [i for i, c in enumerate(ch) if (c[0], c[1]) in ks]
        s = A[idx][:, :9].sum(0)
        novos = int(s[L2] - s[L1]) + int(s[F2] - s[F1])
        lagos.append({"nm": nome,
                      "l1": int(s[L1]), "l2": int(s[L2]), "f1": int(s[F1]), "f2": int(s[F2]),
                      "d_l": int(s[L2] - s[L1]), "d_f": int(s[F2] - s[F1]),
                      # quanto dos votos que apareceram no 2º turno foi para o Lula
                      "pct_lula_novos": pct(int(s[L2] - s[L1]), novos),
                      # o que havia para colher no 1º turno, sem tirar voto de ninguém
                      "terceira_mais_bn": int(s[T1] + s[BN1]),
                      "comp1": int(s[C1]), "comp2": int(s[C2]), "secoes": len(idx)})
    # os mesmos dois números no país, para comparar o "isolado" do post
    novos_pais = int(A[:, L2].sum() - A[:, L1].sum()) + int(A[:, F2].sum() - A[:, F1].sum())

    # ── 2. biometria × resultado, por seção ───────────────────────────────
    sem = {}
    for uf in UFS:
        if uf.lower() in {c[0] for c in ch}:
            for (municipio, zona, secao), n in bu_sem_bio(uf).items():
                sem[(uf.lower(), municipio, zona, secao)] = n
    registros = []
    for i, c in enumerate(ch):
        k = (c[0], c[1], c[2], c[3])
        if k in sem:
            registros.append((int(A[i, L1]), int(A[i, F1]), int(A[i, L2]), int(A[i, F2]),
                              int(A[i, C2]), sem[k]))
    R = np.array(registros, dtype=np.int64)
    comp = R[:, 4]
    frac = np.where(comp > 0, R[:, 5] / np.maximum(comp, 1), 0.0)
    faixas = [("sem falha", frac == 0), ("até 5%", (frac > 0) & (frac <= 0.05)),
              ("5 a 10%", (frac > 0.05) & (frac <= 0.10)), ("10 a 20%", (frac > 0.10) & (frac <= 0.20)),
              ("acima de 20%", frac > 0.20)]
    bio = []
    for rot, sel in faixas:
        l1, f1, l2, f2 = (int(R[sel, i].sum()) for i in range(4))
        bio.append({"faixa": rot, "secoes": int(sel.sum()),
                    "lula_pct": pct(l2, l2 + f2), "flavio_pct": pct(f2, l2 + f2),
                    "margem_1t": pct(l1 - f1, l1 + f1), "margem_2t": pct(l2 - f2, l2 + f2)})
    alto = frac > 0.10
    baixo = frac <= 0.05
    total2 = int(R[:, 2].sum() + R[:, 3].sum())
    margem_total = int(R[:, 2].sum() - R[:, 3].sum())
    def variacao(sel) -> float:
        """Quanto a margem do Lula andou entre os turnos, em pontos, naquele grupo."""
        m1 = 100 * (R[sel, 0].sum() - R[sel, 1].sum()) / max(R[sel, 0].sum() + R[sel, 1].sum(), 1)
        m2 = 100 * (R[sel, 2].sum() - R[sel, 3].sum()) / max(R[sel, 2].sum() + R[sel, 3].sum(), 1)
        return float(round(m2 - m1, 2))

    biometria = {
        "secoes": int(len(R)),
        "faixas": bio,
        "falha_alta": {
            "secoes": int(alto.sum()),
            "pct_validos": pct(int(R[alto, 2].sum() + R[alto, 3].sum()), total2),
            "pct_margem": pct(int(R[alto, 2].sum() - R[alto, 3].sum()), margem_total),
            "pct_ganho_lula": pct(int((R[alto, 2] - R[alto, 0]).sum()), int((R[:, 2] - R[:, 0]).sum())),
            "variacao_pp": variacao(alto),
        },
        "falha_baixa": {"secoes": int(baixo.sum()), "variacao_pp": variacao(baixo)},
    }

    # ── 3. a virada por partido do prefeito ───────────────────────────────
    municipios = [x for x in json.loads((ARQ / "municipios.json").read_text()) if x["uf"] != "zz"]
    pref = prefeitos_2024()
    for x in municipios:
        x["_p"] = pref.get((x["uf"], x["cd"]))

    def virou_lula(x):
        return x["f1"] > x["l1"] and x["l2"] > x["f2"]

    def virou_flavio(x):
        return x["l1"] > x["f1"] and x["f2"] > x["l2"]

    # A taxa honesta é viradas ÷ cidades onde o Flávio ganhou o 1º turno: nos
    # municípios em que o Lula ganhou antes não havia o que virar, e contá-los no
    # denominador só diluiria a comparação.
    por_partido = Counter()
    com_flavio = Counter()
    viraram = Counter()
    for x in municipios:
        if not x["_p"]:
            continue
        p = x["_p"]["partido"]
        por_partido[p] += 1
        if x["f1"] > x["l1"]:
            com_flavio[p] += 1
        if virou_lula(x):
            viraram[p] += 1
    tabela = [{"partido": p, "cidades": n, "flavio_1t": com_flavio[p], "viraram": viraram[p],
               "pct": pct(viraram[p], com_flavio[p])}
              for p, n in por_partido.most_common(8)]

    def bloco(sigla: str) -> dict:
        sel = [x for x in municipios if na_chapa(x["_p"], sigla)]
        c_f = [x for x in sel if x["f1"] > x["l1"]]
        c_l = [x for x in sel if x["l1"] > x["f1"]]
        vl = sum(1 for x in sel if virou_lula(x))
        vf = sum(1 for x in sel if virou_flavio(x))
        return {"cidades": len(sel), "flavio_1t": len(c_f), "lula_1t": len(c_l),
                "viraram_lula": vl, "viraram_flavio": vf,
                "pct_viraram": pct(vl, len(c_f)),
                "flavio_pct_1t": pct(len(c_f), len(sel)),
                "flavio_pct_2t": pct(sum(1 for x in sel if x["f2"] > x["l2"]), len(sel)),
                "lula_pct_1t": pct(len(c_l), len(sel)),
                "lula_pct_2t": pct(sum(1 for x in sel if x["l2"] > x["f2"]), len(sel)),
                "regioes": dict(Counter(REGIAO[x["uf"]] for x in sel if virou_lula(x)))}

    com_flavio_1t = [x for x in municipios if x["f1"] > x["l1"]]
    prefeitos = {
        "municipios": len(municipios),
        "com_prefeito_2024": sum(1 for x in municipios if x["_p"]),
        "flavio_1t": len(com_flavio_1t),
        "viraram_lula": sum(1 for x in municipios if virou_lula(x)),
        "viraram_flavio": sum(1 for x in municipios if virou_flavio(x)),
        "pct_viraram": pct(sum(1 for x in municipios if virou_lula(x)), len(com_flavio_1t)),
        "por_partido": tabela,
        "pl": bloco("PL"),
        "pt": bloco("PT"),
        "empate": [x["nm"] + "/" + x["uf"].upper() for x in municipios if x["l2"] == x["f2"]],
    }

    saida = {"fonte": "votação por seção e Boletim de Urna do TSE (2026) e cadastro de candidatos de 2024",
             "gerado_em": datetime.now().isoformat(timespec="seconds"),
             "lagos": {"cidades": lagos, "pct_lula_novos_pais": pct(int(A[:, L2].sum() - A[:, L1].sum()), novos_pais)},
             "biometria": biometria, "prefeitos": prefeitos}
    texto = json.dumps(saida, ensure_ascii=False, indent=1)
    (CSS / "virada.json").write_text(texto)
    (ARQ / "virada.json").write_text(texto)
    print("ok —", len(lagos), "cidades,", len(R), "seções cruzadas,", len(tabela), "partidos")
    print("Lagos:", [(c["nm"], c["pct_lula_novos"]) for c in lagos])
    print("biometria:", bio[0]["flavio_pct"], bio[1]["flavio_pct"], biometria["falha_alta"])
    print("prefeitos: PL", prefeitos["pl"]["viraram_lula"], "de", prefeitos["pl"]["cidades"],
          "| país", prefeitos["viraram_lula"], "de", prefeitos["flavio_1t"], "=", prefeitos["pct_viraram"])


if __name__ == "__main__":
    main()
