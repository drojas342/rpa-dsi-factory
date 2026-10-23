import csv


def leer_y_validar_csv(ruta):
    """
    Devuelve una lista de registros, uno por cada línea útil del CSV.
    Cada registro tiene:
      - linea: número de línea física del archivo
      - valores_recibidos: la línea completa tal como llegó (sin \n)
      - valores_limpios: entero limpio que se consulta, o None
      - estado: "PENDIENTE" | "FORMATO_INVALIDO" | "ID_NO_NUMERICO" | "ID_NEGATIVO"
      - duplicado_de: número de línea del primer registro con ese id, o None
    """
    registros = []
    primer_registro_por_id = {}

    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lineas_crudas = archivo.read().splitlines()

    lector = csv.reader(lineas_crudas, skipinitialspace=True)

    encabezado = next(lector, None)

    if encabezado is None:
        raise ValueError("El CSV no tiene encabezado. Se esperaba 'id_cuenta'.")

    encabezado_normalizado = [campo.strip() for campo in encabezado]
    if encabezado_normalizado != ["id_cuenta"]:
        raise ValueError(
            f"El CSV debe tener el encabezado 'id_cuenta'. Encontrado: {encabezado}"
        )

    for indice, fila in enumerate(lector):
        numero_linea = indice + 2
        fila_cruda = lineas_crudas[indice + 1] if indice + 1 < len(lineas_crudas) else ""

        # Ignorar líneas vacías ([]).
        if not fila:
            continue

        # Ignorar líneas donde todos los campos están vacíos o con espacios.
        fila_vacia = True
        for campo in fila:
            if campo.strip() != "":
                fila_vacia = False
                break
        if fila_vacia:
            continue

        if len(fila) != 1:
            registros.append({
                "linea": numero_linea,
                "valores_recibidos": fila_cruda,
                "valores_limpios": None,
                "estado": "FORMATO_INVALIDO",
                "duplicado_de": None,
            })
            continue

        valor_original = fila[0]
        valor_limpio = valor_original.strip()

        if (
            len(valor_limpio) >= 2
            and valor_limpio[0] == '"'
            and valor_limpio[-1] == '"'
        ):
            valor_limpio = valor_limpio[1:-1].strip()

        if not valor_limpio.isascii() or not valor_limpio.isdigit():
            registros.append({
                "linea": numero_linea,
                "valores_recibidos": fila_cruda,
                "valores_limpios": None,
                "estado": "ID_NO_NUMERICO",
                "duplicado_de": None,
            })
            continue

        id_cuenta = int(valor_limpio)

        if id_cuenta < 0:
            registros.append({
                "linea": numero_linea,
                "valores_recibidos": fila_cruda,
                "valores_limpios": id_cuenta,
                "estado": "ID_NEGATIVO",
                "duplicado_de": None,
            })
            continue

        if id_cuenta in primer_registro_por_id:
            registros.append({
                "linea": numero_linea,
                "valores_recibidos": fila_cruda,
                "valores_limpios": id_cuenta,
                "estado": "DUPLICADO",
                "duplicado_de": primer_registro_por_id[id_cuenta],
            })
            continue

        primer_registro_por_id[id_cuenta] = numero_linea
        registros.append({
            "linea": numero_linea,
            "valores_recibidos": fila_cruda,
            "valores_limpios": id_cuenta,
            "estado": "PENDIENTE",
            "duplicado_de": None,
        })

    return registros