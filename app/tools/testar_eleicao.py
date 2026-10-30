"""testar_eleicao.py — a versão privada da eleição (/politicos/eleicao) e o que ela afirma.

    venv/bin/python -m tools.testar_eleicao            # dados + telas (Chromium)
    venv/bin/python -m tools.testar_eleicao --sem-tela # só os dados

O produto vende NÚMEROS — "faltaram 1.925 votos", "4,5% dos válidos em Joinville" —
então o teste confere primeiro que a base diz a verdade, contra o próprio TSE:

1. Cadeiras refeitas pela lei = eleitos proclamados pelo TSE, por lista, nas QUATRO
   disputas (ALESC e Câmara, 2022 e 2026). Se uma importação perder um voto de
   legenda (o PV teve 290 em 2026 sem lançar candidato), é aqui que aparece.
2. Soma por município = total do estado (válidos da ALESC 2026).
3. Os números que a tela escreve sobre um caso conhecido (Cadorin 2026: 1º suplente,
   1.925 votos para a 2ª cadeira do NOVO).
4. Seção, bairro e perfil existem para 2022 (2026 só depois do boletim de urna).
5. A tela num Chromium, nas duas larguras: sem erro de JS, sem rolagem lateral,
   modo "resultado final" (sem Previsão/Ao vivo) e cada aba de análise desenhada.

Sem `politicos/data/eleicoes.db` (microdados não importados) o teste PULA, dizendo.
"""
from __future__ import annotations

import base64
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

falhas: list[str] = []


def checar(nome: str, ok: bool, detalhe: str = "") -> None:
    print(("  ok    " if ok else "  FALHA ") + nome + ("" if ok else f" — {detalhe}"), flush=True)
    if not ok:
        falhas.append(nome)


def teste_dados() -> None:
    from politicos import analise_eleitoral as ae
    print("os números contra o TSE")
    for ano in (2026, 2022):
        for cargo, nome in ((7, "ALESC"), (6, "Câmara SC")):
            m = ae._margens(ano, cargo)
            b = ae._base(ano, cargo)
            oficial: dict[str, int] = {}
            for c in b["cands"].values():
                if c["eleito"]:
                    oficial[c["agremiacao"]] = oficial.get(c["agremiacao"], 0) + 1
            nossa = {a: x["cadeiras"] for a, x in m["agr"].items() if x["cadeiras"]}
            checar(f"{nome} {ano}: cadeiras pela lei = eleitos do TSE ({sum(oficial.values())})", nossa == oficial,
                   f"{nossa} × {oficial}")
    con = ae._c()
    validos = con.execute("SELECT SUM(validos) FROM apuracao_mun WHERE ano=2026 AND turno=1 AND cargo=7").fetchone()[0]
    _v, _l, soma = ae._quadro(2026, 7)
    checar("ALESC 2026: soma por município (candidatos + legenda) = válidos do estado", soma == validos, f"{soma} × {validos}")
    checar("ALESC 2026: válidos = 4.271.084 (TSE)", validos == 4271084, str(validos))

    r = ae.raio_x(2026, 7, 30000)
    mg = r["margem"]
    checar("Cadorin 2026: 1º suplente do NOVO", mg["seria_o_proximo"] and mg["posicao_lista"] == 2, str(mg))
    checar("Cadorin 2026: faltaram 1.925 votos para a 2ª cadeira do NOVO", mg["falta_proxima_lista"] == 1925, str(mg))
    checar("Cadorin 2026: Joinville é 66% do voto dele", r["cidades"][0]["nm"] == "JOINVILLE" and 65 < r["cidades"][0]["peso"] < 67)
    checar("Cadorin 2026: ligado ao voto de 2022 (12.390)", (r["anterior"] or {}).get("votos") == 12390, str(r["anterior"]))
    nv = ae.partido(2026, 7, "NOVO")
    checar("NOVO 2026: 187.010 votos e 1 cadeira", nv["votos"] == 187010 and nv["margem"]["cadeiras"] == 1)
    checar("partido pela sigla de 2022 resolve a lista (PT → federação)", not ae.partido(2022, 7, "PT").get("ausente"))

    b22 = ae._base(2022, 7)
    cad22 = next(n for n, c in b22["cands"].items() if c["urna"] == "MATHEUS CADORIN")
    loc = ae.locais(2022, 7, cad22, 81795)
    checar("2022: locais de Joinville somam o voto do município (11.350)", loc and loc["total"] == 11350,
           str(loc and loc["total"]))
    sem_bairro = [x for x in (loc or {}).get("locais", []) if x["bairro"] == "—" and x["v"]]
    checar("2022: todo local com voto tem bairro (zona 105 completada)", not sem_bairro, str(sem_bairro[:3]))
    p = ae.perfil(2022, 7, cad22)
    checar("2022: perfil do eleitorado sai, sem raça/cor (o TSE não publicou)", p and len(p["dimensoes"]) >= 8
           and not any(d["dim"] == "preta_parda" for d in p["dimensoes"]))


def teste_tela() -> None:
    print("a tela num Chromium (porta própria)")
    try:
        from tools.chromium_na_vez import sync_playwright
    except ImportError:
        print("  PULOU (playwright ausente)")
        return
    from itsdangerous import TimestampSigner
    from auth import SECRET_KEY, load_users
    admin = next((u for u, d in load_users().items()
                  if (d.get("role") or ("admin" if d.get("is_admin") else "")) == "admin"), None)
    if not admin:
        print("  PULOU (nenhum admin em users.json)")
        return
    cookie = TimestampSigner(str(SECRET_KEY)).sign(base64.b64encode(json.dumps({"username": admin}).encode())).decode()
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        porta = so.getsockname()[1]
    srv = subprocess.Popen([str(RAIZ / "venv/bin/python"), "-m", "uvicorn", "main:app", "--port", str(porta),
                            "--log-level", "warning"], cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{porta}/login", timeout=2)
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            for largura, nome in ((1360, "largo"), (390, "celular")):
                ctx = nav.new_context(viewport={"width": largura, "height": 900})
                ctx.add_cookies([{"name": "session", "value": cookie, "domain": "127.0.0.1", "path": "/"}])
                pg = ctx.new_page()
                erros: list[str] = []
                pg.on("pageerror", lambda e: erros.append(str(e)))
                pg.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
                base = f"http://127.0.0.1:{porta}/politicos/eleicao"
                pg.goto(base + "#alesc", wait_until="networkidle", timeout=60000)
                pg.wait_for_selector(".ap-hemi circle", timeout=30000)
                checar(f"[{nome}] ALESC: 40 cadeiras", pg.evaluate("document.querySelectorAll('.ap-hemi circle').length") == 40)
                checar(f"[{nome}] resultado final: sem botão Previsão/Ao vivo", pg.query_selector(".ap-modo") is None)
                selos = pg.eval_on_selector_all(".ap-selo", "e => e.map(x => x.textContent.toLowerCase())")
                checar(f"[{nome}] selos = situação do TSE, nada de 'garantido'",
                       any("eleito por" in s for s in selos) and not any("garantido" in s for s in selos))
                for aba, sel in (("candidato", ".el-mapa .ap-mapa-svg path"), ("municipios", ".el-grade-mapa .ap-mapa-svg"),
                                 ("partidos", ".el-grade-mapa .ap-mapa-svg"), ("previsao", ".el-kpis-mini")):
                    pg.goto(base + "?c=2026-7-30000#" + aba, wait_until="networkidle", timeout=60000)
                    try:
                        pg.wait_for_selector(sel, timeout=60000)
                        ok = True
                    except Exception:  # noqa: BLE001
                        ok = False
                    checar(f"[{nome}] aba {aba} desenha", ok)
                    if aba == "candidato" and ok:
                        checar(f"[{nome}] candidato: o texto da margem (1.925)", "1.925" in pg.inner_text("#ap-corpo"))
                        nomes = pg.eval_on_selector_all(".el-conc-nome b", "e => e.map(x => getComputedStyle(x).color)")
                        checar(f"[{nome}] nome dentro de botão não é branco no branco",
                               nomes and all(c != "rgb(255, 255, 255)" for c in nomes), str(nomes[:2]))
                    w = pg.evaluate("document.documentElement.scrollWidth")
                    checar(f"[{nome}] {aba}: sem rolagem lateral", w <= largura + 1, f"{w}px")
                pg.goto(base + "?c=2022-7-30001#candidato", wait_until="networkidle", timeout=60000)
                pg.wait_for_selector(".el-perfil-linha", timeout=60000)
                checar(f"[{nome}] 2022: bairros, pontos e perfil",
                       pg.evaluate("document.querySelectorAll('.el-dentro tbody tr').length") >= 10
                       and pg.evaluate("document.querySelectorAll('.el-ponto').length") >= 50)
                checar(f"[{nome}] nenhum erro de JavaScript", not erros, "; ".join(erros[:3]))
                ctx.close()
            nav.close()
    finally:
        srv.terminate()


def main(argv: list[str]) -> int:
    from politicos import microdados
    if not microdados.BANCO.exists():
        print("PULOU: microdados não importados (python -m politicos.microdados tudo)")
        return 0
    teste_dados()
    if "--sem-tela" not in argv:
        teste_tela()
    print("\n" + ("✓ tudo certo" if not falhas else f"✗ {len(falhas)} falha(s): " + "; ".join(falhas)))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
