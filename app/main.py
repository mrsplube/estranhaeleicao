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

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response
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
    for padrao in ("*.js", "*.css", "*/*.js", "*/*.css", "*/*.json"):
        mt.extend(f.stat().st_mtime for f in static_dir.glob(padrao))
    return str(int(max(mt)))


# Ícone do site (30/10/2026): "ee" das iniciais, branco e amarelo no fundo escuro
# (static/favicon.svg é a fonte; o PNG garante a mesma letra em qualquer navegador).
FAVICON = "/static/favicon-64.png"

templates.env.globals["static_v"] = _static_version()
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


@app.middleware("http")
async def porta(request: Request, call_next):
    caminho = request.url.path
    if MODO == "completo":
        # Arquivo privado: tudo atrás do login (menos o healthcheck).
        if caminho != "/saude" and not current_user(request):
            return Response("login necessário", status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="apuracao"'})
    elif caminho not in PUBLICO and not caminho.startswith(PUBLICO_PREFIXOS):
        return PlainTextResponse("não encontrado", status_code=404)
    resposta = await call_next(request)
    # Página vista (só as páginas, não os arquivos; ver visitas.py).
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
    return PlainTextResponse("User-agent: *\nAllow: /\nSitemap: https://estranhaeleicao.org/sitemap.xml\n")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    urls = "".join(f"<url><loc>https://estranhaeleicao.org{u}</loc></url>"
                   for u in ("/", "/simulacao", "/simulacao/cenarios", "/simulacao/detalhe", "/sobre"))
    return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    + urls + "</urlset>", media_type="application/xml")


@app.get("/saude", include_in_schema=False)
async def saude():
    return {"ok": True}
