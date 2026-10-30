"""Ingesta de fuentes: lee los índices y los documentos sin modificarlos."""
from __future__ import annotations

import csv
import hashlib
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATA = RAIZ / "data"
INDICE = DIR_DATA / "indice_fuentes.csv"
DIR_ADICIONALES = DIR_DATA / "fuentes_adicionales"
INDICE_ADICIONAL = DIR_ADICIONALES / "indice_adicional.csv"
CAMPOS_INDICE = ["id", "fecha", "tipo", "area", "titulo", "archivo"]

_CABECERA = re.compile(r"^\*\*(ID|Fecha|Tipo|Área|Area):\*\*\s*(.+?)\s*$")
# Corte de oración: signo final seguido de espacio y mayúscula (evita cortar "anual-a-mensual." al final).
_CORTE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿«\"])")


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar términos."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower()


@dataclass
class Oracion:
    doc_id: str
    n: int
    texto: str
    inicio: int
    fin: int


@dataclass
class Documento:
    id: str
    fecha: str
    tipo: str
    area: str
    titulo: str
    ruta: Path
    texto: str
    sha256: str
    origen: str
    oraciones: list[Oracion] = field(default_factory=list)

    @property
    def orden(self) -> tuple[str, str]:
        return (self.fecha, self.id)


def leer_cabecera(texto: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for linea in texto.splitlines():
        limpia = linea.strip()
        if limpia.startswith("# ") and "titulo" not in meta:
            meta["titulo"] = limpia[2:].strip()
        m = _CABECERA.match(limpia)
        if m:
            meta[normalizar(m.group(1))] = m.group(2)
    return meta


def segmentar(doc_id: str, texto: str) -> list[Oracion]:
    """Divide el cuerpo en oraciones guardando su posición exacta en el texto original.
    Un párrafo son líneas de cuerpo consecutivas: un salto de línea a mitad de frase no la corta."""
    bloques: list[tuple[int, int]] = []
    inicio_parrafo = fin_parrafo = None
    offset = 0
    for linea in texto.splitlines(keepends=True):
        limpio = linea.strip()
        if limpio and not limpio.startswith("#") and not _CABECERA.match(limpio):
            if inicio_parrafo is None:
                inicio_parrafo = offset
            fin_parrafo = offset + len(linea.rstrip("\r\n"))
        elif inicio_parrafo is not None:
            bloques.append((inicio_parrafo, fin_parrafo))
            inicio_parrafo = None
        offset += len(linea)
    if inicio_parrafo is not None:
        bloques.append((inicio_parrafo, fin_parrafo))

    oraciones: list[Oracion] = []
    for a, b in bloques:
        contenido = texto[a:b]
        pos = 0
        tramos = []
        for corte in _CORTE.finditer(contenido):
            tramos.append((pos, corte.start()))
            pos = corte.end()
        tramos.append((pos, len(contenido)))
        for x, y in tramos:
            fragmento = contenido[x:y]
            frase = fragmento.strip()
            if frase:
                inicio = a + x + (len(fragmento) - len(fragmento.lstrip()))
                oraciones.append(Oracion(doc_id, len(oraciones) + 1, frase, inicio, inicio + len(frase)))
    return oraciones


def _cargar(ruta: Path, fila: dict[str, str], origen: str) -> Documento:
    texto = leer_texto(ruta)
    meta = leer_cabecera(texto)
    doc_id = fila.get("id") or meta.get("id", "")
    return Documento(
        id=doc_id,
        fecha=fila.get("fecha") or meta.get("fecha", ""),
        tipo=fila.get("tipo") or meta.get("tipo", ""),
        area=fila.get("area") or meta.get("area", ""),
        titulo=fila.get("titulo") or meta.get("titulo", ruta.stem),
        ruta=ruta,
        texto=texto,
        sha256=hashlib.sha256(ruta.read_bytes()).hexdigest(),
        origen=origen,
        oraciones=segmentar(doc_id, texto),
    )


def leer_texto(ruta: Path) -> str:
    """UTF-8 (con o sin BOM); si falla, la codificación de Windows con la que guardan Excel o el Bloc de notas."""
    datos = ruta.read_bytes()
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return datos.decode("cp1252")


def _leer_indice(ruta: Path, avisos: list[str]) -> list[dict[str, str]]:
    """Lee un índice tolerando lo que suele romperse al editarlo a mano o con Excel:
    separador ';', codificación de Windows y títulos con comas sin comillas."""
    if not ruta.exists():
        return []
    texto = leer_texto(ruta)
    primera = texto.splitlines()[0] if texto else ""
    separador = ";" if primera.count(";") > primera.count(",") else ","
    filas = list(csv.reader(texto.splitlines(), delimiter=separador))
    if not filas:
        return []
    cabecera = [c.strip().lower() for c in filas[0]]
    resultado = []
    for n, valores in enumerate(filas[1:], start=2):
        if not any(v.strip() for v in valores):
            continue
        if len(valores) > len(cabecera) and cabecera == CAMPOS_INDICE:
            # Coma dentro del título: id, fecha, tipo y área van primero y el archivo al final.
            valores = valores[:4] + [separador.join(valores[4:-1]), valores[-1]]
            avisos.append(f"{ruta.name}, línea {n}: había comas sin comillas en el título; se reconstruyó.")
        if len(valores) != len(cabecera):
            avisos.append(f"{ruta.name}, línea {n}: {len(valores)} columnas en vez de {len(cabecera)}; se omite.")
            continue
        resultado.append({k: v.strip() for k, v in zip(cabecera, valores)})
    return resultado


def siguiente_id(ids: list[str]) -> str:
    numeros = [int(i[1:]) for i in ids if re.fullmatch(r"F\d+", i)]
    return f"F{(max(numeros) if numeros else 0) + 1:02d}"


def _fila_para(ruta: Path, ids_existentes: list[str]) -> dict[str, str]:
    """Metadatos de un documento nuevo: usa su cabecera y completa lo que falte."""
    meta = leer_cabecera(leer_texto(ruta))
    nombre = re.match(r"(F\d+)", ruta.stem)
    doc_id = meta.get("id") or (nombre.group(1) if nombre else "")
    if not doc_id or doc_id in ids_existentes:
        doc_id = siguiente_id(ids_existentes)
    return {
        "id": doc_id,
        "fecha": meta.get("fecha") or date.today().isoformat(),
        "tipo": meta.get("tipo", "Documento adicional"),
        "area": meta.get("area", "Sin área"),
        "titulo": meta.get("titulo", ruta.stem),
    }


def cargar_corpus(extra: list[Path] | tuple[Path, ...] = (), avisos: list[str] | None = None) -> list[Documento]:
    """Paquete original + fuentes adicionales registradas + .md copiados a mano sin indexar
    + rutas extra (sin persistir). Los problemas del índice se anotan en `avisos` sin detener nada."""
    avisos = [] if avisos is None else avisos
    docs: list[Documento] = []
    for indice, carpeta, origen in ((INDICE, INDICE.parent, "paquete"),
                                    (INDICE_ADICIONAL, DIR_ADICIONALES, "adicional")):
        for fila in _leer_indice(indice, avisos):
            ruta = carpeta / fila.get("archivo", "")
            if not fila.get("archivo") or not ruta.is_file():
                avisos.append(f"{indice.name}: {fila.get('id', '?')} apunta a '{fila.get('archivo', '')}', "
                              "que no existe; se omite esa fila.")
                continue
            if fila.get("id") in {d.id for d in docs}:
                avisos.append(f"{indice.name}: el ID {fila['id']} está repetido; se omite la segunda fila.")
                continue
            docs.append(_cargar(ruta, fila, origen))
    # Un archivo dejado en la carpeta sin actualizar el índice no debe ignorarse en silencio.
    leidas = {d.ruta.resolve() for d in docs}
    for carpeta in (DIR_DATA / "fuentes", DIR_ADICIONALES):
        for ruta in sorted(carpeta.glob("*.md")) if carpeta.exists() else []:
            if ruta.resolve() not in leidas:
                docs.append(_cargar(ruta, _fila_para(ruta, [d.id for d in docs]), "no_indexada"))
    for ruta in extra:
        fila = _fila_para(Path(ruta), [d.id for d in docs])
        docs.append(_cargar(Path(ruta), fila, "adicional"))
    return sorted(docs, key=lambda d: d.orden)


def agregar_fuente(ruta: Path) -> str:
    """Copia un documento nuevo (sin editarlo) a data/fuentes_adicionales y lo registra."""
    ruta = Path(ruta)
    ids = [d.id for d in cargar_corpus()]
    fila = _fila_para(ruta, ids)
    DIR_ADICIONALES.mkdir(parents=True, exist_ok=True)
    destino = DIR_ADICIONALES / f"{fila['id']}_{ruta.name}"
    shutil.copyfile(ruta, destino)
    fila["archivo"] = destino.name
    nuevo = not INDICE_ADICIONAL.exists()
    with INDICE_ADICIONAL.open("a", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_INDICE)
        if nuevo:
            escritor.writeheader()
        escritor.writerow(fila)
    return fila["id"]
