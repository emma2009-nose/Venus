"""Ventana para configurar las 4 IAs de Venus (proveedor, clave y modelo).

Se abre antes de la ventana principal. Cada slot corresponde a un nodo fijo:

    1  C   Contexto / Historial / Unificador
    2  R1  Revisor 1
    3  R2  Revisor 2
    4  P   Principal (la que responde al usuario)

No hay ninguna API ni modelo precargado: el usuario los pone aquí.
"""
import logging
import threading
import tkinter as tk
from tkinter import messagebox

from ia.codigo.proveedores import (
    Ids, Roles, CargarTodas, Completa, CrearEstructura,
    GuardarConfig, TextoFaltantes,
    CarpetaBase, CambiarPerfil, LeerPerfilActivo, PerfilesDisponibles,
    BorrarIAsPerfil, CrearPerfil,
)
from ..config import (
    Apagado, Borde, ColorError, ColorExito, ColorTexto, Fondo,
    FuenteLectura, FuenteMono, Lila, Oscuro, Panel,
)
from ..system import AbrirConSistema
from ..theme import Cabecera
from .dialogs import PedirTextoDialogo


def _GetJson(Url, Token=None):
    """GET a una URL y devuelve el JSON (con la librería estándar)."""
    import json
    import urllib.request

    Cabeceras = {"Accept": "application/json"}
    if Token:
        Cabeceras["Authorization"] = f"Bearer {Token}"
    Peticion = urllib.request.Request(Url, headers=Cabeceras)
    with urllib.request.urlopen(Peticion, timeout=25) as Respuesta:
        return json.loads(Respuesta.read().decode("utf-8"))


def _NombresModelos(Datos):
    """Saca los nombres de modelo de /v1/models o de /api/tags de Ollama."""
    Nombres = []

    def Agregar(Elemento):
        if isinstance(Elemento, dict):
            Nombre = (Elemento.get("id") or Elemento.get("name")
                      or Elemento.get("model"))
        else:
            Nombre = str(Elemento)
        if Nombre:
            Nombres.append(str(Nombre))

    if isinstance(Datos, dict):
        for Clave in ("data", "models"):
            Elementos = Datos.get(Clave)
            if isinstance(Elementos, list):
                for Elemento in Elementos:
                    Agregar(Elemento)
    elif isinstance(Datos, list):
        for Elemento in Datos:
            Agregar(Elemento)
    return sorted(set(Nombres))


UrlLocal = "http://localhost:11434/v1"


def _EsUrlLocal(Base):
    Base = (Base or "").lower()
    return ("localhost" in Base or "127.0.0.1" in Base
            or "0.0.0.0" in Base or "11434" in Base)


def ListarModelos(BaseUrl, Clave, Tipo="api"):
    """Lista los modelos de una API o de una IA local.

    Para IA local intenta primero /api/tags (Ollama) y luego /v1/models; así
    funciona también con LM Studio, llama.cpp, LocalAI, etc.
    """
    Base = (BaseUrl or "").strip().rstrip("/")
    Intentos = []
    if Tipo in ("ollama", "local"):
        Origen = Base[:-3] if Base.endswith("/v1") else Base
        Intentos.append((Origen + "/api/tags", None))
    Intentos.append((Base + "/models", Clave or "ollama"))

    Errores = []
    for Url, Token in Intentos:
        try:
            Modelos = _NombresModelos(_GetJson(Url, Token))
            if Modelos:
                return Modelos
        except Exception as E:
            Errores.append(E)
    if Errores:
        raise Errores[-1]
    return []


class VentanaConfigIA:
    def __init__(self, VentanaPadre, BaseDatos, AlGuardar=None, Obligatoria=False):
        self.VentanaPadre = VentanaPadre
        self.BaseDatos = BaseDatos
        self.AlGuardar = AlGuardar
        self.Obligatoria = Obligatoria
        self.Continuar = False
        self._Campos = {}
        self._Estados = {}
        self._Razonamiento = {}
        self._Modo = {}
        self._ModoAnterior = {}
        self._CheckRazonamiento = {}
        self._Editor = None
        self.PerfilActual = LeerPerfilActivo()
        self._PerfilVar = None
        self._EtiquetasPerfil = {}
        self._EtiquetaPorNombre = {}

        self.VentanaConfig = tk.Toplevel(VentanaPadre)
        self.VentanaConfig.title("Venus · IAs")
        self.VentanaConfig.resizable(False, False)
        self.VentanaConfig.configure(bg=Fondo)

        self.MostrarAlIniciar = tk.BooleanVar(
            master=self.VentanaConfig,
            value=(self.BaseDatos.LeerAjuste("mostrar_config_ias") != "0"),
        )
        self.VerClaves = tk.BooleanVar(master=self.VentanaConfig, value=False)

        self._Construir()
        self._Cargar()
        self._PintarPerfiles()
        self.VentanaConfig.protocol("WM_DELETE_WINDOW", self._Cerrar)
        self._Centrar()
        try:
            self.VentanaConfig.grab_set()
        except tk.TclError:
            pass
        self.VentanaConfig.focus_set()

    # ------------------------------------------------------------- construcción
    def _Construir(self):
        Cabecera(self.VentanaConfig, "ias").pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(
            self.VentanaConfig, text="Configura tus IAs",
            font=(FuenteLectura, 17, "bold"), fg=Lila, bg=Fondo,
        ).pack(pady=(2, 0))
        tk.Label(
            self.VentanaConfig,
            text="El usuario solo habla con P; C, R1 y R2 trabajan por detrás "
                 "(R2 es opcional).\n"
                 "URL de ejemplo: https://api.deepseek.com/v1 "
                 "(la base compatible con OpenAI, suele terminar en /v1).\n"
                 "Cada slot puede ser API o IA local; puedes mezclarlos.",
            font=(FuenteLectura, 9), fg=Apagado, bg=Fondo,
            wraplength=940, justify=tk.LEFT,
        ).pack(pady=(2, 8))

        self._MarcoPerfiles = tk.Frame(self.VentanaConfig, bg=Fondo)
        self._MarcoPerfiles.pack(pady=(0, 6))
        self._ConstruirPerfiles()

        Marco = tk.Frame(self.VentanaConfig, bg=Fondo)
        Marco.pack(padx=10, pady=(0, 6))
        for Indice, IdIA in enumerate(Ids):
            Fila, Columna = divmod(Indice, 2)
            self._Tarjeta(Marco, IdIA).grid(
                row=Fila, column=Columna, sticky="nsew", padx=6, pady=6)
        for Columna in range(2):
            Marco.grid_columnconfigure(Columna, weight=1)

        Pie = tk.Frame(self.VentanaConfig, bg=Fondo)
        Pie.pack(padx=14, pady=(2, 10), fill=tk.X)

        Fila1 = tk.Frame(Pie, bg=Fondo)
        Fila1.pack(fill=tk.X, pady=(0, 6))
        self._Boton(Fila1, "Guardar y entrar" if self.Obligatoria else "Guardar",
                    self._GuardarYCerrar).pack(side=tk.LEFT, padx=(0, 6))
        if self.Obligatoria:
            self._Boton(Fila1, "Omitir por ahora",
                        self._Omitir).pack(side=tk.LEFT, padx=(0, 6))
        self._Boton(Fila1, "Usar la API de C en R1 y P",
                    self._CopiarC).pack(side=tk.LEFT, padx=6)
        self._Boton(Fila1, "Borrar todas las IAs de este modo",
                    self._BorrarTodo).pack(side=tk.LEFT, padx=6)
        self._Boton(Fila1, "Abrir carpeta de IAs",
                    self._AbrirCarpeta).pack(side=tk.LEFT, padx=6)
        self._Boton(Fila1, "Salir", self._Salir).pack(side=tk.RIGHT)

        Fila2 = tk.Frame(Pie, bg=Fondo)
        Fila2.pack(fill=tk.X)
        tk.Checkbutton(
            Fila2, text="Mostrar claves", variable=self.VerClaves,
            command=self._AlternarClaves, font=(FuenteLectura, 9),
            fg=ColorTexto, bg=Fondo, activebackground=Fondo,
            activeforeground=Lila, selectcolor=Panel, highlightthickness=0,
        ).pack(side=tk.LEFT)
        tk.Checkbutton(
            Fila2, text="Mostrar esta pantalla al iniciar",
            variable=self.MostrarAlIniciar, font=(FuenteLectura, 9),
            fg=ColorTexto, bg=Fondo, activebackground=Fondo,
            activeforeground=Lila, selectcolor=Panel, highlightthickness=0,
        ).pack(side=tk.LEFT, padx=(16, 0))
        tk.Label(
            Fila2,
            text="Sin API ni modelo precargados · prompts y cuadernos en ~/.venus/ias/",
            font=(FuenteLectura, 8), fg=Apagado, bg=Fondo,
        ).pack(side=tk.RIGHT)

    def _Tarjeta(self, Padre, IdIA):
        Rol = Roles[IdIA]
        Tarjeta = tk.Frame(Padre, bg=Panel, bd=0,
                           highlightbackground=Borde, highlightthickness=1)

        Titulo = f'[{Rol["clave"]}]  {Rol["nombre"]}'
        if IdIA == 3:
            Titulo += " · opcional"
        tk.Label(
            Tarjeta, text=Titulo,
            font=(FuenteLectura, 13, "bold"), fg=Lila, bg=Panel,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 0))
        tk.Label(
            Tarjeta, text=Rol["descripcion"],
            font=(FuenteLectura, 8), fg=Apagado, bg=Panel,
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 6))

        Etiqueta = dict(font=(FuenteLectura, 9), fg=ColorTexto, bg=Panel, anchor="w")

        tk.Label(Tarjeta, text="Proveedor (URL)", **Etiqueta).grid(
            row=2, column=0, sticky="w", padx=(10, 6), pady=2)
        CampoBase = tk.Entry(Tarjeta, font=(FuenteMono, 9), width=44)
        CampoBase.grid(row=2, column=1, columnspan=2, sticky="we",
                       padx=(0, 10), pady=2)

        tk.Label(Tarjeta, text="Clave API", **Etiqueta).grid(
            row=3, column=0, sticky="w", padx=(10, 6), pady=2)
        CampoClave = tk.Entry(Tarjeta, font=(FuenteMono, 9), width=36, show="•")
        CampoClave.grid(row=3, column=1, sticky="we", padx=(0, 6), pady=2)
        self._Boton(
            Tarjeta, "Borrar",
            lambda: CampoClave.delete(0, tk.END), Compacto=True,
        ).grid(row=3, column=2, sticky="e", padx=(0, 10), pady=2)

        tk.Label(Tarjeta, text="Modelo", **Etiqueta).grid(
            row=4, column=0, sticky="w", padx=(10, 6), pady=2)
        CampoModelo = tk.Entry(Tarjeta, font=(FuenteMono, 9), width=32)
        CampoModelo.grid(row=4, column=1, sticky="we", padx=(0, 6), pady=2)
        self._Boton(
            Tarjeta, "Ver modelos",
            lambda: self._VerModelos(IdIA), Compacto=True,
        ).grid(row=4, column=2, sticky="e", padx=(0, 10), pady=2)

        Estado = tk.Label(Tarjeta, text="", font=(FuenteLectura, 8), bg=Panel)
        Estado.grid(row=5, column=0, columnspan=3, sticky="w", padx=10, pady=(4, 0))

        FilaInferior = tk.Frame(Tarjeta, bg=Panel)
        FilaInferior.grid(row=6, column=0, columnspan=3, sticky="we",
                          padx=10, pady=(4, 8))
        tk.Label(
            FilaInferior, text="Modo:", font=(FuenteLectura, 8),
            fg=ColorTexto, bg=Panel,
        ).pack(side=tk.LEFT)
        VarModo = tk.StringVar(master=self.VentanaConfig, value="api")
        for TextoModo, ValorModo in (("API", "api"), ("IA local", "local")):
            tk.Radiobutton(
                FilaInferior, text=TextoModo, variable=VarModo,
                value=ValorModo, command=lambda: self._CambiarModo(IdIA),
                font=(FuenteLectura, 8), fg=ColorTexto, bg=Panel,
                activebackground=Panel, activeforeground=Lila,
                selectcolor=Panel, highlightthickness=0,
            ).pack(side=tk.LEFT, padx=(4, 0))
        VarRazonamiento = tk.BooleanVar(master=self.VentanaConfig, value=False)
        CheckRazonamiento = tk.Checkbutton(
            FilaInferior, text="Razonamiento off", variable=VarRazonamiento,
            font=(FuenteLectura, 8), fg=ColorTexto, bg=Panel,
            activebackground=Panel, activeforeground=Lila,
            selectcolor=Panel, highlightthickness=0,
        )
        CheckRazonamiento.pack(side=tk.LEFT, padx=(8, 0))
        self._Boton(
            FilaInferior, "Prompts y cuaderno",
            lambda: self._AbrirEditor(IdIA), Compacto=True,
        ).pack(side=tk.RIGHT)
        self._Razonamiento[IdIA] = VarRazonamiento
        self._Modo[IdIA] = VarModo
        self._CheckRazonamiento[IdIA] = CheckRazonamiento

        Tarjeta.grid_columnconfigure(1, weight=1)
        Tarjeta.grid_columnconfigure(2, minsize=86)
        self._Campos[IdIA] = {
            "base": CampoBase, "clave": CampoClave, "modelo": CampoModelo,
        }
        self._Estados[IdIA] = Estado
        return Tarjeta

    def _Boton(self, Padre, Texto, Comando, Compacto=False):
        return tk.Button(
            Padre, text=f"[ {Texto} ]", command=Comando,
            font=(FuenteLectura, 8 if Compacto else 9, "bold"),
            fg=Lila, bg=Panel, activebackground=Lila, activeforeground=Oscuro,
            bd=0, padx=6, pady=2,
        )

    # ------------------------------------------------------------------- datos
    def _Cargar(self):
        for Proveedor in CargarTodas():
            Campos = self._Campos[Proveedor.Id]
            for Clave, Valor in (
                ("base", Proveedor.BaseUrl),
                ("clave", Proveedor.ApiKey),
                ("modelo", Proveedor.Modelo),
            ):
                Campos[Clave].delete(0, tk.END)
                if Valor:
                    Campos[Clave].insert(0, Valor)
            EsLocal = Proveedor.Tipo == "local"
            Modo = "local" if EsLocal else "api"
            self._Modo[Proveedor.Id].set(Modo)
            self._ModoAnterior[Proveedor.Id] = Modo
            self._Razonamiento[Proveedor.Id].set(
                Proveedor.Razonamiento == "off")
            self._CheckRazonamiento[Proveedor.Id].config(
                state="disabled" if EsLocal else "normal")
            self._PintarEstado(Proveedor.Id)

    def _Estado(self, IdIA):
        Campos = self._Campos[IdIA]
        Base = Campos["base"].get().strip()
        Clave = Campos["clave"].get().strip()
        Modelo = Campos["modelo"].get().strip()
        Etiqueta = "IA local" if self._Modo[IdIA].get() == "local" else "API"
        if Base and Clave and Modelo:
            return True, f"[+] {Etiqueta} lista", ColorExito
        if IdIA == 3 and not (Base or Clave or Modelo):
            return False, "[·] opcional (sin configurar)", Apagado
        Faltan = []
        if not Base:
            Faltan.append("URL")
        if not Clave:
            Faltan.append("clave")
        if not Modelo:
            Faltan.append("modelo")
        return False, f"[!] {Etiqueta}: falta " + ", ".join(Faltan), ColorError

    def _PintarEstado(self, IdIA):
        _Ok, Texto, Color = self._Estado(IdIA)
        self._Estados[IdIA].config(text=Texto, fg=Color)

    def _ConstruirPerfiles(self):
        for Hijo in list(self._MarcoPerfiles.winfo_children()):
            Hijo.destroy()
        self._EtiquetasPerfil = {}
        self._EtiquetaPorNombre = {}
        tk.Label(
            self._MarcoPerfiles, text="Modo de IAs:",
            font=(FuenteLectura, 10, "bold"), fg=ColorTexto, bg=Fondo,
        ).pack(side=tk.LEFT, padx=(0, 8))

        Usadas = set()
        Opciones = []
        for Perfil in PerfilesDisponibles():
            Etiqueta = Perfil["etiqueta"]
            if Etiqueta in Usadas:
                Etiqueta = f'{Etiqueta} ({Perfil["nombre"]})'
            Usadas.add(Etiqueta)
            self._EtiquetasPerfil[Etiqueta] = Perfil["nombre"]
            self._EtiquetaPorNombre[Perfil["nombre"]] = Etiqueta
            Opciones.append(Etiqueta)

        Actual = self._EtiquetaPorNombre.get(
            self.PerfilActual, Opciones[0] if Opciones else "")
        self._PerfilVar = tk.StringVar(master=self.VentanaConfig, value=Actual)
        Menu = tk.OptionMenu(
            self._MarcoPerfiles, self._PerfilVar, *Opciones,
            command=self._CambiarPerfilDesdeMenu,
        )
        Menu.config(
            bg=Panel, fg=Lila, activebackground=Lila, activeforeground=Oscuro,
            bd=0, highlightthickness=1, highlightbackground=Borde,
            font=(FuenteLectura, 9, "bold"), padx=6, pady=2, width=18,
        )
        Menu["menu"].config(
            bg=Panel, fg=ColorTexto, activebackground=Lila,
            activeforeground=Oscuro, font=(FuenteLectura, 9), tearoff=0,
        )
        Menu.pack(side=tk.LEFT)
        self._Boton(
            self._MarcoPerfiles, "+ Nuevo", self._NuevoPerfil,
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _PintarPerfiles(self):
        if self._PerfilVar is None:
            return
        Etiqueta = self._EtiquetaPorNombre.get(self.PerfilActual)
        if Etiqueta:
            self._PerfilVar.set(Etiqueta)

    def _CambiarPerfilDesdeMenu(self, Etiqueta):
        Nombre = self._EtiquetasPerfil.get(Etiqueta)
        if not Nombre or Nombre == self.PerfilActual:
            return
        self._SeleccionarPerfil(Nombre)
        self._PintarPerfiles()

    def _GuardarPerfilActual(self):
        """Escribe las tarjetas en el modo activo, sin avisos ni validación."""
        for IdIA in Ids:
            Campos = self._Campos[IdIA]
            GuardarConfig(
                IdIA,
                BaseUrl=Campos["base"].get().strip(),
                ApiKey=Campos["clave"].get().strip(),
                Modelo=Campos["modelo"].get().strip(),
                Razonamiento=("off" if self._Razonamiento[IdIA].get() else "auto"),
                Tipo=("local" if self._Modo[IdIA].get() == "local" else "api"),
            )

    def _SeleccionarPerfil(self, Nombre):
        if Nombre == self.PerfilActual:
            return
        self._GuardarPerfilActual()
        if not CambiarPerfil(Nombre):
            return
        self.PerfilActual = Nombre
        self._Cargar()
        self._PintarPerfiles()
        if self.AlGuardar:
            try:
                self.AlGuardar()
            except Exception:
                logging.exception("Falló al avisar del cambio de modo de IAs")

    def _NuevoPerfil(self):
        Texto = PedirTextoDialogo(
            self.VentanaConfig, "Nuevo modo",
            "Nombre del nuevo modo:", Inicial="")
        if Texto is None:
            return
        self._GuardarPerfilActual()
        Nombre = CrearPerfil(Texto)
        if not Nombre:
            messagebox.showerror(
                "IAs", "Ese nombre ya existe o no es válido.",
                parent=self.VentanaConfig)
            return
        if not CambiarPerfil(Nombre):
            return
        self.PerfilActual = Nombre
        self._ConstruirPerfiles()
        self._Cargar()
        self._PintarPerfiles()
        if self.AlGuardar:
            try:
                self.AlGuardar()
            except Exception:
                logging.exception("Falló al avisar del nuevo modo de IAs")

    def _Guardar(self):
        self._GuardarPerfilActual()
        for IdIA in Ids:
            self._PintarEstado(IdIA)
        self.BaseDatos.GuardarAjuste(
            "mostrar_config_ias", "1" if self.MostrarAlIniciar.get() else "0")
        if self.AlGuardar:
            try:
                self.AlGuardar()
            except Exception:
                logging.exception("Falló al avisar del cambio de configuración")
        if not Completa():
            if self.Obligatoria:
                messagebox.showwarning(
                    "IAs", "Faltan datos en: " + TextoFaltantes() +
                    ".\n\nCompleta C, R1 y P (R2 es opcional).",
                    parent=self.VentanaConfig,
                )
                return False
        return True

    def _GuardarYCerrar(self):
        if not self._Guardar():
            return
        self.Continuar = True
        self.VentanaConfig.destroy()
        self._QuitarRaizSiToca()

    def _Omitir(self):
        """Entra a la app sin configurar las IAs; el chat avisará al enviar."""
        self.BaseDatos.GuardarAjuste(
            "mostrar_config_ias", "1" if self.MostrarAlIniciar.get() else "0")
        self.Continuar = True
        self.VentanaConfig.destroy()
        self._QuitarRaizSiToca()

    def _Cerrar(self):
        # La X: si ya hay configuración completa, entra a la app; si no, sale.
        if self.Obligatoria:
            self.Continuar = Completa()
        self.VentanaConfig.destroy()
        self._QuitarRaizSiToca()

    def _Salir(self):
        self.Continuar = False
        self.VentanaConfig.destroy()
        self._QuitarRaizSiToca()

    def _QuitarRaizSiToca(self):
        # En el arranque, la ventana de IAs corre sobre una raíz oculta con
        # mainloop(); al cerrarse hay que soltarla para abrir la principal.
        if self.Obligatoria:
            try:
                self.VentanaPadre.quit()
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- acciones
    def _CopiarC(self):
        Origen = self._Campos[1]
        Base = Origen["base"].get().strip()
        Clave = Origen["clave"].get().strip()
        Modelo = Origen["modelo"].get().strip()
        if not (Base and Clave and Modelo):
            messagebox.showinfo("IAs", "Completa primero la IA C (slot 1).",
                                parent=self.VentanaConfig)
            return
        for IdIA in (2, 4):
            Campos = self._Campos[IdIA]
            for Nombre, Valor in (("base", Base), ("clave", Clave), ("modelo", Modelo)):
                Campos[Nombre].delete(0, tk.END)
                Campos[Nombre].insert(0, Valor)
            self._Razonamiento[IdIA].set(self._Razonamiento[1].get())
            self._Modo[IdIA].set(self._Modo[1].get())
            self._ModoAnterior[IdIA] = self._Modo[1].get()
            self._CheckRazonamiento[IdIA].config(
                state="disabled" if self._Modo[IdIA].get() == "local" else "normal")
            self._PintarEstado(IdIA)

    def _BorrarTodo(self):
        Etiqueta = next(
            (P["etiqueta"] for P in PerfilesDisponibles()
             if P["nombre"] == self.PerfilActual),
            self.PerfilActual,
        )
        if not messagebox.askyesno(
            "IAs",
            f"¿Borrar todas las IAs (APIs y modelos) de «{Etiqueta}»?\n\n"
            "Solo se borran las de este modo. No se tocan los prompts, "
            "los cuadernos ni los otros modos.",
            parent=self.VentanaConfig,
        ):
            return
        if not BorrarIAsPerfil(self.PerfilActual):
            return
        for IdIA in Ids:
            for Campo in self._Campos[IdIA].values():
                Campo.delete(0, tk.END)
            self._Razonamiento[IdIA].set(False)
            self._Modo[IdIA].set("api")
            self._ModoAnterior[IdIA] = "api"
            self._CheckRazonamiento[IdIA].config(state="normal")
            self._PintarEstado(IdIA)

    def _AbrirCarpeta(self):
        try:
            CrearEstructura(1)
            AbrirConSistema(CarpetaBase())
        except Exception as E:
            logging.exception("No se pudo abrir la carpeta de IAs")
            messagebox.showerror("IAs", f"No se pudo abrir la carpeta:\n\n{E}",
                                 parent=self.VentanaConfig)

    def _AbrirEditor(self, IdIA):
        from .ias import VentanaIAs
        if self._Editor is None or not self._Editor.Ventana.winfo_exists():
            self._Editor = VentanaIAs(self.VentanaConfig, IdInicial=IdIA)
        self._Editor.Mostrar(IdIA)

    def _AlternarClaves(self):
        Mostrar = "" if self.VerClaves.get() else "•"
        for Campos in self._Campos.values():
            Campos["clave"].config(show=Mostrar)

    def _CambiarModo(self, IdIA):
        """Cambia el slot entre API remota e IA local."""
        Modo = self._Modo[IdIA].get()
        if Modo == self._ModoAnterior.get(IdIA):
            return
        self._ModoAnterior[IdIA] = Modo
        Campos = self._Campos[IdIA]
        # El modelo de una API no sirve para una IA local (y al revés).
        Campos["modelo"].delete(0, tk.END)
        if Modo == "local":
            Base = Campos["base"].get().strip()
            if not Base or not _EsUrlLocal(Base):
                Campos["base"].delete(0, tk.END)
                Campos["base"].insert(0, UrlLocal)
                Campos["clave"].delete(0, tk.END)
                Campos["clave"].insert(0, "ollama")
            self._Razonamiento[IdIA].set(False)
            self._CheckRazonamiento[IdIA].config(state="disabled")
            self._PintarEstado(IdIA)
            self._VerModelos(IdIA)
        else:
            if _EsUrlLocal(Campos["base"].get().strip()):
                Campos["base"].delete(0, tk.END)
                Campos["clave"].delete(0, tk.END)
            self._CheckRazonamiento[IdIA].config(state="normal")
            self._PintarEstado(IdIA)

    # ------------------------------------------------------------- ver modelos
    def _VerModelos(self, IdIA):
        Campos = self._Campos[IdIA]
        Base = Campos["base"].get().strip()
        Clave = Campos["clave"].get().strip()
        Tipo = "local" if self._Modo[IdIA].get() == "local" else "api"
        if not Base or not Clave:
            messagebox.showinfo("IAs", "Escribe la URL del proveedor y la clave primero.",
                                parent=self.VentanaConfig)
            return
        self._Estados[IdIA].config(text="[·] consultando modelos…", fg=Apagado)

        def Tarea():
            try:
                Modelos = ListarModelos(Base, Clave, Tipo)
            except Exception as E:
                logging.exception("No se pudieron listar los modelos de %s", Base)
                self._LlamarSeguro(
                    lambda: self._Estados[IdIA].config(
                        text=f"[!] {str(E)[:70]}", fg=ColorError))
                return
            self._LlamarSeguro(lambda: self._ElegirModelo(IdIA, Modelos))

        threading.Thread(target=Tarea, daemon=True).start()

    def _LlamarSeguro(self, Funcion):
        try:
            if self.VentanaConfig.winfo_exists():
                self.VentanaConfig.after(0, Funcion)
        except (tk.TclError, RuntimeError):
            pass

    def _ElegirModelo(self, IdIA, Modelos):
        if not Modelos:
            messagebox.showinfo("IAs", "El proveedor no devolvió modelos. "
                                       "Escribe el nombre a mano.",
                                parent=self.VentanaConfig)
            self._PintarEstado(IdIA)
            return

        Ventana = tk.Toplevel(self.VentanaConfig)
        Ventana.title("Modelos disponibles")
        Ventana.configure(bg=Fondo)
        Ventana.resizable(False, False)
        Cabecera(Ventana, "modelos").pack(anchor="w", padx=10, pady=(8, 0))
        tk.Label(Ventana, text=f"Modelos de {Roles[IdIA]['clave']}",
                 font=(FuenteLectura, 12, "bold"), fg=Lila, bg=Fondo).pack(pady=(2, 6))

        Marco = tk.Frame(Ventana, bg=Fondo)
        Marco.pack(padx=10, pady=4)
        Lista = tk.Listbox(Marco, height=15, width=58, font=(FuenteMono, 9),
                           bg=Panel, fg=ColorTexto, selectbackground=Lila,
                           selectforeground=Oscuro, highlightthickness=1,
                           highlightbackground=Borde)
        Barra = tk.Scrollbar(Marco, orient="vertical", command=Lista.yview)
        Lista.configure(yscrollcommand=Barra.set)
        Barra.pack(side=tk.RIGHT, fill=tk.Y)
        Lista.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for Modelo in Modelos:
            Lista.insert(tk.END, Modelo)

        def Usar(_Evento=None):
            Seleccion = Lista.curselection()
            if not Seleccion:
                return
            Elegido = Lista.get(Seleccion[0])
            Campo = self._Campos[IdIA]["modelo"]
            Campo.delete(0, tk.END)
            Campo.insert(0, Elegido)
            self._PintarEstado(IdIA)
            Ventana.destroy()

        Lista.bind("<Double-Button-1>", Usar)
        Botones = tk.Frame(Ventana, bg=Fondo)
        Botones.pack(pady=(4, 10))
        self._Boton(Botones, "Usar", Usar, Compacto=False).pack(side=tk.LEFT, padx=4)
        self._Boton(Botones, "Cancelar", Ventana.destroy, Compacto=False).pack(
            side=tk.LEFT, padx=4)
        Ventana.protocol("WM_DELETE_WINDOW", Ventana.destroy)
        Ventana.transient(self.VentanaConfig)
        try:
            Ventana.grab_set()
        except tk.TclError:
            pass

    # ---------------------------------------------------------------- ventana
    def _Centrar(self):
        self.VentanaConfig.update_idletasks()
        Ancho = max(self.VentanaConfig.winfo_reqwidth(), 980)
        Alto = max(self.VentanaConfig.winfo_reqheight(), 640)
        X = (self.VentanaConfig.winfo_screenwidth() - Ancho) // 2
        Y = (self.VentanaConfig.winfo_screenheight() - Alto) // 3
        self.VentanaConfig.geometry(f"{Ancho}x{Alto}+{max(X, 0)}+{max(Y, 0)}")
