"""Relatório técnico em PDF: reconciliação, transição, testes pré-registrados e poder.

    venv/bin/python -m tools.migracoes.2026-11-02-relatorio-pdf

## Por que existe

O site é para o leitor comum; o relatório é o objeto que um professor lê e cita.
Tudo o que está aqui já está no site (/analise, /metodo, /dados) e nos JSON —
o PDF não calcula nada: lê os arquivos de `apuracao/data/arquivo/2026-2t/` e
monta o texto em volta. Rodar de novo depois de qualquer teste novo.

Grava `static/relatorio/estranhaeleicao-relatorio-tecnico.pdf`.
Fontes: Liberation Serif/Sans (cobrem acentos, letras gregas e ≥ ≈ − ×).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

RAIZ = Path(__file__).resolve().parents[2]
ARQ = RAIZ / "apuracao/data/arquivo/2026-2t"
DESTINO = RAIZ / "static/relatorio/estranhaeleicao-relatorio-tecnico.pdf"
FONTES = Path("/usr/share/fonts/truetype/liberation")
REPO = "https://github.com/mrsplube/estranhaeleicao"

for nome, arq in (("Serif", "LiberationSerif-Regular"), ("Serif-B", "LiberationSerif-Bold"),
                  ("Serif-I", "LiberationSerif-Italic"), ("Serif-BI", "LiberationSerif-BoldItalic"),
                  ("Sans", "LiberationSans-Regular"), ("Sans-B", "LiberationSans-Bold"),
                  ("Mono", "LiberationMono-Regular")):
    pdfmetrics.registerFont(TTFont(nome, str(FONTES / f"{arq}.ttf")))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-B", italic="Serif-I", boldItalic="Serif-BI")

TINTA = colors.HexColor("#1b1f2a")
CINZA = colors.HexColor("#5b6170")
LINHA = colors.HexColor("#c9ccd3")
FUNDO = colors.HexColor("#f2f3f5")
VERDE = colors.HexColor("#dcefe3")
ROXO = colors.HexColor("#ece3f3")
AMBAR = colors.HexColor("#f6ecd6")
AZUL = colors.HexColor("#2f5d9b")

E = {
    "titulo": ParagraphStyle("titulo", fontName="Sans-B", fontSize=19, leading=24, textColor=TINTA, spaceAfter=6),
    "sub": ParagraphStyle("sub", fontName="Serif-I", fontSize=12, leading=16, textColor=CINZA, spaceAfter=14),
    "autor": ParagraphStyle("autor", fontName="Sans", fontSize=9.5, leading=13, textColor=CINZA),
    "h1": ParagraphStyle("h1", fontName="Sans-B", fontSize=13, leading=17, textColor=TINTA, spaceBefore=14, spaceAfter=6, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="Sans-B", fontSize=10.5, leading=14, textColor=TINTA, spaceBefore=10, spaceAfter=4, keepWithNext=1),
    "p": ParagraphStyle("p", fontName="Serif", fontSize=10.3, leading=14.2, alignment=TA_JUSTIFY, spaceAfter=6, textColor=TINTA),
    "resumo": ParagraphStyle("resumo", fontName="Serif", fontSize=9.8, leading=13.6, alignment=TA_JUSTIFY,
                             leftIndent=14, rightIndent=14, spaceAfter=6, textColor=TINTA),
    "nota": ParagraphStyle("nota", fontName="Serif-I", fontSize=8.8, leading=11.6, textColor=CINZA, spaceAfter=6,
                           alignment=TA_JUSTIFY),
    "cel": ParagraphStyle("cel", fontName="Sans", fontSize=8, leading=10, textColor=TINTA),
    "celb": ParagraphStyle("celb", fontName="Sans-B", fontSize=8, leading=10, textColor=TINTA),
    "celc": ParagraphStyle("celc", fontName="Sans", fontSize=7.6, leading=9.4, textColor=TINTA, alignment=TA_CENTER),
    "ref": ParagraphStyle("ref", fontName="Serif", fontSize=9, leading=12, leftIndent=14, firstLineIndent=-14,
                          spaceAfter=3, textColor=TINTA),
    "legenda": ParagraphStyle("legenda", fontName="Sans", fontSize=8.2, leading=10.5, textColor=CINZA, spaceBefore=3,
                              spaceAfter=10),
}


def j(nome: str):
    return json.loads((ARQ / nome).read_text(encoding="utf-8"))


def br(x, casas=1):
    s = f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s.replace("-", "−")


def pct(x, casas=1):
    return br(100 * x, casas) + "%"


P = lambda t, e="p": Paragraph(t, E[e])


def tabela(linhas, larguras, cab=1, zebra=True, estilos=()):
    dados = [[c if not isinstance(c, str) else Paragraph(c, E["celb" if i < cab else "cel"]) for c in l]
             for i, l in enumerate(linhas)]
    t = Table(dados, colWidths=larguras, repeatRows=cab)
    st = [("LINEBELOW", (0, cab - 1), (-1, cab - 1), 0.8, TINTA), ("LINEABOVE", (0, 0), (-1, 0), 0.8, TINTA),
          ("LINEBELOW", (0, -1), (-1, -1), 0.8, TINTA), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if zebra:
        st += [("BACKGROUND", (0, i), (-1, i), FUNDO) for i in range(cab + 1, len(linhas), 2)]
    t.setStyle(TableStyle(st + list(estilos)))
    return t


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ.parent, capture_output=True, text=True).stdout.strip()


def rodape(c, doc):
    c.saveState()
    c.setFont("Sans", 7.5)
    c.setFillColor(CINZA)
    c.drawString(2 * cm, 1.2 * cm, "estranhaeleicao.org · relatório técnico · 2º turno presidencial de 2026")
    c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"{doc.page}")
    c.restoreState()


def grafico_c1(c1):
    s = c1["principal"]["series"]
    itens = [("Flávio (22), 2026", s["22_2026"]["o_e"]), ("Lula (13), 2026", s["13_2026"]["o_e"]),
             ("Bolsonaro (22), 2022", s["22_2022"]["o_e"]), ("Lula (13), 2022", s["13_2022"]["o_e"])]
    d = Drawing(15 * cm, 4.2 * cm)
    ch = HorizontalBarChart()
    ch.x, ch.y, ch.width, ch.height = 3.9 * cm, 0.5 * cm, 10 * cm, 3.4 * cm
    ch.data = [[v for _, v in reversed(itens)]]
    ch.categoryAxis.categoryNames = [n for n, _ in reversed(itens)]
    ch.categoryAxis.labels.fontName = "Sans"
    ch.categoryAxis.labels.fontSize = 8
    ch.categoryAxis.labels.dx = -4
    ch.valueAxis.valueMin, ch.valueAxis.valueMax, ch.valueAxis.valueStep = 0, 3.5, 0.5
    ch.valueAxis.labels.fontName = "Sans"
    ch.valueAxis.labels.fontSize = 7.5
    ch.valueAxis.labelTextFormat = lambda v: br(v, 1)
    ch.bars[0].fillColor = AZUL
    ch.bars[0].strokeColor = None
    ch.barLabelFormat = lambda v: br(v, 2)
    ch.barLabels.fontName = "Sans"
    ch.barLabels.fontSize = 7.5
    ch.barLabels.nudge = 12
    ch.bars[(0, 3)].fillColor = colors.HexColor("#c0392b")
    d.add(ch)
    x1 = ch.x + ch.width * 1 / 3.5
    d.add(Line(x1, ch.y, x1, ch.y + ch.height, strokeColor=CINZA, strokeDashArray=[2, 2], strokeWidth=0.6))
    d.add(String(x1 + 2, ch.y + ch.height + 2, "O/E = 1", fontName="Sans", fontSize=7, fillColor=CINZA))
    return d


def montar() -> list:
    rec, tr, an = j("reconciliacao.json"), j("transicao.json"), j("analise.json")
    c = {k: j(f"{k}.json") for k in ("c1", "c2", "c3", "c4", "c5", "c6", "p1")}
    commit = git("rev-parse", "--short", "HEAD")
    hoje = date.today().strftime("%d/%m/%Y")
    s = []

    # ── capa e resumo ─────────────────────────────────────────────────────
    s += [P("Padrões numéricos alegados como fraude no 2º turno presidencial de 2026: reconciliação de "
            "100% das seções e testes pré-registrados", "titulo"),
          P("Relatório técnico, versão 1", "sub"),
          P(f"Cauê Neves · estranhaeleicao.org · {hoje}<br/>Redação e código assistidos por IA (Claude), "
            f"revisados pelo autor. Código e dados: {REPO} (commit {commit}). "
            "Pré-registro: tag <font face='Mono'>preregistro-v1</font>.", "autor"),
          Spacer(1, 14)]
    s += [P("<b>Resumo.</b> Depois do 2º turno presidencial de 2026 circularam acusações de fraude apoiadas em "
            "padrões numéricos: seções com o candidato derrotado quase zerado, municípios que \"viraram demais\", "
            "boletins tardios favoráveis ao vencedor, voto sem biometria. Este relatório faz três coisas. "
            f"(1) Cruza seção a seção os três arquivos públicos do TSE para o 2º turno (Boletim de Urna, votação "
            f"por seção e detalhe da votação) e o total oficial: <b>0 divergências em {br(rec['secoes']['comparadas'], 0)} "
            f"seções</b>, limite superior de 95% de {br(rec['limite_superior_95']['proporcao'] * 1e6, 0)} seções "
            "divergentes por milhão. (2) Testa seis padrões alegados contra o 2º turno de 2022, com hipóteses, "
            "estatísticas e regras de decisão registradas antes de rodar e correção de Benjamini–Hochberg. Cinco "
            "são compatíveis com 2022 (um deles estatisticamente equivalente); um depende da especificação. "
            "(3) Mede o poder dos testes plantando fraude nos dados: troca de 1% dos votos é detectada em todos os "
            "formatos testados, e acrescentar votos no tamanho da margem é detectado ou não cabe nas seções. "
            "Fraude pequena ou espalhada, abaixo do que mudaria o resultado, passa sem ser vista, e uma troca "
            "uniforme em todas as urnas não é detectável por nenhuma análise de dados. A conclusão é que, nos "
            "formatos que deixam rastro, uma fraude capaz de mudar o resultado está descartada ao nível de 5%; "
            "isso não exclui a fraude que não deixa rastro, que só a conferência do voto pelo eleitor excluiria.",
            "resumo"),
          P("<b>Palavras-chave:</b> forense eleitoral; pré-registro; inferência ecológica; Benjamini–Hochberg; "
            "análise de poder; urna eletrônica.", "resumo"),
          P(f"<b>Como citar:</b> NEVES, Cauê. <i>Padrões numéricos alegados como fraude no 2º turno presidencial "
            f"de 2026: reconciliação de 100% das seções e testes pré-registrados.</i> Relatório técnico, v1. "
            f"estranhaeleicao.org, {hoje}. Disponível em: https://estranhaeleicao.org/analise.", "resumo")]

    # ── 1. pergunta ───────────────────────────────────────────────────────
    s += [P("1. A pergunta", "h1"),
          P("As acusações numéricas misturam três perguntas que precisam ser separadas. <b>Atipicidade:</b> o padrão "
            "de 2026 é raro quando comparado com uma referência? <b>Detecção:</b> se houvesse fraude de um certo "
            "tamanho, os testes a encontrariam? <b>Atribuição:</b> se o padrão é atípico, a causa é fraude? Um teste "
            "sobre resultado agregado responde às duas primeiras, não à terceira. Com uma eleição só, \"houve "
            "fraude?\" não é uma pergunta que um teste frequentista responda sem um modelo de eleição limpa; o que "
            "estes dados permitem é dizer qual tamanho e qual formato de fraude ficam descartados."),
          P("A literatura de forense eleitoral oferece métodos para os padrões alegados (Klimek et al., 2012; "
            "Myagkov, Ordeshook e Shakin, 2009; Mebane, 2011; Rozenas, 2017) e alerta para seus falsos positivos "
            "(Deckert, Myagkov e Ordeshook, 2011). Por isso nenhum teste aqui decide sozinho pelo valor absoluto: "
            "cada um é comparado com o mesmo cálculo numa eleição que não é acusada da mesma forma.")]

    # ── 2. dados ──────────────────────────────────────────────────────────
    s += [P("2. Dados", "h1"),
          P("Todos os arquivos são públicos (dadosabertos.tse.jus.br) e o SHA-256 de cada um está em "
            "<font face='Mono'>docs/preregistro/insumos.sha256</font>. A unidade de análise é a seção eleitoral; "
            "a amostra principal são as seções no Brasil (sem o exterior) presentes nos dois turnos."),
          tabela([["Arquivo", "Conteúdo", "Uso"],
                  ["votacao_secao_2026_BR / 2022_BR", "voto por candidato e seção, 1º e 2º turnos", "todos os testes"],
                  ["bweb_2t_&lt;UF&gt; (2026 e 2022, 28 cada)", "Boletim de Urna: aptos, comparecimento, hora de "
                   "recebimento, eleitores sem biometria, governador", "reconciliação, C3–C6"],
                  ["detalhe_votacao_secao_2026", "instalação, anulação e origem do voto por seção", "reconciliação"],
                  ["votacao_secao_2026_&lt;UF&gt; (6 UFs)", "governador no 1º turno por seção", "C4 (governador)"]],
                 [5.2 * cm, 7.3 * cm, 4.5 * cm]),
          P("Tabela 1. Arquivos de entrada.", "legenda")]

    # ── 3. reconciliação ──────────────────────────────────────────────────
    t = rec["total"]
    orig = rec["origem_do_voto"]
    red = sum(v for k, v in rec["fora_da_urna_no_brasil"].items())
    s += [P("3. Reconciliação de 100% das seções", "h1"),
          P(f"O Boletim de Urna (BU) de cada seção foi cruzado com a votação por seção e com o detalhe da votação, "
            f"e a soma foi comparada com o total oficial. Os 28 arquivos de BU conferem com o hash SHA-512 publicado. "
            f"Em {br(rec['secoes']['comparadas'], 0)} seções, BU e votação por seção dão o mesmo número para os dois "
            f"candidatos, brancos e nulos; BU e detalhe dão o mesmo aptos, comparecimento, brancos e nulos. As "
            f"{rec['bu_x_detalhe']['n_sem_bu_sem_voto']} seções do detalhe sem BU não tiveram voto (41 não "
            f"instaladas e 2 instaladas com comparecimento zero, todas no exterior)."),
          tabela([["", "Oficial", "Soma dos BU", "Votação por seção"]] +
                 [[n, br(t[k]["oficial"], 0), br(t[k]["bu"], 0),
                   br(t[k]["votacao_secao"], 0) if t[k]["votacao_secao"] is not None else "—"]
                  for n, k in (("Lula", "lula"), ("Flávio", "flavio"), ("Brancos", "brancos"),
                               ("Nulos", "nulos"), ("Comparecimento", "comp"))],
                 [4 * cm, 4 * cm, 4 * cm, 4 * cm]),
          P("Tabela 2. Totais do 2º turno: oficial e soma seção a seção. Diferença zero em todas as linhas.", "legenda"),
          P(f"Com 0 divergências em {br(rec['secoes']['comparadas'], 0)} seções, o limite superior unilateral de 95% "
            f"(Clopper-Pearson) para a fração de seções divergentes é {br(rec['limite_superior_95']['proporcao'] * 1e6, 1)} "
            f"por milhão. No Brasil, nenhuma seção votou em cédula no 2º turno: {red} tiveram o boletim gerado pelo "
            f"recuperador de dados (RED) depois de falha da urna e as demais vieram da urna eletrônica; as "
            f"{orig.get('Sistema de apuração', 0)} seções processadas pelo Sistema de Apuração estão no exterior. "
            "Nenhuma seção foi anulada."),
          P("<b>Limite.</b> Os três arquivos saem do TSE, e o hash é servido pelo mesmo site. A reconciliação prova "
            "que o boletim de cada urna é o que entrou no total; não prova que o boletim registra o voto digitado. "
            "As conferências independentes possíveis são comparar o BU afixado na seção com o arquivo publicado e "
            "verificar a assinatura digital de cada boletim com a chave da urna. Nenhuma das duas está aqui.", "nota")]

    # ── 4. transição ──────────────────────────────────────────────────────
    linhas = [["Candidato (1º turno)", "Votos", "Fração ao Lula", "IC 95%", "Decide?"]]
    for x in tr["candidatos"]:
        linhas.append([x["nm"].title(), br(x["votos_1t"], 0), br(x["estimativa"], 2),
                       f"{br(x['ic'][0], 2)} a {br(x['ic'][1], 2)}",
                       "sim" if x["identificado"] else ("borda" if x["na_borda"] else "não")])
    s += [P("4. Para onde foi o voto da terceira via", "h1"),
          P(f"A identidade de totais por município, ganho do Lula = Σ λ<sub>j</sub>·v1<sub>j</sub> + p·novos − "
            f"c·Flávio<sub>1</sub>, foi ajustada por mínimos quadrados ponderados em {br(tr['municipios'], 0)} "
            f"municípios, com cada parâmetro em [0, 1], por solução exata (BVLS). O intervalo de 95% vem de 1.000 "
            f"reamostragens de municípios. A largura média do intervalo é {br(tr['largura_media'], 2)}; só "
            f"{tr['identificados']} de {tr['total']} candidatos têm intervalo estreito o bastante para decidir "
            f"alguma coisa. A troca direta do Flávio para o Lula fica entre {pct(tr['troca']['ic'][0])} e "
            f"{pct(tr['troca']['ic'][1])}."),
          tabela(linhas, [5.3 * cm, 2.4 * cm, 2.6 * cm, 3.2 * cm, 2.2 * cm]),
          P("Tabela 3. Transição por candidato. \"Borda\": estimativa presa em 0 ou 1 com intervalo estreito, o que é "
            "efeito do limite do parâmetro e não informação.", "legenda"),
          P("<b>Correção.</b> Até 31/10/2026 o ajuste usava L-BFGS-B partindo de λ = 0,5 e o intervalo vinha de 40 "
            "subamostras de tamanho n/2. O otimizador parava cerca de 6% acima do mínimo de um problema convexo, e "
            "os λ dos candidatos pequenos ficavam perto do ponto de partida. O site mostrava largura média de 0,78 "
            "e 6 de 10 intervalos inúteis. A correção está no histórico do repositório. Com parâmetros na borda, "
            "o bootstrap percentil não tem garantia de cobertura (Andrews, 2000).", "nota")]

    # ── 5. desenho ────────────────────────────────────────────────────────
    s += [P("5. Desenho dos testes", "h1"),
          P("Os testes foram registrados antes de rodar (tag <font face='Mono'>preregistro-v1</font>, 01/11/2026), "
            "com o SHA-256 dos arquivos de entrada. O plano declara o que já tinha sido visto: totais, as análises "
            "descritivas do site, a transição e a reconciliação. Os estatísticos C1–C6, seus nulos, a comparação com "
            "a referência e a análise de poder ainda não tinham sido calculados por ninguém."),
          P("<b>Referência.</b> R1, principal: o 2º turno presidencial de 2022, mesmo sistema e mesmo desenho; em "
            "2022 o lado perdedor também alegou fraude, então R1 não é a eleição \"que todos aceitam\", e sim a mesma "
            "urna com o sinal da acusação trocado. R2: o 2º turno de governador de 2026 nas seis UFs que o tiveram, "
            "mesmas urnas e mesmo ato de votar, ao lado e sem entrar na regra."),
          P("<b>Regra.</b> \"Atípico\" exige as duas coisas: p ajustado por Benjamini–Hochberg sobre os seis testes "
            "menor que 0,05 <i>e</i> afastamento de 2022 na direção alegada. Fora disso o resultado é compatível com "
            "a referência. Cada teste também roda num multiverso de especificações (piso de comparecimento, efeito "
            "fixo, exclusão das seções do recuperador de dados, limiares); uma decisão só é chamada robusta se for a "
            "mesma em pelo menos 80% delas, e, se não for, o resultado é \"depende da especificação\", sem conclusão. "
            "Os esclarecimentos de implementação de cada teste foram registrados e publicados antes de rodá-lo "
            "(seção 9 do pré-registro; resumo na seção 10 abaixo).")]

    # ── 6. resultados ─────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = (c[k] for k in ("c1", "c2", "c3", "c4", "c5", "c6"))
    s1 = c1["principal"]["series"]
    p2 = c2["principal"]
    s3 = c3["principal"]["series"]
    s4 = c4["principal"]["series"]
    s5 = c5["principal"]["series"]
    p6 = c6["principal"]
    s += [P("6. Resultados", "h1"),
          tabela([["Teste", "Alegação", "Resultado", "Multiverso"],
                  ["C1", "seções com o 22 quase zerado", "compatível", c1["multiverso_mesma_decisao"]],
                  ["C2", "municípios fora do padrão", "compatível", c2["multiverso_mesma_decisao"]],
                  ["C3", "enchimento de urna (comparecimento × voto)", "compatível", c3["multiverso_mesma_decisao"]],
                  ["C4", "boletins tardios mudaram para o 13", "depende da especificação", c4["multiverso_mesma_decisao"]],
                  ["C5", "voto sem biometria favoreceu o 13", "compatível", c5["multiverso_mesma_decisao"]],
                  ["C6", "seções uniformes ou dispersas demais", "equivalente a 2022", c6["multiverso_mesma_decisao"]]],
                 [1.3 * cm, 7.4 * cm, 4.6 * cm, 2.8 * cm],
                 estilos=[("BACKGROUND", (2, i), (2, i), VERDE) for i in (1, 2, 3, 5, 6)] +
                         [("BACKGROUND", (2, 4), (2, 4), AMBAR)], zebra=False),
          P("Tabela 4. Resumo. \"Multiverso\": especificações com a mesma decisão da principal.", "legenda"),
          P("A correção de Benjamini–Hochberg não muda nenhuma decisão: ela só pesaria num teste que já estivesse "
            "afastado de 2022 na direção alegada, e nenhum ficou assim na especificação principal.")]

    s += [P("C1 — Seções quase zeradas para o 22", "h2"),
          P(f"Estatístico: número de seções com o 22 até 10 votos, contra o esperado por um modelo beta-binomial "
            f"que parte do 1º turno da mesma seção (regressão logística fracionária com efeito fixo de UF), com "
            f"10.000 simulações. Observado em 2026: {br(s1['22_2026']['observado'], 0)}; esperado: "
            f"{br(s1['22_2026']['esperado'], 0)} (O/E = {br(s1['22_2026']['o_e'], 2)}, p &lt; 0,001). Mas o mesmo "
            f"modelo dá O/E = {br(s1['22_2022']['o_e'], 2)} para o 22 em 2022: ele subestima seções quase zeradas em "
            f"qualquer eleição. 2026 fica abaixo da referência, então o resultado é compatível. A sobredispersão "
            f"por momentos saiu negativa em 26 das 27 UFs (o 1º turno da mesma seção prevê o 2º melhor que uma "
            f"binomial) e foi truncada em 10<super>−6</super>, o que foi registrado antes dos p-valores."),
          KeepTogether([grafico_c1(c1),
                        P("Figura 1. C1: razão observado/esperado de seções com o candidato até 10 votos. Em "
                          "vermelho, a série testada.", "legenda")])]

    s += [P("C2 — Municípios fora do padrão", "h2"),
          P(f"Mesmo modelo no município, para a fatia do 13; resíduo de Pearson com correção quase-binomial e "
            f"Benjamini–Hochberg (q = 0,05) sobre os municípios. 2026: {p2['2026']['significativos']} de "
            f"{br(p2['2026']['municipios'], 0)} municípios significativos ({p2['2026']['a_favor_13']} a favor do 13). "
            f"2022: {p2['2022']['significativos']} de {br(p2['2022']['municipios'], 0)} "
            f"({p2['2022']['a_favor_13']} a favor do 13). Razão das proporções {br(p2['razao_proporcoes'], 2)} "
            f"(p = {br(p2['p_proporcao'], 2)}); fração a favor do 13 de {pct(p2['d2_2026'])} contra "
            f"{pct(p2['d2_2022'])} (Fisher, p = {br(p2['p_fisher'], 2)}). Silva Jardim, o município citado na "
            f"alegação, fica em {br(c2['silva_jardim']['posicao'], 0)}º de {br(c2['silva_jardim']['de'], 0)} "
            f"(z = {br(c2['silva_jardim']['z'], 2)}). Os maiores desvios são capitais, onde diferenças pequenas viram "
            f"z grandes.")]

    g3 = s3["governador_2026"]
    s += [P("C3 — Comparecimento × voto (enchimento de urna)", "h2"),
          P(f"Modelo de mistura de Klimek et al. (2012) ajustado ao histograma 2D de comparecimento e fatia do "
            f"vencedor por seção, com IC por 1.000 reamostragens de municípios. Fraude incremental: "
            f"{pct(s3['2026']['f_i'])} em 2026 (IC {pct(s3['2026']['f_i_ic'][0])} a {pct(s3['2026']['f_i_ic'][1])}) "
            f"contra {pct(s3['2022']['f_i'])} em 2022 (IC {pct(s3['2022']['f_i_ic'][0])} a "
            f"{pct(s3['2022']['f_i_ic'][1])}); diferença 2026 − 2022 com IC de "
            f"{br(100 * c3['principal']['diferenca_2026_2022']['f_i_ic'][0], 1)} a "
            f"{br(100 * c3['principal']['diferenca_2026_2022']['f_i_ic'][1], 1)} pontos. Fraude extrema, a "
            f"assinatura do enchimento: {pct(s3['2026']['f_e'], 2)} em 2026 e {pct(s3['2022']['f_e'], 2)} em 2022. "
            f"No governador de 2026, {pct(g3['f_i'])} e {pct(g3['f_e'], 2)}. A inclinação de Myagkov et al. (2009), "
            f"votos do 13 por apto sobre comparecimento dentro do município, é {br(s3['2026']['inclinacao_municipio'][0], 2)} "
            f"(2022: {br(s3['2022']['inclinacao_municipio'][0], 2)}), longe do 1 que o enchimento produziria."),
          P("Os valores altos de fraude incremental em 2022 e no governador vêm do menor σ<sub>x</sub> da grade, que "
            "não se distingue de ruído: o componente absorve o desajuste do modelo limpo (comparecimento e voto "
            "normais e independentes), simples demais para um país em que os dois variam juntos por região. Com "
            "histograma de 50 × 50, o valor de 2026 vai a zero. É por isso que a decisão é pela comparação.", "nota")]

    s += [P("C4 — Ordem de chegada dos boletins", "h2"),
          P(f"Correlação de Spearman, dentro do município, entre a hora de recebimento do BU e a mudança da seção "
            f"do 1º para o 2º turno (Δ = L<sub>2</sub>/V<sub>2</sub> − L<sub>1</sub>/V<sub>1</sub>), média ponderada, "
            f"contra 2.000 permutações da hora dentro do município. 2026: {br(s4['2026']['r4'], 3)} "
            f"(p = {br(s4['2026']['p'], 2)}); 2022: {br(s4['2022']['r4'], 3)}. Na especificação principal não há "
            f"nada. Em 4 de 12 especificações (zona no lugar do município, com piso de comparecimento) a correlação "
            f"sobe para 0,002–0,003, fica abaixo de p = 0,05 e acima de 2022. A mesma decisão vale em "
            f"{c4['multiverso_mesma_decisao'].replace('/', ' de ')} especificações, abaixo dos 80% exigidos: pela "
            f"regra registrada, o resultado depende da especificação e não autoriza conclusão. Dois fatos ajudam a "
            f"ler o número: uma correlação de 0,003 não explica quase nada da mudança, e no governador de 2026, "
            f"mesmas urnas e sem acusação, a mesma correlação é {br(c4['governador']['r4'], 3)} "
            f"(p = {br(c4['governador']['p'], 4)}).")]

    s += [P("C5 — Voto sem biometria", "h2"),
          P(f"Regressão de Δ sobre a fração de eleitores sem biometria na seção, com efeito fixo de município, peso "
            f"pelos válidos e erro agrupado por zona. 2026: β = {br(s5['2026']['beta'], 3)} "
            f"(erro {br(s5['2026']['se'], 3)}): a cada 10 pontos a mais de eleitores sem biometria, a seção mudou "
            f"{br(-10 * s5['2026']['beta'], 2)} ponto a <i>menos</i> para o 13, o contrário do que a alegação prevê. "
            f"2022: β = {br(s5['2022']['beta'], 3)}. Diferença com IC de {br(c5['principal']['diferenca_ic'][0], 3)} a "
            f"{br(c5['principal']['diferenca_ic'][1], 3)}.")]

    s += [P("C6 — Dispersão entre seções do mesmo município", "h2"),
          P(f"Dispersão de Pearson (χ²/gl) da fatia do 13 entre as seções de cada município, contra a binomial; "
            f"mediana entre municípios. 2026: {br(p6['series']['2026']['m6'], 2)}; 2022: "
            f"{br(p6['series']['2022']['m6'], 2)}. Razão {br(p6['razao'], 2)}, com IC de {br(p6['razao_ic'][0], 2)} a "
            f"{br(p6['razao_ic'][1], 2)}, inteira dentro da faixa de equivalência de 0,8 a 1,25: a dispersão de 2026 é "
            f"equivalente à de 2022. No governador de 2026: {br(c6['governador']['m6'], 2)}.")]

    # ── 7. poder ──────────────────────────────────────────────────────────
    p1 = c["p1"]
    rot = {"descartado": "descartado", "não descartado": "não descart.", "não cabe": "não cabe"}
    cor = {"descartado": VERDE, "não descartado": ROXO, "não cabe": colors.white}
    des = ("enchimento", "troca")
    fr = (0.001, 0.01, 0.05, 0.20)
    tm = (0.001, 0.005, 0.01, 0.0357)
    linhas = [["Desenho e seções atingidas"] + [f"{br(100 * x, 2).rstrip('0').rstrip(',')}% dos votos" for x in tm]]
    est = []
    for d in des:
        for f in fr:
            linha = [f"{d.capitalize()}, {br(100 * f, 1).replace(',0', '')}% das seções"]
            for k, t_ in enumerate(tm):
                x = next(z for z in p1["cenarios"] if z["base"] == 2026 and z["desenho"] == d
                         and z["fracao_secoes"] == f and z["tamanho"] == t_)
                linha.append(Paragraph(f"{rot[x['leitura']]}<br/>{pct(x['deteccao']['qualquer'], 0)}", E["celc"]))
                est.append(("BACKGROUND", (k + 1, len(linhas)), (k + 1, len(linhas)), cor[x["leitura"]]))
            linhas.append(linha)
    s += [P("7. Poder: que fraude estes testes encontram", "h1"),
          P("Fraude a favor do 13 foi plantada nos dados reais em dois desenhos: <b>enchimento</b> (votos novos, "
            "limitados pelos aptos ausentes) e <b>troca</b> (votos do 22 viram 13). As seções foram sorteadas na "
            "mesma fração em cada UF, de 0,1% a 20%, com tamanhos de 0,1% a 3,57% dos votos válidos (3,57% é a "
            "margem). Em cada réplica rodam os seis testes com a regra de decisão de cada um; a parada é sequencial "
            "(lotes de 20 réplicas, até 200). Como nenhum teste disparou nos dados reais, um cenário detectado em "
            "pelo menos 95% das réplicas fica descartado ao nível de 5%."),
          tabela(linhas, [5.0 * cm, 2.9 * cm, 2.9 * cm, 2.9 * cm, 2.9 * cm], zebra=False, estilos=est),
          P("Tabela 5. Base 2026: leitura e taxa de detecção por \"qualquer teste\". \"Não cabe\": as seções sorteadas "
            "não têm aptos ausentes ou votos do 22 suficientes para a fraude inteira; a taxa é a da parte que coube.",
            "legenda"),
          P("Virar a eleição exigiria trocar 1,8% dos votos do 22 para o 13, ou acrescentar 3,57% de votos falsos. "
            "Trocar 1% já é detectado em todos os formatos; acrescentar 3,57% é detectado espalhado em 20% das seções "
            "e concentrado em 5%, e em 1% das seções ou menos não cabe. Passam sem ser vistos: 0,1% dos votos em "
            "qualquer formato, enchimento espalhado em 20% das seções até 1% do total e troca espalhada de 0,5%. "
            "Nenhum desses mudaria o resultado. A detecção vem quase toda de C1 e C6 (troca) e de C3 (enchimento); "
            "C4 e C5 não detectam fraude sorteada ao acaso porque testam alegações específicas (relação com a hora "
            "de chegada e com a biometria)."),
          P("<b>Base 2022 e versão leve.</b> Plantada nos dados de 2022 e comparada com 2022 real, a fraude é "
            "detectada até em 0,1% dos votos. Isso não é poder: ali a referência é o próprio dado e qualquer empurrão "
            "na direção alegada passa do limiar. Os números estão em p1.json; a conclusão usa só a base de 2026. "
            "Dentro da simulação os testes rodam numa versão leve registrada antes (p e erros-padrão por aproximação "
            "onde o completo exigiria milhares de reamostragens), validada nos dados sem fraude. Duas correções de "
            "código foram feitas depois de rodar parte dos cenários e estão registradas com o resultado anterior "
            "(seção 10).", "nota")]

    # ── 8. conclusão ──────────────────────────────────────────────────────
    s += [P("8. Conclusão", "h1")] + [P(x) for x in an["conclusao"]["paragrafos"]]

    # ── 9. limites ────────────────────────────────────────────────────────
    s += [P("9. Ameaças à validade", "h1")]
    for t_ in (
        "<b>TSE contra TSE.</b> Todos os arquivos vêm da mesma fonte. A reconciliação mostra consistência interna, "
        "não correspondência com o voto digitado.",
        "<b>Sem voto impresso.</b> Não há registro conferido pelo eleitor. Uma auditoria por amostragem de risco no "
        "sentido usual (Stark) não é possível.",
        "<b>Troca uniforme.</b> Uma troca pequena e igual em todas as seções é indistinguível de mudança real de "
        "opinião e escapa de qualquer teste estatístico sobre o resultado.",
        "<b>Referência acusada.</b> 2022 também foi alvo de alegações. A comparação é de 2026 com o mesmo sistema, "
        "não com uma eleição sabidamente limpa.",
        "<b>Dados já vistos.</b> O pré-registro é de análise secundária: os totais e as descritivas eram conhecidos. "
        "O que foi protegido são os estatísticos, os nulos e as regras.",
        "<b>Modelos simples.</b> O modelo limpo de Klimek e o modelo do C1 erram o formato do Brasil; a comparação "
        "com 2022 controla isso, mas não elimina.",
        "<b>Aproximações no poder.</b> A simulação usa a versão leve dos testes; a validação sem fraude reproduz a "
        "versão completa, mas o poder pode diferir perto da fronteira.",
        "<b>Assistência de IA.</b> Código e texto foram escritos com assistência de IA e revisados pelo autor; dois "
        "erros de código foram encontrados lendo resultados e estão documentados."):
        s.append(P("• " + t_))

    # ── 10. desvios ───────────────────────────────────────────────────────
    s += [P("10. Mudanças no plano", "h1"),
          P("Todas estão na seção 9 do pré-registro, com data e motivo, e foram publicadas antes do resultado "
            "correspondente, exceto as duas correções de código do P1, que foram registradas com o resultado de antes."),
          tabela([["Teste", "Mudança", "Quando"],
                  ["C1", "sobredispersão negativa truncada em 10<super>−6</super>", "antes dos p-valores"],
                  ["C2", "p único da regra dupla (Bonferroni interno); variação de efeito fixo", "antes de rodar"],
                  ["C3", "detalhes do modelo de Klimek (distribuições limpas, α, grade de σ<sub>x</sub>, p)", "antes de rodar"],
                  ["C4", "hora do BU, empates, p unilateral, governador", "antes de rodar"],
                  ["C5", "campo de biometria de 2022, p unilateral, IC da diferença", "antes de rodar"],
                  ["C6", "fórmula de φ, p bilateral, faixa nos dois lados", "antes de rodar"],
                  ["P1", "versão leve dos testes, parada sequencial, base 2022", "antes de rodar"],
                  ["P1", "correção do arredondamento da cota de votos por seção", "depois de 27 cenários"],
                  ["P1", "p do C3 na versão leve segue a definição registrada", "depois de 27 cenários"]],
                 [1.5 * cm, 11 * cm, 3.6 * cm]),
          P("Tabela 6. Mudanças registradas.", "legenda")]

    # ── 11. reprodutibilidade ─────────────────────────────────────────────
    s += [P("11. Como reproduzir", "h1"),
          P(f"Código em {REPO}. Em <font face='Mono'>app/</font>, com o ambiente de "
            f"<font face='Mono'>requirements-analise.txt</font> (Python 3.13, numpy 2.5.4, scipy 1.18.1):"),
          P("<font face='Mono' size='8.5'>python -m tools.migracoes.2026-11-01-reconciliacao<br/>"
            "python -m tools.migracoes.2026-11-01-bu-secao<br/>"
            "python -m tools.migracoes.2026-11-01-c1-secoes-zeradas &nbsp;(… c2 a c6)<br/>"
            "python -m tools.migracoes.2026-11-01-p1-poder<br/>"
            "python -m tools.migracoes.2026-11-02-relatorio-pdf</font>"),
          P("Cada script grava um JSON em <font face='Mono'>apuracao/data/arquivo/2026-2t/</font>, servido em "
            "https://estranhaeleicao.org/dados. Tempo aproximado num i5 de 2 núcleos: reconciliação 10 min, C1 40 "
            "min, C3 45 min, C4 60 min, P1 cerca de 10 h.")]

    # ── referências ───────────────────────────────────────────────────────
    s += [P("Referências", "h1")]
    for r in (
        "ANDREWS, D. W. K. Inconsistency of the bootstrap when a parameter is on the boundary of the parameter "
        "space. <i>Econometrica</i>, 68(2), 2000.",
        "BENJAMINI, Y.; HOCHBERG, Y. Controlling the false discovery rate. <i>Journal of the Royal Statistical "
        "Society B</i>, 57(1), 1995.",
        "DECKERT, J.; MYAGKOV, M.; ORDESHOOK, P. C. Benford's Law and the detection of election fraud. "
        "<i>Political Analysis</i>, 19(3), 2011.",
        "ENIKOLOPOV, R. et al. Field experiment estimate of electoral fraud in Russian parliamentary elections. "
        "<i>PNAS</i>, 110(2), 2013.",
        "KING, G. <i>A Solution to the Ecological Inference Problem</i>. Princeton University Press, 1997.",
        "KLIMEK, P.; YEGOROV, Y.; HANEL, R.; THURNER, S. Statistical detection of systematic election "
        "irregularities. <i>PNAS</i>, 109(41), 2012.",
        "MANSKI, C. F. <i>Partial Identification of Probability Distributions</i>. Springer, 2003.",
        "MEBANE, W. R. Comment on \"Benford's Law and the detection of election fraud\". <i>Political Analysis</i>, "
        "19(3), 2011.",
        "MYAGKOV, M.; ORDESHOOK, P. C.; SHAKIN, D. <i>The Forensics of Election Fraud</i>. Cambridge University "
        "Press, 2009.",
        "ROZENAS, A. Detecting election fraud from irregularities in vote-share distributions. <i>Political "
        "Analysis</i>, 25(1), 2017.",
        "STARK, P. B. Conservative statistical post-election audits. <i>Annals of Applied Statistics</i>, 2(2), "
        "2008.",
        "STEEGEN, S. et al. Increasing transparency through a multiverse analysis. <i>Perspectives on "
        "Psychological Science</i>, 11(5), 2016.",
        "VAN DEN AKKER, O. et al. Preregistration of secondary data analysis: a template and tutorial. "
        "<i>Meta-Psychology</i>, 5, 2021."):
        s.append(P(r, "ref"))
    return s


def main() -> int:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(DESTINO), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            title="Padrões numéricos alegados como fraude no 2º turno presidencial de 2026",
                            author="Cauê Neves", subject="Relatório técnico, estranhaeleicao.org",
                            keywords="forense eleitoral, pré-registro, Benjamini-Hochberg, poder")
    doc.build(montar(), onFirstPage=rodape, onLaterPages=rodape)
    print(f"→ {DESTINO.relative_to(RAIZ)} ({DESTINO.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
