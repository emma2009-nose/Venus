import logging
import sqlite3
import tkinter as tk

from .. import state
from ..config import (
    ColorVersion, DegradadoFin, DegradadoInicio, Fondo, NombrePredeterminado, VersionApp,
)
from ..database import BaseDatos
from ..reminders import Recordatorios
from ..text import LimpiarNombre
from ..theme import _Mezclar, AplicarTema, ElegirFuenteMono, TextoRotulo
# --- CALENDARIO DESACTIVADO: su importacion tambien queda comentada.
# from .calendar import VentanaCalendario
from .chat import VentanaMemoriza
from .config_ias import VentanaConfigIA
from .dialogs import PedirNombreDialogo
from .ias import VentanaIAs
from .manuals import VentanaManuales
from .notes import VentanaNotas
from .perfiles import VentanaPerfiles
from .settings import VentanaAjustes

# CALENDARIO DESACTIVADO (2026-11-06): la ventana es mas baja y los bloques
# suben para que no quede un hueco. Valores anteriores, por si se reactiva:
#   geometriaPrincipal = "520x470"
#   "bloqueSuperior": y=152, "bloqueInferior": y=278, "botonAjustes": y=350
GeometriaPrincipal = "520x400"
PosicionesPrincipal = {
    "rotulo": {"relx": 0.5, "y": 18, "anchor": "n"},
    "bloqueSuperior": {"relx": 0.5, "y": 150, "anchor": "n"},
    # "bloqueInferior": {"relx": 0.5, "y": 278, "anchor": "n"},  # calendario
    "botonAjustes": {"relx": 0.5, "y": 286, "anchor": "n"},
    "version": {"x": 8, "rely": 1.0, "y": -6, "anchor": "sw"},
}


class VentanaPrincipal(tk.Tk):
    def __init__(self, BaseDatosObj=None):
        super().__init__()
        ElegirFuenteMono()
        AplicarTema(self)

        self.title("")
        self.geometry(GeometriaPrincipal)
        self.resizable(False, False)

        self.BaseDatos = BaseDatosObj or BaseDatos()
        self._ConfigIA = None
        self._EditorIAs = None
        self._Perfiles = None
        self.withdraw()
        self._PedirNombre()
        self.deiconify()

        # --- CALENDARIO DESACTIVADO: su ventana ya no se crea.
        # self.moduloCalendario = VentanaCalendario(self, self.baseDatos)
        self.ModuloMemoriza = VentanaMemoriza(self, self.BaseDatos)
        self.ModuloManuales = VentanaManuales(self, self.BaseDatos)
        self.ModuloNotas = VentanaNotas(self, self.BaseDatos)
        self.Recordatorios = Recordatorios(self, self.BaseDatos)
        self.ModuloMemoriza.PedirConfig = self.AbrirConfigIA
        self.ModuloMemoriza.AbrirPerfiles = self.AbrirPerfiles
        self.ModuloAjustes = VentanaAjustes(
            self, self.BaseDatos, self.ModuloNotas,
            self.AbrirConfigIA, self.AbrirEditorIAs, self.AbrirPerfiles)

        self._ConstruirUI()
        self.protocol("WM_DELETE_WINDOW", self.AlCerrar)
        self.Recordatorios.Iniciar()

    def AbrirPerfiles(self):
        if self._Perfiles is not None and self._Perfiles.Ventana.winfo_exists():
            self._Perfiles.Ventana.lift()
            return
        self._Perfiles = VentanaPerfiles(
            self, self.BaseDatos,
            AlCambiar=self._ConfigCambiada,
            AbrirConfig=self.AbrirConfigIA)

    def AbrirConfigIA(self):
        if self._ConfigIA is not None and self._ConfigIA.VentanaConfig.winfo_exists():
            self._ConfigIA.VentanaConfig.lift()
            return
        self._ConfigIA = VentanaConfigIA(
            self, self.BaseDatos, AlGuardar=self._ConfigCambiada, Obligatoria=False)

    def AbrirEditorIAs(self, IdIA=1):
        if self._EditorIAs is not None and self._EditorIAs.Ventana.winfo_exists():
            self._EditorIAs.Mostrar(IdIA)
            return
        self._EditorIAs = VentanaIAs(self, IdInicial=IdIA)

    def _ConfigCambiada(self):
        self.ModuloMemoriza.ConfigCambiada()

    def _ConstruirUI(self):
        self.EtiquetaVersion = tk.Label(self, text=f"{VersionApp}", fg=ColorVersion)

        Filas = TextoRotulo("VENUS")
        self.Rotulo = tk.Text(
            self, height=len(Filas), width=len(Filas[0]), wrap="none",
            bd=0, highlightthickness=0, bg=Fondo, cursor="arrow",
            font=(state.FuenteMono, 11, "bold"),
        )
        for N, Linea in enumerate(Filas):
            Etiqueta = f"rotulo{N}"
            self.Rotulo.tag_config(Etiqueta, foreground=_Mezclar(DegradadoInicio, DegradadoFin, N / (len(Filas) - 1)))
            self.Rotulo.insert(tk.END, Linea + ("\n" if N < len(Filas) - 1 else ""), Etiqueta)
        self.Rotulo.config(state="disabled")

        self.MarcoBloqueSuperior = tk.Frame(self)
        # --- CALENDARIO DESACTIVADO ---
        # self.marcoBloqueInferior = tk.Frame(self)

        def CrearBotonMenu(Padre, Texto, Comando):
            Boton = tk.Button(Padre, text=f"[ {Texto} ]", command=Comando)
            Boton.pack(fill=tk.X, pady=5)
            return Boton

        # Orden pedido: Venus IA, Manuales y Calendario (calendario comentado).
        self.BotonMemoriza = CrearBotonMenu(self.MarcoBloqueSuperior, "Venus IA",
                                            self.ModuloMemoriza.MostrarVentanaMemoriza)
        self.BotonManuales = CrearBotonMenu(self.MarcoBloqueSuperior, "Manuales",
                                            self.ModuloManuales.MostrarVentanaManuales)
        # --- CALENDARIO DESACTIVADO: su boton y su bloque, comentados.
        # self.botonCalendario = crearBotonMenu(self.marcoBloqueInferior, "Calendario",
        #                                       self.moduloCalendario.mostrarVentanaCalendario)
        self.BotonAjustes = tk.Button(self, text="[ Ajustes ]",
                                      command=self.ModuloAjustes.MostrarVentanaAjustes)

        self._ColocarElementos()

    def ReconstruirUI(self):
        """Vuelve a crear la interfaz principal con la paleta activa."""
        for Hijo in list(self.winfo_children()):
            if isinstance(Hijo, tk.Toplevel):
                continue
            try:
                Hijo.destroy()
            except tk.TclError:
                pass
        self._ConstruirUI()

    def _PedirNombre(self):
        try:
            Guardado = LimpiarNombre(self.BaseDatos.LeerAjuste("nombre_usuario"))
            YaPreguntado = self.BaseDatos.LeerAjuste("nombre_pedido") is not None
        except sqlite3.Error:
            logging.exception("No se pudo leer el nombre de la base de datos")
            Guardado, YaPreguntado = "", True
        state.NombreUsuario = Guardado or NombrePredeterminado
        if YaPreguntado:
            return
        Nombre = PedirNombreDialogo(self, "Bienvenido", "¿Cómo quieres que te llame?")
        try:
            if Nombre is not None:
                self.BaseDatos.GuardarAjuste("nombre_usuario", Nombre)
            self.BaseDatos.GuardarAjuste("nombre_pedido", "1")
        except sqlite3.Error:
            logging.exception("No se pudo guardar el nombre en la base de datos")
        if Nombre is not None:
            state.NombreUsuario = Nombre or NombrePredeterminado

    def _ColocarElementos(self):
        Elementos = {
            "rotulo": self.Rotulo,
            "bloqueSuperior": self.MarcoBloqueSuperior,
            # --- CALENDARIO DESACTIVADO ---
            # "bloqueInferior": self.marcoBloqueInferior,
            "botonAjustes": self.BotonAjustes,
            "version": self.EtiquetaVersion,
        }
        for Nombre, Elemento in Elementos.items():
            Elemento.place(**PosicionesPrincipal[Nombre])

    def AlCerrar(self):
        self.Recordatorios.Detener()
        # El chat abierto se guarda solo antes de cerrar la app.
        Memoriza = getattr(self, "ModuloMemoriza", None)
        if Memoriza is not None:
            try:
                Memoriza.GuardarConversacionAutomatica()
            except Exception:
                logging.exception("No se pudo guardar el chat al cerrar la app")
        try:
            self.BaseDatos.Cerrar()
        except Exception:
            logging.exception("Error al cerrar la base de datos")
        self.destroy()