"""Parecer didático sobre o relatório técnico v1, em PDF.

    venv/bin/python -m tools.migracoes.2026-11-02-parecer-pdf

## Por que existe

Antes de virar artigo, o relatório v1 foi lido como um parecerista leria. Este
PDF registra as críticas de um jeito que serve para estudar: para cada uma, o
que o v1 diz, por que isso é um problema (com a intuição estatística por trás)
e o que a v2 faz. É o roteiro da v2 e fica no repositório como histórico.

Grava `docs/relatorio/parecer-relatorio-v1.pdf`.
"""
from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

rel = importlib.import_module("tools.migracoes.2026-11-02-relatorio-pdf")
E, P, tabela, br = rel.E, rel.P, rel.tabela, rel.br
RAIZ = rel.RAIZ
DESTINO = RAIZ.parent / "docs/relatorio/parecer-relatorio-v1.pdf"

COR = {"grave": colors.HexColor("#f4d9d6"), "séria": colors.HexColor("#f6ecd6"), "forma": colors.HexColor("#e3e8f2")}

# (número, gravidade, título, o que o v1 diz, por que é problema, como a v2 corrige)
CRITICAS = [
    (1, "grave", "Comparar um ponto com um ponto",
     "A regra de decisão diz que 2026 é atípico se ficar além de 2022. No C1, a decisão saiu de comparar "
     "O/E = 2,67 (2026) com O/E = 3,05 (2022), sem intervalo para nenhum dos dois.",
     "Para dizer que algo é raro, é preciso saber como o normal varia. Uma única eleição de referência não tem "
     "variância: é um ponto. Imagine medir a altura de um aluno e compará-la com a de um único colega. Se ele for "
     "mais baixo, você não pode concluir que tem altura típica; só que não é mais alto que aquele colega. E se "
     "o próprio colega for atípico, a comparação inteira desloca. O v1 também trata 2022 como se fosse medido sem "
     "erro, quando ele foi estimado pelo mesmo modelo, com a mesma incerteza.",
     "Uma classe de referência com várias eleições (2º turno presidencial de 2010, 2014, 2018 e 2022 e os "
     "segundos turnos de governador desses anos). Cada estatístico passa a ter uma distribuição de referência, e "
     "2026 é reportado pelo percentil em que cai. A incerteza de cada eleição entra no cálculo."),
    (2, "grave", "Modelos nulos mal calibrados",
     "O modelo do C1 erra por um fator de 3 nos dois anos (O/E de 2,7 e 3,1). O modelo limpo de Klimek atribui "
     "\"fraude incremental\" a 60% das seções de 2022 e a 71% do governador. O v1 diz que a comparação com 2022 "
     "resolve isso.",
     "Um p-valor só tem o significado que promete se o modelo nulo descrever bem os dados quando não há nada. Se "
     "o modelo já erra muito sem fraude, um p-valor pequeno mede o erro do modelo, não a fraude. Comparar com "
     "2022 só cancela o erro se ele for <i>o mesmo</i> nos dois anos (como uma balança desregulada: comparar dois "
     "pesos na mesma balança funciona só se o desvio for constante). Essa premissa não foi testada.",
     "Diagnósticos de calibração antes de qualquer teste: probabilidade prevista contra frequência observada "
     "por faixa (gráfico de calibração), checagem preditiva das contagens baixas e do histograma 2D. A premissa "
     "de erro constante passa a ser testada na classe de referência: se o erro do modelo varia muito entre "
     "eleições limpas, isso entra na distribuição de referência."),
    (3, "grave", "\"Compatível\" não é \"igual\"",
     "Cinco testes saíram \"compatível com 2022\". Só o C6 tinha faixa de equivalência.",
     "Não rejeitar uma hipótese não é aceitá-la. Ausência de evidência não é evidência de ausência. Um teste "
     "com pouco poder \"não acha nada\" quase sempre, e isso não diz que não há nada. Para afirmar que duas "
     "coisas são parecidas é preciso fixar antes o quanto é \"parecido\" (uma margem) e mostrar que o intervalo "
     "inteiro cabe nela. É o teste de equivalência (TOST, dois testes unilaterais).",
     "Margem de equivalência registrada para cada teste antes de rodar, e a leitura em três categorias: "
     "equivalente (intervalo dentro da margem), atípico (fora, na direção alegada) e inconclusivo (atravessa a "
     "margem). \"Compatível\" sai do vocabulário."),
    (4, "grave", "A análise de poder é circular",
     "O P1 planta fraude S em cima do dado observado e conclui que \"se S tivesse acontecido, teríamos visto\".",
     "Se S tivesse acontecido, o dado observado já seria \"limpo + S\". Plantar S em cima dele simula \"limpo + "
     "2S\". O argumento só vale supondo que o observado é limpo, que é justamente o que se quer testar. Além "
     "disso, a fraude foi sorteada ao acaso, e fraude real seria estratégica (em redutos, em seções de "
     "comparecimento alto, onde há pouca fiscalização). E a conclusão \"1% é detectado, logo 1,8% também\" "
     "supõe que a detecção cresce sempre com o tamanho, o que não foi verificado.",
     "Três mudanças: (a) plantar fraude também nas eleições da classe de referência, que servem de base \"limpa "
     "por hipótese\" independente de 2026, e dizer a premissa por escrito; (b) acrescentar desenhos "
     "estratégicos: concentrada nos municípios mais favoráveis ao vencedor, em seções de comparecimento alto e em "
     "seções sem fiscal (proxy: seções pequenas e rurais); (c) uma grade mais fina de tamanhos, incluindo 1,8% "
     "(o que vira a eleição), com a curva de poder em vez de pontos soltos. Intervalo de Clopper-Pearson em toda "
     "taxa reportada."),
    (5, "grave", "Inferência onde não há amostra",
     "A reconciliação diz que, com 0 divergências em 499.205 seções, o limite superior de 95% é de 6 seções "
     "divergentes por milhão (Clopper-Pearson).",
     "Intervalos de confiança medem a incerteza de usar uma amostra no lugar da população. Aqui foram conferidas "
     "<i>todas</i> as seções: é um censo. A proporção de divergentes não é estimada, é conhecida, e é zero. O "
     "limite de \"6 por milhão\" responde a uma pergunta que não existe e sugere uma incerteza que não há. A "
     "incerteza que existe é de outra natureza: os três arquivos saem da mesma fonte.",
     "O resultado passa a ser determinístico: \"0 de 499.205 seções\". O limite que importa é dito por escrito "
     "(consistência interna, não correspondência com o voto digitado). O mesmo ajuste vale para o site."),
    (6, "séria", "Graus de liberdade do pesquisador",
     "Cada teste recebeu um \"esclarecimento\" escrito antes de rodar, mas por quem já conhecia os dados. O "
     "carimbo de data é uma tag no git do próprio autor.",
     "O valor de um pré-registro está em fixar as escolhas antes de saber como elas afetam o resultado. Quando "
     "sobra muita coisa em aberto, o analista volta a escolher (mesmo de boa-fé), e o pré-registro protege menos "
     "do que parece. E um carimbo controlado pelo próprio autor pode, em princípio, ser refeito.",
     "Adendo v2 do pré-registro com as decisões que antes ficaram para depois já fixadas; registro no OSF "
     "(carimbo independente); e uma lista das escolhas feitas depois de ver dados, com o efeito de cada uma."),
    (7, "séria", "Dependência entre observações",
     "O C1 simula as seções como independentes. O C4 permuta a hora dentro do município. O BH supõe uma "
     "estrutura de dependência entre os seis p-valores.",
     "Seções do mesmo local de votação e da mesma zona se parecem (mesmo bairro, mesmo eleitorado, mesma "
     "logística). Tratar observações correlacionadas como independentes encolhe os erros-padrão e torna os "
     "p-valores pequenos demais. O BH controla a taxa de falsas descobertas sob independência ou dependência "
     "positiva; os seis testes usam os mesmos dados, e isso não foi verificado.",
     "Simulação do C1 com efeito aleatório por local de votação; permutação do C4 em blocos (local e zona); "
     "erros agrupados no nível mais alto plausível; e Benjamini–Yekutieli (válido sob qualquer dependência) ao "
     "lado do BH."),
    (8, "séria", "Política confundida com fraude",
     "2026 é comparado com 2022 sem nenhum controle além do 1º turno da mesma seção.",
     "Candidatos, terceira via, comparecimento e economia mudaram entre os anos. Uma diferença entre 2026 e 2022 "
     "pode ser política, não fraude, e uma semelhança pode esconder duas mudanças em sentidos opostos. A "
     "comparação protege contra falso positivo, mas enfraquece a afirmação de normalidade.",
     "A classe de referência (crítica 1) dilui a dependência de uma eleição só. Os modelos ganham o perfil do "
     "eleitorado por seção (idade, escolaridade, sexo), que o TSE publica, como controle."),
    (9, "séria", "Inferência ecológica frágil",
     "A transição usa uma identidade ad hoc (novos = max(0, ...), peso √n) e cita King e Manski sem usar os "
     "métodos deles. Cinco de dez intervalos são o próprio [0, 1].",
     "Inferência ecológica é a tentativa de saber o comportamento de indivíduos a partir de totais de grupos. "
     "Sem hipóteses fortes, o dado só permite limites (bounds), e não um ponto. Apresentar pontos com "
     "intervalos de bootstrap, num modelo escolhido sem justificativa, passa uma precisão que a identificação "
     "não dá.",
     "A seção vira identificação parcial: os limites de Duncan–Davis por município, agregados, com a "
     "estimativa de King (1997) como ilustração, e a conclusão dita como faixa. Ela sai do corpo do artigo e "
     "vai para um apêndice, porque não testa nenhuma acusação."),
    (10, "séria", "Aproximações não verificadas no poder",
     "Dentro do P1, os testes usam erros-padrão fixos, tirados da especificação sem fraude. Houve duas correções "
     "de código depois de rodar parte dos cenários.",
     "Com fraude, a variância dos estimadores muda; usar o erro-padrão do caso sem fraude pode inflar ou reduzir "
     "o poder. As correções estão documentadas, o que é correto, mas um parecerista vai querer ver o antes e "
     "o depois lado a lado e uma checagem do código.",
     "Validar a versão leve contra a completa em alguns cenários com fraude (não só sem fraude); recalcular o "
     "erro-padrão dentro da réplica onde for barato; publicar o antes e o depois das correções; e testes "
     "automatizados do plantio (o total plantado bate com o pedido)."),
    (11, "forma", "Falta a literatura", "Não há seção de literatura.",
     "Sem dialogar com o que já foi feito sobre a urna brasileira (relatórios de fiscalização de 2022, testes "
     "públicos de segurança do TSE, trabalhos acadêmicos de forense eleitoral), o leitor não sabe o que é novo.",
     "Seção de literatura curta: forense eleitoral (métodos e críticas), auditoria (risk-limiting audits) e "
     "o caso brasileiro."),
    (12, "forma", "Não tem a estrutura de um paper",
     "Resumo de cerca de 250 palavras, sem seção de dados descritivos e sem discussão separada dos resultados.",
     "Revistas pedem resumo de 150 a 200 palavras e uma estrutura previsível (introdução, literatura, dados, "
     "método, resultados, discussão). O leitor acadêmico navega por ela.",
     "Reestruturar nessa ordem, com estatística descritiva das seções (tamanho, comparecimento, fatia) em "
     "tabela própria."),
    (13, "forma", "Poucas figuras", "Uma figura em sete páginas.",
     "Testes sobre distribuições pedem que se mostre a distribuição. O histograma 2D de Klimek é o argumento "
     "visual do método, e a curva de especificações é como se mostra um multiverso.",
     "Figuras: histograma 2D (2026, referências), calibração dos modelos, posição de 2026 na distribuição de "
     "referência de cada teste, curva de especificações, curva de poder."),
    (14, "forma", "p-valores no piso de resolução",
     "\"p &lt; 0,001\" com 10.000 simulações e \"p = 1,000\" no texto.",
     "Com 10.000 simulações, o menor p-valor possível é 1/10.001. Reportá-lo como prova forte é ler o piso da "
     "régua como se fosse a medida. E p = 1 em teste unilateral só diz que o efeito foi para o outro lado.",
     "Reportar \"p &lt; 1/10.001 (piso da simulação)\" e, para efeito no sentido oposto, dizer isso em palavras "
     "com o tamanho do efeito."),
    (15, "forma", "Fuso horário não declarado",
     "O C4 usa a hora de recebimento do boletim sem dizer em que fuso ela está.",
     "Acre, Amazonas e o exterior têm fusos diferentes. Dentro do município isso não muda o resultado, mas o "
     "leitor não tem como saber sem ler o código.",
     "Declarar o fuso (o do registro do TSE) e a razão de ele não afetar a permutação."),
    (16, "forma", "Tom da conclusão",
     "\"Uma fraude capaz de mudar o resultado está descartada ao nível de 5%.\"",
     "A frase é mais forte do que a análise sustenta, dadas as críticas 1 e 4. Um leitor cético lê o tom e "
     "desconfia do resto.",
     "\"Nos formatos testados, e supondo que a referência seja limpa, uma fraude desse tamanho teria sido "
     "detectada com probabilidade de pelo menos 95%.\" O tamanho da afirmação acompanha o desenho."),
]


def bloco(n, grav, titulo, diz, problema, corrige):
    cab = Table([[Paragraph(f"<b>{n}. {titulo}</b>", E["celb"]), Paragraph(grav, E["celc"])]],
                colWidths=[13.6 * cm, 3 * cm])
    cab.setStyle(TableStyle([("BACKGROUND", (1, 0), (1, 0), COR[grav]), ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    corpo = Table([[Paragraph("O que o v1 diz", E["celb"]), Paragraph(diz, E["cel"])],
                   [Paragraph("Por que é um problema", E["celb"]), Paragraph(problema, E["cel"])],
                   [Paragraph("O que a v2 faz", E["celb"]), Paragraph(corrige, E["cel"])]],
                  colWidths=[3.2 * cm, 13.4 * cm])
    corpo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                               ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f6f6f8"))]))
    return KeepTogether([cab, corpo, Spacer(1, 10)])


def montar():
    hoje = date.today().strftime("%d/%m/%Y")
    s = [P("Parecer sobre o relatório técnico v1", "titulo"),
         P("O que um professor de estatística criticaria, e por quê", "sub"),
         P(f"estranhaeleicao.org · {hoje} · sobre <i>Padrões numéricos alegados como fraude no 2º turno presidencial "
           f"de 2026</i>, versão 1", "autor"),
         Spacer(1, 12),
         P("<b>Para que serve este documento.</b> Antes de virar artigo, o relatório v1 foi lido como um parecerista "
           "de revista leria. As dezesseis críticas abaixo estão em ordem de gravidade. Para cada uma: o que o v1 "
           "diz, por que isso é um problema (com a intuição estatística, que é o que interessa para quem está "
           "aprendendo) e o que a versão 2 faz. Ele é também o roteiro da v2."),
         P("<b>Como ler a gravidade.</b> <i>Grave</i>: sozinha, faria a revista rejeitar o artigo. <i>Séria</i>: "
           "pede revisão maior, com análises novas. <i>Forma</i>: não muda os resultados, mas muda a confiança de "
           "quem lê."),
         P("<b>O resumo do parecer.</b> O trabalho é honesto e acima da média em transparência: pré-registro, "
           "multiverso, erros documentados, limites declarados. Mas a inferência se apoia numa única eleição de "
           "referência e em modelos nulos que o próprio texto mostra estarem mal calibrados, e as conclusões de "
           "\"compatibilidade\" são mais fracas do que a redação sugere. A contribuição mais sólida hoje é "
           "descritiva: a conferência das seções e o mapa de quais testes têm poder contra quais formatos de "
           "fraude."),
         tabela([["Gravidade", "Críticas"], ["grave", "1 a 5"], ["séria", "6 a 10"], ["forma", "11 a 16"]],
                [4 * cm, 4 * cm], zebra=False,
                estilos=[("BACKGROUND", (0, 1), (0, 1), COR["grave"]), ("BACKGROUND", (0, 2), (0, 2), COR["séria"]),
                         ("BACKGROUND", (0, 3), (0, 3), COR["forma"])]),
         Spacer(1, 10)]
    s += [bloco(*c) for c in CRITICAS]
    s += [P("Três ideias para levar", "h1"),
          P("<b>1. Um p-valor herda tudo do modelo nulo.</b> Se o modelo erra sem fraude, o p-valor mede o erro. "
            "Antes de testar, mostre que o modelo descreve o caso sem efeito."),
          P("<b>2. Não rejeitar não é aceitar.</b> Para afirmar semelhança, fixe a margem antes e teste a "
            "equivalência. Para afirmar ausência, mostre o poder."),
          P("<b>3. Onde não há amostra, não há intervalo de amostragem.</b> Um censo tem outros limites (fonte, "
            "medição, definição), e são eles que precisam ser ditos.")]
    return s


def main() -> int:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(DESTINO), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm, title="Parecer sobre o relatório técnico v1",
                            author="estranhaeleicao.org", subject="Críticas didáticas e roteiro da versão 2")
    doc.build(montar(), onFirstPage=rel.rodape, onLaterPages=rel.rodape)
    print(f"→ {DESTINO} ({DESTINO.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
