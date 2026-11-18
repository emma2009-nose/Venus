"""Las 4 IAs de Venus: roles, configuración, carpetas, prompts y cuadernos.

Cada IA vive en su propia carpeta dentro de ~/.venus/ias/:

    1/  C   Contexto / Historial / Unificador
    2/  R1  Revisor 1
    3/  R2  Revisor 2
    4/  P   Principal (la que responde al usuario)

Dentro de cada carpeta:

    config.json     proveedor, clave de API y modelo
    prompts/
        prompt_1.txt
        prompt_2.txt
    cuaderno.md     cuaderno personal (la app anota su trabajo)

La app NO trae ningún prompt escrito: si los archivos están vacíos, esa IA no
recibe ningún mensaje de sistema. Los prompts los pone el usuario.
"""
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Roles fijos de los 4 slots. El usuario elige API/modelo para cada uno.
Roles = {
    1: {
        "clave": "C",
        "nombre": "Contexto",
        "descripcion": "Contexto / Historial / Unificador",
    },
    2: {
        "clave": "R1",
        "nombre": "Revisor 1",
        "descripcion": "Revisor / filtro / asignador de reglas",
    },
    3: {
        "clave": "R2",
        "nombre": "Revisor 2",
        "descripcion": "Revisor / filtro / asignador de reglas",
    },
    4: {
        "clave": "P",
        "nombre": "Principal",
        "descripcion": "Persona / integrador final (la que te responde)",
    },
}

Ids = (1, 2, 3, 4)
# C, R1 y P son imprescindibles. R2 es opcional: si no se configura, el
# pipeline usa solo a R1 como revisor.
IdsObligatorios = (1, 2, 4)
MaximoCuaderno = 200_000
Leeme = """CARPETAS DE LAS 4 IAs
=====================

Cada IA de Venus tiene su carpeta, sus prompts y su cuaderno:

  1/  C   Contexto / Historial / Unificador
  2/  R1  Revisor 1
  3/  R2  Revisor 2 (OPCIONAL: si no la configuras, revisa solo R1)
  4/  P   Principal (la que te responde)

Dentro de cada carpeta:

  config.json     copia de la config del modo activo (no hace falta editarlo)
  prompts/
    prompt_1.txt  primer prompt de esa IA (vacío por defecto)
    prompt_2.txt  segundo prompt; se alterna con el primero
  cuaderno.md     cuaderno personal. La app anota el trabajo de la IA y tú
                  también puedes escribir tus notas.

La app NO agrega ningún prompt: solo lee los archivos de prompts/. Si ambos
están vacíos, esa IA no recibe ningún mensaje de sistema.

El cuaderno de cada IA se incluye como contexto en el trabajo de las demás
(solo lectura), para que puedan compartir lo que han aprendido. Cada IA ve el
suyo como [TU CUADERNO] y los demás como [CUADERNO DE R1], etc.

PASOS QUE RECIBE CADA IA
------------------------
El orquestador envía un mensaje con etiquetas como [PASO: BORRADOR] y los
datos del paso ([PETICIÓN DEL USUARIO], [BORRADOR], [REVISION_R1], ...).
Tu prompt debe explicar qué hacer en cada paso.

Modo Generación:
  C       BORRADOR, APLICAR
  R1/R2   REVISION_1, REVISION_2
  P       UNIFICAR, ENTREGAR

Modo Profesor:
  Sin Inglés:  P responde solo (PROFE_RESPUESTA).
  Con Inglés:  P PROFE_BASE -> R1/R2 PROFE_REVISION -> C PROFE_REVISAR ->
               P PROFE_ENTREGAR. Los datos llevan [IDIOMA: INGLÉS].

El usuario solo habla con P; C, R1 y R2 trabajan por detrás.

C, R1 y P son obligatorias para poder usar el chat. R2 es opcional: si su
carpeta no tiene proveedor/clave/modelo, el pipeline revisa solo con R1.

IA LOCAL (OLLAMA, LM STUDIO, LLAMA.CPP...)
------------------------------------------
Cada slot puede ser "API" (remota) o "IA local". En la ventana de IAs elige
el modo del slot:
  API       -> URL, clave y modelo de un proveedor compatible con OpenAI.
  IA local  -> se configura con http://localhost:11434/v1 y la clave "ollama"
               (Ollama). Si usas otro servidor local (LM Studio, llama.cpp,
               LocalAI...), cambia la URL a la suya; "Ver modelos" prueba
               /api/tags y /v1/models.

Los slots son independientes: puedes tener C y P con una API y R1 con una IA
local, y trabajarán juntos en el mismo pipeline. A las IA locales no se les
manda el campo "thinking" de DeepSeek.

MODOS (PERFILES)
----------------
Un modo guarda las 4 configuraciones (APIs y modelos), no los prompts ni los
cuadernos. Se cambia desde Ajustes -> "Modo de IAs" o desde la ventana de IAs.

  perfiles/deepseek.json   C, R1 y P con DeepSeek; R2 vacío.
  perfiles/ollama.json     C qwen2.5:3b, R1 deepseek-r1:1.5b,
                           P deepseek-r1:8b; R2 vacío.
  perfiles/activo.txt      modo que usa Venus ahora.

Puedes añadir modos nuevos y borrar todas las IAs de un modo desde Ajustes
-> Modo de IAs o desde la ventana de IAs:
  "Nuevo perfil"  crea un modo vacío para otro proveedor.
  "Borrar todas las IAs de este modo"  limpia solo las APIs y modelos del
  modo activo. No se tocan los prompts, los cuadernos ni los otros modos.

"""


def CarpetaBase():
    """Carpeta raíz de las IAs (se lee en cada llamada para poder probarla)."""
    from venus import config
    return Path(config.DirIAs)


def CarpetaIA(IdIA):
    return CarpetaBase() / str(IdIA)


def RutaConfig(IdIA):
    return CarpetaIA(IdIA) / "config.json"


def RutaPrompts(IdIA):
    return CarpetaIA(IdIA) / "prompts"


def RutaCuaderno(IdIA):
    return CarpetaIA(IdIA) / "cuaderno.md"


def EtiquetaRol(IdIA):
    Rol = Roles[IdIA]
    return f'{Rol["clave"]} · {Rol["nombre"]} ({Rol["descripcion"]})'


@dataclass
class Proveedor:
    Id: int
    Rol: str
    Nombre: str
    BaseUrl: str = ""
    ApiKey: str = ""
    Modelo: str = ""
    Habilitada: bool = True
    MaxTokens: int = 8000
    # "off" = pide al proveedor que no razone (thinking off),
    # "on"  = lo activa, "auto" = no manda nada (lo decide el modelo).
    Razonamiento: str = "auto"
    # "api"   = API remota compatible con OpenAI (DeepSeek, OpenRouter...),
    # "local" = IA local (Ollama, LM Studio, llama.cpp...).
    Tipo: str = "api"

    def Lista(self):
        """True si tiene lo mínimo para llamar a la API."""
        return bool(self.BaseUrl.strip() and self.ApiKey.strip() and self.Modelo.strip())


def _Defecto(IdIA):
    Rol = Roles[IdIA]
    return {
        "rol": Rol["clave"],
        "base_url": "",
        "api_key": "",
        "modelo": "",
        "habilitada": True,
        "max_tokens": 8000,
        "razonamiento": "auto",
        "tipo": "api",
    }


def _LeerJson(Ruta):
    try:
        with open(Ruta, "r", encoding="utf-8") as F:
            Datos = json.load(F)
        return Datos if isinstance(Datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _EscribirJson(Ruta, Datos):
    Ruta.parent.mkdir(parents=True, exist_ok=True)
    Temporal = Ruta.with_suffix(Ruta.suffix + ".tmp")
    with open(Temporal, "w", encoding="utf-8") as F:
        json.dump(Datos, F, ensure_ascii=False, indent=2)
        F.write("\n")
    os.replace(Temporal, Ruta)
    try:
        os.chmod(Ruta, 0o600)
    except OSError:
        pass


def CrearEstructura(IdIA):
    """Crea la carpeta, los 2 prompts vacíos y el cuaderno si no existen."""
    Rol = Roles[IdIA]
    Carpeta = CarpetaIA(IdIA)
    (Carpeta / "prompts").mkdir(parents=True, exist_ok=True)

    for Nombre in ("prompt_1.txt", "prompt_2.txt"):
        Ruta = Carpeta / "prompts" / Nombre
        if not Ruta.exists():
            Ruta.write_text("", encoding="utf-8")

    Cuaderno = RutaCuaderno(IdIA)
    if not Cuaderno.exists():
        Cuaderno.write_text(
            f"# Cuaderno de {Rol['clave']} — {Rol['nombre']} ({Rol['descripcion']})\n\n"
            "Aquí la app anota el trabajo de esta IA. También puedes escribir tus notas.\n",
            encoding="utf-8",
        )

    RutaLeeme = CarpetaBase() / "LEEME.txt"
    if not RutaLeeme.exists():
        RutaLeeme.parent.mkdir(parents=True, exist_ok=True)
        RutaLeeme.write_text(Leeme, encoding="utf-8")


def CrearTodas():
    for IdIA in Ids:
        CrearEstructura(IdIA)


# ------------------------------------------------------------------ perfiles
# Un perfil ("modo de IAs") guarda las 4 configuraciones. Los prompts y los
# cuadernos son de la IA, no del perfil, así que se comparten entre modos.
def CarpetaPerfiles():
    return CarpetaBase() / "perfiles"


def RutaPerfil(Nombre):
    return CarpetaPerfiles() / f"{Nombre}.json"


def RutaPerfilActivo():
    return CarpetaPerfiles() / "activo.txt"


EtiquetasPerfil = {"deepseek": "DeepSeek", "ollama": "Ollama"}

# Reparto del perfil Ollama: la mejor para P, la segunda para C y la menos
# buena (de las usadas) para R1. R2 queda vacía. llama3.2:3b no se usa.
ModelosOllama = {
    1: "qwen2.5:3b",
    2: "deepseek-r1:1.5b",
    3: "",
    4: "deepseek-r1:8b",
}


def _ConfigVacia():
    return {
        "base_url": "", "api_key": "", "modelo": "",
        "razonamiento": "auto", "tipo": "api",
        "habilitada": True, "max_tokens": 8000,
    }


def _ConfigAOllama(Modelo):
    return {
        "base_url": "http://localhost:11434/v1" if Modelo else "",
        "api_key": "ollama" if Modelo else "",
        "modelo": Modelo or "",
        "razonamiento": "auto",
        "tipo": "local" if Modelo else "api",
        "habilitada": True,
        "max_tokens": 8000,
    }


def _JsonDeProveedor(Proveedor):
    return {
        "base_url": Proveedor.BaseUrl,
        "api_key": Proveedor.ApiKey,
        "modelo": Proveedor.Modelo,
        "razonamiento": Proveedor.Razonamiento,
        "tipo": Proveedor.Tipo,
        "habilitada": Proveedor.Habilitada,
        "max_tokens": Proveedor.MaxTokens,
    }


def _ProveedorDesdeDict(IdIA, Datos):
    Rol = Roles[IdIA]
    Datos = Datos if isinstance(Datos, dict) else {}
    Razonamiento = str(Datos.get("razonamiento", "auto")).strip().lower()
    if Razonamiento not in ("off", "on", "auto"):
        Razonamiento = "auto"
    Tipo = str(Datos.get("tipo", "api")).strip().lower()
    if Tipo in ("ollama", "local"):
        Tipo = "local"
    else:
        Tipo = "api"
    try:
        MaxTokens = int(Datos.get("max_tokens", 8000) or 8000)
    except (TypeError, ValueError):
        MaxTokens = 8000
    return Proveedor(
        Id=IdIA,
        Rol=Rol["clave"],
        Nombre=Rol["nombre"],
        BaseUrl=str(Datos.get("base_url", "")).strip(),
        ApiKey=str(Datos.get("api_key", "")).strip(),
        Modelo=str(Datos.get("modelo", "")).strip(),
        Habilitada=bool(Datos.get("habilitada", True)),
        MaxTokens=MaxTokens,
        Razonamiento=Razonamiento,
        Tipo=Tipo,
    )


def _LeerConfigLegacy(IdIA):
    """Configuración antigua por slot (solo para migrar al perfil DeepSeek)."""
    Datos = _Defecto(IdIA)
    Datos.update(_LeerJson(RutaConfig(IdIA)))
    return _ProveedorDesdeDict(IdIA, Datos)


def _PerfilDeepSeek():
    Ias = {}
    for IdIA in Ids:
        if IdIA == 3:
            Ias[str(IdIA)] = _ConfigVacia()
        else:
            Ias[str(IdIA)] = _JsonDeProveedor(_LeerConfigLegacy(IdIA))
    return {"nombre": "deepseek", "etiqueta": "DeepSeek", "ias": Ias}


def _PerfilOllama():
    Ias = {str(IdIA): _ConfigAOllama(ModelosOllama[IdIA]) for IdIA in Ids}
    return {"nombre": "ollama", "etiqueta": "Ollama", "ias": Ias}


def AsegurarPerfiles():
    """Crea los dos modos si aún no existen y el archivo del modo activo."""
    CarpetaPerfiles().mkdir(parents=True, exist_ok=True)
    if not RutaPerfil("deepseek").is_file():
        _EscribirJson(RutaPerfil("deepseek"), _PerfilDeepSeek())
    if not RutaPerfil("ollama").is_file():
        _EscribirJson(RutaPerfil("ollama"), _PerfilOllama())
    if not RutaPerfilActivo().is_file():
        RutaPerfilActivo().write_text("deepseek", encoding="utf-8")
        try:
            os.chmod(RutaPerfilActivo(), 0o600)
        except OSError:
            pass


def PerfilesDisponibles():
    AsegurarPerfiles()
    Disponibles = []
    for Ruta in sorted(CarpetaPerfiles().glob("*.json")):
        Nombre = Ruta.stem
        Datos = _LeerJson(Ruta)
        Etiqueta = str(Datos.get("etiqueta")
                       or EtiquetasPerfil.get(Nombre, Nombre.title()))
        Disponibles.append({"nombre": Nombre, "etiqueta": Etiqueta})
    Orden = {"deepseek": 0, "ollama": 1}
    Disponibles.sort(key=lambda P: (Orden.get(P["nombre"], 99), P["nombre"]))
    return Disponibles


def LeerPerfilActivo():
    AsegurarPerfiles()
    try:
        Nombre = RutaPerfilActivo().read_text(encoding="utf-8").strip()
    except OSError:
        Nombre = "deepseek"
    if not RutaPerfil(Nombre).is_file():
        Nombre = "deepseek"
    return Nombre


def EtiquetaPerfilActivo():
    Nombre = LeerPerfilActivo()
    Datos = _LeerJson(RutaPerfil(Nombre))
    return str(Datos.get("etiqueta")
               or EtiquetasPerfil.get(Nombre, Nombre.title()))


def LeerPerfil(Nombre):
    AsegurarPerfiles()
    Datos = _LeerJson(RutaPerfil(Nombre))
    Ias = Datos.get("ias") if isinstance(Datos.get("ias"), dict) else {}
    return {IdIA: _ProveedorDesdeDict(IdIA, Ias.get(str(IdIA), {}))
            for IdIA in Ids}


def CambiarPerfil(Nombre):
    AsegurarPerfiles()
    if not RutaPerfil(Nombre).is_file():
        return False
    try:
        RutaPerfilActivo().write_text(Nombre, encoding="utf-8")
        try:
            os.chmod(RutaPerfilActivo(), 0o600)
        except OSError:
            pass
    except OSError:
        logging.exception("No se pudo cambiar el modo de IAs a %s", Nombre)
        return False
    return True


def _SlugPerfil(Texto):
    """Convierte 'OpenRouter' en 'openrouter' (nombre de archivo seguro)."""
    Texto = unicodedata.normalize("NFKD", str(Texto or ""))
    Texto = "".join(C for C in Texto if not unicodedata.combining(C))
    Texto = re.sub(r"[^a-zA-Z0-9]+", "-", Texto).strip("-").lower()
    return Texto[:40]


def CrearPerfil(Etiqueta):
    """Crea un modo nuevo vacío. Devuelve el nombre o None si no es válido."""
    Etiqueta = str(Etiqueta or "").strip()
    Nombre = _SlugPerfil(Etiqueta)
    AsegurarPerfiles()
    if not Nombre or Nombre == "activo" or RutaPerfil(Nombre).is_file():
        return None
    Perfil = {
        "nombre": Nombre,
        "etiqueta": Etiqueta[:40] or Nombre.title(),
        "ias": {str(IdIA): _ConfigVacia() for IdIA in Ids},
    }
    _EscribirJson(RutaPerfil(Nombre), Perfil)
    return Nombre


def BorrarIAsPerfil(Nombre):
    """Borra solo las APIs/modelos de ese modo, no los prompts ni otros modos."""
    AsegurarPerfiles()
    if not RutaPerfil(Nombre).is_file():
        return False
    Perfil = _LeerJson(RutaPerfil(Nombre))
    Perfil["ias"] = {str(IdIA): _ConfigVacia() for IdIA in Ids}
    _EscribirJson(RutaPerfil(Nombre), Perfil)
    # Si es el modo activo, vaciar también las copias por slot.
    if LeerPerfilActivo() == Nombre:
        for IdIA in Ids:
            _EscribirJson(RutaConfig(IdIA), Perfil["ias"][str(IdIA)])
    return True


# ------------------------------------------------------------------ config
def LeerConfig(IdIA):
    return LeerPerfil(LeerPerfilActivo())[IdIA]


def GuardarConfig(IdIA, BaseUrl=None, ApiKey=None, Modelo=None,
                  Habilitada=None, MaxTokens=None, Razonamiento=None,
                  Tipo=None):
    """Guarda la config en el modo activo. api_key=None conserva la clave."""
    AsegurarPerfiles()
    Nombre = LeerPerfilActivo()
    Perfil = _LeerJson(RutaPerfil(Nombre))
    Ias = Perfil.get("ias") if isinstance(Perfil.get("ias"), dict) else {}
    Actual = _ProveedorDesdeDict(IdIA, Ias.get(str(IdIA), {}))
    Datos = _Defecto(IdIA)
    Datos["base_url"] = Actual.BaseUrl if BaseUrl is None else str(BaseUrl).strip()
    Datos["api_key"] = Actual.ApiKey if ApiKey is None else str(ApiKey).strip()
    Datos["modelo"] = Actual.Modelo if Modelo is None else str(Modelo).strip()
    Datos["habilitada"] = Actual.Habilitada if Habilitada is None else bool(Habilitada)
    Datos["max_tokens"] = Actual.MaxTokens if MaxTokens is None else int(MaxTokens)
    Datos["razonamiento"] = (Actual.Razonamiento if Razonamiento is None
                             else str(Razonamiento).strip().lower())
    if Datos["razonamiento"] not in ("off", "on", "auto"):
        Datos["razonamiento"] = "auto"
    Datos["tipo"] = Actual.Tipo if Tipo is None else str(Tipo).strip().lower()
    if Datos["tipo"] in ("ollama", "local"):
        Datos["tipo"] = "local"
    else:
        Datos["tipo"] = "api"
    Ias[str(IdIA)] = {
        "base_url": Datos["base_url"],
        "api_key": Datos["api_key"],
        "modelo": Datos["modelo"],
        "razonamiento": Datos["razonamiento"],
        "tipo": Datos["tipo"],
        "habilitada": Datos["habilitada"],
        "max_tokens": Datos["max_tokens"],
    }
    Perfil["nombre"] = Nombre
    Perfil["etiqueta"] = Perfil.get("etiqueta") or EtiquetasPerfil.get(
        Nombre, Nombre.title())
    Perfil["ias"] = Ias
    _EscribirJson(RutaPerfil(Nombre), Perfil)
    # Compatibilidad: el config.json por slot refleja el modo activo.
    _EscribirJson(RutaConfig(IdIA), Ias[str(IdIA)])
    CrearEstructura(IdIA)
    return Ias[str(IdIA)]


def CargarTodas():
    return [LeerConfig(IdIA) for IdIA in Ids]


def Faltantes():
    """IAs obligatorias (C, R1 y P) a las que les falta proveedor, clave o modelo."""
    return [P for P in CargarTodas()
            if P.Id in IdsObligatorios and not P.Lista()]


def Completa():
    return not Faltantes()


def TextoFaltantes():
    return ", ".join(f'{P.Rol} ({P.Nombre})' for P in Faltantes())


# ------------------------------------------------------------------ prompts
def LeerPrompts(IdIA):
    """Devuelve los prompts no vacíos de la IA, en orden (máximo 2)."""
    Textos = []
    for Nombre in ("prompt_1.txt", "prompt_2.txt"):
        Ruta = RutaPrompts(IdIA) / Nombre
        try:
            Texto = Ruta.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if Texto:
            Textos.append(Texto)
    return Textos


def GuardarPrompts(IdIA, Prompt1, Prompt2):
    Ruta = RutaPrompts(IdIA)
    Ruta.mkdir(parents=True, exist_ok=True)
    (Ruta / "prompt_1.txt").write_text((Prompt1 or "").strip() + "\n", encoding="utf-8")
    (Ruta / "prompt_2.txt").write_text((Prompt2 or "").strip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------- cuadernos
def LeerCuaderno(IdIA):
    try:
        return RutaCuaderno(IdIA).read_text(encoding="utf-8")
    except OSError:
        return ""


def GuardarCuaderno(IdIA, Texto):
    Ruta = RutaCuaderno(IdIA)
    Ruta.parent.mkdir(parents=True, exist_ok=True)
    Ruta.write_text((Texto or "").strip() + "\n", encoding="utf-8")


def _Recortar(Texto, Limite):
    """Recorta un texto largo conservando el final (lo más reciente)."""
    if len(Texto) <= Limite:
        return Texto
    return "…\n" + Texto[-Limite:]


def _RecortarCuaderno(Texto, Limite):
    if len(Texto) <= Limite:
        return Texto
    # Conserva el título inicial y el final (lo más reciente).
    Lineas = Texto.splitlines()
    Cabecera = Lineas[0] if Lineas else "# Cuaderno"
    Cuerpo = "\n".join(Lineas[1:])
    return f"{Cabecera}\n\n[…cuaderno recortado…]\n\n" + Cuerpo[-Limite:]


def Anotar(IdIA, Paso, Texto, Maximo=MaximoCuaderno):
    """Añade una entrada al cuaderno de la IA (trabajo automático)."""
    Texto = (Texto or "").strip()
    if not Texto:
        return
    CrearEstructura(IdIA)
    Ruta = RutaCuaderno(IdIA)
    Entrada = f"\n\n## {datetime.now():%Y-%m-%d %H:%M} · {Paso}\n\n{Texto}\n"
    try:
        Actual = Ruta.read_text(encoding="utf-8") if Ruta.is_file() else ""
        Nuevo = Actual + Entrada
        if len(Nuevo) > Maximo:
            Nuevo = _RecortarCuaderno(Nuevo, int(Maximo * 0.85))
        Ruta.write_text(Nuevo, encoding="utf-8")
    except OSError:
        logging.exception("No se pudo anotar en el cuaderno de la IA %s", IdIA)


def ContextoCuadernos(IdPropio, MaxPropio=3500, MaxOtros=1200):
    """Cuadernos de las 4 IAs: el propio completo y los demás recortados."""
    Bloques = []
    for IdIA in Ids:
        Limite = MaxPropio if IdIA == IdPropio else MaxOtros
        Texto = _RecortarCuaderno(LeerCuaderno(IdIA), Limite).strip()
        if not Texto:
            continue
        Etiqueta = "TU CUADERNO" if IdIA == IdPropio else f"CUADERNO DE {Roles[IdIA]['clave']}"
        Bloques.append(f"[{Etiqueta}]\n{Texto}")
    return "\n\n".join(Bloques)
