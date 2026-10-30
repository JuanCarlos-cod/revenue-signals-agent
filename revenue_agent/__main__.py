"""CLI del Revenue Signals Agent.

  python -m revenue_agent analizar [--modo reglas|llm]
  python -m revenue_agent investigar S1
  python -m revenue_agent agregar ruta/al/documento.md [...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import pipeline, reporte
from .ingesta import agregar_fuente


def _imprimir_ranking(r: pipeline.Resultado, cambios: list[str]) -> None:
    print(f"\nSeñales priorizadas · modo {r.modo} · {len(r.docs)} documentos\n")
    for s in r.senales:
        print(f"  {s.rank}. [{s.id}] {s.nombre}")
        print(f"     prioridad {s.prioridad} · impacto {s.impacto}/5 · evidencia {s.evidencia}/5 · {s.estado}")
        print(f"     fuentes: {', '.join(d.id for d in s.docs)}")
    print(f"\n  Descartados: {', '.join(d['id'] for d in r.descartados) or 'ninguno'}")
    if cambios:
        print("\nCambios frente al análisis anterior:")
        for c in cambios:
            print(f"  - {c}")
    print(f"\nSalidas en {pipeline.DIR_SALIDAS}")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m revenue_agent", description="Revenue Signals Agent")
    sub = parser.add_subparsers(dest="comando", required=True)
    for nombre, ayuda in [("analizar", "Analiza todas las fuentes y genera briefs"),
                          ("investigar", "Muestra el brief y el registro de una señal"),
                          ("agregar", "Incorpora documentos nuevos y muestra qué cambió")]:
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("--modo", choices=["reglas", "llm"], default="reglas",
                       help="reglas: determinístico, sin servicios externos. llm: usa Claude con validación.")
        if nombre == "investigar":
            p.add_argument("senal", help="ID de la señal, por ejemplo S1")
        if nombre == "agregar":
            p.add_argument("rutas", nargs="+", type=Path)
    args = parser.parse_args(argv)

    if args.comando == "agregar":
        for ruta in args.rutas:
            if not ruta.is_file():
                parser.error(f"No existe el archivo: {ruta}")
            print(f"Incorporado {ruta.name} como {agregar_fuente(ruta)}")

    r = pipeline.analizar(args.modo)
    cambios = pipeline.guardar(r)

    if args.comando == "investigar":
        senal = next((s for s in r.senales if s.id.lower() == args.senal.lower()), None)
        if not senal:
            parser.error(f"Señal desconocida. Disponibles: {', '.join(s.id for s in r.senales)}")
        print(reporte.brief(senal, r))
        print(reporte.traza(senal))
        return 0
    _imprimir_ranking(r, cambios)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
