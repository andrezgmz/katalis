"""Convierte el Excel de cifras en datos/cifras.json, que lee la página Cifras.

Uso (desde la carpeta del sitio):
    python scripts/actualizar_cifras.py

Cada hoja del Excel (T02, T03, ...) trae: título, subtítulo, fuente y una o
varias tablas. Este script no calcula nada: copia los números tal cual y
guarda de dónde salieron, para que cada gráfico cite su fuente.
"""
import json, datetime, pathlib, sys
import openpyxl

RAIZ = pathlib.Path(__file__).resolve().parent.parent
EXCEL = RAIZ / "datos" / "fuente" / "Datos_graficos_economia_solidaria.xlsx"
SALIDA = RAIZ / "datos" / "cifras.json"

# Hojas que publica la web. Las del documento regional (R..) y las de
# Antioquia no se publican todavía.
HOJAS = ["T02", "T03", "T04", "T05", "T07", "T08", "T09", "T10", "T11",
         "T12", "T13", "T14", "T17", "T19", "T37"]

# Referencias que el Excel trae en las notas y no en una tabla. Fuente: DANE,
# según el documento técnico (gráficos 4 y 37). Actualícelas con cada corte.
REFERENCIAS = {
    "inflacion_2025": {"valor": 0.051, "fuente": "DANE, inflación anual 2025"},
    "inflacion_2023_2025": {"valor": 0.208, "fuente": "DANE, inflación acumulada 2023-2025"},
}

def limpio(v):
    if isinstance(v, datetime.datetime):
        return v.date().isoformat()
    if isinstance(v, float):
        return round(v, 6)
    return v

def leer_hoja(ws):
    filas = [[limpio(c) for c in r] for r in ws.iter_rows(values_only=True)]
    texto = lambda r: [c for c in r if c is not None]
    titulo, subtitulo, fuente = texto(filas[1])[0], texto(filas[2])[0], texto(filas[3])[0]
    tablas, i = [], 5
    while i < len(filas):
        f = texto(filas[i])
        if f and f[0] == "Notas":
            break
        # Una tabla = fila con un solo texto (nombre) + fila de encabezados + datos
        if len(f) == 1 and i + 1 < len(filas) and len(texto(filas[i + 1])) > 1:
            nombre, encab = f[0], texto(filas[i + 1])
            datos, j = [], i + 2
            while j < len(filas):
                d = texto(filas[j])
                if len(d) < 2:
                    break
                datos.append(d[:len(encab)])
                j += 1
            tablas.append({"nombre": nombre, "columnas": encab, "filas": datos})
            i = j
        else:
            i += 1
    return {"titulo": titulo, "subtitulo": subtitulo, "fuente": fuente, "tablas": tablas}

def main():
    if not EXCEL.exists():
        sys.exit(f"No encuentro el Excel en {EXCEL}")
    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    salida = {
        "generado": datetime.date.today().isoformat(),
        "unidades": "Pesos en miles de millones de pesos; porcentajes como fracción (0,388 = 38,8 %).",
        "referencias": REFERENCIAS,
        "series": {h: leer_hoja(wb[h]) for h in HOJAS},
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {len(HOJAS)} series en {SALIDA.relative_to(RAIZ)}")

if __name__ == "__main__":
    main()
