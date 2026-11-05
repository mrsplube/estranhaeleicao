# Plano de execução da v2 do paper (para qualquer IA continuar)

Escrito em 02/11/2026 para que outra IA (ou outra conversa) consiga continuar sem contexto anterior.
Leia **nesta ordem**: `~/HANDOFF.md` → este arquivo → `docs/preregistro/v2.md` (o que foi registrado) →
`docs/relatorio/parecer-relatorio-v1.pdf` (por que a v2 existe). O pré-registro manda; este plano diz
*como* executar. Se os dois discordarem, vale o pré-registro, e a discordância vira desvio (seção 8 do
`v2.md`).

Marque o andamento na tabela "Estado das etapas" no fim deste arquivo e commite a cada etapa.

---

## 0. Regras que não podem ser quebradas

1. **Disciplina do pré-registro.** Qualquer decisão que o `v2.md` não fixa é escrita na seção 8 do `v2.md`,
   commitada e publicada **antes** de rodar o código que a usa. Erro achado depois de rodar: corrige, registra
   o resultado de antes e o de depois, e publica. Nunca mude uma regra depois de ver o resultado dela.
2. **Publicar sempre.** Toda mudança termina com: commit no `master` → `docker compose restart estranhaeleicao`
   se mexeu em template, rota ou `main.py` → `tools/publicar_github.sh "mensagem"`. Nunca `git push` direto.
3. **Parte técnica só.** Resultados vão para `/analise`, `/metodo`, `/dados` e o PDF. **Não** citar nem
   linkar as análises nos cartões de caso da página inicial (pedido do autor).
4. **Texto do site:** direto, começando pelo dado; verde para o que confere, vermelho/roxo para o que não.
5. **Processos longos:** rodar com `nohup … &` e log em arquivo na raiz do repo (já no `.gitignore`:
   `p1.log`, `baixar-ref.log`; acrescente os novos). Para parar: `ps -eo pid,args | grep "[m]igracoes.<nome>"`
   e `kill <PID>`. **Nunca** `pkill -f <nome>` num comando que contenha o mesmo texto (mata o próprio shell).
6. **Segredos:** token do GitHub em `~/.config/estranhaeleicao/github-token`; nunca imprimir.
7. **Ambiente:** `cd ~/projetos/estranhaeleicao/app && ../venv/bin/python -m tools.migracoes.<script>`.
   Python 3.13, numpy 2.5.4, scipy 1.18.1, reportlab 4.2.5 (`app/requirements-analise.txt`). Máquina de 2
   núcleos: medir o tempo de uma réplica antes de lançar milhares.

## 1. O que já existe e pode ser reaproveitado

| Arquivo (`app/tools/migracoes/`) | O que tem de útil |
|---|---|
| `2026-11-01-c1-secoes-zeradas.py` | `_logit_fe` (logit fracionária com efeito fixo), `_rho`, `_cdf`, `_br`, `_red_2026` |
| `2026-11-01-c2-municipios.py` | `_bh`, `_ajuste` municipal |
| `2026-11-01-c3-impressao-digital.py` | `ajustar(t, v, bins)` (Klimek), `inclinacao` (Myagkov) |
| `2026-11-01-c4-ordem-chegada.py` | `_r4` (Spearman dentro do grupo, permutação rápida) |
| `2026-11-01-c5-biometria.py` | `regressao` (efeito fixo + erro agrupado) |
| `2026-11-01-c6-dispersao.py` | `phi_por_grupo` |
| `2026-11-01-p1-poder.py` | `plantar` (com arredondamento aleatório), `Base`, `testes` (versão leve), parada sequencial |
| `2026-11-01-bu-secao.py` | leitura do BU 2026/2022 → `apuracao/cache/bu_secao_{ano}.pkl` |
| `2026-11-02-relatorio-pdf.py` | estilos, fontes, `tabela`, `rodape` para o PDF v2 |

As tabelas antigas `apuracao/cache/secoes_{2026,2022}.pkl` têm colunas `L1,F1,T1,BN1,C1,L2,F2,BN2,C2,LOCAL`
com **13 fixo em L e 22 fixo em F**. A v2 troca isso por vencedor/perdedor (abaixo).

## 2. Dados (já baixados, hash publicado em `docs/preregistro/insumos-v2.sha256`)

Pasta `app/apuracao/cache/ref/{ano}/`. Formatos verificados em 02/11:

| Arquivo | Formato | Observação |
|---|---|---|
| `votacao_secao_{2010,2014,2018}_BR.zip` | CSV `;` latin-1, com cabeçalho; colunas `NR_TURNO, SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, CD_CARGO, NR_VOTAVEL, QT_VOTOS, NR_LOCAL_VOTACAO` | só Presidente (cargo 1). 95 = branco, 96 = nulo. `CD_MUNICIPIO` sem zeros à esquerda: usar `zfill(5)` |
| `votacao_secao_2022_BR.zip`, `…2026_BR.zip` | idem, em `apuracao/cache/` | idem |
| `detalhe_votacao_secao_{2010,…,2022}.zip` | um CSV por UF + `_BR.csv` (presidente) e, em 2022, `_BRASIL.csv` (tudo) | `QT_APTOS, QT_COMPARECIMENTO, QT_VOTOS_BRANCOS, QT_VOTOS_NULOS` por seção e cargo. **2018 e 2022 trazem `DT_RECEBIMENTO_BU_HOR_TSE` e `DS_ORIGEM_VOTO`**; 2010 e 2014 não. Ler o Presidente do `_BR.csv` e o Governador dos arquivos por UF (cargo 3). Atenção: em 2026 o Presidente está **só** no `_BR.csv` |
| `bweb/` 2014 | `.txt` **sem cabeçalho**, colunas por posição | ver a linha de exemplo no fim desta seção; posição da biometria ainda não identificada |
| `bweb/` 2018 | CSV com cabeçalho; a coluna da UF se chama `"SG_ UF"` (com espaço) | conferir o nome do campo de biometria antes de usar |
| BU 2022 e 2026 | já lidos por `2026-11-01-bu-secao.py` | 2022: `QT_ELEITORES_BIOMETRIA_NH`; 2026: `QT_ELEI_BIOM_SEM_HABILITACAO`; datas em formatos diferentes |

Linha de exemplo do BU 2014 (para mapear posições):
`"28/10/2014";"11:44:50";"158";"144";"AC";"1";"PRESIDENTE";"1";"3";"1279";"13";"PT";"01392";"RIO BRANCO";"26/10/2014";"230";"22";"208";"1";"1";"APURADA";"13";"DILMA";"65";…`
→ UF=5, cargo=6/7, zona=8, seção=9, local=10, município=13, aptos?=16, abstenções?=17, comparecimento?=18,
número votável=22, votos=24 (índices base 1; **confirmar** somando contra o detalhe antes de usar).

**Ainda falta baixar (Etapa 2):** votação por seção **por UF** das disputas de governador em 2º turno
(o `_BR` só tem Presidente). Usar `2026-11-02-baixar-referencias.py` como modelo: baixar, calcular o
SHA-256, acrescentar a `insumos-v2.sha256`, commitar e publicar **antes** de abrir.

Vencedor/perdedor do 2º turno presidencial: 2010 13×45 · 2014 13×45 · 2018 **17**×13 · 2022 13×22 ·
2026 13×22. Governador: o mais votado no 2º turno da UF (calcular do próprio dado).

## 3. Etapas

Cada etapa tem entrega e critério de aceite. Não avance sem o aceite.

### Etapa 1 — Tabela padrão por disputa
Script novo `2026-11-03-v2-tabelas.py`. Para cada disputa (`pres-2010`, `pres-2014`, `pres-2018`,
`pres-2022`, `pres-2026`, depois `gov-{ano}-{uf}`), gravar `apuracao/cache/v2/{id}.pkl` com:

- `chaves`: lista de `(uf, municipio5, zona, secao)`; `local`: `NR_LOCAL_VOTACAO`;
- matriz `A` (float) com colunas, nesta ordem: `W1, P1, O1, BN1, C1, W2, P2, BN2, C2` (W = vencedor,
  P = perdedor, O = demais candidatos do 1º turno, BN = brancos + nulos, C = comparecimento);
- vetores `aptos` (detalhe do 2º turno), `hora` (epoch; `NaN` onde não houver), `sem_bio` (`NaN` onde não
  houver);
- metadados: vencedor, perdedor, fonte de cada campo, número de seções descartadas e por quê.

Amostra: seções no Brasil (sem `ZZ`), presentes nos dois turnos, com `V1 > 0` e `V2 > 0`.
**Aceite:** `pres-2022` e `pres-2026` reproduzem exatamente as somas de `secoes_2022.pkl` e
`secoes_2026.pkl` (com W/P = 13/22); os totais nacionais de cada ano batem com o oficial (W2, P2, BN2).

### Etapa 2 — Disputas de governador
Listar as UFs com 2º turno de governador em 2010, 2014, 2018 e 2022 (do detalhe, cargo 3, turno 2),
baixar a votação por seção dessas UFs (hash antes de abrir), gerar as tabelas `gov-*` e descartar as
disputas com menos de 2.000 seções (regra do `v2.md`, seção 2).
**Aceite:** lista de disputas com número de seções e vencedor; totais conferem com o detalhe.

### Etapa 3 — Testes generalizados
Módulo `2026-11-03-v2-testes.py` com uma função por teste, todas recebendo a tabela padrão e uma
especificação, e devolvendo `{"T": estatístico, "se": erro-padrão, ...extras}`:

- C1: O/E de `P2 ≤ 10`, com o modelo de dois níveis do `v2.md` §5 (efeito de local em logit + beta-binomial);
  erro-padrão por bootstrap de municípios.
- C2: proporção de municípios significativos (BH) e fração a favor do vencedor.
- C3: `f_i`, `f_e` (Klimek) e a inclinação de Myagkov, IC por bootstrap de municípios.
- C4: R4 com permutação em blocos de local dentro do município (só disputas com hora: 2018, 2022, 2026).
- C5: β com erro agrupado por município (só disputas com biometria).
- C6: mediana de φ e razão.

**Aceite:** com W/P = 13/22, a especificação principal reproduz os números da v1 para 2026 e 2022 dentro
do esperado (as mudanças de dependência mexem nos erros-padrão, não no estatístico pontual). Registrar
a comparação num JSON de validação.

### Etapa 4 — Calibração (antes de qualquer leitura)
`2026-11-04-v2-calibracao.py`: os diagnósticos do `v2.md` §4 para cada disputa → `…/v2/calibracao.json`
e uma figura por teste. **Aceite:** a regra "modelo não comparável" foi aplicada e o resultado está
publicado antes da Etapa 5.

### Etapa 5 — Rodar os testes em todas as disputas
Rodar C1–C6 (principal + multiverso da v1) em cada disputa → `apuracao/data/arquivo/2026-2t/v2/{id}.json`.
É a etapa mais longa: estimar o tempo com uma disputa antes de lançar todas, em segundo plano.

### Etapa 6 — Meta-análise e leitura
`2026-11-05-v2-leitura.py`: efeitos aleatórios (REML) por teste sobre as disputas de referência (sem
2026), intervalo de predição, posição de 2026, TOST com as margens do `v2.md` §3, BH e BY, e a leitura
atípico/equivalente/inconclusivo. Grava `v2/leitura.json` e atualiza `analise.json` (troca os resultados
da v1, tira o aviso "versão 2 em andamento", e a palavra "compatível" sai). REML pode ser implementado com
`scipy.optimize` sobre a verossimilhança restrita (não há statsmodels no venv).

### Etapa 7 — Poder v2
Adaptar `2026-11-01-p1-poder.py` conforme o `v2.md` §6: base = disputas presidenciais de referência,
comparação deixa-uma-fora, desenhos estratégicos, grade nova, validação da versão leve **com** fraude
(4 cenários, versão completa com 20 réplicas) e teste automatizado do plantio. **Antes de lançar,**
medir o tempo por réplica: a v1 levou cerca de 10 h para 64 cenários; a v2 tem mais cenários e mais bases.
Se não couber, reduzir a grade **registrando o desvio antes**.

### Etapa 8 — Apêndice de inferência ecológica
Limites de Duncan–Davis por município para a fração de cada candidato da terceira via que foi ao vencedor
em 2026, agregados com peso dos votos; King (1997) como ilustração se der para implementar sem pacote.

### Etapa 9 — Relatório v2
Novo gerador (partindo de `2026-11-02-relatorio-pdf.py`) com a estrutura de paper: introdução,
literatura (forense eleitoral e críticas, auditorias por amostragem de risco, o caso brasileiro), dados
com estatística descritiva, método, calibração, resultados, poder, discussão, ameaças à validade,
apêndices. Figuras: histograma 2D, calibração, posição de 2026 em cada distribuição de referência, curva
de especificações, curva de poder. Resumo com até 200 palavras. p-valores no piso escritos como
"p < 1/(B+1)". Fuso da hora declarado. Publicar em `static/relatorio/` e trocar o link da `/analise`.

### Etapa 10 — Fechamento
Atualizar `/metodo` (se algo mudou), `/dados` (catálogo: rodar `2026-10-31-dados.py`),
`~/Documentation/apps/estranhaeleicao/README.md` e o `~/HANDOFF.md`. Lembrar o autor do DOI (Zenodo) e
do registro no OSF, que só ele pode fazer.

## 4. Armadilhas já conhecidas

- `pkill -f` mata o próprio shell (regra 0.5).
- `hash()` de string muda a cada processo: semente sempre determinística.
- `json.dumps` falha com `numpy.bool_`: usar `default=lambda o: o.item()`.
- `floor` na divisão de votos plantados perde até 20% do alvo: usar arredondamento aleatório.
- Uma aproximação de p-valor precisa seguir a **definição registrada**, não uma conveniente (erro do C3 leve).
- Comparar uma base com ela mesma infla o poder (artefato da base 2022 na v1).
- O Cloudflare sobrescreve o `robots.txt`; rota nova só aparece depois do restart do container.

## 5. Estado das etapas

**Atualização de 05/11, 9h:** o Cursor corrigiu o C3 do P1 de madrugada (v2.md §8). A revisão seguinte achou que o zero de detecção vem sobretudo da heterogeneidade + correção múltipla, e que o centro "do limpo" é um teto (errata no §8). Adendo `docs/preregistro/v3.md` (tag `preregistro-v3`): A e B feitas (`v2/v3-referencias.json`), a `/analise` já mostra a v2; E rodando (`v3-pareada.log`); D e o multiverso entram sozinhos por `tools/v3-cadeia.sh` (`v3-cadeia.log`) quando o P1 acabar (a `v2-cadeia-2.sh` NÃO está rodando). Depois: commitar `poder-*.json`, `multiverso.json`, `v3-pareada.json`, rodar `2026-11-05-v3-site.py`, escrever o PDF v2.

**Em 04/11 ~9h15 foi lançada também `tools/v2-cadeia-2.sh` (log `v2-cadeia-2.log`), que roda o multiverso depois da primeira cadeia.** **Em 04/11 ~9h10 foi lançada a cadeia `tools/v2-cadeia.sh` (log `v2-cadeia.log`)**: espera os 48 governadores, depois roda calibração → leitura → validação do poder → poder nas 4 bases. Ela não commita. Quem retomar: (1) conferir `v2-cadeia.log` e os logs de cada etapa; (2) commitar `v2/gov-*.json`, `calibracao.json`, `leitura.json`, `poder-*.json`; (3) conferir a validação (diferença de detecção leve × completa < 10 pontos nos 4 cenários — se não, o poder leve não vale e é preciso registrar e refazer); (4) só então ler `leitura.json`, atualizar `analise.json` e publicar.


| Etapa | Estado | Commit / observação |
|---|---|---|
| Parecer v1, adendo v2, tag `preregistro-v2` | feito | `dd4f720` (público) |
| Downloads da classe + hashes | feito | `e8355ed` (público) |
| 1. Tabela padrão por disputa | feito (presidente 2010–2026) | aceite: pres-2022 e pres-2026 batem com secoes_*.pkl, diferença 0 em todas as colunas; hora só 2018+, biometria só 2022/2026 (2014/2018 pelo BU: pendente) |
| 2. Governador | feito | 48 tabelas `gov-*` prontas (`v2-tabelas.log`). 42 disputas + 6 de 2026 baixadas, hash publicado (`d98345d`); tabelas `gov-*` sendo montadas em segundo plano (log `v2-tabelas.log`). Conferir: 48 linhas no log, sem Traceback. Decisões da Etapa 3 já registradas na seção 8 do v2.md (`c1795ed`) |
| 3. Testes generalizados | feito | `2026-11-03-v2-testes.py`; aceite em pres-2022 com `--nivel1` (`v2/pres-2022-nivel1.json`): C1 3,054, C2 59/39, C3 0,5962, C6 3,956 iguais à v1; C4 −0,0437 (v1 −0,0435, hora por local); C5 β igual, erro maior (agrupado por município). Uma disputa presidencial leva ~16 min (C3 6 min, C4 9 min) |
| 4. Calibração | feito (04/11) | erro do Newton corrigido e registrado; 2026 comparável em C1, C2, C3 | estatísticas de forma, ver desvio de 04/11 no `v2.md`; insumos gravados por `v2-testes` em `apuracao/cache/v2/{id}-calib.pkl` (p previsto, E por seção, observado; z municipais) |
| 5. Testes em todas as disputas | feito (48 gov + 5 pres, commit `7293b80`) | 5 presidenciais feitas e commitadas (C1 em dois níveis leva 2–3 h cada); 48 de governador rodando em 2 processos (`v2-testes-gov-a.log`, `-b.log`). Falta depois: multiverso (só 2026 + 4 presidenciais, v2.md §8) — o C1 de dois níveis é lento demais; registrar desvio antes (sugestão: multiverso do C1 com `--nivel1`) |
| 6. Meta-análise e leitura | feito: pres-2026 = inconclusivo nos 6 (nenhum atípico; só C3 f_e equivalente); falta levar à página | roda depois da calibração; depois atualizar `analise.json` e a página |
| 7. Poder v2 | código pronto (`2026-11-05-v2-poder.py`) | desvio da grade e dos modos registrado (04/11). Roda sozinho pela cadeia `tools/v2-cadeia.sh` |
| 8. Apêndice de inferência ecológica | feito | `2026-11-05-v2-limites.py` → `v2/limites.json`. 2026: H1 [0; 0,92], H1+H2 [0,15; 0,92] |
| 9. Relatório v2 | gerador pronto (`2026-11-05-v2-paper-pdf.py`) | lê os JSON da v2 e escreve "Pendente" onde faltar; rodar quando a cadeia terminar, revisar página a página, publicar em `static/relatorio/estranhaeleicao-paper-v2.pdf` e trocar o link da `/analise` |
| 10. Fechamento | — | |
