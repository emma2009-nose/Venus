"""Selector rápido del modo de IAs (DeepSeek / Ollama).

Muestra cada modo con sus modelos por rol y permite activarlo al instante.
El botón «Editar APIs» abre la ventana completa de IAs.
"""
import logging
import tkinter as tk
from tkinter import messagebox

from ia.codigo.proveedores import (
    BorrarIAsPerfil, CambiarPerfil, CrearPerfil, LeerPerfil,
    LeerPerfilActivo, PerfilesDisponibles,
)
from ..config import (
    Apagado, Borde, ColorExito, ColorTexto, Fondo, FuenteLectura, Lila,
    Oscuro, Panel,
)
from ..theme import Cabecera
from .dialogs import PedirTextoDialogo


class VentanaPerfiles:
    def __init__(self, VentanaPadre, BaseDatos, AlCambiar=None, AbrirConfig=None):
        self.VentanaPadre = VentanaPadre
        self.BaseDatos = BaseDatos
        self.AlCambiar = AlCambiar
        self.AbrirConfig = AbrirConfig

        self.Ventana = tk.Toplevel(VentanaPadre)
        self.Ventana.title("Venus · Modo de IAs")
        self.Ventana.configure(bg=Fondo)
        self.Ventana.resizable(False, False)
        self._Construir()
        self.Ventana.protocol("WM_DELETE_WINDOW", self.Cerrar)
        self._Centrar()
        try:
            self.Ventana.transient(VentanaPadre)
            self.Ventana.grab_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------- construcción
    def _Construir(self):
        for Hijo in list(self.Ventana.winfo_children()):
            Hijo.destroy()

        Cabecera(self.Ventana, "modo").pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(
            self.Ventana, text="Modo de IAs",
            font=(FuenteLectura, 16, "bold"), fg=Lila, bg=Fondo,
        ).pack(pady=(0, 2))
        tk.Label(
            self.Ventana,
            text="Elige el modo activo. El chat usará sus APIs en el próximo mensaje.",
            font=(FuenteLectura, 9), fg=Apagado, bg=Fondo,
        ).pack(padx=12, pady=(0, 8))

        Activo = LeerPerfilActivo()
        for Perfil in PerfilesDisponibles():
            Nombre = Perfil["nombre"]
            Ias = LeerPerfil(Nombre)
            Tarjeta = tk.Frame(
                self.Ventana, bg=Panel, bd=0,
                highlightbackground=Borde, highlightthickness=1,
            )
            Tarjeta.pack(fill=tk.X, padx=14, pady=5)

            Cab = tk.Frame(Tarjeta, bg=Panel)
            Cab.pack(fill=tk.X, padx=10, pady=(8, 2))
            tk.Label(
                Cab, text=Perfil["etiqueta"],
                font=(FuenteLectura, 12, "bold"), fg=Lila, bg=Panel,
            ).pack(side=tk.LEFT)
            if Nombre == Activo:
                tk.Label(
                    Cab, text="· activo", font=(FuenteLectura, 9, "bold"),
                    fg=ColorExito, bg=Panel,
                ).pack(side=tk.LEFT, padx=6)

            Detalle = " · ".join(
                f"{Ias[I].Rol}: {Ias[I].Modelo or '—'} "
                f"({'local' if Ias[I].Tipo == 'local' else 'API'})"
                for I in (1, 2, 3, 4))
            tk.Label(
                Tarjeta, text=Detalle, font=(FuenteLectura, 9),
                fg=ColorTexto, bg=Panel, anchor="w", justify=tk.LEFT,
                wraplength=560,
            ).pack(fill=tk.X, padx=10, pady=(0, 4))

            Boton = self._Boton(
                Tarjeta, "Usar", lambda N=Nombre: self._Usar(N))
            Boton.pack(anchor="e", padx=10, pady=(0, 8))
            if Nombre == Activo:
                Boton.config(state="disabled", text="[ En uso ]")

        Pie = tk.Frame(self.Ventana, bg=Fondo)
        Pie.pack(fill=tk.X, padx=14, pady=(4, 4))
        self._Boton(Pie, "Nuevo perfil", self._NuevoPerfil).pack(side=tk.LEFT)
        self._Boton(Pie, "Editar APIs del modo activo", self._Editar).pack(
            side=tk.LEFT, padx=6)
        self._Boton(Pie, "Cerrar", self.Cerrar).pack(side=tk.RIGHT)
        Pie2 = tk.Frame(self.Ventana, bg=Fondo)
        Pie2.pack(fill=tk.X, padx=14, pady=(0, 10))
        self._Boton(
            Pie2, "Borrar todas las IAs de este modo", self._BorrarIAs,
        ).pack(side=tk.LEFT)

    def _Boton(self, Padre, Texto, Comando):
        return tk.Button(
            Padre, text=f"[ {Texto} ]", command=Comando,
            font=(FuenteLectura, 9, "bold"), fg=Lila, bg=Panel,
            activebackground=Lila, activeforeground=Oscuro, bd=0, padx=8, pady=3,
        )

    # ----------------------------------------------------------------- acciones
    def _Usar(self, Nombre):
        if not CambiarPerfil(Nombre):
            return
        if self.AlCambiar:
            try:
                self.AlCambiar()
            except Exception:
                logging.exception("Falló al avisar del cambio de modo de IAs")
        self._Construir()

    def _Editar(self):
        Abrir = self.AbrirConfig
        self.Cerrar()
        if Abrir:
            Abrir()

    def _NuevoPerfil(self):
        Texto = PedirTextoDialogo(
            self.Ventana, "Nuevo modo", "Nombre del nuevo modo:", Inicial="")
        if Texto is None:
            return
        Nombre = CrearPerfil(Texto)
        if not Nombre:
            messagebox.showerror(
                "Modo de IAs", "Ese nombre ya existe o no es válido.",
                parent=self.Ventana)
            return
        if not CambiarPerfil(Nombre):
            return
        if self.AlCambiar:
            try:
                self.AlCambiar()
            except Exception:
                logging.exception("Falló al avisar del nuevo modo de IAs")
        self._Construir()
        # Un modo nuevo nace vacío: abrimos el editor para rellenarlo.
        if self.AbrirConfig:
            self._Editar()

    def _BorrarIAs(self):
        Activo = LeerPerfilActivo()
        Etiqueta = next(
            (P["etiqueta"] for P in PerfilesDisponibles()
             if P["nombre"] == Activo),
            Activo,
        )
        if not messagebox.askyesno(
            "Borrar IAs",
            f"¿Borrar todas las IAs (APIs y modelos) de «{Etiqueta}»?\n\n"
            "Solo se borran las de este modo. No se tocan los prompts, "
            "los cuadernos ni los otros modos.",
            parent=self.Ventana,
        ):
            return
        if not BorrarIAsPerfil(Activo):
            return
        if self.AlCambiar:
            try:
                self.AlCambiar()
            except Exception:
                logging.exception("Falló al avisar del borrado de IAs")
        self._Construir()

    def Cerrar(self):
        try:
            self.Ventana.destroy()
        except tk.TclError:
            pass

    def _Centrar(self):
        self.Ventana.update_idletasks()
        Ancho = max(self.Ventana.winfo_reqwidth(), 620)
        Alto = max(self.Ventana.winfo_reqheight(), 360)
        X = (self.Ventana.winfo_screenwidth() - Ancho) // 2
        Y = (self.Ventana.winfo_screenheight() - Alto) // 3
        self.Ventana.geometry(f"{Ancho}x{Alto}+{max(X, 0)}+{max(Y, 0)}")
