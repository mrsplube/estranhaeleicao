/* estranhaeleicao.org — página de entrada (30/10/2026).
 *
 * Lê /apuracao/explicacao/acusacoes.json (~43 KB, gerado por
 * tools/migracoes/2026-10-29-acusacoes-2t.py) e casos_videos.json (o vídeo de
 * cada caso e os números dos casos novos, tools/migracoes/2026-10-30-casos-videos.py).
 * Cada caso tem um nome curto, a teoria, uma etiqueta (verdade e estranho /
 * premissa falsa / verdade, mas normal) e a capa do vídeo que a espalhou; a
 * resposta abre num clique. Todo número vem desse arquivo; o texto
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
  // o = {id, titulo, alegacao, tag, video?, icone?, fontes?: [{rot, url?}], veredito,
  //      pontos: [..], visual?, mais?: [{rot, corpo, classe}]}
  var TAG = {
    estranho: { rot: "Verdade e estranho", cls: "parcial" },
    falsa: { rot: "Premissa falsa", cls: "falso" },
    normal: { rot: "Verdade, mas normal", cls: "ok" },
  };
  var V = null;   // casos_videos.json
  function mil(x) {
    return x >= 1e6 ? (x / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi"
      : x >= 1000 ? Math.round(x / 1000) + " mil" : String(x);
  }
  function capa(o, v) {
    var dentro = [v && v.capa ? h("img", { src: v.capa, alt: "", loading: "lazy", width: "360", height: "480" })
      : h("span", { class: "capa-ico", "aria-hidden": "true", text: o.icone || "▶" }),
      v ? h("span", { class: "capa-play", "aria-hidden": "true" }) : null];
    return v ? h("a", { class: "capa", href: v.url, target: "_blank", rel: "noopener nofollow",
      "aria-label": "Ver o vídeo de @" + v.perfil + " no Instagram" }, dentro)
      : h("div", { class: "capa sem-video" }, dentro);
  }
  function caso(o, n) {
    var v = V && V.videos[o.id], t = TAG[o.tag];
    var art = h("article", { class: "caso", id: "caso-" + o.id });
    var abrir = h("button", { class: "btn btn-mini caso-abrir", type: "button", "aria-expanded": "false",
      text: "Ver a resposta", onclick: function () {
        var aberto = art.classList.toggle("respondido");
        abrir.setAttribute("aria-expanded", String(aberto));
        abrir.textContent = aberto ? "Fechar a resposta" : "Ver a resposta";
      } });
    var quem = v ? h("a", { class: "quem", href: v.url, target: "_blank", rel: "noopener nofollow" },
      "▶ @" + v.perfil, v.curtidas ? h("span", { text: " · ♥ " + mil(v.curtidas) }) : null) : null;
    anexar(art, [
      h("div", { class: "caso-cab" },
        capa(o, v),
        h("div", { class: "caso-txt" },
          h("div", { class: "caso-topo" }, h("span", { text: "Caso " + n }), h("span", { class: "tag " + t.cls, text: t.rot })),
          h("h3", { class: "caso-tit", text: o.titulo }),
          h("p", { class: "alegacao", text: o.alegacao }),
          h("div", { class: "fontes" }, quem, (o.fontes || []).map(function (f) {
            return f.url ? h("a", { class: "fonte", href: f.url, target: "_blank", rel: "noopener nofollow", text: f.rot })
              : h("span", { class: "fonte", text: f.rot });
          })),
          abrir)),
      h("div", { class: "revela" }, h("div", {},
        h("span", { class: "veredito " + t.cls, text: o.veredito }),
        h("ul", { class: "pontos" }, o.pontos.map(function (p) { return h("li", { html: p }); })),
        o.visual || null,
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
      id: "silva-jardim", titulo: "Cidades onde o Flávio parou", tag: "normal",
      alegacao: "Em Araruama (RJ), o Flávio ganhou 11 votos entre os turnos e o Lula 5.581. Em Silva Jardim, 1 contra " + num(t2.lula - t1.lula) + ". A chance disso seria de 1 em 10⁴⁶⁸.",
      fontes: [{ rot: "Silva Jardim, no X", url: "https://x.com/lucascrvg_20/status/2115159021606891820" },
               { rot: "Campos, no Instagram", url: "https://www.instagram.com/reel/DfGXIePNOby/" }],
      veredito: "O número confere. A conta, não.",
      pontos: [
        "<b>“+1” é saldo, não o voto que ele recebeu.</b> " + num(t1.comp - t2.comp) + " pessoas a menos foram votar no 2º turno. Eleitor do Flávio que não voltou desconta do que ele ganhou: ganhar 200 e perder 199 dá +1.",
        "<b>Os votos do Lula vieram da terceira via.</b> Eram " + num(terc) + " votos, " + num(cury + caiado) + " deles de Cury e Caiado, cujo eleitor foi mais para o Lula no país todo. Somando os " + num(bn1) + " brancos e nulos do 1º turno, a conta fecha sem nenhum eleitor do Flávio virar Lula.",
        "<b>Em Campos dos Goytacazes não há “voto do além”.</b> Os 1.386 votos que o vídeo não acha são os " + num(-V.dados.cidades["CAMPOS DOS GOYTACAZES"].f2 + V.dados.cidades["CAMPOS DOS GOYTACAZES"].f1) + " que o Flávio perdeu lá: a conta esqueceu que ele caiu.",
        "<b>Não é exceção.</b> Em " + num(x.flavio_ganho_ate_zero) + " cidades o Flávio ganhou 0 ou menos entre os turnos, e em " + num(x.quase_tudo_lula_com_flavio_60) + " delas ele venceu com 60% ou mais, como lá. Em 2022 o mesmo aconteceu com o Bolsonaro em " + num(d.regua_2022.municipios.f_ganho_ate_zero) + ".",
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
      id: "mesma-secao", titulo: "Os 700 votos que sumiram", tag: "falsa", icone: "💬",
      alegacao: "Flávio fez 700 votos no 1º turno e 8 ou 9 no 2º, na mesma seção.",
      fontes: [{ rot: "prints em grupos de WhatsApp (sem link público)" }],
      veredito: "Não existe nos dados",
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
      id: "zonas", titulo: "O placar repetido", tag: "falsa", icone: "📺",
      alegacao: "O mesmo número se repete em cada zona: Lula " + num(dona.l) + " e Flávio " + num(dona.f) + " em várias zonas de Brasília, e igual em Salvador e São Paulo. Matematicamente isso não existe.",
      fontes: [{ rot: "vídeo no TikTok, repassado no WhatsApp (sem link público)" }],
      veredito: "O número é real, mas de uma zona só",
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
      id: "secoes-10", titulo: "As 106 urnas zeradas", tag: "normal",
      alegacao: "Em " + f2.zeradas + " urnas, ninguém votou no Flávio, nem branco, nem nulo: 100% Lula. Em " + num(f2.secoes) + " seções ele fez no máximo 10 votos. É como ganhar 579 vezes seguidas na Mega-Sena.",
      fontes: [{ rot: "Folha (via Repórter PB)", url: "https://www.reporterpb.com.br/noticia-extra/2026/10/27/flavio-teve-zero-voto-em-106-urnas-nas-quais-somou-quase-15-mil/136248.html" },
               { rot: "Jornal da Cidade Online" }],
      veredito: "O número confere. Não é sinal de fraude.",
      pontos: [
        "<b>“Sem branco nem nulo” não confere.</b> Só " + V.dados.secoes_zeradas.sem_branco_nulo + " das " + V.dados.secoes_zeradas.total + " urnas não tiveram branco nem nulo; somadas, elas tiveram " + num(V.dados.secoes_zeradas.branco_nulo) + ". E a conta da Mega-Sena supõe que cada eleitor é sorteado do país inteiro.",
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
      id: "curva", titulo: "O algoritmo da apuração", tag: "falsa",
      alegacao: "Um algoritmo derrubava o Bolsonaro de tempos em tempos durante a apuração; sem ele, teria de 60% a 65%. E com 51 a 49, a liderança deveria ter trocado várias vezes.",
      fontes: [{ rot: "Aliados Brasil", url: "https://www.aliadosbrasiloficial.com.br/noticia/professor-de-matematica-aponta-supostos-padroes-algoritmicos-na-apuracao-e-estima-que-flavio-bolsonaro-teria-vencido-com-65-dos-votos" }],
      veredito: "É de 2022 e não se sustenta",
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

  // ── casos novos (30/10/2026, a partir dos reels mais vistos) ────────────
  function fonte(k) { return V.fontes[k]; }
  function virada() {
    var n = V.dados.nacional, dl = n.lula2 - n.lula1, df = n.flavio2 - n.flavio1;
    return caso({
      id: "virada", titulo: "A virada inédita", tag: "estranho",
      alegacao: "Pela primeira vez desde 1989, quem perdeu o 1º turno ganhou o 2º. O Lula levou 3 de cada 4 votos em jogo, contra as pesquisas e o mercado de apostas.",
      fontes: [{ rot: "Dep. Alberto Fraga", url: "https://www.instagram.com/reel/DfA-y_9uwSe/" }],
      veredito: "É verdade e é raro. Mas a conta fecha.",
      pontos: [
        "<b>É inédito mesmo.</b> Nos 7 segundos turnos desde 1989, quem liderou o 1º turno ganhou o 2º. Em 2026, não.",
        "<b>Os números conferem.</b> Entre os turnos o Lula ganhou " + mi(dl) + " e o Flávio " + mi(df) + ": de cada 4 votos novos, 3 foram para o Lula.",
        "<b>As pesquisas erraram para o mesmo lado.</b> A última AtlasIntel dava 50,8% ao Flávio; ele terminou com 48,21%. O mercado de apostas seguiu as pesquisas.",
        "<b>Cresceu em todo estado, e mais em %, onde tinha menos.</b> É efeito de base: em pontos do eleitorado, ganhou 6,1 no Piauí e 6,5 em Santa Catarina.",
        "<b>Raro não é impossível.</b> Não precisa de nenhum eleitor do Flávio virar: basta a terceira via, o branco/nulo e quem voltou a votar penderem para o Lula. <a href='/apuracao/cenarios'>Veja 5 jeitos de a conta fechar</a>.",
      ],
      visual: visual(null, h("div", { class: "numeros" },
        numero("+" + mi(dl), "Lula entre os turnos", "l"), numero("+" + mi(df), "Flávio entre os turnos", "f"),
        numero(pc(100 * dl / (dl + df), 0), "dos votos novos foram para o Lula"))),
    });
  }
  function biometria() {
    return caso({
      id: "biometria", titulo: "8,6 milhões sem digital", tag: "falsa",
      alegacao: "Um relatório divulgado nos EUA diz que 8,6 milhões votaram sem biometria depois das 17h. Tirando esses votos, o Flávio teria ganhado.",
      fontes: [fonte("tse_17h"), fonte("nucleo")],
      veredito: "Mistura dois números e conclui o que eles não dizem",
      pontos: [
        "<b>Depois das 17h foram 34.393 votos</b> no país inteiro, segundo o TSE: 0,03% do total, e não milhões.",
        "<b>Os 8,6 milhões são do dia todo:</b> eleitores com digital cadastrada que a urna não reconheceu e que votaram após conferir o documento com foto. É o procedimento normal.",
        "<b>Tirar 8,6 milhões só do Lula</b> supõe que todos votaram nele. Nada no relatório mostra isso, e o voto é secreto.",
        "<b>O relatório não tem autor.</b> A Justiça Eleitoral o classificou como apócrifo e como distorção dos dados públicos.",
      ],
      visual: visual(null, h("div", { class: "numeros" },
        numero("34.393", "votos depois das 17h (TSE)"), numero(mi(V.dados.nacional.lula2 - V.dados.nacional.flavio2), "de vantagem do Lula", "l"))),
    });
  }
  function mesario() {
    return caso({
      id: "mesario", titulo: "O mesário pianista", tag: "falsa",
      alegacao: "Com o número do título, o mesário vota pelo eleitor que faltou ou morreu. Em 500 mil seções, isso dá milhões de votos.",
      fontes: [fonte("aosfatos"), fonte("tse_17h")],
      veredito: "Fraude isolada é crime e aparece. Milhões, não.",
      pontos: [
        "<b>Só o título não basta.</b> Sem a digital, a mesa confere documento com foto e a urna pede o ano de nascimento, que não está no caderno de votação.",
        "<b>Não sobra voto para isso.</b> O vídeo fala em milhões de votos no fim do dia; depois das 17h entraram 34.393 em todo o país.",
        "<b>Quando acontece, aparece.</b> O eleitor de verdade chega e descobre que “já votaram”, como em relatos no interior de SP. Isso vai para a ata e vira investigação.",
        "<b>“O site diz que eu faltei”</b> foi uma mensagem errada do autoatendimento do TSE, corrigida depois (Poder360). Não é registro de voto.",
      ],
    });
  }
  function caminhonete() {
    return caso({
      id: "caminhonete", titulo: "A caminhonete do PT", tag: "estranho", icone: "🚚",
      alegacao: "Urnas foram levadas numa caminhonete com adesivo do PT no Distrito Federal, depois da votação.",
      fontes: [fonte("caminhonete"), fonte("pleno")],
      veredito: "Aconteceu, e foi irregular. Mas não mexeu em voto.",
      pontos: [
        "<b>O vídeo é real.</b> Foi no Riacho Fundo II, depois do fim da votação. O TRE-DF confirmou e abriu apuração, porque usar veículo com propaganda de partido contraria as regras.",
        "<b>Os votos já tinham saído da urna.</b> Quando ela foi recolhida, o boletim já estava impresso e os dados já tinham sido transmitidos ao TSE.",
        "<b>Dá para conferir.</b> O boletim de urna impresso na seção é público: se a urna fosse mexida depois, o resultado publicado não bateria com o papel.",
      ],
    });
  }
  function consulta() {
    return caso({
      id: "consulta", titulo: "A consulta que sumiu", tag: "normal",
      alegacao: "Depois que muita gente foi conferir se pessoas mortas votaram, o TSE tirou do ar a consulta de quem votou. Diz que volta em 3 de novembro.",
      fontes: [fonte("tse_certidao"), fonte("tre_df_certidao")],
      veredito: "Saiu do ar, sim. Estava no calendário desde fevereiro.",
      pontos: [
        "<b>A suspensão é real</b> e vai de 26/10 a 2/11. A consulta e a certidão de quitação voltam na terça, 3 de novembro.",
        "<b>Acontece em toda eleição.</b> Nesses dias a Justiça Eleitoral processa os arquivos das urnas: quem votou, quem faltou e quem justificou. A pausa estava prevista no calendário desde fevereiro.",
        "<b>A mensagem de suspensão não é resultado.</b> Quem vê “ausente” ou “faltou” nesse período não teve o voto apagado: o dado ainda não foi processado.",
        "<b>E morto não vota.</b> O óbito chega ao cartório eleitoral, que cancela o título. Sem título válido, o nome não está no caderno da seção.",
      ],
    });
  }
  function soma() {
    return caso({
      id: "soma", titulo: "A soma que não fecha", tag: "falsa",
      alegacao: "A soma dos estados não bate com o total do Brasil no site do TSE: faltam 766 mil votos.",
      fontes: [{ rot: "print do X" }],
      veredito: "O print é do começo da apuração",
      pontos: [
        "<b>No print, o Lula tem 3,5 milhões de votos</b> (no fim teve 64,3 milhões). Foi tirado com poucas urnas apuradas, e cada estado foi copiado num momento diferente, como o próprio autor conta. Durante a apuração, os números mudam a cada segundo.",
        "<b>No resultado final, a soma fecha voto a voto.</b> As 499.205 seções somam 124.082.273 votos válidos, exatamente o total oficial, em cada estado e no exterior.",
      ],
      visual: visual(null, h("div", { class: "numeros" },
        numero("124.082.273", "soma das seções"), numero("124.082.273", "resultado oficial"))),
    });
  }
  function cedula() {
    return caso({
      id: "cedula", titulo: "Voto no papel", tag: "normal",
      alegacao: "Em Pernambuco, uma seção passou a votar em cédula de papel, sem fiscalização. “Vão roubar essa eleição.”",
      fontes: [fonte("tre_pe")],
      veredito: "Existe e está na lei. É exceção.",
      pontos: [
        "<b>É o plano C.</b> Se a urna quebra, entra uma de reserva. Só se a reserva também falhar a seção vota em cédula, que é apurada depois pela junta eleitoral, com fiscais dos partidos.",
        "<b>Foi raro.</b> Em Pernambuco, 80 das 22.694 urnas foram trocadas no 2º turno, menos que no 1º (123), segundo o TRE-PE.",
        "<b>Não decide nada.</b> Uma seção tem em média uns " + num(V.dados.nacional.comp2 / 499205) + " votantes; a diferença no país foi de " + mi(V.dados.nacional.lula2 - V.dados.nacional.flavio2) + ".",
      ],
    });
  }
  function eleitores() {
    var c = V.dados.bahia;
    return caso({
      id: "eleitores", titulo: "Mais eleitor que habitante", tag: "normal",
      alegacao: "A Bahia tem 23 municípios com mais eleitores do que habitantes, como Catolândia e Firmino Alves.",
      fontes: [fonte("atarde"), fonte("tatu")],
      veredito: "É verdade, e é antigo. Não é voto a mais.",
      pontos: [
        "<b>Os 23 existem</b>, cruzando o eleitorado do TSE com a população estimada pelo IBGE. No país são 733; na Bahia eram 36 em 2022.",
        "<b>É gente que mudou e não transferiu o título.</b> Quem estuda ou trabalha fora continua votando na cidade de origem, e a população do IBGE é estimada.",
        "<b>Quem vota é menos que quem mora.</b> Catolândia tem uns 3.567 habitantes e 4.189 eleitores, mas votaram " + num(c["CATOLÂNDIA"].c2) + " no 2º turno. Em Firmino Alves, " + num(c["FIRMINO ALVES"].c2) + ".",
      ],
    });
  }

  // ── montar os casos ────────────────────────────────────────────────────
  function montarCasos() {
    var lista = document.getElementById("lista-casos");
    Promise.all([pedir("acusacoes.json"), pedir("casos_videos.json")]).then(function (r) {
      var d = r[0], n = 0;
      V = r[1];
      lista.textContent = "";
      [virada, secoesAte10, curva, biometria, mesario, caminhonete, silvaJardim, soma, consulta, mesmaSecao, zonas, cedula, eleitores].forEach(function (f) {
        try { lista.appendChild(f(d)); } catch (e) { console.error(e); }
      });
      lista.querySelectorAll(".caso-topo > span:first-child").forEach(function (el) { el.textContent = "Caso " + (++n); });
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
