import logging
import queue
import re
import threading
import tkinter as tk
import unicodedata
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox

from ia.codigo.ai import CargarImagenes
from ia.codigo.flujo import Modos, ErrorConfiguracion, Orquestador
from ia.codigo.proveedores import Completa, EtiquetaPerfilActivo, TextoFaltantes
from ..config import (
    Apagado, BurbujaSistemaBorde, BurbujaSistemaFondo, BurbujaUsuarioBorde,
    BurbujaUsuarioFondo, BurbujaVenusBorde, BurbujaVenusFondo, ColorSeleccion,
    ColorTexto, ColorTextoSeleccion, ColorUsuario, ColorVenus, Fondo,
    FuenteLectura, FuenteMono, FuenteTexto, GuardarManualesAuto, Lila,
    MensajeSinInternet, Oscuro, Panel, Rosa, RutaManuales, TamanoFuente,
)
from ..images import BuscarImagen, CargarImagenTk
from ..system import HayInternet
from ..text import (
    EtiquetaImagen, EtiquetaUsuario, LimpiarEtiquetas, NombreCortoManual,
    ParsearHistorial,
)
from ..theme import Cabecera
from .dialogs import PedirTextoDialogo

# Altura maxima (en lineas visibles) del campo de escritura.
MaxLineasEntrada = 6

# Saludos que no sirven como titulo de conversacion.
SaludoInicial = re.compile(
    r"^(hola|holi|buenas|buenos d[ií]as|buenas tardes|buenas noches|hey|"
    r"que tal|qué tal|saludos|hi|hello)\b",
    re.IGNORECASE,
)


class VentanaMemoriza:
    def __init__(self, VentanaPadre, BaseDatos):
        self.VentanaPadre = VentanaPadre
        self.BaseDatos = BaseDatos
        self.Orquestador = None
        self.Imagenes = {}
        self._HistorialIA = []
        self._ColaProgreso = queue.Queue()
        self._TareaProgreso = None
        self.EtiquetaProgreso = None
        self.PedirConfig = None
        self.AbrirPerfiles = None
        self.VentanaMemoriza = None
        self.ProfeIngles = False
        try:
            Modo = self.BaseDatos.LeerAjuste("modo_ia") or "generacion"
            if Modo == "ingles":
                # Compatibilidad: el antiguo modo Inglés pasa a Profesor+Inglés.
                Modo = "profesor"
                self.ProfeIngles = True
            else:
                self.ProfeIngles = (
                    self.BaseDatos.LeerAjuste("modo_profesor_ingles") == "1")
        except Exception:
            Modo = "generacion"
        if Modo not in Modos:
            Modo = "generacion"
        self.Modo = Modo
        self.PanelAcciones = None
        self.BotonMenu = None
        self.BotonModo = None
        self.BotonIngles = None
        self.BotonPerfil = None
        self._ImagenesTk = []
        self._Registro = []
        self._EtiquetasTexto = []
        self.LienzoChat = None
        self.MensajesFrame = None
        self._VentanaChat = None
        self._ManualesAuto = {}
        # Id de la conversacion en la base de datos: None = aun sin guardar.
        self._IdConversacion = None

    def MostrarVentanaMemoriza(self):
        if self.VentanaMemoriza is not None and self.VentanaMemoriza.winfo_exists():
            self.VentanaMemoriza.lift()
            return

        # Cada apertura empieza una conversacion nueva. Se guarda sola al
        # cerrar la ventana del chat o la app (guardarConversacionAutomatica).
        self.Orquestador = None
        self._HistorialIA = []
        self._ColaProgreso = queue.Queue()
        self.EtiquetaProgreso = None
        self.MensajesFrame = None
        self.LienzoChat = None
        self._VentanaChat = None
        self._Registro = []
        self._EtiquetasTexto = []
        self._ImagenesTk = []
        self._IdConversacion = None
        self.PanelAcciones = None
        self.BotonMenu = None
        self.BotonModo = None
        self.BotonIngles = None
        self.BotonPerfil = None
        self._UltimoAnchoAjuste = 0
        self._FuenteMensajeCache = None
        self._SeleccionMultiple = None
        self._AnclaSeleccion = None
        self._AnclaNativa = True
        self._Arrastrando = False
        self._UltimoPunto = None
        self._TareaScroll = None
        self._ManualesAuto = {}

        self.Imagenes = CargarImagenes()
        if not Completa():
            messagebox.showwarning(
                "Venus",
                "Faltan IAs por configurar: " + TextoFaltantes() +
                ".\n\nAbre Ajustes → APIs y modelos y completa C, R1 y P "
                "(R2 es opcional).",
                parent=self.VentanaPadre,
            )
            return

        self.VentanaMemoriza = tk.Toplevel(self.VentanaPadre)
        self.VentanaMemoriza.title("Venus")
        # Si otra parte de la app cierra esta ventana (p. ej. al cambiar de
        # tema), se guarda la conversacion antes de destruirla.
        self.VentanaMemoriza.cerrarGuardando = self._CerrarChat
        Cabecera(self.VentanaMemoriza, "Venus").pack(side=tk.TOP, pady=(10, 0))

        # Conversacion en burbujas dentro de un lienzo desplazable.
        MarcoChat = tk.Frame(self.VentanaMemoriza)
        MarcoChat.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.LienzoChat = tk.Canvas(MarcoChat, highlightthickness=0, bg=Fondo,
                                    width=560, height=440)
        BarraChat = tk.Scrollbar(MarcoChat, orient="vertical", command=self.LienzoChat.yview)
        self.LienzoChat.configure(yscrollcommand=BarraChat.set)
        BarraChat.pack(side=tk.RIGHT, fill=tk.Y)
        self.LienzoChat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.MensajesFrame = tk.Frame(self.LienzoChat, bg=Fondo)
        self._VentanaChat = self.LienzoChat.create_window(
            (0, 0), window=self.MensajesFrame, anchor="nw")
        self.MensajesFrame.bind(
            "<Configure>", lambda _E: self.LienzoChat.configure(
                scrollregion=self.LienzoChat.bbox("all")))
        self.LienzoChat.bind("<Configure>", self._AjustarAnchoChat)
        self._EnlazarRueda(self.LienzoChat)
        self._EnlazarRueda(self.MensajesFrame)

        self.EtiquetaProgreso = tk.Label(
            self.VentanaMemoriza, text=" ", fg=Apagado, bg=Fondo,
            font=(FuenteLectura, max(8, TamanoFuente - 15)),
        )
        self.EtiquetaProgreso.pack(pady=(0, 2))

        FrameEntrada = tk.Frame(self.VentanaMemoriza)
        FrameEntrada.pack(fill=tk.X, padx=10, pady=(0, 10))
        # Campo multilinea: crece con el mensaje (hasta MAX_LINEAS_ENTRADA).
        # Es mas estrecho que antes para que [ Menú ] quepa junto a [ Enviar ].
        self.CampoEntrada = tk.Text(
            FrameEntrada, font=(FuenteLectura, TamanoFuente), height=1, width=16,
            wrap=tk.WORD, bd=0, highlightthickness=1,
        )
        self.CampoEntrada.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.CampoEntrada.bind("<Return>", self._EnviarConEnter)
        self.CampoEntrada.bind("<Shift-Return>", self._SaltoDeLinea)
        self.CampoEntrada.bind("<KeyRelease>", self._AjustarAlturaEntrada)
        self._PrepararMenuEntrada()
        self.BotonEnviar = tk.Button(FrameEntrada, text="[ Enviar ]", command=self.Enviar)
        self.BotonEnviar.pack(side=tk.RIGHT, padx=(5, 0), anchor="n")
        # [ Menú ] va al lado de [ Enviar ], en la misma barra de escritura.
        self.BotonMenu = tk.Button(FrameEntrada, text="[ Menú ]",
                                   command=self._AbrirMenuAcciones)
        self.BotonMenu.pack(side=tk.RIGHT, padx=(5, 0), anchor="n")

        FrameAcciones = tk.Frame(self.VentanaMemoriza)
        FrameAcciones.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(FrameAcciones, text="[ Copiar chat ]",
                  command=self.CopiarChat).pack(fill=tk.X)

        # Panel de acciones: se despliega ENCIMA de [ Menú ], sobre el chat, y
        # no se sale de la ventana ni tapa el aviso ni el boton Cerrar.
        self.PanelAcciones = tk.Frame(
            self.VentanaMemoriza, bg=Panel, bd=0,
            highlightthickness=2, highlightbackground=Lila,
        )
        self.BotonHistorial = self._CrearBotonPanel(
            "Historial", self.MostrarHistorialConversaciones)
        self.BotonAgregar = self._CrearBotonPanel(
            "Agregar manual", self.AgregarManual)
        self.BotonModo = self._CrearBotonPanel("Modo: Generación", self.AlternarModo)
        self.BotonIngles = self._CrearBotonPanel("Inglés: off", self.AlternarIngles)
        self.BotonIngles.pack_forget()
        self.BotonPerfil = self._CrearBotonPanel(
            f"IAs: {EtiquetaPerfilActivo()}", self._AbrirPerfiles)
        self._PintarBotonModo()
        self._PintarBotonPerfil()

        tk.Label(
            self.VentanaMemoriza,
            text="Venus es una IA y puede cometer errores.",
            fg=Apagado, bg=Fondo, justify=tk.CENTER,
            font=(FuenteLectura, max(8, TamanoFuente - 14)),
        ).pack(pady=(0, 2))
        tk.Button(self.VentanaMemoriza, text="[ Cerrar ]",
                  command=self._CerrarChat).pack(pady=(0, 10))
        # Cerrar con la X guarda la conversacion igual que el boton Cerrar.
        self.VentanaMemoriza.protocol("WM_DELETE_WINDOW", self._CerrarChat)
        # El panel se cierra al hacer clic en cualquier otro sitio o con Escape.
        self.VentanaMemoriza.bind("<Button-1>", self._ClicFueraPanel, add="+")
        # Y la seleccion del chat se limpia al pulsar fuera de los mensajes.
        self.VentanaMemoriza.bind("<Button-1>", self._ClicFueraSeleccion, add="+")
        self.VentanaMemoriza.bind(
            "<Escape>", lambda _E: self._CerrarMenuAcciones(), add="+")

    def ConfigCambiada(self):
        """La configuración de APIs/modelos/modo cambió: se relee al enviar."""
        self.Orquestador = None
        self._PintarBotonPerfil()

    def _AbrirPerfiles(self):
        if callable(self.AbrirPerfiles):
            self.AbrirPerfiles()

    def _PintarBotonPerfil(self):
        if self.BotonPerfil is not None and self.BotonPerfil.winfo_exists():
            self.BotonPerfil.config(text=f"IAs: {EtiquetaPerfilActivo()}")

    def _CrearBotonPanel(self, Texto, Comando):
        """Boton del panel con el mismo estilo [ ... ] que el resto de la app."""
        Boton = tk.Button(
            self.PanelAcciones, text=Texto, anchor="w", justify=tk.LEFT,
            command=lambda: (self._CerrarMenuAcciones(), Comando()),
        )
        Boton.pack(fill=tk.X, padx=6, pady=3)
        return Boton

    def _PintarBotonModo(self):
        """Refleja el modo (Generación / Profesor) y el botón Inglés."""
        Nombre = "Generación" if self.Modo == "generacion" else "Profesor"
        if self.BotonModo is not None and self.BotonModo.winfo_exists():
            self.BotonModo.config(text=f"[ Modo: {Nombre} ]")
        if self.BotonMenu is not None and self.BotonMenu.winfo_exists():
            Extra = (" · Inglés" if self.Modo == "profesor" and self.ProfeIngles
                     else "")
            self.BotonMenu.config(text=f"[ Menú · {Nombre}{Extra} ]")
        self._PintarBotonIngles()

    def _PintarBotonIngles(self):
        """Muestra u oculta el botón Inglés según el modo activo."""
        if self.BotonIngles is None or not self.BotonIngles.winfo_exists():
            return
        self.BotonIngles.config(
            text=f"Inglés: {'on' if self.ProfeIngles else 'off'}")
        Empaquetado = bool(self.BotonIngles.winfo_manager())
        if self.Modo == "profesor" and not Empaquetado:
            self.BotonIngles.pack(
                fill=tk.X, padx=6, pady=3, after=self.BotonModo)
        elif self.Modo != "profesor" and Empaquetado:
            self.BotonIngles.pack_forget()

    def _AbrirMenuAcciones(self):
        """Despliega el panel encima del boton, sin salirse de la ventana."""
        if self.PanelAcciones is None or not self.PanelAcciones.winfo_exists():
            return
        if self.PanelAcciones.winfo_ismapped():
            self._CerrarMenuAcciones()
            return
        self.PanelAcciones.update_idletasks()
        Ancho = max(self.BotonMenu.winfo_width(), self.PanelAcciones.winfo_reqwidth())
        Alto = self.PanelAcciones.winfo_reqheight()
        XBoton = self.BotonMenu.winfo_rootx() - self.VentanaMemoriza.winfo_rootx()
        YBoton = self.BotonMenu.winfo_rooty() - self.VentanaMemoriza.winfo_rooty()
        X = XBoton
        Y = YBoton - Alto - 6
        if Y < 4:                       # sin hueco arriba: se abre hacia abajo
            Y = YBoton + self.BotonMenu.winfo_height() + 6
        X = max(4, min(X, self.VentanaMemoriza.winfo_width() - Ancho - 4))
        Y = max(4, min(Y, self.VentanaMemoriza.winfo_height() - Alto - 4))
        self.PanelAcciones.place(x=X, y=Y, width=Ancho)
        self.PanelAcciones.lift()

    def _CerrarMenuAcciones(self):
        if self.PanelAcciones is not None and self.PanelAcciones.winfo_exists():
            self.PanelAcciones.place_forget()

    def _ClicFueraPanel(self, Evento=None):
        """Cierra el panel al pulsar en cualquier sitio que no sea el panel."""
        if self.PanelAcciones is None or not self.PanelAcciones.winfo_ismapped():
            return
        Widget = getattr(Evento, "widget", None)
        while Widget is not None:
            if Widget is self.PanelAcciones or Widget is self.BotonMenu:
                return
            Widget = getattr(Widget, "master", None)
        self._CerrarMenuAcciones()

    def AlternarModo(self):
        self.Modo = "profesor" if self.Modo == "generacion" else "generacion"
        try:
            self.BaseDatos.GuardarAjuste("modo_ia", self.Modo)
        except Exception:
            logging.exception("No se pudo guardar el modo de trabajo")
        self._PintarBotonModo()

    def AlternarIngles(self):
        self.ProfeIngles = not self.ProfeIngles
        try:
            self.BaseDatos.GuardarAjuste(
                "modo_profesor_ingles", "1" if self.ProfeIngles else "0")
        except Exception:
            logging.exception("No se pudo guardar la opción de inglés")
        self._PintarBotonModo()

    def _RuedaHistorial(self, Evento):
        """Desplaza la conversacion con la rueda del raton."""
        if self.LienzoChat is None:
            return "break"
        Arriba = getattr(Evento, "num", None) == 4 or getattr(Evento, "delta", 0) > 0
        self.LienzoChat.yview_scroll(-3 if Arriba else 3, "units")
        return "break"

    def _EnlazarRueda(self, Widget):
        for Evento in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            Widget.bind(Evento, self._RuedaHistorial)

    def _EnlazarRuedaEnArbol(self, Widget):
        self._EnlazarRueda(Widget)
        for Hijo in Widget.winfo_children():
            self._EnlazarRuedaEnArbol(Hijo)

    def _SaltoDeLinea(self, Evento=None):
        """Shift+Enter: nueva linea dentro del mensaje, sin enviarlo."""
        self.CampoEntrada.insert(tk.INSERT, "\n")
        self._AjustarAlturaEntrada()
        return "break"

    def _EnviarConEnter(self, Evento=None):
        """Enter: envia el mensaje (salvo que Venus este respondiendo)."""
        if str(self.BotonEnviar["state"]) != "disabled":
            self.Enviar()
        return "break"

    def _AjustarAlturaEntrada(self, Evento=None):
        """Hace crecer el campo de escritura segun las lineas visibles."""
        try:
            self.CampoEntrada.update_idletasks()
            if self.CampoEntrada.winfo_width() <= 1:
                return
            Cuenta = self.CampoEntrada.count("1.0", "end-1c", "displaylines")
            if Cuenta is None:
                Lineas = 1
            else:
                Lineas = (Cuenta[0] if isinstance(Cuenta, tuple) else int(Cuenta)) + 1
        except (tk.TclError, TypeError, ValueError):
            Lineas = 1
        Lineas = max(1, min(MaxLineasEntrada, Lineas))
        if int(self.CampoEntrada.cget("height")) != Lineas:
            self.CampoEntrada.configure(height=Lineas)

    def _LimpiarChat(self):
        self._CancelarScrollSostenido()
        self._SeleccionMultiple = None
        self._AnclaSeleccion = None
        self._Arrastrando = False
        self._UltimoPunto = None
        if self.MensajesFrame is not None:
            for Hijo in self.MensajesFrame.winfo_children():
                Hijo.destroy()
        self._Registro.clear()
        self._EtiquetasTexto.clear()
        self._ImagenesTk.clear()

    def _AnchoBurbuja(self):
        Ancho = self.LienzoChat.winfo_width() if self.LienzoChat is not None else 0
        if Ancho <= 1:
            Ancho = 560
        return max(220, Ancho - 90)

    def _AjustarAnchoChat(self, Evento=None):
        if self.LienzoChat is None:
            return
        try:
            Ancho = self.LienzoChat.winfo_width()
            self.LienzoChat.itemconfig(self._VentanaChat, width=Ancho)
        except tk.TclError:
            return
        if Ancho == self._UltimoAnchoAjuste:
            return
        self._UltimoAnchoAjuste = Ancho
        for Etiqueta in self._EtiquetasTexto:
            if not Etiqueta.winfo_exists():
                continue
            if isinstance(Etiqueta, tk.Text):
                Texto = Etiqueta.get("1.0", "end-1c")
                NuevoAncho = self._AnchoParaTexto(Texto)
                if int(Etiqueta.cget("width")) != NuevoAncho:
                    Etiqueta.configure(width=NuevoAncho)
                self._AjustarAlturaTexto(Etiqueta)
            else:
                Etiqueta.configure(wraplength=self._AnchoBurbuja())

    def _DesplazarAlFinal(self):
        if self.LienzoChat is None:
            return
        self.MensajesFrame.update_idletasks()
        self.LienzoChat.configure(scrollregion=self.LienzoChat.bbox("all"))
        self.LienzoChat.yview_moveto(1.0)

    @staticmethod
    def _EstiloBurbuja(Quien):
        if Quien == "User":
            return ColorUsuario, BurbujaUsuarioFondo, BurbujaUsuarioBorde, "e"
        if Quien == "Venus":
            return ColorVenus, BurbujaVenusFondo, BurbujaVenusBorde, "w"
        return Rosa, BurbujaSistemaFondo, BurbujaSistemaBorde, "w"

    def AgregarTexto(self, Quien, Texto, Razonamiento=""):
        if self.MensajesFrame is None:
            return
        if Quien != "User":
            Texto = LimpiarEtiquetas(Texto)
        self._Registro.append((Quien, Texto))
        ColorNombre, FondoBurbuja, Borde, Lado = self._EstiloBurbuja(Quien)

        Contenedor = tk.Frame(self.MensajesFrame, bg=Fondo)
        Contenedor.pack(fill=tk.X, pady=4)
        Contenedor._esMensaje = True

        if Razonamiento:
            if len(Razonamiento) > 3000:
                Razonamiento = Razonamiento[:3000].rstrip() + "…"
            Pensamiento = tk.Label(
                Contenedor, text=f"Pensamiento de Venus:\n{Razonamiento}",
                justify=tk.LEFT, anchor="w", bg=Fondo, fg=Apagado,
                font=(FuenteLectura, TamanoFuente - 3, "italic"))
            Pensamiento.pack(anchor="w", padx=12, pady=(0, 3))
            Pensamiento.configure(wraplength=self._AnchoBurbuja())
            self._EtiquetasTexto.append(Pensamiento)

        Burbuja = tk.Frame(Contenedor, bg=FondoBurbuja, highlightthickness=2,
                           highlightbackground=Borde, highlightcolor=Borde)
        Burbuja.pack(anchor=Lado, padx=10)

        NombreMostrado = EtiquetaUsuario() if Quien == "User" else Quien

        # El nombre va DENTRO del texto del mensaje (primera linea, en negrita
        # y con su color) para que se pueda seleccionar y copiar con el resto.
        self._LlenarBurbuja(Burbuja, Texto, FondoBurbuja, NombreMostrado, ColorNombre)

        # Arrastrar desde la burbuja o el hueco del mensaje tambien selecciona.
        Piezas = [Contenedor, Burbuja]
        if Razonamiento:
            Piezas.append(Pensamiento)
        for Pieza in Piezas:
            Pieza.bind("<Button-1>", self._EmpezarSeleccion, add="+")
            Pieza.bind("<B1-Motion>", self._ArrastrarSeleccion, add="+")
            Pieza.bind("<ButtonRelease-1>", self._TerminarSeleccion, add="+")

        self._EnlazarRuedaEnArbol(Contenedor)
        self._DesplazarAlFinal()

    def _LlenarBurbuja(self, Burbuja, Texto, FondoBurbuja, Nombre="", ColorNombre=None):
        """Todo el mensaje en un solo Text: la seleccion sale continua.

        El nombre ("Venus:", "usuario:") es la primera linea del mismo texto,
        asi que tambien se selecciona y se copia. Antes cada parrafo y cada
        bloque de codigo era un Text distinto y al arrastrar quedaban huecos.
        """
        Ancho = self._AnchoParaTexto(f"{Nombre}:\n{Texto}" if Nombre else Texto)
        Mensaje = tk.Text(
            Burbuja, height=1, width=Ancho, wrap=tk.WORD,
            bd=0, relief=tk.FLAT, highlightthickness=0,
            bg=FondoBurbuja, fg=ColorTexto,
            font=(FuenteLectura, TamanoFuente - 2),
            padx=10, pady=4, spacing1=0, spacing3=0,
            selectbackground=ColorSeleccion, selectforeground=ColorTextoSeleccion,
            insertwidth=0, cursor="arrow", takefocus=1, exportselection=False,
        )
        # Titulos en negrita y codigo en monoespaciada, dentro del mismo Text.
        Mensaje.tag_config("titulo", font=(FuenteLectura, TamanoFuente - 1, "bold"))
        Mensaje.tag_config("codigo", font=(FuenteMono, max(8, TamanoFuente - 4)))
        Mensaje.tag_config(
            "nombre", font=(FuenteLectura, TamanoFuente, "bold"),
            foreground=ColorNombre or ColorTexto, spacing1=4, spacing3=2)
        if Nombre:
            Mensaje.insert(tk.END, f"{Nombre}:\n", ("nombre",))

        Imagenes = self.Imagenes
        Pos = 0
        for Coincidencia in EtiquetaImagen.finditer(Texto):
            self._InsertarSegmentos(Mensaje, Texto[Pos:Coincidencia.start()])
            Pos = Coincidencia.end()
            Ruta = BuscarImagen(Coincidencia.group(1), Imagenes)
            if Ruta is None:
                logging.warning("Imagen no encontrada: %s", Coincidencia.group(1))
                continue
            try:
                Img = CargarImagenTk(Ruta)
            except Exception:
                logging.exception("No se pudo cargar la imagen %s", Ruta)
                continue
            self._ImagenesTk.append(Img)
            Mensaje.image_create(tk.END, image=Img, pady=6)
            Mensaje.insert(tk.END, "\n")
        self._InsertarSegmentos(Mensaje, Texto[Pos:])

        Mensaje.configure(state=tk.DISABLED)
        Mensaje._mensajeWidgets = [Mensaje]
        Mensaje._textoMensaje = Texto
        Mensaje.pack(anchor="w", fill=tk.X, padx=0, pady=(2, 6))
        self._EtiquetasTexto.append(Mensaje)
        self._PrepararTextoSeleccionable(Mensaje)
        self._ProgramarAjusteAltura(Mensaje)
        return Mensaje

    def _InsertarSegmentos(self, Widget, Texto):
        """Mete prosa, titulos y codigo en el Text, cada uno con su etiqueta."""
        if not Texto:
            return
        Anterior = None
        for Tipo, Contenido in self._SegmentosMensaje(Texto):
            if Tipo == "separador":
                continue
            # Tras un bloque de codigo se deja una linea en blanco (las lineas
            # vacias que rodean las vallas ``` se pierden al quitarlas).
            if Anterior == "codigo" and not Contenido.startswith("\n"):
                Widget.insert(tk.END, "\n")
            if Tipo == "codigo":
                if not Contenido.endswith("\n"):
                    Contenido += "\n"
                Widget.insert(tk.END, Contenido, ("codigo",))
            elif Tipo == "titulo":
                Widget.insert(tk.END, Contenido, ("titulo",))
            else:
                Widget.insert(tk.END, Contenido)
            Anterior = Tipo

    @staticmethod
    def _EsLineaCodigo(Linea):
        Limpia = Linea.strip()
        if not Limpia:
            return None
        if Linea.startswith("    ") or Linea.startswith("\t"):
            return True
        if Limpia.startswith("|") and Limpia.count("|") >= 2:
            return True
        if Limpia.startswith("+") and "---" in Limpia:
            return True
        if any(C in Limpia for C in "┌┬┐├┼┤└┴┘╔╦╗╠╬╣╚╩╝─│═║"):
            return True
        return False

    @staticmethod
    def _EsSeparador(Limpia):
        return (len(Limpia) >= 10 and len(set(Limpia)) == 1
                and Limpia[0] in "=-*_")

    @staticmethod
    def _EsTitulo(Limpia):
        if re.match(r"^(?:PARTE|CAPA|CAPÍTULO|CAPITULO|BLOQUE)\s+\d+\b",
                    Limpia, re.IGNORECASE):
            return True
        if re.match(r"^\d+\.\d+[.)]?\s+\S", Limpia):
            return True
        M = re.match(r"^\d+\.\s+(.+)$", Limpia)
        if M:
            Letras = [C for C in M.group(1) if C.isalpha()]
            if Letras and sum(C.isupper() for C in Letras) / len(Letras) > 0.7:
                return True
        # Titulos generales en mayusculas (HYDRA - GUIA..., FIN DEL MANUAL).
        Letras = [C for C in Limpia if C.isalpha()]
        if 4 <= len(Letras) and len(Limpia) <= 90 and ":" not in Limpia:
            if sum(C.isupper() for C in Letras) / len(Letras) > 0.85:
                return True
        return False

    def _SegmentosMensaje(self, Texto):
        """Separa prosa, codigo/tablas, titulos y separadores."""
        Segmentos = []
        Buffer = []
        TipoActual = None
        EnFence = False
        for Linea in Texto.splitlines(keepends=True):
            Limpia = Linea.strip()
            if Limpia.startswith("```"):
                if Buffer:
                    Segmentos.append((TipoActual or "texto", "".join(Buffer)))
                    Buffer = []
                EnFence = not EnFence
                TipoActual = "codigo" if EnFence else None
                continue
            if EnFence:
                Buffer.append(Linea)
                TipoActual = "codigo"
                continue
            if not Limpia:
                Buffer.append(Linea)
                continue
            if self._EsSeparador(Limpia):
                Tipo = "separador"
            elif self._EsTitulo(Limpia):
                Tipo = "titulo"
            elif self._EsLineaCodigo(Linea):
                Tipo = "codigo"
            else:
                Tipo = "texto"
            if Tipo != TipoActual and Buffer:
                Segmentos.append((TipoActual or "texto", "".join(Buffer)))
                Buffer = []
            TipoActual = Tipo
            Buffer.append(Linea)
        if Buffer:
            Segmentos.append((TipoActual or "texto", "".join(Buffer)))
        return [(Tipo, Contenido) for Tipo, Contenido in Segmentos if Contenido.strip()]

    # ------------------------------------------------------- copiar / pegar
    def _TextoSeleccionado(self, Widget):
        try:
            return Widget.get("sel.first", "sel.last")
        except tk.TclError:
            return ""

    def _CopiarAlPortapapeles(self, Texto):
        if not Texto:
            return
        Ventana = self.VentanaMemoriza
        if Ventana is None:
            return
        try:
            Ventana.clipboard_clear()
            Ventana.clipboard_append(Texto)
            Ventana.update_idletasks()
        except tk.TclError:
            logging.exception("No se pudo copiar al portapapeles")

    # ------------------------------------------------------ seleccion multiple
    def _BloquesSeleccionables(self):
        """Bloques de texto del chat, en el orden en que se ven."""
        return [Bloque for Bloque in self._EtiquetasTexto
                if isinstance(Bloque, tk.Text) and Bloque.winfo_exists()]

    def _TextoSeleccionCompleta(self):
        """Todo lo seleccionado, aunque el arrastre cruce varios bloques."""
        Partes = []
        for Bloque in self._BloquesSeleccionables():
            try:
                Partes.append(Bloque.get(tk.SEL_FIRST, tk.SEL_LAST))
            except tk.TclError:
                continue
        return "\n".join(Parte for Parte in Partes if Parte)

    def _LimpiarSeleccion(self, Excepto=None):
        """Quita la seleccion de todos los bloques menos del indicado."""
        for Bloque in self._BloquesSeleccionables():
            if Bloque is Excepto:
                continue
            try:
                Bloque.tag_remove(tk.SEL, "1.0", "end")
            except tk.TclError:
                pass
        if Excepto is None:
            self._SeleccionMultiple = None

    def _CopiarSeleccion(self, Widget=None):
        Texto = self._TextoSeleccionCompleta()
        if not Texto and Widget is not None:
            Texto = self._TextoSeleccionado(Widget)
        self._CopiarAlPortapapeles(Texto)
        return "break"

    @staticmethod
    def _PosicionIndice(Bloque, Indice):
        try:
            Linea, Columna = str(Bloque.index(Indice)).split(".")
            return int(Linea), int(Columna)
        except (tk.TclError, ValueError):
            return 0, 0

    def _SeleccionarRango(self, Desde, Hasta):
        """Selecciona de (bloque, indice) a (bloque, indice), en cualquier orden."""
        Bloques = self._BloquesSeleccionables()
        if Desde[0] not in Bloques or Hasta[0] not in Bloques:
            return False
        Inicio = (Bloques.index(Desde[0]), *self._PosicionIndice(*Desde))
        Fin = (Bloques.index(Hasta[0]), *self._PosicionIndice(*Hasta))
        if Inicio > Fin:
            Desde, Hasta = Hasta, Desde
        BloqueInicio, IndiceInicio = Desde
        BloqueFin, IndiceFin = Hasta
        PosInicio = Bloques.index(BloqueInicio)
        PosFin = Bloques.index(BloqueFin)
        self._LimpiarSeleccion()
        try:
            if BloqueInicio is BloqueFin:
                BloqueInicio.tag_add(tk.SEL, IndiceInicio, IndiceFin)
            else:
                BloqueInicio.tag_add(tk.SEL, IndiceInicio, "end-1c")
                for Bloque in Bloques[PosInicio + 1:PosFin]:
                    Bloque.tag_add(tk.SEL, "1.0", "end-1c")
                BloqueFin.tag_add(tk.SEL, "1.0", IndiceFin)
        except tk.TclError:
            return False
        self._SeleccionMultiple = Bloques[PosInicio:PosFin + 1]
        return True

    def _SeleccionarTodoTexto(self, Widget):
        Bloques = [Bloque for Bloque in getattr(Widget, "_mensajeWidgets", [Widget])
                   if isinstance(Bloque, tk.Text) and Bloque.winfo_exists()]
        if not Bloques:
            return "break"
        if self._SeleccionarRango((Bloques[0], "1.0"), (Bloques[-1], "end-1c")):
            Widget.focus_set()
        self._AnclaSeleccion = None
        return "break"

    def _EmpezarSeleccion(self, Evento):
        """Clic: olvida la seleccion anterior y recuerda donde empieza."""
        self._LimpiarSeleccion()
        self._AnclaSeleccion = None
        self._AnclaNativa = False
        self._Arrastrando = False
        self._UltimoPunto = None
        Bloques = self._BloquesSeleccionables()
        if not Bloques:
            return None
        Widget = getattr(Evento, "widget", None)
        if isinstance(Widget, tk.Text) and Widget in Bloques:
            Bloque = Widget
            self._AnclaNativa = True
            try:
                Indice = Widget.index(f"@{Evento.X},{Evento.Y}")
            except tk.TclError:
                Indice = "1.0"
        else:
            # Arrastre empezando en la burbuja, en "Venus:" o en un hueco:
            # se toma el texto mas cercano al puntero.
            Bloque = self._BloqueEnPunto(Evento.x_root, Evento.y_root, Bloques[0])
            if Bloque is None:
                return None
            Indice = self._IndiceEnPunto(Bloque, Evento.x_root, Evento.y_root)
        self._AnclaSeleccion = (Bloque, Indice)
        # El foco en el texto hace que Ctrl+C funcione aunque el arrastre
        # haya empezado en la burbuja o en el nombre.
        try:
            Bloque.focus_set()
        except tk.TclError:
            pass
        return None

    def _TerminarSeleccion(self, _Evento=None):
        self._AnclaSeleccion = None
        self._Arrastrando = False
        self._UltimoPunto = None
        self._CancelarScrollSostenido()
        return None

    def _ClicFueraSeleccion(self, Evento=None):
        """Clic en cualquier sitio que no sea un mensaje: limpia la seleccion."""
        Widget = getattr(Evento, "widget", None)
        while Widget is not None:
            try:
                if isinstance(Widget, tk.Text) and Widget in self._EtiquetasTexto:
                    return None
                if getattr(Widget, "_esMensaje", False) or Widget is self.PanelAcciones:
                    return None
            except tk.TclError:
                return None
            Widget = getattr(Widget, "master", None)
        self._LimpiarSeleccion()
        return None

    def _BloqueEnPunto(self, XRoot, YRoot, PorDefecto):
        """Bloque de texto bajo el puntero (o el mas cercano si esta en un hueco)."""
        Objetivo = None
        try:
            Objetivo = self.VentanaMemoriza.winfo_containing(XRoot, YRoot)
        except tk.TclError:
            Objetivo = None
        while Objetivo is not None and not isinstance(Objetivo, tk.Text):
            Objetivo = getattr(Objetivo, "master", None)
        Bloques = self._BloquesSeleccionables()
        if Objetivo in Bloques:
            return Objetivo
        return self._BloqueMasCercano(YRoot, PorDefecto, Bloques)

    @staticmethod
    def _BloqueMasCercano(YRoot, PorDefecto, Bloques):
        Mejor, Distancia = PorDefecto, None
        for Bloque in Bloques:
            try:
                Arriba = Bloque.winfo_rooty()
                Abajo = Arriba + Bloque.winfo_height()
            except tk.TclError:
                continue
            if YRoot < Arriba:
                DistanciaBloque = Arriba - YRoot
            elif YRoot > Abajo:
                DistanciaBloque = YRoot - Abajo
            else:
                DistanciaBloque = 0
            if Distancia is None or DistanciaBloque < Distancia:
                Mejor, Distancia = Bloque, DistanciaBloque
        return Mejor

    @staticmethod
    def _IndiceEnPunto(Bloque, XRoot, YRoot):
        try:
            X = XRoot - Bloque.winfo_rootx()
            Y = YRoot - Bloque.winfo_rooty()
            return Bloque.index(f"@{X},{Y}")
        except tk.TclError:
            return "end-1c"

    # ------------------------------------------------ scroll al arrastrar
    def _DireccionScroll(self, YRoot, Margen=24):
        if self.LienzoChat is None:
            return 0
        try:
            Arriba = self.LienzoChat.winfo_rooty()
            Alto = self.LienzoChat.winfo_height()
        except tk.TclError:
            return 0
        if YRoot < Arriba + Margen:
            return -1
        if YRoot > Arriba + Alto - Margen:
            return 1
        return 0

    def _VistaChat(self):
        try:
            return self.LienzoChat.yview()
        except (tk.TclError, AttributeError):
            return (0.0, 0.0)

    def _AutoscrollSeleccion(self, YRoot):
        """Desplaza el chat si el arrastre llega al borde de arriba o de abajo."""
        Direccion = self._DireccionScroll(YRoot)
        if not Direccion or self.LienzoChat is None:
            return False
        try:
            self.LienzoChat.yview_scroll(Direccion, "units")
            self.LienzoChat.update_idletasks()
        except tk.TclError:
            return False
        return True

    def _ProgramarScrollSostenido(self):
        """Mientras el puntero siga en el borde, se sigue desplazando solo."""
        if self._TareaScroll is not None or self.VentanaMemoriza is None:
            return
        if self._UltimoPunto is None or not self._DireccionScroll(self._UltimoPunto[1]):
            return
        try:
            self._TareaScroll = self.VentanaMemoriza.after(45, self._ScrollSostenido)
        except tk.TclError:
            self._TareaScroll = None

    def _ScrollSostenido(self):
        self._TareaScroll = None
        if not self._Arrastrando or self._UltimoPunto is None:
            return
        XRoot, YRoot = self._UltimoPunto
        Antes = self._VistaChat()
        if not self._AutoscrollSeleccion(YRoot) or self._VistaChat() == Antes:
            return                      # ya no se puede desplazar mas
        self._AplicarSeleccionEnPunto(XRoot, YRoot)
        self._ProgramarScrollSostenido()

    def _CancelarScrollSostenido(self):
        if self._TareaScroll is not None and self.VentanaMemoriza is not None:
            try:
                self.VentanaMemoriza.after_cancel(self._TareaScroll)
            except tk.TclError:
                pass
        self._TareaScroll = None

    def _AplicarSeleccionEnPunto(self, XRoot, YRoot):
        Ancla = getattr(self, "_AnclaSeleccion", None)
        if Ancla is None:
            return
        BloqueAncla, IndiceAncla = Ancla
        Bloque = self._BloqueEnPunto(XRoot, YRoot, BloqueAncla)
        if Bloque is None:
            return
        if Bloque is BloqueAncla and self._AnclaNativa:
            # Empezando sobre el texto, dentro del mismo mensaje manda Tk.
            self._LimpiarSeleccion(Excepto=BloqueAncla)
            self._SeleccionMultiple = None
            return
        Indice = self._IndiceEnPunto(Bloque, XRoot, YRoot)
        self._SeleccionarRango((BloqueAncla, IndiceAncla), (Bloque, Indice))

    def _ArrastrarSeleccion(self, Evento):
        """Selecciona con el raton aunque el arrastre cruce de un mensaje a otro."""
        Ancla = getattr(self, "_AnclaSeleccion", None)
        if Ancla is None:
            return None
        BloqueAncla = Ancla[0]
        try:
            if not BloqueAncla.winfo_exists():
                self._AnclaSeleccion = None
                return None
        except tk.TclError:
            self._AnclaSeleccion = None
            return None

        self._UltimoPunto = (Evento.x_root, Evento.y_root)
        self._Arrastrando = True
        self._AutoscrollSeleccion(Evento.y_root)
        self._AplicarSeleccionEnPunto(Evento.x_root, Evento.y_root)
        self._ProgramarScrollSostenido()
        return "break" if self._SeleccionMultiple else None

    def _MenuParaTexto(self, Widget, ConPegar=False):
        Menu = tk.Menu(
            Widget, tearoff=0, bd=0, bg=Panel, fg=ColorTexto,
            activebackground=ColorSeleccion, activeforeground=ColorTextoSeleccion,
        )
        if ConPegar:
            Menu.add_command(label="Pegar", command=lambda: Widget.event_generate("<<Paste>>"))
            Menu.add_command(label="Cortar", command=lambda: Widget.event_generate("<<Cut>>"))
            Menu.add_separator()
        Menu.add_command(label="Copiar", command=lambda: self._CopiarSeleccion(Widget))
        Menu.add_command(label="Seleccionar todo", command=lambda: self._SeleccionarTodoTexto(Widget))
        if not ConPegar:
            Menu.add_separator()
            Menu.add_command(
                label="Copiar mensaje completo",
                command=lambda: self._CopiarAlPortapapeles(
                    getattr(Widget, "_textoMensaje", None)
                    or Widget.get("1.0", "end-1c")),
            )
            Menu.add_command(
                label="Guardar como manual (.txt)",
                command=lambda: self._GuardarManualDesdeWidget(Widget),
            )
            Menu.add_command(label="Copiar chat completo", command=self.CopiarChat)
        return Menu

    def _MostrarMenuTexto(self, Evento, Menu):
        try:
            Menu.tk_popup(Evento.x_root, Evento.y_root)
        finally:
            Menu.grab_release()
        return "break"

    def _PrepararMenuEntrada(self):
        Menu = self._MenuParaTexto(self.CampoEntrada, ConPegar=True)
        for Secuencia in ("<Button-3>", "<Button-2>"):
            self.CampoEntrada.bind(Secuencia, lambda E, M=Menu: self._MostrarMenuTexto(E, M))

    def _PrepararTextoSeleccionable(self, Widget):
        Menu = self._MenuParaTexto(Widget)
        for Secuencia in ("<Button-3>", "<Button-2>"):
            Widget.bind(Secuencia, lambda E, M=Menu: self._MostrarMenuTexto(E, M))
        for Secuencia in ("<Control-c>", "<Control-C>"):
            Widget.bind(Secuencia, lambda E, W=Widget: self._CopiarSeleccion(W))
        for Secuencia in ("<Control-a>", "<Control-A>"):
            Widget.bind(Secuencia, lambda E, W=Widget: self._SeleccionarTodoTexto(W))
        Widget.bind("<Configure>", lambda E, W=Widget: self._AjustarAlturaTexto(W))
        Widget.bind("<Button-1>", self._EmpezarSeleccion, add="+")
        Widget.bind("<B1-Motion>", self._ArrastrarSeleccion, add="+")
        Widget.bind("<ButtonRelease-1>", self._TerminarSeleccion, add="+")

    def _FuenteMensaje(self):
        if self._FuenteMensajeCache is None:
            try:
                self._FuenteMensajeCache = tkfont.Font(
                    family=FuenteLectura, size=TamanoFuente - 2)
            except tk.TclError:
                self._FuenteMensajeCache = False
        return self._FuenteMensajeCache or None

    def _AnchoTextoCaracteres(self):
        """Ancho maximo del mensaje, en caracteres, segun la fuente actual."""
        Fuente = self._FuenteMensaje()
        AnchoCaracter = max(1, Fuente.measure("0")) if Fuente else 8
        return max(24, int(self._AnchoBurbuja() / AnchoCaracter))

    def _AnchoParaTexto(self, Texto):
        Maximo = self._AnchoTextoCaracteres()
        Lineas = Texto.splitlines() or [Texto]
        Largo = max(len(Linea) for Linea in Lineas)
        return max(12, min(Maximo, Largo + 2))

    def _AjustarAlturaTexto(self, Widget):
        """Ajusta el alto del Text a lo que ocupa de verdad (texto e imagenes)."""
        if getattr(Widget, "_ajustandoAltura", False):
            return
        try:
            Widget.update_idletasks()
            if Widget.winfo_width() <= 1:
                return
            Pixeles = Widget.count("1.0", "end-1c", "ypixels")
            Fuente = self._FuenteMensaje()
            AltoLinea = max(1, Fuente.metrics("linespace")) if Fuente else 20
        except (tk.TclError, TypeError, ValueError):
            return
        if not Pixeles:
            return
        Total = Pixeles[0] if isinstance(Pixeles, tuple) else int(Pixeles)
        Lineas = max(1, -(-int(Total) // AltoLinea))
        try:
            if int(Widget.cget("height")) != Lineas:
                Widget._ajustandoAltura = True
                Widget.configure(height=Lineas)
                Widget._ajustandoAltura = False
        except tk.TclError:
            Widget._ajustandoAltura = False

    def _ProgramarAjusteAltura(self, Widget):
        """Repite el ajuste de alto hasta que la ventana acaba de colocarse.

        El primer calculo puede caer antes de que el lienzo reparta el ancho
        definitivo; con estas pasadas el mensaje nunca se queda cortado.
        """
        if self.VentanaMemoriza is None:
            return
        for Retraso in (0, 40, 150):
            try:
                self.VentanaMemoriza.after(
                    Retraso, lambda W=Widget: self._AjustarAlturaTextoSiExiste(W))
            except tk.TclError:
                return

    def _AjustarAlturaTextoSiExiste(self, Widget):
        try:
            if Widget.winfo_exists():
                self._AjustarAlturaTexto(Widget)
        except tk.TclError:
            pass

    def CopiarChat(self):
        Texto = self._TextoHistorial().rstrip()
        if not Texto:
            messagebox.showinfo("Venus", "No hay ningún mensaje para copiar.",
                                parent=self.VentanaMemoriza)
            return
        self._CopiarAlPortapapeles(Texto)
        self.AgregarTexto("Sistema", "Chat copiado al portapapeles.")

    def _TextoHistorial(self):
        Partes = [f"{Quien}: {Texto}" for Quien, Texto in self._Registro]
        return "\n\n".join(Partes) + ("\n\n" if Partes else "")

    def _InsertarHistorialGuardado(self, Contenido):
        Turnos = ParsearHistorial(Contenido)
        if not Turnos:
            if Contenido.strip():
                self.AgregarTexto("Sistema", Contenido.strip())
            return
        for Turno in Turnos:
            Quien = "User" if Turno["role"] == "user" else "Venus"
            self.AgregarTexto(Quien, Turno["content"])

    def Enviar(self):
        if str(self.BotonEnviar["state"]) == "disabled":
            return
        Pregunta = self.CampoEntrada.get("1.0", "end-1c").strip()
        if not Pregunta:
            return
        if not Completa():
            messagebox.showwarning(
                "Venus",
                "Faltan IAs por configurar: " + TextoFaltantes() +
                ".\n\nAbre Ajustes → APIs y modelos y completa C, R1 y P "
                "(R2 es opcional).",
                parent=self.VentanaMemoriza,
            )
            return

        self.CampoEntrada.delete("1.0", tk.END)
        self._AjustarAlturaEntrada()
        self.AgregarTexto("User", Pregunta)
        self.BotonEnviar.config(state="disabled")
        self.EtiquetaProgreso.config(text="Preparando a las IAs…")
        self._IniciarProgreso()

        Modo = self.Modo
        Ingles = self.ProfeIngles if Modo == "profesor" else False
        Historial = list(self._HistorialIA)
        self.VentanaMemoriza.title("Venus · trabajando…")

        def Tarea():
            EsAviso = False
            if not HayInternet():
                Respuesta, EsAviso = MensajeSinInternet, True
            else:
                try:
                    OrquestadorObj = Orquestador(
                        Modo, Historial=Historial, AlProgreso=self._Progreso,
                        Ingles=Ingles)
                    Respuesta = OrquestadorObj.Preguntar(Pregunta)
                    self._HistorialIA = OrquestadorObj.Historial
                except ErrorConfiguracion as E:
                    Respuesta, EsAviso = str(E), True
                except Exception as E:
                    logging.exception("Falló el flujo multiagente")
                    Respuesta, EsAviso = f"Error inesperado: {E}", True
            try:
                self.VentanaPadre.after(
                    0, lambda: self.MostrarRespuesta(Respuesta, "", EsAviso))
            except (RuntimeError, tk.TclError):
                logging.info("La app se cerró antes de recibir la respuesta")

        threading.Thread(target=Tarea, daemon=True).start()

    def _Progreso(self, Mensaje):
        """Se llama desde el hilo de trabajo: solo encola, no toca Tk."""
        self._ColaProgreso.put(Mensaje)

    def _IniciarProgreso(self):
        self._DetenerProgreso()
        self._TareaProgreso = self.VentanaMemoriza.after(120, self._ProcesarProgreso)

    def _DetenerProgreso(self):
        if self._TareaProgreso is not None:
            try:
                self.VentanaMemoriza.after_cancel(self._TareaProgreso)
            except tk.TclError:
                pass
            self._TareaProgreso = None

    def _ProcesarProgreso(self):
        self._TareaProgreso = None
        if self.VentanaMemoriza is None or not self.VentanaMemoriza.winfo_exists():
            return
        Ultimo = None
        while True:
            try:
                Ultimo = self._ColaProgreso.get_nowait()
            except queue.Empty:
                break
        if Ultimo and self.EtiquetaProgreso is not None:
            self.EtiquetaProgreso.config(text=Ultimo)
            self.VentanaMemoriza.title(f"Venus · {Ultimo}")
        self._TareaProgreso = self.VentanaMemoriza.after(150, self._ProcesarProgreso)

    def MostrarRespuesta(self, Respuesta, Razonamiento="", EsAviso=False):
        if self.VentanaMemoriza is None or not self.VentanaMemoriza.winfo_exists():
            return
        self._DetenerProgreso()
        if self.EtiquetaProgreso is not None and self.EtiquetaProgreso.winfo_exists():
            self.EtiquetaProgreso.config(text=" ")
        self.VentanaMemoriza.title("Venus")
        if EsAviso:
            self.AgregarTexto("Sistema", Respuesta)
        else:
            self.AgregarTexto("Venus", Respuesta, Razonamiento)
            self._GuardarManualAuto(Respuesta)
        self.BotonEnviar.config(state="normal")

    # ------------------------------------------------ manuales automaticos
    def _ContextoUsuario(self):
        Partes = []
        for Quien, Texto in reversed(self._Registro):
            if Quien == "User":
                Partes.append(Texto)
                if len(Partes) >= 6:
                    break
        return "\n".join(reversed(Partes)).lower()

    @staticmethod
    def _PareceManual(Texto, Contexto):
        if len(Texto) < 1200:
            return False
        if not any(Palabra in Contexto for Palabra in ("manual", "guía", "guia", "libro")):
            return False
        Primera = next((Linea.strip() for Linea in Texto.splitlines() if Linea.strip()),
                       "").strip("#*_ ").upper()
        if not any(Palabra in Primera for Palabra in ("MANUAL", "GUÍA", "GUIA", "LIBRO")):
            return False
        Mayusculas = Texto.upper()
        Señales = (
            "FICHA DE FUENTE", "FICHA DE SINTAXIS", "DESGLOSE",
            "CAPA 1", "CAPA 2", "FIN DE LA PARTE", "FIN DEL MANUAL",
            "PARTE 1", "PARTE 2",
        )
        return sum(1 for Señal in Señales if Señal in Mayusculas) >= 2

    @staticmethod
    def _TituloYParte(Texto):
        Primera = next(
            (Linea.strip() for Linea in Texto.splitlines()
             if Linea.strip() and Linea.strip() not in ("```", "```text")),
            "Manual generado",
        ).strip("#*_ ")
        Coincidencia = re.search(r"\bPARTE\s+(\d+)\b", Primera, re.IGNORECASE)
        if Coincidencia:
            Base = Primera[:Coincidencia.start()].strip(" -—–:")
            return Base or "Manual generado", int(Coincidencia.group(1))
        return Primera, None

    @staticmethod
    def _NombreArchivoManual(Titulo):
        Normal = unicodedata.normalize("NFKD", Titulo)
        Normal = "".join(C for C in Normal if not unicodedata.combining(C))
        Normal = re.sub(r"[^A-Za-z0-9 _-]+", " ", Normal)
        Normal = re.sub(r"\s+", " ", Normal).strip(" ._-")
        Normal = Normal[:80].strip(" ._-")
        return Normal or "Manual generado"

    def _RutaManualUnica(self, Base):
        RutaManuales.mkdir(parents=True, exist_ok=True)
        Candidato = RutaManuales / f"{Base}.txt"
        Numero = 2
        while Candidato.exists():
            Candidato = RutaManuales / f"{Base} ({Numero}).txt"
            Numero += 1
        return Candidato

    def _GuardarManualDesdeWidget(self, Widget):
        Texto = getattr(Widget, "_textoMensaje", None) or Widget.get("1.0", "end-1c")
        if Texto.strip():
            self._GuardarManualAuto(Texto, Forzar=True)

    def _GuardarManualAuto(self, Texto, Forzar=False):
        """Guarda la respuesta como .txt y la marca como generada por IA."""
        if not Forzar and not GuardarManualesAuto:
            return
        if not Forzar and not self._PareceManual(Texto, self._ContextoUsuario()):
            return
        Base, Parte = self._TituloYParte(Texto)
        Base = self._NombreArchivoManual(NombreCortoManual(Base))
        Clave = Base.lower()
        Ruta = self._ManualesAuto.get(Clave) if Parte and Parte > 1 else None
        Nuevo = True
        try:
            if Ruta is not None and Ruta.exists():
                with open(Ruta, "a", encoding="utf-8") as Archivo:
                    Archivo.write("\n\n" + Texto.rstrip() + "\n")
                Nuevo = False
            else:
                Ruta = self._RutaManualUnica(Base)
                Ruta.write_text(Texto.rstrip() + "\n", encoding="utf-8")
                self._ManualesAuto[Clave] = Ruta
        except OSError as E:
            logging.exception("No se pudo guardar el manual automático")
            self.AgregarTexto("Sistema", f"No se pudo guardar el manual en Manuales: {E}")
            return
        if self.BaseDatos is not None:
            try:
                Rel = Ruta.relative_to(RutaManuales).as_posix()
                self.BaseDatos.GuardarAjuste(f"manual_generado:{Rel}", "1")
            except Exception:
                logging.exception("No se pudo marcar el manual como generado")
        Modulo = getattr(self.VentanaPadre, "ModuloManuales", None)
        if Modulo is not None and getattr(Modulo, "VentanaManuales", None):
            try:
                Modulo._RefrescarLista()
            except Exception:
                logging.exception("No se pudo refrescar la lista de manuales")
        Accion = "guardado" if Nuevo else "actualizado"
        self.AgregarTexto("Sistema", f"Manual {Accion} en Manuales: {Ruta.name}")

    def _CerrarChat(self):
        """Cierra la ventana del chat guardando antes la conversacion."""
        self._DetenerProgreso()
        self._CancelarScrollSostenido()
        self.GuardarConversacionAutomatica()
        if self.VentanaMemoriza is not None and self.VentanaMemoriza.winfo_exists():
            self.VentanaMemoriza.destroy()

    def _TituloConversacion(self):
        """Nombre descriptivo para el historial, sacado de la conversacion.

        Se usa el primer mensaje del usuario (saltando el saludo si hay otro
        mensaje despues), limpio y cortado por palabra. Si no hay nada util,
        se cae al nombre con fecha.
        """
        Candidatos = []
        for Quien, Texto in self._Registro:
            if Quien != "User":
                continue
            Limpio = re.sub(r"[#*`_>]+", " ", Texto or "")
            Limpio = " ".join(Limpio.split()).strip(' -–—:;,.¿?¡!"\'')
            if Limpio:
                Candidatos.append(Limpio)
        if not Candidatos:
            return f"Conversación {datetime.now().strftime('%d/%m %H:%M')}"
        Elegido = Candidatos[0]
        if len(Candidatos) > 1 and len(Elegido) <= 30 and SaludoInicial.match(Elegido):
            Elegido = Candidatos[1]
        if len(Elegido) > 64:
            Corte = Elegido[:64].rsplit(" ", 1)[0].rstrip(" -–—:;,.")
            Elegido = (Corte or Elegido[:64]) + "…"
        return Elegido[0].upper() + Elegido[1:]

    def _TituloLibre(self, Titulo):
        """Evita titulos repetidos: 'Netcat', 'Netcat (2)', ..."""
        try:
            Existentes = {Fila[1] for Fila in self.BaseDatos.ListarConversaciones()}
        except Exception:
            return Titulo
        if Titulo not in Existentes:
            return Titulo
        Numero = 2
        while f"{Titulo} ({Numero})" in Existentes:
            Numero += 1
        return f"{Titulo} ({Numero})"

    def GuardarConversacionAutomatica(self):
        """Guarda el chat al cerrar la ventana o la app, sin preguntar nada.

        La primera vez crea la conversacion con un titulo sacado de lo que
        hablasteis; despues actualiza esa misma fila para no llenar el
        historial de copias cada vez que se cierra.
        """
        if self.BaseDatos is None:
            return
        Contenido = self._TextoHistorial()
        if not Contenido.strip():
            return
        try:
            if self._IdConversacion is None:
                Titulo = self._TituloLibre(self._TituloConversacion())
                self._IdConversacion = self.BaseDatos.GuardarConversacion(Titulo, Contenido)
            else:
                self.BaseDatos.ActualizarConversacion(self._IdConversacion, Contenido)
        except Exception:
            logging.exception("No se pudo guardar la conversación automáticamente")

    def MostrarHistorialConversaciones(self):
        Ventana = tk.Toplevel(self.VentanaMemoriza)
        Ventana.title("Historial de conversaciones")
        Ventana.geometry("640x500")
        Cabecera(Ventana, "Historial").pack(pady=(10, 0))
        tk.Label(Ventana, text="Conversaciones guardadas",
                 font=(FuenteTexto, TamanoFuente, "bold")).pack(pady=(5, 4))

        Seleccion = {}          # idConversacion -> BooleanVar
        VariableTodo = tk.BooleanVar(value=False)

        def Marcados():
            return [IdConv for IdConv, Variable in Seleccion.items() if Variable.get()]

        def MarcarTodos():
            for Variable in Seleccion.values():
                Variable.set(VariableTodo.get())

        MarcoTodo = tk.Frame(Ventana)
        MarcoTodo.pack(fill=tk.X, padx=16, pady=(0, 4))
        tk.Checkbutton(
            MarcoTodo, text="Seleccionar todo", variable=VariableTodo,
            command=MarcarTodos, bd=0, bg=Fondo, fg=ColorTexto,
            activebackground=Fondo, activeforeground=Lila, selectcolor=Panel,
            highlightthickness=0, cursor="hand2",
        ).pack(side=tk.LEFT)

        # Lista desplazable con una casilla por conversacion.
        MarcoLista = tk.Frame(Ventana)
        MarcoLista.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        Lienzo = tk.Canvas(MarcoLista, highlightthickness=0)
        Barra = tk.Scrollbar(MarcoLista, orient="vertical", command=Lienzo.yview)
        Lienzo.configure(yscrollcommand=Barra.set)
        Barra.pack(side=tk.RIGHT, fill=tk.Y)
        Lienzo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        Contenedor = tk.Frame(Lienzo)
        VentanaLista = Lienzo.create_window((0, 0), window=Contenedor, anchor="nw")
        Contenedor.bind(
            "<Configure>", lambda _E: Lienzo.configure(scrollregion=Lienzo.bbox("all")))
        Lienzo.bind(
            "<Configure>", lambda E: Lienzo.itemconfig(VentanaLista, width=E.width))

        def Cargar(IdConv):
            if str(self.BotonEnviar["state"]) == "disabled":
                messagebox.showinfo("Historial", "Espera a que Venus termine de responder.", parent=Ventana)
                return
            Contenido = self.BaseDatos.ObtenerConversacion(IdConv)
            if Contenido is None:
                messagebox.showerror("Historial", "No se encontró esa conversación.", parent=Ventana)
                return
            # Lo que hubiera abierto se guarda antes de cargar otra conversacion.
            self.GuardarConversacionAutomatica()
            self._LimpiarChat()
            self._InsertarHistorialGuardado(Contenido)
            # Al cerrar, se actualiza esta misma conversacion en vez de duplicarla.
            self._IdConversacion = IdConv
            self._DesplazarAlFinal()
            Aviso = None
            try:
                Turnos = ParsearHistorial(Contenido)
                self._HistorialIA = [dict(T) for T in (Turnos or [])]
                self.Orquestador = None
            except Exception:
                logging.exception("No se pudo restaurar el contexto de la conversación %s", IdConv)
                Aviso = "Conversación abierta, pero Venus no pudo recordar su contexto anterior."
            Ventana.destroy()
            if Aviso:
                self.AgregarTexto("Sistema", Aviso)

        def AbrirMarcada():
            Ids = Marcados()
            if len(Ids) != 1:
                messagebox.showinfo("Historial", "Marca una sola conversación para abrirla.",
                                    parent=Ventana)
                return
            Cargar(Ids[0])

        def Renombrar():
            Ids = Marcados()
            if len(Ids) != 1:
                messagebox.showinfo("Historial", "Marca una sola conversación para renombrarla.",
                                    parent=Ventana)
                return
            Titulo = next((T for I, T, _C in self.BaseDatos.ListarConversaciones()
                           if I == Ids[0]), "")
            Nuevo = PedirTextoDialogo(Ventana, "Renombrar chat", "Nuevo nombre del chat:",
                                      Inicial=Titulo)
            if Nuevo is None:
                return
            Nuevo = Nuevo.strip()
            if not Nuevo:
                return
            self.BaseDatos.RenombrarConversacion(Ids[0], Nuevo)
            Recargar()

        def Borrar():
            Ids = Marcados()
            if not Ids:
                messagebox.showinfo("Historial", "No has marcado ninguna conversación.",
                                    parent=Ventana)
                return
            if not messagebox.askyesno(
                "Borrar conversaciones",
                f"¿Borrar {len(Ids)} conversación(es)?\n\nEsta acción no se puede deshacer.",
                parent=Ventana,
            ):
                return
            for IdConv in Ids:
                self.BaseDatos.EliminarConversacion(IdConv)
                if IdConv == self._IdConversacion:
                    self._IdConversacion = None
            Recargar()

        def Recargar():
            for Hijo in Contenedor.winfo_children():
                Hijo.destroy()
            Seleccion.clear()
            VariableTodo.set(False)
            Conversaciones = self.BaseDatos.ListarConversaciones()
            if not Conversaciones:
                tk.Label(Contenedor, text="Todavía no hay conversaciones guardadas.",
                         fg=Apagado).pack(pady=20)
            for IdConv, Titulo, Creado in Conversaciones:
                Fila = tk.Frame(Contenedor)
                Fila.pack(fill=tk.X, pady=2)
                Variable = tk.BooleanVar(value=False)
                tk.Checkbutton(
                    Fila, variable=Variable, text="", bd=0,
                    bg=Fondo, fg=ColorTexto, activebackground=Fondo,
                    activeforeground=Lila, selectcolor=Panel,
                    highlightthickness=0, cursor="hand2",
                ).pack(side=tk.LEFT, padx=(0, 4))
                tk.Button(Fila, text=f"{Titulo}  —  {Creado}", anchor="w",
                          command=lambda I=IdConv: Cargar(I)
                          ).pack(side=tk.LEFT, fill=tk.X, expand=True)
                Seleccion[IdConv] = Variable
            Contenedor.update_idletasks()
            Lienzo.configure(scrollregion=Lienzo.bbox("all"))

        Recargar()

        FrameBotones = tk.Frame(Ventana)
        FrameBotones.pack(pady=10)
        tk.Button(FrameBotones, text="[ Abrir ]", command=AbrirMarcada).pack(side=tk.LEFT, padx=5)
        tk.Button(FrameBotones, text="[ Renombrar ]", command=Renombrar).pack(side=tk.LEFT, padx=5)
        tk.Button(FrameBotones, text="[ Borrar ]", command=Borrar).pack(side=tk.LEFT, padx=5)
        tk.Button(FrameBotones, text="[ Cerrar ]", command=Ventana.destroy).pack(side=tk.LEFT, padx=5)

    def AgregarManual(self):
        Ruta = filedialog.askopenfilename(
            filetypes=[("Texto o Word", "*.txt *.docx")],
            title="Agregar manual",
        )
        if not Ruta:
            return
        if str(self.BotonEnviar["state"]) == "disabled":
            messagebox.showinfo("Agregar manual", "Espera a que Venus termine de responder.",
                                parent=self.VentanaMemoriza)
            return

        RutaOrigen = Path(Ruta)
        CarpetaDestino = Path(RutaManuales)
        RutaDestino = CarpetaDestino / RutaOrigen.name
        if not messagebox.askyesno(
            "Agregar manual",
            f"'{RutaOrigen.name}' se guardará como MANUAL: Venus buscará en "
            "sus fragmentos cuando sean relevantes.\n\n¿Continuar?",
            parent=self.VentanaMemoriza,
        ):
            return
        if RutaDestino.exists() and not messagebox.askyesno(
            "Archivo existente",
            f"Ya existe '{RutaOrigen.name}' en la carpeta de manuales.\n¿Quieres reemplazarlo?",
            parent=self.VentanaMemoriza,
        ):
            return
        try:
            CarpetaDestino.mkdir(parents=True, exist_ok=True)
            RutaDestino.write_bytes(RutaOrigen.read_bytes())
        except Exception as E:
            logging.exception("No se pudo agregar el manual %s", RutaOrigen)
            messagebox.showerror("Error", f"No se pudo agregar el manual:\n\n{E}",
                                 parent=self.VentanaMemoriza)
            return
        self.AgregarTexto("Sistema", f"Se agregó '{RutaOrigen.name}' como manual. "
                                     "Venus buscará en él cuando sea relevante para tu pregunta.")