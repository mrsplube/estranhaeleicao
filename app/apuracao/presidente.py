"""Presidente no 2º turno: quem vence, projetado a cada atualização do TSE.

O placar parcial engana porque o Brasil não apura por igual: estados e cidades
chegam em ritmos diferentes, e cada lugar vota de um jeito. Aqui o que falta é
projetado CIDADE A CIDADE:

1. **Base do 1º turno** (`--base`): o voto de cada candidato do 2º turno em
   cada município no 1º turno, dos dados abertos do TSE
   (`votacao_partido_munzona_2026`, só o arquivo BR, que é o de presidente).
2. **Quanto já se apurou em cada município**: o `-ab.json` do 2º turno de
   cada UF (eleitores das seções totalizadas ÷ eleitorado).
3. **A virada observada em cada UF**: o 2º turno de verdade na parte apurada
   contra o que o 1º turno dava nessa MESMA parte (em logit, para não estourar
   onde um lado tem 80%). UF com pouco apurado puxa para a virada nacional.
4. **O que falta**: cada município, no que ainda não foi apurado, recebe o
   1º turno dele mais a virada da UF; o volume é o voto válido do 1º turno ×
   a razão 2º/1º turno observada.

A incerteza é sobre a fatia de cada candidato no que falta (não sobre o que já
foi contado): um erro próprio de cada UF, maior enquanto ela apurou pouco, e um
erro nacional comum a todas, que encolhe conforme o país apura. A chance de
vitória é a normal da margem projetada sobre esse desvio.

**Decidido matematicamente** não depende de modelo: a diferença já é maior que
todo o voto que ainda pode entrar (eleitores das seções que faltam + anulados
sub judice) — a mesma régua de `matematica.py`.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import sys
import zipfile
from pathlib import Path

from apuracao import estado as est

UFS_2T = est.UFS + ["zz"]          # zz = exterior
NOMES = {**est.NOMES_UF, "zz": "Exterior"}
URL_BASE = ("https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_partido_munzona/"
            "votacao_partido_munzona_2026.zip")

# Parâmetros do erro (fatia de um candidato no voto que FALTA, em pontos de 0–1):
K_UF = 20_000          # votos válidos apurados na UF para confiar metade na virada dela
SIG_UF = 0.025         # quanto a virada de uma UF pode diferir da nacional
SIG_RES = 0.012        # resíduo dentro da UF (capital × interior, ordem das seções)
SIG_NAC = 0.03         # erro nacional comum enquanto quase nada foi apurado (seção que
K_NAC = 5_000_000      # chega cedo não é sorteio) — cai à metade da variância com 5 mi
K_RHO = 20_000         # mesma ideia para a razão de comparecimento 2º/1º turno


def _base_caminho() -> Path:
    from apuracao import coleta
    return coleta.DADOS / "base_pres_1t.json"


def gerar_base(numeros: list[str], zip_local: Path | None = None) -> dict:
    """{uf: {cd_municipio: [válidos 1º turno, votos do nº A, votos do nº B…]}}."""
    import httpx
    if zip_local is None:
        from apuracao import coleta
        zip_local = coleta.DADOS / "partido_munzona_2026.zip"
        with httpx.stream("GET", URL_BASE, headers={"User-Agent": "Mozilla/5.0"},
                          timeout=httpx.Timeout(120.0, connect=10.0)) as r:
            r.raise_for_status()
            with zip_local.open("wb") as f:
                for pedaco in r.iter_bytes(1 << 16):
                    f.write(pedaco)
    base: dict[str, dict[str, list[int]]] = {}
    with zipfile.ZipFile(zip_local) as z:
        nome = next(n for n in z.namelist() if n.endswith("_BR.csv"))
        with z.open(nome) as bruto:
            leitor = csv.DictReader(io.TextIOWrapper(bruto, encoding="latin-1"), delimiter=";")
            for lin in leitor:
                if lin["NR_TURNO"] != "1" or lin["CD_CARGO"] != "1":
                    continue
                uf, cd = lin["SG_UF"].lower(), lin["CD_MUNICIPIO"].zfill(5)   # o -ab.json usa 5 dígitos
                v = int(lin["QT_VOTOS_NOMINAIS_VALIDOS"] or 0) + int(lin["QT_TOTAL_VOTOS_LEG_VALIDOS"] or 0)
                m = base.setdefault(uf, {}).setdefault(cd, [0] + [0] * len(numeros))
                m[0] += v
                if lin["NR_PARTIDO"] in numeros:
                    m[1 + numeros.index(lin["NR_PARTIDO"])] += v
    return {"numeros": numeros, "ufs": base}


def carregar_base() -> dict | None:
    try:
        return json.loads(_base_caminho().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _i(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def _cands(d: dict) -> list[dict]:
    out = []
    for a in d["carg"][0]["agr"]:
        for p in a["par"]:
            for c in p["cand"]:
                out.append({"n": c["n"], "nm": c["nmu"], "p": p["sg"], "v": _i(c.get("vap")),
                            "e": c.get("e") == "s", "cor": est.cor(p["sg"].upper())})
    out.sort(key=lambda c: c["n"])
    return out


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _expit(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def projetar(brutos: dict[str, dict], base: dict | None = None) -> dict | None:
    """O que a página do 2º turno desenha: placar, projeção, chance e UFs.

    `brutos` tem `pres_br`, `pres_{uf}` (resultado da UF) e `abp_{uf}` (% apurado
    por município da UF), todos da eleição do 2º turno.
    """
    br = brutos.get("pres_br")
    if not br or str(br.get("t")) != "2":
        return None
    base = base if base is not None else carregar_base()
    cands = _cands(br)
    if len(cands) != 2:
        return None
    A, B = cands[0]["n"], cands[1]["n"]
    nums = (base or {}).get("numeros") or []
    tem_base = bool(base) and A in nums and B in nums
    ia, ib = (1 + nums.index(A), 1 + nums.index(B)) if tem_base else (0, 0)

    # 1ª passada: o que cada UF já mostrou (2º turno × 1º turno na mesma parte apurada)
    ufs = []
    for uf in UFS_2T:
        d = brutos.get(f"pres_{uf}")
        if not d:
            continue
        cs = {c["n"]: c["v"] for c in _cands(d)}
        e = d.get("e") or {}
        mun_b = (base or {}).get("ufs", {}).get(uf, {}) if tem_base else {}
        frac, tes = {}, {}
        for m in (brutos.get(f"abp_{uf}") or {}).get("abr", []):
            if m.get("tpabr") != "mun":
                continue
            te = _i((m.get("e") or {}).get("te"))
            if te:
                cd = str(m["cdabr"]).zfill(5)
                frac[cd], tes[cd] = _i(m["e"].get("est")) / te, te
        # O -ab.json e o resultado da UF podem ser de minutos diferentes: o
        # eleitorado apurado do resultado manda, e as frações se ajustam a ele.
        est_ab = sum(f * te for f, te in ((frac[cd], tes[cd]) for cd in frac))
        if est_ab > 0 and _i(e.get("est")):
            k = _i(e.get("est")) / est_ab
            frac = {cd: min(1.0, f * k) for cd, f in frac.items()}
        u = {"uf": uf, "nome": NOMES[uf], "a": cs.get(A, 0), "b": cs.get(B, 0),
             "te": _i(e.get("te")), "est": _i(e.get("est")),
             "pst": est._f((d.get("s") or {}).get("pst"))}
        u["v2c"] = u["a"] + u["b"]
        # 1º turno na parte apurada e na que falta, município a município
        va1c = vb1c = vt1c = 0.0
        resto = []
        for cd, m in mun_b.items():
            f = frac.get(cd.zfill(5))
            if f is None:            # município sem linha no -ab (raro): conta como não apurado
                f = 0.0
            va1c += f * m[ia]; vb1c += f * m[ib]; vt1c += f * m[0]
            if f < 1:
                resto.append((1 - f, m[0], m[ia], m[ib]))
        u.update(va1c=va1c, vb1c=vb1c, vt1c=vt1c, resto=resto)
        if tem_base and u["v2c"] and va1c + vb1c > 0:
            u["virada"] = _logit(u["a"] / u["v2c"]) - _logit(va1c / (va1c + vb1c))
        else:
            u["virada"] = None
        ufs.append(u)
    if not ufs:
        return None

    n_tot = sum(u["v2c"] for u in ufs if u["virada"] is not None)
    virada_nac = (sum(u["v2c"] * u["virada"] for u in ufs if u["virada"] is not None) / (n_tot + 100_000)
                  if n_tot else 0.0)
    v2c_tot = sum(u["v2c"] for u in ufs)
    vt1c_tot = sum(u["vt1c"] for u in ufs)
    rho_nac = min(max((v2c_tot + 200_000 * 1.0) / (vt1c_tot + 200_000), 0.8), 1.25)

    # 2ª passada: o que falta em cada UF
    var_uf = 0.0
    falta_tot = 0.0
    proj_a = proj_b = 0.0
    for u in ufs:
        lam = K_UF / (u["v2c"] + K_UF) if u["virada"] is not None else 1.0
        virada = virada_nac if u["virada"] is None else (1 - lam) * u["virada"] + lam * virada_nac
        rho = (u["v2c"] + K_RHO * rho_nac) / (u["vt1c"] + K_RHO) if tem_base else rho_nac
        rho = min(max(rho, 0.8), 1.25)   # o casamento de município falhou se sair disso
        fa = fb = 0.0
        if tem_base:
            for falta, vt1, va1, vb1 in u["resto"]:
                vr = falta * vt1 * rho
                if vr <= 0:
                    continue
                s1 = (va1 + 0.5) / (va1 + vb1 + 1.0)
                sa = _expit(_logit(s1) + virada)
                fa += vr * sa
                fb += vr * (1 - sa)
        elif u["te"]:
            # Sem a base: o que falta vota como o que já veio na UF
            vr = (u["te"] - u["est"]) * (u["v2c"] / u["est"] if u["est"] else 0.75)
            sa = u["a"] / u["v2c"] if u["v2c"] else 0.5
            fa, fb = vr * sa, vr * (1 - sa)
        falta = fa + fb
        sig2 = SIG_RES ** 2 + (lam * SIG_UF) ** 2
        var_uf += (2 * falta) ** 2 * sig2
        falta_tot += falta
        proj_a += u["a"] + fa
        proj_b += u["b"] + fb
        u.update(falta=round(falta), falta_a=round(fa), falta_b=round(fb),
                 pa_falta=round(100 * fa / falta, 2) if falta else None,
                 virada_pp=None if u["virada"] is None else round(100 * (
                     _expit(_logit(0.5) + virada) - 0.5), 2),
                 propria=round(1 - lam, 2),
                 pa_fim=round(100 * (u["a"] + fa) / (u["v2c"] + falta), 2) if u["v2c"] + falta else None)
    sig_nac = SIG_NAC * math.sqrt(K_NAC / (v2c_tot + K_NAC))
    var = var_uf + (2 * falta_tot * sig_nac) ** 2
    margem = proj_a - proj_b
    dp = math.sqrt(var) if var > 0 else 0.0
    total = proj_a + proj_b
    if dp > 0:
        chance_a = _phi(margem / dp)
    else:
        chance_a = 1.0 if margem > 0 else 0.0 if margem < 0 else 0.5
    meia = 1.645 * dp / (2 * total) if total else 0.0       # faixa de 90% na fatia
    pa = proj_a / total if total else 0.5

    # Régua matemática: o que AINDA pode entrar, todo para quem está atrás.
    e_br, v_br = br.get("e") or {}, br.get("v") or {}
    a_ag = next(c["v"] for c in cands if c["n"] == A)
    b_ag = next(c["v"] for c in cands if c["n"] == B)
    pode_entrar = _i(e_br.get("esnt")) + _i(v_br.get("vansj"))
    decidido = None
    if abs(a_ag - b_ag) > pode_entrar:
        decidido = A if a_ag > b_ag else B
    eleito = next((c["n"] for c in _cands(br) if c["e"]), None)
    if eleito or decidido:                      # a conta fechou: nada de "99,8%"
        chance_a = 1.0 if (eleito or decidido) == A else 0.0

    for c in cands:
        eh_a = c["n"] == A
        c.update(pct=round(100 * c["v"] / (a_ag + b_ag), 3) if a_ag + b_ag else 0.0,
                 proj=round(100 * (pa if eh_a else 1 - pa), 3),
                 proj_min=round(100 * ((pa if eh_a else 1 - pa) - meia), 3),
                 proj_max=round(100 * ((pa if eh_a else 1 - pa) + meia), 3),
                 votos_proj=round(proj_a if eh_a else proj_b),
                 chance=round(100 * (chance_a if eh_a else 1 - chance_a), 3))
    lista_uf = [{k: u[k] for k in ("uf", "nome", "a", "b", "pst", "falta", "falta_a", "falta_b",
                                    "pa_falta", "virada_pp", "propria", "pa_fim")} for u in ufs]
    lista_uf.sort(key=lambda u: -u["falta"])
    return {
        "turno": "2",
        "apuracao": est._apuracao(br),
        "candidatos": cands,
        "a": A, "b": B,
        "margem_agora": a_ag - b_ag,
        "margem_proj": round(margem),
        "dp_margem": round(dp),
        "falta_proj": round(falta_tot),
        "pode_entrar": pode_entrar,
        "decidido": decidido,
        "eleito": eleito,
        "tem_base": tem_base,
        "virada_nacional_pp": round(100 * (_expit(virada_nac) - 0.5), 2),
        "ufs": lista_uf,
    }


def ponto(p: dict) -> dict:
    """Um ponto da linha do tempo da noite (serie_pres.jsonl)."""
    a = p["candidatos"][0] if p["candidatos"][0]["n"] == p["a"] else p["candidatos"][1]
    return {"pst": p["apuracao"]["pst"], "agora": a["pct"], "proj": a["proj"],
            "min": a["proj_min"], "max": a["proj_max"], "chance": a["chance"]}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Previsão do 2º turno presidencial")
    ap.add_argument("--base", action="store_true", help="baixa o 1º turno por município e grava a base")
    ap.add_argument("--zip", help="usar este zip já baixado em vez de baixar")
    a = ap.parse_args(argv)
    if a.base:
        from apuracao import coleta
        br = json.loads((coleta.BRUTOS / "pres_br.json").read_text(encoding="utf-8"))
        numeros = [c["n"] for c in _cands(br)] if str(br.get("t")) == "2" else ["13", "22"]
        b = gerar_base(numeros, Path(a.zip) if a.zip else None)
        destino = _base_caminho()
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(json.dumps(b, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, destino)
        n = sum(len(v) for v in b["ufs"].values())
        tot = [sum(m[i] for u in b["ufs"].values() for m in u.values()) for i in range(1 + len(numeros))]
        print(f"base gravada: {n} municípios em {len(b['ufs'])} UFs; válidos {tot[0]:,}; "
              + "; ".join(f"nº {x}: {tot[1 + i]:,}" for i, x in enumerate(numeros)))
        if not a.zip:
            (coleta.DADOS / "partido_munzona_2026.zip").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
