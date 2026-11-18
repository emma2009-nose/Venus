import logging
import sqlite3
import tkinter as tk
from tkinter import messagebox

from ia.codigo.proveedores import CarpetaBase, CrearEstructura
from .. import state
from ..config import (
    Paletas, Apagado, ColorTexto, Fondo, Lila, NombrePredeterminado, Panel,
    RutaTema,
)
from ..system import AbrirConSistema
from ..theme import Cabecera, CambiarTemaEnVivo, TemaEnUso
from .dialogs import PedirNombreDialogo


class VentanaAjustes:
    def __init__(self, VentanaPadre, BaseDatos, ModuloNotas,
                 AbrirConfig, AbrirEditorIAs, AbrirPerfiles=None):
        self.VentanaPadre = VentanaPadre
        self.BaseDatos = BaseDatos
        self.ModuloNotas = ModuloNotas
        self.AbrirConfig = AbrirConfig
        self.AbrirEditorIAs = AbrirEditorIAs
        self.AbrirPerfiles = AbrirPerfiles or AbrirConfig
        self.VentanaAjustes = None

    def MostrarVentanaAjustes(self):
        if self.VentanaAjustes is not None and self.VentanaAjustes.winfo_exists():
            self.VentanaAjustes.lift()
            return
        self.VentanaAjustes = tk.Toplevel(self.VentanaPadre)
        self.VentanaAjustes.title("Ajustes")
        self.VentanaAjustes.resizable(False, False)
        Cabecera(self.VentanaAjustes, "Ajustes").pack(pady=(10, 0))
        MarcoBotones = tk.Frame(self.VentanaAjustes)
        MarcoBotones.pack(padx=30, pady=15)
        Botones = (
            ("Modo de IAs (DeepSeek/Ollama)", self.AbrirPerfiles),
            ("Editar APIs del modo", self.AbrirConfig),
            ("Prompts y cuadernos", lambda: self.AbrirEditorIAs(1)),
            ("Carpeta de IAs", self.AbrirCarpetaIAs),
            ("Help", self.ModuloNotas.MostrarVentanaNotas),
            ("Cambiar nombre", self.CambiarNombre),
            (f"Tema: {Paletas[TemaEnUso()]['nombre']}", self.CambiarTema),
        )
        for Texto, Comando in Botones:
            tk.Button(MarcoBotones, text=f"[ {Texto} ]", command=Comando).pack(fill=tk.X, pady=5)
        tk.Button(self.VentanaAjustes, text="[ Cerrar ]",
                  command=self.VentanaAjustes.destroy).pack(pady=(0, 15))

    def AbrirCarpetaIAs(self):
        try:
            CrearEstructura(1)
            AbrirConSistema(CarpetaBase())
        except Exception as E:
            logging.exception("No se pudo abrir la carpeta de IAs")
            messagebox.showerror("IAs", f"No se pudo abrir la carpeta:\n\n{E}",
                                 parent=self.VentanaAjustes)

    def CambiarNombre(self):
        Actual = state.NombreUsuario if state.NombreUsuario != NombrePredeterminado else ""
        Nuevo = PedirNombreDialogo(self.VentanaAjustes, "Cambiar nombre",
                                   "Escribe tu nuevo nombre:", Actual,
                                   "[ Guardar ]", "[ Cancelar ]")
        if Nuevo is None:
            return
        try:
            self.BaseDatos.GuardarAjuste("nombre_usuario", Nuevo)
            self.BaseDatos.GuardarAjuste("nombre_pedido", "1")
        except sqlite3.Error as E:
            logging.exception("No se pudo guardar el nombre")
            messagebox.showerror("Error", f"No se pudo guardar el nombre:\n\n{E}",
                                 parent=self.VentanaAjustes)
            return
        state.NombreUsuario = Nuevo or NombrePredeterminado
        messagebox.showinfo("Nombre", f"Nombre guardado: {state.NombreUsuario}",
                            parent=self.VentanaAjustes)

    def CambiarTema(self):
        Dialogo = tk.Toplevel(self.VentanaAjustes)
        Dialogo.title("Tema")
        Dialogo.resizable(False, False)
        Cabecera(Dialogo, "Tema").pack(pady=(10, 0))
        tk.Label(Dialogo, text="Elige el tema de Venus:").pack(padx=20, pady=(8, 4))

        Variable = tk.StringVar(value=TemaEnUso())
        for Clave, Datos in Paletas.items():
            tk.Radiobutton(
                Dialogo, text=Datos["nombre"], variable=Variable, value=Clave,
                anchor="w", justify=tk.LEFT,
                bg=Fondo, fg=ColorTexto, activebackground=Fondo,
                activeforeground=Lila, selectcolor=Panel, highlightthickness=0,
            ).pack(fill=tk.X, padx=30, pady=2)

        tk.Label(Dialogo, text="Se aplica al instante.", fg=Apagado).pack(pady=(6, 0))

        def Guardar():
            Elegido = Variable.get()
            try:
                RutaTema.parent.mkdir(parents=True, exist_ok=True)
                RutaTema.write_text(Elegido, encoding="utf-8")
            except OSError as E:
                logging.exception("No se pudo guardar el tema")
                messagebox.showerror("Tema", f"No se pudo guardar el tema:\n\n{E}",
                                     parent=Dialogo)
                return
            Dialogo.destroy()
            CambiarTemaEnVivo(self.VentanaPadre, Elegido)

        Marco = tk.Frame(Dialogo)
        Marco.pack(pady=10)
        tk.Button(Marco, text="[ Guardar ]", command=Guardar).pack(side=tk.LEFT, padx=5)
        tk.Button(Marco, text="[ Cancelar ]", command=Dialogo.destroy).pack(side=tk.LEFT, padx=5)
        Dialogo.protocol("WM_DELETE_WINDOW", Dialogo.destroy)

        Dialogo.update_idletasks()
        X = (Dialogo.winfo_screenwidth() - Dialogo.winfo_reqwidth()) // 2
        Y = (Dialogo.winfo_screenheight() - Dialogo.winfo_reqheight()) // 3
        Dialogo.geometry(f"+{max(X, 0)}+{max(Y, 0)}")
        try:
            Dialogo.grab_set()
        except tk.TclError:
            pass
