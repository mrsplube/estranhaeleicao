"""A apuração de 2026, tirada do V2 (projetoscaue.lol, mrsplube) em 30/10/2026.

O mesmo código roda em dois modos (SITE_MODO):

- `publico` — estranhaeleicao.org: só a conta do 2º turno presidencial
  (`/`, `/apuracao` e `/apuracao/explicacao/*`). O resto responde 404.
- `completo` — arquivo privado no familiacaue, atrás de HTTP Basic: o painel do
  1º turno, todas as rotas de dados, o explorador de microdados
  (`/politicos/eleicao`, o antigo politicos/resultados.py do V2) e o modo ao
  vivo das noites de eleição (coletor no host, ver docs).

O pacote `apuracao/`, `politicos/` e as templates vieram do V2 sem mudança de
lógica; `auth.py` e `app_visibility.py` são substitutos. O container só lê.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from apuracao import router as apuracao
from auth import MODO, current_user, get_real_ip
import visitas

BASE = Path(__file__).resolve().parent
static_dir = BASE / "static"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=BASE / "templates")
templates.env.auto_reload = False


def _static_version() -> str:
    mt = [0.0]
    # .svg também: um mapa ou gráfico trocado tem de mudar o `?v=` (senão o
    # Cloudflare serve a imagem velha por 4 h, ver mapa-apostas.svg em 30/10).
    # E as capas dos casos (static/casos/*.jpg), que o estranha.js pede com ?v=.
    for padrao in ("*.js", "*.css", "*.svg", "*/*.js", "*/*.css", "*/*.json", "*/*.svg", "*/*.jpg"):
        mt.extend(f.stat().st_mtime for f in static_dir.glob(padrao))
    return str(int(max(mt)))


# Ícone do site (30/10/2026): "ee" das iniciais, branco e amarelo no fundo escuro
# (static/favicon.svg é a fonte; o PNG garante a mesma letra em qualquer navegador).
FAVICON = "/static/favicon-64.png"

templates.env.globals["static_v"] = _static_version()


def _atualizar_versao() -> None:
    """Recalcula a versão dos arquivos estáticos a cada página.

    O código entra por volume, sem rebuild: se a versão ficasse presa no valor do
    primeiro boot, o navegador continuaria pedindo `?v=` velho e serviria JS/CSS
    de antes da edição (aconteceu em 30/10 com os ícones e o gráfico da Polymarket).
    """
    templates.env.globals["static_v"] = _static_version()


def _static_v() -> str:
    """Calculado a cada página, não na subida do processo.

    O código entra por volume, sem rebuild: se a versão ficasse presa no valor do
    primeiro boot, o navegador continuaria pedindo `?v=` velho e serviria JS/CSS
    de antes da edição (aconteceu em 30/10 com os ícones e o gráfico da Polymarket).
    """
    return _static_version()


templates.env.globals["static_v"] = _static_v
templates.env.globals["favicon_for_path"] = lambda path: FAVICON

templates.env.globals["modo_completo"] = MODO == "completo"

apuracao.set_templates(templates)
app.include_router(apuracao.router)
app.include_router(apuracao.paginas)

if MODO == "completo":
    from politicos import resultados
    resultados.set_templates(templates)
    app.include_router(resultados.router)

# O que o modo público serve: a página do 2º turno e os dados que ela pede.
PUBLICO = ("/", "/sobre", "/simulacao", "/simulacao/cenarios", "/simulacao/detalhe", "/apuracao", "/apuracao/cenarios", "/apuracao/detalhe", "/robots.txt", "/sitemap.xml", "/saude", "/favicon.ico", "/v")
PUBLICO_PREFIXOS = ("/apuracao/explicacao/", "/static/")


# O domínio canônico do modo público. Tudo que chega por `www.` ou por `http://`
# vai para cá com 301 (o Seobility marcou os dois: "o site usa www e não-www, o
# que gera conteúdo duplicado" e "o redirecionamento para HTTPS não está certo").
CANONICO = "estranhaeleicao.org"


def _destino_canonico(cabecalhos, caminho: str) -> str | None:
    """A URL de 301 para este pedido, ou None se ele já está no lugar certo.

    Atrás do túnel da Cloudflare o que o app vê não é o que o visitante
    digitou: o pedido chega em `127.0.0.1:3030`, em `http`. O que falta vem
    nos cabeçalhos que o túnel repassa — o `Host` do site e o
    `X-Forwarded-Proto`. Só age quando o host é do domínio do site; qualquer
    outro (a rede local, o healthcheck do compose) passa intacto, senão o
    container se redirecionaria para fora do ar.
    """
    host = (cabecalhos.get("host") or "").split(":")[0].lower()
    if host not in (CANONICO, "www." + CANONICO):
        return None
    proto = (cabecalhos.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    # `proto` vazio é o teste local (`http://127.0.0.1:3038` com Host do site):
    # nesse caso não dá para saber o esquema real, e seguir em frente evita um
    # 301 em falso que quebraria o ensaio.
    if host == CANONICO and proto != "http":
        return None
    return "https://" + CANONICO + caminho


@app.middleware("http")
async def porta(request: Request, call_next):
    caminho = request.url.path
    # `?v=` novo em cada resposta: o código muda sem rebuild (ver _atualizar_versao).
    _atualizar_versao()
    if MODO != "completo" and caminho != "/saude":  # o healthcheck usa 127.0.0.1
        fila = ("?" + request.url.query) if request.url.query else ""
        destino = _destino_canonico(request.headers, caminho + fila)
        if destino:
            return RedirectResponse(destino, status_code=301)
    if MODO == "completo":
        # Arquivo privado: tudo atrás do login (menos o healthcheck).
        if caminho != "/saude" and not current_user(request):
            return Response("login necessário", status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="apuracao"'})
    elif caminho not in PUBLICO and not caminho.startswith(PUBLICO_PREFIXOS):
        return PlainTextResponse("não encontrado", status_code=404)
    resposta = await call_next(request)
    # Cache dos estáticos (31/10/2026, achado do Seobility: "a página leva
    # 0,69 s"). O `?v=` do template muda quando o arquivo muda, então o
    # navegador pode guardar: 1 h, e o ETag do Starlette resolve o resto com
    # 304 sem corpo. As imagens de Open Graph entram junto — o WhatsApp e o X
    # buscam a URL uma vez e guardam do lado deles.
    # NÃO vira `immutable`/`max-age` longo: o `static_v` recalcula o mtime por
    # request de propósito (ver _atualizar_versao) e um arquivo trocado tem de
    # furar o cache. 1 h é o que segura a navegação sem prender o visitante.
    if caminho.startswith("/static/") and resposta.status_code == 200:
        resposta.headers.setdefault("Cache-Control", "public, max-age=3600")
    if MODO != "completo" and request.method == "GET" and caminho in PAGINAS and resposta.status_code == 200:
        try:
            visitas.anotar(caminho, get_real_ip(request), request.headers.get("user-agent", ""), request.headers.get("referer", ""))
        except Exception:
            pass
    return resposta


PAGINAS = {"/", "/simulacao", "/simulacao/cenarios", "/simulacao/detalhe", "/sobre"}


@app.post("/v", include_in_schema=False)
async def evento(request: Request):
    """Evento anônimo do navegador (sendBeacon): {"e": "caso", "a": "biometria"}."""
    if MODO != "completo":
        try:
            d = await request.json()
            visitas.evento(str(d.get("e", "")), str(d.get("a", "")), get_real_ip(request), request.headers.get("user-agent", ""))
        except Exception:
            pass
    return Response(status_code=204)


@app.get("/visitas", include_in_schema=False)
async def ver_visitas(request: Request):
    if MODO != "completo":
        return PlainTextResponse("não encontrado", status_code=404)
    estilo = ("body{font:15px system-ui;margin:24px;background:#0e1326;color:#e4e6f0}table{border-collapse:collapse;margin-bottom:24px}"
              "td,th{padding:5px 12px;border-bottom:1px solid #2d385e;text-align:left}th{color:#e6be55}h2{font-size:17px}")
    return Response(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><title>Visitas</title>"
                    f"<style>{estilo}</style><h1>estranhaeleicao.org · últimos 14 dias</h1>{visitas.resumo_html()}",
                    media_type="text/html")


@app.get("/", include_in_schema=False)
async def raiz(request: Request):
    # A entrada (desde 30/10/2026): os boatos do 2º turno como casos + o jogo
    # "chute a cidade" (static/estranha.js). A conta completa segue em /apuracao.
    return templates.TemplateResponse(request, "estranha.html")


@app.get("/sobre", include_in_schema=False)
async def sobre(request: Request):
    # Por que confiar nas análises: fontes, conferência, limites (30/10/2026).
    return templates.TemplateResponse(request, "sobre.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    return FileResponse(static_dir / "favicon.ico", media_type="image/x-icon")


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    if MODO == "completo":
        return PlainTextResponse("User-agent: *\nDisallow: /\n")
    # O Sitemap vai com URL absoluta (é o que a norma do robots.txt pede) e o
    # resto continua liberado: o site é público e não tem área de busca.
    return PlainTextResponse("User-agent: *\nAllow: /\n\nSitemap: https://estranhaeleicao.org/sitemap.xml\n")


# As páginas que entram no sitemap e os templates que cada uma usa. O `lastmod`
# sai do mtime deles, não de uma data escrita à mão: quando o texto de um caso
# muda, a data da página muda junto — e quando nada muda, a data também não.
SITEMAP = {
    "/": ("site.html", "estranha.html"),
    "/simulacao": ("site.html", "chute.html"),
    "/simulacao/cenarios": ("site.html", "chute.html"),
    "/simulacao/detalhe": ("base.html", "apuracao.html"),
    "/sobre": ("site.html", "sobre.html"),
}


def _lastmod(templates_usados: tuple[str, ...]) -> str:
    """A data do arquivo mais novo que monta a página, em AAAA-MM-DD."""
    mt = [Path(__file__).stat().st_mtime]
    for nome in templates_usados:
        caminho = BASE / "templates" / nome
        if caminho.exists():
            mt.append(caminho.stat().st_mtime)
    return time.strftime("%Y-%m-%d", time.localtime(max(mt)))


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    urls = "".join(
        f"<url><loc>https://estranhaeleicao.org{u}</loc>"
        f"<lastmod>{_lastmod(usados)}</lastmod>"
        f"<changefreq>{'daily' if u == '/' else 'weekly'}</changefreq>"
        f"<priority>{'1.0' if u == '/' else '0.8'}</priority></url>"
        for u, usados in SITEMAP.items())
    return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    + urls + "</urlset>", media_type="application/xml")


@app.get("/saude", include_in_schema=False)
async def saude():
    return {"ok": True}
