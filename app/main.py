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
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from apuracao import router as apuracao
from auth import MODO, current_user

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


FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
           "<rect width='16' height='16' rx='3' fill='%231f6feb'/>"
           "<rect x='3' y='8' width='2' height='5' fill='white'/>"
           "<rect x='7' y='5' width='2' height='8' fill='white'/>"
           "<rect x='11' y='3' width='2' height='10' fill='white'/></svg>")

templates.env.globals["static_v"] = _static_version()
templates.env.globals["favicon_for_path"] = lambda path: FAVICON

templates.env.globals["modo_completo"] = MODO == "completo"

apuracao.set_templates(templates)
app.include_router(apuracao.router)

if MODO == "completo":
    from politicos import resultados
    resultados.set_templates(templates)
    app.include_router(resultados.router)

# O que o modo público serve: a página do 2º turno e os dados que ela pede.
PUBLICO = ("/", "/sobre", "/apuracao", "/apuracao/cenarios", "/apuracao/detalhe", "/robots.txt", "/saude", "/favicon.ico")
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
    return await call_next(request)


@app.get("/", include_in_schema=False)
async def raiz(request: Request):
    # A entrada (desde 30/10/2026): os boatos do 2º turno como casos + o jogo
    # "chute a cidade" (static/estranha.js). A conta completa segue em /apuracao.
    return templates.TemplateResponse(request, "estranha.html")


@app.get("/sobre", include_in_schema=False)
async def sobre(request: Request):
    # Por que confiar nas análises: fontes, conferência, limites (30/10/2026).
    return templates.TemplateResponse(request, "sobre.html")


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    if MODO == "completo":
        return PlainTextResponse("User-agent: *\nDisallow: /\n")
    return PlainTextResponse("User-agent: *\nAllow: /\n")


@app.get("/saude", include_in_schema=False)
async def saude():
    return {"ok": True}
