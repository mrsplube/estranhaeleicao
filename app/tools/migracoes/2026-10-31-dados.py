"""Catálogo de dados do site, para a página /dados.

    venv/bin/python -m tools.migracoes.2026-10-31-dados

## Por que existe

O site publica o resultado de cada conta em JSON — é o que sustenta a promessa
de "qualquer pessoa pode conferir". Mas ninguém encontrava esses arquivos: eles
só apareciam citados de passagem no `noscript` da entrada. Uma página que lista
o que existe, com fonte, data e o que cada arquivo responde, é o que faz um
pesquisador (ou um jornalista) usar o dado e citar o site.

O catálogo NÃO é digitado à mão: cada entrada é conferida contra o arquivo real
— se o JSON não existe ou não abre, a entrada sai do catálogo em vez de virar
um link quebrado. `gerado_em` e a contagem de registros vêm do próprio arquivo.
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "apuracao/data/arquivo/2026-2t"
ESTATICOS = RAIZ / "static"
DESTINO = ARQUIVO / "dados_catalogo.json"

# (arquivo, url pública, o que responde). SÓ entra aqui o que o site serve de
# fato — cada URL é conferida contra o servidor por `main()`, e a que não
# responder 200 sai do catálogo em vez de virar link quebrado.
CATALOGO = [
    ("acusacoes.json", "/apuracao/explicacao/acusacoes.json",
     "Os números de cada caso: as 106 urnas zeradas, a seção de 700 votos, a curva da apuração, a biometria e os municípios. É o insumo dos 27 casos da entrada."),
    ("analise.json", "/apuracao/explicacao/analise.json",
     "O plano dos testes estatísticos das acusações (pré-registrado em 01/11/2026) e o resultado de cada teste, conforme rodam."),
    ("c1.json", "/apuracao/explicacao/c1.json",
     "Teste C1 do pré-registro: seções com o Flávio até 10 votos contra o esperado pelo 1º turno da mesma seção, com 2022 de referência e as 54 especificações do multiverso."),
    ("c2.json", "/apuracao/explicacao/c2.json",
     "Teste C2 do pré-registro: municípios cujo 2º turno foge do previsto pelo 1º, com correção de Benjamini–Hochberg, 2022 de referência e as 24 especificações do multiverso."),
    ("c3.json", "/apuracao/explicacao/c3.json",
     "Teste C3 do pré-registro: o modelo de Klimek et al. (2012) para enchimento de urna e a inclinação de Myagkov et al. (2009), em 2026, 2022 e no governador de 2026, com o multiverso."),
    ("reconciliacao.json", "/apuracao/explicacao/reconciliacao.json",
     "As 499.205 seções do 2º turno cruzadas em três arquivos do TSE (Boletim de Urna, votação por seção e detalhe) e somadas contra o total oficial: divergências, hash SHA-512 de cada boletim, origem do voto e horário de encerramento."),
    ("conta.json", "/apuracao/explicacao/conta.json",
     "A conta do 2º turno município a município: de onde vieram os votos de cada candidato da terceira via, com intervalo de confiança por candidato."),
    ("chute.json", "/apuracao/explicacao/chute.json",
     "O eleitorado do 1º turno em 9 grupos, com o voto de cada grupo no 2º turno segundo as pesquisas citadas. É o insumo do simulador."),
    ("casos_videos.json", "/apuracao/explicacao/casos_videos.json",
     "Os vídeos citados em cada caso: perfil, link, curtidas e as fontes de checagem de cada afirmação."),
    ("municipios.json", "/apuracao/explicacao/municipios.json",
     "O resultado por município, com o voto de cada candidato e o nome de urna, para cruzar com o dado por seção."),
    ("biometria.json", "/static/casos/biometria.json",
     "Quantos eleitores votaram sem a digital reconhecida, por estado e por eleição (2022 e os dois turnos de 2026). Vem do Boletim de Urna do TSE."),
    ("virada.json", "/static/casos/virada.json",
     "A geografia da virada: a Região dos Lagos seção a seção, o cruzamento com a biometria e as cidades que viraram por partido do prefeito."),
    ("@static:casos/polymarket.json", "/static/casos/polymarket.json",
     "A série de preços da Polymarket para a eleição brasileira, de 1º de setembro à noite do 2º turno, de 5 em 5 minutos no dia da votação."),
    ("@static:casos/lados.json", "/static/casos/lados.json",
     "O argumento de quem acusa, a resposta de quem defende e a decisão, para cada um dos 27 casos."),
]


def _url_viva(url: str) -> bool:
    """O servidor local responde 200 nesta URL? (evita link quebrado no catálogo)"""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:3030" + url, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def _conta(d: dict) -> int | None:
    """Quantos registros o arquivo tem, quando isso é óbvio."""
    for chave in ("candidatos", "eleicoes", "municipios", "grupos", "casos"):
        v = d.get(chave)
        if isinstance(v, list):
            return len(v)
    return None


def _fontes(fonte) -> list[dict]:
    """A fonte de cada arquivo como lista de {texto, url}.

    `fonte` aparece de três jeitos nos JSON: texto ("Boletim de Urna..."),
    dicionário ({"secoes": URL, "secoes_gerado_em": data}) ou nulo. Antes isto
    era `str(fonte)`, e o dicionário saía impresso como link em /dados. Agora só
    vira link o que é URL; datas e rótulos ficam como texto.
    """
    if not fonte:
        return []
    if isinstance(fonte, str):
        itens = [fonte]
    elif isinstance(fonte, dict):
        itens = [v for k, v in fonte.items() if isinstance(v, str) and not k.endswith("gerado_em")]
    else:
        return []
    saida = []
    for v in itens:
        url = v if v.startswith("http") else None
        # "resultados.tse.jus.br/oficial/..." é URL sem esquema.
        if url is None and " " not in v and v.split("/")[0].endswith(".jus.br"):
            url = "https://" + v
        saida.append({"texto": v, "url": url})
    return saida


def montar(verificar: bool = True) -> list[dict]:
    saida = []
    vistos = set()
    for nome, url, descricao in CATALOGO:
        if url in vistos:
            continue
        vistos.add(url)
        # `@static:...` aponta para static/ (gráficos e lados), o resto mora no
        # arquivo do 2º turno.
        caminho = (ESTATICOS / nome.split(":", 1)[1]) if nome.startswith("@static:") else (ARQUIVO / nome)
        nome = nome.split(":", 1)[-1].split("/")[-1]
        if not caminho.exists():
            # O catálogo não pode apontar para arquivo que não existe.
            print(f"  (fora: {nome} não existe)")
            continue
        try:
            d = json.loads(caminho.read_text(encoding="utf-8"))
        except ValueError as e:
            print(f"  (fora: {nome} não é JSON válido — {e})")
            continue
        if verificar and not _url_viva(url):
            # O catálogo promete que a URL funciona; se o servidor não serve
            # este arquivo, a entrada sai. Melhor um catálogo menor que um link
            # quebrado numa página feita para dar credibilidade.
            print(f"  (fora: {url} não responde 200 no servidor)")
            continue
        # Alguns arquivos são objeto, outros são lista pura (casos_resumo.json,
        # municipios.json). Os metadados só existem no caso do objeto.
        meta = d if isinstance(d, dict) else {}
        saida.append({
            "nome": nome,
            "url": url,
            "o_que": descricao,
            "gerado_em": str(meta.get("gerado_em") or "")[:10],
            "fontes": _fontes(meta.get("fonte")),
            "registros": _conta(d) if isinstance(d, dict) else len(d),
            "tamanho": caminho.stat().st_size,
        })
    return saida


def main() -> None:
    dados = montar()
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(dados)} conjuntos → {DESTINO.relative_to(RAIZ)}")
    for d in dados:
        print(f"  {d['nome']:22} {d['tamanho']/1024:7.0f} KB  {d['url']}")


if __name__ == "__main__":
    main()
