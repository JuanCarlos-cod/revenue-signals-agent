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
    """Divide el cuerpo en oraciones guardando su posición exacta en el texto original."""
    oraciones: list[Oracion] = []
    offset = 0
    for linea in texto.splitlines(keepends=True):
        contenido = linea.rstrip("\r\n")
        limpio = contenido.strip()
        if limpio and not limpio.startswith("#") and not _CABECERA.match(limpio):
            pos = 0
            tramos = []
            for corte in _CORTE.finditer(contenido):
                tramos.append((pos, corte.start()))
                pos = corte.end()
            tramos.append((pos, len(contenido)))
            for a, b in tramos:
                fragmento = contenido[a:b]
                frase = fragmento.strip()
                if frase:
                    inicio = offset + a + (len(fragmento) - len(fragmento.lstrip()))
                    oraciones.append(Oracion(doc_id, len(oraciones) + 1, frase, inicio, inicio + len(frase)))
        offset += len(linea)
    return oraciones


def _cargar(ruta: Path, fila: dict[str, str], origen: str) -> Documento:
    texto = ruta.read_text(encoding="utf-8")
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


def _leer_indice(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def siguiente_id(ids: list[str]) -> str:
    numeros = [int(i[1:]) for i in ids if re.fullmatch(r"F\d+", i)]
    return f"F{(max(numeros) if numeros else 0) + 1:02d}"


def _fila_para(ruta: Path, ids_existentes: list[str]) -> dict[str, str]:
    """Metadatos de un documento nuevo: usa su cabecera y completa lo que falte."""
    meta = leer_cabecera(ruta.read_text(encoding="utf-8"))
    doc_id = meta.get("id", "")
    if not doc_id or doc_id in ids_existentes:
        doc_id = siguiente_id(ids_existentes)
    return {
        "id": doc_id,
        "fecha": meta.get("fecha") or date.today().isoformat(),
        "tipo": meta.get("tipo", "Documento adicional"),
        "area": meta.get("area", "Sin área"),
        "titulo": meta.get("titulo", ruta.stem),
    }


def cargar_corpus(extra: list[Path] | tuple[Path, ...] = ()) -> list[Documento]:
    """Paquete original + fuentes adicionales registradas + rutas extra (sin persistir)."""
    docs = [_cargar(INDICE.parent / f["archivo"], f, "paquete") for f in _leer_indice(INDICE)]
    docs += [_cargar(DIR_ADICIONALES / f["archivo"], f, "adicional") for f in _leer_indice(INDICE_ADICIONAL)]
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
