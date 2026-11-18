"""Editor de prompts y cuadernos de las 4 IAs.

Cada IA tiene 2 prompts (se alternan entre llamadas) y un cuaderno personal.
La app anota en el cuaderno el trabajo de la IA; aquí también puedes escribir.
"""
import logging
import tkinter as tk
from tkinter import messagebox

from ia.codigo.proveedores import (
    Ids, Roles, CarpetaIA, CrearEstructura, GuardarCuaderno, GuardarPrompts,
    LeerCuaderno, LeerPrompts,
)
from ..config import (
    Apagado, Borde, ColorExito, ColorTexto, Fondo, FuenteLectura, FuenteMono,
    Lila, Oscuro, Panel, Rosa,
)
from ..system import AbrirConSistema
from ..theme import Cabecera

Ayuda = (
    "Los 2 prompts se envían como mensajes de sistema y se alternan entre "
    "llamadas. El cuaderno es memoria compartida: esta IA escribe en el suyo "
    "y lee los de las otras 3. La app no agrega ningún prompt."
)


class VentanaIAs:
    def __init__(self, VentanaPadre, IdInicial=1):
        self.VentanaPadre = VentanaPadre
        self.IdActual = IdInicial
        self._Botones = {}
        self._Cargando = False

        self.Ventana = tk.Toplevel(VentanaPadre)
        self.Ventana.title("Venus · Prompts y cuadernos")
        self.Ventana.configure(bg=Fondo)
        self.Ventana.resizable(True, True)

        self._Construir()
        self._CargarRol(IdInicial)
        self.Ventana.protocol("WM_DELETE_WINDOW", self._Cerrar)
        self._Centrar()
        try:
            self.Ventana.grab_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------- construcción
    def _Construir(self):
        Cabecera(self.Ventana, "prompts").pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(
            self.Ventana, text="Prompts y cuadernos",
            font=(FuenteLectura, 16, "bold"), fg=Lila, bg=Fondo,
        ).pack(pady=(0, 2))
        tk.Label(
            self.Ventana, text=Ayuda,
            font=(FuenteLectura, 8), fg=Apagado, bg=Fondo,
            wraplength=860, justify=tk.LEFT,
        ).pack(padx=12, pady=(0, 8))

        Cuerpo = tk.Frame(self.Ventana, bg=Fondo)
        Cuerpo.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        Lateral = tk.Frame(Cuerpo, bg=Fondo)
        Lateral.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        for IdIA in Ids:
            Rol = Roles[IdIA]
            Boton = tk.Button(
                Lateral, text=f'[{Rol["clave"]}] {Rol["nombre"]}',
                font=(FuenteLectura, 10, "bold"), anchor="w", width=18,
                command=lambda I=IdIA: self._CambiarRol(I),
                fg=Lila, bg=Panel, activebackground=Lila, activeforeground=Oscuro,
                bd=0, padx=8, pady=6,
            )
            Boton.pack(fill=tk.X, pady=3)
            self._Botones[IdIA] = Boton

        self.Panel = tk.Frame(Cuerpo, bg=Fondo)
        self.Panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.EtiquetaRol = tk.Label(
            self.Panel, text="", font=(FuenteLectura, 12, "bold"),
            fg=Lila, bg=Fondo, anchor="w",
        )
        self.EtiquetaRol.pack(fill=tk.X)

        self._Textos = {}
        for Clave, Titulo, Alto in (
            ("prompt1", "Prompt 1", 7),
            ("prompt2", "Prompt 2", 7),
            ("cuaderno", "Cuaderno (la app también escribe aquí)", 14),
        ):
            tk.Label(
                self.Panel, text=Titulo, font=(FuenteLectura, 9, "bold"),
                fg=ColorTexto, bg=Fondo, anchor="w",
            ).pack(fill=tk.X, pady=(6, 2))
            Marco = tk.Frame(self.Panel, bg=Fondo)
            Marco.pack(fill=tk.BOTH, expand=(Clave == "cuaderno"))
            Texto = tk.Text(
                Marco, height=Alto, font=(FuenteMono, 9), wrap=tk.WORD,
                undo=True, bd=0, highlightthickness=1,
                highlightbackground=Borde, highlightcolor=Rosa,
                bg=Panel, fg=ColorTexto, insertbackground=Rosa,
            )
            Barra = tk.Scrollbar(Marco, orient="vertical", command=Texto.yview)
            Texto.configure(yscrollcommand=Barra.set)
            Barra.pack(side=tk.RIGHT, fill=tk.Y)
            Texto.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._Textos[Clave] = Texto

        Botones = tk.Frame(self.Ventana, bg=Fondo)
        Botones.pack(fill=tk.X, padx=12, pady=(0, 10))
        self._Boton(Botones, "Guardar", self._GuardarRol).pack(side=tk.LEFT, padx=(0, 6))
        self._Boton(Botones, "Recargar", self._RecargarRol).pack(side=tk.LEFT, padx=6)
        self._Boton(Botones, "Abrir carpeta", self._AbrirCarpeta).pack(side=tk.LEFT, padx=6)
        self._Boton(Botones, "Cerrar", self._Cerrar).pack(side=tk.RIGHT)
        self.Estado = tk.Label(
            Botones, text="", font=(FuenteLectura, 8), fg=ColorExito, bg=Fondo)
        self.Estado.pack(side=tk.RIGHT, padx=10)

    def _Boton(self, Padre, Texto, Comando):
        return tk.Button(
            Padre, text=f"[ {Texto} ]", command=Comando,
            font=(FuenteLectura, 9, "bold"), fg=Lila, bg=Panel,
            activebackground=Lila, activeforeground=Oscuro, bd=0, padx=8, pady=3,
        )

    # ------------------------------------------------------------------- datos
    def _Texto(self, Clave):
        return self._Textos[Clave].get("1.0", "end-1c")

    def _PonerTexto(self, Clave, Valor):
        Texto = self._Textos[Clave]
        Texto.delete("1.0", tk.END)
        Texto.insert("1.0", Valor or "")
        # Al cargar, el cuaderno no cuenta como "editado por el usuario".
        Texto.edit_modified(False)

    def _CargarRol(self, IdIA):
        self._Cargando = True
        try:
            Prompts = LeerPrompts(IdIA)
            self._PonerTexto("prompt1", Prompts[0] if len(Prompts) > 0 else "")
            self._PonerTexto("prompt2", Prompts[1] if len(Prompts) > 1 else "")
            self._PonerTexto("cuaderno", LeerCuaderno(IdIA))
            Rol = Roles[IdIA]
            self.EtiquetaRol.config(
                text=f'[{Rol["clave"]}] {Rol["nombre"]} · {Rol["descripcion"]}')
            self.IdActual = IdIA
            self.Estado.config(text="")
            self._PintarBotones()
        finally:
            self._Cargando = False

    def _PintarBotones(self):
        for IdIA, Boton in self._Botones.items():
            if IdIA == self.IdActual:
                Boton.configure(bg=Lila, fg=Oscuro)
            else:
                Boton.configure(bg=Panel, fg=Lila)

    def _GuardarRol(self, Silencioso=False):
        if self._Cargando:
            return False
        IdIA = self.IdActual
        try:
            GuardarPrompts(IdIA, self._Texto("prompt1"), self._Texto("prompt2"))
            # La app también escribe en el cuaderno mientras el chat trabaja.
            # En guardados automáticos solo se pisa si lo editaste tú, para no
            # perder las anotaciones nuevas.
            if not Silencioso or self._Textos["cuaderno"].edit_modified():
                GuardarCuaderno(IdIA, self._Texto("cuaderno"))
                self._Textos["cuaderno"].edit_modified(False)
        except OSError as E:
            logging.exception("No se pudieron guardar prompts/cuaderno")
            messagebox.showerror("IAs", f"No se pudo guardar:\n\n{E}", parent=self.Ventana)
            return False
        self.Estado.config(text="Guardado.")
        if not Silencioso:
            self.Ventana.after(1500, lambda: self.Estado.config(text=""))
        return True

    def _RecargarRol(self):
        if self._GuardarRol(Silencioso=True):
            self._CargarRol(self.IdActual)
            self.Estado.config(text="Recargado.")

    def _CambiarRol(self, IdIA):
        if IdIA == self.IdActual:
            return
        if not self._GuardarRol(Silencioso=True):
            return
        self._CargarRol(IdIA)

    def _AbrirCarpeta(self):
        try:
            CrearEstructura(self.IdActual)
            AbrirConSistema(CarpetaIA(self.IdActual))
        except Exception as E:
            logging.exception("No se pudo abrir la carpeta de la IA")
            messagebox.showerror("IAs", f"No se pudo abrir la carpeta:\n\n{E}",
                                 parent=self.Ventana)

    def Mostrar(self, IdIA=None):
        if IdIA is not None and IdIA != self.IdActual:
            self._CambiarRol(IdIA)
        self.Ventana.lift()
        self.Ventana.focus_set()

    def _Cerrar(self):
        self._GuardarRol(Silencioso=True)
        self.Ventana.destroy()

    def _Centrar(self):
        self.Ventana.update_idletasks()
        Ancho = max(self.Ventana.winfo_reqwidth(), 920)
        Alto = max(self.Ventana.winfo_reqheight(), 720)
        X = (self.Ventana.winfo_screenwidth() - Ancho) // 2
        Y = (self.Ventana.winfo_screenheight() - Alto) // 3
        self.Ventana.geometry(f"{Ancho}x{Alto}+{max(X, 0)}+{max(Y, 0)}")
