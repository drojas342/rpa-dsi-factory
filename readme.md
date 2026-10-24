 
# Proceso RPA — Consolidado de cuentas médicas

Proceso automatizado que lee un CSV diario de cuentas médicas, consulta cada identificador contra un sistema externo y genera un Excel consolidado para el equipo de auditoría. Se ejecuta de madrugada, sin supervisión.

---

## ¿He usado Python?

Mi stack principal es **Node.js/Express**. Este reto es mi primera experiencia aplicando Python a un proceso de automatización. Anteriormente había usado Python para ejercicios de lógica de programación, pero no para tareas como manipulación de CSV, generación de Excel, consultas HTTP con reintentos o persistencia de estado entre ejecuciones. Recientemente completé el curso **Python Essentials 1** de Cisco Networking Academy, que me proporcionó una base inicial en el lenguaje: https://www.credly.com/badges/d0dfe708-6728-458b-8387-285fcac3f50e/public_url


---

## Qué hace

1. Lee `cuentas.csv` **tal como llega**, incluyendo espacios, comillas, líneas en blanco y datos no válidos.
2. Consulta cada identificador contra `https://jsonplaceholder.typicode.com/posts/{id}`.
3. Genera `output/reporte_cuentas.xlsx` con el resultado correspondiente a cada línea del CSV.
4. Es **re-ejecutable**: si se ejecuta dos veces seguidas, la segunda no vuelve a consultar los identificadores con resultados definitivos ni duplica filas en el Excel. Si el proceso se interrumpe a mitad de ejecución, puede retomarse desde el estado guardado.

---

## Cómo se ejecuta

```bash
pip install -r requirements.txt
python src/main.py
```

El proceso imprime progreso en consola y escribe el detalle en `logs/ejecucion.log`. Al final muestra un resumen agrupado por causa.

## Qué necesita instalado

Python 3.9+

Dependencias de `requirements.txt`:

- `requests` — cliente HTTP.
- `openpyxl` — escritura del Excel.
- `python-dotenv` — lectura del archivo `.env`.

> **Nota para Windows**: si al ejecutar `python -m pip --version` aparece `No module named pip`, el intérprete de Python no tiene `pip` instalado. Se puede instalar con `python -m ensurepip --upgrade`. Después de eso, `python -m pip install -r requirements.txt` funcionará.

## Estructura del proyecto

```text
# Archivos del repo:
.
├── main.py                    # Orquestador
├── leer_y_validar_csv.py      # Lectura y validación del CSV
├── consultar_id.py            # Consulta HTTP con reintentos
├── estados.py                 # Persistencia del estado (idempotencia)
├── generar_excel.py           # Generación del Excel de salida
├── configuracion_logs.py      # Configuración de logging
├── cuentas.csv                # Archivo de entrada
├── requirements.txt
├── .env.example               # Plantilla de configuración
├── .gitignore
├── README.md
└── BITACORA.md

# Carpetas generadas en ejecución (creadas con mkdir):
├── data/                      # Estado persistente
│   └── estado.json
├── logs/                      # Log de ejecución
│   └── ejecucion.log
└── output/                    # Excel de salida
    └── reporte_cuentas.xlsx
```

Las carpetas `data/`, `logs/` y `output/` se crean solas con `mkdir(parents=True, exist_ok=True)` en la primera ejecución.

## Configuración

Los parámetros del proceso se definen en un archivo `.env`, creado a partir de `.env.example`.

| Variable | Valor predeterminado | Descripción |
|---|---|---|
| `API_URL` | `https://jsonplaceholder.typicode.com/posts` | URL base de la API |
| `API_TIMEOUT` | `10` | Tiempo máximo de espera por petición, en segundos |
| `API_MAX_INTENTOS` | `3` | Número máximo de intentos por identificador |
| `API_ESPERA_BASE` | `1` | Tiempo base del backoff exponencial, en segundos |

Los parámetros se validan al inicio:

- `API_TIMEOUT > 0`
- `API_MAX_INTENTOS >= 1`
- `API_ESPERA_BASE >= 0`

Si alguno de estos valores no cumple las condiciones, el proceso falla con un `ValueError` antes de realizar consultas.

## Decisiones tomadas

### Duplicados

El CSV contiene identificadores repetidos, como `7, 12, 7`.

La decisión de diseño es consultar una sola vez cada identificador único. El primer registro con ese identificador se consulta y su resultado se guarda en el estado. Los registros posteriores reutilizan el resultado guardado, sin realizar nuevas llamadas a la API.

En el Excel, cada línea del CSV aparece con su propio `linea_csv` y `valores_recibidos`, aunque los registros con el mismo identificador compartan el resultado de la consulta.

¿Por qué se hace así? Consultar el mismo identificador varias veces contra la misma API durante una ejecución desperdicia tiempo y recursos. Además, conservar cada línea en el Excel permite al auditor verificar qué datos llegaron, mientras que el estado permite identificar qué consultas ya se realizaron.

**Diferencia entre "omitidos" y "duplicados" en el resumen:**

- `IDs omitidos`: identificadores que ya estaban en el estado de una ejecución anterior y no se volvieron a consultar.
- `Duplicados`: líneas del CSV que repiten un identificador ya visto en este mismo CSV.

Son dos conceptos distintos. En la primera ejecución, `omitidos = 0` y `duplicados = 3`. En la segunda, `omitidos = 16` (los ids únicos ya resueltos) y `duplicados = 3` (los mismos duplicados del CSV).

### Limpieza de identificadores: `valores_recibidos` vs. `valores_limpios`

El CSV llega con espacios (` 23`) y comillas (`"42"`).

El proceso limpia el valor antes de consultarlo, pero conserva el contenido original en el Excel.

- `valores_recibidos`: la línea completa tal como llegó en el CSV, sin el carácter de salto de línea.
- `valores_limpios`: el identificador entero que se consultó, o una celda vacía si no fue posible limpiarlo.

¿Por qué limpiar en lugar de rechazar? El objetivo es procesar el CSV tal como llega. Rechazar ` 23` sería no lidiar con él. Limpiar y conservar el original permite procesar los datos sin perder evidencia de su formato de entrada.

¿Por qué conservar el original? Si el archivo comienza a llegar con espacios, comillas u otros problemas de formato de manera sistemática, el operador puede detectarlo comparando `valores_recibidos` con `valores_limpios`. Sin ambas columnas, la limpieza sería invisible.

### El identificador 0 y los valores inválidos

- `0`: es un entero sintácticamente válido y se consulta. Si la API responde con HTTP 404, queda como `NO_ENCONTRADO`, con causa `ID_INEXISTENTE`.
- Identificadores negativos: se consideran inválidos (`ID_NEGATIVO`). No se consulta la API porque el proceso no espera que existan identificadores negativos.
- Valores no numéricos: un valor como `abc` se clasifica como `ID_NO_NUMERICO`.
- Filas con más de una columna: una entrada como `7,foo` se clasifica como `FORMATO_INVALIDO`.

### Política de reintentos (`consultar_id.py`)

Se reintentan únicamente los errores que podrían resolverse con otro intento.

| Error o respuesta | Clasificación | ¿Se reintenta? |
|---|---|---|
| `requests.exceptions.Timeout` | `TIMEOUT` | Sí |
| `requests.exceptions.ConnectionError` | `ERROR_CONEXION` | Sí |
| HTTP 429 | `HTTP_429` | Sí |
| HTTP 5xx | `HTTP_5xx` | Sí |
| HTTP 404 | `NO_ENCONTRADO` | No |
| HTTP 4xx distinto de 404 | `ERROR_NEGOCIO` | No |
| `JSONDecodeError` | `JSON_INVALIDO` | No |
| Respuesta 2xx que no contiene un objeto JSON | `RESPUESTA_NO_ES_OBJETO` | No |

Los errores HTTP 4xx distintos de 404, como 400, 401, 403 y 422, suelen indicar problemas de credenciales, permisos o contrato. Repetir la misma petición no suele resolverlos.

Una respuesta HTTP 200 cuyo contenido no sea JSON válido puede indicar una respuesta inesperada, por ejemplo, de un proxy o portal de red. Por eso se clasifica como `JSON_INVALIDO`.

Una respuesta 2xx que no sea un objeto JSON se clasifica como `RESPUESTA_NO_ES_OBJETO` para proteger el proceso frente a cambios en el contrato de la API.

El tiempo de espera entre intentos sigue la fórmula:

```text
ESPERA_BASE * 2^(intento - 1)
```

Con `API_ESPERA_BASE=1` y `API_MAX_INTENTOS=3`, hay 3 intentos totales y, por lo tanto, 2 esperas entre intentos:

- Espera tras el primer intento fallido: 1 segundo.
- Espera tras el segundo intento fallido: 2 segundos.
- Total acumulado de espera: 3 segundos.

Si se configurara `API_MAX_INTENTOS=4`, habría 3 esperas (1, 2 y 4 segundos) para un total de 7 segundos. La espera crece exponencialmente para darle tiempo a la API a recuperarse sin saturarla con reintentos inmediatos.

### Estados de salida

Estos son los estados que puede devolver `consultar_id`, y por qué cada uno se reintenta o no en la siguiente ejecución:

| Estado | Significado | Comportamiento en ejecuciones futuras |
|---|---|---|
| `RESUELTO` | La API devolvió el objeto esperado. | Se reutiliza el resultado guardado. |
| `NO_ENCONTRADO` | La API respondió con HTTP 404. | Se omite la consulta. |
| `ERROR_NEGOCIO` | La API rechazó la petición con HTTP 4xx distinto de 404. | Se omite hasta corregir la causa. |
| `ERROR_TECNICO` | Se agotaron los intentos por errores técnicos o respuestas inesperadas. | Se vuelve a intentar en una ejecución futura. |
| `FORMATO_INVALIDO` | La fila contiene un formato no admitido. | No se consulta la API. |
| `ID_NO_NUMERICO` | El identificador no es numérico. | No se consulta la API. |
| `ID_NEGATIVO` | El identificador es negativo. | No se consulta la API. |

## Idempotencia (`estados.py`)

El archivo `data/estado.json` guarda el resultado de cada identificador procesado.

### Escritura atómica

El proceso escribe primero en `estado.tmp` y después utiliza `.replace()` para sustituir `estado.json`. De esta forma, si el proceso se interrumpe mientras escribe el archivo temporal, el estado anterior permanece intacto y no se sustituye por un JSON incompleto.

### Persistencia por identificador

El estado se guarda después de procesar cada identificador, en lugar de esperar hasta el final. Así, si el proceso se interrumpe, el archivo conserva los resultados guardados hasta el último identificador procesado.

### Validación al cargar

Al cargar el estado, se comprueba que:

- El contenido sea un diccionario.
- Cada resultado sea también un diccionario.
- Cada resultado contenga los campos `estado`, `datos` y `causa`.
- El estado pertenezca a los valores conocidos.

Si la validación falla, `estados.py` lanza `RuntimeError` con el motivo, `main.py` lo registra en el log con traceback, y el proceso termina sin consultar nada. El runbook (Paso 3) dice cómo recuperarse: backup, borrar el estado, relanzar.

### Supuesto de concurrencia

El proceso asume que solo se ejecuta una instancia a la vez. No se implementa bloqueo de archivos porque el diseño previsto es una ejecución secuencial durante la madrugada.

## Excel: una fila por línea del CSV

El archivo generado es `output/reporte_cuentas.xlsx`.

Contiene una fila por cada línea útil del CSV, incluidos los registros válidos, duplicados e inválidos.

### Columnas

| Columna | Contenido |
|---|---|
| `linea_csv` | Número de línea física del archivo para localizar el registro original. |
| `valores_recibidos` | Línea completa tal como llegó. |
| `valores_limpios` | Identificador entero consultado. |
| `estado` | Resultado del procesamiento o motivo por el que no se realizó la consulta. |
| `userId` | Valor devuelto por la API, si se resolvió. |
| `title` | Título devuelto por la API, si se resolvió. |
| `body` | Contenido devuelto por la API, si se resolvió. |
| `causa` | Motivo del error o campo vacío si no aplica. |

Las columnas responden a dos necesidades:

- **Auditoría diaria:** consulta `valores_limpios` y `estado`.
- **Diagnóstico operativo:** consulta `valores_recibidos` y `causa`.

El Excel se regenera completamente en cada ejecución a partir del estado y de las líneas del CSV. Por eso, volver a ejecutar el proceso no añade filas duplicadas al reporte.

## Evidencia de idempotencia

### Primera ejecución: estado vacío

```text
--- RESUMEN DE EJECUCIÓN ---
Líneas procesadas del CSV: 20
Consultas realizadas: 16
IDs omitidos por tener resultado definitivo: 0
Resueltos: 16
No encontrados: 3
Errores de negocio: 0
Errores técnicos: 0
Registros inválidos: 1
Duplicados: 3
Reporte Excel: generado correctamente
```

### Segunda ejecución: sin borrar el estado

```text
--- RESUMEN DE EJECUCIÓN ---
Líneas procesadas del CSV: 20
Consultas realizadas: 0
IDs omitidos por tener resultado definitivo: 16
Resueltos: 16
No encontrados: 3
Errores de negocio: 0
Errores técnicos: 0
Registros inválidos: 1
Duplicados: 3
Reporte Excel: generado correctamente
```

### Interpretación

- **Consultas realizadas: 0.** Ningún identificador se volvió a consultar porque los 16 identificadores únicos ya tenían resultados definitivos guardados.
- **IDs omitidos: 16.** Corresponden a los 16 identificadores únicos con resultados definitivos. Los 3 registros duplicados del CSV no se cuentan como omitidos: se cuentan en la línea `Duplicados: 3`. Son dos conceptos distintos: "omitido" es un id que ya estaba en el estado de una ejecución anterior; "duplicado" es una línea del CSV con un id ya visto en este mismo CSV.
- **Excel:** conserva las mismas 20 filas de registros que la primera ejecución. El reporte se regenera completo, sin duplicar filas.

### Tercera ejecución: simulación de una interrupción

Si el proceso se interrumpe a mitad de ejecución, por ejemplo, por una caída de red, un apagón o una interrupción manual, `estado.json` conserva los resultados guardados hasta el último identificador procesado.

Al volver a ejecutar `python src/main.py`, los identificadores con resultados definitivos se omiten y se consultan los que todavía necesitan procesamiento.

El Excel se regenera al finalizar correctamente la ejecución.

## Runbook: qué hacer si falla a las 3 a. m.

### Paso 1. Revisar el log

```bash
tail -100 logs/ejecucion.log
```

El archivo permite consultar el detalle de la ejecución. Busca las líneas `ERROR` y `WARNING` para identificar los problemas por identificador.

### Paso 2. Diagnosticar según el patrón

| Síntoma en el resumen | Causa probable | Acción recomendada |
|---|---|---|
| Muchos `ERROR_TECNICO` con `TIMEOUT` o `ERROR_CONEXION` | Red caída o API lenta. | Verificar la conectividad y volver a ejecutar cuando se restablezca. |
| Muchos `ERROR_TECNICO` con `HTTP_500` o `HTTP_503` | API caída o con problemas. | Verificar el estado del servicio y volver a ejecutar cuando se recupere. |
| Muchos `ERROR_TECNICO` con `HTTP_429` | Límite de solicitudes alcanzado. | Esperar unos minutos y volver a ejecutar. Revisar la política de reintentos. |
| Muchos `ERROR_NEGOCIO` con `HTTP_401` o `HTTP_403` | Problemas de credenciales o permisos. | Revisar las credenciales y los permisos del proveedor antes de volver a ejecutar. |
| Muchos `NO_ENCONTRADO` | CSV incorrecto o identificadores inexistentes. | Verificar que el archivo de entrada sea el correcto. |
| Muchos `ID_NO_NUMERICO` o `FORMATO_INVALIDO` | Archivo CSV de origen con problemas. | Revisar el archivo y corregir los registros inválidos en el origen. |
| `RuntimeError: No se pudo leer el archivo de estado` | Archivo `estado.json` corrupto o inválido. | Seguir el Paso 3. |
| `RuntimeError: No se pudo guardar el reporte Excel` | Problemas de permisos o acceso al directorio de salida. | Verificar los permisos de `output/` y que el archivo Excel no esté bloqueado. |
| `FileNotFoundError: No se encontró el archivo de entrada` | Falta `cuentas.csv`. | Verificar que el archivo esté en la raíz del proyecto. |

### Paso 3. Recuperar un estado corrupto

Antes de eliminar el estado, conserva una copia de seguridad.

En Linux o macOS:

```bash
cp data/estado.json data/estado.json.bak
rm data/estado.json
python src/main.py
```

En Windows PowerShell:

```powershell
Copy-Item data/estado.json data/estado.json.bak
Remove-Item data/estado.json
python src/main.py
```

**Importante:** al eliminar el estado se pierde el historial de resultados definitivos guardados. El proceso volverá a consultar los identificadores desde cero, incluidos los que ya se habían resuelto. Esto puede generar consultas adicionales, por lo que conviene verificar primero si es posible recuperar el archivo original.

### Paso 4. Volver a ejecutar el proceso

```bash
python src/main.py
```

No es necesario borrar otros archivos. El proceso reutiliza los resultados definitivos guardados e intenta nuevamente los que quedaron con errores técnicos.

Si la ejecución anterior terminó correctamente y todos los identificadores tienen resultados definitivos, la nueva ejecución no realizará consultas y regenerará el Excel.

Si estado.json existe pero está vacío: es un archivo corrupto. El proceso falla al inicio con RuntimeError: No se pudo leer el archivo de estado. Sigue el Paso 3: backup, borrar, relanzar. La escritura atómica garantiza que el proceso nunca deja estado.json vacío; si está vacío, algo externo lo truncó

## Qué quedó pendiente

### Tests unitarios con pytest

Los tests automatizados no se implementaron dentro del tiempo disponible para el reto. `pytest` sería una opción para cubrir los siguientes módulos:

- `leer_y_validar_csv.py`: espacios, comillas, líneas vacías e identificadores inválidos. 
- `estados.py`: persistencia del estado, validación y escritura atómica.
- `generar_excel.py`: estructura del libro, encabezados y número de filas.

### Hoja de incidencias en el Excel

Actualmente, los registros inválidos y duplicados aparecen en la hoja principal con su estado correspondiente. Una hoja separada de incidencias podría facilitar el trabajo del auditor, aunque no forma parte de los requisitos implementados.

 
## Cómo verificar que funciona

### 1. Primera ejecución: estado vacío

En Linux o macOS:

```bash
rm -f data/estado.json
python src/main.py
```

En Windows PowerShell:

```powershell
Remove-Item data/estado.json -ErrorAction SilentlyContinue
python src/main.py
```

Resultado esperado:

- Consultas realizadas: 16.
- IDs omitidos: 0.

### 2. Segunda ejecución: comprobar la idempotencia

```bash
python src/main.py
```

Resultado esperado:

- Consultas realizadas: 0.
- IDs omitidos: 16.

### 3. Verificar que el Excel no contiene filas duplicadas por reejecución

```bash
python -c "from openpyxl import load_workbook; wb = load_workbook('output/reporte_cuentas.xlsx'); print(wb.active.max_row)"
```

Resultado esperado:

```text
21
```

El resultado incluye una fila de encabezados y 20 filas de registros.

## Consideraciones

- El proceso utiliza JSONPlaceholder como API de prueba. No es un servicio real de cuentas médicas ni debe utilizarse para transmitir datos médicos reales.
- La recuperación depende de que el estado se haya guardado correctamente después de cada identificador.
- La ejecución concurrente no está contemplada.
- Los tests unitarios y la hoja independiente de incidencias quedan como mejoras futuras.
