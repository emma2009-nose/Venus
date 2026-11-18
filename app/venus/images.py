import tkinter as tk
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

ExtensionesImagen = (".png", ".gif", ".jpg", ".jpeg")
MaxLadoImagen = 320


def ListarImagenes(Carpeta):
    Carpeta = Path(Carpeta)
    if not Carpeta.is_dir():
        return {}
    Imagenes = {}
    for Ruta in sorted(Carpeta.iterdir()):
        Extension = Ruta.suffix.lower()
        if not Ruta.is_file() or Extension not in ExtensionesImagen:
            continue
        if Image is None and Extension not in (".png", ".gif"):
            continue
        Imagenes[Ruta.name] = Ruta
    return Imagenes


def BuscarImagen(Nombre, Imagenes):
    Nombre = Nombre.strip().lower()
    for Archivo, Ruta in Imagenes.items():
        if Archivo.lower() == Nombre or Ruta.stem.lower() == Nombre:
            return Ruta
    return None


def CargarImagenTk(Ruta, MaxLado=MaxLadoImagen):
    if Image is not None:
        with Image.open(Ruta) as ImagenPil:
            ImagenPil.thumbnail((MaxLado, MaxLado))
            return ImageTk.PhotoImage(ImagenPil.copy())
    ImagenTk = tk.PhotoImage(file=str(Ruta))
    Factor = max(1, -(-max(ImagenTk.width(), ImagenTk.height()) // MaxLado))
    return ImagenTk.subsample(Factor) if Factor > 1 else ImagenTk