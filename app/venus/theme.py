import logging
import re
import sys
import tkinter as tk
from tkinter import font as tkfont

from . import state
from .config import Paletas, FuenteTexto, TamanoFuente, TemaActivo

# Borde de las ventanas: color del tema activo, algo fino.
BordeVentanaPx = 2
_TemaActual = TemaActivo

# Opciones de color que se revisan al cambiar de tema en vivo.
_OpcionesColor = (
    "background", "foreground", "highlightbackground", "highlightcolor",
    "activebackground", "activeforeground", "selectbackground", "selectforeground",
    "insertbackground", "selectcolor", "disabledforeground", "disabledbackground",
    "troughcolor",
)


def TemaEnUso():
    return _TemaActual


def _PaletaActual():
    return Paletas.get(_TemaActual, Paletas["oscuro"])


def AplicarTema(Raiz, Paleta=None):
    P = Paleta if Paleta is not None else _PaletaActual()
    Raiz.configure(bg=P["fondo"])
    Raiz.configure(highlightthickness=BordeVentanaPx,
                   highlightbackground=P["colorBordeVentana"],
                   highlightcolor=P["colorBordeVentana"])
    AgregarOpcion = Raiz.option_add
    AgregarOpcion("*Toplevel.highlightThickness", BordeVentanaPx)
    AgregarOpcion("*Toplevel.highlightBackground", P["colorBordeVentana"])
    AgregarOpcion("*Toplevel.highlightColor", P["colorBordeVentana"])
    AgregarOpcion("*Toplevel.relief", "flat")
    AgregarOpcion("*Toplevel.borderWidth", 0)
    AgregarOpcion("*Font", f"{{{FuenteTexto}}} {TamanoFuente}")
    AgregarOpcion("*Background", P["fondo"])
    AgregarOpcion("*Foreground", P["colorTexto"])
    AgregarOpcion("*Button.Background", P["panel"])
    AgregarOpcion("*Button.Foreground", P["lila"])
    AgregarOpcion("*Button.activeBackground", P["lila"])
    AgregarOpcion("*Button.activeForeground", P["oscuro"])
    AgregarOpcion("*Button.disabledForeground", P["desactivado"])
    AgregarOpcion("*Button.relief", "flat")
    AgregarOpcion("*Button.borderWidth", 0)
    AgregarOpcion("*Button.highlightThickness", 1)
    AgregarOpcion("*Button.highlightBackground", P["borde"])
    AgregarOpcion("*Button.highlightColor", P["lila"])
    AgregarOpcion("*Button.padX", 10)
    AgregarOpcion("*Button.padY", 3)
    AgregarOpcion("*Button.cursor", "hand2")
    for TipoWidget in ("Entry", "Text", "Listbox"):
        AgregarOpcion(f"*{TipoWidget}.Background", P["panel"])
        AgregarOpcion(f"*{TipoWidget}.Foreground", P["colorTexto"])
        AgregarOpcion(f"*{TipoWidget}.selectBackground", P["colorSeleccion"])
        AgregarOpcion(f"*{TipoWidget}.selectForeground", P["colorTextoSeleccion"])
        AgregarOpcion(f"*{TipoWidget}.relief", "flat")
        AgregarOpcion(f"*{TipoWidget}.highlightThickness", 1)
        AgregarOpcion(f"*{TipoWidget}.highlightBackground", P["borde"])
        AgregarOpcion(f"*{TipoWidget}.highlightColor", P["rosa"])
    AgregarOpcion("*Entry.insertBackground", P["rosa"])
    AgregarOpcion("*Text.insertBackground", P["rosa"])


def ElegirFuenteMono():
    try:
        Familias = {Familia.lower(): Familia for Familia in tkfont.families()}
        for Candidata in ("Cascadia Mono", "Consolas", "DejaVu Sans Mono",
                          "Liberation Mono", "Courier New"):
            if Candidata.lower() in Familias:
                state.FuenteMono = Familias[Candidata.lower()]
                return
        state.FuenteMono = tkfont.nametofont("TkFixedFont").Actual("family")
    except tk.TclError:
        logging.exception("No se pudo elegir una fuente monoespaciada")


def Cabecera(VentanaPadre, Titulo):
    Marco = tk.Frame(VentanaPadre)
    Ruta = re.sub(r"\W+", "_", Titulo.lower()).strip("_") or "venus"
    tk.Label(
        Marco,
        text=f"┌──({state.NombreUsuario.replace(' ', '_')}@gato)-[~/{Ruta}]\n└─$",
        justify=tk.LEFT, font=(state.FuenteMono, 11, "bold"),
        fg=_PaletaActual()["lila"],
    ).pack(side=tk.LEFT, padx=8)
    return Marco


def _Mezclar(ColorInicial, ColorFinal, Proporcion):
    CanalesInicial = [int(ColorInicial[I:I + 2], 16) for I in (1, 3, 5)]
    CanalesFinal = [int(ColorFinal[I:I + 2], 16) for I in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(
        round(VI + (VF - VI) * Proporcion) for VI, VF in zip(CanalesInicial, CanalesFinal)
    )


def _MapaColores(Viejo, Nuevo):
    """Traduce cada color de la paleta vieja a su equivalente en la nueva."""
    Mapa = {}
    for Clave, ValorViejo in Viejo.items():
        if Clave == "nombre":
            continue
        ValorNuevo = Nuevo.get(Clave)
        if ValorNuevo and ValorNuevo.lower() != ValorViejo.lower():
            Mapa[ValorViejo.lower()] = ValorNuevo
    return Mapa


def _RetematizarWidget(Widget, Mapa):
    try:
        Opciones = Widget.keys()
    except Exception:
        return
    for Opcion in _OpcionesColor:
        if Opcion not in Opciones:
            continue
        try:
            Actual = str(Widget.cget(Opcion)).lower()
        except Exception:
            continue
        Nuevo = Mapa.get(Actual)
        if not Nuevo:
            continue
        try:
            Widget.configure(**{Opcion: Nuevo})
        except tk.TclError:
            pass


def _RetematizarArbol(Widget, Mapa):
    _RetematizarWidget(Widget, Mapa)
    try:
        Hijos = Widget.winfo_children()
    except tk.TclError:
        return
    for Hijo in Hijos:
        _RetematizarArbol(Hijo, Mapa)


def _ActualizarConstantes(Viejo, Nuevo):
    """Actualiza los colores importados en todos los modulos de la app."""
    for Clave, ValorViejo in Viejo.items():
        if Clave == "nombre":
            continue
        ValorNuevo = Nuevo.get(Clave)
        if not ValorNuevo or ValorNuevo == ValorViejo:
            continue
        # Las claves de la paleta están en minúscula ("fondo", "colorTexto"...);
        # las variables del módulo config ya están en PascalCase (Fondo,
        # ColorTexto...). Se capitaliza la primera letra para encontrarlas.
        NombreVariable = Clave[:1].upper() + Clave[1:]
        for NombreModulo, Modulo in list(sys.modules.items()):
            if Modulo is None or not NombreModulo.startswith("venus"):
                continue
            if getattr(Modulo, NombreVariable, None) == ValorViejo:
                try:
                    setattr(Modulo, NombreVariable, ValorNuevo)
                except Exception:
                    pass


def _RepintarRotulo(Raiz, Paleta):
    Rotulo = getattr(Raiz, "Rotulo", None)
    if Rotulo is None:
        return
    try:
        Etiquetas = sorted(T for T in Rotulo.tag_names() if T.startswith("rotulo"))
        Total = len(Etiquetas)
        for Indice, Etiqueta in enumerate(Etiquetas):
            Proporcion = Indice / (Total - 1) if Total > 1 else 0
            Rotulo.tag_config(Etiqueta, foreground=_Mezclar(
                Paleta["degradadoInicio"], Paleta["degradadoFin"], Proporcion))
        Rotulo.configure(bg=Paleta["fondo"])
    except tk.TclError:
        pass


def CambiarTemaEnVivo(Raiz, NombreNuevo):
    """Aplica otra paleta a toda la app sin reiniciar."""
    global _TemaActual
    if NombreNuevo not in Paletas or NombreNuevo == _TemaActual:
        return False
    Viejo = _PaletaActual()
    Nueva = Paletas[NombreNuevo]
    _ActualizarConstantes(Viejo, Nueva)
    _TemaActual = NombreNuevo
    try:
        from . import config as configMod
        configMod.TemaActivo = NombreNuevo
    except Exception:
        pass
    AplicarTema(Raiz)
    # Las ventanas secundarias se cierran y se reabren con la paleta nueva.
    for Hijo in list(Raiz.winfo_children()):
        if isinstance(Hijo, tk.Toplevel):
            Cerrar = getattr(Hijo, "cerrarGuardando", None)
            if callable(Cerrar):
                try:
                    Cerrar()        # el chat guarda la conversacion antes de irse
                    continue
                except Exception:
                    logging.exception("No se pudo guardar el estado de una ventana")
            try:
                Hijo.destroy()
            except tk.TclError:
                pass
    Reconstruir = getattr(Raiz, "ReconstruirUI", None)
    if callable(Reconstruir):
        Reconstruir()
    else:
        _RetematizarArbol(Raiz, _MapaColores(Viejo, Nueva))
        _RepintarRotulo(Raiz, Nueva)
    return True


_LetrasRotulo = {
    "V": ["██╗   ██╗", "██║   ██║", "██║   ██║", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚═══╝  "],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
    "U": ["██╗   ██╗", "██║   ██║", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "S": ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
}


def TextoRotulo(Palabra="VENUS"):
    return [
        "".join(_LetrasRotulo[Letra][IndiceFila] for Letra in Palabra)
        for IndiceFila in range(6)
    ]


def MarcoAscii(Padre, Titulo, AnchoPx, AltoPx, Color):
    Fuente = (state.FuenteMono, 11, "bold")
    Medidor = tkfont.Font(family=state.FuenteMono, size=11, weight="bold")
    Cw = max(1, Medidor.measure("═"))
    Lh = max(1, Medidor.metrics("linespace"))
    Columnas = max(len(Titulo) + 9, -(-AnchoPx // Cw) + 2)
    Filas = max(1, -(-AltoPx // Lh))
    Cabeza = "╔═[ " + Titulo + " ]" + "═" * (Columnas - len(Titulo) - 7) + "╗"
    Pie = "╚" + "═" * (Columnas - 2) + "╝"
    Marco = tk.Frame(Padre)
    tk.Label(Marco, text=Cabeza, font=Fuente, fg=Color).grid(row=0, column=0, columnspan=3)
    Lateral = "\n".join(["║"] * Filas)
    tk.Label(Marco, text=Lateral, font=Fuente, fg=Color).grid(row=1, column=0)
    Interior = tk.Frame(Marco)
    Interior.grid(row=1, column=1, sticky="nsew")
    tk.Label(Marco, text=Lateral, font=Fuente, fg=Color).grid(row=1, column=2)
    tk.Label(Marco, text=Pie, font=Fuente, fg=Color).grid(row=2, column=0, columnspan=3)
    Marco.grid_columnconfigure(1, minsize=(Columnas - 2) * Cw)
    Marco.grid_rowconfigure(1, minsize=Filas * Lh)
    return Marco, Interior
