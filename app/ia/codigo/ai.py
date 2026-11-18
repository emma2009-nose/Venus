"""Cliente de una IA (un nodo del sistema multiagente).

Cada nodo usa su propio proveedor (URL, clave y modelo) y sus propios prompts,
que viven en ~/.venus/ias/<id>/prompts/. Aquí no hay ningún prompt escrito:
si la carpeta no tiene prompts, el nodo no recibe mensajes de sistema.
"""
import logging
import re
import time
from pathlib import Path

from openai import OpenAI

from .proveedores import LeerPrompts

MaxReintentos = 5

# Si el modelo se queda sin tokens a mitad de una respuesta, se le pide que
# continue exactamente donde estaba y se unen las partes.
Continuacion = (
    "Continúa exactamente donde te quedaste. No repitas lo anterior, no "
    "reinicies la respuesta ni vuelvas a poner el título. Termina la frase o "
    "sección pendiente y sigue hasta completar la respuesta."
)


class ErrorIA(Exception):
    pass


class ErrorIAConfiguracion(ErrorIA):
    """Error de autenticación/permisos (401, 403) o clave/modelo rechazado.

    Es distinto de un fallo transitorio (red, 429, 503…): no se puede saltar
    en silencio, porque la IA nunca va a responder mientras no se corrija la
    configuración. El orquestador lo propaga tal cual al usuario.
    """


class NodoIA:
    """Una de las 4 IAs, con su proveedor y sus 2 prompts."""

    def __init__(self, Proveedor):
        self.Proveedor = Proveedor
        self.Nombre = f"{Proveedor.Rol} · {Proveedor.Nombre}"
        self.Cliente = OpenAI(
            api_key=Proveedor.ApiKey or "ollama",
            base_url=Proveedor.BaseUrl,
        )
        self.Prompts = LeerPrompts(Proveedor.Id)
        self.Turno = 0
        self.MaxTokens = Proveedor.MaxTokens or 8000
        self.MaxContinuaciones = 2

    def RecargarPrompts(self):
        self.Prompts = LeerPrompts(self.Proveedor.Id)

    def MensajesSistema(self):
        """Sus prompts como mensajes de sistema (intercalados entre llamadas)."""
        Prompts = list(self.Prompts)
        if len(Prompts) >= 2 and self.Turno % 2 == 1:
            Prompts.reverse()
        return [{"role": "system", "content": P} for P in Prompts]

    def Completar(self, Mensajes, MaxTokens=None):
        """Devuelve el texto de la respuesta, pidiendo continuación si se corta."""
        Sistema = self.MensajesSistema()
        self.Turno += 1
        Conversacion = Sistema + [dict(M) for M in Mensajes]
        Tokens = MaxTokens or self.MaxTokens
        Partes = []
        Finish = None

        for Intento in range(self.MaxContinuaciones + 1):
            Respuesta = self._Llamar(Conversacion, Tokens)
            try:
                Eleccion = Respuesta.choices[0]
                Texto = self._TextoRespuesta(Eleccion.message)
                Finish = getattr(Eleccion, "finish_reason", None)
            except (AttributeError, IndexError, TypeError):
                Texto, Finish = "", None
            Partes.append(Texto)
            if (Finish not in ("length", "max_tokens")
                    or Intento >= self.MaxContinuaciones or not Texto):
                break
            # El modelo verá su propia respuesta parcial y continuará desde ahí.
            Conversacion.append({"role": "assistant", "content": Texto})
            Conversacion.append({"role": "user", "content": Continuacion})

        Unido = "\n\n".join(P for P in Partes if P).strip()
        if len(Partes) > 1 and Finish in ("length", "max_tokens"):
            Unido += ("\n\n[La respuesta se cortó por el límite del modelo. "
                      "Pide «continúa» para seguir.]")
        return Unido

    @staticmethod
    def _TextoRespuesta(Mensaje):
        """Texto visible del mensaje; respaldo para modelos de razonamiento.

        Algunos modelos locales (deepseek-r1, qwen con thinking...) devuelven
        el razonamiento en `reasoning`/`reasoning_content` y dejan `content`
        vacío si se quedan sin tokens. Si no hay contenido, se usa el
        razonamiento; si el contenido trae <think>...</think>, se quita.
        """
        Contenido = (getattr(Mensaje, "content", None) or "").strip()
        Razonamiento = (getattr(Mensaje, "reasoning_content", None)
                        or getattr(Mensaje, "reasoning", None) or "")
        if not isinstance(Razonamiento, str):
            Razonamiento = ""

        if "<think" in Contenido.lower():
            Contenido = re.sub(
                r"<think.*?</think>", "", Contenido,
                flags=re.DOTALL | re.IGNORECASE).strip()
        elif "</think>" in Contenido.lower():
            Contenido = re.split(
                r"</think>", Contenido, maxsplit=1,
                flags=re.IGNORECASE)[-1].strip()

        if not Contenido and Razonamiento.strip():
            Contenido = Razonamiento.strip()
        return Contenido

    def _Llamar(self, Mensajes, Tokens):
        # Razonamiento: "off" pide thinking desactivado (DeepSeek y similares);
        # "auto" no manda nada y deja que el proveedor decida. Las IA locales
        # (Ollama, LM Studio...) no entienden el campo "thinking" de DeepSeek.
        Extra = {}
        EsLocal = (self.Proveedor.Tipo == "local"
                   or "11434" in self.Proveedor.BaseUrl)
        if not EsLocal:
            if self.Proveedor.Razonamiento == "off":
                Extra["thinking"] = {"type": "disabled"}
            elif self.Proveedor.Razonamiento == "on":
                Extra["thinking"] = {"type": "enabled"}
        Opciones = {
            "model": self.Proveedor.Modelo,
            "messages": Mensajes,
            "max_tokens": Tokens,
        }
        if Extra:
            Opciones["extra_body"] = Extra

        UltimoError = None
        for Intento in range(MaxReintentos):
            try:
                return self.Cliente.chat.completions.create(**Opciones)
            except Exception as E:
                UltimoError = E
                Codigo = getattr(E, "status_code", None)
                # Si el modelo no admite tantos tokens de salida, reintenta con 4.000.
                if Codigo in (400, 422) and Tokens > 4000:
                    Tokens = 4000
                    continue
                if Codigo == 401 or "401" in str(E):
                    raise ErrorIAConfiguracion(
                        f"{self.Nombre}: la clave o el modelo fueron rechazados. "
                        "Revisa la configuración de esa IA."
                    ) from E
                if Codigo == 403 or "403" in str(E):
                    raise ErrorIAConfiguracion(
                        f"{self.Nombre}: la API no autoriza este modelo o esta clave."
                    ) from E
                if (Codigo == 429 or "429" in str(E)) and Intento < MaxReintentos - 1:
                    from venus import config
                    time.sleep(config.Espera429)
                    continue
                if (Codigo == 503 or "503" in str(E)) and Intento < MaxReintentos - 1:
                    time.sleep(3)
                    continue
                if "Connection error" in str(E) or "timed out" in str(E).lower():
                    raise ErrorIA(
                        f"{self.Nombre}: no se pudo conectar. Revisa internet y la URL "
                        "del proveedor."
                    ) from E
                raise ErrorIA(f"{self.Nombre}: {E}") from E
        raise ErrorIA(f"{self.Nombre}: {UltimoError}")


def CargarImagenes():
    """Imágenes que la app puede mostrar con [imagen:NOMBRE]."""
    from venus.config import RutaInstrucciones
    from venus.images import ListarImagenes
    from venus.resources import RutaRecurso

    Imagenes = {}
    for Carpeta in (RutaRecurso("instrucciones"), Path(RutaInstrucciones)):
        try:
            if Carpeta.is_dir():
                Imagenes.update(ListarImagenes(Carpeta))
        except Exception:
            logging.exception("No se pudieron listar las imágenes de %s", Carpeta)
    return Imagenes