
from pathlib import Path
import logging

BASE_DIR = Path(__file__).resolve().parent.parent 

LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "ejecucion.log"

def configurar_logging():
     
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8",
        # force=True borra configuraciones previas y obliga al programa a usar ESTA configuración.
        force=True,
    )