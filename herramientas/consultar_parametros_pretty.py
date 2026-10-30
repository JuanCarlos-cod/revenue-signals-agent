
#!/usr/bin/env python3
"""
Herramienta local de consulta de parámetros ficticios.

USO:
    # Salida JSON compatible con el agente
    python herramientas/consultar_parametros.py "Credito Flexible" Web rate_input

    # Salida visual amigable
    python herramientas/consultar_parametros.py "Credito Flexible" Web rate_input --pretty

CAMBIOS REALIZADOS:
    [AJUSTE 1] Se agrega el modo visual opcional --pretty.
    [AJUSTE 2] Se conserva el JSON original como salida predeterminada.
    [AJUSTE 3] Se validan argumentos vacíos y cantidad incorrecta.
    [AJUSTE 4] Se gestionan errores de lectura y JSON inválido.
    [AJUSTE 5] Se valida la estructura básica de los registros.
    [AJUSTE 6] Se normalizan mayúsculas y espacios exteriores.
    [AJUSTE 7] Se muestran resultados y advertencias de forma legible.
    [AJUSTE 8] Se documentan las decisiones para facilitar la entrevista.

No requiere dependencias externas.
"""

import json
import sys
from pathlib import Path
from typing import Any


# CONFIGURACIÓN
DATA_FILE = Path(__file__).parent / "parametros_simulados.json"

WARNING = (
    "Registro simulado; contrastar con fuentes y "
    "no inferir leakage cuantificado."
)


def normalize(value: str) -> str:
    """Normaliza espacios exteriores y mayúsculas para comparar."""
    return value.strip().casefold()


def load_records() -> list[dict[str, Any]]:
    """
    Carga la base JSON local y valida su estructura básica.

    AJUSTE 4 y 5:
    Los errores se convierten en mensajes comprensibles.
    El archivo original se lee sin modificarlo.
    """
    try:
        content = DATA_FILE.read_text(encoding="utf-8")
        records = json.loads(content)

    except FileNotFoundError as exc:
        raise RuntimeError(
            f"No se encontró el archivo {DATA_FILE.name}."
        ) from exc

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"JSON inválido en {DATA_FILE.name}: "
            f"línea {exc.lineno}, columna {exc.colno}."
        ) from exc

    except OSError as exc:
        raise RuntimeError(
            f"No se pudo leer {DATA_FILE.name}: {exc}"
        ) from exc

    if not isinstance(records, list):
        raise RuntimeError(
            "La base JSON debe contener una lista de registros."
        )

    required_fields = {"producto", "canal", "parametro"}

    for index, record in enumerate(records, start=1):
        if (
            not isinstance(record, dict)
            or not required_fields.issubset(record.keys())
        ):
            raise RuntimeError(
                f"El registro #{index} no contiene los campos "
                "obligatorios: producto, canal y parametro."
            )

    return records


def query_records(
    records: list[dict[str, Any]],
    producto: str,
    canal: str,
    parametro: str,
) -> list[dict[str, Any]]:
    """
    Busca coincidencias por producto, canal y parámetro.

    AJUSTE 6:
    La comparación no distingue mayúsculas ni espacios
    al principio o al final.
    """
    return [
        record
        for record in records
        if normalize(str(record["producto"])) == normalize(producto)
        and normalize(str(record["canal"])) == normalize(canal)
        and normalize(str(record["parametro"])) == normalize(parametro)
    ]


def build_result(
    producto: str,
    canal: str,
    parametro: str,
    found: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Construye la respuesta estructurada.

    AJUSTE 2:
    Se mantienen las claves originales para preservar
    la compatibilidad con el agente.
    """
    return {
        "consulta": {
            "producto": producto,
            "canal": canal,
            "parametro": parametro,
        },
        "encontrado": bool(found),
        "registros": found,
        "advertencia": WARNING,
    }


def print_pretty(result: dict[str, Any]) -> None:
    """
    Imprime una vista amigable para el usuario.

    AJUSTE 1 y 7:
    Facilita revisar resultados durante una demo
    sin cambiar el contrato JSON de la herramienta.
    """
    query = result["consulta"]
    found = result["encontrado"]
    records = result["registros"]

    status = (
        "[OK] COINCIDENCIA ENCONTRADA"
        if found
        else "[INFO] SIN COINCIDENCIAS"
    )

    print("=" * 64)
    print("  CONSULTA DE PARÁMETROS — BASE SIMULADA")
    print("=" * 64)
    print(f"  Estado:     {status}")
    print(f"  Producto:   {query['producto']}")
    print(f"  Canal:      {query['canal']}")
    print(f"  Parámetro:  {query['parametro']}")
    print("-" * 64)

    if records:
        print(f"  Registros encontrados: {len(records)}\n")

        for number, record in enumerate(records, start=1):
            print(f"  REGISTRO {number}")

            for key, value in record.items():
                label = key.replace("_", " ").capitalize()

                if isinstance(value, (dict, list)):
                    rendered = json.dumps(
                        value,
                        ensure_ascii=False,
                    )
                else:
                    rendered = str(value)

                print(f"    • {label}: {rendered}")

            print()

    else:
        print("  No se encontraron coincidencias exactas.")
        print(
            "  Esto no demuestra que el parámetro no exista "
            "fuera de esta base."
        )
        print()

    print("-" * 64)
    print(f"  Advertencia: {result['advertencia']}")
    print("=" * 64)


def main() -> int:
    """Punto de entrada de la herramienta CLI."""

    args = sys.argv[1:]

    # AJUSTE 1: activar el modo visual sin alterar los argumentos originales.
    pretty = "--pretty" in args
    args = [arg for arg in args if arg != "--pretty"]

    # AJUSTE 3: validar la cantidad de argumentos.
    if len(args) != 3:
        error = {
            "error": (
                "Uso: consultar_parametros.py "
                "PRODUCTO CANAL PARAMETRO [--pretty]"
            )
        }

        print(
            json.dumps(
                error,
                ensure_ascii=False,
                indent=2 if pretty else None,
            )
        )
        return 2

    producto, canal, parametro = args

    # AJUSTE 3: impedir consultas con campos vacíos.
    if not all(value.strip() for value in args):
        error = {
            "error": (
                "PRODUCTO, CANAL y PARAMETRO "
                "no pueden estar vacíos."
            )
        }

        print(
            json.dumps(
                error,
                ensure_ascii=False,
                indent=2 if pretty else None,
            )
        )
        return 2

    try:
        records = load_records()

        found = query_records(
            records,
            producto,
            canal,
            parametro,
        )

        result = build_result(
            producto,
            canal,
            parametro,
            found,
        )

    except RuntimeError as exc:
        error = {"error": str(exc)}

        print(
            json.dumps(
                error,
                ensure_ascii=False,
                indent=2 if pretty else None,
            )
        )
        return 1

    # AJUSTE 1 y 2: salida visual opcional o JSON compatible.
    if pretty:
        print_pretty(result)
    else:
        print(json.dumps(result, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
