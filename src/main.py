
import csv
from pathlib import Path


# Ruta del proyecto, independientemente del directorio desde el que se ejecute.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "cuentas.csv"


def leer_y_validar_csv(ruta):
    identificadores = []
    identificadores_vistos = set()
    duplicados = []
    invalidos = []

    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.reader(archivo, skipinitialspace=True)

        encabezado = next(lector, None)

        if encabezado is None or [campo.strip() for campo in encabezado] != [
            "id_cuenta"
        ]:
            raise ValueError(
                "El CSV debe tener el encabezado id_cuenta."
            )

        for fila in lector:
            numero_linea = lector.line_num

            # Ignorar líneas vacías o con espacios solamente.
            if not fila or all(not campo.strip() for campo in fila):
                continue

            # Este proceso espera exactamente una columna por registro.
            if len(fila) != 1:
                invalidos.append({
                    "linea": numero_linea,
                    "valor": str(fila),
                    "causa": "FORMATO_INVALIDO",
                })
                continue

            valor_original = fila[0].strip()

            # Tolerar comillas alrededor del valor si hay espacios
            # antes de las comillas en el archivo recibido.
            if (
                len(valor_original) >= 2
                and valor_original[0] == '"'
                and valor_original[-1] == '"'
            ):
                valor_original = valor_original[1:-1].strip()

            # Aceptar únicamente números enteros positivos.
            if not valor_original.isascii() or not valor_original.isdigit():
                invalidos.append({
                    "linea": numero_linea,
                    "valor": valor_original,
                    "causa": "ID_NO_NUMERICO",
                })
                continue

            id_cuenta = int(valor_original)

            if id_cuenta <= 0:
                invalidos.append({
                    "linea": numero_linea,
                    "valor": valor_original,
                    "causa": "ID_NO_POSITIVO",
                })
                continue

            # Normalizar el identificador para detectar duplicados.
            if id_cuenta in identificadores_vistos:
                duplicados.append({
                    "linea": numero_linea,
                    "id_cuenta": id_cuenta,
                })
                continue

            identificadores_vistos.add(id_cuenta)
            identificadores.append(id_cuenta)

    return identificadores, duplicados, invalidos


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de entrada: {CSV_PATH}"
        )

    identificadores, duplicados, invalidos = leer_y_validar_csv(CSV_PATH)

    print("\n--- RESUMEN DE LECTURA Y VALIDACIÓN ---")
    print(f"IDs únicos válidos: {len(identificadores)}")
    print(f"Duplicados detectados: {len(duplicados)}")
    print(f"Registros inválidos: {len(invalidos)}")

    print("\nIDs válidos:")
    print(identificadores)

    print("\nDuplicados:")
    for duplicado in duplicados:
        print(duplicado)

    print("\nInválidos:")
    for invalido in invalidos:
        print(invalido)


if __name__ == "__main__":
    main()
