"""Os vídeos de cada caso da entrada (30/10/2026) e os números dos casos novos.

    venv/bin/python -m tools.migracoes.2026-10-30-casos-videos <pasta-dos-reels>

A pasta tem, para cada reel, o `<id>.info.json` e o `<id>.jpg` que o yt-dlp
grava (`--write-info-json --write-thumbnail`). Entre vídeos que acusam a mesma
coisa, fica o de mais curtidas. Grava:

- `static/casos/<caso>.jpg` — a capa do vídeo, recortada em 3:4;
- `apuracao/data/arquivo/2026-2t/casos_videos.json` — por caso: o vídeo
  (link, perfil, curtidas, comentários) e, para os casos novos, os números
  conferidos no arquivo seção a seção (`apuracao/cache/secoes_2026.pkl`).

Fatos que não estão no arquivo do TSE vêm das fontes em FONTES (checagem da
Justiça Eleitoral, TRE-PE, imprensa) e ficam citados no próprio caso.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
ARQ = RAIZ / "apuracao" / "data" / "arquivo" / "2026-2t"
CAPAS = RAIZ / "static" / "casos"
L1, F1, T1, BN1, C1, L2, F2, BN2, C2 = range(9)

# caso → reel escolhido (o de mais curtidas entre os que acusam a mesma coisa)
VIDEOS = {
    "virada": "DfBFwC2ACEp",        # @pyonglee; também De-UdS6OWmt, De9YCNKNngf
    "secoes-10": "DfFRR-Jx7A2",     # @pradoclima; também DfC_j0ho8Qu
    "curva": "DfBTF4LtGzB",         # @vitorianewsparacatu; também DfHq8SLM4i1
    "biometria": "DfDko4LAqq2",     # @guilherme.peles; também DfGZySAN4EO, DfGGwTbBtWX, DfGOocPuzn-
    "mesario": "DfCYVdXisXF",       # @pyonglee; também De9ivmVxTri
    "silva-jardim": "DfDwG_mNfg1",  # @hericles_sampaio (Araruama); também DfGXIePNOby (Campos)
    "cedula": "De7oX2AMOoq",        # @thiagomedinamd
    "eleitores": "DfAL-6rxYO-",     # @felipecardozooficial
    "soma": "De9kEn-vXzV",          # @euicaroalmeida (print do X)
    "caminhonete": "DfFLlPMkf_5",   # @ch7brasil (carrossel: sem capa baixável)
    "consulta": "DfGEElqB7Ff",      # @gugomes.br; também DfGFl7UNHr1
    "prorrogacao": "DfIJ9H4tP9_",   # @luis.lacombe
    "sala-cofre": "DfFTPO0C0vC",    # @felipececilio.reserva
    "mesaria": "De7jQditGVO",       # @bialaranjeiras
    "pesquisas": "De-UdS6OWmt",     # @eusoudanielfernandes; também DfIZAFdm56K (carrossel)
    "onibus": "DfIxqW7RfsI",        # @metropoles (o áudio da CTB, 30/10)
}

# Casos sem vídeo: foto do Wikimedia Commons (crédito em `creditos`) ou capa
# desenhada com o número do caso (gerada à parte, <caso>.png na mesma pasta).
CAPAS_SEM_VIDEO = {
    "desfile": ("desfile.jpg", "Marvin Brandão, CC BY-SA 4.0"),
    "exercito": ("exercito.jpg", "TSE, CC BY 4.0"),
    "universidades": ("universidades.jpg", "Airton Jordani, CC BY-SA 4.0"),
    # As cinco capas desenhadas até 30/10 viraram foto (31/10), pelo mesmo
    # critério dos três casos acima: imagem do Commons, licença verificada na
    # página do arquivo, recorte 3:4. A origem de cada uma está no comentário.
    # urna UE2020 (seção vazia) — File:Urna eletrônica brasileira UE2020.jpg
    "mesma-secao": ("mesma-secao.jpg", "Antonio Augusto / TSE, Domínio Público"),
    # painel de apuração do TSE, 1º turno de 2026 — File:Eleições 2026 - Primeiro turno (55568483402).jpg
    "zonas": ("zonas.jpg", "Carlos Moura / Agência Senado, CC BY-SA 4.0"),
    # agência da Caixa (o benefício que caiu antes da eleição) — File:Agência da Caixa Econômica Federal na Universidade Federal de Goiás, Goiânia, dezembro de 2022 (1).jpg
    "pacote": ("pacote.jpg", "Fronteira, CC BY-SA 4.0"),
    # presídio de Pacatuba (CE), sem rosto nem pessoa — File:Unidade Prisional em Pacatuba.jpg
    "faccoes": ("faccoes.jpg", "Porto Neto, CC BY-SA 4.0"),
    # cédulas de real apreendidas — File:Dinheiro encontrado.jpg
    "compra": ("compra.jpg", "Mendes Lima / Dourados Agora, CC BY-SA 4.0"),
    # As três capas desenhadas com texto (31/10) também viraram foto, sem rosto:
    # sede do TSE — File:Sede do Tribunal Superior Eleitoral, em Brasília.jpg
    "desinformacao": ("desinformacao.jpg", "Alexandresena, CC BY-SA 4.0"),
    # mãos digitando no WhatsApp — File:Whatsapp texting.jpg
    "maquina-celular": ("maquina-celular.jpg", "Helar Lukats, CC BY-SA 4.0"),
    # o nicho da imagem na Basílica de Aparecida — File:Imagem NSra Basílica.JPG
    "padroeira": ("padroeira.jpg", "Neospo, CC BY 2.5"),
    # As cinco capas de vídeo que eram só print com texto grande viraram foto
    # (31/10), para ler melhor na miniatura de 82px do celular:
    # mesária no terminal do mesário (Itajubá, 2016) — File:Eleição municipal 2016 em Itajubá 1.jpg
    "mesario": ("mesario.jpg", "Mateus S. Figueiredo, CC BY-SA 4.0"),
    # Mauro Paulino, do Datafolha, em entrevista — File:Mauro Paulino (Datafolha) (29456480008).jpg
    "pesquisas": ("pesquisas.jpg", "Associação Brasileira de Jornalismo Investigativo, CC BY 2.0"),
    # ônibus urbano de Salvador — File:Linha de ônibus Campo Grande em Salvador.jpg
    "onibus": ("onibus.jpg", "Heylenny, CC BY-SA 4.0"),
    # comitiva em Catolândia (BA), um dos 23 municípios do caso — File:21 01 2021 Parada não planejada no Município de Catolândia BA (50860674976).jpg
    "eleitores": ("eleitores.jpg", "Palácio do Planalto, CC BY 2.0"),
    # cédula de papel sendo depositada na urna — File:Ballot dropped into ballot box 2024 Swedish EU election at Stångenässkolan, Brastad.jpg
    "cedula": ("cedula.jpg", "W.carter, CC BY-SA 4.0"),
}

FONTES = {
    "tse_17h": {"rot": "Justiça Eleitoral, Fato ou Boato",
                "url": "https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens/2026/relatorio-apocrifo-distorce-dados-para-sugerir-fraude-nas-eleicoes-2026"},
    "nucleo": {"rot": "Núcleo", "url": "https://nucleo.jor.br/republicacao/2026/10/29/relatorio-apocrifo-distorce-microdados-do-tse-para-alegar-fraude-eleitoral/"},
    "tre_pe": {"rot": "TRE-PE", "url": "https://www.tre-pe.jus.br/comunicacao/noticias/2026/Outubro/pernambuco-registra-maior-comparecimento-as-urnas-no-segundo-turno-das-eleicoes-2026"},
    "atarde": {"rot": "A Tarde", "url": "https://atarde.com.br/eleicoes/bahia-tem-23-municipios-com-mais-eleitores-que-habitantes-em-2026-1396858"},
    "tatu": {"rot": "Agência Tatu", "url": "https://www.agenciatatu.com.br/noticia/eleitores-habitantes-nordeste-2026/"},
    "aosfatos": {"rot": "Aos Fatos", "url": "https://www.aosfatos.org/noticias/video-gilmar-mendes-mesario-pianista/"},
    "caminhonete": {"rot": "Gazeta do Povo", "url": "https://www.gazetadopovo.com.br/republica/tre-df-apura-transporte-de-urnas-em-caminhonete-com-adesivo-do-pt/"},
    "pleno": {"rot": "Pleno News", "url": "https://pleno.news/brasil/eleicoes-2026/tse-explica-transporte-de-urnas-em-caminhonete-adesivada-do-pt.html"},
    "faltou": {"rot": "Poder360", "url": "https://www.poder360.com.br/poder-eleicoes-2026/site-do-tse-registra-como-faltou-eleitores-que-votaram/"},
    "tse_certidao": {"rot": "TSE", "url": "https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/emissao-de-certidao-de-quitacao-eleitoral-sera-retomada-na-proxima-terca-feira-3"},
    "tre_df_certidao": {"rot": "TRE-DF", "url": "https://www.tre-df.jus.br/comunicacao/noticias/2026/Outubro/emissao-de-certidao-de-quitacao-eleitoral-pela-internet-fica-suspensa-ate-2-de-novembro"},
    "faltou_tse": {"rot": "Justiça Eleitoral, Fato ou Boato", "url": "https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens/2026/mensagem-faltou-no-servico-de-justificativa-eleitoral-nao-significa-que-eleitor-nao-votou"},
    "atlas": {"rot": "AtlasIntel, 18 a 23/10", "url": "https://bpmoney.com.br/politica/flavio-499-lula-484-ultima-atlasintel-antes-urnas/"},
}


def capa(origem: Path, destino: Path) -> None:
    im = Image.open(origem).convert("RGB")  # PNG desenhado ou JPG
    w, h = im.size
    alvo = 3 / 4
    if w / h > alvo:
        nw = int(h * alvo)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / alvo)
        top = max(0, (h - nh) // 3)
        im = im.crop((0, top, w, top + nh))
    im.resize((360, 480), Image.LANCZOS).save(destino, quality=78, optimize=True)


def soma_mun(A, ch, mun, uf, nome):
    ks = {k for k, v in mun.items() if v == nome and k[0] == uf}
    idx = np.array([i for i, c in enumerate(ch) if (c[0], c[1]) in ks])
    s = A[idx][:, :9].sum(0)
    return {k: int(s[i]) for i, k in enumerate(("l1", "f1", "t1", "bn1", "c1", "l2", "f2", "bn2", "c2"))}


def main(pasta: Path):
    CAPAS.mkdir(exist_ok=True)
    videos = {}
    for caso, rid in VIDEOS.items():
        info = json.loads((pasta / f"{rid}.info.json").read_text())
        # Casos cuja capa é foto (CAPAS_SEM_VIDEO) mantêm a foto: a capa do reel
        # era um print com texto grande, ilegível na miniatura.
        tem_capa = (pasta / f"{rid}.jpg").exists() and caso not in CAPAS_SEM_VIDEO
        if tem_capa:
            capa(pasta / f"{rid}.jpg", CAPAS / f"{caso}.jpg")
        videos[caso] = {"url": info.get("webpage_url") or f"https://www.instagram.com/reel/{rid}/",
                        "perfil": info.get("channel") or info.get("uploader_id"),
                        "curtidas": info.get("like_count"), "comentarios": info.get("comment_count"),
                        "capa": f"/static/casos/{caso}.jpg" if (tem_capa or caso in CAPAS_SEM_VIDEO) else None}

    capas = {}
    for caso, (arq, credito) in CAPAS_SEM_VIDEO.items():
        capa(pasta / arq, CAPAS / f"{caso}.jpg")
        capas[caso] = {"src": f"/static/casos/{caso}.jpg", "credito": credito}

    t = pickle.load(open(RAIZ / "apuracao" / "cache" / "secoes_2026.pkl", "rb"))
    A, ch, mun = t["A"].astype(np.int64), t["chaves"], t["mun"]
    zer = (A[:, F2] == 0) & (A[:, C2] > 0)
    conta = json.loads((ARQ / "conta.json").read_text())["nacional"]
    dados = {
        "secoes_zeradas": {"total": int(zer.sum()), "sem_branco_nulo": int((zer & (A[:, BN2] == 0)).sum()),
                           "branco_nulo": int(A[zer, BN2].sum()), "lula": int(A[zer, L2].sum())},
        "cidades": {nm: soma_mun(A, ch, mun, "rj", nm) for nm in ("ARARUAMA", "CAMPOS DOS GOYTACAZES", "SILVA JARDIM")},
        "bahia": {nm: soma_mun(A, ch, mun, "ba", nm) for nm in ("CATOLÂNDIA", "FIRMINO ALVES", "SAUBARA")},
        "nacional": {k: conta[k] for k in ("lula1", "flavio1", "lula2", "flavio2", "comp1", "comp2", "brancos1", "nulos1", "brancos2", "nulos2")},
    }
    saida = {"videos": videos, "capas": capas, "fontes": FONTES, "dados": dados}
    (ARQ / "casos_videos.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1))
    print(json.dumps(dados["secoes_zeradas"]), {k: (v["l2"] - v["l1"], v["f2"] - v["f1"]) for k, v in dados["cidades"].items()})


if __name__ == "__main__":
    main(Path(sys.argv[1]))
