/* Base da aba de EXPLICAÇÃO do /apuracao.
 *
 * Este arquivo existe para que quem abre /apuracao NÃO baixe o painel da noite
 * de 04/10 (o `apuracao.js` de 2.000 linhas, com hemiciclo, mapa de SC,
 * cadeiras, barreira e quociente). A explicação — as abas "A conta", "Sankey" e
 * "Simulador" — só precisa de oito primitivas: criar elemento, criar SVG,
 * formatar número, cartão, KPI, e o laço de desenho.
 *
 * O painel completo continua em `apuracao.js`, em /apuracao/noite.
 *
 * Contrato com os módulos extras (`AP_EXTRAS.conta|sankey|simulador`): eles
 * recebem este objeto `AP` e é só dele que podem depender. Se um dia um módulo
 * precisar de algo do painel, é sinal de que ele não é explicação.
 */
(function () {
  "use strict";

  var RAIZ = document.getElementById("ap");
  var BASE = (RAIZ && RAIZ.getAttribute("data-base")) || "/apuracao";
  // A versão publicada vai no `?v=` dos JSON: com `max-age` longo no servidor,
  // sem isso o navegador mostra dado de uma publicação antiga.
  var VERSAO = (RAIZ && RAIZ.getAttribute("data-versao")) || "";
  var EXTRAS = window.AP_EXTRAS = window.AP_EXTRAS || {};

  var nf = new Intl.NumberFormat("pt-BR");
  function num(x) { return nf.format(Math.round(x || 0)); }
  function pct(x, casas) {
    return (x || 0).toLocaleString("pt-BR", { minimumFractionDigits: casas === undefined ? 1 : casas,
      maximumFractionDigits: casas === undefined ? 1 : casas }) + "%";
  }
  function curto(x) {
    x = Math.round(x || 0);
    return x >= 10000 ? (x / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mil" : num(x);
  }

  // Só escreve TEXTO (textContent): dado do TSE nunca vira HTML.
  function anexar(el, x) {
    if (x === null || x === undefined || x === false || x === true) return;
    if (Array.isArray(x)) { x.forEach(function (i) { anexar(el, i); }); return; }
    if (x instanceof Node) { el.appendChild(x); return; }
    el.appendChild(document.createTextNode(String(x)));
  }
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
  function cartao(titulo, legendaTxt) {
    var c = h("section", { class: "ap-cartao" }, h("h2", { text: titulo }),
      legendaTxt ? h("p", { class: "ap-legenda-cartao", text: legendaTxt }) : null);
    for (var i = 2; i < arguments.length; i++) anexar(c, arguments[i]);
    return c;
  }
  function kpi(rotulo, valor, nota, barra) {
    return h("div", { class: "ap-kpi" },
      h("div", { class: "ap-kpi-rotulo", text: rotulo }),
      h("div", { class: "ap-kpi-valor", text: valor }),
      nota ? h("div", { class: "ap-kpi-nota", text: nota }) : null,
      barra !== undefined && barra !== null ? h("div", { class: "ap-barra" },
        h("span", { vars: { "--p": Math.min(100, barra) + "%" } })) : null);
  }
  function $(id) { return document.getElementById(id); }
  function avisar(txt) {
    var a = $("ap-aviso");
    if (!a) return;
    if (!txt) { a.hidden = true; return; }
    a.textContent = txt; a.hidden = false;
  }

  var app = { vista: null, estado: null };

  // A aba vem do endereço (#conta, #sankey, #simulador).
  function lerHash() {
    var hsh = (location.hash || "").replace("#", "");
    var existe = Array.prototype.some.call(document.querySelectorAll(".ap-aba"), function (b) {
      return b.getAttribute("data-vista") === hsh;
    });
    app.vista = existe ? hsh : "conta";
  }
  function desenhar() {
    lerHash();
    Array.prototype.forEach.call(document.querySelectorAll(".ap-aba"), function (b) {
      b.setAttribute("aria-current", b.getAttribute("data-vista") === app.vista ? "true" : "false");
    });
    var corpo = $("ap-corpo");
    if (!corpo) return;
    var bloco = EXTRAS[app.vista];
    corpo.textContent = "";
    if (!bloco) {
      corpo.appendChild(h("p", { class: "ap-carregando", text: "Abrindo…" }));
      return;
    }
    anexar(corpo, bloco(AP));
    var rot = $("ap-estado-rotulo");
    if (rot) { rot.textContent = "resultado final"; rot.className = "ap-ao-vivo fim"; }
  }

  var AP = window.AP = {
    h: h, s: s, num: num, pct: pct, curto: curto, cartao: cartao, kpi: kpi,
    app: app, base: BASE, versao: VERSAO, arquivo: true, final: true, turno2: true,
    desenhar: desenhar, avisar: avisar,
    emFoco: function () { return false; },
  };

  $("ap-abas") && $("ap-abas").addEventListener("click", function (ev) {
    var b = ev.target.closest(".ap-aba");
    if (!b) return;
    location.hash = b.getAttribute("data-vista");
  });
  window.addEventListener("hashchange", function () { desenhar(); window.scrollTo(0, 0); });

  // O relógio não corre: a eleição está encerrada e o arquivo não muda.
  var at = $("ap-atualizado");
  if (at) at.textContent = "resultado oficial do TSE";
  var pulso = $("ap-pulso");
  if (pulso) pulso.className = "ap-pulso parado";

  // Os módulos extras chegam DEPOIS deste arquivo (são scripts separados). Se
  // `desenhar()` rodasse aqui, `EXTRAS.conta` ainda não existiria e a página
  // ficaria em "Abrindo…" para sempre. Por isso o primeiro desenho é adiado:
  // quem manda é o `AP_EXTRAS` estar preenchido.
  function desenharQuandoPronto(tentativas) {
    tentativas = tentativas || 0;
    if (Object.keys(EXTRAS).length || tentativas > 40) { desenhar(); return; }
    setTimeout(function () { desenharQuandoPronto(tentativas + 1); }, 50);
  }
  desenharQuandoPronto();
})();
