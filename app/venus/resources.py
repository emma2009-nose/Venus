import sys
from pathlib import Path


def _DetectarAppRoot():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    Candidato = Path(sys.argv[0]).resolve().parent
    if Candidato.name == "venus":
        return Candidato.parent
    return Candidato


AppRoot = _DetectarAppRoot()


def RutaRecurso(RutaRelativa):
    CarpetasBase = []
    if hasattr(sys, "_MEIPASS"):
        CarpetasBase.append(Path(sys._MEIPASS))
    if getattr(sys, "frozen", False):
        CarpetasBase.append(Path(sys.executable).resolve().parent)
    CarpetasBase.append(AppRoot)
    CarpetasBase.append(Path(__file__).resolve().parent)
    for CarpetaBase in CarpetasBase:
        Candidato = CarpetaBase / RutaRelativa
        if Candidato.exists():
            return Candidato
    return CarpetasBase[0] / RutaRelativa