import requests
import time
import logging

import os
from dotenv import load_dotenv

load_dotenv()


API_URL = os.getenv(
    "API_URL",
    "https://jsonplaceholder.typicode.com/posts",
).rstrip("/")

try:
    TIMEOUT = float(os.getenv("API_TIMEOUT", "10"))
    MAX_INTENTOS = int(os.getenv("API_MAX_INTENTOS", "3"))
    ESPERA_BASE = float(os.getenv("API_ESPERA_BASE", "1"))

    if TIMEOUT <= 0:
        raise ValueError("API_TIMEOUT debe ser mayor que 0.")
    if MAX_INTENTOS < 1:
        raise ValueError("API_MAX_INTENTOS debe ser al menos 1.")
    if ESPERA_BASE < 0:
        raise ValueError("API_ESPERA_BASE no puede ser negativo.")

except ValueError as error:
    raise ValueError(f"Configuración inválida en el archivo .env: {error}") from error


def consultar_id(id_cuenta):
    url = f"{API_URL}/{id_cuenta}"
    causa = None   

    for intento in range(1, MAX_INTENTOS + 1):
        try:
            respuesta = requests.get(url, timeout=TIMEOUT)

            # Caso de negocio: el id no existe. NO se reintenta.
            if respuesta.status_code == 404:
                return {
                    "id_cuenta": id_cuenta,
                    "estado": "NO_ENCONTRADO",
                    "datos": None,
                    "causa": "ID_INEXISTENTE",
                }

            # Caso de negocio: la API rechazó la petición (400, 401, 403, 422).
            # No se reintenta: reintentar no arregla.
            if (
                400 <= respuesta.status_code < 500
                and respuesta.status_code not in (404, 429)
            ):
                causa = f"HTTP_{respuesta.status_code}"
                logging.warning(
                    "ID %s: %s (negocio, no se reintenta).",
                    id_cuenta,
                    causa,
                )
                return {
                    "id_cuenta": id_cuenta,
                    "estado": "ERROR_NEGOCIO",
                    "datos": None,
                    "causa": causa,
                }

            # Caso técnico: 429 o 5xx. SÍ se reintenta.
            if respuesta.status_code == 429 or respuesta.status_code >= 500:
                causa = f"HTTP_{respuesta.status_code}"

                if intento < MAX_INTENTOS:
                    espera = ESPERA_BASE * (2 ** (intento - 1))
                    logging.warning(
                        "ID %s: %s. Reintento en %s s (intento %s de %s).",
                        id_cuenta,
                        causa,
                        espera,
                        intento,
                        MAX_INTENTOS,
                    )
                    print(
                        f"ID {id_cuenta}: {causa}. "
                        f"Reintento en {espera} s "
                        f"({intento}/{MAX_INTENTOS})."
                    )
                    time.sleep(espera)
                    continue

                logging.error(
                    "ID %s: %s. Se agotaron los %s intentos.",
                    id_cuenta,
                    causa,
                    MAX_INTENTOS,
                )
                return {
                    "id_cuenta": id_cuenta,
                    "estado": "ERROR_TECNICO",
                    "datos": None,
                    "causa": causa,
                }

            # 2xx: éxito.
            respuesta.raise_for_status()
            datos = respuesta.json()

            if not isinstance(datos, dict):
                logging.error(
                    "ID %s: la respuesta no es un objeto JSON (tipo %s).",
                    id_cuenta,
                    type(datos).__name__,
                )
                return {
                    "id_cuenta": id_cuenta,
                    "estado": "ERROR_TECNICO",
                    "datos": None,
                    "causa": "RESPUESTA_NO_ES_OBJETO",
                }

            return {
                "id_cuenta": id_cuenta,
                "estado": "RESUELTO",
                "datos": datos,
                "causa": None,
            }

        except requests.exceptions.Timeout:
            causa = "TIMEOUT"
            logging.warning(
                "ID %s: TIMEOUT en intento %s de %s.",
                id_cuenta,
                intento,
                MAX_INTENTOS,
            )

        except requests.exceptions.ConnectionError:
            causa = "ERROR_CONEXION"
            logging.warning(
                "ID %s: ERROR_CONEXION en intento %s de %s.",
                id_cuenta,
                intento,
                MAX_INTENTOS,
            )

        except requests.exceptions.HTTPError as error:
            # Solo llega aquí si raise_for_status() lanzó para un 2xx raro.
            # En la práctica no ocurre; defensivo.
            return {
                "id_cuenta": id_cuenta,
                "estado": "ERROR_TECNICO",
                "datos": None,
                "causa": f"HTTP_{error.response.status_code}",
            }

        except requests.exceptions.JSONDecodeError:
            return {
                "id_cuenta": id_cuenta,
                "estado": "ERROR_TECNICO",
                "datos": None,
                "causa": "JSON_INVALIDO",
            }

        except requests.exceptions.RequestException as error:
            return {
                "id_cuenta": id_cuenta,
                "estado": "ERROR_TECNICO",
                "datos": None,
                "causa": f"ERROR_HTTP_{error.__class__.__name__}",
            }

        # Solo Timeout y ConnectionError llegan aquí.
        if intento < MAX_INTENTOS:
            espera = ESPERA_BASE * (2 ** (intento - 1))
            time.sleep(espera)

    return {
        "id_cuenta": id_cuenta,
        "estado": "ERROR_TECNICO",
        "datos": None,
        "causa": causa,
    }