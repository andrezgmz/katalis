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
await navegador.close();
servidor.close();

if (fallas.length) { console.error(`FALLAS: ${fallas.length}\n` + fallas.join("\n")); process.exit(1); }
console.log(`OK: ${PAGINAS.length} páginas × ${Object.keys(VISTAS).length} vistas, cifras y enlaces verificados. 0 fallas.`);
