"""Capa 2 · validar: convierte la respuesta cruda en el formato común (limpio) o la rechaza.

Si un control falla se lanza ErrorValidacion con un mensaje claro: esa fuente no
avanza y la web conserva su último valor bueno. Son funciones puras (sin red ni
disco) para poder probarlas con casos buenos y malos (pruebas/test_validar.py).
"""
import datetime as dt
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile

from comun import BOGOTA, ErrorValidacion

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]
MESES_URL = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _json(datos):
    try:
        return json.loads(datos)
    except ValueError as e:
        raise ErrorValidacion(f"la respuesta no es JSON: {e}")


def _columnas(fila, esperadas, fuente):
    faltan = sorted(set(esperadas) - set(fila))
    if faltan:
        raise ErrorValidacion(f"{fuente}: cambió la estructura, faltan columnas {faltan}; llegaron {sorted(fila)}")


def _numero(texto, campo, fuente):
    try:
        return float(texto)
    except (TypeError, ValueError):
        raise ErrorValidacion(f"{fuente}: «{campo}» no es un número: {texto!r}")


def _fecha_soql(texto, campo, fuente):
    if not isinstance(texto, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00\.000", texto):
        raise ErrorValidacion(f"{fuente}: «{campo}» con formato inesperado: {texto!r}")
    return dt.date.fromisoformat(texto[:10])


# ---------------------------------------------------------------- TRM (SFC · 32sa-8pi3)
def trm(datos, meta, hoy):
    filas = _json(datos)
    if not isinstance(filas, list) or not filas:
        raise ErrorValidacion("trm: la respuesta no trae filas")
    serie = []
    for f in filas:
        if not isinstance(f, dict):
            raise ErrorValidacion("trm: fila con tipo inesperado")
        _columnas(f, ["valor", "unidad", "vigenciadesde", "vigenciahasta"], "trm")
        if f["unidad"] != "COP":
            raise ErrorValidacion(f"trm: unidad inesperada {f['unidad']!r}")
        valor = _numero(f["valor"], "valor", "trm")
        if not 2000 <= valor <= 8000:
            raise ErrorValidacion(f"trm: valor fuera de rango (2.000–8.000): {valor}")
        desde = _fecha_soql(f["vigenciadesde"], "vigenciadesde", "trm")
        hasta = _fecha_soql(f["vigenciahasta"], "vigenciahasta", "trm")
        if desde > hoy + dt.timedelta(days=1):
            raise ErrorValidacion(f"trm: vigencia futura más de 1 día: {desde}")
        if hasta < desde:
            raise ErrorValidacion(f"trm: vigencia al revés: {desde} → {hasta}")
        serie.append({"vigencia_desde": desde.isoformat(), "vigencia_hasta": hasta.isoformat(), "valor": valor})
    serie.sort(key=lambda s: s["vigencia_desde"])
    if len({s["vigencia_desde"] for s in serie}) != len(serie):
        raise ErrorValidacion("trm: hay fechas de vigencia repetidas")
    return {"fuente": "trm", "serie": serie}


# ------------------------------------------------- Tasa de política monetaria (BanRep · 59)
def tasa_emisor(datos, meta, hoy):
    cuerpo = _json(datos)
    if not isinstance(cuerpo, list) or len(cuerpo) != 1 or not isinstance(cuerpo[0], dict):
        raise ErrorValidacion("tasa_emisor: se esperaba una lista con una serie")
    s = cuerpo[0]
    _columnas(s, ["id", "nombre", "unidadCorta", "fuente", "data", "fechaUltimoCargue"], "tasa_emisor")
    if s["id"] != 59 or s["unidadCorta"] != "%":
        raise ErrorValidacion(f"tasa_emisor: serie o unidad inesperada (id={s['id']!r}, unidad={s['unidadCorta']!r})")
    datos_serie = s["data"]
    if not isinstance(datos_serie, list) or len(datos_serie) < 100:
        raise ErrorValidacion("tasa_emisor: la historia llegó vacía o incompleta")
    serie = []
    for par in datos_serie:
        if not (isinstance(par, list) and len(par) == 2 and isinstance(par[0], int) and isinstance(par[1], (int, float))):
            raise ErrorValidacion(f"tasa_emisor: dato con formato inesperado: {par!r}")
        fecha = dt.datetime.fromtimestamp(par[0] / 1000, BOGOTA).date()
        serie.append((fecha, float(par[1])))
    serie.sort()
    fecha, valor = serie[-1]
    if not 0 <= valor <= 30:
        raise ErrorValidacion(f"tasa_emisor: valor fuera de rango (0 %–30 %): {valor}")
    if fecha > hoy + dt.timedelta(days=1):
        raise ErrorValidacion(f"tasa_emisor: último dato con fecha futura: {fecha}")
    # Los cambios de tasa (solo cuando cambia): pocos datos, suficientes para la historia.
    cambios = [{"desde": f.isoformat(), "valor": v} for i, (f, v) in enumerate(serie) if i == 0 or v != serie[i - 1][1]]
    return {"fuente": "tasa_emisor", "ultimo": {"fecha": fecha.isoformat(), "valor": valor},
            "cambios": cambios, "fuente_declarada": s["fuente"], "fecha_ultimo_cargue": s["fechaUltimoCargue"]}


# --------------------------------------------------------------------------- IPC (DANE)
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _celdas_xlsx(datos):
    """Lee la primera hoja de un xlsx con la librería estándar: {(fila, columna): texto}."""
    try:
        z = zipfile.ZipFile(io.BytesIO(datos))
        compartidos = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                compartidos.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
        hoja = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise ErrorValidacion(f"ipc: el anexo no es un xlsx legible: {e}")
    celdas = {}
    for c in hoja.iter("{%s}c" % NS["m"]):
        v = c.find("m:v", NS)
        if v is None or v.text is None:
            continue
        m = re.fullmatch(r"([A-Z]+)(\d+)", c.get("r", ""))
        if not m:
            continue
        col = 0
        for letra in m.group(1):
            col = col * 26 + ord(letra) - 64
        texto = compartidos[int(v.text)] if c.get("t") == "s" else v.text
        celdas[(int(m.group(2)), col)] = texto.strip()
    return celdas


def ipc(datos, meta, hoy):
    celdas = _celdas_xlsx(datos)
    encabezado = [f for (f, c), t in celdas.items() if c == 1 and t == "Mes"]
    if len(encabezado) != 1:
        raise ErrorValidacion("ipc: cambió la estructura, no hay una sola fila «Mes» en la columna A")
    fila_mes = encabezado[0]
    if not any("Base Diciembre de 2018 = 100" in t for t in celdas.values()):
        raise ErrorValidacion("ipc: cambió la base del índice (se esperaba «Base Diciembre de 2018 = 100»)")
    anios = {}
    for (f, c), t in celdas.items():
        if f == fila_mes and c > 1:
            if not re.fullmatch(r"\d{4}", t):
                raise ErrorValidacion(f"ipc: encabezado de año inesperado: {t!r}")
            anios[c] = int(t)
    if len(anios) < 3 or sorted(anios.values()) != list(range(min(anios.values()), max(anios.values()) + 1)):
        raise ErrorValidacion(f"ipc: los años del encabezado no son consecutivos: {sorted(anios.values())}")
    nombres = [celdas.get((fila_mes + i, 1)) for i in range(1, 13)]
    if nombres != MESES:
        raise ErrorValidacion(f"ipc: cambió la estructura, los meses no son Enero…Diciembre: {nombres}")
    indices = {}
    for i in range(12):
        for c, anio in anios.items():
            t = celdas.get((fila_mes + 1 + i, c))
            if t is not None:
                valor = _numero(t, f"{MESES[i]} {anio}", "ipc")
                if valor <= 0:
                    raise ErrorValidacion(f"ipc: índice no positivo en {MESES[i]} {anio}: {valor}")
                indices[f"{anio}-{i + 1:02d}"] = round(valor, 6)
    if not indices:
        raise ErrorValidacion("ipc: la tabla no trae índices")
    ultimo = max(indices)
    # El mes del archivo (en su URL) debe ser el último mes con dato.
    mes_url = meta.get("mes_en_url", "")
    esperado = MESES_URL[int(ultimo[5:]) - 1] + ultimo[:4]
    if mes_url and mes_url != esperado:
        raise ErrorValidacion(f"ipc: el archivo dice {mes_url} pero su último dato es {ultimo}")
    publicado = meta.get("encabezados", {}).get("Last-Modified") or meta.get("encabezados", {}).get("last-modified")
    if not publicado:
        raise ErrorValidacion("ipc: el DANE no informó la fecha de publicación (Last-Modified)")
    fecha_pub = dt.datetime.strptime(publicado, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=dt.timezone.utc)
    if fecha_pub.astimezone(BOGOTA).date() > hoy + dt.timedelta(days=1):
        raise ErrorValidacion(f"ipc: fecha de publicación futura: {publicado}")
    return {"fuente": "ipc", "base": "Diciembre de 2018 = 100", "indices": dict(sorted(indices.items())),
            "ultimo_mes": ultimo, "fecha_publicacion": fecha_pub.isoformat()}


# -------------------------------------------------------- Cartera SFC (rvii-eis8, renglon 5)
COLUMNAS_CARTERA = ["tipo_entidad", "codigo_entidad", "nombreentidad", "fecha_corte", "unicap", "descrip_uc",
                    "renglon", "desc_renglon", "_1_saldo_de_la_cartera_a"]


def cartera_sfc(datos, meta, hoy):
    filas = _json(datos)
    if not isinstance(filas, list) or not filas:
        raise ErrorValidacion("cartera_sfc: la respuesta no trae filas")
    if len(filas) >= 10000:
        raise ErrorValidacion("cartera_sfc: la consulta llegó al límite de filas; el corte podría estar incompleto")
    cortes, total, bancos = set(), 0.0, set()
    for f in filas:
        if not isinstance(f, dict):
            raise ErrorValidacion("cartera_sfc: fila con tipo inesperado")
        _columnas(f, COLUMNAS_CARTERA, "cartera_sfc")
        if f["renglon"] != "5":
            raise ErrorValidacion(f"cartera_sfc: llegó un renglón distinto de 5: {f['renglon']!r}")
        cortes.add(_fecha_soql(f["fecha_corte"], "fecha_corte", "cartera_sfc"))
        total += _numero(f["_1_saldo_de_la_cartera_a"], "_1_saldo_de_la_cartera_a", "cartera_sfc")
        if f["tipo_entidad"] == "1":
            bancos.add(f["codigo_entidad"])
    if len(cortes) != 1:
        raise ErrorValidacion(f"cartera_sfc: se esperaba un solo corte y llegaron {sorted(map(str, cortes))}")
    billones = total / 1e12
    if not 500 <= billones <= 2000:
        raise ErrorValidacion(f"cartera_sfc: total fuera de rango (500–2.000 billones): {billones:,.1f}")
    if len(bancos) <= 20:
        raise ErrorValidacion(f"cartera_sfc: solo {len(bancos)} bancos en el corte (se esperan más de 20)")
    return {"fuente": "cartera_sfc", "corte": next(iter(cortes)).isoformat(), "filas": len(filas),
            "total_billones": round(billones, 3), "bancos": len(bancos)}


VALIDADORES = {"trm": trm, "tasa_emisor": tasa_emisor, "ipc": ipc, "cartera_sfc": cartera_sfc}
