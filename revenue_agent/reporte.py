"""Salidas en Markdown/JSON: ranking, Opportunity Briefs y registro de investigación."""
from __future__ import annotations

import json

from .clasificador import ETIQUETAS
from .pipeline import DIR_SALIDAS, Resultado, Senal


def _cita(a) -> str:
    nota = f" — _{a.nota}_" if a.nota else ""
    # Los saltos de línea dentro de una cita se muestran como espacio; el texto sigue siendo el original.
    return f"- **[{a.doc_id}]** «{' '.join(a.cita.split())}»{nota}"


def _seccion(titulo: str, afirmaciones, vacio: str) -> list[str]:
    lineas = [f"## {titulo}", ""]
    lineas += [_cita(a) for a in afirmaciones] or [f"_{vacio}_"]
    return lineas + [""]


def tabla_senales(r: Resultado) -> list[str]:
    lineas = ["| # | Señal | Naturaleza | Impacto | Evidencia | Prioridad | Estado | Fuentes |",
              "|---|---|---|---|---|---|---|---|"]
    for s in r.senales:
        lineas.append(f"| {s.rank} | **{s.id}** {s.nombre} | {s.naturaleza} | {s.impacto}/5 | {s.evidencia}/5 | "
                      f"**{s.prioridad}** | {s.estado} | {', '.join(d.id for d in s.docs)} |")
    return lineas


def ranking(r: Resultado, cambios: list[str]) -> str:
    lineas = ["# Señales priorizadas", "",
              f"Generado: {r.generado} · Modo: `{r.modo}` · Documentos analizados: {len(r.docs)}", "",
              "Prioridad = impacto (1–5, catálogo) × confianza (0,5 + 0,1 × solidez de la evidencia).", ""]
    lineas += tabla_senales(r)
    lineas += ["", "## Documentos descartados (sin potencial económico)", ""]
    for d in r.descartados:
        cita = f" Cita: «{d['cita']}»" if d["cita"] else ""
        lineas.append(f"- **{d['id']}** {d['titulo']}: {d['motivo']}{cita}")
    if cambios:
        lineas += ["", "## Cambios frente al análisis anterior", ""] + [f"- {c}" for c in cambios]
    if r.uso_llm:
        llamadas = [u for u in r.uso_llm if not u.get("cache")]
        entrada = sum(u.get("tokens_entrada", 0) for u in llamadas)
        salida = sum(u.get("tokens_salida", 0) for u in llamadas)
        lineas += ["", "## Uso del LLM", "",
                   f"{len(llamadas)} llamadas nuevas, {len(r.uso_llm) - len(llamadas)} desde caché; "
                   f"{entrada} tokens de entrada y {salida} de salida."]
    return "\n".join(lineas) + "\n"


def brief(s: Senal, r: Resultado) -> str:
    total = len(r.senales)
    lineas = [f"# Opportunity Brief · {s.id} — {s.nombre}", "",
              f"> Generado: {r.generado} · Modo: `{r.modo}` · Fuentes: {', '.join(d.id for d in s.docs)}", "",
              "| Prioridad | Impacto | Solidez de la evidencia | Estado |", "|---|---|---|---|",
              f"| {s.rank} de {total} (**{s.prioridad}**) | {s.impacto}/5 | {s.evidencia}/5 | {s.estado} |", "",
              f"**Naturaleza:** {s.naturaleza}", "",
              f"**Por qué importa:** {s.justificacion}", "",
              "## Resumen", "", s.resumen, ""]
    lineas += _seccion("Hechos", s.de_tipo("hecho"), "Sin hechos documentados.")
    if s.de_tipo("confirmacion"):
        lineas += _seccion("Confirmaciones", s.de_tipo("confirmacion"), "")
    lineas += _seccion("Hipótesis", s.de_tipo("hipotesis"), "Sin hipótesis.")
    lineas += _seccion("Datos faltantes", s.de_tipo("faltante"), "Sin datos faltantes identificados.")
    lineas += _seccion("Advertencias metodológicas", s.de_tipo("advertencia"), "Sin advertencias.")
    lineas += _seccion("Correcciones y aclaraciones", s.de_tipo("correccion"), "Sin correcciones.")

    lineas += ["## Contradicciones", ""]
    for c in s.contradicciones:
        lineas += [f"- **{c['fuente_corregida']}** decía: «{c['afirmacion_original']}»",
                   f"- **{c['fuente_que_corrige']}** corrige: «{c['correccion']}»",
                   f"- **Resolución:** {c['resolucion']}"]
        if c.get("verificacion"):
            lineas.append(f"- **Verificación:** {c['verificacion']}")
        lineas.append("")
    if not s.contradicciones:
        lineas += ["_No se detectaron contradicciones entre fuentes._", ""]

    lineas += ["## Verificación con la herramienta local", ""]
    if s.consultas:
        lineas += ["| Consulta | Motivo | Disparador | Resultado | Interpretación |", "|---|---|---|---|---|"]
        for c in s.consultas:
            p = c["parametros"]
            lineas.append(f"| `{p['producto']} / {p['canal']} / {p['parametro']}` | {c['motivo']} | "
                          f"[{c['disparador']['fuente']}] «{c['disparador']['termino']}» | `{c['resultado']}` | "
                          f"{c['interpretacion']} |")
        lineas += ["", f"> Advertencia de la herramienta: _{s.consultas[0]['respuesta'].get('advertencia', '')}_", ""]
    else:
        omitidas = [e["detalle"] for e in s.traza if e["accion"] == "omitir_herramienta"]
        lineas += [f"No se consultó. {' '.join(omitidas)}", ""]

    lineas += ["## Impacto económico", "",
               f"Cualitativo: {s.justificacion}",
               "No se presenta una cifra: ninguna fuente aporta montos verificables.", ""]
    lineas += ["## Próximos pasos", ""]
    for i, p in enumerate(s.proximos, 1):
        fuentes = f" [{', '.join(p['fuentes'])}]" if p["fuentes"] else ""
        lineas.append(f"{i}. {p['accion']}{fuentes}")
    abiertos = [f for f in s.de_tipo("faltante") if not f.nota]
    if abiertos:
        lineas.append(f"{len(s.proximos) + 1}. Resolver los {len(abiertos)} datos faltantes abiertos listados arriba.")
    lineas += ["", "## Fuentes consultadas", "", "| ID | Fecha | Tipo | Área | Título | Términos de asignación |",
               "|---|---|---|---|---|---|"]
    for d in s.docs:
        lineas.append(f"| {d.id} | {d.fecha} | {d.tipo} | {d.area} | {d.titulo} | {', '.join(s.terminos.get(d.id, []))} |")
    lineas += ["", f"Registro de investigación: [`trazabilidad/{s.id}.md`](../trazabilidad/{s.id}.md)", ""]
    return "\n".join(lineas)


def traza(s: Senal) -> str:
    lineas = [f"# Registro de investigación · {s.id} — {s.nombre}", "",
              "Acciones observables del agente, en orden. No incluye razonamiento interno del modelo.", "",
              "| Paso | Acción | Detalle |", "|---|---|---|"]
    for e in s.traza:
        detalle = e["detalle"].replace("|", "\\|")
        if "comando" in e:
            detalle += f"<br>`{e['comando']}`"
        lineas.append(f"| {e['paso']} | `{e['accion']}` | {detalle} |")
    pendientes = [f for f in s.de_tipo("faltante") if not f.nota]
    lineas += ["", "## Aspectos no resueltos", ""]
    lineas += [f"- [{a.doc_id}] {' '.join(a.cita.split())}" for a in pendientes] or ["- Ninguno identificado."]
    resueltos = [f for f in s.de_tipo("faltante") if f.nota]
    if resueltos:
        lineas += ["", "## Dudas resueltas por fuentes posteriores", ""]
        lineas += [f"- [{a.doc_id}] {' '.join(a.cita.split())} — _{a.nota}_" for a in resueltos]
    respuestas = [e for e in s.traza if e["accion"] == "consultar_herramienta"]
    if respuestas:
        lineas += ["", "## Respuestas completas de la herramienta", ""]
        for e in respuestas:
            lineas += [f"`{e['comando']}`", "", "```json", json.dumps(e["respuesta"], ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lineas) + "\n"


def escribir(r: Resultado, cambios: list[str]) -> None:
    (DIR_SALIDAS / "briefs").mkdir(parents=True, exist_ok=True)
    (DIR_SALIDAS / "trazabilidad").mkdir(parents=True, exist_ok=True)
    for vieja in [*(DIR_SALIDAS / "briefs").glob("*.md"), *(DIR_SALIDAS / "trazabilidad").glob("*.*")]:
        vieja.unlink()
    (DIR_SALIDAS / "senales_priorizadas.md").write_text(ranking(r, cambios), encoding="utf-8")
    for s in r.senales:
        (DIR_SALIDAS / "briefs" / f"{s.id}.md").write_text(brief(s, r), encoding="utf-8")
        (DIR_SALIDAS / "trazabilidad" / f"{s.id}.md").write_text(traza(s), encoding="utf-8")
        with (DIR_SALIDAS / "trazabilidad" / f"{s.id}.jsonl").open("w", encoding="utf-8") as f:
            for e in s.traza:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with (DIR_SALIDAS / "trazabilidad" / "global.jsonl").open("w", encoding="utf-8") as f:
        for e in r.traza_global:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    if cambios:
        (DIR_SALIDAS / "cambios.md").write_text(
            "# Cambios frente al análisis anterior\n\n" + "\n".join(f"- {c}" for c in cambios) + "\n", encoding="utf-8")
