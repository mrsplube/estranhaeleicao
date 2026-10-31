"""Contagem de visitas sem rastrear ninguém (30/10/2026).

O site público (SITE_MODO=publico) anota cada página vista e alguns eventos
(caso aberto, simulação conferida) num SQLite em /dados. Não guarda IP, não usa
cookie e não chama serviço de fora: o "visitante" é um hash de IP + navegador
com um sal que troca todo dia, então dá para contar pessoas no dia, mas não
seguir ninguém de um dia para o outro nem descobrir quem é.

O arquivo privado (SITE_MODO=completo) lê o mesmo banco e mostra o resumo em
/visitas (atrás do login).
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from urllib.parse import urlparse

BANCO = Path(os.environ.get("VISITAS_DB", "/dados/visitas.db"))
_trava = threading.Lock()
_sal = {"dia": None, "valor": b""}
_fila: list = []          # visitas esperando gravação (em lote, a cada 5 s ou 25 linhas)
_ultima = [0.0]
EVENTOS = {"caso", "resultado", "compartilhar", "tutorial"}


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(BANCO, timeout=5)
    con.execute("pragma journal_mode=wal")
    con.execute("""create table if not exists visita (
        dia text, hora text, caminho text, visitante text, origem text, celular int)""")
    con.execute("create table if not exists evento (dia text, nome text, alvo text, visitante text)")
    con.execute("create index if not exists visita_dia on visita(dia)")
    return con


def ativo() -> bool:
    return BANCO.parent.is_dir() and os.access(BANCO.parent, os.W_OK)


def _visitante(ip: str, ua: str) -> str:
    # O sal do dia vem de um segredo em /dados + a data: igual entre os
    # processos do servidor (a mesma pessoa conta uma vez), diferente a cada dia.
    hoje = date.today().isoformat()
    if _sal["dia"] != hoje:
        arq = BANCO.parent / "sal"
        if not arq.exists():
            arq.write_bytes(secrets.token_bytes(32))
        _sal.update(dia=hoje, valor=hashlib.sha256(arq.read_bytes() + hoje.encode()).digest())
    return hashlib.sha256(_sal["valor"] + ip.encode() + ua.encode()).hexdigest()[:16]


def _origem(ref: str) -> str:
    host = urlparse(ref or "").netloc.lower().removeprefix("www.")
    if not host or host.endswith("estranhaeleicao.org"):
        return ""
    for nome, chave in (("WhatsApp", "whatsapp"), ("Instagram", "instagram"), ("Google", "google."),
                        ("X", "t.co"), ("X", "twitter"), ("Facebook", "facebook"), ("TikTok", "tiktok")):
        if chave in host:
            return nome
    return host[:60]


def anotar(caminho: str, ip: str, ua: str, ref: str) -> None:
    if not ativo() or "bot" in ua.lower() or "spider" in ua.lower():
        return
    agora = datetime.now()
    linha = (agora.date().isoformat(), agora.strftime("%H"), caminho[:80], _visitante(ip, ua),
             _origem(ref), int("Mobi" in ua))
    with _trava:
        _fila.append(linha)
        if len(_fila) < 25 and time.monotonic() - _ultima[0] < 5:
            return
        lote, _fila[:] = list(_fila), []
        _ultima[0] = time.monotonic()
    try:
        con = _con()
        con.executemany("insert into visita values (?,?,?,?,?,?)", lote)
        con.commit(); con.close()
    except sqlite3.Error:
        pass


def evento(nome: str, alvo: str, ip: str, ua: str) -> None:
    if not ativo() or nome not in EVENTOS:
        return
    with _trava:
        con = _con()
        con.execute("insert into evento values (?,?,?,?)",
                    (date.today().isoformat(), nome, (alvo or "")[:60], _visitante(ip, ua)))
        con.commit(); con.close()


def resumo_html(dias: int = 14) -> str:
    if not BANCO.exists():
        return "<p>Ainda não há visitas anotadas.</p>"
    desde = (date.today() - timedelta(days=dias - 1)).isoformat()
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    q = lambda sql, *a: con.execute(sql, a).fetchall()
    por_dia = q("select dia, count(distinct visitante), count(*), round(100.0*avg(celular)) from visita where dia>=? group by dia order by dia desc", desde)
    paginas = q("select caminho, count(*), count(distinct dia||visitante) from visita where dia>=? group by caminho order by 2 desc", desde)
    origens = q("select origem, count(distinct dia||visitante) from visita where dia>=? and origem!='' group by origem order by 2 desc limit 15", desde)
    casos = q("select alvo, count(distinct dia||visitante) from evento where dia>=? and nome='caso' group by alvo order by 2 desc", desde)
    outros = q("select nome, count(*), count(distinct dia||visitante) from evento where dia>=? and nome!='caso' group by nome", desde)
    horas = q("select hora, count(*) from visita where dia=? group by hora order by hora", date.today().isoformat())
    con.close()

    def tab(titulo, cab, linhas):
        corpo = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in l) + "</tr>" for l in linhas) or \
            f"<tr><td colspan={len(cab)}>nada ainda</td></tr>"
        return f"<h2>{titulo}</h2><table><tr>{''.join(f'<th>{c}</th>' for c in cab)}</tr>{corpo}</table>"

    return "".join([
        tab("Por dia", ["dia", "pessoas", "páginas vistas", "% celular"], por_dia),
        tab("Páginas", ["página", "vistas", "pessoas-dia"], paginas),
        tab("Casos abertos (“Ver a resposta”)", ["caso", "pessoas-dia"], casos),
        tab("Outros eventos", ["evento", "vezes", "pessoas-dia"], outros),
        tab("De onde vieram", ["origem", "pessoas-dia"], origens),
        tab("Hoje, por hora", ["hora", "páginas vistas"], horas),
    ])
