"""Gráfico da Polymarket e mapa dos favoritos que perderam (caso "As pesquisas e as apostas").

    venv/bin/python -m tools.migracoes.2026-10-30-polymarket

Grava static/casos/polymarket.json (chance do Lula, de 1/9 à véspera e no dia
25/10 de 5 em 5 min; API pública clob.polymarket.com, mercado "Will Lula win")
e static/casos/mapa-apostas.svg (world-atlas 110m, projeção equirretangular).
"""
import json
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LULA = "30630994248667897740988010928640156931882346081873066002335460180076741328029"
CLOB = "https://clob.polymarket.com/prices-history?market=" + LULA


def pegar(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "estranhaeleicao/1.0"}), timeout=30))


def serie():
    longa = [p for p in pegar(CLOB + "&interval=max&fidelity=720")["history"]
             if datetime(2026, 9, 1).timestamp() <= p["t"] < datetime(2026, 10, 25, 8).timestamp()]
    t0, t1 = int(datetime(2026, 10, 25, 8).timestamp()), int(datetime(2026, 10, 25, 22).timestamp())
    dia = pegar(CLOB + f"&startTs={t0}&endTs={t1}&fidelity=5")["history"]
    fmt = lambda l: [[p["t"], round(100 * p["p"], 1)] for p in l]
    return {"fonte": "https://polymarket.com/event/brazil-presidential-election", "longa": fmt(longa), "dia": fmt(dia),
            "marcos": [["17:03", "Zanin prorroga a votação"], ["19:00", "fecham as últimas seções; sai a apuração"]]}


def mapa():
    topo = pegar("https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json")
    sx, sy = topo["transform"]["scale"]; tx, ty = topo["transform"]["translate"]
    arcos = []
    for a in topo["arcs"]:
        x = y = 0; pts = []
        for dx, dy in a:
            x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
        arcos.append(pts)
    W, H = 720, 330
    P = lambda lon, lat: ((lon + 180) / 360 * W, (84 - lat) / 142 * H)
    def anel(r, leste=False):
        pts = []
        for i in r:
            seg = arcos[i] if i >= 0 else arcos[~i][::-1]
            pts += seg[1:] if pts else seg
        # Quebra o traço onde o país cruza a linha de data (senão vira um risco na tela toda).
        out, ant = "", None
        for q in (P(p[0] + 360 if leste and p[0] < 0 else p[0], p[1]) for p in pts):
            out += ("M" if ant is None or abs(q[0] - ant[0]) > W / 2 else "L") + "%.1f,%.1f" % q
            ant = q
        return out + "Z"
    DESTAQUE = {"076": "br", "862": "ve", "616": "pl", "840": "us"}
    caminhos = []
    for g in topo["objects"]["countries"]["geometries"]:
        if g.get("id") == "010":   # Antártida
            continue
        polis = g.get("arcs", [])
        if g["type"] == "Polygon": polis = [polis]
        d = "".join(anel(r, g.get("id") in ("643", "242")) for poli in polis for r in poli)   # Rússia e Fiji passam da linha de data
        caminhos.append(f'<path class="{DESTAQUE.get(g.get("id"), "")}" d="{d}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" overflow="hidden"><style>path{{fill:#2a3253;stroke:#0e1326;stroke-width:.5}}'
            '.br,.ve,.pl{fill:#e6be55}.us{fill:#a07f2e}</style>' + "".join(caminhos) + "</svg>")


if __name__ == "__main__":
    (RAIZ / "static/casos/polymarket.json").write_text(json.dumps(serie()))
    (RAIZ / "static/casos/mapa-apostas.svg").write_text(mapa())
    print("ok")
