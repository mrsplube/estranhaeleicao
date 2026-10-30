"""Coeficientes de calibração da estimativa de votos (deputado estadual, SC).

Estes números NÃO são chutados: saem de uma regressão log-log sobre TODOS os
candidatos a DEPUTADO ESTADUAL em Santa Catarina em 2022 com receita e voto
(n = 544), direto dos arquivos do TSE (prestação de contas + votação por
candidato), com a receita CORTADA em 29/09/2022 — o mesmo recorte de
informação que se tem três dias antes da eleição, que é quando se prevê.
Incumbente = eleito deputado estadual em 2018.

    log(votos) = a + b·log(receita) + c·incumbente + ε

    a (intercepto)          = -2.736
    b (elasticidade)        =  0.919  → dinheiro rende quase proporcional
    c (incumbência)         =  1.604  → exp(c) = 5,0× (eleito vs desafiante)
    σ (resíduo em log)      =  1.368  (1,07 para quem declarou mais de R$ 200 mil)
    R²                      =  0.507

Até 04/10/2026 os valores eram a=1.099, b=0.650, c=1.179, σ=0.834 (R² 0,619),
ajustados nos 70 candidatos ACOMPANHADOS — uma amostra da ponta de cima, onde a
relação é mais rasa (é a restrição de amplitude: sem os pequenos, a reta deita).
No teste retroativo em 2022 (prever 2022 só com a receita até 29/09 e a lei
inteira) a nova errou 16 cadeiras-legenda e acertou 26 dos 40 eleitos; a
antiga, 18 e 25. A previsão congelada de 04/10/2026 usou a ANTIGA — a
comparação das duas com o resultado de 2026 está na aba Previsão × resultado.

O que isso quer dizer, na prática:

- **Dinheiro rende quase proporcional.** Na população inteira a elasticidade é
  0,92: +100% de dinheiro dá ~+89% de voto. O retorno decrescente forte (0,65)
  era artefato da amostra só com candidatos grandes.
- **Incumbência é o preditor mais forte.** Com a MESMA receita, quem já foi
  eleito tem ~5× os votos de um desafiante. É o efeito mais bem documentado
  da literatura eleitoral brasileira (reeleição +51–67% em estudo da UFSCar;
  efeito ~4× maior que escolaridade/gênero no BPSR/LSE).

Por que "deputado estadual" e não "geral": o sistema é voltado aos candidatos a
deputado estadual em SC, e os coeficientes de outro cargo (governador, senador)
são outra regra. Recalibre aqui se o público mudar.
"""
from __future__ import annotations

import math

# Coeficientes da regressão log-log (ver docstring).
INTERCEPTO_LOG = -2.736
ELASTICIDADE_RECEITA = 0.919
PREMIO_INCUMBENCIA_LOG = 1.604
SIGMA_LOG_RESIDUAL = 1.368

# exp(PREMIO_INCUMBENCIA_LOG) — multiplicador do eleito sobre o desafiante.
MULTIPLICADOR_INCUMBENCIA = math.exp(PREMIO_INCUMBENCIA_LOG)

# Bônus aplicado ao "voto anterior no mesmo cargo" para quem FOI ELEITO em 2022.
#
# É diferente do multiplicador acima. Lá o c captura a vantagem do incumbente
# sobre o desafiante com a MESMA receita. Aqui a pergunta é outra: quem teve X
# votos e foi ELEITO em 2022, quanto deve ter em 2026? A literatura (UFSCar,
# deputado estadual 2010) aponta reeleição +66,86%; usamos 1.3 (+30%), valor
# conservador que não transforma o fato de 2022 numa superestimativa de 2026.
BONUS_VOTO_ANTERIOR_ELEITO = 1.3

# Mínimo de receita (R$) para a estimativa por receita não ser ruído. Abaixo
# disto a regressão devolve menos que um voto e não vale a pena desenhar.
RECEITA_MINIMA = 1000.0

# Pesos intrínsecos do cenário UNIFICADO: quanto cada evidência vale no sinal
# combinado, antes de aplicar a confiança (cobertura) de cada uma.
#
# Receita é a evidência FORTE — regressão calibrada em 2022 (R²=0,619), com
# incumbência e erro conhecido (σ). Seguidor é PROXY fraco, sem dispersão
# calibrada: converte audiência de hoje em voto por uma razão de 2022. Por isso
# a receita pesa mais de duas vezes o seguidor.
#
# A interpretação é didática de propósito: quando a receita está 100% declarada
# E os candidatos estão 100% acompanhados, a confiança do sinal unificado soma
# 1,0 (0,70 + 0,30). Só seguidores cobre, no máximo, 30% do quadro — os outros
# 70% continuam preenchidos pela votação de 2022. É um parâmetro de desenho,
# não um coeficiente ajustado: recalibre aqui se quiser outro equilíbrio.
PESO_RECEITA_UNIFICADO = 0.70
PESO_SEGUIDORES_UNIFICADO = 0.30


def votos_por_receita(receita: float, incumbente: bool = False) -> int | None:
    """Votos esperados a partir da receita de campanha, com retornos decrescentes.

    `incumbente=True` quando o candidato foi ELEITO para deputado estadual em
    2022 (qualquer modalidade: QP, média). Não é previsão — é a média do modelo
    calibrado, e o desvio padrão do resíduo (SIGMA_LOG_RESIDUAL) acompanha o
    número para quem quer a faixa.
    """
    if not receita or receita < RECEITA_MINIMA:
        return None
    log_votos = (INTERCEPTO_LOG
                 + ELASTICIDADE_RECEITA * math.log(receita)
                 + (PREMIO_INCUMBENCIA_LOG if incumbente else 0.0))
    return max(0, round(math.exp(log_votos)))


def votos_por_receita_faixa(receita: float, incumbente: bool = False) -> tuple[int, int] | None:
    """Estimativa pontual e intervalo de ±1σ (em log) da receita.

    O intervalo usa o resíduo do modelo — não é um intervalo de confiança
    estatístico formal, é a dispersão que o modelo tem nos dados de 2022.
    """
    if not receita or receita < RECEITA_MINIMA:
        return None
    log_votos = (INTERCEPTO_LOG
                 + ELASTICIDADE_RECEITA * math.log(receita)
                 + (PREMIO_INCUMBENCIA_LOG if incumbente else 0.0))
    lo = max(0, round(math.exp(log_votos - SIGMA_LOG_RESIDUAL)))
    hi = round(math.exp(log_votos + SIGMA_LOG_RESIDUAL))
    return lo, hi
