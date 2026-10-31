/* O chute do 2º turno (/apuracao) e os cinco cenários extremos (/apuracao/cenarios), 30/10/2026.
 *
 * Lê /apuracao/explicacao/chute.json (tools/migracoes/2026-10-30-chute-2t.py):
 * 9 grupos de eleitor do 1º turno (mais quem faltou nos dois, fixo), a dica da pesquisa de cada um e
 * cinco cenários extremos que fecham com o TSE. Cada grupo se divide em três destinos —
 * Lula, Flávio, nenhum (branco, nulo ou não foi votar) — numa barra com duas
 * divisas que se arrastam (setas do teclado também movem).
 *
 * O chute fica no localStorage do visitante ("estranha-chute") para a página
 * dos cenários comparar com ele; nada vai para servidor.
 */
(function () {
  "use strict";

  var RAIZ = document.getElementById("chute");
  var PAGINA = RAIZ.dataset.pagina, VERSAO = RAIZ.dataset.versao || "";
  var CORPO = document.getElementById("chute-corpo");
  var DEST = ["lula", "flavio", "nenhum"];
  var NOME = { lula: "Lula", flavio: "Flávio", nenhum: "Nenhum" };
  var CHAVE = "estranha-chute-2";   // -2: "não foi votar" virou "foi votar só no 2º turno" (30/10/2026)
  var ESCALA = {};   // fração do grupo que a largura inteira da barra representa (1 = tudo)
  var d = null, est = null, fora2 = null;
  // Os grupos que viram cartão: "faltou nos dois turnos" (fam "fixo") entra na conta, mas não é escolha.
  function visiveis() { return d.grupos.filter(function (g) { return g.fam !== "fixo"; }); }

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
  function pc(x, c) {
    c = c === undefined ? 0 : c;
    return x.toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c }) + "%";
  }
  function mi(x, c) {
    c = c === undefined ? 2 : c;
    return (x / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c }) + " mi";
  }
  function preso(x) { return Math.max(0, Math.min(1, x)); }
  function copiar(f) { var c = {}; for (var k in f) c[k] = { lula: f[k].lula, flavio: f[k].flavio, nenhum: f[k].nenhum }; return c; }
  function ler() { try { return JSON.parse(localStorage.getItem(CHAVE) || "null"); } catch (e) { return null; } }
  function gravar() { try { localStorage.setItem(CHAVE, JSON.stringify(est)); } catch (e) { /* sem storage */ } }
  var calmo = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function partida(g) {
    if (g.id === "lula1") return { lula: 1, flavio: 0, nenhum: 0 };
    if (g.id === "flavio1") return { lula: 0, flavio: 1, nenhum: 0 };
    if (g.fam === "fixo") return { lula: 0, flavio: 0, nenhum: 1 };
    return { lula: 1 / 3, flavio: 1 / 3, nenhum: 1 / 3 };
  }
  function conta(fatia) {
    var S = { lula: 0, flavio: 0, nenhum: 0 };
    d.grupos.forEach(function (g) { DEST.forEach(function (k) { S[k] += fatia[g.id][k] * g.v; }); });
    S.pct = 100 * S.lula / (S.lula + S.flavio);
    return S;
  }
  function curto(g) {
    var t = g.nome.replace("Votou no ", "").replace("Votou em ", "").replace("Votou ", "");
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  // ── a barra de três cores ──────────────────────────────────────────────
  // Lula | Flávio | nenhum. A divisa 0 fica no fim do Lula, a 1 no fim do Flávio.
  // `e` (escala) é a fração do grupo que a largura inteira representa.
  // Cada fatia leva o próprio percentual dentro. Quando as duas divisas caem
  // no mesmo ponto (ex.: 100% Lula), elas se afastam na tela para dar para
  // pegar cada uma; o valor não muda.
  var ALCA = 36;   // px: distância mínima entre as duas divisas na tela
  function barra(g, f, aoMudar, nomes) {
    nomes = nomes || NOME;
    var e = ESCALA[g.id] || 1;
    var rots = DEST.map(function () { return h("b", { class: "seg-rot" }); });
    var segs = DEST.map(function (k, i) { return h("span", { class: "seg " + k }, rots[i]); });
    var alcas = ["Divisa entre Lula e Flávio", "Divisa entre Flávio e nenhum"].map(function (rot, i) {
      return h("span", { class: "alca alca-" + i, role: "slider", tabindex: "0", "aria-label": rot + ": " + g.nome,
        "aria-valuemin": "0", "aria-valuemax": "100" });
    });
    var trilho = h("div", { class: "trilho3" }, segs, alcas);
    function rotulo(i, k, x, larg) {
      var p = 100 * x[k], c = p > 0 && p < 10 && e < 1 ? 1 : 0;
      var px = larg * (trilho.clientWidth || 300) / 100;   // em px, para o rótulo não ficar sob as divisas
      rots[i].textContent = px >= 110 ? nomes[k] + " " + pc(p, c) : px >= 48 ? pc(p, c) : "";
    }
    function pos() {
      var x = f(), a = Math.min(1, x.lula / e), b = Math.min(1, (x.lula + x.flavio) / e);
      var larg = [a, b - a, 1 - b].map(function (v) { return 100 * Math.max(0, v); });
      segs.forEach(function (s, i) { s.style.width = larg[i] + "%"; rotulo(i, DEST[i], x, larg[i]); });
      var W = trilho.clientWidth;
      if (W) {
        var pa = a * W, pb = b * W;
        if (pb - pa < ALCA) {
          var m = (pa + pb) / 2;
          pa = m - ALCA / 2; pb = m + ALCA / 2;
          if (pb > W) { pa -= pb - W; pb = W; }
          if (pa < 0) { pb -= pa; pa = 0; }
        }
        alcas[0].style.left = pa + "px"; alcas[1].style.left = pb + "px";
      } else {
        alcas[0].style.left = 100 * a + "%"; alcas[1].style.left = 100 * b + "%";
      }
      trilho.classList.toggle("junto", (b - a) * (W || 300) < ALCA);
      alcas[0].setAttribute("aria-valuenow", Math.round(100 * x.lula));
      alcas[0].setAttribute("aria-valuetext", "Lula " + pc(100 * x.lula) + ", Flávio " + pc(100 * x.flavio));
      alcas[1].setAttribute("aria-valuenow", Math.round(100 * (x.lula + x.flavio)));
      alcas[1].setAttribute("aria-valuetext", "Flávio " + pc(100 * x.flavio) + ", nenhum " + pc(100 * x.nenhum));
    }
    function definir(qual, frac) {
      var x = f(), a = x.lula, b = x.lula + x.flavio;
      frac = Math.round(1000 * preso(frac)) / 1000;
      if (qual === 0) { a = Math.min(frac, b); } else { b = Math.max(frac, a); }
      x.lula = a; x.flavio = b - a; x.nenhum = 1 - b;
      pos(); aoMudar(true);
    }
    // Leva a barra até `alvo` animando (dica escolhida, demonstração).
    var anim = 0;
    function animar(alvo, ms, fim) {
      var x = f(), de = { lula: x.lula, flavio: x.flavio, nenhum: x.nenhum }, t0 = null, id = ++anim;
      if (calmo) ms = 0;
      function passo(t) {
        if (id !== anim) return;
        if (t0 === null) t0 = t;
        var u = ms ? Math.min(1, (t - t0) / ms) : 1, k = 1 - Math.pow(1 - u, 3);
        DEST.forEach(function (c) { x[c] = de[c] + (alvo[c] - de[c]) * k; });
        pos();
        if (u < 1) requestAnimationFrame(passo);
        else if (fim) fim();
      }
      requestAnimationFrame(passo);
    }
    function parar() { anim++; trilho.classList.remove("demo"); }
    function fracDe(ev) {
      var r = trilho.getBoundingClientRect();
      return e * preso((ev.clientX - r.left) / r.width);
    }
    // Com as divisas juntas, quem decide qual mexer é o lado para onde se arrasta.
    var arrastando = -1, x0 = 0, juntas = false;
    alcas.forEach(function (al, i) {
      al.addEventListener("pointerdown", function (ev) {
        ev.preventDefault(); parar(); arrastando = i; x0 = ev.clientX;
        var x = f(); juntas = x.flavio * trilho.clientWidth / e < ALCA;
        al.setPointerCapture(ev.pointerId); al.classList.add("pega");
      });
      al.addEventListener("pointermove", function (ev) {
        if (arrastando !== i) return;
        if (juntas) {
          if (Math.abs(ev.clientX - x0) < 4) return;
          arrastando = ev.clientX < x0 ? 0 : 1;
          var x = f();
          if (arrastando === 1 && x.lula + x.flavio >= 1 - 1e-9) arrastando = 0;   // tudo encostado no fim: só dá para puxar a 1ª
          if (arrastando === 0 && x.lula <= 1e-9) arrastando = 1;
          juntas = false;
        }
        definir(arrastando, fracDe(ev));
      });
      function solta() { arrastando = -1; al.classList.remove("pega"); }
      al.addEventListener("pointerup", solta);
      al.addEventListener("pointercancel", solta);
      al.addEventListener("keydown", function (ev) {
        var x = f(), atual = i === 0 ? x.lula : x.lula + x.flavio, passo = e * (ev.shiftKey ? 0.05 : 0.01);
        if (ev.key === "ArrowRight" || ev.key === "ArrowUp") definir(i, atual + passo);
        else if (ev.key === "ArrowLeft" || ev.key === "ArrowDown") definir(i, atual - passo);
        else return;
        parar(); ev.preventDefault();
      });
    });
    // Tocar/clicar no trilho leva a divisa mais próxima até ali.
    trilho.addEventListener("click", function (ev) {
      if (ev.target.classList.contains("alca")) return;
      parar();
      var fr = fracDe(ev), x = f();
      definir(Math.abs(fr - x.lula) <= Math.abs(fr - (x.lula + x.flavio)) ? 0 : 1, fr);
    });
    if (window.ResizeObserver) new ResizeObserver(function () { pos(); }).observe(trilho);
    pos();
    return { el: trilho, pos: pos, animar: animar, parar: parar };
  }

  // ── a página do chute ──────────────────────────────────────────────────
  var cartoes = {}, rodapeConta = null, painel = null;

  // A pergunta de cada cartão: "quem votou em X no 1º turno, no 2º votou em…"
  var QUEM = { lula1: "no <b>Lula</b>", flavio1: "no <b>Flávio</b>", cury: "no <b>Cury</b>", renan: "no <b>Renan</b>",
    caiado: "no <b>Caiado</b>", zema: "no <b>Zema</b>", outros: "num <b>desses 6</b>", bn1: "<b>branco ou nulo</b>" };
  function pergunta(g) {
    if (g.id === "abst1") return "Quem <b>faltou no 1º turno</b> e foi votar no 2º, votou em…";
    return "Quem votou " + QUEM[g.id] + " no 1º turno, no 2º turno votou em…";
  }

  // As pesquisas viram "personagens" que dão palpite; cada uma tem cor e inicial.
  var INST = { "Quaest": ["quaest", "q"], "AtlasIntel": ["atlasintel", "a"], "Datafolha": ["datafolha", "d"], "Palpite clássico": [null, "p"] };

  function balao(g, o) {
    var b = o.bruto, t = b.lula + b.flavio + b.nenhum;
    var num = o.texto ? h("span", { class: "op-txt", text: o.texto }) : h("span", { class: "op-nums" },
      h("span", { class: "lula" }, h("i"), Math.round(b.lula) + "%"),
      h("span", { class: "flavio" }, h("i"), Math.round(b.flavio) + "%"),
      h("span", { class: "nenhum" }, h("i"), Math.round(b.nenhum) + "%"));
    return h("div", { class: "op-bal" },
      h("span", { class: "mini-barra" }, DEST.map(function (k) { return h("span", { class: k, style: "width:" + 100 * b[k] / t + "%" }); })),
      num);
  }

  function cartao(g, i) {
    var nums = h("div", { class: "barra-num" });
    var ok = h("span", { class: "grupo-ok", text: "✓ definido" });
    var art = h("article", { class: "grupo" + (est.mexido[g.id] ? " feito" : ""), id: "g-" + g.id });
    var ops = [];
    function pintar() {
      var x = est.fatia[g.id];
      nums.textContent = "";
      DEST.forEach(function (k) {
        nums.appendChild(h("span", { class: k }, h("i"), NOME[k] + " " + mi(x[k] * g.v)));
      });
      ops.forEach(function (el, j) {
        var usa = est.dica[g.id] === j;
        el.classList.toggle("usada", usa);
        el.setAttribute("aria-pressed", usa ? "true" : "false");
      });
    }
    function mudou(mao) {
      var novo = !est.mexido[g.id];
      if (mao) delete est.dica[g.id];
      est.mexido[g.id] = true; art.classList.add("feito");
      if (novo && !calmo) { art.classList.remove("pop"); void art.offsetWidth; art.classList.add("pop"); }
      pintar(); gravar(); pintarRodape();
    }
    var b = barra(g, function () { return est.fatia[g.id]; }, mudou);
    function aplicar(j) {
      var o = g.opinioes[j];
      est.dica[g.id] = j;
      b.animar({ lula: o.lula, flavio: o.flavio, nenhum: o.nenhum }, 650, function () { mudou(false); });
      pintar();
    }
    (g.opinioes || []).forEach(function (o, j) {
      var av = INST[o.inst] || [null, "p"];
      ops.push(h("div", { class: "op op-" + av[1], style: "--i:" + j, role: "button", tabindex: "0", "aria-pressed": "false",
          "aria-label": "Usar a sugestão: " + o.inst + (o.texto ? ", " + o.texto : ", Lula " + Math.round(o.bruto.lula) + "%, Flávio " + Math.round(o.bruto.flavio) + "%"),
          onclick: function (ev) { if (!ev.target.closest("a")) aplicar(j); },
          onkeydown: function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); aplicar(j); } } },
        h("div", { class: "op-cab" },
          av[0] ? h("img", { class: "op-logo op-logo-" + av[0], src: "/static/logos/" + av[0] + ".svg", alt: o.inst })
            : h("b", { class: "op-nome", text: "🧠 " + o.inst }),
          h("span", { class: "op-marca", "aria-hidden": "true" })),
        h("span", { class: "op-quando" },
          o.fonte ? h("a", { href: o.fonte.url, target: "_blank", rel: "noopener", text: o.fonte.nome.replace(o.inst + ", ", "") + " ↗" }) : "sem pesquisa",
          o.obs ? h("span", { class: "op-obs", text: o.obs }) : null),
        balao(g, o)));
    });
    var foto = g.foto ? h("img", { src: g.foto.src, alt: curto(g), width: "160", height: "160", loading: "lazy" })
      : g.lista ? h("span", { class: "mosaico" }, g.lista.map(function (m) {
          return h("img", { class: m.apoio.cor, src: m.foto, alt: m.nome, title: m.nome + " · " + m.apoio.txt, width: "96", height: "96", loading: "lazy" });
        }))
      : h("span", { class: "grupo-icone " + g.id, "aria-hidden": "true", text: g.id === "bn1" ? "✕" : g.icone || "" });
    var lista = g.lista ? h("ul", { class: "membros" }, g.lista.map(function (m) {
      return h("li", null, h("img", { src: m.foto, alt: "", width: "96", height: "96", loading: "lazy" }),
        h("span", { class: "membro-nome" }, m.nome, h("small", { text: " " + m.partido })),
        h("span", { class: "apoio " + m.apoio.cor, text: m.apoio.txt }));
    })) : null;
    anexar(art, [
      h("div", { class: "grupo-foto " + (g.apoio ? g.apoio.cor : "neutro") + (g.lista ? " tem-mosaico" : "") }, foto),
      h("div", { class: "grupo-cab" },
        h("div", { class: "grupo-topo" },
          h("span", { class: "grupo-n", text: (i + 1) + "/" + visiveis().length }),
          g.apoio && g.fam !== "finalistas" ? h("span", { class: "apoio " + g.apoio.cor, text: g.apoio.txt }) : null,
          ok),
        h("h3", { class: "pergunta " + (g.fam === "finalistas" ? g.apoio.cor : ""), html: pergunta(g) })),
      h("div", { class: "grupo-corpo" },
        lista,
        g.id === "abst1" && fora2 ? h("p", { class: "nota-fixa", html: "🏠 O 2º turno teve <b>" + mi(g.v) + "</b> de eleitores a mais que o 1º (TSE). É esse saldo que entra na conta. " +
          "Os outros " + mi(fora2.v, 1) + " faltaram nos dois turnos e ficam de fora." }) : null,
        b.el,
        nums,
        ops.length ? h("div", { class: "dicas" },
          h("p", { class: "dicas-tit" }, h("span", { class: "dicas-ico", "aria-hidden": "true", text: "💡" }),
            h("span", null, "Sugestões", h("small", { text: " · toque numa para aplicar" }))),
          h("div", { class: "ops" }, ops)) : null),
    ]);
    pintar();
    cartoes[g.id] = { el: art, pos: b.pos, pintar: pintar, barra: b };
    return art;
  }

  // Na primeira visita, a primeira barra se mexe sozinha uma vez, com a mãozinha.
  function demonstrar() {
    if (calmo || Object.keys(est.mexido).length) return;
    var g = d.grupos[0], c = cartoes[g.id], x = est.fatia[g.id];
    var orig = { lula: x.lula, flavio: x.flavio, nenhum: x.nenhum };
    var trilho = c.barra.el, mao = h("span", { class: "mao", "aria-hidden": "true", text: "👆" });
    var bal = h("span", { class: "tuto-bal", text: "Arraste as divisas para dividir os eleitores" });
    var alca = trilho.querySelector(".alca-0"), vivo = true;
    trilho.appendChild(mao); trilho.parentNode.insertBefore(bal, trilho);
    function segue() { if (!vivo) return; mao.style.left = alca.style.left; requestAnimationFrame(segue); }
    function fim() {
      vivo = false; c.barra.parar(); mao.remove();
      setTimeout(function () { bal.classList.add("some"); }, 2500);
    }
    trilho.addEventListener("pointerdown", function () { fim(); bal.remove(); }, { once: true });
    var io = new IntersectionObserver(function (en) {
      if (!en[0].isIntersecting) return;
      io.disconnect();
      trilho.classList.add("demo"); segue();
      setTimeout(function () {
        if (!vivo) return;
        c.barra.animar({ lula: 0.62, flavio: 0.22, nenhum: 0.16 }, 1100, function () {
          setTimeout(function () { if (vivo) c.barra.animar(orig, 900, fim); }, 700);
        });
      }, 600);
    });
    io.observe(trilho);
  }

  function pintarRodape() {
    var vis = visiveis(), feitos = vis.filter(function (g) { return est.mexido[g.id]; }).length;
    rodapeConta.textContent = feitos + "/" + vis.length + " grupos definidos";
    var fill = rodapeConta.parentNode.querySelector(".prog i");
    if (fill) fill.style.width = (100 * feitos / vis.length) + "%";
    if (painel && !painel.hidden) mostrarResultado(false);
  }

  // Bate quando os dois candidatos ficam a menos de 400 mil votos do TSE, em
  // votos absolutos (não em %). Como os grupos somam o eleitorado e cada barra
  // fecha em 100%, acertar os dois em votos acerta também os válidos.
  var TOLERA = 400000;

  // O painel é montado uma vez; mexer nas barras depois só atualiza os números
  // (antes ele era refeito a cada movimento da divisa, e travava).
  var R = null, agendado = false;
  function montarPainel() {
    function lado(k, nome) {
      var el = h("div", { class: "lado " + k },
        h("img", { src: "/static/fotos/" + k + ".jpg", alt: nome, width: "160", height: "160" }),
        h("span", { class: "lado-nome", text: nome }),
        h("b", { class: "lado-pct" }),
        h("span", { class: "lado-tag", text: "venceria" }));
      return el;
    }
    function linha(nome, cls) {
      var tr = h("tr", { class: cls }, h("th", { scope: "row", text: nome }), h("td"), h("td"),
        h("td", { class: "dif" }, h("span", { class: "dif-ico", "aria-hidden": "true" }), h("span", { class: "dif-num" })));
      return tr;
    }
    R = { lula: lado("lula", "Lula"), flavio: lado("flavio", "Flávio"), barra: h("span", { class: "lula" }),
      ver: h("div", { class: "veredito-res" }), verIco: h("span", { class: "vr-ico", "aria-hidden": "true" }),
      verTit: h("b"), verTxt: h("span"), tl: linha("Lula", "lula"), tf: linha("Flávio", "flavio"), nota: h("p", { class: "res-nota" }) };
    anexar(R.ver, [R.verIco, h("div", null, R.verTit, R.verTxt)]);
    painel.textContent = "";
    anexar(painel, [
      h("p", { class: "caso-rot", text: "Na sua simulação" }),
      h("div", { class: "duelo-res" }, R.lula, h("span", { class: "duelo-x", text: "×" }), R.flavio),
      h("div", { class: "placar-sim" },
        h("div", { class: "comp-barra" }, R.barra, h("span", { class: "flavio" })),
        h("span", { class: "marca-tse", style: "left:" + d.tse.pct_lula + "%" }, h("small", { text: "TSE " + pc(d.tse.pct_lula, 2) }))),
      R.ver,
      h("table", { class: "tab-votos" },
        h("thead", null, h("tr", null, h("th", { text: "" }), h("th", { text: "Seu chute" }), h("th", { text: "TSE" }), h("th", { text: "Diferença" }))),
        h("tbody", null, R.tl, R.tf)),
      R.nota,
      h("div", { class: "hero-acoes" },
        h("a", { class: "btn btn-pri", href: "/simulacao/cenarios", text: "Ver 5 jeitos de a conta fechar →" }),
        h("button", { class: "btn", type: "button", text: "Recomeçar", onclick: function () {
          est = { fatia: {}, mexido: {}, dica: {} };
          d.grupos.forEach(function (g) { est.fatia[g.id] = partida(g); });
          R = null; gravar(); montarChute(); window.scrollTo({ top: 0, behavior: calmo ? "auto" : "smooth" });
        } })),
    ]);
  }

  function atualizarPainel() {
    var S = conta(est.fatia), P = d.pesquisa.resultado;
    var dl = S.lula - d.tse.lula, df = S.flavio - d.tse.flavio;
    var bate = Math.abs(dl) < TOLERA && Math.abs(df) < TOLERA;
    var ganha = S.pct >= 50 ? "lula" : "flavio", certoVencedor = (d.tse.pct_lula >= 50) === (ganha === "lula");
    var faltam = visiveis().filter(function (g) { return !est.mexido[g.id]; });
    ["lula", "flavio"].forEach(function (k) {
      R[k].classList.toggle("ganha", k === ganha); R[k].classList.toggle("perde", k !== ganha);
      R[k].querySelector(".lado-pct").textContent = pc(k === "lula" ? S.pct : 100 - S.pct, 2);
    });
    R.barra.style.width = S.pct + "%";
    function erro1(nome, x) {
      return Math.abs(x) < TOLERA ? null : (x < 0 ? "faltaram " : "sobraram ") + mi(Math.abs(x)) + " para o " + nome;
    }
    R.ver.className = "veredito-res " + (bate ? "ok" : "nao");
    R.verIco.textContent = bate ? "✓" : "✕";
    R.verTit.textContent = bate ? "Bateu com o TSE" : "Não bateu com o TSE";
    R.verTxt.textContent = bate ? "Lula e Flávio a menos de 400 mil votos do oficial." :
      [erro1("Lula", dl), erro1("Flávio", df)].filter(Boolean).join(" e ")
        .replace(/^(faltaram|sobraram) (.*) e \1 /, "$1 $2 e ")
        .replace(/^./, function (c) { return c.toUpperCase(); }) + "." +
      (certoVencedor ? "" : " Na vida real, o Lula venceu.");
    [[R.tl, S.lula, d.tse.lula], [R.tf, S.flavio, d.tse.flavio]].forEach(function (x) {
      var tr = x[0], dif = x[1] - x[2], ok = Math.abs(dif) < TOLERA, td = tr.querySelectorAll("td");
      tr.classList.toggle("ok", ok); tr.classList.toggle("erro", !ok);
      td[0].textContent = mi(x[1]); td[1].textContent = mi(x[2]);
      td[2].querySelector(".dif-ico").textContent = ok ? "✓" : "✕";
      td[2].querySelector(".dif-num").textContent = Math.abs(dif) < 50000 ? "exato" : (dif > 0 ? "+" : "−") + mi(Math.abs(dif));
    });
    R.nota.innerHTML = "Só com a pesquisa: <b>Lula " + pc(P.pct_lula, 1) + "</b>, faltando " + mi(d.tse.lula - P.lula) + " para ele." +
      (faltam.length ? " " + faltam.length + (faltam.length > 1 ? " grupos sem mexer." : " grupo sem mexer.") : "");
  }

  function mostrarResultado(rolar) {
    if (!R || !painel.contains(R.ver)) montarPainel();
    painel.hidden = false;
    if (rolar) { try { navigator.sendBeacon("/v", new Blob([JSON.stringify({ e: "resultado", a: PAGINA })], { type: "application/json" })); } catch (x) { /* sem beacon */ }
      atualizarPainel(); painel.scrollIntoView({ behavior: calmo ? "auto" : "smooth", block: "start" }); return; }
    // Arrastando: no máximo uma atualização por quadro.
    if (agendado) return;
    agendado = true;
    requestAnimationFrame(function () { agendado = false; atualizarPainel(); });
  }

  function montarChute() {
    CORPO.textContent = "";
    cartoes = {};
    var fam = null;
    var TIT = { finalistas: "Quem votou num dos dois", terceira: "Quem votou na terceira via", fora: "Quem não escolheu ninguém no 1º turno" };
    visiveis().forEach(function (g, i) {
      if (g.fam !== fam) { fam = g.fam; CORPO.appendChild(h("h2", { class: "familia", text: TIT[fam] || fam })); }
      CORPO.appendChild(cartao(g, i));
    });
    painel = h("section", { class: "painel-resultado", id: "resultado", hidden: true });
    R = null;
    CORPO.appendChild(painel);
    rodapeConta = h("span", { class: "rodape-conta" });
    var fixo = h("div", { class: "barra-fixa" },
      h("div", { class: "barra-fixa-in" },
        h("div", { class: "barra-fixa-txt" }, rodapeConta, h("div", { class: "prog" }, h("i"))),
        h("button", { class: "btn btn-pri", type: "button", text: "Ver se bate com o TSE", onclick: function () { mostrarResultado(true); } })));
    CORPO.appendChild(fixo);
    pintarRodape();
    if (location.hash === "#resultado") mostrarResultado(true);
    else { var ja = false; try { ja = localStorage.getItem(TUT) === "1"; } catch (e) { ja = true; } if (ja) demonstrar(); else tutorial(false); }
  }

  // ── a página dos cenários ──────────────────────────────────────────────
  // Cada cenário mostra os mesmos grupos do chute, em linhas pequenas: a foto,
  // quem é, e a barra Lula | Flávio | nenhum (só de olhar, sem divisas). Uma
  // linha fina embaixo é a pesquisa, e um selo diz onde o cenário se afasta dela.
  var ROT = { lula1: "Lula", flavio1: "Flávio", cury: "Cury", renan: "Renan", caiado: "Caiado", zema: "Zema",
    outros: "Outros 6", bn1: "Branco/nulo", abst1: "Só no 2º turno" };

  function avatar(g) {
    if (g.foto) return h("img", { class: "av " + (g.apoio ? g.apoio.cor : ""), src: g.foto.src, alt: "", width: "160", height: "160", loading: "lazy" });
    return h("span", { class: "av av-ico " + g.id, "aria-hidden": "true", text: g.id === "bn1" ? "✕" : g.icone || "" });
  }

  function barraMini(x) {
    return h("span", { class: "bm" }, DEST.map(function (k) {
      var p = 100 * x[k];
      return h("span", { class: "bm-seg " + k, style: "width:" + p + "%", title: NOME[k] + " " + pc(p, 1) }, p >= 14 ? h("b", { text: pc(p) }) : null);
    }));
  }
  function linhaFina(x) {
    return h("span", { class: "bm-fina" }, DEST.map(function (k) { return h("span", { class: k, style: "width:" + 100 * x[k] + "%" }); }));
  }

  // O que o cenário pede de diferente da pesquisa: saldo (Lula − Flávio) a mais, em votos.
  function saldoVsPesquisa(c, g) {
    var a = c.fatia[g.id], p = d.pesquisa.fatia[g.id];
    return ((a.lula - a.flavio) - (p.lula - p.flavio)) * g.v;
  }

  // Linhas do cartão de cenário: a terceira via vira uma linha só (nos
  // cenários extremos, todos os grupos dela têm a mesma fatia).
  function linhasCenario(c) {
    var G = {}; d.grupos.forEach(function (g) { G[g.id] = g; });
    var terc = d.grupos.filter(function (g) { return g.fam === "terceira"; });
    function media(fat, gs) {
      var v = 0, x = { lula: 0, flavio: 0, nenhum: 0 };
      gs.forEach(function (g) { v += g.v; DEST.forEach(function (k) { x[k] += fat[g.id][k] * g.v; }); });
      DEST.forEach(function (k) { x[k] /= v; });
      return { v: v, x: x };
    }
    var T = media(c.fatia, terc), TP = media(d.pesquisa.fatia, terc);
    var tudo = c.tudo || [];
    var linhas = [
      { av: avatar(G.lula1), nome: "Lula", v: G.lula1.v, x: c.fatia.lula1, p: d.pesquisa.fatia.lula1, ids: ["lula1"] },
      { av: avatar(G.flavio1), nome: "Flávio", v: G.flavio1.v, x: c.fatia.flavio1, p: d.pesquisa.fatia.flavio1, ids: ["flavio1"] },
      { av: h("span", { class: "av-pilha" }, ["cury", "caiado", "renan"].map(function (id) { return avatar(G[id]); })),
        nome: "Terceira via", v: T.v, x: T.x, p: TP.x, ids: terc.map(function (g) { return g.id; }) },
      { av: avatar(G.bn1), nome: "Branco/nulo", v: G.bn1.v, x: c.fatia.bn1, p: d.pesquisa.fatia.bn1, ids: ["bn1"] },
      { av: avatar(G.abst1), nome: "Só no 2º turno", v: G.abst1.v, x: c.fatia.abst1, p: d.pesquisa.fatia.abst1, ids: ["abst1"] },
    ];
    return linhas.map(function (l) {
      var marcado = l.ids.every(function (id) { return tudo.indexOf(id) >= 0; });
      var chip = !marcado ? null : l.x.lula > 0.99 ? "tudo pro Lula" : pc(100 * l.x.lula) + " viraram Lula";
      return h("div", { class: "cl" + (marcado ? " tudo" : "") },
        l.av,
        h("div", { class: "cl-txt" },
          h("span", { class: "cl-nome", text: l.nome }),
          chip ? h("span", { class: "cl-tudo", text: chip }) : h("small", { class: "cl-sub", text: mi(l.v, 1) })),
        h("div", { class: "cl-barras" }, barraMini(l.x), linhaFina(l.p)));
    });
  }

  function montarCenarios() {
    var meu = ler(), temMeu = meu && meu.fatia && Object.keys(meu.mexido || {}).length;
    CORPO.textContent = "";
    var S = temMeu ? conta(meu.fatia) : null;
    CORPO.appendChild(h("div", { class: "aviso-meu" },
      h("span", { html: temMeu ? "Seu chute deu <b>Lula " + pc(S.pct, 1) + "</b>" + (Math.abs(S.lula - d.tse.lula) > 50000 ? ", com " +
          mi(Math.abs(S.lula - d.tse.lula)) + (S.lula < d.tse.lula ? " a menos" : " a mais") + " para ele que o TSE." : ", em cima do TSE.")
        : "Você ainda não chutou." }),
      h("a", { href: "/simulacao", text: temMeu ? "voltar à simulação" : "simular primeiro" })));
    CORPO.appendChild(h("p", { class: "cen-leg" }, "Cada barra: para onde foi o grupo no 2º turno. ",
      h("span", { class: "lula" }, h("i"), "Lula"), h("span", { class: "flavio" }, h("i"), "Flávio"),
      h("span", { class: "nenhum" }, h("i"), "nenhum"), h("span", { class: "fina" }, h("i"), "o que a pesquisa previa")));
    d.cenarios.forEach(function (c, i) {
      CORPO.appendChild(h("article", { class: "cenario" },
        h("div", { class: "cen-topo" },
          h("span", { class: "cen-n", text: String(i + 1) }),
          h("h3", { class: "cen-tit", text: c.titulo })),
        h("p", { class: "cen-resumo", text: c.resumo }),
        h("div", { class: "cen-linhas" }, linhasCenario(c)),
        h("div", { class: "cen-pe" },
          h("span", { class: "cen-fecha" }, h("i", { "aria-hidden": "true", text: "✓" }),
            "fecha com o TSE: ", h("b", { class: "c-lula", text: pc(d.tse.pct_lula, 2) }), " × ", h("b", { class: "c-flavio", text: pc(100 - d.tse.pct_lula, 2) })),
          h("button", { class: "btn btn-mini", type: "button", text: "Carregar no meu chute →", onclick: function () {
            var mex = {};
            d.grupos.forEach(function (g) { mex[g.id] = true; });
            est = { fatia: copiar(c.fatia), mexido: mex, dica: {} };
            gravar();
            location.href = "/simulacao#resultado";
          } }))));
    });
    CORPO.appendChild(h("section", { class: "convite" },
      h("p", { class: "caso-rot", text: "E qual é o certo?" }),
      h("p", { html: "Nenhum: são extremos, e todos fecham sem fraude. Comparando município a município, a troca direta do Flávio para o Lula fica perto de zero; " +
        "a terceira via, o branco/nulo e quem só votou no 2º turno foram mais para o Lula que a pesquisa previa. O real fica <b>entre os cenários 1, 2 e 3</b>." }),
      h("a", { class: "btn btn-fantasma", href: "/simulacao/detalhe", text: "Estimativa por município →" })));
  }

  // ── abertura com o vídeo de uso (1ª visita, ou "Ver como funciona") ─────
  var TUT = "estranha-tutorial";
  function tutorial(forcar) {
    var cx = document.getElementById("tutorial"), ok = document.getElementById("tutorial-ok");
    if (!cx) return;
    var visto = false; try { visto = localStorage.getItem(TUT) === "1"; } catch (e) { /* sem storage */ }
    if (visto && !forcar) return;
    cx.hidden = false; document.body.classList.add("sem-rolagem");
    var v = cx.querySelector("video"); if (v) { v.currentTime = 0; v.play().catch(function () {}); }
    var falta = forcar ? 0 : 6;
    function tic() {
      ok.disabled = falta > 0;
      ok.textContent = falta > 0 ? "Entendi, quero simular (" + falta + ")" : "Entendi, quero simular";
      ok.classList.toggle("aceso", falta <= 0);
      if (falta-- > 0) setTimeout(tic, 1000);
    }
    tic();
    ok.onclick = function () {
      cx.hidden = true; document.body.classList.remove("sem-rolagem");
      try { localStorage.setItem(TUT, "1"); } catch (e) { /* sem storage */ }
      demonstrar();
    };
  }
  var verTut = document.getElementById("ver-tutorial");
  if (verTut) verTut.addEventListener("click", function () { tutorial(true); });

  // ── início ─────────────────────────────────────────────────────────────
  fetch("/apuracao/explicacao/chute.json" + (VERSAO ? "?v=" + encodeURIComponent(VERSAO) : ""))
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (x) {
      d = x;
      fora2 = d.grupos.filter(function (g) { return g.fam === "fixo"; })[0] || null;
      var salvo = ler();
      est = { fatia: {}, mexido: (salvo && salvo.mexido) || {}, dica: (salvo && salvo.dica) || {} };
      d.grupos.forEach(function (g) {
        var s = salvo && salvo.fatia && salvo.fatia[g.id];
        est.fatia[g.id] = s && s.lula >= 0 ? s : partida(g);
      });
      if (PAGINA === "cenarios") montarCenarios(); else montarChute();
    })
    .catch(function () { CORPO.innerHTML = "<p class='carregando'>Não consegui abrir os dados agora. Recarregue a página.</p>"; });
})();
