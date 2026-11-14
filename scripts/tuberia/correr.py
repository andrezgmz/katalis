"""Corre la tubería: extraer → validar → calcular → revisar saltos → aplicar (crudo, limpio, indicadores, web).

Uso:
  python scripts/tuberia/correr.py                       # todo de una vez (uso local); los saltos anómalos se retienen
  python scripts/tuberia/correr.py --etapa extraer  --resultados DIR [--probar-aprobacion]
  python scripts/tuberia/correr.py --etapa aplicar  --resultados DIR [--con-anomalias] [--modo M] [--resumen RUTA]

Etapa «extraer»: pide a cada fuente, valida, calcula y compara con el último valor bueno
publicado (saltos.py). No toca datos/: deja todo en DIR (respuestas, formato limpio,
indicadores, saltos y las respuestas rechazadas).
Etapa «aplicar»: escribe en datos/ lo que extraer dejó en DIR.
  - Sin --con-anomalias: una fuente con salto anómalo queda «retenida» (no avanza; la web
    conserva su último valor bueno).
  - Con --con-anomalias: también avanza la fuente con salto. El workflow lo hace en una copia
    aparte y solo la publica si Andrés aprueba (environment «datos-anomalos»).
Las dos variantes salen de la misma extracción: lo aprobado es exactamente lo que se verificó.
Siempre escribe una línea por fuente en datos/registro.jsonl. Siempre termina con código 0:
el workflow decide el color con el resumen.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
import tempfile
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import calcular  # noqa: E402
import extraer  # noqa: E402
import saltos  # noqa: E402
import validar  # noqa: E402
from comun import (INDICADORES, LIMPIO, ErrorFuente, ErrorValidacion, ahora_utc, corrida_id,  # noqa: E402
                   escribir_json, guardar_crudo, hoy_bogota, leer_json, registrar, sha256, vencimiento_cert_banrep)
from empaquetar import empaquetar  # noqa: E402

AVISO_CERT_DIAS = 30
PRUEBA_PUERTA = "prueba de la puerta de aprobación (lanzada a mano con probar_aprobacion): el dato es el real"


def _filas(limpio):
    return (len(limpio.get("serie", [])) or len(limpio.get("indices", {})) or limpio.get("filas")
            or len(limpio.get("cambios", [])))


def extraer_fuente(fuente, momento, carpeta, probar_aprobacion=False):
    """Extrae, valida, calcula y revisa saltos. Deja todo en carpeta/<fuente>/. Devuelve el resultado."""
    hoy = hoy_bogota(momento)
    destino = carpeta / fuente
    destino.mkdir(parents=True, exist_ok=True)
    linea = {"fuente": fuente, "hora_utc": momento.isoformat()}
    resultado = {"fuente": fuente, "linea": linea}
    try:
        respuesta = extraer.FUENTES[fuente](momento)
        datos, meta = respuesta["datos"], respuesta["meta"]
        linea.update(url=meta["url"], consulta=meta.get("consulta"), sha256=sha256(datos), bytes=len(datos))
        try:
            limpio = validar.VALIDADORES[fuente](datos, meta, hoy)
            indicador = calcular.CALCULOS[fuente](limpio, hoy)
        except ErrorValidacion:
            (destino / f"rechazada.{respuesta['extension']}").write_bytes(datos)
            escribir_json(destino / "rechazada.json", meta)
            raise
        anomalias = saltos.REVISIONES[fuente](limpio, indicador, leer_json(LIMPIO / f"{fuente}.json"),
                                              leer_json(INDICADORES / f"{fuente}.json"))
        if probar_aprobacion and fuente == "trm":
            anomalias.append(PRUEBA_PUERTA)
        (destino / f"respuesta.{respuesta['extension']}").write_bytes(datos)
        resultado.update(estado="ok", extension=respuesta["extension"], meta=meta, limpio=limpio,
                         indicador=indicador, anomalias=anomalias)
        linea["filas"] = _filas(limpio)
        if "filas_futuras_ignoradas" in limpio:  # solo tasa_emisor
            linea["filas_futuras_ignoradas"] = limpio["filas_futuras_ignoradas"]
    except (ErrorFuente, ErrorValidacion) as e:
        resultado["estado"] = "falla"
        linea.update(resultado="falla", error=f"{type(e).__name__}: {e}")
    except Exception as e:  # un error inesperado en una fuente no tumba las demás
        resultado["estado"] = "falla"
        linea.update(resultado="falla", error=f"inesperado {type(e).__name__}: {e}",
                     traza=traceback.format_exc(limit=3))
    escribir_json(destino / "resultado.json", resultado)
    return resultado


def etapa_extraer(carpeta, fuentes, probar_aprobacion=False):
    carpeta.mkdir(parents=True, exist_ok=True)
    momento = ahora_utc()
    resultados = [extraer_fuente(f, momento, carpeta, probar_aprobacion) for f in fuentes]
    indice = {"momento": momento.isoformat(), "corrida": corrida_id(), "fuentes": fuentes,
              "anomalias": {r["fuente"]: r["anomalias"] for r in resultados if r.get("anomalias")}}
    escribir_json(carpeta / "extraccion.json", indice)
    for r in resultados:
        detalle = r["linea"].get("error") or ("SALTO: " + " | ".join(r["anomalias"]) if r["anomalias"] else "normal")
        print(f"{'OK   ' if r['estado'] == 'ok' else 'FALLA'} {r['fuente']:12} {r['linea'].get('filas', '')!s:>6} {detalle}")
    return indice


def etapa_aplicar(carpeta, modo, con_anomalias=False, resumen_ruta=None):
    indice = leer_json(carpeta / "extraccion.json")
    momento = dt.datetime.fromisoformat(indice["momento"])
    lineas, retenidas = [], []
    for fuente in indice["fuentes"]:
        r = leer_json(carpeta / fuente / "resultado.json")
        linea = {"corrida": indice["corrida"], "modo": modo, **r["linea"]}
        if r["estado"] == "ok":
            if r["anomalias"]:
                linea["saltos"] = r["anomalias"]
            if r["anomalias"] and not con_anomalias:
                linea["resultado"] = "retenido"
                retenidas.append({"fuente": fuente, "motivos": r["anomalias"]})
            else:
                datos = (carpeta / fuente / f"respuesta.{r['extension']}").read_bytes()
                archivo, nuevo = guardar_crudo(fuente, datos, r["extension"], r["meta"], momento)
                escribir_json(LIMPIO / f"{fuente}.json", {**r["limpio"], "crudo": archivo})
                escribir_json(INDICADORES / f"{fuente}.json", {**r["indicador"], "crudo": archivo})
                linea.update(resultado="ok", crudo=archivo, crudo_estado="nuevo" if nuevo else "sin cambios")
                if r["anomalias"]:
                    linea["aprobacion"] = "publicado con la aprobación de Andrés (environment datos-anomalos)"
        registrar(linea)
        lineas.append(linea)
        detalle = linea.get("error") or (f"retenido: {' | '.join(linea['saltos'])}" if linea["resultado"] == "retenido"
                                         else f"{linea['crudo_estado']}: {linea['crudo']}")
        print(f"{linea['resultado'].upper():9} {fuente:12} {detalle}")

    paquete = empaquetar({l["fuente"]: l["resultado"] == "ok" for l in lineas}, momento)

    avisos = []
    vence = vencimiento_cert_banrep()
    dias = (vence - momento).days
    if dias <= AVISO_CERT_DIAS:
        avisos.append({"titulo": "Certificado por vencer: GeoTrust EV RSA CA G2",
                       "detalle": f"El intermedio guardado para el Banco de la República vence el {vence:%Y-%m-%d} "
                                  f"(faltan {dias} días). Ver scripts/tuberia/FUENTES.md."})
    resumen = {"corrida": indice["corrida"], "modo": modo, "corte": hoy_bogota(momento).isoformat(),
               "con_anomalias": con_anomalias,
               "fallas": [{"fuente": l["fuente"], "error": l["error"]} for l in lineas if l["resultado"] == "falla"],
               "anomalias": retenidas if not con_anomalias else
                            [{"fuente": f, "motivos": m} for f, m in indice["anomalias"].items()],
               "avisos": avisos, "cert_banrep_vence": vence.date().isoformat(), "macro": paquete["indicadores"]}
    if resumen_ruta:
        pathlib.Path(resumen_ruta).write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Fuentes con falla: {len(resumen['fallas'])} · con salto anómalo: {len(indice['anomalias'])} · "
          f"certificado del Banco vence en {dias} días")
    return resumen


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--etapa", choices=["todo", "extraer", "aplicar"], default="todo")
    p.add_argument("--resultados", help="carpeta de trabajo entre «extraer» y «aplicar»")
    p.add_argument("--modo", choices=["prueba", "publicacion"], default="prueba")
    p.add_argument("--resumen")
    p.add_argument("--con-anomalias", action="store_true")
    p.add_argument("--probar-aprobacion", action="store_true")
    p.add_argument("--fuentes", default=",".join(extraer.FUENTES))
    args = p.parse_args()
    if args.etapa != "todo" and not args.resultados:
        p.error("--resultados es obligatorio con --etapa extraer o aplicar")
    carpeta = pathlib.Path(args.resultados or tempfile.mkdtemp(prefix="tuberia-"))
    if args.etapa in ("todo", "extraer"):
        etapa_extraer(carpeta, args.fuentes.split(","), args.probar_aprobacion)
    if args.etapa in ("todo", "aplicar"):
        etapa_aplicar(carpeta, args.modo, args.con_anomalias, args.resumen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
