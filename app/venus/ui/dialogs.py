import tkinter as tk

from ..config import Apagado, LargoMaxNombre, NombrePredeterminado
from ..text import LimpiarNombre
from ..theme import Cabecera


def PedirNombreDialogo(VentanaPadre, Titulo, Pregunta, Inicial="",
                       TextoAceptar="[ Entrar ]", TextoCancelar="[ Omitir ]"):
    Resultado = {"nombre": None}

    Dialogo = tk.Toplevel(VentanaPadre)
    Dialogo.title(Titulo)
    Dialogo.resizable(False, False)

    def Aceptar(Evento=None):
        Resultado["nombre"] = LimpiarNombre(Campo.get())
        Dialogo.destroy()

    Cabecera(Dialogo, Titulo).pack(pady=(10, 0))
    tk.Label(Dialogo, text=Pregunta).pack(padx=20, pady=(5, 5))
    tk.Label(Dialogo, text=f"(máx. {LargoMaxNombre} letras; vacío = {NombrePredeterminado})",
             fg=Apagado).pack()
    Campo = tk.Entry(Dialogo, width=22)
    Campo.insert(0, Inicial)
    Campo.pack(padx=20, pady=10)
    Campo.bind("<Return>", Aceptar)
    Campo.bind("<Escape>", lambda Evento: Dialogo.destroy())

    MarcoBotones = tk.Frame(Dialogo)
    MarcoBotones.pack(pady=(0, 15))
    tk.Button(MarcoBotones, text=TextoAceptar, command=Aceptar).pack(side=tk.LEFT, padx=5)
    tk.Button(MarcoBotones, text=TextoCancelar, command=Dialogo.destroy).pack(side=tk.LEFT, padx=5)
    Dialogo.protocol("WM_DELETE_WINDOW", Dialogo.destroy)

    Dialogo.update_idletasks()
    X = (Dialogo.winfo_screenwidth() - Dialogo.winfo_reqwidth()) // 2
    Y = (Dialogo.winfo_screenheight() - Dialogo.winfo_reqheight()) // 3
    Dialogo.geometry(f"+{max(X, 0)}+{max(Y, 0)}")
    Campo.focus_force()
    try:
        Dialogo.grab_set()
    except tk.TclError:
        pass
    VentanaPadre.wait_window(Dialogo)
    return Resultado["nombre"]


def PedirTextoDialogo(VentanaPadre, Titulo, Pregunta, Inicial="", LargoMaximo=60,
                      TextoAceptar="[ Guardar ]", TextoCancelar="[ Cancelar ]"):
    """Pide un texto corto (renombrar, etc.). Devuelve el texto o None si se cancela."""
    Resultado = {"texto": None}

    Dialogo = tk.Toplevel(VentanaPadre)
    Dialogo.title(Titulo)
    Dialogo.resizable(False, False)

    def Aceptar(Evento=None):
        Texto = Campo.get().strip()
        if not Texto:
            return
        Resultado["texto"] = Texto[:LargoMaximo]
        Dialogo.destroy()

    Cabecera(Dialogo, Titulo).pack(pady=(10, 0))
    tk.Label(Dialogo, text=Pregunta).pack(padx=20, pady=(5, 5))
    tk.Label(Dialogo, text=f"(máx. {LargoMaximo} caracteres)", fg=Apagado).pack()
    Campo = tk.Entry(Dialogo, width=36)
    Campo.insert(0, Inicial)
    Campo.select_range(0, tk.END)
    Campo.pack(padx=20, pady=10)
    Campo.bind("<Return>", Aceptar)
    Campo.bind("<Escape>", lambda Evento: Dialogo.destroy())

    MarcoBotones = tk.Frame(Dialogo)
    MarcoBotones.pack(pady=(0, 15))
    tk.Button(MarcoBotones, text=TextoAceptar, command=Aceptar).pack(side=tk.LEFT, padx=5)
    tk.Button(MarcoBotones, text=TextoCancelar, command=Dialogo.destroy).pack(side=tk.LEFT, padx=5)
    Dialogo.protocol("WM_DELETE_WINDOW", Dialogo.destroy)

    Dialogo.update_idletasks()
    X = (Dialogo.winfo_screenwidth() - Dialogo.winfo_reqwidth()) // 2
    Y = (Dialogo.winfo_screenheight() - Dialogo.winfo_reqheight()) // 3
    Dialogo.geometry(f"+{max(X, 0)}+{max(Y, 0)}")
    Campo.focus_force()
    try:
        Dialogo.grab_set()
    except tk.TclError:
        pass
    VentanaPadre.wait_window(Dialogo)
    return Resultado["texto"]