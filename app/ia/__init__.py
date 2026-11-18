"""Motor de IA de Venus.

Todo lo que se puede tocar de la IA vive aquí:

  - codigo/proveedores.py  las 4 IAs, sus carpetas, prompts y cuadernos
  - codigo/ai.py           cliente de un nodo (proveedor + 2 prompts)
  - codigo/flujo.py        pipeline C -> R1/R2 -> P
  - codigo/documento_web.py  descarga de URL para el contexto
  - prompts/archivo/       prompts antiguos, solo de referencia

Las APIs, los modelos y los prompts de cada IA viven en ~/.venus/ias/.
La app no trae ningún prompt escrito ni ninguna API precargada.
"""
