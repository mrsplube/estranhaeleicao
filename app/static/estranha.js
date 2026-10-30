/* estranhaeleicao.org — página de entrada (30/10/2026).
 *
 * Lê /apuracao/explicacao/acusacoes.json (~43 KB, gerado por
 * tools/migracoes/2026-10-29-acusacoes-2t.py). Cada caso mostra a teoria e quem
 * postou; a resposta abre num clique. Todo número vem desse arquivo; o texto
 * longo de cada caso continua em /apuracao/detalhe (static/apuracao_acusacoes.js).
 * O chute do 2º turno mora em /apuracao (static/chute.js).
 */
(function () {
  "use strict";

  var VERSAO = (document.currentScript && document.currentScript.dataset.versao) || "";
  var BASE = "/apuracao/explicacao/";

  // ── utilidades ─────────────────────────────────────────────────────────
  function h(tag, attrs) {
    var el = document.createElement(tag);
    for (var k in (attrs || {})) {
      var v = attrs[k];
      if (v == null || v === false) continue;
      if (k === "text") el.textContent = v;
      else if (k === "html") el.innerHTML = v;
      else if (k === "class") el.className = v;
      else if (k === "style") el.style.cssText = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v);
    }
    for (var i = 2; i < arguments.length; i++) anexar(el, arguments[i]);
    return el;
  }
  function anexar(el, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) c.forEach(function (x) { anexar(el, x); });
    else el.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
  }
  var SVG = "http://www.w3.org/2000/svg";
  function s(tag, attrs) {
    var el = document.createElementNS(SVG, tag);
    for (var k in (attrs || {})) {
      if (k === "text") el.textContent = attrs[k];
      else el.setAttribute(k, attrs[k]);
    }
    return el;
  }
  function num(x) { return Math.round(x).toLocaleString("pt-BR"); }
  function pc(x, c) {
    c = c === undefined ? 1 : c;
    return x.toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c }) + "%";
  }
  function sinal(x) { return (x > 0 ? "+" : x < 0 ? "−" : "") + num(Math.abs(x)); }
  function mi(x) { return (x / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " mi"; }
  function pedir(arquivo) {
    return fetch(BASE + arquivo + (VERSAO ? "?v=" + encodeURIComponent(VERSAO) : ""))
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  }
  // ── peças de um caso ───────────────────────────────────────────────────
  // o = {id, n, alegacao, fontes: [{rot, url?}], veredito, tom, pontos: [..], visual, mais: [{rot, corpo, classe}]}
  function caso(o) {
    var art = h("article", { class: "caso", id: "caso-" + o.id });
    var abrir = h("button", { class: "btn btn-pri caso-abrir", type: "button", "aria-expanded": "false",
      text: "É estranho mesmo? Ver a resposta", onclick: function () {
        var aberto = art.classList.toggle("respondido");
        abrir.setAttribute("aria-expanded", String(aberto));
        abrir.textContent = aberto ? "Fechar a resposta" : "É estranho mesmo? Ver a resposta";
        abrir.classList.toggle("btn-pri", !aberto);
      } });
    anexar(art, [
      h("div", { class: "caso-topo" }, h("span", { text: "Caso " + o.n }), h("span", { class: "veredito-mini " + o.tom, text: o.selo })),
      h("p", { class: "caso-rot", text: "A teoria" }),
      h("blockquote", { class: "alegacao", text: o.alegacao }),
      h("div", { class: "fontes" }, h("span", { class: "fontes-rot", text: "Quem afirmou:" }), o.fontes.map(function (f) {
        return f.url ? h("a", { class: "fonte", href: f.url, target: "_blank", rel: "noopener nofollow", text: f.rot })
          : h("span", { class: "fonte", text: f.rot });
      })),
      abrir,
      h("div", { class: "revela" }, h("div", {},
        h("p", { class: "caso-rot", text: "A resposta" }),
        h("span", { class: "veredito " + o.tom, text: o.veredito }),
        h("ul", { class: "pontos" }, o.pontos.map(function (p) { return h("li", { html: p }); })),
        o.visual,
        (o.mais || []).map(function (m) {
          return h("details", { class: "mais " + (m.classe || "") }, h("summary", { text: m.rot }), h("div", { class: "corpo" }, m.corpo));
        }))),
    ]);
    return art;
  }
  function visual(titulo, conteudo, leg) {
    return h("div", { class: "visual" }, titulo ? h("h4", { text: titulo }) : null, conteudo, leg ? h("p", { class: "leg", text: leg }) : null);
  }
  function p(html) { return h("p", { html: html }); }
  function numero(valor, rot, classe) { return h("div", { class: "numero " + (classe || "") }, h("b", { text: valor }), h("span", { text: rot })); }

  // ── caso 1: Silva Jardim ───────────────────────────────────────────────
  function silvaJardim(d) {
    var x = d.silva_jardim, m = x.municipio, t1 = m.t1, t2 = m.t2, g = d.teste_do_grok;
    var terc = t1.validos - t1.lula - t1.flavio, bn1 = t1.brancos + t1.nulos;
    var cury = 0, caiado = 0;
    m.terceira.forEach(function (c) { if (/CURY/.test(c.nm)) cury = c.v; if (/CAIADO/.test(c.nm)) caiado = c.v; });
    var cidades = h("div", { class: "cidades" }, x.exemplos.map(function (e) {
      return h("div", { class: "cid" },
        h("div", { class: "cid-nome" }, e.nm + " ", h("small", { text: e.uf.toUpperCase() })),
        h("div", { class: "cid-pct" }, pc(e.f2_pct, 1), h("small", { text: " Flávio" })),
        h("div", { class: "cid-saldo" }, h("span", { class: "f", text: "Flávio " + sinal(e.d_f) }), " · ", h("span", { class: "l", text: "Lula " + sinal(e.d_l) })));
    }));
    var pct = function (a, b) { return pc(100 * a / b, 0); };
    return caso({
      id: "silva-jardim", n: 1,
      alegacao: "Em Silva Jardim (RJ), Flávio ganhou 1 voto e Lula " + num(t2.lula - t1.lula) + " entre os turnos. A chance disso é de 1 em 10⁴⁶⁸.",
      fontes: [{ rot: "Post no X", url: "https://x.com/lucascrvg_20/status/2115159021606891820" },
               { rot: "a conta foi pedida ao Grok e republicada no Instagram" }],
      veredito: "O número confere. A conta, não.", tom: "parcial", selo: "tem explicação",
      pontos: [
        "<b>“+1” é saldo, não o voto que ele recebeu.</b> " + num(t1.comp - t2.comp) + " pessoas a menos foram votar no 2º turno. Eleitor do Flávio que não voltou desconta do que ele ganhou: ganhar 200 e perder 199 dá +1.",
        "<b>Os votos do Lula vieram da terceira via.</b> Eram " + num(terc) + " votos, " + num(cury + caiado) + " deles de Cury e Caiado, cujo eleitor foi mais para o Lula no país todo. Somando os " + num(bn1) + " brancos e nulos do 1º turno, a conta fecha sem nenhum eleitor do Flávio virar Lula.",
        "<b>Silva Jardim não é exceção.</b> Em " + num(x.flavio_ganho_ate_zero) + " cidades o Flávio ganhou 0 ou menos entre os turnos, e em " + num(x.quase_tudo_lula_com_flavio_60) + " delas ele venceu com 60% ou mais, como lá. Em 2022 o mesmo aconteceu com o Bolsonaro em " + num(d.regua_2022.municipios.f_ganho_ate_zero) + ".",
      ],
      visual: visual("Municípios parecidos, onde o Flávio venceu com 60% ou mais", cidades,
        "Saldo de cada um entre o 1º e o 2º turno. O mesmo desenho de Silva Jardim, de Roraima ao Rio."),
      mais: [{
        rot: "Adendo: e o Monte Carlo?", classe: "adendo",
        corpo: [
          p("Monte Carlo é um método legítimo: sorteia-se um modelo milhares de vezes. Mas a resposta só vale o que vale o modelo, e o do post trata cada um dos 985 votos como uma moeda com 2/3 de chance de cair no Flávio."),
          p("Aplicando o mesmo modelo a <b>todas</b> as cidades, e não só à escolhida depois de ver o resultado:"),
          h("div", { class: "numeros" },
            numero(pct(g["2026"].impossivel_a_favor_do_13, g["2026"].avaliados), "das cidades em 2026 seriam “impossíveis” a favor do Lula", "l"),
            numero(pct(g["2022"].impossivel_a_favor_do_22, g["2022"].avaliados), "das cidades em 2022 seriam “impossíveis” a favor do Bolsonaro", "f")),
          p("O modelo acusa sempre o lado para onde o país virou. O que ele mede é que o eleitor do 2º turno não é sorteio do 1º, e isso todo mundo já sabe. <b>A fala do Monte Carlo não se aplica a este caso.</b>"),
        ],
      }],
    });
  }

  // ── caso 2: 700 → 8 na mesma seção ─────────────────────────────────────
  function mesmaSecao(d) {
    var x = d.mesma_secao, q = x.maiores_quedas.slice(0, 5);
    var max = Math.max.apply(null, q.map(function (s) { return s.flavio[0]; }));
    var linhas = h("div", { class: "linhas" }, q.map(function (s) {
      return h("div", { class: "linha" },
        h("div", { class: "linha-nome" }, s.municipio + "/" + s.uf.toUpperCase() + " ", h("small", { text: "zona " + s.zona + ", seção " + s.secao })),
        h("div", { class: "linha-val", html: "Flávio <b>" + s.flavio[0] + " → " + s.flavio[1] + "</b> · votantes " + s.comparecimento[0] + " → " + s.comparecimento[1] }),
        h("div", { class: "trilho" },
          h("i", { class: "antes", style: "width:" + (100 * s.flavio[0] / max) + "%" }),
          h("i", { class: "depois", style: "width:" + (100 * s.flavio[1] / max) + "%" })));
    }));
    return caso({
      id: "mesma-secao", n: 2,
      alegacao: "Flávio fez 700 votos no 1º turno e 8 ou 9 no 2º, na mesma seção.",
      fontes: [{ rot: "prints em grupos de WhatsApp (sem link público)" }],
      veredito: "Não existe nos dados", tom: "falso", selo: "não procede",
      pontos: [
        "<b>700 votos não cabem numa seção.</b> O máximo que o Flávio teve numa seção foi " + num(x.max_flavio[1]) + ". A seção mais cheia do país teve " + num(x.max_comparecimento[1]) + " votantes.",
        "<b>Nenhuma seção caiu de 100 para 10.</b> Das " + num(x.secoes_nos_dois_turnos) + " seções que existiram nos dois turnos, nenhuma teve o Flávio com 100 ou mais e depois até 10.",
        "<b>As quedas reais são de uns 100 votos</b>, sempre com o comparecimento caindo junto: seções rurais do Acre e do Amazonas em que menos gente voltou para votar.",
      ],
      visual: visual("As maiores quedas reais, na mesma seção", linhas,
        "Barra clara: votos do Flávio no 1º turno. Barra escura: no 2º. Um print de 700 → 8 costuma comparar o local de votação inteiro com uma seção, ou outro cargo."),
    });
  }

  // ── caso 3: o mesmo número em cada zona ────────────────────────────────
  function zonas(d) {
    var x = d.zonas, bsb = x.video.filter(function (v) { return v.onde === "tela" && v.zonas.length > 1; })[0], dona = bsb.dona;
    var placar = function (z) { return num(z.l) + " × " + num(z.f); };
    var tabela = h("div", { class: "rolagem" }, h("table", { class: "tab" },
      h("thead", {}, h("tr", {}, h("th", { text: "Zona de " + bsb.nm }), h("th", { text: "o vídeo mostrou" }), h("th", { text: "o resultado real" }))),
      h("tbody", {}, bsb.zonas.map(function (z) {
        var e = z.zona === dona.zona;
        return h("tr", { class: e ? "dona" : "" }, h("td", { text: "zona " + z.zona }),
          h("td", { class: e ? "real" : "preso", text: placar(dona) }), h("td", { class: "real", text: placar(z) }));
      }))));
    return caso({
      id: "zonas", n: 3,
      alegacao: "O mesmo número se repete em cada zona: Lula " + num(dona.l) + " e Flávio " + num(dona.f) + " em várias zonas de Brasília, e igual em Salvador e São Paulo. Matematicamente isso não existe.",
      fontes: [{ rot: "vídeo no TikTok gravado na tela do app Resultados, repassado no WhatsApp em 30/10" }],
      veredito: "O número é real, mas de uma zona só", tom: "parcial", selo: "tem explicação",
      pontos: [
        "<b>" + placar(dona) + " é o resultado da zona " + dona.zona + " de " + bsb.nm + "</b>, e só dela. Cada número do vídeo confere com uma única zona.",
        "<b>A tela travou.</b> No vídeo, o topo troca o nome da zona, mas os números ficam presos na zona aberta antes. A própria autora diz que o app “está demorando um pouquinho”.",
        "<b>No país inteiro, nenhuma zona repete outra.</b> São " + num(x.zonas_pais) + " zonas e " + num(x.placares_repetidos) + " placares repetidos, nem entre cidades diferentes.",
      ],
      visual: visual("O que a tela mostrou × o que cada zona teve (Lula × Flávio)", tabela,
        "Somando as " + x.cidades[bsb.nm].zonas + " zonas, " + bsb.nm + " deu " + placar(x.cidades[bsb.nm]) + ", o mesmo total que o app mostra em “Zona: Todas”."),
    });
  }

  // ── caso 4: 3.042 seções com o Flávio até 10 votos ─────────────────────
  function barras(series) {
    var W = 420, H = 200, mE = 34, mB = 24, mT = 10, n = 11, grupo = (W - mE) / n, lb = Math.min(11, (grupo - 4) / series.length);
    var max = Math.max.apply(null, [].concat.apply([], series.map(function (x) { return x.v; })));
    var topo = Math.ceil(max / 100) * 100;
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, class: "grafico", role: "img",
      "aria-label": "Seções por número de votos do candidato do 22, de 0 a 10" });
    [0, topo / 2, topo].forEach(function (v) {
      var y = mT + (H - mT - mB) * (1 - v / topo);
      svg.appendChild(s("line", { x1: mE, x2: W, y1: y, y2: y, class: "grade" }));
      svg.appendChild(s("text", { x: mE - 6, y: y + 4, "text-anchor": "end", class: "eixo", text: num(v) }));
    });
    for (var i = 0; i < n; i++) {
      var x0 = mE + i * grupo + (grupo - lb * series.length) / 2;
      series.forEach(function (sr, k) {
        var alt = (H - mT - mB) * sr.v[i] / topo;
        var r = s("rect", { x: x0 + k * lb, y: H - mB - alt, width: lb - 2, height: alt, rx: 2, class: sr.classe });
        r.appendChild(s("title", { text: sr.rot + ": " + num(sr.v[i]) + " seções com " + i + " votos" }));
        svg.appendChild(r);
      });
      svg.appendChild(s("text", { x: mE + i * grupo + grupo / 2, y: H - 8, "text-anchor": "middle", class: "eixo", text: i }));
    }
    return svg;
  }
  function secoesAte10(d) {
    var x = d.secoes_ate_10, f2 = x.flavio_2t, f1 = x.flavio_1t, T = x.total, r22 = d.regua_2022.secoes.f_ate_10;
    var series = [
      { v: r22.por_voto_2t, rot: "2022, 2º turno (Bolsonaro)", classe: "barra-a", cor: "color-mix(in srgb, var(--texto-3) 70%, transparent)" },
      { v: f1.por_voto, rot: "2026, 1º turno", classe: "barra-b", cor: "color-mix(in srgb, var(--flavio) 45%, transparent)" },
      { v: f2.por_voto, rot: "2026, 2º turno", classe: "barra-c", cor: "var(--flavio)" }];
    return caso({
      id: "secoes-10", n: 4,
      alegacao: "Em " + num(f2.secoes) + " seções Flávio fez no máximo 10 votos e Lula somou " + num(Math.round(f2.outro_somou / 1000)) + " mil; em " + f2.zeradas + " urnas ele teve zero.",
      fontes: [{ rot: "Folha (via Repórter PB)", url: "https://www.reporterpb.com.br/noticia-extra/2026/10/27/flavio-teve-zero-voto-em-106-urnas-nas-quais-somou-quase-15-mil/136248.html" },
               { rot: "Pleno News", url: "https://pleno.news/brasil/eleicoes-2026/flavio-tem-zero-voto-em-urnas-que-somaram-14-mil-para-lula.html" },
               { rot: "post republicado pelo Jornal da Cidade Online" }],
      veredito: "O número confere. Não é sinal de fraude.", tom: "parcial", selo: "tem explicação",
      pontos: [
        "<b>Os números batem com o TSE:</b> " + num(f2.secoes) + " seções, " + num(f2.outro_somou) + " votos do Lula nelas, " + f2.zeradas + " com o Flávio zerado.",
        "<b>Já era assim antes.</b> No 1º turno, quando o Flávio terminou na frente no país, já eram " + num(f1.secoes) + " seções. No 2º turno de 2022, com o Bolsonaro, eram " + num(r22.t2) + ".",
        "<b>São seções pequenas e homogêneas:</b> " + x.comparecimento_medio[0] + " votantes em média (no país, " + x.comparecimento_medio[1] + "), muitas em aldeias, povoados e assentamentos. " + x.zeradas_em_aldeia[0] + " das " + x.zeradas_em_aldeia[1] + " zeradas ficam em aldeia indígena.",
        "<b>Não decidem nada:</b> anulando todas, a vantagem do Lula cairia de " + mi(x.margem) + " para " + mi(x.margem_sem_elas) + " votos.",
      ],
      visual: visual("Seções por número de votos do candidato do 22 (de 0 a 10)", [
        barras(series),
        h("div", { class: "legenda" }, series.map(function (sr) { return h("span", { style: "--c:" + sr.cor, text: sr.rot }); }))],
        "O desenho de 2026 é o mesmo do 1º turno e menor que o de 2022."),
      mais: [{ rot: "Para onde foi o voto nessas seções", corpo: p("Nelas o Lula ganhou " + num(T.l2 - T.l1) + " votos entre os turnos e o Flávio perdeu " + num(T.f1 - T.f2) +
        ". Havia " + num(T.t1) + " votos da terceira via e " + num(T.bn1) + " brancos e nulos no 1º turno, com quase o mesmo número de votantes (" + sinal(T.c2 - T.c1) + "). A conta fecha no voto.") }],
    });
  }

  // ── caso 5: o "algoritmo" da curva ─────────────────────────────────────
  function grafCurva(n) {
    var W = 420, H = 220, mE = 36, mD = 8, mT = 10, mB = 24, y0 = 46, y1 = 56;
    var X = function (v) { return mE + (W - mE - mD) * v / 100; };
    var Y = function (v) { return mT + (H - mT - mB) * (y1 - Math.max(y0, Math.min(y1, v))) / (y1 - y0); };
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, class: "grafico", role: "img",
      "aria-label": "Fatia do Bolsonaro ao longo da apuração de 2022, na ordem em que os boletins chegaram" });
    [46, 48, 50, 52, 54, 56].forEach(function (v) {
      svg.appendChild(s("line", { x1: mE, x2: W - mD, y1: Y(v), y2: Y(v), class: "grade" }));
      svg.appendChild(s("text", { x: mE - 6, y: Y(v) + 4, "text-anchor": "end", class: "eixo", text: v + "%" }));
    });
    [0, 25, 50, 75, 100].forEach(function (v) { svg.appendChild(s("text", { x: X(v), y: H - 6, "text-anchor": "middle", class: "eixo", text: v + "%" })); });
    svg.appendChild(s("line", { x1: mE, x2: W - mD, y1: Y(n.final), y2: Y(n.final), class: "ref" }));
    svg.appendChild(s("text", { x: W - mD, y: Y(n.final) + 16, "text-anchor": "end", class: "eixo", text: "final: " + pc(n.final, 2) }));
    var d = n.curva.map(function (q, i) { return (i ? "L" : "M") + X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1); }).join(" ");
    var path = s("path", { d: d, class: "serie bolso desenha" });
    svg.appendChild(path);
    path.style.setProperty("--len", 1200);
    return svg;
  }
  function curva(d) {
    var n = d.regua_2022.noite, r = n.recorte[0], t22 = d.regua_2022.trocas, q = n.quedas[0];
    return caso({
      id: "curva", n: 5,
      alegacao: "Um algoritmo derrubava o Bolsonaro de tempos em tempos durante a apuração; sem ele, teria de 60% a 65%.",
      fontes: [{ rot: "Reel republicado pelo Vitória News (28/10)", url: "https://www.instagram.com/reels/DfBTF4LtGzB/" },
               { rot: "Aliados Brasil", url: "https://www.aliadosbrasiloficial.com.br/noticia/professor-de-matematica-aponta-supostos-padroes-algoritmicos-na-apuracao-e-estima-que-flavio-bolsonaro-teria-vencido-com-65-dos-votos" }],
      veredito: "É de 2022 e não se sustenta", tom: "falso", selo: "não procede",
      pontos: [
        "<b>O vídeo é sobre 2022.</b> O professor fala do Bolsonaro e das “472 urnas”, que são as " + num(n.secoes) + " seções do 2º turno de 2022. Foi a legenda do post de 2026 que pôs o 60–65% no Flávio.",
        "<b>Cada “queda” tem hora e lugar.</b> Os boletins chegam por região e fuso. A maior queda do trecho do vídeo foi às " + q.hora.slice(0, 5) + ", com boletins de " + q.lugares.join(", ") + ", seções que qualquer um confere.",
        "<b>Recortar e colar fabrica qualquer vencedor.</b> Juntar só as subidas dá " + pc(r.bolsonaro_so_subidas, 1) + " ao Bolsonaro, o número do vídeo. O mesmo recorte dá " + pc(r.lula_so_quedas, 1) + " ao Lula.",
      ],
      visual: visual("A apuração de 2022 refeita com os boletins, na ordem de chegada", [
        grafCurva(n),
        h("div", { class: "duelo" },
          h("div", { class: "f" }, h("b", { text: pc(r.bolsonaro_so_subidas, 1) }), h("span", { text: "Bolsonaro, juntando só as subidas dele" })),
          h("div", { class: "l" }, h("b", { text: pc(r.lula_so_quedas, 1) }), h("span", { text: "Lula, juntando só as quedas do Bolsonaro" })))],
        "Fatia do Bolsonaro (eixo vertical) conforme a apuração avançava (horizontal). Ela sobe e desce conforme a região que chega; em ordem sorteada, a liderança troca em média " + t22.trocas_mediana + " vezes."),
    });
  }

  // ── montar os casos ────────────────────────────────────────────────────
  function montarCasos() {
    var lista = document.getElementById("lista-casos");
    pedir("acusacoes.json").then(function (d) {
      lista.textContent = "";
      [silvaJardim, mesmaSecao, zonas, secoesAte10, curva].forEach(function (f) {
        try { lista.appendChild(f(d)); } catch (e) { console.error(e); }
      });
      var obs = "IntersectionObserver" in window && new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("visivel"); obs.unobserve(e.target); } });
      }, { rootMargin: "0px 0px -8% 0px" });
      lista.querySelectorAll(".caso").forEach(function (c) { obs ? obs.observe(c) : c.classList.add("visivel"); });
    }).catch(function () {
      lista.innerHTML = "<p class='carregando'>Não consegui abrir os casos agora. Recarregue a página.</p>";
    });
  }

  document.addEventListener("DOMContentLoaded", montarCasos);
})();
