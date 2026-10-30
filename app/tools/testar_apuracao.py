"""Testes da apuração ao vivo (/apuracao) — a conta, as rotas e a tela.

    venv/bin/python -m tools.testar_apuracao            # tudo
    venv/bin/python -m tools.testar_apuracao --ensaio /tmp/x   # só gera o ensaio

O que se confere, e por quê:

- **A conta do estado é a do TSE.** `estado.proporcional` passa pelas amostras de
  vereador de 2024 (`politicos/amostras_tse2024/`, resultado oficial dentro) e
  tem de dar as mesmas cadeiras que o TSE proclamou — é a mesma função que roda
  na noite, só que com um gabarito.
- **Ensaio com votos fictícios** sobre os arquivos REAIS de 2026 (a estrutura
  que o TSE vai preencher): toda UF fecha a soma de vagas, a Câmara soma 513,
  cada cadeira projetada tem um candidato, e a barreira é coerente com os
  próprios números.
- **As rotas**: ETag + 304 (é o que deixa a página barata), UF inexistente 404,
  freio por IP devolvendo 429, e o interruptor do /admin pedindo login.
- **A tela num Chromium de verdade**, numa porta própria apontada para o
  ensaio: nenhum erro de JS, hemiciclo com 40 bolinhas, cartões do foco,
  tabela da barreira — rota 200 não é tela que funciona.
"""
from __future__ import annotations

import json
import math
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from apuracao import coleta, estado as est   # noqa: E402

VERBOSE = "-v" in sys.argv
_falhas: list[str] = []


def checar(nome: str, ok: bool, detalhe: str = "") -> None:
    if ok:
        if VERBOSE:
            print(f"  ok   {nome}")
    else:
        _falhas.append(f"{nome} — {detalhe}")
        print(f"  FALHA {nome} — {detalhe}")


# ── ensaio ───────────────────────────────────────────────────────────────────

PESO = {"PL": 3.0, "NOVO": 1.2, "MDB": 1.6, "PSD": 1.2, "PT": 1.4, "UNIÃO": 1.0, "PP": 1.0,
        "MISSÃO": 0.6, "REPUBLICANOS": 0.8, "PODE": 0.7, "PSOL": 0.5}


def _brutos_reais() -> dict[str, dict]:
    """Os arquivos de 2026 já baixados pelo coletor (ou baixa agora)."""
    if not all((coleta.BRUTOS / f"{k}.json").exists() for k in coleta.FONTES):
        subprocess.run([sys.executable, "-m", "apuracao.coleta"], cwd=RAIZ, check=True,
                       env={**os.environ, "APURACAO_DADOS": str(coleta.DADOS)}, timeout=120)
    return {k: json.loads((coleta.BRUTOS / f"{k}.json").read_text(encoding="utf-8"))
            for k in coleta.FONTES}


def ficticio(d: dict, fracao: float, rng: random.Random) -> dict:
    """Preenche um arquivo do TSE com votos inventados, na forma que o TSE usa."""
    d = json.loads(json.dumps(d))
    if "abr" in d and "carg" not in d:
        # Acompanhamento (-ab.json): cada município/UF num ritmo próprio.
        for a in d["abr"]:
            f = min(1.0, max(0.0, rng.gauss(fracao, 0.25)))
            te = int(a["e"].get("te") or 0)
            a["e"].update(est=str(int(te * f)), esnt=str(te - int(te * f)))
            a["s"]["pst"] = f"{100 * f:.2f}".replace(".", ",")
        return d
    carg = d["carg"][0]
    vv = 0
    for a in carg["agr"]:
        for p in a["par"]:
            peso = PESO.get(p["sg"].upper(), 0.4)
            nom = 0
            for c in p["cand"]:
                v = int(fracao * rng.lognormvariate(math.log(2500 * peso), 1.3))
                c["vap"] = str(v)
                c["dvt"] = "Válido"
                if fracao < 1:
                    c["e"], c["st"] = "n", ""     # parcial: o TSE ainda não proclamou ninguém
                nom += v
            leg = int(nom * rng.uniform(0.03, 0.09))
            p.update(tvtn=str(nom), tvan=str(nom), tvtl=str(leg), tval=str(leg), dvt="Válido (legenda)")
            vv += nom + leg
    for a in carg["agr"]:
        for p in a["par"]:
            for c in p["cand"]:
                c["pvap"] = f"{100 * int(c['vap']) / vv:.2f}".replace(".", ",") if vv else "0,00"
    ts = int(d["s"]["ts"])
    d["s"].update(st=str(int(ts * fracao)), pst=f"{100 * fracao:.2f}".replace(".", ","))
    # O arquivo real que serve de molde já está totalizado (desde 04/10/2026, 21h56);
    # sem isto o ensaio parcial dizia "totalização concluída".
    d["tf"] = "s" if fracao >= 1 else "n"
    # Eleitores das seções que faltam: é o teto do voto restante na conta matemática.
    d.setdefault("e", {})["esnt"] = str(int(int(d["e"].get("te") or 0) * (1 - fracao) * 0.8))
    d["v"].update(vv=str(vv), vl=str(sum(int(p["tvtl"]) for a in carg["agr"] for p in a["par"])))
    return d


def ensaio(pasta: Path, fracao: float = 0.42, semente: int = 4) -> dict:
    """Grava em `pasta` um estado completo com votos fictícios e devolve-o."""
    rng = random.Random(semente)
    brutos = {k: ficticio(v, fracao, rng) for k, v in _brutos_reais().items()}
    (pasta / "brutos").mkdir(parents=True, exist_ok=True)
    for k, v in brutos.items():
        (pasta / "brutos" / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, "-c",
                    "from apuracao import coleta; coleta.recalcular()"],
                   cwd=RAIZ, check=True, env={**os.environ, "APURACAO_DADOS": str(pasta)}, timeout=120)
    return json.loads((pasta / "estado.json").read_text(encoding="utf-8"))


# ── testes ───────────────────────────────────────────────────────────────────

def teste_gabarito_2024() -> None:
    print("estado.proporcional contra o resultado oficial de 2024")
    for f in sorted((RAIZ / "politicos" / "amostras_tse2024").glob("*.json")):
        d = est.proporcional(json.loads(f.read_text(encoding="utf-8")))
        dif = {a["sigla"]: (a["cadeiras"], a["cadeiras_tse"]) for a in d["agremiacoes"]
               if a["cadeiras"] != a["cadeiras_tse"]}
        checar(f"{f.stem}: cadeiras = TSE", not dif, str(dif))
        eleitos_tse = {(c["nm"], c["n"]) for c in d["candidatos"] if c["e"]}
        eleitos_nossos = {(c["nm"], c["n"]) for c in d["candidatos"] if c["proj"]}
        checar(f"{f.stem}: os MESMOS eleitos", eleitos_tse == eleitos_nossos,
               f"só TSE {sorted(eleitos_tse - eleitos_nossos)[:3]} · só nós {sorted(eleitos_nossos - eleitos_tse)[:3]}")


def solidez_matematica(arquivos: list[Path], sementes: int = 3) -> tuple[int, int, int, list[str]]:
    """Apurações PARCIAIS sorteadas sobre resultados FINAIS de 2024.

    Cada candidato e cada legenda ficam com uma fração aleatória do voto final;
    o que falta é exatamente a diferença. O resultado oficial é UM dos jeitos
    de completar a apuração, então: todo "eleito garantido" tem de ter sido
    eleito, e nenhum "fora garantido" pode ter sido. (Em produção o restante é
    um teto MAIOR — eleitores das seções que faltam —, o que só deixa a conta
    mais cautelosa.)
    """
    from apuracao import matematica as mt
    from politicos import eleicao
    garantidos = foras = 0
    erros: list[str] = []
    for semente in range(sementes):
        rng = random.Random(semente)
        for f in arquivos:
            d = json.loads(f.read_text(encoding="utf-8"))
            carg = d["carg"][0]
            nv = int(carg["nv"])
            base = rng.choice([0.5, 0.8, 0.9, 0.95, 0.98, 0.995])
            listas, votos, eleitos = {}, {}, set()
            parcial = final = 0
            for a in carg["agr"]:
                lst, V = [], 0
                for p in a["par"]:
                    if p.get("dvt", "") == "Anulado":
                        continue
                    leg = int(p.get("tvtl") or 0)
                    lp = int(leg * min(1, base * rng.uniform(0.9, 1.1)))
                    final += leg
                    parcial += lp
                    V += lp
                    for c in p["cand"]:
                        if c.get("dvt", "Válido") != "Válido":
                            continue
                        vf = int(c["vap"])
                        vp = int(vf * min(1, base * rng.uniform(0.85, 1.15)))
                        final += vf
                        parcial += vp
                        V += vp
                        lst.append((vp, c["sqcand"]))
                        if c.get("e") == "s":
                            eleitos.add(c["sqcand"])
                lst.sort(key=lambda x: -x[0])
                listas[a["nm"]], votos[a["nm"]] = lst, V
            r = eleicao.distribuir(votos, nv, candidatos={l: [v for v, _ in x] for l, x in listas.items()},
                                   validos=parcial)
            agora = {cid for l, fs in r["fases"].items() for (_, cid), _f in zip(listas[l], fs)}
            for cid, st in mt.situacoes(votos, listas, nv, parcial, final - parcial, agora).items():
                if st == mt.FORA:
                    foras += 1
                    if cid in eleitos:
                        erros.append(f"{f.stem}: {cid} dado como fora e foi eleito")
                else:
                    garantidos += 1
                    if cid not in eleitos:
                        erros.append(f"{f.stem}: {cid} dado como garantido e não foi eleito")
    return garantidos, foras, len(arquivos) * sementes, erros


def teste_margem_vaga() -> None:
    print("folga da última vaga")
    # QE 250, uma sobra. A leva a 2ª cadeira com média 200. B encosta na 2ª
    # com média 150 e o próximo candidato acima de 20% do quociente.
    # Folga = (200 − 150) × 2 = 100 votos.
    cargo = {
        "qe": 250,
        "esperado": {"qe": 250},
        "agremiacoes": [
            {"id": "A", "votos": 400, "pe": 400,
             "fases": {"QP": 1, "média": 1, "3ª fase": 0},
             "fases_esp": {"QP": 1, "média": 0, "3ª fase": 0}},
            {"id": "B", "votos": 300, "pe": 500,
             "fases": {"QP": 1, "média": 0, "3ª fase": 0},
             "fases_esp": {"QP": 1, "média": 1, "3ª fase": 0}},
        ],
        "candidatos": [
            {"a": "A", "v": 220, "pe": 220, "dvt": "Válido"},
            {"a": "A", "v": 180, "pe": 180, "dvt": "Válido"},
            {"a": "B", "v": 200, "pe": 260, "dvt": "Válido"},
            {"a": "B", "v": 100, "pe": 240, "dvt": "Válido"},
        ],
    }
    agora = est.margem_da_vaga(cargo)
    checar("agora: A segura a 2ª", agora == {"dono": "A", "cadeira": 2, "fora": "B", "cadeira_fora": 2, "folga": 100},
           str(agora))
    # Na previsão B é quem tem a sobra (média 250) e A fica de fora (média 200).
    # Folga = (250 − 200) × 2 = 100.
    esp = est.margem_da_vaga(cargo, previsto=True)
    checar("previsão: B segura e A fica de fora",
           esp == {"dono": "B", "cadeira": 2, "fora": "A", "cadeira_fora": 2, "folga": 100}, str(esp))
    # Candidato de B abaixo de 20% do quociente (50): B não disputa a sobra.
    cargo["candidatos"][3]["v"] = 40
    sem = est.margem_da_vaga(cargo)
    checar("sem o piso de 20%, ninguém disputa", sem["folga"] is None, str(sem))


def teste_matematica() -> None:
    print("situação matemática (eleito/fora garantido) contra 2024")
    amostras = sorted((RAIZ / "politicos" / "amostras_tse2024").glob("*.json"))
    extra = os.environ.get("APURACAO_AMOSTRAS_2024")
    if extra:
        amostras += sorted(Path(extra).rglob("*.json"))
    g, f, n, erros = solidez_matematica(amostras, sementes=6 if not extra else 3)
    checar("nenhum garantido errado em apurações parciais", not erros, "; ".join(erros[:3]))
    checar("a conta certifica alguém (não é muda)", g > 0 and f > 0, f"{g} garantidos, {f} fora")
    if VERBOSE:
        print(f"  {n} apurações parciais: {g} eleitos garantidos, {f} fora garantidos")
    from apuracao import matematica as mt
    # Apuração encerrada: as respostas são o próprio resultado.
    for f_ in amostras[:3]:
        d = est.proporcional(json.loads(f_.read_text(encoding="utf-8")))
        ruins = [c["nm"] for c in d["candidatos"] if c["dvt"] == "Válido"
                 and (c["mat"] in (mt.ELEITO_QP, mt.ELEITO_SOBRAS)) != c["e"]]
        checar(f"{f_.stem}: encerrada, garantidos = eleitos do TSE", not ruins, str(ruins[:3]))


def _fora_apto(c: dict, previsto: bool) -> tuple[bool, str]:
    """O '1º de fora' da última vaga tem de poder disputá-la: o próximo candidato da
    lista com 20% do quociente. Em 05/10/2026 a margem era calculada sem a lista de
    candidatos e apontava o PL do ensaio (próximo candidato com 12.118 < 13.285)."""
    v = c.get("vaga_esp" if previsto else "vaga")
    if not v or not v.get("fora"):
        return True, "sem 1º de fora"
    qe = (c.get("esperado") or {}).get("qe") if previsto else c.get("qe")
    chave = "pe" if previsto else "v"
    lista = sorted((x.get(chave) if x.get(chave) is not None else x["v"]) for x in c["candidatos"]
                   if x["a"] == v["fora"] and x.get("dvt") in ("", "Válido", None))[::-1]
    prox = lista[v["cadeira_fora"] - 1] if v["cadeira_fora"] - 1 < len(lista) else 0
    return prox >= 0.2 * qe, f"{v['fora']}: próximo candidato {prox} × 20% de {qe}"


def teste_ensaio(e: dict) -> None:
    print("ensaio com votos fictícios")
    for nome, c in (("ALESC", e["sc"]["estadual"]), ("Câmara SC", e["sc"]["federal"])):
        for previsto, rot in ((False, "agora"), (True, "previsão")):
            ok, det = _fora_apto(c, previsto)
            checar(f"{nome}: o 1º de fora da última vaga ({rot}) tem candidato com 20% do QE", ok, det)
        soma = sum(a["cadeiras"] for a in c["agremiacoes"])
        checar(f"{nome}: soma das cadeiras = vagas", soma == c["vagas"], f"{soma} ≠ {c['vagas']}")
        projetados = sum(1 for x in c["candidatos"] if x["proj"])
        checar(f"{nome}: cada cadeira tem um candidato", projetados == c["vagas"], f"{projetados}")
        vv = c["apuracao"]["validos"]
        from politicos.eleicao import quociente_eleitoral
        checar(f"{nome}: QE = válidos ÷ vagas, arredondado", c["qe"] == quociente_eleitoral(vv, c["vagas"]))
        checar(f"{nome}: pst chegou", 41 < c["apuracao"]["pst"] < 43, str(c["apuracao"]["pst"]))
        for a in c["agremiacoes"]:
            if a["fases"]["QP"] > int(a["qp"]):
                checar(f"{nome}: {a['sigla']} não leva mais QP do que o quociente", False, str(a))
    cam = e["camara"]
    checar("Câmara: 513 vagas", cam["vagas"] == 513, str(cam["vagas"]))
    checar("Câmara: 513 cadeiras projetadas", sum(a["cadeiras"] for a in cam["agremiacoes"]) == 513)
    checar("Câmara: 27 UFs", len(cam["ufs"]) == 27, str(len(cam["ufs"])))
    for a in cam["agremiacoes"]:
        b = a["barreira"]
        a_ok = a["pct"] >= 2.5 and len(a["ufs_pct"]) >= 9
        b_ok = a["cadeiras"] >= 13 and len(a["ufs_cadeira"]) >= 9
        if (b["a"], b["b"], b["passa"]) != (a_ok, b_ok, a_ok or b_ok):
            checar(f"barreira coerente para {a['sigla']}", False, str(b))
    feds = [a for a in cam["agremiacoes"] if a["federacao"]]
    checar("as 5 federações aparecem como uma linha cada", len(feds) == 5,
           str([a["sigla"] for a in feds]))
    checar("NOVO e MISSÃO isolados", {"NOVO", "MISSÃO"} <= {a["id"] for a in cam["agremiacoes"]})
    pres = [c["nm"] for c in e["presidente"]["candidatos"]]
    checar("presidente traz Zema e Renan", "ZEMA" in pres and "RENAN SANTOS" in pres, str(pres[:5]))


def teste_rotas(pasta: Path) -> None:
    print("rotas")
    os.environ["APURACAO_DADOS"] = str(pasta)
    import importlib
    importlib.reload(coleta)
    from fastapi.testclient import TestClient
    import main
    from apuracao import router as rt
    rt.coleta = coleta
    anon = TestClient(main.app, follow_redirects=False)
    # O ensaio é da página AO VIVO (a da próxima eleição), com o interruptor ligado —
    # em produção ela fica arquivada entre uma eleição e outra.
    original = rt.is_visible
    rt.is_visible = lambda app, papel: True
    r = anon.get("/apuracao")
    checar("/apuracao abre sem login", r.status_code == 200, str(r.status_code))
    checar("página carrega o JS", "/static/apuracao.js" in r.text)
    r = anon.get("/apuracao/estado.json")
    checar("estado.json 200", r.status_code == 200, str(r.status_code))
    etag = r.headers.get("etag")
    checar("estado.json tem ETag", bool(etag))
    r2 = anon.get("/apuracao/estado.json", headers={"If-None-Match": etag or ""})
    checar("mesmo ETag devolve 304", r2.status_code == 304, str(r2.status_code))
    checar("UF existente 200", anon.get("/apuracao/uf/sp.json").status_code == 200)
    checar("UF inexistente 404", anon.get("/apuracao/uf/xx.json").status_code == 404)
    checar("série responde", anon.get("/apuracao/serie.json").status_code == 200)

    rt._freio_dados.vistos.clear()
    codigos = [anon.get("/apuracao/estado.json", headers={"If-None-Match": etag}).status_code
               for _ in range(rt._freio_dados.limite + 3)]
    checar("freio por IP devolve 429 depois do limite", codigos[-1] == 429, str(codigos[-4:]))
    rt._freio_dados.vistos.clear()
    rt._freio_pagina.vistos.clear()

    rt.is_visible = lambda app, papel: False
    try:
        r = anon.get("/apuracao")
        checar("interruptor desligado: página arquivada ('encerrada'), sem login",
               r.status_code == 200 and "encerrada" in r.text and "/static/apuracao.js" not in r.text, str(r.status_code))
        checar("arquivada: ?previa=1 anônimo continua vendo a encerrada",
               "/static/apuracao.js" not in anon.get("/apuracao?previa=1").text)
        checar("interruptor desligado: JSON pede login",
               anon.get("/apuracao/estado.json").status_code == 401)
        from tools.testar_rotas import cliente
        checar("interruptor desligado: logado continua vendo",
               cliente().get("/apuracao/estado.json").status_code == 200)
        checar("arquivada: logado vê a prévia com ?previa=1",
               "/static/apuracao.js" in cliente().get("/apuracao?previa=1").text)
    finally:
        rt.is_visible = original
        rt._freio_dados.vistos.clear()


def _porta_livre() -> int:
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        return so.getsockname()[1]


def teste_tela(pasta: Path, foto: Path | None = None) -> None:
    print("a tela num Chromium (porta própria, dados do ensaio)")
    try:
        from tools.chromium_na_vez import sync_playwright
    except ImportError:
        print("  (playwright ausente — pulado)")
        return
    porta = _porta_livre()
    srv = subprocess.Popen(
        [str(RAIZ / "venv/bin/python"), "-m", "uvicorn", "main:app", "--port", str(porta),
         "--log-level", "warning"], cwd=RAIZ,
        env={**os.environ, "APURACAO_DADOS": str(pasta), "APURACAO_AO_VIVO": "1"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import urllib.request
        for _ in range(90):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{porta}/apuracao/estado.json", timeout=2)
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            for largura, nome in ((1360, "largo"), (390, "celular")):
                pg = nav.new_page(viewport={"width": largura, "height": 900})
                erros: list[str] = []
                pg.on("pageerror", lambda e: erros.append(str(e)))
                pg.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
                pg.goto(f"http://127.0.0.1:{porta}/apuracao#alesc", wait_until="networkidle", timeout=60000)
                pg.wait_for_selector(".ap-hemi circle", timeout=20000)
                checar(f"[{nome}] nenhum erro de JavaScript", not erros, "; ".join(erros[:3]))
                bolas = pg.evaluate("[...document.querySelectorAll('.ap-hemi')].map(h => h.querySelectorAll('circle').length)")
                checar(f"[{nome}] ALESC: um hemiciclo só, o esperado no fim (40)", bolas == [40], str(bolas))
                checar(f"[{nome}] cartão 'Quem deve ser eleito' com a lista",
                       pg.eval_on_selector_all(".ap-esp-lista li", "e => e.length") >= 10)
                # Desde 04/10 19h33 cada modo mostra SÓ os próprios números (pedido do Cauê):
                # nada do "agora" miúdo embaixo do esperado.
                checar(f"[{nome}] cartões do foco: só os números do modo escolhido",
                       pg.eval_on_selector_all(".ap-focado", "e => e.length") >= 2
                       and pg.eval_on_selector_all(".ap-focado .ap-agora-mini", "e => e.length") == 0)
                focos = pg.eval_on_selector_all(".ap-focado .ap-focado-nome", "e => e.map(x => x.textContent)")
                checar(f"[{nome}] cartões do foco: NOVO e MISSÃO", "NOVO" in focos and "MISSÃO" in focos, str(focos))
                largura_doc = pg.evaluate("document.documentElement.scrollWidth")
                checar(f"[{nome}] sem rolagem horizontal", largura_doc <= largura + 1, f"{largura_doc}px")
                pg.wait_for_selector(".ap-mapa-svg path", timeout=20000)
                municipios = pg.eval_on_selector_all(".ap-mapa-svg path", "e => e.length")
                checar(f"[{nome}] mapa de SC com os 295 municípios", municipios == 295, str(municipios))
                pg.wait_for_selector(".ap-base-bolha", timeout=20000)
                checar(f"[{nome}] base do selecionado desenhada no mapa",
                       pg.eval_on_selector_all(".ap-base-bolha", "e => e.length") > 5)
                checar(f"[{nome}] lista diz quanto da base foi apurado",
                       "da base apurada" in pg.inner_text(".ap-base-lista"))
                if nome == "celular":
                    linhas_cand = pg.eval_on_selector_all("#ap-candidatos tbody tr", "e => e.length")
                    checar("[celular] lista de candidatos abre curta (8)", linhas_cand == 8, str(linhas_cand))
                # Seguir um candidato: estrela → cartão "Seus candidatos" → sobrevive ao recarregar.
                pg.click("#ap-candidatos tbody tr >> nth=2 >> .ap-estrela")
                pg.wait_for_selector(".ap-favs", timeout=10000)
                seguido = pg.inner_text(".ap-favs .ap-favs-nome b")
                pg.reload(wait_until="networkidle")
                pg.wait_for_selector(".ap-favs", timeout=20000)
                checar(f"[{nome}] favorito sobrevive ao recarregar", pg.inner_text(".ap-favs .ap-favs-nome b") == seguido)
                pg.click(".ap-so-favs")
                so = pg.eval_on_selector_all("#ap-candidatos tbody tr", "e => e.length")
                checar(f"[{nome}] '★ só os meus' filtra a lista", so == 1, str(so))
                # Previsão × Ao vivo: troca tudo, e a escolha fica no navegador.
                checar(f"[{nome}] abre no modo Previsão", "previsão" in pg.inner_text("#ap-candidatos thead").lower())
                pg.click(".ap-modo-btn[data-modo=aovivo]")
                pg.wait_for_function("document.querySelector('#ap-candidatos thead').innerText.toLowerCase().includes('agora')", timeout=10000)
                checar(f"[{nome}] Ao vivo: tabela de partidos em 'Cadeiras agora'",
                       "cadeiras agora" in pg.inner_text(".ap-c7 .ap-tabela thead").lower())
                pg.reload(wait_until="networkidle")
                pg.wait_for_selector(".ap-modo-btn.on", timeout=20000)
                checar(f"[{nome}] a escolha do modo sobrevive ao recarregar",
                       pg.get_attribute(".ap-modo-btn.on", "data-modo") == "aovivo")
                pg.click(".ap-modo-btn[data-modo=previsao]")
                pg.wait_for_function("document.querySelector('#ap-candidatos thead').innerText.toLowerCase().includes('previsão')", timeout=10000)
                pg.goto(f"http://127.0.0.1:{porta}/apuracao#camara-sc")
                pg.wait_for_function("!document.querySelector('.ap-favs')", timeout=10000)
                checar(f"[{nome}] favorito é por tipo de eleição (não aparece no federal)", True)
                pg.goto(f"http://127.0.0.1:{porta}/apuracao#alesc")
                pg.wait_for_selector(".ap-favs", timeout=10000)
                # Município: vai ao TSE pelo Pi (cache + teto); a tela desenha as barras.
                pg.fill("input[list=ap-mun-lista]", "FLORIANÓPOLIS")
                pg.dispatch_event("input[list=ap-mun-lista]", "change")
                try:
                    pg.wait_for_selector(".ap-mun-linha", timeout=25000)
                    checar(f"[{nome}] município abre com as barras dos partidos",
                           pg.eval_on_selector_all(".ap-mun-linha", "e => e.length") >= 5)
                except Exception as e:  # noqa: BLE001
                    checar(f"[{nome}] município abre com as barras dos partidos", False, repr(e)[:120])
                if foto:
                    pg.screenshot(path=str(foto / f"alesc-{nome}.png"), full_page=True)
                pg.goto(f"http://127.0.0.1:{porta}/apuracao#brasil")
                pg.wait_for_function("document.querySelectorAll('.ap-hemi circle').length > 100",
                                     timeout=20000)
                bolas = pg.evaluate("[...document.querySelectorAll('.ap-hemi')].map(h => h.querySelectorAll('circle').length)")
                checar(f"[{nome}] Câmara: um hemiciclo só, o esperado no fim (513)", bolas == [513], str(bolas))
                linhas = pg.eval_on_selector_all(".ap-selo.passa, .ap-selo.nao", "e => e.length")
                minimo = 15 if nome == "largo" else 8
                checar(f"[{nome}] barreira com veredito por linha", linhas >= minimo, str(linhas))
                if nome == "celular":
                    checar("[celular] barreira abre curta, com 'Todos os partidos'",
                           linhas == 8 and pg.is_visible("text=Todos os partidos"), str(linhas))
                if foto:
                    pg.screenshot(path=str(foto / f"brasil-{nome}.png"), full_page=True)
                pg.wait_for_selector(".ap-eleitos-ufs, .ap-esp-item", timeout=20000)
                checar(f"[{nome}] Câmara · Brasil: eleitos do partido escolhido, UF por UF",
                       pg.eval_on_selector_all(".ap-esp-item", "e => e.length") >= 1)
                pg.wait_for_selector(".ap-mapa-br path", timeout=20000)
                checar(f"[{nome}] mapa do Brasil com as 27 UFs",
                       pg.eval_on_selector_all(".ap-mapa-br path", "e => e.length") == 27)
                pg.click(".ap-uf >> nth=0")
                pg.wait_for_selector(".ap-voltar", timeout=20000)
                checar(f"[{nome}] UF abre a disputa dela", pg.is_visible(".ap-hemi"))
                pg.goto(f"http://127.0.0.1:{porta}/apuracao#majoritarias")
                pg.wait_for_function("!document.querySelector('.ap-hemi')", timeout=20000)
                pg.wait_for_selector(".ap-maj-linha", timeout=20000)
                pg.wait_for_selector(".ap-gov-uf, .ap-gov-grade + p, .ap-cartao .ap-mudo", timeout=20000)
                if pg.eval_on_selector_all(".ap-gov-uf", "e => e.length") == 0:
                    pg.click("text=Só UFs onde o foco disputa")
                checar(f"[{nome}] governadores e Senado pelo Brasil",
                       pg.wait_for_selector(".ap-gov-uf", timeout=20000) is not None)
                checar(f"[{nome}] majoritárias desenham", pg.eval_on_selector_all(".ap-maj-linha", "e => e.length") > 10)
                if foto:
                    pg.screenshot(path=str(foto / f"majoritarias-{nome}.png"), full_page=True)
                checar(f"[{nome}] nenhum erro de JavaScript no fim", not erros, "; ".join(erros[:3]))
                pg.close()
            nav.close()
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except subprocess.TimeoutExpired:
            srv.kill()


def main() -> int:
    if "--ensaio" in sys.argv:
        alvo = Path(sys.argv[sys.argv.index("--ensaio") + 1])
        e = ensaio(alvo)
        print(f"ensaio gravado em {alvo} (gerado_em {e['gerado_em']})")
        return 0
    print("=" * 62)
    print("apuração ao vivo")
    print("=" * 62)
    pasta = Path(tempfile.mkdtemp(prefix="apuracao-ensaio-"))
    foto = Path(sys.argv[sys.argv.index("--fotos") + 1]) if "--fotos" in sys.argv else None
    try:
        teste_margem_vaga()
        teste_gabarito_2024()
        teste_matematica()
        e = ensaio(pasta)
        teste_ensaio(e)
        teste_rotas(pasta)
        teste_tela(pasta, foto)
    except Exception as ex:  # noqa: BLE001
        _falhas.append(f"estourou: {ex!r}")
        print(f"  ERRO: {ex!r}")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    print("=" * 62)
    if _falhas:
        print(f"{len(_falhas)} falha(s):")
        for f in _falhas:
            print(f"  - {f}")
        return 1
    print("tudo passou")
    return 0


if __name__ == "__main__":
    sys.exit(main())
