import logging
import sys
import tkinter as tk
from pathlib import Path

from ia.codigo.proveedores import Completa

from . import state
from .config import VersionApp
from .database import BaseDatos
from .logging_setup import ConfigurarLogging
from .reminders import EjecutarAviso
from .system import EsWine
from .theme import AplicarTema, ElegirFuenteMono
from .ui.config_ias import VentanaConfigIA
from .ui.main import VentanaPrincipal


def _ConfigurarIAsAntesDeAbrir(BaseDatos):
    """Muestra la pantalla de APIs/modelos si toca. False = el usuario salió."""
    if BaseDatos.LeerAjuste("mostrar_config_ias") == "0":
        return True
    # Si el usuario ya tiene un perfil de IA configurado (C, R1 y P listos),
    # abrimos Venus directamente en lugar de la pantalla de "agrega tu IA".
    if Completa():
        return True

    Raiz = tk.Tk()
    Raiz.withdraw()
    ElegirFuenteMono()
    AplicarTema(Raiz)
    Ventana = VentanaConfigIA(Raiz, BaseDatos, Obligatoria=True)
    Raiz.mainloop()
    Continuar = Ventana.Continuar
    Raiz.destroy()
    return Continuar


def Main():
    ConfigurarLogging()
    logging.info("Venus %s | Wine=%s | frozen=%s | notify-send=%s",
                 VersionApp, EsWine(), getattr(sys, "frozen", False),
                 Path("Z:/usr/bin/notify-send").exists())
    if len(sys.argv) >= 3 and sys.argv[1] == "--aviso":
        EjecutarAviso(sys.argv[2])
        return

    BaseDatosObj = BaseDatos()
    try:
        state.NombreUsuario = (
            BaseDatosObj.LeerAjuste("nombre_usuario") or state.NombreUsuario)
    except Exception:
        logging.exception("No se pudo leer el nombre del usuario")

    try:
        Continuar = _ConfigurarIAsAntesDeAbrir(BaseDatosObj)
    except Exception:
        logging.exception("No se pudo abrir la configuración de IAs")
        Continuar = True

    if not Continuar:
        BaseDatosObj.Cerrar()
        return

    App = VentanaPrincipal(BaseDatosObj)
    App.mainloop()


if __name__ == "__main__":
    Main()
