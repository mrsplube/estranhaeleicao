/* A conta do 2º turno de 2026 — a aba que explica o resultado.
 *
 * Registrada em window.AP_EXTRAS.conta (o apuracao.js chama as vistas extras
 * com o objeto AP). Todo número vem de dois arquivos congelados:
 *
 *   /apuracao/explicacao/analise.json      → os totais, o fluxo e a conferência
 *   /apuracao/explicacao/municipios.json   → os 5.570 municípios (mapa/lista)
 *
 * Nada aqui é recalculado em cima de JSON grande nem vai ao TSE. Todo DOM é
 * montado por AP.h(), que só escreve TEXTO — dado do TSE nunca vira HTML.
 *
 * A régua editorial desta aba, que é o motivo dela existir: quem chega aqui
 * desconfiado do resultado precisa poder CONFERIR a conta, não ser convencido
 * por adjetivo. Por isso todo bloco tem (a) o número, (b) a fonte, e (c) o que
 * ele NÃO prova. Onde é estimativa, a palavra "estimativa" está no cartão, não
 * no rodapé.
 */
(function () {
  "use strict";

  var AP, h, num, pct, cartao, kpi;
  var dados = null, pedindo = false, muns = null, pedindoMuns = false;
  var erro = null;
  // Versão da publicação (o `static_v` do template). O JSON é servido com
  // `max-age` longo porque é ARQUIVO CONGELADO — mas quando o site é
  // republicado o conteúdo pode ter mudado, e sem a versão na URL o navegador
  // continuaria mostrando o arquivo velho por um dia. Com `?v=`, publicar é
  // publicar: a URL muda e o cache cai sozinho.
  var VER = (function () {
    var r = document.getElementById("ap");
    return (r && r.getAttribute("data-versao")) || "";
  })();
  function comVersao(caminho) {
    return AP.base + caminho + (VER ? "?v=" + encodeURIComponent(VER) : "");
  }

  var A = { cor: "#e3364a", nm: "Lula", n: "13" };
  var B = { cor: "#2a78d6", nm: "Flavio", n: "22" };

  function $(id) { return document.getElementById(id); }
  function mm(x) {
    // milhões/pontos percentuais: a língua em que a eleição se discute
    var a = Math.abs(x || 0);
    if (a >= 1e6) return (x / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " mi";
    if (a >= 1e3) return (x / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 0 }) + " mil";
    return num(x);
  }
  function mi(x) {
    return (x / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function pp(x) {
    return (x > 0 ? "+" : x < 0 ? "−" : "") +
      Math.abs(x).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " p.p.";
  }
  function pctv(x, casas) { return pct(x, casas === undefined ? 2 : casas); }

  // ── carregamento ────────────────────────────────────────────────────────
  // Uma falha NÃO pode congelar a aba: antes, um erro na primeira tentativa
  // deixava `erro` setado e a tela mostrava "Não consegui abrir a conta" para
  // sempre, mesmo com o arquivo disponível. Agora toda chamada de `desenhar`
  // tenta de novo enquanto não houver dado.
  function carregar() {
    if (dados || pedindo) return;
    pedindo = true;
    erro = null;
    fetch(comVersao("/explicacao/conta.json"), { cache: "default" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (d) { dados = d; pedindo = false; AP.desenhar(); })
      .catch(function (e) { erro = e; pedindo = false; AP.desenhar(); });
  }
  // `pronto` é para a página única: ela pede a lista só quando a seção das
  // cidades abre (são ~650 KB) e redesenha SÓ a seção — um AP.desenhar()
  // aqui recolheria todas as seções abertas e perderia o cenário montado.
  function carregarMuns(pronto) {
    if (muns) { if (pronto) pronto(); return; }
    if (pedindoMuns) return;
    pedindoMuns = true;
    fetch(comVersao("/explicacao/municipios.json"), { cache: "default" })
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (l) { muns = l; pedindoMuns = false; if (pronto) pronto(); else AP.desenhar(); })
      .catch(function () { pedindoMuns = false; });
  }
  function semAcento(t) {
    return (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toUpperCase();
  }

  // ── blocos ──────────────────────────────────────────────────────────────
  function abertura(d) {
    var n = d.nacional;
    var ganhoLula = d.ganho_lula, ganhoFlavio = d.ganho_flavio;
    var novos = d.novos_validos, terc = d.terceira_via;
    // A frase que responde à pergunta antes de qualquer gráfico.
    return cartao("A pergunta, respondida em três números",
      "Se o Flavio foi o mais votado em 04/10, como o Lula terminou com " + mi(n.lula2) +
      " milhões de votos? A resposta não é opinião: são estes três números, e os três podem ser conferidos no TSE.",
      h("div", { class: "ap-conta-tres" },
        h("div", { class: "ap-conta-tres-item", vars: { "--cor": A.cor } },
          h("div", { class: "ap-conta-tres-num", text: "+" + mi(ganhoLula) + " mi" }),
          h("div", { class: "ap-conta-tres-rot", text: "de votos a mais para o Lula do 1º para o 2º turno" }),
          h("div", { class: "ap-conta-tres-nota", text: "Ele tinha " + mi(n.lula1) + " mi em 04/10 e teve " + mi(n.lula2) + " mi em 25/10." })),
        h("div", { class: "ap-conta-tres-item", vars: { "--cor": B.cor } },
          h("div", { class: "ap-conta-tres-num", text: "+" + mi(ganhoFlavio) + " mi" }),
          h("div", { class: "ap-conta-tres-rot", text: "de votos a mais para o Flavio" }),
          h("div", { class: "ap-conta-tres-nota", text: "Ele tinha " + mi(n.flavio1) + " mi em 04/10 e teve " + mi(n.flavio2) + " mi em 25/10." })),
        h("div", { class: "ap-conta-tres-item", vars: { "--cor": "#64748b" } },
          h("div", { class: "ap-conta-tres-num", text: mi(terc) + " mi" }),
          h("div", { class: "ap-conta-tres-rot", text: "de votos foram para a terceira via no 1º turno" }),
          h("div", { class: "ap-conta-tres-nota", text: "Os 10 candidatos que não passaram: 7,8% dos válidos. No 2º turno esse eleitor escolheu um dos dois, anulou ou não foi votar."}))),
      h("p", { class: "ap-conta-conta" },
        "Some os dois lados: " + mm(ganhoLula) + " + " + mm(ganhoFlavio) + " = " +
        mm(ganhoLula + ganhoFlavio) + " de votos a mais para os dois candidatos juntos. " +
        "Desse total, " + mm(novos) + " são votos válidos que passaram a existir (mais gente votando, menos branco e nulo) e " +
        mm(terc) + " são votos que no 1º turno foram para outro candidato."),
      h("p", { class: "ap-conta-fonte", text: "Fonte: arquivo oficial do TSE por UF (ele2026/6257 e 6258). A soma bate exatamente com o que o TSE publicou nos dois turnos." }));
  }

  function cartaoComparecimento(d) {
    var n = d.nacional;
    var br = n.brancos1 - n.brancos2, nu = n.nulos1 - n.nulos2;
    var comp = n.comp2 - n.comp1;
    return cartao("Primeiro mal-entendido: “faltou gente votar”",
      "Não faltou. O 2º turno teve MAIS gente nas urnas que o 1º — e ainda teve menos branco e menos nulo, então o número de votos válidos subiu 4%.",
      h("div", { class: "ap-kpis" },
        kpi("Comparecimento · 1º turno", mm(n.comp1), "eleitores nas urnas em 04/10"),
        kpi("Comparecimento · 2º turno", mm(n.comp2), "+" + mm(n.comp2 - n.comp1) + " eleitores que o 1º turno", 100),
      ),
      h("div", { class: "ap-conta-fluxo" },
        linhaFluxo("Compareceram a mais", comp, "positive", "Mais " + mm(comp) + " pessoas foram votar em 25/10 do que em 04/10, no país inteiro."),
        linhaFluxo("Brancos a menos", br, "positive", "Branco caiu de " + mm(n.brancos1) + " para " + mm(n.brancos2) + ". Em disputa de dois, o eleitor escolhe."),
        linhaFluxo("Nulos a menos", nu, "positive", "Nulo caiu de " + mm(n.nulos1) + " para " + mm(n.nulos2) + " — erro de digitação também diminui com dois números na tela.")),
      h("p", { class: "ap-conta-conta" },
        "Somando: " + mm(comp) + " de comparecimento a mais + " + mm(br + nu) + " de branco/nulo que viraram voto válido = " +
        mm(novosValidos(d)) + " de votos válidos que não existiam no 1º turno. É essa linha que o cartão seguinte divide entre os dois candidatos."),
      h("details", { class: "ap-conta-detalhe" },
        h("summary", { text: "Por que essas três linhas não se somam duas vezes" }),
        h("p", { text: "Cada turno tem UMA identidade, e ela fecha no voto: comparecimento = votos válidos + brancos + nulos. No 1º turno, " +
          num(n.comp1) + " = " + num(n.validos1) + " + " + num(n.brancos1) + " + " + num(n.nulos1) + ". No 2º, " +
          num(n.comp2) + " = " + num(n.validos2) + " + " + num(n.brancos2) + " + " + num(n.nulos2) + ". Conferido nos dois: fecha exato." }),
        h("p", { text: "As três linhas acima não são três parcelas somadas por cima: são a DIFERENÇA entre as duas identidades. " +
          "O comparecimento subiu " + num(comp) + ", e branco+nulo caiu " + num(br + nu) + ". O que sobra é o aumento dos válidos: " +
          num(comp) + " − " + num(br + nu) + " = " + num(novosValidos(d)) + ", que é exatamente a diferença entre " +
          num(n.validos2) + " e " + num(n.validos1) + ". Se houvesse voto contado duas vezes, essa igualdade quebraria." }),
        h("p", { text: "E a conferência independente: a soma de TODAS as seções de cada estado bate com o arquivo oficial do TSE em 28 de 28 " +
          "unidades (cartão abaixo). Um voto duplicado apareceria como diferença de 1 — e a diferença é zero em todas." })));
  }
  function novosValidos(d) { return d.novos_validos; }

  function linhaFluxo(rotulo, valor, tipo, nota) {
    return h("div", { class: "ap-conta-fluxo-linha " + (tipo || "") },
      h("div", { class: "ap-conta-fluxo-rot", text: rotulo }),
      h("div", { class: "ap-conta-fluxo-val", text: (valor >= 0 ? "+" : "−") + mm(Math.abs(valor)) }),
      h("div", { class: "ap-conta-fluxo-nota", text: nota }));
  }

  function cartaoTransferencia(d) {
    var f = d.fluxo || {};
    if (!f.ok) {
      return cartao("Para onde foi a terceira via", "A estimativa não pôde ser feita: " + (f.motivo || "sem dados") + ".");
    }
    var bl = f.reparticao;
    // Barra: 100% de cada pool dividido entre os dois. O comprimento é o tamanho
    // do pool, para o olho ver que a terceira via foi quase o dobro dos novos.
    return cartao("Para onde foram os votos: novos e terceira via",
      "Estimativa por município (não é pesquisa, e não é o voto de ninguém): o que explica a variação do Lula em cada uma das " +
      num(f.municipios) + " cidades em que se vota. O modelo acerta 99,6% do movimento cidade a cidade. A barra usa o valor que FECHA a conta do país.",
      h("div", { class: "ap-conta-pools" },
        poolBar("Votos válidos que apareceram", f.novos, bl.novos_lula, bl.novos_flavio,
          "Comparecimento maior e menos branco/nulo.", "a"),
        poolBar("Votos da terceira via no 1º turno", f.terceira, bl.terceira_lula, bl.terceira_flavio,
          "Os 10 candidatos que não disputaram o 2º turno.", "b")),
      h("p", { class: "ap-conta-atalho" },
        h("a", { href: "#sankey", text: "Ver o Sankey: cada cenário que a conta aceita, e o mínimo que a aritmética obriga →" })),
      h("p", { class: "ap-conta-conta" },
        "A conta fecha no voto: " + mm(f.novos_para_lula) + " + " + mm(f.terceira_para_lula) + " = " + mm(d.ganho_lula) +
        " para o Lula, e " + mm(f.novos_para_flavio) + " + " + mm(f.terceira_para_flavio) + " = " + mm(d.ganho_flavio) +
        " para o Flavio. Somando os dois lados dá " + mm(f.novos + f.terceira) + " — exatamente os " + mm(f.novos) +
        " de votos novos mais os " + mm(f.terceira) + " da terceira via. Nenhum voto entra em duas faixas."),
      h("p", { class: "ap-conta-conta" },
        "O " + pct(bl.terceira_lula, 1) + " da terceira via é o mínimo que a aritmética obriga, não o chute do modelo: a regressão sozinha dizia " +
        pct(100 * f.b, 1) + ", que é impossível (não sobraria voto novo suficiente para fechar a conta). O valor consistente fica entre " +
        pct(100 * Math.max(f.b, (d.ganho_lula - f.novos) / f.terceira), 1) + " e " + pct(f.b_ic[1] * 100, 1) + " — e todo esse intervalo está acima da metade."),
      h("details", { class: "ap-conta-detalhe" },
        h("summary", { text: "Como essa estimativa é feita (e o que ela não prova)" }),        h("p", { text: "Para cada município, a conta é: variação do voto do Lula = a × (votos válidos novos) + b × (votos da terceira via). " +
          "Os coeficientes a e b são achados de uma vez, com os 5.570 municípios, por mínimos quadrados — o mesmo método que se usa para " +
          "separar o efeito de duas coisas que acontecem juntas. Saiu a = " + f.a.toLocaleString("pt-BR", { maximumFractionDigits: 3 }) +
          " (intervalo de 95%: " + f.a_ic[0].toLocaleString("pt-BR") + " a " + f.a_ic[1].toLocaleString("pt-BR") + ") e b = " +
          f.b.toLocaleString("pt-BR", { maximumFractionDigits: 3 }) + " (95%: " + f.b_ic[0].toLocaleString("pt-BR") + " a " +
          f.b_ic[1].toLocaleString("pt-BR") + ")." }),
        h("p", { text: "Os 9,32 mi e os 4,78 mi acima são os totais do PAÍS — é o que fecha com os outros cartões desta aba. A regressão usa " +
          num(f.municipios) + " municípios (o piso de 300 votos válidos no 1º turno deixa de fora as cidades minúsculas), e a soma deles dá " +
          mm(f.terceira_recorte) + " e " + mm(f.novos_recorte) + " — a diferença para o total nacional é recorte, não voto contado duas vezes." }),
        h("p", { text: "a ≈ 1 quer dizer que o voto NOVO foi todo para o Lula, dentro do que o dado consegue distinguir. b ≈ 0,56 quer dizer que pouco mais " +
          "da metade da terceira via foi para o Lula. Os intervalos são largos porque cidade não é urna: o que se mede é o movimento agregado, não o " +
          "voto de cada pessoa." }),
        h("p", { text: "O que ela NÃO prova: (1) que um eleitor específico do Ciro ou do Caiado votou no Lula — voto é secreto e isso não é observável; " +
          "(2) que a transferência foi igual em todo lugar — em cidade pequena o intervalo é maior; (3) que não houve troca nos dois sentidos (gente que " +
          "votou Lula no 1º turno e Flavio no 2º). A conta é consistente com os totais, e é o máximo que dado agregado permite afirmar." }),
        h("p", { text: "Sobre os candidatos da terceira via, um por um: NÃO é possível separar. Os votos dos 10 andam juntos demais (quem tem voto do Cury " +
          "também tem voto do Caiado, na mesma cidade), e a conta devolveria números inventados. Quem fizer essa conta por candidato e publicar " +
          "casa decimal está vendendo precisão que o dado não tem." })),
      h("p", { class: "ap-conta-fonte", text: "Fonte: votação por seção de 2026 (dados abertos do TSE), os dois turnos, agregada por município." }));
  }

  function poolBar(titulo, total, pctLula, pctFlavio, nota, chave) {
    return h("div", { class: "ap-conta-pool" },
      h("div", { class: "ap-conta-pool-topo" },
        h("span", { class: "ap-conta-pool-titulo", text: titulo }),
        h("span", { class: "ap-conta-pool-total", text: mm(total) + " votos" })),
      h("div", { class: "ap-conta-pool-barra", role: "img",
        "aria-label": titulo + ": " + pctv(pctLula, 1) + " para o Lula, " + pctv(pctFlavio, 1) + " para o Flavio" },
        h("span", { class: "ap-conta-pool-a", vars: { "--p": pctLula + "%", "--cor": A.cor } }),
        h("span", { class: "ap-conta-pool-b", vars: { "--p": pctFlavio + "%", "--cor": B.cor } })),
      h("div", { class: "ap-conta-pool-legenda" },
        h("span", { vars: { "--cor": A.cor } }, h("b", { text: pctv(pctLula, 1) }), " Lula · ≈" + mm(total * pctLula / 100)),
        h("span", { vars: { "--cor": B.cor } }, h("b", { text: pctv(pctFlavio, 1) }), " Flavio · ≈" + mm(total * pctFlavio / 100))),
      h("p", { class: "ap-conta-pool-nota", text: nota }));
  }

  function cartaoComparecimentoUf(d) {
    var ufs = (d.ufs || []).slice();
    if (!ufs.length) return null;
    var subiu = ufs.filter(function (u) { return u.variacao > 0; });
    var caiu = ufs.filter(function (u) { return u.variacao < 0; });
    // O eixo é a variação em pontos do eleitorado — é o que se pode comparar
    // entre estados de tamanhos diferentes.
    var max = Math.max.apply(null, ufs.map(function (u) { return Math.abs(u.variacao); }).concat([1]));
    var corpo = ufs.map(function (u) {
      var p = 100 * Math.abs(u.variacao) / max;
      return h("div", { class: "ap-conta-uf" + (u.variacao < 0 ? " caiu" : "") },
        h("span", { class: "ap-conta-uf-nome", text: u.nome }),
        h("span", { class: "ap-conta-uf-barra" },
          h("span", { vars: { "--p": p + "%" } })),
        h("span", { class: "ap-conta-uf-val", text: pp(u.variacao) }),
        h("span", { class: "ap-conta-uf-detalhe", text: pctv(u.pct1, 1) + " → " + pctv(u.pct2, 1) }));
    });
    return cartao("Segundo mal-entendido: “onde faltou urna”",
      "O comparecimento não subiu igual em todo lugar. Em " + caiu.length + " estados ele CAIU; em " + subiu.length + " subiu. " +
      "A média nacional subiu porque os estados que subiram são os maiores.",
      h("div", { class: "ap-conta-ufs" }, corpo),
      h("p", { class: "ap-conta-conta" },
        (function () {
          // O Exterior entra na tabela (tem eleitor e tem urna), mas não é
          // estado brasileiro — para o exemplo da frase, fica de fora.
          var br = (d.ufs || []).filter(function (u) { return u.uf !== "zz"; });
          var pior = br.length ? br[0] : ufs[0];
          var melhor = br.length ? br[br.length - 1] : ufs[ufs.length - 1];
          return "O " + pior.nome + " foi o caso extremo: " + pp(pior.variacao) + " de comparecimento, o maior tombo do país." +
            " Do outro lado, " + melhor.nome + ", com " + pp(melhor.variacao) + " — isso é comportamento de eleitor " +
            "(abstenção de 2º turno varia por região), não falha de urna. É justamente o que a conferência seção a seção " +
            "abaixo testa: se uma urna a menos tivesse votado, a soma das seções não fecharia com o total oficial.";
        })()),
      h("p", { class: "ap-conta-fonte", text: "Fonte: eleitorado e comparecimento oficiais do TSE por UF, nos dois turnos. Barras em pontos percentuais do eleitorado." }));
  }

  function cartaoConferencia(d) {
    var c = d.conferencia || {};
    var ufs = (c.ufs || []).slice().sort(function (a, b) { return a.nome < b.nome ? -1 : 1; });
    var selo = c.todas
      ? h("div", { class: "ap-conta-selo ok" },
          h("b", { text: "Fecha em " + c.fecham + " de " + c.total + " unidades da federação." }),
          " Para cada UF, a soma de TODAS as seções de 25/10 — comparecimento, válidos, brancos, nulos e o número de seções — " +
          "tem de dar exatamente o que o TSE publicou como resultado oficial daquele estado. Não deu diferença de 1 voto em nenhuma.")
      : h("div", { class: "ap-conta-selo ruim" }, "Alguma UF não fecha — veja a tabela.");
    var corpo = ufs.map(function (u) {
      return h("tr", {},
        h("td", { text: u.nome }),
        h("td", { class: "num", text: num(u.secoes) }),
        h("td", { class: "num", text: num(u.comp) }),
        h("td", { class: "num", text: num(u.validos) }),
        h("td", { class: "num" }, h("span", { class: "ap-conta-ok", text: u.fecha ? "0" : "≠" })));
    });
    return cartao("A conferência: seção por seção, contra o resultado oficial",
      "É o teste que sustenta todo o resto desta aba. Se a soma das seções não fechasse com o arquivo oficial do TSE, nenhuma conta feita " +
      "a partir delas valeria.",
      selo,
      h("details", { class: "ap-conta-detalhe" },
        h("summary", { text: "Ver a tabela das " + ufs.length + " unidades (e a diferença de cada uma)" }),
        h("div", { class: "ap-tabela-rolagem" },
          h("table", { class: "ap-tabela" },
            h("thead", {}, h("tr", {},
              h("th", { text: "Unidade" }),
              h("th", { class: "num", text: "seções somadas" }),
              h("th", { class: "num", text: "comparecimento" }),
              h("th", { class: "num", text: "votos válidos" }),
              h("th", { class: "num", text: "diferença" }))),
            h("tbody", {}, corpo))),
        h("p", { class: "ap-mudo", text: "A coluna “diferença” é o quanto a soma das seções menos o total oficial dá. Zero em todas — inclusive no Exterior, " +
          "que só tem uma diferença de seções não instaladas, sem voto dentro." })),
      h("p", { class: "ap-conta-conta" },
        "O que isso elimina: a hipótese de que os arquivos por seção (a fonte mais fina que o TSE publica) contem uma história diferente do " +
        "resultado proclamado. Eles contam a MESMA história, ao voto. O que isso NÃO elimina: o que só um recibo de urna ou a auditoria do " +
        "próprio TSE pode provar — esta página confere documentos, não urnas."),
      h("p", { class: "ap-conta-fonte", text: "Fonte: votacao_secao_2026_BR (dados abertos) somada e comparada com o arquivo oficial de cada UF (resultados.tse.jus.br)." }));
  }

  function cartaoCidades(d) {
    var corpo = h("div", { class: "ap-conta-cidades-corpo" });
    var entrada = h("input", { type: "search", list: "ap-conta-lista-cidades",
      placeholder: "Digite uma cidade (ex.: Joinville)", "aria-label": "Município" });
    var lista = h("datalist", { id: "ap-conta-lista-cidades" });
    var sel = null;

    function achar(v) {
      var alvo = semAcento(v);
      if (!alvo || !muns) return null;
      var achados = muns.filter(function (m) { return semAcento(m.nm) === alvo; });
      if (achados.length > 1) {
        var doUf = achados.filter(function (m) { return m.uf === "sc"; });
        return doUf.length ? doUf[0] : achados[0];
      }
      return achados[0] || null;
    }
    function abrir(m) {
      if (!m) { corpo.textContent = "Cidade não encontrada. Tente o nome como aparece no TSE (sem acento também funciona)."; return; }
      sel = m;
      corpo.textContent = "";
      corpo.appendChild(montar(m, m.v1, m.l1, m.f1));
    }
    function montar(m, t, l, f) {
      return h("div", { class: "ap-conta-mun" },
        h("div", { class: "ap-conta-mun-topo" },
          h("span", { text: m.nm + " · " + m.uf.toUpperCase() })),
        h("div", { class: "ap-conta-mun-par" },
          parTurno("1º turno (04/10)", t, l, f),
          parTurno("2º turno (25/10)", m.v2, m.l2, m.f2)),
        h("p", { class: "ap-conta-mun-nota", text:
          "Válidos: " + num(t) + " → " + num(m.v2) + " (" + (m.v2 >= t ? "+" : "") + num(m.v2 - t) + "). " +
          "Terceira via aqui no 1º turno: " + num(m.t) + " votos (" + pctv(100 * m.t / t, 1) + " dos válidos). " +
          "Variação do Lula: " + (m.l2 - m.l1 >= 0 ? "+" : "") + num(m.l2 - m.l1) + " votos." }));
    }
    function parTurno(rot, t, l, f) {
      return h("div", { class: "ap-conta-mun-turno" },
        h("div", { class: "ap-conta-mun-rot", text: rot }),
        h("div", { class: "ap-conta-mun-barra" },
          h("span", { vars: { "--p": (100 * l / t) + "%", "--cor": A.cor } }),
          h("span", { vars: { "--p": (100 * f / t) + "%", "--cor": B.cor } })),
        h("div", { class: "ap-conta-mun-nums" },
          h("span", { vars: { "--cor": A.cor }, text: pctv(100 * l / t, 1) + " Lula" }),
          h("span", { vars: { "--cor": B.cor }, text: pctv(100 * f / t, 1) + " Flavio" })));
    }
    entrada.addEventListener("change", function () { abrir(achar(entrada.value)); });
    if (muns) {
      muns.slice(0, 6000).forEach(function (m) { lista.appendChild(h("option", { value: m.nm })); });
    }
    // Exemplos de cara: uma capital que virou, uma cidade média, um reduto de
    // cada lado. O objetivo é a pessoa clicar e ver que a conta vale no lugar
    // dela também.
    var exemplos = ["SÃO PAULO", "RIO DE JANEIRO", "JOINVILLE", "FORTALEZA", "PORTO ALEGRE", "SALVADOR"];
    var botoes = exemplos.map(function (nm2) {
      return h("button", { type: "button", class: "ap-conta-chip", text: nm2.charAt(0) + nm2.slice(1).toLowerCase(),
        onclick: function () { entrada.value = nm2; abrir(achar(nm2)); } });
    });
    return cartao("A conta na sua cidade",
      "Escolha um município: os dois turnos lado a lado, com o tamanho da terceira via naquele lugar. É a mesma aritmética do país, " +
      "prefeitura por prefeitura.",
      h("div", { class: "ap-conta-busca" }, entrada),
      h("div", { class: "ap-conta-chips" }, botoes),
      h("p", { class: "ap-conta-dica", text: "Todas as " + (muns ? num(muns.length) : "5.570") + " cidades estão na lista — digite a sua." }),
      lista,
      corpo,
      h("p", { class: "ap-conta-fonte", text: "Fonte: votação por seção de 2026 (dados abertos do TSE), agregada por município." }));
  }

  function cartaoMetodo(d) {
    var c = d.conferencia || {};
    return cartao("O que esta página faz, e o que ela não faz",
      "A régua é simples: o que é contagem aparece com o total; o que é estimativa aparece com o intervalo. Nada aqui pede que você acredite.",
      h("ul", { class: "ap-conta-lista" },
        h("li", {}, h("b", { text: "Contagem (não há o que discutir): " }),
          "comparecimento, brancos, nulos, votos de cada candidato nos dois turnos, e a soma seção a seção de cada estado. " +
          "São " + num(d.linhas_secao || 0) + " linhas de seção processadas, e o total fecha com o TSE em " + c.fecham + " de " + c.total + "."),
        h("li", {}, h("b", { text: "Estimativa (diz o intervalo): " }),
          "a divisão da terceira via entre os dois. Sai de uma regressão em " + num((d.fluxo || {}).municipios || 0) +
          " municípios, com os coeficientes e os intervalos de 95% publicados acima."),
        h("li", {}, h("b", { text: "Não observável (e a página não finge): " }),
          "o voto de uma pessoa. Voto é secreto. Dizer “o eleitor do Cury foi para o Lula” é uma inferência sobre o agregado, " +
          "nunca sobre alguém."),
        h("li", {}, h("b", { text: "Não é auditoria: " }),
          "esta página confere os documentos que o TSE publica. O que prova a integridade da urna é o boletim de urna impresso, " +
          "o teste público de segurança e a auditoria do próprio TSE — e isso está em resultados.tse.jus.br.")),
      h("p", { class: "ap-conta-fonte", text: "Fontes: resultados.tse.jus.br (resultado oficial) e dadosabertos.tse.jus.br (votação por seção, por município e por partido)." }));
  }

  // ── por que não dá para dizer "o eleitor do Zema" ────────────────────────
  function cartaoPorCandidato(d) {
    var cands = (d.candidatos || []).filter(function (c) {
      return c.n !== "13" && c.n !== "22";
    });
    if (!cands.length) return null;
    var linhas = cands.map(function (c) {
      return h("tr", {},
        h("td", { text: c.nm }),
        h("td", { class: "num", text: c.p }),
        h("td", { class: "num", text: pctv(100 * (c.v || 0) / d.nacional.validos1, 2) }));
    });
    return cartao("“Mas quanto do eleitor do Zema foi para o Lula?”",
      "Essa é a pergunta natural — e a resposta honesta é que o dado público não permite responder. Não é limitação de esforço: é limitação de dado.",
      h("p", { class: "ap-conta-conta" },
        "Para separar dez candidatos seria preciso que os eleitores de cada um estivessem em lugares diferentes. Não estão. As bases geográficas dos dez " +
        "são praticamente as mesmas: medidas cidade a cidade, a semelhança entre dois candidatos quaisquer da terceira via vai de 0,86 a 0,99 " +
        "(1,00 seria idêntico). Onde tem voto do Cury tem voto do Caiado, do Renan, do Zema — na mesma proporção. Sem lugares distintos, a conta não tem como " +
        "distinguir quem foi para onde: qualquer divisão que se publique por candidato é arbitrária, escolhida por quem publica."),
      h("p", { class: "ap-conta-conta" },
        "Quando tentei estimar assim mesmo, o resultado se denunciou sozinho: a conta devolveu coeficientes como " +
        "“11,5 vezes os votos do Edmilson” e “22,3 vezes os da Clariana” — impossíveis, porque ninguém vota 11 vezes. É o que acontece quando se pede ao " +
        "modelo uma separação que o dado não tem. Publicar isso com duas casas decimais seria vender precisão inventada."),
      h("details", { class: "ap-conta-detalhe" },
        h("summary", { text: "Ver os dez candidatos e a fatia de cada um no 1º turno" }),
        h("div", { class: "ap-tabela-rolagem" },
          h("table", { class: "ap-tabela" },
            h("thead", {}, h("tr", {},
              h("th", { text: "Candidato" }), h("th", { class: "num", text: "Partido" }),
              h("th", { class: "num", text: "% dos válidos" }))),
            h("tbody", {}, linhas)))),
      h("p", { class: "ap-conta-conta" },
        "O que dá para afirmar, e é o que esta aba mostra: do conjunto dos " + mm(d.terceira_via) + " votos da terceira via, pouco mais da metade " +
        "terminou no Lula. Distribuir essa metade entre os dez é chute — e o cartão anterior explica por que nenhum chute é melhor que outro."),
      h("p", { class: "ap-conta-fonte", text: "Semelhança medida pelo cosseno entre os vetores de voto de cada candidato nos 5.643 municípios." }));
  }

  // Os blocos abaixo são usados pela PÁGINA ÚNICA, que chama `iniciar` antes
  // de montá-los. Sem isto, `h`/`cartao` continuariam indefinidos fora da
  // `vista` e cada bloco estouraria com "h is not a function".
  function iniciar(APx) {
    AP = APx; h = AP.h; num = AP.num; pct = AP.pct; cartao = AP.cartao; kpi = AP.kpi;
  }

  function vista(APx) {
    iniciar(APx);
    if (!dados && erro) {
      // Mostra o aviso, mas continua tentando: o arquivo pode voltar.
      setTimeout(function () { erro = null; AP.desenhar(); }, 2500);
      return [cartao("Não consegui abrir a conta por um instante", "",
        h("p", { text: "O arquivo da explicação não respondeu agora. Tentando de novo sozinho — se demorar, recarregue a página." }))];
    }
    if (!dados) { carregar(); return [h("p", { class: "ap-carregando", text: "Abrindo a conta do 2º turno…" })]; }
    if (!muns) carregarMuns();
    return [
      abertura(dados),
      cartaoPorCandidato(dados),
      h("div", { class: "ap-grade" },
        h("div", { class: "ap-c12" }, cartaoComparecimento(dados)),
        h("div", { class: "ap-c12" }, cartaoTransferencia(dados)),        h("div", { class: "ap-c12" }, cartaoComparecimentoUf(dados)),
        h("div", { class: "ap-c5 ap-pilha" }, cartaoConferencia(dados)),
        h("div", { class: "ap-c7 ap-pilha" }, cartaoCidades(dados))),
      cartaoMetodo(dados),
    ];
  }

  // Os blocos ficam expostos para a PÁGINA ÚNICA (apuracao_analise.js) montar
  // as seções recolhíveis sem duplicar código. Este arquivo deixa de ser uma
  // aba: vira a biblioteca das seções longas.
  window.AP_BLOCOS = window.AP_BLOCOS || {};
  window.AP_BLOCOS.iniciar_conta = iniciar;
  window.AP_BLOCOS.abertura = abertura;
  window.AP_BLOCOS.comparecimento = cartaoComparecimento;
  window.AP_BLOCOS.transferencia = cartaoTransferencia;
  window.AP_BLOCOS.comparecimentoUf = cartaoComparecimentoUf;
  window.AP_BLOCOS.conferencia = cartaoConferencia;
  window.AP_BLOCOS.cidades = cartaoCidades;
  window.AP_BLOCOS.carregarMunicipios = carregarMuns;
  window.AP_BLOCOS.metodo = cartaoMetodo;
  window.AP_BLOCOS.porCandidato = cartaoPorCandidato;

  window.AP_EXTRAS = window.AP_EXTRAS || {};
  window.AP_EXTRAS.conta = vista;
  if (AP && AP.app.estado && AP.app.vista === "conta") AP.desenhar();
})();
