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

import contextvars
import json
import os
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
DATASET = BASE / "apuracao" / "data" / "arquivo" / "2026-2t"


def _casos_resumo() -> list[dict]:
    """Os 27 casos em texto, para o HTML da entrada (31/10/2026).

    Lido na subida: o arquivo só muda quando o gerador roda, e um erro de
    leitura (arquivo faltando, JSON quebrado) NÃO pode derrubar o site — a
    entrada sem o resumo funciona, só perde o texto para o robô. Por isso o
    `except` devolve lista vazia em vez de propagar.
    """
    try:
        return json.loads((DATASET / "casos_resumo.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


CASOS_RESUMO = _casos_resumo()


def _dados_catalogo() -> list[dict]:
    """O catálogo do /dados. Mesma regra do resumo: arquivo faltando ou JSON
    quebrado devolve lista vazia em vez de derrubar o site."""
    try:
        return json.loads((DATASET / "dados_catalogo.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=BASE / "templates")
templates.env.auto_reload = False
templates.env.globals["casos_resumo"] = CASOS_RESUMO
templates.env.globals["dados_catalogo"] = _dados_catalogo()


def _temas() -> list[dict]:
    """Os temas do /<slug>. Arquivo faltando = lista vazia (o site segue, sem
    as páginas de tema)."""
    try:
        return json.loads((DATASET / "temas.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


TEMAS = _temas()

# caso → [slug, pergunta do tema], para o link "saber mais" da lista em texto
# (que precisa existir no HTML servido, não só no cartão montado por JS).
templates.env.globals["tema_do_caso"] = {
    item["id"]: [t["slug"], t["titulo"]] for t in TEMAS for item in t["itens"]}


# Extensões que entram no `?v=`. .svg também (um mapa ou gráfico trocado tem de
# mudar a versão, senão o Cloudflare serve a imagem velha por 4 h — ver
# mapa-apostas.svg em 30/10) e as capas dos casos (.jpg), que o estranha.js
# pede com `?v=`.
_EXT_V = (".js", ".css", ".svg", ".json", ".jpg")
# Pastas de estáticos que a versão olha. Com `scandir` em vez de `glob`, a
# montagem da versão caiu de ~3,6 para ~0,8 ms no host (são ~75 arquivos e o
# template pede `static_v` até 10 vezes por página).
_DIRS_V = ("", "casos", "logos", "fotos", "og", "apuracao")


def _versao_agora() -> str:
    """mtime do estático mais novo, em segundos (o `?v=` das URLs)."""
    mt = 0.0
    for sub in _DIRS_V:
        try:
            with os.scandir(static_dir / sub) as it:
                for e in it:
                    if e.name.endswith(_EXT_V):
                        try:
                            m = e.stat().st_mtime
                        except OSError:
                            continue
                        if m > mt:
                            mt = m
        except FileNotFoundError:
            continue
    return str(int(mt))


# Ícone do site (30/10/2026): "ee" das iniciais, branco e amarelo no fundo escuro
# (static/favicon.svg é a fonte; o PNG garante a mesma letra em qualquer navegador).
FAVICON = "/static/favicon-64.png"

# `static_v` é string já na subida. Tem de ser string e não função: o Jinja não
# chama o que acha em `{{ static_v }}`, imprime o `repr` — em 31/10 a URL saiu
# como `?v=<function _static_v at 0x...>` (as páginas eram cacheadas com a
# chave errada e, o pior, o mesmo valor em toda visita).
templates.env.globals["static_v"] = _versao_agora()


def _atualizar_versao() -> str:
    """Recalcula a versão dos arquivos estáticos no começo de cada página.

    O código entra por volume, sem rebuild: se a versão ficasse presa no valor do
    primeiro boot, o navegador continuaria pedindo `?v=` velho e serviria JS/CSS
    de antes da edição (aconteceu em 30/10 com os ícones e o gráfico da Polymarket).
    Uma varredura por pedido, aqui, e o template lê a string pronta — são até 10
    `{{ static_v }}` por página, e antes cada um refazia o disco.
    """
    v = _versao_agora()
    templates.env.globals["static_v"] = v
    return v


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
PUBLICO = ("/", "/sobre", "/metodo", "/analise", "/dados", "/fraude-nas-urnas", "/biometria",
           "/virada-do-2-turno", "/prorrogacao", "/mesario", "/campanha-e-governo", "/simulacao", "/simulacao/cenarios", "/simulacao/detalhe", "/apuracao", "/apuracao/cenarios", "/apuracao/detalhe", "/robots.txt", "/sitemap.xml", "/saude", "/favicon.ico", "/v")
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
        # Barra final numa página que existe: 301 para a forma canônica (o
        # `rel="canonical"` já aponta para lá). Sem isso, /sobre/ e /sobre
        # respondiam 404 pela mesma URL... e 200 com barras diferentes seriam
        # duas URLs com o mesmo conteúdo aos olhos de quem rastreia.
        # O destino é relativo de propósito: o host do pedido já é o certo (ou
        # o domínio do site, ou o 127.0.0.1 do ensaio), e o 301 para o
        # domínio canônico é assunto de `_destino_canonico`, logo acima.
        if caminho.endswith("/") and caminho.rstrip("/") in PAGINAS:
            fila = ("?" + request.url.query) if request.url.query else ""
            return RedirectResponse(caminho.rstrip("/") + fila, status_code=301)
        return _nao_encontrado(request)
    # HEAD: o FastAPI, nestas rotas, responde 405 (o método de cada `@app.get`
    # é só GET). Cabeçalho é o que o robô e o monitor de link querem; serve
    # como GET, e o uvicorn corta o corpo sozinho em HEAD.
    if request.method == "HEAD":
        request.scope["method"] = "GET"
        resposta = await call_next(request)
        request.scope["method"] = "HEAD"
    else:
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


PAGINAS = {"/", "/simulacao", "/simulacao/cenarios", "/simulacao/detalhe", "/sobre", "/metodo", "/analise", "/dados"}


def _nao_encontrado(request: Request) -> Response:
    """404 de verdade (status 404, não 200) com uma página que ajuda a sair.

    Antes, o middleware devolvia um texto puro de 15 bytes: o robô via 404
    (certo) e a pessoa via "não encontrado" sem barra, sem rodapé e sem saída.
    A página leva `noindex` e não declara canônica: o endereço que a produziu
    não existe.
    """
    return templates.TemplateResponse(request, "404.html", status_code=404)


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


@app.get("/metodo", include_in_schema=False)
async def metodo(request: Request):
    # Método e limites (31/10/2026): o que está feito, o que não está e o que o
    # dado não permite concluir — a página que um leitor acadêmico procura antes
    # de dar crédito. Fica separada do /sobre porque quem quer o método quer a
    # página inteira, sem rolar a opinião do autor antes.
    return templates.TemplateResponse(request, "metodo.html")


def _analise() -> dict | None:
    """O plano e os resultados do /analise. Lido a cada visita (são ~8 KB):
    quando um teste roda, o script grava o resultado e a página muda sem restart."""
    try:
        return json.loads((DATASET / "analise.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@app.get("/analise", include_in_schema=False)
async def analise(request: Request):
    # Análise estatística (01/11/2026): os testes das acusações numéricas,
    # registrados antes de rodar (docs/preregistro/), e o resultado de cada um.
    return templates.TemplateResponse(request, "analise.html", {"analise": _analise()})


@app.get("/dados", include_in_schema=False)
async def dados(request: Request):
    # Dados abertos (31/10/2026): o catálogo dos JSON que sustentam cada caso.
    # A lista vem de `dados_catalogo.json`, que o gerador só grava depois de
    # conferir cada URL contra este servidor — link quebrado não entra.
    return templates.TemplateResponse(request, "dados.html",
                                      {"agora": time.strftime("%d/%m/%Y")})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    return FileResponse(static_dir / "favicon.ico", media_type="image/x-icon")


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    if MODO == "completo":
        return PlainTextResponse("User-agent: *\nDisallow: /\n")
    # O Sitemap vai com URL absoluta (é o que a norma do robots.txt pede) e o
    # resto continua liberado: o site é público e não tem área de busca.
    #
    # Crawlers de IA (31/10/2026): liberados de propósito. A página existe para
    # responder a uma dúvida, e hoje muita gente pergunta ao ChatGPT ou ao
    # Perplexity antes de procurar no Google — bloquear ali é escolher não ser
    # lido. `ai-train=no` continua: o texto pode ser citado, não serve para
    # treinar modelo.
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Content-Signal: search=yes, ai-input=yes, ai-train=no\n\n"
        "User-agent: GPTBot\n"
        "Allow: /\n\n"
        "User-agent: PerplexityBot\n"
        "Allow: /\n\n"
        "User-agent: ClaudeBot\n"
        "Allow: /\n\n"
        "User-agent: Google-Extended\n"
        "Allow: /\n\n"
        "Sitemap: https://estranhaeleicao.org/sitemap.xml\n")


# As páginas que entram no sitemap, os templates que as montam e os arquivos de
# dados que elas leem. O `lastmod` sai do mtime deles, não de uma data escrita à
# mão: quando o texto de um caso muda — no template da entrada ou no
# `acusacoes.json`, que é de onde o estranha.js monta os casos —, a data da
# página muda junto; e quando nada muda, a data também não.
SITEMAP = {
    "/": (("site.html", "estranha.html"), ("acusacoes.json", "casos_videos.json")),
    "/simulacao": (("site.html", "chute.html"), ("chute.json",)),
    "/simulacao/cenarios": (("site.html", "chute.html"), ("chute.json",)),
    "/simulacao/detalhe": (("base.html", "apuracao.html"), ("conta.json", "acusacoes.json")),
    "/sobre": (("site.html", "sobre.html"), ()),
    "/metodo": (("site.html", "metodo.html"), ()),
    "/analise": (("site.html", "analise.html"), ("analise.json",)),
    "/dados": (("site.html", "dados.html"), ("dados_catalogo.json",)),
    # Temas (31/10/2026): entram no sitemap de propósito mesmo sem link
    # interno — é por aqui que o Google descobre as páginas órfãs.
    **{"/" + t["slug"]: (("site.html", "tema.html"), ("temas.json",)) for t in TEMAS},
}


def _lastmod(templates_usados: tuple[str, ...], dados: tuple[str, ...] = ()) -> str:
    """A data do arquivo mais novo que monta a página, em AAAA-MM-DD."""
    mt = [Path(__file__).stat().st_mtime]
    for nome in templates_usados:
        caminho = BASE / "templates" / nome
        if caminho.exists():
            mt.append(caminho.stat().st_mtime)
    for nome in dados:
        caminho = DATASET / nome
        if caminho.exists():
            mt.append(caminho.stat().st_mtime)
    return time.strftime("%Y-%m-%d", time.localtime(max(mt)))


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    urls = "".join(
        f"<url><loc>https://estranhaeleicao.org{u}</loc>"
        f"<lastmod>{_lastmod(usados, dados)}</lastmod>"
        f"<changefreq>{'daily' if u == '/' else 'weekly'}</changefreq>"
        f"<priority>{'1.0' if u == '/' else '0.8'}</priority></url>"
        for u, (usados, dados) in SITEMAP.items())
    return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    + urls + "</urlset>", media_type="application/xml")


@app.get("/saude", include_in_schema=False)
async def saude():
    return {"ok": True}


@app.get("/{slug}", include_in_schema=False)
async def tema(slug: str, request: Request):
    # Página por tema (31/10/2026). Fica no FIM do arquivo de propósito: é uma
    # rota genérica de um segmento, e o FastAPI casa na ordem de registro —
    # se viesse antes, capturaria /sobre, /metodo, /dados e /simulacao.
    # Slug desconhecido cai no 404 de verdade (não no texto puro de antes).
    for t in TEMAS:
        if t["slug"] == slug:
            return templates.TemplateResponse(request, "tema.html", {"tema": t})
    return _nao_encontrado(request)
