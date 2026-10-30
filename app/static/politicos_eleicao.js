/* Eleição · resultado e microdados (/politicos/eleicao) — as abas de análise.
 *
 * Roda DEPOIS de static/apuracao.js, que desenha as abas do resultado e expõe
 * window.AP (as mesmas ferramentas de desenho: h, cartao, kpi…). Aqui se
 * registram três vistas em window.AP_EXTRAS: candidato, municipios e partidos.
 * Cada vista é uma função que devolve os blocos; o que ainda não chegou do
 * servidor aparece como "carregando" e, quando chega, a página se redesenha.
 *
 * Dado do servidor só entra como TEXTO (h() usa textContent).
 */
(function () {
  "use strict";
  var AP = window.AP;
  if (!AP) return;
  var h = AP.h, s = AP.s, num = AP.num, pct = AP.pct, curto = AP.curto, cartao = AP.cartao, kpi = AP.kpi;
  var BASE = AP.base;
  var CARGOS = [[7, "Deputado estadual"], [6, "Deputado federal"], [3, "Governador"], [5, "Senador"], [1, "Presidente (votos em SC)"]];
  var CARGO_CURTO = { 7: "Dep. estadual", 6: "Dep. federal", 3: "Governador", 5: "Senado", 1: "Presidente" };
  var ANOS = [2026, 2022];
  // Sequencial de um matiz só (claro → escuro), legível em daltonismo; zero = cinza.
  var ESCALA = ["#dbe9f6", "#a9cce6", "#6aa7d4", "#3a7fbf", "#1d5698", "#0b3168"];
  var SEM_VOTO = "#eef1f5";

  function lerSalvo(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } }
  function salvar(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* só nesta visita */ } }
  function celular() { return window.matchMedia("(max-width: 640px)").matches; }

  var st = {
    cache: {}, pendente: {}, mapa: null, abertos: {}, ordem: {},
    cand: lerSalvo("eleicao-cand"), candAno: 2026, candCargo: 7, busca: "", cidade: {},
    mun: lerSalvo("eleicao-mun") || { cd: 81051, cargo: 7, ano: 2026 },
    part: lerSalvo("eleicao-partido") || { a: null, cargo: 7, ano: 2026 },
  };
  if (st.cand) { st.candAno = st.cand.ano; st.candCargo = st.cand.cargo; }
  // Link direto: /politicos/eleicao?c=2026-7-30000#candidato
  (function () {
    var m = /[?&]c=(\d{4})-(\d)-(\d+)/.exec(location.search);
    if (m) { st.cand = { ano: +m[1], cargo: +m[2], n: +m[3] }; st.candAno = +m[1]; st.candCargo = +m[2]; }
  })();

  // ── rede: cada URL vai uma vez; quem pede antes de chegar recebe undefined ──
  function obter(url) {
    if (st.cache[url] !== undefined) return st.cache[url];
    if (!st.pendente[url]) {
      st.pendente[url] = true;
      fetch(BASE + url, { credentials: "same-origin" }).then(function (r) {
        if (r.status === 401) { location.href = "/login"; return null; }
        return r.ok ? r.json() : { erro: r.status };
      }).catch(function () { return { erro: "rede" }; }).then(function (d) {
        st.cache[url] = d || { erro: "vazio" };
        delete st.pendente[url];
        AP.desenhar();
      });
    }
    return undefined;
  }
  function carregando(txt) { return h("p", { class: "ap-carregando", text: txt || "Carregando…" }); }
  function falhou(d) {
    if (d && d.erro === 503) return h("p", { class: "ap-mudo", text: "Os microdados ainda estão sendo importados. Volte em alguns minutos." });
    return h("p", { class: "ap-mudo", text: "Não consegui carregar isto agora." });
  }
  function q(params) {
    return Object.keys(params).filter(function (k) { return params[k] !== null && params[k] !== undefined && params[k] !== ""; })
      .map(function (k) { return k + "=" + encodeURIComponent(params[k]); }).join("&");
  }

  // ── pedaços ─────────────────────────────────────────────────────────────
  function pilulas(opcoes, atual, aoEscolher, rotulo) {
    return h("div", { class: "el-pilulas", role: "radiogroup", "aria-label": rotulo },
      opcoes.map(function (o) {
        var on = o[0] === atual;
        return h("button", { type: "button", class: "el-pilula" + (on ? " on" : ""), role: "radio",
          "aria-checked": on ? "true" : "false", text: o[1],
          onclick: function () { if (!on) aoEscolher(o[0]); } });
      }));
  }
  function chip(a, cor) {
    return h("span", { class: "ap-nome-agr", vars: cor ? { "--cor": cor } : null, text: a });
  }
  function delta(x, casas, sufixo) {
    if (x === null || x === undefined || isNaN(x)) return h("span", { class: "ap-mudo", text: "—" });
    var t = (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toLocaleString("pt-BR", { minimumFractionDigits: casas || 0, maximumFractionDigits: casas || 0 }) + (sufixo || "");
    return h("span", { class: "el-delta " + (x > 0 ? "sobe" : x < 0 ? "desce" : ""), text: t });
  }
  function mais(chave, total, mostrados) {
    if (total <= mostrados) return null;
    return h("button", { type: "button", class: "ap-mais", text: "Mostrar mais (" + (total - mostrados) + ")",
      onclick: function () { st.abertos[chave] = mostrados + (celular() ? 10 : 25); AP.desenhar(); } });
  }
  function limite(chave, inicial) { return st.abertos[chave] || inicial; }
  function tabela(cabecalho, linhas, classe) {
    return h("div", { class: "ap-tabela-rolagem" }, h("table", { class: "ap-tabela " + (classe || "") },
      h("thead", {}, h("tr", {}, cabecalho.map(function (c) {
        return h("th", { class: c[1] || null, text: c[0] });
      }))), h("tbody", {}, linhas)));
  }
  function barra(p, cor) {
    return h("span", { class: "el-barra" }, h("span", { vars: { "--p": Math.max(0, Math.min(100, p)) + "%", "--cor": cor || "var(--el-azul)" } }));
  }

  // ── mapa de SC ──────────────────────────────────────────────────────────
  function quebras(valores) {
    var v = valores.filter(function (x) { return x > 0; }).sort(function (a, b) { return a - b; });
    if (!v.length) return [];
    var qs = [];
    for (var i = 1; i < ESCALA.length; i++) qs.push(v[Math.min(v.length - 1, Math.floor(v.length * i / ESCALA.length))]);
    return qs;
  }
  function corEscala(x, qs) {
    if (!x) return SEM_VOTO;
    var i = 0;
    while (i < qs.length && x > qs[i]) i++;
    return ESCALA[i];
  }
  function fmtPct(x) { return pct(x, x < 0.1 ? 3 : x < 1 ? 2 : 1); }
  /* valores: {cd: número} → coroplético; ou cores: {cd: cor} já decididas. */
  function mapaSC(opts) {
    var caixa = h("div", { class: "ap-mapa el-mapa" });
    if (!st.mapa) {
      caixa.appendChild(carregando("Carregando o mapa…"));
      AP.carregarMapa().then(function (m) { st.mapa = m; AP.desenhar(); });
      return caixa;
    }
    var m = st.mapa;
    var qs = opts.valores ? quebras(Object.keys(opts.valores).map(function (k) { return opts.valores[k]; })) : null;
    var svg = s("svg", { viewBox: "0 0 " + m.largura + " " + m.altura, class: "ap-mapa-svg", role: "img", "aria-label": opts.rotulo });
    Object.keys(m.municipios).forEach(function (cd) {
      var x = m.municipios[cd];
      var fill = opts.cores ? (opts.cores[cd] || SEM_VOTO) : corEscala(opts.valores[cd], qs);
      var p = s("path", { d: x.d, fill: fill, "data-tip": opts.dica(cd, x.nm), class: String(opts.destaque) === cd ? "el-destaque" : "" });
      if (opts.clique) p.addEventListener("click", function () { opts.clique(cd, x.nm); });
      svg.appendChild(p);
    });
    if (opts.destaque && m.municipios[String(opts.destaque)]) {
      var dx = m.municipios[String(opts.destaque)];
      svg.appendChild(s("path", { d: dx.d, class: "el-contorno" }));
    }
    caixa.appendChild(svg);
    if (qs && qs.length) {
      var faixas = [[SEM_VOTO, "sem voto"]];
      var ant = 0;
      qs.concat([Infinity]).forEach(function (lim, i) {
        faixas.push([ESCALA[i], lim === Infinity ? "acima de " + fmtPct(ant) : "até " + fmtPct(lim)]);
        ant = lim;
      });
      caixa.appendChild(h("div", { class: "ap-mapa-legenda" }, faixas.map(function (f) {
        return h("span", { vars: { "--cor": f[0] }, text: f[1] });
      })));
    } else if (opts.legenda) caixa.appendChild(opts.legenda);
    return caixa;
  }

  // ── aba Candidato ───────────────────────────────────────────────────────
  function escolherCand(ano, cargo, n) {
    st.cand = { ano: ano, cargo: cargo, n: n };
    st.candAno = ano; st.candCargo = cargo;
    salvar("eleicao-cand", st.cand);
    st.abertos = {};
    if (history.replaceState) history.replaceState(null, "", "?c=" + ano + "-" + cargo + "-" + n + "#candidato");
    AP.desenhar();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function seletorCandidato() {
    var lista = obter("/candidatos.json?" + q({ ano: st.candAno, cargo: st.candCargo }));
    var resultados = h("ul", { class: "el-resultados" });
    var busca = h("input", { type: "search", placeholder: "Nome, número ou partido", value: st.busca, "aria-label": "Buscar candidato",
      "data-foco": "busca-candidato" });
    function normal(t) { return String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase(); }
    function preencher() {
      resultados.textContent = "";
      if (!lista || lista.erro) return;
      var termo = normal(st.busca.trim());
      var achados = lista.filter(function (c) {
        return !termo || normal(c.nm).indexOf(termo) >= 0 || String(c.n).indexOf(termo) === 0 || normal(c.p) === termo || normal(c.ac) === termo;
      }).slice(0, termo ? 30 : 12);
      achados.forEach(function (c) {
        var atual = st.cand && st.cand.n === c.n && st.cand.ano === st.candAno && st.cand.cargo === st.candCargo;
        resultados.appendChild(h("li", {}, h("button", { type: "button", class: "el-resultado" + (atual ? " on" : ""),
          onclick: function () { escolherCand(st.candAno, st.candCargo, c.n); } },
          h("span", { class: "el-res-nome", text: c.nm }),
          h("span", { class: "ap-mudo", text: c.n + " · " + c.p }),
          h("span", { class: "el-res-votos", text: num(c.v) }),
          c.e ? h("span", { class: "ap-selo oficial", text: "eleito" }) : null)));
      });
      if (!achados.length) resultados.appendChild(h("li", { class: "ap-mudo", text: "Ninguém com esse nome neste cargo." }));
    }
    busca.addEventListener("input", function () { st.busca = busca.value; preencher(); });
    preencher();
    return cartao("Escolha o candidato", null,
      h("div", { class: "el-seletor" },
        pilulas(CARGOS, st.candCargo, function (c) { st.candCargo = c; AP.desenhar(); }, "Cargo"),
        pilulas(ANOS.map(function (a) { return [a, String(a)]; }), st.candAno, function (a) { st.candAno = a; AP.desenhar(); }, "Ano"),
        busca),
      lista === undefined ? carregando() : lista.erro ? falhou(lista) : resultados);
  }

  function cabecalhoCand(d) {
    var kpis = [];
    kpis.push(kpi("Votos", num(d.votos), (d.pct != null ? pct(d.pct, 2) + " dos válidos · " : "") +
      (d.posicao ? d.posicao + "º de " + d.candidatos : "")));
    if (d.anterior) {
      var var_ = d.anterior.votos ? (d.votos - d.anterior.votos) / d.anterior.votos * 100 : null;
      kpis.push(kpi("Em " + d.anterior.ano, num(d.anterior.votos),
        d.anterior.cargo_nome + " · " + d.anterior.situacao + (var_ != null && d.anterior.cargo === d.cargo ? " · " + (var_ >= 0 ? "+" : "−") + Math.abs(Math.round(var_)) + "%" : "")));
    } else if (d.tem_anterior) kpis.push(kpi("Em " + (d.ano - 4), "—", "não disputou eleição geral em SC"));
    if (d.previsao && d.previsao.p_eleito != null) {
      kpis.push(kpi("Previsão antes da eleição", Math.round(d.previsao.p_eleito * 100) + "%",
        "de chance de eleição (" + (d.eleito ? "acertou: eleito" : "foi " + (d.situacao || "não eleito").toLowerCase()) + ")"));
    }
    if (d.previsao && d.previsao.receita) {
      kpis.push(kpi("Custo por voto", "R$ " + (d.previsao.receita / Math.max(1, d.votos)).toLocaleString("pt-BR", { maximumFractionDigits: 2, minimumFractionDigits: 2 }),
        "R$ " + curto(d.previsao.receita) + " de receita declarada ao TSE"));
    }
    if (d.instagram) {
      kpis.push(kpi("Instagram", d.instagram.seguidores ? curto(d.instagram.seguidores) : "—",
        "@" + d.instagram.username + " · " + (d.instagram.seguidores && d.votos ? (d.votos / d.instagram.seguidores).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " voto por seguidor" : "")));
    }
    var c = cartao(d.nm, null,
      h("div", { class: "el-cab" },
        h("div", { class: "el-cab-id" },
          chip(d.ac, d.cor), h("span", { class: "ap-mudo", text: d.partido + " · " + d.n + " · " + d.cargo_nome + " " + d.ano }),
          h("span", { class: "ap-selo " + (d.eleito ? "oficial" : "fora"), text: (d.situacao || "").toLowerCase() }),
          d.nome && d.nome !== d.nm ? h("span", { class: "ap-mudo", text: d.nome }) : null),
        h("span", { class: "el-cab-links" },
          h("a", { class: "el-link", href: "/politicos/eleicao/raio-x.pdf?" + q({ ano: d.ano, cargo: d.cargo, n: d.n }),
            target: "_blank", rel: "noopener", text: "Raio-X em PDF" }),
          d.instagram ? h("a", { class: "el-link", href: "/politicos?perfil=" + d.instagram.perfil_id, text: "Ficha no monitor de redes →" }) : null)),
      h("div", { class: "ap-kpis el-kpis" }, kpis));
    return c;
  }

  function cartaoMargem(d) {
    var m = d.margem;
    if (!m) return null;
    var frases = [];
    var lista = d.ac + " fez " + m.cadeiras_lista + (m.cadeiras_lista === 1 ? " cadeira" : " cadeiras");
    if (d.eleito) {
      frases.push(h("p", { class: "el-frase forte" }, "Eleito como " + m.posicao_lista + "º da lista de " + m.tamanho_lista + ". " + lista + "."));
      if (m.sobre_1o_suplente != null) frases.push(h("p", { class: "el-frase" },
        "Ficou " + num(m.sobre_1o_suplente) + " votos à frente do 1º suplente (" + m.primeiro_suplente + ")."));
      if (m.folga_lista != null && m.posicao_lista === m.cadeiras_lista) frases.push(h("p", { class: "el-frase" },
        "Era a última vaga da lista: com " + num(m.folga_lista + 1) + " votos a menos, o " + d.ac + " perderia essa cadeira."));
    } else if (m.cadeiras_lista === 0) {
      frases.push(h("p", { class: "el-frase forte" }, "A lista (" + d.ac + ") não elegeu ninguém."));
      if (m.falta_proxima_lista != null) frases.push(h("p", { class: "el-frase" },
        "Faltaram " + num(m.falta_proxima_lista) + " votos à lista para a primeira cadeira" +
        (m.posicao_lista === 1 ? " — que seria dele." : ".")));
    } else {
      frases.push(h("p", { class: "el-frase forte" }, (m.seria_o_proximo ? "1º suplente: " : m.posicao_lista + "º da lista: ") + lista + "."));
      if (m.seria_o_proximo && m.falta_proxima_lista != null) frases.push(h("p", { class: "el-frase destaque" },
        "Com mais " + num(m.falta_proxima_lista) + " votos para o " + d.ac + ", a lei dava a próxima cadeira à lista — e ela seria dele."));
      if (m.para_passar_ultimo != null) frases.push(h("p", { class: "el-frase" },
        "Para passar o último eleito da lista (" + m.ultimo_eleito + "), faltaram " + num(m.para_passar_ultimo) + " votos."));
    }
    var pisos = [];
    if (d.votos < m.piso_10) pisos.push("abaixo de 10% do quociente (" + num(m.piso_10) + "): não poderia entrar nem pelo quociente partidário");
    else if (d.votos < m.piso_20) pisos.push("acima de 10% do quociente (" + num(m.piso_10) + "), abaixo de 20% (" + num(m.piso_20) + "): não poderia pegar sobra na 2ª fase");
    else pisos.push("acima de 20% do quociente (" + num(m.piso_20) + "): podia entrar por qualquer fase");
    return cartao("A cadeira, pela lei", "Quociente eleitoral " + num(m.qe) + ". As contas refazem a distribuição oficial com votos a mais ou a menos.",
      frases, h("p", { class: "ap-mudo", text: "Votação " + pisos[0] + "." }));
  }

  function cartaoMapaCand(d) {
    var valores = {}, porCd = {};
    d.cidades.forEach(function (c) { valores[String(c.cd)] = c.forca; porCd[String(c.cd)] = c; });
    var con = d.concentracao;
    var sel = st.cidade[d.n + ":" + d.ano] || (d.cidades[0] && d.cidades[0].cd);
    var mapa = mapaSC({ valores: valores, rotulo: "Força de " + d.nm + " em cada município", destaque: sel,
      dica: function (cd, nm) {
        var c = porCd[cd];
        if (!c || !c.v) return nm + ": sem voto";
        return nm + ": " + num(c.v) + " votos · " + fmtPct(c.forca) + " dos válidos · " + (c.pos ? c.pos + "º lugar" : "") + " · " + pct(c.peso, 1) + " do total dele";
      },
      clique: function (cd) { st.cidade[d.n + ":" + d.ano] = +cd; AP.desenhar(); } });
    var lado = h("div", { class: "el-mapa-lado" },
      h("div", { class: "ap-kpis el-kpis-mini" },
        kpi("Municípios com voto", String(con.municipios), "de 295"),
        kpi("Cidades que valem", con.n_efetivo.toLocaleString("pt-BR"), "nº efetivo: o voto dele equivale a tantas cidades do mesmo tamanho"),
        kpi("Maior cidade", pct(con.top1, 0), "do voto dele vem de uma cidade só"),
        kpi("5 maiores", pct(con.top5, 0), "do voto dele"),
        kpi("Primeiro lugar em", String(con.em_1o), con.em_1o === 1 ? "cidade" : "cidades"),
        kpi("Acima de 5%", String(con.acima_5pct), "cidades onde teve 5% ou mais dos válidos")),
      h("p", { class: "ap-mun-sub", text: "De onde vem o voto" }),
      h("ul", { class: "el-peso-lista" }, d.cidades.slice(0, 8).map(function (c) {
        return h("li", {}, h("span", { class: "el-peso-nome", text: c.nm }), barra(c.peso), h("span", { class: "num", text: pct(c.peso, 1) }));
      })));
    return cartao("Onde está o voto", "Cor = força: o voto dele ÷ os válidos da cidade. Toque numa cidade para ver os locais de votação.",
      h("div", { class: "el-grade-mapa" }, mapa, lado));
  }

  function cartaoCidades(d) {
    var chave = "cid:" + d.ano + ":" + d.n;
    var ordem = st.ordem[chave] || "v";
    var cids = d.cidades.filter(function (c) { return c.v > 0; }).slice();
    var temAnt = !!d.anterior;
    var chaveOrd = { v: function (c) { return -c.v; }, forca: function (c) { return -c.forca; },
      delta: function (c) { return -((c.v || 0) - (c.v_ant || 0)); }, pos: function (c) { return c.pos || 999; } };
    cids.sort(function (a, b) { return chaveOrd[ordem](a) - chaveOrd[ordem](b); });
    var n = limite(chave, celular() ? 10 : 20);
    var linhas = cids.slice(0, n).map(function (c) {
      return h("tr", { class: "el-clicavel", onclick: function () { st.cidade[d.n + ":" + d.ano] = c.cd; AP.desenhar();
          var alvo = document.getElementById("el-dentro"); if (alvo) alvo.scrollIntoView({ behavior: "smooth" }); } },
        h("td", { text: c.nm }), h("td", { class: "num", text: num(c.v) }),
        h("td", { class: "num", text: pct(c.peso, 1) }), h("td", { class: "num", text: fmtPct(c.forca) }),
        h("td", { class: "num ocultar-celular", text: c.pos ? c.pos + "º de " + c.de : "—" }),
        h("td", { class: "ocultar-celular", text: c.lider ? c.lider : "★ ele" }),
        temAnt ? h("td", { class: "num ocultar-celular", text: c.v_ant != null ? num(c.v_ant) : "—" }) : null,
        temAnt ? h("td", { class: "num" }, delta((c.v || 0) - (c.v_ant || 0))) : null);
    });
    var ordens = [["v", "Mais votos"], ["forca", "Mais força"], ["pos", "Melhor posição"]];
    if (temAnt) ordens.push(["delta", "Mais cresceu"]);
    return cartao("Cidade a cidade", cids.length + " municípios com voto" + (temAnt ? " · comparação com " + d.anterior.ano + " (" + d.anterior.cargo_nome.toLowerCase() + ")" : ""),
      pilulas(ordens, ordem, function (o) { st.ordem[chave] = o; AP.desenhar(); }, "Ordenar"),
      tabela([["Cidade"], ["Votos", "num"], ["Peso", "num"], ["Força", "num"], ["Posição", "num ocultar-celular"],
        ["Quem liderou", "ocultar-celular"]].concat(temAnt ? [[String(d.anterior.ano), "num ocultar-celular"], ["Δ", "num"]] : []), linhas),
      mais(chave, cids.length, n));
  }

  function cartaoConcorrentes(d) {
    if (!d.concorrentes || !d.concorrentes.length) return null;
    return cartao("Quem disputa o mesmo eleitor", "Sobreposição = quanto do voto dos dois vem das mesmas cidades, na mesma proporção. Toque para abrir.",
      h("ul", { class: "el-conc" }, d.concorrentes.map(function (c) {
        return h("li", {}, h("button", { type: "button", class: "el-conc-item", onclick: function () { escolherCand(d.ano, d.cargo, c.n); } },
          h("span", { class: "el-conc-nome" }, h("b", { text: c.nm }), " ", chip(c.ac, c.cor),
            c.mesma_lista ? h("span", { class: "ap-selo media", text: "mesma lista" }) : null),
          barra(c.sobreposicao, c.cor), h("span", { class: "num", text: pct(c.sobreposicao, 0) }),
          h("span", { class: "ap-mudo el-conc-v", text: num(c.v) + " votos · " + (c.st || "").toLowerCase() })));
      })));
  }

  function cartaoDentro(d) {
    var cd = st.cidade[d.n + ":" + d.ano] || (d.cidades[0] && d.cidades[0].cd);
    var cid = d.cidades.filter(function (c) { return c.cd === cd; })[0];
    var opcoes = d.cidades.filter(function (c) { return c.v > 0; }).slice(0, 60);
    var escolha = h("select", { "aria-label": "Cidade" }, opcoes.map(function (c) {
      return h("option", { value: String(c.cd), text: c.nm + " (" + num(c.v) + ")" });
    }));
    escolha.value = String(cd);
    escolha.addEventListener("change", function () { st.cidade[d.n + ":" + d.ano] = +escolha.value; AP.desenhar(); });
    var corpo;
    if (!d.secoes) {
      corpo = h("p", { class: "ap-mudo", text: d.ano === 2026
        ? "O TSE ainda não publicou o voto de 2026 por seção (o boletim de urna sai alguns dias depois da eleição). Ele entra aqui sozinho quando sair. Enquanto isso, escolha 2022 no seletor para ver como funciona."
        : "Voto por seção indisponível para este ano." });
    } else {
      var loc = obter("/locais.json?" + q({ ano: d.ano, cargo: d.cargo, n: d.n, cd: cd }));
      if (loc === undefined) corpo = carregando();
      else if (loc.erro || loc.indisponivel) corpo = falhou(loc);
      else corpo = desenharLocais(loc, d.nm, "dentro:" + d.ano + ":" + d.n + ":" + cd);
    }
    var c = cartao("Dentro da cidade" + (cid ? " · " + cid.nm : ""), "Locais de votação (escolas) e bairros, pelo voto por seção do TSE.",
      h("div", { class: "ap-filtros" }, escolha), corpo);
    c.id = "el-dentro";
    return c;
  }

  function desenharLocais(loc, quem, chave) {
    var nB = limite(chave + ":b", celular() ? 8 : 15), nL = limite(chave + ":l", celular() ? 8 : 15);
    var maxB = Math.max.apply(null, loc.bairros.map(function (b) { return b.forca; }).concat([0.01]));
    var bairros = loc.bairros.filter(function (b) { return b.v > 0; });
    var locais = loc.locais.filter(function (l) { return l.v > 0; });
    return h("div", { class: "el-dentro" },
      pontosCidade(loc, quem),
      h("div", {},
        h("p", { class: "ap-mun-sub", text: "Bairros (" + bairros.length + " com voto)" }),
        tabela([["Bairro"], ["Votos", "num"], ["Força", "num"], [""]], bairros.slice(0, nB).map(function (b) {
          return h("tr", {}, h("td", { text: b.bairro }), h("td", { class: "num", text: num(b.v) }),
            h("td", { class: "num", text: fmtPct(b.forca) }), h("td", {}, barra(b.forca / maxB * 100)));
        })), mais(chave + ":b", bairros.length, nB),
        h("p", { class: "ap-mun-sub", text: "Locais de votação (" + locais.length + " com voto)" }),
        tabela([["Local"], ["Bairro", "ocultar-celular"], ["Votos", "num"], ["Força", "num"]], locais.slice(0, nL).map(function (l) {
          return h("tr", {}, h("td", { text: l.nm }), h("td", { class: "ocultar-celular", text: l.bairro }),
            h("td", { class: "num", text: num(l.v) }), h("td", { class: "num", text: fmtPct(l.forca) }));
        })), mais(chave + ":l", locais.length, nL)));
  }

  /* Os locais de votação como pontos, dentro do contorno da cidade (lat/lon do TSE). */
  function pontosCidade(loc, quem) {
    var pts = loc.locais.filter(function (l) { return l.lat && l.lon; });
    if (pts.length < 3) return h("p", { class: "ap-mudo", text: "Sem coordenadas dos locais desta cidade." });
    var lats = pts.map(function (p) { return p.lat; }), lons = pts.map(function (p) { return p.lon; });
    var la0 = Math.min.apply(null, lats), la1 = Math.max.apply(null, lats);
    var lo0 = Math.min.apply(null, lons), lo1 = Math.max.apply(null, lons);
    var fx = Math.cos((la0 + la1) / 2 * Math.PI / 180);
    var W = 320, pad = 14;
    var k = (W - 2 * pad) / Math.max((lo1 - lo0) * fx, (la1 - la0), 0.0001);
    var H = Math.max(160, Math.round((la1 - la0) * k + 2 * pad));
    var maxV = Math.max.apply(null, pts.map(function (p) { return p.v; }).concat([1]));
    var qs = quebras(pts.map(function (p) { return p.forca; }));
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, class: "el-pontos", role: "img", "aria-label": "Locais de votação de " + loc.nm });
    pts.slice().sort(function (a, b) { return a.v - b.v; }).forEach(function (p) {
      var x = pad + (p.lon - lo0) * fx * k, y = pad + (la1 - p.lat) * k;
      svg.appendChild(s("circle", { cx: x.toFixed(1), cy: y.toFixed(1), r: (2.5 + 9 * Math.sqrt(p.v / maxV)).toFixed(1),
        fill: corEscala(p.forca, qs), class: "el-ponto",
        "data-tip": p.nm + " (" + p.bairro + "): " + num(p.v) + " votos de " + quem + " · " + fmtPct(p.forca) + " dos válidos do local" }));
    });
    return h("div", { class: "el-pontos-caixa" }, svg,
      h("p", { class: "ap-mudo", text: "Cada círculo é um local de votação: tamanho = votos, cor = força ali." }));
  }

  function cartaoPerfil(d) {
    if (!d.secoes) return null;
    var p = obter("/perfil.json?" + q({ ano: d.ano, cargo: d.cargo, n: d.n }));
    var corpo;
    if (p === undefined) corpo = carregando();
    else if (p.erro || p.indisponivel) corpo = h("p", { class: "ap-mudo", text: "Sem perfil do eleitorado por seção para " + d.ano + " ainda." });
    else {
      corpo = h("div", { class: "el-perfil" }, p.dimensoes.map(function (x) {
        var idx = x.indice;
        return h("div", { class: "el-perfil-linha" },
          h("span", { class: "el-perfil-rot", text: x.rotulo }),
          h("span", { class: "el-perfil-barras" },
            h("span", { class: "el-perfil-b meu", vars: { "--p": Math.min(100, x.meu) + "%" } }),
            h("span", { class: "el-perfil-b geral", vars: { "--p": Math.min(100, x.geral) + "%" } })),
          h("span", { class: "num", text: pct(x.meu, 0) + " × " + pct(x.geral, 0) }),
          h("span", { class: "el-indice " + (idx >= 110 ? "sobe" : idx <= 90 ? "desce" : ""), text: idx == null ? "—" : String(idx) }));
      }), h("p", { class: "ap-mudo", text: "Barra escura = eleitorado das seções, pesado pelo voto dele; clara = pesado pelo voto de todos. Índice 100 = igual à média; 120 = 20% acima. Perfil do eleitorado de " + p.ano_perfil + "." }));
    }
    return cartao("Onde ele é forte, pelo perfil do eleitorado", "Inferência ecológica: compara seções, não pessoas.", corpo);
  }

  function vistaCandidato() {
    var blocos = [seletorCandidato()];
    if (!st.cand) {
      var lista = obter("/candidatos.json?" + q({ ano: st.candAno, cargo: st.candCargo }));
      if (lista && !lista.erro && lista.length) {
        var foco = (AP.app.foco || []);
        var pref = lista.filter(function (c) { return foco.indexOf(String(c.p).toUpperCase()) >= 0; })[0] || lista[0];
        st.cand = { ano: st.candAno, cargo: st.candCargo, n: pref.n };
      } else return blocos;
    }
    var c = st.cand;
    var d = obter("/candidato.json?" + q({ ano: c.ano, cargo: c.cargo, n: c.n }));
    if (d === undefined) { blocos.push(carregando("Montando o raio-x…")); return blocos; }
    if (d.erro) { blocos.push(falhou(d)); return blocos; }
    blocos.push(cabecalhoCand(d));
    var margem = cartaoMargem(d);
    if (margem) blocos.push(margem);
    blocos.push(cartaoMapaCand(d));
    blocos.push(h("div", { class: "el-duas" }, cartaoConcorrentes(d), cartaoPerfil(d)));
    blocos.push(cartaoDentro(d));
    blocos.push(cartaoCidades(d));
    return blocos;
  }

  // ── aba Municípios ──────────────────────────────────────────────────────
  function vistaMunicipios() {
    var m = st.mun;
    var muns = obter("/municipios.json");
    var lid = obter("/lideres.json?" + q({ ano: m.ano, cargo: m.cargo }));
    var cid = obter("/cidade.json?" + q({ ano: m.ano, cargo: m.cargo, cd: m.cd }));
    function trocar(campo, v) { st.mun[campo] = v; salvar("eleicao-mun", st.mun); st.abertos = {}; AP.desenhar(); }
    var escolha = h("select", { "aria-label": "Município" });
    if (muns && !muns.erro) muns.forEach(function (x) { escolha.appendChild(h("option", { value: x.cd, text: x.nm })); });
    escolha.value = String(m.cd);
    escolha.addEventListener("change", function () { trocar("cd", +escolha.value); });
    var blocos = [cartao("Município", null, h("div", { class: "el-seletor" },
      pilulas(CARGOS, m.cargo, function (c) { trocar("cargo", c); }, "Cargo"),
      pilulas(ANOS.map(function (a) { return [a, String(a)]; }), m.ano, function (a) { trocar("ano", a); }, "Ano"),
      escolha))];
    var mapa;
    if (lid === undefined) mapa = carregando("Carregando o mapa…");
    else if (lid.erro) mapa = falhou(lid);
    else {
      var cores = {};
      Object.keys(lid.cidades).forEach(function (cd) { cores[cd] = lid.cidades[cd].cor || "#9aa5b4"; });
      mapa = mapaSC({ cores: cores, rotulo: "Lista mais votada em cada município", destaque: m.cd,
        dica: function (cd, nm) {
          var x = lid.cidades[cd];
          return x ? nm + ": " + x.ac + " " + pct(x.pct, 1) + (x.cand ? " · mais votado: " + x.cand + " (" + pct(x.cand_pct, 1) + ")" : "") : nm;
        },
        clique: function (cd) { trocar("cd", +cd); },
        legenda: h("div", { class: "ap-mapa-legenda" }, lid.legenda.slice(0, 10).map(function (x) {
          return h("span", { vars: { "--cor": x.cor || "#9aa5b4" }, text: x.ac + " (" + x.cidades + ")" });
        })) });
    }
    var det;
    if (cid === undefined) det = carregando();
    else if (cid.erro) det = falhou(cid);
    else det = detalheCidade(cid);
    blocos.push(h("div", { class: "el-grade-mapa" }, cartao(CARGO_CURTO[m.cargo] + " · quem venceu onde " + m.ano,
      "Cor = a lista (partido ou federação) mais votada na cidade. Toque numa cidade para abri-la.", mapa), det));
    if (cid && !cid.erro) blocos.push(candidatosCidade(cid));
    return blocos;
  }

  function detalheCidade(c) {
    var comp = c.aptos ? c.comparecimento / c.aptos * 100 : null;
    var bn = c.comparecimento ? ((c.brancos || 0) + (c.nulos || 0)) / c.comparecimento * 100 : null;
    var n = limite("agr:" + c.cd, 12);
    var temAnt = c.agremiacoes.some(function (a) { return a.pct_ant != null; });
    return cartao(c.nm, CARGO_CURTO[c.cargo] + " · " + c.ano,
      h("div", { class: "ap-kpis el-kpis-mini" },
        kpi("Eleitores", num(c.aptos), ""), kpi("Comparecimento", comp != null ? pct(comp, 1) : "—", num(c.comparecimento) + " votaram"),
        kpi("Brancos e nulos", bn != null ? pct(bn, 1) : "—", num((c.brancos || 0) + (c.nulos || 0))),
        kpi("Votos válidos", num(c.validos), "")),
      tabela([["Lista"], ["%", "num"], [temAnt ? String(c.ano - 4) : "", "num"], [temAnt ? "Δ p.p." : "", "num"]],
        c.agremiacoes.slice(0, n).map(function (a) {
          return h("tr", { class: "el-clicavel", onclick: function () {
              st.part = { a: a.a, cargo: c.cargo, ano: c.ano }; salvar("eleicao-partido", st.part); location.hash = "partidos"; } },
            h("td", {}, chip(a.ac, a.cor)), h("td", { class: "num", text: pct(a.pct, 1) }),
            h("td", { class: "num", text: a.pct_ant != null ? pct(a.pct_ant, 1) : "" }),
            h("td", { class: "num" }, temAnt && a.pct_ant != null ? delta(a.pct - a.pct_ant, 1) : ""));
        })), mais("agr:" + c.cd, c.agremiacoes.length, n));
  }

  function candidatosCidade(c) {
    var chave = "cands:" + c.cd + ":" + c.cargo;
    var n = limite(chave, celular() ? 10 : 20);
    return cartao("Mais votados em " + c.nm, "Toque num nome para abrir o raio-x do candidato.",
      tabela([["#", "num"], ["Candidato"], ["Lista", "ocultar-celular"], ["Votos", "num"], ["%", "num"]],
        c.candidatos.slice(0, n).map(function (x, i) {
          return h("tr", { class: "el-clicavel", onclick: function () { escolherCand(c.ano, c.cargo, x.n); location.hash = "candidato"; } },
            h("td", { class: "num", text: String(i + 1) }),
            h("td", {}, x.nm + " ", x.e ? h("span", { class: "ap-selo oficial", text: "eleito" }) : null),
            h("td", { class: "ocultar-celular", text: x.p }), h("td", { class: "num", text: num(x.v) }),
            h("td", { class: "num", text: pct(x.pct, 1) }));
        })), mais(chave, c.candidatos.length, n));
  }

  // ── aba Partidos ────────────────────────────────────────────────────────
  function vistaPartidos() {
    var p = st.part;
    function trocar(campo, v) { st.part[campo] = v; salvar("eleicao-partido", st.part); st.abertos = {}; AP.desenhar(); }
    if (!p.a) {
      var foco = (AP.app.foco || []);
      p.a = foco.length ? foco[0] : "NOVO";
    }
    var d = obter("/partido.json?" + q({ ano: p.ano, cargo: p.cargo, a: p.a }));
    var opcoes = d && !d.erro ? d.agremiacoes : [];
    var escolha = h("select", { "aria-label": "Partido ou federação" }, opcoes.map(function (x) { return h("option", { value: x.a, text: x.ac }); }));
    escolha.value = d && d.agremiacao ? d.agremiacao : p.a;
    escolha.addEventListener("change", function () { trocar("a", escolha.value); });
    var blocos = [cartao("Partido ou federação", null, h("div", { class: "el-seletor" },
      pilulas(CARGOS.slice(0, 2), p.cargo, function (c) { trocar("cargo", c); }, "Cargo"),
      pilulas(ANOS.map(function (a) { return [a, String(a)]; }), p.ano, function (a) { trocar("ano", a); }, "Ano"),
      escolha))];
    if (d === undefined) { blocos.push(carregando()); return blocos; }
    if (d.erro) { blocos.push(falhou(d)); return blocos; }
    if (d.ausente) { blocos.push(h("p", { class: "ap-mudo", text: "Esta lista não disputou " + CARGO_CURTO[p.cargo] + " em " + p.ano + ". Escolha outra acima." })); return blocos; }
    if (d.pedido && d.pedido !== d.agremiacao) blocos.push(h("p", { class: "ap-aviso-modo",
      text: "Em " + d.ano + ", \"" + d.pedido + "\" não existia como lista: mostrando " + d.ac + ", a maior das que formaram a lista de hoje." }));
    var mg = d.margem || {};
    blocos.push(h("div", { class: "ap-kpis" },
      kpi("Votos", num(d.votos), pct(d.pct, 2) + " dos válidos" + (d.pct_ant != null ? " · " + (d.ano - 4) + ": " + pct(d.pct_ant, 2) : "")),
      kpi("Voto de legenda", d.votos ? pct(d.legenda / d.votos * 100, 1) : "—", num(d.legenda) + " votos só no partido"),
      mg.cadeiras != null ? kpi("Cadeiras", String(mg.cadeiras), mg.folga != null ? "a última com folga de " + num(mg.folga) + " votos" : "nenhuma") : null,
      mg.falta_proxima != null ? kpi("Para a próxima", num(mg.falta_proxima), "votos a mais e a lei dava mais uma cadeira") : null));
    var valores = {}, porCd = {};
    d.cidades.forEach(function (c) { valores[String(c.cd)] = c.forca; porCd[String(c.cd)] = c; });
    var mapa = mapaSC({ valores: valores, rotulo: "Força de " + d.ac + " em cada município",
      dica: function (cd, nm) {
        var c = porCd[cd];
        return c ? nm + ": " + num(c.v) + " votos · " + fmtPct(c.forca) + (c.forca_ant != null ? " (em " + (d.ano - 4) + ": " + fmtPct(c.forca_ant) + ")" : "") : nm + ": sem voto";
      },
      clique: function (cd) { st.mun = { cd: +cd, cargo: d.cargo, ano: d.ano }; salvar("eleicao-mun", st.mun); location.hash = "municipios"; } });
    var nC = limite("pc:" + d.agremiacao, celular() ? 8 : 15);
    blocos.push(h("div", { class: "el-grade-mapa" },
      cartao("Onde " + d.ac + " é forte", "Cor = votos da lista ÷ válidos da cidade. Toque para abrir a cidade.", mapa),
      cartao("Quem puxou a lista", "Peso = votos do candidato ÷ votos da lista (com legenda).",
        tabela([["Candidato"], ["Votos", "num"], ["Peso", "num"], [""]], d.candidatos.slice(0, nC).map(function (c) {
          return h("tr", { class: "el-clicavel", onclick: function () { escolherCand(d.ano, d.cargo, c.n); location.hash = "candidato"; } },
            h("td", {}, c.nm + " ", c.e ? h("span", { class: "ap-selo oficial", text: "eleito" }) : null),
            h("td", { class: "num", text: num(c.v) }), h("td", { class: "num", text: pct(c.peso, 1) }),
            h("td", {}, barra(c.peso * 2, d.cor)));
        })), mais("pc:" + d.agremiacao, d.candidatos.length, nC))));
    var chave = "pcid:" + d.agremiacao;
    var ordem = st.ordem[chave] || "v";
    var cids = d.cidades.slice().sort(function (a, b) {
      if (ordem === "forca") return b.forca - a.forca;
      if (ordem === "delta") return (b.forca - (b.forca_ant || 0)) - (a.forca - (a.forca_ant || 0));
      if (ordem === "queda") return (a.forca - (a.forca_ant || 0)) - (b.forca - (b.forca_ant || 0));
      return b.v - a.v;
    });
    var temAnt = cids.some(function (c) { return c.forca_ant != null; });
    var n = limite(chave, celular() ? 10 : 20);
    var ordens = [["v", "Mais votos"], ["forca", "Mais força"]];
    if (temAnt) ordens.push(["delta", "Mais cresceu"], ["queda", "Mais caiu"]);
    blocos.push(cartao("Cidade a cidade", temAnt ? "Comparação com " + (d.ano - 4) + ": os partidos de então somados na lista de hoje (PP + União, PTB + Patriota…)." : null,
      pilulas(ordens, ordem, function (o) { st.ordem[chave] = o; AP.desenhar(); }, "Ordenar"),
      tabela([["Cidade"], ["Votos", "num"], ["Força", "num"]].concat(temAnt ? [[String(d.ano - 4), "num"], ["Δ p.p.", "num"]] : []),
        cids.slice(0, n).map(function (c) {
          return h("tr", {}, h("td", { text: c.nm }), h("td", { class: "num", text: num(c.v) }), h("td", { class: "num", text: fmtPct(c.forca) }),
            temAnt ? h("td", { class: "num", text: c.forca_ant != null ? fmtPct(c.forca_ant) : "—" }) : null,
            temAnt ? h("td", { class: "num" }, delta(c.forca - (c.forca_ant || 0), 1)) : null);
        })), mais(chave, cids.length, n)));
    return blocos;
  }

  // ── aba Previsão (só admin) ──────────────────────────────────────────────
  function cartaoAlgoritmo(m) {
    var c = m.comparacao, f = c.foto_congelada;
    var linhas = c.variantes.map(function (v) {
      var destaque = v.nome === "completo" || v.nome === "sem_receita";
      return h("tr", { class: destaque ? "foco" : null },
        h("td", {}, h("b", { text: v.nome.replace(/_/g, " ") }), h("div", { class: "ap-mudo", text: m.descricao[v.nome] || "" })),
        h("td", { class: "num", text: v.eleitos_certos + "/40" }), h("td", { class: "num", text: String(v.cadeiras_erradas) }),
        h("td", { class: "num", text: v.r2.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }),
        h("td", { class: "num ocultar-celular", text: v.spearman.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }),
        h("td", { class: "num ocultar-celular", text: v.brier != null ? v.brier.toLocaleString("pt-BR", { minimumFractionDigits: 3 }) : "—" }));
    });
    if (f) linhas.push(h("tr", { class: "el-linha-ref" },
      h("td", {}, h("b", { text: "foto congelada 04/10" }), h("div", { class: "ap-mudo", text: "a previsão feita antes da apuração (cenário " + f.cenario + ")" })),
      h("td", { class: "num", text: f.eleitos_certos + "/40" }), h("td", { class: "num", text: String(f.cadeiras_erradas) }),
      h("td", { class: "num", text: "—" }),
      h("td", { class: "num ocultar-celular", text: f.spearman != null ? f.spearman.toLocaleString("pt-BR", { minimumFractionDigits: 2 }) : "—" }),
      h("td", { class: "num ocultar-celular", text: f.brier != null ? f.brier.toLocaleString("pt-BR", { minimumFractionDigits: 3 }) : "—" })));
    function pesos(nome, titulo) {
      var ps = (m.pesos[nome] || []).slice(0, 8);
      var max = Math.max.apply(null, ps.map(function (x) { return Math.abs(x.padronizado); }).concat([0.01]));
      return h("div", {}, h("p", { class: "ap-mun-sub", text: titulo }),
        h("ul", { class: "el-peso-lista el-pesos" }, ps.map(function (x) {
          return h("li", {}, h("span", { class: "el-peso-nome", text: x.variavel }),
            barra(Math.abs(x.padronizado) / max * 100, x.padronizado >= 0 ? "var(--el-azul)" : "var(--el-desce)"),
            h("span", { class: "num", text: (x.padronizado >= 0 ? "+" : "−") + Math.abs(x.padronizado).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) }));
        })));
    }
    return cartao("O algoritmo (" + m.versao + ")",
      "Treinado em " + m.n + " candidatos a deputado estadual de 2026: o que se sabia na manhã de 04/10 contra o resultado. " +
      "Tudo medido FORA da amostra (validação cruzada 10×5): cada candidato previsto por um modelo que não o viu.",
      tabela([["Variante"], ["Eleitos certos", "num"], ["Cadeiras erradas", "num"], ["R² do voto", "num"],
        ["Postos", "num ocultar-celular"], ["Brier", "num ocultar-celular"]], linhas),
      h("p", { class: "el-frase" }, "Leitura: o modelo ORDENA bem os candidatos dentro da lista (postos 0,85 com receita, 0,72 sem), " +
        "mas nenhuma variante acerta o TAMANHO das listas — a onda do PL não estava em variável nenhuma. Por isso os nomes certos ficam em 26–29 de 40 em todas."),
      h("div", { class: "el-duas el-pesos-grade" }, pesos("completo", "Perto da eleição (com receita): o que pesa"),
        pesos("sem_receita", "Longe da eleição (sem receita): o que pesa")),
      h("p", { class: "ap-mudo", text: "Peso padronizado: quanto o voto previsto (em log) muda com 1 desvio-padrão da variável. Negativo = puxa para baixo. " +
        "As marcas \"sem receita\", \"sem Instagram\" e \"estreante\" corrigem o zero das variáveis em log (quem não tem o dado não é quem tem zero) — não são efeito de não ter Instagram." }));
  }

  function cartaoProxima(p) {
    var cands = p.candidatos;
    var entram = cands.filter(function (c) { return c.entra && !c.eleito; });
    var saem = cands.filter(function (c) { return c.eleito && !c.entra; });
    var n = limite("prox", celular() ? 15 : 40);
    function pessoa(c) {
      return h("li", {}, h("button", { type: "button", class: "el-conc-item", onclick: function () { escolherCand(2026, 7, c.numero); location.hash = "candidato"; } },
        h("span", { class: "el-conc-nome" }, h("b", { text: c.nome }), " ", chip(c.ac, c.cor)),
        barra(c.p_eleito * 100, c.cor), h("span", { class: "num", text: pct(c.p_eleito * 100, 0) }),
        h("span", { class: "ap-mudo el-conc-v", text: c.posicao_lista + "º previsto na lista · " + num(c.votos) + " votos em 2026" })));
    }
    return [
      cartao("A próxima ALESC, se fosse hoje", "Modelo " + p.modelo.variante.replace(/_/g, " ") + ": voto de 2026 + mandato + Instagram (coleta desde " +
        p.janela_redes_desde.split("-").reverse().join("/") + "). Cada lista com as cadeiras que fez em 2026; o modelo decide QUEM as ocupa. " +
        "Muda sozinho a cada coleta semanal do monitor de redes. Não é pesquisa: quem ainda não é candidato não aparece.",
        h("div", { class: "ap-kpis el-kpis-mini" },
          kpi("Mudariam de dono", String(entram.length), "cadeiras de 40, pela ordem prevista"),
          kpi("Postos com folga", String(cands.filter(function (c) { return c.p_eleito >= 0.8; }).length), "chance de 80% ou mais"),
          kpi("Disputa aberta", String(cands.filter(function (c) { return c.p_eleito >= 0.3 && c.p_eleito < 0.7; }).length), "entre 30% e 70% de chance")),
        h("div", { class: "el-duas" },
          h("div", {}, h("p", { class: "ap-mun-sub", text: "Entrariam (suplentes ou fora em 2026)" }),
            entram.length ? h("ul", { class: "el-conc" }, entram.map(pessoa)) : h("p", { class: "ap-mudo", text: "Ninguém." })),
          h("div", {}, h("p", { class: "ap-mun-sub", text: "Sairiam (eleitos em 2026)" }),
            saem.length ? h("ul", { class: "el-conc" }, saem.map(pessoa)) : h("p", { class: "ap-mudo", text: "Ninguém." })))),
      p.fora_do_monitor && p.fora_do_monitor.length ? cartao("Fora do monitor de redes", "Sem Instagram acompanhado (não declararam rede social ao TSE). A previsão deles usa só o voto de 2026 e o mandato — cadastre o @ na fila do /politicos para entrarem na conta.",
        h("ul", { class: "el-fora" }, p.fora_do_monitor.map(function (c) {
          return h("li", {}, h("b", { text: c.nome }), " ", h("span", { class: "ap-mudo", text: c.partido + " · " + num(c.votos) + " votos" }),
            c.eleito ? h("span", { class: "ap-selo oficial", text: "eleito 2026" }) : null);
        }))) : null,
      cartao("Chance de ocupar uma cadeira da própria lista", "Ordenado pela chance. Toque para abrir o raio-x de 2026.",
        tabela([["Candidato"], ["Lista", "ocultar-celular"], ["2026", "num"], ["Posição prevista", "num ocultar-celular"], ["Chance", "num"], [""]],
          cands.slice(0, n).map(function (c) {
            return h("tr", { class: "el-clicavel", onclick: function () { escolherCand(2026, 7, c.numero); location.hash = "candidato"; } },
              h("td", {}, c.nome + " ", c.eleito ? h("span", { class: "ap-selo oficial", text: "eleito 2026" }) : null,
                c.monitorado ? null : h("span", { class: "ap-mudo", "data-tip": "Sem Instagram no monitor: previsto só pelo voto e pelo mandato", text: " · sem redes" })),
              h("td", { class: "ocultar-celular" }, chip(c.ac, c.cor)),
              h("td", { class: "num", text: num(c.votos) }),
              h("td", { class: "num ocultar-celular", text: c.posicao_lista + "º" }),
              h("td", { class: "num", text: pct(c.p_eleito * 100, 0) }),
              h("td", {}, c.entra && !c.eleito ? h("span", { class: "el-delta sobe", text: "entra" }) : !c.entra && c.eleito ? h("span", { class: "el-delta desce", text: "sai" }) : null));
          })), mais("prox", cands.length, n))];
  }

  function vistaPrevisao() {
    var m = obter("/modelo.json"), p = obter("/proxima.json");
    var blocos = [];
    if (p === undefined) blocos.push(carregando("Calculando a próxima eleição…"));
    else if (p.erro || p.indisponivel) blocos.push(falhou(p));
    else blocos = blocos.concat(cartaoProxima(p));
    if (m === undefined) blocos.push(carregando());
    else if (m.erro || m.indisponivel) blocos.push(h("p", { class: "ap-mudo", text: "O algoritmo ainda não foi treinado (python -m politicos.modelo treinar)." }));
    else blocos.push(cartaoAlgoritmo(m));
    return blocos;
  }

  window.AP_EXTRAS.previsao = vistaPrevisao;
  window.AP_EXTRAS.candidato = vistaCandidato;
  window.AP_EXTRAS.municipios = vistaMunicipios;
  window.AP_EXTRAS.partidos = vistaPartidos;
  if (AP.app.estado && window.AP_EXTRAS[AP.app.vista]) AP.desenhar();
})();
