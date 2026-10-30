/* A conta do 2º turno — UMA página, com o desenho COMPLETO no topo (29/10/2026).
 *
 * É o híbrido entre a versão de 28/10 (o Cauê gostava de ver tudo num desenho
 * só, com os controles abertos) e a de 29/10 de manhã (legível e honesta).
 * A ordem da página:
 *
 *   1. Os três números que respondem a pergunta              (abertura)
 *   2. O Sankey completo: as 10 fontes do 1º turno → os 3     (o coração)
 *      destinos do 2º, com o placar fixo e uma linha
 *      arrastável por fonte logo abaixo
 *   3. Recolhidos: o que a aritmética garante (o Sankey de     (o detalhe)
 *      só o que mudou + a prova do piso), cada candidato com
 *      o intervalo, comparecimento, cidade, conferência
 *
 * **A quebra de escala.** Os 53,88 mi do Lula e os 56,10 mi do Flavio no 1º
 * turno são 6 vezes tudo o que mudou de lado; na mesma régua, o Zema vira fio.
 * A versão de 28/10 resolvia com raiz quadrada (e a legenda "largura = votos"
 * mentia); aqui os dois blocos têm altura FIXA com a marca ≈ ("fora de
 * escala") e todo o resto é linear. No destino, o bloco diz "já tinha + ganhou".
 *
 * **Os destinos na ordem Lula / Branco-nulo / Flavio.** O voto que ficou anda
 * reto (Lula em cima, Flavio embaixo), e branco/nulo — "nenhum dos dois" —
 * fica no meio. Dentro de cada família, as fontes vão da que mais deu ao Lula
 * para a que mais deu ao Flavio (ordem do ponto de partida, fixa depois disso):
 * menos faixa cruzando faixa.
 *
 * **Um controle por fonte.** Uma barra de três cores (Lula | Flavio |
 * branco/nulo) com duas divisas que se arrastam; setas do teclado também
 * movem. No toque, a barra só obedece a gesto HORIZONTAL (o vertical é rolar a
 * página) e tocar no nome abre dois controles deslizantes, para quem não
 * acerta a divisa com o dedo.
 *
 * **O estado.** As 8 fontes móveis (5 grupos da terceira via, comparecimento a
 * mais, branco e nulo do 1º turno) se dividem entre três destinos; os votos que
 * já eram do Lula e do Flavio ficam com eles (a troca direta medida é ≈ 0,
 * `transicao.py`). Assim as fontes somam os destinos ao voto: +10,38 mi,
 * +3,72 mi e os 4,15 mi de branco/nulo do 2º turno.
 *
 * Três coisas que não podem voltar (vieram da versão de 28/10):
 *  - destino FIXO no total do TSE enquanto o slider mexe — aqui o destino é a
 *    soma do cenário, e o TSE é o contorno tracejado;
 *  - medidor em % ("99%" com 2,5 mi de votos no lugar errado) — aqui o placar
 *    diz quantos votos faltam ou sobram em cada destino;
 *  - "Fechar a conta" por média — aqui é IPF (ajuste proporcional iterativo),
 *    que fecha os três totais e preserva o que a pessoa mexeu quando dá.
 */
(function () {
  "use strict";

  var AP, h, s, num, cartao;
  var d = null, pedindo = false, erro = null;
  var blocos = {};

  var COR = { lula: "#e3364a", flavio: "#2a78d6", bn: "#64748b", fonte: "#94a3b8" };
  var DEST = ["lula", "flavio", "bn"];            // ordem da barra de cada fonte
  var DEST_DESENHO = ["lula", "bn", "flavio"];    // ordem no Sankey
  var NOME_DEST = { lula: "Lula", flavio: "Flavio", bn: "Branco/nulo" };

  // ── formatação ──────────────────────────────────────────────────────────
  function mm(x) {
    var a = Math.abs(x || 0);
    if (a >= 1e6) return (x / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " mi";
    if (a >= 1e3) return (x / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 0 }) + " mil";
    return num(x);
  }
  function mi2(x) {
    return (x / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function mi(x) { return mi2(x) + " mi"; }
  function pc(x, c) {
    return (x || 0).toLocaleString("pt-BR", { minimumFractionDigits: c === undefined ? 1 : c,
      maximumFractionDigits: c === undefined ? 1 : c }) + "%";
  }
  function soma(lista, f) { return lista.reduce(function (t, x) { return t + f(x); }, 0); }
  function preso01(x) { return Math.max(0, Math.min(1, x)); }

  // ── carregar ────────────────────────────────────────────────────────────
  function carregar() {
    if (d || pedindo) return;
    pedindo = true; erro = null;
    var url = AP.base + "/explicacao/conta.json" +
      (AP.versao ? "?v=" + encodeURIComponent(AP.versao) : "");
    fetch(url, { cache: "default" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (x) { d = x; pedindo = false; AP.desenhar(); })
      .catch(function (e) { erro = e; pedindo = false; AP.desenhar(); });
  }

  // ── o desenho: um Sankey horizontal, usado pelos dois cartões ───────────
  // `c.fontes`: [{id, v, linhas, cor, px, quebra, vao}] — `px` é altura FIXA
  //   (o bloco fora de escala), e o resto é linear.
  // `c.destinos`: [{id, v, alvo, cor, linhas, base: {px, noFim}}] — `base` é o
  //   pedaço fora de escala do destino ("já tinha"); `alvo` é o tamanho que o
  //   TSE manda para a parte linear, desenhado como contorno tracejado.
  // `c.fluxos`: [{de, para, v | px, cor, op, titulo, nota}], na ordem de
  //   empilhar. A faixa tem a MESMA largura nas duas pontas e nenhuma ganha
  //   largura mínima.
  // `c.minPx`: faixa mais fina que isso NÃO é desenhada, mas o lugar dela fica
  //   reservado (as vizinhas não andam). Abaixo de ~1,5 px ela só vira um fio
  //   que cruza o desenho sem dizer nada; o número continua no foco e na barra.
  var ALT_LINHA = [15, 14, 13];
  var CLASSE_LINHA = ["ap-cam-n", "ap-cam-v", "ap-cam-s"];

  function sankeyH(c) {
    var W = c.W, H = c.H, TOPO = 8, FUNDO = 8, NO = 12;
    var xE = c.rotE, xD = W - c.rotD - NO;
    var util = H - TOPO - FUNDO;
    var vaosE = soma(c.fontes.slice(1), function (n) { return n.vao != null ? n.vao : c.vao; });
    var vaosD = c.vao * (c.destinos.length - 1);
    var fixoE = soma(c.fontes, function (n) { return n.px || 0; });
    var fixoD = soma(c.destinos, function (n) { return n.base ? n.base.px : 0; });
    var somaE = soma(c.fontes, function (n) { return n.px ? 0 : n.v; }) || 1;
    var somaD = soma(c.destinos, function (n) { return Math.max(n.v, n.alvo || 0); }) || 1;
    var k = Math.min((util - vaosE - fixoE) / somaE, (util - vaosD - fixoD) / somaD);

    var E = {}, D = {};
    var altE = somaE * k + vaosE + fixoE;
    var y = TOPO + (util - altE) / 2;
    c.fontes.forEach(function (n, i) {
      if (i) y += n.vao != null ? n.vao : c.vao;
      n.y = y; n.h = n.px || n.v * k; n.cur = y; y += n.h; E[n.id] = n;
    });
    var altD = soma(c.destinos, function (n) { return (n.base ? n.base.px : 0) + Math.max(n.v, n.alvo || 0) * k; }) + vaosD;
    y = TOPO + (util - altD) / 2;
    c.destinos.forEach(function (n, i) {
      if (i) y += c.vao;
      n.bh = n.base ? n.base.px : 0;
      n.y = y; n.h = n.bh + n.v * k; n.cur = y;
      y += n.bh + Math.max(n.v, n.alvo || 0) * k; D[n.id] = n;
    });

    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H,
      class: "ap-cam-svg" + (c.classe ? " " + c.classe : ""), role: "img", "aria-label": c.rotulo });

    var notas = [];
    c.fluxos.forEach(function (f) {
      var alt = f.px != null ? f.px : f.v * k;
      if (!(alt > 0)) return;
      var a = E[f.de], b = D[f.para];
      var y0 = a.cur, y1 = b.cur;
      a.cur += alt; b.cur += alt;
      if (c.minPx && alt < c.minPx) return;
      var x0 = xE + NO, x1 = xD, cx = (x0 + x1) / 2;
      var p = s("path", { class: "ap-cam-faixa", fill: f.cor, "fill-opacity": f.op,
        "data-de": f.de, "data-para": f.para,
        d: "M" + x0 + "," + y0 + " C" + cx + "," + y0 + " " + cx + "," + y1 + " " + x1 + "," + y1 +
           " L" + x1 + "," + (y1 + alt) + " C" + cx + "," + (y1 + alt) + " " + cx + "," + (y0 + alt) +
           " " + x0 + "," + (y0 + alt) + " Z" });
      p.appendChild(s("title", { text: f.titulo }));
      svg.appendChild(p);
      if (f.nota && alt >= 18) notas.push({ x: cx, y: (y0 + y1) / 2 + alt / 2 + 4, t: f.nota });
    });
    notas.forEach(function (n) {
      svg.appendChild(s("text", { x: n.x, y: n.y, "text-anchor": "middle", class: "ap-cam-nota", text: n.t }));
    });

    c.fontes.forEach(function (n) {
      svg.appendChild(s("rect", { x: xE, y: n.y, width: NO, height: Math.max(1, n.h), rx: 2,
        fill: n.cor || COR.fonte, "fill-opacity": n.quebra ? 0.5 : 1, class: "ap-cam-no", "data-no": n.id }));
      if (n.quebra) quebra(svg, xE, n.y + n.h / 2, NO);
    });
    c.destinos.forEach(function (n) {
      if (n.alvo != null) {
        svg.appendChild(s("rect", { x: xD - 3, y: n.y - 2, width: NO + 6, height: n.bh + n.alvo * k + 4, rx: 3,
          class: "ap-cam-alvo" }));
      }
      var yBase = n.base && n.base.noFim ? n.y + n.v * k : n.y;
      var yLin = n.base && !n.base.noFim ? n.y + n.bh : n.y;
      if (n.bh) {
        svg.appendChild(s("rect", { x: xD, y: yBase, width: NO, height: n.bh, rx: 2, fill: n.cor,
          "fill-opacity": 0.5, class: "ap-cam-no", "data-no": n.id }));
        quebra(svg, xD, yBase + n.bh / 2, NO);
      }
      svg.appendChild(s("rect", { x: xD, y: yLin, width: NO, height: Math.max(1, n.v * k), rx: 2, fill: n.cor,
        class: "ap-cam-no", "data-no": n.id }));
    });
    rotulos(svg, c.fontes, xE - 10, "end", xE - 2, H);
    rotulos(svg, c.destinos, xD + NO + 10, "start", xD + NO + 2, H);
    return svg;
  }

  // A marca ≈ de "fora de escala": um ziguezague da cor do cartão por cima do bloco.
  function quebra(svg, x, y, w) {
    var p = w / 4 + 1;
    svg.appendChild(s("path", { class: "ap-cam-quebra",
      d: "M" + (x - 2) + "," + (y - 3) + " l" + p + ",6 l" + p + ",-6 l" + p + ",6 l" + p + ",-6" }));
  }

  // Rótulos de uma coluna, sem se sobrepor: cada um quer ficar no meio do seu
  // nó; quem não cabe é empurrado para baixo (e, se passar do fundo, a coluna
  // inteira sobe). Rótulo deslocado ganha um fio até o nó.
  function rotulos(svg, nos, x, ancora, xFio, H) {
    var itens = nos.map(function (n) {
      var ls = n.linhas.filter(function (l) { return l; });
      var alt = 0;
      ls.forEach(function (l, i) { alt += ALT_LINHA[Math.min(i, 2)]; });
      return { n: n, ls: ls, alt: alt + 4, meio: n.y + Math.max(n.h, 1) / 2 };
    });
    var fim = -Infinity;
    itens.forEach(function (it) { it.topo = Math.max(it.meio - it.alt / 2, fim); fim = it.topo + it.alt; });
    var teto = H - 2;
    for (var i = itens.length - 1; i >= 0; i--) {
      if (itens[i].topo + itens[i].alt > teto) itens[i].topo = teto - itens[i].alt;
      teto = itens[i].topo;
    }
    itens.forEach(function (it) {
      var centro = it.topo + it.alt / 2;
      if (Math.abs(centro - it.meio) > 4) {
        var xr = ancora === "end" ? x + 4 : x - 4;
        svg.appendChild(s("path", { class: "ap-cam-fio",
          d: "M" + xFio + "," + it.meio + " L" + xr + "," + centro }));
      }
      var yy = it.topo + 2;
      it.ls.forEach(function (l, j) {
        yy += ALT_LINHA[Math.min(j, 2)];
        svg.appendChild(s("text", { x: x, y: yy - 3, "text-anchor": ancora,
          class: CLASSE_LINHA[Math.min(j, 2)], "data-no": it.n.id, text: l }));
      });
    });
  }

  function larguraDe(host, teto) {
    var w = host ? host.clientWidth : 0;
    return w ? Math.min(w, teto || 920) : 0;
  }

  // ── o Sankey de só o que mudou (recolhido em "O que a aritmética garante") ──
  // Nesse recorte a conta tem UM grau de liberdade: escolhida a fatia q da
  // terceira via que foi para o Lula, o resto sai por subtração.
  //   terceira → Lula = q·T (≥ q_min·T = 5,60 mi)   novos → Lula = GL − q·T
  function base() {
    var l = d.limite || {};
    var T = l.terceira || d.terceira_via, N = l.novos || d.novos_validos;
    var GL = l.ganho_lula || d.ganho_lula, GF = l.ganho_flavio || d.ganho_flavio;
    var qmin = Math.max(0, (GL - N) / T), qmax = Math.min(1, GL / T);
    var mod = d.modelo || {};
    var preso = function (q) { return Math.min(qmax, Math.max(qmin, q)); };
    return {
      T: T, N: N, GL: GL, GF: GF, qmin: qmin, qmax: qmax,
      qmod: mod.q != null ? preso(mod.q) : qmin,
      faixa: mod.q_ic ? [preso(mod.q_ic[0]), preso(mod.q_ic[1])] : null,
    };
  }

  var cam = { q: null, host: null, frase: null, saida: null, input: null, aviso: null };

  function svgCaminho(W) {
    var b = base(), q = cam.q, estreito = W < 560;
    var tL = q * b.T, nL = b.GL - tL;
    var tLfixo = b.qmin * b.T, nLfixo = b.GL - b.qmax * b.T;
    var fl = [
      { de: "t", para: "l", v: tLfixo, fixo: true, nota: estreito ? null : "mínimo obrigatório: " + mi(tLfixo) },
      { de: "t", para: "l", v: tL - tLfixo },
      { de: "t", para: "f", v: b.T - tL },
      { de: "n", para: "l", v: nLfixo, fixo: true },
      { de: "n", para: "l", v: nL - nLfixo },
      { de: "n", para: "f", v: b.N - nL },
    ];
    var nomeE = { t: "Terceira via", n: "Votos novos" }, nomeD = { l: "Lula", f: "Flavio" };
    fl.forEach(function (f) {
      f.cor = f.para === "l" ? COR.lula : COR.flavio;
      f.op = f.fixo ? 0.85 : 0.32;
      f.titulo = nomeE[f.de] + " → " + nomeD[f.para] + ": " + mi(f.v) +
        (f.fixo ? " (obrigatório pela aritmética)" : " (depende do cenário)");
    });
    return sankeyH({
      W: W, H: estreito ? 230 : 290, vao: 22,
      rotE: estreito ? 96 : 200, rotD: estreito ? 80 : 120,
      rotulo: "De onde vieram os votos a mais do Lula e do Flavio no 2º turno",
      fontes: [
        { id: "t", v: b.T, linhas: ["Terceira via", mi(b.T), estreito ? null : "Cury, Renan, Caiado e mais 7"] },
        { id: "n", v: b.N, linhas: [estreito ? "Votos novos" : "Votos válidos novos", mi(b.N),
          estreito ? null : "mais votantes, menos branco/nulo"] },
      ],
      destinos: [
        { id: "l", v: b.GL, cor: COR.lula, linhas: ["Lula", "+" + mi(b.GL)] },
        { id: "f", v: b.GF, cor: COR.flavio, linhas: ["Flavio", "+" + mi(b.GF)] },
      ],
      fluxos: fl,
    });
  }

  function redesenharCaminho() {
    var W = larguraDe(cam.host);
    if (!W) return;
    cam.host.textContent = "";
    cam.host.appendChild(svgCaminho(W));
  }

  // Abaixo do piso a conta não fecha: o slider para nele e a tela diz por quê.
  function definirQ(v) {
    var b = base();
    var abaixo = v < b.qmin - 1e-9;
    cam.q = Math.min(b.qmax, Math.max(b.qmin, v));
    cam.input.value = String(Math.round(100 * cam.q));
    pintarCaminho(abaixo);
    redesenharCaminho();
  }

  function pintarCaminho(abaixo) {
    var b = base(), q = cam.q;
    var noPiso = q - b.qmin < 0.005, noTeto = b.qmax - q < 0.005;
    cam.saida.textContent = noPiso ? pc(100 * b.qmin, 1) + " (o mínimo)" : pc(100 * q, 0);
    var tL = q * b.T, nL = b.GL - tL;
    var frase = "Neste cenário, " + pc(100 * q, noPiso ? 1 : 0) + " da terceira via (" + mi(tL) + ") e " +
      pc(100 * nL / b.N, 0) + " dos votos novos (" + mi(nL) + ") foram para o Lula. O Flavio ficou com " +
      mi(b.T - tL) + " da terceira via e " + mi(b.N - nL) + " dos votos novos.";
    if (noPiso) frase += " É o mínimo possível: todo voto novo foi para o Lula, e ainda faltavam " + mi(b.qmin * b.T) + ".";
    else if (noTeto) frase += " É o outro extremo: o ganho do Flavio veio todo dos votos novos.";
    cam.frase.textContent = frase + " Qualquer posição do controle fecha com o TSE.";
    cam.aviso.hidden = !abaixo;
  }

  function cartaoCaminho() {
    var b = base(), n = d.nacional || {};
    if (cam.q === null) cam.q = b.qmod;
    cam.host = h("div", { class: "ap-cam-host" });
    cam.frase = h("p", { class: "ap-cam-frase", "aria-live": "polite" });
    cam.saida = h("output", { class: "ap-cam-saida" });
    cam.aviso = h("p", { class: "ap-cam-aviso", hidden: true,
      text: "Abaixo de " + pc(100 * b.qmin, 1) + " a conta não fecha: o Lula precisaria de mais de 100% dos votos novos." });
    cam.input = h("input", { type: "range", min: "0", max: "100", step: "1",
      value: String(Math.round(100 * cam.q)), id: "ap-cam-q",
      "aria-label": "Quanto da terceira via foi para o Lula",
      oninput: function (ev) { definirQ(parseFloat(ev.target.value) / 100); } });

    var mod = d.modelo;
    var paraModelo = mod ? (
      "O modelo geográfico (regressão por município) aponta " + pc(100 * mod.q_modelo, 1) +
      (mod.ajustado_pelo_piso
        ? ", abaixo do mínimo, então o número honesto é o piso de " + pc(100 * b.qmin, 1) +
          (b.faixa ? ", com intervalo até " + pc(100 * b.faixa[1], 1) : "") + "."
        : (b.faixa ? " (intervalo de " + pc(100 * b.faixa[0], 1) + " a " + pc(100 * b.faixa[1], 1) + ")." : ".")) +
      " Nenhum cenário põe a terceira via majoritariamente no Flavio.") : null;

    var controle = h("div", { class: "ap-cam-ctl" },
      h("div", { class: "ap-cam-ctl-topo" },
        h("label", { for: "ap-cam-q", text: "Quanto da terceira via foi para o Lula?" }),
        cam.saida),
      cam.input,
      h("div", { class: "ap-cam-regua", "aria-hidden": "true" },
        h("span", { class: "ap-cam-regua-imp", vars: { "--ate": (100 * b.qmin) + "%" } }),
        b.faixa ? h("span", { class: "ap-cam-regua-mod",
          vars: { "--de": (100 * b.faixa[0]) + "%", "--ate": (100 * b.faixa[1]) + "%" } }) : null),
      h("div", { class: "ap-cam-regua-leg" },
        h("span", { class: "imp", text: "abaixo de " + pc(100 * b.qmin, 1) + ": impossível pela aritmética" }),
        b.faixa ? h("span", { class: "mod", text: "faixa do modelo geográfico" }) : null),
      cam.aviso,
      h("div", { class: "ap-cam-chips" },
        h("button", { type: "button", class: "ap-conta-chip", text: "O que o modelo aponta",
          onclick: function () { definirQ(b.qmod); } }),
        h("button", { type: "button", class: "ap-conta-chip", text: "Toda a terceira via no Lula",
          onclick: function () { definirQ(b.qmax); } })));

    var c = cartao("De onde vieram os " + mi(b.GL + b.GF) + " de votos a mais",
      "O mesmo resultado em dois blocos: a terceira via do 1º turno e os votos válidos que apareceram no 2º, " +
      "divididos entre o ganho do Lula e o do Flavio. Neste recorte a conta tem um grau de liberdade só, e por isso " +
      "dá para ver o mínimo que a aritmética obriga.",
      cam.host,
      h("p", { class: "ap-cam-fora", text: "Fora do desenho, porque não mudaram de lado: os " + mi(n.lula1) +
        " que já eram do Lula e os " + mi(n.flavio1) + " que já eram do Flavio no 1º turno." }),
      h("div", { class: "ap-cam-leg" },
        h("span", { class: "cheio", text: "cheio: a aritmética obriga (contagem e subtração)" }),
        h("span", { class: "claro", text: "claro: depende do cenário (nenhum dado agregado decide)" })),
      controle,
      cam.frase,
      paraModelo ? h("p", { class: "ap-conta-conta", text: paraModelo }) : null,
      h("p", { class: "ap-conta-fonte", text: "Fonte: totais oficiais do TSE nos dois turnos. As faixas cheias são " +
        "subtração; as claras são a parte que só uma pesquisa com eleitor poderia dividir." }));
    c.classList.add("ap-cam");
    pintarCaminho(false);
    return c;
  }

  // ── o estado do cenário (fonte a fonte) ─────────────────────────────────
  var CURTO = { "ESCRITOR AUGUSTO CURY": "Cury", "RENAN SANTOS": "Renan", "RONALDO CAIADO": "Caiado",
                "ZEMA": "Zema", "VETERINÁRIO WILSON GRASSI": "W. Grassi" };
  var MINUSC = { de: 1, da: 1, do: 1, dos: 1, das: 1, e: 1 };
  function titulo(nm) {
    if (nm === "ESCRITOR AUGUSTO CURY") return "Augusto Cury";
    return nm.toLowerCase().split(" ").map(function (p, i) {
      return i && MINUSC[p] ? p : p.charAt(0).toUpperCase() + p.slice(1);
    }).join(" ");
  }

  var fontesCache = null;
  function fontesSim() {
    if (fontesCache) return fontesCache;
    var n = d.nacional || {}, o = (d.variaveis || {}).novos_origens || {};
    var out = [], t = d.transicao;
    if (t && t.ok) {
      var IND = 4;
      t.candidatos.slice(0, IND).forEach(function (c) {
        out.push({ id: c.n, nome: titulo(c.nm), curto: CURTO[c.nm] || titulo(c.nm).split(" ")[0],
          v: c.votos_1t, fam: "terceira", est: c.estimativa, ic: c.ic, medido: c.identificado, borda: c.na_borda });
      });
      var resto = t.candidatos.slice(IND);
      var vr = soma(resto, function (c) { return c.votos_1t; });
      out.push({ id: "resto", nome: "Outros " + resto.length, curto: "Outros " + resto.length, v: vr,
        fam: "terceira", est: vr ? soma(resto, function (c) { return c.estimativa * c.votos_1t; }) / vr : 0.5,
        membros: resto.map(function (c) { return titulo(c.nm); }).join(", ") });
    } else {
      out.push({ id: "terceira", nome: "Terceira via", curto: "Terceira via", v: d.terceira_via, fam: "terceira", est: null });
    }
    out.push({ id: "voltaram", nome: "Compareceram a mais", curto: "Compareceram", v: o.abstencao || 0, fam: "novos",
      nota: "saldo: o 2º turno teve " + mi(o.abstencao || 0) + " de eleitores a mais" });
    // Branco e nulo do 1º turno são UMA fonte (o destino do 2º turno já junta
    // os dois) e TRAVADA: a parte que continua branco/nulo não é escolha, sai
    // da conta (ver `ajustarTravado`). A pessoa só divide o resto.
    out.push({ id: "bn1", nome: "Branco e nulo no 1º turno", curto: "Br./nulo 1º t.", travado: true, fam: "novos",
      v: (n.brancos1 || 0) + (n.nulos1 || 0),
      partes: [n.brancos1 || 0, n.nulos1 || 0] });
    fontesCache = out.filter(function (f) { return f.v > 0; });
    return fontesCache;
  }

  function alvosSim() {
    var n = d.nacional || {};
    return { lula: n.lula2 - n.lula1, flavio: n.flavio2 - n.flavio1, bn: (n.brancos2 || 0) + (n.nulos2 || 0) };
  }

  var sim = null;   // { fatia: {id: {lula, flavio, bn}}, mexidos: {}, partida: {}, status: {}, historia }

  function copiar(fatia) {
    var c = {};
    Object.keys(fatia).forEach(function (k) { c[k] = { lula: fatia[k].lula, flavio: fatia[k].flavio, bn: fatia[k].bn }; });
    return c;
  }

  // IPF: escala as colunas até o alvo, depois as linhas até os votos da fonte,
  // e repete. Converge para o cenário MAIS PARECIDO com o de partida que fecha
  // os dois lados — é o que "fechar a conta" quer dizer. Os alvos são
  // reescalados para a soma das fontes (o dado tem 588 votos de diferença de
  // arredondamento entre os dois lados, e sem isso o laço nunca assenta).
  function ipf(fs, alvo) {
    var tot = soma(fs, function (f) { return f.v; });
    var totA = soma(DEST, function (k) { return Math.max(0, alvo[k]); }) || 1;
    var A = DEST.map(function (k) { return Math.max(0, alvo[k]) * tot / totA; });
    var m = fs.map(function (f) {
      var q = sim.fatia[f.id];
      return DEST.map(function (k) { return Math.max(q[k], 1e-3) * f.v; });
    });
    for (var it = 0; it < 4000; it++) {
      for (var j = 0; j < 3; j++) {
        var sc = soma(m, function (l) { return l[j]; });
        if (sc > 0) m.forEach(function (l) { l[j] *= A[j] / sc; });
      }
      var desvio = 0;
      m.forEach(function (l, i) {
        var sl = l[0] + l[1] + l[2];
        desvio += Math.abs(sl - fs[i].v);
        if (sl > 0) for (var j2 = 0; j2 < 3; j2++) l[j2] *= fs[i].v / sl;
      });
      if (desvio < 50) break;
    }
    fs.forEach(function (f, i) {
      sim.fatia[f.id] = { lula: m[i][0] / f.v, flavio: m[i][1] / f.v, bn: m[i][2] / f.v };
    });
  }

  // Ponto de partida: a estimativa de cada candidato (o cartão do intervalo)
  // com o branco/nulo do cenário do servidor, e o IPF fecha a conta. Sai
  // dentro do intervalo de cada um (Cury 99%, Caiado ~77%, Renan ~14%), o que
  // não acontecia com o `inicial` do servidor (Caiado 90%, Renan 3%).
  // Depois, cada família é ordenada da fonte que mais deu ao Lula para a que
  // mais deu ao Flavio — e essa ordem não muda mais (linha que pula de lugar
  // enquanto a pessoa arrasta é pior que uma faixa cruzada).
  var FAMILIAS = ["terceira", "novos"];
  function iniciarSim() {
    var fs = fontesSim(), ini = (d.inicial || {}).fatia || {};
    sim = { fatia: {}, mexidos: {}, status: null, historia: "modelo" };
    fs.forEach(function (f) {
      var bn = (ini[f.id] && ini[f.id].bn) || (f.fam === "terceira" ? 0.02 : 0.3);
      if (f.fam === "terceira") {
        var L = f.est == null ? 0.6 : f.est;
        sim.fatia[f.id] = { lula: L * (1 - bn), flavio: (1 - L) * (1 - bn), bn: bn };
      } else if (f.travado && (ini.branco1 || ini.nulo1)) {
        var pe = [ini.branco1 || ini.nulo1, ini.nulo1 || ini.branco1], vt = f.partes[0] + f.partes[1];
        sim.fatia[f.id] = {};
        DEST.forEach(function (k) { sim.fatia[f.id][k] = (pe[0][k] * f.partes[0] + pe[1][k] * f.partes[1]) / vt; });
      } else if (ini[f.id]) {
        sim.fatia[f.id] = { lula: ini[f.id].lula, flavio: ini[f.id].flavio, bn: ini[f.id].bn };
      } else {
        sim.fatia[f.id] = { lula: 0.5, flavio: 0.2, bn: 0.3 };
      }
    });
    ipf(fs, alvosSim());
    ajustarTravado();
    sim.partida = copiar(sim.fatia);
    fs.sort(function (a, b) {
      var fa = FAMILIAS.indexOf(a.fam), fb = FAMILIAS.indexOf(b.fam);
      if (fa !== fb) return fa - fb;
      if (a.id === "resto" || b.id === "resto") return a.id === "resto" ? 1 : -1;
      return (sim.partida[b.id].lula - sim.partida[b.id].flavio) - (sim.partida[a.id].lula - sim.partida[a.id].flavio);
    });
  }

  // A fonte travada (branco e nulo do 1º turno): a parte que continua
  // branco/nulo é o branco/nulo do 2º turno menos o que as OUTRAS fontes
  // mandaram para lá. O resto se divide entre Lula e Flavio na proporção que a
  // pessoa escolheu. Com isso o destino branco/nulo fecha sempre com o TSE, e
  // "o Renan anulou metade" puxa sozinho mais branco/nulo do 1º turno para um
  // candidato — é o que a conta exige.
  function ajustarTravado() {
    var fs = fontesSim(), alvo = alvosSim();
    fs.forEach(function (f) {
      if (!f.travado) return;
      var outros = soma(fs.filter(function (g) { return g !== f; }), function (g) { return sim.fatia[g.id].bn * g.v; });
      var fica = Math.max(0, Math.min(f.v, alvo.bn - outros)) / f.v;
      var x = sim.fatia[f.id], livre = x.lula + x.flavio, r = livre > 1e-9 ? x.lula / livre : 0.7;
      sim.fatia[f.id] = { lula: (1 - fica) * r, flavio: (1 - fica) * (1 - r), bn: fica };
    });
  }

  function contaSim() {
    var fs = fontesSim(), alvo = alvosSim();
    var S = { lula: 0, flavio: 0, bn: 0 };
    fs.forEach(function (f) { DEST.forEach(function (k) { S[k] += sim.fatia[f.id][k] * f.v; }); });
    var dif = {}, erroT = 0;
    DEST.forEach(function (k) { dif[k] = S[k] - alvo[k]; erroT += Math.abs(dif[k]); });
    // Cada voto no lugar errado aparece duas vezes (falta num destino e sobra
    // noutro), daí a metade. 15 mil é folga de arredondamento, não de cenário.
    return { S: S, alvo: alvo, dif: dif, fora: erroT / 2, fecha: erroT / 2 < 15000 };
  }

  // Em voltas: o IPF mexe no branco/nulo das outras fontes, a fonte travada
  // acompanha, e a volta seguinte acerta o que sobrou. A primeira volta diz o
  // que aconteceu; uma recusa depois também conta.
  function fecharConta() {
    var st = null;
    for (var volta = 0; volta < 6; volta++) {
      var r = fecharUmaVez();
      if (!st || !r.ok) st = r;
      ajustarTravado();
      if (contaSim().fecha) break;
    }
    sim.status = st;
  }

  function fecharUmaVez() {
    var fs = fontesSim(), alvo = alvosSim();
    var presas = fs.filter(function (f) { return sim.mexidos[f.id]; });
    var livres = fs.filter(function (f) { return !sim.mexidos[f.id]; });
    var resto = { lula: alvo.lula, flavio: alvo.flavio, bn: alvo.bn };
    presas.forEach(function (f) { DEST.forEach(function (k) { resto[k] -= sim.fatia[f.id][k] * f.v; }); });
    var estouro = DEST.filter(function (k) { return resto[k] < 0; });
    if (!presas.length) {
      ipf(fs, alvo);
      return { ok: true, txt: "Ajustei as " + fs.length + " fontes na proporção do seu cenário." };
    } else if (livres.length && !estouro.length) {
      ipf(livres, resto);
      var nomes = presas.map(function (f) { return f.nome; });
      return { ok: true, txt: "Ajustei só as fontes que você não mexeu; " + nomes.join(", ") +
        (nomes.length > 1 ? " ficaram" : " ficou") + " como você deixou." };
    } else {
      var motivo = estouro.length
        ? "só as fontes que você mexeu já mandam " + mi(alvo[estouro[0]] - resto[estouro[0]]) + " para " +
          NOME_DEST[estouro[0]] + ", mais que os " + mi(alvo[estouro[0]]) + " que ele ganhou"
        : "você mexeu em todas as fontes e não sobrou nenhuma para ajustar";
      ipf(fs, alvo);
      sim.mexidos = {};
      return { ok: false, txt: "Do jeito que estava não fecha: " + motivo + ". Ajustei todas, inclusive as que você mexeu." };
    }
  }

  // ── as histórias prontas ────────────────────────────────────────────────
  // Cada uma é um clique que monta um cenário e diz, numa frase, o que ele
  // mostra. "Toda para o Flavio" é de propósito impossível: é o mínimo de
  // 60% visto pelo avesso.
  function fonteRenan() {
    return fontesSim().filter(function (f) { return /renan/i.test(f.nome); })[0];
  }
  var HISTORIAS = [
    { id: "modelo", rot: "Estimativa do modelo", fazer: function () {
      sim.fatia = copiar(sim.partida); sim.mexidos = {};
      sim.status = { ok: true, txt: "Ponto de partida: a estimativa de cada candidato, ajustada para fechar com o TSE. " +
        "É um cenário possível, não uma medição." };
    } },
    { id: "renan", rot: "E se o Renan anulasse metade?", pode: fonteRenan, fazer: function () {
      var f = fonteRenan();
      sim.fatia = copiar(sim.partida); sim.mexidos = {};
      var x = sim.fatia[f.id], r = x.lula + x.flavio ? x.lula / (x.lula + x.flavio) : 0;
      sim.fatia[f.id] = { lula: 0.5 * r, flavio: 0.5 * (1 - r), bn: 0.5 };
      sim.mexidos[f.id] = true;
      ajustarTravado();
      fecharConta();
      if (sim.status.ok) sim.status = { ok: true, txt: "Metade dos " + mi(f.v) + " do Renan foi para branco/nulo, " +
        "e a conta ainda fecha: as outras fontes se ajustaram (compare as barras com o ponto de partida). " +
        "O dado não descarta essa história, nem a confirma." };
    } },
    { id: "flavio", rot: "E se a terceira via fosse toda para o Flavio?", fazer: function () {
      sim.fatia = copiar(sim.partida); sim.mexidos = {};
      var paraFlavio = 0;
      fontesSim().forEach(function (f) {
        if (f.fam !== "terceira") return;
        var x = sim.fatia[f.id];
        sim.fatia[f.id] = { lula: 0, flavio: 1 - x.bn, bn: x.bn };
        sim.mexidos[f.id] = true;
        paraFlavio += (1 - x.bn) * f.v;
      });
      ajustarTravado();
      sim.status = { ok: false, txt: "Não fecha, e nenhum ajuste salva: só a terceira via mandaria " + mi(paraFlavio) +
        " ao Flavio, mais que todo o ganho dele entre os turnos (" + mi(alvosSim().flavio) + "). " +
        "É o mínimo de 60% para o Lula visto pelo avesso." };
    } },
  ];

  // ── o cartão principal: desenho completo + placar + linhas ──────────────
  var hib = { host: null, foco: null, placar: null, selo: null, linhas: null, status: null, chips: null, fixo: null };

  function svgCompleto(W) {
    var fs = fontesSim(), c = contaSim(), n = d.nacional || {}, estreito = W < 560;
    var STUB = estreito ? 26 : 32;
    var fontes = [{ id: "lula1", px: STUB, cor: COR.lula, quebra: true,
      linhas: [estreito ? "Lula 1º t." : "Lula no 1º turno", mi(n.lula1) + " ≈", estreito ? null : "fora de escala"] }];
    fs.forEach(function (f, i) {
      fontes.push({ id: f.id, v: f.v, vao: i === 0 || f.fam !== fs[i - 1].fam ? 16 : 4,
        linhas: [estreito ? f.curto : f.nome, mi(f.v)] });
    });
    fontes.push({ id: "flavio1", px: STUB, cor: COR.flavio, quebra: true, vao: 16,
      linhas: [estreito ? "Flavio 1º t." : "Flavio no 1º turno", mi(n.flavio1) + " ≈", estreito ? null : "fora de escala"] });

    var ganho = function (k, b) { return estreito ? mi2(b) + " + " + mi2(c.S[k]) : "já tinha " + mi2(b) + " + ganhou " + mi2(c.S[k]); };
    var destinos = [
      { id: "lula", v: c.S.lula, alvo: c.alvo.lula, cor: COR.lula, base: { px: STUB },
        linhas: ["Lula", mi(n.lula1 + c.S.lula), ganho("lula", n.lula1)] },
      { id: "bn", v: c.S.bn, alvo: c.alvo.bn, cor: COR.bn,
        linhas: ["Branco/nulo", mi(c.S.bn), estreito ? null : "nenhum dos dois"] },
      { id: "flavio", v: c.S.flavio, alvo: c.alvo.flavio, cor: COR.flavio, base: { px: STUB, noFim: true },
        linhas: ["Flavio", mi(n.flavio1 + c.S.flavio), ganho("flavio", n.flavio1)] },
    ];

    var fluxos = [{ de: "lula1", para: "lula", px: STUB, cor: COR.lula, op: 0.16,
      titulo: "Lula no 1º turno → Lula: " + mi(n.lula1) + " ficaram (fora de escala)" }];
    fs.forEach(function (f) {
      DEST_DESENHO.forEach(function (k) {
        var v = sim.fatia[f.id][k] * f.v;
        fluxos.push({ de: f.id, para: k, v: v, cor: COR[k], op: k === "bn" ? 0.45 : 0.42,
          titulo: f.nome + " → " + NOME_DEST[k] + ": " + mi(v) + " (" + pc(100 * sim.fatia[f.id][k], 0) + ")" });
      });
    });
    fluxos.push({ de: "flavio1", para: "flavio", px: STUB, cor: COR.flavio, op: 0.16,
      titulo: "Flavio no 1º turno → Flavio: " + mi(n.flavio1) + " ficaram (fora de escala)" });

    return sankeyH({ W: W, H: estreito ? 470 : 500, vao: 22,
      rotE: estreito ? 114 : 176, rotD: estreito ? 92 : 190, classe: "ap-hib-svg", minPx: 1.5,
      rotulo: "Para onde foi cada voto do 1º turno: dez fontes à esquerda, Lula, branco/nulo e Flavio no 2º turno à direita",
      fontes: fontes, destinos: destinos, fluxos: fluxos });
  }

  // Foco: passar o mouse (ou tocar) numa fonte ou num destino acende só as
  // faixas dele e escreve os números na linha de baixo. Clicar fixa o foco
  // (clicar de novo solta); ele sobrevive ao redesenho de cada arrasto.
  function textoFoco(id) {
    var n = d.nacional || {}, c = contaSim(), fs = fontesSim();
    var f = fs.filter(function (x) { return x.id === id; })[0];
    if (f) {
      var x = sim.fatia[f.id];
      var partes = DEST.map(function (k) { return NOME_DEST[k] + " " + pc(100 * x[k], 0) + " (" + mi(x[k] * f.v) + ")"; });
      var mod = f.ic ? " Modelo: " + pc(100 * f.est, 0) + " para o Lula, intervalo de " + pc(100 * f.ic[0], 0) + " a " +
        pc(100 * f.ic[1], 0) + (f.medido ? "." : f.borda ? " (preso na borda do ajuste)." : ": o dado não decide.") : "";
      return f.nome + " · " + mi(f.v) + " no 1º turno → " + partes.join(" · ") + "." + mod +
        (f.membros ? " São: " + f.membros + "." : "");
    }
    if (id === "lula1" || id === "flavio1") {
      var t = (d.transicao || {}).troca || {};
      return (id === "lula1" ? "Lula" : "Flavio") + " no 1º turno · " + mi(id === "lula1" ? n.lula1 : n.flavio1) +
        ". No desenho, esses votos ficam com ele: a troca direta medida entre os dois é praticamente zero" +
        (t.votos_ic ? " (intervalo de 0 a " + mi(t.votos_ic[1]) + ")" : "") + ". O bloco está fora de escala.";
    }
    if (NOME_DEST[id]) {
      var deonde = fs.map(function (x) { return { nm: x.curto, v: sim.fatia[x.id][id] * x.v }; })
        .filter(function (x) { return x.v >= 5000; })
        .sort(function (a, b) { return b.v - a.v; });
      var lista = deonde.slice(0, 5).map(function (x) { return x.nm + " " + mi2(x.v); }).join(" · ") +
        (deonde.length > 5 ? " e mais " + (deonde.length - 5) : "");
      var basev = id === "lula" ? n.lula1 : id === "flavio" ? n.flavio1 : 0;
      return NOME_DEST[id] + " no 2º turno · " + mi(basev + c.S[id]) + " no seu cenário (TSE: " + mi(basev + c.alvo[id]) + ")" +
        (basev ? " = " + mi(basev) + " que já eram dele + " + mi(c.S[id]) + " de fora" : "") + ". Vieram de: " + lista + ".";
    }
    return "Passe o mouse (ou toque) numa fonte ou num destino para ver só os votos dele. Clique para fixar.";
  }

  function aplicarFoco(svg, id) {
    if (!svg) return;
    svg.classList.toggle("foco", !!id);
    Array.prototype.forEach.call(svg.querySelectorAll(".ap-cam-faixa"), function (p) {
      p.classList.toggle("on", !!id && (p.getAttribute("data-de") === id || p.getAttribute("data-para") === id));
    });
    hib.foco.textContent = textoFoco(id);
  }

  function ligarFoco(svg) {
    var alvoDe = function (ev) { var a = ev.target.closest && ev.target.closest("[data-no]"); return a ? a.getAttribute("data-no") : null; };
    svg.addEventListener("pointerover", function (ev) { var id = alvoDe(ev); if (id) aplicarFoco(svg, id); });
    svg.addEventListener("pointerleave", function () { aplicarFoco(svg, hib.fixo); });
    svg.addEventListener("click", function (ev) {
      var id = alvoDe(ev);
      hib.fixo = id && hib.fixo !== id ? id : null;
      aplicarFoco(svg, hib.fixo);
    });
  }

  function redesenharCompleto() {
    var W = larguraDe(hib.host, 1180);
    if (!W) return;
    hib.host.textContent = "";
    var svg = svgCompleto(W);
    hib.host.appendChild(svg);
    ligarFoco(svg);
    aplicarFoco(svg, hib.fixo);
  }
  var quadro = 0;
  function agendarDesenho() {
    if (quadro) return;
    quadro = requestAnimationFrame(function () { quadro = 0; redesenharCompleto(); });
  }

  function pintarPlacar() {
    var c = contaSim(), n = d.nacional || {};
    var basev = { lula: n.lula1 || 0, flavio: n.flavio1 || 0, bn: 0 };
    hib.placar.textContent = "";
    DEST_DESENHO.forEach(function (k) {
      var dif = c.dif[k], ok = Math.abs(dif) < 15000;
      hib.placar.appendChild(h("span", { class: "ap-plc-item" + (ok ? "" : " fora"), vars: { "--cor": COR[k] },
        title: "Resultado oficial: " + mi(basev[k] + c.alvo[k]) },
        h("b", { text: NOME_DEST[k] }),
        h("span", { class: "ap-plc-v", text: mi(basev[k] + c.S[k]) }),
        h("span", { class: "ap-plc-dif " + (ok ? "ok" : "falta"),
          text: ok ? "✓" : (dif > 0 ? "sobram " : "faltam ") + mm(Math.abs(dif)) })));
    });
    hib.selo.className = "ap-plc-selo " + (c.fecha ? "ok" : "falta");
    hib.selo.textContent = c.fecha ? "✓ fecha com o TSE" : "não fecha: " + mm(c.fora) + " no lugar errado";
  }

  function pintarStatus() {
    hib.status.className = "ap-hib-status " + (sim.status ? (sim.status.ok ? "ok" : "aviso") : "");
    hib.status.textContent = sim.status ? sim.status.txt : "";
    hib.status.hidden = !sim.status;
    Array.prototype.forEach.call(hib.chips.querySelectorAll("[data-historia]"), function (b) {
      b.classList.toggle("on", b.getAttribute("data-historia") === sim.historia);
    });
  }

  // Tudo que muda o cenário inteiro (história, fechar, voltar) passa aqui.
  function atualizarTudo() {
    montarLinhas();
    pintarPlacar();
    pintarStatus();
    redesenharCompleto();
  }

  // ── a barra de três cores, com duas divisas arrastáveis ─────────────────
  // Lula | Flavio | branco/nulo. A divisa A separa Lula de Flavio; a B separa
  // Flavio de branco/nulo. Clicar na barra leva a divisa mais próxima até ali.
  // No toque, só gesto horizontal mexe (o vertical continua rolando a página);
  // um toque parado também leva a divisa — é intenção, não rolagem.
  function barra3(f, aoMudar) {
    var segs = DEST.map(function (k) { return h("span", { class: "ap-b3-seg", vars: { "--cor": COR[k] } }); });
    var alcas = ["Divisa entre Lula e Flavio", "Divisa entre Flavio e branco/nulo"].map(function (rot) {
      return h("span", { class: "ap-b3-alca", role: "slider", tabindex: "0", "aria-label": rot + " — " + f.nome,
        "aria-valuemin": "0", "aria-valuemax": "100" });
    });
    var ic = f.ic ? [h("span", { class: "ap-b3-ic", vars: { "--de": (100 * f.ic[0]) + "%", "--ate": (100 * f.ic[1]) + "%" },
        title: "Modelo: " + pc(100 * f.est, 0) + " para o Lula (intervalo " + pc(100 * f.ic[0], 0) + "–" + pc(100 * f.ic[1], 0) + ")" }),
      h("span", { class: "ap-b3-est", vars: { "--p": (100 * f.est) + "%" } })] : [];
    var el = h("div", { class: "ap-b3" }, segs, ic, alcas);
    // Fonte travada: o pedaço branco/nulo sai da conta, não se arrasta. Fica
    // só a divisa Lula | Flavio.
    if (f.travado) {
      segs[2].classList.add("travado");
      alcas[1].classList.add("oculta");
      alcas[1].setAttribute("tabindex", "-1");
      alcas[1].setAttribute("aria-hidden", "true");
      alcas[0].setAttribute("aria-label", "Divisa entre Lula e Flavio — " + f.nome + " (o branco/nulo é travado pela conta)");
    }

    function pos() {
      var x = sim.fatia[f.id], a = x.lula, b = x.lula + x.flavio;
      segs[0].style.width = (100 * x.lula) + "%";
      segs[1].style.width = (100 * x.flavio) + "%";
      segs[2].style.width = (100 * x.bn) + "%";
      alcas[0].style.left = (100 * a) + "%";
      alcas[1].style.left = (100 * b) + "%";
      alcas[0].setAttribute("aria-valuenow", String(Math.round(100 * a)));
      alcas[0].setAttribute("aria-valuetext", "Lula " + pc(100 * x.lula, 0) + ", Flavio " + pc(100 * x.flavio, 0));
      alcas[1].setAttribute("aria-valuenow", String(Math.round(100 * b)));
      alcas[1].setAttribute("aria-valuetext", "Flavio " + pc(100 * x.flavio, 0) + ", branco/nulo " + pc(100 * x.bn, 0));
    }
    function definir(qual, frac) {
      var x = sim.fatia[f.id], a = x.lula, b = x.lula + x.flavio;
      frac = Math.round(1000 * preso01(frac)) / 1000;
      if (f.travado) {
        if (qual === 1) return;
        x.lula = Math.min(frac, 1 - x.bn); x.flavio = 1 - x.bn - x.lula;
        pos(); aoMudar();
        return;
      }
      if (qual === 0) a = Math.min(frac, b); else b = Math.max(frac, a);
      x.lula = a; x.flavio = b - a; x.bn = 1 - b;
      pos(); aoMudar();
    }
    function fracDe(ev) { var r = el.getBoundingClientRect(); return (ev.clientX - r.left) / r.width; }
    function qualDe(ev, frac) {
      if (f.travado || ev.target === alcas[0]) return 0;
      if (ev.target === alcas[1]) return 1;
      var x = sim.fatia[f.id], a = x.lula, b = x.lula + x.flavio;
      if (Math.abs(a - b) < 1e-6) return frac > a ? 1 : 0;
      return Math.abs(frac - a) <= Math.abs(frac - b) ? 0 : 1;
    }
    var gesto = null;   // { id, x0, y0, qual, ativo, toque }
    function capturar(id) { try { el.setPointerCapture(id); } catch (e) { /* ponteiro que já acabou */ } }
    el.addEventListener("pointerdown", function (ev) {
      var frac = fracDe(ev);
      gesto = { id: ev.pointerId, x0: ev.clientX, y0: ev.clientY, qual: qualDe(ev, frac),
                toque: ev.pointerType === "touch", ativo: ev.pointerType !== "touch" };
      if (gesto.ativo) {
        capturar(ev.pointerId);
        definir(gesto.qual, frac);
        alcas[gesto.qual].focus({ preventScroll: true });
        ev.preventDefault();
      }
    });
    el.addEventListener("pointermove", function (ev) {
      if (!gesto || ev.pointerId !== gesto.id) return;
      if (!gesto.ativo) {
        var dx = Math.abs(ev.clientX - gesto.x0), dy = Math.abs(ev.clientY - gesto.y0);
        if (dx > 6 && dx > dy) { gesto.ativo = true; capturar(ev.pointerId); }
        else return;
      }
      definir(gesto.qual, fracDe(ev));
    });
    el.addEventListener("pointerup", function (ev) {
      if (gesto && gesto.toque && !gesto.ativo &&
          Math.abs(ev.clientX - gesto.x0) < 6 && Math.abs(ev.clientY - gesto.y0) < 6) {
        definir(gesto.qual, fracDe(ev));
      }
      gesto = null;
    });
    el.addEventListener("pointercancel", function () { gesto = null; });
    alcas.forEach(function (alca, i) {
      alca.addEventListener("keydown", function (ev) {
        var x = sim.fatia[f.id], v = i ? x.lula + x.flavio : x.lula, passo = ev.shiftKey ? 0.05 : 0.01;
        if (ev.key === "ArrowLeft" || ev.key === "ArrowDown") v -= passo;
        else if (ev.key === "ArrowRight" || ev.key === "ArrowUp") v += passo;
        else if (ev.key === "Home") v = 0;
        else if (ev.key === "End") v = 1;
        else return;
        ev.preventDefault();
        definir(i, v);
      });
    });
    pos();
    el.pos = pos;
    return el;
  }

  var repintar = {};   // id → redesenha a linha (a travada muda quando as outras mudam)

  function linhaFonte(f) {
    var nums = h("div", { class: "ap-hib-nums" });
    var linha;
    var painel = h("div", { class: "ap-hib-painel", hidden: true });
    function pintarNums() {
      var x = sim.fatia[f.id];
      nums.textContent = "";
      DEST.forEach(function (k) {
        nums.appendChild(h("span", { vars: { "--cor": COR[k] },
          text: (k === "bn" ? "br./nulo" : NOME_DEST[k]) + " " + pc(100 * x[k], 0) + (k === "bn" && f.travado ? " (travado)" : "") }));
      });
    }
    function mudou() {
      sim.mexidos[f.id] = true;
      sim.historia = null;
      sim.status = null;
      linha.classList.add("mexido");
      ajustarTravado();
      fontesSim().forEach(function (g) { if (g.travado && repintar[g.id]) repintar[g.id](); });
      pintarNums(); sincronizarPainel();
      pintarPlacar(); pintarStatus(); agendarDesenho();
    }
    var barra = barra3(f, mudou);

    // Os controles finos: dois deslizantes (Lula e branco/nulo; o Flavio é o
    // que sobra). Para quem não acerta a divisa com o dedo.
    var inL = h("input", { type: "range", min: "0", max: "100", step: "1", "aria-label": "Parte de " + f.nome + " que foi para o Lula",
      oninput: function (ev) { fino("lula", parseFloat(ev.target.value) / 100); } });
    var inB = h("input", { type: "range", min: "0", max: "100", step: "1", "aria-label": "Parte de " + f.nome + " que votou branco ou nulo",
      oninput: function (ev) { fino("bn", parseFloat(ev.target.value) / 100); } });
    function sincronizarPainel() {
      var x = sim.fatia[f.id];
      inL.value = String(Math.round(100 * x.lula));
      inB.value = String(Math.round(100 * x.bn));
    }
    function fino(campo, v) {
      var x = sim.fatia[f.id];
      v = preso01(v);
      if (f.travado) {
        x.lula = Math.min(v, 1 - x.bn); x.flavio = 1 - x.bn - x.lula;
        barra.pos(); mudou();
        return;
      }
      if (campo === "lula") { x.lula = v; if (x.lula + x.bn > 1) x.bn = 1 - v; }
      else { x.bn = v; if (x.lula + x.bn > 1) x.lula = 1 - v; }
      x.flavio = Math.max(0, 1 - x.lula - x.bn);
      barra.pos();
      mudou();
    }
    painel.appendChild(h("label", { class: "ap-hib-fino" }, h("span", { vars: { "--cor": COR.lula }, text: "Lula" }), inL));
    if (!f.travado) painel.appendChild(h("label", { class: "ap-hib-fino" }, h("span", { vars: { "--cor": COR.bn }, text: "Branco/nulo" }), inB));
    painel.appendChild(h("p", { class: "ap-hib-fino-nota", text: f.travado
      ? "O branco/nulo é travado pela conta; o Flavio fica com o que sobra." : "O Flavio fica com o que sobra." }));
    sincronizarPainel();
    repintar[f.id] = function () { barra.pos(); pintarNums(); sincronizarPainel(); };

    var selo = null;
    if (f.fam === "terceira" && f.est != null && f.ic) {
      selo = f.medido ? h("span", { class: "ap-cd-selo ok", text: "medido" })
        : f.borda ? h("span", { class: "ap-cd-selo borda", text: "na borda" })
        : h("span", { class: "ap-hib-selo", text: "o dado não decide" });
    }
    var meta = f.ic ? "modelo " + pc(100 * f.est, 0) + " para o Lula (" + pc(100 * f.ic[0], 0) + "–" + pc(100 * f.ic[1], 0) + ")"
      : f.membros ? f.membros
      : f.travado ? "branco " + mi(f.partes[0]) + " + nulo " + mi(f.partes[1]) + ". O pedaço riscado é travado: é o branco/nulo do 2º turno (" +
          mi(alvosSim().bn) + ") menos o que as outras fontes mandaram para lá. Você divide o resto entre Lula e Flavio."
      : f.nota || "";
    linha = h("div", { class: "ap-hib-linha" + (sim.mexidos[f.id] ? " mexido" : "") },
      h("div", { class: "ap-hib-quem" },
        h("button", { type: "button", class: "ap-hib-nome", "aria-expanded": "false",
          title: "Ajustar com controles deslizantes",
          onclick: function (ev) {
            painel.hidden = !painel.hidden;
            ev.currentTarget.setAttribute("aria-expanded", painel.hidden ? "false" : "true");
          } }, h("b", { text: f.nome }), h("span", { class: "ap-hib-v", text: mi(f.v) })),
        selo,
        meta ? h("span", { class: "ap-hib-meta", text: meta }) : null),
      barra, nums, painel);
    pintarNums();
    return linha;
  }

  function montarLinhas() {
    var fs = fontesSim();
    hib.linhas.textContent = "";
    repintar = {};
    [["terceira", "Terceira via", "quem votou nos 10 que não passaram"],
     ["novos", "Quem não tinha escolhido candidato", "faltou, votou branco ou anulou no 1º turno"]].forEach(function (fam) {
      var gs = fs.filter(function (f) { return f.fam === fam[0]; });
      if (!gs.length) return;
      hib.linhas.appendChild(h("div", { class: "ap-hib-fam" }, h("b", { text: fam[1] }), h("span", { text: fam[2] })));
      gs.forEach(function (f) { hib.linhas.appendChild(linhaFonte(f)); });
    });
  }

  function cartaoCompleto() {
    var n = d.nacional || {}, t = (d.transicao || {}).troca || {};
    hib.host = h("div", { class: "ap-cam-host ap-hib-host" });
    hib.foco = h("p", { class: "ap-hib-foco", "aria-live": "polite", text: textoFoco(null) });
    hib.placar = h("div", { class: "ap-plc-itens" });
    hib.selo = h("span", { class: "ap-plc-selo" });
    hib.status = h("p", { class: "ap-hib-status", hidden: true });
    hib.linhas = h("div", { class: "ap-hib-linhas" });
    hib.chips = h("div", { class: "ap-hib-chips" },
      h("span", { class: "ap-hib-chips-rot", text: "Histórias prontas:" }),
      HISTORIAS.filter(function (x) { return !x.pode || x.pode(); }).map(function (x) {
        return h("button", { type: "button", class: "ap-conta-chip", "data-historia": x.id, text: x.rot,
          onclick: function () { x.fazer(); sim.historia = x.id; atualizarTudo(); } });
      }));

    var c = cartao("Para onde foi cada voto do 1º turno",
      "À esquerda, como se votou em 04/10; à direita, em 25/10. A altura dos blocos é a contagem do TSE; " +
      "a divisão das faixas é uma estimativa, e você pode mudá-la logo abaixo.",
      hib.host,
      hib.foco,
      h("div", { class: "ap-hib-leg" },
        h("span", { class: "faixa", text: "faixa: votos que foram de uma fonte a um destino (estimativa)" }),
        h("span", { class: "quebra", text: "≈ fora de escala: os " + mi2(n.lula1) + " e " + mi2(n.flavio1) + " mi que já eram dos dois" }),
        h("span", { class: "alvo", text: "contorno tracejado: o resultado oficial" })),
      h("div", { class: "ap-hib-placar" },
        h("div", { class: "ap-hib-placar-topo" },
          hib.placar,
          hib.selo,
          h("div", { class: "ap-hib-acoes" },
            h("button", { type: "button", class: "ap-btn ap-btn-primario", text: "Fechar a conta",
              title: "Ajusta as fontes que você não mexeu até os três totais baterem com o TSE",
              onclick: function () { fecharConta(); sim.historia = null; atualizarTudo(); } }),
            h("button", { type: "button", class: "ap-btn", text: "Voltar ao início",
              onclick: function () { HISTORIAS[0].fazer(); sim.historia = "modelo"; atualizarTudo(); } })))),
      h("h3", { class: "ap-hib-titulo", text: "Mude a divisão de cada fonte" }),
      h("p", { class: "ap-hib-dica", text: "Arraste as divisas da barra (ou use as setas do teclado). " +
        "Toque no nome para ajustar com controles deslizantes. A linha laranja acima da barra é o intervalo do modelo para o Lula." }),
      hib.chips,
      hib.status,
      hib.linhas,
      h("p", { class: "ap-conta-fonte", text: "Lula e Flavio do 1º turno ficam com eles: a troca direta medida é praticamente zero" +
        (t.votos_ic ? " (intervalo de 0 a " + mi(t.votos_ic[1]) + ")" : "") +
        ". Fonte: totais do TSE nos dois turnos; estimativa por candidato com a votação por seção agregada por município." }));
    c.classList.add("ap-hib");
    montarLinhas();
    pintarPlacar();
    pintarStatus();
    return c;
  }

  // ── seções recolhidas ───────────────────────────────────────────────────
  function secao(titulo, resumo, conteudo, aoAbrir) {
    return h("details", { class: "ap-sec", ontoggle: aoAbrir ? function (ev) { if (ev.target.open) aoAbrir(); } : null },
      h("summary", { class: "ap-sec-topo" },
        h("span", { class: "ap-sec-seta", "aria-hidden": "true" }),
        h("span", { class: "ap-sec-titulo", text: titulo }),
        resumo ? h("span", { class: "ap-sec-resumo", text: resumo }) : null),
      h("div", { class: "ap-sec-corpo" }, conteudo));
  }

  // A lista das 5.570 cidades (~650 KB) só desce quando a seção abre, e quem
  // monta o cartão é o `apuracao_conta.js` — o MESMO módulo que guarda a lista.
  // (Antes esta página baixava a lista para si e o cartão lia a cópia do outro
  // módulo, que nunca chegava: "Cidade não encontrada" até para Joinville.)
  function secaoCidades() {
    var corpo = h("div", {}, h("p", { class: "ap-carregando", text: "Abrindo a lista das cidades…" }));
    return secao("A conta na sua cidade", "busque o município", corpo, function () {
      if (!blocos.carregarMunicipios || !blocos.cidades) return;
      blocos.carregarMunicipios(function () {
        corpo.textContent = "";
        corpo.appendChild(blocos.cidades(d));
      });
    });
  }

  // ── a vista ─────────────────────────────────────────────────────────────
  var ouvindoTamanho = false;
  function ouvirTamanho() {
    if (ouvindoTamanho) return;
    ouvindoTamanho = true;
    var timer = null, ultimo = window.innerWidth;
    window.addEventListener("resize", function () {
      if (window.innerWidth === ultimo) return;
      ultimo = window.innerWidth;
      clearTimeout(timer);
      timer = setTimeout(function () { redesenharCompleto(); redesenharCaminho(); }, 150);
    });
  }

  function vista(APx) {
    AP = APx; h = AP.h; s = AP.s; num = AP.num; cartao = AP.cartao;
    blocos = window.AP_BLOCOS || {};
    // Cada módulo precisa receber o AP antes de montar seus blocos (é o que
    // define h/cartao/s lá dentro).
    if (blocos.iniciar_conta) blocos.iniciar_conta(AP);
    if (blocos.iniciar_sankey) blocos.iniciar_sankey(AP);
    if (blocos.iniciar_acusacoes) blocos.iniciar_acusacoes(AP);
    if (!d) {
      if (erro) {
        setTimeout(function () { erro = null; pedindo = false; carregar(); }, 2500);
        return [cartao("Abrindo a conta…", "", h("p", { text: "O arquivo não respondeu agora. Tentando de novo sozinho." }))];
      }
      carregar();
      return [h("p", { class: "ap-carregando", text: "Abrindo a conta do 2º turno…" })];
    }
    if (!sim) iniciarSim();
    ouvirTamanho();
    var b = base(), conf = d.conferencia || {}, tr = d.transicao || {};
    var caiu = (d.ufs || []).filter(function (u) { return u.variacao < 0; }).length;
    var out = [
      blocos.abertura ? blocos.abertura(d) : null,
      cartaoCompleto(),
      blocos.acusacoes ? blocos.acusacoes() : null,
      secao("O que a aritmética garante", "a terceira via deu ao Lula pelo menos " + pc(100 * b.qmin, 1),
        [cartaoCaminho(), blocos.limite ? blocos.limite(d) : null], redesenharCaminho),
      blocos.transicao ? secao("Cada candidato: como o modelo estima",
        tr.ok ? tr.identificados + " de " + tr.total + " com intervalo que decide" : null, blocos.transicao(d)) : null,
      secao("Quanto se votou nos dois turnos", "+" + mm(d.novos_validos) + " votos válidos · caiu em " + caiu + " estados",
        [blocos.comparecimento ? blocos.comparecimento(d) : null,
         blocos.comparecimentoUf ? blocos.comparecimentoUf(d) : null]),
      secaoCidades(),
      secao("Como conferimos, e o que a página não faz",
        (conf.fecham || 0) + " de " + (conf.total || 0) + " fecham ao voto",
        [blocos.conferencia ? blocos.conferencia(d) : null, blocos.metodo ? blocos.metodo(d) : null]),
    ];
    // O SVG é desenhado na largura real da caixa, em pixels: o texto sai no
    // tamanho escrito em qualquer tela.
    setTimeout(redesenharCompleto, 0);
    return out;
  }

  window.AP_EXTRAS = window.AP_EXTRAS || {};
  window.AP_EXTRAS.conta = vista;
  window.AP_EXTRAS.analise = vista;
  if (AP && AP.app.estado && AP.app.vista === "conta") AP.desenhar();
})();
