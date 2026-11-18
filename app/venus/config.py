import os
from pathlib import Path

VersionApp = "BETA"
SinVentana = 0x08000000

# Fuentes
FuenteTexto = "Comic Sans MS"
TamanoFuente = 24
# Fuentes para zonas de lectura larga (chat y visor de manuales). Basicas,
# legibles y presentes en cualquier Linux, sin depender de Comic Sans.
FuenteLectura = "DejaVu Sans"
FuenteMono = "DejaVu Sans Mono"


def _RutaEntorno(Nombre, Defecto):
    return Path(os.environ.get(Nombre, str(Defecto)))


DirDatos = _RutaEntorno("VENUS_DIR_DATOS", Path.home() / ".venus")
RutaArchivoBd = _RutaEntorno("VENUS_RUTA_BD", DirDatos / "venus.db")
RutaLog = DirDatos / "venus.log"
RutaManuales = _RutaEntorno("VENUS_RUTA_MANUALES", DirDatos / "manuales")
RutaInstrucciones = _RutaEntorno("VENUS_DIR_INSTRUCCIONES", DirDatos / "instrucciones")
RutaTema = DirDatos / "tema.txt"

# Una carpeta por IA (C, R1, R2, P). Dentro van sus 2 prompts y su cuaderno.
DirIAs = _RutaEntorno("VENUS_DIR_IAS", DirDatos / "ias")

# ------------------------------------------------------------------ TEMAS
# Cada paleta define los mismos nombres de color que usa toda la app.
Paletas = {
    "oscuro": {
        "nombre": "Oscuro",
        "fondo": "#0F0C12",
        "panel": "#1C1621",
        "botones": "#A533FF",
        "botonResaltado": "#B940FF",
        "colorTexto": "#E0D3EB",
        "rosa": "#FF409C",
        "lila": "#A533FF",
        "apagado": "#856B99",
        "oscuro": "#0C080F",
        "desactivado": "#594766",
        "borde": "#522873",
        "colorSeleccion": "#582680",
        "colorVenus": "#B57BFF",
        "colorUsuario": "#A533FF",
        "colorExito": "#7CFFB2",
        "colorError": "#FF6B6B",
        "colorVersion": "#8625AC",
        "colorTextoSeleccion": "#FFFFFF",
        "colorBordeVentana": "#650788",
        "degradadoInicio": "#A533FF",
        "degradadoFin": "#FF409C",
        "burbujaUsuarioFondo": "#251A30",
        "burbujaUsuarioBorde": "#A533FF",
        "burbujaVenusFondo": "#191320",
        "burbujaVenusBorde": "#B57BFF",
        "burbujaSistemaFondo": "#1C1621",
        "burbujaSistemaBorde": "#856B99",
    },
    "blueberry": {
        "nombre": "Claro",
        # Paleta "Blueberries": 04235A, 064490, 2686E0, 41A8F9,
        # 68CAFB y A7ECFB. El fondo es un tinte muy claro de A7ECFB
        # para que el texto navy siga siendo legible.
        "fondo": "#EAF7FE",
        "panel": "#FFFFFF",
        "botones": "#064490",
        "botonResaltado": "#2686E0",
        "colorTexto": "#04235A",
        "rosa": "#2686E0",
        "lila": "#064490",
        "apagado": "#3F6F9C",
        "oscuro": "#FFFFFF",
        "desactivado": "#8FB4D6",
        "borde": "#A7ECFB",
        "colorSeleccion": "#41A8F9",
        "colorVenus": "#064490",
        "colorUsuario": "#2686E0",
        "colorExito": "#0E7C6B",
        "colorError": "#C62828",
        "colorVersion": "#2686E0",
        "colorTextoSeleccion": "#04235A",
        "colorBordeVentana": "#064490",
        "degradadoInicio": "#04235A",
        "degradadoFin": "#68CAFB",
        "burbujaUsuarioFondo": "#DFF4FF",
        "burbujaUsuarioBorde": "#2686E0",
        "burbujaVenusFondo": "#FFFFFF",
        "burbujaVenusBorde": "#41A8F9",
        "burbujaSistemaFondo": "#F1FAFF",
        "burbujaSistemaBorde": "#A7ECFB",
    },
}


def _LeerTema():
    try:
        Tema = RutaTema.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "oscuro"
    return Tema if Tema in Paletas else "oscuro"


TemaActivo = _LeerTema()
_Paleta = Paletas[TemaActivo]

Fondo = _Paleta["fondo"]
Panel = _Paleta["panel"]
Botones = _Paleta["botones"]
BotonResaltado = _Paleta["botonResaltado"]
ColorTexto = _Paleta["colorTexto"]
Rosa = _Paleta["rosa"]
Lila = _Paleta["lila"]
Apagado = _Paleta["apagado"]
Oscuro = _Paleta["oscuro"]
Desactivado = _Paleta["desactivado"]
Borde = _Paleta["borde"]
ColorSeleccion = _Paleta["colorSeleccion"]
ColorVenus = _Paleta["colorVenus"]
ColorUsuario = _Paleta["colorUsuario"]
ColorExito = _Paleta["colorExito"]
ColorError = _Paleta["colorError"]
ColorVersion = _Paleta["colorVersion"]
ColorTextoSeleccion = _Paleta["colorTextoSeleccion"]
ColorBordeVentana = _Paleta["colorBordeVentana"]
DegradadoInicio = _Paleta["degradadoInicio"]
DegradadoFin = _Paleta["degradadoFin"]
BurbujaUsuarioFondo = _Paleta["burbujaUsuarioFondo"]
BurbujaUsuarioBorde = _Paleta["burbujaUsuarioBorde"]
BurbujaVenusFondo = _Paleta["burbujaVenusFondo"]
BurbujaVenusBorde = _Paleta["burbujaVenusBorde"]
BurbujaSistemaFondo = _Paleta["burbujaSistemaFondo"]
BurbujaSistemaBorde = _Paleta["burbujaSistemaBorde"]

# ------------------------------------------------------- APIs Y MODELOS
# No hay ninguna API ni ningún modelo escrito en el código: los 4 proveedores
# se configuran en la ventana de IAs y viven en ~/.venus/ias/<id>/config.json.

NombrePredeterminado = "venus"
LargoMaxNombre = 20

# Un archivo que pase de este tamaño no cabe como instruccion (se envia entero
# en cada pregunta). A partir de aqui se trata como manual y se busca por
# fragmentos (RAG).
MaxCaracteresInstruccion = 24_000

# Guardar automáticamente en Manuales las respuestas que parezcan un manual.
# Se puede desactivar con VENUS_GUARDAR_MANUALES_AUTO=0.
GuardarManualesAuto = os.environ.get("VENUS_GUARDAR_MANUALES_AUTO", "1").strip() != "0"

MensajeSinInternet = "No hay conexión a internet. Revisa tu Wi-Fi e inténtalo de nuevo."

# ------------------------------------------------------------------ PIPELINE
# Ajustes de coste/latencia y seguridad del flujo multiagente. Se leen solo de
# variables de entorno (no hay UI para volver a guardarlas en cada arranque).

# 0 = no inyectar los cuadernos de las demás IAs como contexto (más rápido, y
# evita que contenido de terceros se reinyecte y quede "en memoria" para
# siempre). 1 = compartir cuadernos (comportamiento original).
CompartirCuadernos = os.environ.get("VENUS_COMPARTIR_CUADERNOS", "1").strip() != "0"

# Segundos de espera en cada reintento por error 429 (límite de peticiones).
# Bajarlo acorta los turnos con Rate Limit; subirlo da más margen al proveedor.
Espera429 = float(os.environ.get("VENUS_ESPERA_429", "15"))

# Rondas de revisión del modo Generación. 2 = flujo completo
# P -> R1/R2 -> C -> P -> R1/R2 -> C -> P (hasta 9 llamadas).
# 1 = una sola ronda P -> R1/R2 -> C -> P (unas 5-6 llamadas): más barato y
# rápido, con el mismo formato de respuesta.
Revisiones = 1 if os.environ.get("VENUS_REVISIONES", "2").strip() == "1" else 2

