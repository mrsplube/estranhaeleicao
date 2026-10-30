"""Microdados eleitorais de SC — o voto de cada candidato por município e por seção.

    venv/bin/python -m politicos.microdados resultados   # 2026, arquivos do TSE por município
    venv/bin/python -m politicos.microdados historico    # 2022 por município + quem é quem
    venv/bin/python -m politicos.microdados secoes 2022  # 2022 por seção (100 MB de zip)
    venv/bin/python -m politicos.microdados locais 2026  # locais de votação, com lat/lon
    venv/bin/python -m politicos.microdados perfil 2026  # perfil do eleitorado por seção
    venv/bin/python -m politicos.microdados boletins     # 2026 por seção, quando o TSE publicar
    venv/bin/python -m politicos.microdados tudo

Tudo vai para `politicos/data/eleicoes.db`, separado do banco do app porque é
grande (milhões de linhas por seção) e porque é DADO PÚBLICO reimportável: se
o arquivo sumir, este comando o refaz do zero. Nada aqui gasta dinheiro.

Três decisões que o resto do código assume:

- **Cargo é o código do TSE** (1 presidente, 3 governador, 5 senador, 6 deputado
  federal, 7 deputado estadual) e município é o código do TSE (não o do IBGE —
  a tabela `municipio` traz os dois). Inteiro em tudo: são milhões de linhas.
- **`pessoa` liga a mesma pessoa entre eleições**: nome completo sem acento +
  data de nascimento. O número muda de uma eleição para outra, o SQ também, e
  o CPF o TSE não publica mais; nome + nascimento não colide em SC.
- **Voto de legenda é uma linha com o número do partido** (2 dígitos), branco é
  95 e nulo é 96 — exatamente como o boletim de urna escreve. Somar uma
  agremiação é somar os números dos seus candidatos e dos seus partidos.
- **Voto anulado também fica** (Paulo Eccel teve 16.689 votos sub judice em
  2026): onde ele foi votado é informação. Mas `candidato.valido = 0`, e toda
  soma de partido tem de juntar com `candidato` e filtrar `valido`.

Arquivo grande do TSE nunca é baixado inteiro para a memória: o CDN aceita
`Range`, então se lê o diretório do ZIP, acha-se o membro de SC e ele é
descomprimido EM FLUXO, linha a linha (o CSV por seção de 2022 tem 662 MB).
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sqlite3
import struct
import sys
import time
import unicodedata
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from politicos import eleicao

PASTA = Path(__file__).resolve().parent / "data"
BANCO = Path(os.environ.get("ELEICOES_DB") or PASTA / "eleicoes.db")
BRUTOS_2026 = PASTA / "tse" / "2026"
UA = {"User-Agent": "Mozilla/5.0 (microdados projetoscaue.lol)"}
ODSELE = "https://cdn.tse.jus.br/estatistica/sead/odsele/"
RESULTADOS = "https://resultados.tse.jus.br/oficial/ele2026"
CKAN = "https://dadosabertos.tse.jus.br/api/3/action/"

CARGOS = {1: "Presidente", 3: "Governador", 5: "Senador", 6: "Deputado federal", 7: "Deputado estadual"}
SIGLA_CARGO = {"pres": 1, "gov": 3, "sen": 5, "fed": 6, "est": 7}
BRANCO, NULO, ANULADO = 95, 96, 97      # 97: voto anulado / apurado em separado (boletim de urna)
# Arquivos de resultado por município, eleição 2026 (1º turno): presidente é a
# eleição federal (6257); os outros quatro cargos, a estadual (6259).
ARQ_2026 = {1: ("6257", "c0001"), 3: ("6259", "c0003"), 5: ("6259", "c0005"),
            6: ("6259", "c0006"), 7: ("6259", "c0007")}

ESQUEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS municipio (
    cd    INTEGER PRIMARY KEY,          -- código do TSE
    ibge  INTEGER,
    nome  TEXT NOT NULL,
    uf    TEXT NOT NULL DEFAULT 'SC'
);
CREATE TABLE IF NOT EXISTS candidato (
    ano INTEGER, turno INTEGER, cargo INTEGER, numero INTEGER,
    sq TEXT, nome TEXT, urna TEXT, nascimento TEXT,
    partido TEXT, agremiacao TEXT, situacao TEXT, eleito INTEGER, votos INTEGER,
    pessoa TEXT,
    valido INTEGER DEFAULT 1,           -- 0 = votos anulados (sub judice, indeferido)
    PRIMARY KEY (ano, turno, cargo, numero)
);
CREATE INDEX IF NOT EXISTS candidato_pessoa ON candidato(pessoa);
CREATE INDEX IF NOT EXISTS candidato_sq ON candidato(sq);
CREATE TABLE IF NOT EXISTS partido (
    ano INTEGER, turno INTEGER, cargo INTEGER, numero INTEGER,   -- número do partido (2 dígitos)
    sigla TEXT, agremiacao TEXT,
    PRIMARY KEY (ano, turno, cargo, numero)
);
CREATE TABLE IF NOT EXISTS voto_mun (
    ano INTEGER, turno INTEGER, cargo INTEGER, numero INTEGER, cd INTEGER, votos INTEGER,
    PRIMARY KEY (ano, turno, cargo, numero, cd)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS voto_mun_cd ON voto_mun(ano, turno, cargo, cd);
CREATE TABLE IF NOT EXISTS apuracao_mun (
    ano INTEGER, turno INTEGER, cargo INTEGER, cd INTEGER,
    aptos INTEGER, comparecimento INTEGER, abstencao INTEGER,
    validos INTEGER, nominais INTEGER, legenda INTEGER, brancos INTEGER, nulos INTEGER,
    PRIMARY KEY (ano, turno, cargo, cd)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS voto_secao (
    ano INTEGER, turno INTEGER, cargo INTEGER, cd INTEGER, zona INTEGER, secao INTEGER,
    numero INTEGER, votos INTEGER,
    PRIMARY KEY (ano, turno, cargo, numero, cd, zona, secao)
) WITHOUT ROWID;
-- Votos válidos de cada seção por cargo (brancos e nulos fora): o denominador
-- de "força no local" e do perfil, que sem isto somavam 1 milhão de linhas por pedido.
CREATE TABLE IF NOT EXISTS total_secao (
    ano INTEGER, turno INTEGER, cargo INTEGER, cd INTEGER, zona INTEGER, secao INTEGER, validos INTEGER,
    PRIMARY KEY (ano, turno, cargo, cd, zona, secao)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS secao (
    ano INTEGER, cd INTEGER, zona INTEGER, secao INTEGER,
    local INTEGER, aptos INTEGER, comparecimento INTEGER,
    PRIMARY KEY (ano, cd, zona, secao)
) WITHOUT ROWID;
-- O número do local só é único DENTRO da cidade: a zona 105 cobre Garuva, Itapoá
-- e Joinville, e as três têm um "local 1031". Com (ano, zona, local) de chave, um
-- sobrescrevia o outro.
CREATE TABLE IF NOT EXISTS local_votacao (
    ano INTEGER, cd INTEGER, zona INTEGER, local INTEGER,
    nome TEXT, endereco TEXT, bairro TEXT, lat REAL, lon REAL, eleitores INTEGER,
    PRIMARY KEY (ano, cd, zona, local)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS perfil_secao (
    ano INTEGER, cd INTEGER, zona INTEGER, secao INTEGER, eleitores INTEGER,
    fem INTEGER, masc INTEGER,
    i16_24 INTEGER, i25_34 INTEGER, i35_44 INTEGER, i45_59 INTEGER, i60 INTEGER,
    esc_fund INTEGER, esc_medio INTEGER, esc_sup INTEGER,
    branca INTEGER, preta_parda INTEGER, cor_inf INTEGER,
    PRIMARY KEY (ano, cd, zona, secao)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS importacao (
    fonte TEXT PRIMARY KEY, feito_em TEXT, linhas INTEGER, detalhe TEXT
);
"""


def conectar(leitura: bool = False) -> sqlite3.Connection:
    """`leitura=True` é para quem só consulta (o container da apuração é somente
    leitura); o importador abre sem ele e garante o esquema."""
    if leitura:
        con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True, timeout=30)
        con.row_factory = sqlite3.Row
        return con
    PASTA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BANCO, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def _registrar(con: sqlite3.Connection, fonte: str, linhas: int, detalhe: str = "") -> None:
    con.execute("INSERT OR REPLACE INTO importacao VALUES (?,?,?,?)",
                (fonte, datetime.now().astimezone().isoformat(timespec="seconds"), linhas, detalhe))
    con.commit()


def pessoa(nome: str, nascimento: str) -> str:
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().upper()
    s = " ".join(re.sub(r"[^A-Z ]", " ", s).split())
    return f"{s}|{nascimento or ''}" if s else ""


def _int(x) -> int:
    try:
        return int(str(x).replace(",", ".").split(".")[0])
    except (TypeError, ValueError):
        return 0


def _real(x) -> float | None:
    try:
        v = float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return v if v not in (-1.0, 0.0) else None


# ── ZIP do TSE em fluxo ─────────────────────────────────────────────────────
def _pedir(url: str, faixa: tuple[int, int] | None = None, metodo: str = "GET", prazo: int = 120):
    cab = dict(UA)
    if faixa:
        cab["Range"] = f"bytes={faixa[0]}-{faixa[1]}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=cab, method=metodo), timeout=prazo)


def _membro(url: str, sufixo: str) -> tuple[int, int, int]:
    """(início dos dados comprimidos, tamanho comprimido, método) do membro do ZIP."""
    with _pedir(url, metodo="HEAD", prazo=60) as r:
        tam = int(r.headers["Content-Length"])
    with _pedir(url, (max(0, tam - 70000), tam - 1)) as r:
        cauda = r.read()
    i = cauda.rfind(b"PK\x05\x06")
    if i < 0:
        raise RuntimeError("fim do ZIP não encontrado")
    cd_tam, cd_off = struct.unpack("<II", cauda[i + 12:i + 20])
    if cd_off == 0xFFFFFFFF:
        j = cauda.rfind(b"PK\x06\x06")
        cd_tam = struct.unpack("<Q", cauda[j + 40:j + 48])[0]
        cd_off = struct.unpack("<Q", cauda[j + 48:j + 56])[0]
    with _pedir(url, (cd_off, cd_off + cd_tam - 1)) as r:
        cd = r.read()
    p = 0
    while p < len(cd) - 4 and cd[p:p + 4] == b"PK\x01\x02":
        metodo = struct.unpack("<H", cd[p + 10:p + 12])[0]
        csz = struct.unpack("<I", cd[p + 20:p + 24])[0]
        nl, el, cl = struct.unpack("<HHH", cd[p + 28:p + 34])
        off = struct.unpack("<I", cd[p + 42:p + 46])[0]
        nome = cd[p + 46:p + 46 + nl].decode("latin-1")
        extra = cd[p + 46 + nl:p + 46 + nl + el]
        if csz == 0xFFFFFFFF or off == 0xFFFFFFFF:      # ZIP64: tamanhos no campo extra
            k = 0
            while k < len(extra) - 4:
                hid, hl = struct.unpack("<HH", extra[k:k + 4])
                if hid == 1:
                    vals, q = [], k + 4
                    while q < k + 4 + hl:
                        vals.append(struct.unpack("<Q", extra[q:q + 8])[0])
                        q += 8
                    usz_f = struct.unpack("<I", cd[p + 24:p + 28])[0] == 0xFFFFFFFF
                    idx = 1 if usz_f else 0
                    if csz == 0xFFFFFFFF:
                        csz = vals[idx]
                        idx += 1
                    if off == 0xFFFFFFFF:
                        off = vals[idx]
                    break
                k += 4 + hl
        if nome.upper().endswith(sufixo.upper()):
            with _pedir(url, (off, off + 29)) as r:
                loc = r.read()
            lnl, lel = struct.unpack("<HH", loc[26:30])
            return off + 30 + lnl + lel, csz, metodo
        p += 46 + nl + el + cl
    raise RuntimeError(f"membro *{sufixo} não encontrado em {url}")


def linhas_csv(url: str, sufixo: str):
    """Cada linha do CSV do membro, como dict, descomprimindo em fluxo."""
    ini, csz, metodo = _membro(url, sufixo)
    desc = zlib.decompressobj(-15) if metodo == 8 else None

    def texto():
        resto = ""
        with _pedir(url, (ini, ini + csz - 1), prazo=600) as r:
            while True:
                bloco = r.read(1 << 20)
                if not bloco:
                    break
                dado = desc.decompress(bloco) if desc else bloco
                parte = resto + dado.decode("latin-1")
                corte = parte.rfind("\n")
                if corte < 0:
                    resto = parte
                    continue
                yield from parte[:corte].split("\n")
                resto = parte[corte + 1:]
            if desc:
                resto += desc.flush().decode("latin-1")
        if resto:
            yield from resto.split("\n")

    leitor = csv.reader((l.rstrip("\r") for l in texto()), delimiter=";")
    cab = next(leitor)
    for valores in leitor:
        if len(valores) == len(cab):
            yield dict(zip(cab, valores))


# ── 2026: arquivos de resultado por município (o mesmo que o app do TSE lê) ──
def _baixar_json(url: str, destino: Path) -> bool:
    if destino.exists():
        return True
    for espera in (0, 5, 20):
        time.sleep(espera)
        try:
            with _pedir(url, prazo=30) as r:
                corpo = r.read()
            json.loads(corpo)
        except Exception:  # noqa: BLE001 — rede ou JSON truncado: tenta de novo
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(corpo))
        os.replace(tmp, destino)
        return True
    return False


def baixar_resultados_2026() -> dict:
    """Os 295 municípios × 5 cargos, guardados comprimidos (são o resultado oficial)."""
    cfg_dest = BRUTOS_2026 / "municipios.json.gz"
    _baixar_json(f"{RESULTADOS}/6259/config/mun-e006259-cm.json", cfg_dest)
    cfg = json.loads(gzip.decompress(cfg_dest.read_bytes()))
    sc = next(a for a in cfg["abr"] if a["cd"].lower() == "sc")
    pedidos = []
    for m in sc["mu"]:
        for cargo, (ele, c) in ARQ_2026.items():
            nome = f"sc{m['cd']}-{c}-e00{ele}-u.json"
            pedidos.append((f"{RESULTADOS}/{ele}/dados/sc/{nome}", BRUTOS_2026 / f"{c}" / f"{m['cd']}.json.gz"))
    # Estado inteiro de cada cargo (o arquivo que a apuração já usou).
    for cargo, (ele, c) in ARQ_2026.items():
        uf = "br" if cargo == 1 else "sc"
        pedidos.append((f"{RESULTADOS}/{ele}/dados/{uf}/{uf}-{c}-e00{ele}-u.json", BRUTOS_2026 / f"{c}" / f"{uf}.json.gz"))
    with ThreadPoolExecutor(max_workers=8) as ex:
        ok = list(ex.map(lambda p: _baixar_json(*p), pedidos))
    return {"pedidos": len(pedidos), "faltaram": ok.count(False), "municipios": sc["mu"]}


def _ler_bruto(c: str, onde: str) -> dict | None:
    arq = BRUTOS_2026 / c / f"{onde}.json.gz"
    try:
        return json.loads(gzip.decompress(arq.read_bytes()))
    except (OSError, ValueError):
        return None


def importar_resultados_2026(con: sqlite3.Connection) -> dict:
    baixado = baixar_resultados_2026()
    con.execute("DELETE FROM municipio")
    con.executemany("INSERT INTO municipio (cd, ibge, nome, uf) VALUES (?,?,?,'SC')",
                    [(_int(m["cd"]), _int(m.get("cdi")), m["nm"]) for m in baixado["municipios"]])
    for t in ("candidato", "partido", "voto_mun", "apuracao_mun"):
        con.execute(f"DELETE FROM {t} WHERE ano = 2026 AND turno = 1")
    linhas = 0
    for cargo, (ele, c) in ARQ_2026.items():
        estado = _ler_bruto(c, "br" if cargo == 1 else "sc")
        if not estado:
            raise RuntimeError(f"sem o arquivo estadual do cargo {cargo}")
        cands = []
        for a in estado["carg"][0]["agr"]:
            canon = eleicao.agremiacao_do_tse(a["nm"], [p["sg"] for p in a["par"]])
            for p in a["par"]:
                con.execute("INSERT OR REPLACE INTO partido VALUES (?,?,?,?,?,?)",
                            (2026, 1, cargo, _int(p["n"]), p["sg"], canon))
                for x in p["cand"]:
                    valido = (x.get("dvt") or "Válido").startswith("Válido")
                    st = x.get("st") or ""
                    cands.append((2026, 1, cargo, _int(x["n"]), x.get("sqcand"), x.get("nm"), x.get("nmu"),
                                  x.get("dt"), p["sg"], canon, st if valido else f"{st} ({x.get('dvt')})",
                                  1 if x.get("e") == "s" else 0, _int(x.get("vap")),
                                  pessoa(x.get("nm"), x.get("dt")), 1 if valido else 0))
        con.executemany("INSERT OR REPLACE INTO candidato VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        for m in baixado["municipios"]:
            d = _ler_bruto(c, m["cd"])
            if not d:
                continue
            cd = _int(m["cd"])
            e, v = d.get("e") or {}, d.get("v") or {}
            con.execute("INSERT OR REPLACE INTO apuracao_mun VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (2026, 1, cargo, cd, _int(e.get("te")), _int(e.get("c")), _int(e.get("a")),
                         _int(v.get("vv")), _int(v.get("vnom")), _int(v.get("vl")),
                         _int(v.get("vb")), _int(v.get("tvn"))))
            votos = []
            for a in d["carg"][0]["agr"]:
                for p in a["par"]:
                    if p.get("dvt") == "Anulado":
                        continue
                    leg = _int(p.get("tvtl"))
                    if leg and cargo in (6, 7):
                        votos.append((2026, 1, cargo, _int(p["n"]), cd, leg))
                    for x in p["cand"]:
                        n = _int(x.get("vap"))
                        if n:
                            votos.append((2026, 1, cargo, _int(x["n"]), cd, n))
            con.executemany("INSERT OR REPLACE INTO voto_mun VALUES (?,?,?,?,?,?)", votos)
            linhas += len(votos)
    _registrar(con, "resultados-2026", linhas, f"{baixado['pedidos']} arquivos, {baixado['faltaram']} faltaram")
    return {"linhas": linhas, "faltaram": baixado["faltaram"]}


# ── 2022: quem é quem e o voto por município ────────────────────────────────
_CARGO_DS = {"PRESIDENTE": 1, "GOVERNADOR": 3, "SENADOR": 5, "DEPUTADO FEDERAL": 6, "DEPUTADO ESTADUAL": 7}


def _agremiacao_2022(r: dict) -> str:
    """A legenda com que o candidato concorreu em 2022 (federação conta como uma)."""
    sg = (r.get("SG_PARTIDO") or "").upper().replace(" ", "")
    fed = (r.get("SG_FEDERACAO") or "").strip()
    if fed and not fed.startswith("#"):
        return fed.replace(" ", "")
    return sg


def importar_historico(con: sqlite3.Connection, ano: int = 2022) -> dict:
    nasc: dict[str, tuple[str, str]] = {}
    for r in linhas_csv(f"{ODSELE}consulta_cand/consulta_cand_{ano}.zip", "_SC.csv"):
        nasc[r["SQ_CANDIDATO"]] = (r.get("NM_CANDIDATO") or "", r.get("DT_NASCIMENTO") or "")
    pres = {}
    for r in linhas_csv(f"{ODSELE}consulta_cand/consulta_cand_{ano}.zip", "_BRASIL.csv"):
        if (r.get("DS_CARGO") or "").upper() == "PRESIDENTE":
            pres[r["SQ_CANDIDATO"]] = (r.get("NM_CANDIDATO") or "", r.get("DT_NASCIMENTO") or "")
    nasc.update(pres)
    for t in ("candidato", "partido", "voto_mun", "apuracao_mun"):
        con.execute(f"DELETE FROM {t} WHERE ano = ?", (ano,))
    cands: dict[tuple, list] = {}
    votos: dict[tuple, int] = {}
    for r in linhas_csv(f"{ODSELE}votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip", "_SC.csv"):
        cargo = _CARGO_DS.get((r.get("DS_CARGO") or "").upper())
        if not cargo:
            continue
        turno, n, cd = _int(r["NR_TURNO"]), _int(r["NR_CANDIDATO"]), _int(r["CD_MUNICIPIO"])
        k = (ano, turno, cargo, n)
        if k not in cands:
            nome, nascimento = nasc.get(r["SQ_CANDIDATO"], (r.get("NM_CANDIDATO") or "", ""))
            sit = (r.get("DS_SIT_TOT_TURNO") or "").strip()
            cands[k] = [ano, turno, cargo, n, r["SQ_CANDIDATO"], nome, r.get("NM_URNA_CANDIDATO"), nascimento,
                        (r.get("SG_PARTIDO") or "").upper().replace(" ", ""), _agremiacao_2022(r),
                        sit.capitalize().replace(" qp", " QP"), 1 if sit.upper().startswith("ELEITO") else 0, 0,
                        pessoa(nome, nascimento),
                        1 if (r.get("NM_TIPO_DESTINACAO_VOTOS") or "Válido").startswith("Válido") else 0]
        v = _int(r.get("QT_VOTOS_NOMINAIS"))
        cands[k][12] += v
        if v:
            votos[(ano, turno, cargo, n, cd)] = votos.get((ano, turno, cargo, n, cd), 0) + v
    con.executemany("INSERT OR REPLACE INTO candidato VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(cands.values()))
    # Voto de legenda, por partido e município.
    for r in linhas_csv(f"{ODSELE}votacao_partido_munzona/votacao_partido_munzona_{ano}.zip", "_SC.csv"):
        cargo = _CARGO_DS.get((r.get("DS_CARGO") or "").upper())
        if cargo not in (6, 7):
            continue
        con.execute("INSERT OR REPLACE INTO partido VALUES (?,?,?,?,?,?)",
                    (ano, _int(r["NR_TURNO"]), cargo, _int(r["NR_PARTIDO"]),
                     (r.get("SG_PARTIDO") or "").upper().replace(" ", ""), _agremiacao_2022(r)))
        v = _int(r.get("QT_TOTAL_VOTOS_LEG_VALIDOS") or r.get("QT_VOTOS_LEGENDA_VALIDOS"))
        if v:
            k = (ano, _int(r["NR_TURNO"]), cargo, _int(r["NR_PARTIDO"]), _int(r["CD_MUNICIPIO"]))
            votos[k] = votos.get(k, 0) + v
    con.executemany("INSERT OR REPLACE INTO voto_mun VALUES (?,?,?,?,?,?)",
                    [(*k, v) for k, v in votos.items() if v])
    apur: dict[tuple, list[int]] = {}
    for r in linhas_csv(f"{ODSELE}detalhe_votacao_munzona/detalhe_votacao_munzona_{ano}.zip", "_SC.csv"):
        cargo = _CARGO_DS.get((r.get("DS_CARGO") or "").upper())
        if not cargo:
            continue
        k = (ano, _int(r["NR_TURNO"]), cargo, _int(r["CD_MUNICIPIO"]))
        soma = apur.setdefault(k, [0] * 8)
        for i, col in enumerate(("QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_TOTAL_VOTOS_VALIDOS",
                                 "QT_VOTOS_NOMINAIS_VALIDOS", "QT_TOTAL_VOTOS_LEG_VALIDOS", "QT_VOTOS_BRANCOS",
                                 "QT_TOTAL_VOTOS_NULOS")):
            soma[i] += _int(r.get(col))
    con.executemany("INSERT OR REPLACE INTO apuracao_mun VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(*k, *v) for k, v in apur.items()])
    _registrar(con, f"historico-{ano}", len(votos), f"{len(cands)} candidaturas")
    return {"candidatos": len(cands), "votos_mun": len(votos)}


# ── por seção ───────────────────────────────────────────────────────────────
def _gravar_secoes(con: sqlite3.Connection, ano: int, turnos: set[int] | None, linhas, fonte: str) -> int:
    """Grava voto por seção (e a seção, com aptos/comparecimento quando houver)."""
    con.execute("DELETE FROM voto_secao WHERE ano = ?", (ano,))
    lote, n, secoes, nomes_locais = [], 0, {}, {}
    for r in linhas:
        turno = _int(r.get("NR_TURNO") or 1)
        if turnos and turno not in turnos:
            continue
        cargo = _int(r.get("CD_CARGO") or r.get("CD_CARGO_PERGUNTA"))
        if cargo not in CARGOS:
            continue
        cd, zona, sec = _int(r["CD_MUNICIPIO"]), _int(r["NR_ZONA"]), _int(r["NR_SECAO"])
        votos = _int(r.get("QT_VOTOS"))
        if not votos:
            continue
        tipo = (r.get("DS_TIPO_VOTAVEL") or "").upper()
        numero = (BRANCO if tipo == "BRANCO" else NULO if tipo == "NULO"
                  else ANULADO if tipo.startswith("ANULADO") else _int(r["NR_VOTAVEL"]))
        lote.append((ano, turno, cargo, cd, zona, sec, numero, votos))
        chave = (cd, zona, sec)
        if chave not in secoes:
            secoes[chave] = (_int(r.get("NR_LOCAL_VOTACAO")), _int(r.get("QT_APTOS")) or None,
                             _int(r.get("QT_COMPARECIMENTO")) or None)
            if r.get("NM_LOCAL_VOTACAO"):
                nomes_locais[(cd, zona, _int(r.get("NR_LOCAL_VOTACAO")))] = (r["NM_LOCAL_VOTACAO"],
                                                                             r.get("DS_LOCAL_VOTACAO_ENDERECO"))
        if len(lote) >= 50000:
            con.executemany("INSERT OR REPLACE INTO voto_secao VALUES (?,?,?,?,?,?,?,?)", lote)
            n += len(lote)
            lote = []
    if lote:
        con.executemany("INSERT OR REPLACE INTO voto_secao VALUES (?,?,?,?,?,?,?,?)", lote)
        n += len(lote)
    con.execute("DELETE FROM total_secao WHERE ano = ?", (ano,))
    con.execute(f"""INSERT INTO total_secao
                    SELECT ano, turno, cargo, cd, zona, secao, SUM(votos) FROM voto_secao
                     WHERE ano = ? AND numero NOT IN ({BRANCO}, {NULO}, {ANULADO})
                     GROUP BY ano, turno, cargo, cd, zona, secao""", (ano,))
    for (cd, zona, sec), (local, aptos, comp) in secoes.items():
        con.execute("""INSERT INTO secao (ano, cd, zona, secao, local, aptos, comparecimento) VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(ano, cd, zona, secao) DO UPDATE SET local = excluded.local,
                         aptos = COALESCE(excluded.aptos, secao.aptos),
                         comparecimento = COALESCE(excluded.comparecimento, secao.comparecimento)""",
                    (ano, cd, zona, sec, local, aptos, comp))
    completar_locais(con, ano, nomes_locais)
    _registrar(con, fonte, n, f"{len(secoes)} seções")
    return n


def _nome_local(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().upper()
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", s).split())


def completar_locais(con: sqlite3.Connection, ano: int, nomes: dict | None = None) -> int:
    """Local de votação que a votação cita e o cadastro do ano não traz.

    Aconteceu em 2022: a zona 105 de Joinville tem 10 escolas na votação por
    seção e nenhuma no cadastro de locais. O nome vem da própria votação; o
    bairro e as coordenadas, da MESMA escola (mesmo nome, mesma cidade) no
    cadastro de outro ano — o número da zona muda, a escola não.
    """
    for (cd, zona, local), (nome, end) in (nomes or {}).items():
        con.execute("INSERT OR IGNORE INTO local_votacao (ano, cd, zona, local, nome, endereco, bairro) VALUES (?,?,?,?,?,?,'')",
                    (ano, cd, zona, local, nome, end))
    outros: dict[tuple[int, str], dict] = {}
    for r in con.execute("SELECT * FROM local_votacao WHERE ano != ? AND bairro != '' ORDER BY ano", (ano,)):
        outros[(r["cd"], _nome_local(r["nome"]))] = dict(r)
    n = 0
    for r in con.execute("SELECT * FROM local_votacao WHERE ano = ? AND (bairro = '' OR lat IS NULL)", (ano,)).fetchall():
        o = outros.get((r["cd"], _nome_local(r["nome"])))
        if o:
            con.execute("""UPDATE local_votacao SET bairro = CASE WHEN bairro = '' THEN ? ELSE bairro END,
                                  lat = COALESCE(lat, ?), lon = COALESCE(lon, ?)
                            WHERE ano = ? AND cd = ? AND zona = ? AND local = ?""",
                        (o["bairro"], o["lat"], o["lon"], ano, r["cd"], r["zona"], r["local"]))
            n += 1
    con.commit()
    return n


def nomes_locais_2022(con: sqlite3.Connection) -> dict:
    """Só o nome dos locais da votação por seção de 2022 (para completar o cadastro)."""
    nomes = {}
    for r in linhas_csv(f"{ODSELE}votacao_secao/votacao_secao_2022_SC.zip", "_SC.csv"):
        k = (_int(r["CD_MUNICIPIO"]), _int(r["NR_ZONA"]), _int(r["NR_LOCAL_VOTACAO"]))
        if k not in nomes:
            nomes[k] = (r.get("NM_LOCAL_VOTACAO"), r.get("DS_LOCAL_VOTACAO_ENDERECO"))
    return {"completados": completar_locais(con, 2022, nomes), "locais_na_votacao": len(nomes)}


def importar_secoes_2022(con: sqlite3.Connection) -> dict:
    n = _gravar_secoes(con, 2022, None,
                       linhas_csv(f"{ODSELE}votacao_secao/votacao_secao_2022_SC.zip", "_SC.csv"), "secoes-2022")
    return {"linhas": n}


def _url_boletins(ano: int = 2026, turno: int = 1) -> str | None:
    """O ZIP do boletim de urna de SC, se o TSE já publicou (pelo catálogo de dados abertos)."""
    for q in (f"boletim de urna {ano}", f"resultados-{ano}-boletim-de-urna"):
        try:
            with _pedir(f"{CKAN}package_search?q={urllib.request.quote(q)}&rows=20", prazo=40) as r:
                pacotes = json.loads(r.read())["result"]["results"]
        except Exception:  # noqa: BLE001
            continue
        for p in pacotes:
            if str(ano) not in p["name"] or "boletim" not in p["name"]:
                continue
            for rec in p.get("resources", []):
                u = rec.get("url") or ""
                if re.search(rf"bweb_{turno}t_SC_\d+\.zip$", u):
                    return u
    return None


def importar_boletins(con: sqlite3.Connection, ano: int = 2026) -> dict:
    """Voto por seção de 2026 a partir do boletim de urna (bweb), quando sair."""
    feito = con.execute("SELECT detalhe FROM importacao WHERE fonte = ?", (f"secoes-{ano}",)).fetchone()
    url = _url_boletins(ano)
    if not url:
        return {"publicado": False}
    if feito and feito["detalhe"] and url in feito["detalhe"]:
        return {"publicado": True, "ja_importado": True}
    n = _gravar_secoes(con, ano, {1}, linhas_csv(url, ".csv"), f"secoes-{ano}")
    con.execute("UPDATE importacao SET detalhe = detalhe || ' · ' || ? WHERE fonte = ?", (url, f"secoes-{ano}"))
    con.commit()
    return {"publicado": True, "linhas": n, "url": url}


def importar_locais(con: sqlite3.Connection, ano: int) -> dict:
    url = f"{ODSELE}eleitorado_locais_votacao/eleitorado_local_votacao_{ano}.zip"
    sufixo = "_SC.csv" if ano >= 2026 else f"_{ano}.csv"
    con.execute("DELETE FROM local_votacao WHERE ano = ?", (ano,))
    locais: dict[tuple, list] = {}
    secoes = []
    for r in linhas_csv(url, sufixo):
        if (r.get("SG_UF") or "").upper() != "SC" or _int(r.get("NR_TURNO") or 1) != 1:
            continue
        zona, loc, cd = _int(r["NR_ZONA"]), _int(r["NR_LOCAL_VOTACAO"]), _int(r["CD_MUNICIPIO"])
        el = _int(r.get("QT_ELEITOR_SECAO"))
        k = (ano, cd, zona, loc)
        if k not in locais:
            locais[k] = [ano, cd, zona, loc, r.get("NM_LOCAL_VOTACAO"), r.get("DS_ENDERECO"),
                         (r.get("NM_BAIRRO") or "").strip().upper(), _real(r.get("NR_LATITUDE")),
                         _real(r.get("NR_LONGITUDE")), 0]
        locais[k][9] += el
        secoes.append((ano, cd, zona, _int(r["NR_SECAO"]), loc, el or None))
    con.executemany("INSERT OR REPLACE INTO local_votacao VALUES (?,?,?,?,?,?,?,?,?,?)", list(locais.values()))
    con.executemany("""INSERT INTO secao (ano, cd, zona, secao, local, aptos) VALUES (?,?,?,?,?,?)
                       ON CONFLICT(ano, cd, zona, secao) DO UPDATE SET local = excluded.local,
                         aptos = COALESCE(secao.aptos, excluded.aptos)""", secoes)
    _registrar(con, f"locais-{ano}", len(locais), f"{len(secoes)} seções")
    return {"locais": len(locais), "secoes": len(secoes)}


_IDADE = {"i16_24": (16, 24), "i25_34": (25, 34), "i35_44": (35, 44), "i45_59": (45, 59), "i60": (60, 200)}


def _faixa_idade(ds: str) -> str | None:
    nums = [int(x) for x in re.findall(r"\d+", ds or "")]
    if not nums:
        return None
    ini = nums[0]
    for col, (a, b) in _IDADE.items():
        if a <= ini <= b:
            return col
    return None


def _escolaridade(ds: str) -> str | None:
    ds = (ds or "").upper()
    if "SUPERIOR" in ds:
        return "esc_sup"
    if "MÉDIO" in ds or "MEDIO" in ds:
        return "esc_medio"
    if ds and "NÃO INFORMADO" not in ds:
        return "esc_fund"            # analfabeto, lê e escreve, fundamental
    return None


def importar_perfil(con: sqlite3.Connection, ano: int = 2026) -> dict:
    url = f"{ODSELE}perfil_eleitor_secao/perfil_eleitor_secao_{ano}_SC.zip"
    cols = ["eleitores", "fem", "masc", *_IDADE, "esc_fund", "esc_medio", "esc_sup", "branca", "preta_parda", "cor_inf"]
    soma: dict[tuple, dict[str, int]] = {}
    for r in linhas_csv(url, "_SC.csv"):
        k = (ano, _int(r["CD_MUNICIPIO"]), _int(r["NR_ZONA"]), _int(r["NR_SECAO"]))
        q = _int(r.get("QT_ELEITORES") or r.get("QT_ELEITORES_PERFIL"))
        if not q:
            continue
        d = soma.get(k)
        if d is None:
            d = soma[k] = dict.fromkeys(cols, 0)
        d["eleitores"] += q
        g = (r.get("DS_GENERO") or "").upper()
        if g.startswith("FEM"):
            d["fem"] += q
        elif g.startswith("MASC"):
            d["masc"] += q
        fi = _faixa_idade(r.get("DS_FAIXA_ETARIA"))
        if fi:
            d[fi] += q
        es = _escolaridade(r.get("DS_GRAU_ESCOLARIDADE"))
        if es:
            d[es] += q
        cor = (r.get("DS_RACA_COR") or "").upper()
        if cor.startswith("BRANCA"):
            d["branca"] += q
        elif cor.startswith("PRETA") or cor.startswith("PARDA"):
            d["preta_parda"] += q
        if cor and "NÃO INFORMADO" not in cor:
            d["cor_inf"] += q
    con.execute("DELETE FROM perfil_secao WHERE ano = ?", (ano,))
    con.executemany(f"INSERT INTO perfil_secao VALUES ({','.join('?' * (4 + len(cols)))})",
                    [(*k, *(d[c] for c in cols)) for k, d in soma.items()])
    _registrar(con, f"perfil-{ano}", len(soma))
    return {"secoes": len(soma)}


def situacao(con: sqlite3.Connection | None = None) -> list[dict]:
    con = con or conectar()
    return [dict(r) for r in con.execute("SELECT * FROM importacao ORDER BY fonte")]


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Microdados eleitorais de SC → politicos/data/eleicoes.db")
    ap.add_argument("passo", choices=["resultados", "historico", "secoes", "locais", "perfil", "boletins",
                                      "nomes-locais", "tudo", "situacao"])
    ap.add_argument("ano", nargs="?", type=int)
    a = ap.parse_args(argv)
    con = conectar()
    t0 = time.monotonic()

    def rodar(nome, fn, *args):
        t = time.monotonic()
        r = fn(con, *args)
        con.commit()
        print(f"[{datetime.now():%H:%M:%S}] {nome}: {r} ({time.monotonic() - t:.0f} s)", flush=True)

    if a.passo in ("resultados", "tudo"):
        rodar("resultados 2026", importar_resultados_2026)
    if a.passo in ("historico", "tudo"):
        rodar("histórico 2022", importar_historico, a.ano or 2022)
    if a.passo == "secoes" or a.passo == "tudo":
        rodar("seções 2022", importar_secoes_2022)
    if a.passo in ("locais", "tudo"):
        for ano in ([a.ano] if a.ano else [2022, 2026]):
            rodar(f"locais {ano}", importar_locais, ano)
    if a.passo in ("perfil", "tudo"):
        rodar(f"perfil {a.ano or 2026}", importar_perfil, a.ano or 2026)
    if a.passo in ("boletins", "tudo"):
        rodar("boletins 2026", importar_boletins, a.ano or 2026)
    if a.passo == "nomes-locais":
        rodar("nomes dos locais 2022", nomes_locais_2022)
    if a.passo == "situacao":
        for r in situacao(con):
            print(r)
    if a.passo == "tudo":
        print(f"tudo em {time.monotonic() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
