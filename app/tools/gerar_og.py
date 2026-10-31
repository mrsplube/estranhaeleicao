"""gerar_og.py — as imagens de compartilhamento (Open Graph) do site.

Em 31/10/2026 o site passou a ter uma imagem por página em `static/og/`, no
lugar do `static/og.jpg` único (que continua lá, para o que já foi postado).
Todas seguem a mesma arte: o fundo escuro da marca (as três manchas de luz do
site_base.css), a curva da apuração que a entrada usa no topo, o h1 da página
em Space Grotesk e o nome do site no pé.

    cd app && python3 tools/gerar_og.py           # regrava static/og/*.png
    cd app && python3 tools/gerar_og.py --olhar   # prova em /var/tmp/og-ensaio

Fontes: Space Grotesk e Inter (SIL Open Font License), em `static/og/fontes/`.
Sem elas o script cai no DejaVu do sistema e avisa — a arte muda de cara.
As imagens saem em PNG com paleta de 128 cores: ~25 a 40 KB cada, bem abaixo
do teto de 200 KB do WhatsApp/X.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent.parent
SAIDA = BASE / "static" / "og"
FONTES = SAIDA / "fontes"
FONTE_TITULO = FONTES / "SpaceGrotesk.ttf"
FONTE_TEXTO = FONTES / "Inter.ttf"
FONTE_SISTEMA_NEGRITO = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTE_SISTEMA = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

L, A = 1200, 630  # a medida que o Open Graph pede (1.91:1)
ESCALA = 2        # desenha no dobro e reduz: o texto fica com a borda limpa

# As cores de static/site_base.css.
FUNDO = (14, 19, 38)
LULA = (227, 54, 74)
FLAVIO = (59, 130, 246)
TERCEIRA = (167, 139, 250)
TEXTO = (228, 230, 240)
TEXTO_3 = (118, 128, 165)
DESTAQUE = (230, 190, 85)
LINHA = (45, 56, 94)


def _fonte(caminho: Path, tamanho: int, peso: str, alternativa: str) -> ImageFont.FreeTypeFont:
    """A fonte variável no peso pedido; avisa e cai no sistema se faltar."""
    if caminho.exists():
        f = ImageFont.truetype(str(caminho), int(tamanho))
        try:
            f.set_variation_by_name(peso)
        except Exception:  # fonte sem eixos variáveis: fica no peso do arquivo
            pass
        return f
    print(f"AVISO: {caminho} não existe — usando {alternativa}", file=sys.stderr)
    return ImageFont.truetype(alternativa, int(tamanho))


def _fundo() -> Image.Image:
    """O fundo do site: manchas radiais sobre o azul-noite (site_base.css)."""
    alt, larg = A * ESCALA, L * ESCALA
    y, x = np.mgrid[0:alt, 0:larg].astype(np.float32)
    base = np.zeros((alt, larg, 3), dtype=np.float32)
    base[:, :] = FUNDO

    def mancha(cx: float, cy: float, raio: float, cor: tuple[int, int, int], forca: float):
        dx = (x - cx * larg) / (raio * larg)
        dy = (y - cy * alt) / (raio * larg)
        d = np.sqrt(dx * dx + dy * dy)
        peso = np.clip(1.0 - d, 0.0, 1.0) ** 1.6 * forca
        for i in range(3):
            base[:, :, i] += (cor[i] - base[:, :, i]) * peso

    mancha(0.94, -0.10, 0.55, FLAVIO, 0.32)
    mancha(-0.10, 0.06, 0.50, LULA, 0.28)
    mancha(0.55, 1.20, 0.70, TERCEIRA, 0.12)

    # Véu no topo: o texto ganha contraste sem apagar a cor.
    veu = np.linspace(0.22, 0.0, alt, dtype=np.float32)[:, None, None]
    base = base * (1 - veu) + base * 0.5 * veu
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def _grade(img: Image.Image) -> None:
    """A malha fina pontilhada do fundo do site, só no canto da arte."""
    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    passo = 26 * ESCALA
    for gx in range(int(L * ESCALA * 0.54), L * ESCALA, passo):
        for gy in range(int(A * ESCALA * 0.10), int(A * ESCALA * 0.92), passo):
            r = 1.2 * ESCALA / 2
            d.ellipse((gx - r, gy - r, gx + r, gy + r), fill=(255, 255, 255, 16))
    img.alpha_composite(camada)


def _ler_curvas() -> list[tuple[int, int, int, list[tuple[float, float]]]]:
    """As duas curvas da apuração, do mesmo SVG que a entrada usa no topo.

    Fica só o traço fino (`stroke-width="3.5"`): o brilho é um blur aplicado
    aqui, então não precisa do path duplicado com `opacity=".45"`.
    """
    svg = (BASE / "static" / "fundo-curvas.svg").read_text(encoding="utf-8")
    curvas = []
    for m in re.finditer(r'<path d="([^"]+)" stroke="(#[0-9a-fA-F]{6})" stroke-width="3\.5"', svg):
        pontos = [(float(a), float(b)) for a, b in
                  re.findall(r"[ML](\d+(?:\.\d+)?),(\d+(?:\.\d+)?)", m.group(1))]
        c = m.group(2).lstrip("#")
        curvas.append((int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), pontos))
    return curvas


def _curvas(img: Image.Image) -> None:
    """A curva do 2º turno no canto direito, esmaecida — a arte do topo da home."""
    curvas = _ler_curvas()
    if not curvas:
        return
    # A área do SVG (800×300) encaixada no canto inferior direito.
    larg = L * ESCALA * 0.52
    alt = larg * 300 / 800
    x0 = L * ESCALA - larg + 70 * ESCALA
    y0 = A * ESCALA - alt + 18 * ESCALA
    sx, sy = larg / 800, alt / 300

    brilho = Image.new("RGBA", img.size, (0, 0, 0, 0))
    db = ImageDraw.Draw(brilho)
    nitido = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dn = ImageDraw.Draw(nitido)
    for r, g, b, pontos in curvas:
        pts = [(x0 + px * sx, y0 + py * sy) for px, py in pontos]
        if len(pts) < 2:
            continue
        db.line(pts, fill=(r, g, b, 80), width=9 * ESCALA, joint="curve")
        dn.line(pts, fill=(r, g, b, 205), width=int(2.6 * ESCALA), joint="curve")

    img.alpha_composite(brilho.filter(ImageFilter.GaussianBlur(9 * ESCALA)))
    img.alpha_composite(nitido)


def _marca(d: ImageDraw.ImageDraw, x: float, y: float, tamanho: int) -> None:
    """"estranhaeleicao.org" com a sílaba do meio em amarelo (o .hud-marca)."""
    f = _fonte(FONTE_TITULO, tamanho, "Bold", FONTE_SISTEMA_NEGRITO)
    for texto, cor in (("estranha", TEXTO), ("eleicao", DESTAQUE), (".org", TEXTO_3)):
        d.text((x, y), texto, font=f, fill=cor, anchor="ls")
        x += f.getlength(texto)


def _placa(d: ImageDraw.ImageDraw, x: float, y: float, largura: float) -> None:
    """A barra do placar do 2º turno (51,79% Lula × 48,21% Flávio), como no site."""
    alt = 14 * ESCALA
    raio = alt / 2
    esq = largura * 0.5179
    d.rounded_rectangle((x, y, x + largura, y + alt), radius=raio, fill=FLAVIO)
    d.rounded_rectangle((x, y, x + esq, y + alt), radius=raio, fill=LULA)
    d.rectangle((x + esq - raio, y, x + esq + raio, y + alt), fill=LULA)

    f = _fonte(FONTE_TEXTO, 15 * ESCALA, "SemiBold", FONTE_SISTEMA)
    yy = y + alt + 14 * ESCALA
    d.text((x, yy), "Lula 51,79%", font=f, fill=LULA, anchor="la")
    d.text((x + largura, yy), "48,21% Flávio", font=f, fill=FLAVIO, anchor="ra")


def _degrade(camada: Image.Image, texto: str, fonte: ImageFont.FreeTypeFont,
             x: float, y: float) -> None:
    """Uma palavra do título em degradê — o `<span>` do h1 no site.

    Pinta uma máscara do texto com o degradê do amarelo claro ao dourado e
    cola na camada. Tudo em ImageDraw "de verdade" (sem blend layer), senão
    o `alpha_composite` de outra camada apaga o que já foi desenhado.
    """
    larg = int(fonte.getlength(texto)) + 10 * ESCALA
    alt = int(fonte.size * 1.4)
    mascara = Image.new("L", (larg, alt), 0)
    ImageDraw.Draw(mascara).text((5 * ESCALA, 0), texto, font=fonte, fill=255)

    fim = mascara.getbbox()
    if not fim:
        return
    ini, falso = (250, 228, 152), (216, 176, 78)
    grad = Image.new("RGB", (larg, alt))
    dg = ImageDraw.Draw(grad)
    for i in range(larg):
        t = i / max(1, larg - 1)
        dg.line([(i, 0), (i, alt)], fill=tuple(int(a + (b - a) * t) for a, b in zip(ini, falso)))
    camada.paste(grad, (int(x) - 5 * ESCALA, int(y)), mascara)


def montar(titulo: str, etiqueta: str, arquivo: str, placa: bool = False,
           rodape: str = "dados do TSE · 2º turno de 2026") -> Path:
    """Uma arte por página: etiqueta no topo, h1 no meio, marca no pé.

    `titulo` traz as quebras de linha do h1 separadas por `|` (onde o `<br>`
    está no HTML). A última linha sai em degradê, como o `<span>` do h1.
    """
    img = _fundo()
    _grade(img)
    _curvas(img)

    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    m = 84 * ESCALA                      # margem da arte
    # A curva divide o canto direito: o texto não passa da metade de lá.
    limite = (700 if placa else 820) * ESCALA

    # Etiqueta do topo: o mesmo papel do .hero-tag das páginas.
    f_etq = _fonte(FONTE_TEXTO, 15 * ESCALA, "SemiBold", FONTE_SISTEMA)
    d.text((m, 96 * ESCALA), " ".join(etiqueta.upper()), font=f_etq, fill=DESTAQUE, anchor="ls")
    d.line((m, 122 * ESCALA, m + 46 * ESCALA, 122 * ESCALA), fill=DESTAQUE, width=3 * ESCALA)

    # O maior corpo em que o h1 cabe na largura e na altura que sobraram.
    linhas = [ln.strip() for ln in titulo.split("|") if ln.strip()]
    alt_max = (258 if placa else 300) * ESCALA
    tamanho = 96
    while tamanho > 34:
        f_tit = _fonte(FONTE_TITULO, tamanho * ESCALA, "Bold", FONTE_SISTEMA_NEGRITO)
        if (max(f_tit.getlength(x) for x in linhas) <= limite
                and len(linhas) * tamanho * ESCALA * 1.10 <= alt_max):
            break
        tamanho -= 2

    y = 196 * ESCALA
    for i, linha in enumerate(linhas):
        if i == len(linhas) - 1 and len(linhas) > 1:
            _degrade(camada, linha, f_tit, m, y)
        else:
            d.text((m, y), linha, font=f_tit, fill=TEXTO, anchor="la")
        y += f_tit.size * 1.10

    if placa:
        _placa(d, m, min(y + 24 * ESCALA, 452 * ESCALA), 430 * ESCALA)

    # Pé: a marca e a fonte do dado, para a imagem se explicar sozinha.
    _marca(d, m, A * ESCALA - 76 * ESCALA, 34 * ESCALA)
    f_pe = _fonte(FONTE_TEXTO, 15 * ESCALA, "Medium", FONTE_SISTEMA)
    d.text((L * ESCALA - m, A * ESCALA - 76 * ESCALA), rodape,
           font=f_pe, fill=TEXTO_3, anchor="rs")
    d.line((m, A * ESCALA - 40 * ESCALA, L * ESCALA - m, A * ESCALA - 40 * ESCALA),
           fill=LINHA, width=2 * ESCALA)

    img.alpha_composite(camada)
    final = img.convert("RGB").resize((L, A), Image.LANCZOS)
    destino = SAIDA / arquivo
    destino.parent.mkdir(parents=True, exist_ok=True)
    _salvar(final, destino)
    return destino


def _salvar(img: Image.Image, destino: Path) -> None:
    """PNG de paleta: mantém a arte viva e o arquivo abaixo de 100 KB."""
    p = img.quantize(colors=128, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG)
    p.save(destino, "PNG", optimize=True)
    kb = destino.stat().st_size / 1024
    try:
        nome = destino.relative_to(BASE.parent)
    except ValueError:
        nome = destino
    print(f"{nome}  {img.width}×{img.height}  {kb:.0f} KB")
    if kb > 200:
        print(f"  ATENÇÃO: {destino.name} passou de 200 KB", file=sys.stderr)


# Cada página com a sua arte. O `|` é onde o `<br>` está no h1 da página.
PAGINAS = [
    dict(arquivo="entrada.png", etiqueta="2º turno · 25/10/2026", placa=True,
         titulo="Teorias sobre|fraudes na eleição,|conferidas."),
    dict(arquivo="simulacao.png", etiqueta="simulador · 2º turno de 2026", placa=True,
         titulo="Simule o|2º turno"),
    dict(arquivo="cenarios.png", etiqueta="depois da simulação",
         titulo="Cinco jeitos|de a conta fechar"),
    dict(arquivo="detalhe.png", etiqueta="a conta do 2º turno",
         titulo="A conta do|2º turno",
         rodape="Lula 51,79% × Flávio 48,21% · dados do TSE"),
    dict(arquivo="sobre.png", etiqueta="sobre o site",
         titulo="Não confie|em nós.|Confira.",
         rodape="fontes abertas do TSE · contas públicas"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera as imagens Open Graph em static/og/.")
    ap.add_argument("--olhar", action="store_true", help="grava em /var/tmp/og-ensaio")
    args = ap.parse_args()
    global SAIDA
    if args.olhar:
        SAIDA = Path("/var/tmp/og-ensaio")
    for p in PAGINAS:
        montar(**p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
