/* Botão "Compartilhar o site" do rodapé (templates/site_rodape.html).
 * No celular abre a folha de compartilhar do sistema; no computador, copia o link. */
(function () {
  "use strict";
  var URL = "https://estranhaeleicao.org", TXT = "Teorias sobre fraude na eleição de 2026, conferidas no dado do TSE";
  document.querySelectorAll(".pe-compartilhar").forEach(function (b) {
    var rot = b.textContent;
    b.addEventListener("click", function () {
      try { navigator.sendBeacon("/v", new Blob([JSON.stringify({ e: "compartilhar", a: location.pathname })], { type: "application/json" })); } catch (x) { /* sem beacon */ }
      if (navigator.share) { navigator.share({ title: "estranhaeleicao.org", text: TXT, url: URL }).catch(function () {}); return; }
      var feito = function () { b.textContent = "Link copiado ✓"; setTimeout(function () { b.textContent = rot; }, 2200); };
      if (navigator.clipboard) navigator.clipboard.writeText(URL).then(feito, function () { prompt("Copie o link:", URL); });
      else prompt("Copie o link:", URL);
    });
  });
})();
