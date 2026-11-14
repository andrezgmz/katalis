"""Construye las páginas del sitio a partir de contenido/.

Uso (desde la carpeta del sitio):
    python scripts/construir_sitio.py

Cada archivo de contenido/ empieza con una línea de datos:
    <!-- {"titulo": "...", "descripcion": "...", "menu": "cifras", "js": ["assets/js/cifras.js"]} -->
y luego el HTML del cuerpo. Encabezado, pie, contacto y política de seguridad
viven solo aquí, para cambiarlos una vez.
"""
import datetime as dt, html, json, pathlib, re

RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Datos que cambian
# Acción principal «Agendar una conversación»: agenda de Google Calendar (decisión de Andrés, 13-nov-2026).
AGENDA = ("https://calendar.google.com/calendar/appointments/schedules/"
          "AcZssZ1uNj8qjBkHzNTpQ3xpwBEC2JpFaiqzCVFoVAZ7U4T3BTQpQwDIKS9i5YP16_GGFQuTDu4y9KL8")
# WhatsApp es secundario: solo en el pie y en Nosotros.
WHATSAPP = "573167836311"
WHATSAPP_ROTULO = "WhatsApp +57 316 783 6311"
CORREO = "hola@katalispartners.com.co"
CORREO_SEGURIDAD = "seguridad@katalispartners.com.co"  # Solo en SECURITY.md y /.well-known/security.txt.
# Perfil personal de Andrés; la página de empresa en LinkedIn se crea después.
LINKEDIN = "https://www.linkedin.com/in/william-andr%C3%A9s-g%C3%B3mez-lizarazo"
LINKEDIN_ROTULO = "William Andrés Gómez en LinkedIn"
DOMINIO = "https://katalispartners.com.co"
# La plataforma Ejecutar sin Miedo, en su subdominio. Se cambia solo aquí.
PLATAFORMA = "https://app.katalispartners.com.co/ejecutar-sin-miedo/"
LIBRO_HOTMART = ""  # Pegue aquí el enlace de Hotmart cuando el libro salga a la venta.
# security.txt (RFC 9116): «Expires» debe quedar a menos de un año. La prueba falla cuando vence: renovarlo aquí.
SECURITY_TXT_VENCE = "2027-11-01T00:00:00-05:00"


LOGO = ('<svg width="30" height="30" viewBox="0 0 100 100" aria-hidden="true">'
        '<rect x="10" y="8" width="20" height="84" rx="3" fill="#F7F4EE"/>'
        '<polygon points="36,48 74,8 94,8 46,58" fill="#9DB4FF"/>'
        '<polygon points="52,60 64,48 96,92 72,92" fill="#FF8A65"/></svg>')

MENU = [("estrategia.html", "Estrategia", "estrategia"), ("salud.html", "Salud", "salud"),
        ("cifras.html", "Cifras", "cifras"), ("blog/index.html", "Blog", "blog"),
        ("libro.html", "Libro", "libro"), ("nosotros.html", "Nosotros", "nosotros")]

# Pulso macro: franja bajo el encabezado de todas las páginas. Sale de datos/web/macro.json
# (lo arma la tubería de datos, scripts/tuberia/). Nada se escribe a mano aquí.
BOGOTA = dt.timezone(dt.timedelta(hours=-5))
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
PULSO_FUENTE_CORTA = {"trm": "SFC", "tasa_emisor": "BanRep", "inflacion": "DANE"}
# Días sin actualizar antes de mostrar «desactualizado» (decisión de Andrés, 12-nov-2026).
PULSO_LIMITE = {"trm": ("fecha", 7), "tasa_emisor": ("ultima_consulta_ok", 45), "inflacion": ("fecha_publicacion", 45)}

# Citas que exige cada fuente (decisión de Andrés, 14-nov-2026). Viven solo aquí.
# DANE, términos y condiciones, numeral 2: cita textual obligatoria.
CITA_DANE = "Fuente: Departamento Administrativo Nacional de Estadística: www.dane.gov.co"
# Banco de la República, aviso legal: fuente y fecha en que se consultó el portal (la de la corrida que trajo el dato).
CITA_BANREP = "Fuente: Banco de la República."
SERIE_BANREP_EMISOR = "https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/59/tasas_interes_politica_monetaria"
# TRM: la ficha de datos.gov.co 32sa-8pi3 declara «Creative Commons Attribution | Share Alike 4.0 International»
# (licenseId CC_40_BY_SA) y atribución «Superintendencia Financiera de Colombia». Verificado el 14-nov-2026.
CITA_SFC = "Superintendencia Financiera de Colombia vía datos.gov.co · CC BY-SA 4.0"
FICHA_TRM = "https://www.datos.gov.co/d/32sa-8pi3"
LICENCIA_CC_BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/legalcode"


def _num(valor, decimales=2):
    return f"{valor:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _fecha_corta(iso):
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.day} {MESES_CORTOS[d.month - 1]} {d.year}"


def desactualizado(clave, dato, hoy):
    campo, dias = PULSO_LIMITE[clave]
    if dato.get("valor") is None or not dato.get(campo):
        return False
    return (hoy - dt.date.fromisoformat(dato[campo][:10])).days > dias


def leer_macro():
    try:
        return json.loads((RAIZ / "datos" / "web" / "macro.json").read_text(encoding="utf-8")).get("indicadores", {})
    except FileNotFoundError:
        return {}


def consulta_banrep(macro):
    """«Consultado el …» con la fecha (Bogotá) de la última consulta exitosa que guardó la tubería; None si no hay dato."""
    d = macro.get("tasa_emisor", {})
    if d.get("valor") is None or not d.get("ultima_consulta_ok"):
        return None
    momento = dt.datetime.fromisoformat(d["ultima_consulta_ok"]).astimezone(BOGOTA)
    return _fecha_corta(momento.date().isoformat())


def citas(macro):
    """Las tres citas en HTML (franja y privacidad). El texto exigido queda intacto; los enlaces no lo cambian."""
    fecha = consulta_banrep(macro)
    banrep = CITA_BANREP.replace("Banco de la República",
                                 f'<a href="{SERIE_BANREP_EMISOR}" rel="noopener">Banco de la República</a>')
    entidad, licencia = CITA_SFC.split(" · ")
    return {
        "trm": (f'<a href="{FICHA_TRM}" rel="noopener">{entidad}</a> · '
                f'<a href="{LICENCIA_CC_BY_SA}" rel="license noopener">{licencia}</a>'),
        "tasa_emisor": banrep + (f" Consultado el {fecha}." if fecha else ""),
        "inflacion": CITA_DANE.replace("www.dane.gov.co", '<a href="https://www.dane.gov.co" rel="noopener">www.dane.gov.co</a>'),
    }


def pulso_macro(hoy, macro=None):
    macro = leer_macro() if macro is None else macro
    items = []
    for clave in ("trm", "tasa_emisor", "inflacion"):
        d = macro.get(clave, {})
        nombre = {"trm": "TRM", "tasa_emisor": "Tasa del Emisor", "inflacion": "Inflación anual"}[clave]
        # La URL sale de esta constante, no de macro.json; todo valor del JSON se escapa (defensa en profundidad).
        url = {"trm": "https://www.datos.gov.co/d/32sa-8pi3",
               "tasa_emisor": "https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/59/tasas_interes_politica_monetaria",
               "inflacion": "https://www.dane.gov.co/index.php/estadisticas-por-tema/precios-y-costos/indice-de-precios-al-consumidor-ipc"}[clave]
        fuente = f'<a class="pulso-fuente" href="{url}" rel="noopener" title="Fuente oficial: {html.escape(str(d.get("fuente", PULSO_FUENTE_CORTA[clave])), quote=True)}">{PULSO_FUENTE_CORTA[clave]}</a>'
        if d.get("valor") is None:
            items.append(f'<span class="pulso-item" data-clave="{clave}"><span class="pulso-nombre">{nombre}:</span> '
                         f'<b class="pulso-valor" data-valor="">sin dato</b> {fuente}</span>')
            continue
        if clave == "trm":
            texto, fecha = "$" + _num(d["valor"]), _fecha_corta(d["fecha"])
        elif clave == "tasa_emisor":
            texto, fecha = _num(d["valor"]) + " %", "desde " + _fecha_corta(d["vigente_desde"])
        else:
            texto, fecha = _num(d["valor"]) + " %", f'{MESES_CORTOS[int(d["mes"][5:]) - 1]} {d["mes"][:4]}'
        viejo = desactualizado(clave, d, hoy)
        items.append(f'<span class="pulso-item" data-clave="{clave}" data-desactualizado="{str(viejo).lower()}">'
                     f'<span class="pulso-nombre">{nombre}</span> <b class="pulso-valor" data-valor="{html.escape(str(d["valor"]), quote=True)}">{texto}</b> '
                     f'<span class="pulso-fecha">{fecha}</span>'
                     + (' <span class="pulso-viejo">desactualizado</span>' if viejo else "") + f' {fuente}</span>')
    c = citas(macro)
    notas = "".join(f'<span class="pulso-cita" data-cita="{clave}"><b>{nombre}</b> {c[clave]}</span>'
                    for clave, nombre in (("trm", "TRM:"), ("tasa_emisor", "Tasa del Emisor:"), ("inflacion", "Inflación:")))
    return (f'<div class="pulso" role="region" aria-label="Pulso macro: cifras oficiales" data-hoy="{hoy.isoformat()}">'
            f'<div class="envoltura pulso-fila">{"".join(items)}</div>'
            f'<p class="envoltura pulso-citas">{notas}</p></div>')


def datos_estructurados():
    """JSON-LD de la firma (solo en index.html). Es un bloque de datos, no código: la CSP no lo ejecuta ni lo bloquea.
    Solo los datos que aprobó Andrés (13-nov-2026); la prueba revisa que no haya otros."""
    datos = {
        "@context": "https://schema.org",
        "@type": "ProfessionalService",
        "name": "Katalis Partners",
        "legalName": "Gómez Hernández Consulting S.A.S.",
        "url": DOMINIO + "/",
        "email": CORREO,
        "telephone": "+" + WHATSAPP,
        "areaServed": "Colombia",
        "address": {"@type": "PostalAddress", "addressLocality": "Bogotá", "addressCountry": "CO"},
        "sameAs": [LINKEDIN],
    }
    texto = json.dumps(datos, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{texto}</script>\n'


def security_txt():
    return (f"Contact: mailto:{CORREO_SEGURIDAD}\n"
            f"Expires: {SECURITY_TXT_VENCE}\n"
            "Preferred-Languages: es\n"
            f"Canonical: {DOMINIO}/.well-known/security.txt\n")


def pagina(ruta, titulo, descripcion, actual, cuerpo, scripts, pulso=""):
    nivel = ruta.count("/")
    p = "../" * nivel
    items = "".join(
        f'<a href="{p}{href}"{" aria-current=page" if clave == actual else ""}>{txt}</a>'
        for href, txt, clave in MENU)
    WA = "https://wa.me/" + WHATSAPP
    url = DOMINIO + "/" + ("" if ruta == "index.html" else ruta.removesuffix("index.html"))
    ld = datos_estructurados() if ruta == "index.html" else ""
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
{ld}</head>
<body>
<a class="saltar" href="#contenido">Saltar al contenido</a>
<header class="cabecera">
<nav aria-label="Principal">
<a class="marca" href="{p}index.html" aria-label="Katalis Partners, inicio">{LOGO}<span><b>KATALIS</b><small>PARTNERS</small></span></a>
<button class="menu-boton" aria-expanded="false" aria-controls="menu">Menú</button>
<div class="menu" id="menu">{items}<a class="menu-plataforma" href="{PLATAFORMA}" rel="noopener">Plataforma</a><a class="boton boton-claro" href="{AGENDA}" rel="noopener">Agendar una conversación</a></div>
</nav>
</header>
{pulso}
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
<div class="pie-contacto"><h4>Contacto</h4><ul>
<li><a href="{AGENDA}" rel="noopener">Agendar una conversación</a></li>
<li><a href="mailto:{CORREO}">{CORREO}</a></li>
<li><a href="{WA}" rel="noopener">{WHATSAPP_ROTULO}</a></li>
<li><a href="{LINKEDIN}" rel="noopener">{LINKEDIN_ROTULO}</a></li>
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
    macro = leer_macro()
    pulso = pulso_macro(dt.datetime.now(BOGOTA).date(), macro)
    c = citas(macro)
    reemplazos = {"{{CITA_TRM}}": c["trm"], "{{CITA_BANREP}}": c["tasa_emisor"], "{{CITA_DANE}}": c["inflacion"],"{{AGENDA}}": AGENDA, "{{WHATSAPP}}": "https://wa.me/" + WHATSAPP, "{{WHATSAPP_ROTULO}}": WHATSAPP_ROTULO,
                  "{{CORREO}}": "mailto:" + CORREO, "{{CORREO_TEXTO}}": CORREO, "{{PLATAFORMA}}": PLATAFORMA,
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
        html = pagina(ruta, meta["titulo"], meta["descripcion"], meta.get("menu", ""), cuerpo, meta.get("js", []), pulso)
        (RAIZ / ruta).parent.mkdir(parents=True, exist_ok=True)
        (RAIZ / ruta).write_text(html, encoding="utf-8")
        hechas.append(ruta)
    urls = "".join(f"<url><loc>{DOMINIO}/{'' if r == 'index.html' else r.removesuffix('index.html')}</loc></url>" for r in hechas if r != "404.html")
    (RAIZ / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8", newline="\n")
    (RAIZ / ".well-known").mkdir(exist_ok=True)
    (RAIZ / ".well-known" / "security.txt").write_text(security_txt(), encoding="utf-8", newline="\n")
    print("OK:", len(hechas), "páginas, sitemap.xml y .well-known/security.txt:", ", ".join(hechas))


if __name__ == "__main__":
    main()
