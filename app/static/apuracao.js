/* Apuração ao vivo (/apuracao) — página pública.
 *
 * Lê /apuracao/estado.json (gravado pelo cron a cada mudança no TSE) e redesenha.
 * O fetch usa cache "no-cache": o navegador manda o ETag e o servidor responde
 * 304 quando nada mudou — é isso que deixa mil pessoas olhando sem pesar no Pi.
 * Aba escondida não consulta nada.
 *
 * DOM montado por h(), que só escreve TEXTO (textContent): dado do TSE nunca vira
 * HTML. Cor de partido vem do JSON e entra como variável CSS (--cor).
 */
(function () {
  "use strict";

  // A mesma página serve a transmissão pública (/apuracao) e a versão privada de
  // resultado final dentro do /politicos: `data-base` diz de onde vêm os dados e
  // `data-final="1"` desliga tudo o que só faz sentido com a apuração correndo
  // (modo Previsão/Ao vivo, pulso, série, avisos, mapa do % apurado).
  var RAIZ = document.getElementById("ap");
  var BASE = (RAIZ && RAIZ.getAttribute("data-base")) || "/apuracao";
  var FINAL = !!(RAIZ && RAIZ.getAttribute("data-final") === "1");
  // Eleição encerrada (25/10/2026): os JSON são ARQUIVO CONGELADO. Não há pulso,
  // não há série crescendo, não há nada a revalidar de 8 em 8 segundos — e por
  // isso a página não pode ficar num laço de `fetch` para sempre (era o que ela
  // fazia no modo ao vivo, e era exatamente o gasto contínuo que a eleição ter
  // minado deixou de justificar). `estatico()` lê o pulso UMA vez para saber se
  // o servidor é arquivo ou coletor vivo; daí em diante ninguém pede de novo.
  var ARQUIVO = FINAL;
  // 2º turno (25/10/2026): o presidente vira a aba principal. Vale também no
  // arquivo, porque o 2026 congelado é o 2º turno.
  var TURNO2 = !!(RAIZ && RAIZ.getAttribute("data-turno") === "2");
  var T_AGORA = FINAL ? "no resultado" : "agora";
  var T_PONTO = FINAL ? "resultado" : "agora";
  var T_PAROU = FINAL ? "resultado final" : "se parasse agora";
  var INTERVALO_MS = 8000;
  var INTERVALO_SERIE_MS = 45000;
  var FOCO_CHAVE = "apuracao-foco";
  var FAV_CHAVE = "apuracao-favoritos";
  // Celular mostra pouco de cada vez: cada lista abre curta e cresce no "mostrar mais".
  function celular() { return window.matchMedia("(max-width: 640px)").matches; }
  function passo() { return celular() ? 8 : 20; }

  var app = {
    estado: null, gerado: null, vista: "alesc", uf: null, foco: null,
    ufs: {}, serie: [], ultimoOk: 0, falhas: 0, espera: INTERVALO_MS,
    busca: "", filtroAgr: "", soFavs: false, limite: null, timer: null,
    favs: {}, abertos: {}, pulso: null,
    municipios: null, mun: {}, munSel: null, situacoes: null,
    mapa: null, mapaBr: null, basesCache: {}, baseSel: {},
    extras: {}, eleitosSel: null, majSoFoco: true, ordemEsp: true, modo: "previsao",
  };
  var MUN_CHAVE = "apuracao-municipio";
  var EXTRAS = window.AP_EXTRAS = window.AP_EXTRAS || {};
  var AVISO_CHAVE = "apuracao-avisos";

  // ── utilidades ──────────────────────────────────────────────────────────
  function h(tag, attrs) {
    var el = document.createElement(tag);
    var a = attrs || {};
    Object.keys(a).forEach(function (k) {
      var v = a[k];
      if (v === null || v === undefined || v === false) return;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k === "vars") Object.keys(v).forEach(function (n) { el.style.setProperty(n, v[n]); });
      else if (k.indexOf("on") === 0) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    });
    for (var i = 2; i < arguments.length; i++) anexar(el, arguments[i]);
    return el;
  }
  function anexar(el, filho) {
    if (filho === null || filho === undefined || filho === false) return;
    if (Array.isArray(filho)) { filho.forEach(function (f) { anexar(el, f); }); return; }
    el.appendChild(typeof filho === "object" ? filho : document.createTextNode(String(filho)));
  }
  var SVG = "http://www.w3.org/2000/svg";
  function s(tag, attrs) {
    var el = document.createElementNS(SVG, tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") el.textContent = attrs[k];
      else if (k === "vars") Object.keys(attrs[k]).forEach(function (n) { el.style.setProperty(n, attrs[k][n]); });
      else el.setAttribute(k, attrs[k]);
    });
    return el;
  }
  var nf = new Intl.NumberFormat("pt-BR");
  function num(x) { return nf.format(Math.round(x || 0)); }
  function pct(x, casas) {
    return (x || 0).toLocaleString("pt-BR", { minimumFractionDigits: casas === undefined ? 1 : casas,
      maximumFractionDigits: casas === undefined ? 1 : casas }) + "%";
  }
  function $(id) { return document.getElementById(id); }
  function curto(x) {
    x = Math.round(x || 0);
    return x >= 10000 ? (x / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mil" : num(x);
  }
  // ── modo: "previsao" (o esperado no fim) ou "aovivo" (se parasse agora) ──
  // Escolha de cada pessoa, guardada no navegador dela. O número do OUTRO modo
  // aparece sempre discreto embaixo do principal.
  var MODO_CHAVE = "apuracao-modo";
  function lerModo() {
    try { return localStorage.getItem(MODO_CHAVE) === "aovivo" ? "aovivo" : "previsao"; } catch (e) { return "previsao"; }
  }
  function prev() { return !FINAL && app.modo !== "aovivo"; }
  var CAMPOS = { cad: ["cad_esp", "cadeiras"], votos: ["pe", "votos"], pct: ["pct_esp", "pct"],
    qp: ["qp_esp", "qp"], fases: ["fases_esp", "fases"] };
  function princ(x, k) { var c = CAMPOS[k]; return prev() && x[c[0]] != null ? x[c[0]] : x[c[1]]; }
  // Cada modo mostra SÓ os próprios números (pedido do Cauê, 04/10): nada do outro.
  function secund() { return null; }
  function rotSec() { return prev() ? "agora" : "previsão"; }
  function vC(c) { return prev() && c.pe != null ? c.pe : c.v; }
  function vCsec() { return null; }
  function entraC(c) { return prev() && c.pe != null ? c.pef : c.proj; }
  function usaPrev(cargo) { return prev() && !!cargo.esperado; }
  function aprox(x, usa) { return (usa ? "≈ " : "") + (usa ? curto(x) : num(x)); }
  function mini(txt) { return txt == null ? null : h("span", { class: "ap-agora-mini ap-bloco", text: txt }); }
  function desenharModo() {
    Array.prototype.forEach.call(document.querySelectorAll(".ap-modo-btn"), function (b) {
      var on = b.getAttribute("data-modo") === app.modo;
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.classList.toggle("on", on);
    });
  }

  // ── foco ────────────────────────────────────────────────────────────────
  function lerFoco() {
    try {
      var salvo = JSON.parse(localStorage.getItem(FOCO_CHAVE) || "null");
      if (Array.isArray(salvo)) return salvo;     // vazio vale: dá para seguir só candidatos
    } catch (e) { /* sem localStorage: segue o padrão */ }
    return null;
  }
  function gravarFoco() {
    try { localStorage.setItem(FOCO_CHAVE, JSON.stringify(app.foco)); } catch (e) { /* ok */ }
  }
  function emFoco(agr) {
    if (!app.foco) return false;
    if (app.foco.indexOf(agr.id) >= 0 || app.foco.indexOf(agr.sigla) >= 0) return true;
    // Na Câmara `partidos` é {sigla: votos}; numa UF é [{sg, votos}].
    var lista = Array.isArray(agr.partidos) ? agr.partidos.map(function (p) { return p.sg; })
      : Object.keys(agr.partidos || {});
    return lista.some(function (sg) { return app.foco.indexOf(String(sg).toUpperCase()) >= 0; });
  }
  function candidatoEmFoco(c) { return app.foco && app.foco.indexOf(String(c.p).toUpperCase()) >= 0; }

  // ── favoritos: candidato a candidato, separados por tipo de eleição ─────
  // Chave = cargo + UF ("est-sc", "fed-sc", "fed-sp", "pres", "gov-sc", "sen-sc");
  // dentro dela, o NÚMERO do candidato, que é único naquele cargo e naquela UF.
  var TIPOS = { "est-sc": "Deputado estadual · SC", "fed-sc": "Deputado federal · SC",
    "pres": "Presidente", "gov-sc": "Governador · SC", "sen-sc": "Senado · SC" };
  function nomeTipo(t) { return TIPOS[t] || ("Deputado federal · " + t.slice(4).toUpperCase()); }
  function lerFavs() {
    try {
      var d = JSON.parse(localStorage.getItem(FAV_CHAVE) || "{}");
      return d && typeof d === "object" && !Array.isArray(d) ? d : {};
    } catch (e) { return {}; }
  }
  function gravarFavs() {
    try { localStorage.setItem(FAV_CHAVE, JSON.stringify(app.favs)); } catch (e) { /* ok */ }
  }
  function ehFav(tipo, c) { return (app.favs[tipo] || []).indexOf(String(c.n)) >= 0; }
  function estrela(tipo, c) {
    var on = ehFav(tipo, c);
    return h("button", { type: "button", class: "ap-estrela" + (on ? " on" : ""),
      "aria-pressed": on ? "true" : "false",
      "aria-label": (on ? "Tirar " : "Seguir ") + c.nm + " (" + nomeTipo(tipo) + ")",
      title: on ? "Deixar de seguir" : "Seguir este candidato", text: on ? "★" : "☆",
      onclick: function (ev) {
        ev.stopPropagation();
        var lista = app.favs[tipo] || [], n = String(c.n), i = lista.indexOf(n);
        if (i >= 0) lista.splice(i, 1); else lista.push(n);
        app.favs[tipo] = lista;
        if (!lista.length) delete app.favs[tipo];
        gravarFavs(); desenhar();
      } });
  }
  function maisBotao(chave, total, mostrados, rotulo) {
    if (total <= mostrados) return null;
    return h("button", { type: "button", class: "ap-mais",
      text: (rotulo || "Mostrar mais") + " (" + (total - mostrados) + ")",
      onclick: function () { app.abertos[chave] = mostrados + passo(); desenhar(); } });
  }
  function limiteDe(chave, inicial) { return app.abertos[chave] || inicial; }

  function partidosConhecidos() {
    var vistos = {};
    var e = app.estado;
    if (e && e.camara) e.camara.agremiacoes.forEach(function (a) {
      Object.keys(a.partidos || {}).forEach(function (sg) { vistos[sg.toUpperCase()] = a.cor; });
    });
    if (e && e.sc && e.sc.estadual) e.sc.estadual.agremiacoes.forEach(function (a) {
      a.partidos.forEach(function (p) { vistos[p.sg.toUpperCase()] = a.cor; });
    });
    return vistos;
  }

  function desenharFoco() {
    var cores = partidosConhecidos();
    var chips = $("ap-foco-chips");
    chips.textContent = "";
    if (!app.foco.length) chips.appendChild(h("span", { class: "ap-foco-vazio", text: "nenhum partido · só seus ★" }));
    app.foco.forEach(function (sg) {
      chips.appendChild(h("span", { class: "ap-chip", vars: { "--cor": cores[sg] || "#9ca3af" } }, sg,
        h("button", { type: "button", "aria-label": "Tirar " + sg + " do foco", text: "×",
          onclick: function () {
            app.foco = app.foco.filter(function (x) { return x !== sg; });
            gravarFoco(); desenhar();
          } })));
    });
    var sel = $("ap-foco-select");
    var atual = sel.value;
    sel.textContent = "";
    sel.appendChild(h("option", { value: "", text: "+ partido" }));
    Object.keys(cores).sort().forEach(function (sg) {
      if (app.foco.indexOf(sg) < 0) sel.appendChild(h("option", { value: sg, text: sg }));
    });
    sel.value = atual && app.foco.indexOf(atual) < 0 ? atual : "";
  }

  // ── hemiciclo ───────────────────────────────────────────────────────────
  function posicoes(total) {
    // Fileiras pela quantidade: poucas cadeiras em muitas fileiras viram pontos soltos.
    var linhas = total <= 12 ? 2 : total <= 30 ? 3 : total <= 60 ? 4 : total <= 150 ? 7 : 12;
    var r0 = 0.46, raios = [], soma = 0;
    for (var i = 0; i < linhas; i++) {
      var r = r0 + (1 - r0) * (linhas === 1 ? 1 : i / (linhas - 1));
      raios.push(r); soma += r;
    }
    var por = raios.map(function (r) { return Math.max(1, Math.round(total * r / soma)); });
    por[por.length - 1] += total - por.reduce(function (a, b) { return a + b; }, 0);
    var pts = [];
    raios.forEach(function (r, i) {
      var n = por[i];
      for (var j = 0; j < n; j++) {
        pts.push({ ang: n === 1 ? Math.PI / 2 : Math.PI * (1 - j / (n - 1)), r: r });
      }
    });
    pts.sort(function (a, b) { return b.ang - a.ang || a.r - b.r; });
    // Raio da bolinha: o menor entre o passo das fileiras e o passo no arco mais apertado.
    var passoFileira = linhas > 1 ? (1 - r0) / (linhas - 1) : 0.3;
    var passoArco = Math.min.apply(null, raios.map(function (r, i) {
      return por[i] > 1 ? Math.PI * r / (por[i] - 1) : 1;
    }));
    return { pts: pts, linhas: linhas, raio: 0.36 * Math.min(passoFileira, passoArco) };
  }

  function hemiciclo(agremiacoes, vagas, rotulo, campo, legendaSub) {
    campo = campo || "cadeiras";
    var L = 400, A = 212, cx = L / 2, cy = A - 18, R = 176;
    var geo = posicoes(vagas);
    var raioBola = Math.min(16, R * geo.raio);
    var svg = s("svg", { viewBox: "0 0 " + L + " " + A, class: "ap-hemi", role: "img",
      "aria-label": rotulo });
    var fila = [];
    agremiacoes.forEach(function (a) { for (var k = 0; k < (a[campo] || 0); k++) fila.push(a); });
    geo.pts.forEach(function (p, i) {
      var a = fila[i];
      var c = s("circle", { cx: (cx + R * p.r * Math.cos(p.ang)).toFixed(1),
        cy: (cy - R * p.r * Math.sin(p.ang)).toFixed(1), r: raioBola.toFixed(1),
        fill: a ? a.cor : "#e2e8f0" });
      if (a && emFoco(a)) c.setAttribute("class", "foco");
      c.setAttribute("data-tip", a ? a.sigla + " · " + a[campo] + " cadeira(s)" : "vaga ainda sem dono");
      svg.appendChild(c);
    });
    var distribuidas = fila.length;
    svg.appendChild(s("text", { x: cx, y: cy - 22, "text-anchor": "middle", class: "ap-hemi-total",
      text: distribuidas ? String(vagas) : "—" }));
    svg.appendChild(s("text", { x: cx, y: cy - 4, "text-anchor": "middle", class: "ap-hemi-sub",
      text: distribuidas ? (legendaSub || "cadeiras projetadas") : "aguardando votos" }));
    return svg;
  }

  function ordenarEsp(agrs) {
    return agrs.slice().sort(function (a, b) { return (princ(b, "cad") || 0) - (princ(a, "cad") || 0) || princ(b, "votos") - princ(a, "votos"); });
  }

  function legendaDupla(agremiacoes) {
    return h("div", { class: "ap-legenda" }, ordenarEsp(agremiacoes).filter(function (a) { return a.cadeiras || a.cad_esp; })
      .map(function (a) {
        var p = princ(a, "cad"), o = secund(a, "cad");
        var muda = o != null && o !== p;
        return h("span", { class: (emFoco(a) ? "foco" : "") + (muda ? " muda" : ""), vars: { "--cor": a.cor },
          "data-tip": a.sigla + ": " + a.cad_esp + " na previsão, " + a.cadeiras + " agora" },
          a.sigla + " ", h("b", { text: String(p) }), muda ? h("small", { class: "ap-agora-mini", text: " (" + rotSec() + " " + o + ")" }) : null);
      }));
  }

  function legenda(agremiacoes) {
    return h("div", { class: "ap-legenda" }, agremiacoes.filter(function (a) { return a.cadeiras; })
      .map(function (a) {
        return h("span", { class: emFoco(a) ? "foco" : null, vars: { "--cor": a.cor } },
          a.sigla + " ", h("b", { text: String(a.cadeiras) }));
      }));
  }

  // ── pedaços ─────────────────────────────────────────────────────────────
  function kpi(rotulo, valor, nota, barra) {
    return h("div", { class: "ap-kpi" },
      h("div", { class: "ap-kpi-rotulo", text: rotulo }),
      h("div", { class: "ap-kpi-valor", text: valor }),
      nota ? h("div", { class: "ap-kpi-nota", text: nota }) : null,
      barra !== undefined ? h("div", { class: "ap-barra" }, h("span", { vars: { "--p": Math.min(100, barra) + "%" } })) : null);
  }
  // Precedência: o TSE proclamou > garantido pela matemática > projeção de agora.
  function selo(c, cargo) {
    // Resultado final: vale a situação que o TSE proclamou, e só ela.
    if (FINAL) return h("span", { class: "ap-selo " + (c.e ? "oficial" : "fora"),
      text: (c.st || (c.e ? "eleito" : "não eleito")).toLowerCase() });
    if (c.e) return h("span", { class: "ap-selo oficial", text: "eleito (TSE)" });
    if (c.mat === "eleito-qp") return h("span", { class: "ap-selo garantido",
      "data-tip": "Eleito mesmo que todo o voto que falta vá contra: já não há como perder a cadeira.",
      text: "eleito · garantido" });
    if (c.mat === "eleito-sobras") return h("span", { class: "ap-selo garantido",
      "data-tip": "Eleito pelas sobras (maior média) mesmo no pior caso do voto que falta.",
      text: "eleito nas sobras · garantido" });
    if (c.mat === "fora") return h("span", { class: "ap-selo eliminado",
      "data-tip": "Nem com todo o voto que falta ele alcança uma cadeira.", text: "fora · garantido" });
    if (c.proj === "QP") return h("span", { class: "ap-selo qp", text: "entra (QP)" });
    if (c.proj === "média") return h("span", { class: "ap-selo media", text: "entra (média)" });
    if (c.proj === "3ª fase") return h("span", { class: "ap-selo f3", text: "entra (3ª fase)" });
    return h("span", { class: "ap-selo fora", text: cargo && cargo.qe ? "fora por ora" : "—" });
  }
  function cartao(titulo, legendaTxt) {
    var c = h("section", { class: "ap-cartao" }, h("h2", { text: titulo }),
      legendaTxt ? h("p", { class: "ap-legenda-cartao", text: legendaTxt }) : null);
    for (var i = 2; i < arguments.length; i++) anexar(c, arguments[i]);
    return c;
  }

  function cartaoFoco(cargo, agr, tipo) {
    var usa = usaPrev(cargo) && agr.cad_esp != null;
    var cands = (cargo.candidatos || []).filter(function (c) { return c.a === agr.id; })
      .sort(function (a, b) { return vC(b) - vC(a); });
    var garantidas = cands.filter(function (c) { return c.mat === "eleito-qp" || c.mat === "eleito-sobras"; }).length;
    var chaveMini = "mini:" + tipo + ":" + agr.id;
    var nMini = limiteDe(chaveMini, celular() ? 3 : 5);
    var cad = usa ? agr.cad_esp : agr.cadeiras, cadO = secund(agr, "cad");
    var fasesObj = (usa ? agr.fases_esp : agr.fases) || {};
    var fases = [];
    if (fasesObj.QP) fases.push(h("span", { class: "ap-fase", text: fasesObj.QP + " pelo QP" }));
    if (fasesObj["média"]) fases.push(h("span", { class: "ap-fase", text: fasesObj["média"] + " por média" }));
    if (fasesObj["3ª fase"]) fases.push(h("span", { class: "ap-fase", text: fasesObj["3ª fase"] + " na 3ª fase" }));
    if (!fases.length) fases.push(h("span", { class: "ap-fase", text: cargo.qe ? "sem cadeira" : "aguardando votos" }));
    var votos = usa ? agr.pe : agr.votos, qp = usa ? agr.qp_esp : agr.qp;
    var qe = usa ? cargo.esperado.qe : cargo.qe;
    var falta = qe ? Math.max(0, Math.ceil((Math.floor(qp || 0) + 1) * qe - votos)) : 0;
    var oficial = cargo.apuracao.totalizado && agr.cadeiras_tse;
    var qpFmt = function (x) { return (x || 0).toLocaleString("pt-BR", { maximumFractionDigits: 2 }); };
    function dado(valor, rotulo, outro) {
      return h("div", {}, h("b", { text: valor }), rotulo, outro != null ? mini(rotSec() + " " + outro) : null);
    }
    return h("article", { class: "ap-cartao ap-focado", vars: { "--cor": agr.cor } },
      h("div", { class: "ap-focado-topo" },
        h("span", { class: "ap-focado-nome", text: agr.sigla }),
        oficial ? h("span", { class: "ap-selo oficial", text: agr.cadeiras_tse + " oficiais" }) : null),
      h("div", { class: "ap-focado-cad" + (cadO != null && cadO !== cad ? " muda" : "") }, String(cad),
        h("small", { text: (cad === 1 ? "cadeira" : "cadeiras") + (usa ? " na previsão" : FINAL ? "" : " se parasse agora") })),
      garantidas ? h("div", { class: "ap-agora-linha", text: garantidas + " já garantida" + (garantidas > 1 ? "s" : "") }) : null,
      h("div", { class: "ap-focado-fases" }, fases),
      h("div", { class: "ap-focado-dados" },
        dado(aprox(votos, usa), "votos", null),
        dado(pct(usa ? agr.pct_esp : agr.pct, 2), "dos válidos", secund(agr, "pct") != null ? pct(secund(agr, "pct"), 2) : null),
        dado(qpFmt(qp), "QP", secund(agr, "qp") != null ? qpFmt(secund(agr, "qp")) : null)),
      qe && qp >= 1 && !FINAL ? h("div", { class: "ap-qp" }, "Faltariam ≈ " + num(falta) + " votos para a próxima cadeira pelo QP") : null,
      h("ul", { class: "ap-mini-lista" }, cands.slice(0, nMini).map(function (c) {
        var o = vCsec(c);
        return h("li", {}, estrela(tipo, c),
          h("span", { class: "ap-mini-nome" }, c.nm + " ", h("span", { class: "ap-mudo", text: c.n })),
          h("span", { class: "ap-v" }, h("b", { text: aprox(vC(c), usa && c.pe != null) }),
            o != null ? mini(rotSec() + " " + (usa ? num(o) : "≈ " + curto(o))) : null),
          seloFinal(c, cargo));
      })), maisBotao(chaveMini, cands.length, nMini, "Ver mais candidatos"));
  }

  function seloFinal(c, cargo) {
    if (c.e || c.mat) return selo(c, cargo);
    if (prev() && c.pe != null) return h("span", { class: "ap-selo " + (c.pef ? "fim-entra" : "fim-fora"),
      "data-tip": "Previsão ≈ " + num(c.pe) + " votos (confiança " + (c.pc || "—") + ").",
      text: c.pef ? "▲ entra" + (c.pef === "média" ? " (média)" : c.pef === "3ª fase" ? " (3ª fase)" : "") : "▽ fica fora" });
    return selo(c, cargo);
  }

  function tabelaAgremiacoes(cargo, tipo) {
    var corpo = h("tbody");
    var chave = "agr:" + tipo;
    var n = limiteDe(chave, celular() ? 6 : 99);
    var usa = usaPrev(cargo);
    var tem = !!cargo.esperado;
    var qpFmt = function (x) { return x ? x.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) : "—"; };
    ordenarEsp(cargo.agremiacoes).slice(0, n).forEach(function (a) {
      var fs = (usa ? a.fases_esp : a.fases) || {};
      var so = function () { return null; };
      corpo.appendChild(h("tr", { "data-agr": a.id, class: emFoco(a) ? "foco" : null,
        onclick: function () { app.filtroAgr = a.id; app.limite = null; desenhar();
          var alvo = $("ap-candidatos"); if (alvo) alvo.scrollIntoView({ behavior: "smooth" }); } },
        h("td", {}, h("span", { class: "ap-nome-agr", vars: { "--cor": a.cor }, text: a.sigla }),
          a.federacao ? h("span", { class: "ap-partidos", text: a.partidos.map(function (p) { return p.sg; }).join(" · ") }) : null),
        h("td", { class: "num" }, aprox(usa ? a.pe : a.votos, usa), so(usa ? num(a.votos) : "≈ " + curto(a.pe))),
        h("td", { class: "num" }, pct(usa ? a.pct_esp : a.pct, 2), so(pct(usa ? a.pct : a.pct_esp, 2))),
        h("td", { class: "num ocultar-celular", text: qpFmt(usa ? a.qp_esp : a.qp) }),
        h("td", { class: "num ocultar-celular", text: [fs.QP || 0, fs["média"] || 0, fs["3ª fase"] || 0].join(" / ") }),
        h("td", { class: "num" }, h("b", { text: String(usa ? a.cad_esp : a.cadeiras) }), so(String(usa ? a.cadeiras : a.cad_esp))),
        cargo.apuracao.totalizado ? h("td", { class: "num ocultar-celular", text: a.cadeiras_tse ? String(a.cadeiras_tse) : "—" }) : null));
    });
    return h("div", { class: "ap-tabela-rolagem" }, h("table", { class: "ap-tabela" },
      h("thead", {}, h("tr", {},
        h("th", { text: "Partido / federação" }), h("th", { class: "num", text: usa ? "Votos (previsão)" : "Votos" }),
        h("th", { class: "num", text: "%" }), h("th", { class: "num ocultar-celular", text: "QP" }),
        h("th", { class: "num ocultar-celular", text: "QP / média / 3ª" }),
        h("th", { class: "num", text: usa ? "Cadeiras (previsão)" : FINAL ? "Cadeiras" : "Cadeiras agora" }),
        cargo.apuracao.totalizado ? h("th", { class: "num ocultar-celular", text: "Oficial" }) : null)),
      corpo), maisBotao(chave, cargo.agremiacoes.length, n, "Todos os partidos"));
  }

  function listaCandidatos(cargo, tipo) {
    if (!app.limite) app.limite = passo();
    var temEsp = prev() && (cargo.candidatos || []).some(function (c) { return c.pe != null; });
    var tem = (cargo.candidatos || []).some(function (c) { return c.pe != null; });
    var busca = h("input", { type: "search", placeholder: "Buscar candidato, número ou partido",
      value: app.busca, "aria-label": "Buscar candidato" });
    busca.addEventListener("input", function () { app.busca = busca.value; app.limite = passo(); desenharLista(); });
    var soFavs = h("button", { type: "button", class: "ap-so-favs" + (app.soFavs ? " on" : ""),
      "aria-pressed": app.soFavs ? "true" : "false", text: "★ só os meus",
      onclick: function () { app.soFavs = !app.soFavs; app.limite = passo(); desenhar(); } });
    var filtro = h("select", { "aria-label": "Filtrar por partido ou federação" },
      h("option", { value: "", text: "Todos os partidos" }),
      cargo.agremiacoes.map(function (a) { return h("option", { value: a.id, text: a.sigla }); }));
    filtro.value = app.filtroAgr;
    filtro.addEventListener("change", function () { app.filtroAgr = filtro.value; app.limite = passo(); desenharLista(); });
    var alvo = h("div");
    var ordenados = (cargo.candidatos || []).slice().sort(function (a, b) { return vC(b) - vC(a); });
    var posicao = {};
    ordenados.forEach(function (c, i) { posicao[c.n] = i + 1; });
    var siglaDe = {};
    cargo.agremiacoes.forEach(function (a) { siglaDe[a.id] = a; });
    function desenharLista() {
      var q = app.busca.trim().toUpperCase();
      var linhas = ordenados.filter(function (c) {
        if (app.soFavs && !ehFav(tipo, c)) return false;
        if (app.filtroAgr && c.a !== app.filtroAgr) return false;
        if (!q) return true;
        return (c.nm + " " + c.n + " " + c.p).toUpperCase().indexOf(q) >= 0;
      });
      var corpo = h("tbody");
      linhas.slice(0, app.limite).forEach(function (c) {
        var agr = siglaDe[c.a] || {};
        corpo.appendChild(h("tr", { class: (ehFav(tipo, c) ? "fav " : "") + (candidatoEmFoco(c) ? "foco" : "") },
          h("td", { class: "ap-col-estrela" }, estrela(tipo, c)),
          h("td", { class: "num ap-mudo ap-col-pos", text: String(posicao[c.n]) }),
          h("td", {}, h("b", { text: c.nm }),
            h("span", { class: "ap-partidos", text: c.n + " · " + c.p + (agr.federacao ? " (" + agr.sigla + ")" : "") +
              (c.pc ? " · confiança " + c.pc : "") })),
          h("td", { class: "num" }, h("b", { text: aprox(vC(c), temEsp && c.pe != null) }),
            tem && vCsec(c) != null ? mini(rotSec() + " " + (temEsp ? num(vCsec(c)) : "≈ " + curto(vCsec(c)))) : null),
          h("td", { class: "num" }, seloFinal(c, cargo))));
      });
      alvo.textContent = "";
      alvo.appendChild(h("div", { class: "ap-tabela-rolagem" }, h("table", { class: "ap-tabela" },
        h("thead", {}, h("tr", {}, h("th", { class: "ap-col-estrela", "aria-label": "Seguir" }),
          h("th", { class: "num ap-col-pos", text: "#" }), h("th", { text: "Candidato" }),
          h("th", { class: "num", text: temEsp ? "Votos (previsão)" : "Votos" }),
          h("th", { class: "num", text: temEsp ? "Previsão" : "Agora" }))), corpo)));
      if (linhas.length > app.limite) {
        alvo.appendChild(h("button", { type: "button", class: "ap-mais",
          text: "Mostrar mais (" + (linhas.length - app.limite) + ")",
          onclick: function () { app.limite += passo() * 2; desenharLista(); } }));
      }
      if (!linhas.length) alvo.appendChild(h("p", { class: "ap-mudo", text: app.soFavs
        ? "Você ainda não segue ninguém aqui. Toque na ☆ ao lado de um nome." : "Ninguém com esse filtro." }));
    }
    desenharLista();
    return h("div", { id: "ap-candidatos" }, h("div", { class: "ap-filtros" }, busca, filtro, soFavs), alvo);
  }

  function serieFoco(campo, rotulo) {
    var campoEsp = campo + "_esp";
    var pts = app.serie.filter(function (p) { return p.pst && p.pst[campo] > 0; });
    if (pts.length < 2) return null;
    var usaEsp = prev() && pts.some(function (p) { return p[campoEsp] && Object.keys(p[campoEsp]).length; });
    var chaveP = usaEsp ? campoEsp : campo;
    if (usaEsp) pts = pts.filter(function (p) { return p[campoEsp] && Object.keys(p[campoEsp]).length; });
    if (pts.length < 2) return null;
    var focos = [], ref = (campo === "camara" ? app.estado.camara : campo === "estadual" ? app.estado.sc.estadual : app.estado.sc.federal);
    (ref.agremiacoes || []).forEach(function (a) { if (emFoco(a)) focos.push(a); });
    if (!focos.length) return null;
    var L = 600, A = 180, m = { e: 30, d: 90, t: 12, b: 26 };
    var maxY = 1;
    pts.forEach(function (p) { focos.forEach(function (a) { maxY = Math.max(maxY, (p[chaveP] || {})[a.id] || 0); }); });
    var topoX = Math.min(100, Math.max(25, Math.ceil(Math.max.apply(null, pts.map(function (p) { return p.pst[campo]; })) / 25) * 25));
    var x = function (v) { return m.e + (L - m.e - m.d) * v / topoX; };
    var y = function (v) { return A - m.b - (A - m.t - m.b) * v / maxY; };
    var svg = s("svg", { viewBox: "0 0 " + L + " " + A, class: "ap-serie", role: "img", "aria-label": rotulo });
    [0, .25, .5, .75, 1].map(function (f) { return Math.round(f * topoX); }).forEach(function (t) {
      svg.appendChild(s("text", { x: x(t), y: A - 8, "text-anchor": "middle", class: "rotulo", text: t + "%" }));
    });
    for (var k = 0; k <= maxY; k += Math.max(1, Math.ceil(maxY / 4))) {
      svg.appendChild(s("line", { x1: m.e, x2: L - m.d, y1: y(k), y2: y(k), class: "eixo" }));
      svg.appendChild(s("text", { x: m.e - 6, y: y(k) + 4, "text-anchor": "end", class: "rotulo", text: String(k) }));
    }
    focos.forEach(function (a) {
      var d = "", ultimo = null;
      pts.forEach(function (p, i) {
        var vx = x(p.pst[campo]), vy = y((p[chaveP] || {})[a.id] || 0);
        d += (i ? (" H" + vx.toFixed(1) + " V" + vy.toFixed(1)) : ("M" + vx.toFixed(1) + " " + vy.toFixed(1)));
        ultimo = { x: vx, y: vy, v: (p[chaveP] || {})[a.id] || 0 };
      });
      svg.appendChild(s("path", { d: d, class: "linha", vars: { "--cor": a.cor } }));
      svg.appendChild(s("circle", { cx: ultimo.x, cy: ultimo.y, r: 4, class: "ponto", vars: { "--cor": a.cor } }));
      svg.appendChild(s("text", { x: ultimo.x + 8, y: ultimo.y + 4, class: "nome", text: a.sigla + " " + ultimo.v }));
    });
    return cartao(usaEsp ? "Previsão de cadeiras do foco ao longo da noite" : "Cadeiras do foco ao longo da noite (se parasse em cada momento)",
      "Eixo horizontal: seções totalizadas. Cada degrau é uma atualização do TSE que mudou o número.", svg);
  }

  // A próxima legislatura contra a eleita em 2022: quem volta, quem chega, quem sai e por quê.
  function cartaoEsperados(cargo, tipo) {
    var cands = cargo.candidatos || [];
    var usa = usaPrev(cargo);
    if (!cands.some(function (c) { return c.pef !== undefined; }) && !cargo.mandato) return null;
    var siglaDe = {}, porN = {};
    cargo.agremiacoes.forEach(function (a) { siglaDe[a.id] = a; });
    cands.forEach(function (c) { porN[c.n] = c; });
    var dentro = function (c) { return !!(c.e || entraC(c)); };
    var eleitos = cands.filter(dentro).sort(function (a, b) { return vC(b) - vC(a); });
    var md = cargo.mandato;
    var casa = tipo === "est-sc" ? "ALESC" : "bancada de SC na Câmara";
    var n = limiteDe("esp:" + tipo, celular() ? 10 : 20);
    // A legislatura eleita em 2022 contra o modo escolhido (previsão ou agora).
    var saem = [], voltam = 0, novos = 0;
    if (md && md.lista22) {
      md.lista22.forEach(function (x) {
        var c = x.n26 ? porN[x.n26] : null;
        if (c && dentro(c)) { voltam++; return; }
        saem.push({ nm: x.nm, p: x.p, motivo: c ? "concorre e fica fora" + (usa ? " na previsão (≈ " + curto(c.pe) + " votos)" : " agora (" + num(c.v) + " votos)")
          : x.outro ? "concorre a " + x.outro : "não concorre" });
      });
      novos = eleitos.filter(function (c) { return !c.e22; }).length;
    }
    function linha(c) {
      var agr = siglaDe[c.a] || {};
      var tag = md ? (c.e22 ? ["reeleito", "volta"] : ["novo", "novo"]) : null;
      var o = vCsec(c);
      return h("li", { class: "ap-esp-item" + (candidatoEmFoco(c) || ehFav(tipo, c) ? " foco" : ""), vars: { "--cor": agr.cor || "#9ca3af" } },
        estrela(tipo, c),
        h("div", { class: "ap-favs-nome" }, h("b", { text: c.nm }),
          h("span", { class: "ap-partidos", text: (agr.sigla || c.p) + (usa && c.pc ? " · confiança " + c.pc : "") })),
        h("div", { class: "ap-favs-num" }, h("b", { text: aprox(vC(c), usa && c.pe != null) }),
          o != null ? mini(rotSec() + " " + (usa ? num(o) : "≈ " + curto(o))) : null),
        tag ? h("span", { class: "ap-selo " + tag[0], text: tag[1] }) : null);
    }
    var comp = null;
    if (md) {
      var ids = {};
      Object.keys(md.composicao_2022).forEach(function (k) { ids[k] = true; });
      cargo.agremiacoes.forEach(function (a) { if (princ(a, "cad")) ids[a.id] = true; });
      comp = h("div", { class: "ap-comp" }, Object.keys(ids).map(function (id) {
        var a = siglaDe[id] || { sigla: id, cor: "#9ca3af" };
        return { a: a, antes: md.composicao_2022[id] || 0, depois: siglaDe[id] ? princ(a, "cad") || 0 : 0 };
      }).sort(function (p, q) { return q.depois - p.depois || q.antes - p.antes; }).map(function (x) {
        var dif = x.depois - x.antes;
        return h("span", { class: "ap-comp-item" + (emFoco(x.a) ? " foco" : ""), vars: { "--cor": x.a.cor },
          "data-tip": x.a.sigla + ": " + x.antes + " eleitos em 2022 → " + x.depois + (usa ? " na previsão" : " " + T_AGORA) },
          x.a.sigla + " ", h("b", { text: x.antes + " → " + x.depois }),
          dif ? h("em", { class: dif > 0 ? "sobe" : "desce", text: (dif > 0 ? " +" : " ") + dif }) : null);
      }));
    }
    var quando = usa ? "na previsão" : FINAL ? "no resultado final" : "se a apuração parasse agora";
    return cartao((tipo === "est-sc" ? "ALESC 2027–2031" : "Câmara · bancada de SC 2027–2031") + " · quem " + (usa ? "deve ser eleito" : FINAL ? "foi eleito" : "está eleito agora"),
      md ? eleitos.length + " eleitos " + quando + ": " + voltam + " voltam da legislatura eleita em 2022 e " + novos +
        " chegam; " + saem.length + " dos " + md.eleitos_2022 + " eleitos em 2022 saem."
        : eleitos.length + " eleitos " + quando + ".",
      comp ? h("div", {}, h("p", { class: "ap-mun-sub", text: "Bancadas: eleitas em 2022 → " + (usa ? "previsão" : FINAL ? "eleitas em 2026" : "agora") }), comp) : null,
      h("div", { class: "ap-esp-grade" },
        h("div", {},
          h("p", { class: "ap-mun-sub", text: usa ? "Prováveis eleitos (mais votos previstos primeiro)" : (FINAL ? "Eleitos (mais votados primeiro)" : "Eleitos se parasse agora (mais votados primeiro)") }),
          h("ol", { class: "ap-esp-lista" }, eleitos.slice(0, n).map(linha)),
          maisBotao("esp:" + tipo, eleitos.length, n, "Todos os eleitos")),
        md ? h("div", {},
          h("p", { class: "ap-mun-sub", text: "Saem da " + casa + " (eleitos em 2022)" }),
          saem.length ? h("ul", { class: "ap-esp-lista" }, saem.map(function (x) {
            return h("li", { class: "ap-esp-item ap-sai", vars: { "--cor": "#cbd5e1" } },
              h("span", { class: "ap-uf-sigla", text: "↘" }),
              h("div", { class: "ap-favs-nome" }, h("b", { text: x.nm }), h("span", { class: "ap-partidos", text: x.p + " · " + x.motivo })));
          })) : h("p", { class: "ap-mudo", text: "Ninguém: todos os eleitos de 2022 voltam." })) : null));
  }

  // Folga da última cadeira das sobras, em votos. Acima de zero, a legenda que
  // segura a vaga AGORA ainda a tem. Abaixo, essa mesma legenda está de fora.
  // Espelha apuracao/estado.py margem_da_vaga — a série guarda o resultado.
  function sinalVaga(v, ancora) {
    if (!v || v.folga == null || !ancora) return null;
    if (v.dono === ancora) return v.folga;
    if (v.fora === ancora) return -v.folga;
    return null;
  }
  function nomeProprio(s) {
    return (s || "").toLowerCase().replace(/(^|[\s'-])(\S)/g, function (_, a, b) { return a + b.toUpperCase(); });
  }
  function candidatoDaCadeira(cargo, agrId, cadeira) {
    var lista = (cargo.candidatos || []).filter(function (c) {
      return c.a === agrId && (!c.dvt || c.dvt === "Válido");
    }).sort(function (a, b) { return b.v - a.v; });
    return lista[(cadeira || 1) - 1] || null;
  }
  function horaDe(ts) { return (ts || "").slice(11, 16).replace(":", "h"); }
  function comSinal(n) { return (n > 0 ? "+" : n < 0 ? "−" : "") + num(Math.abs(n)); }
  function passoBonito(faixa, n) {
    var bruto = (faixa || 1) / n, p = Math.pow(10, Math.floor(Math.log10(bruto))), f = bruto / p;
    return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
  }
  // Um ponto por % apurado, em ordem: o TSE às vezes devolve um arquivo antigo
  // por alguns segundos, e o % volta atrás — a linha não pode andar para trás.
  function pontosVaga(ancora) {
    var out = [], maxPst = -1;
    app.serie.forEach(function (p) {
      if (!p.pst || !(p.pst.estadual >= 70)) return;
      var a = sinalVaga(p.vaga, ancora), e = sinalVaga(p.vaga_esp, ancora);
      if (a == null && e == null) return;
      var x = p.pst.estadual;
      if (x < maxPst) return;
      if (x === maxPst) out.pop();
      maxPst = x;
      out.push({ x: x, a: a, e: e, ts: p.ts });
    });
    return out;
  }
  function cartaoVaga(cargo) {
    var v = cargo.vaga;
    if (!v || v.folga == null || !v.fora) return null;
    var porId = {};
    cargo.agremiacoes.forEach(function (a) { porId[a.id] = a; });
    function agr(id) { return porId[id] || { id: id, sigla: id, cor: "#64748b", votos: 0 }; }
    function nome(id) { return h("b", { class: "ap-vaga-nome", vars: { "--cor": agr(id).cor }, text: agr(id).sigla }); }
    // O cartão acompanha quem está imediatamente de fora: abaixo de zero, a
    // vaga escapou. O candidato é o próximo da lista dessa legenda.
    var ancora = v.fora, F = agr(ancora), D = agr(v.dono);
    var cand = candidatoDaCadeira(cargo, ancora, v.cadeira_fora);
    var pessoa = cand ? nomeProprio(cand.nm) : null;
    var fechou = !!(cand && cand.mat === "fora");
    var encerrada = !!(cargo.apuracao && (cargo.apuracao.totalizado || !cargo.restante));
    var mDono = D.votos / v.cadeira, mFora = F.votos / v.cadeira_fora;
    var esp = cargo.vaga_esp, espTxt = null;
    if (esp && esp.folga != null && !encerrada) {
      if (esp.fora === ancora) espTxt = "Na previsão do fim: fora por " + num(esp.folga) + " votos";
      else if (esp.dono === ancora) espTxt = "Na previsão do fim: entra, com " + num(esp.folga) + " votos de folga";
    }
    var status = fechou ? ["decidido", "nao"] : encerrada ? ["apuração encerrada", "fim"]
      : ["em aberto · ≈ " + curto(cargo.restante) + " votos a apurar", "quase"];
    function lado(a, cad, media, rotulo, dentro) {
      return h("div", { class: "ap-vaga-lado " + (dentro ? "dentro" : "fora"), vars: { "--cor": a.cor } },
        h("span", { class: "ap-vaga-lado-nome" }, h("b", { text: a.sigla }), " · " + cad + "ª cadeira"),
        h("span", { class: "ap-vaga-lado-media" }, h("b", { text: num(media) }), h("small", { text: " média" })),
        h("span", { class: "ap-vaga-lado-rot", text: rotulo }));
    }
    return h("section", { class: "ap-cartao ap-vaga", vars: { "--cor": F.cor } },
      h("div", { class: "ap-vaga-cab" },
        h("h2", { text: "Última vaga da Assembleia" }),
        h("span", { class: "ap-vaga-status " + status[1], text: status[0] })),
      h("div", { class: "ap-vaga-topo" },
        h("div", { class: "ap-vaga-placar" },
          h("p", { class: "ap-vaga-quem" }, pessoa ? [h("b", { text: pessoa }), " (", nome(ancora), ")"] : nome(ancora),
            fechou || encerrada ? " não se elegeu por" : " está fora por"),
          h("p", { class: "ap-vaga-numero" }, num(v.folga), h("small", { text: " votos" })),
          espTxt ? h("p", { class: "ap-vaga-esp", text: espTxt }) : null),
        h("div", { class: "ap-vaga-duelo" },
          lado(D, v.cadeira, mDono, "leva a vaga", true),
          lado(F, v.cadeira_fora, mFora, "fica de fora", false),
          h("p", { class: "ap-vaga-conta", text: "Nas sobras vence a maior média (votos ÷ cadeiras + 1). A diferença é de " +
            num(mDono - mFora) + " na média; como a do " + F.sigla + " divide por " + v.cadeira_fora + ", são " +
            num(v.folga) + " votos." }))),
      graficoVaga(pontosVaga(ancora), F));
  }
  function graficoVaga(pts, F) {
    if (pts.length < 2) return null;
    var vals = [];
    pts.forEach(function (p) { if (p.a != null) vals.push(p.a); if (p.e != null) vals.push(p.e); });
    var L = 600, A = 240, m = { e: 58, d: 70, t: 14, b: 30 };
    var lo = Math.min(0, Math.min.apply(null, vals)), hi = Math.max(0, Math.max.apply(null, vals));
    var passo = passoBonito(hi - lo, 4);
    lo = Math.floor(lo / passo) * passo; hi = Math.ceil(hi / passo) * passo;
    if (hi <= 0) hi = passo;
    if (lo >= 0) lo = -passo;
    var x0 = pts[0].x, x1 = pts[pts.length - 1].x;
    if (x1 - x0 < 0.5) { x0 -= 0.25; x1 += 0.25; }
    var x = function (t) { return m.e + (L - m.e - m.d) * (t - x0) / (x1 - x0); };
    var y = function (t) { return m.t + (A - m.t - m.b) * (hi - t) / (hi - lo); };
    var svg = s("svg", { viewBox: "0 0 " + L + " " + A, class: "ap-vaga-svg", role: "img",
      "aria-label": "Folga do " + F.sigla + " na última vaga, ao longo da apuração" });
    svg.appendChild(s("rect", { x: m.e, y: y(hi), width: L - m.e - m.d, height: y(0) - y(hi), class: "zona dentro" }));
    svg.appendChild(s("rect", { x: m.e, y: y(0), width: L - m.e - m.d, height: y(lo) - y(0), class: "zona fora" }));
    svg.appendChild(s("text", { x: m.e + 8, y: y(hi) + 15, class: "zona-rot dentro", text: "▲ " + F.sigla + " dentro" }));
    svg.appendChild(s("text", { x: m.e + 8, y: y(lo) - 8, class: "zona-rot fora", text: "▼ " + F.sigla + " fora" }));
    for (var t = lo; t <= hi + passo / 2; t += passo) {
      if (t !== 0) svg.appendChild(s("line", { x1: m.e, x2: L - m.d, y1: y(t), y2: y(t), class: "grade" }));
      svg.appendChild(s("text", { x: m.e - 8, y: y(t) + 4, "text-anchor": "end", class: "rotulo", text: comSinal(t) }));
    }
    svg.appendChild(s("line", { x1: m.e, x2: L - m.d, y1: y(0), y2: y(0), class: "zero" }));
    var px = passoBonito(x1 - x0, 4), casas = px < 1 ? 1 : 0;
    for (var u = Math.ceil(x0 / px) * px; u <= x1 + 1e-9; u += px) {
      svg.appendChild(s("text", { x: x(u), y: A - 10, "text-anchor": "middle", class: "rotulo",
        text: u.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }) + "%" }));
    }
    svg.appendChild(s("text", { x: L - m.d, y: A - 10, "text-anchor": "start", dx: 6, class: "rotulo", text: "apurado" }));
    function traco(k) {
      var d = "", ativo = false;
      pts.forEach(function (p) {
        if (p[k] == null) { ativo = false; return; }
        d += (ativo ? "L" : "M") + x(p.x).toFixed(1) + " " + y(p[k]).toFixed(1);
        ativo = true;
      });
      return d.indexOf("L") >= 0 ? d : "";
    }
    var dPrev = traco("e"), dAgora = traco("a");
    if (dPrev) svg.appendChild(s("path", { d: dPrev, class: "linha prev" }));
    if (dAgora) svg.appendChild(s("path", { d: dAgora, class: "linha" }));
    // Só a última virada ganha marca: com o vaivém do fim da noite, marcar
    // todas vira um pente de linhas.
    var virada = null;
    for (var i = 1; i < pts.length; i++) {
      var p0 = pts[i - 1], p1 = pts[i];
      if (p0.a == null || p1.a == null || (p0.a > 0) === (p1.a > 0)) continue;
      virada = { x: p0.x + (p1.x - p0.x) * p0.a / (p0.a - p1.a), ts: p1.ts, entrou: p1.a > 0 };
    }
    if (virada) {
      var vx = x(virada.x);
      svg.appendChild(s("line", { x1: vx, x2: vx, y1: m.t, y2: A - m.b, class: "virada" }));
      svg.appendChild(s("text", { x: vx, y: m.t + 10, dx: -5, "text-anchor": "end", class: "virada-rot",
        text: (virada.entrou ? "entrou às " : "saiu às ") + horaDe(virada.ts) }));
    }
    var ultA = null, ultE = null;
    pts.forEach(function (p) { if (p.a != null) ultA = p; if (p.e != null) ultE = p; });
    var yA = ultA ? y(ultA.a) : null, yE = ultE ? y(ultE.e) : null;
    if (yA != null && yE != null && Math.abs(yA - yE) < 16) {
      if (yA <= yE) yE = yA + 16; else yE = yA - 16;
    }
    if (ultE && dPrev) svg.appendChild(s("text", { x: x(ultE.x) + 8, y: yE + 4, class: "valor prev", text: comSinal(ultE.e) }));
    if (ultA) {
      svg.appendChild(s("circle", { cx: x(ultA.x), cy: y(ultA.a), r: 4.5, class: "ponto" }));
      svg.appendChild(s("text", { x: x(ultA.x) + 8, y: yA + 4, class: "valor", text: comSinal(ultA.a) }));
    }
    pts.forEach(function (p) {
      if (p.a == null) return;
      var tip = horaDe(p.ts) + " · " + pct(p.x, 2) + " apurado · " + F.sigla +
        (p.a > 0 ? " dentro por " + num(p.a) : " fora por " + num(-p.a)) + " votos" +
        (p.e != null ? " · previsão " + comSinal(p.e) : "");
      svg.appendChild(s("circle", { cx: x(p.x), cy: y(p.a), r: 7, class: "alvo", "data-tip": tip }));
    });
    var leg = h("div", { class: "ap-vaga-legenda" },
      h("span", {}, h("i", { class: "ap-vaga-swatch" }), "apuração (se parasse em cada momento)"),
      dPrev ? h("span", {}, h("i", { class: "ap-vaga-swatch prev" }), "previsão do fim") : null);
    return h("figure", { class: "ap-vaga-fig" }, svg, leg);
  }

  // Disputa da última vaga: a fila das médias das sobras, com a linha de corte,
  // e quanto cada partido do foco tem de folga (ou quanto falta) em VOTOS.
  // Tudo do modo escolhido: votos e cadeiras de agora, ou os da previsão.
  function cartaoDisputa(cargo, tipo) {
    var usa = usaPrev(cargo);
    var qe = usa ? cargo.esperado.qe : cargo.qe;
    if (!qe) return null;
    var votosDe = function (a) { return usa ? a.pe : a.votos; };
    var cands = {};
    (cargo.candidatos || []).forEach(function (c) {
      if (c.dvt && c.dvt !== "Válido") return;
      (cands[c.a] = cands[c.a] || []).push(usa && c.pe != null ? c.pe : c.v);
    });
    Object.keys(cands).forEach(function (k) { cands[k].sort(function (x, y) { return y - x; }); });
    var ganhas = [], fila = [];
    cargo.agremiacoes.forEach(function (a) {
      var V = votosDe(a) || 0, fs = (usa ? a.fases_esp : a.fases) || {};
      var k = fs.QP || 0, m = (fs["média"] || 0) + (fs["3ª fase"] || 0);
      for (var i = 1; i <= m; i++) ganhas.push({ a: a, media: V / (k + i), cadeira: k + i, V: V });
      var prox = (cands[a.id] || [])[k + m] || 0;
      var apto = V >= 0.8 * qe && prox >= 0.2 * qe;
      if (V > 0) fila.push({ a: a, media: V / (k + m + 1), cadeira: k + m + 1, V: V, apto: apto,
        motivo: V < 0.8 * qe ? "não tem 80% do QE" : prox < 0.2 * qe ? "próximo candidato sem 20% do QE" : "" });
    });
    if (!ganhas.length) return null;
    ganhas.sort(function (x, y) { return y.media - x.media; });
    fila.sort(function (x, y) { return y.media - x.media; });
    var ultima = ganhas[ganhas.length - 1];
    var aptos = fila.filter(function (f) { return f.apto; });
    var primeiro = aptos[0];
    // Margem em votos: quanto o dono de uma vaga pode perder antes de ser
    // passado, ou quanto quem está fora precisa ganhar para passar.
    function folga(g) { return primeiro ? Math.round((g.media - primeiro.media) * g.cadeira) : null; }
    function falta(f) { return Math.max(0, Math.round((ultima.media - f.media) * f.cadeira) + 1); }
    var frases = cargo.agremiacoes.filter(emFoco).map(function (a) {
      var minhas = ganhas.filter(function (g) { return g.a.id === a.id; });
      var fora = fila.filter(function (f) { return f.a.id === a.id; })[0];
      var partes = [];
      if (minhas.length) {
        var g = minhas[minhas.length - 1];
        partes.push(g.cadeira + "ª cadeira entra pelas sobras com folga de ≈ " + num(folga(g)) + " votos");
      }
      if (fora) partes.push(fora.apto ? (fora.cadeira + "ª cadeira: faltam ≈ " + num(falta(fora)) + " votos")
        : (fora.cadeira + "ª cadeira: fora da disputa (" + fora.motivo + ")"));
      return h("li", { class: "ap-disp-frase", vars: { "--cor": a.cor } }, h("b", { text: a.sigla + ": " }), partes.join(" · "));
    });
    function linha(x, dentro, i) {
      var nota = dentro ? (primeiro ? "folga ≈ " + num(folga(x)) + " votos" : "")
        : x.apto ? "faltam ≈ " + num(falta(x)) + " votos" : x.motivo;
      return h("tr", { class: (emFoco(x.a) ? "foco " : "") + (dentro ? "" : "fora") },
        h("td", { class: "num ap-mudo", text: dentro ? String(i + 1) : "" }),
        h("td", {}, h("span", { class: "ap-nome-agr", vars: { "--cor": x.a.cor }, text: x.a.sigla }),
          h("span", { class: "ap-partidos", text: x.cadeira + "ª cadeira" })),
        h("td", { class: "num" }, h("b", { text: num(x.media) })),
        h("td", { class: "num" }, dentro ? h("span", { class: "ap-selo passa", text: "entra" })
          : h("span", { class: "ap-selo " + (x.apto ? "nao" : "fora"), text: x.apto ? "fica fora" : "não disputa" })),
        h("td", { class: "num ap-partidos", text: nota }));
    }
    var proximos = fila.slice(0, 4);
    var corpo = h("tbody", {}, ganhas.map(function (g, i) { return linha(g, true, i); }),
      h("tr", { class: "ap-corte" }, h("td", { colspan: "5", text: "── linha de corte: " + cargo.vagas + "ª cadeira ──" })),
      proximos.map(function (f) { return linha(f, false); }));
    var dif = primeiro ? ultima.media - primeiro.media : null;
    return cartao("Disputa da última vaga" + (usa ? " · previsão" : " · " + T_PONTO),
      "Sobras = maior média (votos ÷ cadeiras + 1). Acima da linha, quem leva; abaixo, a fila. Folga = votos que o partido pode perder antes de ser passado; falta = votos que precisa ganhar.",
      primeiro ? h("p", { class: "ap-disp-manchete" }, "Última vaga: ", h("b", { text: ultima.a.sigla + " (" + ultima.cadeira + "ª)" }),
        " × 1º de fora: ", h("b", { text: primeiro.a.sigla + " (" + primeiro.cadeira + "ª)" }),
        " — diferença de " + num(dif) + " na média (≈ " + num(Math.round(dif * primeiro.cadeira)) + " votos para o " + primeiro.a.sigla + ")") : null,
      frases.length ? h("ul", { class: "ap-disp-frases" }, frases) : null,
      h("div", { class: "ap-tabela-rolagem" }, h("table", { class: "ap-tabela ap-disp" },
        h("thead", {}, h("tr", {}, h("th", { class: "num", text: "#" }), h("th", { text: "Partido · cadeira" }),
          h("th", { class: "num", text: "Média" }), h("th", { class: "num", text: "" }), h("th", { class: "num", text: "Margem" }))),
        corpo)));
  }

  function cartaoFavoritos(cargo, tipo) {
    var meus = (cargo.candidatos || []).filter(function (c) { return ehFav(tipo, c); });
    if (!meus.length) return null;
    var posicao = {};
    (cargo.candidatos || []).forEach(function (c, i) { posicao[c.n] = i + 1; });
    var siglaDe = {};
    cargo.agremiacoes.forEach(function (a) { siglaDe[a.id] = a; });
    return h("section", { class: "ap-cartao ap-favs" },
      h("div", { class: "ap-favs-topo" }, h("h2", { text: "★ Seus candidatos · " + nomeTipo(tipo) }),
        !FINAL && (tipo === "est-sc" || tipo === "fed-sc") ? botaoAvisos() : null),
      h("ul", { class: "ap-favs-lista" }, meus.map(function (c) {
        var agr = siglaDe[c.a] || {};
        return h("li", { vars: { "--cor": agr.cor || "#9ca3af" } }, estrela(tipo, c),
          h("div", { class: "ap-favs-nome" }, h("b", { text: c.nm }),
            h("span", { class: "ap-partidos", text: c.n + " · " + (agr.sigla || c.p) + " · " + posicao[c.n] + "º no geral" }),
            prev() && c.pc ? h("span", { class: "ap-partidos", text: "confiança " + c.pc }) : null),
          h("div", { class: "ap-favs-num" }, h("b", { text: aprox(vC(c), prev() && c.pe != null) }),
            prev() ? null : mini(pct(c.pct, 2))),
          seloFinal(c, cargo));
      })));
  }

  // ── por município (SC) ──────────────────────────────────────────────────
  function abrirMunicipio(cd) {
    app.munSel = cd;
    try { localStorage.setItem(MUN_CHAVE, cd); } catch (e) { /* ok */ }
    desenhar();
    var alvo = document.getElementById("ap-municipio");
    if (alvo) alvo.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function cartaoMunicipio(tipo) {
    var cargo = tipo === "est-sc" ? "est" : "fed";
    var corpo = h("div", { class: "ap-mun-corpo" });
    var entrada = h("input", { type: "search", list: "ap-mun-lista", placeholder: "Digite a cidade (ex.: Joinville)",
      "aria-label": "Município de SC", value: "" });
    var lista = h("datalist", { id: "ap-mun-lista" });
    function abrir(cd) {
      if (!cd) return;
      app.munSel = cd;
      try { localStorage.setItem(MUN_CHAVE, cd); } catch (e) { /* ok */ }
      var chave = cd + ":" + cargo;
      var guardado = app.mun[chave];
      if (guardado && Date.now() - guardado.t < 45000) { desenharMun(guardado.d); return; }
      corpo.textContent = "Abrindo…";
      fetch(BASE + "/municipio/" + cd + ".json?cargo=" + cargo, { cache: "no-cache" })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) { app.mun[chave] = { t: Date.now(), d: d }; desenharMun(d); })
        .catch(function () { corpo.textContent = "O TSE não respondeu agora; tente de novo em instantes."; });
    }
    function desenharMun(d) {
      var n = limiteDe("mun:" + tipo, celular() ? 6 : 10);
      var maxPct = Math.max.apply(null, d.agremiacoes.map(function (a) { return a.pct; }).concat([1]));
      var meus = d.candidatos.filter(function (c) { return ehFav(tipo, c); });
      var focoCands = d.candidatos.filter(candidatoEmFoco).slice(0, 5);
      corpo.textContent = "";
      anexar(corpo, [
        h("p", { class: "ap-legenda-cartao", text: d.municipio.nome + " · " + pct(d.apuracao.pst, 2) +
          " das seções · " + num(d.apuracao.validos) + " votos válidos" }),
        h("div", { class: "ap-mun-barras" }, d.agremiacoes.slice(0, n).map(function (a) {
          return h("div", { class: "ap-mun-linha" + (emFoco(a) ? " foco" : "") },
            h("span", { class: "ap-nome-agr", vars: { "--cor": a.cor }, text: a.sigla }),
            h("div", { class: "ap-barrinha" }, h("span", { vars: { "--p": (100 * a.pct / maxPct).toFixed(1) + "%", "--cor": a.cor } })),
            h("span", { class: "num", text: pct(a.pct, 1) }));
        })),
        maisBotao("mun:" + tipo, d.agremiacoes.length, n, "Todos os partidos"),
        meus.length ? h("p", { class: "ap-mun-sub", text: "★ Seus candidatos aqui" }) : null,
        meus.length ? h("ul", { class: "ap-mini-lista" }, meus.map(function (c) {
          return h("li", {}, estrela(tipo, c), h("span", { class: "ap-mini-nome", text: c.nm + " (" + c.p + ")" }),
            h("span", { class: "ap-v", text: num(c.v) }), h("span", { class: "ap-mudo", text: pct(c.pct, 1) }));
        })) : null,
        h("p", { class: "ap-mun-sub", text: "Mais votados na cidade" }),
        h("ul", { class: "ap-mini-lista" }, d.candidatos.slice(0, celular() ? 5 : 8).map(function (c) {
          return h("li", {}, estrela(tipo, c), h("span", { class: "ap-mini-nome", text: c.nm + " (" + c.p + ")" }),
            h("span", { class: "ap-v", text: num(c.v) }), h("span", { class: "ap-mudo", text: pct(c.pct, 1) }));
        })),
        focoCands.length ? h("p", { class: "ap-mun-sub", text: "Do seu foco" }) : null,
        focoCands.length ? h("ul", { class: "ap-mini-lista" }, focoCands.map(function (c) {
          return h("li", {}, estrela(tipo, c), h("span", { class: "ap-mini-nome", text: c.nm + " (" + c.p + ")" }),
            h("span", { class: "ap-v", text: num(c.v) }), h("span", { class: "ap-mudo", text: pct(c.pct, 1) }));
        })) : null]);
    }
    function preencher() {
      lista.textContent = "";
      (app.municipios || []).forEach(function (m) { lista.appendChild(h("option", { value: m.nm })); });
    }
    entrada.addEventListener("change", function () {
      var alvo = (app.municipios || []).filter(function (m) { return m.nm === entrada.value.trim().toUpperCase(); })[0];
      if (alvo) abrir(alvo.cd);
    });
    if (app.municipios) preencher();
    else fetch(BASE + "/municipios.json").then(function (r) { return r.ok ? r.json() : []; })
      .then(function (l) { app.municipios = l; preencher(); }).catch(function () { /* ok */ });
    var salvo = app.munSel;
    if (!salvo) { try { salvo = localStorage.getItem(MUN_CHAVE); } catch (e) { salvo = null; } }
    if (salvo) setTimeout(function () { abrir(salvo); }, 0);
    else corpo.appendChild(h("p", { class: "ap-mudo", text: "Escolha uma das 295 cidades para ver como ela está votando." }));
    var c = cartao("Por município", "Só votos: cadeira não se decide por cidade. Dá para escolher tocando no mapa.",
      h("div", { class: "ap-filtros" }, entrada), lista, corpo);
    c.id = "ap-municipio";
    return c;
  }

  // ── mapa de SC: % apurado por município + base dos selecionados ─────────
  // Preenchimento = quanto do ELEITORADO do município já foi totalizado (escala
  // de um só azul; cinza = nada ainda). Círculo âmbar = peso do município na
  // base do candidato/partido escolhido (área proporcional). A conta "% da base
  // apurada" pondera um pelo outro: é o que diz se o voto dele já chegou.
  var FAIXAS_MAPA = [
    { ate: 0, cor: "#e2e8f0", rotulo: "sem dados" },
    { ate: 25, cor: "#86b6ef", rotulo: "até 25%" },
    { ate: 50, cor: "#5598e7", rotulo: "25–50%" },
    { ate: 75, cor: "#2a78d6", rotulo: "50–75%" },
    { ate: 99.95, cor: "#1c5cab", rotulo: "75–99%" },
    { ate: 101, cor: "#0d366b", rotulo: "100%" }];
  function corApurado(p) {
    if (!p) return FAIXAS_MAPA[0].cor;
    for (var i = 1; i < FAIXAS_MAPA.length; i++) if (p <= FAIXAS_MAPA[i].ate) return FAIXAS_MAPA[i].cor;
    return FAIXAS_MAPA[FAIXAS_MAPA.length - 1].cor;
  }
  function carregarMapa() {
    if (app.mapa) return Promise.resolve(app.mapa);
    return fetch("/static/apuracao/sc-mapa.json?v=1").then(function (r) { return r.json(); })
      .then(function (m) { app.mapa = m; setTimeout(desenhar, 0); return m; });   // nomes das cidades chegam junto
  }
  function nomeMun(cd) { return app.mapa && app.mapa.municipios[cd] ? app.mapa.municipios[cd].nm : cd; }

  function opcoesBase(cargo, tipo) {
    var ops = [];
    (cargo.candidatos || []).forEach(function (c) {
      if (ehFav(tipo, c)) ops.push({ chave: "n=" + c.n, rotulo: "★ " + c.nm + " (" + c.p + ")", cand: c });
    });
    cargo.agremiacoes.filter(emFoco).forEach(function (a) {
      ops.push({ chave: "agr=" + encodeURIComponent(a.id), rotulo: "Partido: " + a.sigla, agr: a });
      (cargo.candidatos || []).filter(function (c) { return c.a === a.id && !ehFav(tipo, c); }).slice(0, 3)
        .forEach(function (c) { ops.push({ chave: "n=" + c.n, rotulo: c.nm + " (" + a.sigla + ")", cand: c }); });
    });
    return ops;
  }

  function linhaBase(item) {
    var x = item.cand || item.agr;
    var votos = item.cand ? x.v : x.votos;
    var ba = x.ba;
    var fonte = item.cand ? ({ "2022": "base = voto dele em 2022", "2022-outro-cargo": "base = voto dele em 2022 (outro cargo)",
      partido: "base = voto do partido em 2022", eleitorado: "base = eleitorado" })[x.bf] || "" : "base = voto do partido em 2022";
    return h("li", { class: "ap-base-item" },
      h("div", { class: "ap-base-nome" }, h("b", { text: item.cand ? x.nm : "Partido " + x.sigla }),
        h("span", { class: "ap-partidos", text: (prev() && x.pe != null ? "≈ " + curto(x.pe) + " votos na previsão" : num(votos) + (FINAL ? " votos" : " votos agora")) + " · " + fonte })),
      h("div", { class: "ap-base-barra", "data-tip": "Quanto dos votos esperados dele (pela base) já foi apurado" },
        h("span", { vars: { "--p": (100 * (ba || 0)).toFixed(1) + "%" } }),
        h("em", { text: ba == null ? "—" : pct(100 * ba, 0) + " da base apurada" })),
      h("div", { class: "ap-partidos ap-esp-linha" }, item.cand
        ? (x.pe != null && prev() ? "previsão ≈ " + curto(x.pe) + " votos · " + (x.pef ? "▲ entra" : "▽ fica fora") + (x.pc ? " · confiança " + x.pc : "") : "")
        : (x.pe != null ? "Esperado ≈ " + curto(x.pe) + " votos · " + x.cad_esp + (x.cad_esp === 1 ? " cadeira" : " cadeiras") : "")),
      x.bm && x.bm.length && (!item.cand || x.bf === "2022" || x.bf === "2022-outro-cargo") ? h("div", { class: "ap-partidos" }, "Principal base: " + x.bm.map(function (m) {
        return nomeMun(m[0]) + " " + num(m[1], 0) + "% (apurado " + num(m[2], 0) + "%)";
      }).join(" · ")) : null);
  }

  function cartaoMapa(cargo, tipo) {
    var t = tipo === "est-sc" ? "est" : "fed";
    var mun = app.estado.municipios_sc || {};
    var ops = opcoesBase(cargo, tipo);
    var sel = app.baseSel[tipo];
    if (sel === undefined || !ops.some(function (o) { return o.chave === sel; })) sel = ops.length ? ops[0].chave : "";
    var caixaMapa = h("div", { class: "ap-mapa" }, h("p", { class: "ap-mudo", text: "Carregando o mapa…" }));
    var escolha = h("select", { "aria-label": "Mostrar a base de" },
      h("option", { value: "", text: "Só o % apurado" }),
      ops.map(function (o) { return h("option", { value: o.chave, text: o.rotulo }); }));
    escolha.value = sel;
    escolha.addEventListener("change", function () { app.baseSel[tipo] = escolha.value; desenhar(); });

    function desenharMapa(m, fatias) {
      var svg = s("svg", { viewBox: "0 0 " + m.largura + " " + m.altura, class: "ap-mapa-svg", role: "img",
        "aria-label": "Mapa de Santa Catarina: % apurado por município" });
      Object.keys(m.municipios).forEach(function (cd) {
        var x = m.municipios[cd], a = mun[cd] || [0, 0, 0];
        var tip = x.nm + ": " + pct(a[1], 1) + " dos eleitores apurados (" + pct(a[0], 1) + " das seções)";
        if (fatias && fatias[cd]) tip += " · " + pct(100 * fatias[cd], 1) + " da base";
        var path = s("path", { d: x.d, fill: corApurado(a[1]), "data-tip": tip + " · toque para abrir" });
        path.addEventListener("click", function () { abrirMunicipio(cd); });
        svg.appendChild(path);
      });
      if (fatias) {
        var max = Math.max.apply(null, Object.keys(fatias).map(function (k) { return fatias[k]; }).concat([0.0001]));
        Object.keys(fatias).sort(function (p, q) { return fatias[q] - fatias[p]; }).slice(0, 80).forEach(function (cd) {
          var x = m.municipios[cd];
          if (!x) return;
          var r = 2 + 16 * Math.sqrt(fatias[cd] / max);
          var a = mun[cd] || [0, 0, 0];
          svg.appendChild(s("circle", { cx: x.c[0], cy: x.c[1], r: r.toFixed(1), class: "ap-base-bolha",
            "data-tip": x.nm + ": " + pct(100 * fatias[cd], 1) + " da base · " + pct(a[1], 0) + " apurado" }));
        });
      }
      caixaMapa.textContent = "";
      caixaMapa.appendChild(svg);
      caixaMapa.appendChild(h("div", { class: "ap-mapa-legenda" }, FAIXAS_MAPA.map(function (f) {
        return h("span", { vars: { "--cor": f.cor }, text: f.rotulo });
      }), fatias ? h("span", { class: "ap-legenda-bolha", text: "círculo = peso na base" }) : null));
    }
    carregarMapa().then(function (m) {
      if (!sel) { desenharMapa(m, null); return; }
      var cache = app.basesCache[t + ":" + sel];
      if (cache) { desenharMapa(m, cache); return; }
      desenharMapa(m, null);
      fetch(BASE + "/base/" + t + ".json?" + sel).then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { if (d) { app.basesCache[t + ":" + sel] = d.fatias; desenharMapa(m, d.fatias); } })
        .catch(function () { /* o mapa de % apurado já está desenhado */ });
    }).catch(function () { caixaMapa.textContent = "Não consegui carregar o mapa agora."; });

    // Os municípios: quantos fecharam e como estão as maiores cidades.
    var cods = Object.keys(mun).filter(function (cd) { return mun[cd][2] > 0 && cd !== "zz"; });
    var fechados = cods.filter(function (cd) { return mun[cd][0] >= 100; }).length;
    var andando = cods.filter(function (cd) { return mun[cd][0] > 0 && mun[cd][0] < 100; }).length;
    var nGrandes = limiteDe("grandes:" + tipo, celular() ? 5 : 10);
    var grandes = cods.sort(function (p, q) { return mun[q][2] - mun[p][2]; });
    var nBases = limiteDe("bases:" + tipo, celular() ? 3 : 6);
    var itens = ops.filter(function (o) { return o.cand || o.agr; });
    return cartao("Mapa da apuração · SC", fechados + " municípios fechados, " + andando + " em andamento, " +
        (cods.length - fechados - andando) + " sem dados ainda.",
      h("div", { class: "ap-mapa-grade" },
        h("div", { class: "ap-mapa-area" }, h("div", { class: "ap-filtros" }, escolha), caixaMapa),
        h("div", { class: "ap-mapa-lado" },
          itens.length ? h("p", { class: "ap-mun-sub", text: "Quanto da base já foi apurado" }) :
            h("p", { class: "ap-mudo", text: "Siga candidatos (☆) ou escolha partidos no foco para ver a base deles aqui." }),
          h("ul", { class: "ap-base-lista" }, itens.slice(0, nBases).map(linhaBase)),
          maisBotao("bases:" + tipo, itens.length, nBases, "Mais candidatos")),
        h("div", { class: "ap-mapa-cidades" },
          h("p", { class: "ap-mun-sub", text: "Maiores cidades (toque no mapa para abrir uma)" }),
          h("ul", { class: "ap-mini-lista" }, grandes.slice(0, nGrandes).map(function (cd) {
            return h("li", { class: "ap-cidade" }, h("span", { class: "ap-mini-nome", text: nomeMun(cd) }),
              h("span", { class: "ap-mudo", text: num(mun[cd][2]) + " eleitores" }),
              h("span", { class: "ap-v", text: pct(mun[cd][1], 0) }));
          })),
          maisBotao("grandes:" + tipo, grandes.length, nGrandes, "Mais cidades"))));
  }

  // ── arquivos que só uma aba usa (baixados quando a aba abre) ────────────
  function extra(nome, aoChegar) {
    var guardado = app.extras[nome];
    if (guardado && guardado.gerado === app.gerado) return guardado.dados;
    if (!guardado || !guardado.pedindo) {
      app.extras[nome] = { gerado: guardado ? guardado.gerado : null, dados: guardado ? guardado.dados : null, pedindo: true };
      fetch(BASE + "/" + nome + ".json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { app.extras[nome] = { gerado: app.gerado, dados: d, pedindo: false }; if (d) aoChegar(); })
        .catch(function () { app.extras[nome].pedindo = false; });
    }
    return guardado ? guardado.dados : null;
  }
  function seloFase(x) {
    if (x.e) return h("span", { class: "ap-selo oficial", text: "eleito (TSE)" });
    if (x.mat === "eleito-qp" || x.mat === "eleito-sobras") return h("span", { class: "ap-selo garantido", text: "garantido" });
    return h("span", { class: "ap-selo " + (x.proj === "QP" ? "qp" : x.proj === "média" ? "media" : "f3"),
      text: (FINAL ? "" : "agora: ") + (x.proj === "QP" ? "QP" : x.proj === "média" ? "média" : "3ª fase") });
  }

  // Quem cada agremiação elege AGORA para a Câmara, UF por UF.
  function cartaoEleitosBrasil(cam) {
    var d = extra("eleitos", desenhar);
    var focos = cam.agremiacoes.filter(emFoco).map(function (a) { return a.id; });
    var sel = app.eleitosSel || (focos.length ? focos[0] : cam.agremiacoes[0].id);
    var escolha = h("select", { "aria-label": "Partido ou federação" },
      cam.agremiacoes.filter(function (a) { return a.cadeiras || a.cad_esp; }).map(function (a) {
        return h("option", { value: a.id, text: a.sigla + " (" + princ(a, "cad") + ")" });
      }));
    escolha.value = sel;
    escolha.addEventListener("change", function () { app.eleitosSel = escolha.value; desenhar(); });
    var agr = cam.agremiacoes.filter(function (a) { return a.id === sel; })[0] || {};
    var corpo;
    if (!d) corpo = h("p", { class: "ap-mudo", text: "Carregando…" });
    else {
      var todos = (d.por_agremiacao || {})[sel] || [];
      var temEsp = todos.some(function (x) { return x.pe != null; });
      var usaE = prev() && temEsp;
      var lista = usaE ? todos.filter(function (x) { return x.pef || x.e; }) : todos.filter(function (x) { return x.proj || x.e; });
      lista.sort(function (a, b) { return a.uf < b.uf ? -1 : a.uf > b.uf ? 1 : (usaE ? (b.pe || 0) - (a.pe || 0) : b.v - a.v); });
      var saem = [];
      var n = limiteDe("eleitos:" + sel, celular() ? 12 : 40);
      var porUf = {};
      lista.forEach(function (x) { (porUf[x.uf] = porUf[x.uf] || []).push(x); });
      corpo = lista.length ? h("div", {},
        h("div", { class: "ap-eleitos-ufs" }, Object.keys(porUf).sort(function (a, b) { return porUf[b].length - porUf[a].length || (a < b ? -1 : 1); })
          .map(function (uf) { return h("span", { class: "ap-chip-uf", text: uf.toUpperCase() + " " + porUf[uf].length }); })),
        h("ol", { class: "ap-esp-lista" }, lista.slice(0, n).map(function (x) {
          return h("li", { class: "ap-esp-item", vars: { "--cor": agr.cor || "#9ca3af" } },
            h("span", { class: "ap-uf-sigla", text: x.uf.toUpperCase() }),
            h("div", { class: "ap-favs-nome" }, h("b", { text: x.nm }),
              h("span", { class: "ap-partidos", text: x.n + " · " + x.p + " · " + pct(x.pct, 2) + " na UF" })),
            h("div", { class: "ap-favs-num" }, h("b", { text: usaE && x.pe != null ? "≈ " + curto(x.pe) : num(x.v) }),
              mini(usaE ? "votos na previsão" : "votos")),
            x.e || x.mat ? seloFase(x) : null);
        })), maisBotao("eleitos:" + sel, lista.length, n, "Todos"),
        saem.length ? h("p", { class: "ap-mun-sub", text: "Dentro agora, devem sair no fim" }) : null,
        saem.length ? h("ul", { class: "ap-esp-lista" }, saem.map(function (x) {
          return h("li", { class: "ap-esp-item", vars: { "--cor": agr.cor || "#9ca3af" } },
            h("span", { class: "ap-uf-sigla", text: x.uf.toUpperCase() }),
            h("div", { class: "ap-favs-nome" }, h("b", { text: x.nm }), h("span", { class: "ap-partidos", text: x.n + " · " + x.p })),
            h("div", { class: "ap-favs-num" }, h("b", { text: "≈ " + curto(x.pe) }), h("span", { class: "ap-partidos", text: "no fim · agora " + num(x.v) })),
            h("span", { class: "ap-selo fim-fora", text: "no fim: ▽ fora" }));
        })) : null)
        : h("p", { class: "ap-mudo", text: "Ninguém eleito." });
    }
    return cartao(prev() ? "Quem cada partido deve eleger · Câmara" : (FINAL ? "Quem cada partido elegeu · Câmara" : "Quem cada partido elege agora · Câmara"),
      (agr.sigla ? agr.sigla + ": " + princ(agr, "cad") + " deputados federais " + (prev() ? "na previsão" : FINAL ? "eleitos" : "se parasse agora") +
        ". " : "") +
      (prev() ? "Fora de SC a base é a do partido em 2022: dentro dele, a ordem é a de agora." : ""),
      h("div", { class: "ap-filtros" }, escolha), corpo);
  }

  // Senado: as 54 cadeiras em disputa, por partido, se a ordem de agora se mantiver.
  function cartaoSenado() {
    var d = extra("majoritarias", desenhar);
    if (!d || !d.senado_disputa) return cartao("Senado · as 54 vagas em disputa", "Carregando…");
    var agrs = d.senado_disputa.map(function (x) {
      return { id: x.sigla, sigla: x.sigla, cor: x.cor, cadeiras: x.n, cad_esp: x.n, partidos: [{ sg: x.sigla }] };
    });
    var gov = d.governos_lideranca || {};
    var focoGov = Object.keys(gov).filter(function (sg) { return app.foco.indexOf(sg.toUpperCase()) >= 0; });
    return cartao(FINAL ? "Senado · as 54 vagas de 2026" : "Senado · as 54 vagas em disputa",
      (FINAL ? "Os dois mais votados de cada UF (as outras 27 cadeiras não estavam em jogo). "
        : "As duas mais votadas de cada UF, se a ordem de agora se mantiver (as outras 27 cadeiras não estão em jogo). ") +
      "Governos: " + Object.keys(gov).slice(0, 6).map(function (sg) { return sg + (FINAL ? " em " : " lidera em ") + gov[sg]; }).join(", ") +
      (focoGov.length ? "" : ".") ,
      hemiciclo(agrs, 54, "Senado: vagas em disputa", "cadeiras", "vagas em disputa"), legenda(agrs),
      h("ul", { class: "ap-mini-lista" }, d.senado_disputa.filter(function (x) { return app.foco.indexOf(x.sigla.toUpperCase()) >= 0; })
        .map(function (x) {
          return h("li", {}, h("span", { class: "ap-mini-nome", text: x.sigla + ": " + x.nomes.join(", ") }),
            h("span", { class: "ap-v", text: String(x.n) }), h("span", {}));
        })));
  }

  // Governador e Senado pelo Brasil, com o foco destacado.
  function cartaoGovernosBrasil() {
    var d = extra("majoritarias", desenhar);
    var corpo;
    var botao = h("button", { type: "button", class: "ap-ordem" + (app.majSoFoco ? " on" : ""),
      text: app.majSoFoco ? "Só UFs onde o foco disputa" : "Todas as UFs",
      onclick: function () { app.majSoFoco = !app.majSoFoco; desenhar(); } });
    if (!d) corpo = h("p", { class: "ap-mudo", text: "Carregando…" });
    else {
      var linhas = [];
      Object.keys(app.estado.nomes_uf).sort().forEach(function (uf) {
        var g = (d.governador || {})[uf], sn = (d.senador || {})[uf];
        var focoG = g ? g.candidatos.filter(candidatoEmFoco) : [];
        var focoS = sn ? sn.candidatos.filter(candidatoEmFoco) : [];
        if (app.majSoFoco && app.foco.length && !focoG.length && !focoS.length) return;
        linhas.push(blocoUfMaj(uf, g, sn, focoG, focoS));
      });
      corpo = linhas.length ? h("div", { class: "ap-gov-grade" }, linhas)
        : h("p", { class: "ap-mudo", text: "O foco não tem candidato a governador nem a senador em nenhuma UF." });
    }
    return cartao("Governadores e Senado pelo Brasil",
      "Governador: mais de 50% dos válidos elege no 1º turno; senão, os dois primeiros vão ao 2º. Senado: duas vagas, os dois mais votados.",
      h("div", { class: "ap-filtros" }, botao), corpo);
  }
  function blocoUfMaj(uf, g, sn, focoG, focoS) {
    function linhaCand(c, pos, marca) {
      return h("div", { class: "ap-gov-cand" + (candidatoEmFoco(c) ? " foco" : "") },
        h("span", { class: "ap-gov-pos", text: pos + "º" }),
        h("span", { class: "ap-mini-nome", text: c.nm + " (" + c.p + ")" }),
        h("b", { text: pct(c.pct, 1) }), marca || null);
    }
    var partes = [h("div", { class: "ap-gov-topo" }, h("b", { text: (app.estado.nomes_uf[uf] || uf.toUpperCase()) }),
      h("span", { class: "ap-mudo", text: g ? pct(g.apuracao.pst, 0) + " apurado" : "" }))];
    if (g && g.candidatos.length) {
      var c1 = g.candidatos[0], c2 = g.candidatos[1];
      var situacao = g.apuracao.totalizado ? (c1.e ? "eleito" : "2º turno")
        : c1.pct > 50 ? "1º turno, se mantiver" : "2º turno provável";
      partes.push(h("p", { class: "ap-mun-sub", text: "Governador · " + situacao }));
      partes.push(linhaCand(c1, 1, c1.pct > 50 ? h("span", { class: "ap-selo garantido", text: "> 50%" }) : null));
      if (c2) partes.push(linhaCand(c2, 2));
      focoG.forEach(function (c) { var i = g.candidatos.indexOf(c); if (i > 1) partes.push(linhaCand(c, i + 1)); });
    }
    if (sn && sn.candidatos.length) {
      partes.push(h("p", { class: "ap-mun-sub", text: "Senado · 2 vagas" }));
      sn.candidatos.slice(0, 2).forEach(function (c, i) { partes.push(linhaCand(c, i + 1)); });
      focoS.forEach(function (c) { var i = sn.candidatos.indexOf(c); if (i > 1) partes.push(linhaCand(c, i + 1)); });
    }
    return h("div", { class: "ap-gov-uf" }, partes);
  }

  // ── mapa do Brasil: % apurado por UF + cadeiras do foco ─────────────────
  function cartaoMapaBrasil(cam, focos) {
    var ufs = app.estado.ufs_br || {};
    var caixa = h("div", { class: "ap-mapa" }, h("p", { class: "ap-mudo", text: "Carregando o mapa…" }));
    var ids = focos.map(function (a) { return a.id; });
    function desenharBr(m) {
      var svg = s("svg", { viewBox: "0 0 " + m.largura + " " + m.altura, class: "ap-mapa-svg ap-mapa-br", role: "img",
        "aria-label": "Mapa do Brasil: % apurado por UF" });
      var bolhas = [];
      Object.keys(m.ufs).forEach(function (uf) {
        var x = m.ufs[uf], a = ufs[uf] || [0, 0, 0], u = (cam.ufs || {})[uf] || { cadeiras: {}, vagas: 0 };
        var soma = 0;
        ids.forEach(function (id) { soma += (((prev() && u.cad_esp) || u.cadeiras)[id]) || 0; });
        var tip = uf.toUpperCase() + ": " + pct(a[1], 1) + " dos eleitores apurados" +
          (ids.length ? " · foco: " + soma + " de " + u.vagas + " cadeiras " + (prev() ? "na previsão" : T_AGORA) : "") + " · toque para abrir";
        var path = s("path", { d: x.d, fill: corApurado(a[1]), "data-tip": tip });
        path.addEventListener("click", function () { location.hash = uf === "sc" ? "camara-sc" : "uf-" + uf; });
        svg.appendChild(path);
        if (soma) bolhas.push({ x: x.c, n: soma, tip: tip });
      });
      var max = Math.max.apply(null, bolhas.map(function (b) { return b.n; }).concat([1]));
      bolhas.forEach(function (b) {
        var r = 6 + 16 * Math.sqrt(b.n / max);
        svg.appendChild(s("circle", { cx: b.x[0], cy: b.x[1], r: r.toFixed(1), class: "ap-base-bolha", "data-tip": b.tip }));
        svg.appendChild(s("text", { x: b.x[0], y: b.x[1] + 4, "text-anchor": "middle", class: "ap-bolha-num", text: String(b.n) }));
      });
      caixa.textContent = "";
      caixa.appendChild(svg);
      caixa.appendChild(h("div", { class: "ap-mapa-legenda" }, FAIXAS_MAPA.map(function (f) {
        return h("span", { vars: { "--cor": f.cor }, text: f.rotulo });
      }), ids.length ? h("span", { class: "ap-legenda-bolha", text: "círculo = cadeiras do foco" }) : null));
    }
    if (app.mapaBr) setTimeout(function () { desenharBr(app.mapaBr); }, 0);
    else fetch("/static/apuracao/br-mapa.json?v=1").then(function (r) { return r.json(); })
      .then(function (m) { app.mapaBr = m; desenharBr(m); })
      .catch(function () { caixa.textContent = "Não consegui carregar o mapa agora."; });
    return cartao("Mapa da apuração · Brasil", "Cor = quanto do eleitorado da UF já foi apurado. " +
      (ids.length ? "Círculo = cadeiras " + (prev() ? "na previsão" : T_AGORA) + " de " + focos.map(function (a) { return a.sigla; }).join(" + ") + "." : "") +
      " Toque numa UF para abrir.", caixa);
  }

  // ── avisos dos seus ★ ───────────────────────────────────────────────────
  // Avisa quando um candidato seguido muda de situação que importa: ficou
  // garantido, ficou matematicamente fora, ou o TSE proclamou. Com a página
  // aberta (mesmo em outra aba) e permissão do navegador; sem permissão, só
  // a faixa de aviso da própria página.
  function avisosLigados() { try { return localStorage.getItem(AVISO_CHAVE) === "1"; } catch (e) { return false; } }
  function situacaoFav(c) { return c.e ? "eleito pelo TSE" : c.mat === "eleito-qp" || c.mat === "eleito-sobras" ? "eleito (garantido)" : c.mat === "fora" ? "fora (garantido)" : null; }
  function conferirAvisos() {
    var e = app.estado;
    if (!e) return;
    var atual = {};
    [["est-sc", e.sc.estadual], ["fed-sc", e.sc.federal]].forEach(function (par) {
      var tipo = par[0], cargo = par[1];
      if (!cargo) return;
      (cargo.candidatos || []).forEach(function (c) {
        if (ehFav(tipo, c)) atual[tipo + ":" + c.n] = { nome: c.nm, tipo: tipo, sit: situacaoFav(c) };
      });
    });
    var antes = app.situacoes;
    app.situacoes = atual;
    if (!antes) return;                       // primeira leitura: só memoriza
    Object.keys(atual).forEach(function (k) {
      var a = atual[k];
      if (a.sit && (!antes[k] || antes[k].sit !== a.sit)) {
        var txt = a.nome + " (" + nomeTipo(a.tipo) + "): " + a.sit;
        avisar("★ " + txt);
        if (avisosLigados() && window.Notification && Notification.permission === "granted") {
          try { new Notification("Apuração 2026", { body: txt, tag: k }); } catch (err) { /* ok */ }
        }
      }
    });
  }
  function botaoAvisos() {
    if (!window.Notification) return null;
    var ligado = avisosLigados() && Notification.permission === "granted";
    return h("button", { type: "button", class: "ap-avisos" + (ligado ? " on" : ""), "aria-pressed": ligado ? "true" : "false",
      text: ligado ? "🔔 avisos ligados" : "🔔 avisar quando ficarem garantidos",
      onclick: function () {
        if (ligado) { try { localStorage.setItem(AVISO_CHAVE, "0"); } catch (e) { /* ok */ } desenhar(); return; }
        Notification.requestPermission().then(function (p) {
          try { localStorage.setItem(AVISO_CHAVE, p === "granted" ? "1" : "0"); } catch (e) { /* ok */ }
          if (p !== "granted") avisar("O navegador não deixou mostrar notificações; os avisos aparecem só aqui na página.");
          desenhar();
        });
      } });
  }

  // ── vistas ──────────────────────────────────────────────────────────────
  function vistaProporcional(cargo, titulo, campoSerie, voltar, tipo) {
    if (!cargo) return [h("p", { class: "ap-carregando", text: "Sem dados deste cargo ainda." })];
    var ap = cargo.apuracao;
    var focos = cargo.agremiacoes.filter(emFoco);
    var blocos = [];
    if (voltar) blocos.push(h("button", { type: "button", class: "ap-voltar", text: "← todas as UFs",
      onclick: function () { location.hash = "brasil"; } }));
    blocos.push(h("div", { class: "ap-kpis" },
      kpi("Seções totalizadas", pct(ap.pst, 2), num(ap.st) + " de " + num(ap.ts), ap.pst),
      usaPrev(cargo)
        ? kpi("Votos válidos · previsão", "≈ " + curto(cargo.esperado.validos), "no fim da apuração")
        : kpi("Votos válidos", num(ap.validos), ap.legenda ? num(ap.legenda) + " na legenda" : titulo),
      usaPrev(cargo)
        ? kpi("Quociente eleitoral · previsão", "≈ " + num(cargo.esperado.qe), "10% = " + num(cargo.esperado.qe * 0.1) + " · 20% = " + num(cargo.esperado.qe * 0.2))
        : kpi("Quociente eleitoral", cargo.qe ? num(cargo.qe) : "—",
            cargo.qe ? "10% = " + num(cargo.piso_qp) + " · 20% = " + num(cargo.piso_media) : "válidos ÷ " + cargo.vagas + " vagas"),
      FINAL ? kpi("Eleitos", (cargo.candidatos || []).filter(function (c) { return c.e; }).length + " de " + cargo.vagas, "proclamados pelo TSE") :
      kpi("Já garantidas", (cargo.garantidos || 0) + " de " + cargo.vagas,
        ap.totalizado ? "totalização concluída" : cargo.qe ? "ainda podem entrar até " + num(cargo.restante) + " votos" : "projeção sobre a parcial")));
    if (tipo === "est-sc") {
      var blocoVaga = cartaoVaga(cargo);
      if (blocoVaga) blocos.push(blocoVaga);
    }
    var favs = cartaoFavoritos(cargo, tipo);
    if (favs) blocos.push(favs);
    if (focos.length) blocos.push(h("div", { class: "ap-focos" }, focos.map(function (a) { return cartaoFoco(cargo, a, tipo); })));
    var disputa = cartaoDisputa(cargo, tipo);
    if (disputa) blocos.push(disputa);
    var esperados = cartaoEsperados(cargo, tipo);
    var mapaSc = !FINAL && (tipo === "est-sc" || tipo === "fed-sc") && app.estado.municipios_sc ? cartaoMapa(cargo, tipo) : null;
    var serie = campoSerie ? serieFoco(campoSerie, titulo) : null;
    blocos.push(h("div", { class: "ap-grade" },
      h("div", { class: "ap-c5 ap-pilha" }, cargo.esperado
        ? cartao(titulo + (usaPrev(cargo) ? " · previsão" : " · " + T_PAROU), usaPrev(cargo)
            ? "Cidade a cidade: o voto real onde já se apurou e a base de cada candidato onde ainda falta. Contorno escuro = partido em foco."
            : (FINAL ? "Cada bolinha é uma cadeira eleita. Contorno escuro = partido em foco." : "Cada bolinha é uma cadeira, com os votos de agora. Contorno escuro = partido em foco."),
            hemiciclo(ordenarEsp(cargo.agremiacoes), cargo.vagas, titulo, usaPrev(cargo) ? "cad_esp" : "cadeiras", usaPrev(cargo) ? "na previsão" : T_AGORA),
            legendaDupla(cargo.agremiacoes))
        : cartao(titulo, "Cada bolinha é uma cadeira. Contorno escuro = partido em foco.",
            hemiciclo(cargo.agremiacoes, cargo.vagas, titulo + ": cadeiras projetadas"), legenda(cargo.agremiacoes)), serie),
      h("div", { class: "ap-c7" }, cartao("Partidos e federações",
        "Federação disputa como uma lista só. Clique para ver os candidatos.", tabelaAgremiacoes(cargo, tipo)))));
    if (esperados) blocos.push(esperados);
    if (mapaSc) blocos.push(mapaSc);
    if (tipo === "est-sc" || tipo === "fed-sc") blocos.push(cartaoMunicipio(tipo));
    blocos.push(cartao("Candidatos", (prev() ? "Previsão = cidade a cidade, pela base de cada um (▲ entra, ▽ fora)." : "Agora = se a apuração parasse neste instante.") +
      " \"Garantido\" = já não muda, seja qual for o voto que falta. ☆ = seguir.",
      listaCandidatos(cargo, tipo)));
    return blocos;
  }

  function vistaBrasil() {
    var cam = app.estado.camara;
    if (!cam) return [h("p", { class: "ap-carregando", text: "Sem dados da Câmara ainda." })];
    var focos = cam.agremiacoes.filter(emFoco);
    var blocos = [h("div", { class: "ap-kpis" },
      kpi("Seções totalizadas (Brasil)", pct(cam.pst, 2), "média das 27 UFs, pelo número de seções", cam.pst),
      kpi("Votos válidos · Câmara", num(cam.validos), "soma das 27 UFs"),
      kpi("Vagas", String(cam.vagas), "projeção = soma das 27 distribuições"),
      kpi("Passam na barreira" + (prev() ? " · previsão" : " · " + T_PONTO),
        String(cam.agremiacoes.filter(function (a) { return (prev() ? (a.barreira_esp || a.barreira) : a.barreira).passa; }).length),
        "de " + cam.agremiacoes.length + " partidos e federações"))];
    var serieCam = serieFoco("camara", "Câmara");
    blocos.push(h("div", { class: "ap-grade" },
      h("div", { class: "ap-c5 ap-pilha" }, cartao("Câmara dos Deputados" + (prev() ? " · previsão" : " · " + T_PAROU), prev()
        ? "513 cadeiras, UF por UF, se o voto que falta vier no padrão da base de cada partido (SC: de cada candidato, cidade a cidade)."
        : (FINAL ? "513 cadeiras, UF por UF." : "513 cadeiras, UF por UF, com os votos de agora."),
        hemiciclo(ordenarEsp(cam.agremiacoes), cam.vagas, "Câmara", prev() ? "cad_esp" : "cadeiras", prev() ? "na previsão" : T_AGORA),
        legendaDupla(cam.agremiacoes)), serieCam),
      h("div", { class: "ap-c7" }, cartao("Cláusula de barreira 2026" + (prev() ? " · previsão" : " · " + T_PONTO),
        "Passa quem fizer 2,5% dos válidos com 1,5% em 9 UFs (A) OU eleger 13 deputados em 9 UFs (B). Traço = 2,5%.",
        tabelaBarreira(cam)))));
    blocos.push(h("div", { class: "ap-grade" },
      app.estado.ufs_br ? h("div", { class: "ap-c7" }, cartaoMapaBrasil(cam, focos)) : null,
      h("div", { class: app.estado.ufs_br ? "ap-c5" : "ap-c12" }, cartao("Por estado", focos.length
        ? "Número = cadeiras " + (prev() ? "na previsão" : T_AGORA) + " de " + focos.map(function (a) { return a.sigla; }).join(" + ") + " na UF. Toque para abrir a UF."
        : "Toque numa UF para ver a disputa dela.", gradeUfs(cam, focos)))));
    blocos.push(cartaoEleitosBrasil(cam));
    return blocos;
  }

  function tabelaBarreira(cam) {
    var corpo = h("tbody");
    var P = prev();
    var pc = function (a) { return P && a.pct_esp != null ? a.pct_esp : a.pct; };
    var pc2 = function (a) { return P ? a.pct : a.pct_esp; };
    var ufs = function (a) { return P && a.ufs_pct_esp != null ? a.ufs_pct_esp : a.ufs_pct.length; };
    var ufs2 = function (a) { return P ? a.ufs_pct.length : a.ufs_pct_esp; };
    var cad = function (a) { return P && a.cad_esp != null ? a.cad_esp : a.cadeiras; };
    var cad2 = function (a) { return P ? a.cadeiras : a.cad_esp; };
    var ufc = function (a) { return P && a.ufs_cadeira_esp != null ? a.ufs_cadeira_esp : a.ufs_cadeira.length; };
    var ufc2 = function (a) { return P ? a.ufs_cadeira.length : a.ufs_cadeira_esp; };
    var escala = Math.max(5, cam.agremiacoes.reduce(function (m, a) { return Math.max(m, pc(a)); }, 0) * 1.05);
    var nBar = limiteDe("barreira", celular() ? 8 : 99);
    function par() { return null; }
    ordenarEsp(cam.agremiacoes).slice(0, nBar).forEach(function (a) {
      var b = P ? (a.barreira_esp || a.barreira) : a.barreira, b2 = P ? a.barreira : a.barreira_esp;
      corpo.appendChild(h("tr", { class: emFoco(a) ? "foco" : null },
        h("td", {}, h("span", { class: "ap-nome-agr", vars: { "--cor": a.cor }, text: a.sigla })),
        h("td", { class: "ap-celula-barra" },
          h("div", { class: "ap-barrinha", "data-tip": pct(pc(a), 2) + " dos válidos" },
            h("span", { vars: { "--p": (100 * pc(a) / escala).toFixed(1) + "%", "--cor": a.cor } }),
            h("i", { vars: { "--x": (100 * 2.5 / escala).toFixed(1) + "%" } })),
          h("span", { class: "ap-partidos" }, h("b", { text: pct(pc(a), 2) }))),
        h("td", { class: "num", "data-tip": "UFs com 1,5% ou mais" + (FINAL ? ": " : " (agora): ") + a.ufs_pct.join(", ").toUpperCase() },
          h("b", { text: ufs(a) + "/9" }), par(ufs2(a))),
        h("td", { class: "num" }, h("b", { text: cad(a) + "/13" }), par(cad2(a))),
        h("td", { class: "num ocultar-celular", "data-tip": "UFs com eleito" + (FINAL ? ": " : " (agora): ") + a.ufs_cadeira.join(", ").toUpperCase() },
          h("b", { text: ufc(a) + "/9" }), par(ufc2(a))),
        h("td", { class: "num" }, h("span", { class: "ap-selo " + (b.passa ? "passa" : "nao"),
          text: b.passa ? (b.a && b.b ? "A e B" : b.a ? "por A" : "por B") : "não passa" }),
          null)));
    });
    return h("div", { class: "ap-tabela-rolagem" }, h("table", { class: "ap-tabela" },
      h("thead", {}, h("tr", {}, h("th", { text: "Partido / federação" }), h("th", { text: "% nacional" }),
        h("th", { class: "num", text: "UFs 1,5%" }), h("th", { class: "num", text: "Deputados" }),
        h("th", { class: "num ocultar-celular", text: "UFs c/ eleito" }), h("th", { class: "num", text: "Barreira" }))),
      corpo), maisBotao("barreira", cam.agremiacoes.length, nBar, "Todos os partidos"));
  }

  function gradeUfs(cam, focos) {
    var ids = focos.map(function (a) { return a.id; });
    var cor = focos.length ? focos[0].cor : null;
    return h("div", { class: "ap-ufs" }, Object.keys(cam.ufs).map(function (uf) {
      var u = cam.ufs[uf], soma = 0;
      ids.forEach(function (id) { soma += (((prev() && u.cad_esp) || u.cadeiras)[id]) || 0; });
      return h("button", { type: "button", class: "ap-uf" + (soma ? " tem" : ""), vars: cor ? { "--cor": cor } : null,
        onclick: function () { location.hash = "uf-" + uf; } },
        h("b", { text: uf.toUpperCase() }),
        h("span", { class: "ap-uf-cad", text: focos.length ? String(soma) : String(u.vagas) }),
        h("span", { class: "ap-uf-nota", text: (focos.length ? "de " + u.vagas : "vagas") + " · " + pct(u.pst, 0) }));
    }));
  }

  function blocoMajoritario(titulo, d, nota, tipo) {
    if (!d) return null;
    var ap = d.apuracao;
    var lista = h("div", {});
    var chave = "maj:" + tipo;
    var n = limiteDe(chave, celular() ? 5 : 99);
    // Os seus ★ sobem para o topo; o resto segue a ordem de votos.
    var ordem = d.candidatos.slice().sort(function (a, b) {
      return (ehFav(tipo, b) ? 1 : 0) - (ehFav(tipo, a) ? 1 : 0) || b.v - a.v;
    });
    var visiveis = ordem.filter(function (c, i) { return i < n || candidatoEmFoco(c) || ehFav(tipo, c); });
    visiveis.forEach(function (c) {
      lista.appendChild(h("div", { class: "ap-maj-linha" + (candidatoEmFoco(c) || ehFav(tipo, c) ? " foco" : "") },
        h("span", { class: "ap-maj-nome" }, estrela(tipo, c), h("span", {}, h("b", { text: c.nm }),
          h("small", { text: c.n + " · " + c.col.replace(/\//g, "/\u200b") }))),
        h("span", { class: "num", text: pct(c.pct, 2) }),
        h("span", { class: "num ap-mudo" }, c.e ? h("span", { class: "ap-selo oficial", text: c.st || "eleito" }) : num(c.v)),
        h("div", { class: "ap-maj-barra" }, h("span", { vars: { "--p": Math.min(100, c.pct) + "%", "--cor": c.cor } }))));
    });
    if (d.turno === "2") titulo += " · 2º turno";
    return cartao(titulo, pct(ap.pst, 2) + " das seções totalizadas" + (nota ? " · " + nota : ""), lista,
      maisBotao(chave, d.candidatos.length, visiveis.length, "Todos os candidatos"));
  }

  function vistaMajoritarias() {
    var e = app.estado;
    return [prev() ? h("p", { class: "ap-aviso-modo", text: TURNO2
        ? "Governo e Senado não têm previsão: os números desta aba são os da contagem de agora. A previsão do presidente está na aba Presidente · 2º turno."
        : "Presidente, governo e Senado não têm previsão: os números desta aba são os da contagem de agora." }) : null,
      h("div", { class: "ap-grade" },
      h("div", { class: "ap-c6" }, blocoMajoritario("Presidente", e.presidente, "% dos válidos", "pres")),
      h("div", { class: "ap-c6" }, blocoMajoritario("Governador · SC", e.sc.governador, "% dos válidos", "gov-sc")),
      h("div", { class: "ap-c6" }, blocoMajoritario("Senado · SC", e.sc.senador, "duas vagas nesta eleição", "sen-sc")),
      h("div", { class: "ap-c6" }, cartaoSenado()),
      h("div", { class: "ap-c12" }, cartaoGovernosBrasil()))];
  }

  // ── Presidente, 2º turno (apuracao/presidente.py) ───────────────────────
  // O placar parcial engana (cada estado apura num ritmo); a previsão projeta o
  // voto que falta cidade a cidade. Ordem fixa dos dois lados (nº do candidato):
  // quando a liderança troca, ninguém troca de lugar na tela.
  function mi(x) {
    var a = Math.abs(x || 0);
    if (a >= 1e6) return (x / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: a >= 1e7 ? 1 : 2 }) + " mi";
    return curto(x);
  }
  function chanceTxt(x) {
    return x >= 99.9 ? "> 99,9%" : x <= 0.1 ? "< 0,1%" : pct(x, x >= 99 || x <= 1 ? 1 : 0);
  }
  function barraDuelo(pa, A, B, faixa) {
    return h("div", { class: "ap-duelo-barra", role: "img",
      "aria-label": A.nm + " " + pct(pa, 1) + " × " + B.nm + " " + pct(100 - pa, 1) },
      h("span", { class: "ap-duelo-a", vars: { "--p": pa + "%", "--cor": A.cor } }),
      h("span", { class: "ap-duelo-b", vars: { "--p": (100 - pa) + "%", "--cor": B.cor } }),
      faixa ? h("span", { class: "ap-duelo-faixa", vars: { "--de": faixa[0] + "%", "--ate": faixa[1] + "%" },
        "data-tip": "Faixa de 90% da previsão: " + pct(faixa[0], 1) + " a " + pct(faixa[1], 1) }) : null,
      h("span", { class: "ap-duelo-meio", "data-tip": "50% dos válidos" }));
  }
  function ladoPres(c, grande, linhas) {
    return h("div", { class: "ap-pres-lado", vars: { "--cor": c.cor } },
      h("div", { class: "ap-pres-nome", text: c.nm }),
      h("div", { class: "ap-pres-grande" }, h("b", { text: grande[0] }), grande[1] ? h("span", { text: grande[1] }) : null),
      linhas.map(function (t) { return t ? h("div", { class: "ap-pres-linha", text: t }) : null; }));
  }

  function statusPres(p) {
    var nome = function (n) { return p.candidatos.filter(function (c) { return c.n === n; })[0]; };
    if (p.eleito) return h("p", { class: "ap-pres-status fim", text: nome(p.eleito).nm + " eleito — o TSE já proclamou o resultado." });
    if (p.decidido) return h("p", { class: "ap-pres-status fim", text: nome(p.decidido).nm +
      " já venceu matematicamente: a diferença de " + num(Math.abs(p.margem_agora)) +
      " votos é maior que todo o voto que ainda pode entrar (" + num(p.pode_entrar) + " eleitores nas seções que faltam)." });
    return h("p", { class: "ap-pres-status", text: "Matematicamente em aberto: ainda faltam " + num(p.pode_entrar) +
      " eleitores nas seções não apuradas" + (prev() ? "." : ", e a diferença é de " + num(Math.abs(p.margem_agora)) + " votos.") });
  }

  function cartaoQuemVence(p, A, B) {
    var lado = function (c) {
      return ladoPres(c, [chanceTxt(c.chance), " de chance"], [
        pct(c.proj, 1) + " dos válidos no fim",
        "faixa de 90%: " + pct(c.proj_min, 1) + " a " + pct(c.proj_max, 1),
        "≈ " + mi(c.votos_proj) + " de votos"]);
    };
    var dif = p.margem_proj, lider = dif >= 0 ? A : B;
    return cartao("Quem vence", "Previsão com " + pct(p.apuracao.pst, 2) + " das seções apuradas · o voto que falta projetado cidade a cidade",
      h("div", { class: "ap-pres-duelo" }, lado(A), lado(B)),
      barraDuelo(A.proj, A, B, [A.proj_min, A.proj_max]),
      h("p", { class: "ap-pres-nota", text: "Diferença esperada no fim: " + lider.nm + " por ≈ " + mi(Math.abs(dif)) +
        " de votos. Na parte já apurada, o 2º turno anda " + (p.virada_nacional_pp >= 0 ? "a favor de " + A.nm : "a favor de " + B.nm) +
        " em " + pct(Math.abs(p.virada_nacional_pp), 1).replace("%", " pontos") +
        " em relação ao que o 1º turno dava nos mesmos lugares." }));
  }

  function cartaoPlacarPres(p, A, B) {
    var lado = function (c) { return ladoPres(c, [pct(c.pct, 2)], [num(c.v) + " votos"]); };
    var ap = p.apuracao, dif = p.margem_agora, lider = dif >= 0 ? A : B;
    return cartao("Placar do TSE", pct(ap.pst, 2) + " das seções totalizadas · % dos votos válidos",
      h("div", { class: "ap-pres-duelo" }, lado(A), lado(B)),
      barraDuelo(A.pct, A, B, null),
      h("p", { class: "ap-pres-nota", text: lider.nm + " à frente por " + num(Math.abs(dif)) + " votos. Brancos " +
        num(ap.brancos) + " · nulos " + num(ap.nulos) + " · abstenção " + num(ap.abstencao) + "." }));
  }

  // Linha da noite: % do candidato A (acima de 50, A na frente) com a faixa.
  function graficoDuelo(pts, A, B, opc) {
    if (pts.length < 2) return h("p", { class: "ap-legenda-cartao", text: "A linha aparece a partir da segunda atualização do TSE." });
    var L = 600, Alt = 230, m = { e: 46, d: 66, t: 12, b: 28 };
    var lo, hi;
    if (opc.fixo) { lo = opc.fixo[0]; hi = opc.fixo[1]; }
    else {
      var dev = 0.5;
      pts.forEach(function (p) {
        [p.y, p.lo, p.hi].forEach(function (v) { if (v != null) dev = Math.max(dev, Math.abs(v - 50)); });
      });
      var pas = passoBonito(dev, 3);
      var meia = Math.ceil(dev / pas) * pas;
      lo = 50 - meia; hi = 50 + meia;
    }
    var x0 = pts[0].x, x1 = pts[pts.length - 1].x;
    if (x1 - x0 < 0.5) { x0 = Math.max(0, x0 - 0.25); x1 += 0.25; }
    var x = function (t) { return m.e + (L - m.e - m.d) * (t - x0) / (x1 - x0); };
    var y = function (t) { return m.t + (Alt - m.t - m.b) * (hi - Math.max(lo, Math.min(hi, t))) / (hi - lo); };
    var svg = s("svg", { viewBox: "0 0 " + L + " " + Alt, class: "ap-vaga-svg ap-duelo-svg", role: "img", "aria-label": opc.rotulo });
    svg.appendChild(s("rect", { x: m.e, y: y(hi), width: L - m.e - m.d, height: y(50) - y(hi), class: "zona-cand", vars: { "--cor": A.cor } }));
    svg.appendChild(s("rect", { x: m.e, y: y(50), width: L - m.e - m.d, height: y(lo) - y(50), class: "zona-cand", vars: { "--cor": B.cor } }));
    svg.appendChild(s("text", { x: m.e + 8, y: y(hi) + 15, class: "zona-rot", vars: { "--cor": A.cor }, text: "▲ " + A.nm + " " + opc.zona }));
    svg.appendChild(s("text", { x: m.e + 8, y: y(lo) - 8, class: "zona-rot", vars: { "--cor": B.cor }, text: "▼ " + B.nm + " " + opc.zona }));
    var pas2 = passoBonito(hi - lo, 4);
    for (var t = Math.ceil(lo / pas2) * pas2; t <= hi + 1e-9; t += pas2) {
      if (Math.abs(t - 50) > 1e-9) svg.appendChild(s("line", { x1: m.e, x2: L - m.d, y1: y(t), y2: y(t), class: "grade" }));
      svg.appendChild(s("text", { x: m.e - 8, y: y(t) + 4, "text-anchor": "end", class: "rotulo",
        text: t.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%" }));
    }
    svg.appendChild(s("line", { x1: m.e, x2: L - m.d, y1: y(50), y2: y(50), class: "zero" }));
    var px = passoBonito(x1 - x0, 4), casas = px < 1 ? 1 : 0;
    for (var u = Math.ceil(x0 / px) * px; u <= x1 + 1e-9; u += px) {
      svg.appendChild(s("text", { x: x(u), y: Alt - 8, "text-anchor": "middle", class: "rotulo",
        text: u.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }) + "%" }));
    }
    svg.appendChild(s("text", { x: L - m.d, y: Alt - 8, "text-anchor": "start", dx: 6, class: "rotulo", text: "apurado" }));
    var comFaixa = pts.filter(function (p) { return p.lo != null; });
    if (comFaixa.length > 1) {
      var d = "";
      comFaixa.forEach(function (p, i) { d += (i ? "L" : "M") + x(p.x).toFixed(1) + " " + y(p.hi).toFixed(1); });
      comFaixa.slice().reverse().forEach(function (p) { d += "L" + x(p.x).toFixed(1) + " " + y(p.lo).toFixed(1); });
      svg.appendChild(s("path", { d: d + "Z", class: "faixa", vars: { "--cor": A.cor } }));
    }
    var dl = "";
    pts.forEach(function (p, i) { dl += (i ? "L" : "M") + x(p.x).toFixed(1) + " " + y(p.y).toFixed(1); });
    var ult = pts[pts.length - 1], corUlt = ult.y >= 50 ? A.cor : B.cor;
    svg.appendChild(s("path", { d: dl, class: "linha", vars: { "--cor": "var(--ap-texto)" } }));
    svg.appendChild(s("circle", { cx: x(ult.x), cy: y(ult.y), r: 4.5, class: "ponto", vars: { "--cor": corUlt } }));
    svg.appendChild(s("text", { x: x(ult.x) + 8, y: y(ult.y) + 4, class: "valor", vars: { "--cor": corUlt },
      text: opc.valor(ult.y) }));
    pts.forEach(function (p) {
      svg.appendChild(s("circle", { cx: x(p.x), cy: y(p.y), r: 7, class: "alvo", "data-tip": opc.dica(p) }));
    });
    return h("figure", { class: "ap-vaga-fig" }, svg);
  }

  function cartaoNoitePres(serie, A, B) {
    var pts;
    if (prev()) {
      pts = serie.map(function (p) { return { x: p.pst, y: p.proj, lo: p.min, hi: p.max, ts: p.ts, c: p.chance }; });
      var chance = serie.map(function (p) { return { x: p.pst, y: p.chance, ts: p.ts }; });
      return cartao("A previsão ao longo da noite", "Eixo de baixo: % das seções apuradas · cada ponto é uma atualização do TSE",
        h("div", { class: "ap-pres-graficos" }, h("div", {},
        h("h3", { class: "ap-pres-sub", text: A.nm + " no fim, em % dos válidos (faixa de 90%)" }),
        graficoDuelo(pts, A, B, { rotulo: "Previsão de " + A.nm + " ao longo da apuração", zona: "vence",
          valor: function (v) { return pct(v, 1); },
          dica: function (p) { return horaDe(p.ts) + " · " + pct(p.x, 2) + " apurado · previsão " + A.nm + " " + pct(p.y, 1) +
            " (" + pct(p.lo, 1) + "–" + pct(p.hi, 1) + ") · chance " + chanceTxt(p.c); } })),
        h("div", {},
        h("h3", { class: "ap-pres-sub", text: "Chance de vitória de " + A.nm }),
        graficoDuelo(chance, A, B, { rotulo: "Chance de vitória de " + A.nm, zona: "favorito", fixo: [0, 100],
          valor: function (v) { return chanceTxt(v); },
          dica: function (p) { return horaDe(p.ts) + " · " + pct(p.x, 2) + " apurado · chance de " + A.nm + " " + chanceTxt(p.y); } }))));
    }
    pts = serie.map(function (p) { return { x: p.pst, y: p.agora, ts: p.ts }; });
    return cartao("O placar ao longo da noite", "Linha: " + A.nm + " em % dos válidos já contados · eixo de baixo: % das seções apuradas",
      h("div", { class: "ap-pres-graficos um" }, h("div", {},
      graficoDuelo(pts, A, B, { rotulo: "Placar de " + A.nm + " ao longo da apuração", zona: "na frente",
        valor: function (v) { return pct(v, 2); },
        dica: function (p) { return horaDe(p.ts) + " · " + pct(p.x, 2) + " apurado · " + A.nm + " " + pct(p.y, 2); } }))));
  }

  function cartaoUfsPres(p, A, B) {
    var chave = "pres-ufs";
    var n = limiteDe(chave, celular() ? 8 : 28);
    var ufs = p.ufs.slice();
    var corpo = h("tbody", {});
    var cab, legenda;
    if (prev()) {
      ufs.sort(function (a, b) { return Math.abs(b.falta_a - b.falta_b) - Math.abs(a.falta_a - a.falta_b); });
      cab = ["Estado", "apurado", "votos que faltam", A.nm + " no que falta", "saldo do que falta"];
      ufs.slice(0, n).forEach(function (u) {
        var saldo = u.falta_a - u.falta_b, quem = saldo >= 0 ? A : B;
        corpo.appendChild(h("tr", {},
          h("td", { text: u.nome }),
          h("td", { class: "num", text: pct(u.pst, 1) }),
          h("td", { class: "num ap-pres-opc", text: "≈ " + mi(u.falta) }),
          h("td", { class: "num ap-pres-opc", text: u.pa_falta == null ? "—" : pct(u.pa_falta, 1) }),
          h("td", { class: "num" }, h("span", { class: "ap-pres-saldo", vars: { "--cor": quem.cor },
            text: (u.falta ? quem.nm.split(" ")[0] + " +" + mi(Math.abs(saldo)) : "—") }))));
      });
      var sa = p.ufs.reduce(function (t, u) { return t + u.falta_a - u.falta_b; }, 0);
      var quem = sa >= 0 ? A : B;
      legenda = "Faltam ≈ " + mi(p.falta_proj) + " de votos válidos. Pela projeção, eles rendem a " + quem.nm + " um saldo de ≈ " +
        mi(Math.abs(sa)) + ". Estados em ordem do saldo que ainda vão render.";
    } else {
      ufs.sort(function (a, b) { return (b.a + b.b) - (a.a + a.b); });
      cab = ["Estado", "apurado", A.nm, B.nm, "diferença"];
      ufs.slice(0, n).forEach(function (u) {
        var tot = u.a + u.b, dif = u.a - u.b, quem = dif >= 0 ? A : B;
        corpo.appendChild(h("tr", {},
          h("td", { text: u.nome }),
          h("td", { class: "num", text: pct(u.pst, 1) }),
          h("td", { class: "num ap-pres-opc", text: tot ? pct(100 * u.a / tot, 1) : "—" }),
          h("td", { class: "num ap-pres-opc", text: tot ? pct(100 * u.b / tot, 1) : "—" }),
          h("td", { class: "num" }, tot ? h("span", { class: "ap-pres-saldo", vars: { "--cor": quem.cor },
            text: quem.nm.split(" ")[0] + " +" + num(Math.abs(dif)) }) : "—")));
      });
      legenda = "O que cada estado já contou, em ordem de votos apurados.";
    }
    var tab = h("table", { class: "ap-tabela" },
      // No celular cabem 3 colunas: estado, apurado e o saldo (as do meio somem).
      h("thead", {}, h("tr", {}, cab.map(function (c, i) {
        return h("th", { class: i === 0 ? "" : i === 2 || i === 3 ? "num ap-pres-opc" : "num", text: c });
      }))), corpo);
    return cartao(prev() ? "Onde está o voto que falta" : "Estado por estado", legenda,
      h("div", { class: "ap-tabela-rolagem" }, tab),
      maisBotao(chave, p.ufs.length, Math.min(n, p.ufs.length), "Todos os estados"));
  }

  // Mapa do 2º turno: o % apurado de cada estado (cinza — o azul da escala do
  // 1º turno é a cor de um dos candidatos) e quem vence em cada um.
  var FAIXAS_PRES = [
    { ate: 0, cor: "#f1f5f9", rotulo: "sem dados" },
    { ate: 25, cor: "#cbd5e1", rotulo: "até 25%" },
    { ate: 50, cor: "#94a3b8", rotulo: "25–50%" },
    { ate: 75, cor: "#64748b", rotulo: "50–75%" },
    { ate: 99.95, cor: "#334155", rotulo: "75–99%" },
    { ate: 101, cor: "#0f172a", rotulo: "100%" }];
  function corApuradoPres(p) {
    if (!p) return FAIXAS_PRES[0].cor;
    for (var i = 1; i < FAIXAS_PRES.length; i++) if (p <= FAIXAS_PRES[i].ate) return FAIXAS_PRES[i].cor;
    return FAIXAS_PRES[FAIXAS_PRES.length - 1].cor;
  }

  function cartaoMapaPres(p, A, B) {
    var usa = prev();
    var caixa = h("div", { class: "ap-pres-mapas" }, h("p", { class: "ap-mudo", text: "Carregando o mapa…" }));
    var porUf = {};
    p.ufs.forEach(function (u) { porUf[u.uf] = u; });
    var fatia = function (u) { var t = u.a + u.b; return usa ? u.pa_fim : (t ? 100 * u.a / t : null); };
    function mapa(m, titulo, cor, dica, legenda) {
      var svg = s("svg", { viewBox: "0 0 " + m.largura + " " + m.altura, class: "ap-mapa-svg", role: "img", "aria-label": titulo });
      Object.keys(m.ufs).forEach(function (uf) {
        var u = porUf[uf], c = u ? cor(u) : { fill: FAIXAS_PRES[0].cor };
        var at = { d: m.ufs[uf].d, fill: c.fill, "data-tip": u ? dica(u) : uf.toUpperCase() + ": sem dados ainda" };
        if (c.op != null) at["fill-opacity"] = c.op.toFixed(2);
        svg.appendChild(s("path", at));
      });
      return h("figure", { class: "ap-pres-mapa" }, h("figcaption", { class: "ap-pres-sub", text: titulo }), svg,
        h("div", { class: "ap-mapa-legenda" }, legenda));
    }
    function desenharMapas(m) {
      caixa.textContent = "";
      caixa.appendChild(mapa(m, "Quanto cada estado já apurou",
        function (u) { return { fill: corApuradoPres(u.pst) }; },
        function (u) { return u.nome + ": " + pct(u.pst, 1) + " das seções apuradas"; },
        FAIXAS_PRES.map(function (f) { return h("span", { vars: { "--cor": f.cor }, text: f.rotulo }); })));
      caixa.appendChild(mapa(m, usa ? "Quem vence em cada estado (previsão)" : "Quem está na frente em cada estado",
        function (u) {
          var x = fatia(u);
          if (x == null) return { fill: FAIXAS_PRES[0].cor };
          return { fill: (x >= 50 ? A : B).cor, op: 0.25 + 0.75 * Math.min(1, Math.abs(x - 50) / 15) };
        },
        function (u) {
          var x = fatia(u);
          if (x == null) return u.nome + ": ainda sem votos";
          var l = x >= 50 ? A : B;
          return u.nome + ": " + l.nm + " " + pct(x >= 50 ? x : 100 - x, 1) + (usa ? " no fim (previsão)" : " agora") +
            " · " + pct(u.pst, 1) + " apurado";
        },
        [h("span", { vars: { "--cor": A.cor }, text: A.nm }), h("span", { vars: { "--cor": B.cor }, text: B.nm }),
          h("span", { class: "ap-mudo", text: "cor mais forte = vantagem maior" })]));
    }
    if (app.mapaBr) setTimeout(function () { desenharMapas(app.mapaBr); }, 0);
    else fetch("/static/apuracao/br-mapa.json?v=1").then(function (r) { return r.json(); })
      .then(function (m) { app.mapaBr = m; desenharMapas(m); })
      .catch(function () { caixa.textContent = "Não consegui carregar o mapa agora."; });
    return cartao("Mapa da apuração", "Passe o dedo ou o mouse num estado para ver os números. O exterior não aparece no mapa.", caixa);
  }

  function vistaPresidente() {
    var p = extra("presidente", desenhar);
    var serie = extra("serie_pres", desenhar) || [];
    if (!p) return [h("p", { class: "ap-carregando", text: "Carregando o 2º turno…" })];
    var A = p.candidatos.filter(function (c) { return c.n === p.a; })[0];
    var B = p.candidatos.filter(function (c) { return c.n === p.b; })[0];
    return [statusPres(p), h("div", { class: "ap-grade" },
      h("div", { class: "ap-c12" }, prev() ? cartaoQuemVence(p, A, B) : cartaoPlacarPres(p, A, B)),
      h("div", { class: "ap-c12" }, cartaoMapaPres(p, A, B)),
      h("div", { class: "ap-c12" }, cartaoNoitePres(serie, A, B)),
      h("div", { class: "ap-c12" }, cartaoUfsPres(p, A, B)))];
  }

  function carregarUf(uf) {
    var antes = app.ufs[uf];
    if (antes && antes.gerado === app.gerado) return Promise.resolve(antes.dados);
    return fetch(BASE + "/uf/" + uf + ".json", { cache: "no-cache" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) { app.ufs[uf] = { gerado: app.gerado, dados: d }; return d; });
  }

  // ── desenho geral ───────────────────────────────────────────────────────
  function lerHash() {
    var hsh = (location.hash || "").replace("#", "");
    if (hsh.indexOf("uf-") === 0) { app.vista = "uf"; app.uf = hsh.slice(3); return; }
    // Aba que o HTML declara e este arquivo não desenha é de um módulo extra
    // (window.AP_EXTRAS, ver static/politicos_eleicao.js): só vale se a aba existe.
    var declarada = Array.prototype.some.call(document.querySelectorAll(".ap-aba"), function (b) {
      return b.getAttribute("data-vista") === hsh;
    });
    // Aba padrão. No painel (/apuracao/noite) não existe aba "conta": a
    // explicação mora na outra página. Se o endereço não pede aba nenhuma,
    // cai na primeira que o HTML declarar.
    var primeira = document.querySelector(".ap-aba[data-vista]");
    app.vista = declarada ? hsh
      : (TURNO2 && document.querySelector('.ap-aba[data-vista="conta"]') ? "conta"
        : (primeira ? primeira.getAttribute("data-vista") : "alesc"));
    app.uf = null;
  }

  function cargoDaVista() {
    var e = app.estado;
    if (app.vista === "alesc") return e.sc.estadual;
    if (app.vista === "camara-sc") return e.sc.federal;
    return null;
  }

  function desenhar() {
    if (!app.estado) return;
    var e = app.estado;
    if (!app.foco) app.foco = lerFoco() || e.foco_padrao.slice();
    if (!app.favsLidos) { app.favs = lerFavs(); app.favsLidos = true; }
    desenharModo();
    desenharFoco();
    // Previsão/Ao vivo só fazem sentido durante a apuração; a eleição acabou.
    // O /apuracao/noite e o /politicos/eleicao nem têm a caixa: sem a guarda,
    // o desenho inteiro estourava aqui e a página ficava em "Carregando…".
    var caixaModo = $("ap-modo");
    if (caixaModo) caixaModo.hidden = true;
    // Partido em foco não vale para o 2º turno nem para a conta.
    $("ap-foco").hidden = app.vista === "presidente" || app.vista === "conta";
    Array.prototype.forEach.call(document.querySelectorAll(".ap-aba"), function (b) {
      var ativa = b.getAttribute("data-vista") === app.vista || (app.vista === "uf" && b.getAttribute("data-vista") === "brasil");
      b.setAttribute("aria-current", ativa ? "true" : "false");
    });
    var corpo = $("ap-corpo");
    var rolagem = window.scrollY;
    var foco = document.activeElement && document.activeElement.closest && document.activeElement.closest("#ap-candidatos") ? document.activeElement : null;
    var chaveFoco = document.activeElement && document.activeElement.getAttribute ? document.activeElement.getAttribute("data-foco") : null;
    var blocos;
    if (app.vista === "alesc") blocos = vistaProporcional(e.sc.estadual, "Assembleia Legislativa · SC", "estadual", false, "est-sc");
    else if (app.vista === "camara-sc") blocos = vistaProporcional(e.sc.federal, "Câmara dos Deputados · SC", "federal", false, "fed-sc");
    else if (app.vista === "brasil") blocos = vistaBrasil();
    else if (app.vista === "presidente") blocos = vistaPresidente();
    else if (app.vista === "majoritarias") blocos = vistaMajoritarias();
    else if (EXTRAS[app.vista]) blocos = EXTRAS[app.vista](AP);
    else if (app.vista !== "uf") blocos = [h("p", { class: "ap-carregando", text: "Carregando…" })];
    else if (app.vista === "uf") {
      if (app.uf === "sc") { location.hash = "camara-sc"; return; }
      var guardado = app.ufs[app.uf];
      if (!guardado || guardado.gerado !== app.gerado) {
        carregarUf(app.uf).then(desenhar).catch(function () { avisar("Não consegui abrir essa UF agora."); });
        if (!guardado) { corpo.textContent = ""; corpo.appendChild(h("p", { class: "ap-carregando", text: "Abrindo a UF…" })); return; }
      }
      blocos = vistaProporcional(guardado.dados, "Câmara dos Deputados · " + (e.nomes_uf[app.uf] || app.uf.toUpperCase()), null, true, "fed-" + app.uf);
    }
    corpo.textContent = "";
    anexar(corpo, blocos);
    window.scrollTo(0, rolagem);
    if (foco && foco.tagName === "INPUT") {
      var novo = corpo.querySelector("#ap-candidatos input");
      if (novo) { novo.focus(); novo.setSelectionRange(novo.value.length, novo.value.length); }
    }
    if (chaveFoco) {   // campo de um módulo extra que pediu para manter o foco
      var outro = corpo.querySelector('[data-foco="' + chaveFoco.replace(/[^\w-]/g, "") + '"]');
      if (outro) { outro.focus(); if (outro.setSelectionRange) outro.setSelectionRange(outro.value.length, outro.value.length); }
    }
    relogio();
  }

  function avisar(txt) {
    var a = $("ap-aviso");
    if (!txt) { a.hidden = true; return; }
    a.textContent = txt; a.hidden = false;
  }

  function relogio() {
    var e = app.estado;
    if (!e) return;
    var seg = app.ultimoOk ? Math.round((Date.now() - app.ultimoOk) / 1000) : null;
    var segTse = app.pulso ? Math.round((Date.now() - Date.parse(app.pulso.conferido_em)) / 1000) : null;
    $("ap-atualizado").textContent = seg === null ? "conectando…"
      : segTse !== null && segTse >= 0 ? "TSE conferido há " + segTse + " s"
      : seg < 5 ? "atualizado agora" : "conferido há " + seg + " s";
    var c = app.vista === "presidente" ? e.presidente
      : cargoDaVista() || (e.camara && app.vista !== "majoritarias" ? null : e.presidente);
    var dg = c && c.apuracao ? c.apuracao.dg : (e.fontes && (e.fontes.fed_sp || e.fontes.pres_br)) || "";
    $("ap-tse").textContent = dg ? "arquivo do TSE: " + dg : "";
    var pstAlesc = TURNO2 && e.presidente ? e.presidente.apuracao.pst : e.sc.estadual ? e.sc.estadual.apuracao.pst : 0;
    var rot = $("ap-estado-rotulo"), pulso = $("ap-pulso");
    if (FINAL) {
      $("ap-atualizado").textContent = "resultado oficial do TSE";
      $("ap-tse").textContent = dg ? "TSE · " + dg : "";
      rot.textContent = "resultado final"; rot.className = "ap-ao-vivo fim"; pulso.className = "ap-pulso parado";
      return;
    }
    if (pstAlesc >= 100) { rot.textContent = "apurado"; rot.className = "ap-ao-vivo fim"; pulso.className = "ap-pulso parado"; }
    else if (pstAlesc > 0) { rot.textContent = "ao vivo"; rot.className = "ap-ao-vivo"; pulso.className = "ap-pulso"; }
    else { rot.textContent = "aguardando"; rot.className = "ap-ao-vivo espera"; pulso.className = "ap-pulso parado"; }
  }

  function avisoDeEspera() {
    if (FINAL) return "";
    // Coletor parado é pior que TSE parado: a página pareceria viva com dado velho.
    if (app.pulso) {
      var min = Math.round((Date.now() - Date.parse(app.pulso.conferido_em)) / 60000);
      if (min >= 2) return "Atenção: faz " + min + " min que este painel não consegue conferir o TSE. Os números podem estar atrasados — confira também em resultados.tse.jus.br.";
    }
    var e = app.estado;
    var pst = TURNO2 && e.presidente ? e.presidente.apuracao.pst : e.sc.estadual ? e.sc.estadual.apuracao.pst : 0;
    if (pst > 0) return "";
    return "A apuração começa depois das 17h (horário de Brasília), quando fecham as urnas. Deixe esta página aberta: os números chegam sozinhos, sem recarregar.";
  }

  // ── rede ────────────────────────────────────────────────────────────────
  function agendar(ms) {
    clearTimeout(app.timer);
    app.timer = setTimeout(buscar, ms);
  }

  function buscar() {
    // Aba escondida não consulta — a não ser que os avisos dos ★ estejam ligados,
    // e aí consulta devagar (1 por minuto), que é o que faz o aviso chegar.
    if (!ARQUIVO && document.hidden && !avisosLigados()) { agendar(INTERVALO_MS); return; }
    fetch(BASE + "/estado.json", { cache: ARQUIVO ? "default" : "no-cache" }).then(function (r) {
      if (r.status === 429) throw { espera: 30000, msg: "Muitos acessos deste endereço — esperando meio minuto." };
      if (r.status === 401) { location.href = "/login"; return null; }
      if (!r.ok) throw { espera: Math.min(60000, app.espera * 2), msg: "O servidor não respondeu agora; tentando de novo." };
      return r.json();
    }).then(function (d) {
      if (!d) return;
      app.ultimoOk = Date.now(); app.falhas = 0; app.espera = INTERVALO_MS;
      if (d.gerado_em !== app.gerado) {
        app.estado = d; app.gerado = d.gerado_em;
        if (!app.favsLidos) { app.favs = lerFavs(); app.favsLidos = true; }
        desenhar();
        conferirAvisos();
      }
      avisar(avisoDeEspera());
      if (!ARQUIVO) agendar(document.hidden ? 60000 : INTERVALO_MS);
    }).catch(function (err) {
      if (err instanceof Error) console.error(err);   // defeito de desenho, não de rede
      app.falhas++;
      app.espera = (err && err.espera) || Math.min(60000, app.espera * 2);
      if (app.falhas > 1 || (err && err.espera)) avisar((err && err.msg) || "Sem conexão; tentando de novo.");
      agendar(app.espera);
    });
  }

  // Publicação nova: recarrega sozinha, a não ser que a pessoa esteja digitando
  // (aí só avisa). Foco, ★ e aba ficam no localStorage e no endereço.
  function versaoNova() {
    var digitando = document.activeElement && /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName);
    if (!digitando) { location.reload(); return; }
    var a = $("ap-aviso");
    a.textContent = "Esta página ganhou uma versão nova — toque aqui para atualizar.";
    a.hidden = false;
    a.onclick = function () { location.reload(); };
  }

  function buscarPulso() {
    // No arquivo congelado o pulso é consultado UMA vez, para saber se o
    // servidor ainda tem coletor vivo (e se o JS no ar é desta versão). Não
    // volta: uma aba parada na tela não pode ficar batendo no Pi para sempre.
    if (document.hidden) return;
    fetch(BASE + "/pulso.json", { cache: "default" }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || d.estatico) return;      // arquivo: não há nada a acompanhar
        var minha = ($("ap") || {}).dataset ? $("ap").dataset.versao : "";
        if (d.pagina && minha && d.pagina !== minha) { versaoNova(); return; }
        if (d.conferido_em) { app.pulso = d; if (app.estado) avisar(avisoDeEspera()); relogio(); }
        setTimeout(buscarPulso, 20000);
      })
      .catch(function () { /* o estado.json já avisa quando a rede cai */ });
  }

  function buscarSerie() {
    if (!document.hidden) {
      fetch(BASE + "/serie.json", { cache: "default" }).then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (d && d.length !== app.serie.length) { app.serie = d; desenhar(); }
        }).catch(function () { /* a série é acessória */ });
    }
    if (!ARQUIVO) setTimeout(buscarSerie, INTERVALO_SERIE_MS);
  }

  // ── eventos ─────────────────────────────────────────────────────────────
  $("ap-abas").addEventListener("click", function (ev) {
    var b = ev.target.closest(".ap-aba");
    if (!b) return;
    location.hash = b.getAttribute("data-vista");
  });
  window.addEventListener("hashchange", function () {
    lerHash(); app.filtroAgr = ""; app.busca = ""; app.limite = null; app.abertos = {}; app.soFavs = false;
    desenhar(); window.scrollTo(0, 0);
  });
  app.modo = lerModo();
  desenharModo();
  var caixaModo = $("ap-modo");
  if (caixaModo && !FINAL) caixaModo.addEventListener("click", function (ev) {
    var b = ev.target.closest(".ap-modo-btn");
    if (!b) return;
    app.modo = b.getAttribute("data-modo") === "aovivo" ? "aovivo" : "previsao";
    try { localStorage.setItem(MODO_CHAVE, app.modo); } catch (e) { /* só nesta visita */ }
    desenharModo();
    desenhar();
  });
  $("ap-foco-select").addEventListener("change", function (ev) {
    var v = ev.target.value;
    if (v && app.foco.indexOf(v) < 0) { app.foco.push(v); gravarFoco(); desenhar(); }
  });
  if (!ARQUIVO) document.addEventListener("visibilitychange", function () { if (!document.hidden) agendar(50); });

  var dica = null, dicaTimer = null;
  document.addEventListener("click", function (ev) {
    if (!window.matchMedia("(hover: none)").matches) return;
    var alvo = ev.target.closest && ev.target.closest("[data-tip]");
    if (!alvo) { if (dica) dica.hidden = true; return; }
    if (!dica) { dica = h("div", { class: "ap-tooltip", role: "tooltip" }); document.body.appendChild(dica); }
    dica.textContent = alvo.getAttribute("data-tip");
    dica.hidden = false;
    dica.style.left = Math.max(8, Math.min(window.innerWidth - 268, ev.clientX - 120)) + "px";
    dica.style.top = Math.max(8, ev.clientY - 60) + "px";
    clearTimeout(dicaTimer);
    dicaTimer = setTimeout(function () { dica.hidden = true; }, 3500);
  });
  document.addEventListener("mousemove", function (ev) {
    var alvo = ev.target.closest && ev.target.closest("[data-tip]");
    if (!alvo) { if (dica) dica.hidden = true; return; }
    if (!dica) { dica = h("div", { class: "ap-tooltip", role: "tooltip" }); document.body.appendChild(dica); }
    dica.textContent = alvo.getAttribute("data-tip");
    dica.hidden = false;
    dica.style.left = Math.min(window.innerWidth - 270, ev.clientX + 12) + "px";
    dica.style.top = (ev.clientY + 14) + "px";
  });

  // Para os módulos extras: as mesmas ferramentas de desenho e o estado.
  var AP = window.AP = { h: h, s: s, num: num, pct: pct, curto: curto, cartao: cartao, kpi: kpi,
    app: app, base: BASE, final: FINAL, arquivo: ARQUIVO, turno2: TURNO2,
    desenhar: desenhar, avisar: avisar, emFoco: emFoco,
    carregarMapa: function () { return app.mapa ? Promise.resolve(app.mapa) : carregarMapa(); } };

  lerHash();
  buscar();
  if (ARQUIVO) {
    // Arquivo congelado: a série do 1º turno é buscada UMA vez (é estática) e o
    // relógio não corre — não há nada contando. Nenhum laço de repetição.
    setTimeout(buscarSerie, 1500);
  } else {
    setTimeout(buscarSerie, 1500);
    setTimeout(buscarPulso, 800);
    setInterval(relogio, 1000);
  }
})();
