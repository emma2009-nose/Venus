import logging
import re
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext

from ..config import (
    Apagado, ColorTexto, Fondo, FuenteMono, FuenteTexto, Lila, Panel, Rosa,
    RutaManuales, TamanoFuente,
)
from ..system import AbrirConSistema
from ..text import LeerTextoArchivo, NombreCortoManual
from ..theme import Cabecera
from .dialogs import PedirTextoDialogo

Extensiones = (".txt", ".docx")


class VentanaManuales:
    def __init__(self, VentanaPadre, BaseDatos=None):
        self.VentanaPadre = VentanaPadre
        self.BaseDatos = BaseDatos
        self.VentanaManuales = None
        self.RutaManualesUsuario = RutaManuales
        self.Lienzo = None
        self.ContenedorLista = None
        # Casillas de la lista: ruta -> BooleanVar
        self._SeleccionManuales = {}
        self.VariableTodo = None
        try:
            self.RutaManualesUsuario.mkdir(parents=True, exist_ok=True)
        except OSError:
            logging.exception("No se pudo crear la carpeta de manuales")

    # ------------------------------------------------------------ rueda
    def _Desplazar(self, Unidades):
        if self.Lienzo is not None:
            self.Lienzo.yview_scroll(Unidades, "units")

    def _EnlazarRueda(self, Widget):
        """Hace que la rueda del raton desplace la lista al pasar por encima."""
        Widget.bind("<MouseWheel>", lambda E: self._Desplazar(-3 if E.delta > 0 else 3))
        Widget.bind("<Button-4>", lambda E: self._Desplazar(-3))
        Widget.bind("<Button-5>", lambda E: self._Desplazar(3))

    def _EnlazarRuedaEnArbol(self, Widget):
        self._EnlazarRueda(Widget)
        for Hijo in Widget.winfo_children():
            self._EnlazarRuedaEnArbol(Hijo)

    # ---------------------------------------------------- marcas de origen
    def _RutaRelativa(self, RutaPath):
        try:
            return RutaPath.relative_to(self.RutaManualesUsuario).as_posix()
        except ValueError:
            return RutaPath.name

    def _LeerMarca(self, Prefijo, RutaRel, RutaPath):
        if self.BaseDatos is not None:
            try:
                return self.BaseDatos.LeerAjuste(f"{Prefijo}:{RutaRel}") == "1"
            except Exception:
                logging.exception("No se pudo leer la marca %s", Prefijo)
        return RutaPath.with_name(f"{RutaPath.name}.{Prefijo}").exists()

    def _GuardarMarca(self, Prefijo, RutaRel, RutaPath, Activo):
        if self.BaseDatos is not None:
            try:
                self.BaseDatos.GuardarAjuste(
                    f"{Prefijo}:{RutaRel}", "1" if Activo else "0")
                return
            except Exception:
                logging.exception("No se pudo guardar la marca %s", Prefijo)
        Sidecar = RutaPath.with_name(f"{RutaPath.name}.{Prefijo}")
        try:
            if Activo:
                Sidecar.touch(exist_ok=True)
            elif Sidecar.exists():
                Sidecar.unlink()
        except OSError:
            logging.exception("No se pudo guardar la marca %s en %s", Prefijo, Sidecar)

    def _EsGenerado(self, RutaRel, RutaPath):
        return self._LeerMarca("manual_generado", RutaRel, RutaPath)

    def _AvisoVisto(self, RutaRel, RutaPath):
        return self._LeerMarca("aviso_manual_visto", RutaRel, RutaPath)

    # ------------------------------------------------------- renombrar
    def RenombrarManual(self, RutaPath):
        """Renombra el archivo del manual conservando sus marcas."""
        if not RutaPath.exists():
            return
        RelOrigen = self._RutaRelativa(RutaPath)
        Marcas = {
            Prefijo: self._LeerMarca(Prefijo, RelOrigen, RutaPath)
            for Prefijo in ("manual_generado", "aviso_manual_visto")
        }
        Nuevo = PedirTextoDialogo(
            self.VentanaManuales, "Renombrar manual",
            "Escribe el nuevo nombre del manual:",
            Inicial=RutaPath.stem, LargoMaximo=90,
        )
        if Nuevo is None:
            return
        Nombre = re.sub(r'[\\/:*?"<>|]+', " ", Nuevo)
        Nombre = re.sub(r"\s+", " ", Nombre).strip(" .")
        if not Nombre:
            messagebox.showinfo("Renombrar manual",
                                "El nombre no puede estar vacío.",
                                parent=self.VentanaManuales)
            return
        Destino = RutaPath.with_name(f"{Nombre}{RutaPath.suffix.lower()}")
        if Destino == RutaPath:
            return
        if Destino.exists():
            messagebox.showerror(
                "Renombrar manual",
                f"Ya existe un manual llamado '{Destino.name}'.",
                parent=self.VentanaManuales,
            )
            return
        try:
            RutaPath.rename(Destino)
        except OSError as E:
            logging.exception("No se pudo renombrar el manual %s", RutaPath)
            messagebox.showerror("Error", f"No se pudo renombrar el manual:\n{E}",
                                 parent=self.VentanaManuales)
            return
        # Las marcas se guardan por ruta relativa: hay que moverlas al nombre nuevo
        # para que el manual siga marcado como [IA] y no vuelva a avisar.
        self._GuardarMarca("manual_generado", RelOrigen, RutaPath, False)
        self._GuardarMarca("aviso_manual_visto", RelOrigen, RutaPath, False)
        RelDestino = self._RutaRelativa(Destino)
        for Prefijo, Activo in Marcas.items():
            if Activo:
                self._GuardarMarca(Prefijo, RelDestino, Destino, True)
        self._RefrescarLista()

    # ------------------------------------------------------------ listado
    def _ListarManuales(self):
        """Devuelve [(ruta relativa, Path), ...] incluyendo subcarpetas."""
        Archivos = {}
        Carpeta = self.RutaManualesUsuario
        if Carpeta.is_dir():
            for P in Carpeta.rglob("*"):
                if P.is_file() and P.suffix.lower() in Extensiones:
                    Archivos[P.relative_to(Carpeta).as_posix()] = P
        return sorted(Archivos.items(), key=lambda Par: Par[0].lower())

    def MostrarVentanaManuales(self):
        if self.VentanaManuales is not None and self.VentanaManuales.winfo_exists():
            self.VentanaManuales.lift()
            self._RefrescarLista()      # por si se agrego algo mientras estaba abierta
            return
        self.VentanaManuales = tk.Toplevel(self.VentanaPadre)
        self.VentanaManuales.title("Manuales")
        self.VentanaManuales.geometry("560x540")
        self.VentanaManuales.minsize(420, 320)
        Cabecera(self.VentanaManuales, "Manuales").pack(pady=(10, 0))
        tk.Label(self.VentanaManuales, text="Selecciona un manual",
                 font=(FuenteTexto, TamanoFuente, "bold")).pack(pady=(5, 4))

        MarcoTodo = tk.Frame(self.VentanaManuales)
        MarcoTodo.pack(fill=tk.X, padx=14, pady=(0, 4))
        self.VariableTodo = tk.BooleanVar(value=False)
        tk.Checkbutton(
            MarcoTodo, text="Seleccionar todo", variable=self.VariableTodo,
            command=self._MarcarTodosLosManuales,
            bd=0, bg=Fondo, fg=ColorTexto, activebackground=Fondo,
            activeforeground=Lila, selectcolor=Panel, highlightthickness=0,
            cursor="hand2",
        ).pack(side=tk.LEFT)

        # Lista desplazable: lienzo + barra + rueda del raton.
        MarcoLista = tk.Frame(self.VentanaManuales)
        MarcoLista.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.Lienzo = tk.Canvas(MarcoLista, highlightthickness=0)
        Barra = tk.Scrollbar(MarcoLista, orient="vertical", command=self.Lienzo.yview)
        self.Lienzo.configure(yscrollcommand=Barra.set)
        Barra.pack(side=tk.RIGHT, fill=tk.Y)
        self.Lienzo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ContenedorLista = tk.Frame(self.Lienzo)
        self._VentanaLista = self.Lienzo.create_window(
            (0, 0), window=self.ContenedorLista, anchor="nw")
        self.ContenedorLista.bind(
            "<Configure>", lambda _E: self.Lienzo.configure(scrollregion=self.Lienzo.bbox("all")))
        self.Lienzo.bind(
            "<Configure>", lambda E: self.Lienzo.itemconfig(self._VentanaLista, width=E.width))
        self._EnlazarRueda(self.Lienzo)
        self._EnlazarRuedaEnArbol(self.ContenedorLista)

        self._RefrescarLista()

        tk.Label(
            self.VentanaManuales,
            text="Marca las casillas y pulsa [ Borrar ]. Clic derecho: renombrar.",
            fg=Apagado, font=(FuenteTexto, max(9, TamanoFuente - 8)),
            wraplength=520, justify=tk.CENTER,
        ).pack(pady=(0, 2))

        FrameInferior = tk.Frame(self.VentanaManuales)
        FrameInferior.pack(pady=10)
        tk.Button(FrameInferior, text="[ Agregar manual ]",
                  command=self.AgregarManual).pack(side=tk.LEFT, padx=5)
        tk.Button(FrameInferior, text="[ Borrar ]",
                  command=self.BorrarSeleccionados).pack(side=tk.LEFT, padx=5)
        tk.Button(FrameInferior, text="[ Cerrar ]",
                  command=self.VentanaManuales.destroy).pack(side=tk.LEFT, padx=5)

    def _RefrescarLista(self):
        if self.ContenedorLista is None:
            return
        for Hijo in self.ContenedorLista.winfo_children():
            Hijo.destroy()
        self._SeleccionManuales = {}
        if self.VariableTodo is not None:
            self.VariableTodo.set(False)
        Manuales = self._ListarManuales()
        if not Manuales:
            tk.Label(self.ContenedorLista,
                     text="No hay manuales agregados todavía.").pack(pady=20)
        else:
            for Etiqueta, ArchivoPath in Manuales:
                Generado = self._EsGenerado(Etiqueta, ArchivoPath)
                Fila = tk.Frame(self.ContenedorLista)
                Fila.pack(fill=tk.X, pady=2)
                Nombre = NombreCortoManual(Etiqueta) if Generado else Path(Etiqueta).stem
                Texto = f"> [IA] {Nombre}" if Generado else f"> {Nombre}"
                Opciones = {
                    "text": Texto, "anchor": "w",
                    "command": lambda Ruta=ArchivoPath: self.AbrirManual(Ruta),
                }
                if Generado:
                    Opciones["fg"] = Rosa
                Variable = tk.BooleanVar(value=False)
                tk.Checkbutton(
                    Fila, variable=Variable, text="", bd=0,
                    bg=Fondo, fg=ColorTexto, activebackground=Fondo,
                    activeforeground=Lila, selectcolor=Panel,
                    highlightthickness=0, cursor="hand2",
                ).pack(side=tk.LEFT, padx=(0, 4))
                BotonAbrir = tk.Button(Fila, **Opciones)
                BotonAbrir.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self._SeleccionManuales[ArchivoPath] = Variable

                # Renombrar y borrar se hacen con el raton, sin botones que
                # ocupen la fila: clic derecho sobre el manual.
                Menu = tk.Menu(Fila, tearoff=0)
                Menu.add_command(
                    label="Renombrar",
                    command=lambda Ruta=ArchivoPath: self.RenombrarManual(Ruta),
                )
                Menu.add_command(
                    label="Borrar",
                    command=lambda Ruta=ArchivoPath: self.BorrarManual(Ruta),
                )

                def MostrarMenu(Evento, M=Menu):
                    try:
                        M.tk_popup(Evento.x_root, Evento.y_root)
                    finally:
                        M.grab_release()
                    return "break"

                for Widget in (BotonAbrir, Fila):
                    Widget.bind("<Button-3>", MostrarMenu)
                    Widget.bind("<Button-2>", MostrarMenu)
        self._EnlazarRuedaEnArbol(self.ContenedorLista)
        if self.Lienzo is not None:
            self.ContenedorLista.update_idletasks()
            self.Lienzo.configure(scrollregion=self.Lienzo.bbox("all"))

    def _MarcarTodosLosManuales(self):
        Valor = bool(self.VariableTodo is not None and self.VariableTodo.get())
        for Variable in self._SeleccionManuales.values():
            Variable.set(Valor)

    def BorrarSeleccionados(self):
        """Borra de una vez todos los manuales marcados con la casilla."""
        Rutas = [Ruta for Ruta, Variable in self._SeleccionManuales.items()
                 if Variable.get()]
        if not Rutas:
            messagebox.showinfo("Borrar manuales",
                                "No has marcado ningún manual.",
                                parent=self.VentanaManuales)
            return
        Nombres = ", ".join(Ruta.stem for Ruta in Rutas[:5])
        if len(Rutas) > 5:
            Nombres += f" y {len(Rutas) - 5} más"
        if not messagebox.askyesno(
            "Borrar manuales",
            f"¿Borrar {len(Rutas)} manual(es)?\n\n{Nombres}\n\n"
            "Esta acción no se puede deshacer.",
            parent=self.VentanaManuales,
        ):
            return
        Errores = []
        for Ruta in Rutas:
            try:
                Ruta.unlink()
            except OSError as E:
                Errores.append(f"{Ruta.name}: {E}")
                continue
            Rel = self._RutaRelativa(Ruta)
            self._GuardarMarca("manual_generado", Rel, Ruta, False)
            self._GuardarMarca("aviso_manual_visto", Rel, Ruta, False)
        self._RefrescarLista()
        if Errores:
            messagebox.showerror("Error",
                                 "No se pudieron borrar:\n\n" + "\n".join(Errores),
                                 parent=self.VentanaManuales)

    def BorrarManual(self, RutaPath):
        if not messagebox.askyesno(
            "Borrar manual",
            f"¿Seguro que quieres borrar '{RutaPath.stem}'?\nEsta acción no se puede deshacer.",
            parent=self.VentanaManuales,
        ):
            return
        try:
            RutaPath.unlink()
        except OSError as E:
            logging.exception("No se pudo borrar el manual %s", RutaPath)
            messagebox.showerror("Error", f"No se pudo borrar el manual:\n{E}",
                                 parent=self.VentanaManuales)
            return
        Rel = self._RutaRelativa(RutaPath)
        self._GuardarMarca("manual_generado", Rel, RutaPath, False)
        self._GuardarMarca("aviso_manual_visto", Rel, RutaPath, False)
        self._RefrescarLista()

    def AgregarManual(self):
        Ruta = filedialog.askopenfilename(
            filetypes=[("Texto o Word", "*.txt *.docx")],
            title="Selecciona el manual que quieres agregar",
            parent=self.VentanaManuales,
        )
        if not Ruta:
            return
        Origen = Path(Ruta)
        Destino = self.RutaManualesUsuario / Origen.name
        if Destino.exists() and not messagebox.askyesno(
            "Agregar manual",
            f"Ya existe '{Origen.name}'.\n¿Quieres reemplazarlo?",
            parent=self.VentanaManuales,
        ):
            return
        try:
            self.RutaManualesUsuario.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Origen, Destino)
        except OSError as E:
            logging.exception("No se pudo agregar el manual %s", Origen)
            messagebox.showerror("Error", f"No se pudo agregar el manual:\n{E}",
                                 parent=self.VentanaManuales)
            return
        self._RefrescarLista()

    def AbrirManual(self, RutaPath):
        RutaRel = self._RutaRelativa(RutaPath)
        if self._EsGenerado(RutaRel, RutaPath) and not self._AvisoVisto(RutaRel, RutaPath):
            self._GuardarMarca("aviso_manual_visto", RutaRel, RutaPath, True)
            messagebox.showinfo(
                "Aviso",
                "Venus es una IA y puede contener errores.\n\n"
                "Este manual fue generado por IA y no pasó por revisión humana.",
                parent=self.VentanaManuales,
            )
        if RutaPath.suffix.lower() == ".docx":
            try:
                AbrirConSistema(RutaPath)
            except Exception as E:
                logging.exception("No se pudo abrir %s", RutaPath)
                messagebox.showerror("Error", f"No se pudo abrir el manual:\n{E}",
                                     parent=self.VentanaManuales)
            return
        try:
            Contenido = LeerTextoArchivo(RutaPath)
        except Exception as E:
            logging.exception("No se pudo abrir el manual %s", RutaPath)
            messagebox.showerror("Error", f"No se pudo abrir el manual:\n{E}",
                                 parent=self.VentanaManuales)
            return
        VentanaManual = tk.Toplevel(self.VentanaManuales)
        TituloVentana = NombreCortoManual(RutaPath.name) if self._EsGenerado(RutaRel, RutaPath) else RutaPath.stem
        VentanaManual.title(TituloVentana)
        Texto = scrolledtext.ScrolledText(
            VentanaManual, wrap=tk.WORD,
            font=(FuenteMono, TamanoFuente - 4), width=60, height=18)
        Texto.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        Texto.insert("1.0", Contenido)
        Texto.config(state="disabled")

        def Rueda(Evento):
            Arriba = getattr(Evento, "num", None) == 4 or getattr(Evento, "delta", 0) > 0
            Texto.yview_scroll(-3 if Arriba else 3, "units")
            return "break"

        Texto.bind("<MouseWheel>", Rueda)
        Texto.bind("<Button-4>", Rueda)
        Texto.bind("<Button-5>", Rueda)
        tk.Button(VentanaManual, text="[ Cerrar ]",
                  command=VentanaManual.destroy).pack(pady=(0, 10))
