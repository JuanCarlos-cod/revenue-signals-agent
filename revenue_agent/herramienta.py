"""Adaptador de la herramienta local `consultar_parametros.py` (se invoca sin modificarla)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unicodedata

from .ingesta import RAIZ

RUTA_HERRAMIENTA = RAIZ / "herramientas" / "consultar_parametros.py"


def _quitar(texto: str) -> str:
    """La base usa nombres sin tildes ("Credito"); se conserva la capitalización."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def consultar(producto: str, canal: str, parametro: str) -> dict:
    """Ejecuta la herramienta como proceso aparte. El script corre todo al importarse,
    por eso no se puede llamar como función."""
    args = [_quitar(producto), _quitar(canal), _quitar(parametro)]
    proceso = subprocess.run(
        [sys.executable, "-I", str(RUTA_HERRAMIENTA), *args],
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=30,
    )
    try:
        respuesta = json.loads(proceso.stdout)
    except json.JSONDecodeError:
        respuesta = {"error": proceso.stdout.strip() or proceso.stderr.strip()}
    return {
        "comando": ["python", "herramientas/consultar_parametros.py", *args],
        "codigo_salida": proceso.returncode,
        "respuesta": respuesta,
    }


def interpretar(respuesta: dict) -> tuple[str, str]:
    """Traduce el registro a una conclusión acotada: nunca cuantifica."""
    if "error" in respuesta:
        return "error", f"La herramienta devolvió un error: {respuesta['error']}"
    if not respuesta.get("encontrado"):
        return "sin_registro", "No hay registro para esa combinación; la consulta no aporta evidencia."
    r = respuesta["registros"][0]
    esperado, valor, estado = r["unidad_esperada"], r["valor_configurado"], r["estado_produccion"]
    if estado == "no_desplegado":
        return "no_desplegado", f"Configurado como '{valor}' y no desplegado en producción."
    if valor == esperado and estado == "vigente":
        return "conforme", f"Valor '{valor}' coincide con lo esperado ('{esperado}') y está vigente."
    if valor == "pendiente_de_validar" or estado == "sin_confirmacion":
        return "no_verificado", (f"Se espera '{esperado}', pero el valor está '{valor}' y el estado en "
                                 f"producción es '{estado}': no confirma ni descarta la hipótesis.")
    return "revisar", f"Valor '{valor}' (esperado '{esperado}'), estado '{estado}'."
