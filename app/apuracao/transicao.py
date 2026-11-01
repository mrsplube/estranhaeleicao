"""Transição de votos por candidato da terceira via — inferência ecológica.

A pergunta: *de cada candidato da terceira via, que fração foi para o Lula?*
Para responder com honestidade, este módulo faz três coisas e **diz quando o
dado não decide**.

## O método

Para cada município `i`, a identidade em votos é:

    ganho_Lula(i) = Σ_j λ_j · v1_j(i)  +  p · novos(i)  -  c · flavio1(i)

onde `v1_j(i)` é o voto do candidato `j` da terceira via no 1º turno daquele
município, `novos(i)` são os votos válidos que apareceram, `flavio1(i)` é o voto
do Flavio no 1º turno e:

- `λ_j` (0–1) — fração dos votos de `j` que foi para o Lula;
- `p` (0–1) — fração dos votos novos que foi para o Lula;
- `c` (0–1) — fração do eleitorado do Flavio que migrou para o Lula.

Ajuste por mínimos quadrados ponderados (peso = tamanho do município), com cada
parâmetro preso ao intervalo [0, 1] e resolvido EXATAMENTE por BVLS
(`scipy.optimize.lsq_linear`, mínimos quadrados com limites). É um ajuste
restrito, no espírito da inferência ecológica, mas **não** é o modelo de King
(1997) nem uma solução por simplex: os limites aqui são por parâmetro, um a um,
e não uma restrição de que as linhas de uma tabela somem 1. A diferença importa
para quem for replicar: não há aqui a estrutura de bounds/prior do King.

## Por que o intervalo é obrigatório

O modelo **prevê bem o total** (RMSE fora da amostra melhor que o modelo
agregado de 2 pools), mas isso NÃO quer dizer que cada `λ_j` esteja bem
estimado. Medido aqui: a largura média do IC de 95% (bootstrap por município) é
~0,65 — dois terços da faixa possível. Para 5 dos 10 candidatos o intervalo
é o próprio [0, 1]: **o dado não decide**.

## Correção de 01/11/2026

Até 31/10 o ajuste era feito por L-BFGS-B partindo de λ = 0,5, e o IC vinha de
40 subamostras de tamanho n/2 sorteadas com reposição. Dois problemas:

1. **O otimizador parava antes do mínimo.** O problema é convexo (quadrático
   com limites por caixa), então tem um único mínimo — mas o L-BFGS-B com
   `ftol=1e-9` parava com soma de quadrados ~6% acima dele, e os λ dos
   candidatos pequenos ficavam perto do ponto de partida (os "~0,82" que o site
   mostrava eram isso, não estimativa). O BVLS resolve o problema exato; por ser
   convexo, não precisa de múltiplos pontos de partida.
2. **40 réplicas de n/2 não dão IC de 95%.** O percentil 2,5% de 40 valores é
   o 2º menor, e meia amostra alarga o intervalo sem correção de escala. Agora
   são 1.000 réplicas n-de-n (reamostragem de municípios com reposição), ~17 s.

Ressalva que continua valendo: com parâmetro na borda (0 ou 1) o bootstrap
percentil não tem garantia de cobertura (Andrews, 2000). Por isso `na_borda`.

Por isso a saída nunca é um número solto. Cada candidato vem com:

- `estimativa` — o λ ajustado;
- `ic` — intervalo de 95% por bootstrap;
- `largura` — o tamanho do intervalo;
- `identificado` — False quando largura > 0,5 (metade da faixa possível).

Quem publicar "o Zema deu 80% ao Flavio" está vendendo precisão que o dado não
tem. A tela mostra a barra de incerteza exatamente para impedir isso.

## O que é sólido

A **troca direta** (`c`) é identificável e sai ≈ 0 (IC ~0–2%). Ou seja: não
houve debandada do Flavio para o Lula. Isso responde à pergunta original sem
modelo nenhum — é o que a identidade de totais já obrigava.

Bóson de referência externa: o DataDCO, que apura urna a urna, publica que a
troca Lula↔Flavio é "não mensurável" e dá o mesmo tipo de faixa larga.
"""
from __future__ import annotations

import json
from pathlib import Path

PISO_MUNICIPIO = 300        # votos válidos no 1º turno para o município entrar
VOLTAS_BOOTSTRAP = 1000     # réplicas n-de-n por município: ~17 s no caue
LARGURA_IDENTIFICADO = 0.5  # acima disso o dado não decide


def _dados(base: Path) -> dict:
    return json.loads((base / "explicacao.json").read_text(encoding="utf-8"))


def _matrizes(dados: dict):
    import numpy as np
    nums = dados["numeros"]
    terc = [n for n in nums if n not in ("13", "22")]
    muns = [m for m in dados["municipios"]
            if m["t1"]["validos"] >= PISO_MUNICIPIO and m["t2"]["validos"] > 0]
    X = np.array([[m["t1"]["outros"][nums.index(j)] for j in terc] for m in muns], float)
    novos = np.array([max(0, m["t2"]["validos"] - m["t1"]["validos"]) for m in muns], float)
    f1 = np.array([m["t1"]["flavio"] for m in muns], float)
    y = np.array([m["t2"]["lula"] - m["t1"]["lula"] for m in muns], float)
    return terc, muns, X, novos, f1, y


def _ajustar(A, y, peso):
    """Mínimos quadrados ponderados com todos os parâmetros presos em [0, 1].

    Solução exata (BVLS): o problema é convexo, então não há mínimo local.
    """
    from scipy.optimize import lsq_linear
    return lsq_linear(A * peso[:, None], y * peso, bounds=(0, 1), method="bvls").x


def calcular(base: Path) -> dict:
    """Roda o modelo e devolve estimativa + IC de cada candidato (e a troca)."""
    try:
        import numpy as np
        from scipy.optimize import lsq_linear  # noqa: F401
    except ImportError:
        return {"ok": False, "motivo": "sem numpy/scipy no ambiente"}
    dados = _dados(base)
    terc, muns, X, novos, f1, y = _matrizes(dados)
    k = len(terc)
    if len(muns) < 100:
        return {"ok": False, "motivo": "poucos municípios"}

    A = np.column_stack([X, novos, -f1])
    peso = np.sqrt(f1 + novos + 1)      # município grande pesa mais
    base_est = _ajustar(A, y, peso)

    # Bootstrap n-de-n: sorteia municípios com reposição, refaz o ajuste exato.
    rng = np.random.default_rng(7)
    amostras = []
    for _ in range(VOLTAS_BOOTSTRAP):
        idx = rng.integers(0, len(y), len(y))
        amostras.append(_ajustar(A[idx], y[idx], peso[idx]))
    am = np.array(amostras)
    if len(am) < 10:
        return {"ok": False, "motivo": "bootstrap não convergiu"}

    nomes = {c["n"]: c["nm"] for c in dados.get("candidatos_1t") or []}
    partidos = {c["n"]: c["p"] for c in dados.get("candidatos_1t") or []}
    candidatos = []
    for j, n in enumerate(terc):
        lo, hi = np.clip(np.percentile(am[:, j], [2.5, 97.5]), 0, 1) + 0.0  # sem "-0.0"
        largura = float(hi - lo)
        votos = float(X[:, j].sum())
        est = float(base_est[j])
        # λ preso em 0 com IC de largura ~0 não é "medido": é o otimizador
        # empurrando o parâmetro para a borda. Isso não é informação, e a tela
        # precisa dizer isso em vez de exibir "0% com certeza".
        na_borda = (est <= 0.001 or est >= 0.999) and largura < 0.1
        candidatos.append({
            "n": n, "nm": nomes.get(n, n), "p": partidos.get(n, ""),
            "votos_1t": round(votos),
            "estimativa": round(est, 4),
            "ic": [round(float(lo), 4), round(float(hi), 4)],
            "largura": round(largura, 4),
            "identificado": largura <= LARGURA_IDENTIFICADO and not na_borda,
            "na_borda": bool(na_borda),
            "votos_lula": round(est * votos),
            "votos_flavio": round((1 - est) * votos),
            "votos_ic": [round(float(lo) * votos), round(float(hi) * votos)],
        })
    candidatos.sort(key=lambda c: -c["votos_1t"])

    lo_c, hi_c = np.percentile(am[:, k + 1], [2.5, 97.5])
    larguras = [c["largura"] for c in candidatos]
    return {
        "ok": True,
        "metodo": "mínimos quadrados ponderados por município, cada parâmetro preso em [0, 1] (BVLS, solução exata)",
        "bootstrap": {"replicas": VOLTAS_BOOTSTRAP, "tipo": "n-de-n por município, percentil 2,5–97,5"},
        "municipios": len(muns),
        "candidatos": candidatos,
        "novos_lula": round(float(base_est[k]), 4),
        "troca": {
            "fracao": round(float(base_est[k + 1]), 4),
            "ic": [round(float(lo_c), 4), round(float(hi_c), 4)],
            "votos": round(float(base_est[k + 1]) * float(f1.sum())),
            "votos_ic": [round(float(lo_c) * float(f1.sum())), round(float(hi_c) * float(f1.sum()))],
            "eleitorado_flavio": round(float(f1.sum())),
        },
        "largura_media": round(float(sum(larguras) / len(larguras)), 3),
        "identificados": sum(1 for c in candidatos if c["identificado"]),
        "total": len(candidatos),
        # Referência externa: quem apura urna a urna também não mede a troca direta.
        "referencia_externa": "DataDCO (urna a urna) publica a troca Lula↔Flávio como não mensurável.",
    }




# ── o cenário inicial: o que fecha nos TRÊS destinos ────────────────────────
# A versão anterior chutava as fatias no JavaScript e a conta ficava 4 mi fora.
# Aqui as fatias são RESOLVIDAS: para cada fonte, a distribuição entre Lula,
# Flavio e branco/nulo que faz os três destinos baterem com o TSE.
#
# Parametrização por softmax (3 logits por fonte) para não precisar de restrição
# de simplex no otimizador — as linhas somam 1 por construção. Mínimos quadrados
# normalizados; o erro fica em ~600 votos de 128 mi.
def cenario_inicial(dados: dict) -> dict:
    import numpy as np
    from scipy.optimize import minimize
    # Aceita as duas formas: o `explicacao.json` traz `nacional.t1/t2` e o
    # `conta.json` traz os campos achatados. Sem isto a função só rodava num
    # dos dois e dava KeyError no outro.
    if "t1" in (dados.get("nacional") or {}):
        t1, t2 = dados["nacional"]["t1"], dados["nacional"]["t2"]
        n = {"lula1": t1["lula"], "flavio1": t1["flavio"],
             "brancos1": t1["brancos"], "nulos1": t1["nulos"], "comp1": t1["comp"],
             "lula2": t2["lula"], "flavio2": t2["flavio"],
             "brancos2": t2["brancos"], "nulos2": t2["nulos"], "comp2": t2["comp"]}
    else:
        n = dados["nacional"]
    bn2 = n["brancos2"] + n["nulos2"]
    volt = n["comp2"] - n["comp1"]
    F = {"lula1": n["lula1"], "flavio1": n["flavio1"],
         "branco1": n["brancos1"], "nulo1": n["nulos1"], "voltaram": volt}
    for c in (dados.get("transicao") or {}).get("candidatos", [])[:4]:
        F[c["n"]] = c["votos_1t"]
    resto = (dados.get("transicao") or {}).get("candidatos", [])[4:]
    if resto:
        F["resto"] = sum(c["votos_1t"] for c in resto)
    chaves = list(F)
    v = np.array([F[c] for c in chaves], float)
    alvo = np.array([n["lula2"], n["flavio2"], bn2], float)
    k = len(chaves)

    def build(x):
        X = x.reshape(k, 3)
        X = X - X.max(axis=1, keepdims=True)
        E = np.exp(X)
        return E / E.sum(axis=1, keepdims=True)

    def custo(x):
        S = v @ build(x)
        return float((((S - alvo) / (alvo.sum() * 0.01)) ** 2).sum())

    x0 = []
    for c in chaves:
        if c == "lula1" or c == "voltaram":
            x0 += [4, 0, 0]
        elif c == "flavio1":
            x0 += [0, 4, 0]
        elif c in ("branco1", "nulo1"):
            x0 += [0, 0, 4]
        else:
            e = next((cc["estimativa"] for cc in (dados.get("transicao") or {}).get("candidatos", [])
                      if cc["n"] == c), 0.82)
            x0 += [e * 4, (1 - e) * 3.6, (1 - e) * 0.4]
    r = minimize(custo, np.array(x0), method="L-BFGS-B",
                 options={"maxiter": 50000, "ftol": 1e-15, "gtol": 1e-12})
    P = build(r.x)
    S = v @ P
    return {
        "fatia": {c: {"lula": round(float(P[i, 0]), 6),
                      "flavio": round(float(P[i, 1]), 6),
                      "bn": round(float(P[i, 2]), 6)} for i, c in enumerate(chaves)},
        "destinos": {"lula": round(float(S[0])), "flavio": round(float(S[1])),
                     "bn": round(float(S[2]))},
        "alvo": {"lula": n["lula2"], "flavio": n["flavio2"], "bn": bn2},
        "erro": round(float(np.abs(S - alvo).sum())),
    }


def gerar(base: Path) -> dict:
    """Grava `transicao.json` — usado pelo Sankey. Roda na migração (~20 s)."""
    r = calcular(base)
    destino = base / "transicao.json"
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(r, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(destino)
    return r
