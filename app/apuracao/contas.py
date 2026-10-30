"""As contas do 2º turno — UM lugar para cada identidade.

Este módulo existe porque a mesma fórmula estava escrita em três arquivos
(`explicacao.py`, `cenarios.py`, `simulador.py`) e as três podiam divergir. Foi
assim que o bug dos 5.246 votos do número 28 passou despercebido: cada módulo
classificava "voto válido" por conta própria.

Aqui só entram **identidades contábeis** — coisas que o TSE garante e que dão o
mesmo número não importa por onde se chegue. Estimativa não mora aqui.

As quatro grandezas, todas derivadas dos totais oficiais:

    novos_válidos  = válidos(2T) - válidos(1T)
                   = (comparecimento que subiu) + (branco que virou voto) + (nulo que virou voto)

    terceira_via   = válidos(1T) - votos(Lula,1T) - votos(Flavio,1T)

    ganho(Lula)    = votos(Lula,2T) - votos(Lula,1T)
    ganho(Flavio)  = votos(Flavio,2T) - votos(Flavio,1T)

E a identidade que amarra tudo — é ela que a tela usa para dizer "fecha no voto":

    novos_válidos + terceira_via = ganho(Lula) + ganho(Flavio)

O **piso da terceira via** é a consequência mais útil. Como o Lula não pode ter
recebido mais que 100% dos votos novos:

    p·novos + q·terceira = ganho(Lula),  com p ≤ 1
    =>  q ≥ (ganho(Lula) - novos) / terceira

e isso NÃO é estimativa: é o limite inferior que a aritmética impõe.
"""
from __future__ import annotations

import json
from pathlib import Path


def _i(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def totais(explicacao: dict) -> dict:
    """Todos os números de referência, a partir do `explicacao.json`."""
    nac = explicacao.get("nacional") or {}
    n1 = nac.get("t1") or {}
    n2 = nac.get("t2") or {}
    lula1, lula2 = _i(n1.get("lula")), _i(n2.get("lula"))
    flavio1, flavio2 = _i(n1.get("flavio")), _i(n2.get("flavio"))
    validos1, validos2 = _i(n1.get("validos")), _i(n2.get("validos"))
    comp1, comp2 = _i(n1.get("comp")), _i(n2.get("comp"))
    br1, br2 = _i(n1.get("brancos")), _i(n2.get("brancos"))
    nu1, nu2 = _i(n1.get("nulos")), _i(n2.get("nulos"))

    novos = validos2 - validos1
    terceira = validos1 - lula1 - flavio1
    ganho_lula = lula2 - lula1
    ganho_flavio = flavio2 - flavio1

    # As três origens dos votos novos. Somam `novos` por identidade; se a fonte
    # mudar (outra eleição), a soma fica como veio e a tela avisa.
    voltaram = comp2 - comp1
    de_branco = br1 - br2
    de_nulo = nu1 - nu2

    return {
        # votos de cada candidato nos dois turnos
        "lula1": lula1, "lula2": lula2, "flavio1": flavio1, "flavio2": flavio2,
        # o resto do comparecimento
        "validos1": validos1, "validos2": validos2,
        "comp1": comp1, "comp2": comp2,
        "brancos1": br1, "brancos2": br2, "nulos1": nu1, "nulos2": nu2,
        # derivadas
        "novos_validos": novos,
        "terceira_via": terceira,
        "ganho_lula": ganho_lula,
        "ganho_flavio": ganho_flavio,
        "novos_origens": {"abstencao": voltaram, "branco": de_branco, "nulo": de_nulo},
        "origens_fecham": voltaram + de_branco + de_nulo == novos,
        "margem": lula2 - flavio2,
    }


def piso_terceira(t: dict) -> dict:
    """O mínimo que a terceira via teve de dar ao Lula. Limite DURO.

    Supõe o melhor caso possível para o Lula: 100% dos votos novos para ele.
    O que faltar para fechar o ganho dele só pode ter vindo da terceira via.
    """
    novos, terc, gl = t["novos_validos"], t["terceira_via"], t["ganho_lula"]
    if not terc:
        return {"fracao": 0.0, "votos": 0, "p_necessario_se_zero": 0.0, "zero_impossivel": False}
    fracao = max(0.0, (gl - novos) / terc)
    fracao = min(1.0, fracao)
    p_se_zero = (gl / novos) if novos else 0.0
    return {
        "fracao": round(fracao, 6),
        "votos": round(fracao * terc),
        # Se a terceira via fosse toda para o Flavio, o Lula precisaria desta
        # fração dos votos novos. Passar de 1 é a prova do absurdo.
        "p_necessario_se_zero": round(p_se_zero, 4),
        "zero_impossivel": p_se_zero > 1.0,
    }


def fecha(t: dict) -> dict:
    """A identidade que a tela exibe: fontes = destinos, no voto."""
    fontes = t["novos_validos"] + t["terceira_via"]
    destinos = t["ganho_lula"] + t["ganho_flavio"]
    return {"fontes": fontes, "destinos": destinos,
            "dif": fontes - destinos, "fecha": fontes == destinos}


def conferir(t: dict) -> list[str]:
    """Problemas que o dado traria. Vazio = tudo consistente.

    Roda na migração e no teste; é o que impede o bug dos 5.246 votos (nulos do
    número 28 contados como válidos) de passar em silêncio de novo.
    """
    achados = []
    if not t["origens_fecham"]:
        o = t["novos_origens"]
        achados.append(
            f"as três origens dos votos novos somam {o['abstencao'] + o['branco'] + o['nulo']:,}, "
            f"mas novos_validos = {t['novos_validos']:,}")
    f = fecha(t)
    if not f["fecha"]:
        achados.append(
            f"fontes ({f['fontes']:,}) != destinos ({f['destinos']:,}) — diferença de {f['dif']:+,}")
    if t["terceira_via"] < 0:
        achados.append("terceira via negativa: os dois candidatos têm mais votos que os válidos")
    return achados


def carregar(base: Path) -> dict:
    """Os totais a partir da pasta congelada."""
    dados = json.loads((base / "explicacao.json").read_text(encoding="utf-8"))
    return totais(dados)
