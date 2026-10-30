"""Congela o 2º turno de 2026 no formato que a página já sabe desenhar.

    venv/bin/python -m tools.migracoes.2026-10-27-arquivo-2t

O `/apuracao` foi desenhado para ler `data/` enquanto o coletor reescreve os
arquivos a cada minuto. Com a eleição acabada isso não faz mais sentido, e a
regra do projeto (a mesma do 1º turno) é: **a página pública lê o ARQUIVO
congelado** em `data/arquivo/<eleição>/`, e `data/` volta a ser a pasta de
trabalho do próximo coletor.

O que este script faz, a partir de `data/` JÁ TOTALIZADO:

1. copia os brutos do 2º turno (`pres_br`, `pres_{uf}`, `abp_{uf}`, `gov_*`) para
   `arquivo/2026-2t/brutos/` — é o que o `apuracao/estado.py` lê para montar as
   abas de presidente e de governadores;
2. roda o próprio `apuracao.coleta.recalcular()` apontando `APURACAO_DADOS` para
   a pasta nova, para que `estado.json`, `majoritarias.json`, `uf/*.json` e
   `presidente.json` sejam gerados pelo MESMO código que gerou os da noite;
3. copia a linha do tempo (`serie_pres.jsonl`), que é o que a aba Presidente
   desenha no gráfico;
4. confere que a pasta nova não tem ETag de coletor nem pulso — quem serve a
   página não deve achar que há algo a conferir no TSE.

Não vai à rede: tudo já está em disco.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from apuracao import coleta   # noqa: E402

ORIGEM = RAIZ / "apuracao" / "data"
DESTINO = ORIGEM / "arquivo" / "2026-2t"

# Só o que o 2º turno desenha. Os arquivos de deputado do 1º turno (centenas de
# KB cada, por UF) ficam onde estão: o estado.json congelado já traz as cadeiras
# calculadas, e é ele que a página lê.
COPIAR = (["pres_br"] + [f"pres_{uf}" for uf in list("ac al am ap ba ce df es go ma mg "
                                                    "ms mt pa pb pe pi pr rj rn ro rr rs "
                                                    "sc se sp to".split()) + ["zz"]]
          + [f"abp_{uf}" for uf in list("ac al am ap ba ce df es go ma mg ms mt pa pb pe "
                                       "pi pr rj rn ro rr rs sc se sp to".split()) + ["zz"]]
          + [f"gov_{uf}" for uf in "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr "
                                   "rj rn ro rr rs sc se sp to".split()]
          + ["gov_sc", "sen_sc", "est_sc", "fed_sc", "ab_sc", "ab_br"])


def main() -> int:
    if not (ORIGEM / "estado.json").exists():
        print("sem data/estado.json: rode o coletor antes (ou copie o arquivo da noite).")
        return 1
    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / "brutos").mkdir(exist_ok=True)
    (DESTINO / "uf").mkdir(exist_ok=True)

    copiados = 0
    for chave in COPIAR:
        de = ORIGEM / "brutos" / f"{chave}.json"
        if de.exists():
            shutil.copy2(de, DESTINO / "brutos" / f"{chave}.json")
            copiados += 1
    print(f"brutos copiados: {copiados}")

    # A linha do tempo da noite. O coletor a reescreve a cada ponto; aqui ela vira
    # um arquivo só, com os pontos repetidos removidos (é o que a página desenha).
    serie = ORIGEM / "serie_pres.jsonl"
    if serie.exists():
        pontos, ultimo = [], None
        for linha in serie.read_text(encoding="utf-8").splitlines():
            try:
                p = json.loads(linha)
            except ValueError:
                continue
            chave = (p.get("pst"), p.get("agora"), p.get("proj"))
            if chave != ultimo:
                pontos.append(p)
            ultimo = chave
            if len(pontos) > 400:      # a noite inteira cabe; 400 pontos é o bastante
                pontos = pontos[-400:]
        (DESTINO / "serie_pres.jsonl").write_text(
            "\n".join(json.dumps(p, separators=(",", ":")) for p in pontos) + "\n", encoding="utf-8")
        print(f"linha do tempo: {len(pontos)} pontos (de {serie.stat().st_size / 1e3:.0f} KB)")

    # Os arquivos que a página serve, gerados pelo código de produção apontado
    # para a pasta nova. Assim o 2º turno congelado é idêntico ao que estava no ar.
    env = {**os.environ, "APURACAO_DADOS": str(DESTINO), "APURACAO_TURNO": "2"}
    print("recalculando estado/majoritarias/presidente na pasta congelada…")
    subprocess.run([sys.executable, "-c",
                    "from apuracao import coleta; coleta.recalcular()"],
                   cwd=RAIZ, env=env, check=True, timeout=300)

    # A base do 1º turno por município é o que a projeção do vencedor usa para
    # saber o que falta em cada cidade; sem ela `presidente.json` nem é gerado.
    base = ORIGEM / "base_pres_1t.json"
    if base.exists():
        shutil.copy2(base, DESTINO / "base_pres_1t.json")
        print(f"base do 1º turno por município: {base.stat().st_size / 1e6:.1f} MB")

    # O `presidente.projetar` procura a base em `coleta.DADOS`, que o
    # `APURACAO_DADOS` já apontou para a pasta congelada — mas ele é lido na
    # importação do módulo, então a variável é posta antes do subprocesso.

    # Deputado e Senado não mudam no 2º turno: são os MESMOS arquivos do 1º
    # turno congelado. Copiados para cá, a página do 2º turno lê uma pasta só e
    # não precisa saber que existem duas eleições no disco.
    origem_1t = ORIGEM / "arquivo" / "2026-1t"
    herdados = 0
    for nome in ("eleitos.json",):
        de = origem_1t / nome
        if de.exists():
            shutil.copy2(de, DESTINO / nome)
            herdados += 1
    for de in sorted((origem_1t / "uf").glob("*.json")):
        shutil.copy2(de, DESTINO / "uf" / de.name)
        herdados += 1
    print(f"herdados do 1º turno (Câmara/Senado, que não mudam): {herdados} arquivos")

    # Coisa de coletor vivo não vai para o arquivo: ETag, pulso e log são
    # justamente o que fazia a página achar que precisava conferir o TSE.
    for sobra in ("etags.json", "pulso.json", "coleta.log"):
        (DESTINO / sobra).unlink(missing_ok=True)

    # Os números da aba de explicação (transferência de votos, IC, conferência)
    # são calculados AQUI, uma vez. Se ficassem para a hora da visita, cada
    # abertura da página gastaria 11 s de CPU do Pi.
    print("calculando a análise do 2º turno (bootstrap, ~11 s)…")
    from apuracao import explicacao
    gerado = explicacao.gerar_cache(DESTINO)
    print(f"  analise.json e municipios.json: {gerado['n']:,} municípios")

    # A transição POR CANDIDATO (com IC) roda aqui: ~20 s de otimização.
    from apuracao import transicao
    tr = transicao.gerar(DESTINO)
    if tr.get("ok"):
        print(f"  transicao.json: {tr['identificados']}/{tr['total']} candidatos identificados; "
              f"troca Flavio->Lula = {tr['troca']['votos']:,} votos")

    # O Sankey e o limite aritmético: calculados aqui, não na visita.
    from apuracao import cenarios
    c = cenarios.gerar(DESTINO)
    if c.get("ok"):
        lim = c["limite"]
        print(f"  cenarios.json: a 3ª via deu ao Lula no mínimo {100 * lim['q_min']:.1f}% "
              f"({lim['q_min_votos']:,} votos) — limite aritmético")

    # O simulador: os três eixos e a fronteira de vitória.
    from apuracao import simulador
    sim = simulador.gerar(DESTINO)
    if sim.get("ok"):
        v = sim["variaveis"]
        print(f"  simulador.json: real = {v['real']['novos_lula']:.0f}% dos novos e "
              f"{v['real']['terceira_lula']:.2f}% da 3ª via; teto da troca {v['c_max']:,}")

    tam = sum(f.stat().st_size for f in DESTINO.rglob("*") if f.is_file())
    print(f"gravado em {DESTINO} ({tam / 1e6:.1f} MB)")
    for nome in ("estado.json", "presidente.json", "majoritarias.json", "serie_pres.jsonl"):
        p = DESTINO / nome
        print(f"  {nome}: {'ok' if p.exists() else 'FALTA'}"
              + (f" ({p.stat().st_size / 1e3:.0f} KB)" if p.exists() else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
