"""Construye las páginas del sitio a partir de contenido/.

Uso (desde la carpeta del sitio):
    python scripts/construir_sitio.py

Cada archivo de contenido/ empieza con una línea de datos:
    <!-- {"titulo": "...", "descripcion": "...", "menu": "cifras", "js": ["assets/js/cifras.js"]} -->
y luego el HTML del cuerpo. Encabezado, pie, contacto y política de seguridad
viven solo aquí, para cambiarlos una vez.
"""
import json, pathlib, re

RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Datos que cambian
WHATSAPP = "573167836311"
CORREO = "andrezgmz@outlook.com"
LINKEDIN = "https://www.linkedin.com/in/william-andr%C3%A9s-g%C3%B3mez-lizarazo"
DOMINIO = "https://katalispartners.com.co"
# La plataforma Ejecutar sin Miedo (la app no se muda: hay QR y enlaces impresos). Si pasa a un subdominio, se cambia solo aquí.
PLATAFORMA = "https://andrezgmz.github.io/ejecutar-sin-miedo/"
LIBRO_HOTMART = ""  # Pegue aquí el enlace de Hotmart cuando el libro salga a la venta.


LOGO = ('<svg width="30" height="30" viewBox="0 0 100 100" aria-hidden="true">'
        '<rect x="10" y="8" width="20" height="84" rx="3" fill="#F7F4EE"/>'
        '<polygon points="36,48 74,8 94,8 46,58" fill="#9DB4FF"/>'
        '<polygon points="52,60 64,48 96,92 72,92" fill="#FF8A65"/></svg>')

MENU = [("estrategia.html", "Estrategia", "estrategia"), ("salud.html", "Salud", "salud"),
        ("cifras.html", "Cifras", "cifras"), ("blog/index.html", "Blog", "blog"),
        ("libro.html", "Libro", "libro"), ("nosotros.html", "Nosotros", "nosotros")]

def pagina(ruta, titulo, descripcion, actual, cuerpo, scripts):
    nivel = ruta.count("/")
    p = "../" * nivel
    items = "".join(
        f'<a href="{p}{href}"{" aria-current=page" if clave == actual else ""}>{txt}</a>'
        for href, txt, clave in MENU)
    WA = "https://wa.me/" + WHATSAPP
    url = DOMINIO + "/" + ("" if ruta == "index.html" else ruta.removesuffix("index.html"))
    html = f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'; upgrade-insecure-requests">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{descripcion}">
<meta property="og:title" content="{titulo}">
<meta property="og:description" content="{descripcion}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<link rel="canonical" href="{url}">
<meta property="og:locale" content="es_CO">
<meta name="theme-color" content="#161A2E">
<link rel="icon" href="{p}assets/img/favicon.svg" type="image/svg+xml">
<meta name="referrer" content="strict-origin-when-cross-origin">
<link rel="preload" href="{p}assets/fonts/plus-jakarta-sans-latin-800-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{p}assets/css/katalis.css">
</head>
<body>
<a class="saltar" href="#contenido">Saltar al contenido</a>
<header class="cabecera">
<nav aria-label="Principal">
<a class="marca" href="{p}index.html" aria-label="Katalis Partners, inicio">{LOGO}<span><b>KATALIS</b><small>PARTNERS</small></span></a>
<button class="menu-boton" aria-expanded="false" aria-controls="menu">Menú</button>
<div class="menu" id="menu">{items}<a class="menu-plataforma" href="{PLATAFORMA}" rel="noopener">Plataforma</a><a class="boton boton-claro" href="{WA}" rel="noopener">Agendar una conversación</a></div>
</nav>
</header>
<main id="contenido">
{cuerpo}
</main>
<footer class="pie">
<div class="envoltura">
<div>
<a class="marca" href="{p}index.html">{LOGO}<span><b>KATALIS</b><small>PARTNERS</small></span></a>
<p class="pie-lema">Bajamos la barrera del cambio. Estrategia para organizaciones · Ciencia del cuidado para la salud.</p>
</div>
<div><h4>Sitio</h4><ul>{"".join(f'<li><a href="{p}{h}">{t}</a></li>' for h, t, _ in MENU)}</ul></div>
<div><h4>Contacto</h4><ul>
<li><a href="{WA}" rel="noopener">WhatsApp</a></li>
<li><a href="mailto:{CORREO}">Correo</a></li>
<li><a href="{LINKEDIN}" rel="noopener">LinkedIn</a></li>
</ul></div>
<div class="legal"><span>Gómez Hernández Consulting S.A.S. (Katalis Partners) · NIT 902.121.376-5 · Bogotá D.C.</span><a href="{p}privacidad.html">Privacidad y datos</a></div>
</div>
</footer>
<script src="{p}assets/js/sitio.js"></script>
{"".join(f'<script src="{p}{js}"></script>' for js in scripts)}
</body>
</html>
'''
    return html


def main():
    reemplazos = {"{{WHATSAPP}}": "https://wa.me/" + WHATSAPP, "{{CORREO}}": "mailto:" + CORREO, "{{PLATAFORMA}}": PLATAFORMA,
                  "{{LIBRO}}": LIBRO_HOTMART or "mailto:" + CORREO + "?subject=Av%C3%ADsame%20cuando%20salga%20Ejecutar%20sin%20Miedo",
                  "{{LIBRO_TEXTO}}": "Comprar en Hotmart" if LIBRO_HOTMART else "Avísame cuando salga"}
    hechas = []
    for fuente in sorted((RAIZ / "contenido").rglob("*.html")):
        primera, cuerpo = fuente.read_text(encoding="utf-8").split("\n", 1)
        meta = json.loads(re.fullmatch(r"<!--\s*(\{.*\})\s*-->", primera.strip()).group(1))
        for k, v in reemplazos.items():
            cuerpo = cuerpo.replace(k, v)
        ruta = fuente.relative_to(RAIZ / "contenido").as_posix()
        cuerpo = cuerpo.replace("{{RAIZ}}", "../" * ruta.count("/"))
        html = pagina(ruta, meta["titulo"], meta["descripcion"], meta.get("menu", ""), cuerpo, meta.get("js", []))
        (RAIZ / ruta).parent.mkdir(parents=True, exist_ok=True)
        (RAIZ / ruta).write_text(html, encoding="utf-8")
        hechas.append(ruta)
    urls = "".join(f"<url><loc>{DOMINIO}/{'' if r == 'index.html' else r.removesuffix('index.html')}</loc></url>" for r in hechas if r != "404.html")
    (RAIZ / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8", newline="\n")
    print("OK:", len(hechas), "páginas y sitemap.xml:", ", ".join(hechas))


if __name__ == "__main__":
    main()
