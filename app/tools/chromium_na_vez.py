"""chromium_na_vez.py — um teste com Chromium por vez no Pi inteiro.

Por que existe (23/10/2026): em 20 e 21/10 o earlyoom encerrou centenas de processos
— Chromium, headless_shell, Python dos testes, sessões do Claude — porque várias
sessões rodavam suítes com Chromium AO MESMO TEMPO. Cada Chromium de teste come de
200 a 400 MB; três juntos com o site e as sessões abertas passam dos 3,8 GB do Pi.

O jeito de usar é trocar o import, e nada mais muda no teste:

    from tools.chromium_na_vez import sync_playwright   # no lugar do playwright.sync_api

    with sync_playwright() as pw:      # espera a vez; libera ao sair do bloco
        nav = pw.chromium.launch()

Teste que abre o Chromium por outro caminho (o `exportar.sessao` dos posts, o
`render.py`) segura a vez para o resto do processo com `segurar("nome")`.

A trava é um `flock` num arquivo: o kernel a solta sozinha quando o processo morre
(teste morto pelo prazo não deixa trava presa). Dentro do mesmo processo ela é
reentrante — o `testar_pecas` abre e fecha o Chromium oito vezes. Quem espera vê de
quem é a vez; passado CHROMIUM_ESPERA_MAX segundos (padrão 20 min) desiste com erro.
Só os TESTES passam por aqui: a exportação de posts do site tem a fila dela
(`renova/render_fila.py`), e a vigia do Instagram é um serviço à parte.
"""
from __future__ import annotations

import fcntl
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# Importado aqui, e não dentro do sync_playwright(): os testes envolvem o import num
# try/except ImportError para pular quando o Playwright não está instalado.
from playwright.sync_api import sync_playwright as _sync_playwright_original

TRAVA = Path(__file__).resolve().parent.parent / "data" / ".chromium-teste.trava"
ESPERA_MAX = int(os.environ.get("CHROMIUM_ESPERA_MAX", "1200"))
AVISO_A_CADA = 30   # segundos entre um "ainda esperando" e outro

_fd = None          # o arquivo da trava, aberto enquanto ESTE processo tem a vez
_niveis = 0         # quantos blocos deste processo estão dentro (reentrância)


def _dono() -> str:
    try:
        return TRAVA.read_text().strip() or "outro teste"
    except OSError:
        return "outro teste"


def _nome_padrao() -> str:
    return Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else f"pid {os.getpid()}"


def _pegar(nome: str) -> None:
    global _fd, _niveis
    if _niveis:
        _niveis += 1
        return
    TRAVA.parent.mkdir(parents=True, exist_ok=True)
    fd = open(TRAVA, "a+")
    t0 = ultimo_aviso = time.monotonic()
    avisou = False
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            agora = time.monotonic()
            if agora - t0 > ESPERA_MAX:
                fd.close()
                prazo = f"{ESPERA_MAX // 60} min" if ESPERA_MAX >= 120 else f"{ESPERA_MAX} s"
                raise RuntimeError(f"{nome}: desisti de esperar o Chromium depois de {prazo} "
                                   f"— ocupado por {_dono()}")
            if not avisou or agora - ultimo_aviso >= AVISO_A_CADA:
                print(f"[chromium] {nome} esperando a vez — ocupado por {_dono()}",
                      file=sys.stderr, flush=True)
                avisou, ultimo_aviso = True, agora
            time.sleep(1)
    fd.seek(0)
    fd.truncate()
    fd.write(f"{nome} (pid {os.getpid()}, desde {datetime.now():%H:%M:%S})\n")
    fd.flush()
    if avisou:
        print(f"[chromium] {nome} pegou a vez depois de {time.monotonic() - t0:.0f} s",
              file=sys.stderr, flush=True)
    _fd, _niveis = fd, 1


def _soltar() -> None:
    global _fd, _niveis
    if not _niveis:
        return
    _niveis -= 1
    if _niveis or _fd is None:
        return
    try:
        _fd.seek(0)
        _fd.truncate()
        fcntl.flock(_fd, fcntl.LOCK_UN)
    finally:
        _fd.close()
        _fd = None


@contextmanager
def vez(nome: str | None = None):
    """Bloco que só roda quando nenhum outro teste está com o Chromium aberto."""
    _pegar(nome or _nome_padrao())
    try:
        yield
    finally:
        _soltar()


def segurar(nome: str | None = None) -> None:
    """Pega a vez e fica com ela até o processo acabar (o kernel solta no fim)."""
    _pegar(nome or _nome_padrao())


@contextmanager
def sync_playwright():
    """O `sync_playwright()` do Playwright, esperando a vez antes de abrir."""
    with vez():
        with _sync_playwright_original() as pw:
            yield pw
