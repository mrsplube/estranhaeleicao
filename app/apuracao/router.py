"""Apuração 2026 — página PÚBLICA (projetoscaue.lol/apuracao).

**Eleição encerrada desde 25/10/2026.** A página não fala mais com o TSE, não
roda coletor e não recalcula nada a cada visita: ela lê o ARQUIVO CONGELADO da
noite, em `data/arquivo/2026-2t/` (2º turno) e `data/arquivo/2026-1t/`
(deputados, Senado e governos, que o 2º turno não mudou).

O que isso significa na prática:

- **Zero pedido ao TSE.** Nenhuma rota daqui importa `httpx`. O painel do TSE
  era um serviço da noite da eleição; manter isso vivo depois era pedir
  arquivo que não muda mais — e, pior, pedir de minuto em minuto.
- **Zero conta por visita.** Os JSON são servidos de disco com ETag e
  `max-age` longo: o caso comum é um 304 sem corpo, e um arquivo só é lido
  quando o mtime muda (o que, congelado, nunca acontece).
- **Zero escrita contínua.** O último arquivo que esta página toca é o que já
  está no disco. `coleta.log`, `serie.jsonl` e `pulso.json` não crescem mais.

Cada arquivo fica em memória até o mtime mudar, com ETag. O freio por IP
(`_Freio`) continua: a página nunca precisou dele contra leitor humano, só
contra robô.

A explicação do 2º turno (a aba "A conta do 2º turno") é servida de
`data/arquivo/2026-2t/explicacao.json`, gerado uma vez por
`tools/migracoes/2026-10-27-explicacao-2t.py` a partir da votação por seção
dos dois turnos.

**Para a PRÓXIMA eleição** (o /politicos/eleicao continua sendo a versão
privada com microdados):

1. trocar os códigos de eleição em `coleta.py` e conferir o `config/ele-c.json`
   do TSE;
2. apontar `coleta.DADOS` para uma pasta nova (`apuracao/data/` já é a pasta de
   trabalho do próximo coletor — o 2026 está todo em `data/arquivo/`);
3. religar os crons `# apuracao` e `# apuracao-mun` (handoff de 04/10/2026);
4. trocar `ARQUIVO` em `router.py` (e em `apuracao/tela.py`) para a pasta nova
   — ou apagar a constante e voltar a ler `coleta.DADOS`;
5. ligar o interruptor público no /admin.

`/apuracao?previa=1` mostra a página com os números a quem está logado.
"""
from __future__ import annotations

import gzip
import json
import os
import time
from collections import deque
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app_visibility import is_visible
from auth import current_user, get_real_ip
from apuracao import explicacao

router = APIRouter(prefix="/apuracao")
_templates: Jinja2Templates | None = None

# Onde mora o 2026 encerrado. É a ÚNICA fonte de dado desta página: nada aqui
# aponta para `coleta.DADOS`, que é a pasta que o coletor reescreveria na próxima
# eleição (e que, se o cron voltasse a rodar, faria a página mudar sozinha).
ARQUIVO = Path(__file__).resolve().parent / "data" / "arquivo" / "2026-2t"
ARQUIVO_1T = Path(__file__).resolve().parent / "data" / "arquivo" / "2026-1t"

# Arquivo congelado não muda: o navegador pode guardar por muito tempo e o Pi
# não precisa responder nem o 304. A noite da eleição usava 4 s; agora não há
# nada a revalidar.
CACHE = "public, max-age=86400"


def set_templates(t: Jinja2Templates) -> None:
    global _templates
    _templates = t


class _Freio:
    """Janela deslizante por IP. Em memória: o site tem um worker só."""

    def __init__(self, por_minuto: int):
        self.limite = por_minuto
        self.vistos: dict[str, deque] = {}
        self.faxina = time.monotonic()

    def passa(self, ip: str) -> bool:
        agora = time.monotonic()
        if agora - self.faxina > 120:
            self.vistos = {k: v for k, v in self.vistos.items() if v and agora - v[-1] < 60}
            self.faxina = agora
        fila = self.vistos.setdefault(ip, deque())
        while fila and agora - fila[0] > 60:
            fila.popleft()
        if len(fila) >= self.limite:
            return False
        fila.append(agora)
        return True


_freio_dados = _Freio(por_minuto=120)
_freio_pagina = _Freio(por_minuto=30)


def _porta(request: Request, freio: _Freio, json_: bool) -> None:
    """Interruptor do /admin e freio por IP, nesta ordem."""
    if arquivada() and not current_user(request):
        if json_:
            raise HTTPException(status_code=401, detail="login necessário")
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    if not freio.passa(get_real_ip(request)):
        raise HTTPException(status_code=429, detail="muitas requisições — aguarde um minuto",
                            headers={"Retry-After": "30"})


class _Arquivo:
    """Um JSON do disco em memória, recarregado quando o mtime muda."""

    def __init__(self):
        self.cache: dict[Path, tuple[int, bytes, str]] = {}

    def ler(self, caminho: Path) -> tuple[bytes, str] | None:
        try:
            mt = caminho.stat().st_mtime_ns
        except OSError:
            return None
        guardado = self.cache.get(caminho)
        if guardado and guardado[0] == mt:
            return guardado[1], guardado[2]
        corpo = caminho.read_bytes()
        etag = f'"{mt:x}"'
        self.cache[caminho] = (mt, corpo, etag)
        return corpo, etag


_arquivos = _Arquivo()


def _servir(request: Request, caminho: Path, cache: str = CACHE) -> Response:
    lido = _arquivos.ler(caminho)
    if lido is None:
        return JSONResponse({"erro": "arquivo não encontrado"}, status_code=503)
    corpo, etag = lido
    cab = {"ETag": etag, "Cache-Control": cache}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cab)
    return Response(corpo, media_type="application/json", headers=cab)


def arquivada() -> bool:
    """Interruptor público desligado = página fechada. `APURACAO_AO_VIVO=1`
    força o modo aberto (é o que o ensaio de tools/testar_apuracao.py usa)."""
    return not is_visible("apuracao", "publico") and not os.environ.get("APURACAO_AO_VIVO")


@router.get("", response_class=HTMLResponse)
async def chute(request: Request):
    """O chute do 2º turno (desde 30/10/2026): a pessoa divide cada grupo de
    eleitor do 1º turno entre Lula, Flávio e nenhum, com a dica da pesquisa, e
    no fim vê se bate com o TSE. Lê `explicacao/chute.json`."""
    _porta(request, _freio_pagina, json_=False)
    return _templates.TemplateResponse(request, "chute.html", {"pagina": "chute"})


@router.get("/cenarios", response_class=HTMLResponse)
async def cenarios(request: Request):
    """Três jeitos de a conta fechar com o TSE (o passo depois do chute)."""
    _porta(request, _freio_pagina, json_=False)
    return _templates.TemplateResponse(request, "chute.html", {"pagina": "cenarios"})


@router.get("/detalhe", response_class=HTMLResponse)
async def pagina(request: Request, previa: int = 0):
    user = current_user(request)
    if arquivada() and not (previa and user):
        if not _freio_pagina.passa(get_real_ip(request)):
            raise HTTPException(status_code=429, detail="muitas requisições — aguarde um minuto")
        from auth import can_access
        return _templates.TemplateResponse(request, "apuracao_encerrada.html", {
            "user": user, "interno": bool(user and can_access(user, "politicos")),
            "is_admin": bool(user and user.get("role") == "admin"),
        })
    _porta(request, _freio_pagina, json_=False)
    return _templates.TemplateResponse(request, "apuracao.html", {
        "user": current_user(request),
        "segundo_turno": True,
        "explicacao": explicacao.resumo(ARQUIVO),
    })


@router.get("/noite", response_class=HTMLResponse)
async def noite(request: Request):
    """O PAINEL da noite de 04/10 — o outro app.

    Antes ele vivia na mesma página que a explicação, e todo mundo baixava as
    2.000 linhas do `apuracao.js` (hemiciclo, quociente, sobras, mapa de SC)
    para ler "de onde vieram os votos". Separado: a explicação carrega ~75 KB,
    o painel carrega o que precisa, e quem não quer o painel não paga por ele.
    """
    _porta(request, _freio_pagina, json_=False)
    return _templates.TemplateResponse(request, "apuracao_noite.html", {
        "user": current_user(request), "segundo_turno": True,
    })


@router.get("/estado.json")
async def estado(request: Request):
    _porta(request, _freio_dados, json_=True)
    return _servir(request, ARQUIVO / "estado.json")


@router.get("/presidente.json")
async def presidente(request: Request):
    """2º turno: placar, previsão do vencedor e o voto que faltava por UF."""
    _porta(request, _freio_dados, json_=True)
    return _servir(request, ARQUIVO / "presidente.json")


@router.get("/serie_pres.json")
async def serie_pres(request: Request):
    """A noite do 2º turno: % apurado, placar, projeção e chance, sem repetidos.

    Já é um arquivo curto (a noite inteira em ~270 pontos), congelado — não há
    mais o que podar a cada pedido.
    """
    _porta(request, _freio_dados, json_=True)
    try:
        pontos = [json.loads(linha) for linha in
                  (ARQUIVO / "serie_pres.jsonl").read_text(encoding="utf-8").splitlines()
                  if linha.strip()]
    except (OSError, ValueError):
        return JSONResponse([])
    return JSONResponse(pontos, headers={"Cache-Control": CACHE})


@router.get("/majoritarias.json")
async def majoritarias(request: Request):
    """Governador e Senado das 27 UFs (só a aba de majoritárias pede)."""
    _porta(request, _freio_dados, json_=True)
    return _servir(request, ARQUIVO / "majoritarias.json")


@router.get("/eleitos.json")
async def eleitos(request: Request):
    """Quem cada agremiação elegeu para a Câmara, UF por UF."""
    _porta(request, _freio_dados, json_=True)
    return _servir(request, ARQUIVO / "eleitos.json")


@router.get("/uf/{uf}.json")
async def por_uf(uf: str, request: Request):
    _porta(request, _freio_dados, json_=True)
    uf = uf.lower()
    if len(uf) != 2 or not uf.isalpha():
        raise HTTPException(status_code=404)
    return _servir(request, ARQUIVO / "uf" / f"{uf}.json")


@router.get("/explicacao/conta.json")
async def explicacao_conta(request: Request):
    """TUDO o que a aba de explicação usa, num arquivo só (~17 KB).

    Antes eram três arquivos (`analise`, `cenarios`, `simulador`) dizendo os
    mesmos totais. Os três viraram um: os números de topo, o fluxo de votos com
    IC, o Sankey, os cenários e os eixos do simulador. Gerado na migração —
    nenhuma visita calcula nada.

    As rotas antigas continuam respondendo (redirecionando no cliente) para não
    quebrar aba aberta em quem já estava na página.
    """
    _porta(request, _freio_dados, json_=True)
    return _servir(request, ARQUIVO / "conta.json")


@router.get("/explicacao/municipios.json")
async def explicacao_municipios(request: Request):
    """Os 5.570 municípios no formato compacto da aba (mapa e lista de cidades).

    É um arquivo de ~600 KB, servido com ETag: o navegador pega uma vez e
    revalida. Separado do `explicacao.json` (1,5 MB) porque a tela desenha o
    mapa antes de precisar dos detalhes.
    """
    _porta(request, _freio_dados, json_=True)
    return _servir(request, ARQUIVO / "municipios.json")


@router.get("/explicacao/chute.json")
async def explicacao_chute(request: Request):
    """Os grupos de eleitor, a dica da pesquisa e os três cenários (~10 KB).
    Gerado por `tools/migracoes/2026-10-30-chute-2t.py`."""
    _porta(request, _freio_dados, json_=True)
    return _servir(request, ARQUIVO / "chute.json")


@router.get("/explicacao/casos_videos.json")
async def explicacao_casos_videos(request: Request):
    """O vídeo de cada caso da entrada e os números dos casos novos (~5 KB).
    Gerado por `tools/migracoes/2026-10-30-casos-videos.py`."""
    _porta(request, _freio_dados, json_=True)
    return _servir(request, ARQUIVO / "casos_videos.json")


@router.get("/explicacao/acusacoes.json")
async def explicacao_acusacoes(request: Request):
    """As acusações que circularam depois do 2º turno, conferidas no dado (~22 KB).

    Gerado uma vez por `tools/migracoes/2026-10-29-acusacoes-2t.py` a partir da
    votação por seção; a página só lê. Pedido quando a seção das acusações abre.
    """
    _porta(request, _freio_dados, json_=True)
    return _servir(request, ARQUIVO / "acusacoes.json")


@router.get("/pulso.json")
async def pulso(request: Request):
    """Fim da linha para esta rota.

    Na noite da eleição ela dizia "o coletor conferiu o TSE há N segundos" e a
    página recarregava sozinha quando o JS mudava. Não há mais coletor: devolver
    um pulso vivo seria mentir para a tela (e o laço de 20 s do JS continuaria
    pedindo para sempre). O `estatico` diz ao JS que ele deve desligar isso.
    """
    _porta(request, _freio_dados, json_=True)
    versao = str((_templates.env.globals.get("static_v") if _templates else "") or "")
    return JSONResponse({"estatico": True, "conferido_em": None, "pagina": versao},
                        headers={"Cache-Control": CACHE})


@router.get("/base/{tipo}.json")
async def base(tipo: str, request: Request, n: str | None = None, agr: str | None = None):
    """De onde vêm os votos de UM candidato (ou de uma agremiação) — para o mapa.

    Lê as bases do 1º turno congeladas; não recalcula nada.
    """
    _porta(request, _freio_dados, json_=True)
    from apuracao import bases as bases_mod
    if tipo not in ("est", "fed") or (not n and not agr):
        raise HTTPException(status_code=404)
    destino = ARQUIVO_1T / "bases.json"
    try:
        mt = destino.stat().st_mtime_ns
    except OSError:
        return JSONResponse({"erro": "bases não encontradas"}, status_code=503)
    if _bases["mt"] != mt:
        _bases.update(mt=mt, dados=bases_mod.carregar(destino))
    b = _bases["dados"] or {}
    if agr:
        fat = (b.get("agr", {}).get(tipo) or {}).get(agr)
        if fat is None:
            raise HTTPException(status_code=404)
        fonte = "partido"
    else:
        if n not in (b.get(tipo) or {}):
            raise HTTPException(status_code=404)
        fat, fonte = bases_mod.fatias(b, tipo, n)
    return JSONResponse({"fonte": fonte, "fatias": fat}, headers={"Cache-Control": CACHE})


_bases: dict = {"mt": None, "dados": None}


@router.get("/serie.json")
async def serie(request: Request):
    """A linha do tempo do 1º turno (deputados/ALESC), sem os pontos repetidos.

    É a mesma noite de 04/10 que o arquivo congelado guardou; o 2º turno tem a
    sua em `serie_pres.json`. Nada é podado a cada pedido: o arquivo já é curto.
    """
    _porta(request, _freio_dados, json_=True)
    try:
        pontos = [json.loads(linha) for linha in
                  (ARQUIVO_1T / "serie.jsonl").read_text(encoding="utf-8").splitlines()
                  if linha.strip()]
    except (OSError, ValueError):
        return JSONResponse([])
    return JSONResponse(pontos, headers={"Cache-Control": CACHE})


# ── por município (SC, deputado estadual e federal) ──────────────────────────
# Na noite da eleição esta rota ia ao TSE por cidade aberta (cache de 60 s e um
# teto de idas por minuto, porque o TSE recusa pedido vindo de outro domínio).
# **Acabou:** o TSE não publica mais nada de 2026, e repetir o mesmo pedido do
# arquivo final era exatamente o gasto contínuo que a eleição encerrada deixou
# de justificar.
#
# Os dois cargos já foram importados para `politicos/data/tse/2026/c0006|c0007/`
# (296 municípios cada, ~1 KB comprimido por arquivo) e a conta é a MESMA função
# da noite (`apuracao.estado.municipal`). A primeira cidade aberta decodifica o
# cargo inteiro em memória (~1 s); as seguintes são um dicionário.
CARGOS_MUN = {"est": "c0007", "fed": "c0006"}
_TSE_2026 = Path(__file__).resolve().parent.parent / "politicos" / "data" / "tse" / "2026"
_mun_cache: dict[str, dict] = {}
_municipios: dict = {"lista": None}


def _carregar_municipios(cargo: str) -> dict[str, dict]:
    """Todos os municípios de SC de um cargo, do arquivo do TSE em disco."""
    if cargo in _mun_cache:
        return _mun_cache[cargo]
    from apuracao import estado as est
    pasta = _TSE_2026 / CARGOS_MUN[cargo]
    dados: dict[str, dict] = {}
    for arq in pasta.glob("*.json.gz"):
        try:
            dados[arq.name[:-len(".json.gz")]] = est.municipal(
                json.loads(gzip.decompress(arq.read_bytes())))
        except (OSError, ValueError, KeyError):
            continue
    _mun_cache[cargo] = dados
    return dados


def _municipios_sc() -> dict[str, str]:
    """{código de 5 dígitos: nome} — do próprio resultado, sem pedir config."""
    if _municipios["lista"] is None:
        from politicos import microdados
        lista = {}
        try:
            with gzip.open(microdados.BRUTOS_2026 / "municipios.json.gz") as f:
                cfg = json.load(f)
            sc = next(a for a in cfg["abr"] if a["cd"].lower() == "sc")
            lista = {m["cd"].zfill(5): m["nm"] for m in sc["mu"]}
        except (OSError, ValueError, StopIteration):
            pass
        _municipios["lista"] = lista
    return _municipios["lista"]


@router.get("/municipios.json")
async def municipios(request: Request):
    """As 295 cidades de SC (só a aba de SC pede)."""
    _porta(request, _freio_dados, json_=True)
    lista = _municipios_sc()
    return JSONResponse([{"cd": k, "nm": v} for k, v in sorted(lista.items(), key=lambda kv: kv[1])],
                        headers={"Cache-Control": CACHE})


@router.get("/municipio/{cd}.json")
async def municipio(cd: str, request: Request, cargo: str = "est"):
    """Um município de SC: voto por agremiação e todos os candidatos.

    Lê do disco e não vai à rede em nenhuma hipótese.
    """
    _porta(request, _freio_dados, json_=True)
    from starlette.concurrency import run_in_threadpool
    if cargo not in CARGOS_MUN or not cd.isdigit():
        raise HTTPException(status_code=404)
    cd = cd.zfill(5)
    try:
        dados = (await run_in_threadpool(_carregar_municipios, cargo)).get(cd)
    except Exception:  # noqa: BLE001
        return JSONResponse({"erro": "microdados de 2026 indisponíveis"}, status_code=503)
    if dados is None:
        raise HTTPException(status_code=404)
    dados = dict(dados)
    dados["municipio"] = {"cd": cd, "nome": _municipios_sc().get(cd, cd)}
    return JSONResponse(dados, headers={"Cache-Control": CACHE})
