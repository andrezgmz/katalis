"""Corre la tubería completa: extraer → validar → calcular → empaquetar.

Uso:  python scripts/tuberia/correr.py [--modo prueba|publicacion] [--resumen RUTA] [--rechazados CARPETA]

Cada fuente avanza sola: si una falla, las demás siguen y la web conserva el
último valor bueno de la que falló. Solo una fuente validada deja archivos en
datos/ (crudo, limpio, indicadores); la respuesta rechazada va a --rechazados
(en GitHub Actions se sube como artifact, no al repositorio).
Siempre escribe una línea por fuente en datos/registro.jsonl.
El commit a main y los issues los hace el workflow, solo en modo publicación.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import calcular  # noqa: E402
import extraer  # noqa: E402
import validar  # noqa: E402
from comun import (INDICADORES, LIMPIO, RAIZ, ErrorFuente, ErrorValidacion, ahora_utc, corrida_id,  # noqa: E402
                   escribir_json, guardar_crudo, hoy_bogota, registrar, sha256, vencimiento_cert_banrep)
from empaquetar import empaquetar  # noqa: E402

AVISO_CERT_DIAS = 30


def correr_fuente(fuente, momento, rechazados):
    hoy = hoy_bogota(momento)
    linea = {"fuente": fuente, "hora_utc": momento.isoformat()}
    try:
        respuesta = extraer.FUENTES[fuente](momento)
        datos, meta = respuesta["datos"], respuesta["meta"]
        linea.update(url=meta["url"], consulta=meta.get("consulta"), sha256=sha256(datos), bytes=len(datos))
        try:
            limpio = validar.VALIDADORES[fuente](datos, meta, hoy)
            indicador = calcular.CALCULOS[fuente](limpio, hoy)
        except ErrorValidacion:
            if rechazados:
                carpeta = pathlib.Path(rechazados) / fuente
                carpeta.mkdir(parents=True, exist_ok=True)
                (carpeta / f"respuesta.{respuesta['extension']}").write_bytes(datos)
                (carpeta / "consulta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            raise
        archivo, nuevo = guardar_crudo(fuente, datos, respuesta["extension"], meta, momento)
        escribir_json(LIMPIO / f"{fuente}.json", {**limpio, "crudo": archivo})
        escribir_json(INDICADORES / f"{fuente}.json", {**indicador, "crudo": archivo})
        filas = (len(limpio.get("serie", [])) or len(limpio.get("indices", {})) or limpio.get("filas")
                 or len(limpio.get("cambios", [])))
        linea.update(resultado="ok", filas=filas, crudo=archivo,
                     crudo_estado="nuevo" if nuevo else "sin cambios")
    except (ErrorFuente, ErrorValidacion) as e:
        linea.update(resultado="falla", error=f"{type(e).__name__}: {e}")
    except Exception as e:  # un error inesperado en una fuente no tumba las demás
        linea.update(resultado="falla", error=f"inesperado {type(e).__name__}: {e}",
                     traza=traceback.format_exc(limit=3))
    return linea


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modo", choices=["prueba", "publicacion"], default="prueba")
    p.add_argument("--resumen")
    p.add_argument("--rechazados")
    p.add_argument("--fuentes", default=",".join(extraer.FUENTES))
    args = p.parse_args()

    momento, corrida = ahora_utc(), corrida_id()
    lineas = []
    for fuente in args.fuentes.split(","):
        linea = {"corrida": corrida, "modo": args.modo, **correr_fuente(fuente, momento, args.rechazados)}
        registrar(linea)
        lineas.append(linea)
        estado = "OK   " if linea["resultado"] == "ok" else "FALLA"
        detalle = linea.get("error") or f"{linea['crudo_estado']}: {linea['crudo']}"
        print(f"{estado} {fuente:12} {linea.get('filas', '')!s:>6} {detalle}")

    exitos = {l["fuente"]: l["resultado"] == "ok" for l in lineas}
    paquete = empaquetar(exitos, momento)

    avisos = []
    vence = vencimiento_cert_banrep()
    dias = (vence - momento).days
    if dias <= AVISO_CERT_DIAS:
        avisos.append({"titulo": "Certificado por vencer: GeoTrust EV RSA CA G2",
                       "detalle": f"El intermedio guardado para el Banco de la República vence el {vence:%Y-%m-%d} "
                                  f"(faltan {dias} días). Ver scripts/tuberia/FUENTES.md."})

    resumen = {"corrida": corrida, "modo": args.modo, "corte": hoy_bogota(momento).isoformat(),
               "fallas": [{"fuente": l["fuente"], "error": l["error"]} for l in lineas if l["resultado"] != "ok"],
               "avisos": avisos, "cert_banrep_vence": vence.date().isoformat(),
               "macro": paquete["indicadores"]}
    if args.resumen:
        pathlib.Path(args.resumen).write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Fuentes con falla: {len(resumen['fallas'])} · certificado del Banco vence en {dias} días")
    return 0


if __name__ == "__main__":
    sys.exit(main())
