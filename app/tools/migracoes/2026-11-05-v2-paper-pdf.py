"""v2, Etapa 9: o paper em PDF, a partir dos JSON da v2.

    venv/bin/python -m tools.migracoes.2026-11-05-v2-paper-pdf

Ver `docs/v2-plano-execucao.md` (Etapa 9). O PDF não calcula nada: lê
`apuracao/data/arquivo/2026-2t/v2/` (disputas, calibração, leitura, multiverso,
poder, limites) e a reconciliação. Onde um arquivo ainda não existe, a seção
diz "pendente": dá para gerar rascunhos no meio do caminho.

Grava `static/relatorio/estranhaeleicao-paper-v2.pdf`.
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import date

import numpy as np
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, SimpleDocTemplate, Spacer

rel = importlib.import_module("tools.migracoes.2026-11-02-relatorio-pdf")
E, P, tabela, br, pct, git = rel.E, rel.P, rel.tabela, rel.br, rel.pct, rel.git
RAIZ = rel.RAIZ
ARQ = rel.ARQ
V2 = ARQ / "v2"
DESTINO = RAIZ / "static/relatorio/estranhaeleicao-paper-v2.pdf"
REPO = rel.REPO
VERDE, ROXO, AMBAR, AZUL, CINZA = rel.VERDE, rel.ROXO, rel.AMBAR, rel.AZUL, rel.CINZA
NOMES = {"C1": "seções com o perdedor quase zerado", "C2": "municípios fora do padrão",
         "C3": "enchimento de urna (Klimek)", "C4": "boletins tardios e mudança de voto",
         "C5": "voto sem biometria", "C6": "dispersão entre seções do município"}


def ler(nome):
    p = V2 / nome
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def disputas():
    out = {}
    for p in sorted(V2.glob("*.json")):
        if p.stem.startswith(("pres-", "gov-")) and not p.stem.endswith("nivel1"):
            out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def figura_floresta(comp: dict, refs: dict, teste: str, nome: str, tirar) -> Drawing | None:
    """Referências (cinza), intervalo de predição (faixa) e 2026 (vermelho)."""
    ys = [tirar(r) for r in refs.values() if r.get(teste)]
    ys = sorted(y for y, s in ys if y is not None)
    t26 = comp.get("T_2026")
    if not ys or t26 is None or comp.get("pi") is None:
        return None
    lo, hi = comp["pi"]
    vmin, vmax = min(ys + [lo, t26]), max(ys + [hi, t26])
    pad = 0.08 * (vmax - vmin or 1)
    vmin, vmax = vmin - pad, vmax + pad
    W, H = 15 * cm, 2.2 * cm
    d = Drawing(W, H)
    x = lambda v: 1.2 * cm + (W - 2.4 * cm) * (v - vmin) / (vmax - vmin)
    d.add(Rect(x(lo), 0.55 * cm, x(hi) - x(lo), 0.9 * cm, fillColor=colors.HexColor("#e3e8f2"), strokeColor=None))
    d.add(Line(1.2 * cm, 1.0 * cm, W - 1.2 * cm, 1.0 * cm, strokeColor=CINZA, strokeWidth=0.5))
    for y in ys:
        d.add(Circle(x(y), 1.0 * cm, 2.2, fillColor=colors.HexColor("#8a90a0"), strokeColor=None))
    d.add(Circle(x(t26), 1.0 * cm, 4, fillColor=colors.HexColor("#c0392b"), strokeColor=None))
    d.add(String(1.2 * cm, 1.75 * cm, f"{teste} — {nome}", fontName="Sans-B", fontSize=7.5, fillColor=rel.TINTA))
    for v in (vmin + pad, vmax - pad):
        d.add(String(x(v), 0.15 * cm, br(v, 3), fontName="Sans", fontSize=6.5, fillColor=CINZA, textAnchor="middle"))
    return d


def montar() -> list:
    rec = json.loads((ARQ / "reconciliacao.json").read_text(encoding="utf-8"))
    ds = disputas()
    refs = {k: r for k, r in ds.items() if r["ano"] != 2026}
    cal, leit, mult, lim = ler("calibracao.json"), ler("leitura.json"), ler("multiverso.json"), ler("limites.json")
    poderes = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in V2.glob("poder-pres-*.json")
               if not p.stem.endswith("validacao")}
    valid = ler("poder-pres-2022-validacao.json")
    lei26 = (leit or {}).get("disputas_2026", {}).get("pres-2026")
    hoje = date.today().strftime("%d/%m/%Y")
    commit = git("rev-parse", "--short", "HEAD")
    n_pres = sum(1 for k in refs if k.startswith("pres-"))
    n_gov = sum(1 for k in refs if k.startswith("gov-"))
    s = []

    # ── título e resumo ──────────────────────────────────────────────────
    leituras = lei26["leitura"] if lei26 else {}
    cont = {k: sum(1 for v in leituras.values() if v.startswith(k)) for k in ("atípico", "equivalente", "inconclusivo")}
    s += [P("Padrões numéricos alegados como fraude no 2º turno presidencial de 2026: testes pré-registrados "
            f"contra uma classe de referência de {n_pres + n_gov} disputas", "titulo"),
          P("Versão 2 (preprint)", "sub"),
          P(f"Cauê Neves · estranhaeleicao.org · {hoje}<br/>Código e dados: {REPO} (commit {commit}). Pré-registro: "
            "tags <font face='Mono'>preregistro-v1</font> e <font face='Mono'>preregistro-v2</font>. Redação e código "
            "assistidos por IA (Claude), revisados pelo autor.", "autor"), Spacer(1, 12)]
    resumo = ("Testamos seis padrões numéricos apontados como prova de fraude no 2º turno presidencial brasileiro de "
              f"2026 contra uma classe de referência de {n_pres} segundos turnos presidenciais (2010–2022) e {n_gov} de "
              "governador, com estatísticas, nulos e regras de decisão registrados antes de abrir os dados. Cada padrão "
              "é lido como atípico (fora do intervalo de predição de uma meta-análise de efeitos aleatórios, na direção "
              "alegada, com correção para seis testes), equivalente (teste de equivalência com margem fixada antes) ou "
              "inconclusivo. ")
    if lei26:
        resumo += (f"Resultado: {cont['atípico']} atípico(s), {cont['equivalente']} equivalente(s) e "
                   f"{cont['inconclusivo']} inconclusivo(s). ")
    else:
        resumo += "Resultado: pendente. "
    resumo += ("Os arquivos públicos do Boletim de Urna, da votação e do detalhe por seção coincidem nas 499.205 seções. "
               "Medimos também o poder dos testes contra fraude plantada nas eleições de referência, inclusive em "
               "formatos estratégicos. Uma troca pequena e uniforme em todas as urnas não é detectável por nenhum teste "
               "sobre o resultado agregado.")
    s += [P("<b>Resumo.</b> " + resumo, "resumo"),
          P("<b>Palavras-chave:</b> forense eleitoral; pré-registro; meta-análise; teste de equivalência; análise de "
            "poder; Brasil.", "resumo"),
          P("<b>Classificação JEL:</b> C12, C18, D72.", "resumo")]

    # ── 1. introdução ────────────────────────────────────────────────────
    s += [P("1. Introdução", "h1"),
          P("Depois do 2º turno presidencial de 2026 circularam acusações de fraude apoiadas em padrões numéricos: "
            "seções com o candidato derrotado quase zerado, municípios que viraram \"demais\", boletins que chegaram "
            "tarde e favoreceram o vencedor, voto sem biometria. Cada acusação compara um número de 2026 com uma "
            "intuição do que seria normal. Este trabalho troca a intuição por uma referência medida: o mesmo cálculo "
            "em todas as eleições comparáveis desde 2010, feitas no mesmo sistema."),
          P("Separamos três perguntas. <b>Atipicidade</b>: o padrão de 2026 é raro na classe de referência? "
            "<b>Detecção</b>: se houvesse fraude de um certo tamanho e formato, os testes a encontrariam? "
            "<b>Atribuição</b>: se é atípico, a causa é fraude? Testes sobre resultado agregado respondem às duas "
            "primeiras. A terceira exige evidência de outra natureza (a trilha física do voto) e fica fora do escopo."),
          P("A versão 1 deste trabalho comparava 2026 com uma única eleição (2022) e lia \"não rejeitar\" como "
            "\"compatível\". Uma revisão crítica (publicada no repositório) mostrou que isso não sustenta conclusões "
            "de normalidade. A versão 2 amplia a referência, troca a leitura por testes de equivalência, verifica a "
            "calibração dos modelos nulos antes de usá-los e refaz a análise de poder sobre bases independentes de "
            "2026.")]

    # ── 2. literatura ────────────────────────────────────────────────────
    s += [P("2. Literatura", "h1"),
          P("<b>Forense eleitoral.</b> Métodos estatísticos para fraude a partir de resultados agregados exploram "
            "assinaturas esperadas de manipulação: excesso de comparecimento associado a voto no vencedor (Myagkov, "
            "Ordeshook e Shakin, 2009), a \"impressão digital\" bidimensional de comparecimento e voto (Klimek et al., "
            "2012), picos em percentuais redondos (Kobak, Shpilkin e Pshenichnikov, 2016; Rozenas, 2017) e testes de "
            "dígitos (Beber e Scacco, 2012; Mebane, 2011). A mesma literatura documenta falsos positivos: Deckert, "
            "Myagkov e Ordeshook (2011) mostram que testes de dígitos não separam fraude de eleições limpas, e o "
            "próprio ajuste de modelos de mistura depende de um modelo de eleição limpa que raramente vale. Por isso a "
            "comparação com eleições de referência, e não com um valor teórico, é o centro deste desenho."),
          P("<b>Auditoria.</b> Auditorias por amostragem de risco (Stark, 2008; Lindeman e Stark, 2012) limitam a "
            "probabilidade de um resultado errado ser certificado, mas exigem um registro do voto conferido pelo "
            "eleitor. O sistema brasileiro não tem esse registro; as conferências possíveis são a do boletim impresso "
            "na seção com o arquivo publicado e a da assinatura digital de cada urna."),
          P("<b>O caso brasileiro.</b> A urna eletrônica é usada em todo o país desde 2000. Fujiwara (2015) mostra que "
            "ela reduziu o voto inválido e aumentou o peso político de eleitores de menor escolaridade, com efeitos "
            "sobre política pública. O TSE realiza testes públicos de segurança e de integridade, e em 2022 houve "
            "fiscalização por entidades externas, inclusive as Forças Armadas. Até onde sabemos, não há trabalho que "
            "teste os padrões numéricos alegados em 2026 contra uma classe de referência com regras registradas.")]

    # ── 3. dados ─────────────────────────────────────────────────────────
    linhas = [["Disputa", "Vencedor × perdedor", "Seções", "Municípios", "Hora", "Biometria"]]
    for k in sorted(ds):
        if not k.startswith("pres-"):
            continue
        r = ds[k]
        linhas.append([k.replace("pres-", "Presidente "), f"{r['vencedor']} × {r['perdedor']}", br(r["secoes"], 0),
                       br(r["municipios"], 0), "sim" if r.get("C4", {}).get("T") is not None else "não",
                       "sim" if r.get("C5", {}).get("T") is not None else "não"])
    s += [P("3. Dados", "h1"),
          P(f"Todos os arquivos são públicos (dadosabertos.tse.jus.br); o SHA-256 de cada um foi publicado antes de ele "
            f"ser aberto (<font face='Mono'>docs/preregistro/insumos-v2.sha256</font>). A unidade é a seção eleitoral, "
            f"no Brasil, presente nos dois turnos. A classe de referência tem {n_pres} segundos turnos presidenciais e "
            f"{n_gov} de governador com pelo menos 2.000 seções; em todas, os papéis são vencedor e perdedor do 2º "
            f"turno. A hora de recebimento do boletim (horário de Brasília, como registrado pelo TSE) existe a partir de "
            f"2018; a biometria por seção, em 2022 e 2026."),
          tabela(linhas, [3.4 * cm, 3.2 * cm, 2.4 * cm, 2.4 * cm, 1.8 * cm, 2.2 * cm]),
          P("Tabela 1. Disputas presidenciais. As de governador estão nos dados.", "legenda")]

    # ── 4. método ────────────────────────────────────────────────────────
    s += [P("4. Método", "h1"),
          P("<b>Testes.</b> C1: razão observado/esperado de seções com o perdedor até 10 votos, com o esperado de um "
            "modelo logístico fracionário a partir do 1º turno da mesma seção e efeito aleatório de local de votação. "
            "C2: proporção de municípios cujo resultado foge do previsto pelo 1º turno (Benjamini–Hochberg) e a "
            "fração deles a favor do vencedor. C3: as frações de fraude incremental e extrema do modelo de Klimek et "
            "al. (2012). C4: correlação, dentro do município, entre a hora de recebimento do boletim e a mudança da "
            "seção do 1º para o 2º turno, com permutação em blocos de local. C5: inclinação da mudança da seção sobre a "
            "fração de eleitores sem biometria. C6: mediana da dispersão de Pearson entre seções do mesmo município."),
          P("<b>Leitura.</b> Para cada componente, uma meta-análise de efeitos aleatórios (REML) sobre as disputas de "
            "referência dá a média μ̂, a heterogeneidade τ̂² e o intervalo de predição de 95% para uma disputa nova. "
            "<i>Atípico</i>: 2026 fora do intervalo, na direção alegada, com p ajustado por Benjamini–Hochberg e "
            "Benjamini–Yekutieli (o mais conservador) abaixo de 0,05. <i>Equivalente</i>: o intervalo de 90% da "
            "diferença entre 2026 e μ̂ dentro da margem fixada antes (TOST). <i>Inconclusivo</i>: os demais casos. "
            "Um teste cujo modelo nulo se calibra em 2026 de forma diferente das referências é inconclusivo por "
            "construção."),
          P("<b>Registro.</b> O plano foi registrado em duas etapas (v1 e v2), e cada decisão que ele deixava em "
            "aberto foi registrada antes do cálculo correspondente, com data e motivo (seção 8 do pré-registro v2). "
            "Os resultados da v1 eram conhecidos quando a v2 foi escrita; as eleições de referência não.")]

    # ── 5. reconciliação ─────────────────────────────────────────────────
    s += [P("5. Os arquivos coincidem", "h1"),
          P(f"O Boletim de Urna de cada seção, a votação por seção e o detalhe da votação foram cruzados nas "
            f"{br(rec['censo']['secoes_conferidas'], 0)} seções do 2º turno de 2026: {rec['censo']['secoes_divergentes']} "
            "divergências, e a soma é igual ao total oficial. Como todas as seções foram conferidas, não há margem "
            "de erro. O limite é de outra natureza: os três arquivos saem do TSE, e a conferência mostra consistência "
            "interna, não correspondência com o voto digitado.")]

    # ── 6. calibração ────────────────────────────────────────────────────
    s += [P("6. Calibração dos modelos nulos", "h1")]
    if cal:
        linhas = [["Teste", "Estatística de forma", "Referências (média; intervalo)", "2026", "Leitura"]]
        for c in ("C1", "C2", "C3"):
            iv = cal["intervalos"].get(c)
            v26 = cal["por_disputa"].get("pres-2026", {}).get(c)
            linhas.append([c, cal["estatisticas"][c],
                           f"{br(iv['media'], 3)}; {br(iv['lo'], 3)} a {br(iv['hi'], 3)}" if iv else "—",
                           br(v26, 3) if v26 is not None else "—", cal["leitura_2026"].get("pres-2026", {}).get(c, "—")])
        s += [P("Antes de qualquer teste, cada modelo nulo foi avaliado em todas as disputas por uma estatística de "
                "forma (não pelo próprio estatístico do teste). 2026 fora do intervalo das referências torna o teste "
                "inconclusivo."),
              tabela(linhas, [1.3 * cm, 4.6 * cm, 4.6 * cm, 2 * cm, 3.6 * cm]),
              P("Tabela 2. Calibração.", "legenda")]
    else:
        s += [P("Pendente.")]

    # ── 7. resultados ────────────────────────────────────────────────────
    s += [P("7. Resultados", "h1")]
    if lei26:
        linhas = [["Teste", "Componente", "2026", "Referência μ̂", "Intervalo de predição", "Percentil", "Leitura"]]
        figs = []
        tirar = {(t, n): f for t, n, f, _, _ in importlib.import_module("tools.migracoes.2026-11-05-v2-leitura").COMPONENTES}
        for c in lei26["componentes"]:
            if c.get("T_2026") is None:
                continue
            linhas.append([c["teste"], c["componente"], br(c["T_2026"], 3),
                           br(c["mu"], 3) if c.get("mu") is not None else "—",
                           f"{br(c['pi'][0], 3)} a {br(c['pi'][1], 3)}" if c.get("pi") else "—",
                           pct(c["percentil"], 0) if c.get("percentil") is not None else "—",
                           lei26["leitura"].get(c["teste"], "—")])
            f = figura_floresta(c, refs, c["teste"], c["componente"], tirar[(c["teste"], c["componente"])])
            if f:
                figs.append(f)
        s += [tabela(linhas, [1.1 * cm, 4.2 * cm, 1.7 * cm, 2 * cm, 3 * cm, 1.6 * cm, 2.6 * cm]),
              P("Tabela 3. Leitura de cada componente em 2026. Escalas: log para razões (C1, C2, C6).", "legenda")]
        s += [KeepTogether([f]) for f in figs]
        s += [P("Figura 1. Cada linha: as disputas de referência (cinza), o intervalo de predição de 95% (faixa) e "
                "2026 (vermelho).", "legenda")]
        gov = {k: v["leitura"] for k, v in leit["disputas_2026"].items() if k.startswith("gov-")}
        if gov:
            s += [P("Os segundos turnos de governador de 2026, nas mesmas urnas, lidos pela mesma regra e sem entrar na "
                    "conclusão: " + "; ".join(f"{k.split('-')[-1].upper()}: " +
                                              ", ".join(f"{t} {v}" for t, v in l.items()) for k, l in gov.items()) + ".",
                    "nota")]
    else:
        s += [P("Pendente.")]

    # ── 8. multiverso ────────────────────────────────────────────────────
    s += [P("8. Robustez", "h1")]
    if mult and lei26:
        linhas = [["Teste", "Variações", "Mesma leitura da principal", "Robusto (≥ 80%)"]]
        for t in sorted({v["teste"] for v in mult["variacoes"]}):
            vs = [v for v in mult["variacoes"] if v["teste"] == t]
            principal = lei26["leitura"].get(t, "")
            iguais = sum(1 for v in vs if principal.startswith(v["leitura"]))
            linhas.append([t, str(len(vs)), f"{iguais} de {len(vs)}", "sim" if iguais / len(vs) >= 0.8 else "não"])
        s += [P("Cada teste foi recalculado nas variações da v1 (piso de comparecimento, exclusão das seções do "
                "recuperador de dados, efeito fixo, limiares), em 2026 e nas quatro presidenciais de referência."),
              tabela(linhas, [2 * cm, 3 * cm, 5 * cm, 4 * cm]), P("Tabela 4. Multiverso.", "legenda")]
    else:
        s += [P("Pendente.")]

    # ── 9. poder ─────────────────────────────────────────────────────────
    s += [P("9. Poder", "h1")]
    if poderes:
        linhas = [["Desenho", "Fração", "0,25%", "0,5%", "1%", "1,8%", "3,57%"]]
        chave = {}
        for b in poderes.values():
            for c in b["cenarios"]:
                chave.setdefault((c["modo"], c["desenho"], c["fracao"], c["tamanho"]), []).append(
                    c["deteccao"].get("qualquer", 0))
        for (m, d) in (("troca", "aleatorio"), ("enchimento", "aleatorio"), ("troca", "reduto"),
                       ("troca", "comparecimento_alto"), ("enchimento", "pouca_fiscalizacao")):
            for f in (0.05, 0.20, 0.50):
                cel = [f"{m}, {d.replace('_', ' ')}", pct(f, 0)]
                for tm in (0.0025, 0.005, 0.01, 0.018, 0.0357):
                    v = chave.get((m, d, f, tm))
                    cel.append(pct(min(v), 0) if v else "—")
                linhas.append(cel)
        s += [P(f"Fraude a favor do vencedor foi plantada em {len(poderes)} das disputas presidenciais de referência, "
                "lida contra a referência sem a própria base. A tabela mostra a menor taxa de detecção entre as bases "
                "(o caso mais desfavorável). 1,8% dos válidos é a troca que viraria 2026."),
              tabela(linhas, [5.2 * cm, 1.4 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm], zebra=True),
              P("Tabela 5. Taxa de detecção por \"qualquer teste\".", "legenda")]
        if valid:
            difs = [c.get("diferenca_qualquer") for c in valid["cenarios"]]
            s += [P(f"Validação da versão leve dos testes contra a completa em 4 cenários: diferença máxima de "
                    f"{pct(max(difs), 0)} na taxa de detecção (limite registrado: 10 pontos).", "nota")]
    else:
        s += [P("Pendente.")]

    # ── 10. discussão ────────────────────────────────────────────────────
    s += [P("10. Discussão", "h1"),
          P("O que os testes permitem dizer depende das três leituras. Equivalente significa que, na escala do menor "
            "efeito de interesse fixado antes, 2026 é como a média das eleições de referência. Inconclusivo significa "
            "que o dado não distingue: nem semelhança nem diferença. Atípico significaria que 2026 está fora do que a "
            "variação entre eleições produz, o que pede explicação e não identifica a causa."),
          P("A análise de poder supõe que as eleições de referência são limpas o bastante para servir de base. Ela "
            "mostra quais formatos e tamanhos de fraude deixariam marca; não alcança uma troca uniforme e pequena em "
            "todas as urnas, que é indistinguível de mudança real de opinião e só seria excluída por uma trilha "
            "conferida pelo eleitor.")]

    # ── 11. ameaças ──────────────────────────────────────────────────────
    s += [P("11. Ameaças à validade", "h1")]
    for t_ in ("<b>Referência não sabidamente limpa.</b> As eleições de 2010 a 2022 também foram objeto de alegações; "
               "a referência é \"o mesmo sistema\", não \"sem fraude\".",
               "<b>Uma eleição de interesse.</b> 2026 é uma observação; a classe de referência dá variância à "
               "comparação, mas não transforma um caso em amostra.",
               "<b>Dados já vistos.</b> 2026 e 2022 eram conhecidos quando o plano foi escrito; as demais eleições não.",
               "<b>Aproximações.</b> Erros-padrão com o modelo fixo, C1 de um nível no poder e no multiverso; todas "
               "registradas antes e, onde possível, validadas.",
               "<b>Causalidade.</b> Mudanças de candidato, campanha e contexto entre eleições entram na heterogeneidade "
               "τ², não são controladas."):
        s.append(P("• " + t_))

    # ── apêndices ────────────────────────────────────────────────────────
    s += [P("Apêndice A. Para onde foi o voto da terceira via", "h1")]
    if lim:
        d26 = next(d for d in lim["disputas"] if d["disputa"] == "pres-2026")
        s += [P(f"Sem modelo, o dado só identifica um intervalo (Duncan e Davis, 1953; Manski, 2003). Supondo apenas "
                f"que quem votou no vencedor no 1º turno votou nele de novo, a fração da terceira via que foi ao "
                f"vencedor em 2026 fica entre {pct(d26['H1']['nacional'][0], 0)} e {pct(d26['H1']['nacional'][1], 0)}. "
                f"Supondo também que ninguém trocou o perdedor pelo vencedor, entre {pct(d26['H1_H2']['nacional'][0], 0)} "
                f"e {pct(d26['H1_H2']['nacional'][1], 0)}. Em {d26['municipios_onde_vencedor_perdeu_votos']} municípios "
                "o vencedor perdeu votos entre os turnos, o que contradiz a primeira hipótese.")]
    s += [P("Apêndice B. Reprodução", "h1"),
          P(f"Código em {REPO}; plano em <font face='Mono'>docs/v2-plano-execucao.md</font>; registros em "
            "<font face='Mono'>docs/preregistro/</font>. Cada script grava um JSON em "
            "<font face='Mono'>app/apuracao/data/arquivo/2026-2t/v2/</font>, servido em estranhaeleicao.org/dados.")]
    s += [P("Referências", "h1")]
    for r in (
        "BEBER, B.; SCACCO, A. What the numbers say: a digit-based test for election fraud. <i>Political Analysis</i>, "
        "20(2), 2012.",
        "BENJAMINI, Y.; HOCHBERG, Y. Controlling the false discovery rate. <i>JRSS B</i>, 57(1), 1995.",
        "BENJAMINI, Y.; YEKUTIELI, D. The control of the false discovery rate in multiple testing under dependency. "
        "<i>Annals of Statistics</i>, 29(4), 2001.",
        "DECKERT, J.; MYAGKOV, M.; ORDESHOOK, P. C. Benford's Law and the detection of election fraud. <i>Political "
        "Analysis</i>, 19(3), 2011.",
        "DUNCAN, O. D.; DAVIS, B. An alternative to ecological correlation. <i>American Sociological Review</i>, 18(6), "
        "1953.",
        "FUJIWARA, T. Voting technology, political responsiveness, and infant health: evidence from Brazil. "
        "<i>Econometrica</i>, 83(2), 2015.",
        "KLIMEK, P.; YEGOROV, Y.; HANEL, R.; THURNER, S. Statistical detection of systematic election irregularities. "
        "<i>PNAS</i>, 109(41), 2012.",
        "KOBAK, D.; SHPILKIN, S.; PSHENICHNIKOV, M. S. Integer percentages as electoral falsification fingerprints. "
        "<i>Annals of Applied Statistics</i>, 10(1), 2016.",
        "LINDEMAN, M.; STARK, P. B. A gentle introduction to risk-limiting audits. <i>IEEE Security &amp; Privacy</i>, "
        "10(5), 2012.",
        "MANSKI, C. F. <i>Partial Identification of Probability Distributions</i>. Springer, 2003.",
        "MEBANE, W. R. Comment on \"Benford's Law and the detection of election fraud\". <i>Political Analysis</i>, "
        "19(3), 2011.",
        "MYAGKOV, M.; ORDESHOOK, P. C.; SHAKIN, D. <i>The Forensics of Election Fraud</i>. Cambridge University Press, "
        "2009.",
        "ROZENAS, A. Detecting election fraud from irregularities in vote-share distributions. <i>Political Analysis</i>, "
        "25(1), 2017.",
        "SCHUIRMANN, D. J. A comparison of the two one-sided tests procedure and the power approach for assessing the "
        "equivalence of average bioavailability. <i>Journal of Pharmacokinetics and Biopharmaceutics</i>, 15(6), 1987.",
        "STARK, P. B. Conservative statistical post-election audits. <i>Annals of Applied Statistics</i>, 2(2), 2008.",
        "VAN DEN AKKER, O. et al. Preregistration of secondary data analysis: a template and tutorial. "
        "<i>Meta-Psychology</i>, 5, 2021."):
        s.append(P(r, "ref"))
    return s


def main() -> int:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(DESTINO), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm, title="Padrões numéricos alegados como fraude no 2º turno de 2026 (v2)",
                            author="Cauê Neves", subject="Preprint, estranhaeleicao.org")
    doc.build(montar(), onFirstPage=rel.rodape, onLaterPages=rel.rodape)
    print(f"→ {DESTINO.relative_to(RAIZ)} ({DESTINO.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
