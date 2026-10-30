/* As acusações que circularam depois do 2º turno, uma por uma (29/10/2026).
 *
 * Lê /apuracao/explicacao/acusacoes.json (~22 KB, gerado por
 * tools/migracoes/2026-10-29-acusacoes-2t.py a partir do arquivo seção a
 * seção do TSE). Nenhuma conta por visita.
 *
 * A régua de cada bloco, nesta ordem:
 *   1. o que a acusação diz, com o número dela;
 *   2. se o número CONFERE — quando confere, a página diz que confere;
 *   3. o que o dado mostra em volta (o 1º turno, o espelho, o resto do país);
 *   4. como qualquer um confere sozinho.
 *
 * Quem fez cada post fica de fora: a página responde à afirmação, não à
 * pessoa. Nome só de figura pública que assinou a afirmação (a carta do
 * Flávio) e de veículo que a publicou.
 */
(function () {
  "use strict";

  var AP, h, s, num, cartao;
  var dados = null, pedindo = false, erro = null, corpo = null;

  var COR = { lula: "#e3364a", flavio: "#2a78d6", cinza: "#94a3b8", alerta: "#b45309" };

  function mi(x) {
    return (x / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " mi";
  }
  function pc(x, c) {
    return (x || 0).toLocaleString("pt-BR", { minimumFractionDigits: c === undefined ? 1 : c,
      maximumFractionDigits: c === undefined ? 1 : c }) + "%";
  }
  function sinal(x) { return (x > 0 ? "+" : x < 0 ? "−" : "") + num(Math.abs(x)); }

  function carregar() {
    if (dados || pedindo) return;
    pedindo = true; erro = null;
    fetch(AP.base + "/explicacao/acusacoes.json" + (AP.versao ? "?v=" + encodeURIComponent(AP.versao) : ""),
      { cache: "default" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (x) { dados = x; pedindo = false; preencher(); })
      .catch(function (e) { erro = e; pedindo = false; preencher(); });
  }

  // ── peças comuns ────────────────────────────────────────────────────────
  function item(id, frase, onde, veredito, tom, conteudo) {
    return h("details", { class: "ap-acu", id: "acusacao-" + id },
      h("summary", { class: "ap-acu-topo" },
        h("span", { class: "ap-sec-seta", "aria-hidden": "true" }),
        h("span", { class: "ap-acu-cab" },
          h("span", { class: "ap-acu-frase", text: "“" + frase + "”" }),
          h("span", { class: "ap-acu-onde", text: onde })),
        h("span", { class: "ap-acu-veredito " + tom, text: veredito })),
      h("div", { class: "ap-acu-corpo" }, conteudo));
  }
  function bloco(rotulo, conteudo) {
    return h("div", { class: "ap-acu-bloco" }, h("h4", { text: rotulo }), conteudo);
  }
  function p(txt) { return h("p", { text: txt }); }
  function tabela(cab, linhas, classes) {
    return h("div", { class: "ap-tabela-rolagem" },
      h("table", { class: "ap-tabela ap-acu-tabela" },
        h("thead", {}, h("tr", {}, cab.map(function (c, i) {
          return h("th", { class: (classes && classes[i]) || "", text: c });
        }))),
        h("tbody", {}, linhas.map(function (l) {
          return h("tr", {}, l.map(function (c, i) { return h("td", { class: (classes && classes[i]) || "", text: c }); }));
        }))));
  }

  // A tabela "precisou eleitor trocar de lado?" nas duas eleições: em 2026 a
  // troca que importa é 22 → Lula; em 2022, Lula → 22 (o lado da virada).
  function tabelaTroca(d) {
    var a = d.troca_minima["2026"], b = d.troca_minima["2022"];
    var par = function (x) { return num(x[0]) + " (" + num(x[1]) + " eleitores)"; };
    return tabela(["Precisou eleitor do outro finalista mudar de lado?", "2026: do 22 para o Lula", "2022: do Lula para o 22"], [
      ["Municípios em que a conta exige troca (contando quem faltou no 1º turno)",
        num(a.municipios_estrito.para_13) + " de " + num(a.municipios_estrito.com_eleitorado),
        num(b.municipios_estrito.para_22) + " de " + num(b.municipios_estrito.com_eleitorado)],
      ["Municípios que exigiriam, se votou a mesma gente nos dois turnos", par(a.municipios_mesma_gente.para_13), par(b.municipios_mesma_gente.para_22)],
      ["Seções que exigiriam, se votou a mesma gente nos dois turnos", par(a.secoes_mesma_gente.para_13), par(b.secoes_mesma_gente.para_22)],
      ["Seções no sentido contrário (mesma hipótese)", par(a.secoes_mesma_gente.para_22), par(b.secoes_mesma_gente.para_13)],
    ], ["", "num", "num"]);
  }

  // As cidades da ponta, dos dois lados, com 2022 e o teste das seções: a
  // mudança se espalha pela cidade (cidade mudando) ou se concentra em poucas
  // seções (o que uma adulteração deixaria)?
  function foraDoPadrao(d) {
    var f = d.fora_do_padrao;
    if (!f) return p("Sem o dado das cidades.");
    var pp = function (x) { return (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " p.p."; };
    var nome = function (c) { return c.nm + "/" + c.uf.toUpperCase(); };
    var de2022 = function (c) {
      var y = c.em_2022;
      return y ? pp(y.desvio) + " (22 " + sinal(y.f[1] - y.f[0]) + ", Lula " + sinal(y.l[1] - y.l[0]) + ")" : "—";
    };
    var linhas = function (lista, rotulo) {
      return lista.map(function (c) {
        return [nome(c), pc(c.pct[0], 1) + " → " + pc(c.pct[1], 1), pp(c.desvio),
          c.secoes_no_sentido + " de " + c.secoes + " (pior: " + pc(100 * c.pior_secao, 0) + ")", de2022(c)];
      });
    };
    var acha = function (nm) { return f.contra_o_22.filter(function (c) { return c.nm === nm; })[0]; };
    var casos = [];
    var pr = acha("Pracuúba"), pa = acha("Paranhos"), rg = acha("Rafael Godeiro");
    if (pr && pr.em_2022) casos.push("Pracuúba (AP) perde perto de um quarto do comparecimento entre os turnos nas duas eleições (" +
      sinal(pr.em_2022.c[1] - pr.em_2022.c[0]) + " em 2022, " + sinal(pr.c[1] - pr.c[0]) + " em 2026); em 2022 quem mais perdeu foi o Lula (" +
      sinal(pr.em_2022.l[1] - pr.em_2022.l[0]) + "), em 2026 o Flávio (" + sinal(pr.f[1] - pr.f[0]) + ").");
    if (pa) casos.push("Em Paranhos (MS) o comparecimento subiu " + sinal(pa.c[1] - pa.c[0]) + " no 2º turno, puxado pelas seções da aldeia Pirajuí e das escolas rurais: " +
      "o Flávio ficou parado (" + sinal(pa.f[1] - pa.f[0]) + ") e o Lula ganhou " + sinal(pa.l[1] - pa.l[0]) + ".");
    if (rg && rg.em_2022) casos.push("Em Rafael Godeiro (RN) o Flávio caiu em todas as " + rg.secoes + " seções (" + sinal(rg.f[1] - rg.f[0]) + " votos); em 2022 a cidade acompanhou o país, " +
      "com o Lula perdendo " + num(rg.em_2022.l[0] - rg.em_2022.l[1]) + " votos entre os turnos.");
    return [
      p("Silva Jardim não é a mais estranha. A régua: quanto a fatia do candidato do 22 mudou entre os turnos na cidade, menos quanto mudou no país (" +
        pp(f.nacional[0]) + " em 2026, " + pp(f.nacional[1]) + " em 2022). As " + num(f.cidades) + " cidades se espalham do mesmo jeito nas duas eleições: desvio-padrão de " +
        f.dp[0].toLocaleString("pt-BR") + " ponto em 2026 e " + f.dp[1].toLocaleString("pt-BR") + " em 2022."),
      p("Onde o Flávio subiu bem mais que o país: " + f.ufs_favor[0].cidades + " das 50 cidades da ponta ficam em " + f.ufs_favor[0].nome +
        ", terra do Caiado — lá a terceira via foi para o Flávio (o estado inteiro ficou, em média, " + pp(f.goias.desvio_medio) + " acima do país)."),
      tabela(["Cidade", "o 22: 1º → 2º turno", "em relação ao país", "seções em que o 22 subiu", "2022 (em relação ao país)"],
        linhas(f.a_favor_do_22), ["", "num", "num", "num", "num"]),
      p("Onde o Flávio ficou bem abaixo do país: pequenas cidades de " + f.ufs_contra.slice(0, 3).map(function (u) { return u.nome + " (" + u.cidades + " das 50)"; }).join(", ") + "."),
      tabela(["Cidade", "o 22: 1º → 2º turno", "em relação ao país", "seções em que o 22 caiu", "2022 (em relação ao país)"],
        linhas(f.contra_o_22), ["", "num", "num", "num", "num"]),
      p("A coluna das seções é o teste que separa cidade de urna. Nas duas pontas a mudança aparece na maior parte das seções da cidade, e a seção em que o 22 mais mudou " +
        "responde por uma fatia pequena do total (a “pior” entre parênteses). Onde o 22 caiu em menos seções, como em Paranhos, ele ficou parado e o desvio veio de eleitor novo do outro lado. Uma adulteração deixaria a mudança presa a poucas seções; o que aparece é a cidade inteira mudando. " +
        "Em cidade pequena isso tem nome: liderança local que muda de lado entre os turnos, ou comparecimento que despenca ou dispara."),
      casos.length ? p(casos.join(" ")) : null,
    ];
  }

  // ── 1. Silva Jardim e o "10^-468" ───────────────────────────────────────
  function silvaJardim(d) {
    var x = d.silva_jardim, m = x.municipio, t1 = m.t1, t2 = m.t2;
    var bn1 = t1.brancos + t1.nulos, bn2 = t2.brancos + t2.nulos;
    var CURTO = { "ESCRITOR AUGUSTO CURY": "Cury", "RONALDO CAIADO": "Caiado", "RENAN SANTOS": "Renan", "ZEMA": "Zema" };
    var resto = 0, terc = [];
    m.terceira.forEach(function (c) { if (CURTO[c.nm]) terc.push(CURTO[c.nm] + " " + num(c.v)); else resto += c.v; });
    if (resto) terc.push("outros " + num(resto));
    return item("silva-jardim",
      "Em Silva Jardim (RJ), Flávio ganhou 1 voto e Lula 984 entre os turnos: a chance disso é de 10^−468",
      "post no X que pediu a conta ao Grok, republicado no Instagram",
      "o número confere; a conta, não", "parcial", [
        bloco("O que confere", [
          p("Os números do post estão certos. Flávio foi de " + num(t1.flavio) + " para " + num(t2.flavio) +
            " (" + sinal(t2.flavio - t1.flavio) + "), Lula de " + num(t1.lula) + " para " + num(t2.lula) +
            " (" + sinal(t2.lula - t1.lula) + "), e Flávio venceu com " + pc(100 * t2.flavio / t2.validos, 2) + "."),
          tabela(["", "1º turno", "2º turno", "diferença"], [
            ["Comparecimento", num(t1.comp), num(t2.comp), sinal(t2.comp - t1.comp)],
            ["Branco e nulo", num(bn1), num(bn2), sinal(bn2 - bn1)],
            ["Votos válidos", num(t1.validos), num(t2.validos), sinal(t2.validos - t1.validos)],
            ["Lula", num(t1.lula), num(t2.lula), sinal(t2.lula - t1.lula)],
            ["Flávio", num(t1.flavio), num(t2.flavio), sinal(t2.flavio - t1.flavio)],
            ["Terceira via", num(t1.validos - t1.lula - t1.flavio), "—", ""],
          ], ["", "num", "num", "num"]),
          h("p", { class: "ap-acu-leg", text: "Terceira via na cidade: " + terc.join(" · ") + "." })]),
        bloco("Silva Jardim em 2022", (function () {
          var r = d.regua_2022, v = r.municipios.exemplos["rj-59110"], n = r.nacional;
          if (!v) return p("Sem o dado de 2022 para a cidade.");
          return [
            tabela(["Entre o 1º e o 2º turno", "2022 (Bolsonaro)", "2026 (Flávio)"], [
              ["Saldo do candidato do 22", sinal(v.f2 - v.f1), sinal(t2.flavio - t1.flavio)],
              ["Saldo do Lula", sinal(v.l2 - v.l1), sinal(t2.lula - t1.lula)],
              ["Terceira via no 1º turno", num(v.t1), num(t1.validos - t1.lula - t1.flavio)],
              ["O 22 no 2º turno", pc(100 * v.f2 / v.v2, 1), pc(100 * t2.flavio / t2.validos, 1)],
            ], ["", "num", "num"]),
            p("Em 2022 a cidade foi para o outro lado: o Bolsonaro ganhou mais que o Lula entre os turnos (" + sinal(v.f2 - v.f1) + " × " +
              sinal(v.l2 - v.l1) + "), como no país (" + mi(n.flavio2 - n.flavio1) + " × " + mi(n.lula2 - n.lula1) + "). " +
              "A cidade é a mesma, o tamanho da terceira via também; o que mudou foi para onde ela foi. " +
              "Em 2022 o saldo do Bolsonaro foi zero ou negativo em só " + num(r.municipios.f_ganho_ate_zero) + " municípios; em 2026, o do Flávio, em " +
              num(x.flavio_ganho_ate_zero) + ". É a virada nacional da terceira via aparecendo cidade a cidade.")];
        })()),
        bloco("Por que a conta do Grok está errada", h("ul", { class: "ap-conta-lista" },
          h("li", {}, h("b", { text: "“+1” é saldo, não o voto que o Flávio recebeu. " }),
            "O comparecimento CAIU " + num(t1.comp - t2.comp) + " pessoas. Numa cidade onde ele tinha 62% dos votos, o eleitor dele que não voltou " +
            "desconta do que ele ganhou da terceira via. Ganhar 200 e perder 199 dá “+1”."),
          h("li", {}, h("b", { text: "Os 985 votos não são sorteio da cidade. " }),
            "São quase todos os " + num(t1.validos - t1.lula - t1.flavio) + " eleitores da terceira via, e a maior parte deles era de Cury e Caiado — " +
            "os dois cujo eleitor foi majoritariamente para o Lula no país inteiro. Dar a cada um a chance que o Grok usou (66,7% de ir para o Flávio) é supor o contrário."),
          h("li", {}, h("b", { text: "Se a conta valesse, o país estaria cheio de milagres. " }),
            "O ganho líquido do Flávio foi zero ou negativo em " + num(x.flavio_ganho_ate_zero) + " dos " + num(x.municipios) +
            " municípios, e em " + num(x.quase_tudo_lula) + " deles 99% ou mais do saldo ficou com o Lula — " + num(x.quase_tudo_lula_com_flavio_60) +
            " desses com o Flávio vencendo por 60% ou mais."))),
        bloco("Municípios parecidos, onde o Flávio venceu com 60% ou mais",
          tabela(["Município", "Flávio no 2º t.", "saldos 2026 (22 × Lula)", "saldos 2022 (22 × Lula)", "terceira via 2026"],
            x.exemplos.map(function (e) {
              var v = d.regua_2022.municipios.exemplos[e.uf + "-" + e.cd];
              return [e.nm + "/" + e.uf.toUpperCase(), pc(e.f2_pct, 1), sinal(e.d_f) + " × " + sinal(e.d_l),
                v ? sinal(v.f2 - v.f1) + " × " + sinal(v.l2 - v.l1) : "—", num(e.terc)];
            }),
            ["", "num", "num", "num", "num"])),
        bloco("Precisou eleitor do Flávio virar Lula?", (function () {
          var tm = d.troca_minima, el = tm.silva_jardim.eleitorado, terc1 = t1.validos - t1.lula - t1.flavio;
          var faltou = el ? el - t1.comp : null;
          return [
            p("Não. O que o Lula ganhou só pode ter vindo da terceira via, do branco e nulo do 1º turno, de quem não votou no 1º turno — ou de eleitor do Flávio. " +
              "Em Silva Jardim, os " + sinal(t2.lula - t1.lula) + " do Lula cabem nos " + num(terc1) + " da terceira via mais os " + num(bn1) +
              " brancos e nulos do 1º turno, e ainda sobram " + num(terc1 + bn1 - (t2.lula - t1.lula)) +
              (faltou ? " — sem contar os " + num(faltou) + " eleitores da cidade que não votaram no 1º turno" : "") +
              ". A conta fecha sem um único eleitor do Flávio mudando de lado."),
            tabelaTroca(d),
            p("No país inteiro, contando quem faltou no 1º turno, nenhum município exige que um eleitor do Flávio tenha virado Lula — nem, em 2022, que um eleitor do Lula tenha virado Bolsonaro. " +
              "Só sob a hipótese forte de que votou exatamente a mesma gente nos dois turnos aparece troca obrigatória, e mínima, nas duas eleições e nos dois sentidos. " +
              "Mesmo essa pode ser só gente diferente indo votar: alguém que faltou no 1º turno votando no 2º, e vice-versa.")];
        })()),
        bloco("E o Monte Carlo?", (function () {
          var g = d.teste_do_grok;
          return [
            p("Monte Carlo é um jeito legítimo de calcular uma chance: sorteia-se um modelo milhares de vezes. A resposta só vale o que vale o modelo. " +
              "O do post trata os 985 votos como moedas independentes, cada uma com a mesma chance de cair no Flávio. Para ver se esse modelo mede fraude, " +
              "basta aplicá-lo a todas as cidades, e não só à escolhida depois de ver o resultado:"),
            tabela(["Eleição", "cidades avaliadas", "“impossíveis” a favor do Lula", "“impossíveis” a favor do 22"], [
              ["2026", num(g["2026"].avaliados), num(g["2026"].impossivel_a_favor_do_13), num(g["2026"].impossivel_a_favor_do_22)],
              ["2022", num(g["2022"].avaliados), num(g["2022"].impossivel_a_favor_do_13), num(g["2022"].impossivel_a_favor_do_22)],
            ], ["", "num", "num", "num"]),
            h("p", { class: "ap-acu-leg", text: "“Impossível” = chance menor que 1 em 1 milhão pelo modelo do post." }),
            p("O modelo chama de impossível o resultado de " + pc(100 * g["2026"].impossivel_a_favor_do_13 / g["2026"].avaliados, 0) +
              " das cidades em 2026, a favor do Lula, e de " + pc(100 * g["2022"].impossivel_a_favor_do_22 / g["2022"].avaliados, 0) +
              " em 2022, a favor do Bolsonaro: acusa sempre o lado para onde o país virou. O que ele detecta é que o eleitor do 2º turno não é sorteio do " +
              "resultado do 1º — o que todo mundo já sabe. Para dizer se uma cidade é estranha, compara-se com as outras cidades, como no bloco abaixo.")];
        })()),
        bloco("Silva Jardim é estranha?", p("Pela composição da terceira via na cidade, o esperado era o Lula ganhar uns " + num(m.esperado_lula) +
          "; ganhou " + num(t2.lula - t1.lula) + " — " + num(x.residuo_votos) + " a mais (" + pc(x.residuo_pct, 1) + " dos válidos). " +
          "É a ponta da distribuição, mas uma ponta comum: " + num(x.acima) + " municípios vão mais longe nessa direção e " + num(x.do_outro_lado) +
          " vão tão longe quanto na direção contrária (o Lula ganhando MENOS que o esperado). É o espalhamento normal de cidade a cidade.")),
        bloco("Outras cidades fora do padrão", foraDoPadrao(d)),
        bloco("Confira você mesmo", p("A busca “A conta na sua cidade”, mais abaixo, mostra os dois turnos de qualquer município. " +
          "Digite Silva Jardim, Araruama, Boa Vista, Rafael Godeiro ou Hidrolândia.")),
      ]);
  }

  // ── 2. "700 votos no 1º turno e 8 ou 9 no 2º, na mesma seção" ──────────
  function mesmaSecao(d) {
    var x = d.mesma_secao;
    return item("mesma-secao",
      "Flávio fez 700 votos no 1º turno e 8 ou 9 no 2º, na mesma seção",
      "prints em grupos de WhatsApp",
      "não existe nos dados", "falso", [
        bloco("O que o arquivo do TSE mostra", h("ul", { class: "ap-conta-lista" },
          h("li", {}, h("b", { text: "700 votos não cabem numa seção. " }),
            "O máximo que o Flávio teve numa seção foi " + num(x.max_flavio[0]) + " no 1º turno e " + num(x.max_flavio[1]) +
            " no 2º. A seção com mais gente votando teve " + num(x.max_comparecimento[1]) + " eleitores."),
          h("li", {}, h("b", { text: "Nenhuma seção caiu de 100 para 10. " }),
            "Em " + num(x.secoes_nos_dois_turnos) + " seções que existiram nos dois turnos, nenhuma teve o Flávio com 100 votos ou mais no 1º turno e até 10 no 2º."),
          h("li", {}, h("b", { text: "As seções são as mesmas nos dois turnos. " }),
            "Só " + num(x.so_1t) + " seção existiu apenas no 1º turno, e sem voto do Flávio. Não houve junção de seções que explicasse um número sumindo."))),
        bloco("As maiores quedas reais, na mesma seção",
          [tabela(["Seção", "Flávio", "Lula", "comparecimento"],
            x.maiores_quedas.slice(0, 6).map(function (q) {
              return [q.municipio + "/" + q.uf.toUpperCase() + " · zona " + q.zona + ", seção " + q.secao,
                q.flavio[0] + " → " + q.flavio[1], q.lula[0] + " → " + q.lula[1], q.comparecimento[0] + " → " + q.comparecimento[1]];
            }), ["", "num", "num", "num"]),
          p("A maior queda real foi de uns 100 votos, e sempre com o comparecimento caindo junto — seção rural do Acre e do Amazonas em que menos gente voltou para votar. " +
            "Um print com 700 → 8 compara coisas diferentes: o local de votação inteiro com uma seção, outro cargo, ou outra zona com o mesmo número de seção.")]),
        bloco("E troca de lado dentro da seção?", (function () {
          var a26 = d.troca_minima["2026"].secoes_mesma_gente, a22 = d.troca_minima["2022"].secoes_mesma_gente;
          return p("Supondo que votou exatamente a mesma gente nos dois turnos de cada seção, " + num(a26.para_13[0]) + " das " +
            num(d.troca_minima["2026"].secoes) + " seções exigiriam que algum eleitor do Flávio tivesse ido para o Lula: " + num(a26.para_13[1]) +
            " eleitores ao todo, " + pc(100 * a26.para_13[1] / d.nacional.flavio1, 2) + " dos votos do Flávio no 1º turno. Em 2022, no sentido contrário (Lula → Bolsonaro), eram " +
            num(a22.para_22[0]) + " seções e " + num(a22.para_22[1]) + " eleitores. Mudar de voto entre turnos acontece nas duas eleições, nos dois sentidos, sempre em escala mínima — " +
            "e mesmo isso pode ser só troca de quem foi votar.");
        })()),
        bloco("E em 2022?", (function () {
          var r = d.regua_2022.secoes;
          return p("O mesmo padrão: o máximo do Bolsonaro numa seção foi " + num(r.max_f[0]) + " no 1º turno e " + num(r.max_f[1]) +
            " no 2º (as seções de 2022 eram maiores: até " + num(r.max_comparecimento[0]) + " eleitores votando). A maior queda dele de um turno para o outro, " +
            "na mesma seção, foi de " + num(r.maior_queda_f) + " votos, e nenhuma seção caiu de 100 ou mais para até 10.");
        })()),
        bloco("Confira você mesmo", p("Com a zona e a seção do print, o boletim de urna de cada turno está em resultados.tse.jus.br, " +
          "e o arquivo seção a seção (votacao_secao_2026_BR) está nos dados abertos do TSE.")),
      ]);
  }

  // ── 2b. "Repetindo em cada zona o mesmo número" (vídeo de 30/10) ─────────
  // O vídeo filma o app Resultados trocando de zona; a migração diz de que
  // zona é cada número que a tela mostrou (`zonas.video`).
  function zonasRepetidas(d) {
    var x = d.zonas;
    var placar = function (z) { return num(z.l) + " × " + num(z.f); };
    var quem = function (z) { return z.l > z.f ? "o Lula" : "o Flávio"; };
    var tela = x.video.filter(function (v) { return v.onde === "tela" && v.zonas.length > 1; });
    var z8 = x.video.filter(function (v) { return v.onde === "tela" && v.zonas.length === 1; })[0];
    var nove = x.video.filter(function (v) { return v.onde === "papel" && v.dona.zona === 9; })[0];
    var bsb = tela[0], dona = bsb.dona;
    var outras = bsb.zonas.filter(function (z) { return z.zona !== dona.zona; });
    var soma = outras.reduce(function (a, z) { return { l: a.l + z.l, f: a.f + z.f }; }, { l: 0, f: 0 });
    var flavioVenceu = outras.filter(function (z) { return z.f > z.l; }).length;
    var c = x.cidades[bsb.nm];
    var linhas = [];
    tela.forEach(function (v) {
      v.zonas.forEach(function (z) {
        linhas.push([v.nm + " · zona " + z.zona, placar(v.dona), placar(z),
          z.zona === v.dona.zona ? "é desta zona" : "é da zona " + v.dona.zona]);
      });
    });
    return item("zonas",
      "O mesmo número se repete em cada zona: Lula 32.714 e Flávio 29.764 nas zonas de Brasília, e igual em Salvador e São Paulo. Matematicamente isso não existe",
      "vídeo do TikTok gravado na tela do app Resultados do TSE, circulando no WhatsApp em 30/10/2026",
      "o número confere; é de uma zona só", "parcial", [
        bloco("O número é real, e é de uma zona", [
          p("O vídeo tem razão numa coisa: várias zonas com o mesmo placar, voto a voto, não acontecem. E não aconteceram. " +
            num(dona.l) + " votos para o Lula e " + num(dona.f) + " para o Flávio é o resultado da zona " + dona.zona + " de " + bsb.nm +
            " (" + num(dona.secoes) + " seções), e só dela. Cada número que o vídeo mostra confere com UMA zona: " +
            tela.slice(1).map(function (v) { return "o de " + v.nm + " é a zona " + v.dona.zona; }).join(", ") + "."),
          tabela(["Zona aberta no vídeo", "a tela mostrou (Lula × Flávio)", "o resultado desta zona", "o número da tela"],
            linhas, ["", "num", "num", ""]),
          p("Em toda sequência do vídeo a tela começa certa e depois para: o topo troca o nome da zona, e os números ficam presos numa zona aberta antes. " +
            (z8 ? "Em " + z8.nm + ", a primeira zona aberta, a " + z8.dona.zona + ", aparece com o número dela (" + placar(z8.dona) + "). " : "") +
            "No meio do vídeo a própria autora diz que o app “está demorando um pouquinho”.")]),
        nove ? bloco("A mesma zona, dois números", p("No começo do vídeo, a autora mostra uma folha com o que anotou antes de gravar. Lá, a zona 9 de " + nove.nm +
          " está com " + placar(nove.dona) + ", o resultado real dela, e as zonas " + nove.zonas.slice(1).map(function (z) { return z.zona; }).join(" e ") +
          " repetem esse número. No vídeo, a mesma zona 9 aparece com " + placar(dona) + ", o da zona " + dona.zona +
          ". Se o número estivesse gravado no resultado, a zona 9 teria um só. Tem dois, e cada um é o da zona aberta antes dela: quem leva o número de uma zona para a outra é a tela, não a urna.")) : null,
        bloco("No país inteiro, nenhuma zona repete outra", p("O arquivo seção a seção do 2º turno tem " + num(x.zonas_pais) +
          " zonas (cada par de município e zona). " + (x.placares_repetidos ? num(x.placares_repetidos) + " placares aparecem mais de uma vez." :
          "Nenhum placar do Lula e do Flávio aparece duas vezes, nem entre cidades diferentes.") + " Nas " + num(x.cidades_varias_zonas) +
          " cidades com mais de uma zona (" + num(x.zonas_nessas_cidades) + " zonas ao todo), nenhuma tem duas zonas com o mesmo número.")),
        bloco("Se a tela fosse o resultado, ganharia o Lula", p("Nas " + outras.length + " zonas de " + bsb.nm + " que aparecem repetidas (" +
          outras.map(function (z) { return z.zona; }).join(", ") + "), o número da tela dá o Lula na frente, com " + pc(100 * dona.l / (dona.l + dona.f), 1) +
          ". No resultado, o Flávio venceu em " + (flavioVenceu === outras.length ? "todas as " + outras.length : num(flavioVenceu)) +
          ", e o Lula teve " + pc(100 * soma.l / (soma.l + soma.f), 1) + " delas. A tela parada também não puxa sempre para o mesmo lado: o número que ficou preso em " +
          tela.slice(1).map(function (v) { return v.nm + " é de uma zona em que venceu " + quem(v.dona); }).join("; em ") + ". " +
          "As " + c.zonas + " zonas de " + bsb.nm + " somam " + num(c.l) + " votos para o Lula e " + num(c.f) + " para o Flávio, o total que o próprio app mostra em “Zona: Todas”.")),
        bloco("Confira você mesmo", p("Abra a zona " + outras[0].zona + " de " + bsb.nm + " direto, sem passar pela " + dona.zona +
          ", ou pelo navegador em resultados.tse.jus.br: o número dela é " + placar(outras[0]) + " (Lula × Flávio). " +
          "Se o app parecer parado, feche e abra de novo entre uma zona e outra. O boletim de urna de cada seção está no mesmo site, e o arquivo " +
          "votacao_secao_2026_BR (dados abertos do TSE) traz o voto de cada seção, com a zona.")),
      ]);
  }

  // ── 3. "3.042 seções com Flávio até 10 votos" ───────────────────────────
  // Séries lado a lado, de 0 a 10 votos: [{v: [11 números], rot, classe}].
  function barras(series, rotulo) {
    var max = Math.max.apply(null, [].concat.apply([], series.map(function (x) { return x.v; }))) || 1;
    return h("div", { class: "ap-acu-barras", role: "img", "aria-label": rotulo },
      h("div", { class: "ap-acu-barras-leg" }, series.map(function (x) { return h("span", { class: x.classe, text: x.rot }); })),
      series[0].v.map(function (_, i) {
        return h("div", { class: "ap-acu-barra-linha" },
          h("span", { class: "rot", text: i + (i === 1 ? " voto" : " votos") }),
          h("span", { class: "par" }, series.map(function (x) {
            return h("span", { class: x.classe, vars: { "--p": (100 * x.v[i] / max) + "%" } }, h("i", { text: num(x.v[i]) }));
          })));
      }));
  }
  function secoesAte10(d) {
    var x = d.secoes_ate_10, f2 = x.flavio_2t, f1 = x.flavio_1t, l2 = x.lula_2t, T = x.total;
    var pctL = function (s, t) { return pc(100 * s["l" + t] / (s["l" + t] + s["f" + t] + (t === 1 ? s.t1 : 0)), 1); };
    var linhas = x.faixas_2t.map(function (fx) {
      return [fx.voto + (fx.voto === 1 ? " voto" : " votos"), num(fx.secoes), num(fx.l1), num(fx.l2), num(fx.f1)];
    });
    linhas.push(["Total", num(T.secoes), num(T.l1), num(T.l2), num(T.f1)]);
    return item("secoes-10",
      "Em " + num(f2.secoes) + " seções Flávio fez no máximo 10 votos e Lula somou " + num(Math.round(f2.outro_somou / 1000)) + " mil; em " + f2.zeradas + " urnas ele teve zero",
      "post republicado pelo Jornal da Cidade Online e levantamento divulgado pela Folha",
      "o número confere; não é do 2º turno", "parcial", [
        bloco("O que confere", p("Os números estão certos: " + num(f2.secoes) + " seções com o Flávio entre 0 e 10 votos no 2º turno, " +
          num(f2.outro_somou) + " votos do Lula nelas, e " + f2.zeradas + " seções com o Flávio zerado (" + num(f2.outro_nas_zeradas) + " votos do Lula). " +
          "A contagem de 0 a 10 do post bate seção por seção.")),
        bloco("O voto do Lula nessas mesmas seções, nos dois turnos", [
          tabela(["Flávio no 2º turno", "seções", "Lula no 1º turno", "Lula no 2º turno", "Flávio no 1º turno"], linhas,
            ["", "num", "num", "num", "num"]),
          p("São as mesmas seções nas duas colunas do Lula. Em 04/10, quando o Flávio terminou na frente no país, elas já deram ao Lula " +
            num(T.l1) + " votos (" + pctL(T, 1) + " dos válidos); em 25/10, " + num(T.l2) + " (" + pctL(T, 2) + "). " +
            "Nas " + f2.zeradas + " zeradas, o Flávio tinha " + num(x.faixas_2t[0].f1) + " votos somados no 1º turno — um por seção, em média."),
          p("O Lula ganhou " + num(T.l2 - T.l1) + " votos nelas, e o Flávio perdeu " + num(T.f1 - T.f2) + ". Para onde foi a terceira via dali (" +
            num(T.t1) + " votos) e o branco e nulo que caiu (" + num(T.bn1 - T.bn2) + "), com o mesmo número de eleitores votando (" +
            sinal(T.c2 - T.c1) + "): a conta fecha no voto.")]),
        bloco("O 1º turno já tinha o mesmo desenho", [
          barras([{ v: d.regua_2022.secoes.f_ate_10.por_voto_2t, rot: "2022, 2º turno (Bolsonaro)", classe: "c" },
                  { v: f1.por_voto, rot: "2026, 1º turno", classe: "a" },
                  { v: f2.por_voto, rot: "2026, 2º turno", classe: "b" }],
            "Seções por número de votos do candidato do 22, de 0 a 10: 2º turno de 2022, 1º e 2º turno de 2026"),
          p("No 1º turno já havia " + num(f1.secoes) + " seções com o Flávio até 10 votos (" + f1.zeradas + " zeradas). " +
            "Das " + num(f2.secoes) + " do 2º turno, " + num(x.ja_eram.secoes) + " já tinham o Flávio até 10 votos em 04/10. " +
            "As outras " + num(x.entraram.secoes) + " entraram na lista porque ele caiu de pouco mais de 10 para 10 ou menos: perdeu " +
            num(x.entraram.f1 - x.entraram.f2) + " votos nelas, enquanto o comparecimento ali caiu " + num(x.entraram.c1 - x.entraram.c2) +
            ". É eleitor dele que não voltou para votar, não voto trocado.")]),
        bloco("E em 2022?", (function () {
          var r = d.regua_2022.secoes.f_ate_10, l22 = d.regua_2022.secoes.lula_ate_10;
          return p("Havia mais. No 2º turno de 2022 o Bolsonaro teve até 10 votos em " + num(r.t2) + " seções (" + r.zeradas[1] + " zeradas), com " +
            num(r.lula_nelas[1]) + " votos do Lula nelas; no 1º turno de 2022 eram " + num(r.t1) + " (" + r.zeradas[0] + " zeradas). " +
            "Os estados são os mesmos: " + r.ufs.map(function (u) { return u.nome + " " + num(u.secoes); }).join(" · ") + ". " +
            "E o espelho também: seções com o Lula até 10 votos foram " + num(l22[1]) + " no 2º turno de 2022. " +
            "A seção renumera de uma eleição para outra, então a comparação é do padrão, não da mesma seção.");
        })()),
        bloco("Que seções são essas", p("Seções pequenas: " + num(x.comparecimento_medio[0]) + " eleitores votando em média, contra " +
          num(x.comparecimento_medio[1]) + " no país. " + num(x.local_rural[0]) + " delas (" + pc(100 * x.local_rural[0] / x.local_rural[1], 0) +
          ") ficam em local cujo nome diz aldeia, povoado, assentamento, comunidade ou zona rural — no país inteiro são " +
          pc(100 * x.local_rural_pais[0] / x.local_rural_pais[1], 1) + ". Das " + x.zeradas_em_aldeia[1] + " zeradas, " + x.zeradas_em_aldeia[0] +
          " são em aldeia indígena. Por estado: " + x.ufs.map(function (u) { return u.nome + " " + num(u.secoes); }).join(" · ") + ".")),
        bloco("Precisou eleitor do Flávio virar Lula nelas?", (function () {
          var tm = d.troca_minima.secoes_ate_10.secoes_mesma_gente;
          return p("No conjunto delas, não: o Lula ganhou " + num(T.l2 - T.l1) + " votos, e havia " + num(T.t1) + " votos da terceira via e " +
            num(T.bn1) + " brancos e nulos do 1º turno nessas mesmas seções. Seção por seção, e supondo que votou exatamente a mesma gente nos dois turnos, " +
            num(tm.para_13[0]) + " das " + num(f2.secoes) + " exigiriam alguma troca do Flávio para o Lula — " + num(tm.para_13[1]) + " eleitores somados.");
        })()),
        bloco("O peso delas no resultado", p("Se as " + num(f2.secoes) + " seções fossem anuladas inteiras, a vantagem do Lula cairia de " +
          num(x.margem) + " para " + num(x.margem_sem_elas) + " votos. O resultado não depende delas.")),
        bloco("E o espelho?", p("Seções com o Lula até 10 votos no 2º turno: " + num(l2.secoes) + " (" + l2.zeradas + " zeradas). " +
          "São menos porque o voto do Flávio é mais espalhado entre cidades grandes e médias, e o do Lula se concentra em lugares muito homogêneos. " +
          "Essa assimetria também já estava no 1º turno (" + num(x.lula_1t.secoes) + " seções com o Lula até 10).")),
        bloco("Confira você mesmo", p("No arquivo votacao_secao_2026_BR do TSE, filtre NR_VOTAVEL = 22 e conte as seções com QT_VOTOS até 10 em cada turno; " +
          "depois some o NR_VOTAVEL = 13 dessas mesmas seções (UF, município, zona e seção) no 1º e no 2º turno.")),
      ]);
  }

  // ── 4. "a curva da apuração tem um padrão" ──────────────────────────────
  function graficoCurva(c) {
    var W = 640, H = 260, mE = 40, mD = 24, mT = 12, mB = 30, y0 = 35, y1 = 55;
    var X = function (v) { return mE + (W - mE - mD) * v / 100; };
    var Y = function (v) { return mT + (H - mT - mB) * (y1 - v) / (y1 - y0); };
    var linha = function (pts) { return pts.map(function (q, i) { return (i ? "L" : "M") + X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1); }).join(" "); };
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, class: "ap-acu-curva", role: "img",
      "aria-label": "Participação do Lula ao longo da contagem: a noite real, oito ordens sorteadas e a ordem por região" });
    [35, 40, 45, 50, 55].forEach(function (v) {
      svg.appendChild(s("line", { x1: mE, x2: W - mD, y1: Y(v), y2: Y(v), class: "grade" }));
      svg.appendChild(s("text", { x: mE - 6, y: Y(v) + 4, "text-anchor": "end", class: "eixo", text: v + "%" }));
    });
    [0, 25, 50, 75, 100].forEach(function (v) {
      svg.appendChild(s("text", { x: X(v), y: H - 10, "text-anchor": "middle", class: "eixo", text: v + "%" }));
    });
    svg.appendChild(s("line", { x1: mE, x2: W - mD, y1: Y(c.final), y2: Y(c.final), class: "final" }));
    c.sorteadas.forEach(function (pts) { svg.appendChild(s("path", { d: linha(pts), class: "sorteio" })); });
    svg.appendChild(s("path", { d: linha(c.por_regiao), class: "regiao" }));
    svg.appendChild(s("path", { d: linha(c.noite), class: "noite" }));
    svg.appendChild(s("text", { x: X(100) - 4, y: Y(c.final) - 6, "text-anchor": "end", class: "eixo", text: "final: " + pc(c.final, 2) }));
    return svg;
  }
  // A noite real, em uma frase: onde começou, se o Flávio passou à frente, o
  // ponto mais baixo do Lula e quando ele voltou à frente. Calculado da série,
  // para o texto nunca contar uma noite diferente da do gráfico.
  function noiteTexto(c) {
    var n = c.noite, ini = n[0], fim = n[n.length - 1];
    var min = n.reduce(function (a, b) { return b[1] < a[1] ? b : a; }, ini);
    var txt = "Na noite de 25/10 o Lula tinha " + pc(ini[1], 1) + " com " + pc(ini[0], 0) + " apurado";
    if (min[1] < 50) {
      var cai = n.filter(function (x) { return x[1] < 50; })[0];
      var volta = n.filter(function (x) { return x[0] > min[0] && x[1] >= 50; })[0];
      txt += ". O Flávio passou à frente com " + pc(cai[0], 0) + " apurado, o Lula chegou a " + pc(min[1], 2) +
        " com " + pc(min[0], 0) + ", e voltou à frente com " + pc(volta ? volta[0] : fim[0], 0) + " apurado";
    }
    return txt + ", terminando com " + pc(fim[1], 2) + ". Também houve uma virada durante a contagem.";
  }

  // Gráfico de linha genérico: eixos, faixas sombreadas, linhas de referência.
  // o = {W, H, x: [x0, x1], y: [y0, y1], tx: [ticks], ty: [ticks], fx, fy,
  //      series: [{pts, classe}], faixas: [{de, ate, classe}], refs: [{y, rot}],
  //      marcas: [{x, rot}], rotulo}
  function grafico(o) {
    var W = o.W || 640, H = o.H || 240, mE = 52, mD = 24, mT = 12, mB = 28;
    var X = function (v) { return mE + (W - mE - mD) * (v - o.x[0]) / (o.x[1] - o.x[0]); };
    var Y = function (v) { return mT + (H - mT - mB) * (o.y[1] - v) / (o.y[1] - o.y[0]); };
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, class: "ap-acu-curva", role: "img", "aria-label": o.rotulo });
    (o.faixas || []).forEach(function (f) {
      svg.appendChild(s("rect", { x: X(f.de), y: mT, width: Math.max(1.5, X(f.ate) - X(f.de)), height: H - mT - mB, class: f.classe }));
    });
    o.ty.forEach(function (v) {
      svg.appendChild(s("line", { x1: mE, x2: W - mD, y1: Y(v), y2: Y(v), class: "grade" }));
      svg.appendChild(s("text", { x: mE - 6, y: Y(v) + 4, "text-anchor": "end", class: "eixo", text: o.fy(v) }));
    });
    o.tx.forEach(function (v) {
      svg.appendChild(s("text", { x: X(v), y: H - 9, "text-anchor": "middle", class: "eixo", text: o.fx(v) }));
    });
    (o.refs || []).forEach(function (r) {
      svg.appendChild(s("line", { x1: mE, x2: W - mD, y1: Y(r.y), y2: Y(r.y), class: "final" }));
      // rótulo à esquerda: no fim a curva encosta na linha do resultado final
      if (r.rot) svg.appendChild(s("text", { x: mE + 6, y: Y(r.y) + 14, "text-anchor": "start", class: "eixo", text: r.rot }));
    });
    o.series.forEach(function (sr) {
      svg.appendChild(s("path", { class: sr.classe, d: sr.pts.map(function (q, k) {
        return (k ? "L" : "M") + X(q[0]).toFixed(1) + "," + Y(Math.max(o.y[0], Math.min(o.y[1], q[1]))).toFixed(1);
      }).join(" ") }));
    });
    (o.marcas || []).forEach(function (m) {
      svg.appendChild(s("line", { x1: X(m.x), x2: X(m.x), y1: mT, y2: H - mB, class: "marca" }));
      svg.appendChild(s("text", { x: X(m.x) + 4, y: mT + 12, class: "eixo marca-rot", text: m.rot }));
    });
    return svg;
  }

  function curva(d) {
    var c = d.curva, r = d.regua_2022, n = r.noite, j = n.janela, t26 = d.trocas_2026, t22 = r.trocas;
    var pctDe = function (x) { return 100 * x / n.secoes; };
    var vira = n.trocas.length ? n.trocas[n.trocas.length - 1] : null;
    var lin = function (l) { return [l.hora, (l.variacao_pp > 0 ? "+" : "−") + Math.abs(l.variacao_pp).toLocaleString("pt-BR", { maximumFractionDigits: 3 }) + " p.p.",
      pc(l.bolsonaro_no_lote, 1), l.lugares.join(", ")]; };
    var noite22 = grafico({
      W: 640, H: 250, x: [0, 100], y: [44, 60], tx: [0, 25, 50, 75, 100], ty: [44, 48, 52, 56, 60],
      fx: function (v) { return v + "%"; }, fy: function (v) { return v + "%"; },
      faixas: [{ de: pctDe(j.de), ate: pctDe(j.ate), classe: "janela" }],
      refs: [{ y: 50 }, { y: n.final, rot: "final do Bolsonaro: " + pc(n.final, 2) }],
      marcas: vira ? [{ x: vira.pct, rot: vira.hora + ": Lula passa à frente" }] : [],
      series: [{ pts: n.curva, classe: "bolso" }],
      rotulo: "Fatia acumulada do Bolsonaro na ordem real de chegada dos boletins de 2022, com a janela do vídeo marcada" });
    var zoom = grafico({
      W: 640, H: 230, x: [j.de, j.ate], y: [0.514, 0.518], tx: [70000, 75000, 80000, 85000], ty: [0.514, 0.515, 0.516, 0.517, 0.518],
      fx: function (v) { return (v / 1000) + "k"; }, fy: function (v) { return v.toFixed(3); },
      faixas: n.quedas.map(function (q) { return { de: q.de, ate: q.ate, classe: "queda" }; })
        .concat(n.subidas.map(function (q) { return { de: q.de, ate: q.ate, classe: "subida" }; })),
      series: [{ pts: j.zoom, classe: "bolso" }],
      rotulo: "O trecho do vídeo, entre o boletim 70 mil e o 85 mil, na escala do vídeo" });
    return item("curva",
      "Um algoritmo derrubava o Bolsonaro de tempos em tempos durante a apuração; sem ele, teria de 60% a 65%",
      "vídeo de um professor sobre 2022, republicado pelo Vitória News em 28/10/2026 como se fosse sobre o Flávio",
      "é de 2022 e não se sustenta", "falso", [
        bloco("O vídeo é sobre 2022", p("No vídeo, o professor fala do Bolsonaro, diz que ele “teria ganhado as eleições com 60 a 65%” e que “fomos roubados em 2022”; " +
          "sobre 2026 diz só que “estamos sendo roubados novamente”, sem mostrar dado. As “472 urnas” do vídeo são as " + num(n.secoes) +
          " seções do 2º turno de 2022. Foi a legenda do post de 2026 que pôs o 60–65% no Flávio.")),
        bloco("O gráfico dele, refeito com os boletins de 2022", [
          noite22,
          h("div", { class: "ap-acu-curva-leg" },
            h("span", { class: "bolso", text: "fatia acumulada do Bolsonaro, boletim a boletim, na ordem em que chegaram ao TSE" }),
            h("span", { class: "janela", text: "o trecho do vídeo" })),
          zoom,
          h("div", { class: "ap-acu-curva-leg" },
            h("span", { class: "queda", text: "as 3 maiores “penalizações” do trecho" }),
            h("span", { class: "subida", text: "as 3 maiores subidas" })),
          p("Cada boletim de urna de 2022 traz a hora em que chegou ao TSE. Com os " + num(n.secoes) + " boletins do 2º turno nessa ordem " +
            "(os 28 arquivos com o SHA-512 conferido, e a soma batendo com o resultado oficial), entre o boletim 70 mil e o 85 mil — das " +
            j.hora[0] + " às " + j.hora[1] + " de 30/10/2022 — a fatia do Bolsonaro fica entre " + pc(100 * j.min, 2) + " e " + pc(100 * j.max, 2) +
            ": é o gráfico do vídeo. A altura inteira desse zoom é de 0,4 ponto percentual.")]),
        bloco("Cada “penalização” tem hora e lugar", [
          tabela(["hora", "efeito na curva", "Bolsonaro no lote", "de onde vieram os boletins"],
            n.quedas.map(lin).concat(n.subidas.map(lin)), ["", "num", "num", ""]),
          p("Cada linha é um lote de 400 boletins seguidos. Quando o lote dá ao Bolsonaro menos que a média acumulada até ali (perto de 51,6%), a curva desce; " +
            "quando dá mais, sobe. A maior “penalização” do trecho tirou " + Math.abs(n.quedas[0].variacao_pp).toLocaleString("pt-BR") +
            " ponto dele, com boletins de " + n.quedas[0].lugares.join(", ") + " — seções que existem, com número, e que qualquer um confere.")]),
        bloco("“Só uma inversão” não é sinal de nada", p("Com as mesmas seções de 2022 em ordem sorteada, a liderança troca de mão em média " + t22.trocas_mediana +
          " vezes, mas todas antes de " + pc(t22.ultima_troca_max, 1) + " das seções contadas; depois disso o Lula fica na frente até o fim. " +
          "O professor está certo que a ordem sorteada tem mais trocas, e errado ao supor que a apuração chega em ordem sorteada: os boletins chegam por região e por fuso. " +
          "Os primeiros 20% de 2022 vieram sobretudo de " + n.ufs_inicio.map(function (u) { return u.nome; }).join(", ") +
          "; o que chegou depois da virada (" + (vira ? vira.hora + ", com " + pc(vira.pct, 1) + " contado" : "") + "), de " +
          n.ufs_fim.map(function (u) { return u.nome; }).join(", ") + ". Uma soma que chega em blocos assim cruza o resultado final poucas vezes — às vezes uma só.")),
        bloco("Recortar e colar fabrica qualquer vencedor", [
          tabela(["tamanho do recorte", "só os trechos em que o Bolsonaro sobe", "só os trechos em que ele cai"],
            n.recorte.map(function (x) { return [x.tamanho === 1 ? "boletim a boletim" : "lotes de " + x.tamanho, "Bolsonaro " + pc(x.bolsonaro_so_subidas, 1), "Lula " + pc(x.lula_so_quedas, 1)]; }),
            ["", "num", "num"]),
          p("O vídeo propõe tirar os trechos em que o Bolsonaro cai e colar os que ele sobe. Boletim a boletim, isso dá a ele " + pc(n.recorte[0].bolsonaro_so_subidas, 1) +
            " — o número do vídeo. O mesmo recorte do outro lado dá ao Lula " + pc(n.recorte[0].lula_so_quedas, 1) + ". Tirar os trechos de queda é tirar as seções em que o outro foi melhor; " +
            "o recorte escolhe o vencedor, e o tamanho do recorte escolhe a margem.")]),
        bloco("E em 2026?", [
          graficoCurva(c),
          h("div", { class: "ap-acu-curva-leg" },
            h("span", { class: "noite", text: "a noite de 25/10 (% do Lula × % apurado)" }),
            h("span", { class: "sorteio", text: "as seções de 2026 em 8 ordens sorteadas" }),
            h("span", { class: "regiao", text: "as mesmas seções do Sul para o Nordeste" })),
          p(noiteTexto(c) + " Em ordem sorteada, as seções de 2026 trocam a liderança em média " + t26.trocas_mediana + " vezes, todas antes de " +
            pc(t26.ultima_troca_max, 1) + " contado; do Sul para o Nordeste, o Lula começa com " + pc(c.por_regiao[0][1], 1) + " e vira no fim."),
          p("Os boletins de 2026 com a hora de chegada ainda não saíram nos dados abertos do TSE; quando saírem, a noite de 2026 se refaz do mesmo jeito.")]),
        bloco("Confira você mesmo", p("Os boletins de urna de 2022 estão em dadosabertos.tse.jus.br (conjunto “resultados-2022-boletim-de-urna”). " +
          "Ordene as seções pela coluna DT_BU_RECEBIDO, some os votos do 13 e do 22 e desenhe a fração acumulada.")),
      ]);
  }

  // ── montar ──────────────────────────────────────────────────────────────
  function preencher() {
    if (!corpo) return;
    corpo.textContent = "";
    if (!dados) {
      corpo.appendChild(h("p", { class: "ap-carregando", text: erro ? "Não consegui abrir as checagens agora. Recarregue a página." : "Abrindo as checagens…" }));
      return;
    }
    [silvaJardim, mesmaSecao, zonasRepetidas, secoesAte10, curva].forEach(function (f) {
      try { corpo.appendChild(f(dados)); } catch (e) { /* um bloco quebrado não derruba os outros */ }
    });
  }

  function cartaoAcusacoes() {
    corpo = h("div", { class: "ap-acu-lista" });
    preencher();
    carregar();
    return cartao("As acusações, uma por uma",
      "O que circulou depois do 2º turno, conferido no arquivo seção a seção do TSE (499 mil seções, os dois turnos). " +
      "Quando o número de uma acusação confere, a página diz que confere — o que muda é o que ele significa.",
      corpo,
      h("p", { class: "ap-conta-fonte" }, "Fonte: votacao_secao_2026_BR (dados abertos do TSE), somada e conferida com o resultado oficial. Checagens citadas: ",
        h("a", { href: "https://www.agencialupa.org/checagem/2026/10/28/apos-fuga-do-brasil-flavio-bolsonaro-mente-sobre-eleicoes-em-carta-com-teor-golpista/", target: "_blank", rel: "noopener", text: "Lupa" }),
        " e ",
        h("a", { href: "https://www.poder360.com.br/poder-eleicoes-2026/flavio-usa-teoria-imprecisa-para-chamar-vitoria-de-lula-de-fraude/", target: "_blank", rel: "noopener", text: "Poder360" }),
        "."));
  }

  function iniciar(APx) { AP = APx; h = AP.h; s = AP.s; num = AP.num; cartao = AP.cartao; }

  window.AP_BLOCOS = window.AP_BLOCOS || {};
  window.AP_BLOCOS.iniciar_acusacoes = iniciar;
  window.AP_BLOCOS.acusacoes = cartaoAcusacoes;
})();
