/* Os cartões de prova do 2º turno — biblioteca da página única.
 *
 * Três blocos, montados por `apuracao_analise.js` (que é quem desenha o
 * Sankey desde 29/10/2026; o Sankey de cenários que morava aqui saiu):
 *
 *   limite      o que a aritmética obriga — a terceira via deu ao Lula pelo
 *               menos 60,1% dela. Não é modelo: são duas subtrações.
 *   transicao   cada candidato da terceira via com o intervalo de 95%. Só 1
 *               dos 10 tem intervalo que decide algo, e a barra mostra isso.
 *   abstencao   por que a abstenção que voltou já está nos votos novos.
 */
(function () {
  "use strict";

  var AP, h, num, pct, cartao;

  function mm(x) {
    var a = Math.abs(x || 0);
    if (a >= 1e6) return (x / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " mi";
    if (a >= 1e3) return (x / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 0 }) + " mil";
    return num(x);
  }

  function cartaoLimite(d) {
    var l = d.limite || {};
    if (!l.ok) return null;
    return cartao("O que a aritmética obriga (não é estimativa)",
      "Esta é a parte mais forte da página, e são duas subtrações. Nenhuma escolha de modelo entra aqui: só o total de votos de cada campo.",
      h("div", { class: "ap-conta-limite" },
        h("div", { class: "ap-conta-limite-num", text: "≥ " + pct(100 * l.q_min, 1) }),
        h("div", { class: "ap-conta-limite-txt" },
          h("b", { text: "da terceira via foi para o Lula, no mínimo. " }),
          "Se TODOS os " + mm(l.novos) + " votos válidos novos tivessem ido para o Lula, ainda faltariam " +
          mm(l.q_min_votos) + " para fechar o ganho dele. Esses só podiam vir da terceira via.")),
      h("div", { class: "ap-conta-limite-prova" },
        h("div", { class: "ap-conta-limite-linha" },
          h("span", { text: "Ganho do Lula entre os turnos" }),
          h("b", { text: mm(l.ganho_lula) })),
        h("div", { class: "ap-conta-limite-linha" },
          h("span", { text: "Menos os votos válidos que apareceram (todos para ele, o melhor caso)" }),
          h("b", { text: "− " + mm(l.novos) })),
        h("div", { class: "ap-conta-limite-linha total" },
          h("span", { text: "Sobra que veio obrigatoriamente da terceira via" }),
          h("b", { text: "= " + mm(l.q_min_votos) }))),
      h("p", { class: "ap-conta-conta" },
        "O contrário também vale, e é o que derruba a hipótese mais comum: se a terceira via tivesse ido TODA para o Flávio, " +
        "o Lula precisaria tirar " + mm(l.ganho_lula) + " dos votos novos — isto é, " +
        pct(100 * l.p_necessario_se_q_zero, 0) + " de " + mm(l.novos) + ". Como não existe " +
        pct(100 * l.p_necessario_se_q_zero, 0) + " de um conjunto, esse cenário é impossível. " +
        "E o Flávio não perdeu voto para ninguém: ele também ganhou (" + mm(l.ganho_flavio) + ")."),
      h("p", { class: "ap-conta-fonte", text: "Fonte: votos válidos e votos por candidato, arquivo oficial do TSE nos dois turnos. A identidade é contábil: novos + terceira via = ganho dos dois candidatos, ao voto." }));
  }

  function cartaoAbstencao(d) {
    // A hipótese "as abstenções do 1º turno apareceram e votaram no Lula".
    // Ela NÃO precisa de tratamento à parte: quem se absteve no 1º turno e
    // votou no 2º já está DENTRO dos "votos válidos novos". É uma linha de
    // texto, e resolve o mal-entendido sem inventar número.
    return cartao("E a abstenção do 1º turno que apareceu?",
      "Já está contada — e é o cartão que fecha a lista das “formas de o Lula ter vencido”.",
      h("p", { class: "ap-conta-conta" },
        "Quem se absteve em 04/10 e votou em 25/10 não é uma terceira fonte: o voto dele é um dos " +
        mm((d.limite || {}).novos) + " de votos válidos NOVOS. Quando o comparecimento sobe e branco/nulo cai, o voto que " +
        "aparece entra exatamente nessa linha do Sankey — venha ele de quem se absteve, de quem votou branco ou de quem anulou."),
      h("p", { class: "ap-conta-conta" },
        "Por isso as fontes possíveis são duas, e só duas: voto válido que passou a existir, ou voto que no 1º turno foi para " +
        "outro candidato. Não há terceira origem para os 10,38 milhões — e é essa a razão de a conta fechar tão apertada."),
      h("p", { class: "ap-conta-fonte", text: "Fonte: comparecimento, brancos e nulos oficiais do TSE nos dois turnos." }));
  }

  // ── por candidato da terceira via, com a incerteza à vista ───────────────
  // O modelo por candidato existe (`transicao` no conta.json) e prevê melhor o
  // total que o agregado — mas isso não quer dizer que cada λ esteja medido.
  // Medimos: só 1 dos 10 tem intervalo estreito o bastante para afirmar algo.
  // Então cada linha mostra a estimativa E a barra do IC, e o rótulo diz quando
  // o dado não decide. Sem isso, "Zema 0%" viraria manchete.
  function cartaoTransicao(d) {
    var t = d.transicao;
    if (!t || !t.ok) {
      return cartao("Por candidato: o modelo não rodou",
        "O cálculo da transição por candidato não está disponível agora.",
        h("p", { class: "ap-conta-fonte", text: (t && t.motivo) || "sem dados" }));
    }
    var linhas = t.candidatos.map(function (c) {
      // A barra: 0–100% do eixo, com o trecho do IC em destaque e o ponto da
      // estimativa. Largura grande = o dado não decide.
      var barra = h("div", { class: "ap-trans-barra", role: "img",
        "aria-label": c.nm + ": estimativa " + pct(100 * c.estimativa, 0) +
          ", intervalo de " + pct(100 * c.ic[0], 0) + " a " + pct(100 * c.ic[1], 0) },
        h("span", { class: "ap-trans-ic", vars: { "--de": (100 * c.ic[0]) + "%",
          "--ate": (100 * c.ic[1]) + "%" } }),
        h("span", { class: "ap-trans-pt", vars: { "--p": (100 * c.estimativa) + "%" } }));
      var selo;
      if (c.na_borda) selo = h("span", { class: "ap-trans-selo borda", text: "na borda" });
      else if (c.identificado) selo = h("span", { class: "ap-trans-selo ok", text: "medido" });
      else selo = h("span", { class: "ap-trans-selo incerto", text: "não decide" });
      return h("div", { class: "ap-trans-linha" + (c.identificado ? "" : " incerta") },
        h("div", { class: "ap-trans-nome" },
          h("b", { text: c.nm }),
          h("span", { class: "ap-trans-partido", text: " " + c.p }),
          h("span", { class: "ap-trans-votos", text: num(c.votos_1t) + " votos no 1º turno" })),
        h("div", { class: "ap-trans-centro" }, barra),
        h("div", { class: "ap-trans-num" },
          h("b", { text: pct(100 * c.estimativa, 0) }),
          h("span", { text: "IC " + pct(100 * c.ic[0], 0) + "–" + pct(100 * c.ic[1], 0) }),
          selo));
    });
    var tr = t.troca;
    return cartao("Cada candidato da terceira via: quanto foi para o Lula",
      "Estimativa por município, com o intervalo de 95% de cada uma. A barra cinza é o intervalo: quanto mais larga, menos o dado decide. " +
      "Só " + t.identificados + " de " + t.total + " candidatos têm intervalo estreito o bastante para afirmar alguma coisa.",
      h("div", { class: "ap-trans-legenda" },
        h("span", { class: "ap-mudo", text: "0% = todo o voto dele foi para o Flávio · 100% = todo para o Lula" })),
      h("div", { class: "ap-trans-lista" }, linhas),
      // As pesquisas dão ao Lula de 34% a 52% do eleitor do Cury; o modelo, bem
      // mais. Sem explicar a diferença, o leitor toma uma das duas por erro.
      h("p", { class: "ap-trans-pesquisa" },
        h("b", { text: "Por que o modelo e as pesquisas não batem. " }),
        "As pesquisas perguntaram ao eleitor do Cury em quem ia votar e deram ao Lula de 34% (Quaest) a 52% (AtlasIntel). " +
        "O modelo não pergunta a ninguém: compara, cidade por cidade, onde o Cury teve voto e onde o Lula cresceu. " +
        "Se o Lula cresceu justamente onde o Cury era forte, o modelo atribui o crescimento ao eleitor do Cury, mesmo que parte " +
        "tenha vindo de outros eleitores das mesmas cidades. Por isso a estimativa sai alta e o intervalo, largo: é o limite do " +
        "dado por cidade, não o voto de cada pessoa."),
      h("div", { class: "ap-trans-troca" },
        h("b", { text: "E a troca direta do Flávio para o Lula? " }),
        "≈ " + num(tr.votos) + " votos (intervalo de " + num(tr.votos_ic[0]) + " a " + num(tr.votos_ic[1]) +
        ", sobre " + num(tr.eleitorado_flavio) + " que votaram nele no 1º turno). Ou seja: praticamente nenhuma. " +
        "O Flávio terminou o 2º turno com MAIS votos que tinha no 1º — não houve debandada."),
      h("details", { class: "ap-conta-detalhe" },
        h("summary", { text: "Por que 8 dos 10 vêm como “não decide”" }),
        h("p", { text: "O modelo é de inferência ecológica: mínimos quadrados por município com os parâmetros presos entre 0 e 1 " +
          "(a formulação clássica de Goodman/King para tabelas J×K). Ele reproduz bem o TOTAL — prevê melhor que o modelo agregado —, " +
          "mas isso não implica que cada coeficiente esteja bem estimado. Os votos dos dez candidatos sobem e descem juntos pelos " +
          "municípios, então o modelo não consegue atribuir a mudança a um deles em particular." }),
        h("p", { text: "Medimos a consequência: largura média do intervalo de 95% de " + String(t.largura_media).replace(".", ",") +
          " (numa escala de 0 a 1). Para seis candidatos o intervalo é o próprio [0%, 100%]. O Cury sai medido (" +
          pct(100 * t.candidatos[0].ic[0], 0) + " a " + pct(100 * t.candidatos[0].ic[1], 0) +
          ") porque é o maior e o mais disperso geograficamente; o Zema aparece “na borda” porque o otimizador o empurrou para zero — " +
          "isso é artefato do ajuste, não uma descoberta." }),
        h("p", { text: t.referencia_externa + " Quem publica número firme por candidato está indo além do que este dado permite." })),
      h("p", { class: "ap-conta-fonte", text: "Fonte: votação por seção de 2026 (dados abertos do TSE), agregada por município. " +
        "Método: " + t.metodo + ", em " + num(t.municipios) + " municípios; intervalo por 40 subamostras." }));
  }

  function iniciar(APx) {
    AP = APx; h = AP.h; num = AP.num; pct = AP.pct; cartao = AP.cartao;
  }

  window.AP_BLOCOS = window.AP_BLOCOS || {};
  window.AP_BLOCOS.iniciar_sankey = iniciar;
  window.AP_BLOCOS.limite = cartaoLimite;
  window.AP_BLOCOS.transicao = cartaoTransicao;
  window.AP_BLOCOS.abstencao = cartaoAbstencao;
})();
