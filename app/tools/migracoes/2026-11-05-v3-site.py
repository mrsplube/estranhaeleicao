"""Leva a leitura da v2 e as análises da v3 para `analise.json` (página /analise).

    venv/bin/python -m tools.migracoes.2026-11-05-v3-site

Troca os resultados da v1 ("compatível") pelos da v2 (atípico/equivalente/
inconclusivo) e retira a frase de detecção com 95%, que dependia de comparar
com uma eleição só. Rodar de novo quando a curva do C3 com mediana própria terminar.
"""
from __future__ import annotations

import importlib
import json
import sys

rel = importlib.import_module("tools.migracoes.2026-11-02-relatorio-pdf")
ARQ, br = rel.ARQ, rel.br
V2 = ARQ / "v2"


BASES = (2010, 2014, 2018, 2022)


def resumo_poder() -> dict:
    """Conta os cenários do P1 nas 4 bases e procura as detecções na curva com a mediana própria."""
    cen, med = [], {}
    for ano in BASES:
        cen += [dict(c, base=ano) for c in json.loads((V2 / f"poder-pres-{ano}.json").read_text(encoding="utf-8"))["cenarios"]]
        arq = V2 / f"poder-pres-{ano}-mediana.json"
        if arq.exists():
            for c in json.loads(arq.read_text(encoding="utf-8"))["cenarios"]:
                med[(ano, c["desenho"], c["fracao"], c["tamanho"])] = c["deteccao"]["C3"]
    cabem = [c for c in cen if c["cabe"]]
    pegos = [c for c in cabem if c["deteccao"]["qualquer"] >= 0.95]
    assert len(cen) == 300 and len({(c["modo"], c["desenho"], c["fracao"], c["tamanho"]) for c in pegos}) == 1
    assert all(c["deteccao"]["C3"] >= 0.95 for c in pegos)
    assert not [c for c in cabem if 0 < c["deteccao"]["qualquer"] < 0.95]
    vira = [c for c in cabem if c["modo"] == "troca" and c["tamanho"] >= 0.018]
    return {"total": len(cen), "cabem": len(cabem), "pegos": pegos, "vira": vira, "c3_proprio": [
        (c["base"], med[k]) for c in pegos if (k := (c["base"], c["desenho"], c["fracao"], c["tamanho"])) in med]}


def main() -> int:
    a = json.loads((ARQ / "analise.json").read_text(encoding="utf-8"))
    lei = json.loads((V2 / "leitura.json").read_text(encoding="utf-8"))["disputas_2026"]["pres-2026"]
    v3 = {(c["teste"], c["componente"]): c
          for c in json.loads((V2 / "v3-referencias.json").read_text(encoding="utf-8"))["componentes"]}
    pr = json.loads((V2 / "pres-2026.json").read_text(encoding="utf-8"))
    p22 = json.loads((V2 / "pres-2022.json").read_text(encoding="utf-8"))
    comp = {(c["teste"], c["componente"]): c for c in lei["componentes"]}
    pc = lambda t, n: br(100 * comp[(t, n)]["percentil"], 0)
    k = lambda t, n: comp[(t, n)]["k"]
    pod = resumo_poder()
    assert not any(c["deteccao"]["qualquer"] for c in pod["vira"])
    prop = pod["c3_proprio"]
    anos = " e ".join(str(ano) for ano, _ in prop)
    texto_prop = (f"Com a mediana da própria amostra, a detecção cai para {br(100 * max(d for _, d in prop), 0)}% em {anos}. "
                  if prop else "")
    faltam = [ano for ano in (2010, 2014) if ano not in {x for x, _ in prop}]
    texto_p1 = (f"Quase nada detectado. Dos {pod['total']} cenários de fraude plantada, {pod['cabem']} cabem nos dados. A troca "
                f"de 1,8% ou mais dos votos, o bastante para virar 2026, não foi detectada em nenhum dos {len(pod['vira'])} "
                f"cenários em que coube. Só um formato foi pego: enchimento de 3,57% dos votos em 20% das seções, em "
                f"{len(pod['pegos'])} das 4 eleições, pelo C3. Essa conta usa o centro da eleição sem fraude, que não existe "
                f"numa eleição real, e por isso é um teto. {texto_prop}"
                + (f"A conta de {' e '.join(map(str, faltam))} ainda está rodando. " if faltam else "")
                + "Cada cenário sem detecção tem 20 réplicas: a chance real vai de 0% a 17%. A versão anterior deste teste "
                "comparava só com 2022, e o resultado dela foi retirado.")
    c1, c2, c3, c4, c5, c6 = (pr[x] for x in ("C1", "C2", "C3", "C4", "C5", "C6"))
    textos = {
        "C1": (f"Inconclusivo. São {br(c1['O'], 0)} seções contra {br(c1['E'], 0)} esperadas: {br(c1['T'], 1)} vezes. É alto, "
               f"no percentil {pc('C1', 'log O/E')} entre {k('C1', 'log O/E')} eleições, mas dentro do que a variação entre "
               f"eleições produz (p = {br(comp[('C1', 'log O/E')]['p'], 2)}). O mesmo cálculo dá {br(p22['C1']['T'], 1)} "
               "vezes para o Bolsonaro em 2022. Três disputas de referência ficam acima de 2026."),
        "C2": (f"Inconclusivo. {c2['significativos']} de {br(c2['municipios'], 0)} municípios ficam fora do previsto pelo 1º "
               f"turno, percentil {pc('C2', 'log proporção significativa')} entre {k('C2', 'log proporção significativa')} "
               f"eleições. Dos {c2['significativos']}, {c2['a_favor_vencedor']} pendem para o vencedor, percentil "
               f"{pc('C2', 'fração a favor do vencedor')}. Nada fora do comum, mas o intervalo é largo demais para dizer que é igual."),
        "C3": (f"Inconclusivo. A fraude extrema, marca do enchimento de urna, é {br(100 * c3['f_e'], 3)}% das seções: "
               f"equivalente à referência. A fraude incremental é {br(100 * c3['f_i'], 1)}%, abaixo da média das eleições "
               f"({br(100 * comp[('C3', 'f_i')]['mu'], 1)}%), percentil {pc('C3', 'f_i')}. O teste só fica sem veredito porque "
               "esse valor sai da margem para o lado contrário ao alegado."),
        "C4": (f"Inconclusivo. Dentro do município, a correlação entre a hora do boletim e a mudança da seção é "
               f"{br(c4['T'], 3)}, percentil {pc('C4', 'correlação hora × mudança')} entre "
               f"{k('C4', 'correlação hora × mudança')} eleições. Nenhum sinal de boletins tardios diferentes."),
        "C5": (f"Inconclusivo, com sinal contrário à alegação. A cada 10 pontos a mais de eleitores sem biometria, a seção "
               f"mudou {br(-10 * c5['T'], 2)} ponto a menos para o Lula. Em 2022 eram {br(10 * p22['C5']['T'], 2)} a mais. Só 2022 "
               "tem esse dado, então não há distribuição de referência."),
        "C6": (f"Inconclusivo contra todas as eleições; equivalente contra as presidenciais. A dispersão entre seções é "
               f"{br(c6['T'], 2)}, percentil {pc('C6', 'log mediana de φ')}. Contra as 4 presidenciais de referência, que "
               "variam pouco entre si, o intervalo cabe na margem de equivalência."),
    }
    for t in a["testes"]:
        if t["id"] in textos:
            t.update({"status": "feito", "decisao": "inconclusivo", "resultado": textos[t["id"]],
                      "dados": "/apuracao/explicacao/v2/leitura.json"})
            t["referencia"] = "46 segundos turnos de 2010 a 2022 (presidente e governador), com intervalo de predição."
        if t["id"] == "P1":
            t.pop("tabela", None)
            t.pop("nota", None)
            t.update({"status": "feito", "decisao": "poder", "dados": "/apuracao/explicacao/v2/poder-pres-2022.json",
                      "referencia": "As 4 eleições presidenciais de 2010 a 2022, cada uma lida contra as demais.",
                      "estatistica": "Fraude plantada em cada eleição de referência, em 5 desenhos, inclusive formatos "
                                     "estratégicos (redutos, comparecimento alto, locais pequenos).",
                      "resultado": texto_p1})
    tost = v3[("C1", "log O/E")]["todas"]["poder_tost"]
    a["conclusao"] = {"titulo": "O que os testes dizem", "paragrafos": [
        "Nenhum dos seis padrões alegados ficou fora do que a variação entre 46 eleições produz. Nenhum saiu atípico.",
        "Isso não prova que 2026 foi normal. Contra todas as eleições, nenhum dos seis saiu equivalente, e o motivo é "
        f"o próprio desenho: as eleições variam tanto que, mesmo com uma eleição normal, a chance de sair equivalente "
        f"seria de 0% a 16%, conforme o teste ({br(100 * tost, 0)}% no das seções zeradas). A margem foi fixada antes de "
        "medir essa variação. Foi um erro de desenho, e ele está registrado.",
        "Quem alarga a referência são os governadores. Contra as 4 presidenciais, a dispersão entre seções e a fraude "
        "extrema saem equivalentes, e continua não havendo nada atípico. É uma conta com poucas eleições, feita depois "
        "de ver o resultado, e vale como indicação.",
        f"Estes testes pegam pouca fraude. A troca de 1,8% ou mais dos votos, o bastante para virar 2026, não foi detectada em "
        f"nenhum dos {len(pod['vira'])} cenários. Uma versão anterior desta página dizia que fraude capaz de mudar o "
        "resultado teria sido detectada com 95% de probabilidade. Essa frase dependia de comparar com uma eleição só e foi "
        "retirada.",
        "Os arquivos do TSE coincidem nas 499.205 seções. Uma troca pequena e igual em todas as urnas continua invisível "
        "para qualquer análise de dados. Estes testes não provam que houve fraude nem que não houve.",
    ]}
    a["atualizado_em"] = "2026-11-05"
    a["preregistro"]["v3"] = "https://github.com/mrsplube/estranhaeleicao/blob/main/docs/preregistro/v3.md"
    (ARQ / "analise.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    for t in a["testes"]:
        print(t["id"], t.get("resultado", "")[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
