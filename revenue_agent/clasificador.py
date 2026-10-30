"""Clasificación determinística de oraciones por señales lingüísticas.

El orden de las reglas es la precedencia: una oración que niega impacto o corrige otra
fuente se clasifica así aunque también contenga lenguaje condicional.
"""
from __future__ import annotations

import re

from .ingesta import normalizar

TIPOS = ("hecho", "confirmacion", "hipotesis", "faltante", "advertencia", "correccion", "negacion_impacto")

ETIQUETAS = {
    "hecho": "Hecho",
    "confirmacion": "Confirmación",
    "hipotesis": "Hipótesis",
    "faltante": "Dato faltante",
    "advertencia": "Advertencia metodológica",
    "correccion": "Corrección / aclaración",
    "negacion_impacto": "Negación de impacto",
}

_REGLAS: list[tuple[str, list[str]]] = [
    ("negacion_impacto", [r"no cambia ningun", r"no existe vinculo", r"no afectara", r"no se modificaran",
                          r"sin impacto (economico|comercial)"]),
    ("correccion", [r"corregir", r"correccion", r"aclaracion", r"\baclara\b", r"rectific", r"desmient",
                    r"se utilizo .* para describir", r"interpretaron", r"no distingue"]),
    ("faltante", [r"no se ha confirmado", r"no se confirma", r"nadie confirma", r"no se encuentra",
                  r"no dispone", r"no se dispone", r"no se adjunta", r"se desconoce", r"\baun no\b",
                  r"todavia no", r"no incluye", r"deben? verificarse", r"debe confirmar",
                  r"no se ha (conciliado|cuantificado|estimado|medido|validado)", r"no proporciona",
                  r"\bfalta", r"pendiente", r"\bsolicita\b", r"antes de (concluir|solicitar|retirar|inferir)",
                  r"sin aprobacion"]),
    ("confirmacion", [r"se confirmo", r"quedo confirmad", r"confirmamos", r"\bverifico\b",
                      r"esta activ[ao] en produccion"]),
    ("advertencia", [r"advierte", r"inducir a error", r"no esta ajustad", r"sin (controlar|ajustar)",
                     r"no debe asumirse", r"no representa", r"muestra es pequena", r"se considera preliminar"]),
    ("hipotesis", [r"\bparece", r"\bpodrian?\b", r"\bestaria", r"aparentemente", r"\beventual",
                   r"\banticipa", r"preliminar", r"sospech", r"\bposibles?\b", r"\bplanea", r"evaluando",
                   r"en evaluacion", r"proponiendo", r"\bsugiere", r"\brecuerda"]),
]
_COMPILADAS = [(tipo, [re.compile(p) for p in patrones]) for tipo, patrones in _REGLAS]


def clasificar(oracion: str) -> tuple[str, str]:
    """Devuelve (tipo, patrón que decidió). Sin patrón aplicable, es un hecho."""
    texto = normalizar(oracion)
    for tipo, patrones in _COMPILADAS:
        for patron in patrones:
            if patron.search(texto):
                return tipo, patron.pattern
    return "hecho", ""


def tiene_termino_economico(texto: str, terminos: list[str]) -> bool:
    normal = normalizar(texto)
    return any(t in normal for t in terminos)
