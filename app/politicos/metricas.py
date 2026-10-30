"""Métricas de desempenho no Instagram.

Funções puras: recebem números, devolvem números. Sem banco, sem rede — é o que
permite testá-las contra os mesmos casos que o GabineteMC usa
(`tools/testar_metricas_padrao.py`) e garantir que "engajamento" queira dizer a
mesma coisa nos dois apps, mesmo com os códigos separados.

Duas advertências que valem para tudo aqui:

- **Compartilhamento e salvamento não existem para perfil de terceiro.** A API
  pública não os entrega; só a API oficial de uma conta que você administra. As
  colunas existem no banco e ficam zeradas. Não invente indicador em cima delas.
- **Maturação.** Post com menos de 14 dias ainda está juntando engajamento.
  Todo cálculo comparativo tem de filtrar por `publicado_em <= hoje-14d`, senão
  quem postou ontem parece que despencou.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

# O ÍNDICE COMPOSTO FOI REMOVIDO em 10/08/2026.
#
# Era um 0–100 que combinava cinco dimensões com pesos escolhidos a olho. Depois
# que a votação real de 2022 entrou no banco deu para testá-lo: entre os 22
# candidatos que disputaram estadual em 2022 e têm coleta hoje, a correlação do
# índice com o voto foi de +0,14 — ruído. Pior, a dimensão "crescimento de
# seguidores", que pesava 20%, correlaciona NEGATIVAMENTE (-0,29): quem tem base
# pequena cresce rápido em porcentagem, e quem já tem 200 mil votos cresce devagar.
# Ou seja, um quinto do índice empurrava na direção errada.
#
# O que sobrou no lugar: as métricas cruas, cada uma ordenável, e a coluna de
# voto anterior — que é dado, não estimativa. Não recrie o índice sem calibrar
# contra voto de verdade.

# Piso de posts para o perfil ser comparável. Com menos que isto a média por post
# é ruído: um único vídeo bom desloca tudo.
MINIMO_POSTS = 5

# Base de referência para amortecer a taxa por seguidor em contas pequenas.
# 3 mil seguidores com 19% viram algo comparável a 20 mil com 3%.
AMORTECIMENTO = 20_000

# A corrida que o painel acompanha. Voto de outro cargo entra como referência
# fraca, nunca no lugar deste.
CARGO_REFERENCIA = "DEPUTADO ESTADUAL"


def engajamento(curtidas: int, comentarios: int) -> int:
    """Interações públicas de um post. Comentário não vale mais que curtida aqui:
    ponderar os dois é uma escolha editorial que muda o ranking, e preferimos a
    definição simples, que é a que o Fanpage Karma usa como base."""
    return int(curtidas or 0) + int(comentarios or 0)


def taxa_por_seguidor(total_engajamento: int, seguidores: int, posts: int) -> float | None:
    """Engajamento médio por post dividido por seguidor, em %.

    É a métrica que permite comparar quem tem 2 milhões com quem tem 3 mil, e é
    por isso que a série de seguidores é pré-requisito de tudo.
    """
    if not seguidores or not posts:
        return None
    return round((total_engajamento / posts) / seguidores * 100, 4)


def taxa_por_visualizacao(total_engajamento: int, visualizacoes: int) -> float | None:
    """Para vídeo: engajamento sobre quem de fato viu. Menos sensível a
    impulsionamento que a taxa por seguidor."""
    if not visualizacoes:
        return None
    return round(total_engajamento / visualizacoes * 100, 4)


def frequencia_semanal(posts: int, dias: int) -> float | None:
    if not dias:
        return None
    return round(posts / (dias / 7), 2)


def crescimento_pct(antes: int | None, depois: int | None) -> float | None:
    if not antes or depois is None:
        return None
    return round((depois - antes) / antes * 100, 3)


def suspeita_impulsionamento(visualizacoes: int, seguidores: int,
                             total_engajamento: int) -> bool:
    """Alcance muito acima da base com engajamento proporcionalmente baixo.

    Não é prova de nada — é um sinal para olhar, e a tela diz isso. Cruzar com a
    Biblioteca de Anúncios da Meta é o que transforma suspeita em fato.
    """
    if not seguidores or not visualizacoes:
        return False
    if visualizacoes < seguidores * 3:
        return False
    return (total_engajamento / visualizacoes) < 0.01


# ── consultas prontas sobre o banco ──────────────────────────────────────────

def _corte_maturacao(con=None, dias: int | None = None) -> str:
    """Último dia que já maturou. Na v2 o prazo é configurável na tela."""
    if dias is None:
        from politicos import db as _db
        dias = _db.maturacao_dias(con) if con is not None else _db.MATURACAO_PADRAO
    return (date.today() - timedelta(days=dias)).strftime("%Y-%m-%d")


def resumo_perfis(con, desde: str | None = None, ate: str | None = None,
                  partido: str | None = None) -> list[dict]:
    """Uma linha por perfil acompanhado, já com as métricas do período.

    `ate` nunca passa da maturação: pedir "até hoje" devolve até hoje-14d.
    """
    corte = _corte_maturacao(con)
    ate = min(ate, corte) if ate else corte
    desde = desde or "2026-01-01"

    filtro = "WHERE p.acompanhar=1"
    args: list = []
    if partido:
        filtro += " AND p.partido=?"
        args.append(partido)

    linhas = con.execute(f"""
        SELECT p.id, p.username, p.nome, p.partido, p.numero, p.cargo, p.faixa,
               p.seguidores, p.verificado,
               COUNT(o.id)                        AS posts,
               COALESCE(SUM(o.curtidas),0)        AS curtidas,
               COALESCE(SUM(o.comentarios),0)     AS comentarios,
               COALESCE(SUM(o.visualizacoes),0)   AS visualizacoes,
               MIN(o.publicado_em)                AS primeiro,
               MAX(o.publicado_em)                AS ultimo
          FROM perfis p
          LEFT JOIN posts o ON o.perfil_id = p.id
               AND date(o.publicado_em) BETWEEN ? AND ?
          {filtro}
         GROUP BY p.id
    """, (desde, ate, *args)).fetchall()

    # Snapshots de TODOS os perfis numa consulta só. Antes era uma consulta por
    # perfil dentro do laço — 278 idas ao banco a cada carregamento da tela.
    #
    # Vai até HOJE, não até o corte de maturação: contagem de seguidores não
    # amadurece, é uma leitura pontual. Cortar em `ate` descartava o snapshot
    # desta semana e zerava o crescimento de quase todo mundo.
    series: dict[int, list[tuple[str, int]]] = {}
    for s in con.execute(
        """SELECT perfil_id, semana, seguidores FROM snapshots
            WHERE semana >= ? ORDER BY perfil_id, semana""",
        (desde,),
    ):
        series.setdefault(s["perfil_id"], []).append((s["semana"], s["seguidores"]))

    # Histórico eleitoral: o melhor previsor da nominata. Uma consulta só.
    #
    # A ordem escolhe qual disputa representa o candidato, e ela importa: pegar
    # o MAIOR voto de qualquer cargo colocava a votação de governador ou de
    # prefeito de Joinville lado a lado com a de deputado estadual, como se
    # fossem a mesma corrida. Agora a última disputa de DEPUTADO ESTADUAL vem
    # primeiro; só quem nunca disputou estadual cai em outro cargo, e a tela
    # marca isso com o nome do cargo.
    votos: dict[int, dict] = {}
    for r in con.execute(f"""
        SELECT perfil_id, ano, cargo, votos, situacao, municipio
          FROM v2_votos_candidato
         ORDER BY (UPPER(cargo) = '{CARGO_REFERENCIA}') DESC, ano DESC, votos DESC
    """):
        votos.setdefault(r["perfil_id"], {
            "votos": r["votos"], "ano": r["ano"], "cargo": r["cargo"],
            "situacao": r["situacao"], "municipio": r["municipio"],
            "mesmo_cargo": (r["cargo"] or "").upper() == CARGO_REFERENCIA})

    # Um glob só em vez de um stat() por perfil.
    from politicos import db as _db
    com_foto = ({p.stem for p in _db.PICS_DIR.glob("*.jpg")}
                if _db.PICS_DIR.exists() else set())

    dias = (date.fromisoformat(ate) - date.fromisoformat(desde)).days or 1
    saida = []
    for r in linhas:
        eng = engajamento(r["curtidas"], r["comentarios"])
        serie = series.get(r["id"], [])
        saida.append({
            "id": r["id"], "username": r["username"], "nome": r["nome"],
            "partido": r["partido"], "numero": r["numero"], "cargo": r["cargo"],
            "faixa": r["faixa"], "seguidores": r["seguidores"],
            "verificado": bool(r["verificado"]),
            "foto": (f"/static/politicos_pics/{r['username']}.jpg"
                     if r["username"] in com_foto else None),
            "posts": r["posts"], "engajamento": eng,
            "visualizacoes": r["visualizacoes"],
            "por_post": round(eng / r["posts"], 1) if r["posts"] else None,
            "por_seguidor": taxa_por_seguidor(eng, r["seguidores"], r["posts"]),
            "por_visualizacao": taxa_por_visualizacao(eng, r["visualizacoes"]),
            "frequencia": frequencia_semanal(r["posts"], dias),
            "crescimento": (crescimento_pct(serie[0][1], serie[-1][1])
                            if len(serie) >= 2 else None),
            "historico": votos.get(r["id"]),
            # Quantos votos cada mil seguidores renderam na última disputa. Separa
            # quem converte audiência em voto de quem só tem plateia.
            "votos_por_mil_seg": (
                round(votos[r["id"]]["votos"] / r["seguidores"] * 1000, 1)
                if r["id"] in votos and r["seguidores"] else None),
            # Série curta para o sparkline da linha. Só os valores: o eixo x é a
            # ordem, e nomear as semanas aqui triplicaria o JSON à toa.
            "serie": [v for _, v in serie],
            # As pontas da série DESTE perfil. O cabeçalho da coluna mostra a
            # janela global, mas cada perfil tem a sua: quem entrou na semana
            # passada tem 7 dias de crescimento, não 16 semanas, e dizer o
            # contrário é o mesmo erro que já se corrigiu uma vez.
            "serie_de": serie[0][0] if serie else None,
            "serie_ate": serie[-1][0] if serie else None,
        })
    return saida


def taxa_amortecida(por_seguidor: float | None, seguidores: int | None,
                    mediana: float) -> float | None:
    """Puxa a taxa de contas pequenas na direção da mediana.

    Quanto menor a base, menos a taxa observada é evidência: um post que
    estourou fora da base infla 19% numa conta de 3 mil e nada numa de 200 mil.
    """
    if por_seguidor is None:
        return None
    n = seguidores or 0
    peso = n / (n + AMORTECIMENTO)
    return round(por_seguidor * peso + mediana * (1 - peso), 4)


def com_cobertura(linhas: list[dict], minimo_posts: int = MINIMO_POSTS) -> list[dict]:
    """Marca quem tem dado suficiente para ser comparado.

    Duas coisas diferentes ficam de fora, e a tela as trata igual porque o
    efeito é o mesmo — não dá para comparar:

    - perfil ainda não coletado (o backfill não chegou nele);
    - perfil com pouquíssimo post no período, onde a média por post é ruído.
    """
    from statistics import median

    comparaveis = [d for d in linhas if (d["posts"] or 0) >= minimo_posts]
    taxas = [d["por_seguidor"] for d in comparaveis if d["por_seguidor"] is not None]
    med = median(taxas) if taxas else 0.0
    for d in linhas:
        d["coberto"] = (d["posts"] or 0) >= minimo_posts
        d["por_seguidor_ajustado"] = (
            taxa_amortecida(d["por_seguidor"], d["seguidores"], med)
            if d["coberto"] else None)
    return sorted(linhas, key=lambda d: -(d["seguidores"] or 0))
