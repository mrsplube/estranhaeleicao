/* Botão "Compartilhar" do rodapé (templates/site_rodape.html).
 *
 * Um botão só, em qualquer tela:
 * - celular/tablet (ponteiro grosso): tenta a folha nativa (navigator.share);
 *   se ela não existir ou recusar (menos AbortError, que é o usuário fechando),
 *   cai no mesmo menu do computador;
 * - computador: abre o menu de canais (copiar link, WhatsApp, X, Telegram,
 *   e-mail). Nada de copiar às cegas: o clique sempre mostra alguma coisa.
 *
 * O `prompt()` só aparece como último recurso: navegador sem clipboard, sem
 * share e com a cópia por seleção também bloqueada.
 *
 * A telemetria é a mesma de antes ({e:"compartilhar", a:<caminho>}); o canal
 * vai no campo `c`, que o /v (main.py → visitas.evento) lê só `e` e `a` e
 * ignora o resto sem quebrar. */
(function () {
  "use strict";
  var PADRAO_TITULO = "estranhaeleicao.org";

  function ehToque() {
    try { return !!(window.matchMedia && window.matchMedia("(hover: none) and (pointer: coarse)").matches); }
    catch (x) { return false; }
  }

  /* A página certa: sem hash e sem query (o `?v=` do cache-busting e as âncoras
     não têm nada a ver com o que se está compartilhando). */
  function urlPagina() {
    try {
      var u = new URL(location.href);
      u.hash = "";
      u.search = "";
      return u.href;
    } catch (x) {
      return location.origin + location.pathname;
    }
  }

  /* O texto sai da própria página: og:title (é o que o WhatsApp mostra) e,
     se não houver, o <title> sem o rabicho " · estranhaeleicao.org". */
  function tituloPagina() {
    var meta = document.querySelector('meta[property="og:title"]');
    var t = meta && meta.getAttribute("content") ? meta.getAttribute("content") : "";
    if (!t) t = document.title || "";
    t = t.replace(/\s*[·|–—-]\s*estranhaeleicao\.org\s*$/i, "").trim();
    return t || PADRAO_TITULO;
  }

  function registrar(canal) {
    try {
      navigator.sendBeacon("/v", new Blob([JSON.stringify({ e: "compartilhar", a: location.pathname, c: canal })], { type: "application/json" }));
    } catch (x) { /* sem beacon */ }
  }

  /* Cópia do link: clipboard moderno → textarea+execCommand → prompt(). */
  function copiar(texto, pronto, falhou) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(texto).then(pronto, function () { copiarAntigo(texto, pronto, falhou); });
      return;
    }
    copiarAntigo(texto, pronto, falhou);
  }

  function copiarAntigo(texto, pronto, falhou) {
    var velho = document.createElement("textarea");
    var ok = false;
    try {
      velho.value = texto;
      velho.setAttribute("readonly", "");
      velho.style.cssText = "position:fixed;top:0;left:-9999px;opacity:0";
      document.body.appendChild(velho);
      velho.select();
      ok = !!(document.execCommand && document.execCommand("copy"));
    } catch (x) { ok = false; }
    if (velho.parentNode) velho.parentNode.removeChild(velho);
    if (ok) { pronto(); return; }
    // último recurso absoluto: navegador antigo, sem clipboard e sem execCommand
    try {
      prompt("Copie o link:", texto);
      return;
    } catch (x) { /* nem prompt existe */ }
    if (falhou) falhou();
  }

  document.querySelectorAll(".pe-compartilhar").forEach(function (botao) {
    var caixa = botao.parentNode;
    var menu = caixa ? caixa.querySelector(".pe-menu") : null;
    if (!menu) return;

    var relogio = 0;

    var itens = function () {
      return Array.prototype.filter.call(menu.querySelectorAll(".pe-item"), function (el) {
        return el.getAttribute("aria-disabled") !== "true";
      });
    };

    /* Os links nascem vazios no HTML (sem JS não há menu para abrir): aqui eles
       ganham a URL da página e o texto dela. */
    var url = urlPagina();
    var titulo = tituloPagina();
    var junto = titulo + " — " + url;
    var links = {
      whatsapp: "https://wa.me/?text=" + encodeURIComponent(junto),
      twitter: "https://twitter.com/intent/tweet?text=" + encodeURIComponent(titulo) + "&url=" + encodeURIComponent(url),
      telegram: "https://t.me/share/url?url=" + encodeURIComponent(url) + "&text=" + encodeURIComponent(titulo),
      email: "mailto:?subject=" + encodeURIComponent(titulo) + "&body=" + encodeURIComponent(junto)
    };
    Array.prototype.forEach.call(menu.querySelectorAll("[data-canal]"), function (el) {
      var destino = links[el.getAttribute("data-canal")];
      if (destino) el.setAttribute("href", destino);
    });
    var aberto = false;

    function focoEm(i) {
      var lista = itens();
      if (!lista.length) return;
      var alvo = lista[(i + lista.length) % lista.length];
      try { alvo.focus(); } catch (x) { /* sem foco */ }
    }

    /* O rodapé é o fim da página, então o menu abre para cima. Só desce quando
       não há altura em cima (tela baixa); e, se nenhum dos lados couber
       inteiro, escolhe o lado maior e encolhe o menu com rolagem interna —
       nunca deixa o menu sair da tela nem cria rolagem horizontal. */
    function posicionar() {
      var folga = 8, vh = window.innerHeight || document.documentElement.clientHeight || 0;
      var vw = document.documentElement.clientWidth || window.innerWidth || 0;
      menu.classList.remove("pe-menu-baixo");
      menu.style.maxHeight = "";
      // Se o botão estiver colado na direita (rodapé estreito), o menu alinha
      // pela direita; senão, pela esquerda. Em nenhum caso sai da tela.
      menu.style.left = ""; menu.style.right = "";
      var r = menu.getBoundingClientRect();
      if (r.right > vw - folga) { menu.style.left = "auto"; menu.style.right = "0"; }
      var altura = menu.getBoundingClientRect().height;
      var b = botao.getBoundingClientRect();
      var emCima = b.top - folga * 2, embaixo = vh - b.bottom - folga * 2;
      // não cabe em cima e há mais espaço embaixo: abre para baixo
      if (emCima < altura && embaixo > emCima) menu.classList.add("pe-menu-baixo");
      var sobra = menu.classList.contains("pe-menu-baixo") ? embaixo : emCima;
      if (sobra < altura) menu.style.maxHeight = Math.max(0, Math.floor(sobra)) + "px";
    }

    function abrir(primeiro) {
      if (aberto) return;
      aberto = true;
      menu.hidden = false;
      botao.setAttribute("aria-expanded", "true");
      posicionar();
      if (primeiro) focoEm(0);
    }

    function fechar(devolverFoco) {
      if (!aberto) return;
      aberto = false;
      menu.hidden = true;
      botao.setAttribute("aria-expanded", "false");
      if (devolverFoco) { try { botao.focus(); } catch (x) { /* sem foco */ } }
    }

    // --- o clique no botão
    botao.addEventListener("click", function (ev) {
      ev.preventDefault();
      // toque com folha nativa: a folha é a primeira escolha; o menu é a saída
      if (ehToque() && typeof navigator.share === "function") {
        registrar("nativo");
        try {
          var p = navigator.share({ title: titulo, text: titulo, url: url });
          if (p && typeof p.catch === "function") {
            p.catch(function (err) {
              if (err && err.name === "AbortError") return; // o usuário fechou
              registrar("menu");
              abrir(true);
            });
          }
        } catch (x) {
          abrir(true);
        }
        return;
      }
      registrar("menu");
      // clique de ponteiro abre sem tirar o foco do botão; Enter/Espaço (detail
      // 0) já leva o foco ao primeiro item, para as setas terem onde andar.
      if (aberto) fechar(true);
      else abrir(ev.detail === 0);
    });

    /* Setas no botão abrem o menu no primeiro/último item; Tab fecha e segue.
       O menu some no keydown, antes de o navegador escolher o próximo alvo do
       Tab — assim o foco não fica preso num item que acabou de desaparecer. */
    botao.addEventListener("keydown", function (ev) {
      if (ev.key === "Tab" && aberto) { fechar(false); return; }
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        var desce = ev.key === "ArrowDown";
        if (!aberto) abrir(true);
        if (desce) focoEm(0);
        else focoEm(itens().length - 1);
      }
    });

    /* Depois do Tab dentro do menu o foco tem de sair do menu: vai para o
       próximo elemento focável da página que não seja um item que acabou de
       sumir (ou, no Shift+Tab, volta para o botão). */
    function focarFora(paraFrente) {
      var alvo = botao;
      if (paraFrente) {
        var todos = Array.prototype.slice.call(
          document.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'));
        var i = todos.indexOf(botao);
        for (var j = i + 1; j >= 0 && j < todos.length; j++) {
          var el = todos[j];
          if (menu.contains(el)) continue;
          if (el.offsetWidth || el.offsetHeight || el.getClientRects().length) { alvo = el; break; }
        }
      }
      try { alvo.focus(); } catch (x) { /* sem foco */ }
    }

    // --- itens do menu
    menu.addEventListener("click", function (ev) {
      var item = ev.target.closest ? ev.target.closest(".pe-item") : null;
      if (!item) return;
      if (item.getAttribute("data-canal") !== "copiar") {
        // WhatsApp, X, Telegram e e-mail: o link já está no href, abre sozinho
        registrar(item.getAttribute("data-canal"));
        fechar(true);
        return;
      }
      ev.preventDefault();
      var rot = item.querySelector(".pe-item-rot") || item;
      if (!rot.getAttribute("data-original")) rot.setAttribute("data-original", rot.textContent);
      var original = rot.getAttribute("data-original");
      var volta = function () {
        rot.textContent = original;
        item.classList.remove("pe-item-ok");
      };
      copiar(url, function () {
        registrar("copiar");
        rot.textContent = "Copiado ✓";
        item.classList.add("pe-item-ok");
        clearTimeout(relogio);
        relogio = setTimeout(volta, 2000);
      }, function () {
        rot.textContent = "Não deu para copiar";
        clearTimeout(relogio);
        relogio = setTimeout(volta, 2000);
      });
    });

    // --- teclado dentro do menu
    menu.addEventListener("keydown", function (ev) {
      var k = ev.key;
      if (k === "Escape") { ev.preventDefault(); fechar(true); return; }
      if (k === "Tab") { ev.preventDefault(); fechar(false); focarFora(!ev.shiftKey); return; }
      if (k === "ArrowDown" || k === "ArrowUp") {
        ev.preventDefault();
        var lista = itens();
        var i = lista.indexOf(document.activeElement);
        focoEm(k === "ArrowDown" ? i + 1 : i - 1);
        return;
      }
      if (k === "Home") { ev.preventDefault(); focoEm(0); return; }
      if (k === "End") { ev.preventDefault(); focoEm(itens().length - 1); return; }
    });

    // --- o resto da página fecha o menu
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && aberto) { ev.preventDefault(); fechar(true); }
    });
    document.addEventListener("pointerdown", function (ev) {
      if (aberto && !caixa.contains(ev.target)) fechar(false);
    });
    document.addEventListener("focusin", function (ev) {
      if (aberto && !caixa.contains(ev.target)) fechar(false);
    });
    // Gira o celular ou muda o zoom com o menu aberto: reposiciona.
    window.addEventListener("resize", function () { if (aberto) posicionar(); });
  });
})();
