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
    """Fecha de vencimiento (UTC) del intermedio guardado."""
    texto = ssl._ssl._test_decode_cert(str(CERT_BANREP))["notAfter"]  # p. ej. 'Jul  2 12:42:57 2030 GMT'
    return dt.datetime.strptime(texto, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)


def descargar(url, intentos=3, espera=5, timeout=90):
    """GET con reintentos. Devuelve (bytes, encabezados). Nunca desactiva la verificación TLS."""
    host = urllib.parse.urlsplit(url).hostname
    ctx = contexto_banrep() if host in HOSTS_BANREP else ssl.create_default_context()
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "*/*"})
    ultimo = None
    for n in range(1, intentos + 1):
        try:
            with urllib.request.urlopen(pedido, timeout=timeout, context=ctx) as r:
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

    Si es idéntica (mismo sha256) a la última guardada, no la duplica.
    Las respuestas grandes se comprimen con gzip: al descomprimir son los mismos bytes.
    Devuelve la ruta relativa del archivo, o la del último idéntico.
    """
    huella = sha256(datos)
    carpeta_fuente = CRUDO / fuente
    previas = sorted(carpeta_fuente.glob("*/consulta.json")) if carpeta_fuente.exists() else []
    if previas:
        anterior = json.loads(previas[-1].read_text(encoding="utf-8"))
        if anterior.get("sha256") == huella:
            return anterior["archivo"], False
    carpeta = carpeta_fuente / hoy_bogota(momento).isoformat()
    carpeta.mkdir(parents=True, exist_ok=True)
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
