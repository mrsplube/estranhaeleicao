"""Extrai o resumo dos casos de `static/estranha.js` para o HTML servido.

    venv/bin/python -m tools.migracoes.2026-10-31-casos-resumo        (de app/)

## Por que existe

Até 31/10/2026 a página inicial entregava 300 palavras de texto ao robô: os 27
casos inteiros eram montados no navegador, a partir do `estranha.js`. O Google
até executa JavaScript, mas em fila e sem garantia de quando — e para uma
página cujo valor é justamente o texto, depender disso é abrir mão do índice.

Este script lê o `estranha.js` (a fonte única, onde o texto dos casos mora) e
grava `apuracao/data/arquivo/2026-2t/casos_resumo.json`, que `main.py` usa no
template. O navegador continua montando os cartões interativos; o HTML passa a
ter também um resumo legível — para o robô e para quem abre a página com o
JavaScript bloqueado.

O resumo NÃO é conteúdo escondido: ele aparece na página, acima dos cartões.
Marcar no HTML um texto que só o robô vê seria cloaking.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "static/estranha.js"
DESTINO = RAIZ / "apuracao/data/arquivo/2026-2t/casos_resumo.json"

# A ordem em que os casos são declarados no JS é a ordem em que a página os
# mostra (casos()), e é ela que o resumo tem de respeitar.
RE_CASO = re.compile(r'id: "([\w-]+)", titulo: "([^"]*)", tag: "(\w+)"')


def _texto(seg: str, campo: str) -> str:
    """O valor de um campo de string do objeto, já sem os pedaços de código."""
    m = re.search(campo + r':\s*', seg)
    if not m:
        return ""
    # Pega a EXPRESSÃO inteira do campo, não só a primeira string: o JS monta
    # com concatenação ("Em " + f2.zeradas + " urnas, ninguém..."), e parar na
    # primeira aspa fechava a frase no meio ("Em"). O fim é a linha do campo,
    # que é onde a vírgula separa de `fontes:`/`veredito:`.
    resto = seg[m.end():]
    bruto = resto.split("\n", 1)[0].rstrip().rstrip(",")
    # Cada pedaço de código entre aspas vira um marcador, em vez de sumir.
    bruto = re.sub(r'"\s*\+\s*[^+"]+?\s*\+\s*"', "…", bruto)
    bruto = re.sub(r'"\s*\+\s*[^+"]+?\s*\+\s*"', "…", bruto)   # pares encadeados
    bruto = re.sub(r'"\s*\+\s*[^+"]+?$', "…", bruto)
    bruto = re.sub(r'^[^"]*?\+', "", bruto, count=1) if not bruto.startswith('"') else bruto
    bruto = bruto.replace('"', "")
    bruto = bruto.replace('\\"', '"').replace("\\'", "'")
    bruto = re.sub(r"<[^>]+>", "", bruto)          # tira <b>, <a> etc.
    bruto = re.sub(r"\s+", " ", bruto).strip()
    bruto = re.sub(r"(\s*…\s*)+", " … ", bruto).strip()
    return bruto


# Os valores que o JS interpola por código (não por literal) e que fazem parte
# da AFIRMAÇÃO — a alegação precisa dizer o número que o vídeo mostra. Sem isso
# o resumo sairia com "Lula … e Flávio …", que não é afirmação nenhuma.
# Calculados do próprio acusacoes.json (v. `_numeros()`), não digitados à mão.
def _numeros() -> dict[str, list[str]]:
    import json
    d = json.loads((RAIZ / "apuracao/data/arquivo/2026-2t/acusacoes.json").read_text(encoding="utf-8"))
    dona = next(v["dona"] for v in d["zonas"]["video"] if v.get("onde") == "tela" and len(v.get("zonas", [])) > 1)
    f2 = d["secoes_ate_10"]["flavio_2t"]
    mil = lambda n: f"{n:,}".replace(",", ".")
    return {
        "zonas": [mil(dona["l"]), mil(dona["f"])],
        "secoes-10": [str(f2["zeradas"]), mil(f2["secoes"])],
        # "1 contra N": o Lula em Silva Jardim foi de t1 para t2.
        "silva-jardim": [mil(d["silva_jardim"]["municipio"]["t2"]["lula"] - d["silva_jardim"]["municipio"]["t1"]["lula"])],
    }


def extrair() -> list[dict]:
    js = FONTE.read_text(encoding="utf-8")
    casos = []
    marcas = list(RE_CASO.finditer(js))
    numeros = _numeros()
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(js)
        seg = js[m.end():fim]
        cid = m.group(1)
        alegacao = _texto(seg, "alegacao")
        for valor in numeros.get(cid, []):
            alegacao = alegacao.replace("…", valor, 1)
        casos.append({
            "id": cid,
            "titulo": m.group(2),
            "tag": m.group(3),
            "alegacao": alegacao,
            "veredito": _texto(seg, "veredito"),
        })
    return casos


def main() -> None:
    casos = extrair()
    if len(casos) < 20:
        raise SystemExit(f"extraiu só {len(casos)} casos — o formato do estranha.js mudou?")
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(casos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(casos)} casos → {DESTINO.relative_to(RAIZ)}")
    for c in casos[:3]:
        print(f"  {c['id']:16} {c['titulo'][:40]:42} | {c['alegacao'][:60]}")


if __name__ == "__main__":
    main()
