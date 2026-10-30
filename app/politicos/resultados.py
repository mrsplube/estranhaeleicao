"""Eleição 2026 · resultado final — a versão PRIVADA da apuração, dentro do /politicos.

    /politicos/eleicao        a página (mesmo acesso do /politicos)

A página pública (`/apuracao`) ficou arquivada para a próxima eleição; esta é a
que continua no ar. Ela reaproveita o desenho da apuração (`static/apuracao.js`
com `data-final="1"`, que desliga Previsão/Ao vivo, pulso e avisos) e soma as
abas de análise (`static/politicos_eleicao.js`), que leem os microdados
(`politicos/microdados.py` → `politicos/data/eleicoes.db`).

Os números da apuração vêm do ARQUIVO congelado da noite
(`apuracao/data/arquivo/2026-1t/`), nunca de `apuracao/data/`, que é a pasta
que o coletor reescreve quando a próxima eleição começar.
"""
from __future__ import annotations

import gzip
import json
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from auth import can_access, require_login
from politicos import analise_eleitoral as ae
from politicos import microdados

router = APIRouter(prefix="/politicos/eleicao")
_templates: Jinja2Templates | None = None
ARQUIVO = Path(__file__).resolve().parent.parent / "apuracao" / "data" / "arquivo" / "2026-1t"
ANO = 2026
CARGO_MUN = {"est": "c0007", "fed": "c0006"}
_trava = threading.Lock()      # uma conexão SQLite só, e o worker é um só


def set_templates(t: Jinja2Templates) -> None:
    global _templates
    _templates = t


def _guarda(user: dict) -> None:
    if not can_access(user, "politicos"):
        raise HTTPException(status_code=404)


def _json(dados, request: Request | None = None, etag: str | None = None) -> Response:
    cab = {"Cache-Control": "private, max-age=300"}
    if etag:
        cab["ETag"] = etag
        if request is not None and request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=cab)
    return JSONResponse(dados, headers=cab)


_versao = {"v": None}


def _conferir_versao() -> None:
    """Importação nova (o boletim de urna de 2026, por exemplo) invalida o que a
    análise guardou em memória — sem isso o site seguiria dizendo "sem seções"
    até reiniciar."""
    try:
        v = ae._c().execute("SELECT MAX(feito_em) FROM importacao").fetchone()[0]
    except Exception:  # noqa: BLE001
        v = None
    if v != _versao["v"]:
        if _versao["v"] is not None:
            ae.limpar_cache()
        _versao["v"] = v


async def _analise(fn, *args):
    def rodar():
        with _trava:
            _conferir_versao()
            return fn(*args)
    if not ae.disponivel():
        raise HTTPException(status_code=503, detail="microdados ainda não importados")
    return await run_in_threadpool(rodar)


@router.get("", response_class=HTMLResponse)
async def pagina(request: Request, user: dict = Depends(require_login)):
    _guarda(user)
    return _templates.TemplateResponse(request, "politicos_eleicao.html", {
        "user": user, "is_admin": user.get("role") == "admin", "ano": ANO,
    })


# ── o arquivo da noite (o mesmo formato que a página pública lia) ──────────
_cache: dict[Path, tuple[int, bytes, str]] = {}


def _arquivo(request: Request, nome: str) -> Response:
    caminho = ARQUIVO / nome
    try:
        mt = caminho.stat().st_mtime_ns
    except OSError:
        raise HTTPException(status_code=404)
    guardado = _cache.get(caminho)
    if not guardado or guardado[0] != mt:
        guardado = (mt, caminho.read_bytes(), f'"{mt:x}"')
        _cache[caminho] = guardado
    _mt, corpo, etag = guardado
    cab = {"ETag": etag, "Cache-Control": "private, max-age=3600"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cab)
    return Response(corpo, media_type="application/json", headers=cab)


@router.get("/dados/estado.json")
async def estado(request: Request, user: dict = Depends(require_login)):
    _guarda(user)
    return _arquivo(request, "estado.json")


@router.get("/dados/majoritarias.json")
async def majoritarias(request: Request, user: dict = Depends(require_login)):
    _guarda(user)
    return _arquivo(request, "majoritarias.json")


@router.get("/dados/eleitos.json")
async def eleitos(request: Request, user: dict = Depends(require_login)):
    _guarda(user)
    return _arquivo(request, "eleitos.json")


@router.get("/dados/uf/{uf}.json")
async def por_uf(uf: str, request: Request, user: dict = Depends(require_login)):
    _guarda(user)
    uf = uf.lower()
    if len(uf) != 2 or not uf.isalpha():
        raise HTTPException(status_code=404)
    return _arquivo(request, f"uf/{uf}.json")


@router.get("/dados/municipios.json")
async def municipios(request: Request, user: dict = Depends(require_login)):
    _guarda(user)
    lista = await _analise(lambda: sorted(({"cd": str(m["cd"]), "nm": m["nome"]} for m in ae._municipios().values()),
                                          key=lambda x: x["nm"]))
    return _json(lista)


@router.get("/dados/municipio/{cd}.json")
async def municipio_tse(cd: str, request: Request, cargo: str = "est", user: dict = Depends(require_login)):
    """O município como o TSE o publicou (guardado na importação; não vai à rede)."""
    _guarda(user)
    from apuracao import estado as est
    if cargo not in CARGO_MUN or not cd.isdigit():
        raise HTTPException(status_code=404)
    arq = microdados.BRUTOS_2026 / CARGO_MUN[cargo] / f"{cd}.json.gz"

    def ler():
        d = est.municipal(json.loads(gzip.decompress(arq.read_bytes())))
        with _trava:
            d["municipio"] = {"cd": cd, "nome": ae._municipios().get(int(cd), {}).get("nome", cd)}
        return d
    if not arq.exists():
        raise HTTPException(status_code=404)
    return _json(await run_in_threadpool(ler))


# ── análises (microdados) ──────────────────────────────────────────────────
def _cargo(cargo: int) -> int:
    if cargo not in microdados.CARGOS:
        raise HTTPException(status_code=404)
    return cargo


def _ano(ano: int) -> int:
    if ano not in (2022, 2026):
        raise HTTPException(status_code=404)
    return ano


@router.get("/dados/candidatos.json")
async def candidatos(request: Request, ano: int = ANO, cargo: int = 7, user: dict = Depends(require_login)):
    _guarda(user)
    return _json(await _analise(ae.lista_candidatos, _ano(ano), _cargo(cargo)))


@router.get("/dados/candidato.json")
async def candidato(request: Request, n: int, ano: int = ANO, cargo: int = 7, user: dict = Depends(require_login)):
    _guarda(user)
    r = await _analise(ae.raio_x, _ano(ano), _cargo(cargo), n)
    if r is None:
        raise HTTPException(status_code=404)
    return _json(r)


@router.get("/dados/cidade.json")
async def cidade(request: Request, cd: int, ano: int = ANO, cargo: int = 7, user: dict = Depends(require_login)):
    _guarda(user)
    r = await _analise(ae.municipio, _ano(ano), _cargo(cargo), cd)
    if r is None:
        raise HTTPException(status_code=404)
    return _json(r)


@router.get("/dados/partido.json")
async def partido(request: Request, a: str, ano: int = ANO, cargo: int = 7, user: dict = Depends(require_login)):
    _guarda(user)
    r = await _analise(ae.partido, _ano(ano), _cargo(cargo), a)
    if r is None:
        raise HTTPException(status_code=404)
    return _json(r)


@router.get("/dados/locais.json")
async def locais(request: Request, cd: int, n: int | None = None, a: str | None = None, ano: int = ANO,
                 cargo: int = 7, user: dict = Depends(require_login)):
    _guarda(user)
    if n is None and not a:
        raise HTTPException(status_code=400, detail="informe o candidato (n) ou a agremiação (a)")
    r = await _analise(ae.locais, _ano(ano), _cargo(cargo), n, cd, a)
    return _json(r if r is not None else {"indisponivel": True})


@router.get("/dados/perfil.json")
async def perfil(request: Request, n: int, ano: int = ANO, cargo: int = 7, user: dict = Depends(require_login)):
    _guarda(user)
    r = await _analise(ae.perfil, _ano(ano), _cargo(cargo), n)
    return _json(r if r is not None else {"indisponivel": True})


@router.get("/dados/situacao.json")
async def situacao(request: Request, user: dict = Depends(require_login)):
    """O que já foi importado (e o que ainda espera o TSE publicar)."""
    _guarda(user)
    return _json(await _analise(lambda: microdados.situacao(ae._c())))


@router.get("/dados/lideres.json")
async def lideres(request: Request, ano: int = ANO, cargo: int = 7, user: dict = Depends(require_login)):
    _guarda(user)
    return _json(await _analise(ae.lideres, _ano(ano), _cargo(cargo)))


# ── previsão (só admin, como a aba Previsão × resultado do /politicos) ─────
def _guarda_admin(user: dict) -> None:
    _guarda(user)
    if user.get("role") != "admin":
        raise HTTPException(status_code=404)


_proxima: dict = {"chave": None, "valor": None}


@router.get("/dados/modelo.json")
async def modelo_json(request: Request, user: dict = Depends(require_login)):
    """O algoritmo v2: comparação das variantes fora da amostra e os pesos."""
    _guarda_admin(user)
    from politicos import modelo
    m = await run_in_threadpool(modelo.carregar)
    if not m:
        return _json({"indisponivel": True})
    return _json({"versao": m["versao"], "criado_em": m["criado_em"], "n": m["n"], "treino": m["treino"],
                  "comparacao": m["comparacao"],
                  "pesos": {k: v["pesos"] for k, v in m["modelos"].items()},
                  "descricao": modelo.DESCRICAO})


@router.get("/dados/proxima.json")
async def proxima_json(request: Request, user: dict = Depends(require_login)):
    """A próxima ALESC se fosse hoje (muda quando o monitor de redes coleta)."""
    _guarda_admin(user)
    from datetime import date
    from politicos import modelo

    def calcular():
        from politicos import db
        con = db.conectar()
        try:
            ultima = con.execute("SELECT MAX(quando) q FROM gastos").fetchone()["q"]
        finally:
            con.close()
        chave = (date.today().isoformat(), ultima, (modelo.carregar() or {}).get("id"))
        if _proxima["chave"] != chave:
            with _trava:
                r = modelo.proxima()
                if r:
                    for c in r["candidatos"]:
                        c["ac"], c["cor"] = ae.curta(c["agremiacao"]), ae.cor(c["agremiacao"])
                    r["listas"] = [{"a": a, "ac": ae.curta(a), "cor": ae.cor(a), "cadeiras": n}
                                   for a, n in sorted(r["cadeiras"].items(), key=lambda kv: -kv[1]) if n]
                _proxima.update(chave=chave, valor=r)
        return _proxima["valor"]
    r = await run_in_threadpool(calcular)
    return _json(r if r else {"indisponivel": True})


@router.get("/raio-x.pdf")
async def raio_x_pdf(request: Request, n: int, ano: int = ANO, cargo: int = 7, user: dict = Depends(require_login)):
    """O raio-x do candidato em PDF (duas páginas A4)."""
    _guarda(user)
    from politicos import raio_x_pdf as rx
    r = await _analise(rx.gerar, _ano(ano), _cargo(cargo), n)
    if not r:
        raise HTTPException(status_code=404)
    corpo, nome = r
    return Response(corpo, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{nome}"', "Cache-Control": "private, max-age=300"})
