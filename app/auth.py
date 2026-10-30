"""Substituto do auth.py do V2.

Dois modos (variável SITE_MODO, ver main.py):

- `publico` (estranhaeleicao.org): ninguém loga; as telas internas nunca aparecem.
- `completo` (arquivo privado no familiacaue): HTTP Basic com o usuário e o hash
  em ARQUIVO_USUARIO / ARQUIVO_SENHA_SHA256 (.env, fora do git). Quem passa é
  admin — o arquivo é de uma pessoa só.

O router da apuração e o resultados.py vieram do V2 sem mudança; eles só
precisam de current_user, require_login, can_access e get_real_ip.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

from fastapi import HTTPException, Request

MODO = os.environ.get("SITE_MODO", "publico")
_USUARIO = os.environ.get("ARQUIVO_USUARIO", "")
_SENHA_SHA256 = os.environ.get("ARQUIVO_SENHA_SHA256", "")


def _basic(request: Request) -> str | None:
    if MODO != "completo" or not (_USUARIO and _SENHA_SHA256):
        return None
    cab = request.headers.get("authorization", "")
    if not cab.lower().startswith("basic "):
        return None
    try:
        usuario, _, senha = base64.b64decode(cab[6:]).decode("utf-8").partition(":")
    except (ValueError, UnicodeDecodeError):
        return None
    ok_u = hmac.compare_digest(usuario, _USUARIO)
    ok_s = hmac.compare_digest(hashlib.sha256(senha.encode()).hexdigest(), _SENHA_SHA256)
    return usuario if ok_u and ok_s else None


def current_user(request: Request):
    nome = _basic(request)
    return {"username": nome, "role": "admin"} if nome else None


def require_login(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": 'Basic realm="apuracao"'})
    return user


def can_access(user, app_key: str) -> bool:
    return bool(user)


def get_real_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    # Só o cloudflared (mesma máquina, rede do host) pode dizer o IP real.
    if peer in ("127.0.0.1", "::1"):
        for header in ("cf-connecting-ip", "x-forwarded-for", "x-real-ip"):
            val = request.headers.get(header)
            if val:
                return val.split(",")[0].strip()[:80]
    return peer[:80]
