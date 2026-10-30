"""Orquestación: documentos → afirmaciones → señales → herramienta → prioridad → salidas."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import clasificador, herramienta, llm
from .ingesta import RAIZ, Documento, cargar_corpus, normalizar

CATALOGO = RAIZ / "config" / "catalogo_senales.json"
DIR_SALIDAS = RAIZ / "salidas"
_TIPOS_ABIERTOS = ("hipotesis", "faltante", "correccion")
_REFERENCIA_PREVIA = re.compile(r"anterior|previ[oa]|mencionad|se informo|\bF\d{2}\b")
_STOP = {"sobre", "entre", "desde", "hasta", "para", "como", "pero", "tiene", "todos", "cada", "algunos",
         "antes", "estado", "equipo", "solicita"}


@dataclass
class Afirmacion:
    doc_id: str
    tipo: str
    cita: str
    inicio: int
    fin: int
    origen: str
    explicacion: str = ""
    nota: str = ""


@dataclass
class Senal:
    id: str
    nombre: str
    naturaleza: str
    impacto: int
    justificacion: str
    acciones: list[str]
    consultas_config: list[dict]
    nota_herramienta: str = ""
    emergente: bool = False
    docs: list[Documento] = field(default_factory=list)
    terminos: dict[str, list[str]] = field(default_factory=dict)
    afirmaciones: list[Afirmacion] = field(default_factory=list)
    consultas: list[dict] = field(default_factory=list)
    contradicciones: list[dict] = field(default_factory=list)
    traza: list[dict] = field(default_factory=list)
    evidencia: float = 0.0
    confianza: float = 0.0
    prioridad: float = 0.0
    rank: int = 0
    estado: str = ""
    resumen: str = ""
    proximos: list[dict] = field(default_factory=list)

    def de_tipo(self, *tipos: str) -> list[Afirmacion]:
        return [a for a in self.afirmaciones if a.tipo in tipos]


@dataclass
class Resultado:
    modo: str
    generado: str
    docs: list[Documento]
    descartados: list[dict]
    senales: list[Senal]
    traza_global: list[dict]
    uso_llm: list[dict]
    avisos: list[str] = field(default_factory=list)


def _evento(traza: list[dict], accion: str, detalle: str, **datos) -> None:
    traza.append({"paso": len(traza) + 1, "accion": accion, "detalle": detalle, **datos})


def _raices(texto: str) -> set[str]:
    return {p[:6] for p in re.findall(r"[a-z_]{5,}", normalizar(texto)) if p not in _STOP}


# ---------- Extracción por documento ----------

def _extraer_reglas(doc: Documento) -> list[Afirmacion]:
    afirmaciones = []
    for o in doc.oraciones:
        tipo, patron = clasificador.clasificar(o.texto)
        afirmaciones.append(Afirmacion(doc.id, tipo, o.texto, o.inicio, o.fin, "reglas",
                                       f"patrón: {patron}" if patron else "sin marcador de duda"))
    return afirmaciones


def _extraer_llm(doc: Documento, temas: list[dict], traza: list[dict], uso: list[dict]):
    """Devuelve (afirmaciones, datos del modelo) o None si este documento vuelve a reglas.
    Lanza LLMNoDisponible si el servicio no está disponible para ningún documento."""
    try:
        datos, meta = llm.extraer_documento(doc, temas)
    except json.JSONDecodeError as e:
        _evento(traza, "llm_fallback", f"{doc.id}: JSON inválido ({e}). Se usa el modo reglas.", fuente=doc.id)
        return None
    uso.append({"doc": doc.id, **meta})
    afirmaciones, rechazadas = [], 0
    for item in datos["afirmaciones"]:
        cita = item["cita"].strip()
        inicio = doc.texto.find(cita)
        if not cita or inicio < 0:
            rechazadas += 1
            continue
        afirmaciones.append(Afirmacion(doc.id, item["tipo"], cita, inicio, inicio + len(cita), "llm",
                                       item.get("explicacion", "")))
    _evento(traza, "verificar_citas_llm",
            f"{doc.id}: {len(afirmaciones)} citas literales verificadas, {rechazadas} descartadas por no aparecer en la fuente.",
            fuente=doc.id)
    if not afirmaciones:
        return None
    return afirmaciones, datos


def _puntuar(doc: Documento, afirmaciones: list[Afirmacion], tema: dict) -> tuple[int, list[str]]:
    texto = normalizar(doc.titulo + " " + " ".join(a.cita for a in afirmaciones if a.tipo != "negacion_impacto"))
    hits, puntos = [], 0
    for termino in tema["terminos_fuertes"]:
        if normalizar(termino) in texto:
            puntos += 2
            hits.append(termino)
    for termino in tema["terminos_debiles"]:
        if normalizar(termino) in texto:
            puntos += 1
            hits.append(termino)
    return puntos, hits


# ---------- Análisis por señal ----------

def _marcar_confirmaciones(s: Senal) -> None:
    for conf in s.de_tipo("confirmacion"):
        doc_conf = next(d for d in s.docs if d.id == conf.doc_id)
        raices = _raices(conf.cita)
        for hip in s.de_tipo("hipotesis"):
            doc_hip = next(d for d in s.docs if d.id == hip.doc_id)
            if doc_hip.orden < doc_conf.orden and len(raices & _raices(hip.cita)) >= 2:
                hip.nota = f"confirmada por {conf.doc_id}"
                _evento(s.traza, "confirmacion",
                        f"{conf.doc_id} confirma la hipótesis de {hip.doc_id}.", fuentes=[hip.doc_id, conf.doc_id])


def _detectar_contradicciones(s: Senal) -> None:
    """Una corrección que alude a una fuente previa se enfrenta a la afirmación anterior más afín
    (hipótesis o hecho): gana la que comparte más raíces, y ante empate la más reciente."""
    for doc in s.docs:
        correcciones = [a for a in s.afirmaciones if a.doc_id == doc.id and a.tipo == "correccion"]
        explicitas = [a for a in correcciones if _REFERENCIA_PREVIA.search(normalizar(a.cita))]
        if not explicitas:
            continue
        corr = explicitas[0]
        propias = [a.cita for a in s.afirmaciones if a.doc_id == doc.id and a.tipo in ("correccion", "hecho", "confirmacion")]
        base = _raices(doc.titulo + " " + " ".join(propias))
        menciona_tipo = normalizar(corr.cita)
        candidatos = []
        for previo in s.docs:
            if previo.orden >= doc.orden:
                continue
            bonus = 1 if normalizar(previo.tipo).split()[0] in menciona_tipo else 0
            bonus += 1 if normalizar(previo.area) in menciona_tipo else 0
            for hip in s.afirmaciones:
                if hip.doc_id == previo.id and hip.tipo in ("hipotesis", "hecho"):
                    comun = base & _raices(hip.cita)
                    if comun:
                        candidatos.append((len(comun) + bonus, previo.orden, previo, hip))
        if not candidatos:
            continue
        _, _, previo, hip = max(candidatos, key=lambda c: (c[0], c[1]))
        hip.nota = f"superada por {doc.id}"
        resolucion = (f"Prevalece {doc.id} ({doc.fecha}, {doc.area}) sobre {previo.id} ({previo.fecha}): "
                      f"es posterior y corrige explícitamente la versión anterior.")
        s.contradicciones.append({"fuente_corregida": previo.id, "fuente_que_corrige": doc.id,
                                  "afirmacion_original": hip.cita, "correccion": corr.cita, "resolucion": resolucion})
        _evento(s.traza, "resolver_contradiccion", resolucion, fuentes=[previo.id, doc.id])


def _decidir_herramienta(s: Senal) -> None:
    if not s.consultas_config:
        motivo = s.nota_herramienta or "No hay un parámetro de la herramienta asociado a esta señal."
        _evento(s.traza, "omitir_herramienta", motivo)
        return
    abiertas = s.de_tipo(*_TIPOS_ABIERTOS)
    for c in s.consultas_config:
        disparo = next(((a, t) for a in abiertas for t in c["disparadores"] if normalizar(t) in normalizar(a.cita)), None)
        etiqueta = f"{c['producto']} / {c['canal']} / {c['parametro']}"
        if not disparo:
            _evento(s.traza, "omitir_herramienta",
                    f"{etiqueta}: ninguna hipótesis o dato faltante lo justifica.", parametros=c)
            continue
        afirmacion, termino = disparo
        _evento(s.traza, "decidir_herramienta",
                f"Consultar {etiqueta}. {c['motivo']} Disparador: «{termino}» en {afirmacion.doc_id}.",
                fuentes=[afirmacion.doc_id])
        ejecucion = herramienta.consultar(c["producto"], c["canal"], c["parametro"])
        codigo, interpretacion = herramienta.interpretar(ejecucion["respuesta"])
        consulta = {"parametros": {k: c[k] for k in ("producto", "canal", "parametro")}, "motivo": c["motivo"],
                    "disparador": {"fuente": afirmacion.doc_id, "termino": termino, "cita": afirmacion.cita},
                    **ejecucion, "resultado": codigo, "interpretacion": interpretacion}
        s.consultas.append(consulta)
        comando = " ".join(f'"{a}"' if " " in a else a for a in ejecucion["comando"])
        _evento(s.traza, "consultar_herramienta", interpretacion, comando=comando, respuesta=ejecucion["respuesta"])
        revision = (ejecucion["respuesta"].get("registros") or [{}])[0].get("ultima_revision", "")
        for contradiccion in s.contradicciones:
            fecha_corrige = next(d.fecha for d in s.docs if d.id == contradiccion["fuente_que_corrige"])
            if revision and revision < fecha_corrige:
                contradiccion["verificacion"] = (
                    f"El registro de la herramienta ({revision}) es anterior a {contradiccion['fuente_que_corrige']} "
                    f"({fecha_corrige}): no permite validar la corrección. Pendiente: confirmarla con el área.")
                _evento(s.traza, "verificar_contradiccion", contradiccion["verificacion"],
                        fuentes=[contradiccion["fuente_corregida"], contradiccion["fuente_que_corrige"]])
            elif contradiccion["fuente_corregida"] == afirmacion.doc_id and codigo == "no_desplegado":
                contradiccion["verificacion"] = (f"La herramienta respalda a {contradiccion['fuente_que_corrige']}: "
                                                 f"{interpretacion}")
                _evento(s.traza, "verificar_contradiccion", contradiccion["verificacion"],
                        fuentes=[contradiccion["fuente_corregida"], contradiccion["fuente_que_corrige"]])


def _puntuar_senal(s: Senal) -> None:
    hechos = len(s.de_tipo("hecho"))
    confirmaciones = len(s.de_tipo("confirmacion"))
    consultas_utiles = sum(1 for c in s.consultas if c["resultado"] not in ("sin_registro", "error"))
    s.evidencia = round(min(5.0, 1 + 0.5 * hechos + 0.5 * len(s.docs) + 1.5 * confirmaciones + 0.5 * consultas_utiles), 2)
    s.confianza = round(0.5 + 0.1 * s.evidencia, 2)
    s.prioridad = round(s.impacto * s.confianza, 2)
    if confirmaciones:
        s.estado = "Confirmada en fuente; impacto pendiente de cuantificar"
    elif s.de_tipo("hipotesis", "faltante"):
        s.estado = "Por validar"
    else:
        s.estado = "Documentada"
    if s.contradicciones:
        s.estado += " · contradicción resuelta"
    _evento(s.traza, "priorizar",
            f"Impacto {s.impacto}/5 × confianza {s.confianza} = {s.prioridad} "
            f"(evidencia {s.evidencia}/5: {hechos} hechos, {len(s.docs)} fuentes, {confirmaciones} confirmaciones, "
            f"{consultas_utiles} consultas con registro).")


def _redactar(s: Senal, modo: str, traza_global: list[dict], uso: list[dict]) -> None:
    ids = ", ".join(d.id for d in s.docs)
    partes = [f"{s.naturaleza}. Basada en {len(s.docs)} fuente(s) ({ids}): "
              f"{len(s.de_tipo('hecho'))} hechos, {len(s.de_tipo('hipotesis'))} hipótesis y "
              f"{len(s.de_tipo('faltante'))} datos faltantes."]
    for c in s.consultas:
        p = c["parametros"]
        partes.append(f"Herramienta ({p['canal']}/{p['parametro']}): {c['interpretacion']}")
    # Contraste entre canales del mismo parámetro: uno conforme y otro no acota la duda.
    por_parametro: dict[str, dict[str, str]] = {}
    for c in s.consultas:
        por_parametro.setdefault(c["parametros"]["parametro"], {})[c["parametros"]["canal"]] = c["resultado"]
    for parametro, canales in por_parametro.items():
        dudosos = [k for k, v in canales.items() if v in ("no_verificado", "revisar")]
        conformes = [k for k, v in canales.items() if v == "conforme"]
        if dudosos and conformes:
            cierre = ("La confirmación proviene de las fuentes, no de la herramienta."
                      if s.de_tipo("confirmacion") else "No prueba el defecto.")
            partes.append(f"El contraste acota la duda sobre {parametro} al canal {', '.join(dudosos)}; "
                          f"{', '.join(conformes)} está conforme. {cierre}")
    for c in s.contradicciones:
        partes.append(c["resolucion"] + (f" {c['verificacion']}" if c.get("verificacion") else ""))
    if s.de_tipo("confirmacion"):
        partes.append("Existe confirmación en fuente, pero el impacto económico sigue sin cuantificar.")
    else:
        partes.append("No se cuantifica pérdida ni ganancia: la evidencia disponible no lo permite.")
    s.resumen = " ".join(partes)
    s.proximos = [{"accion": a, "fuentes": []} for a in s.acciones]

    if modo != "llm":
        return
    afirmaciones = [{"fuente": a.doc_id, "tipo": a.tipo, "cita": a.cita, "nota": a.nota} for a in s.afirmaciones]
    consultas = [{"parametros": c["parametros"], "interpretacion": c["interpretacion"]} for c in s.consultas]
    try:
        datos, meta = llm.redactar_brief(s.nombre, afirmaciones, consultas)
    except (llm.LLMNoDisponible, json.JSONDecodeError) as e:
        _evento(s.traza, "llm_fallback", f"Resumen con plantilla: {e}.")
        return
    uso.append({"senal": s.id, **meta})
    validos = {d.id for d in s.docs}
    citados = set(re.findall(r"F\d{2}", datos["resumen"]))
    if not citados <= validos:
        _evento(s.traza, "rechazar_resumen_llm", f"El resumen citaba fuentes ajenas a la señal: {sorted(citados - validos)}.")
        return
    s.resumen = datos["resumen"]
    s.proximos = [p for p in datos["proximos_pasos"] if set(p["fuentes"]) <= validos] or s.proximos
    _evento(s.traza, "redactar_resumen_llm", f"Resumen y próximos pasos redactados por {llm.MODELO}; IDs verificados.")


# ---------- Pipeline ----------

def analizar(modo: str = "reglas", extra: list[Path] | tuple[Path, ...] = ()) -> Resultado:
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    temas = {t["id"]: t for t in catalogo["temas"]}
    terminos_econ = catalogo["terminos_economicos"]
    traza: list[dict] = []
    uso: list[dict] = []

    avisos: list[str] = []
    docs = cargar_corpus(extra, avisos)
    for aviso in avisos:
        _evento(traza, "aviso_indice", aviso)
    _evento(traza, "ingestar", f"{len(docs)} documentos leídos sin modificar.",
            fuentes=[d.id for d in docs], sha256={d.id: d.sha256[:12] for d in docs})
    for d in docs:
        if d.origen == "no_indexada":
            _evento(traza, "ingestar_no_indexada",
                    f"{d.ruta.name} no figura en ningún índice; se incorpora como {d.id} ({d.fecha}).", fuente=d.id)

    senales: dict[str, Senal] = {}
    descartados: list[dict] = []
    for doc in docs:
        datos_llm = resultado_llm = None
        if modo == "llm":
            try:
                resultado_llm = _extraer_llm(doc, catalogo["temas"], traza, uso)
            except llm.LLMNoDisponible as e:
                modo = f"reglas (LLM no disponible: {e})"
                _evento(traza, "llm_fallback", f"{e}. Todo el análisis continúa en modo reglas.")
        if resultado_llm:
            afirmaciones, datos_llm = resultado_llm
        else:
            afirmaciones = _extraer_reglas(doc)
        for a in afirmaciones:
            assert doc.texto[a.inicio:a.fin] == a.cita, f"Cita no literal en {doc.id}"

        negaciones = [a for a in afirmaciones if a.tipo == "negacion_impacto"]
        abiertas = [a for a in afirmaciones if a.tipo not in ("hecho", "negacion_impacto")]
        economico = clasificador.tiene_termino_economico(
            " ".join(a.cita for a in afirmaciones if a.tipo != "negacion_impacto"), terminos_econ)

        if datos_llm is not None:
            tema_id = datos_llm["tema"]
            relevante = datos_llm["relevante"] and tema_id != "NINGUNO"
            hits = ["(asignado por LLM)"]
            if tema_id not in temas and tema_id != "NUEVO":
                tema_id = "NUEVO" if relevante else "NINGUNO"
        else:
            puntuados = sorted(((*_puntuar(doc, afirmaciones, t), t["id"]) for t in temas.values()), reverse=True)
            puntos, hits, tema_id = puntuados[0]
            relevante = not (negaciones and not abiertas)
            if puntos < 2:
                tema_id = "NUEVO" if (relevante and economico and abiertas) else "NINGUNO"

        if not relevante or tema_id == "NINGUNO":
            motivo = (datos_llm or {}).get("motivo_descarte") or (
                "Declara explícitamente que no hay impacto económico." if negaciones
                else "Sin términos ni afirmaciones con potencial económico.")
            cita = negaciones[0] if negaciones else None
            descartados.append({"id": doc.id, "titulo": doc.titulo, "motivo": motivo,
                                "cita": cita.cita if cita else ""})
            _evento(traza, "descartar_ruido", f"{doc.id}: {motivo}", fuente=doc.id, cita=cita.cita if cita else "")
            continue

        if tema_id == "NUEVO":
            impacto = catalogo["impacto_emergente"]
            if datos_llm and 1 <= datos_llm["impacto_estimado"] <= 5:
                impacto = datos_llm["impacto_estimado"]
            nombre = (datos_llm or {}).get("nombre_tema_nuevo") or doc.titulo
            sid = f"E-{doc.id}"
            senales[sid] = Senal(sid, nombre, "Señal emergente no catalogada", impacto,
                                 "Impacto por evaluar: el tema no está en el catálogo de dominio.",
                                 ["Validar con el área responsable si el hallazgo tiene impacto en ingresos.",
                                  "Identificar si existe un parámetro o registro verificable para este tema."],
                                 [], "No hay consultas configuradas para temas emergentes.", emergente=True)
            tema_id = sid
        elif tema_id not in senales:
            t = temas[tema_id]
            senales[tema_id] = Senal(t["id"], t["nombre"], t["naturaleza"], t["impacto"], t["justificacion_impacto"],
                                     t["acciones"], t["consultas"], t.get("nota_herramienta", ""))
        s = senales[tema_id]
        s.docs.append(doc)
        s.terminos[doc.id] = hits
        s.afirmaciones.extend(a for a in afirmaciones if a.tipo != "negacion_impacto")
        _evento(s.traza, "asignar_fuente", f"{doc.id} ({doc.fecha}, {doc.tipo}) por términos: {', '.join(hits)}.",
                fuente=doc.id)

    for s in senales.values():
        conteo = {t: len(s.de_tipo(t)) for t in clasificador.TIPOS if s.de_tipo(t)}
        _evento(s.traza, "clasificar_afirmaciones",
                f"{len(s.afirmaciones)} citas literales verificadas contra el texto original: {conteo}.")
        _marcar_confirmaciones(s)
        _detectar_contradicciones(s)
        _decidir_herramienta(s)
        _puntuar_senal(s)
        _redactar(s, modo, traza, uso)
        _evento(s.traza, "pendientes",
                f"{len(s.de_tipo('faltante'))} datos faltantes sin resolver.",
                fuentes=sorted({f.doc_id for f in s.de_tipo("faltante")}))

    ordenadas = sorted(senales.values(), key=lambda s: (-s.prioridad, s.id))
    for i, s in enumerate(ordenadas, 1):
        s.rank = i
    return Resultado(modo, datetime.now().isoformat(timespec="seconds"), docs, descartados, ordenadas, traza, uso,
                     avisos)


# ---------- Estado y cambios ----------

def resumen_estado(r: Resultado) -> dict:
    return {
        "generado": r.generado,
        "modo": r.modo,
        "documentos": [d.id for d in r.docs],
        "descartados": [d["id"] for d in r.descartados],
        "senales": {
            s.id: {
                "nombre": s.nombre, "rank": s.rank, "prioridad": s.prioridad, "estado": s.estado,
                "fuentes": [d.id for d in s.docs],
                "conteo": {t: len(s.de_tipo(t)) for t in clasificador.TIPOS},
                "hipotesis": {a.cita: a.nota for a in s.de_tipo("hipotesis")},
                "consultas": {f"{c['parametros']['canal']}/{c['parametros']['parametro']}": c["resultado"]
                              for c in s.consultas},
                "contradicciones": [f"{c['fuente_que_corrige']}→{c['fuente_corregida']}" for c in s.contradicciones],
            }
            for s in r.senales
        },
    }


def comparar(anterior: dict, actual: dict) -> list[str]:
    cambios: list[str] = []
    nuevos = [d for d in actual["documentos"] if d not in anterior["documentos"]]
    if nuevos:
        cambios.append(f"Documentos nuevos: {', '.join(nuevos)}.")
    for d in nuevos:
        if d in actual["descartados"]:
            cambios.append(f"{d} se descartó como ruido.")
    previas, ahora = anterior["senales"], actual["senales"]
    for sid, s in ahora.items():
        if sid not in previas:
            cambios.append(f"Nueva señal {sid} «{s['nombre']}» en el puesto {s['rank']} (prioridad {s['prioridad']}).")
            continue
        p = previas[sid]
        for f in s["fuentes"]:
            if f not in p["fuentes"]:
                cambios.append(f"{sid}: incorpora {f}.")
        if s["prioridad"] != p["prioridad"]:
            puesto = f" (puesto {p['rank']} → {s['rank']})" if s["rank"] != p["rank"] else ""
            cambios.append(f"{sid}: prioridad {p['prioridad']} → {s['prioridad']}{puesto}.")
        elif s["rank"] != p["rank"]:
            cambios.append(f"{sid}: pasa del puesto {p['rank']} al {s['rank']} por la entrada de otras señales.")
        if s["estado"] != p["estado"]:
            cambios.append(f"{sid}: estado «{p['estado']}» → «{s['estado']}».")
        for tipo, n in s["conteo"].items():
            delta = n - p["conteo"].get(tipo, 0)
            if delta:
                cambios.append(f"{sid}: {clasificador.ETIQUETAS[tipo]} {delta:+d}.")
        for cita, nota in s["hipotesis"].items():
            if nota and p["hipotesis"].get(cita) != nota:
                cambios.append(f"{sid}: hipótesis «{cita[:80]}…» ahora {nota}.")
        for clave, res in s["consultas"].items():
            if p["consultas"].get(clave) != res:
                cambios.append(f"{sid}: herramienta {clave}: {p['consultas'].get(clave, 'sin consulta')} → {res}.")
        for c in s["contradicciones"]:
            if c not in p["contradicciones"]:
                cambios.append(f"{sid}: nueva contradicción resuelta ({c}).")
    for sid in previas:
        if sid not in ahora:
            cambios.append(f"La señal {sid} desapareció.")
    return cambios or ["Sin cambios respecto al análisis anterior."]


def guardar(r: Resultado) -> list[str]:
    """Escribe salidas y devuelve los cambios frente al estado previo."""
    from . import reporte

    DIR_SALIDAS.mkdir(exist_ok=True)
    ruta_estado = DIR_SALIDAS / "estado.json"
    actual = resumen_estado(r)
    cambios = []
    if ruta_estado.exists():
        anterior = json.loads(ruta_estado.read_text(encoding="utf-8"))
        cambios = comparar(anterior, actual)
        (DIR_SALIDAS / "estado_anterior.json").write_text(json.dumps(anterior, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_estado.write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding="utf-8")
    reporte.escribir(r, cambios)
    return cambios
