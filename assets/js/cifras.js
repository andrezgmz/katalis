/* Tablero de cifras. Lee datos/cifras.json (generado desde el Excel por
   scripts/actualizar_cifras.py) y dibuja todo. Aquí no se inventa ni se
   escribe a mano ningún número: si falta un dato, el tablero lo dice. */
(function () {
  "use strict";
  var RUTA = "datos/cifras.json";
  var TIPOS = ["CAC", "Otras cooperativas", "Fondos de empleados", "Mutuales", "Otras entidades"];
  // Paleta del manual de marca (pág. 9): Cobalto, Señal, Coral oscuro, Pulso y Grafito.
  var COLOR = { "CAC": "#2F4FD8", "Otras cooperativas": "#9DB4FF", "Fondos de empleados": "#D9572F", "Mutuales": "#FF8A65", "Otras entidades": "#4A4F63" };
  var NOMBRE_LARGO = { "CAC": "Cooperativas de ahorro y crédito", "Otras cooperativas": "Otras cooperativas", "Fondos de empleados": "Fondos de empleados", "Mutuales": "Mutuales", "Otras entidades": "Otras entidades" };
  // Decreto 769 de 2025, art. 4: rige desde el día siguiente a su publicación
  // (Diario Oficial 53.175 del 8-jul-2025).
  var VIGENCIA_769 = new Date(2025, 6, 9);

  var D, filtro = "Todas", graficos = {}, pendientes = {};

  /* ---------- formato ---------- */
  function num(v, dec) { return Number(v).toLocaleString("es-CO", { minimumFractionDigits: dec || 0, maximumFractionDigits: dec || 0 }); }
  function pesos(milesMillones) {
    return milesMillones >= 1000 ? "$" + num(milesMillones / 1000, 2) + " BB" : "$" + num(milesMillones, 0) + " mil millones";
  }
  function pct(frac, dec) { return num(frac * 100, dec === undefined ? 1 : dec) + " %"; }
  function variacion(a, b) { return b / a - 1; }
  function signo(frac) { return (frac >= 0 ? "+" : "−") + pct(Math.abs(frac)); }
  function corte(c) { var p = c.split("-"); return p[0].toLowerCase() + "-20" + p[1]; }
  function millones(p) { return num(p / 1e6, 2) + " M"; }

  function serie(id) { return D.series[id]; }
  function tabla(id, i) { return serie(id).tablas[i || 0]; }
  function filaDe(t, clave) { for (var i = 0; i < t.filas.length; i++) if (t.filas[i][0] === clave) return t.filas[i]; return null; }
  function fuente(id, el) { var e = document.getElementById(el); if (e) e.textContent = serie(id).fuente.replace(/\.?$/, "."); }
  function txt(id, v) { var e = document.getElementById(id); if (e) e.textContent = v; }
  // Todo se construye con nodos y textContent: sin innerHTML, compatible con la CSP.
  function el(tag, clase, hijos) {
    var e = document.createElement(tag);
    if (clase) e.className = clase;
    [].concat(hijos || []).forEach(function (h) { e.append(h); });
    return e;
  }
  function llenar(id, nodos) { document.getElementById(id).replaceChildren.apply(document.getElementById(id), nodos); }

  function kpi(rotulo, valor, lectura, clase) {
    return el("div", "kpi", [el("div", "rotulo", rotulo), el("div", "valor", valor), el("div", "lectura " + (clase || "neutro"), lectura)]);
  }
  function barras(cont, filas, resaltadas) {
    var max = Math.max.apply(null, filas.map(function (f) { return f.v; }));
    llenar(cont, filas.map(function (f, i) {
      var relleno = el("div", "relleno");
      relleno.style.width = (f.v / max * 100).toFixed(1) + "%";
      if (f.c) relleno.style.background = f.c;
      var on = typeof resaltadas === "function" ? resaltadas(f, i) : f.k === resaltadas;
      return el("div", "barra-h" + (on ? " resalta" : ""), [el("div", "cab", [el("span", "", f.k), el("span", "", f.e)]), el("div", "pista", relleno)]);
    }));
  }

  /* ---------- Chart.js: estilo común ---------- */
  function baseChart() {
    if (!window.Chart) return false;
    Chart.defaults.font.family = "'Plus Jakarta Sans', Arial, sans-serif";
    Chart.defaults.font.size = 13;
    Chart.defaults.color = "#4A4F63";
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.tooltip.backgroundColor = "#161A2E";
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.layout.padding = { top: 10 };
    return true;
  }
  function dibujar(id, config) {
    if (graficos[id]) graficos[id].destroy();
    var c = document.getElementById(id);
    if (!c || !window.Chart) return;
    graficos[id] = new Chart(c, config);
  }
  var EJE = { grid: { color: "#E9E5DC" }, border: { display: false } };
  function apagar(color, activo) { return activo ? color : color + "33"; }

  /* ---------- Panel 1: sector solidario ---------- */
  function sector() {
    var t2 = tabla("T02", 0), t4 = tabla("T04", 0), g4 = tabla("T04", 1), t5 = tabla("T05", 2);
    var tot = t2.filas.reduce(function (a, f) { return [a[0] + f[1], a[1] + f[2], a[2] + f[3]]; }, [0, 0, 0]);
    var anios = t4.filas.map(function (f) { return f[0]; });
    var a22 = t4.filas[0], a25 = t4.filas[t4.filas.length - 1];
    var k;
    if (filtro === "Todas") {
      var pas = t5.filas.reduce(function (a, f) { return a + f[2]; }, 0);
      k = [
        kpi("Entidades que reportaron, dic-2025", num(tot[0]), "Vigiladas por Supersolidaria"),
        kpi("Activos del sector, dic-2025", pesos(tot[1]), "Pesos corrientes"),
        kpi("Asociados, dic-2025", millones(tot[2]), "Personas vinculadas"),
        kpi("Crecimiento de los activos, 2022–2025", signo(variacion(a22[6], a25[6])), "Inflación 2023–2025: " + pct(D.referencias.inflacion_2023_2025.valor), "sube")
      ];
      txt("financia-titulo", "Pasivos frente al activo, por tipo de entidad");
    } else {
      var f = filaDe(t2, filtro), g = filaDe(g4, filtro), infl = D.referencias.inflacion_2023_2025.valor;
      k = [
        kpi("Entidades, dic-2025", num(f[1]), pct(f[4]) + " de las entidades del sector"),
        kpi("Activos, dic-2025", pesos(f[2]), pct(f[5]) + " del activo del sector"),
        kpi("Asociados, dic-2025", f[3] >= 1e6 ? millones(f[3]) : num(f[3]), pct(f[6]) + " de los asociados del sector"),
        kpi("Crecimiento de los activos, 2022–2025", signo(g[3]), (g[3] > infl ? "Por encima" : "Por debajo") + " de la inflación del periodo (" + pct(infl) + ")", g[3] > infl ? "sube" : "baja")
      ];
    }
    llenar("kpi-sector", k);
    txt("sector-nota", filtro === "Todas" ? "Todas las entidades que reportaron a Supersolidaria." : NOMBRE_LARGO[filtro] + ". Las demás barras quedan atenuadas.");

    dibujar("g-activos-anio", {
      type: "bar",
      data: { labels: anios, datasets: TIPOS.map(function (tp, i) {
        return { label: tp, data: t4.filas.map(function (f) { return f[i + 1] / 1000; }), backgroundColor: apagar(COLOR[tp], filtro === "Todas" || filtro === tp), borderRadius: 3, stack: "s" };
      }) },
      options: { plugins: { tooltip: { callbacks: { label: function (c) { return c.dataset.label + ": " + pesos(c.raw * 1000); } } } },
        scales: { x: { stacked: true, grid: { display: false } }, y: Object.assign({ stacked: true, title: { display: true, text: "Billones de pesos" } }, EJE) } }
    });

    barras("b-participacion", t2.filas.map(function (f) { return { k: f[0], v: f[5], e: pct(f[5]) + " del activo · " + pct(f[6]) + " de asociados", c: COLOR[f[0]] }; }), filtro);
    barras("b-financia", t5.filas.map(function (f) { return { k: f[0], v: f[4], e: pct(f[4], 0), c: COLOR[f[0]] }; }), filtro);
  }

  function sectorFijos() {
    fuente("T04", "f-activos-anio"); fuente("T02", "f-participacion"); fuente("T05", "f-financia");
    var t7 = tabla("T07", 0);
    dibujar("g-tamano", {
      type: "bar",
      data: { labels: t7.filas.map(function (f) { return f[0]; }), datasets: [
        { label: "% de cooperativas", data: t7.filas.map(function (f) { return f[4] * 100; }), backgroundColor: "#161A2E", borderRadius: 3 },
        { label: "% del activo", data: t7.filas.map(function (f) { return f[5] * 100; }), backgroundColor: "#9DB4FF", borderRadius: 3 }] },
      options: { indexAxis: "y", plugins: { tooltip: { callbacks: { label: function (c) { return c.dataset.label + ": " + num(c.raw, 1) + " %"; } } } },
        scales: { x: Object.assign({ ticks: { callback: function (v) { return v + " %"; } } }, EJE), y: { grid: { display: false } } } }
    });
    txt("t-tamano", serie("T07").titulo); fuente("T07", "f-tamano");

    var t9 = tabla("T09", 0);
    barras("b-inclusion", t9.filas.map(function (f) { return { k: f[0], v: f[1], e: pct(f[1]), c: f[0] === "Promedio nacional" ? "#161A2E" : null }; }), "Promedio nacional");
    txt("t-inclusion", serie("T09").titulo); fuente("T09", "f-inclusion");
    perfil(1);
    fuente("T10", "f-perfil");
  }

  function perfil(i) {
    var t = tabla("T10", i);
    dibujar("g-perfil", {
      type: "bar",
      data: { labels: t.filas.map(function (f) { return f[0]; }), datasets: [
        { label: "Sector solidario", data: t.filas.map(function (f) { return f[1] * 100; }), backgroundColor: "#A9AEC2", borderRadius: 3 },
        { label: "Cooperativas de ahorro y crédito", data: t.filas.map(function (f) { return f[2] * 100; }), backgroundColor: "#2F4FD8", borderRadius: 3 }] },
      options: { plugins: { tooltip: { callbacks: { label: function (c) { return c.dataset.label + ": " + num(c.raw, 1) + " %"; } } } },
        scales: { y: Object.assign({ ticks: { callback: function (v) { return v + " %"; } } }, EJE), x: { grid: { display: false } } } }
    });
  }

  /* ---------- Panel 2: ahorro y crédito ---------- */
  function cac() {
    var s = tabla("T13", 1), ini = s.filas[0], fin = s.filas[s.filas.length - 1];
    var r = tabla("T14", 0), r25 = r.filas[r.filas.length - 1];
    var meses = fin[1];
    llenar("kpi-cac", [
      kpi("Activos de las CAC, " + corte(fin[0]), pesos(fin[3]), signo(variacion(ini[3], fin[3])) + " en " + meses + " meses", "sube"),
      kpi("Depósitos de los asociados", pesos(fin[2]), signo(variacion(ini[2], fin[2])) + " en " + meses + " meses", "sube"),
      kpi("Cartera de créditos", pesos(fin[4]), signo(variacion(ini[4], fin[4])) + ": crece menos que los depósitos", "baja"),
      kpi("Excedente sobre ingresos, " + r25[0], pct(r25[7]), "Desde " + pct(r.filas[0][7]) + " en " + r.filas[0][0], "sube")
    ]);

    var idx = tabla("T13", 0);
    var estilos = { "Depósitos": ["#2F4FD8", 3], "Cartera": ["#FF8A65", 3], "Activos": ["#161A2E", 1.5], "Patrimonio": ["#A9AEC2", 1.5] };
    dibujar("g-indice", {
      type: "line",
      data: { datasets: ["Depósitos", "Cartera", "Activos", "Patrimonio"].map(function (n) {
        var col = idx.columnas.indexOf(n);
        return { label: n, data: idx.filas.map(function (f) { return { x: f[1], y: f[col], corte: f[0] }; }), borderColor: estilos[n][0], backgroundColor: estilos[n][0], borderWidth: estilos[n][1], pointRadius: 4, tension: 0.25 };
      }) },
      options: { plugins: { tooltip: { callbacks: { title: function (c) { return c[0].raw.corte; }, label: function (c) { return c.dataset.label + ": " + num(c.raw.y, 1); } } } },
        scales: { x: Object.assign({ type: "linear", min: 0, max: 32, ticks: { stepSize: 4, callback: function (v) { return ({ 0: "Dic-23", 12: "Dic-24", 24: "Dic-25", 32: "Ago-26" })[v] || ""; } } }, EJE),
          y: Object.assign({ min: 95, title: { display: true, text: "Índice, dic-2023 = 100" } }, EJE) } }
    });
    txt("t-indice", serie("T13").titulo); fuente("T13", "f-indice");

    var t3 = tabla("T03", 0);
    barras("b-depto", t3.filas.map(function (f) { return { k: f[0] + " (" + f[1] + ")", v: f[3], e: pct(f[3]) }; }), function (f, i) { return i < 3; });
    txt("t-depto", serie("T03").titulo); fuente("T03", "f-depto");

    var t37 = tabla("T37", 0), inflacion = D.referencias.inflacion_2025.valor;
    llenar("tabla-cac", t37.filas.map(function (f) {
      var v = f[3], real = v > inflacion, punto = el("span", "punto");
      punto.style.background = real ? "#1F7A4D" : "#A63A1F";
      return el("tr", "", [el("td", "", f[0]), el("td", "num", pesos(f[1])), el("td", "num", pesos(f[2])), el("td", "num", signo(v)),
        el("td", "", [punto, real ? "Crece en términos reales" : "Por debajo de la inflación"])]);
    }));
    txt("f-tabla-cac", serie("T37").fuente + ". Inflación 2025: " + pct(inflacion, 2) + ".");

    dibujar("g-ingresos", {
      type: "bar",
      data: { labels: r.filas.map(function (f) { return f[0]; }), datasets: [
        { label: "Costos (intereses y otros)", data: r.filas.map(function (f) { return f[5] * 100; }), backgroundColor: "#A9AEC2" },
        { label: "Gastos de operación y deterioro", data: r.filas.map(function (f) { return f[6] * 100; }), backgroundColor: "#D9D4C8" },
        { label: "Excedente", data: r.filas.map(function (f) { return f[7] * 100; }), backgroundColor: "#2F4FD8" }] },
      options: { indexAxis: "y", plugins: { tooltip: { callbacks: { label: function (c) { return c.dataset.label + ": " + num(c.raw, 1) + " %"; } } } },
        scales: { x: Object.assign({ stacked: true, max: 100, ticks: { callback: function (v) { return v + " %"; } } }, EJE), y: { stacked: true, grid: { display: false } } } }
    });
    txt("t-ingresos", serie("T14").titulo); fuente("T14", "f-ingresos");
  }

  /* ---------- Panel 3: pagos digitales y norma ---------- */
  function sumarMeses(f, m) { var d = new Date(f.getTime()); d.setMonth(d.getMonth() + m); return d; }
  function fechaCorta(d) { return d.toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" }); }

  function pagos() {
    var t19 = tabla("T19", 0), cortes = t19.columnas.slice(1);
    var coop = filaDe(t19, "Cooperativas"), total = t19.filas.reduce(function (a, f) { return a + f[f.length - 1]; }, 0);
    var hoy = new Date();
    var plazos = [
      ["Política de transformación digital: categoría plena", "Art. 2.11.14.6", 6],
      ["Política de transformación digital: categoría intermedia", "Art. 2.11.14.6", 9],
      ["Política de transformación digital: categoría básica", "Art. 2.11.14.6", 12],
      ["Servicios transaccionales: plenas e intermedias", "Art. 2.11.14.4", 12],
      ["Canal no presencial: plenas e intermedias", "Art. 2.11.14.5", 15]
    ];
    var vencidos = plazos.filter(function (p) { return sumarMeses(VIGENCIA_769, p[2]) <= hoy; }).length;
    llenar("kpi-pagos", [
      kpi("Cooperativas conectadas a Bre-B, " + cortes[cortes.length - 1].replace(" (entidades)", ""), num(coop[coop.length - 1]), pct(coop[coop.length - 1] / total, 0) + " de las " + total + " entidades conectadas", "sube"),
      kpi("Cooperativas que se conectaron en un año", "+" + num(coop[coop.length - 1] - coop[1]), "Desde " + coop[1] + " en el primer corte"),
      kpi("Plazos del Decreto 769 de 2025 ya vencidos", vencidos + " de " + plazos.length, "Contados desde la vigencia: " + fechaCorta(VIGENCIA_769), vencidos ? "baja" : "neutro"),
      kpi("Finanzas abiertas para las CAC", "Voluntarias", "El Decreto 368 de 2026 obliga solo a vigiladas por la SFC")
    ]);

    dibujar("g-breb", {
      type: "bar",
      data: { labels: t19.filas.map(function (f) { return f[0]; }), datasets: cortes.map(function (c, i) {
        var tonos = [["#C9D4FF", "#D7DBE0"], ["#8FA3F0", "#B8C0C8"], ["#2F4FD8", "#8A939E"]][i];
        return { label: c.replace(" (entidades)", ""), data: t19.filas.map(function (f) { return f[i + 1]; }), backgroundColor: t19.filas.map(function (f) { return f[0] === "Cooperativas" ? tonos[0] : tonos[1]; }), borderRadius: 3 };
      }) },
      options: { plugins: { legend: { display: true } }, scales: { y: Object.assign({ title: { display: true, text: "Entidades conectadas" } }, EJE), x: { grid: { display: false } } } }
    });
    txt("t-breb", serie("T19").titulo); fuente("T19", "f-breb");

    llenar("lista-769", plazos.map(function (p) {
      var f = sumarMeses(VIGENCIA_769, p[2]), dias = Math.floor((hoy - f) / 864e5), venc = hoy >= f;
      return el("li", "", [el("span", "fecha", fechaCorta(f)),
        el("span", "", [el("b", "", p[0]), el("br"), el("small", "neutro", p[1] + " · " + p[2] + " meses desde la vigencia")]),
        el("span", "estado " + (venc ? "estado-vencido" : "estado-vigente"), venc ? "Venció hace " + num(dias) + " días" : "Faltan " + num(-dias) + " días")]);
    }));
  }

  /* ---------- pestañas y filtros ---------- */
  function pestanas() {
    var botones = document.querySelectorAll(".pestanas [role=tab]");
    botones.forEach(function (b) {
      b.addEventListener("click", function () {
        botones.forEach(function (o) { o.setAttribute("aria-selected", o === b ? "true" : "false"); document.getElementById(o.getAttribute("aria-controls")).hidden = o !== b; });
        document.getElementById("filtro-tipo").hidden = b.id !== "tab-sector";
        // Chart.js mide el contenedor al dibujar: cada panel se dibuja la primera vez que se ve.
        if (pendientes[b.id]) { pendientes[b.id](); delete pendientes[b.id]; }
      });
    });
    var ini = document.getElementById({ "#cac": "tab-cac", "#pagos": "tab-pagos" }[location.hash] || "tab-sector");
    if (ini) ini.click();
    document.querySelectorAll("#filtro-tipo button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#filtro-tipo button").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
        filtro = b.dataset.tipo; sector();
      });
    });
    document.querySelectorAll("#perfil-opciones button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#perfil-opciones button").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
        perfil(Number(b.dataset.tabla));
      });
    });
  }

  function error(msg) {
    var e = document.getElementById("estado"); e.textContent = msg; e.hidden = false;
  }

  fetch(RUTA, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (datos) {
    D = datos;
    if (!baseChart()) error("No se pudo cargar la librería de gráficos. Las cifras siguen en las tablas.");
    pendientes = { "tab-sector": function () { sector(); sectorFijos(); }, "tab-cac": cac, "tab-pagos": pagos };
    pestanas();
    txt("generado", "Datos convertidos el " + new Date(D.generado + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" }) + ".");
  }).catch(function () { error("No se pudieron cargar las cifras. Recargue la página; si sigue fallando, escríbanos."); });
})();
