"""Sondeo de fuentes macro nuevas (Etapa A2 del plan de la web, 14-nov-2026).

SOLO LECTURA: consulta cada fuente candidata una vez, revisa forma, fuente declarada y fechas,
y escribe un resumen. No publica nada, no escribe en datos/ ni cambia la tubería.

Uso:
    python scripts/sondeo/sondear.py [--salida resumen.json]

En GitHub Actions lo corre .github/workflows/sondeo-fuentes-macro.yml (permiso de solo lectura).
El resumen va a la salida estándar, a $GITHUB_STEP_SUMMARY (si existe) y, con --salida, a un JSON.
Termina en 1 si alguna fuente no respondió o no pasó los controles mínimos.

Fuera de la sonda a propósito:
- COLCAP y cualquier dato de la Bolsa de Valores de Colombia (BVC): la BVC es privada y licencia sus
  datos; el Banco de la República lo publica con «Fuente: Bolsa de Valores de Colombia - BVC», y su
  aviso legal prohíbe reproducir información de fuentes externas al Banco. No se consulta.
"""
import argparse
import datetime as dt
import io
import json
import os
import pathlib
import sys
import time
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tuberia"))
from comun import BOGOTA, ErrorFuente, ahora_utc, descargar, hoy_bogota, sha256, soql  # noqa: E402

BANREP_SERIE = ("https://suameca.banrep.gov.co/estadisticas-economicas-back/rest/"
                "estadisticaEconomicaRestService/consultaInformacionSerie?idSerie={id}")
BANREP_FICHA = "https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/{id}"
DANE_ARCHIVOS = "https://www.dane.gov.co/files/operaciones/"
MESES_URL = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
TRIMESTRES = ["I", "II", "III", "IV"]

# Fuentes que el aviso legal del Banco no deja reproducir (información externa al Banco).
FUENTES_EXTERNAS = ("bloomberg", "refinitiv", "bolsa de valores", "bvc", "reuters")

# Series del Banco de la República a sondear: (clave, idSerie, uso)
#   uso «candidata»: fuente propia del Banco, se podría publicar.
#   uso «contraste»: la fuente primaria es otra entidad (DANE); solo para validar, no para publicar.
BANREP = [
    ("ibr_overnight", 241, "candidata"),
    ("ibr_1_mes", 242, "candidata"),
    ("dtf_90_semanal", 65, "candidata"),
    ("colocacion_total_semanal", 15110, "candidata"),
    ("colocacion_total_mensual", 15125, "candidata"),
    ("desempleo_banrep", 15312, "contraste"),
    ("pib_real_trimestral_banrep", 15271, "contraste"),
]

# Conjuntos de datos.gov.co (Superintendencia Financiera): (clave, recurso, columna de fecha)
SOCRATA = [
    ("sfc_captacion_mercado_monetario", "axk9-g2nh", "fechacorte"),
    ("sfc_colocacion_ultimos_2_meses", "qzsc-9esp", "fecha_corte"),
]


def fuente_permitida(fuente):
    """True si la fuente declarada por el Banco es el propio Banco (sin datos de terceros privados)."""
    texto = (fuente or "").lower()
    if any(x in texto for x in FUENTES_EXTERNAS):
        return False
    return texto.removeprefix("fuente:").strip().startswith("banco de la rep")


def separar_futuras(serie, hoy):
    """Divide [(fecha, valor)] en vigentes (<= hoy) y futuras (> hoy). Misma regla que tasa_emisor (PR #8)."""
    return [p for p in serie if p[0] <= hoy], [p for p in serie if p[0] > hoy]


def candidatos_geih(hoy, n=4):
    """Nombres de anexo GEIH de los últimos n meses de referencia (el DANE publica el mes anterior)."""
    nombres, anio, mes = [], hoy.year, hoy.month
    for _ in range(n):
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
        nombres.append(f"GEIH/anex-GEIH-{MESES_URL[mes - 1]}{anio}.xlsx")
    return nombres


def candidatos_pib(hoy, n=4):
    """Nombres de anexo de PIB a precios constantes de los últimos n trimestres."""
    nombres, anio, trim = [], hoy.year, (hoy.month - 1) // 3 + 1
    for _ in range(n):
        trim -= 1
        if trim == 0:
            anio, trim = anio - 1, 4
        nombres.append(f"PIB/anex-ProduccionConstantes-{TRIMESTRES[trim - 1]}trim{anio}.xlsx")
    return nombres


def _cronometro(funcion):
    inicio = time.monotonic()
    resultado = funcion()
    return resultado, round(time.monotonic() - inicio, 1)


def sondear_banrep(clave, id_serie, uso, hoy):
    url = BANREP_SERIE.format(id=id_serie)
    (datos, _), segundos = _cronometro(lambda: descargar(url))
    cuerpo = json.loads(datos)
    if not isinstance(cuerpo, list) or len(cuerpo) != 1:
        raise ErrorFuente(f"se esperaba una serie y llegaron {len(cuerpo) if isinstance(cuerpo, list) else type(cuerpo).__name__}")
    s = cuerpo[0]
    serie = sorted((dt.datetime.fromtimestamp(t / 1000, BOGOTA).date(), float(v)) for t, v in s["data"])
    vigentes, futuras = separar_futuras(serie, hoy)
    if not vigentes:
        raise ErrorFuente("todas las filas tienen fecha futura")
    fecha, valor = vigentes[-1]
    return {
        "clave": clave, "entidad": "Banco de la República", "uso": uso, "url": url,
        "ficha": BANREP_FICHA.format(id=id_serie), "nombre": s.get("nombre"), "fuente_declarada": s.get("fuente"),
        "fuente_propia_del_banco": fuente_permitida(s.get("fuente")),
        "periodicidad": s.get("descripcionPeriodicidad"), "unidad": s.get("unidad"),
        "ficha_tecnica": s.get("fichaTecnica"), "ultimo_cargue": s.get("fechaUltimoCargue"),
        "filas": len(serie), "desde": serie[0][0].isoformat(), "ultima_fecha_vigente": fecha.isoformat(),
        "ultimo_valor": valor, "filas_futuras": len(futuras),
        "ultima_fecha_publicada": serie[-1][0].isoformat(), "bytes": len(datos), "sha256": sha256(datos),
        "segundos": segundos,
    }


def sondear_socrata(clave, recurso, columna, hoy):
    meta_url = f"https://www.datos.gov.co/api/views/{recurso}.json"
    (meta_bytes, _), _ = _cronometro(lambda: descargar(meta_url))
    meta = json.loads(meta_bytes)
    consulta = soql(recurso, select=f"max({columna}) as ultimo")
    (datos, _), segundos = _cronometro(lambda: descargar(consulta, timeout=240))
    ultimo = json.loads(datos)[0]["ultimo"]
    consulta_n = soql(recurso, select="count(*) as n", where=f"{columna} = '{ultimo}'")
    (datos_n, _), _ = _cronometro(lambda: descargar(consulta_n, timeout=240))
    datos_info = meta.get("metadata", {}).get("custom_fields", {}).get("Información de Datos", {})
    return {
        "clave": clave, "entidad": meta.get("attribution"), "uso": "candidata", "url": consulta,
        "ficha": f"https://www.datos.gov.co/d/{recurso}", "nombre": meta.get("name"),
        "licencia": (meta.get("license") or {}).get("name"), "licencia_enlace": (meta.get("license") or {}).get("termsLink"),
        "frecuencia_declarada": datos_info.get("Frecuencia de Actualización"),
        "filas_actualizadas_utc": dt.datetime.fromtimestamp(meta.get("rowsUpdatedAt", 0), dt.timezone.utc).isoformat(),
        "ultimo_corte": ultimo[:10], "filas_ultimo_corte": int(json.loads(datos_n)[0]["n"]),
        "rezago_dias": (hoy - dt.date.fromisoformat(ultimo[:10])).days,
        "columnas": [c["fieldName"] for c in meta.get("columns", [])], "segundos": segundos,
    }


def sondear_dane(clave, candidatos, hoy):
    """Prueba los nombres de anexo del más reciente al más viejo; se queda con el primero que existe."""
    intentos = []
    for nombre in candidatos:
        url = DANE_ARCHIVOS + nombre
        try:
            (datos, encabezados), segundos = _cronometro(lambda: descargar(url, intentos=1))
        except ErrorFuente as e:
            intentos.append(f"{nombre}: {e}")
            continue
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            libro = z.read("xl/workbook.xml").decode("utf-8", "replace")
        hojas = [h.split('"')[0] for h in libro.split('<sheet name="')[1:]]
        modificado = encabezados.get("Last-Modified")
        publicado = (dt.datetime.strptime(modificado, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=dt.timezone.utc)
                     .astimezone(BOGOTA).isoformat() if modificado else None)
        return {
            "clave": clave, "entidad": "DANE", "uso": "candidata", "url": url, "archivo": nombre,
            "intentos_previos": intentos, "last_modified_bogota": publicado, "bytes": len(datos),
            "sha256": sha256(datos), "hojas": hojas, "segundos": segundos,
        }
    raise ErrorFuente("ningún anexo encontrado: " + " | ".join(intentos))


OMITIDAS = [{
    "clave": "colcap", "entidad": "Bolsa de Valores de Colombia (privada)", "uso": "omitida",
    "motivo": ("No se consulta. El Banco de la República lo publica (idSerie 6) con «Fuente: Bolsa de Valores de "
               "Colombia - BVC», y su aviso legal dice que la información de fuentes externas al Banco «no puede ser "
               "reproducida o divulgada». La BVC licencia sus datos: no se consulta de forma automática."),
}]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--salida", help="ruta de un JSON con el resumen (fuera del repositorio)")
    args = parser.parse_args(argv)
    momento = ahora_utc()
    hoy = hoy_bogota(momento)
    resultados = []
    trabajos = ([(c, lambda c=c, i=i, u=u: sondear_banrep(c, i, u, hoy)) for c, i, u in BANREP]
                + [(c, lambda c=c, r=r, k=k: sondear_socrata(c, r, k, hoy)) for c, r, k in SOCRATA]
                + [("dane_desempleo_geih", lambda: sondear_dane("dane_desempleo_geih", candidatos_geih(hoy), hoy)),
                   ("dane_pib_trimestral", lambda: sondear_dane("dane_pib_trimestral", candidatos_pib(hoy), hoy))])
    for clave, trabajo in trabajos:
        try:
            r = trabajo()
            r["resultado"] = "ok"
            if r.get("uso") == "candidata" and r.get("fuente_propia_del_banco") is False:
                r["resultado"] = "fuente externa al Banco: no publicar"
        except Exception as e:  # una fuente que falla no tumba las demás
            r = {"clave": clave, "resultado": "falla", "error": f"{type(e).__name__}: {e}"}
        resultados.append(r)
    resultados += [dict(o, resultado="omitida a propósito") for o in OMITIDAS]

    resumen = {"momento_utc": momento.isoformat(), "hoy_bogota": hoy.isoformat(), "fuentes": resultados}
    lineas = [f"## Sondeo de fuentes macro · {momento.isoformat()} (hoy en Bogotá: {hoy})", "",
              "| Serie | Resultado | Último dato | Detalle |", "|---|---|---|---|"]
    for r in resultados:
        if "ultima_fecha_vigente" in r:
            ultimo = f"{r['ultima_fecha_vigente']} · {r['ultimo_valor']}"
            detalle = (f"{r['periodicidad']} · fuente: {r['fuente_declarada']} · filas futuras: {r['filas_futuras']} "
                       f"(última publicada {r['ultima_fecha_publicada']}) · {r['segundos']} s")
        elif "ultimo_corte" in r:
            ultimo = f"corte {r['ultimo_corte']} ({r['filas_ultimo_corte']} filas)"
            detalle = f"rezago {r['rezago_dias']} días · licencia: {r['licencia']} · {r['segundos']} s"
        elif "archivo" in r:
            ultimo = r["archivo"]
            detalle = f"Last-Modified {r['last_modified_bogota']} · {r['bytes']} bytes · hojas: {', '.join(r['hojas'][:6])}"
        else:
            ultimo, detalle = "—", r.get("motivo") or r.get("error", "")
        lineas.append(f"| {r['clave']} | {r['resultado']} | {ultimo} | {detalle} |")
    texto = "\n".join(lineas) + "\n"
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto)
    if args.salida:
        pathlib.Path(args.salida).write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    fallas = [r["clave"] for r in resultados if r["resultado"] == "falla"]
    print(f"Fuentes con falla: {len(fallas)} {fallas if fallas else ''}")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
