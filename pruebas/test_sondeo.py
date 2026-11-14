"""Pruebas de las funciones puras del sondeo de fuentes (scripts/sondeo/sondear.py). Sin red."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sondeo"))
import sondear  # noqa: E402


class PruebaFuentePermitida(unittest.TestCase):
    def test_fuentes_del_banco(self):
        for f in ("Banco de la República",
                  "Fuente: Banco de la República con información de la Superintendencia Financiera de Colombia"):
            with self.subTest(f=f):
                self.assertTrue(sondear.fuente_permitida(f))

    def test_fuentes_externas_no(self):
        # Textos reales del Banco: COLCAP (idSerie 6) y Prime (idSerie 88).
        for f in ("Fuente: Bolsa de Valores de Colombia - BVC", "Bloomberg", "Refinitiv",
                  "Fuente: Departamento Administrativo Nacional de Estadística (DANE)", "", None):
            with self.subTest(f=f):
                self.assertFalse(sondear.fuente_permitida(f))


class PruebaFechas(unittest.TestCase):
    def test_separar_futuras(self):
        hoy = dt.date(2026, 11, 13)
        serie = [(dt.date(2026, 11, 12), 1.0), (dt.date(2026, 11, 13), 2.0), (dt.date(2026, 11, 20), 3.0)]
        vigentes, futuras = sondear.separar_futuras(serie, hoy)
        self.assertEqual(vigentes[-1], (dt.date(2026, 11, 13), 2.0))
        self.assertEqual(futuras, [(dt.date(2026, 11, 20), 3.0)])

    def test_candidatos_geih_cruzan_el_anio(self):
        self.assertEqual(sondear.candidatos_geih(dt.date(2027, 2, 10), n=3),
                         ["GEIH/anex-GEIH-ene2027.xlsx", "GEIH/anex-GEIH-dic2026.xlsx", "GEIH/anex-GEIH-nov2026.xlsx"])

    def test_candidatos_pib(self):
        # Nombres reales del DANE: anex-ProduccionConstantes-IItrim2026.xlsx (publicado en agosto de 2026).
        self.assertEqual(sondear.candidatos_pib(dt.date(2026, 11, 14), n=2),
                         ["PIB/anex-ProduccionConstantes-IIItrim2026.xlsx", "PIB/anex-ProduccionConstantes-IItrim2026.xlsx"])
        self.assertEqual(sondear.candidatos_pib(dt.date(2027, 1, 5), n=1), ["PIB/anex-ProduccionConstantes-IVtrim2026.xlsx"])


class PruebaAlcance(unittest.TestCase):
    def test_colcap_nunca_se_consulta(self):
        ids = {i for _, i, _ in sondear.BANREP}
        self.assertNotIn(6, ids)  # COLCAP en el Banco: fuente BVC
        self.assertNotIn(88, ids)  # Prime: fuente Bloomberg
        self.assertNotIn("bvc.com.co", open(sondear.__file__, encoding="utf-8").read())  # ni una URL de la BVC

    def test_no_escribe_en_el_repositorio(self):
        codigo = open(sondear.__file__, encoding="utf-8").read()
        for prohibido in ("escribir_json", "guardar_crudo", "registrar(", "LIMPIO", "INDICADORES", "WEB /"):
            with self.subTest(prohibido=prohibido):
                self.assertNotIn(prohibido, codigo)


if __name__ == "__main__":
    unittest.main()
