"""Raio-X eleitoral de um candidato, em PDF — o que o gabinete leva para a reunião.

    GET /politicos/eleicao/raio-x.pdf?ano=2026&cargo=7&n=30000

Duas páginas A4 com o mesmo conteúdo da aba Candidato de /politicos/eleicao,
saído de `analise_eleitoral` (nada é recalculado aqui): quem é e quanto fez, a
cadeira pela lei, o mapa de força em SC, de onde vem o voto, cidade a cidade
com 2022 ao lado, quem disputa o mesmo eleitor, os bairros da maior cidade e o
perfil do eleitorado das seções. Autocontido em reportlab, como o boletim.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Path as Caminho, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from politicos import analise_eleitoral as ae

MAPA = Path(__file__).resolve().parent.parent / "static" / "apuracao" / "sc-mapa.json"
TINTA = colors.HexColor("#0f172a")
SUAVE = colors.HexColor("#64748b")
LINHA = colors.HexColor("#e2e8f0")
FUNDO = colors.HexColor("#f1f5f9")
DESTAQUE = colors.HexColor("#b45309")
FUNDO_DESTAQUE = colors.HexColor("#fef3c7")
ESCALA = ["#dbe9f6", "#a9cce6", "#6aa7d4", "#3a7fbf", "#1d5698", "#0b3168"]
SEM_VOTO = "#eef1f5"
LARGURA_UTIL = A4[0] - 30 * mm


def _n(x, casas: int = 0) -> str:
    if x is None:
        return "—"
    s = f"{x:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x, casas: int = 1) -> str:
    return "—" if x is None else _n(x, casas) + "%"


def _estilos() -> dict:
    base = dict(fontName="Helvetica", textColor=TINTA)
    return {
        "titulo": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=TINTA),
        "sub": ParagraphStyle("s", fontSize=9, leading=12, textColor=SUAVE, fontName="Helvetica"),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=TINTA,
                             spaceBefore=10, spaceAfter=4),
        "p": ParagraphStyle("p", fontSize=9.5, leading=13, **base),
        "forte": ParagraphStyle("f", fontSize=10.5, leading=14, fontName="Helvetica-Bold", textColor=TINTA),
        "destaque": ParagraphStyle("d", fontSize=10, leading=14, fontName="Helvetica-Bold", textColor=DESTAQUE,
                                   backColor=FUNDO_DESTAQUE, borderPadding=(5, 6, 5, 6), spaceBefore=4, spaceAfter=6),
        "mudo": ParagraphStyle("m", fontSize=7.5, leading=10, textColor=SUAVE, fontName="Helvetica"),
        "kpi_v": ParagraphStyle("kv", fontName="Helvetica-Bold", fontSize=14, leading=16, textColor=TINTA),
        "kpi_r": ParagraphStyle("kr", fontName="Helvetica-Bold", fontSize=6.5, leading=8, textColor=SUAVE),
        "kpi_n": ParagraphStyle("kn", fontSize=7, leading=9, textColor=SUAVE, fontName="Helvetica"),
    }


def _esc(t) -> str:
    return (str(t or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _kpis(itens: list[tuple[str, str, str]], e: dict) -> Table:
    celulas = [[Paragraph(_esc(r).upper(), e["kpi_r"]), Paragraph(_esc(v), e["kpi_v"]), Paragraph(_esc(n), e["kpi_n"])]
               for r, v, n in itens]
    por_linha = 3
    linhas = [celulas[i:i + por_linha] for i in range(0, len(celulas), por_linha)]
    linhas[-1] += [""] * (por_linha - len(linhas[-1]))
    t = Table([[c for c in linha] for linha in linhas], colWidths=[LARGURA_UTIL / por_linha] * por_linha)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, LINHA),
                           ("INNERGRID", (0, 0), (-1, -1), 0.5, LINHA), ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _tabela(cab: list[str], linhas: list[list], larguras: list[float], direita: tuple = ()) -> Table:
    t = Table([cab] + linhas, colWidths=larguras, repeatRows=1)
    estilo = [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7), ("TEXTCOLOR", (0, 0), (-1, 0), SUAVE),
              ("FONT", (0, 1), (-1, -1), "Helvetica", 8), ("TEXTCOLOR", (0, 1), (-1, -1), TINTA),
              ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINHA), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for col in direita:
        estilo.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(estilo))
    return t


# ── mapa de força ───────────────────────────────────────────────────────────
_mapa_cache: dict = {}


def _malha() -> dict:
    if not _mapa_cache:
        _mapa_cache.update(json.loads(MAPA.read_text(encoding="utf-8")))
    return _mapa_cache


def _quebras(valores: list[float]) -> list[float]:
    v = sorted(x for x in valores if x > 0)
    if not v:
        return []
    return [v[min(len(v) - 1, len(v) * i // len(ESCALA))] for i in range(1, len(ESCALA))]


def _cor(x: float, qs: list[float]) -> str:
    if not x:
        return SEM_VOTO
    i = 0
    while i < len(qs) and x > qs[i]:
        i += 1
    return ESCALA[i]


def mapa_forca(cidades: list[dict], largura: float = LARGURA_UTIL * 0.62) -> Drawing:
    m = _malha()
    k = largura / m["largura"]
    alto = m["altura"] * k
    forca = {str(c["cd"]): c["forca"] for c in cidades if c["v"]}
    qs = _quebras(list(forca.values()))
    d = Drawing(largura, alto + 26)
    numero = re.compile(r"-?\d+(?:\.\d+)?")
    for cd, x in m["municipios"].items():
        p = Caminho(fillColor=colors.HexColor(_cor(forca.get(cd, 0), qs)), strokeColor=colors.white, strokeWidth=0.25)
        for anel in x["d"].split("M")[1:]:
            nums = [float(v) for v in numero.findall(anel)]
            pts = list(zip(nums[0::2], nums[1::2]))
            if len(pts) < 3:
                continue
            p.moveTo(pts[0][0] * k, alto + 26 - pts[0][1] * k)
            for px, py in pts[1:]:
                p.lineTo(px * k, alto + 26 - py * k)
            p.closePath()
        d.add(p)
    # legenda
    faixas = [(SEM_VOTO, "sem voto")]
    ant = 0.0
    for i, lim in enumerate(qs + [None]):
        faixas.append((ESCALA[i], f"acima de {_pct(ant, 2)}" if lim is None else f"até {_pct(lim, 2)}"))
        ant = lim if lim is not None else ant
    x0 = 0
    for cor_, rot in faixas:
        d.add(Rect(x0, 4, 8, 6, fillColor=colors.HexColor(cor_), strokeColor=None))
        d.add(String(x0 + 10, 4.5, rot, fontName="Helvetica", fontSize=5.5, fillColor=SUAVE))
        x0 += 12 + len(rot) * 2.6
    return d


# ── o documento ─────────────────────────────────────────────────────────────
def gerar(ano: int, cargo: int, numero: int) -> tuple[bytes, str] | None:
    d = ae.raio_x(ano, cargo, numero)
    if not d:
        return None
    e = _estilos()
    hist = []

    titulo = f"Raio-X eleitoral · {d['nm']}"
    hist.append(Paragraph(_esc(titulo), e["titulo"]))
    hist.append(Paragraph(_esc(f"{d['ac']} ({d['partido']}) · nº {d['n']} · {d['cargo_nome']} · SC {d['ano']} · "
                               f"{(d['situacao'] or '').lower()}"), e["sub"]))
    hist.append(Spacer(1, 6))

    kp = [("Votos", _n(d["votos"]), (f"{_pct(d['pct'], 2)} dos válidos · " if d["pct"] is not None else "")
           + (f"{d['posicao']}º de {d['candidatos']}" if d["posicao"] else ""))]
    if d["anterior"]:
        a = d["anterior"]
        var = (d["votos"] - a["votos"]) / a["votos"] * 100 if a["votos"] and a["cargo"] == d["cargo"] else None
        kp.append((f"Em {a['ano']}", _n(a["votos"]), f"{a['cargo_nome']} · {a['situacao']}"
                   + (f" · {'+' if var >= 0 else '−'}{abs(round(var))}%" if var is not None else "")))
    con = d["concentracao"]
    kp.append(("Concentração", _pct(con["top1"], 0), f"do voto numa cidade · {con['municipios']} municípios com voto"))
    if d.get("previsao") and d["previsao"].get("p_eleito") is not None:
        kp.append(("Previsão antes da eleição", _pct(d["previsao"]["p_eleito"] * 100, 0), "de chance de eleição"))
    if d.get("previsao") and d["previsao"].get("receita"):
        kp.append(("Custo por voto", "R$ " + _n(d["previsao"]["receita"] / max(1, d["votos"]), 2),
                   "R$ " + _n(d["previsao"]["receita"]) + " de receita declarada"))
    if d.get("instagram"):
        ig = d["instagram"]
        kp.append(("Instagram", _n(ig.get("seguidores")), "@" + ig["username"]))
    hist.append(_kpis(kp, e))

    m = d.get("margem")
    if m:
        hist.append(Paragraph("A cadeira, pela lei", e["h2"]))
        lista = f"{d['ac']} fez {m['cadeiras_lista']} {'cadeira' if m['cadeiras_lista'] == 1 else 'cadeiras'}"
        if d["eleito"]:
            hist.append(Paragraph(_esc(f"Eleito como {m['posicao_lista']}º da lista de {m['tamanho_lista']}. {lista}."), e["forte"]))
            if m.get("sobre_1o_suplente") is not None:
                hist.append(Paragraph(_esc(f"Ficou {_n(m['sobre_1o_suplente'])} votos à frente do 1º suplente "
                                           f"({m['primeiro_suplente']})."), e["p"]))
        elif m["cadeiras_lista"] == 0:
            hist.append(Paragraph(_esc(f"A lista ({d['ac']}) não elegeu ninguém."), e["forte"]))
            if m.get("falta_proxima_lista") is not None:
                hist.append(Paragraph(_esc(f"Faltaram {_n(m['falta_proxima_lista'])} votos à lista para a primeira cadeira."), e["p"]))
        else:
            hist.append(Paragraph(_esc(("1º suplente: " if m["seria_o_proximo"] else f"{m['posicao_lista']}º da lista: ") + lista + "."), e["forte"]))
            if m["seria_o_proximo"] and m.get("falta_proxima_lista") is not None:
                hist.append(Paragraph(_esc(f"Com mais {_n(m['falta_proxima_lista'])} votos para o {d['ac']}, a lei dava a "
                                           "próxima cadeira à lista — e ela seria dele."), e["destaque"]))
            if m.get("para_passar_ultimo") is not None:
                hist.append(Paragraph(_esc(f"Para passar o último eleito da lista ({m['ultimo_eleito']}), faltaram "
                                           f"{_n(m['para_passar_ultimo'])} votos."), e["p"]))
        hist.append(Paragraph(_esc(f"Quociente eleitoral {_n(m['qe'])}; 10% = {_n(m['piso_10'])}, 20% = {_n(m['piso_20'])}. "
                                   "As contas refazem a distribuição oficial com votos a mais ou a menos."), e["mudo"]))

    hist.append(Paragraph("Onde está o voto", e["h2"]))
    lado = [[Paragraph(_esc(c["nm"]), e["p"]), Paragraph(_pct(c["peso"], 1), e["p"])] for c in d["cidades"][:12] if c["v"]]
    t_lado = Table([[Paragraph("<b>DE ONDE VEM</b>", e["kpi_r"]), Paragraph("<b>PESO</b>", e["kpi_r"])]] + lado,
                   colWidths=[LARGURA_UTIL * 0.26, LARGURA_UTIL * 0.1])
    t_lado.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, LINHA), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                                ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    bloco = Table([[mapa_forca(d["cidades"]), t_lado]], colWidths=[LARGURA_UTIL * 0.63, LARGURA_UTIL * 0.37])
    bloco.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    hist.append(bloco)
    hist.append(Paragraph(_esc(f"Cor = força: o voto dele ÷ os válidos da cidade. Nº efetivo de cidades: "
                               f"{_n(con['n_efetivo'], 1)} · 5 maiores = {_pct(con['top5'], 0)} do voto · "
                               f"1º lugar em {con['em_1o']} · 5% ou mais dos válidos em {con['acima_5pct']}."), e["mudo"]))

    hist.append(PageBreak())
    hist.append(Paragraph("Cidade a cidade", e["h2"]))
    tem_ant = bool(d["anterior"])
    cab = ["Cidade", "Votos", "Peso", "Força", "Posição", "Quem liderou"] + ([str(d["anterior"]["ano"]), "Δ"] if tem_ant else [])
    linhas = []
    for c in [c for c in d["cidades"] if c["v"]][:28]:
        lin = [c["nm"].title(), _n(c["v"]), _pct(c["peso"], 1), _pct(c["forca"], 2),
               f"{c['pos']}º de {c['de']}" if c["pos"] else "—", (c["lider"] or "ele").title()[:24]]
        if tem_ant:
            lin += [_n(c["v_ant"]) if c["v_ant"] is not None else "—",
                    ("+" if (c["v"] - (c["v_ant"] or 0)) >= 0 else "−") + _n(abs(c["v"] - (c["v_ant"] or 0)))]
        linhas.append(lin)
    larg = [0.22, 0.09, 0.08, 0.08, 0.12, 0.23] + ([0.09, 0.09] if tem_ant else [])
    hist.append(_tabela(cab, linhas, [x * LARGURA_UTIL for x in larg], direita=(1, 2, 3, 4) + ((6, 7) if tem_ant else ())))

    if d["concorrentes"]:
        hist.append(Paragraph("Quem disputa o mesmo eleitor", e["h2"]))
        hist.append(_tabela(["Candidato", "Lista", "Votos", "Sobreposição", "Situação"],
                            [[c["nm"].title(), c["ac"] + (" (mesma lista)" if c["mesma_lista"] else ""), _n(c["v"]),
                              _pct(c["sobreposicao"], 0), (c["st"] or "").lower()] for c in d["concorrentes"][:8]],
                            [x * LARGURA_UTIL for x in (0.3, 0.25, 0.12, 0.13, 0.2)], direita=(2, 3)))
        hist.append(Paragraph("Sobreposição = quanto do voto dos dois vem das mesmas cidades, na mesma proporção.", e["mudo"]))

    if d["secoes"] and d["cidades"]:
        maior = d["cidades"][0]
        loc = ae.locais(d["ano"], d["cargo"], d["n"], maior["cd"])
        if loc and loc["bairros"]:
            bairros = [b for b in loc["bairros"] if b["v"]][:14]
            hist.append(KeepTogether([
                Paragraph(_esc(f"Dentro de {maior['nm'].title()}: os bairros"), e["h2"]),
                _tabela(["Bairro", "Votos", "Força", "Locais"],
                        [[b["bairro"].title(), _n(b["v"]), _pct(b["forca"], 2), str(b["locais"])] for b in bairros],
                        [x * LARGURA_UTIL for x in (0.5, 0.15, 0.15, 0.2)], direita=(1, 2, 3))]))
        p = ae.perfil(d["ano"], d["cargo"], d["n"])
        if p:
            hist.append(KeepTogether([
                Paragraph("Onde ele é forte, pelo perfil do eleitorado", e["h2"]),
                _tabela(["Grupo", "Seções dele", "Média", "Índice"],
                        [[x["rotulo"], _pct(x["meu"], 0), _pct(x["geral"], 0), str(x["indice"])] for x in p["dimensoes"]],
                        [x * LARGURA_UTIL for x in (0.4, 0.2, 0.2, 0.2)], direita=(1, 2, 3)),
                Paragraph(_esc(f"Eleitorado das seções (TSE, {p['ano_perfil']}) pesado pelo voto dele, contra o mesmo pesado "
                               "pelo voto de todos. Índice 100 = igual à média. Inferência ecológica: compara seções, não pessoas."),
                          e["mudo"])]))
    else:
        hist.append(Spacer(1, 6))
        hist.append(Paragraph("O voto por seção (bairros, locais e perfil do eleitorado) entra quando o TSE publicar o "
                              "boletim de urna desta eleição.", e["mudo"]))

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(SUAVE)
        canvas.drawString(15 * mm, 9 * mm, f"Projetos Cauê Neves · Políticos SC · fontes: TSE (resultados e dados abertos) · "
                                           f"gerado em {datetime.now():%d/%m/%Y %H:%M}")
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"{doc.page}")
        canvas.restoreState()

    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
                      title=titulo, author="Políticos SC").build(hist, onFirstPage=rodape, onLaterPages=rodape)
    nome = re.sub(r"[^a-z0-9]+", "-", d["nm"].lower()).strip("-")
    return buf.getvalue(), f"raio-x-{nome}-{d['ano']}.pdf"
