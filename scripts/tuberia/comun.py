"""Piezas comunes de la tubería de datos (solo librería estándar).

Rutas, cliente HTTP con reintentos, huellas, registro de ejecuciones y el
contexto TLS propio para el Banco de la República (ver FUENTES.md).
"""
import datetime as dt
import gzip
import hashlib
import json
import os
import pathlib
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DATOS = RAIZ / "datos"
CRUDO, LIMPIO, INDICADORES, WEB = DATOS / "crudo", DATOS / "limpio", DATOS / "indicadores", DATOS / "web"
REGISTRO = DATOS / "registro.jsonl"

BOGOTA = dt.timezone(dt.timedelta(hours=-5), "America/Bogota")  # Colombia no cambia de hora.
AGENTE = "KatalisDatos/1.0 (+https://katalispartners.com.co)"

# Certificado intermedio que el servidor del Banco de la República no envía (ver FUENTES.md).
# Solo se usa para ese host, sumado a los certificados del sistema; la verificación sigue activa.
CERT_BANREP = pathlib.Path(__file__).resolve().parent / "certificados" / "GeoTrustEVRSACAG2.crt.pem"
CERT_BANREP_SHA256 = "2d140f20b8a96e2b4d2f1cc5aca5e5a1e7dc56a7491e510906960f38d2d21aef"
HOSTS_BANREP = {"suameca.banrep.gov.co"}
# Fecha de vencimiento del intermedio (campo notAfter, verificado con openssl). Va fija junto a la huella:
# si se cambia el archivo, la huella deja de coincidir y hay que actualizar las dos.
CERT_BANREP_VENCE = dt.datetime(2030, 7, 2, 12, 42, 57, tzinfo=dt.timezone.utc)


class ErrorFuente(Exception):
    """La fuente no respondió como se esperaba (red, HTTP, certificado)."""


class ErrorValidacion(Exception):
    """La respuesta llegó, pero no pasa los controles: esa fuente no avanza."""


def ahora_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def hoy_bogota(momento=None):
    return (momento or ahora_utc()).astimezone(BOGOTA).date()


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def contexto_banrep():
    """Contexto TLS solo para el Banco de la República: certificados del sistema + el intermedio fijado."""
    pem = CERT_BANREP.read_text(encoding="ascii")
    if sha256(ssl.PEM_cert_to_DER_cert(pem)) != CERT_BANREP_SHA256:
        raise ErrorFuente("el certificado intermedio guardado no coincide con su huella SHA-256 fijada")
    ctx = ssl.create_default_context()          # verifica certificado y nombre del host
    ctx.load_verify_locations(cadata=pem)
    return ctx


def vencimiento_cert_banrep():
    """Fecha de vencimiento (UTC) del intermedio guardado (constante junto a su huella)."""
    return CERT_BANREP_VENCE


class RedireccionSegura(urllib.request.HTTPRedirectHandler):
    """Solo sigue redirecciones https:// al mismo host. Cualquier otra es un error de la fuente."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destino = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        origen = urllib.parse.urlsplit(req.full_url)
        if destino.scheme != "https" or destino.hostname != origen.hostname:
            raise ErrorFuente(f"redirección no permitida ({code}) de {origen.scheme}://{origen.hostname} "
                              f"a {destino.scheme}://{destino.hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def abridor(ctx):
    """urllib con TLS verificado (ctx) y sin redirecciones a otro esquema u otro host."""
    return urllib.request.build_opener(RedireccionSegura(), urllib.request.HTTPSHandler(context=ctx))


def descargar(url, intentos=3, espera=5, timeout=90):
    """GET con reintentos. Devuelve (bytes, encabezados). Nunca desactiva la verificación TLS."""
    partes = urllib.parse.urlsplit(url)
    if partes.scheme != "https":
        raise ErrorFuente(f"solo se consultan fuentes por https: {url}")
    ctx = contexto_banrep() if partes.hostname in HOSTS_BANREP else ssl.create_default_context()
    abrir = abridor(ctx)
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "*/*"})
    ultimo = None
    for n in range(1, intentos + 1):
        try:
            with abrir.open(pedido, timeout=timeout) as r:
                return r.read(), dict(r.headers.items())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            ultimo = e
            if isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500 and e.code != 429:
                break
            if n < intentos:
                time.sleep(espera * n)
    raise ErrorFuente(f"{url} → {type(ultimo).__name__}: {ultimo}")


def soql(recurso, **parametros):
    """URL exacta de una consulta SoQL a datos.gov.co (la misma que queda en el registro)."""
    return f"https://www.datos.gov.co/resource/{recurso}.json?" + urllib.parse.urlencode(
        {f"${k}": v for k, v in parametros.items()}, quote_via=urllib.parse.quote)


def guardar_crudo(fuente, datos: bytes, extension, meta, momento):
    """Guarda la respuesta tal cual en datos/crudo/<fuente>/<AAAA-MM-DD>/.

    Solo crea una carpeta nueva si el sha256 cambió frente a la última respuesta guardada
    (la de hora más reciente); si es igual, no copia nada y quien llama anota «sin cambios».
    Nunca sobrescribe: si ya hay una carpeta de ese día, usa <fecha>-2, <fecha>-3…
    Las respuestas grandes se comprimen con gzip: al descomprimir son los mismos bytes.
    Devuelve (ruta relativa del archivo vigente, True si se guardó uno nuevo).
    """
    huella = sha256(datos)
    carpeta_fuente = CRUDO / fuente
    previas = [json.loads(p.read_text(encoding="utf-8")) for p in carpeta_fuente.glob("*/consulta.json")] \
        if carpeta_fuente.exists() else []
    if previas:
        anterior = max(previas, key=lambda c: c.get("hora_utc", ""))
        if anterior.get("sha256") == huella:
            return anterior["archivo"], False
    dia = hoy_bogota(momento).isoformat()
    carpeta, n = carpeta_fuente / dia, 1
    while carpeta.exists():
        n += 1
        carpeta = carpeta_fuente / f"{dia}-{n}"
    carpeta.mkdir(parents=True)
    nombre = f"respuesta.{extension}"
    if len(datos) > 200_000:
        nombre += ".gz"
        (carpeta / nombre).write_bytes(gzip.compress(datos, mtime=0))
    else:
        (carpeta / nombre).write_bytes(datos)
    relativo = (carpeta / nombre).relative_to(RAIZ).as_posix()
    (carpeta / "consulta.json").write_text(json.dumps(
        {**meta, "sha256": huella, "bytes": len(datos), "archivo": relativo}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    return relativo, True


def escribir_json(ruta, objeto):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(objeto, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def leer_json(ruta, defecto=None):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defecto


def registrar(linea):
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRO.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(linea, ensure_ascii=False, sort_keys=True) + "\n")


def corrida_id():
    return os.environ.get("GITHUB_RUN_ID") or "local-" + ahora_utc().strftime("%Y%m%dT%H%M%SZ")
