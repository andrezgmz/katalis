"""Capa 3 · calcular: del formato limpio a indicadores listos para usar.

Funciones puras. La variación anual del IPC se calcula con el mismo mes del
año anterior: (índice del mes / índice del mismo mes un año antes − 1) × 100.
"""
import datetime as dt

from comun import ErrorValidacion


def trm(limpio, hoy):
    serie = [s for s in limpio["serie"] if dt.date.fromisoformat(s["vigencia_desde"]) <= hoy]
    if not serie:
        raise ErrorValidacion("trm: no hay una TRM vigente para hoy")
    ultimo = serie[-1]
    desde = (hoy - dt.timedelta(days=30)).isoformat()
    return {"fuente": "trm", "valor": ultimo["valor"], "vigencia_desde": ultimo["vigencia_desde"],
            "vigencia_hasta": ultimo["vigencia_hasta"],
            "serie_30_dias": [{"fecha": s["vigencia_desde"], "valor": s["valor"]} for s in serie if s["vigencia_desde"] >= desde]}


def tasa_emisor(limpio, hoy):
    return {"fuente": "tasa_emisor", "valor": limpio["ultimo"]["valor"], "fecha": limpio["ultimo"]["fecha"],
            "vigente_desde": limpio["cambios"][-1]["desde"]}


def ipc(limpio, hoy):
    mes = limpio["ultimo_mes"]
    anterior = f"{int(mes[:4]) - 1}{mes[4:]}"
    if anterior not in limpio["indices"]:
        raise ErrorValidacion(f"ipc: falta el índice de {anterior} para calcular la variación anual")
    indice, base = limpio["indices"][mes], limpio["indices"][anterior]
    variacion = round((indice / base - 1) * 100, 2)
    if not -5 <= variacion <= 40:
        raise ErrorValidacion(f"ipc: variación anual fuera de rango (−5 %–40 %): {variacion}")
    return {"fuente": "ipc", "mes": mes, "indice": indice, "indice_mismo_mes_anio_anterior": base,
            "variacion_anual": variacion, "fecha_publicacion": limpio["fecha_publicacion"]}


def cartera_sfc(limpio, hoy):
    # Fase 0: solo se extrae y se valida; se publica en la Fase 1.
    return {"fuente": "cartera_sfc", "corte": limpio["corte"], "total_billones": limpio["total_billones"],
            "bancos": limpio["bancos"], "publicar": False}


CALCULOS = {"trm": trm, "tasa_emisor": tasa_emisor, "ipc": ipc, "cartera_sfc": cartera_sfc}
