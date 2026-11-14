"""Pruebas de scripts/tuberia/validar.py y calcular.py: casos buenos y malos, sin red.

Uso: python -m unittest discover -s pruebas -p "test_*.py"
"""
import datetime as dt
import io
import json
import pathlib
import sys
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "tuberia"))

import calcular  # noqa: E402
import validar  # noqa: E402
from comun import ErrorValidacion  # noqa: E402

HOY = dt.date(2026, 11, 12)


def trm_json(*filas):
    return json.dumps([{"valor": v, "unidad": "COP", "vigenciadesde": f"{d}T00:00:00.000",
                        "vigenciahasta": f"{h or d}T00:00:00.000"} for v, d, h in filas]).encode()


def tpm_json(ultimo=12.25, id_=59, unidad="%", sin=None, n=200):
    base = 1761973200000  # 2025-11-01 00:00 Bogotá
    data = [[base + i * 86400000, 9.25 if i < n - 40 else ultimo] for i in range(n)]
    s = {"id": id_, "nombre": "Tasa de política monetaria", "unidadCorta": unidad, "fuente": "Banco de la República",
         "data": data, "fechaUltimoCargue": "12 de noviembre de 2026"}
    if sin:
        s.pop(sin)
    return json.dumps([s]).encode()


def xlsx_ipc(anios=(2024, 2025, 2026), meses=None, base="Base Diciembre de 2018 = 100", hasta=(2026, 10),
             valores=None, cabecera="Mes"):
    """Arma un xlsx mínimo con la misma forma que el anexo de índices del DANE."""
    meses = meses or validar.MESES
    filas = [(3, {1: "Total, Índice de Precios al Consumidor (IPC)"}), (8, {25: base}),
             (9, {1: cabecera, **{2 + i: str(a) for i, a in enumerate(anios)}})]
    for m, nombre in enumerate(meses, 1):
        celdas = {1: nombre}
        for i, a in enumerate(anios):
            if (a, m) <= hasta:
                celdas[2 + i] = str(valores.get((a, m), 100 + (a - 2024) * 6 + m * 0.4) if valores else 100 + (a - 2024) * 6 + m * 0.4)
        filas.append((9 + m, celdas))
    textos = []
    def col(n):
        s = ""
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s
    xml_filas = []
    for f, celdas in filas:
        cs = []
        for c, v in sorted(celdas.items()):
            try:
                float(v)
                cs.append(f'<c r="{col(c)}{f}"><v>{v}</v></c>')
            except ValueError:
                textos.append(v)
                cs.append(f'<c r="{col(c)}{f}" t="s"><v>{len(textos) - 1}</v></c>')
        xml_filas.append(f'<row r="{f}">{"".join(cs)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}>' + "".join(f"<si><t>{t}</t></si>" for t in textos) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>{"".join(xml_filas)}</sheetData></worksheet>')
    return buf.getvalue()


META_IPC = {"mes_en_url": "oct2026", "encabezados": {"Last-Modified": "Mon, 09 Nov 2026 22:41:00 GMT"}}


def cartera_json(n_bancos=30, saldo_por_fila=27e12, renglon="5", sin=None, cortes=("2026-08-31",)):
    filas = []
    for i in range(n_bancos):
        f = {"tipo_entidad": "1", "codigo_entidad": str(i + 1), "nombreentidad": f"Banco {i + 1}",
             "fecha_corte": f"{cortes[i % len(cortes)]}T00:00:00.000", "unicap": "1", "descrip_uc": "CRÉDITO ROTATIVO",
             "renglon": renglon, "desc_renglon": "TOTAL", "_1_saldo_de_la_cartera_a": str(saldo_por_fila)}
        if sin:
            f.pop(sin)
        filas.append(f)
    return json.dumps(filas).encode()


class PruebaTRM(unittest.TestCase):
    def test_bueno(self):
        r = validar.trm(trm_json(("3297.07", "2026-11-11", "2026-11-12"), ("3269.88", "2026-11-10", None)), {}, HOY)
        self.assertEqual([s["valor"] for s in r["serie"]], [3269.88, 3297.07])
        ind = calcular.trm(r, HOY)
        self.assertEqual((ind["valor"], ind["vigencia_desde"]), (3297.07, "2026-11-11"))

    def test_fuera_de_rango(self):
        for v in ("1999.99", "8000.01", "329707"):
            with self.subTest(v=v), self.assertRaisesRegex(ErrorValidacion, "fuera de rango"):
                validar.trm(trm_json((v, "2026-11-11", None)), {}, HOY)

    def test_vigencia_futura(self):
        validar.trm(trm_json(("3300", "2026-11-13", None)), {}, HOY)  # mañana sí (TRM del fin de semana)
        with self.assertRaisesRegex(ErrorValidacion, "futura"):
            validar.trm(trm_json(("3300", "2026-11-14", None)), {}, HOY)

    def test_columnas_cambiadas(self):
        datos = json.dumps([{"valor_trm": "3297.07", "unidad": "COP", "vigenciadesde": "2026-11-11T00:00:00.000",
                             "vigenciahasta": "2026-11-11T00:00:00.000"}]).encode()
        with self.assertRaisesRegex(ErrorValidacion, "faltan columnas"):
            validar.trm(datos, {}, HOY)

    def test_tipo_cambiado(self):
        with self.assertRaisesRegex(ErrorValidacion, "no es un número"):
            validar.trm(trm_json(("tres mil", "2026-11-11", None)), {}, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "formato inesperado"):
            validar.trm(trm_json(("3297", "11/11/2026", None)), {}, HOY)

    def test_vacio_y_no_json(self):
        with self.assertRaises(ErrorValidacion):
            validar.trm(b"[]", {}, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "no es JSON"):
            validar.trm(b"<html>error</html>", {}, HOY)


class PruebaTasaEmisor(unittest.TestCase):
    def test_bueno(self):
        r = validar.tasa_emisor(tpm_json(), {}, HOY)
        self.assertEqual(r["ultimo"]["valor"], 12.25)
        self.assertEqual([c["valor"] for c in r["cambios"]], [9.25, 12.25])
        self.assertEqual(calcular.tasa_emisor(r, HOY)["valor"], 12.25)

    def test_fuera_de_rango(self):
        for v in (-0.5, 30.5):
            with self.subTest(v=v), self.assertRaisesRegex(ErrorValidacion, "fuera de rango"):
                validar.tasa_emisor(tpm_json(ultimo=v), {}, HOY)

    # Fechas por delante (corrida 43549211008, 13-nov-2026: la serie llegaba hasta el lunes festivo 16-nov).
    @staticmethod
    def tpm_hasta(ultima, valores_finales=(), n=200):
        """Serie diaria de n filas en 12,25 % que termina en `ultima`; las últimas filas pueden llevar otros valores."""
        fin = dt.datetime(ultima.year, ultima.month, ultima.day, tzinfo=dt.timezone(dt.timedelta(hours=-5)))
        fechas = [int((fin - dt.timedelta(days=n - 1 - i)).timestamp() * 1000) for i in range(n)]
        valores = [12.25] * (n - len(valores_finales)) + list(valores_finales)
        s = {"id": 59, "nombre": "Tasa de política monetaria", "unidadCorta": "%", "fuente": "Banco de la República",
             "data": [[f, v] for f, v in zip(fechas, valores)], "fechaUltimoCargue": "13 de noviembre de 2026"}
        return json.dumps([s]).encode()

    def test_filas_futuras_se_ignoran(self):
        hoy = dt.date(2026, 11, 13)
        # 14, 15 y 16 de noviembre son futuras; la del 16 trae otro valor para comprobar que no se usa.
        r = validar.tasa_emisor(self.tpm_hasta(dt.date(2026, 11, 16), valores_finales=(12.25, 12.25, 9.9)), {}, hoy)
        self.assertEqual(r["ultimo"], {"fecha": "2026-11-13", "valor": 12.25})
        self.assertEqual(r["filas_futuras_ignoradas"], 3)
        self.assertTrue(all(c["desde"] <= "2026-11-13" for c in r["cambios"]))
        self.assertEqual(calcular.tasa_emisor(r, hoy)["valor"], 12.25)

    def test_solo_futuras_falla(self):
        with self.assertRaisesRegex(ErrorValidacion, "todas las filas tienen fecha futura"):
            validar.tasa_emisor(self.tpm_hasta(dt.date(2027, 12, 31)), {}, dt.date(2026, 11, 13))

    def test_normal_sin_futuras(self):
        r = validar.tasa_emisor(self.tpm_hasta(dt.date(2026, 11, 13)), {}, dt.date(2026, 11, 13))
        self.assertEqual(r["ultimo"], {"fecha": "2026-11-13", "valor": 12.25})
        self.assertEqual(r["filas_futuras_ignoradas"], 0)

    def test_trm_conserva_su_regla(self):
        # La regla de TRM no cambia: vigencia a más de 1 día por delante se rechaza.
        with self.assertRaisesRegex(ErrorValidacion, "vigencia futura"):
            validar.trm(trm_json((4000, "2026-11-16", None)), {}, dt.date(2026, 11, 13))

    def test_estructura(self):
        with self.assertRaisesRegex(ErrorValidacion, "faltan columnas"):
            validar.tasa_emisor(tpm_json(sin="data"), {}, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "serie o unidad"):
            validar.tasa_emisor(tpm_json(id_=60), {}, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "incompleta"):
            validar.tasa_emisor(tpm_json(n=10), {}, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "una serie"):
            validar.tasa_emisor(b"[]", {}, HOY)


class PruebaIPC(unittest.TestCase):
    def test_bueno_y_variacion_anual(self):
        r = validar.ipc(xlsx_ipc(valores={(2025, 10): 151.76, (2026, 10): 161.32}), META_IPC, HOY)
        self.assertEqual(r["ultimo_mes"], "2026-10")
        self.assertEqual(r["fecha_publicacion"][:10], "2026-11-09")
        ind = calcular.ipc(r, HOY)
        self.assertEqual(ind["variacion_anual"], 6.3)  # 161,32 / 151,76 − 1

    def test_variacion_fuera_de_rango(self):
        r = validar.ipc(xlsx_ipc(valores={(2025, 10): 100, (2026, 10): 150}), META_IPC, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "fuera de rango"):
            calcular.ipc(r, HOY)
        r = validar.ipc(xlsx_ipc(valores={(2025, 10): 100, (2026, 10): 94}), META_IPC, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "fuera de rango"):
            calcular.ipc(r, HOY)

    def test_indice_no_positivo(self):
        with self.assertRaisesRegex(ErrorValidacion, "no positivo"):
            validar.ipc(xlsx_ipc(valores={(2026, 3): 0}), META_IPC, HOY)

    def test_estructura_cambiada(self):
        with self.assertRaisesRegex(ErrorValidacion, "Mes"):
            validar.ipc(xlsx_ipc(cabecera="Mes de referencia"), META_IPC, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "base"):
            validar.ipc(xlsx_ipc(base="Base Diciembre de 2008 = 100"), META_IPC, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "meses"):
            validar.ipc(xlsx_ipc(meses=["Ene"] + validar.MESES[1:]), META_IPC, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "consecutivos"):
            validar.ipc(xlsx_ipc(anios=(2023, 2025, 2026)), META_IPC, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "xlsx legible"):
            validar.ipc(b"esto no es un xlsx", META_IPC, HOY)

    def test_mes_del_archivo_y_publicacion(self):
        with self.assertRaisesRegex(ErrorValidacion, "el archivo dice"):
            validar.ipc(xlsx_ipc(), {**META_IPC, "mes_en_url": "sep2026"}, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "Last-Modified"):
            validar.ipc(xlsx_ipc(), {"mes_en_url": "oct2026", "encabezados": {}}, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "futura"):
            validar.ipc(xlsx_ipc(), {"mes_en_url": "oct2026", "encabezados": {"Last-Modified": "Mon, 30 Nov 2026 10:00:00 GMT"}}, HOY)

    def test_sin_mismo_mes_anio_anterior(self):
        r = validar.ipc(xlsx_ipc(), META_IPC, HOY)
        r["indices"].pop("2025-10")
        with self.assertRaisesRegex(ErrorValidacion, "falta el índice"):
            calcular.ipc(r, HOY)


class PruebaCarteraSFC(unittest.TestCase):
    def test_bueno(self):
        r = validar.cartera_sfc(cartera_json(), {}, HOY)
        self.assertEqual((r["corte"], r["bancos"], r["total_billones"]), ("2026-08-31", 30, 810.0))

    def test_total_fuera_de_rango(self):
        with self.assertRaisesRegex(ErrorValidacion, "fuera de rango"):
            validar.cartera_sfc(cartera_json(saldo_por_fila=1e12), {}, HOY)       # 30 billones
        with self.assertRaisesRegex(ErrorValidacion, "fuera de rango"):
            validar.cartera_sfc(cartera_json(saldo_por_fila=1e14), {}, HOY)       # 3.000 billones

    def test_pocos_bancos(self):
        with self.assertRaisesRegex(ErrorValidacion, "bancos"):
            validar.cartera_sfc(cartera_json(n_bancos=20, saldo_por_fila=40e12), {}, HOY)

    def test_estructura(self):
        with self.assertRaisesRegex(ErrorValidacion, "faltan columnas"):
            validar.cartera_sfc(cartera_json(sin="_1_saldo_de_la_cartera_a"), {}, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "renglón distinto"):
            validar.cartera_sfc(cartera_json(renglon="10"), {}, HOY)
        with self.assertRaisesRegex(ErrorValidacion, "un solo corte"):
            validar.cartera_sfc(cartera_json(cortes=("2026-08-31", "2026-07-31")), {}, HOY)


class PruebaCapaCruda(unittest.TestCase):
    """Capa cruda: carpeta nueva solo si cambia el sha256; nunca sobrescribe."""

    def setUp(self):
        import tempfile
        import comun
        self.comun = comun
        self.tmp = tempfile.TemporaryDirectory()
        self.antes = (comun.RAIZ, comun.CRUDO)
        comun.RAIZ = pathlib.Path(self.tmp.name)
        comun.CRUDO = comun.RAIZ / "datos" / "crudo"

    def tearDown(self):
        self.comun.RAIZ, self.comun.CRUDO = self.antes
        self.tmp.cleanup()

    def guardar(self, datos, hora):
        momento = dt.datetime.fromisoformat(hora)
        return self.comun.guardar_crudo("trm", datos, "json", {"hora_utc": hora}, momento)

    def test_sin_cambios_no_duplica(self):
        a, nuevo = self.guardar(b'[{"v":1}]', "2026-11-12T16:00:00+00:00")
        self.assertTrue(nuevo)
        b, nuevo = self.guardar(b'[{"v":1}]', "2026-11-13T16:00:00+00:00")   # otro día, misma respuesta
        self.assertEqual((b, nuevo), (a, False))
        self.assertEqual(len(list(self.comun.CRUDO.glob("trm/*"))), 1)

    def test_cambio_el_mismo_dia_no_sobrescribe(self):
        a, _ = self.guardar(b'[{"v":1}]', "2026-11-12T16:00:00+00:00")
        b, nuevo = self.guardar(b'[{"v":2}]', "2026-11-12T18:00:00+00:00")
        self.assertTrue(nuevo)
        self.assertTrue(b.startswith("datos/crudo/trm/2026-11-12-2/"))
        self.assertEqual((self.comun.RAIZ / a).read_bytes(), b'[{"v":1}]')   # la primera sigue intacta
        # La comparación es contra la más reciente por hora, no por nombre de carpeta.
        c, nuevo = self.guardar(b'[{"v":1}]', "2026-11-12T20:00:00+00:00")
        self.assertTrue(nuevo)
        self.assertTrue(c.startswith("datos/crudo/trm/2026-11-12-3/"))


if __name__ == "__main__":
    unittest.main()
