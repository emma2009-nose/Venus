# Venus

Aplicación de escritorio (Tkinter) con un sistema multiagente de IA. El usuario
habla con **P** (Principal); detrás trabajan **C** (Contexto/Unificador) y los
revisores **R1**/**R2**, cada uno con su propio proveedor, modelo y cuaderno.

> **Nota:** Venus **no trae ninguna API ni prompt precargado**. Hay que
> configurar al menos C, R1 y P en *Ajustes → APIs y modelos* (R2 es opcional).

## Requisitos

- Python 3.9 o superior.
- `tkinter` (suele venir con Python en Linux; en algunas distros hay que
  instalar el paquete `python3-tk`).
- Las dependencias de `requirements.txt`.

## Instalación

```bash
cd app
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar

```bash
python Venus.py
```

La primera vez se abre la pantalla de configuración de IAs. Completa C, R1 y P
con la URL, la clave y el modelo de cada una (R2 es opcional). Esa configuración
se guarda en `~/.venus/ias/` junto con los prompts y los cuadernos.

### Variables de entorno útiles

| Variable | Qué hace |
| --- | --- |
| `VENUS_DIR_DATOS` | Carpeta raíz de datos (por defecto `~/.venus`). |
| `VENUS_RUTA_MANUALES` | Carpeta con los manuales (.txt / .docx) para buscar. |
| `VENUS_RUTA_BD` | Ruta de la base de datos `venus.db`. |
| `VENUS_GUARDAR_MANUALES_AUTO=0` | No guardar respuestas automáticamente como manuales. |
| `VENUS_DOC_WEB_PERMITIR_LOCAL=1` | Permite descargar URLs locales/privadas (solo pruebas). |
| `VENUS_COMPARTIR_CUADERNOS=0` | No inyectar los cuadernos de las demás IAs (más rápido y evita que contenido de terceros se reinyecte para siempre). |
| `VENUS_ESPERA_429` | Segundos de espera por cada reintento ante error 429 (por defecto `15`). |
| `VENUS_REVISIONES=1` | Modo rápido: una sola ronda de revisión (~5-6 llamadas en vez de hasta 9). |

## Módulos

- `ia/codigo/ai.py` — cliente de un nodo de IA (proveedor + prompts).
- `ia/codigo/proveedores.py` — las 4 IAs, perfiles, prompts y cuadernos.
- `ia/codigo/flujo.py` — el pipeline C → R1/R2 → P (modos Generación/Profesor).
- `ia/codigo/documento_web.py` — descarga segura de una URL como documentación.
- `venus/rag.py` — búsqueda local en los manuales del usuario.
- `venus/ui/` — la interfaz (chat, manuales, calendario, perfiles, ajustes…).

## Modos de trabajo

- **Generación**: P borra → R1/R2 revisan → C aplica → P unifica → revisan →
  C aplica → P entrega.
- **Profesor**: P responde solo. El botón **«Inglés»** del chat activa las
  revisiones en inglés (P → R1/R2 → C → P).

## Empaquetar / entregar

Para crear un `.zip` limpio **sin** el entorno virtual, la caché ni el
historial de Git:

```bash
git archive --format=zip -o venus.zip HEAD
```

Si prefieres empaquetar la carpeta directamente (sin Git), excluye las carpetas
de trabajo:

```bash
zip -r venus.zip . -x '.venv/*' '__pycache__/*' '.git/*' '*.pyc'
```

El repositorio no incluye `.venv` ni `__pycache__` (están en `.gitignore`), así
que `git archive` ya produce un zip pequeño y sin nombres de usuario.


## Licencia

- **Código**: PolyForm Noncommercial License 1.0.0 (ver `LICENSE`).
- **Prompts y manuales**: CC BY-NC-SA 4.0 (ver `LICENSE-PROMPTS-MANUALES`).
- **Contribuciones**: sujetas al acuerdo en `CLA.md`.
- **Titular**: venus.
