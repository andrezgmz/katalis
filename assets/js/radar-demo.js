/* Demo del Radar (estrategia.html): 8 preguntas, resultado en la misma página.
   No envía ni guarda nada: sin red, sin cookies, sin almacenamiento. Arma el SVG
   con createElementNS y los textos con textContent (nunca innerHTML).
   Las preguntas y los ejes salen del HTML (data-eje, data-corto): no se repiten aquí. */
(function () {
  var preguntas = Array.prototype.slice.call(document.querySelectorAll(".rd-pregunta"));
  var svg = document.getElementById("rd-radar");
  if (!preguntas.length || !svg) return;

  var SVG = "http://www.w3.org/2000/svg";
  var CX = 240, CY = 190, R = 120;
  // Cortes del libro, sobre 40 (suma de los 8 ejes).
  function nivel(total) {
    if (total < 17) return "Inicial";
    if (total < 28) return "En desarrollo";
    if (total < 36) return "Consolidado";
    return "Avanzado";
  }
  var $ = function (id) { return document.getElementById(id); };
  // El botón «Conversemos sobre su resultado» abre la agenda tal cual: el resultado no sale de esta página.

  function nodo(tipo, attrs, padre) {
    var n = document.createElementNS(SVG, tipo);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (padre) padre.appendChild(n);
    return n;
  }
  function punto(i, valor) {
    var a = -Math.PI / 2 + i * 2 * Math.PI / 8, r = R * valor / 5;
    return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
  }
  function poligono(valores) {
    return valores.map(function (v, i) { var p = punto(i, v); return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ");
  }

  // Lo que respondió (null si falta).
  function respuestas() {
    return preguntas.map(function (f) {
      var r = f.querySelector("input:checked");
      return r ? Number(r.value) : null;
    });
  }

  // Resultado puro: se prueba desde pruebas/verificar.mjs con los mismos datos.
  function resultado(vals) {
    var total = vals.reduce(function (a, b) { return a + b; }, 0);
    var min = Math.min.apply(null, vals);
    var techo = vals.every(function (v) { return v === min; })
      ? "ejes parejos, todos en " + min
      : preguntas.filter(function (f, i) { return vals[i] === min; }).map(function (f) { return f.dataset.eje; }).join(", ");
    var bajos = preguntas.filter(function (f, i) { return vals[i] < 2; }).map(function (f) { return f.dataset.eje; });
    return { total: total, nivel: nivel(total), techo: techo, bajos: bajos };
  }

  function dibujar(vals) {
    while (svg.lastChild && svg.lastChild.tagName !== "title") svg.removeChild(svg.lastChild);
    for (var n = 1; n <= 5; n++) nodo("polygon", { points: poligono([n, n, n, n, n, n, n, n]), "class": "rd-anillo" }, svg);
    preguntas.forEach(function (f, i) {
      var p = punto(i, 5), q = punto(i, 5.9);
      nodo("line", { x1: CX, y1: CY, x2: p[0], y2: p[1], "class": "rd-eje" }, svg);
      var t = nodo("text", { x: q[0].toFixed(1), y: (q[1] + 4).toFixed(1),
        "text-anchor": Math.abs(q[0] - CX) < 8 ? "middle" : (q[0] > CX ? "start" : "end"),
        "class": "rd-rotulo-eje" + (vals[i] < 2 ? " rd-bajo" : "") }, svg);
      t.textContent = f.dataset.corto;
    });
    nodo("polygon", { points: poligono(vals), "class": "rd-area" }, svg);
    vals.forEach(function (v, i) {
      var p = punto(i, v);
      nodo("circle", { cx: p[0].toFixed(1), cy: p[1].toFixed(1), r: v < 2 ? 6 : 4.5, "class": v < 2 ? "rd-punto rd-bajo" : "rd-punto" }, svg);
    });
  }

  function actualizar() {
    var vals = respuestas(), faltan = vals.filter(function (v) { return v === null; }).length;
    $("rd-contador").textContent = String(8 - faltan);
    preguntas.forEach(function (f, i) { f.classList.toggle("rd-respondida", vals[i] !== null); });
    $("rd-falta").hidden = faltan === 0;
    $("rd-listo").hidden = faltan > 0;
    if (faltan) return;

    var r = resultado(vals);
    dibujar(vals);
    $("rd-total").textContent = String(r.total);
    $("rd-nivel").textContent = r.nivel;
    $("rd-techo").textContent = r.techo;
    $("rd-riesgo").hidden = r.bajos.length === 0;
    $("rd-bajos").textContent = r.bajos.join(", ");
    svg.setAttribute("aria-label", "Radar: " + r.total + " de 40, " + r.nivel + ". Techo: " + r.techo + ".");
  }

  preguntas.forEach(function (f) { f.addEventListener("change", actualizar); });
  actualizar();
})();
