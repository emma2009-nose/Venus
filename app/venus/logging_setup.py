import logging
from .config import DirDatos, RutaLog


def ConfigurarLogging():
    try:
        DirDatos.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=RutaLog,
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            encoding="utf-8",
        )
    except OSError:
        logging.basicConfig(level=logging.INFO)