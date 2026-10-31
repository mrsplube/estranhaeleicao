# estranhaeleição — Entendendo 2026

Código do [estranhaeleicao.org](https://estranhaeleicao.org): as teorias sobre fraude no
2º turno presidencial de 2026, conferidas nos dados abertos do TSE, e um simulador para
qualquer pessoa tentar fazer a conta do 2º turno fechar.

## O que tem aqui

| Caminho | O quê |
|---|---|
| `app/main.py` | servidor (FastAPI). `SITE_MODO=publico` serve só as páginas públicas |
| `app/templates/`, `app/static/` | as páginas: casos (`estranha.*`), chute e cenários (`chute.*`), sobre (`sobre.*`), método (`metodo.*`) |
| `app/apuracao/` | a conta do 2º turno: coleta, conferência seção a seção e as rotas de dados |
| `app/apuracao/data/arquivo/2026-2t/` | os resultados congelados que as páginas leem (JSON) |
| `app/tools/migracoes/` | os geradores desses JSON, a partir dos arquivos do TSE |

## De onde vêm os dados

- Resultado oficial: [resultados.tse.jus.br](https://resultados.tse.jus.br)
- Votação por seção dos dois turnos: [dadosabertos.tse.jus.br](https://dadosabertos.tse.jus.br) (`votacao_secao_2026_BR`)

O cache dos arquivos do TSE (~1 GB) não vai para o git; os geradores baixam de novo.
A soma das 499.205 seções do 2º turno bate com o resultado oficial em todos os estados
e no exterior em comparecimento, válidos, brancos e nulos (diferença zero nas 28
unidades, e o total nacional fecha: 128.236.074 comparecimentos e 124.082.273 válidos).

A contagem de seções tem uma diferença conhecida: 43 seções do exterior aparecem no
arquivo oficial (1.351) e não na votação nominal (1.308), e os votos dessas seções
estão contados — é por isso que as outras grandezas fecham e a de seções não. A causa
provável (não publicação de votação nominal onde há eleitores de menos para o sigilo)
ainda não foi confirmada na documentação do TSE. Ver `/metodo` e `conferencia.difs`
em `conta.json`.

## Rodar

```bash
python -m venv venv && venv/bin/pip install -r app/requirements.txt
cd app && SITE_MODO=publico ../venv/bin/uvicorn main:app --port 3030
```

Ou com Docker: `docker compose up estranhaeleicao`.

## Licença

Código sob a licença MIT (ver `LICENSE`). Dados: TSE, públicos. Fotos dos candidatos:
Wikimedia Commons (TSE, CC BY 4.0; Ricardo Stuckert/PR, CC BY 2.0). Ícones: Font Awesome
Free (CC BY 4.0). Os logos dos institutos de pesquisa pertencem a eles.

Feito por [Cauê Neves](https://www.linkedin.com/in/cauesn/).
