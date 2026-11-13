"""Capa 4 · empaquetar: arma datos/web/macro.json, el único archivo que lee la web.

Toma los indicadores vigentes (capa 3). Si una fuente falló en esta corrida, su
indicador no cambió en disco: se conserva el último valor bueno y su última
consulta exitosa. La etiqueta «desactualizado» la decide el sitio al construir.
"""
from comun import INDICADORES, WEB, ahora_utc, escribir_json, leer_json

PULSO = {
    "trm": {"nombre": "TRM", "unidad": "pesos por dólar", "fuente": "Superintendencia Financiera",
            "url_fuente": "https://www.datos.gov.co/d/32sa-8pi3"},
    "tasa_emisor": {"nombre": "Tasa del Emisor", "unidad": "% efectivo anual", "fuente": "Banco de la República",
                    "url_fuente": "https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/59/tasas_interes_politica_monetaria"},
    "inflacion": {"nombre": "Inflación anual", "unidad": "% anual", "fuente": "DANE",
                  "url_fuente": "https://www.dane.gov.co/index.php/estadisticas-por-tema/precios-y-costos/indice-de-precios-al-consumidor-ipc"},
}


def empaquetar(exitos, momento=None):
    """exitos: {fuente: True/False} de esta corrida. Devuelve el paquete escrito."""
    momento = momento or ahora_utc()
    anterior = (leer_json(WEB / "macro.json", {}) or {}).get("indicadores", {})
    salida = {}

    def base(clave, ok_fuente):
        previo = anterior.get(clave, {})
        return {**PULSO[clave], "ultima_consulta_ok": momento.isoformat() if ok_fuente else previo.get("ultima_consulta_ok")}

    t = leer_json(INDICADORES / "trm.json")
    salida["trm"] = {**base("trm", exitos.get("trm")), **({"valor": t["valor"], "fecha": t["vigencia_desde"],
                     "fecha_publicacion": t["vigencia_desde"]} if t else {"valor": None})}

    e = leer_json(INDICADORES / "tasa_emisor.json")
    salida["tasa_emisor"] = {**base("tasa_emisor", exitos.get("tasa_emisor")), **({"valor": e["valor"], "fecha": e["fecha"],
                             "vigente_desde": e["vigente_desde"]} if e else {"valor": None})}

    i = leer_json(INDICADORES / "ipc.json")
    salida["inflacion"] = {**base("inflacion", exitos.get("ipc")), **({"valor": i["variacion_anual"], "mes": i["mes"],
                           "fecha_publicacion": i["fecha_publicacion"][:10]} if i else {"valor": None})}

    paquete = {"generado": momento.isoformat(),
               "nota": "Lo genera scripts/tuberia/empaquetar.py; no se edita a mano.",
               "indicadores": salida}
    escribir_json(WEB / "macro.json", paquete)
    return paquete
