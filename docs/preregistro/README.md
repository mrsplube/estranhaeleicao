# Pré-registro: testes estatísticos das acusações numéricas de fraude no 2º turno presidencial de 2026

**Versão 1 — 01/11/2026.** Registrada pela tag git `preregistro-v1` neste repositório. Os
arquivos de entrada estão congelados pelo SHA-256 em [`insumos.sha256`](insumos.sha256).
Os desvios deste plano entram na seção 9, com data e motivo. Não se reescreve o texto acima dela.

Autor: Cauê Neves (estranhaeleicao.org). Redação assistida por IA (Claude), revisada pelo autor.

---

## 1. Pergunta

As acusações numéricas que circularam depois do 2º turno de 2026 dizem que o resultado tem
padrões que só a fraude explicaria. Este plano pergunta, para cada padrão:

1. **Atipicidade:** o padrão de 2026 é raro, comparado com uma referência que ninguém acusa
   da mesma forma?
2. **Detecção:** se houvesse fraude de um tamanho dado, os testes a encontrariam?

Fica fora daqui uma terceira pergunta, a de **atribuição**: se um padrão atípico foi
causado por fraude. Um teste estatístico sobre resultado agregado não responde isso. Um
resultado "atípico" vai ser descrito como atípico e investigado; ele não vai ser chamado de
fraude.

Com uma eleição só, "houve fraude?" não é uma pergunta que um teste responda sem um modelo de
eleição limpa. O que este plano entrega é o tamanho de fraude que estes dados permitem
descartar, e de que tipo.

## 2. Dados

Todos públicos, do TSE (dadosabertos.tse.jus.br), com o hash na lista de insumos:

| Arquivo | O que tem | Uso |
|---|---|---|
| `votacao_secao_2026_BR.zip` | voto por candidato, seção a seção, nos dois turnos | C1–C6 |
| `votacao_secao_2022_BR.zip` | o mesmo, 2022 | referência |
| `bweb_2t_<UF>_*.zip` (2026, 28 arquivos) | Boletim de Urna: aptos, comparecimento, hora de recebimento, eleitores sem biometria, cargo de governador | C3–C6 |
| `bweb_2t_<UF>_*.zip` (2022, 28 arquivos) | o mesmo, 2022 | referência |
| `detalhe_votacao_secao_2026.zip` | instalação, anulação e origem do voto por seção | filtros |

**Unidade:** a seção eleitoral. Município (`CD_MUNICIPIO` do TSE) para os efeitos fixos.
**Amostra principal:** as seções no Brasil (sem o exterior, `ZZ`) presentes nos dois turnos.
**Notação** por seção *i*, turno *t*: `L_t`, `F_t` = votos do 13 e do 22; `T_1` = votos dos
demais candidatos no 1º turno; `BN_t` = brancos + nulos; `C_t` = comparecimento;
`V_t = L_t + F_t (+ T_1)` = válidos; `A` = aptos (do BU do 2º turno). Em 2022, o 22 é o
Bolsonaro e o 13 é o Lula.

**Referências de "eleição sem a fraude alegada":**
- **R1, principal:** o 2º turno presidencial de 2022. Mesmo desenho (dois turnos, 13 × 22),
  mesmo sistema. Em 2022 o lado perdedor também alegou fraude, então a R1 não é "a eleição
  que todos aceitam". Ela é a mesma urna e o mesmo método, com o sinal da acusação trocado. O
  que se testa é se 2026 se afasta de 2022 na direção alegada.
- **R2:** o 2º turno de governador de 2026, nos estados que o tiveram. São as mesmas urnas,
  no mesmo dia, com o mesmo eleitor e no mesmo ato de votar. Um padrão produzido pela urna
  deveria aparecer também nesse cargo.
- **R3, para C1:** o mesmo estatístico calculado para o 13 em 2026 e para os dois lados em
  2022.

## 3. O que já foi visto antes deste registro

O plano é de **análise secundária de dados já explorados**, e isso limita o quanto ele
protege contra escolhas feitas depois de ver o resultado. O autor e as IAs que trabalharam
no site já viram:

- os totais nacionais, estaduais e municipais dos dois turnos de 2022 e 2026;
- as análises descritivas de `acusacoes.json`: seções com o 22 ≤ 10 votos (106 com zero),
  municípios fora da faixa p5–p95 do desvio contra a previsão, Silva Jardim, "troca mínima",
  o binomial do "teste do Grok", a régua de 2022 e os placares por zona;
- a transição por candidato da terceira via (`transicao.json`) e a reconciliação de 100% das
  seções (Boletim de Urna × votação por seção × detalhe × oficial: 0 divergências em
  499.205 seções).

**Ainda não foram calculados, por ninguém, até esta versão:** os estatísticos C1–C6 da
seção 4, com seus nulos, a comparação com R1/R2 nos termos abaixo e a análise de poder da
seção 6. Para o C1 o *número* observado (106 seções com zero, `secoes_ate_10`) já é
conhecido. O que não é conhecido é o valor esperado sob o modelo nulo.

## 4. Testes confirmatórios

Para cada teste: estatístico, nulo, regra de decisão e especificação principal. **"Atípico"
exige as duas condições** de cada regra: significância estatística, com o p-valor ajustado
por Benjamini–Hochberg sobre os seis testes (q = 0,05), e afastamento da referência na
direção alegada. Fora disso o resultado é **"compatível com a referência"**.

### C1 — Seções quase zeradas para o 22 (caso `secoes-10`)

- **Alegação:** há seções demais em que o Flávio teve ≤ 10 votos.
- **Estatístico:** `S1 = #{i : F_2 ≤ 10}` e a razão observado/esperado `O/E`.
- **Nulo:** em cada seção, `F_2 ~ BetaBinomial(V_2, p̂_i, ρ̂)`. `p̂_i` sai de uma regressão
  logística fracionária (IRLS, peso `V_2`) da fatia do 22 no 2º turno sobre as fatias do
  1º turno na mesma seção (`F_1/V_1`, `L_1/V_1`, `T_1/V_1`, `BN_1/C_1`), com efeito fixo de UF.
  `ρ̂` (sobredispersão) é estimado por momentos dentro de cada UF. 10.000 simulações.
- **p-valor:** unilateral, fração das simulações com `S1_sim ≥ S1_obs`.
- **Atípico se:** p ajustado < 0,05 **e** o `O/E` do 22 em 2026 for maior que o maior `O/E`
  entre as referências R3 (13 em 2026; 13 e 22 em 2022), calculadas do mesmo jeito.

### C2 — Municípios fora do padrão (casos `silva-jardim`, `fora_do_padrao`)

- **Alegação:** municípios que viraram mais do que o 1º turno explica.
- **Modelo:** a mesma regressão logística fracionária de C1, no município, para a fatia do
  13 no 2º turno. Resíduo de Pearson dividido por `√φ̂` (quase-binomial). p-valor bilateral
  normal; Benjamini–Hochberg com q = 0,05 sobre todos os municípios.
- **Estatístico:** `N2` = municípios significativos; `D2` = fração deles a favor do 13.
- **Atípico se:** a proporção de municípios significativos em 2026 for maior que a de 2022
  (teste de duas proporções, unilateral, p < 0,05) **e** a razão das proporções for > 1,25,
  **ou** se `D2` em 2026 for maior que a fração a favor do vencedor em 2022 (Fisher exato,
  unilateral, p < 0,05).

### C3 — Impressão digital comparecimento × voto (enchimento de urna)

- **Alegação implícita** em várias acusações: votos acrescentados onde ninguém votou.
- **C3a, principal:** o modelo de mistura de Klimek et al. (2012), ajustado ao histograma 2D
  (comparecimento `C_2/A` × fatia do 13 em `V_2`) por mínimos quadrados, como no artigo. O
  modelo estima `f_i` (fraude incremental) e `f_e` (fraude extrema). IC de 95% por bootstrap
  de municípios (1.000 réplicas).
- **C3b, secundário:** a inclinação de Myagkov, Ordeshook e Shakin (2009): `L_2/A` sobre
  `C_2/A`, com efeito fixo de município e peso `A`. Em enchimento de urna a inclinação passa
  de 1.
- **Atípico se:** o IC de `f_i` ou `f_e` em 2026 excluir zero **e** ficar acima do valor de
  2022 (IC da diferença por bootstrap excluindo 0). Para o p-valor de C3 entra o teste de
  `f_i + f_e = 0` (bootstrap).

### C4 — Ordem de chegada dos boletins (caso `curva`)

- **Alegação:** os votos que chegaram tarde são diferentes dos que chegaram cedo.
- **Estatístico:** `R4` = média, ponderada por número de seções, da correlação de Spearman,
  dentro de cada município com ≥ 10 seções, entre a hora de recebimento do BU e
  `Δ_i = L_2/V_2 − L_1/V_1`. O Δ na mesma seção controla a composição do eleitorado.
- **Nulo:** a hora de recebimento é permutada dentro do município (2.000 permutações).
- **Atípico se:** p ajustado < 0,05 **e** `R4` de 2026 > `R4` de 2022, com o IC de 95% da
  diferença (bootstrap de municípios) excluindo zero.

### C5 — Biometria (caso `biometria`)

- **Alegação:** onde mais gente votou sem a digital, o 13 ganhou mais.
- **Modelo:** `Δ_i = α_m + β · s_i + ε`, com `s_i` = eleitores sem biometria / `C_2` (BU do
  2º turno), efeito fixo de município, peso `V_2` e erro-padrão agrupado por zona.
- **Atípico se:** `β` de 2026 > 0 com p ajustado < 0,05 **e** `β_2026 − β_2022` com IC de 95%
  excluindo zero.

### C6 — Homogeneidade entre seções do mesmo município

- **Alegação implícita:** resultados "uniformes demais" ou "dispersos demais" dentro da
  cidade.
- **Estatístico:** a dispersão de Pearson `φ_m` da fatia do 13 no 2º turno entre as seções do
  município (χ²/gl contra a binomial com a fatia municipal), em municípios com ≥ 10 seções.
  `M6` = mediana de `φ_m`.
- **Atípico se:** a razão `M6_2026 / M6_2022`, com IC de 95% por bootstrap de municípios,
  ficar inteira fora da faixa de equivalência [0,8; 1,25]. Para o p-valor de C6 entra o teste
  de razão = 1.

**Onde a R2 (governador 2026) entra:** C3, C4 e C6 também são calculados para o 2º turno de
governador nos estados que o tiveram. O resultado vai lado a lado; não entra na regra de
decisão. Se um padrão do presidente também aparecer no governador, isso é informação sobre
a urna e o eleitorado, não sobre o candidato.

## 5. Especificações alternativas (multiverso)

A especificação principal é a da seção 4. Todas as variações abaixo também são calculadas e
**publicadas inteiras**, e não só a que favorecer uma conclusão:

- piso de comparecimento por seção: nenhum (principal), ≥ 50, ≥ 100;
- efeito fixo de município (principal) ou de zona;
- com ou sem as seções com boletim gerado pelo recuperador de dados (RED);
- C1 com limiar de 0, 5 ou 10 votos (principal: 10, como na alegação);
- C2 com q = 0,05 (principal) ou 0,10;
- C3 com histograma de 100 × 100 (principal) ou 50 × 50.

Um resultado só é descrito como robusto se a decisão (atípico ou compatível) for a mesma em
pelo menos 80% das especificações.

## 6. Poder: que tamanho de fraude estes testes encontram

Este é o resultado principal do plano.

**Fraude plantada.** Sobre os dados de 2022 e de 2026, simula-se fraude a favor do
vencedor, em quatro desenhos:

| Desenho | Como |
|---|---|
| Enchimento | acrescenta votos ao 13 e ao comparecimento, até o limite de aptos |
| Troca | move votos do 22 para o 13 sem mexer no comparecimento |
| Concentrada | qualquer dos dois em 0,1% ou 1% das seções |
| Difusa | qualquer dos dois em 5% ou 20% das seções |

**Tamanhos:** fraude total de 0,1%, 0,5%, 1% e 3,57% dos votos válidos (3,57% é a margem
de 2026). Seções sorteadas ao acaso dentro das UFs, com 200 réplicas por cenário. Em cada
réplica rodam C1–C6 com a regra da seção 4.

**Saída:**
- a taxa de detecção de cada teste e de "qualquer teste" (com BH) por cenário;
- o **MDE80**, o menor tamanho de cada desenho detectado com probabilidade ≥ 80%.

**Leitura obrigatória.** Se nenhum teste der atípico em 2026, os cenários com detecção
≥ 95% ficam **descartados ao nível de 5%**. A probabilidade de não ver nada, se eles
tivessem acontecido, é de no máximo 5%. Os cenários com detecção menor ficam **não
descartados**, com a taxa ao lado.

**O que nenhum destes testes enxerga.** Uma troca proporcional e uniforme em todas as seções
(por exemplo, 2% dos votos do 22 viram 13 em toda urna) não deixa assinatura na distribuição,
porque é idêntica a uma mudança real de opinião. Ela só é detectável comparando o boletim
impresso na seção com o voto do eleitor, e o Brasil não tem voto impresso conferido pelo
eleitor. O relatório vai dizer isso ao lado de qualquer conclusão.

## 7. Análises exploratórias (sem regra de decisão)

Calculadas e publicadas como descrição, sem entrar na conclusão:

- **Testes de dígitos** (2º dígito de Benford, último dígito). A literatura mostra que eles
  não distinguem fraude de eleição limpa (Deckert, Myagkov e Ordeshook, 2011; Mebane, 2011).
  Entram porque são o que as pessoas perguntam, com essa ressalva.
- **eforensics** (Mebane et al.): modelo bayesiano de mistura, com a sensibilidade a "votos
  perdidos", que é a principal fonte de falso positivo do método.
- **Picos em percentuais redondos** (Rozenas, 2017).
- **Erro das pesquisas** contra a distribuição histórica de erros no Brasil, quando houver
  base histórica montada.
- **Curva nacional da apuração** refeita na ordem real de recebimento dos boletins.

## 8. Conclusão: como ela vai ser escrita

| Resultado | Frase |
|---|---|
| Nenhum teste atípico, e o padrão é robusto no multiverso | "Os padrões alegados são compatíveis com 2022. Fraude dos tipos X acima de Y votos está descartada a 5%; fraude dos tipos Z não é detectável por estes testes." |
| Algum teste atípico | "O padrão P de 2026 é atípico contra 2022 (p = …, tamanho …). Isso não identifica a causa." Segue a análise do que mais explicaria o padrão. |
| Resultado frágil no multiverso | "Depende da especificação": publicar a curva de especificações e não concluir. |

Em nenhum caso vai sair "provamos que não houve fraude" ou "houve fraude".

## 9. Desvios do plano

Toda mudança depois da tag `preregistro-v1` entra aqui, com a data, o que mudou e o motivo,
**antes** de rodar a versão modificada. Erros de código corrigidos depois de rodar também
entram aqui, com o resultado antes e depois.

| Data | Teste | Mudança | Motivo |
|---|---|---|---|
| 01/11/2026 | C1 | Esclarecimento de implementação, sem mudança de regra: o ρ̂ por momentos saiu **negativo** (subdispersão) em 26 das 27 UFs, porque o 1º turno da mesma seção prevê o 2º melhor que uma binomial. A beta-binomial não representa subdispersão; ρ̂ foi truncado em 10⁻⁶ (≈ binomial), o limite do espaço de parâmetros. | Registrado depois de calcular O e E e **antes** de calcular qualquer p-valor. O/E da especificação principal já visto nesse momento: 22/2026 = 2,67; 13/2026 = 1,61; 22/2022 = 3,05; 13/2022 = 1,21. |
| 01/11/2026 | C2 | Três esclarecimentos, escritos **antes de rodar o C2**: (1) a regra tem dois componentes; o p do C2 que entra no Benjamini–Hochberg entre testes é `min(1, 2·min(p_proporção, p_Fisher))` (Bonferroni dentro do teste). (2) O vencedor de 2022 também foi o 13, então "a favor do vencedor em 2022" = a favor do 13 em 2022. (3) Efeito fixo de município não existe com o município como unidade; no multiverso do C2 a alternativa ao efeito fixo de UF (principal) é **sem** efeito fixo. As outras variações (piso 0/50/100, com e sem RED, q = 0,05/0,10) valem como escritas. | O plano não definia um p único para um teste com regra dupla, nem a variação de efeito fixo para um teste municipal. Nenhum número do C2 foi calculado antes deste registro. |
| 01/11/2026 | C3 | Detalhes de implementação, escritos **antes de rodar o C3**: comparecimento `t = C_2/A` (aptos e comparecimento do BU), fatia do vencedor `v = L_2/V_2`. Distribuições limpas de Klimek: `t` e `v` normais independentes, truncadas em [0, 1], com média = mediana das seções e desvio = 1,4826·MAD (robusto à cauda de fraude). Fraude incremental: `x ~ |N(0, σx)|`, `t' = t + x(1−t)`, votos do vencedor `+ x·N(1−t) + x^α·oposição`, oposição `·(1−x^α)`, com α = 2 (o valor do artigo). Fraude extrema: `x = 1 − |N(0, σx)|`. σx escolhido na grade {0,025; 0,05; 0,075; 0,1; 0,15; 0,2} pelo menor erro quadrático. Como o histograma do modelo é linear em `f_i` e `f_e` dados os componentes, o ajuste é mínimos quadrados com limites (`f ≥ 0`) sobre componentes simulados com 400 mil sorteios e semente fixa. Bootstrap: reamostra municípios e reestima tudo (médias, desvios, componentes); 1.000 réplicas na especificação principal e 200 em cada especificação do multiverso. p do C3 para o BH: `(1 + #{b : f_i* + f_e* = 0}) / (1 + B)` em 2026, como escrito. Governador (R2): por UF, `v` = fatia do mais votado no 2º turno de governador, ajuste conjunto. C3b: inclinação por mínimos quadrados ponderados por `A` dentro do município, erro agrupado por município; a variação de efeito fixo (município/zona) vale só para o C3b. | O artigo deixa esses pontos em aberto, e o plano dizia só "como no artigo". Nenhum número do C3 foi calculado antes deste registro. |
| 01/11/2026 | C4 | Esclarecimentos escritos **antes de rodar o C4**: hora = `DT_BU_RECEBIDO` do BU do 2º turno; seções sem hora saem. Spearman calculado como correlação de Pearson dos postos, com empates no posto médio. O p é **unilateral para cima** (a alegação é que os boletins tardios pendem para o 13): `(1 + #{R4* ≥ R4}) / (1 + 2.000)`. A permutação embaralha a hora dentro do município, mantendo o Δ de cada seção. O IC da diferença 2026 − 2022 vem de 2.000 reamostragens de municípios sobre as correlações municipais. No multiverso, a alternativa ao município é a zona (mesmo mínimo de 10 seções). Governador (R2): `Δ` = fatia do vencedor do 2º turno de governador na seção menos a fatia dele no 1º turno de governador na mesma seção (votação por seção, cargo 3); ao lado, sem entrar na regra. | Pontos que o plano não fixava. Nenhum número do C4 foi calculado antes deste registro. |

## 10. Referências

- Deckert, J., Myagkov, M. e Ordeshook, P. C. (2011). Benford's Law and the detection of
  election fraud. *Political Analysis*, 19(3).
- Enikolopov, R. et al. (2013). Field experiment estimate of electoral fraud in Russian
  parliamentary elections. *PNAS*, 110(2).
- Klimek, P., Yegorov, Y., Hanel, R. e Thurner, S. (2012). Statistical detection of
  systematic election irregularities. *PNAS*, 109(41).
- Mebane, W. R. (2011). Comment on "Benford's Law and the detection of election fraud".
  *Political Analysis*, 19(3).
- Myagkov, M., Ordeshook, P. C. e Shakin, D. (2009). *The Forensics of Election Fraud*.
  Cambridge University Press.
- Rozenas, A. (2017). Detecting election fraud from irregularities in vote-share
  distributions. *Political Analysis*, 25(1).
- Benjamini, Y. e Hochberg, Y. (1995). Controlling the false discovery rate. *JRSS B*, 57(1).
- Steegen, S. et al. (2016). Increasing transparency through a multiverse analysis.
  *Perspectives on Psychological Science*, 11(5).
- Van den Akker, O. et al. (2021). Preregistration of secondary data analysis: a template and
  tutorial. *Meta-Psychology*, 5.
