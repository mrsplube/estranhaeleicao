"""Reconciliação de 100% das seções do 2º turno presidencial de 2026.

    venv/bin/python -m tools.migracoes.2026-11-01-reconciliacao

## Por que existe

O TSE publica o resultado do 2º turno em três arquivos independentes entre si
no formato, e o site até aqui só usava um (votação por seção):

1. **Boletim de Urna** (`bweb_2t_<UF>_*.zip`), um por UF + exterior, com hash
   SHA-512 publicado ao lado — o que cada urna imprimiu e transmitiu;
2. **Votação por seção** (`votacao_secao_2026_BR.zip`) — o voto por candidato,
   seção a seção, já totalizado;
3. **Detalhe da votação por seção** (`detalhe_votacao_secao_2026.zip`) —
   aptos, comparecimento, brancos, nulos, se a seção foi instalada/anulada e a
   ORIGEM do voto (urna eletrônica, recuperador de dados, cédula...).

Aqui os três são cruzados **seção por seção** e somados contra o total oficial.
Se uma seção tivesse um número no boletim e outro na totalização, ela aparece.

## O que isto prova e o que NÃO prova

Prova: os arquivos públicos do TSE são consistentes entre si em 100% das
seções — o que a urna registrou no boletim é o que entrou no total.

NÃO prova: que o boletim reflete o voto digitado. Os três arquivos saem do
mesmo TSE, e o hash SHA-512 é servido pelo mesmo CDN (garante que o download
veio inteiro, não que o conteúdo é verdadeiro). O Brasil não tem voto impresso
conferido pelo eleitor; a conferência independente possível é comparar o BU
afixado na porta da seção (ou o QR code dele) com este arquivo, e verificar a
assinatura digital de cada `.bu` com a chave da urna. Nenhuma das duas está
aqui.

Gera `apuracao/data/arquivo/2026-2t/reconciliacao.json`. Os brutos ficam em
`apuracao/cache/` (fora do git), como os de 2022.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / "apuracao/cache"
ARQUIVO = RAIZ / "apuracao/data/arquivo/2026-2t"
DESTINO = ARQUIVO / "reconciliacao.json"
API = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-boletim-de-urna"
VOTACAO = CACHE / "votacao_secao_2026_BR.zip"
DETALHE_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip"
DETALHE = CACHE / "detalhe_votacao_secao_2026.zip"
PASTA_BU = CACHE / "bweb2026_2t"
UA = {"User-Agent": "estranhaeleicao/1.0"}
LULA, FLAVIO = "13", "22"


def _baixar(url: str, destino: Path) -> None:
    tmp = destino.with_suffix(destino.suffix + ".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=900) as r, open(tmp, "wb") as f:
        while bloco := r.read(1 << 20):
            f.write(bloco)
    tmp.replace(destino)


def _texto(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("ascii", "replace")


def boletins() -> list[dict]:
    """Baixa (se faltar) o BU do 2º turno de cada UF e confere o SHA-512 publicado."""
    pacote = json.load(urllib.request.urlopen(urllib.request.Request(API, headers=UA), timeout=60))["result"]
    PASTA_BU.mkdir(exist_ok=True)
    saida = []
    for r in pacote["resources"]:
        nome = r.get("name", "")
        if "Segundo turno" not in nome or "Boletim de Urna" not in nome:
            continue
        url = r["url"]
        arq = PASTA_BU / url.rsplit("/", 1)[1]
        if not arq.exists():
            print(f"  baixando {arq.name}", flush=True)
            _baixar(url, arq)
        publicado = _texto(url + ".sha512").split()[0].lower()
        calculado = hashlib.sha512(arq.read_bytes()).hexdigest()
        saida.append({"uf": nome.split(" - ")[0].strip(), "arquivo": arq.name, "url": url,
                      "sha512": calculado, "hash_confere": calculado == publicado})
    return sorted(saida, key=lambda b: b["uf"])


def _csv(z: zipfile.ZipFile, nome: str):
    return csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1"), delimiter=";", quotechar='"')


def _int(v: str) -> int:
    try:
        return max(int(v), 0)
    except (TypeError, ValueError):
        return 0     # "#NULO#", "#NE#", "-1": não é contagem


def ler_bu(arq: Path) -> dict:
    """Seção → contagens do Presidente no BU."""
    z = zipfile.ZipFile(arq)
    nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    s: dict[tuple, dict] = {}
    for row in _csv(z, nome):
        if row["CD_CARGO_PERGUNTA"] != "1":
            continue
        k = (row["SG_UF"], row["CD_MUNICIPIO"], row["NR_ZONA"], row["NR_SECAO"])
        d = s.get(k)
        if d is None:
            d = s[k] = {"aptos": _int(row["QT_APTOS"]), "comp": _int(row["QT_COMPARECIMENTO"]),
                        "lula": 0, "flavio": 0, "brancos": 0, "nulos": 0, "outros": 0,
                        "encerramento": row["DT_ENCERRAMENTO"], "abertura": row["DT_ABERTURA"],
                        "agregadas": row["DS_SECOES_AGREGADAS"] not in ("", "#NULO#", "-1"),
                        "sem_bio": _int(row["QT_ELEI_BIOM_SEM_HABILITACAO"])}
        tipo, nr, q = row["DS_TIPO_VOTAVEL"], row["NR_VOTAVEL"], _int(row["QT_VOTOS"])
        if tipo == "Branco":
            d["brancos"] += q
        elif tipo == "Nulo":
            d["nulos"] += q
        elif nr == LULA:
            d["lula"] += q
        elif nr == FLAVIO:
            d["flavio"] += q
        else:
            d["outros"] += q
    return s


def ler_votacao() -> dict:
    """Seção → votos do Presidente no 2º turno, do arquivo de votação por seção."""
    z = zipfile.ZipFile(VOTACAO)
    nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    s: dict[tuple, Counter] = defaultdict(Counter)
    for row in _csv(z, nome):
        if row["NR_TURNO"] != "2" or row["CD_CARGO"] != "1":
            continue
        k = (row["SG_UF"], row["CD_MUNICIPIO"], row["NR_ZONA"], row["NR_SECAO"])
        nr = row["NR_VOTAVEL"]
        campo = {LULA: "lula", FLAVIO: "flavio", "95": "brancos", "96": "nulos"}.get(nr, "outros")
        s[k][campo] += _int(row["QT_VOTOS"])
    return s


def ler_detalhe() -> dict:
    """Seção → aptos, comparecimento, brancos, nulos, origem e situação (Presidente, 2º turno)."""
    if not DETALHE.exists():
        print("  baixando detalhe_votacao_secao_2026.zip (234 MB)", flush=True)
        _baixar(DETALHE_URL, DETALHE)
    z = zipfile.ZipFile(DETALHE)
    # O Presidente (abrangência nacional) só está em `_BR.csv`; os arquivos por
    # UF trazem os cargos estaduais e `_BRASIL.csv` traz tudo junto.
    nomes = [n for n in z.namelist() if n.endswith("_BR.csv")]
    s = {}
    for nome in nomes:
        for row in _csv(z, nome):
            if row["NR_TURNO"] != "2" or row["CD_CARGO"] != "1":
                continue
            k = (row["SG_UF"], row["CD_MUNICIPIO"], row["NR_ZONA"], row["NR_SECAO"])
            s[k] = {"aptos": _int(row["QT_APTOS"]), "comp": _int(row["QT_COMPARECIMENTO"]),
                    "brancos": _int(row["QT_VOTOS_BRANCOS"]), "nulos": _int(row["QT_VOTOS_NULOS"]),
                    "origem": row["DS_ORIGEM_VOTO"], "instalada": row["ST_SECAO_INSTALADA"],
                    "anulada": row["ST_SECAO_ANULADA"], "modelo": row["CD_MODELO_URNA"]}
    return s


def main() -> int:
    print("Boletins de Urna (BU) do 2º turno…", flush=True)
    bus = boletins()
    ruins = [b["uf"] for b in bus if not b["hash_confere"]]
    print(f"  {len(bus)} arquivos, SHA-512 confere em {len(bus) - len(ruins)}" + (f" (NÃO: {ruins})" if ruins else ""))
    bu: dict[tuple, dict] = {}
    for b in bus:
        bu.update(ler_bu(PASTA_BU / b["arquivo"]))
    print(f"  {len(bu):,} seções no BU", flush=True)

    print("votação por seção…", flush=True)
    vs = ler_votacao()
    print(f"  {len(vs):,} seções", flush=True)
    print("detalhe da votação por seção…", flush=True)
    det = ler_detalhe()
    print(f"  {len(det):,} seções", flush=True)

    # 1. BU × votação por seção: voto por candidato, seção a seção.
    so_bu = sorted(set(bu) - set(vs))
    so_vs = sorted(set(vs) - set(bu))
    div_voto = []
    for k in set(bu) & set(vs):
        a, b = bu[k], vs[k]
        dif = {c: b[c] - a[c] for c in ("lula", "flavio", "brancos", "nulos", "outros") if b[c] != a[c]}
        if dif:
            div_voto.append({"secao": "/".join(k), **dif})

    # 2. BU × detalhe: aptos, comparecimento, brancos e nulos.
    div_det = []
    for k in set(bu) & set(det):
        a, b = bu[k], det[k]
        dif = {c: b[c] - a[c] for c in ("aptos", "comp", "brancos", "nulos") if b[c] != a[c]}
        if dif:
            div_det.append({"secao": "/".join(k), **dif})
    so_bu_det = sorted(set(bu) - set(det))
    # O detalhe lista também as seções sem BU porque não houve voto (não
    # instaladas, ou instaladas com comparecimento 0): não é divergência.
    so_det = sorted(k for k in set(det) - set(bu) if det[k]["instalada"] != "Não" and det[k]["comp"] > 0)
    sem_voto = sorted(k for k in set(det) - set(bu) if not (det[k]["instalada"] != "Não" and det[k]["comp"] > 0))

    # 3. Soma das seções × total oficial.
    oficial = json.loads((ARQUIVO / "explicacao.json").read_text(encoding="utf-8"))["nacional"]["t2"]
    soma_bu = {c: sum(d[c] for d in bu.values()) for c in ("lula", "flavio", "brancos", "nulos", "comp")}
    soma_vs = {c: sum(d[c] for d in vs.values()) for c in ("lula", "flavio", "brancos", "nulos")}
    total = {}
    for c in ("lula", "flavio", "brancos", "nulos", "comp"):
        total[c] = {"oficial": oficial[c], "bu": soma_bu[c], "votacao_secao": soma_vs.get(c),
                    "bate": oficial[c] == soma_bu[c] and soma_vs.get(c, oficial[c]) == oficial[c]}

    # Por UF, para quem quiser conferir um estado.
    por_uf: dict[str, dict] = defaultdict(lambda: {"secoes": 0, "lula": 0, "flavio": 0, "comp": 0})
    for k, d in bu.items():
        u = por_uf[k[0]]
        u["secoes"] += 1
        for c in ("lula", "flavio", "comp"):
            u[c] += d[c]

    # Subprodutos que respondem casos do site direto do dado oficial.
    origem = Counter(d["origem"] for d in det.values())
    instalada = Counter(d["instalada"] for d in det.values())
    anulada = Counter(d["anulada"] for d in det.values())
    modelo = Counter(d["modelo"] for d in det.values())

    def _hora(s: str) -> datetime | None:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    # Horário de encerramento como a urna registrou no BU (no exterior, o do posto).
    enc = [h for d in bu.values() if (h := _hora(d["encerramento"]))]
    depois_17 = sum(1 for h in enc if (h.hour, h.minute) >= (17, 1))
    depois_1730 = sum(1 for h in enc if (h.hour, h.minute) >= (17, 30))
    depois_18 = sum(1 for h in enc if h.hour >= 18)
    # Voto fora da urna eletrônica, no Brasil (o exterior usa o Sistema de Apuração).
    fora_urna_br = Counter(d["origem"] for k, d in det.items()
                           if k[0] != "ZZ" and d["origem"] != "Urna Eletrônica")

    n = len(set(bu) & set(vs))
    divergentes = len({d["secao"] for d in div_voto} | {"/".join(k) for k in so_bu + so_vs})
    r = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "fonte": {
            "boletim_de_urna": API.replace("/api/3/action/package_show?id=", "/dataset/"),
            "votacao_secao": "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip",
            "detalhe_votacao_secao": DETALHE_URL,
        },
        "o_que_prova": "Os três arquivos públicos do TSE (Boletim de Urna, votação por seção e detalhe) "
                       "são consistentes entre si, seção a seção, e somam o total oficial.",
        "o_que_nao_prova": "Que o boletim reflete o voto digitado: os três saem do mesmo TSE. "
                           "A conferência independente é o BU afixado na seção e a assinatura digital de cada urna.",
        "boletins": bus,
        "secoes": {"bu": len(bu), "votacao_secao": len(vs), "detalhe": len(det), "comparadas": n},
        "bu_x_votacao": {"so_no_bu": ["/".join(k) for k in so_bu][:50], "so_na_votacao": ["/".join(k) for k in so_vs][:50],
                         "n_so_no_bu": len(so_bu), "n_so_na_votacao": len(so_vs),
                         "divergentes": len(div_voto), "exemplos": div_voto[:50]},
        "bu_x_detalhe": {"n_so_no_bu": len(so_bu_det), "n_so_no_detalhe_com_voto": len(so_det),
                         "n_sem_bu_sem_voto": len(sem_voto),
                         "divergentes": len(div_det), "exemplos": div_det[:50]},
        "total": total,
        # Censo, não amostra: todas as seções foram conferidas, então a proporção de
        # divergentes é conhecida, não estimada. Até 02/11 havia aqui um limite de
        # Clopper-Pearson ("6 por milhão"), que responde a uma pergunta de amostragem
        # que não existe (parecer do relatório v1, crítica 5).
        "censo": {
            "secoes_divergentes": divergentes, "secoes_conferidas": n,
            "leitura": "Todas as seções foram conferidas: a proporção de divergentes é exatamente "
                       "secoes_divergentes / secoes_conferidas, sem incerteza amostral. O limite é de "
                       "outra natureza: os três arquivos saem do TSE.",
        },
        "por_uf": dict(sorted(por_uf.items())),
        "origem_do_voto": dict(origem.most_common()),
        "fora_da_urna_no_brasil": dict(fora_urna_br.most_common()),
        "secao_instalada": dict(instalada), "secao_anulada": dict(anulada),
        "modelo_urna": dict(modelo.most_common()),
        "encerramento": {"secoes_com_hora": len(enc), "depois_das_17h": depois_17,
                         "depois_das_17h30": depois_1730, "depois_das_18h": depois_18},
        "agregadas": sum(1 for d in bu.values() if d["agregadas"]),
    }
    tmp = DESTINO.with_suffix(".tmp")
    tmp.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DESTINO)

    print(f"\nseções: BU {len(bu):,} · votação {len(vs):,} · detalhe {len(det):,}")
    print(f"BU × votação: {len(div_voto)} divergentes, {len(so_bu)} só no BU, {len(so_vs)} só na votação")
    print(f"BU × detalhe: {len(div_det)} divergentes, {len(so_bu_det)} só no BU, {len(so_det)} só no detalhe com voto, {len(sem_voto)} sem BU e sem voto")
    for c, t in total.items():
        print(f"  {c:8} oficial {t['oficial']:>12,}  BU {t['bu']:>12,}  votação {t['votacao_secao'] if t['votacao_secao'] is not None else '—':>12}  {'ok' if t['bate'] else 'DIFERE'}")
    print(f"censo: {divergentes} divergentes em {n:,} seções conferidas")
    print(f"origem: {dict(origem)}")
    print(f"fora da urna, só no Brasil: {dict(fora_urna_br)}")
    print(f"anulada: {dict(anulada)} · instalada: {dict(instalada)}")
    print(f"encerradas depois das 17h: {depois_17:,}; 17h30: {depois_1730:,}; 18h: {depois_18:,}")
    print(f"→ {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
