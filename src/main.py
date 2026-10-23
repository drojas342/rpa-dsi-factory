from pathlib import Path
import logging

from leer_y_validar_csv import leer_y_validar_csv
from consultar_id import consultar_id
from estados import cargar_estado, guardar_estado
from generar_excel import generar_excel
from configuracion_logs import configurar_logging


# Ruta del proyecto, independientemente del directorio desde el que se ejecute.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "cuentas.csv"


def main():
    configurar_logging()

    logging.info("Inicio de ejecución del proceso RPA.")
    print("Configuración de logs activada.")

    try:
        if not CSV_PATH.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo de entrada: {CSV_PATH}"
            )

        registros = leer_y_validar_csv(CSV_PATH)
        estado = cargar_estado()

        consultas_realizadas = 0
        omitidos = 0

        for registro in registros:
            # Solo se consultan registros válidos y no duplicados.
            if registro["estado"] != "PENDIENTE":
                continue

            id_cuenta = registro["valores_limpios"]
            clave = str(id_cuenta)
            resultado_anterior = estado.get(clave)
 
            if (
                resultado_anterior
                and resultado_anterior.get("estado")
                in ("RESUELTO", "NO_ENCONTRADO", "ERROR_NEGOCIO")
            ):
                registro["estado"] = resultado_anterior["estado"]
                registro["datos"] = resultado_anterior.get("datos")
                registro["causa"] = resultado_anterior.get("causa")
                omitidos += 1

                print(f"ID {id_cuenta}: ya procesado, se omite.")
                logging.info(
                    "ID %s omitido: ya tiene un resultado definitivo.",
                    id_cuenta,
                )
                continue

            print(f"Consultando ID {id_cuenta}...")

            resultado = consultar_id(id_cuenta)

            # Guardar el resultado, incluso si ocurrió un error técnico.
            estado[clave] = resultado

            try:
                guardar_estado(estado)
            except RuntimeError:
                logging.exception(
                    "No se pudo guardar el estado del ID %s.",
                    id_cuenta,
                )
                raise

            registro["estado"] = resultado["estado"]
            registro["datos"] = resultado.get("datos")
            registro["causa"] = resultado.get("causa")
            consultas_realizadas += 1

            print(f"ID {id_cuenta}: {resultado['estado']}")

            logging.info(
                "ID %s finalizado con estado %s. Causa: %s",
                id_cuenta,
                resultado["estado"],
                resultado.get("causa"),
            )

            if resultado["estado"] == "ERROR_TECNICO":
                logging.error(
                    "ID %s terminó con error técnico. Causa: %s",
                    id_cuenta,
                    resultado.get("causa"),
                )

        # Resolver duplicados con el resultado del primer registro con ese id.
        for registro in registros:
            if registro["duplicado_de"] is None:
                continue

            id_cuenta = registro["valores_limpios"]
            resultado = estado.get(str(id_cuenta))

            if resultado:
                registro["estado"] = resultado["estado"]
                registro["datos"] = resultado.get("datos")
                registro["causa"] = resultado.get("causa")
            else:
                # no debería ocurrir, pero si ocurre no rompe el proceso.
                registro["estado"] = "ERROR_TECNICO"
                registro["causa"] = "SIN_RESULTADO_PARA_DUPLICADO"
                logging.error(
                    "ID %s duplicado en línea %s sin resultado en el estado.",
                    id_cuenta,
                    registro["linea"],
                )

        # Estadísticas sobre los registros.
        resueltos = sum(
            1 for r in registros if r["estado"] == "RESUELTO"
        )
        no_encontrados = sum(
            1 for r in registros if r["estado"] == "NO_ENCONTRADO"
        )
        errores_negocio = sum(
            1 for r in registros if r["estado"] == "ERROR_NEGOCIO"
        )
        errores_tecnicos = sum(
            1 for r in registros if r["estado"] == "ERROR_TECNICO"
        )
        invalidos = sum(
            1 for r in registros
            if r["estado"] in ("FORMATO_INVALIDO", "ID_NO_NUMERICO", "ID_NEGATIVO")
        )
        duplicados = sum(
            1 for r in registros if r["duplicado_de"] is not None
        )

        # Agrupar por causa los errores técnicos.
        causas_tecnicas = {}
        for r in registros:
            if r["estado"] != "ERROR_TECNICO":
                continue
            causa = r.get("causa") or "CAUSA_NO_ESPECIFICADA"
            causas_tecnicas[causa] = causas_tecnicas.get(causa, 0) + 1

        # Agrupar por causa los errores de negocio (HTTP_400, HTTP_401, etc.).
        causas_negocio = {}
        for r in registros:
            if r["estado"] != "ERROR_NEGOCIO":
                continue
            causa = r.get("causa") or "CAUSA_NO_ESPECIFICADA"
            causas_negocio[causa] = causas_negocio.get(causa, 0) + 1

        # Agrupar por causa los no encontrados (ID_INEXISTENTE, etc.).
        causas_no_encontrado = {}
        for r in registros:
            if r["estado"] != "NO_ENCONTRADO":
                continue
            causa = r.get("causa") or "CAUSA_NO_ESPECIFICADA"
            causas_no_encontrado[causa] = causas_no_encontrado.get(causa, 0) + 1

        # Agrupar por causa los registros inválidos.
        causas_invalidos = {}
        for r in registros:
            if r["estado"] not in ("FORMATO_INVALIDO", "ID_NO_NUMERICO", "ID_NEGATIVO"):
                continue
            causa = r["estado"]
            causas_invalidos[causa] = causas_invalidos.get(causa, 0) + 1

        # Intentar generar el Excel. Si falla, registrar el error y
        # continuar mostrando el resumen de la ejecución.
        reporte_generado = False

        try:
            generar_excel(registros)
            reporte_generado = True
        except Exception:
            logging.exception("No se pudo generar el reporte Excel.")
            print(
                "\nADVERTENCIA: no se pudo generar el reporte Excel. "
                "Consulta el archivo de log para más detalles."
            )

        print("\n--- RESUMEN DE EJECUCIÓN ---")
        print(f"Líneas procesadas del CSV: {len(registros)}")
        print(f"Consultas realizadas: {consultas_realizadas}")
        print(f"IDs omitidos por tener resultado definitivo: {omitidos}")
        print(f"Resueltos: {resueltos}")
        print(f"No encontrados: {no_encontrados}")
        print(f"Errores de negocio: {errores_negocio}")
        print(f"Errores técnicos: {errores_tecnicos}")
        print(f"Registros inválidos: {invalidos}")
        print(f"Duplicados: {duplicados}")
        print(
            "Reporte Excel: "
            + ("generado correctamente" if reporte_generado else "no generado")
        )

        logging.info(
            "Resumen de ejecución: lineas=%s, consultas=%s, omitidos=%s, "
            "resueltos=%s, no_encontrados=%s, errores_negocio=%s, "
            "errores_tecnicos=%s, invalidos=%s, duplicados=%s, reporte_generado=%s",
            len(registros),
            consultas_realizadas,
            omitidos,
            resueltos,
            no_encontrados,
            errores_negocio,
            errores_tecnicos,
            invalidos,
            duplicados,
            reporte_generado,
        )

        print("\nNo encontrados agrupados por causa:")
        if causas_no_encontrado:
            for causa, cantidad in sorted(causas_no_encontrado.items()):
                print(f"- {causa}: {cantidad}")
        else:
            print("- Ninguno")

        logging.info(
            "No encontrados agrupados por causa: %s",
            causas_no_encontrado,
        )

        print("\nErrores de negocio agrupados por causa:")
        if causas_negocio:
            for causa, cantidad in sorted(causas_negocio.items()):
                print(f"- {causa}: {cantidad}")
        else:
            print("- Ninguno")

        logging.info(
            "Errores de negocio agrupados por causa: %s",
            causas_negocio,
        )

        print("\nErrores técnicos agrupados por causa:")
        if causas_tecnicas:
            for causa, cantidad in sorted(causas_tecnicas.items()):
                print(f"- {causa}: {cantidad}")
        else:
            print("- Ninguno")

        logging.info(
            "Errores técnicos agrupados por causa: %s",
            causas_tecnicas,
        )

        print("\nRegistros inválidos agrupados por causa:")
        if causas_invalidos:
            for causa, cantidad in sorted(causas_invalidos.items()):
                print(f"- {causa}: {cantidad}")
        else:
            print("- Ninguno")

        logging.info(
            "Registros inválidos agrupados por causa: %s",
            causas_invalidos,
        )

        if not reporte_generado:
            raise RuntimeError(
                "La ejecución terminó, pero no se pudo generar el reporte Excel."
            )

    except Exception:
        logging.exception("La ejecución del proceso RPA terminó con error.")
        raise

    else:
        logging.info("Fin de ejecución del proceso RPA.")


if __name__ == "__main__":
    main()