
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "data" / "estado.json"


def cargar_estado():
    """Carga y valida los resultados guardados en ejecuciones anteriores."""
    if not STATE_PATH.exists():
        return {}

    try:
        with open(STATE_PATH, "r", encoding="utf-8") as archivo:
            estado = json.load(archivo)

        if not isinstance(estado, dict):
            raise ValueError("El estado debe ser un objeto JSON.")

        estados_validos = {"RESUELTO", "NO_ENCONTRADO", "ERROR_NEGOCIO", "ERROR_TECNICO"}

        for id_cuenta, resultado in estado.items():
            if not isinstance(resultado, dict):
                raise ValueError(
                    f"El resultado del ID {id_cuenta} debe ser un objeto JSON."
                )

            campos_requeridos = {"estado", "datos" ,"causa"}
            
            if not campos_requeridos.issubset(resultado):
                raise ValueError(
                    f"El resultado del ID {id_cuenta} no contiene todos los campos requeridos."
                )

            if resultado["estado"] not in estados_validos:
                raise ValueError(
                    f"El resultado del ID {id_cuenta} tiene un estado desconocido: "
                    f"{resultado['estado']}"
                )

        return estado

    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(
            f"No se pudo leer el archivo de estado: {error}"
        ) from error
    



def guardar_estado(estado):
    """Guarda el estado mediante un archivo temporal."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    archivo_temporal = STATE_PATH.with_suffix(".tmp")

    try:
        with open(archivo_temporal, "w", encoding="utf-8") as archivo:
            json.dump(estado, archivo, ensure_ascii=False, indent=2)

        archivo_temporal.replace(STATE_PATH)

    except OSError as error:
        raise RuntimeError(
            f"No se pudo guardar el archivo de estado: {error}"
        ) from error
