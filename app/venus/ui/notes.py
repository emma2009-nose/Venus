import tkinter as tk

from ..theme import Cabecera


class VentanaNotas:
    def __init__(self, VentanaPadre, BaseDatos):
        self.VentanaPadre = VentanaPadre
        self.BaseDatos = BaseDatos
        self.VentanaNotas = None

    def MostrarVentanaNotas(self):
        if self.VentanaNotas is not None and self.VentanaNotas.winfo_exists():
            self.VentanaNotas.lift()
            return
        self.VentanaNotas = tk.Toplevel(self.VentanaPadre)
        self.VentanaNotas.title("Notas")
        self.VentanaNotas.geometry("500x500")
        Cabecera(self.VentanaNotas, "Notas").pack(pady=10)