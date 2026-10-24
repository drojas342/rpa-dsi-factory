# Bitácora

## 1. Herramienta de IA usada

Usé ChatGPT de forma simultánea mientras escribía el código. No la usé para generar la solución completa de una vez, sino para:

- Planificar el reto de forma incremental (el prompt del punto 2).
- Resolver partes que no había hecho con Python: manipular archivos CSV y Excel en Python, y persistir estado entre ejecuciones.
- Revisar el código contra los requisitos del enunciado.
- Confirmar y corregir fragmentos puntuales, y explicar qué hacía cada parte.

No usé IA para las decisiones de diseño (duplicados, limpieza, frontera de reintentos, estructura del Excel). Esas las tomé yo y están en el punto 4.

## 2. Prompts que me sirvieron

### Prompt 1 — Planificación incremental

> Quiero que me ayudes a planificar este reto de forma incremental, es decir, crear un paso a paso que me ayude a construir la solución de forma incremental para cumplir con el objetivo propuesto.

Este prompt me dio el esqueleto del proyecto: qué archivos crear, en qué orden, y qué responsabilidad tiene cada uno. Sin él habría empezado por `main.py` y me habría enredado.

### Prompt 2 — Revisión contra requisitos

> Revisa el código y verifica que cumpla con los requerimientos propuestos.

Este prompt me sirvió para detectar que faltaban cosas. La IA, al revisar contra el enunciado, señaló varios huecos (por ejemplo, que no estaba manejando el caso de respuesta 2xx que no fuera un objeto JSON). No todos los huecos los acepté, pero el ejercicio de revisar contra la lista de requisitos me obligó a mirar el código con ojos de evaluador.

### Prompt 3 — Explicaciones puntuales (no copiado tal cual, fueron varios)

Durante el desarrollo le pedí explicaciones de fragmentos específicos: cómo funciona `csv.reader`, cómo se hace una escritura atómica en Python, cómo se calcula el backoff exponencial, por qué `isdigit()` acepta dígitos Unicode. No fueron prompts largos ni elaborados, fueron preguntas concretas sobre partes que no conocía.

## 3. Algo que la IA entregó mal o incompleto

Estos son los errores que encontré al revisar el código de la IA.

### Error 1 — La IA descartaba el 0 como inválido

La IA generó:

```python
if id_cuenta <= 0:
    invalidos.append({"causa": "ID_NO_POSITIVO", ...})
```

El CSV del enunciado trae un 0. Con esa condición, el 0 se descartaba como inválido y nunca se consultaba. El enunciado dice "por cada identificador consulta". El 0 es sintácticamente un entero válido.

**Cómo lo detecté:** revisé el CSV contra el código. Vi el 0 en la línea 21 y me pregunté "¿qué pasa con este?". Al leer la condición, me di cuenta de que nunca llegaba a la API.

**Qué hice:** cambié `<= 0` a `< 0`. Solo los negativos son inválidos. El 0 se consulta, la API responde 404 y queda como `NO_ENCONTRADO`, causa `ID_INEXISTENTE`.

### Error 2 — La IA no validaba que la respuesta de la API fuera un objeto

La IA generaba:

```python
datos = respuesta.json()
return {"estado": "RESUELTO", "datos": datos, ...}
```

Asumía que `respuesta.json()` siempre devuelve un diccionario. Pero `json()` puede devolver una lista, un string, un número o `None`. En `generar_excel.py`, la línea `datos.get("userId")` reventaría con `AttributeError` si `datos` no fuera un dict. Eso viola el requisito "ningún identificador que falle puede detener el proceso".

**Cómo lo detecté:** revisando el flujo entre `consultar_id.py` y `generar_excel.py`. `generar_excel` hace `datos.get(...)`; eso asume dict. Si `consultar_id` no garantiza dict, el contrato entre los dos módulos está roto.

**Qué hice:** agregué `isinstance(datos, dict)` en `consultar_id.py`. Si no es un dict, devuelvo `ERROR_TECNICO` con causa `RESPUESTA_NO_ES_OBJETO`.

  
### Error 3 — La IA no validaba que el estado cargado tuviera valores conocidos

En `estados.py`, la IA validaba que el JSON fuera un dict de dicts y que cada resultado tuviera los campos `estado`, `datos` y `causa`. Pero no validaba que `estado` fuera uno de los tres valores conocidos (`RESUELTO`, `NO_ENCONTRADO`, `ERROR_TECNICO`).

Cómo lo detecté: probé mentalmente qué pasaría si alguien edita estado.json a mano y deja "estado": "RESUELTOX". El proceso lo cargaría, main.py lo trataría como "no es RESUELTO ni NO_ENCONTRADO" y re-consultaría el id sin necesidad. El JSON se corrompe silenciosamente y el proceso hace trabajo de más.

Agregué la validación:

```python
if resultado["estado"] not in estados_validos:
    raise ValueError(...)
```

Una línea. Si el JSON está corrupto, el proceso falla ruidosamente al inicio, no a la mitad re-consultando ids sin razón.

## 4. Qué decidí yo sin consultarle

**Limpiar los identificadores en vez de rechazarlos.** La IA me proponía descartar `' 23'` y `'"42"'` como inválidos. Decidí limpiarlos y conservar el original en una columna `valores_recibidos`, para que el auditor vea qué llegó y qué se consultó. El enunciado dice "lidiar con el CSV tal como llega"; rechazar sería no lidiar con él.

**Dos columnas en el Excel: `valores_recibidos` y `valores_limpios`.** La IA proponía solo el id limpio. Decidí conservar las dos columnas pensando en el usuario que va a revisar el Excel.

- `valores_recibidos` le muestra qué llegó en el CSV.
- `valores_limpios` le muestra qué se procesó después de la limpieza.

Con las dos columnas, el usuario puede comparar y darse cuenta de por qué un id no fue procesado (por ejemplo: abc en valores_recibidos con valores_limpios vacío, o ' 23' con 23), corregir los datos de entrada si es necesario, y volver a procesar. Sin las dos columnas, la limpieza sería invisible y el usuario no sabría si el problema está en el CSV o en el proceso.

**Excel regenerado completo en vez de agregar filas.** La IA proponía ir escribiendo fila por fila. Decidí regenerar el Excel completo desde `estado.json` al final.

**`ERROR_NEGOCIO` como estado nuevo.** La IA trataba todos los 4xx como `ERROR_TECNICO`. Decidí separar 401/403 (credenciales) de 500 (red) porque la acción del operador es distinta. En el runbook de las 3 a. m. esa diferencia importa. 
