import re
from datetime import datetime

_Ampm = r"([ap])\.?\s?m\.?"
EtiquetaHora = re.compile(
    r"\(\s*(\d{1,2})\s*[:/h]\s*(\d{2})\s*(?:" + _Ampm + r")?\s*\)"
    r"(?:\s*\(\s*" + _Ampm + r"\s*\))?",
    re.IGNORECASE,
)


def ExtraerHoras(Texto):
    Horas = []
    for Coincidencia in EtiquetaHora.finditer(Texto):
        Hora, Minuto = int(Coincidencia.group(1)), int(Coincidencia.group(2))
        Sufijo = (Coincidencia.group(3) or Coincidencia.group(4) or "").lower()
        if Minuto > 59:
            continue
        if Sufijo:
            if not 1 <= Hora <= 12:
                continue
            Hora = Hora % 12 + (12 if Sufijo == "p" else 0)
        elif Hora > 23:
            continue
        if (Hora, Minuto) not in Horas:
            Horas.append((Hora, Minuto))
    return sorted(Horas)


def MomentosDeNota(Fecha, Contenido, Ahora=None):
    Ahora = (Ahora or datetime.now()).replace(second=0, microsecond=0)
    try:
        Dia = datetime.strptime(Fecha, "%d/%m/%Y")
    except ValueError:
        return [], []
    Futuros, Pasados = [], []
    for Hora, Minuto in ExtraerHoras(Contenido):
        Momento = Dia.replace(hour=Hora, minute=Minuto)
        (Futuros if Momento >= Ahora else Pasados).append(Momento.strftime("%Y-%m-%d %H:%M"))
    return Futuros, Pasados


def ResumenNota(Contenido, MaxCar=200):
    Limpio = " ".join(EtiquetaHora.sub(" ", Contenido).split())
    return Limpio if len(Limpio) <= MaxCar else Limpio[:MaxCar - 1].rstrip() + "…"


def ArmarAviso(Contenido, FechaHora, Ahora=None):
    Ahora = Ahora or datetime.now()
    Momento = datetime.strptime(FechaHora, "%Y-%m-%d %H:%M")
    if (Ahora - Momento).total_seconds() > 180:
        Titulo = f"Venus · atrasado ({Momento.strftime('%d/%m %H:%M')})"
    else:
        Titulo = f"Venus · {Momento.strftime('%H:%M')}"
    return Titulo, ResumenNota(Contenido) or "Tienes una nota programada."