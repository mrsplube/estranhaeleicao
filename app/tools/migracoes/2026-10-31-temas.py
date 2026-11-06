"""Temas e subtítulos pesquisáveis dos casos (31/10/2026).

    venv/bin/python -m tools.migracoes.2026-10-31-temas

## Por que existe

Duas coisas do SEO que o site não tinha:

1. **Subtítulo pesquisável.** Os títulos dos cartões são bons de ler e ruins de
   buscar: ninguém digita "o mesário pianista" no Google. `BUSCA` dá a cada caso
   a frase que a pessoa realmente digita, e ela entra como subtítulo na lista em
   texto (o cartão interativo continua com o título de sempre).

2. **Página por tema.** Tudo mora numa URL só, e uma URL não rankeia para 27
   assuntos. `TEMAS` agrupa os casos em seis páginas com pergunta própria —
   cada uma com o texto completo dos casos que a respondem.

Grava `temas.json`, que `main.py` usa no template `tema.html`.
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "apuracao/data/arquivo/2026-2t"
DESTINO = ARQUIVO / "temas.json"

# A frase que a pessoa digita. Não é slogan: é a consulta, escrita como alguém
# escreveria na barra do navegador.
BUSCA = {
    "silva-jardim": "Cidades onde o Flávio perdeu votos entre os turnos: a conta fecha?",
    "mesma-secao": "Flávio fez 700 votos e depois 8 na mesma seção?",
    "zonas": "O mesmo placar em todas as zonas eleitorais: é fraude?",
    "secoes-10": "106 urnas sem nenhum voto para Flávio: é fraude?",
    "curva": "O gráfico da apuração mostra fraude? O que o vídeo esconde",
    "virada": "A virada do Lula no 2º turno é inédita? Foi fraude?",
    "pesquisas": "As pesquisas erraram o resultado de 2026?",
    "biometria": "8,6 milhões de votos sem biometria: o que aconteceu?",
    "mesario": "Mesário pode votar no lugar do eleitor?",
    "caminhonete": "Urnas na caminhonete com adesivo do PT: houve fraude?",
    "consulta": "Por que a consulta de quem votou saiu do ar?",
    "sala-cofre": "Fiscais do PL foram expulsos da sala-cofre do TSE?",
    "soma": "A soma dos estados não bate com o total do Brasil?",
    "cedula": "Voto em cédula de papel em 2026: existe?",
    "eleitores": "Cidade com mais eleitores que habitantes: é fraude?",
    "prorrogacao": "Por que a votação foi prorrogada até as 19h?",
    "onibus": "Faltou ônibus em Salvador no dia da votação?",
    "desfile": "O desfile da escola de samba para o Lula foi abuso?",
    "pacote": "O pacote de medidas do governo antes da eleição é abuso?",
    "maquina-celular": "O governo usou o WhatsApp do Gov.br para pedir voto?",
    "exercito": "O canal do Janones coordenava fake news contra o Flávio?",
    "universidades": "Universidades públicas viraram comitê de campanha?",
    "mesaria": "Mesária fazendo campanha dentro da seção: aconteceu?",
    "faccoes": "O PCC e o Comando Vermelho apoiaram o Lula?",
    "desinformacao": "A Justiça Eleitoral mandou apagar conteúdo de quem?",
    "compra": "Houve compra de votos em massa em 2026?",
    "padroeira": "Lula insistiu na fake news da padroeira?",
    "impossivel": "Flávio diz que a eleição foi matematicamente impossível: a conta fecha?",
    "camera-coberta": "Câmera coberta na seção eleitoral: é fraude?",
}

# Cada tema vira uma URL própria. A ordem importa: é a ordem dos links no
# índice de temas (que hoje não existe — as páginas são órfãs de propósito).
TEMAS = [
    {
        "slug": "fraude-nas-urnas",
        "titulo": "As urnas foram fraudadas em 2026?",
        "h1": "As urnas <br><span>foram fraudadas?</span>",
        "tag": "fraude na contagem",
        "descricao": "As teorias de fraude na urna e na apuração de 2026, cada uma conferida no dado do TSE: o gráfico da apuração, a soma que não fecha, a urna na caminhonete e as 106 urnas zeradas.",
        "intro": "As acusações que apontam para a urna, para a transmissão ou para a soma dos votos. Cada uma tem o número que a sustenta e o que o dado do TSE mostra.",
        "casos": ["secoes-10", "curva", "soma", "mesma-secao", "zonas", "sala-cofre", "caminhonete", "cedula", "eleitores", "camera-coberta"],
    },
    {
        "slug": "biometria",
        "titulo": "8,6 milhões de votos sem biometria: é fraude?",
        "h1": "8,6 milhões <br><span>sem biometria</span>",
        "tag": "voto sem digital",
        "descricao": "O que são os 8,6 milhões de votos sem biometria citados pelo relatório, por que a taxa caiu em relação a 2022 e por que isso não muda o resultado.",
        "intro": "O número que o relatório apresentou como prova de fraude, conferido seção a seção no Boletim de Urna do TSE — e comparado com 2022 e com o 1º turno.",
        "casos": ["biometria"],
    },
    {
        "slug": "virada-do-2-turno",
        "titulo": "A virada do Lula no 2º turno foi possível sem fraude?",
        "h1": "A virada <br><span>do 2º turno</span>",
        "tag": "a virada",
        "descricao": "A virada inédita de 2026, a geografia dela e o erro das pesquisas: os números conferem e a conta fecha sem nenhum voto inventado.",
        "intro": "Pela primeira vez desde 1989, quem perdeu o 1º turno ganhou o 2º. É raro, é estranho, e a conta fecha — aqui está como.",
        "casos": ["virada", "impossivel", "pesquisas", "silva-jardim"],
    },
    {
        "slug": "prorrogacao",
        "titulo": "Por que a votação foi prorrogada até as 19h?",
        "h1": "A votação <br><span>até as 19h</span>",
        "tag": "prorrogação",
        "descricao": "A prorrogação determinada pelo STF no 2º turno de 2026, os 34.393 votos depois das 17h e a falta de ônibus em Salvador: o que aconteceu e o que não aconteceu.",
        "intro": "A decisão da meia hora final virou o argumento mais repetido. Os números do que entrou depois das 17h estão medidos, e são pequenos.",
        "casos": ["prorrogacao", "onibus"],
    },
    {
        "slug": "mesario",
        "titulo": "Mesário pode votar no lugar do eleitor?",
        "h1": "Mesário vota <br><span>no seu lugar?</span>",
        "tag": "mesário e caderno",
        "descricao": "O que impede um mesário de votar no lugar de outro eleitor, os casos que existiram em 2026 e por que eles não somam milhões de votos.",
        "intro": "A acusação existe e tem caso real. O que ela não tem é escala: o caminho do voto em nome de outra pessoa deixa rastro, e o rastro está no dado.",
        "casos": ["mesario", "mesaria", "consulta"],
    },
    {
        "slug": "campanha-e-governo",
        "titulo": "Abuso de poder e máquina pública na eleição de 2026",
        "h1": "Campanha <br><span>e governo</span>",
        "tag": "abuso de poder",
        "descricao": "As denúncias sobre o uso da máquina pública e da campanha em 2026: o pacote de medidas, as mensagens do Gov.br, o canal do Janones, as universidades e a compra de votos.",
        "intro": "As denúncias que não são sobre a urna, e sim sobre a campanha: uso do governo, desinformação, transporte e compra de voto. Quase nada aqui tem julgamento final.",
        "casos": ["pacote", "maquina-celular", "exercito", "universidades", "desfile", "faccoes", "desinformacao", "compra", "padroeira"],
    },
]


def main() -> None:
    casos = json.loads((ARQUIVO / "casos_resumo.json").read_text(encoding="utf-8"))
    lados = json.loads((RAIZ / "static/casos/lados.json").read_text(encoding="utf-8"))["casos"]
    por_id = {c["id"]: c for c in casos}

    # Subtítulo pesquisável vai para o casos_resumo.json, que a entrada usa.
    faltando = [c["id"] for c in casos if c["id"] not in BUSCA]
    if faltando:
        raise SystemExit(f"caso sem subtítulo de busca: {faltando}")
    for c in casos:
        c["busca"] = BUSCA[c["id"]]
    (ARQUIVO / "casos_resumo.json").write_text(
        json.dumps(casos, ensure_ascii=False, indent=1), encoding="utf-8")

    # Página por tema, com o texto inteiro de cada caso que a responde.
    usados = set()
    temas = []
    for t in TEMAS:
        itens = []
        for cid in t["casos"]:
            c = por_id.get(cid)
            if not c:
                print(f"  (fora: {cid} não existe em casos_resumo.json)")
                continue
            usados.add(cid)
            l = lados.get(cid, {})
            itens.append({
                "id": cid,
                "titulo": c["titulo"],
                "busca": c["busca"],
                "tag": c["tag"],
                "alegacao": c["alegacao"],
                "veredito": c["veredito"],
                "acusa": l.get("fraude", ""),
                "defende": l.get("defesa", ""),
                "decisao": (l.get("juiz") or {}).get("sintese", ""),
            })
        temas.append({**{k: v for k, v in t.items() if k != "casos"}, "itens": itens})

    orfaos = sorted(set(por_id) - usados)
    if orfaos:
        print(f"  (caso sem tema: {orfaos})")

    DESTINO.write_text(json.dumps(temas, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(t["itens"]) for t in temas)
    print(f"{len(temas)} temas, {total} casos → {DESTINO.relative_to(RAIZ)}")
    for t in temas:
        print(f"  /{t['slug']:22} {len(t['itens'])} caso(s)")


if __name__ == "__main__":
    main()
