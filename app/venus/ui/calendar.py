# ============================================================================
# CALENDARIO DESACTIVADO (2026-11-06)
#
# Esta ventana ya NO se abre: en venus/ui/main.py estan comentados su
# importacion, su instancia y el boton [ Calendario ]. El codigo se conserva
# tal cual (sin tocar) para poder reactivarlo.
#
# Para volver a activarlo: descomentar esas tres lineas de main.py y restaurar
# en main.py la geometria "520x470" y las posiciones antiguas que estan
# anotadas en el comentario de posicionesPrincipal.
#
# La base de datos y los recordatorios siguen funcionando; el resto de la app
# no depende de este modulo.
# ============================================================================
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from tkcalendar import Calendar

from ..config import (
    Apagado, Botones, ColorTexto, Desactivado, Fondo, FuenteTexto, Lila,
    Oscuro, Panel, Rosa, TamanoFuente,
)
from ..reminders import ActualizarTareas
from ..theme import Cabecera
from ..times import MomentosDeNota


class VentanaCalendario:
    def __init__(self, VentanaPadre, BaseDatos):
        self.VentanaPadre = VentanaPadre
        self.BaseDatos = BaseDatos
        self.VentanaCalendario = None
        self.VentanaNotasDia = None

    def MostrarVentanaCalendario(self):
        if self.VentanaCalendario is not None and self.VentanaCalendario.winfo_exists():
            self.VentanaCalendario.lift()
            return

        self.VentanaCalendario = tk.Toplevel(self.VentanaPadre)
        self.VentanaCalendario.title("Calendario")
        self.VentanaCalendario.resizable(False, False)

        Cabecera(self.VentanaCalendario, "Calendario").grid(row=0, column=0, columnspan=2, pady=(12, 0))

        self.WidgetCalendario = Calendar(
            self.VentanaCalendario, selectmode="day", date_pattern="dd/mm/yyyy",
            font=(FuenteTexto, TamanoFuente), background=Panel, foreground=ColorTexto,
            bordercolor=Rosa, headersbackground=Botones, headersforeground=Oscuro,
            selectbackground=Rosa, selectforeground=Oscuro,
            normalbackground=Fondo, normalforeground=ColorTexto,
            weekendbackground=Panel, weekendforeground=Lila,
            othermonthbackground=Fondo, othermonthforeground=Desactivado,
            othermonthwebackground=Fondo, othermonthweforeground=Desactivado,
        )
        self.WidgetCalendario.grid(row=1, column=0, columnspan=2, padx=20, pady=20)

        self.BotonSeleccionarFecha = tk.Button(self.VentanaCalendario, text="[ Seleccionar Fecha ]",
                                              command=self.AbrirNotasDelDia)
        self.BotonSeleccionarFecha.grid(row=2, column=0, pady=10, padx=10)

        self.BotonCerrarCalendario = tk.Button(self.VentanaCalendario, text="[ Cerrar ]",
                                              command=self.VentanaCalendario.destroy)
        self.BotonCerrarCalendario.grid(row=2, column=1, pady=10, padx=10)

    def AbrirNotasDelDia(self):
        if self.VentanaNotasDia is not None and self.VentanaNotasDia.winfo_exists():
            self.VentanaNotasDia.lift()
            messagebox.showinfo("Notas", "Ya hay una nota abierta. Ciérrala antes de abrir otra.",
                                parent=self.VentanaNotasDia)
            return

        self.FechaActual = self.WidgetCalendario.get_date()
        self.VentanaNotasDia = tk.Toplevel(self.VentanaCalendario)
        self.VentanaNotasDia.title(f"Notas - {self.FechaActual}")
        self.VentanaNotasDia.resizable(False, False)

        Cabecera(self.VentanaNotasDia, f"Notas {self.FechaActual}").grid(
            row=0, column=0, columnspan=3, pady=(10, 0))

        tk.Label(
            self.VentanaNotasDia,
            text="Para que Venus te avise, escribe la hora entre paréntesis:\n(15:30)",
            justify=tk.LEFT, fg=Apagado, wraplength=700,
        ).grid(row=1, column=0, columnspan=3, pady=(10, 0), padx=10, sticky="w")

        self.CajaTextoNota = scrolledtext.ScrolledText(self.VentanaNotasDia, width=40, height=8)
        self.CajaTextoNota.grid(row=2, column=0, columnspan=3, pady=10, padx=10)

        NotasGuardadas = self.BaseDatos.ObtenerNotasPorFecha(self.FechaActual)
        if NotasGuardadas:
            self.IdNotaActual = NotasGuardadas[-1][0]
            self.CajaTextoNota.insert("1.0", NotasGuardadas[-1][1])
        else:
            self.IdNotaActual = None

        self.MarcoBotonesNota = tk.Frame(self.VentanaNotasDia)
        self.MarcoBotonesNota.configure(width=200, height=150)
        self.MarcoBotonesNota.grid(row=3, column=0, columnspan=3, pady=20)

        tk.Button(self.MarcoBotonesNota, text="[ Abrir .txt ]",
                  command=self.AbrirTxtEnNota).grid(row=0, column=0, pady=5, padx=10)
        tk.Button(self.MarcoBotonesNota, text="[ Exportar .txt ]",
                  command=self.ExportarNotaTxt).grid(row=0, column=1, pady=5, padx=10)
        tk.Button(self.MarcoBotonesNota, text="[ Guardar ]",
                  command=self.GuardarNotaEnBaseDatos).grid(row=1, column=0, columnspan=2, pady=5, padx=10)

    def AbrirTxtEnNota(self):
        Ruta = filedialog.askopenfilename(filetypes=[("Texto", "*.txt")])
        if not Ruta:
            return
        try:
            with open(Ruta, "r", encoding="utf-8") as ArchivoAbierto:
                Contenido = ArchivoAbierto.read()
        except Exception as E:
            logging.exception("No se pudo abrir %s", Ruta)
            messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{E}", parent=self.VentanaNotasDia)
            return
        self.CajaTextoNota.delete("1.0", "end")
        self.CajaTextoNota.insert("1.0", Contenido)

    def ExportarNotaTxt(self):
        Ruta = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Texto", "*.txt")])
        if not Ruta:
            return
        try:
            with open(Ruta, "w", encoding="utf-8") as ArchivoDestino:
                ArchivoDestino.write(self.CajaTextoNota.get("1.0", "end-1c"))
        except Exception as E:
            logging.exception("No se pudo guardar %s", Ruta)
            messagebox.showerror("Error", f"No se pudo guardar el archivo:\n{E}", parent=self.VentanaNotasDia)

    def GuardarNotaEnBaseDatos(self):
        Contenido = self.CajaTextoNota.get("1.0", "end-1c").strip()
        if not Contenido:
            messagebox.showinfo("Notas", "No hay nada que guardar.", parent=self.VentanaNotasDia)
            return

        Futuros, Pasados = MomentosDeNota(self.FechaActual, Contenido)
        try:
            if self.IdNotaActual is None:
                self.IdNotaActual = self.BaseDatos.GuardarNota(self.FechaActual, Contenido)
            else:
                self.BaseDatos.ActualizarNota(self.IdNotaActual, Contenido)
            Viejos, Nuevos = self.BaseDatos.ReemplazarAvisos(self.IdNotaActual, Futuros)
        except Exception as E:
            logging.exception("No se pudo guardar la nota del %s", self.FechaActual)
            messagebox.showerror("Error", f"No se pudo guardar la nota:\n{E}", parent=self.VentanaNotasDia)
            return

        self.VentanaNotasDia.title(f"Notas - {self.FechaActual} (guardado)")
        self.VentanaNotasDia.config(cursor="watch")
        self.VentanaNotasDia.update_idletasks()
        try:
            EnSistema = ActualizarTareas(Viejos, Nuevos)
        finally:
            self.VentanaNotasDia.config(cursor="")

        Mensaje = "Nota guardada en Venus."
        if Futuros:
            Horas = ", ".join(M[-5:] for M in Futuros)
            Mensaje += f"\n\nTe avisaré el {self.FechaActual} a las: {Horas}."
            if EnSistema:
                Mensaje += "\nSonará aunque Venus esté cerrada (el computador debe estar encendido)."
            else:
                Mensaje += "\nNo pude programarlo en el sistema, así que Venus debe estar abierta a esa hora."
        if Pasados:
            Horas = ", ".join(M[-5:] for M in Pasados)
            Mensaje += f"\n\nEstas horas ya pasaron y no se programaron: {Horas}."
        messagebox.showinfo("Notas", Mensaje, parent=self.VentanaNotasDia)