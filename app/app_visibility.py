"""Substituto do app_visibility.py do V2.

O interruptor público do /admin virou variável de ambiente: com
APURACAO_ARQUIVADA=1 o /apuracao mostra a página "encerrada" a quem não está
logado (era o estado do V2 entre eleições). Sem ela, a página é pública.
"""
import os


def is_visible(app_key: str, role: str) -> bool:
    return not os.environ.get("APURACAO_ARQUIVADA")
