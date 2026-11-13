"""Capa 1 · extraer: pide a cada fuente oficial y devuelve la respuesta tal cual.

Cada función devuelve un diccionario con los bytes de la respuesta, su extensión
y los metadatos de la consulta (URL exacta, consulta SoQL, encabezados útiles).
No interpreta números: eso es de validar.py.
"""
import datetime as dt
import json
import re
import urllib.parse

from comun import ErrorFuente, ahora_utc, descargar, hoy_bogota, soql

DANE_IPC_PAGINA = "https://www.dane.gov.co/index.php/estadisticas-por-tema/precios-y-costos/indice-de-precios-al-consumidor-ipc"
# Anexo mensual de índices: la carpeta y el nombre cambian con el mes publicado (p. ej. oct2026).
DANE_IPC_PATRON = re.compile(r'href="(/files/operaciones/IPC/([a-z]{3})(\d{4})/anex-IPC-Indices-\2\3\.xlsx)"')
BANREP_TPM = ("https://suameca.banrep.gov.co/estadisticas-economicas-back/rest/"
              "estadisticaEconomicaRestService/consultaInformacionSerie?idSerie=59")


def _meta(url, encabezados, **extra):
    utiles = {k: v for k, v in encabezados.items() if k.lower() in ("last-modified", "content-type", "etag", "date")}
    return {"url": url, "hora_utc": ahora_utc().isoformat(), "encabezados": utiles, **extra}


def trm(momento=None):
    """TRM de la SFC en datos.gov.co (32sa-8pi3): los últimos 45 días, para el último valor y 30 días."""
    desde = (hoy_bogota(momento) - dt.timedelta(days=45)).isoformat()
    url = soql("32sa-8pi3", where=f"vigenciadesde >= '{desde}T00:00:00'", order="vigenciadesde DESC", limit="100")
    datos, enc = descargar(url)
    return {"datos": datos, "extension": "json", "meta": _meta(url, enc, consulta=urllib.parse.unquote(url.split("?", 1)[1]))}


def tasa_emisor(momento=None):
    """Tasa de política monetaria · Banco de la República, serie 59 (servicio REST del portal suameca)."""
    datos, enc = descargar(BANREP_TPM)
    return {"datos": datos, "extension": "json", "meta": _meta(BANREP_TPM, enc, nota="servicio del portal, no es una API documentada")}


def ipc(momento=None):
    """IPC · DANE: descubre en la página oficial el anexo de índices del último mes y lo descarga."""
    pagina, _ = descargar(DANE_IPC_PAGINA)
    enlaces = DANE_IPC_PATRON.findall(pagina.decode("utf-8", "replace"))
    if not enlaces:
        raise ErrorFuente("la página del IPC del DANE no tiene un enlace con el patrón anex-IPC-Indices-<mes><año>.xlsx")
    rutas = sorted({e[0] for e in enlaces})
    if len(rutas) != 1:
        raise ErrorFuente(f"la página del IPC del DANE tiene {len(rutas)} anexos de índices distintos: {rutas}")
    url = "https://www.dane.gov.co" + rutas[0]
    datos, enc = descargar(url)
    return {"datos": datos, "extension": "xlsx",
            "meta": _meta(url, enc, pagina=DANE_IPC_PAGINA, mes_en_url=enlaces[0][1] + enlaces[0][2])}


def cartera_sfc(momento=None):
    """Cartera SFC (rvii-eis8): solo el último corte, filtrado a renglon=5 (total por producto)."""
    url_corte = soql("rvii-eis8", select="max(fecha_corte) as ultimo")
    respuesta, _ = descargar(url_corte)
    try:
        corte = json.loads(respuesta)[0]["ultimo"]
    except (ValueError, KeyError, IndexError) as e:
        raise ErrorFuente(f"no se pudo leer el último corte de rvii-eis8: {e}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00\.000", corte):
        raise ErrorFuente(f"fecha de corte con formato inesperado: {corte!r}")
    url = soql("rvii-eis8", where=f"fecha_corte = '{corte}' AND renglon = '5'",
               order="tipo_entidad, codigo_entidad, unicap", limit="10000")
    datos, enc = descargar(url, timeout=180)
    return {"datos": datos, "extension": "json",
            "meta": _meta(url, enc, consulta=urllib.parse.unquote(url.split("?", 1)[1]), consulta_corte=urllib.parse.unquote(url_corte.split("?", 1)[1]))}


FUENTES = {"trm": trm, "tasa_emisor": tasa_emisor, "ipc": ipc, "cartera_sfc": cartera_sfc}
