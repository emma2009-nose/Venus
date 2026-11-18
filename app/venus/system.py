import base64
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from .config import DirDatos, SinVentana
from .text import LimpiarComando

_Wine = None


def EsWine():
    global _Wine
    if _Wine is None:
        _Wine = False
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.WinDLL("ntdll").wine_get_version
                _Wine = True
            except (OSError, AttributeError):
                pass
    return _Wine


def RutaUnix(RutaWindows):
    try:
        Resultado = subprocess.run(
            ["winepath", "-u", str(RutaWindows)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=15, creationflags=SinVentana,
        )
        return Resultado.stdout.strip() or None
    except Exception:
        logging.exception("winepath falló con %s", RutaWindows)
        return None


def _Ejecutar(Comando, Entorno=None, TiempoLimite=30):
    ArgumentosExtra = {"creationflags": SinVentana} if sys.platform.startswith("win") else {}
    try:
        Resultado = subprocess.run(
            Comando, env=Entorno, capture_output=True,
            stdin=subprocess.DEVNULL, timeout=TiempoLimite, **ArgumentosExtra,
        )
    except Exception:
        logging.exception("No se pudo ejecutar %s", Comando[0])
        return False
    logging.info("Ejecutado %s -> código %s", Comando[:4], Resultado.returncode)
    if Resultado.returncode != 0:
        logging.warning("%s terminó con error: %s", Comando[0],
                        (Resultado.stderr or b"").decode("utf-8", "replace").strip()[:300])
    return Resultado.returncode == 0


def EjecutarUnix(Argumentos, Esperar=True, TiempoLimite=30):
    Comando = ["cmd", "/c", "start", "/unix"] + (["/wait"] if Esperar else []) + list(Argumentos)
    return _Ejecutar(Comando, TiempoLimite=TiempoLimite)


def LanzarUnix(Argumentos):
    return EjecutarUnix(Argumentos, Esperar=False)


# ---------------- Internet ----------------

def HayInternet(TiempoLimite=2):
    # Primero el host del proveedor de P (si ya está configurado) y luego
    # destinos genéricos. Así no depende de un proveedor concreto.
    Destinos = []
    try:
        from urllib.parse import urlparse
        from ia.codigo.proveedores import LeerConfig
        Url = urlparse(LeerConfig(4).BaseUrl)
        if Url.hostname:
            Destinos.append((Url.hostname, Url.port or 443))
    except Exception:
        logging.exception("No se pudo leer el proveedor de la IA principal")
    Destinos += [("1.1.1.1", 443), ("8.8.8.8", 443)]
    for Destino in Destinos:
        try:
            with socket.create_connection(Destino, timeout=TiempoLimite):
                return True
        except OSError:
            continue
    return False


# ---------------- Abrir archivos ----------------

_UltimaApertura = {}


def _PrepararParaAbrir(Ruta):
    Ruta = Path(Ruta)
    CarpetaEmpaquetada = getattr(sys, "_MEIPASS", None)
    EnTemporal = bool(CarpetaEmpaquetada) and str(Ruta).startswith(str(CarpetaEmpaquetada))
    if EsWine():
        CarpetaPersonal = os.environ.get("HOME")
        Destino = Path("Z:/") / (CarpetaPersonal.strip("/") + "/Venus_abiertos") if CarpetaPersonal else DirDatos / "abiertos"
    elif EnTemporal:
        Destino = DirDatos / "abiertos"
    else:
        return Ruta
    Destino.mkdir(parents=True, exist_ok=True)
    Copia = Destino / Ruta.name
    Copia.write_bytes(Ruta.read_bytes())
    return Copia


def AbrirConSistema(Ruta):
    Ahora = time.time()
    if Ahora - _UltimaApertura.get(str(Ruta), 0) < 3:
        return
    _UltimaApertura[str(Ruta)] = Ahora
    Ruta = _PrepararParaAbrir(Ruta)
    if EsWine():
        RutaLinux = RutaUnix(Ruta)
        if RutaLinux:
            for Programa in (["/usr/bin/xdg-open"], ["/usr/bin/gio", "open"]):
                if Path("Z:" + Programa[0]).exists() and EjecutarUnix(Programa + [RutaLinux], Esperar=False, TiempoLimite=15):
                    return
            for Programa in ("/usr/bin/libreoffice", "/usr/bin/soffice"):
                if Path("Z:" + Programa).exists() and LanzarUnix([Programa, "--writer", RutaLinux]):
                    return
        raise OSError("No se encontró una aplicación de Linux para abrir el archivo.")
    if sys.platform.startswith("win"):
        os.startfile(str(Ruta))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(Ruta)])
    else:
        Env = dict(os.environ, SAL_USE_VCLPLUGIN="gen")
        if Ruta.suffix.lower() in (".docx", ".doc", ".odt"):
            for Programa in ("libreoffice", "soffice"):
                if shutil.which(Programa):
                    subprocess.Popen([Programa, "--writer", str(Ruta)],
                                     env=Env, start_new_session=True)
                    return
        subprocess.Popen(["xdg-open", str(Ruta)], env=Env, start_new_session=True)


# ---------------- Notificaciones ----------------

_GuionNotificacionWindows = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$t = [System.Security.SecurityElement]::Escape($env:VENUS_TITULO)
$m = [System.Security.SecurityElement]::Escape($env:VENUS_MENSAJE)
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$t</text><text>$m</text></binding></visual></toast>")
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$id = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id).Show($toast)
"""

_GuionGloboWindows = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.BalloonTipTitle = $env:VENUS_TITULO
$n.BalloonTipText = $env:VENUS_MENSAJE
$n.Visible = $true
$n.ShowBalloonTip(10000)
Start-Sleep -Seconds 8
$n.Dispose()
"""


def _Powershell(Guion, Entorno, TiempoLimite=20):
    Codificado = base64.b64encode(Guion.encode("utf-16-le")).decode("ascii")
    return _Ejecutar(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-WindowStyle", "Hidden", "-EncodedCommand", Codificado],
        Entorno=Entorno, TiempoLimite=TiempoLimite,
    )


def EnviarNotificacion(Titulo, Mensaje):
    try:
        if EsWine():
            if not Path("Z:/usr/bin/notify-send").exists():
                return False
            return EjecutarUnix(["/usr/bin/notify-send", "-a", "Venus",
                                 LimpiarComando(Titulo), LimpiarComando(Mensaje)])
        Entorno = dict(os.environ, VENUS_TITULO=Titulo, VENUS_MENSAJE=Mensaje)
        if sys.platform.startswith("win"):
            return (_Powershell(_GuionNotificacionWindows, Entorno)
                    or _Powershell(_GuionGloboWindows, Entorno, TiempoLimite=25))
        if sys.platform == "darwin":
            Comando = ["osascript",
                       "-e", "on run argv",
                       "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                       "-e", "end run",
                       Titulo, Mensaje]
        else:
            if not shutil.which("notify-send"):
                return False
            Comando = ["notify-send", "-a", "Venus", Titulo, Mensaje]
        return _Ejecutar(Comando, Entorno=Entorno, TiempoLimite=20)
    except Exception:
        logging.exception("No se pudo enviar la notificación del sistema")
        return False


# ---------------- Tareas programadas ----------------

NombreTarea = "venus-aviso-{}"

_GuionTareaWindows = r"""
$ErrorActionPreference = 'Stop'
$a = New-ScheduledTaskAction -Execute $env:VENUS_PROGRAMA -Argument $env:VENUS_ARGS
$t = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($env:VENUS_CUANDO, 'yyyy-MM-dd HH:mm', [Globalization.CultureInfo]::InvariantCulture))
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $env:VENUS_TAREA -TaskPath '\Venus\' -Action $a -Trigger $t -Settings $s -Force | Out-Null
"""


def _ComandoAviso(IdAviso):
    if getattr(sys, "frozen", False):
        return sys.executable, ["--aviso", str(IdAviso)]
    Programa = Path(sys.executable)
    if sys.platform.startswith("win") and Programa.with_name("pythonw.exe").exists():
        Programa = Programa.with_name("pythonw.exe")
    return str(Programa), [str(Path(sys.argv[0]).resolve()), "--aviso", str(IdAviso)]


def _CarpetaSystemdUsuario():
    CarpetaBase = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(CarpetaBase) / "systemd" / "user"


def _ArgumentoSystemd(Texto):
    return '"' + Texto.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def _EscribirUnidades(Carpeta, Nombre, ComandoInicio, FechaHora, Entorno=()):
    Carpeta.mkdir(parents=True, exist_ok=True)
    LineasEntorno = "".join(f"Environment={_ArgumentoSystemd(E)}\n" for E in Entorno)
    Servicio = ("[Unit]\nDescription=Aviso de Venus\n\n"
                f"[Service]\nType=oneshot\n{LineasEntorno}ExecStart={ComandoInicio}\n")
    Temporizador = ("[Unit]\nDescription=Aviso de Venus\n\n"
                    f"[Timer]\nOnCalendar={FechaHora}:00\nPersistent=true\nAccuracySec=1s\n"
                    f"Unit={Nombre}.service\n\n[Install]\nWantedBy=timers.target\n")
    for Ext, Texto in (("service", Servicio), ("timer", Temporizador)):
        with open(Carpeta / f"{Nombre}.{Ext}", "w", encoding="utf-8", newline="\n") as F:
            F.write(Texto)


def _CarpetaSystemdWine():
    CarpetaPersonal = os.environ.get("HOME")
    if not CarpetaPersonal or not Path("Z:/usr/bin/systemctl").exists():
        return None
    CarpetaBase = os.environ.get("XDG_CONFIG_HOME") or f"{CarpetaPersonal}/.config"
    return Path("Z:/") / (CarpetaBase.strip("/") + "/systemd/user")


def _ProgramarWine(Nombre, Programa, Args, FechaHora):
    Carpeta = _CarpetaSystemdWine()
    RutaCLinux = RutaUnix("C:\\")
    if Carpeta is None or not RutaCLinux:
        return False
    Prefijo = os.environ.get("WINEPREFIX") or RutaCLinux.rstrip("/").rsplit("/", 1)[0]
    Partes = ["/usr/bin/env", "wine"]
    for Argumento in [Programa, *Args]:
        if re.fullmatch(r"--\w+|\d+", Argumento):
            Partes.append(Argumento)
        else:
            RutaConvertida = RutaUnix(Argumento)
            if not RutaConvertida:
                return False
            Partes.append(RutaConvertida)
    ComandoInicio = " ".join(_ArgumentoSystemd(P) for P in Partes)
    _EscribirUnidades(Carpeta, Nombre, ComandoInicio, FechaHora,
                      Entorno=(f"WINEPREFIX={Prefijo}", "WINEDEBUG=-all"))
    Sc = "/usr/bin/systemctl"
    return (EjecutarUnix([Sc, "--user", "daemon-reload"])
            and EjecutarUnix([Sc, "--user", "enable", f"{Nombre}.timer"])
            and EjecutarUnix([Sc, "--user", "restart", f"{Nombre}.timer"]))


def ProgramarTarea(IdAviso, FechaHora):
    Nombre = NombreTarea.format(IdAviso)
    Programa, Args = _ComandoAviso(IdAviso)
    try:
        if EsWine():
            return _ProgramarWine(Nombre, Programa, Args, FechaHora)
        if sys.platform.startswith("win"):
            Entorno = dict(os.environ, VENUS_PROGRAMA=Programa,
                           VENUS_ARGS=subprocess.list2cmdline(Args),
                           VENUS_CUANDO=FechaHora, VENUS_TAREA=Nombre)
            return _Powershell(_GuionTareaWindows, Entorno, TiempoLimite=30)
        if sys.platform.startswith("linux"):
            if not shutil.which("systemctl"):
                return False
            ComandoInicio = " ".join(_ArgumentoSystemd(A) for A in [Programa, *Args])
            _EscribirUnidades(_CarpetaSystemdUsuario(), Nombre, ComandoInicio, FechaHora)
            return (_Ejecutar(["systemctl", "--user", "daemon-reload"])
                    and _Ejecutar(["systemctl", "--user", "enable", f"{Nombre}.timer"])
                    and _Ejecutar(["systemctl", "--user", "restart", f"{Nombre}.timer"]))
    except Exception:
        logging.exception("No se pudo programar el aviso %s en el sistema", IdAviso)
    return False


def CancelarTarea(IdAviso):
    Nombre = NombreTarea.format(IdAviso)
    try:
        if EsWine():
            Carpeta = _CarpetaSystemdWine()
            if Carpeta is None or not ((Carpeta / f"{Nombre}.timer").exists()
                                       or (Carpeta / f"{Nombre}.service").exists()):
                return
            Sc = "/usr/bin/systemctl"
            EjecutarUnix([Sc, "--user", "disable", "--now", f"{Nombre}.timer"])
            for Ext in ("timer", "service"):
                (Carpeta / f"{Nombre}.{Ext}").unlink(missing_ok=True)
            EjecutarUnix([Sc, "--user", "daemon-reload"])
        elif sys.platform.startswith("win"):
            _Ejecutar(["schtasks", "/Delete", "/TN", f"\\Venus\\{Nombre}", "/F"], TiempoLimite=20)
        elif sys.platform.startswith("linux") and shutil.which("systemctl"):
            Carpeta = _CarpetaSystemdUsuario()
            if not ((Carpeta / f"{Nombre}.timer").exists() or (Carpeta / f"{Nombre}.service").exists()):
                return
            _Ejecutar(["systemctl", "--user", "disable", "--now", f"{Nombre}.timer"])
            for Ext in ("timer", "service"):
                (Carpeta / f"{Nombre}.{Ext}").unlink(missing_ok=True)
            _Ejecutar(["systemctl", "--user", "daemon-reload"])
    except Exception:
        logging.exception("No se pudo cancelar el aviso %s", IdAviso)