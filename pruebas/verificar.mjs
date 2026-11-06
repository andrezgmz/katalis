// Verificación antes de publicar. Uso: node pruebas/verificar.mjs
// Sirve el sitio en local, abre cada página en escritorio y celular y falla si
// hay errores de consola, bloqueos de la política de seguridad, recursos de
// terceros, desborde horizontal, enlaces internos rotos o cifras que no
// coinciden con datos/cifras.json.
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("..", import.meta.url));
const TIPOS = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json", ".svg": "image/svg+xml", ".woff2": "font/woff2" };
const PAGINAS = ["index.html", "estrategia.html", "salud.html", "cifras.html", "libro.html", "nosotros.html", "privacidad.html", "404.html", "blog/index.html", "blog/el-ahorro-llega-mas-rapido.html", "blog/la-madurez-digital-no-se-compra.html"];
const VISTAS = { escritorio: { width: 1440, height: 900 }, celular: { width: 390, height: 844 } };

const servidor = createServer(async (req, res) => {
  const ruta = normalize(decodeURIComponent(new URL(req.url, "http://x").pathname)).replace(/^([/\\])+/, "");
  try { res.writeHead(200, { "Content-Type": TIPOS[extname(ruta)] || "application/octet-stream" }).end(await readFile(join(RAIZ, ruta))); }
  catch { res.writeHead(404).end(); }
}).listen(0);
const BASE = `http://127.0.0.1:${servidor.address().port}/`;

const fallas = [];
const falla = (pagina, vista, msg) => fallas.push(`${pagina} [${vista}] ${msg}`);
const navegador = await chromium.launch();

for (const [vista, viewport] of Object.entries(VISTAS)) {
  const pag = await navegador.newPage({ viewport });
  let actual = "";
  pag.on("console", (m) => { if (m.type() === "error") falla(actual, vista, "consola: " + m.text()); });
  pag.on("pageerror", (e) => falla(actual, vista, "error JS: " + e.message));
  pag.on("request", (r) => { if (!r.url().startsWith(BASE) && !r.url().startsWith("data:")) falla(actual, vista, "recurso de tercero: " + r.url()); });
  pag.on("response", (r) => { if (r.status() >= 400 && r.url().startsWith(BASE)) falla(actual, vista, `${r.status()} ${r.url().replace(BASE, "")}`); });
  for (const p of PAGINAS) {
    actual = p;
    await pag.goto(BASE + p, { waitUntil: "networkidle" });
    const ancho = await pag.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (ancho > 0) falla(p, vista, `desborde horizontal de ${ancho}px`);
    if (vista === "escritorio") {
      const enlaces = await pag.$$eval("a[href]", (as) => as.map((a) => a.href).filter((h) => h.startsWith(location.origin)));
      for (const h of new Set(enlaces)) {
        const r = await pag.request.get(h.split("#")[0]);
        if (r.status() !== 200) falla(p, vista, "enlace roto: " + h.replace(BASE, ""));
      }
    }
  }
  await pag.close();
}

// Cifras: lo que se ve debe salir del JSON.
const datos = JSON.parse(await readFile(join(RAIZ, "datos/cifras.json"), "utf8"));
const pag = await navegador.newPage({ viewport: VISTAS.escritorio });
await pag.goto(BASE + "cifras.html", { waitUntil: "networkidle" });
const kpis = async (id) => pag.$$eval(`#${id} .valor`, (v) => v.map((e) => e.textContent));
const s = await kpis("kpi-sector");
const t2 = datos.series.T02.tablas[0].filas;
const totalEntidades = t2.reduce((a, f) => a + f[1], 0).toLocaleString("es-CO");
if (s[0] !== totalEntidades) falla("cifras.html", "datos", `entidades ${s[0]} ≠ ${totalEntidades}`);
await pag.click("#tab-cac");
const c = await kpis("kpi-cac");
const fin = datos.series.T13.tablas[1].filas.at(-1);
const esperado = "$" + (fin[3] / 1000).toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " BB";
if (c[0] !== esperado) falla("cifras.html", "datos", `activos CAC ${c[0]} ≠ ${esperado}`);
for (const [tab, id] of [["tab-sector", "g-activos-anio"], ["tab-cac", "g-indice"], ["tab-pagos", "g-breb"]]) {
  await pag.click("#" + tab);
  const dibujado = await pag.$eval("#" + id, (cv) => cv.width > 0 && cv.getBoundingClientRect().height > 100);
  if (!dibujado) falla("cifras.html", "datos", `gráfico ${id} sin dibujar`);
}
await pag.close();

// Demo del Radar (estrategia.html): cortes, techo, sin red, WhatsApp solo con el resultado.
{
  const V = "radar";
  const rd = await navegador.newPage({ viewport: VISTAS.escritorio });
  await rd.goto(BASE + "estrategia.html", { waitUntil: "networkidle" });
  const pedidos = [];
  rd.on("request", (r) => pedidos.push(r.url()));
  const EJES = await rd.$$eval(".rd-pregunta", (fs) => fs.map((f) => f.dataset.eje));
  if (EJES.length !== 8) falla("estrategia.html", V, `${EJES.length} preguntas, se esperaban 8`);
  const responder = async (vals) => { for (let i = 0; i < 8; i++) await rd.check(`input[name="rd-${i + 1}"][value="${vals[i]}"]`); };
  const leer = async () => rd.evaluate(() => ({
    listo: !document.getElementById("rd-listo").hidden,
    total: document.getElementById("rd-total").textContent,
    nivel: document.getElementById("rd-nivel").textContent,
    techo: document.getElementById("rd-techo").textContent,
    bajos: document.getElementById("rd-riesgo").hidden ? "" : document.getElementById("rd-bajos").textContent,
    wa: document.getElementById("rd-whatsapp").href,
    puntos: document.querySelectorAll("#rd-radar .rd-punto").length,
  }));
  const nivelDe = (t) => (t < 17 ? "Inicial" : t < 28 ? "En desarrollo" : t < 36 ? "Consolidado" : "Avanzado");
  // Con 7 de 8 todavía no hay resultado.
  for (let i = 0; i < 7; i++) await rd.check(`input[name="rd-${i + 1}"][value="3"]`);
  if ((await leer()).listo) falla("estrategia.html", V, "muestra resultado con 7 de 8 respuestas");
  // Los cortes del libro: 8, 16, 17, 27, 28, 35, 36 y 40.
  for (const objetivo of [8, 16, 17, 27, 28, 35, 36, 40]) {
    const vals = Array(8).fill(1);
    for (let resto = objetivo - 8, i = 0; resto > 0; i = (i + 1) % 8) if (vals[i] < 5) { vals[i]++; resto--; }
    await responder(vals);
    const r = await leer();
    if (!r.listo || r.total !== String(objetivo) || r.nivel !== nivelDe(objetivo)) falla("estrategia.html", V, `total ${objetivo}: se vio ${r.total} «${r.nivel}», se esperaba «${nivelDe(objetivo)}»`);
    if (r.puntos !== 8) falla("estrategia.html", V, `radar con ${r.puntos} puntos`);
  }
  // Techo, ejes bajo 2 y el mensaje de WhatsApp (solo el resultado).
  const casos = [
    { vals: [4, 4, 4, 4, 4, 2, 4, 4], techo: EJES[5], bajos: "" },
    { vals: [3, 1, 4, 4, 5, 1, 4, 4], techo: `${EJES[1]}, ${EJES[5]}`, bajos: `${EJES[1]}, ${EJES[5]}` },
    { vals: [3, 3, 3, 3, 3, 3, 3, 3], techo: "ejes parejos, todos en 3", bajos: "" },
  ];
  const waMenu = await rd.$eval(".menu a[href^='https://wa.me/']", (a) => a.href);
  for (const c of casos) {
    await responder(c.vals);
    const r = await leer();
    const total = c.vals.reduce((a, b) => a + b, 0);
    if (r.techo !== c.techo) falla("estrategia.html", V, `techo «${r.techo}», se esperaba «${c.techo}»`);
    if (r.bajos !== c.bajos) falla("estrategia.html", V, `ejes bajo 2 «${r.bajos}», se esperaba «${c.bajos}»`);
    const esperado = `${waMenu}?text=${encodeURIComponent(`Hice el autodiagnóstico del Radar: ${total}/40, ${nivelDe(total)}; techo: ${c.techo}`)}`;
    if (r.wa !== esperado) falla("estrategia.html", V, `WhatsApp: ${r.wa}`);
    const u = new URL(r.wa);
    if ([...u.searchParams.keys()].join() !== "text") falla("estrategia.html", V, `WhatsApp con parámetros de más: ${u.search}`);
  }
  // Con teclado: la flecha cambia la respuesta.
  await rd.focus('input[name="rd-1"][value="3"]');
  await rd.keyboard.press("ArrowRight");
  if (!(await rd.$eval('input[name="rd-1"][value="4"]', (i) => i.checked))) falla("estrategia.html", V, "la flecha del teclado no cambia la respuesta");
  if (pedidos.length) falla("estrategia.html", V, `${pedidos.length} pedidos de red al responder: ${pedidos.slice(0, 3).join(" | ")}`);
  // La plataforma: en el menú de todas las páginas y en la sección, misma pestaña, rel=noopener.
  const plataforma = await rd.$$eval("a[href^='https://andrezgmz.github.io/ejecutar-sin-miedo/']", (as) => as.map((a) => `${a.rel}|${a.target}`));
  if (plataforma.length !== 2 || plataforma.some((x) => x !== "noopener|")) falla("estrategia.html", V, `enlaces a la plataforma: ${plataforma.join(", ")}`);
  await rd.close();
}

// Reglas de SECURITY.md que se leen en el código: CSP igual en todas las páginas, sin innerHTML ni código en línea.
const CSP = `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'; upgrade-insecure-requests`;
for (const p of PAGINAS) {
  const html = await readFile(join(RAIZ, p), "utf8");
  const csp = (html.match(/http-equiv="Content-Security-Policy" content="([^"]*)"/) || [])[1];
  if (csp !== CSP) falla(p, "código", "la CSP cambió");
  if (/<script(?![^>]*\bsrc=)[^>]*>/i.test(html) || /\sstyle=/i.test(html) || /\son[a-z]+=/i.test(html)) falla(p, "código", "código o estilo en línea");
  if (!html.includes('class="menu-plataforma" href="https://andrezgmz.github.io/ejecutar-sin-miedo/" rel="noopener"')) falla(p, "código", "falta «Plataforma» en el menú");
}
for (const js of ["assets/js/sitio.js", "assets/js/cifras.js", "assets/js/radar-demo.js"]) {
  const codigo = (await readFile(join(RAIZ, js), "utf8")).replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  if (/innerHTML|outerHTML|insertAdjacentHTML|document\.write|localStorage|sessionStorage|indexedDB|document\.cookie/.test(codigo)) falla(js, "código", "usa innerHTML, almacenamiento o cookies");
  // cifras.js lee datos/cifras.json del mismo sitio; el demo del Radar no pide nada.
  if (js.endsWith("radar-demo.js") && /fetch\(|XMLHttpRequest|sendBeacon|WebSocket/.test(codigo)) falla(js, "código", "el demo hace pedidos de red");
}
await navegador.close();
servidor.close();

if (fallas.length) { console.error(`FALLAS: ${fallas.length}\n` + fallas.join("\n")); process.exit(1); }
console.log(`OK: ${PAGINAS.length} páginas × ${Object.keys(VISTAS).length} vistas, cifras, enlaces, demo del Radar y reglas de seguridad verificados. 0 fallas.`);
