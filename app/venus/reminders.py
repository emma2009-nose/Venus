import logging
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from .config import RutaArchivoBd
from .database import BaseDatos
from .system import CancelarTarea, EnviarNotificacion, ProgramarTarea
from .times import ArmarAviso


class Recordatorios:
    IntervaloMs = 15000
    MaxIndividuales = 5

    def __init__(self, VentanaPadre, BaseDatos):
        self.VentanaPadre = VentanaPadre
        self.BaseDatos = BaseDatos
        self._TareaProgramada = None

    def Iniciar(self):
        threading.Thread(target=SincronizarTareas, args=(self.BaseDatos,), daemon=True).start()
        self._Revisar()

    def Detener(self):
        if self._TareaProgramada is not None:
            try:
                self.VentanaPadre.after_cancel(self._TareaProgramada)
            except tk.TclError:
                pass
            self._TareaProgramada = None

    def _Revisar(self):
        try:
            Ahora = datetime.now()
            Pendientes = self.BaseDatos.AvisosPendientes(Ahora.strftime("%Y-%m-%d %H:%M"))
            Propios = [(IdAviso, Contenido, FechaHora) for IdAviso, Contenido, FechaHora in Pendientes
                       if self.BaseDatos.ReclamarAviso(IdAviso)]
            for IdAviso, Contenido, FechaHora in Propios[:self.MaxIndividuales]:
                Titulo, Mensaje = ArmarAviso(Contenido, FechaHora, Ahora)
                self._Enviar(Titulo, Mensaje)
            Resto = len(Propios) - self.MaxIndividuales
            if Resto > 0:
                self._Enviar("Venus", f"Además tenías {Resto} recordatorios atrasados en tus notas.")
            if Propios:
                Ids = [IdAviso for IdAviso, _, _ in Propios]
                threading.Thread(target=lambda: [CancelarTarea(I) for I in Ids], daemon=True).start()
        except Exception:
            logging.exception("Error al revisar los recordatorios")
        self._TareaProgramada = self.VentanaPadre.after(self.IntervaloMs, self._Revisar)

    def _Enviar(self, Titulo, Mensaje):
        def Tarea():
            if EnviarNotificacion(Titulo, Mensaje):
                return
            try:
                self.VentanaPadre.after(0, lambda: messagebox.showinfo(Titulo, Mensaje, parent=self.VentanaPadre))
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=Tarea, daemon=True).start()


def SincronizarTareas(BaseDatos):
    try:
        for IdAviso, FechaHora in BaseDatos.AvisosFuturos(datetime.now().strftime("%Y-%m-%d %H:%M")):
            ProgramarTarea(IdAviso, FechaHora)
    except Exception:
        logging.exception("No se pudieron sincronizar los avisos con el sistema")


def ActualizarTareas(IdsViejos, Nuevos):
    for IdAviso in IdsViejos:
        CancelarTarea(IdAviso)
    Resultados = [ProgramarTarea(IdAviso, Momento) for IdAviso, Momento in Nuevos]
    return all(Resultados)


def EjecutarAviso(IdAviso):
    try:
        IdAviso = int(IdAviso)
    except ValueError:
        return
    try:
        BaseDatosObj = BaseDatos(RutaArchivoBd)
        try:
            Fila = BaseDatosObj.ObtenerAviso(IdAviso)
            if Fila and BaseDatosObj.ReclamarAviso(IdAviso):
                Titulo, Mensaje = ArmarAviso(Fila[0], Fila[1])
                if not EnviarNotificacion(Titulo, Mensaje):
                    logging.warning("El sistema no pudo mostrar la notificación del aviso %s", IdAviso)
        finally:
            BaseDatosObj.Cerrar()
    except Exception:
        logging.exception("Falló el aviso %s", IdAviso)
    finally:
        CancelarTarea(IdAviso)