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
  // Variação em pontos percentuais, com 3 casas (51,6% → 51,8% é 0,2 ponto).
  // Sempre por extenso: "pp" só aparece em texto de método, nunca no número solto.
  function ppNum(x) {
    return x.toLocaleString("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 }) + " ponto percentual";
  }
  // Número com sinal (+/−). Não confundir com o beacon `sinal(e, a)` abaixo:
  // os dois chamados `sinal` no mesmo escopo faziam a formatação devolver undefined.
  function comSinal(x) { return (x > 0 ? "+" : x < 0 ? "−" : "") + num(Math.abs(x)); }
  function mi(x) { return (x / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " mi"; }
  function pedir(arquivo) {
    return fetch(BASE + arquivo + (VERSAO ? "?v=" + encodeURIComponent(VERSAO) : ""))
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  }
  // ── peças de um caso ───────────────────────────────────────────────────
  // o = {id, titulo, alegacao, tag, video?, icone?, fontes?: [{rot, url?}], checagem?, situacao?, veredito,
  //      pontos: [..], visual?, mais?: [{rot, corpo, classe}]}
  var TAG = {
    estranho: { rot: "Verdade e estranho", cls: "parcial" },
    falsa: { rot: "Premissa falsa", cls: "falso" },
    normal: { rot: "Verdade, mas normal", cls: "ok" },
  };
  // Um ícone por ponto da resposta, na ordem (lê melhor que um marcador igual para todos).
  var ICONES = {
    "virada": ["🆕", "✅", "📈", "🗺️", "🧮"], "pesquisas": ["✅", "📏", "🎲", "🗳️"],
    "secoes-10": ["❌", "🔁", "🏘️", "⚖️"], "curva": ["📅", "🕒", "📐", "🔀", "🧮", "✂️"],
    "biometria": ["🕔", "📉", "🧮", "🔒", "📄", "📈", "🖐️"], "mesario": ["🪪", "🕔", "🚨", "💬"],
    "sala-cofre": ["🔒", "❓", "🧾"], "caminhonete": ["🎥", "📤", "🧾"],
    "silva-jardim": ["➖", "🔀", "🔎", "🗺️", "🏖️", "🔁"], "soma": ["⏱️", "✅"], "consulta": ["📅", "⏳", "🚫", "🪦"],
    "mesma-secao": ["🚫", "🔍", "📉"], "zonas": ["📍", "📱", "🗺️"], "cedula": ["🗳️", "🔢", "⚖️"],
    "eleitores": ["✅", "🚚", "🏠"], "prorrogacao": ["⏰", "🌧️", "📉", "🕰️"], "desfile": ["💰", "🛑", "⚖️"],
    "pacote": ["📆", "📲", "⚖️", "🗳️", "🚫"], "exercito": ["📣", "🔍", "🔁"], "universidades": ["🎓", "📜", "📚", "❔"],
    "mesaria": ["❓", "🚔", "⚖️"], "faccoes": ["🔍", "🗑️", "⚖️"], "compra": ["💵", "📍", "🔎"],
    "padroeira": ["📜", "⛪", "🗣️", "📣", "🔁"],
    "desinformacao": ["⚖️", "🔁", "⏳", "🚫", "🧮"],
    "maquina-celular": ["📲", "✅", "⚖️", "🎓", "🗳️"],
    "onibus": ["🏷️", "🚌", "⏰", "🗳️"],
  };
  var V = null;   // casos_videos.json
  var LADOS = null;   // static/casos/lados.json: quem acusa, quem defende e a decisão de cada caso
  function mil(x) {
    return x >= 1e6 ? (x / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi"
      : x >= 1000 ? Math.round(x / 1000) + " mil" : String(x);
  }
  function capa(o, v) {
    var foto = (v && v.capa) || (V && V.capas && V.capas[o.id] && V.capas[o.id].src);
    // Com ?v=, a capa trocada não fica presa no cache do navegador nem do Cloudflare.
    if (foto && VERSAO) foto += "?v=" + encodeURIComponent(VERSAO);
    var dentro = [foto ? h("img", { src: foto, alt: "", loading: "lazy", width: "360", height: "480" })
      : h("span", { class: "capa-ico", "aria-hidden": "true", text: o.icone || "▶" }),
      v ? h("span", { class: "capa-play", "aria-hidden": "true" }) : null];
    return v ? h("a", { class: "capa", href: v.url, target: "_blank", rel: "noopener nofollow",
      "aria-label": "Ver o vídeo de @" + v.perfil + " no Instagram" }, dentro)
      : h("div", { class: "capa sem-video" }, dentro);
  }
  // Contagem anônima (visitas.py): qual caso foi aberto. Sem cookie, sem IP guardado.
  function sinal(e, a) {
    try { navigator.sendBeacon("/v", new Blob([JSON.stringify({ e: e, a: a })], { type: "application/json" })); } catch (x) { /* sem beacon */ }
  }
  function link(f) {
    return f.url ? h("a", { href: f.url, target: "_blank", rel: "noopener nofollow", text: f.rot }) : h("span", { text: f.rot });
  }
  // Lista em texto corrido: "a, b e c".
  function emLinha(els) {
    var out = [];
    els.forEach(function (el, i) { if (i) out.push(i === els.length - 1 ? " e " : ", "); out.push(el); });
    return out;
  }
  // "Os dois lados": o melhor argumento de quem acusa, a melhor resposta e a decisão.
  function dois(id) {
    var x = LADOS && LADOS.casos[id];
    if (!x) return null;
    return h("details", { class: "mais lados" }, h("summary", { text: "Os dois lados" }),
      h("div", { class: "corpo lados-grade" },
        h("div", { class: "lado-a" }, h("b", { text: "Quem acusa" }), h("p", { text: x.fraude })),
        h("div", { class: "lado-d" }, h("b", { text: "Quem defende" }), h("p", { text: x.defesa })),
        h("div", { class: "lado-j" }, h("b", { text: "Decisão: " + x.juiz.decisao }), h("p", { text: x.juiz.sintese }))));
  }
  function caso(o, n) {
    var v = V && V.videos[o.id], t = TAG[o.tag];
    var art = h("article", { class: "caso", id: "caso-" + o.id });
    function alternar(abrir) {
      var aberto = art.classList.toggle("respondido", abrir);
      ver.setAttribute("aria-expanded", String(aberto));
      if (!aberto && art.getBoundingClientRect().top < 0) art.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    // O cartão inteiro abre e fecha a resposta, menos onde o clique já faz outra coisa.
    art.addEventListener("click", function (ev) {
      if (ev.target.closest("a, button, summary, details, input, svg, .capa, .lados, .visual, .circulou")) return;
      if (window.getSelection && String(window.getSelection()).length) return;
      var abrir = !art.classList.contains("respondido");
      alternar(abrir);
      if (abrir) sinal("caso", o.id);
    });
    var ver = h("button", { class: "btn btn-mini caso-abrir", type: "button", "aria-expanded": "false", "aria-controls": "rev-" + o.id,
      text: "Ver a resposta", onclick: function () { alternar(true); sinal("caso", o.id); } });
    function recolher(onde) {
      return h("button", { class: "recolher " + onde, type: "button", title: "Recolher a resposta", "aria-label": "Recolher a resposta",
        onclick: function () { alternar(false); } }, h("i", { "aria-hidden": "true" }));
    }
    var onde = emLinha([].concat(
      v ? [h("a", { href: v.url, target: "_blank", rel: "noopener nofollow", text: "vídeo de @" + v.perfil + " no Instagram" + (v.curtidas ? " (" + mil(v.curtidas) + " curtidas)" : "") })] : [],
      (o.fontes || []).map(link)));
    anexar(art, [
      o.tag === "estranho" ? h("span", { class: "carimbo", "aria-hidden": "true", text: "estranho" }) : null,
      recolher("cima"),
      h("div", { class: "caso-cab" },
        capa(o, v),
        h("div", { class: "caso-txt" },
          h("div", { class: "caso-topo" }, h("span", { class: "tag " + t.cls, text: t.rot })),
          h("h3", { class: "caso-tit", text: o.titulo }),
          h("p", { class: "alegacao", text: o.alegacao }),
          ver)),
      h("div", { class: "revela", id: "rev-" + o.id }, h("div", {},
        h("span", { class: "veredito " + t.cls, text: o.veredito }),
        o.situacao ? h("p", { class: "situacao", html: "<b>Situação:</b> " + o.situacao }) : null,
        h("ul", { class: "pontos com-icone" }, o.pontos.map(function (p, i) {
          var ic = (ICONES[o.id] || [])[i];
          return h("li", null, h("span", { class: "pt-ico", "aria-hidden": "true", text: ic || "•" }), h("span", { html: p }));
        })),
        o.visual || null,
        dois(o.id),
        (o.mais || []).map(function (m) {
          return h("details", { class: "mais " + (m.classe || "") }, h("summary", { text: m.rot }), h("div", { class: "corpo" }, m.corpo));
        }),
        h("p", { class: "circulou" }, onde.length ? ["Onde circulou: ", onde, ". "] : null,
          o.checagem ? ["Fontes da resposta: ", emLinha(o.checagem.map(link)), "."] : null),
        recolher("baixo"))),
    ]);
    return art;
  }
  function visual(titulo, conteudo, leg) {
    return h("div", { class: "visual" }, titulo ? h("h4", { text: titulo }) : null, conteudo, leg ? h("p", { class: "leg", text: leg }) : null);
  }
  function p(html) { return h("p", { html: html }); }
  function numero(valor, rot, classe) { return h("div", { class: "numero " + (classe || "") }, h("b", { text: valor }), h("span", { text: rot })); }
  // O caminho de uma coisa (o voto, a urna) em 3 ou 4 etapas com seta entre elas.
  function fluxo(itens) {
    return h("ol", { class: "fluxo" }, itens.map(function (t, i) {
      return h("li", null, h("i", { "aria-hidden": "true", text: i + 1 }), h("b", { text: t[0] }), h("span", { text: t[1] }));
    }));
  }
  // Barras simples de dois valores (compara duas eleições).
  function barrasAno(itens) {
    var max = Math.max.apply(null, itens.map(function (x) { return x[1]; }));
    return h("div", { class: "barras-ano" }, itens.map(function (x) {
      return h("div", { class: "ba-lin" }, h("span", { class: "ba-rot", text: x[0] }),
        h("div", { class: "ba-trilho" }, h("i", { style: "width:" + (100 * x[1] / max) + "%" })),
        h("b", { text: "R$ " + x[1].toLocaleString("pt-BR", { minimumFractionDigits: 1 }) + " mi" }));
    }));
  }
  // Três barras por cidade: quem mora, quem tem título e quem votou (2º turno).
  function barrasCidades(itens) {
    var max = Math.max.apply(null, [].concat.apply([], itens.map(function (x) { return [x[1] || 0, x[2], x[3]]; })));
    return h("div", { class: "barras-cid" }, itens.map(function (x) {
      var lin = function (valor, cls, rot) {
        return h("div", { class: "bc-lin" },
          h("span", { class: "bc-rot", text: rot }),
          h("div", { class: "bc-trilho" }, h("i", { class: cls, style: "width:" + (100 * valor / max) + "%" })),
          h("b", { text: num(valor) }));
      };
      return h("div", { class: "bc-cid" }, h("h5", { text: x[0] }),
        x[1] ? lin(x[1], "hab", "Mora") : null,
        lin(x[2], "ele", "Título"), lin(x[3], "vot", "Votou"));
    }));
  }
  // Linha do tempo curta: a data à esquerda e o fato à direita.
  function linhaTempo(itens) {
    return h("ol", { class: "tempo" }, itens.map(function (t) {
      return h("li", { class: t[2] || "" }, h("time", { text: t[0] }), h("span", { html: t[1] }));
    }));
  }

  // ── caso 1: Silva Jardim ───────────────────────────────────────────────
  function silvaJardim(d) {
    var x = d.silva_jardim, m = x.municipio, t1 = m.t1, t2 = m.t2, g = d.teste_do_grok;
    var terc = t1.validos - t1.lula - t1.flavio, bn1 = t1.brancos + t1.nulos;
    var cury = 0, caiado = 0;
    m.terceira.forEach(function (c) { if (/CURY/.test(c.nm)) cury = c.v; if (/CAIADO/.test(c.nm)) caiado = c.v; });
    // As mesmas cidades em 2022. Sem isto o saldo de 2026 sozinho não conta a
    // história: em 2022 o candidato do 22 cresceu mais que o Lula entre os
    // turnos, em 2026 foi o contrário. Cada linha leva o nome do candidato
    // (nada de "22" abreviado) e uma barra com o peso de cada saldo.
    var anoCidade = function (ano, f, l, nomeF) {
      var total = Math.abs(f) + Math.abs(l) || 1;
      return h("div", { class: "cid-bloco" },
        h("div", { class: "cid-saldo" },
          h("span", { class: "ano", text: ano }),
          h("span", { class: "f", text: nomeF + " " + comSinal(f) }),
          h("span", { class: "l", text: "Lula " + comSinal(l) })),
        h("div", { class: "cid-barra", "aria-hidden": "true" },
          h("i", { class: "f", style: "width:" + (100 * Math.abs(f) / total) + "%" }),
          h("i", { class: "l", style: "width:" + (100 * Math.abs(l) / total) + "%" })));
    };
    var cidades = h("div", {},
      h("p", { class: "cid-chave", text: "Saldo de cada candidato entre o 1º e o 2º turno, nas duas eleições. Em 2022, o Bolsonaro cresceu mais que o Lula nessas cidades. Em 2026, o Lula cresceu mais que o Flávio." }),
      h("div", { class: "cidades" }, x.exemplos.map(function (e) {
        var v = d.regua_2022.municipios.exemplos[e.uf + "-" + e.cd];
        return h("div", { class: "cid" },
          h("div", { class: "cid-nome" }, e.nm + " ", h("small", { text: e.uf.toUpperCase() })),
          h("div", { class: "cid-pct" }, pc(e.f2_pct, 1), h("small", { text: " Flávio" })),
          anoCidade("2026", e.d_f, e.d_l, "Flávio"),
          v ? anoCidade("2022", v.f2 - v.f1, v.l2 - v.l1, "Bolsonaro") : null);
      })));
    var pct = function (a, b) { return pc(100 * a / b, 0); };
    return caso({
      id: "silva-jardim", titulo: "Cidades onde o Flávio parou", tag: "normal",
      alegacao: "Em Araruama (RJ), o Flávio ganhou 11 votos entre os turnos e o Lula 5.581. Em Silva Jardim, 1 contra " + num(t2.lula - t1.lula) + ". A chance disso seria de 1 em 10⁴⁶⁸.",
      fontes: [{ rot: "Silva Jardim, no X", url: "https://x.com/lucascrvg_20/status/2115159021606891820" },
               { rot: "Campos, no Instagram", url: "https://www.instagram.com/reel/DfGXIePNOby/" },
               { rot: "Região dos Lagos, no Instagram", url: "https://www.instagram.com/p/DfD8_8tkeBX/" }],
      veredito: "O número confere. A conta, não.",
      pontos: [
        "<b>“+1” é saldo, não o voto que ele recebeu.</b> " + num(t1.comp - t2.comp) + " pessoas a menos votaram no 2º turno. Ganhar 200 e perder 199 dá +1.",
        "<b>Os votos do Lula vieram da terceira via.</b> Eram " + num(terc) + " votos, " + num(cury + caiado) + " deles de Cury e Caiado. Com os " + num(bn1) + " brancos e nulos do 1º turno, a conta fecha sem nenhum eleitor do Flávio virar Lula.",
        "<b>Em Campos dos Goytacazes não há “voto do além”.</b> Os 1.386 votos que o vídeo não acha são os " + num(-V.dados.cidades["CAMPOS DOS GOYTACAZES"].f2 + V.dados.cidades["CAMPOS DOS GOYTACAZES"].f1) + " que o Flávio perdeu lá.",
        "<b>Não é exceção.</b> O Flávio ganhou 0 voto ou perdeu em " + num(x.flavio_ganho_ate_zero) + " cidades; em " + num(x.quase_tudo_lula_com_flavio_60) + " delas, ele tinha vencido com 60% ou mais. Em 2022, o Bolsonaro estava no mesmo lugar em " + num(d.regua_2022.municipios.f_ganho_ate_zero) + ".",
        "<b>As seis cidades da Região dos Lagos também conferem com o TSE</b>, de Cabo Frio a Arraial do Cabo. Em todas, o que o Lula ganhou é menos do que havia de terceira via e branco/nulo no 1º turno (em Cabo Frio, 9.169 contra 14.195). Multiplicar a chance das seis como se fossem sorteios separados não vale: são cidades vizinhas, com o mesmo eleitorado e a mesma campanha.",
        "<b>Quem cresceu mais mudou de candidato.</b> Nas seis cidades do quadro, em 2022 o Bolsonaro ganhou mais votos que o Lula entre os turnos. Em 2026, o Lula ganhou mais que o Flávio.",
      ],
      visual: visual("Municípios parecidos, onde o Flávio venceu com 60% ou mais: 2022 e 2026", cidades,
        "Uma amostra, não o país: das " + num(x.municipios) + " cidades, são as seis em que o Flávio venceu com 60% ou mais e em que o saldo ficou quase todo com o Lula. O saldo é quantos votos cada candidato ganhou (ou perdeu) entre o 1º e o 2º turno."),
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
        "<b>Nenhuma seção caiu de 100 para 10.</b> Seção é a menor unidade da votação: um local, uma urna. Entre as " + num(x.secoes_nos_dois_turnos) + " seções que existiram nos dois turnos, nenhuma teve o Flávio com 100 votos ou mais no 1º turno e 10 ou menos no 2º. Em 2022, a maior queda do Bolsonaro na mesma seção foi de " + d.regua_2022.secoes.maior_queda_f + " votos.",
        "<b>As maiores quedas reais são de uns 100 votos</b>, com o comparecimento caindo junto, em seções rurais do Acre e do Amazonas.",
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
      alegacao: "O mesmo número se repete em cada zona: Lula " + num(dona.l) + " e Flávio " + num(dona.f) + " em várias zonas de Brasília, e igual em Salvador e São Paulo. Isso não existe.",
      fontes: [{ rot: "vídeo no TikTok, repassado no WhatsApp (sem link público)" }],
      veredito: "O número é real, mas de uma zona só",
      pontos: [
        "<b>Lula " + num(dona.l) + " × Flávio " + num(dona.f) + " é o total da zona " + dona.zona + " de " + bsb.nm + "</b>, e só dela. Zona eleitoral é a divisão que agrupa as seções de uma região.",
        "<b>A tela travou.</b> O nome da zona muda, mas os números ficam presos na zona anterior. A autora diz que o app “está demorando um pouquinho”.",
        "<b>No país inteiro, nenhuma zona repete outra.</b> São " + num(x.zonas_pais) + " zonas e " + num(x.placares_repetidos) + " placares repetidos.",
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
      alegacao: "Em " + f2.zeradas + " urnas, ninguém votou no Flávio, nem branco, nem nulo: 100% Lula. Em " + num(f2.secoes) + " seções — cada seção é um local de votação, com a sua urna — ele fez no máximo 10 votos. É como ganhar 579 vezes seguidas na Mega-Sena.",
      fontes: [{ rot: "Folha (via Repórter PB)", url: "https://www.reporterpb.com.br/noticia-extra/2026/10/27/flavio-teve-zero-voto-em-106-urnas-nas-quais-somou-quase-15-mil/136248.html" },
               { rot: "Jornal da Cidade Online" }],
      veredito: "O número confere. Não é sinal de fraude.",
      pontos: [
        "<b>“Sem branco nem nulo” não confere.</b> Das " + V.dados.secoes_zeradas.total + " urnas em que o Flávio não teve voto, só " + V.dados.secoes_zeradas.sem_branco_nulo + " não tiveram nenhum voto branco ou nulo. Somadas, essas " + V.dados.secoes_zeradas.total + " urnas tiveram " + num(V.dados.secoes_zeradas.branco_nulo) + " votos brancos ou nulos. A conta da Mega-Sena também supõe um eleitor sorteado do país inteiro, o que não é o caso de uma aldeia.",
        "<b>Já era assim antes.</b> As seções em que o Flávio fez até 10 votos eram " + pc(100 * f1.secoes / x.secoes_total, 2) + " do total no 1º turno e " + pc(100 * f2.secoes / x.secoes_total, 2) + " no 2º; com o Bolsonaro, em 2022, eram " + pc(100 * r22.t2 / d.regua_2022.secoes.secoes, 2) + ".",
        "<b>São seções pequenas e homogêneas:</b> " + x.comparecimento_medio[0] + " votantes em média (no país, " + x.comparecimento_medio[1] + "), em aldeias, povoados e assentamentos. " + x.zeradas_em_aldeia[0] + " das " + x.zeradas_em_aldeia[1] + " zeradas ficam em aldeia indígena.",
        "<b>Não decidem o resultado:</b> se as " + num(f2.secoes) + " seções fossem anuladas, a vantagem do Lula cairia de " + mi(x.margem) + " para " + mi(x.margem_sem_elas) + ". Continuaria dele.",
      ],
      visual: visual("Seções por número de votos do candidato do PL (Flávio em 2026, Bolsonaro em 2022)", [
        barras(series),
        h("div", { class: "legenda" }, series.map(function (sr) { return h("span", { style: "--c:" + sr.cor, text: sr.rot }); }))],
        "O desenho de 2026 é o mesmo do 1º turno e menor que o de 2022."),
      mais: [{ rot: "Para onde foi o voto nessas seções", corpo: p("Nelas o Lula ganhou " + num(T.l2 - T.l1) + " votos entre os turnos e o Flávio perdeu " + num(T.f1 - T.f2) +
        ". Havia " + num(T.t1) + " votos da terceira via e " + num(T.bn1) + " brancos e nulos no 1º turno, com quase o mesmo número de votantes (" + comSinal(T.c2 - T.c1) + "). A conta fecha no voto.") }],
    });
  }

  // ── caso 5: o "algoritmo" da curva ─────────────────────────────────────
  // O vídeo mostra gráficos de um notebook (Colab): a apuração de 2022 e um
  // zoom que ele lê como "o algoritmo agindo". Os rótulos do eixo do zoom,
  // lidos quadro a quadro, são 0,518 / 0,517 / 0,516 / 0,515 — ou seja, a
  // janela tem 0,3 ponto de altura, não 0,2 (corrigido em 31/10/2026, com o
  // vídeo baixado e medido: o eixo estava sendo suposto, não lido).
  // Aqui: o mesmo recorte (as seções 70.000 a 75.000, ~17h40) redesenhado do
  // arquivo do TSE, na mesma janela de 0,515 a 0,518.
  function grafZoom(n) {
    var z = n.janela.zoom.filter(function (p) { return p[0] >= 70000 && p[0] <= 75000; });
    var W = 420, H = 218, mE = 56, mD = 10, mT = 18, mB = 34;
    var x0 = z[0][0], x1 = z[z.length - 1][0];
    // O MESMO eixo do gráfico do vídeo: os rótulos, lidos quadro a quadro, vão
    // de 0,515 (embaixo) a 0,518 (em cima) — 0,3 ponto de altura. É o ponto do
    // caso: nesses 0,3 ponto cabem 10 vezes a variação do dado oficial.
    var lo = 0.515, hi = 0.518;
    var X = function (x) { return mE + (W - mE - mD) * (x - x0) / (x1 - x0); };
    var Y = function (v) { return mT + (H - mT - mB) * (hi - v) / (hi - lo); };
    var amp = 100 * (max100(z) - min100(z));
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, class: "grafico", role: "img",
      "aria-label": "Fatia do Bolsonaro nas seções 70.000 a 75.000 de 2022, desenhada no eixo do gráfico do vídeo, que vai de 0,515 a 0,518: a linha sai quase reta e varia " + ppNum(amp) });
    [0.515, 0.516, 0.517, 0.518].forEach(function (v) {
      svg.appendChild(s("line", { x1: mE, x2: W - mD, y1: Y(v), y2: Y(v), class: "grade" }));
      svg.appendChild(s("text", { x: mE - 7, y: Y(v) + 4, "text-anchor": "end", class: "eixo", text: v.toFixed(3).replace(".", ",") }));
    });
    [[70000, "start"], [72500, "middle"], [75000, "middle"]].forEach(function (t) {
      svg.appendChild(s("text", { x: X(t[0]) + (t[1] === "start" ? 2 : 0), y: H - 8, "text-anchor": t[1], class: "eixo", text: (t[0] / 1000) + "k" }));
    });
    svg.appendChild(s("text", { x: W - mD, y: mT - 4, "text-anchor": "end", class: "eixo", text: "eixo do vídeo" }));
    svg.appendChild(s("path", { class: "serie bolso", d: z.map(function (p, i) { return (i ? "L" : "M") + X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1); }).join(" ") }));
    return svg;
  }
  function min100(z) { return Math.min.apply(null, z.map(function (p) { return p[1]; })); }
  function max100(z) { return Math.max.apply(null, z.map(function (p) { return p[1]; })); }
  function grafCurva(n) {
    var W = 420, H = 228, mE = 42, mD = 8, mT = 10, mB = 34, y0 = 48, y1 = 57;
    var X = function (v) { return mE + (W - mE - mD) * v / 100; };
    var Y = function (v) { return mT + (H - mT - mB) * (y1 - Math.max(y0, Math.min(y1, v))) / (y1 - y0); };
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, class: "grafico", role: "img",
      "aria-label": "Fatia do Bolsonaro ao longo da apuração de 2022, na ordem em que os boletins chegaram: começa perto de 49%, sobe a 56% e desce até 49%" });
    [48, 50, 52, 54, 56].forEach(function (v) {
      svg.appendChild(s("line", { x1: mE, x2: W - mD, y1: Y(v), y2: Y(v), class: "grade" }));
      svg.appendChild(s("text", { x: mE - 6, y: Y(v) + 4, "text-anchor": "end", class: "eixo", text: v + "%" }));
    });
    [0, 25, 50, 75, 100].forEach(function (v) {
      svg.appendChild(s("text", { x: X(v), y: H - 8, "text-anchor": v === 0 ? "start" : "middle", class: "eixo", text: v + "%" }));
    });
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
    var z = n.janela.zoom.filter(function (p) { return p[0] >= 70000 && p[0] <= 75000; });
    var amp = 100 * (max100(z) - min100(z));
    return caso({
      id: "curva", titulo: "O algoritmo da apuração", tag: "falsa",
      alegacao: "Um candidato que perdeu por 49% a 51% não podia ter uma inversão só: em ordem aleatória, a liderança teria virado várias vezes. E não pode haver tendência de subida dentro da apuração — toda vez que a curva sobe, um algoritmo a derruba. Sem essas quedas, o Bolsonaro teria ganhado com 60% a 65%.",
      fontes: [{ rot: "Aliados Brasil", url: "https://www.aliadosbrasiloficial.com.br/noticia/professor-de-matematica-aponta-supostos-padroes-algoritmicos-na-apuracao-e-estima-que-flavio-bolsonaro-teria-vencido-com-65-dos-votos" }],
      veredito: "É de 2022. As quedas existem, mas são regiões chegando",
      pontos: [
        "<b>O vídeo é de 2022, não desta eleição.</b> Ele fala do Bolsonaro e diz que ele “teria ganhado as eleições com 60 a 65% dos votos”; sobre 2026, só que “estamos sendo roubados novamente”. Quem pôs o número no Flávio foi a legenda do perfil que repostou o vídeo em 28/10.",
        "<b>As quedas existem — e cada uma tem hora e lugar.</b> A urna conta os votos e manda o resultado para o TSE; os resultados chegam por região, não sorteados, e rápido: no trecho do vídeo, quase 180 urnas por segundo. A maior queda é às " + q.hora.slice(0, 5) + ", quando as 400 urnas seguintes deram " + pc(q.bolsonaro_no_lote, 1) + " ao Bolsonaro contra os 51,7% acumulados até ali. Não é o voto que muda: é a leva de urnas que chega, e a maior parte dela era de " + q.lugares.join(", ") + ".",
        "<b>O gráfico dele não é o dado do TSE.</b> No trecho que ele amplia, o eixo vai de 51,5% a 51,8%. Ali, o dado oficial varia " + ppNum(amp).replace(" ponto percentual", " ponto") + " e sai quase reto; o traço do vídeo sobe e desce uns 0,17 ponto, seis vezes mais. Refazendo a conta com os boletins, em várias ordens, o serrote dele não aparece.",
        "<b>Não houve “uma inversão só”.</b> Na ordem do arquivo do TSE, a liderança muda 6 vezes: três com poucos votos contados e três às 18h43, quando a diferença era de 13 a 176 votos em 80 milhões. É empate virando a cada lote de urnas.",
        "<b>Sorteio e apuração real não se comparam.</b> Em ordem sorteada, a liderança troca em média " + t22.trocas_mediana + " vezes, todas antes de " + pc(t22.ultima_troca_max, 1) + " contado. Na apuração real, as urnas chegam por região, e a virada pode vir tarde. Contar inversões não diz nada sobre fraude.",
        "<b>Recortar e colar fabrica qualquer vencedor.</b> Juntar só os trechos em que o Bolsonaro sobe dá " + pc(r.bolsonaro_so_subidas, 1) + " a ele; juntar só os que caem dá " + pc(r.lula_so_quedas, 1) + " ao Lula. O recorte escolhe o vencedor.",
      ],
      visual: [visual("O eixo do gráfico dele (0,515 a 0,518) com o dado do TSE na mesma janela", [
        grafZoom(n),
        h("div", { class: "numeros" },
          numero("0,3", "ponto de altura no eixo do vídeo", "falso"),
          numero(ppNum(amp).replace(" ponto percentual", ""), "ponto de variação no dado do TSE", "ok"),
          numero("18h43", "quando a liderança virou — com 80 milhões de votos contados"))],
        "A linha azul é o dado do TSE — a fatia acumulada do Bolsonaro — desenhada no eixo do gráfico do vídeo. Ela sai quase reta: no mesmo trecho, o dado oficial varia 0,028 ponto, e o eixo do vídeo tem 0,3 ponto de altura. O serrilhado que ele aponta não aparece aí."),
        visual("A apuração de 2022 refeita com os boletins, na ordem de chegada", [
          grafCurva(n),
          h("div", { class: "duelo" },
            h("div", { class: "f" }, h("b", { text: pc(r.bolsonaro_so_subidas, 1) }), h("span", { text: "Bolsonaro, juntando só as subidas dele" })),
            h("div", { class: "l" }, h("b", { text: pc(r.lula_so_quedas, 1) }), h("span", { text: "Lula, juntando só as quedas do Bolsonaro" })))],
          "Fatia do Bolsonaro (vertical) conforme os boletins chegavam (horizontal). Ela começa em 49%, mas salta para 56% com 1,2% das urnas contadas — as primeiras que chegaram eram do Distrito Federal e do Paraná —, e desce até 49% quando o resto do país entra. Visto de longe, o que existe é uma subida e uma descida longas, não um serrote de degraus.")],
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
        "<b>É inédito.</b> De 1989 a 2022 houve 7 segundos turnos para presidente, e em todos eles quem liderou o 1º turno ganhou o 2º. Em 2026, pela primeira vez, quem estava atrás virou.",
        "<b>Os números conferem:</b> o Lula ganhou " + mi(dl) + " votos a mais que no 1º turno, e o Flávio, " + mi(df) + ". De cada 4 votos que apareceram no 2º turno, 3 foram para o Lula.",
        "<b>Onde já era forte, cresceu menos em %.</b> No Piauí, onde teve 71% dos votos válidos no 1º turno, o Lula ganhou 8,6% mais votos no 2º; em Santa Catarina, onde teve 25%, ganhou 26%. Em número de votos, porém, o ganho foi parecido: o equivalente a 6,1% dos válidos do 1º turno no Piauí e a 6,5% em Santa Catarina.",
        "<b>A virada foi espalhada.</b> Em 211 cidades o Flávio venceu o 1º turno e o Lula, o 2º; o contrário aconteceu em uma só, Uirapuru (GO). Três de cada quatro ficam no Sudeste e no Sul.",
        "<b>Raro não é impossível.</b> Basta a terceira via, o branco/nulo e quem voltou a votar penderem para o Lula. <a href='/simulacao/cenarios'>5 jeitos de a conta fechar</a>.",
      ],
      visual: visual(null, h("div", { class: "numeros" },
        numero("+" + mi(dl), "Lula entre os turnos", "l"), numero("+" + mi(df), "Flávio entre os turnos", "f"),
        numero(pc(100 * dl / (dl + df), 0), "dos votos novos foram para o Lula"))),
    });
  }
  // Gráfico de linha da chance do Lula na Polymarket em 25/10 (static/casos/polymarket.json).
  var POLY = null;
  function grafPoly() {
    var box = h("div", { class: "graf-poly" }, h("p", { class: "carregando", text: "…" }));
    var desenhar = function (d) {
      var pts = d.dia.filter(function (p) { var hr = new Date(p[0] * 1000).getHours(); return hr >= 12 && hr < 22; });
      var W = 420, H = 200, mE = 34, mB = 22, mT = 10, mD = 8;
      var t0 = pts[0][0], t1 = pts[pts.length - 1][0];
      var X = function (t) { return mE + (W - mE - mD) * (t - t0) / (t1 - t0); };
      var Y = function (v) { return mT + (H - mT - mB) * (1 - v / 100); };
      var svg = s("svg", { viewBox: "0 0 " + W + " " + H, class: "grafico", role: "img", "aria-label": "Chance do Lula na Polymarket em 25 de outubro: cerca de 20% até as 17h, 35% às 18h e acima de 80% depois das 19h" });
      [0, 50, 100].forEach(function (v) {
        svg.appendChild(s("line", { x1: mE, x2: W - mD, y1: Y(v), y2: Y(v), class: "grade" }));
        svg.appendChild(s("text", { x: mE - 6, y: Y(v) + 4, "text-anchor": "end", class: "eixo", text: v + "%" }));
      });
      var hora = function (h_, m) { var d0 = new Date(t0 * 1000); d0.setHours(h_, m || 0, 0, 0); return d0.getTime() / 1000; };
      [[17, 3, "prorrogação"], [19, 0, "apuração"]].forEach(function (m) {
        var x = X(hora(m[0], m[1]));
        svg.appendChild(s("line", { x1: x, x2: x, y1: mT, y2: H - mB, class: "ref" }));
        svg.appendChild(s("text", { x: x + 4, y: mT + 12, class: "eixo marco", text: m[2] }));
      });
      [12, 14, 16, 18, 20].forEach(function (hr) { svg.appendChild(s("text", { x: X(hora(hr)), y: H - 6, "text-anchor": "middle", class: "eixo", text: hr + "h" })); });
      svg.appendChild(s("path", { class: "serie poly", d: pts.map(function (p, i) { return (i ? "L" : "M") + X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1); }).join(" ") }));
      box.textContent = ""; box.appendChild(svg);
    };
    (POLY ? Promise.resolve(POLY) : fetch("/static/casos/polymarket.json" + (VERSAO ? "?v=" + encodeURIComponent(VERSAO) : "")).then(function (r) { return r.json(); }))
      .then(function (d) { POLY = d; desenhar(d); }).catch(function () { box.textContent = ""; });
    return box;
  }
  function pesquisas() {
    return caso({
      id: "pesquisas", titulo: "As pesquisas e as apostas", tag: "estranho",
      alegacao: "Na véspera, Datafolha e AtlasIntel davam o Flávio na frente, e a Polymarket dava 80% de chance a ele. O Lula ganhou. A chance de a pesquisa errar tanto era de 3 em 1.000.",
      fontes: [L("vídeo de @pyonglee", "https://www.instagram.com/reel/DfBFwC2ACEp/"), L("post de @dadosinterativos", "https://www.instagram.com/p/DfIZAFdm56K/")],
      checagem: [L("Bem Paraná (Datafolha 24/10)", "https://www.bemparana.com.br/eleicoes-2026/datafolha-flavio-bolsonaro-tem-51-dos-votos-validos-e-lula-49-na-vespera-do-2o-turno/"), L("BP Money (AtlasIntel)", "https://bpmoney.com.br/politica/flavio-499-lula-484-ultima-atlasintel-antes-urnas/"), L("BP Money (Polymarket)", "https://bpmoney.com.br/mercado/polymarket-errou-segundo-turno-lula-mercados-previsao/")],
      veredito: "Erraram, e um pouco além da margem. Já aconteceu antes.",
      pontos: [
        "<b>Os números das pesquisas conferem.</b> O Datafolha de 24/10 dava Flávio 51% e Lula 49% dos votos válidos, com margem de erro de 2 pontos para mais ou para menos. A última AtlasIntel dava 50,8% a 49,2%. O resultado oficial foi Lula 51,79%.",
        "<b>O erro foi de uns 3 pontos percentuais.</b> A pesquisa dava Flávio 51% e Lula 49%; o resultado deu Lula 51,79% e Flávio 48,21%. Cada um ficou a 2,8 pontos do que a pesquisa dizia — um pouco além da margem de 2. Em 2022 foi maior e para o outro lado: as pesquisas subestimaram o Bolsonaro no 1º turno em vários pontos.",
        "<b>As apostas seguiram as pesquisas.</b> A Polymarket está proibida no Brasil desde abril; quem apostava era quase todo de fora, com pouco volume. E 20% de chance não é zero: em 2016, a Betfair dava 83% de chance a Hillary Clinton, que perdeu.",
        "<b>Onde a pesquisa costuma errar:</b> em quem decide o voto no fim, em quem não votou no 1º turno e volta no 2º, e no destino da terceira via. Foi exatamente o que decidiu esta eleição.",
      ],
      visual: [visual(null, h("div", { class: "numeros" },
        numero("49%", "Lula na véspera (Datafolha)", "l"), numero("51,79%", "Lula no resultado", "l"), numero("80%", "chance do Flávio na Polymarket", "f"))),
        visual("Chance do Lula na Polymarket, no dia da eleição", grafPoly(),
          "Às 17h03 a votação foi prorrogada; às 17h06 saiu a primeira parcial (0,25% das seções, com o Lula na frente), e o TSE parou a contagem até as 19h. A subida das 17h é essa parcial; a virada, depois das 19h, é a apuração voltando."),
        visual("Onde o favorito das apostas já perdeu", h("div", { class: "mapa-apostas" },
          h("img", { src: "/static/casos/mapa-apostas.svg" + (VERSAO ? "?v=" + encodeURIComponent(VERSAO) : ""), alt: "Mapa: Brasil, Venezuela e Polônia destacados", loading: "lazy" }),
          h("ul", { class: "mapa-leg" },
            h("li", { html: "<b>Brasil 2026</b> · Flávio ~80% na Polymarket" }),
            h("li", { html: "<b>Polônia 2025</b> · Trzaskowski ~64% na Polymarket" }),
            h("li", { html: "<b>Venezuela 2024</b> · Maduro ~87% na Polymarket" }))))],
    });
  }
  // ── biometria: quantos votaram sem a digital, por eleição ───────────────
  // static/casos/biometria.json (tools/migracoes/2026-10-31-biometria.py), do
  // Boletim de Urna do TSE. A pergunta do relatório é "8,6 milhões é anormal?";
  // a resposta é a mesma taxa em 2022 e no 1º turno.
  var BIO = null;
  function grafBio() {
    var box = h("div", { class: "graf-bio" }, h("p", { class: "carregando", text: "…" }));
    var desenhar = function (b) {
      var ordem = [[2022, 1, "2022 · 1º turno"], [2022, 2, "2022 · 2º turno"], [2026, 1, "2026 · 1º turno"], [2026, 2, "2026 · 2º turno"]];
      var serie = ordem.map(function (o) {
        var t = b.eleicoes.filter(function (e) { return e.ano === o[0] && e.turno === o[1]; });
        var vot = t.reduce(function (a, e) { return a + e.votaram; }, 0);
        var sb = t.reduce(function (a, e) { return a + e.sem_bio; }, 0);
        return { rot: o[2], vot: vot, sb: sb, pct: 100 * sb / Math.max(vot, 1), hoje: o[0] === 2026 && o[1] === 2 };
      });
      var max = Math.max.apply(null, serie.map(function (x) { return x.pct; }));
      var W = 420, H = 235, mE = 44, mB = 46, mT = 34, grupo = (W - mE - 6) / serie.length, lb = Math.min(64, grupo - 16);
      var topo = Math.ceil(max / 2) * 2;
      var svg = s("svg", { viewBox: "0 0 " + W + " " + H, class: "grafico", role: "img",
        "aria-label": "Percentual de quem votou sem a biometria habilitada: " + serie.map(function (x) { return x.rot + " " + pc(x.pct, 1); }).join(", ") });
      [0, topo / 2, topo].forEach(function (v) {
        var y = mT + (H - mT - mB) * (1 - v / topo);
        svg.appendChild(s("line", { x1: mE, x2: W - 6, y1: y, y2: y, class: "grade" }));
        svg.appendChild(s("text", { x: mE - 6, y: y + 4, "text-anchor": "end", class: "eixo", text: pc(v, 0) }));
      });
      serie.forEach(function (x, i) {
        var alt = (H - mT - mB) * x.pct / topo;
        var x0 = mE + i * grupo + (grupo - lb) / 2;
        var r = s("rect", { x: x0, y: H - mB - alt, width: lb, height: alt, rx: 3, class: x.hoje ? "bio-hoje" : "bio-outra" });
        r.appendChild(s("title", { text: x.rot + ": " + num(x.sb) + " de " + num(x.vot) + " (" + pc(x.pct, 2) + ")" }));
        svg.appendChild(r);
        svg.appendChild(s("text", { x: x0 + lb / 2, y: H - mB - alt - 6, "text-anchor": "middle", class: "eixo valor", text: pc(x.pct, 1) }));
        svg.appendChild(s("text", { x: x0 + lb / 2, y: H - mB - alt - 20, "text-anchor": "middle", class: "eixo fraco", text: (x.sb / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi" }));
        svg.appendChild(s("text", { x: x0 + lb / 2, y: H - mB + 16, "text-anchor": "middle", class: "eixo", text: x.rot.split(" · ")[0] }));
        svg.appendChild(s("text", { x: x0 + lb / 2, y: H - mB + 30, "text-anchor": "middle", class: "eixo fraco", text: x.rot.split(" · ")[1] }));
      });
      box.textContent = ""; box.appendChild(svg);
    };
    (BIO ? Promise.resolve(BIO) : fetch("/static/casos/biometria.json" + (VERSAO ? "?v=" + encodeURIComponent(VERSAO) : "")).then(function (r) { return r.json(); }))
      .then(function (d) { BIO = d; desenhar(d); }).catch(function () { box.textContent = ""; });
    return box;
  }
  function biometria() {
    return caso({
      id: "biometria", titulo: "8,6 milhões sem digital", tag: "falsa",
      alegacao: "Um relatório divulgado nos EUA diz que 8,6 milhões votaram sem biometria depois das 17h. Tirando esses votos, o Flávio teria ganhado.",
      fontes: [L("vídeo de @hendelsmx (“toda a vantagem do Lula” nas urnas sem biometria)", "https://www.instagram.com/reel/DfIYypgOuoH/")],
      checagem: [fonte("tse_17h"), fonte("nucleo")],
      veredito: "Mistura dois números, e o maior deles é menor que em 2022",
      pontos: [
        "<b>Os 8,6 milhões existem, mas são do dia todo:</b> o Boletim de Urna do TSE — o arquivo com o resultado de cada urna — soma " + num(8632488) + " eleitores com biometria que votaram sem ela no 2º turno, em todo o país, dos " + num(127854631) + " que votaram. É a digital que não foi reconhecida e o voto liberado com documento com foto.",
        "<b>Isso é menos que nas eleições anteriores:</b> em 2022 foram 8,08% no 2º turno e 8,74% no 1º; em 2026, 6,68% no 1º. A taxa caiu, não subiu.",
        "<b>Depois das 17h foram 34.393 votos</b> no país, segundo o TSE: 0,03% do total. É esse o número da prorrogação, não 8,6 milhões.",
        "<b>Tirar 8,6 milhões só do Lula</b> supõe que todos votaram nele. O voto é secreto.",
        "<b>O relatório não tem autor.</b> A Justiça Eleitoral o chamou de apócrifo.",
        "<b>Se o voto sem digital tivesse feito a virada, ele teria crescido no 2º turno.</b> Cresceu " + num(8632488 - 8342249) + " (de 8,34 milhões para 8,63 milhões). Mesmo que todos fossem votos inventados para o Lula, seriam " + pc(100 * (8632488 - 8342249) / (V.dados.nacional.lula2 - V.dados.nacional.flavio2), 1) + " da diferença final.",
        "<b>A falha da digital é de quem vota ali, não do turno.</b> Em cada estado a taxa quase não mudou entre os turnos: no Piauí, 8,7% e 9,0%; em São Paulo, 6,0% nos dois. A falha costuma ser maior entre idosos e quem faz trabalho manual, que gastam a digital. E a relação entre mais falha e mais voto no Lula já existia no 1º turno, na mesma medida.",
      ],
      visual: visual("Quem votou sem a digital reconhecida, por eleição (% de quem votou)", [
        grafBio(),
        h("div", { class: "numeros" },
          numero("6,75%", "no 2º turno de 2026", "f"),
          numero("8,08%", "no 2º turno de 2022", "ok"))],
        "Fonte: Boletim de Urna do TSE, soma de todas as seções do país. O 1º turno de 2026 marcou 6,68%. A prática é antiga e a taxa vem caindo: o que o relatório chama de prova é o procedimento normal, em volume menor que o de 2022."),
    });
  }
  function mesario(d) {
    return caso({
      id: "mesario", titulo: "O mesário pianista", tag: "falsa",
      alegacao: "Com o número do título, o mesário vota pelo eleitor que faltou ou morreu. Em 500 mil seções, isso dá milhões de votos.",
      checagem: [fonte("aosfatos"), fonte("tse_17h")],
      veredito: "Fraude isolada é crime e aparece. Milhões, não.",
      pontos: [
        "<b>Saber o número do título não basta.</b> Sem a digital, é a mesa que confere o documento com foto do eleitor e digita o ano em que ele nasceu: a urna só libera o voto se o ano bater com o do cadastro. O eleitor também assina o caderno de votação.",
        "<b>Não sobra voto para isso.</b> Depois das 17h entraram 34.393 votos no país todo. A diferença final foi de " + mi(V.dados.nacional.lula2 - V.dados.nacional.flavio2) + " — 129 vezes isso. Para a fraude descrita virar o resultado, teria de ter entrado 129 vezes mais votos nesse intervalo.",
        "<b>Quando acontece, aparece:</b> em Salvador, no 1º turno, uma mesária foi presa suspeita de votar no lugar de um PM, que chegou depois. Há relatos parecidos no interior de SP.",
        "<b>“O site diz que eu faltei”</b> foi um erro de mensagem do TSE, já corrigido.",
      ],
      visual: visual("Onde o voto de outra pessoa entraria", [
        fluxo([["Caderno", "o mesário vê o nome de quem faltou"], ["Documento", "sem digital, a mesa pede foto e o ano de nascimento"], ["Urna", "cada voto entra no boletim de urna, o papel que a seção imprime"]]),
        h("div", { class: "numeros" },
          numero("34.393", "votos depois das 17h no país (TSE)", "l"),
          numero(num(d.mesma_secao.secoes_nos_dois_turnos), "seções para fazer isso"),
          numero("1", "caso confirmado, em Salvador"))],
        "Um voto a mais por seção daria 500 mil; a diferença foi de " + mi(d.nacional.margem) + "."),
    });
  }
  function caminhonete(d) {
    return caso({
      id: "caminhonete", titulo: "A caminhonete do PT", tag: "estranho", icone: "🚚",
      alegacao: "Urnas foram levadas numa caminhonete com adesivo do PT no Distrito Federal, depois da votação.",
      checagem: [fonte("caminhonete"), fonte("pleno")],
      veredito: "Aconteceu, e foi irregular. Mas não mexeu em voto.",
      pontos: [
        "<b>O vídeo é real.</b> Riacho Fundo II, depois da votação. O TRE-DF abriu apuração: veículo com propaganda de partido é proibido.",
        "<b>Os votos já tinham saído:</b> ao fechar, a urna imprime o boletim de urna — o papel com o resultado daquela seção — e os dados já foram transmitidos ao TSE antes do recolhimento.",
        "<b>Dá para conferir:</b> o boletim impresso é público. Se a urna fosse mexida, o resultado não bateria com o papel.",
      ],
      visual: visual("O que acontece antes de a urna entrar na caminhonete", [
        fluxo([["Fecha", "17h: a urna encerra e imprime o boletim"], ["Transmite", "os votos vão ao TSE antes de sair da seção"], ["Recolhe", "só então a urna é levada, sob escolta"]]),
        h("div", { class: "numeros" },
          numero("0", "votos que dependem do transporte", "ok"),
          numero(num(d.mesma_secao.secoes_nos_dois_turnos), "boletins para comparar"))],
        "Irregular foi o adesivo de partido no veículo; o TRE-DF abriu apuração por isso."),
    });
  }
  function consulta() {
    return caso({
      id: "consulta", titulo: "A consulta que sumiu", tag: "normal",
      alegacao: "O TSE tirou do ar a consulta de quem votou, depois que muita gente foi ver se mortos votaram.",
      fontes: [{ rot: "vídeo de @rubensdettoni", url: "https://www.instagram.com/reel/DfGFl7UNHr1/" },
               { rot: "o advogado Daniel Lima sobre “impedido de votar”", url: "https://www.instagram.com/reel/DfIiM5wytn6/" }],
      checagem: [fonte("tse_certidao"), fonte("tre_df_certidao"), fonte("faltou_tse"),
        L("TSE, hipóteses de cancelamento do título", "https://www.tse.jus.br/servicos-eleitorais/titulo-e-local-de-votacao/titulo-eleitoral"),
        L("TRE-PR, título em caso de óbito", "https://www.tre-pr.jus.br/comunicacao/noticias/2021/Abril/justica-eleitoral-explica-o-que-fazer-com-o-titulo-eleitoral-em-caso-de-obito")],
      veredito: "Saiu do ar, sim. Estava no calendário desde fevereiro.",
      pontos: [
        "<b>A suspensão é real.</b> De 26/10 a 2/11 o TSE processa os dados da votação e fecha o Cadastro Eleitoral; a consulta à situação do título e a certidão de quitação só voltam na terça, 3/11. Não é improviso: o calendário aprovado em fevereiro já previa essa pausa, como nos pleitos de 2018, 2020, 2022 e 2024.",
        "<b>“Ausente”, na consulta de agora, ainda não é resultado.</b> A lista mostra a situação de cada eleitor, mas nesses dias o TSE ainda está processando os registros de quem votou, faltou ou justificou. Por isso, “ausente” ali significa que o dado ainda não foi atualizado: não significa que a pessoa faltou nem que alguém votou no lugar dela. O próprio TSE avisa que, durante a suspensão, a mensagem na tela não permite concluir se alguém compareceu às urnas.",
        "<b>“Impedido de votar”, no e-Título, também não é fraude.</b> A tela aparece quando o título está cancelado (por exemplo, por três turnos seguidos sem votar nem justificar) ou suspenso (como na condenação criminal). É a situação do eleitor no cadastro, que vale antes de ele chegar à seção.",
        "<b>Quem morreu não tem título para ser usado.</b> O falecimento é uma das causas de cancelamento: o cartório de registro civil informa o óbito à Justiça Eleitoral, e o cartório da zona cancela a inscrição. Sem inscrição, o nome não entra no caderno de votação (a lista de quem vota na seção) nem na urna — então não há título para alguém usar no lugar dele. A conferência é pela consulta do TSE, que mostra a situação da inscrição: cancelada, quando o óbito já chegou ao Cadastro Eleitoral.",
      ],
      visual: visual("A consulta, dia a dia", [
        linhaTempo([["fev.", "o calendário eleitoral já previa a suspensão", ""],
                    ["26/10", "a consulta sai do ar, no dia seguinte à eleição", ""],
                    ["2/11", "último dia sem consulta", ""],
                    ["3/11", "volta ao ar, com os dados processados", ""]])],
        "Nos mesmos dias, o TSE processa quem votou, quem faltou e quem justificou."),
    });
  }
  // A sala-cofre é uma câmara fechada da STI: guarda as cópias lacradas dos
  // programas e os computadores que somam os votos. Quem recebe fiscais é a
  // sala de totalização, a poucos metros. O card dizia "a sala-cofre nunca foi
  // aberta a visitas", o que deixava no ar que os fiscais dividiam a sala com a
  // contagem — e o TSE respondeu que eles nunca estiveram lá: a sala-cofre não é
  // espaço de visitação (Fato ou Boato, Agência Brasil, Aos Fatos, 26/10/2026).
  function salaCofre(d) {
    return caso({
      id: "sala-cofre", titulo: "Os comandos na sala-cofre", tag: "falsa",
      alegacao: "Um servidor da sala-cofre do TSE — a câmara fechada onde ficam guardadas as cópias dos programas que rodam nas urnas e os computadores que somam os votos — recebia ao menos oito comandos externos. E os fiscais do PL foram tirados de lá depois das 17h.",
      fontes: [L("fala do Flávio Bolsonaro", "https://www.aosfatos.org/noticias/derrotado-flavio-mente-sugerir-eleicao-fraudada/")],
      checagem: [L("Justiça Eleitoral, Fato ou Boato", "https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens/2026/e-falso-que-fiscais-do-pl-foram-retirados-da-sala-cofre-do-tse"), L("Agência Brasil", "https://agenciabrasil.ebc.com.br/justica/noticia/2026-10/tse-nega-acusacao-de-flavio-sobre-expulsao-de-fiscais-de-sala-cofre"), L("Aos Fatos", "https://www.aosfatos.org/noticias/derrotado-flavio-mente-sugerir-eleicao-fraudada/"), L("TSE, a lacração de 2026", "https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/sistemas-das-eleicoes-gerais-de-2026-sao-assinados-digitalmente-e-lacrados-pelo-tse"), L("TSE, as máquinas da totalização", "https://www.tse.jus.br/comunicacao/noticias/2020/Novembro/nota-de-esclarecimento-sobre-nuvem-para-contabilizar-votos"), L("UOL Confere, as duas salas", "https://noticias.uol.com.br/confere/ultimas-noticias/2022/09/02/o-que-e-a-sala-cofre-do-tse-e-para-que-ela-serve.htm")],
      veredito: "Promessa sem prova. E a soma das urnas não deixa espaço.",
      pontos: [
        "<b>Não havia fiscal do PL na sala-cofre para ser tirado.</b> Ela não é sala de visita nem de trabalho no dia da eleição: é uma câmara fechada, que só se abre para a manutenção dos equipamentos. Fiscais de partido acompanham a <i>sala de totalização</i>, outra sala, a poucos metros. Lá os dois fiscais do PL estiveram, com registro de presença.",
        "<b>Nenhuma prova foi mostrada.</b> O vídeo, de 29/10, diz que a informação “caso seja comprovada” mostraria os comandos, e que “ainda não sabemos do que se trata”.",
        "<b>O que sai da sala-cofre tem que bater com o papel.</b> Cada urna imprime o boletim de urna — o resultado daquela seção, em papel — antes de transmitir, e uma via fica com os fiscais. As " + num(d.mesma_secao.secoes_nos_dois_turnos) + " seções batem voto a voto com o total oficial.",
      ],
      visual: visual("Duas salas, e o papel que decide", [
        h("ul", { class: "onde" },
          h("li", null, h("b", { text: "Sala-cofre" }), h("span", { text: "fechada: as cópias dos programas, lacradas antes da eleição, e os computadores que somam os votos. Ninguém trabalha nela." })),
          h("li", null, h("b", { text: "Sala de totalização" }), h("span", { text: "aberta e filmada: a equipe só acompanha o sistema." }))),
        fluxo([["Urna", "imprime o boletim, em papel, antes de transmitir"], ["Boletim", "uma via fica com os fiscais da seção"], ["Total", "só vale se bater com os papéis"]]),
        h("div", { class: "numeros" },
          numero(num(d.mesma_secao.secoes_nos_dois_turnos), "boletins impressos"),
          numero("0", "divergência com o total oficial", "ok"))],
        "As duas ficam na Secretaria de Tecnologia da Informação, no anexo do TSE, a poucos metros uma da outra."),
    });
  }
  function soma() {
    return caso({
      id: "soma", titulo: "A soma que não fecha", tag: "falsa",
      alegacao: "A soma dos estados não bate com o total do Brasil no site do TSE: faltam 766 mil votos.",
      fontes: [{ rot: "print do X" }],
      veredito: "O print é do começo da apuração",
      pontos: [
        "<b>O print foi tirado no começo da apuração:</b> nele o Lula aparece com 3,5 milhões de votos, e no fim teve 64,3 milhões. Cada estado foi copiado num momento diferente, com a contagem ainda subindo.",
        "<b>No fim, a soma fecha voto a voto:</b> os votos válidos das 499.205 seções somam 124.082.273, exatamente o número oficial.",
      ],
      visual: visual(null, h("div", { class: "numeros" },
        numero("124.082.273", "soma das seções"), numero("124.082.273", "resultado oficial"))),
    });
  }
  function cedula() {
    return caso({
      id: "cedula", titulo: "Voto no papel", tag: "normal",
      alegacao: "Em Pernambuco, uma seção passou a votar em cédula de papel, sem fiscalização. “Vão roubar essa eleição.”",
      checagem: [fonte("tre_pe")],
      veredito: "Existe e está na lei. É exceção.",
      pontos: [
        "<b>É o último recurso, previsto em lei.</b> Se a urna quebra, a seção usa a urna reserva. Só se as duas falharem é que se vota em cédula de papel — e esses votos são apurados à parte pela junta eleitoral, formada pelo juiz da zona e por dois a quatro cidadãos, com fiscais dos partidos acompanhando.",
        "<b>Foi raro.</b> Em Pernambuco, 80 das 22.694 urnas foram trocadas no 2º turno (0,35%), segundo o TRE-PE. Somando o eleitorado dessas seções, daria cerca de 20 mil votos: 0,5% da diferença final.",
        "<b>Não decide o resultado.</b> Uma seção tem, em média, " + num(V.dados.nacional.comp2 / 499205) + " votantes; a diferença final foi de " + mi(V.dados.nacional.lula2 - V.dados.nacional.flavio2) + ".",
      ],
      visual: visual("O que acontece quando a urna falha", [
        fluxo([["Urna", "trava ou não liga"], ["Reserva", "a seção usa a urna reserva"], ["Cédula", "sem reserva, vota no papel, com fiscais"], ["Junta", "os papéis são apurados à parte"]]),
        h("div", { class: "numeros" },
          numero("80", "urnas trocadas em Pernambuco"),
          numero("22.694", "urnas no estado"))]),
    });
  }
  function eleitores() {
    var c = V.dados.bahia;
    return caso({
      id: "eleitores", titulo: "Mais eleitor que habitante", tag: "normal",
      alegacao: "A Bahia tem 23 municípios com mais eleitores do que habitantes, como Catolândia e Firmino Alves.",
      checagem: [fonte("atarde"), fonte("tatu")],
      veredito: "É verdade, e é antigo. Não é voto a mais.",
      pontos: [
        "<b>Os 23 municípios existem.</b> É o cruzamento da lista de eleitores do TSE com a população estimada pelo IBGE. No país são 733 cidades nessa situação; na Bahia eram 36 em 2022.",
        "<b>É gente que mudou de cidade e não transferiu o título.</b> O título continua valendo no município antigo. E a população é estimativa do IBGE, o que também abre diferença.",
        "<b>Vota menos gente do que mora:</b> Catolândia tem 3.567 habitantes e 4.189 eleitores; votaram " + num(c["CATOLÂNDIA"].c2) + " no 2º turno. Em Firmino Alves, " + num(c["FIRMINO ALVES"].c2) + ".",
      ],
      visual: visual("Quem votou de fato (2º turno)", [barrasCidades([["Catolândia", 3567, 4189, c["CATOLÂNDIA"].c2], ["Firmino Alves", null, 4960, c["FIRMINO ALVES"].c2]]),
        h("p", { class: "leg", text: "Cinza: habitantes (IBGE). Azul: eleitores com título. Amarelo: quem compareceu." })],
        "O título fica no município de origem: quem mudou e não transferiu continua votando lá."),
    });
  }

  // ── além da urna: denúncias sobre a campanha (30/10/2026) ──────────────
  // Não são sobre a contagem: são acusações de abuso de poder, desinformação
  // e compra de voto. As que estão no TSE ainda não foram julgadas.
  function L(rot, url) { return { rot: rot, url: url }; }
  function prorrogacao() {
    return caso({
      id: "prorrogacao", titulo: "A prorrogação de última hora", tag: "estranho", icone: "⏰",
      alegacao: "A meia hora do fim, o ministro Zanin, ex-advogado do Lula, prorrogou a votação até as 19h em todo o país, a pedido da campanha do Lula.",
      fontes: [L("vídeo de @namaquete.br", "https://www.instagram.com/reel/DfFIOFdvQXQ/")],
      checagem: [L("Poder360", "https://www.poder360.com.br/poder-eleicoes-2026/zanin-prorroga-votacao-do-2o-turno-ate-19h/"), L("Conjur", "https://conjur.com.br/2026-out-25/crise-dos-onibus-faz-zanin-prorrogar-eleicoes-ate-as-19h-em-todo-o-brasil/"), L("Exame", "https://exame.com/brasil/por-que-o-tse-decidiu-prorrogar-o-horario-de-votacao-ate-as-19h/"), L("Agência Brasil", "https://agenciabrasil.ebc.com.br/politica/noticia/2026-10/campanha-de-flavio-pede-votacao-ate-19h-por-chuvas-em-alguns-estados"), L("G1, cronologia", "https://g1.globo.com/politica/eleicoes/2026/noticia/2026/10/25/pedidos-de-prorrogacao-do-horario-de-votacao-veja-cronologia.ghtml"), L("Rádio Senado", "https://www12.senado.leg.br/radio/1/noticia/2026/10/26/prorrogacao-do-horario-de-votacao-marca-o-segundo-turno-de-2026"), fonte("tse_17h")],
      veredito: "Aconteceu, e é estranho. Mas quase ninguém votou depois.",
      pontos: [
        "<b>É verdade.</b> A coligação do Lula pediu ao TSE às 13h22, por falta de ônibus em três cidades baianas, e às 16h29 pediu ao STF para todo o país. Zanin decidiu às 17h03, quando a votação já tinha fechado em boa parte das seções.",
        "<b>O Flávio também pediu.</b> Às 15h26, por chuva, alagamento e falta de energia em 17 cidades de SP, PR e SC; às 15h42, o pedido incluía MG e RS. O PL pediu também para segurar a divulgação dos resultados.",
        "<b>Mudou pouco:</b> urna já fechada não reabriu. Depois das 17h entraram 34.393 votos (0,03%), só 1.981 entre 18h e 19h; a diferença foi de " + mi(V.dados.nacional.lula2 - V.dados.nacional.flavio2) + ".",
        "<b>Não é rotina:</b> em 2022, o TSE recusou prorrogar o horário depois das blitze da PRF. Esta foi a primeira vez na história.",
      ],
      visual: visual("A tarde do dia 25, hora por hora", [
        linhaTempo([["13h15", "TRE-BA manda liberar 100% da frota de Salvador e prender o secretário de Mobilidade", ""],
                    ["13h22", "a coligação do Lula pede prorrogação ao TSE (Salvador, Feira de Santana e Lauro de Freitas)", ""],
                    ["15h26", "o PL pede o mesmo, por causa da chuva: 17 cidades de SP, PR e SC; às 15h42, inclui MG e RS", ""],
                    ["16h29", "a coligação do Lula pede ao STF a prorrogação para todo o país", ""],
                    ["17h01", "o MP Eleitoral diz que o horário deve ficar nas 17h", ""],
                    ["17h03", "Zanin prorroga até as 19h, para o país todo", ""],
                    ["17h06", "sai a primeira parcial (0,25% das seções); depois o TSE para a totalização", ""],
                    ["17h49", "Nunes Marques: só as seções ainda abertas seguem até as 19h", ""],
                    ["19h", "acaba a votação e a apuração recomeça, com 1,6% das seções já apuradas", ""]]),
        h("div", { class: "numeros" },
          numero("34.393", "votos depois das 17h"), numero(mi(V.dados.nacional.lula2 - V.dados.nacional.flavio2), "de diferença no fim", "l"))]),
    });
  }
  // ── os ônibus de Salvador (31/10/2026) ─────────────────────────────────
  // Dois lados no mesmo episódio: adesivos do Lula colados nos ônibus por
  // sindicalistas, e a prefeitura segurando a frota para tirá-los. O que se pode
  // medir é o comparecimento da cidade (secoes_2026, soma por município).
  function onibus() {
    return caso({
      id: "onibus", titulo: "Os ônibus de Salvador", tag: "estranho", icone: "🚌",
      alegacao: "Sindicalistas da CTB adesivaram os ônibus de Salvador para o Lula no dia do 2º turno, segundo um áudio atribuído ao presidente do Sindicato dos Rodoviários. Do outro lado, a prefeitura segurou ônibus nas garagens e deixou eleitor sem transporte.",
      checagem: [L("Bahia Notícias", "https://www.bahianoticias.com.br/noticia/323016-pablo-souza-diz-que-prefeitura-vai-pedir-prisao-de-sindicalistas-envolvidos-em-adesivaco-de-onibus-no-2-turno"), L("SBT News", "https://sbtnews.sbt.com.br/noticia/politica/retirar-adesivos-atrasou-onibus-diz-prefeito-de-salvador-1"), L("Muita Informação (TRE-BA)", "https://muitainformacao.com.br/politica/tre-ba-revoga-prisao-de-pablo-souza-e-manda-investigar-reducao-de-mais-de-50-da-frota-de-onibus/"), L("nota do sindicato", "https://muitainformacao.com.br/eleicoes/sindicato-dos-rodoviarios-nega-envolvimento-na-retencao-de-onibus-durante-eleicoes-em-salvador/")],
      veredito: "Os dois lados erraram. Faltou ônibus, mas não faltou eleitor.",
      situacao: "a Polícia Federal e a Procuradoria Eleitoral apuram a redução da frota; o PL pediu a prisão dos sindicalistas. Ninguém foi julgado.",
      pontos: [
        "<b>Os adesivos existiram.</b> Ônibus amanheceram com propaganda do Lula, o que é proibido em transporte público. O áudio divulgado em 29/10 mostra a divisão das garagens para colar o material; o sindicato nega ter retido ônibus.",
        "<b>A frota caiu.</b> Para tirar os adesivos, a prefeitura (Bruno Reis, União Brasil) segurou ônibus nas garagens. Às 13h15 o TRE-BA mandou liberar 100% da frota e prender o secretário de Mobilidade; a prisão foi revogada no dia seguinte, sem absolvição. A PF registrou 42% a menos numa garagem.",
        "<b>Foi o motivo da prorrogação.</b> A falta de ônibus em Salvador, Feira de Santana e Lauro de Freitas é o que a campanha do Lula levou ao TSE às 13h22 (ver “A prorrogação de última hora”).",
        "<b>O eleitor foi votar mesmo assim.</b> Em Salvador, votaram 5,5% mais pessoas que no 1º turno, contra 2,4% no país e mais que em qualquer outra capital. Se a falta de ônibus segurou alguém, isso não aparece no total da cidade.",
      ],
      visual: visual("Quanto o comparecimento subiu do 1º para o 2º turno", [
        h("div", { class: "numeros" },
          numero("+5,5%", "Salvador"),
          numero("+5,1%", "Feira de Santana"),
          numero("+2,4%", "o país todo")),
        linhaTempo([["madrugada", "ônibus amanhecem com adesivos do Lula", ""],
                    ["manhã", "a prefeitura segura ônibus para tirar os adesivos", ""],
                    ["13h15", "o TRE-BA manda liberar a frota e prender o secretário de Mobilidade", ""],
                    ["13h22", "a campanha do Lula pede ao TSE para prorrogar a votação", ""],
                    ["26/10", "a prisão é revogada; PF e Procuradoria seguem apurando", ""]])],
        "Comparecimento: soma das seções do TSE nos dois turnos. Salvador foi de 1,56 milhão para 1,65 milhão de votantes."),
    });
  }
  function desfile() {
    return caso({
      id: "desfile", titulo: "O desfile do Lula", tag: "estranho", icone: "🎭",
      alegacao: "A Acadêmicos de Niterói fez um desfile de Carnaval em homenagem ao Lula, com jingle e o número 13, pago com dinheiro público. O Novo pediu a cassação da chapa.",
      checagem: [L("Metrópoles", "https://www.metropoles.com/colunas/manoela-alcantara/tse-suposto-abuso-desfile-lula-carnaval"), L("Congresso em Foco", "https://www.congressoemfoco.com.br/noticia/121132/novo-pede-ao-tse-inelegibilidade-de-lula-por-desfile-de-carnaval"), L("Poder360", "https://www.poder360.com.br/poder-governo/saiba-como-foi-o-desfile-pro-lula-da-academicos-de-niteroi/"), L("Gazeta do Povo", "https://www.gazetadopovo.com.br/republica/oito-abusos-eleitorais-de-lula-que-nao-foram-contidos-pela-justica/")],
      veredito: "O desfile e o dinheiro público existem. O TSE ainda não julgou.",
      situacao: "ação do Novo aceita pelo TSE, na fase de provas. Não houve absolvição.",
      pontos: [
        "<b>Teve dinheiro público:</b> R$ 7,5 a 9,65 milhões, da Prefeitura de Niterói, da Embratur e de outros patrocinadores. A defesa diz que as 12 escolas receberam pelos mesmos critérios de sempre.",
        "<b>O TSE não proibiu o desfile antes</b> — impedir seria censura prévia —, mas pode punir depois.",
        "<b>Se o abuso for provado:</b> a pena vai de multa à cassação da chapa, com até 8 anos de inelegibilidade para quem se beneficiou. A escola de samba foi rebaixada no Carnaval.",
      ],
      visual: visual("O dinheiro público no desfile", [
        h("div", { class: "numeros" }, numero("R$ 7,5–9,65 mi", "dinheiro público (Prefeitura, Embratur e outros)", "f")),
        fluxo([["Antes", "o TSE não proíbe: seria censura prévia"], ["Depois", "o TSE pode punir o abuso"], ["Se provado", "multa, cassação e 8 anos inelegível"]])],
        "Ação do Novo aceita, na fase de provas. Não houve absolvição."),
    });
  }
  function pacote() {
    return caso({
      id: "pacote", titulo: "O pacote antes da eleição", tag: "estranho", icone: "💸",
      alegacao: "No ano da eleição, o governo despejou um pacote: gasolina e diesel com imposto cortado, Bolsa Família reajustado, Desenrola 3.0, fim da taxa das blusinhas e bets proibidas. O Novo contou 35 medidas no ano, 12 delas já dentro da campanha.",
      checagem: [L("Gazeta do Povo", "https://www.gazetadopovo.com.br/republica/oito-abusos-eleitorais-de-lula-que-nao-foram-contidos-pela-justica/"), L("Metrópoles", "https://www.metropoles.com/colunas/neila-guimaraes/novo-pede-cassacao-da-chapa-de-lula-por-medidas-em-ano-eleitoral"), L("Revista Oeste", "https://revistaoeste.com/politica/cassacao-chapa-lula-flavio-tse/"), L("Times Brasil", "https://timesbrasil.com.br/eleicoes-2026/decisao-2026-pacote-de-bondades-de-lula-acumula-mais-de-20-medidas-e-promessas-desde-o-inicio-da-campanha-presidencial/")],
      veredito: "As medidas existem. Se foram abuso, o TSE ainda vai dizer.",
      situacao: "ações do Novo e do Flávio sem julgamento. As mensagens do Gov.br viraram um caso à parte.",
      pontos: [
        "<b>Datas apertadas:</b> gasolina e etanol desonerados 25 dias antes do 1º turno, Bolsa Família 17 dias antes, Desenrola 3.0 (R$ 15 bi) e fim das bets 9 dias antes.",
        "<b>A lista é maior:</b> cabem nela o fim da taxa das blusinhas (24 dias antes), o Move Brasil ampliado, o consignado do INSS sem biometria e R$ 500 milhões a mais de subsídio à casa própria.",
        "<b>Depois do 1º turno a fila continuou:</b> mais R$ 0,26 de corte na gasolina (9/10), Prospera MEI com perdão de R$ 12,6 bi (13/10) e o Pé-de-Meia universitário prometido 12 dias antes do 2º turno.",
        "<b>A lei proíbe usar o governo para candidato</b>, mas permite programa já previsto no orçamento. A defesa diz que é o caso; a acusação, que a data foi escolhida pela campanha.",
        "<b>Não é fraude na urna:</b> a pena por abuso é cassação, não recontagem.",
      ],
      visual: visual("As medidas, com a distância do 1º turno (4/10)", [
        linhaTempo([["–25 dias", "gasolina e etanol desonerados, diesel com R$ 1 de subvenção (9/9)", ""],
                    ["–24 dias", "fim da taxa das blusinhas, Lei 15.502 (10/9)", ""],
                    ["–17 dias", "Bolsa Família reajustado em 15,04% (17/9)", ""],
                    ["–9 dias", "Desenrola 3.0, R$ 15 bi, e bets proibidas (25/9)", ""],
                    ["entre os turnos", "gasolina sem tributo federal: mais R$ 0,26, total de R$ 0,89 por litro (9/10); Prospera MEI e Pé-de-Meia prometido (13/10)", ""],
                    ["até 26/10", "diesel subsidiado; o benefício vencia um dia depois do 2º turno", ""]])],
        "A lei permite programa já previsto no orçamento; o que se discute é a data."),
    });
  }
  // ── a máquina no celular: os avisos do governo e o título dos jovens ─────
  // Duas acusações com o mesmo dono: o que o governo falou (WhatsApp do Gov.br
  // e Meu INSS às vésperas do 2º turno) e o que teria deixado de falar (a
  // campanha de alistamento dos jovens). A ação é a AIJE 0603241-16.2026.
  function maquinaCelular() {
    return caso({
      id: "maquina-celular", titulo: "A máquina no celular", tag: "estranho", icone: "📲",
      alegacao: "O governo usou o WhatsApp do Gov.br e o Meu INSS para falar com dezenas de milhões de pessoas às vésperas da eleição, e avisou aposentados de que votar valia como prova de vida. E não fez campanha para o jovem tirar o título, porque sabe que a maioria dos jovens é de direita.",
      fontes: [{ rot: "ação de Flávio no TSE (20/10); a parte do título dos jovens circula em posts, sem vídeo público localizado" }],
      checagem: [L("G1", "https://g1.globo.com/politica/noticia/2026/10/22/corregedor-do-tse-nega-pedido-de-flavio-bolsonaro-para-suspender-mensagens-do-governo.ghtml"), L("decisão do TSE (PDF)", "https://conjur.com.br/wp-content/uploads/2026/10/0603241-16-ATO-8-1.pdf"), L("Poder360", "https://www.poder360.com.br/poder-governo/governo-lula-manda-milhoes-de-zaps-para-divulgar-programas/"), L("INSS", "https://www.gov.br/inss/pt-br/assuntos/inss-alerta-cidadaos-sobre-realizacao-da-prova-de-vida"), L("TSE", "https://www.tse.jus.br/comunicacao/noticias/2026/Julho/mais-de-158-milhoes-de-eleitores-estao-aptos-votar-nas-eleicoes-2026"), L("Folha", "https://www1.folha.uol.com.br/poder/2026/07/mulheres-puxam-queda-de-23-de-eleitores-adolescentes-nesta-eleicao.shtml"), L("TSE, campanha jovem", "https://www.tse.jus.br/comunicacao/noticias/2026/Abril/campanha-do-tse-voltada-a-jovens-e-finalista-do-4o-premio-social-media-gov"), L("Valor", "https://valor.globo.com/politica/noticia/2026/10/24/quem-esta-na-frente-nas-pesquisas-para-presidente-veja-os-ultimos-resultados-por-genero-idade-e-escolaridade.ghtml")],
      veredito: "As mensagens existem; a queda dos jovens também. O elo entre as duas não está demonstrado.",
      situacao: "AIJE 0603241-16.2026.6.00.0000 no TSE, sem julgamento. Suspender os disparos foi negado em 22/10; o mérito não tem data.",
      pontos: [
        "<b>Os avisos saíram.</b> Em 21/10, a quatro dias do 2º turno, a conta GovBR no WhatsApp e o Meu INSS avisaram aposentados de que votar valia como prova de vida. O aviso de 1/10 já listava o voto entre as formas de fazer a comprovação.",
        "<b>O que a mensagem diz é verdade.</b> Desde 2022, por portaria do INSS, votar conta como prova de vida, e a Justiça Eleitoral repassa ao INSS a lista de quem compareceu. Quem não vota não perde o benefício: o INSS segue procurando outros registros.",
        "<b>O TSE não suspendeu os disparos.</b> Em 22/10, o corregedor Cueva negou o pedido: nos exemplos do processo não há candidato, pedido de voto nem elogio ao governo. Ele ressalvou que a negativa não é salvo-conduto, e a ação continua.",
        "<b>Os jovens:</b> o eleitorado de 16 e 17 anos caiu de 2,12 milhões para 1,63 milhão (−22,8%), enquanto a população dessa idade caiu 5,6%. E houve campanha do TSE em 2026, menor que a de 2022: 470 mil contas alcançadas nos 19 posts do Instagram, contra 88 milhões de pessoas no tuitaço de 2022.",
        "<b>“Jovem é de direita” não aparece no dado.</b> Na véspera, o Datafolha deu Lula 52% e Flávio 44% entre 16 e 24 anos; a Quaest, na faixa de 16 a 34, deu Flávio 47% a 43%. Intenção declarada muda de pesquisa para pesquisa.",
      ],
      visual: visual("As datas dos avisos e o tamanho do eleitorado jovem", [
        linhaTempo([["4/7", "começa o período em que a lei veda publicidade institucional", ""],
                    ["1/10", "o INSS avisa pelo WhatsApp do Gov.br: votar é uma das formas de prova de vida", ""],
                    ["6–20/10", "mensagens sobre Enem, Farmácia Popular e vacinas, segundo a ação", ""],
                    ["21/10", "a conta GovBR repete, a quatro dias do 2º turno: votar vale como prova de vida", ""],
                    ["22/10", "o corregedor do TSE nega suspender os disparos; a ação segue", ""]]),
        h("div", { class: "numeros" },
          numero("170 mi", "notificações por mês, na escala do contrato do Serpro", "f"),
          numero("44 mi", "envios só na fase piloto, segundo o Ministério da Saúde", "f"),
          numero("1,40 mi", "eleitores de 16 e 17 anos em 2018", "ok"),
          numero("2,12 mi", "os mesmos eleitores em 2022", "ok"),
          numero("1,63 mi", "os mesmos eleitores em 2026", "ok"))],
        "Quantas pessoas receberam as mensagens não é público: o governo diz que o número varia por ministério. Do lado dos jovens, o eleitorado de 16 e 17 anos foi de 0,95% do total em 2018 a 1,3% em 2022, e caiu para 1,03% em 2026."),
    });
  }
  function exercito() {
    return caso({
      id: "exercito", titulo: "O Exército do Lula", tag: "estranho", icone: "📣",
      alegacao: "Um canal de WhatsApp do deputado André Janones, com mais de 3 milhões de seguidores, coordenava fake news contra o Flávio para a campanha do Lula.",
      checagem: [L("CNN Brasil", "https://www.cnnbrasil.com.br/blogs/gustavo-uribe/eleicoes/tecnicos-do-tse-dizem-nao-poder-aferir-se-exercito-do-lula-usou-fake-news/"), L("Gazeta do Povo", "https://www.gazetadopovo.com.br/eleicoes/2026/tse-nao-acha-fake-news-canal-janones-mas-registra-mensagens-apagadas/"), L("TSE", "https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/tse-determina-esclarecimentos-antes-de-analisar-pedidos-de-flavio-contra-lula-e-janones")],
      veredito: "O canal e as “missões” existem. Fake news, o TSE não conseguiu medir.",
      pontos: [
        "<b>O canal existe</b> e dava “missões” de compartilhamento aos seguidores.",
        "<b>Os técnicos do TSE não acharam conteúdo falso.</b> Mas 81 mensagens já tinham sido apagadas do canal antes de serem lidas, e por isso eles disseram que não dá para afirmar se houve.",
        "<b>O canal foi suspenso e depois liberado:</b> o presidente do TSE tirou do ar; o corregedor devolveu até o plenário decidir.",
      ],
      visual: visual("O que os técnicos do TSE conseguiram ler", [
        h("div", { class: "numeros" },
          numero("3 mi+", "seguidores do canal", "f"),
          numero("81", "mensagens apagadas antes da leitura", "falso"),
          numero("—", "conteúdo falso identificado")),
        fluxo([["Canal", "dava “missões” de compartilhamento"], ["Leitura", "81 mensagens já tinham sido apagadas"], ["Conclusão", "não dá para afirmar que houve fake news"]])]),
    });
  }
  function universidades() {
    return caso({
      id: "universidades", titulo: "Universidades em campanha", tag: "estranho", icone: "🎓",
      alegacao: "Universidades públicas, como a UFSC, viraram comitê do Lula: adesivos no campus, atos de campanha e aulas suspensas para os estudantes irem votar.",
      fontes: [L("vídeo de professor da UFSC (Jornal Razão)", "https://jornalrazao.com/politica/ufsc-virou-comite-do-pt-professor-denuncia-adesivos-lula-campus-florianopolis")],
      checagem: [L("Gazeta do Povo", "https://www.gazetadopovo.com.br/eleicoes/2026/universidades-suspendem-aulas-pedido-dces-campanha-lula/"), L("OitoMeia", "https://www.oitomeia.com.br/noticias/politica/2026/09/26/ato-politico-lula-ufpi-realizado-gera-questionamentos-controversias/"), L("Revista Oeste", "https://revistaoeste.com/politica/deputado-denuncia-uso-de-espacos-de-universidade-federal-para-campanha-do-pt/")],
      veredito: "Aconteceu em vários campi. Propaganda em prédio público é proibida.",
      pontos: [
        "<b>Os casos existem:</b> adesivos na UFSC, ato na UFPI, espaços da Ufes e do Ifes, cartazes retirados da UFS por ordem judicial.",
        "<b>A lei proíbe propaganda eleitoral em bem público</b> — prédio, muro e equipamento mantidos pelo poder público (art. 37 da Lei das Eleições, a Lei 9.504/1997). A punição é multa.",
        "<b>As aulas foram suspensas</b> em 23/10, a sexta antes do voto, para a ida, e em 26/10, a segunda depois, para a volta — na UFPB, UFS, UFSC, Unesp e outras, a pedido dos diretórios centrais dos estudantes (DCEs). Não houve ação na Justiça contra a suspensão.",
        "<b>Mudou o resultado?</b> Não dá para medir: o voto é secreto, e ninguém sabe em quem cada estudante votou.",
      ],
      visual: visual("Onde apareceu e o que a Justiça fez", [
        h("ul", { class: "onde" },
          h("li", null, h("b", { text: "UFSC" }), h("span", { text: "adesivos no campus" })),
          h("li", null, h("b", { text: "UFPI" }), h("span", { text: "ato político" })),
          h("li", null, h("b", { text: "Ufes / Ifes" }), h("span", { text: "espaços usados em campanha" })),
          h("li", null, h("b", { text: "UFS" }), h("span", { text: "cartazes retirados por ordem judicial" }))),
        h("div", { class: "numeros" },
          numero("R$ 2–8 mil", "multa por propaganda em bem público (art. 37)"),
          numero("23 e 26/10", "aulas suspensas (ida e volta) a pedido dos DCEs"))]),
    });
  }
  function mesaria(d) {
    return caso({
      id: "mesaria", titulo: "A mesária cabo eleitoral", tag: "estranho",
      alegacao: "Uma mesária pediu voto para o 13 dentro da seção, na Bahia.",
      checagem: [L("Metrópoles", "https://www.metropoles.com/distrito-federal/na-mira/mesaria-e-presa-no-df-suspeita-de-fazer-campanha-para-lula-dentro-de-escola"), L("Jornal Opção", "https://www.jornalopcao.com.br/ultimas-noticias/mesaria-e-detida-suspeita-de-pedir-votos-para-lula-durante-segundo-turno-no-distrito-federal-882307/"), L("Correio", "https://www.correio24horas.com.br/bahia/mesaria-e-presa-sob-suspeita-de-votar-no-lugar-de-policial-militar-em-salvador-1026")],
      veredito: "Na Bahia, não confirmado. No DF, aconteceu, e é crime.",
      pontos: [
        "<b>O vídeo da Bahia não foi confirmado</b> por nenhum veículo de imprensa nem pelo TRE-BA (o tribunal eleitoral do estado).",
        "<b>No DF, uma mesária foi detida.</b> Foi no 2º turno, no Gama, por fazer campanha dentro da seção. A primeira notícia dizia que era para o Lula; a PM disse depois que era para o Flávio.",
        "<b>É crime, e o caso apareceu:</b> a presidente da seção chamou o juiz eleitoral e a polícia. Um caso numa seção não muda um resultado com " + mi(V.dados.nacional.lula2 - V.dados.nacional.flavio2) + " de diferença.",
      ],
      visual: visual("Os dois vídeos", [
        h("div", { class: "duelo" },
          h("div", { class: "f" }, h("b", { text: "Bahia" }), h("span", { text: "não confirmado por veículo nem pelo TRE-BA" })),
          h("div", { class: "l" }, h("b", { text: "DF" }), h("span", { text: "detida no Gama; a PM depois disse que era para o Flávio" }))),
        h("div", { class: "numeros" }, numero("1", "seção afetada"), numero(num(d.mesma_secao.secoes_nos_dois_turnos), "seções no país"))]),
    });
  }
  function faccoes() {
    return caso({
      id: "faccoes", titulo: "As facções votaram no Lula", tag: "falsa", icone: "🚨",
      alegacao: "O PCC e o Comando Vermelho declararam apoio ao Lula e pagavam R$ 200 a moradores para votar nele.",
      checagem: [L("Aos Fatos", "https://www.aosfatos.org/noticias/pcc-comando-vermelho-apoio-lula-falso/"), L("Boatos.org", "https://www.boatos.org/politica/pcc-e-comando-vermelho-cv-declaram-apoio-a-lula-no-2o-turno-das-eleicoes.html"), L("Correio Braziliense", "https://www.correiobraziliense.com.br/politica/2026/10/7521443-mendonca-manda-retirar-videos-que-associam-lula-ao-pcc-e-impoe-multa-de-rs-10-mil.html")],
      veredito: "Não há registro do apoio nem do pagamento",
      pontos: [
        "<b>Nenhum comunicado das facções existe:</b> o Aos Fatos procurou e não achou. O Ministério Público do Rio não tem informação sobre apoio, e uma fonte do MP de São Paulo desmentiu.",
        "<b>O TSE mandou tirar do ar</b> os vídeos do “R$ 200 do PCC” e os posts do Flávio que ligavam o Lula às facções.",
        "<b>A regra valeu para os dois lados:</b> posts que ligavam o Flávio ao crime também foram removidos.",
      ],
      visual: visual("Quem procurou o comunicado e o que achou", [
        h("div", { class: "numeros" },
          numero("0", "comunicados de facção encontrados", "ok"),
          numero("10 mil", "de multa do TSE por vídeo de “R$ 200 do PCC”", "falso")),
        fluxo([["Aos Fatos", "procurou os comunicados: não existem"], ["MP-SP", "uma fonte do MP desmentiu"], ["MP-RJ", "não tem informação sobre apoio"]])]),
    });
  }
  // ── o contencioso de desinformação das duas campanhas ───────────────────
  // Não é o caso `exercito` (o canal do Janones e o que os técnicos do TSE
  // leram nele): aqui são as decisões — quem pediu, quem foi condenado, o que
  // saiu do ar. O placar sai da imprensa, decisão por decisão; o TSE não
  // publica balanço de remoções por campanha, então a contagem é a das ordens
  // que este levantamento localizou.
  function desinformacao() {
    var a = function (rot, url) {
      return '<a href="' + url + '" target="_blank" rel="noopener nofollow">' + rot + "</a>";
    };
    // Duas contagens publicadas, uma de cada lado, e uma tabela por categoria
    // de decisão. Nada de total único: somar liminar, mérito e pedido negado
    // juntaria coisas que não se somam.
    // `cat` aceita <br>: o <b> é montado com html, não com texto.
    var linha = function (cat, f, l) {
      return h("tr", {},
        h("td", { html: "<b>" + cat + "</b>" }),
        h("td", { html: f }), h("td", { html: l }));
    };
    // Eixo do placar: a quem a decisão favoreceu. Remover conteúdo contra o
    // Flávio favorece o Flávio; negar um pedido dele favorece o Lula.
    var placar = h("div", { class: "rolagem" }, h("table", { class: "tab placar-tab", style: "min-width: 430px" },
      h("thead", {}, h("tr", {},
        h("th", { text: "2026" }),
        h("th", { text: "Favoreceu o Flávio" }),
        h("th", { text: "Favoreceu o Lula" }))),
      h("tbody", {},
        linha("Multa de mérito", "—", "R$ 5 mil, ligação ao PCC (28/09)"),
        linha("Multa em decisão individual",
          "R$ 15 mil à campanha do Lula<br>por impulsionamento (25/09)",
          "R$ 5 mil por impulsionamento (05/10)"),
        linha("Remoção confirmada<br>pelo plenário",
          "Aparecida (30/09)<br>posts de Lindbergh e Correia (13/10)<br>vídeo de Fabrício Vargas (15/10)<br>posts da Unha e Carne (20/10)",
          "3 posts no X de Flávio (08/10)<br>2 vídeos de IA do PL (13/10)<br>vídeo do INSS (15/10)"),
        linha("Remoção em liminar,<br>sem julgamento final",
          "2 vídeos do Lula e 1 da Janja (08/10)<br>5 posts de Janones e Lindbergh (08/10)",
          "peça de rádio da “saidinha” (21/10)<br>20 posts do Flávio e aliados (21/10)<br>post do PL sobre o PCC (22/10)<br>vídeo da “Tropa do Flávio” (23/10)"),
        linha("Pedido negado",
          "<b>7</b>: 5 de 04/08, a “Carta aos<br>brasileiros” e “Dama de Ferro”",
          "<b>3</b>: escala 7x0, vídeo do<br>Master e “mentiroso master”"))));
    return caso({
      id: "desinformacao", titulo: "O que a Justiça mandou apagar", tag: "normal", icone: "⚖️",
      // "normal" e não "falsa": o fenômeno (a Justiça remover conteúdo em campanha)
      // é real e documentado, dos dois lados. O que se corrige é o "só um lado",
      // e isso está no veredito, não na etiqueta.
      alegacao: "Só um lado foi condenado: a Justiça Eleitoral manda apagar conteúdo de uma campanha e deixa a outra em paz.",
      checagem: [
        L("TSE", "https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/tse-manda-retirar-do-ar-videos-com-uso-de-inteligencia-artificial-publicados-por-flavio-bolsonaro"),
        L("G1", "https://g1.globo.com/politica/eleicoes/2026/noticia/2026/10/09/tse-manda-retirar-publicacoes-de-lula-janja-e-aliados-contra-flavio-bolsonaro.ghtml"),
        L("TSE", "https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/plenario-mantem-remocao-de-publicacao-que-associa-flavio-bolsonaro-a-operacao-da-pf"),
        L("Metrópoles", "https://www.metropoles.com/brasil/andre-mendonca-multa-campanha-de-lula-por-impulsionar-video-contra-flavio"),
        L("CNN Brasil", "https://www.cnnbrasil.com.br/eleicoes/tse-manda-remover-video-com-ia-sobre-lula-em-canal-tropa-do-flavio/"),
        L("Times Brasil (levantamento do Globo)", "https://timesbrasil.com.br/brasil/decisao-2026-acoes-judiciais-na-disputa-pela-presidencia-da-republica-crescem-165-em-relacao-a-2022/"),
        L("A Crítica (os 20 posts)", "https://acritica.net/eleicoes-2026/nunes-marques-suspende-20-postagens-contra-lula-apos-denuncia-de-deepfake/"),
      ],
      veredito: "Os dois lados apagaram conteúdo e pagaram multa",
      situacao: "quase tudo é liminar, não sentença. O plenário já confirmou remoções contra os dois lados. Seguem sem julgamento final, por exemplo, os vídeos do Lula e da Janja (08/10) e a peça da “saidinha” do Flávio (21/10).",
      pontos: [
        "<b>A Justiça mandou apagar conteúdo dos dois lados.</b> Não há contagem oficial: o TSE não publica quantos conteúdos removeu de cada campanha.",
        "<b>Os placares que existem quase empatam.</b> Até o 1º turno, levantamento do Globo achou 55 decisões favoráveis ao Lula e 50 ao Flávio, em 698 ações. O jurídico do Lula diz ter 371 decisões a favor em 584, mas é a conta da própria campanha.",
        "<b>As multas também foram dos dois lados.</b> R$ 5 mil ao Flávio por ligar o Lula ao PCC e R$ 5 mil por impulsionar propaganda negativa; R$ 15 mil à campanha do Lula por impulsionar vídeo contra a família Bolsonaro.",
        "<b>A maior parte é liminar, e algumas caíram.</b> O plenário liberou os posts da escala 7x0 por 5 a 1, e o vídeo do Lula sobre o “tesouraço” só continua fora do ar porque o relator pediu destaque.",
        "<b>Os números não se somam.</b> Uma ordem pode atingir 1.125 publicações; outra, um único post.",
      ],
      visual: visual("O placar, por categoria de decisão", [
        h("div", { class: "duelo" },
          h("div", { class: "f" }, h("b", { text: "50" }), h("span", { text: "decisões favoráveis ao Flávio" })),
          h("div", { class: "l" }, h("b", { text: "55" }), h("span", { text: "favoráveis ao Lula" }))),
        h("p", { class: "leg", style: "margin:0 0 14px", text: "Até o 1º turno, em 698 ações no TSE (44% com decisão). Levantamento do Globo, não é balanço do tribunal." }),
        placar],
        "Abaixo, só as decisões que esta apuração localizou na imprensa, e não o número de posts: uma ordem pode atingir um post ou 1.125. O TSE mantém um repositório de decisões sobre desinformação, mas não publica quantos conteúdos removeu de cada campanha."),
      mais: [{
        rot: "As decisões, uma a uma",
        corpo: [
          linhaTempo([
            ["04/08", "Mendonça nega 5 dos 6 pedidos do PT; manda retirar só o deepfake de Lula e Jaques Wagner " + a("(Poder360)", "https://www.poder360.com.br/poder-eleicoes-2026/campanha-de-lula-vai-ao-tse-contra-flavio-e-carlos/"), ""],
            ["25/09", "Campanha do Lula: multa de R$ 15 mil por impulsionar vídeo contra a família Bolsonaro " + a("(Metrópoles)", "https://www.metropoles.com/brasil/andre-mendonca-multa-campanha-de-lula-por-impulsionar-video-contra-flavio"), ""],
            ["28/09", "Flávio: multa de R$ 5 mil e remoção definitiva do post “defensor do PCC e do Comando Vermelho” " + a("(CNN)", "https://www.cnnbrasil.com.br/eleicoes/tse-aplica-multa-de-r-5-mil-a-flavio-por-ligar-lula-ao-pcc-e-ao-cv/"), ""],
            ["30/09", "Flávio: plenário mantém a remoção de 1.125 posts sobre Nossa Senhora Aparecida, com alcance restringido " + a("(BBC)", "https://www.bbc.com/portuguese/articles/cmvgy277qg5po"), ""],
            ["08/10", "Flávio: 3 posts no X. Lula: 2 vídeos no Instagram; Janja: 1 vídeo; Janones e Lindbergh: 5 publicações " + a("(G1)", "https://g1.globo.com/politica/eleicoes/2026/noticia/2026/10/09/tse-manda-retirar-publicacoes-de-lula-janja-e-aliados-contra-flavio-bolsonaro.ghtml"), ""],
            ["13/10", "Plenário confirma a remoção de posts de Lindbergh e Rogério Correia sobre milícia e recusa a de “Dama de Ferro” " + a("(Poder360)", "https://www.poder360.com.br/poder-justica/tse-julga-acoes-sobre-videos-que-ligam-lula-e-flavio-ao-crime/"), ""],
            ["15/10", "Flávio: plenário confirma a remoção do vídeo que liga o Lula às fraudes do INSS " + a("(CNN)", "https://www.cnnbrasil.com.br/eleicoes/tse-determina-remocao-de-video-de-flavio-que-liga-lula-a-caso-do-inss/"), ""],
            ["20/10", "Gleisi, Boulos, Lindbergh e Rogério Correia: plenário mantém a remoção dos posts sobre a Operação Unha e Carne " + a("(TSE)", "https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/plenario-mantem-remocao-de-publicacao-que-associa-flavio-bolsonaro-a-operacao-da-pf"), ""],
            ["21/10", "Flávio: peça de rádio da “saidinha” proibida; no mesmo dia, Nunes Marques suspende 20 posts do Flávio e de aliados contra o Lula, por suspeita de deepfake " + a("(CNN)", "https://www.cnnbrasil.com.br/eleicoes/tse-manda-suspender-propaganda-que-diz-que-lula-e-a-favor-da-saidinha/"), ""],
            ["22/10", "Plenário derruba a liminar e libera os posts da escala 7x0; o PL é condenado a apagar post sobre proteção ao PCC " + a("(Metrópoles)", "https://www.metropoles.com/colunas/grande-angular/tse-libera-posts-de-erika-hilton-que-associam-flavio-a-escala-7x0"), ""],
            ["23/10", "Flávio: vídeo com IA no canal “Tropa do Flávio” removido " + a("(CNN)", "https://www.cnnbrasil.com.br/eleicoes/tse-manda-remover-video-com-ia-sobre-lula-em-canal-tropa-do-flavio/"), ""],
          ]),
          p("Datas de decisão ou de publicação da decisão. O TSE não reúne as remoções das duas campanhas num balanço público, e a lista não é exaustiva."),
        ],
      }],
    });
  }
  function compra() {
    return caso({
      id: "compra", titulo: "Compra de votos", tag: "normal", icone: "💵",
      alegacao: "Houve compra de votos em massa, com dinheiro vivo.",
      checagem: [L("CNN Brasil", "https://www.cnnbrasil.com.br/eleicoes/pf-ja-apreendeu-r-27-milhoes-em-especie-em-combate-a-compra-de-voto/"), L("O Tempo", "https://www.otempo.com.br/eleicoes/2026/2026/10/3/pf-prende-47-pessoas-em-flagrante-durante-11-acoes-contra-compra-de-votos")],
      veredito: "Existe, foi combatida, e não aponta para o 2º turno",
      pontos: [
        "<b>A compra de votos existe:</b> a Polícia Federal apreendeu R$ 27 milhões em dinheiro vivo até o 1º turno — R$ 4,6 milhões em 2022 — e prendeu 47 pessoas em flagrante.",
        "<b>Os casos são locais:</b> Tocantins, Roraima, Pará, Amazonas e Amapá, em disputas de deputado e de governador. Nenhum liga a compra à campanha presidencial.",
        "<b>Mais apreensão não quer dizer mais fraude.</b> Pode ser só mais fiscalização. E nada disso explica a virada do 2º turno.",
      ],
      visual: visual("Dinheiro apreendido na eleição", [barrasAno([["2022", 4.6], ["2026", 27]]),
        h("p", { class: "leg", text: "R$ milhões em espécie apreendidos pela PF até o 1º turno, e 47 presos em flagrante em 11 ações." })],
        "TO, RR, PA, AM e AP, em disputas de deputado e governador. Nada liga à campanha presidencial."),
    });
  }

  // ── a padroeira depois da correção (31/10/2026) ────────────────────────
  // O que circula: a campanha do Lula teria insistido na história de que o
  // Flávio tiraria de Nossa Senhora Aparecida o título de padroeira, mesmo
  // depois do desmentido. O que os registros mostram: o enquadramento seguiu
  // no palanque, a autoria não foi repetida, e a peça espelhada (a capa falsa
  // da Veja contra o Lula) também foi removida. Ver a linha do tempo.
  function padroeira() {
    var a = function (rot, url) {
      return '<a href="' + url + '" target="_blank" rel="noopener nofollow">' + rot + "</a>";
    };
    return caso({
      id: "padroeira", titulo: "A padroeira depois da correção", tag: "estranho", icone: "🕯️",
      alegacao: "Depois de a GloboNews corrigir e o TSE chamar de inverídica a história de que o Flávio tiraria a padroeira do Brasil, a campanha do Lula insistiu no assunto: “eu não sei se foi fake news”.",
      fontes: [L("Pleno.News, 28/09", "https://pleno.news/brasil/politica-nacional/mesmo-apos-ser-desmentido-lula-insiste-em-fake-sobre-padroeira.html")],
      checagem: [
        L("BBC Brasil", "https://www.bbc.com/portuguese/articles/ck30540nv5m6o"),
        L("Aos Fatos", "https://www.aosfatos.org/noticias/boato-sobre-nossa-senhora-aparecida-e-flavio-retoma-narrativas-falsas-de-2018-e-2022/"),
        L("CNN Brasil", "https://www.cnnbrasil.com.br/eleicoes/fake-news-ne-presidente-lula-e-contestado-sobre-nossa-senhora/"),
        L("Câmara dos Deputados", "https://www.camara.leg.br/noticias/546239-PROJETO-QUE-TIRA-DE-NOSSA-SENHORA-O-TITULO-DE-PADROEIRA-DO-BRASIL-ESTA-ARQUIVADO"),
        L("CBN", "https://cbn.globo.com/coberturas/eleicoes-2026/noticia/2026/10/02/lula-impulsiona-publicacoes-sobre-bets-e-nossa-senhora-flavio-foca-em-seguranca-e-bolsa-familia.ghtml"),
      ],
      veredito: "Insistiu no tema, não na autoria",
      situacao: "não há sentença: as remoções são liminares ou referendos do plenário. A notícia-crime contra o servidor da Secom foi enviada à Polícia Federal, e a Justiça restringiu as redes dele, sem prender.",
      pontos: [
        "<b>O que circulou era falso, e o projeto era de outro.</b> O texto que tiraria da santa o título de padroeira é o PL 2.623/2007, do então deputado Victório Galli, rejeitado pela Comissão de Educação e Cultura e arquivado em 22 de agosto de 2008. O Flávio era deputado estadual no Rio e não há registro de autoria ou de apoio dele.",
        "<b>O título não sai por caneta presidencial.</b> Quem declarou Aparecida padroeira do Brasil foi o papa Pio XI, em 1930, e a lei de 1980, sancionada por Figueiredo, criou o feriado nacional de 12 de outubro citando o título na redação. O projeto de 2007 mudava a redação dessa lei — não o ato que deu o título.",
        "<b>Dois dias depois da correção, o enquadramento não mudou.</b> Em 27/09, na Band, Lula disse que “mexer com Nossa Senhora Aparecida não é aceitável”; avisado de que a história era falsa, respondeu “eu não sei se foi fake news” e que o “dado concreto” era a circulação nas redes. Nessa fala, ele não atribui o projeto ao Flávio.",
        "<b>O assunto seguiu no palanque.</b> Em 28/09, em Belém, Lula disse que “ninguém vai avacalhar com Nossa Senhora Aparecida” e a Janja, que “o outro lado quer o fim da Padroeira do Brasil”; no fim do ato, recebeu e ergueu uma imagem de Nossa Senhora de Nazaré, padroeira do Pará, e em 29/09, em Fortaleza, recebeu outra. Na semana seguinte, a campanha pagou R$ 70 mil para impulsionar um corte em que ele promete manter o título.",
        "<b>A peça contrária também existiu.</b> Em 30/09, o TSE mandou apagar quatro posts com uma capa falsa da Veja que atribuía ao Lula e ao PT um projeto para excluir Aparecida e favorecer a umbanda; a Abril e a Reuters confirmaram que a capa não foi publicada. O Aos Fatos lembra que boatos do mesmo tipo circularam contra o Jair Bolsonaro em 2018 e 2022, também sem base.",
      ],
      visual: visual("O que aconteceu, e o que a campanha fez depois do desmentido", [
        linhaTempo([
          ["23/09", "passa a circular que o Flávio, se eleito, tiraria o título de padroeira. O projeto citado, de 2007, está arquivado desde 2008.", ""],
          ["24/09", "no Em Pauta, da GloboNews, a comentarista fala de uma reação católica a uma mobilização evangélica; o trecho passa a circular como “o Flávio vai tirar”. À noite, ele desmente.", ""],
          ["25/09", "de madrugada, a GloboNews corrige e pede desculpas. À tarde, Mendonça, no TSE, manda remover 1.125 posts e chama a associação de “notoriamente inverídica”.", ""],
          ["27/09", "Lula, no Canal Livre: “eu não sei se foi fake news”. No mesmo dia, Dino, no STF, derruba a ordem do TSE.", ""],
          ["28/09", "em Belém, “ninguém vai avacalhar com Nossa Senhora”; Janja: “o outro lado quer o fim da Padroeira”. À noite, Fux restabelece a remoção.", ""],
          ["30/09", "o plenário do TSE confirma a remoção, restrita a quem afirma como fato que o Flávio propôs ou apoiou a retirada. No mesmo dia, manda apagar 4 posts com a capa falsa da Veja contra o Lula.", ""],
          ["01–02/10", "a campanha impulsiona, por R$ 70 mil, um corte em que Lula promete manter o título.", ""],
        ]),
        h("div", { class: "numeros" },
          numero("1.125", "posts removidos em 25/09", "falso"),
          numero("2 dias", "entre a correção e a fala de Lula"),
          numero("R$ 70 mil", "no impulsionamento do corte", "f"),
          numero("—", "registros da campanha repetindo a autoria", "ok"))],
        "Datas de publicação, de correção e de decisão. “Insistir” aqui é o que está documentado: o tema continuou nos discursos e no impulsionamento depois de 25/09; a afirmação de que o Flávio tinha o projeto não se repete em nenhum registro que eu tenha achado."),
      mais: [{
        rot: "Campanha, apoiador e peça oficial — o que é o quê",
        corpo: [
          p("<b>Fala de campanha.</b> O que tem data, palco e responsável: a entrevista de Lula à Band em 27/09, o discurso em Belém em 28/09, a fala de Janja no mesmo ato, as imagens erguidas em Belém e Fortaleza, o impulsionamento pago do corte. É o que este caso trata."),
          p("<b>Conteúdo de apoiador.</b> A história começou a circular na noite de 23/09 por perfis de esquerda, segundo o Estadão, e o monitoramento da campanha de Flávio apontou o perfil “Dilma Bolada” como um dos pontos de partida — o responsável negou ter divulgado informação falsa. Não há registro de que a campanha do Lula tenha produzido ou distribuído esses posts: são de apoiadores, e a campanha não responde por eles."),
          p("<b>Peça oficial registrada.</b> A propaganda do PT que, em 29/09, chamou de “inaceitável” o que descreveu como ataque do Flávio à CNBB e à Igreja Católica; o vídeo de 26/09 do perfil “Brasil com Lula” que põe em dúvida a posição dele sobre a padroeira, mantido no ar por decisão de 17/10; e o corte impulsionado com R$ 70 mil. São peças da campanha, registradas e rastreáveis."),
        ],
      }, {
        rot: "O que eu não encontrei", classe: "adendo",
        corpo: [
          p("Não achei registro de a campanha, depois de 25/09, voltar a dizer que o Flávio propôs ou apoia a retirada do título. O que os registros mostram é o enquadramento genérico — “o outro lado quer o fim da padroeira” — e a recusa de Lula em aceitar o rótulo de fake news."),
          p("Um dirigente do PT disse à " + a("CNN", "https://www.cnnbrasil.com.br/eleicoes/pt-ve-escorregao-de-flavio-em-critica-a-cnbb-e-avalia-explorar-declaracao/") + " que o partido seguiria lembrando que Galli, autor do projeto, foi assessor especial de Jair Bolsonaro. Isso é verdade e é outra coisa: o projeto existe, é de 2007 e é do campo bolsonarista; o que não existe é o Flávio ter proposto ou apoiado."),
          p("Em 17/10, o TSE negou remover um vídeo da campanha do Lula que chamava o Flávio de “mentiroso Master” e punha em dúvida sua posição sobre a padroeira. A ministra Estela Aranha considerou que o vídeo é " + a("crítica, não afirmação de fato falso", "https://noticias.r7.com/eleicoes/2026/tse-nega-remocao-de-video-que-chama-flavio-bolsonaro-de-mentiroso-master-17102026/") + " — a mesma linha que o plenário adotou em 30/09."),
        ],
      }, {
        rot: "O servidor da Secom e o pedido de prisão",
        corpo: [
          p("O episódio mais próximo de “insistir no falso” não é da campanha. A notícia-crime da campanha de Flávio afirma que George Marques, coordenador-geral de Estratégia e Informação da Secom, compartilhou um post que pedia para “parar de divulgar a retratação” e “continuar compartilhando que nossa senhora foi atacada, precisa chegar no interior do Nordeste, no interior do Norte”."),
          p("A Secom respondeu que a manifestação foi pessoal, em perfil particular, fora do expediente e em equipamento próprio. Em 30/09, a Justiça Eleitoral " + a("negou a prisão", "https://www.cnnbrasil.com.br/politica/justica-nega-pedido-de-prisao-de-servidor-de-lula-mas-restringe-redes/") + " pedida pela campanha, proibiu Marques de publicar conteúdo político-eleitoral até o fim da eleição e enviou o caso à Polícia Federal."),
        ],
      }],
    });
  }

  // ── quantos casos a pessoa já viu ──────────────────────────────────────
  // Uma pílula fixa embaixo, só enquanto a lista está na tela: o anel enche e o
  // número sobe conforme os cartões passam. Assim fica claro que tem mais
  // caso abaixo. Os cartões entram 300px antes de aparecer, sem demora.
  function contador(lista) {
    var cards = [].slice.call(lista.querySelectorAll(".caso")), total = cards.length, vistos = {};
    var R = 15, C = 2 * Math.PI * R;
    var arco = s("circle", { cx: 18, cy: 18, r: R, class: "cont-arco", "stroke-dasharray": C, "stroke-dashoffset": C });
    var anel = s("svg", { viewBox: "0 0 36 36", class: "cont-anel", "aria-hidden": "true" });
    anel.appendChild(s("circle", { cx: 18, cy: 18, r: R, class: "cont-fundo" }));
    anel.appendChild(arco);
    var num = h("b", { text: "0" });
    var pil = h("div", { class: "contador", role: "status", "aria-live": "polite" }, anel,
      h("span", { class: "cont-txt" }, num, h("span", { text: " de " + total + " casos vistos" })));
    document.body.appendChild(pil);
    function pintar() {
      var n = Object.keys(vistos).length;
      if (num.textContent !== String(n)) { num.textContent = n; pil.classList.remove("pulo"); void pil.offsetWidth; pil.classList.add("pulo"); }
      arco.setAttribute("stroke-dashoffset", C * (1 - n / total));
      pil.classList.toggle("completo", n === total);
    }
    if (!("IntersectionObserver" in window)) { cards.forEach(function (c) { c.classList.add("visivel"); }); return; }
    var entra = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("visivel"); entra.unobserve(e.target); } });
    }, { rootMargin: "0px 0px 300px 0px" });
    var viu = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { vistos[e.target.id] = 1; viu.unobserve(e.target); } });
      pintar();
    }, { threshold: 0.55 });
    var naTela = new IntersectionObserver(function (es) { pil.classList.toggle("on", es[0].isIntersecting); }, { rootMargin: "-30% 0px -30% 0px" });
    cards.forEach(function (c) { entra.observe(c); viu.observe(c); });
    naTela.observe(lista);
  }

  // ── montar os casos ────────────────────────────────────────────────────
  function montarCasos() {
    var lista = document.getElementById("lista-casos");
    var lados = fetch("/static/casos/lados.json" + (VERSAO ? "?v=" + encodeURIComponent(VERSAO) : ""))
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    Promise.all([pedir("acusacoes.json"), pedir("casos_videos.json"), lados]).then(function (r) {
      var d = r[0];
      V = r[1]; LADOS = r[2];
      lista.textContent = "";
      [virada, pesquisas, caminhonete, secoesAte10, silvaJardim, consulta, cedula, eleitores, curva, biometria, mesario, salaCofre, soma, mesmaSecao, zonas].forEach(function (f) {
        try { lista.appendChild(f(d)); } catch (e) { console.error(e); }
      });
      lista.appendChild(h("div", { class: "divisa-casos" },
        h("h3", { text: "Além da urna" }),
        h("p", { text: "Denúncias que não são sobre a contagem dos votos, mas sobre a campanha: abuso de poder, desinformação e compra de voto. As ações no TSE ainda não foram julgadas no mérito — a exceção é o placar de decisões sobre desinformação, que reúne justamente liminares e as poucas sentenças." })));
      [prorrogacao, onibus, desfile, pacote, maquinaCelular, exercito, universidades, mesaria, faccoes, padroeira, desinformacao, compra].forEach(function (f) {
        try { lista.appendChild(f(d)); } catch (e) { console.error(e); }
      });

      contador(lista);
    }).catch(function () {
      lista.innerHTML = "<p class='carregando'>Não consegui abrir os casos agora. Recarregue a página.</p>";
    });
  }

  document.addEventListener("DOMContentLoaded", montarCasos);
})();
