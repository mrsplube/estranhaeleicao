/* data.js — o calendário do site.

O <input type="date"> pinta a data no idioma do NAVEGADOR, não no lang da
página. Um Chrome em inglês mostra mm/dd/yyyy mesmo com <html lang="pt-br">,
que foi o 10/13/2026 do /tarefas. Este arquivo troca a cara de todo
type=date, datetime-local e time por dd/mm/aaaa e hh:mm (24 h). O input
original fica no formulário: o JavaScript de cada tela continua lendo e
escrevendo .value em AAAA-MM-DD, e é isso que o POST envia.

Não escreva outro calendário. Um campo novo é só <input type="date">.
Quem precisa do seletor do navegador marca data-nativo no input.

A semana começa no domingo, como o calendário civil brasileiro.
*/
(function (factory) {
    var api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    if (typeof document !== "undefined") {
        var partir = function () { api.ligar(document); };
        if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", partir);
        else partir();
    }
})(function () {
    "use strict";

    var MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
    var SEMANA = [
        ["D", "Domingo"], ["S", "Segunda"], ["T", "Terça"], ["Q", "Quarta"],
        ["Q", "Quinta"], ["S", "Sexta"], ["S", "Sábado"],
    ];
    var SELETOR = [
        'input[type="date"]:not(.data-iso):not([data-nativo])',
        'input[type="datetime-local"]:not(.data-iso):not([data-nativo])',
        'input[type="time"]:not(.data-iso):not([data-nativo])',
    ].join(",");
    var ICONE = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">'
        + '<path fill="currentColor" d="M7 11h2v2H7v-2zm4 0h2v2h-2v-2zm4 0h2v2h-2v-2z'
        + 'M5 4h2V2h2v2h6V2h2v2h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6'
        + 'a2 2 0 0 1 2-2zm0 6v10h14V10H5z"/></svg>';

    var meta = new WeakMap();
    var popups = new WeakMap();

    function pad(n) { return (n < 10 ? "0" : "") + n; }

    function modoDe(input) {
        if (input.type === "time") return "time";
        if (input.type === "datetime-local") return "datetime";
        return "date";
    }

    function dataValida(ano, mes, dia) {
        if (mes < 1 || mes > 12 || dia < 1 || ano < 1000 || ano > 9999) return false;
        var dt = new Date(ano, mes - 1, dia);
        return dt.getFullYear() === ano && dt.getMonth() === mes - 1 && dt.getDate() === dia;
    }

    function horaValida(h, mi) {
        return h >= 0 && h <= 23 && mi >= 0 && mi <= 59;
    }

    function dataParaIso(dt) {
        return dt.getFullYear() + "-" + pad(dt.getMonth() + 1) + "-" + pad(dt.getDate());
    }

    function hojeIso() { return dataParaIso(new Date()); }

    function isoParaData(iso) {
        var p = iso.split("-");
        return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
    }

    /* "" vazio, null inválida, undefined incompleta, string = ISO aceito. */
    function ler(texto, modo) {
        var t = String(texto || "").trim();
        if (!t) return { estado: "vazio", iso: "" };
        if (modo === "time") {
            var hm = t.match(/^(\d{1,2})(?::(\d{2}))?$/);
            if (!hm) return { estado: "invalido" };
            if (hm[2] == null) return { estado: "incompleto" };
            var h = Number(hm[1]), mi = Number(hm[2]);
            if (!horaValida(h, mi)) return { estado: "invalido" };
            return { estado: "ok", iso: pad(h) + ":" + pad(mi) };
        }
        var m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:[ T](\d{1,2}):(\d{2}))?$/);
        if (!m) {
            var so = t.replace(/\D/g, "");
            var precisa = modo === "datetime" ? 12 : 8;
            if (so.length < precisa && /^[\d/ :]*$/.test(t)) return { estado: "incompleto" };
            if (so.length === precisa && modo === "date") {
                m = [null, so.slice(0, 2), so.slice(2, 4), so.slice(4, 8)];
            } else if (so.length === precisa && modo === "datetime") {
                m = [null, so.slice(0, 2), so.slice(2, 4), so.slice(4, 8), so.slice(8, 10), so.slice(10, 12)];
            } else return { estado: "invalido" };
        }
        var dia = Number(m[1]), mes = Number(m[2]), ano = Number(m[3]);
        if (!dataValida(ano, mes, dia)) return { estado: "invalido" };
        var iso = ano + "-" + pad(mes) + "-" + pad(dia);
        if (modo === "datetime") {
            if (m[4] == null) return { estado: "incompleto" };
            var hh = Number(m[4]), mm = Number(m[5]);
            if (!horaValida(hh, mm)) return { estado: "invalido" };
            iso += "T" + pad(hh) + ":" + pad(mm);
        }
        return { estado: "ok", iso: iso };
    }

    function textoDe(iso, modo) {
        if (!iso) return "";
        if (modo === "time") {
            var hm = String(iso).match(/^(\d{2}):(\d{2})/);
            return hm ? hm[1] + ":" + hm[2] : "";
        }
        var m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
        if (!m) return "";
        var data = m[3] + "/" + m[2] + "/" + m[1];
        if (modo !== "datetime") return data;
        return m[4] ? data + " " + m[4] + ":" + m[5] : data;
    }

    function mascara(digs, modo) {
        var d = String(digs || "").replace(/\D/g, "");
        if (modo === "time") {
            d = d.slice(0, 4);
            return d.length <= 2 ? d : d.slice(0, 2) + ":" + d.slice(2);
        }
        d = d.slice(0, modo === "datetime" ? 12 : 8);
        var s = d.slice(0, 2);
        if (d.length > 2) s += "/" + d.slice(2, 4);
        if (d.length > 4) s += "/" + d.slice(4, 8);
        if (modo === "datetime" && d.length > 8) {
            s += " " + d.slice(8, 10);
            if (d.length > 10) s += ":" + d.slice(10, 12);
        }
        return s;
    }

    /* true quando a pessoa (ou a máscara) já pôs as barras no lugar.
       "1/2/2026" fica como está; "13102" vira "13/10/2". */
    function jaFormatado(cru, modo) {
        if (modo === "time") return /^(\d{1,2})(:\d{0,2})?$/.test(cru);
        if (modo === "datetime") {
            return /^(\d{1,2})(\/\d{0,2})?(\/\d{0,4})?( \d{0,2})?(:\d{0,2})?$/.test(cru);
        }
        return /^(\d{1,2})(\/\d{0,2})?(\/\d{0,4})?$/.test(cru);
    }

    function posicao(fmt, nDigs) {
        if (nDigs <= 0) return 0;
        var n = 0;
        for (var i = 0; i < fmt.length; i++) {
            if (fmt.charAt(i) >= "0" && fmt.charAt(i) <= "9") n++;
            if (n >= nDigs) return i + 1;
        }
        return fmt.length;
    }

    function cmpIso(a, b) {
        var x = a.length === b.length ? a : a.slice(0, 10);
        var y = a.length === b.length ? b : b.slice(0, 10);
        if (x < y) return -1;
        if (x > y) return 1;
        return 0;
    }

    function limite(input, qual) {
        var attr = input.getAttribute && input.getAttribute(qual);
        if (attr) return attr;
        var prop = input[qual];
        return prop ? String(prop) : "";
    }

    function dentro(iso, min, max) {
        if (!iso) return true;
        if (min && cmpIso(iso, min) < 0) return false;
        if (max && cmpIso(iso, max) > 0) return false;
        return true;
    }

    /* step do <input type="time"> é em segundos. 300 = de 5 em 5 minutos. */
    function encaixarPasso(hhmm, step) {
        var s = Number(step);
        if (!s || s < 60) return hhmm;
        var passo = s / 60;
        var total = Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
        var arred = Math.round(total / passo) * passo;
        if (arred >= 24 * 60) arred = 0;
        if (arred < 0) arred = 0;
        return pad(Math.floor(arred / 60)) + ":" + pad(arred % 60);
    }

    function grade(ano, mes) {
        var primeiro = new Date(ano, mes - 1, 1);
        var cursor = new Date(ano, mes - 1, 1 - primeiro.getDay());
        var cels = [];
        var i, dt;
        for (i = 0; i < 42; i++) {
            dt = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + i);
            cels.push({
                iso: dataParaIso(dt),
                dia: dt.getDate(),
                fora: dt.getMonth() !== mes - 1,
            });
        }
        while (cels.length >= 14) {
            var semana = cels.slice(cels.length - 7);
            var alguma = false;
            for (i = 0; i < semana.length; i++) if (!semana[i].fora) alguma = true;
            if (alguma) break;
            cels.length -= 7;
        }
        return cels;
    }

    function nomeDia(iso) {
        var p = iso.split("-");
        return Number(p[2]) + " de " + MESES[Number(p[1]) - 1] + " de " + p[0];
    }

    function evento(doc, nome) {
        var Visao = doc.defaultView || (typeof window !== "undefined" ? window : null);
        var Ev = (Visao && Visao.Event) || Event;
        return new Ev(nome, { bubbles: true });
    }

    function mensagem(modo) {
        if (modo === "time") return "Hora inválida. Use hh:mm.";
        if (modo === "datetime") return "Data inválida. Use dd/mm/aaaa hh:mm.";
        return "Data inválida. Use dd/mm/aaaa.";
    }

    function validade(input, texto) {
        if (typeof input.setCustomValidity === "function") input.setCustomValidity(texto);
    }

    function mostrarErro(m, texto) {
        validade(m.input, texto);
        m.texto.setAttribute("aria-invalid", "true");
        m.msg.hidden = false;
        m.msg.textContent = texto;
    }

    function limparErro(m) {
        validade(m.input, "");
        m.texto.removeAttribute("aria-invalid");
        m.msg.hidden = true;
        m.msg.textContent = "";
    }

    function desenhar(input) {
        var m = meta.get(input);
        if (!m) return;
        var txt = textoDe(input.value, m.modo);
        m.texto.dataset.sujo = "";
        if (m.texto.value !== txt) m.texto.value = txt;
    }

    function gravar(input, iso, disparar) {
        var m = meta.get(input);
        if (input.value !== iso) {
            input.value = iso;
            if (disparar) {
                input.dispatchEvent(evento(input.ownerDocument, "input"));
                input.dispatchEvent(evento(input.ownerDocument, "change"));
            }
        } else {
            desenhar(input);
        }
        if (m) limparErro(m);
        var st = popups.get(input.ownerDocument);
        if (st && st.alvo === input && !st.pop.hidden && iso && iso.charAt(4) === "-") {
            st.foco = iso.slice(0, 10);
            st.ano = Number(iso.slice(0, 4));
            st.mes = Number(iso.slice(5, 7));
            desenharPopup(st, false);
        }
    }

    function avaliar(m, aoSair) {
        var lido = ler(m.texto.value, m.modo);
        if (lido.estado === "vazio") {
            gravar(m.input, "", true);
            return true;
        }
        if (lido.estado === "ok") {
            var iso = m.modo === "time" ? encaixarPasso(lido.iso, m.input.getAttribute("step")) : lido.iso;
            if (!dentro(iso, limite(m.input, "min"), limite(m.input, "max"))) {
                if (aoSair) mostrarErro(m, "Fora do intervalo permitido.");
                return false;
            }
            gravar(m.input, iso, true);
            return true;
        }
        if (aoSair) mostrarErro(m, mensagem(m.modo));
        else limparErro(m);
        return false;
    }

    function acharDesc(input, nome) {
        var p = Object.getPrototypeOf(input);
        while (p) {
            var d = Object.getOwnPropertyDescriptor(p, nome);
            if (d) return d;
            p = Object.getPrototypeOf(p);
        }
        return null;
    }

    /* O descritor é lido no input de verdade, não no carregamento do arquivo:
       no teste (node) o HTMLInputElement só existe depois do linkedom. */
    function gancharValor(input) {
        var descValor = acharDesc(input, "value");
        if (descValor && descValor.set && descValor.get) {
            try {
                Object.defineProperty(input, "value", {
                    configurable: true,
                    enumerable: true,
                    get: function () { return descValor.get.call(this); },
                    set: function (v) {
                        descValor.set.call(this, v == null ? "" : String(v));
                        desenhar(this);
                    },
                });
            } catch (e) { /* algum navegador não deixa redefinir; o blur ainda acerta */ }
        }
        var descData = acharDesc(input, "valueAsDate");
        if (!descData || !descData.set || !descData.get) return;
        try {
            Object.defineProperty(input, "valueAsDate", {
                configurable: true,
                enumerable: true,
                get: function () { return descData.get.call(this); },
                set: function (v) {
                    descData.set.call(this, v);
                    desenhar(this);
                },
            });
        } catch (e2) { /* idem */ }
    }

    function rotuloDe(input) {
        var direto = input.getAttribute("aria-label");
        if (direto) return direto.trim();
        var label = input.closest("label");
        if (!label) return "";
        var t = "";
        for (var i = 0; i < label.childNodes.length; i++) {
            if (label.childNodes[i].nodeType === 3) t += label.childNodes[i].textContent;
        }
        return t.replace(/\s+/g, " ").trim();
    }

    function apontarLegenda(input, texto) {
        if (!input.id || input.closest("label")) return;
        var id = input.id.replace(/"/g, "");
        var leg = input.ownerDocument.querySelector('label[for="' + id + '"]');
        if (!leg) return;
        texto.id = id + "-texto";
        leg.setAttribute("for", texto.id);
    }

    function sincronizar(input) {
        var m = meta.get(input);
        if (!m) return;
        m.texto.disabled = !!input.disabled;
        m.texto.readOnly = !!input.readOnly;
        if (m.botao) m.botao.disabled = !!(input.disabled || input.readOnly);
    }

    function vigiarForm(input) {
        var form = input.form;
        if (!form || form.dataset.dataForms) return;
        form.dataset.dataForms = "1";
        form.addEventListener("reset", function () {
            setTimeout(function () {
                form.querySelectorAll("input.data-iso").forEach(desenhar);
            }, 0);
        });
    }

    function popupDe(doc) {
        var ja = popups.get(doc);
        if (ja) return ja;
        var pop = doc.createElement("div");
        pop.className = "data-pop";
        pop.setAttribute("role", "dialog");
        pop.setAttribute("aria-label", "Calendário");
        pop.hidden = true;

        var topo = doc.createElement("div");
        topo.className = "data-pop-topo";
        function nav(texto, delta, oQue) {
            var b = doc.createElement("button");
            b.type = "button";
            b.className = "data-pop-nav";
            b.textContent = texto;
            b.setAttribute("data-delta", String(delta));
            b.setAttribute("aria-label", oQue);
            return b;
        }
        topo.appendChild(nav("«", -12, "Ano anterior"));
        topo.appendChild(nav("‹", -1, "Mês anterior"));
        var titulo = doc.createElement("div");
        titulo.className = "data-pop-titulo";
        topo.appendChild(titulo);
        topo.appendChild(nav("›", 1, "Próximo mês"));
        topo.appendChild(nav("»", 12, "Próximo ano"));

        var sem = doc.createElement("div");
        sem.className = "data-sem";
        sem.setAttribute("aria-hidden", "true");
        SEMANA.forEach(function (par) {
            var s = doc.createElement("span");
            s.textContent = par[0];
            s.title = par[1];
            sem.appendChild(s);
        });

        var dias = doc.createElement("div");
        dias.className = "data-dias";
        dias.setAttribute("role", "grid");

        var pe = doc.createElement("div");
        pe.className = "data-pop-pe";
        function acao(rotulo, nome) {
            var b = doc.createElement("button");
            b.type = "button";
            b.textContent = rotulo;
            b.setAttribute("data-acao", nome);
            return b;
        }
        var hoje = acao("Hoje", "hoje");
        var limpar = acao("Limpar", "limpar");
        var hora = doc.createElement("input");
        hora.type = "text";
        hora.className = "data-pop-hora";
        hora.inputMode = "numeric";
        hora.placeholder = "hh:mm";
        hora.setAttribute("aria-label", "Hora");
        hora.autocomplete = "off";
        pe.appendChild(hoje);
        pe.appendChild(limpar);
        pe.appendChild(hora);

        pop.appendChild(topo);
        pop.appendChild(sem);
        pop.appendChild(dias);
        pop.appendChild(pe);
        (doc.body || doc.documentElement).appendChild(pop);

        var st = {
            pop: pop, titulo: titulo, dias: dias, hoje: hoje, limpar: limpar,
            hora: hora, alvo: null, ano: 2026, mes: 1, foco: "", doc: doc,
        };
        popups.set(doc, st);
        ligarPopup(st);
        return st;
    }

    function ligarPopup(st) {
        var pop = st.pop;
        pop.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
        pop.addEventListener("click", function (ev) {
            var el = ev.target && ev.target.nodeType === 1 ? ev.target : ev.target && ev.target.parentNode;
            var b = el && el.closest ? el.closest("button") : null;
            if (!b || !pop.contains(b)) return;
            if (b.hasAttribute("data-delta")) {
                moverMes(st, Number(b.getAttribute("data-delta")));
                return;
            }
            var acao = b.getAttribute("data-acao");
            if (acao === "hoje") escolher(st, hojeIso());
            else if (acao === "limpar") escolher(st, "");
            else if (b.classList.contains("data-dia") && !b.disabled) escolher(st, b.getAttribute("data-iso"));
        });
        pop.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape") {
                ev.preventDefault();
                var alvo = st.alvo;
                fechar(st);
                var m = alvo && meta.get(alvo);
                if (m) m.texto.focus();
                return;
            }
            if (!ev.target.classList || !ev.target.classList.contains("data-dia")) return;
            var delta = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[ev.key];
            if (!delta || !st.foco) return;
            ev.preventDefault();
            var dt = isoParaData(st.foco);
            dt.setDate(dt.getDate() + delta);
            st.foco = dataParaIso(dt);
            st.ano = dt.getFullYear();
            st.mes = dt.getMonth() + 1;
            desenharPopup(st, true);
        });
        st.hora.addEventListener("input", function () {
            var cru = st.hora.value;
            if (!jaFormatado(cru, "time")) st.hora.value = mascara(cru, "time");
            var lido = ler(st.hora.value, "time");
            if (lido.estado !== "ok" || !st.alvo) return;
            var data = (st.alvo.value || "").slice(0, 10);
            if (!/^\d{4}-\d{2}-\d{2}$/.test(data)) return;
            gravar(st.alvo, data + "T" + lido.iso, true);
        });
        st.hora.addEventListener("mousedown", function (ev) { ev.stopPropagation(); });
    }

    function moverMes(st, delta) {
        var dt = new Date(st.ano, st.mes - 1 + delta, 1);
        st.ano = dt.getFullYear();
        st.mes = dt.getMonth() + 1;
        desenharPopup(st, false);
    }

    function horaDo(input) {
        var m = String(input.value || "").match(/T(\d{2}):(\d{2})/);
        return m ? m[1] + ":" + m[2] : "";
    }

    function desenharPopup(st, focar) {
        var input = st.alvo;
        if (!input) return;
        st.titulo.textContent = MESES[st.mes - 1] + " de " + st.ano;
        var marcado = (input.value || "").slice(0, 10);
        var hoje = hojeIso();
        var min = limite(input, "min");
        var max = limite(input, "max");
        st.dias.textContent = "";
        grade(st.ano, st.mes).forEach(function (cel) {
            var b = st.doc.createElement("button");
            b.type = "button";
            b.className = "data-dia";
            if (cel.fora) b.classList.add("data-fora");
            if (cel.iso === hoje) b.classList.add("data-hoje");
            b.textContent = String(cel.dia);
            b.setAttribute("data-iso", cel.iso);
            b.setAttribute("aria-label", nomeDia(cel.iso));
            var off = !dentro(cel.iso, min, max);
            b.disabled = off;
            if (cel.iso === marcado) b.setAttribute("aria-pressed", "true");
            b.tabIndex = cel.iso === st.foco ? 0 : -1;
            st.dias.appendChild(b);
        });
        var modo = meta.get(input).modo;
        st.hora.hidden = modo !== "datetime";
        st.hora.value = horaDo(input);
        st.hoje.disabled = !dentro(hoje, min, max);
        if (focar) {
            var btn = st.dias.querySelector('[data-iso="' + st.foco + '"]');
            if (btn) btn.focus();
        }
    }

    function posicionar(st) {
        var m = st.alvo && meta.get(st.alvo);
        var win = st.doc.defaultView;
        if (!m || !win) return;
        var r = m.campo.getBoundingClientRect();
        var pop = st.pop;
        pop.style.top = (r.bottom + 6) + "px";
        pop.style.left = Math.max(8, r.left) + "px";
        pop.hidden = false;
        var pw = pop.offsetWidth || 280;
        var ph = pop.offsetHeight || 320;
        var top = r.bottom + 6;
        if (top + ph > win.innerHeight - 8) top = Math.max(8, r.top - ph - 6);
        var left = r.left;
        if (left + pw > win.innerWidth - 8) left = Math.max(8, win.innerWidth - pw - 8);
        pop.style.top = top + "px";
        pop.style.left = left + "px";
    }

    function abrir(input) {
        var m = meta.get(input);
        if (!m || input.disabled || input.readOnly || m.modo === "time") return;
        var doc = input.ownerDocument;
        var st = popupDe(doc);
        st.alvo = input;
        var iso = (input.value || "").slice(0, 10);
        var base = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso : hojeIso();
        st.ano = Number(base.slice(0, 4));
        st.mes = Number(base.slice(5, 7));
        st.foco = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso : (dentro(hojeIso(), limite(input, "min"), limite(input, "max")) ? hojeIso() : base);
        desenharPopup(st, false);
        posicionar(st);
        if (m.botao) m.botao.setAttribute("aria-expanded", "true");
        var btn = st.dias.querySelector('[data-iso="' + st.foco + '"]');
        if (btn) btn.focus();
    }

    function fechar(st) {
        if (!st || st.pop.hidden) return;
        var alvo = st.alvo;
        st.pop.hidden = true;
        st.alvo = null;
        var m = alvo && meta.get(alvo);
        if (m && m.botao) m.botao.setAttribute("aria-expanded", "false");
    }

    function escolher(st, iso) {
        var input = st.alvo;
        if (!input) return;
        var m = meta.get(input);
        if (!iso) gravar(input, "", true);
        else if (m.modo === "datetime") gravar(input, iso + "T" + (horaDo(input) || "00:00"), true);
        else gravar(input, iso, true);
        fechar(st);
        m.texto.focus();
    }

    function reposicionar(doc) {
        var st = popups.get(doc);
        if (st && !st.pop.hidden) posicionar(st);
    }

    function aoDigitar(m) {
        var texto = m.texto;
        var cru = texto.value;
        var ini = texto.selectionStart || 0;
        var digsAntes = cru.slice(0, ini).replace(/\D/g, "").length;
        if (cru && !jaFormatado(cru, m.modo)) {
            var fmt = mascara(cru, m.modo);
            if (fmt !== cru) {
                texto.value = fmt;
                var p = posicao(fmt, digsAntes);
                if (texto.setSelectionRange) {
                    try { texto.setSelectionRange(p, p); } catch (e) { /* sem foco */ }
                }
            }
        }
        texto.dataset.sujo = "1";
        var lido = ler(texto.value, m.modo);
        if (lido.estado === "vazio") {
            gravar(m.input, "", true);
            return;
        }
        if (lido.estado === "ok") {
            /* O passo (de 5 em 5 minutos, por exemplo) só encaixa ao sair do
               campo. Encaixar aqui engolia o 14:33 no meio da digitação. */
            if (dentro(lido.iso, limite(m.input, "min"), limite(m.input, "max"))) gravar(m.input, lido.iso, true);
            else mostrarErro(m, "Fora do intervalo permitido.");
            return;
        }
        limparErro(m);
    }

    function ligarUm(input) {
        if (!input || !input.parentNode || input.classList.contains("data-iso")) return;
        if (input.closest && input.closest("template")) return;
        var doc = input.ownerDocument;
        var modo = modoDe(input);
        var campo = doc.createElement("span");
        campo.className = "data-campo";
        var linha = doc.createElement("span");
        linha.className = "data-linha" + (modo === "time" ? "" : " data-com-cal");
        var texto = doc.createElement("input");
        texto.type = "text";
        texto.className = ((input.className || "") + " data-texto").trim();
        texto.autocomplete = "off";
        texto.spellcheck = false;
        texto.inputMode = "numeric";
        texto.placeholder = modo === "time" ? "hh:mm" : modo === "datetime" ? "dd/mm/aaaa hh:mm" : "dd/mm/aaaa";
        texto.dataset.modo = modo;
        texto.size = modo === "time" ? 5 : modo === "datetime" ? 16 : 10;
        var rot = rotuloDe(input);
        if (input.getAttribute("aria-label")) texto.setAttribute("aria-label", input.getAttribute("aria-label"));
        var botao = null;
        if (modo !== "time") {
            botao = doc.createElement("button");
            botao.type = "button";
            botao.className = "data-abre";
            botao.innerHTML = ICONE;
            botao.setAttribute("aria-label", rot ? "Abrir calendário, " + rot : "Abrir calendário");
            botao.setAttribute("aria-haspopup", "dialog");
            botao.setAttribute("aria-expanded", "false");
        }
        var msg = doc.createElement("span");
        msg.className = "data-msg";
        msg.hidden = true;

        var m = { input: input, texto: texto, botao: botao, msg: msg, campo: campo, modo: modo };
        meta.set(input, m);
        input.classList.add("data-iso");
        input.tabIndex = -1;
        input.setAttribute("aria-hidden", "true");
        apontarLegenda(input, texto);

        input.parentNode.insertBefore(campo, input);
        campo.appendChild(linha);
        linha.appendChild(texto);
        if (botao) linha.appendChild(botao);
        linha.appendChild(input);
        campo.appendChild(msg);

        gancharValor(input);
        desenhar(input);
        sincronizar(input);
        vigiarForm(input);

        texto.addEventListener("input", function () { aoDigitar(m); });
        texto.addEventListener("blur", function (ev) {
            /* O clique no ícone segura o foco (mousedown cancela a troca).
               Tab até o ícone tem de validar — senão 31/02 passa batido. */
            var vai = ev.relatedTarget;
            var st = popups.get(doc);
            if (st && vai && st.pop.contains(vai)) return;
            avaliar(m, true);
        });
        texto.addEventListener("keydown", function (ev) {
            if (ev.key === "ArrowDown" || (ev.altKey && ev.key === "ArrowDown")) {
                ev.preventDefault();
                abrir(input);
                return;
            }
            if (ev.key === "Enter") avaliar(m, true);
            if (ev.key !== "Backspace" || texto.selectionStart !== texto.selectionEnd) return;
            var i = texto.selectionStart;
            var ch = texto.value.charAt(i - 1);
            if (ch !== "/" && ch !== ":" && ch !== " ") return;
            ev.preventDefault();
            var antes = texto.value.slice(0, i - 1).replace(/\D/g, "").slice(0, -1);
            var resto = texto.value.slice(i).replace(/\D/g, "");
            var fmt = mascara(antes + resto, modo);
            texto.value = fmt;
            var p = posicao(fmt, antes.length);
            if (texto.setSelectionRange) {
                try { texto.setSelectionRange(p, p); } catch (e) { /* sem foco */ }
            }
            aoDigitar(m);
        });
        if (botao) {
            botao.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
            botao.addEventListener("click", function () {
                var st = popups.get(doc);
                if (st && !st.pop.hidden && st.alvo === input) {
                    fechar(st);
                    texto.focus();
                } else abrir(input);
            });
        }
        input.addEventListener("focus", function () {
            if (!texto.disabled) texto.focus();
        });
        input.addEventListener("invalid", function (ev) {
            ev.preventDefault();
            var falta = input.validity && input.validity.valueMissing;
            mostrarErro(m, falta ? (modo === "time" ? "Informe a hora." : "Informe a data.") : (input.validationMessage || mensagem(modo)));
            texto.focus();
        });
        if (typeof input.showPicker === "function") {
            try { input.showPicker = function () { abrir(input); }; } catch (e) { /* só leitura */ }
        }
    }

    function ligar(doc) {
        if (!doc || !doc.querySelectorAll) return;
        var raiz = doc.body || doc;
        raiz.querySelectorAll(SELETOR).forEach(ligarUm);
        var el = doc.documentElement;
        if (!el || el.dataset.dataObs) return;
        el.dataset.dataObs = "1";
        var obs = new MutationObserver(function (recs) {
            recs.forEach(function (r) {
                if (r.type === "childList") {
                    r.addedNodes.forEach(function (n) {
                        if (!n || n.nodeType !== 1) return;
                        if (n.matches && n.matches(SELETOR)) ligarUm(n);
                        if (n.querySelectorAll) n.querySelectorAll(SELETOR).forEach(ligarUm);
                    });
                } else if (r.target && r.target.classList && r.target.classList.contains("data-iso")) {
                    sincronizar(r.target);
                }
            });
        });
        obs.observe(el, {
            childList: true, subtree: true, attributes: true,
            attributeFilter: ["disabled", "readonly"],
        });
        doc.addEventListener("mousedown", function (ev) {
            var st = popups.get(doc);
            if (!st || st.pop.hidden) return;
            if (st.pop.contains(ev.target)) return;
            var m = st.alvo && meta.get(st.alvo);
            if (m && m.campo.contains(ev.target)) return;
            fechar(st);
        });
        var win = doc.defaultView;
        if (win) {
            win.addEventListener("resize", function () { reposicionar(doc); });
            win.addEventListener("scroll", function () { reposicionar(doc); }, true);
        }
    }

    return {
        ler: ler,
        textoDe: textoDe,
        mascara: mascara,
        jaFormatado: jaFormatado,
        grade: grade,
        dentro: dentro,
        encaixarPasso: encaixarPasso,
        nomeDia: nomeDia,
        ligar: ligar,
        posicao: posicao,
    };
});
