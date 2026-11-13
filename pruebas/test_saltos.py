"""Pruebas de saltos anómalos (saltos.py), redirecciones (comun.py) y retención en correr.py. Sin red externa.

Uso: python -m unittest discover -s pruebas -p "test_*.py"
"""
import datetime as dt
import http.server
import json
import pathlib
import ssl
import sys
import tempfile
import threading
import unittest
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "tuberia"))

import comun  # noqa: E402
import saltos  # noqa: E402
from comun import ErrorFuente  # noqa: E402


def trm_limpio(*pares):
    return {"serie": [{"vigencia_desde": d, "vigencia_hasta": d, "valor": v} for d, v in pares]}


def trm_ind(valor, fecha):
    return {"valor": valor, "vigencia_desde": fecha}


class PruebaTRM(unittest.TestCase):
    previo = trm_limpio(("2026-11-10", 3300.0), ("2026-11-11", 3297.07))

    def test_variacion_normal_pasa(self):
        nuevo = trm_limpio(("2026-11-10", 3300.0), ("2026-11-11", 3297.07), ("2026-11-12", 3350.0))
        self.assertEqual(saltos.trm(nuevo, trm_ind(3350.0, "2026-11-12"), self.previo,
                                    trm_ind(3297.07, "2026-11-11")), [])

    def test_variacion_justo_en_5_pasa(self):
        self.assertEqual(saltos.trm(trm_limpio(), trm_ind(3150.0, "2026-11-12"), None, trm_ind(3000.0, "x")), [])

    def test_variacion_mayor_a_5_se_detiene(self):
        m = saltos.trm(trm_limpio(), trm_ind(3500.0, "2026-11-12"), None, trm_ind(3297.07, "2026-11-11"))
        self.assertEqual(len(m), 1)
        self.assertIn("±5 %", m[0])

    def test_caida_mayor_a_5_se_detiene(self):
        self.assertTrue(saltos.trm(trm_limpio(), trm_ind(3100.0, "d"), None, trm_ind(3297.07, "d0")))

    def test_historia_cambiada_se_detiene(self):
        nuevo = trm_limpio(("2026-11-10", 3301.0), ("2026-11-11", 3297.07))
        m = saltos.trm(nuevo, trm_ind(3297.07, "2026-11-11"), self.previo, trm_ind(3297.07, "2026-11-11"))
        self.assertEqual(len(m), 1)
        self.assertIn("2026-11-10", m[0])

    def test_sin_previo_no_compara(self):
        self.assertEqual(saltos.trm(trm_limpio(("2026-11-12", 9000.0)), trm_ind(9000.0, "x"), None, None), [])


class PruebaContrasteTRM(unittest.TestCase):
    def test_iguales_pasa(self):
        self.assertEqual(saltos.contraste_trm({"2026-11-11": 3297.07}, {"2026-11-11": 3297.07}),
                         ([], "2026-11-11"))

    def test_diferencia_menor_a_0_1_pasa(self):
        self.assertEqual(saltos.contraste_trm({"d": 3297.07}, {"d": 3300.0})[0], [])  # −0,089 %

    def test_diferencia_mayor_a_0_1_se_detiene(self):
        motivos, fecha = saltos.contraste_trm({"d1": 3000.0, "d2": 3297.07}, {"d2": 3310.0})
        self.assertEqual(fecha, "d2")
        self.assertIn("0,1 %", motivos[0])

    def test_sin_fechas_comunes_no_hay_contraste(self):
        self.assertEqual(saltos.contraste_trm({"d1": 1.0}, {"d2": 2.0}), ([], None))


def tpm_limpio(*cambios):
    return {"cambios": [{"desde": d, "valor": v} for d, v in cambios]}


class PruebaTasaEmisor(unittest.TestCase):
    previo = tpm_limpio(("2026-07-01", 12.5), ("2026-10-01", 12.25))

    def revisar(self, valor, nuevo=None):
        nuevo = nuevo or tpm_limpio(("2026-07-01", 12.5), ("2026-10-01", 12.25), ("2026-11-15", valor))
        return saltos.tasa_emisor(nuevo, {"valor": valor}, self.previo, {"valor": 12.25})

    def test_sin_cambio_pasa(self):
        self.assertEqual(self.revisar(12.25, self.previo), [])

    def test_baja_de_0_25_pasa(self):
        self.assertEqual(self.revisar(12.0), [])

    def test_sube_1_punto_pasa(self):
        self.assertEqual(self.revisar(13.25), [])

    def test_no_multiplo_de_0_25_se_detiene(self):
        m = self.revisar(12.4)
        self.assertEqual(len(m), 1)
        self.assertIn("múltiplo de 0,25", m[0])

    def test_mas_de_1_punto_se_detiene(self):
        m = self.revisar(13.5)
        self.assertEqual(len(m), 1)
        self.assertIn("1 punto", m[0])

    def test_historia_cambiada_se_detiene(self):
        nuevo = tpm_limpio(("2026-07-01", 12.75), ("2026-10-01", 12.25))
        self.assertIn("2026-07-01", self.revisar(12.25, nuevo)[0])

    def test_cambio_borrado_de_la_historia_se_detiene(self):
        nuevo = tpm_limpio(("2026-10-01", 12.25))
        self.assertIn("desapareció", self.revisar(12.25, nuevo)[0])


class PruebaIPC(unittest.TestCase):
    previo_l = {"indices": {"2026-08": 160.9, "2026-09": 161.0}}
    previo_i = {"variacion_anual": 6.3, "mes": "2026-09"}

    def revisar(self, variacion, indices=None):
        nuevo = {"indices": indices or {"2026-08": 160.9, "2026-09": 161.0, "2026-10": 161.32}}
        return saltos.ipc(nuevo, {"variacion_anual": variacion, "mes": "2026-10"}, self.previo_l, self.previo_i)

    def test_cambio_normal_pasa(self):
        self.assertEqual(self.revisar(6.1), [])

    def test_cambio_justo_en_1_5_pasa(self):
        self.assertEqual(self.revisar(7.8), [])

    def test_cambio_mayor_a_1_5_se_detiene(self):
        self.assertIn("1,5 puntos", self.revisar(8.0)[0])

    def test_indice_pasado_cambiado_se_detiene(self):
        m = self.revisar(6.3, {"2026-08": 159.0, "2026-09": 161.0, "2026-10": 161.32})
        self.assertIn("2026-08", m[0])


class _Redirige(http.server.BaseHTTPRequestHandler):
    destino = ""

    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", self.destino)
        self.end_headers()

    def log_message(self, *args):
        pass


class PruebaRedirecciones(unittest.TestCase):
    """P2: ninguna redirección a http:// ni a otro host; una a https del mismo host sí se sigue."""

    def setUp(self):
        self.servidor = http.server.HTTPServer(("127.0.0.1", 0), _Redirige)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.servidor.server_port}/a"

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def abrir(self, destino):
        _Redirige.destino = destino
        return comun.abridor(ssl.create_default_context()).open(self.url, timeout=5)

    def test_redireccion_a_http_falla(self):
        with self.assertRaisesRegex(ErrorFuente, "redirección no permitida .* a http://127.0.0.1"):
            self.abrir(f"http://127.0.0.1:{self.servidor.server_port}/b")

    def test_redireccion_a_otro_host_falla(self):
        with self.assertRaisesRegex(ErrorFuente, "a https://otro.example"):
            self.abrir("https://otro.example/b")

    def test_redireccion_https_mismo_host_se_sigue(self):
        pedido = urllib.request.Request("https://www.datos.gov.co/a")
        nuevo = comun.RedireccionSegura().redirect_request(pedido, None, 302, "Found", {}, "https://www.datos.gov.co/b")
        self.assertEqual(nuevo.full_url, "https://www.datos.gov.co/b")

    def test_descargar_solo_https(self):
        with self.assertRaisesRegex(ErrorFuente, "solo se consultan fuentes por https"):
            comun.descargar(self.url)


class PruebaRetencion(unittest.TestCase):
    """Un salto anómalo no avanza sin --con-anomalias; con él, sí (y queda anotado)."""

    def setUp(self):
        import correr
        import empaquetar
        self.correr, self.empaquetar = correr, empaquetar
        self.tmp = tempfile.TemporaryDirectory()
        raiz = pathlib.Path(self.tmp.name)
        datos = raiz / "datos"
        self.antes = (comun.RAIZ, comun.CRUDO, comun.REGISTRO, correr.LIMPIO, correr.INDICADORES,
                      empaquetar.INDICADORES, empaquetar.WEB)
        comun.RAIZ, comun.CRUDO, comun.REGISTRO = raiz, datos / "crudo", datos / "registro.jsonl"
        correr.LIMPIO, correr.INDICADORES = datos / "limpio", datos / "indicadores"
        empaquetar.INDICADORES, empaquetar.WEB = datos / "indicadores", datos / "web"
        self.datos = datos
        comun.escribir_json(datos / "indicadores" / "trm.json", {"valor": 3297.07, "vigencia_desde": "2026-11-11"})
        self.trabajo = raiz / "trabajo"
        carpeta = self.trabajo / "trm"
        carpeta.mkdir(parents=True)
        (carpeta / "respuesta.json").write_bytes(b"[]")
        comun.escribir_json(carpeta / "resultado.json", {
            "fuente": "trm", "estado": "ok", "extension": "json", "meta": {"url": "https://x"},
            "linea": {"fuente": "trm", "hora_utc": "2026-11-12T16:00:00+00:00"},
            "limpio": {"serie": []}, "indicador": {"valor": 3600.0, "vigencia_desde": "2026-11-12",
                                                   "vigencia_hasta": "2026-11-12"},
            "anomalias": ["trm: salto de prueba"]})
        comun.escribir_json(self.trabajo / "extraccion.json", {
            "momento": "2026-11-12T16:00:00+00:00", "corrida": "prueba", "fuentes": ["trm"],
            "anomalias": {"trm": ["trm: salto de prueba"]}})

    def tearDown(self):
        (comun.RAIZ, comun.CRUDO, comun.REGISTRO, self.correr.LIMPIO, self.correr.INDICADORES,
         self.empaquetar.INDICADORES, self.empaquetar.WEB) = self.antes
        self.tmp.cleanup()

    def registro(self):
        return [json.loads(l) for l in (self.datos / "registro.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_sin_aprobacion_se_retiene(self):
        r = self.correr.etapa_aplicar(self.trabajo, "prueba")
        self.assertEqual(r["anomalias"], [{"fuente": "trm", "motivos": ["trm: salto de prueba"]}])
        self.assertEqual(comun.leer_json(self.datos / "indicadores" / "trm.json")["valor"], 3297.07)
        self.assertEqual(r["macro"]["trm"]["valor"], 3297.07)
        self.assertFalse((self.datos / "crudo").exists())
        self.assertEqual(self.registro()[0]["resultado"], "retenido")

    def test_con_aprobacion_avanza(self):
        r = self.correr.etapa_aplicar(self.trabajo, "publicacion", con_anomalias=True)
        self.assertEqual(r["macro"]["trm"]["valor"], 3600.0)
        linea = self.registro()[0]
        self.assertEqual(linea["resultado"], "ok")
        self.assertIn("aprobación", linea["aprobacion"])


if __name__ == "__main__":
    unittest.main()
