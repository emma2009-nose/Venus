import re
from pathlib import Path

from docx import Document

from . import state
from .config import LargoMaxNombre, NombrePredeterminado

EtiquetaTurno = re.compile(r"^(User|Venus|Sistema): ", re.MULTILINE)
EtiquetaImagen = re.compile(r"\[imagen:\s*([^\]\n]+?)\s*\]", re.IGNORECASE)

# Etiquetas internas que algunos modelos anaden aunque el prompt no las pida.
EtiquetaRespuesta = re.compile(
    r"^[ \t]*(?:[#>*_\-]+[ \t]*)?"
    r"(?:M[EÉ]TODO(?:\s+USADO)?|SEGURIDAD|SEM[AÁ]FORO|CLASIFICACI[OÓ]N)"
    r"[ \t]*:[^\n]*$",
    re.IGNORECASE,
)

# Linea de clasificacion que el prompt de produccion pedia al final:
#   SEGURIDAD: baja | MÉTODO: nmap -sV
LineaClasificacion = re.compile(
    r"\n?[ \t]*SEGURIDAD:[ \t]*([^|\n]+?)[ \t]*\|[ \t]*M[EÉ]TODO:[ \t]*([^\n]+?)[ \t]*\Z",
    re.IGNORECASE,
)


def LimpiarEtiquetas(Texto):
    """Quita lineas tipo 'Método: ...' o 'Seguridad: ...' de un mensaje."""
    if not Texto:
        return Texto
    Lineas = [Linea for Linea in Texto.splitlines() if not EtiquetaRespuesta.match(Linea)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(Lineas)).strip()


def SepararClasificacion(Texto):
    """Separa la ultima linea 'SEGURIDAD: x | METODO: y' del resto del texto."""
    Coincidencia = LineaClasificacion.search((Texto or "").rstrip())
    if not Coincidencia:
        return Texto, None, None
    return (Texto[:Coincidencia.start()].rstrip(),
            Coincidencia.group(1).strip().lower(),
            Coincidencia.group(2).strip())


def LimpiarRespuesta(Texto):
    """Deja la respuesta como debe verla el usuario (sin etiquetas internas)."""
    if not Texto:
        return Texto
    Texto, _Seguridad, _Metodo = SepararClasificacion(Texto)
    return LimpiarEtiquetas(Texto)


def LeerTextoArchivo(Ruta):
    Ruta = Path(Ruta)
    Sufijo = Ruta.suffix.lower()
    if Sufijo == ".txt":
        return Ruta.read_text(encoding="utf-8")
    if Sufijo == ".docx":
        Doc = Document(Ruta)
        return "\n".join(P.text for P in Doc.paragraphs)
    raise ValueError("Formato no soportado.")


def LimpiarComando(Texto):
    for Caracter in '&|<>^%"\r\n':
        Texto = Texto.replace(Caracter, " ")
    return " ".join(Texto.split())


def LimpiarNombre(Texto):
    return re.sub(r"\s+", " ", Texto or "").strip()[:LargoMaxNombre]


def NombreCortoManual(Titulo):
    """Devuelve solo el nombre de la herramienta de un manual.

    Ejemplos:
      "NMAP - GUÍA RÁPIDA COMPLETA Y EXPLICADA" -> "NMAP"
      "MANUAL DE HYDRA — PARTE 1"               -> "HYDRA"
      "TIPO LIBRO PYTHON"                       -> "PYTHON"
      "HYDRA GUIA RAPIDA DE REFERENCIA"          -> "HYDRA"
    """
    Nombre = re.sub(r"\.(txt|docx)$", "", (Titulo or "").strip(), flags=re.IGNORECASE)
    Nombre = re.sub(r"^\[IA\]\s*", "", Nombre, flags=re.IGNORECASE)
    for Separador in (" — ", " – ", " - ", " | ", ": "):
        if Separador in Nombre:
            Nombre = Nombre.split(Separador, 1)[0]
            break
    Nombre = re.sub(
        r"^(?:MANUAL(?:\s+DE)?|GU[IÍ]A|LIBRO|TIPO\s+LIBRO)\s+",
        "", Nombre, flags=re.IGNORECASE,
    )
    Nombre = re.split(
        r"\s+(?:GU[IÍ]A|MANUAL|LIBRO)\b", Nombre, maxsplit=1, flags=re.IGNORECASE
    )[0]
    Nombre = re.sub(r"\s*\(\d+\)\s*$", "", Nombre)
    Nombre = re.sub(r"\s+", " ", Nombre).strip(" ._-")
    return Nombre or "Manual"


def EtiquetaUsuario():
    return state.NombreUsuario if state.NombreUsuario != NombrePredeterminado else "User"


def ParsearHistorial(Contenido):
    Marcas = list(EtiquetaTurno.finditer(Contenido))
    Turnos = []
    for Indice, Marca in enumerate(Marcas):
        Fin = Marcas[Indice + 1].start() if Indice + 1 < len(Marcas) else len(Contenido)
        Texto = Contenido[Marca.end():Fin].strip()
        if Marca.group(1) == "Sistema" or not Texto:
            continue
        Rol = "user" if Marca.group(1) == "User" else "assistant"
        if Turnos and Turnos[-1][0] == Rol:
            Turnos[-1][1] += "\n\n" + Texto
        else:
            Turnos.append([Rol, Texto])
    while Turnos and Turnos[0][0] != "user":
        Turnos.pop(0)
    return [{"role": Rol, "content": TextoTurno} for Rol, TextoTurno in Turnos]