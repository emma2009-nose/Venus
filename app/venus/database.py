import sqlite3
import threading
from datetime import datetime

from .config import RutaArchivoBd


class BaseDatos:
    def __init__(self, RutaBd=RutaArchivoBd):
        self.RutaBaseDatos = RutaBd
        self.RutaBaseDatos.parent.mkdir(parents=True, exist_ok=True)
        self.Candado = threading.RLock()
        self.Conexion = sqlite3.connect(self.RutaBaseDatos, check_same_thread=False)
        self.Conexion.execute("PRAGMA foreign_keys = ON")
        self._CrearTablas()

    def _Escribir(self, Sql, Params=()):
        with self.Candado:
            CursorBd = self.Conexion.execute(Sql, Params)
            self.Conexion.commit()
            return CursorBd.lastrowid

    def _Leer(self, Sql, Params=()):
        with self.Candado:
            return self.Conexion.execute(Sql, Params).fetchall()

    def _CrearTablas(self):
        self._Escribir("""
            CREATE TABLE IF NOT EXISTS notas_calendario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                contenido TEXT NOT NULL,
                creado TEXT NOT NULL
            )
        """)
        self._Escribir("""
            CREATE TABLE IF NOT EXISTS conversaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                contenido TEXT NOT NULL,
                creado TEXT NOT NULL
            )
        """)
        self._Escribir("""
            CREATE TABLE IF NOT EXISTS avisos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nota_id INTEGER NOT NULL REFERENCES notas_calendario(id) ON DELETE CASCADE,
                fecha_hora TEXT NOT NULL,
                enviado INTEGER NOT NULL DEFAULT 0
            )
        """)
        self._Escribir("""
            CREATE TABLE IF NOT EXISTS ajustes (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
        """)

    def LeerAjuste(self, Clave):
        Filas = self._Leer("SELECT valor FROM ajustes WHERE clave = ?", (Clave,))
        return Filas[0][0] if Filas else None

    def GuardarAjuste(self, Clave, Valor):
        self._Escribir(
            "INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (Clave, Valor),
        )

    @staticmethod
    def _Ahora():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def GuardarNota(self, Fecha, Contenido):
        return self._Escribir(
            "INSERT INTO notas_calendario (fecha, contenido, creado) VALUES (?, ?, ?)",
            (Fecha, Contenido, self._Ahora()),
        )

    def ObtenerNotasPorFecha(self, Fecha):
        return self._Leer(
            "SELECT id, contenido, creado FROM notas_calendario WHERE fecha = ? ORDER BY id",
            (Fecha,),
        )

    def ActualizarNota(self, IdNota, Contenido):
        self._Escribir("UPDATE notas_calendario SET contenido = ? WHERE id = ?", (Contenido, IdNota))

    def EliminarNota(self, IdNota):
        self._Escribir("DELETE FROM notas_calendario WHERE id = ?", (IdNota,))

    def ReemplazarAvisos(self, IdNota, Momentos):
        with self.Candado:
            Viejos = [F[0] for F in self.Conexion.execute(
                "SELECT id FROM avisos WHERE nota_id = ?", (IdNota,)).fetchall()]
            self.Conexion.execute("DELETE FROM avisos WHERE nota_id = ?", (IdNota,))
            Nuevos = []
            for Momento in Momentos:
                CursorBd = self.Conexion.execute(
                    "INSERT INTO avisos (nota_id, fecha_hora, enviado) VALUES (?, ?, 0)",
                    (IdNota, Momento),
                )
                Nuevos.append((CursorBd.lastrowid, Momento))
            self.Conexion.commit()
        return Viejos, Nuevos

    def AvisosFuturos(self, Ahora):
        return self._Leer(
            "SELECT id, fecha_hora FROM avisos WHERE enviado = 0 AND fecha_hora > ? ORDER BY fecha_hora",
            (Ahora,),
        )

    def ObtenerAviso(self, IdAviso):
        Filas = self._Leer(
            "SELECT n.contenido, a.fecha_hora FROM avisos a "
            "JOIN notas_calendario n ON n.id = a.nota_id WHERE a.id = ?",
            (IdAviso,),
        )
        return Filas[0] if Filas else None

    def ReclamarAviso(self, IdAviso):
        with self.Candado:
            CursorBd = self.Conexion.execute(
                "UPDATE avisos SET enviado = 1 WHERE id = ? AND enviado = 0", (IdAviso,)
            )
            self.Conexion.commit()
            return CursorBd.rowcount == 1

    def AvisosPendientes(self, Ahora):
        return self._Leer(
            "SELECT a.id, n.contenido, a.fecha_hora FROM avisos a "
            "JOIN notas_calendario n ON n.id = a.nota_id "
            "WHERE a.enviado = 0 AND a.fecha_hora <= ? ORDER BY a.fecha_hora",
            (Ahora,),
        )

    def MarcarAvisoEnviado(self, IdAviso):
        self._Escribir("UPDATE avisos SET enviado = 1 WHERE id = ?", (IdAviso,))

    def GuardarConversacion(self, Titulo, Contenido):
        return self._Escribir(
            "INSERT INTO conversaciones (titulo, contenido, creado) VALUES (?, ?, ?)",
            (Titulo, Contenido, self._Ahora()),
        )

    def ActualizarConversacion(self, IdConv, Contenido):
        self._Escribir(
            "UPDATE conversaciones SET contenido = ? WHERE id = ?", (Contenido, IdConv))

    def ListarConversaciones(self):
        return self._Leer("SELECT id, titulo, creado FROM conversaciones ORDER BY id DESC")

    def ObtenerConversacion(self, IdConv):
        Filas = self._Leer("SELECT contenido FROM conversaciones WHERE id = ?", (IdConv,))
        return Filas[0][0] if Filas else None

    def RenombrarConversacion(self, IdConv, Titulo):
        self._Escribir("UPDATE conversaciones SET titulo = ? WHERE id = ?", (Titulo, IdConv))

    def EliminarConversacion(self, IdConv):
        self._Escribir("DELETE FROM conversaciones WHERE id = ?", (IdConv,))

    def Cerrar(self):
        with self.Candado:
            self.Conexion.commit()
            self.Conexion.close()