"""Banco do app Políticos.

Independente do resto do site: nada aqui importa de `noticias/` ou `doe/`.
Hoje é um banco só (`politicos.db`), compartilhado pelo time. A divisão por
usuário está prevista mas NÃO implementada — ver `DECISOES.md`. Por isso toda
função pública já recebe o caminho do banco por parâmetro opcional, para o dia
em que virar `data/{user}.db` sem reescrever chamada.
"""
from __future__ import annotations

import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parent
DB_PATH = DIR / "politicos.db"
PICS_DIR = DIR.parent / "static" / "politicos_pics"

BRT = timezone(timedelta(hours=-3))

# Maturação: post só é contado depois que o engajamento assentou. 14 dias é o
# PADRÃO, não mais uma constante: na v2 o valor é configurável na tela
# (`v2_config.maturacao_dias`). Mudar não recoleta nada — a maturação é um filtro
# de LEITURA, aplicado na hora de calcular. Baixar para 3 dias faz aparecer o que
# foi publicado esta semana, com engajamento ainda subindo; subir para 30 deixa o
# número mais estável e a tela mais atrasada.
MATURACAO_PADRAO = 14
MATURACAO_MIN = 0
MATURACAO_MAX = 90

# Mantido para quem importa o nome antigo; prefira `maturacao_dias(con)`.
MATURACAO_DIAS = MATURACAO_PADRAO

SCHEMA = """
CREATE TABLE IF NOT EXISTS perfis (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    nome          TEXT,
    nome_completo TEXT,
    partido       TEXT,
    numero        TEXT,
    cargo         TEXT,
    sq_candidato  TEXT,
    ocupacao      TEXT,
    faixa         INTEGER DEFAULT 5,
    acompanhar    INTEGER DEFAULT 1,
    seguidores    INTEGER,
    total_posts   INTEGER,
    verificado    INTEGER DEFAULT 0,
    -- Descarte da fila de revisão é reversível de propósito: apagar a linha
    -- fazia o import semanal recriar o candidato na segunda seguinte, e o
    -- trabalho de quem revisou se perdia toda semana.
    descartado_em TEXT,
    criado_em     TEXT
);
CREATE INDEX IF NOT EXISTS ix_perfis_partido ON perfis(partido);
CREATE INDEX IF NOT EXISTS ix_perfis_acomp   ON perfis(acompanhar, faixa);

CREATE TABLE IF NOT EXISTS snapshots (
    perfil_id   INTEGER NOT NULL,
    semana      TEXT    NOT NULL,
    seguidores  INTEGER,
    seguindo    INTEGER,
    total_posts INTEGER,
    coletado_em TEXT,
    PRIMARY KEY (perfil_id, semana)
);

CREATE TABLE IF NOT EXISTS posts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    perfil_id         INTEGER NOT NULL,
    shortcode         TEXT    UNIQUE,
    tipo              TEXT,
    publicado_em      TEXT    NOT NULL,
    legenda           TEXT,
    hashtags          TEXT,
    mencoes           TEXT,
    curtidas          INTEGER DEFAULT 0,
    comentarios       INTEGER DEFAULT 0,
    visualizacoes     INTEGER DEFAULT 0,
    reproducoes       INTEGER DEFAULT 0,
    compartilhamentos INTEGER DEFAULT 0,
    salvamentos       INTEGER DEFAULT 0,
    duracao_seg       REAL,
    parceria_paga     INTEGER DEFAULT 0,
    url               TEXT,
    thumb_url         TEXT,
    video_url         TEXT,
    origem            TEXT,
    coletado_em       TEXT
);
CREATE INDEX IF NOT EXISTS ix_posts_perfil ON posts(perfil_id, publicado_em);
CREATE INDEX IF NOT EXISTS ix_posts_data   ON posts(publicado_em);

-- Livro-razão da coleta. Existe por um motivo só: NUNCA pagar duas vezes pela
-- mesma janela. Toda coleta consulta isto antes de chamar a Apify.
CREATE TABLE IF NOT EXISTS janelas (
    perfil_id   INTEGER NOT NULL,
    inicio      TEXT    NOT NULL,
    fim         TEXT    NOT NULL,
    posts       INTEGER DEFAULT 0,
    custo_usd   REAL    DEFAULT 0,
    run_id      TEXT,
    coletado_em TEXT,
    PRIMARY KEY (perfil_id, inicio, fim)
);

CREATE TABLE IF NOT EXISTS gastos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    quando    TEXT    NOT NULL,
    tipo      TEXT    NOT NULL,
    itens     INTEGER DEFAULT 0,
    custo_usd REAL    DEFAULT 0,
    run_id    TEXT,
    detalhe   TEXT
);
CREATE INDEX IF NOT EXISTS ix_gastos_quando ON gastos(quando);

-- Base do simulador de cadeiras: votação real por legenda.
CREATE TABLE IF NOT EXISTS eleicao_votos (
    ano      INTEGER NOT NULL,
    cargo    TEXT    NOT NULL,
    legenda  TEXT    NOT NULL,
    votos    INTEGER NOT NULL,
    cadeiras INTEGER,
    PRIMARY KEY (ano, cargo, legenda)
);

-- ── tabelas da v2 ────────────────────────────────────────────────────────────
-- Tudo com prefixo v2_. O banco é COMPARTILHADO com a v1, que continua no ar
-- como ponto de retorno: a v2 só acrescenta, nunca altera o que a v1 lê.

CREATE TABLE IF NOT EXISTS v2_config (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS v2_favoritos (
    perfil_id INTEGER PRIMARY KEY,
    criado_em TEXT
);

CREATE TABLE IF NOT EXISTS v2_grupos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nome      TEXT NOT NULL UNIQUE,
    cor       TEXT,
    criado_em TEXT
);
CREATE TABLE IF NOT EXISTS v2_grupo_perfis (
    grupo_id  INTEGER NOT NULL,
    perfil_id INTEGER NOT NULL,
    PRIMARY KEY (grupo_id, perfil_id)
);

-- Votação do próprio candidato em eleições anteriores. É o melhor previsor que
-- existe para a nominata, e é de graça: vem dos dados abertos do TSE.
CREATE TABLE IF NOT EXISTS v2_votos_candidato (
    perfil_id INTEGER NOT NULL,
    ano       INTEGER NOT NULL,
    cargo     TEXT    NOT NULL,
    votos     INTEGER,
    situacao  TEXT,
    nome_urna TEXT,
    partido   TEXT,
    municipio TEXT,
    PRIMARY KEY (perfil_id, ano, cargo)
);
CREATE INDEX IF NOT EXISTS ix_v2votos_perfil ON v2_votos_candidato(perfil_id);

-- Pauta de cada post, classificada por IA barata. Hashtag foi descartada em
-- 10/08/2026 (quase ninguém usa; o que sobrava era geografia). Um post só se
-- classifica UMA vez — a chave primária é o que impede pagar de novo.
CREATE TABLE IF NOT EXISTS v2_post_tema (
    post_id INTEGER PRIMARY KEY,
    tema    TEXT NOT NULL,
    modelo  TEXT,
    quando  TEXT
);
CREATE INDEX IF NOT EXISTS ix_v2tema ON v2_post_tema(tema);

-- Recortes do cadastro do TSE que a v1 não importou.
--
-- `cpf_hash` é SHA-256 do CPF, nunca o número: serve para casar o mesmo
-- candidato entre arquivos de eleições diferentes (o SQ_CANDIDATO muda a cada
-- pleito) sem que o banco passe a guardar dado pessoal em claro.
CREATE TABLE IF NOT EXISTS v2_perfil_extra (
    perfil_id       INTEGER PRIMARY KEY,
    genero          TEXT,
    cor_raca        TEXT,
    grau_instrucao  TEXT,
    federacao       TEXT,
    coligacao       TEXT,
    nascimento      TEXT,
    cnpj_campanha   TEXT,
    cpf_hash        TEXT
);

-- Cenários do simulador: as premissas são do usuário, uma linha por partido.
CREATE TABLE IF NOT EXISTS cenarios (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nome      TEXT NOT NULL,
    criado_em TEXT,
    nota      TEXT
);
CREATE TABLE IF NOT EXISTS cenario_ajustes (
    cenario_id INTEGER NOT NULL,
    partido    TEXT    NOT NULL,
    ajuste_pct REAL    DEFAULT 0,
    PRIMARY KEY (cenario_id, partido)
);

-- Receita de campanha declarada ao TSE em eleições passadas (uma linha por
-- candidato/ano). Cruzada com v2_votos_candidato dá o custo por voto histórico
-- que alimenta o cenário "Receita" do simulador.
CREATE TABLE IF NOT EXISTS v2_financeiro (
    perfil_id     INTEGER NOT NULL,
    ano           INTEGER NOT NULL,
    receita       REAL,
    fonte         TEXT,
    nome_urna     TEXT,
    atualizado_em TEXT,
    PRIMARY KEY (perfil_id, ano)
);

-- Receita de 2026, fotografada toda semana: o valor sobe durante a campanha
-- (doações via IDC), e a série é o que permite dizer "arrecadou +X na semana".
CREATE TABLE IF NOT EXISTS v2_receitas_semana (
    perfil_id         INTEGER NOT NULL,
    semana            TEXT    NOT NULL,
    receita_acumulada REAL,
    doacoes           INTEGER,
    fonte             TEXT,
    coletado_em       TEXT,
    PRIMARY KEY (perfil_id, semana)
);

-- Quantos candidatos cada legenda registrou no TSE, atualizado no job semanal.
-- É o denominador honesto de tudo que se diz por legenda: acompanhar 33 de 47
-- candidatos do PL e 2 de 47 do PSB não sustentam a mesma afirmação.
CREATE TABLE IF NOT EXISTS v2_cadastro_legenda (
    legenda       TEXT PRIMARY KEY,
    candidatos    INTEGER,
    atualizado_em TEXT
);

-- Quem mexeu na fila de revisão. A fila decide quem entra na coleta paga e
-- quem some da tela; sem registro, um descarte errado é indistinguível de um
-- candidato que o TSE nunca publicou.
CREATE TABLE IF NOT EXISTS v2_auditoria (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    quando    TEXT NOT NULL,
    usuario   TEXT,
    acao      TEXT NOT NULL,
    perfil_id INTEGER,
    detalhe   TEXT
);
CREATE INDEX IF NOT EXISTS ix_v2auditoria ON v2_auditoria(quando);
"""

# Colunas acrescentadas depois que o banco já existia. `CREATE TABLE IF NOT
# EXISTS` não altera tabela criada, então quem tem banco antigo precisa disto.
MIGRACOES = [
    ("perfis", "descartado_em", "TEXT"),
    ("v2_perfil_extra", "cnpj_campanha", "TEXT"),
    ("v2_perfil_extra", "cpf_hash", "TEXT"),
]

# Índices sobre colunas migradas: só podem ser criados depois do ALTER TABLE.
INDICES = """
CREATE INDEX IF NOT EXISTS ix_v2extra_cpf ON v2_perfil_extra(cpf_hash);
CREATE INDEX IF NOT EXISTS ix_perfis_fila ON perfis(acompanhar, descartado_em);
"""


def conectar(caminho: Path | str | None = None) -> sqlite3.Connection:
    # Na apuração (caue) o politicos.db é uma CÓPIA congelada do V2 em 30/10/2026,
    # num container somente leitura: abre imutável, sem WAL nem escrita.
    con = sqlite3.connect(f"file:{caminho or DB_PATH}?immutable=1", uri=True, timeout=30,
                          check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def migrar(con: sqlite3.Connection) -> list[str]:
    """Acrescenta colunas novas em banco que já existia. Idempotente."""
    feitas = []
    for tabela, coluna, tipo in MIGRACOES:
        existentes = {r[1] for r in con.execute(f"PRAGMA table_info({tabela})")}
        if existentes and coluna not in existentes:
            con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            feitas.append(f"{tabela}.{coluna}")
    return feitas


def criar(caminho: Path | str | None = None) -> None:
    con = conectar(caminho)
    con.executescript(SCHEMA)
    migrar(con)
    con.executescript(INDICES)
    con.commit()
    con.close()


def auditar(con: sqlite3.Connection, usuario: str | None, acao: str,
            perfil_id: int | None = None, detalhe: str = "") -> None:
    con.execute(
        """INSERT INTO v2_auditoria (quando, usuario, acao, perfil_id, detalhe)
           VALUES (?,?,?,?,?)""",
        (agora(), usuario, acao, perfil_id, detalhe))


# ── datas ────────────────────────────────────────────────────────────────────

def segunda(d: date) -> str:
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")


def semana_atual() -> str:
    return segunda(datetime.now(BRT).date())


def limite_maturacao(con=None) -> date:
    """Último dia cujo engajamento já assentou (usa a config quando há conexão)."""
    dias = maturacao_dias(con) if con is not None else MATURACAO_PADRAO
    return datetime.now(BRT).date() - timedelta(days=dias)


def agora() -> str:
    return datetime.now(BRT).isoformat(timespec="seconds")


# ── perfis ───────────────────────────────────────────────────────────────────

def upsert_perfil(con: sqlite3.Connection, username: str, **campos) -> int:
    username = username.strip().lstrip("@").lower()
    row = con.execute("SELECT id FROM perfis WHERE username=?", (username,)).fetchone()
    if row:
        if campos:
            sets = ", ".join(f"{k}=?" for k in campos)
            con.execute(f"UPDATE perfis SET {sets} WHERE id=?",
                        (*campos.values(), row["id"]))
        return row["id"]
    cols = ["username", "criado_em", *campos.keys()]
    vals = [username, agora(), *campos.values()]
    cur = con.execute(
        f"INSERT INTO perfis ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        vals,
    )
    return cur.lastrowid


def perfis_para_acompanhar(con: sqlite3.Connection, faixa_max: int = 5) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM perfis WHERE acompanhar=1 AND faixa<=? ORDER BY faixa, seguidores DESC",
        (faixa_max,),
    ).fetchall()


# ── livro-razão ──────────────────────────────────────────────────────────────

def janela_coletada(con: sqlite3.Connection, perfil_id: int, inicio: str, fim: str) -> bool:
    return con.execute(
        "SELECT 1 FROM janelas WHERE perfil_id=? AND inicio<=? AND fim>=?",
        (perfil_id, inicio, fim),
    ).fetchone() is not None


def registrar_janela(con: sqlite3.Connection, perfil_id: int, inicio: str, fim: str,
                     posts: int, custo: float, run_id: str | None) -> None:
    con.execute(
        """INSERT OR REPLACE INTO janelas
           (perfil_id, inicio, fim, posts, custo_usd, run_id, coletado_em)
           VALUES (?,?,?,?,?,?,?)""",
        (perfil_id, inicio, fim, posts, custo, run_id, agora()),
    )


def registrar_gasto(con: sqlite3.Connection, tipo: str, itens: int, custo: float,
                    run_id: str | None = None, detalhe: str = "") -> None:
    con.execute(
        "INSERT INTO gastos (quando, tipo, itens, custo_usd, run_id, detalhe) VALUES (?,?,?,?,?,?)",
        (agora(), tipo, itens, custo, run_id, detalhe),
    )


def gasto_no_ciclo(con: sqlite3.Connection, inicio_ciclo: str) -> float:
    r = con.execute("SELECT COALESCE(SUM(custo_usd),0) s FROM gastos WHERE quando>=?",
                    (inicio_ciclo,)).fetchone()
    return float(r["s"] or 0)


# ── configuração da v2 ───────────────────────────────────────────────────────

def get_config(con, chave: str, padrao: str | None = None) -> str | None:
    r = con.execute("SELECT valor FROM v2_config WHERE chave=?", (chave,)).fetchone()
    return r["valor"] if r else padrao


def set_config(con, chave: str, valor: str) -> None:
    con.execute("INSERT OR REPLACE INTO v2_config (chave, valor) VALUES (?,?)",
                (chave, str(valor)))


def maturacao_dias(con) -> int:
    """Dias que um post precisa ter para entrar nas contas.

    Configurável na tela. Não recoleta nada: é filtro de leitura.
    """
    try:
        v = int(get_config(con, "maturacao_dias", str(MATURACAO_PADRAO)))
    except (TypeError, ValueError):
        return MATURACAO_PADRAO
    return max(MATURACAO_MIN, min(MATURACAO_MAX, v))


def corte_maturacao(con) -> str:
    from datetime import date as _date
    return (_date.today() - timedelta(days=maturacao_dias(con))).strftime("%Y-%m-%d")


# ── manutenção ───────────────────────────────────────────────────────────────

def limpar_thumbs(dias: int = 90, max_mb: int = 500) -> dict:
    """Remove thumbnails antigas para não encher o SD card do Pi.

    Critérios de remoção (OR):
    1. Arquivo mais antigo que `dias` dias.
    2. Diretório acima de `max_mb` MB — remove os mais antigos primeiro.
    """
    import os
    thumbs = DIR / "thumbs"
    if not thumbs.exists():
        return {"removidos": 0, "motivo": "diretório não existe"}

    arquivos = []
    for f in thumbs.glob("*.jpg"):
        try:
            st = f.stat()
            arquivos.append((f, st.st_mtime, st.st_size))
        except OSError:
            continue

    if not arquivos:
        return {"removidos": 0, "motivo": "nenhum arquivo"}

    arquivos.sort(key=lambda x: x[1])  # mais antigos primeiro
    corte_ts = time.time() - dias * 86400
    removidos = 0

    # 1. Por idade
    for f, mtime, size in arquivos:
        if mtime < corte_ts:
            f.unlink(missing_ok=True)
            removidos += 1

    # 2. Por tamanho total
    restantes = [(f, mtime, size) for f, mtime, size in arquivos
                 if mtime >= corte_ts]
    total_bytes = sum(s for _, _, s in restantes)
    limite = max_mb * 1024 * 1024
    for f, mtime, size in restantes:
        if total_bytes <= limite:
            break
        f.unlink(missing_ok=True)
        total_bytes -= size
        removidos += 1

    return {"removidos": removidos, "restantes": len(arquivos) - removidos}
