"""Pruebas del comportamiento esperado sobre el paquete del reto (modo reglas, sin red)."""
import unittest
from pathlib import Path

from revenue_agent import pipeline

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos_entrevista"


def _senal(r, sid):
    return next(s for s in r.senales if s.id == sid)


class PaqueteOriginal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = pipeline.analizar("reglas")

    def test_ingesta_completa(self):
        self.assertEqual([d.id for d in self.r.docs], [f"F{i:02d}" for i in range(1, 19)])

    def test_citas_literales(self):
        for s in self.r.senales:
            for a in s.afirmaciones:
                doc = next(d for d in self.r.docs if d.id == a.doc_id)
                self.assertEqual(doc.texto[a.inicio:a.fin], a.cita)

    def test_ruido_descartado_con_cita(self):
        self.assertEqual(sorted(d["id"] for d in self.r.descartados), ["F13", "F14", "F15", "F16"])
        self.assertTrue(all(d["cita"] for d in self.r.descartados))

    def test_agrupacion_y_orden(self):
        grupos = {s.id: [d.id for d in s.docs] for s in self.r.senales}
        self.assertEqual(grupos, {"S1": ["F01", "F02", "F03", "F04"], "S2": ["F05", "F06", "F07"],
                                  "S3": ["F08", "F09", "F10", "F11", "F12"], "S4": ["F17", "F18"]})
        self.assertEqual([s.id for s in self.r.senales], ["S1", "S4", "S2", "S3"])

    def test_s1_no_confirma_ni_cuantifica(self):
        s1 = _senal(self.r, "S1")
        self.assertEqual(s1.estado, "Por validar")
        self.assertIn("F01", {a.doc_id for a in s1.de_tipo("hipotesis")})
        self.assertNotRegex(s1.resumen, r"\d+\s*%|S/|\$")

    def test_herramienta_con_criterio(self):
        consultas = {s.id: [(c["parametros"]["canal"], c["resultado"]) for c in s.consultas] for s in self.r.senales}
        self.assertEqual(consultas["S1"], [("Web", "no_verificado"), ("Sucursal", "conforme")])
        self.assertEqual(consultas["S3"], [("Web", "no_desplegado")])
        self.assertEqual(consultas["S2"], [])
        self.assertEqual(consultas["S4"], [])

    def test_contradiccion_f11_f12(self):
        s3 = _senal(self.r, "S3")
        self.assertEqual(len(s3.contradicciones), 1)
        c = s3.contradicciones[0]
        self.assertEqual((c["fuente_corregida"], c["fuente_que_corrige"]), ("F11", "F12"))
        self.assertIn("respalda a F12", c["verificacion"])


class EvidenciaNueva(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.antes = pipeline.resumen_estado(pipeline.analizar("reglas"))
        cls.r = pipeline.analizar("reglas", extra=[EJEMPLOS / "F19_confirmacion_tasa_web.md",
                                                   EJEMPLOS / "F20_comision_duplicada_app.md"])

    def test_confirmacion_actualiza_s1(self):
        s1 = _senal(self.r, "S1")
        self.assertIn("F19", [d.id for d in s1.docs])
        self.assertTrue(s1.estado.startswith("Confirmada"))
        f01 = next(a for a in s1.de_tipo("hipotesis") if a.doc_id == "F01")
        self.assertEqual(f01.nota, "confirmada por F19")

    def test_tema_nuevo_es_emergente(self):
        self.assertIn("E-F20", [s.id for s in self.r.senales])
        self.assertNotIn("F20", [d.id for d in _senal(self.r, "S4").docs])

    def test_cambios_reportados(self):
        cambios = pipeline.comparar(self.antes, pipeline.resumen_estado(self.r))
        texto = "\n".join(cambios)
        self.assertIn("Documentos nuevos: F19, F20", texto)
        self.assertIn("S1: incorpora F19", texto)
        self.assertIn("Nueva señal E-F20", texto)


class CasosDeEnsayo(unittest.TestCase):
    def test_participio_no_es_faltante(self):
        r = pipeline.analizar("reglas", extra=[EJEMPLOS / "F21_muestra_ajustada_web.md"])
        f21 = [a for a in _senal(r, "S1").afirmaciones if a.doc_id == "F21"]
        self.assertEqual(f21[0].tipo, "hecho")  # "la muestra solicitada" no pide nada

    def test_correccion_de_un_hecho_con_registro_anterior(self):
        r = pipeline.analizar("reglas", extra=[EJEMPLOS / "F22_selector_en_produccion.md"])
        s3 = _senal(r, "S3")
        nueva = next(c for c in s3.contradicciones if c["fuente_que_corrige"] == "F22")
        self.assertEqual(nueva["fuente_corregida"], "F12")
        self.assertIn("es anterior a F22", nueva["verificacion"])

    def test_ruido_con_palabra_tarifa(self):
        r = pipeline.analizar("reglas", extra=[EJEMPLOS / "F23_tarifa_estacionamiento.md"])
        self.assertIn("F23", [d["id"] for d in r.descartados])


if __name__ == "__main__":
    unittest.main()
