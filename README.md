
# RepetiDesk IA
## Detector de Incidentes Repetidos de Helpdesk

Proyecto integrador AIENG01 - Sesión 9

### Descripción

RepetiDesk IA es un agente de inteligencia artificial que identifica posibles incidentes repetidos en una mesa de ayuda (Helpdesk).

El proyecto está inspirado en las necesidades de soporte técnico de una empresa del sector logístico y utiliza únicamente datos simulados.

Fue desarrollado reutilizando componentes de los laboratorios L3, L4, L6, L7 y L8 del curso AI Engineer con Claude.

## El caso

### ¿Quién lo usa?

Los técnicos de Helpdesk de una empresa logística que necesitan identificar reportes relacionados con fallas de sistemas, impresoras y conectividad.

### ¿Qué le pide el usuario?

Analizar los tickets registrados e identificar posibles incidentes repetidos según el sistema afectado, la ubicación y la descripción del problema.

### ¿Cómo sabemos que lo resolvió?

El agente identifica los tickets que presentan síntomas similares, genera grupos de posibles incidentes relacionados y explica los motivos de agrupación.

No confirma una causa raíz sin evidencia técnica.

### Ejemplo

Pregunta:

¿Qué incidentes repetidos hay en Helpdesk?

Respuesta esperada:

- Inventarios, Bodega Bogotá: T001, T002, T003, T015.
- Impresoras, Bodega Bogotá: T004, T005.
- Red, Bodega Cali: T007, T008.

Resultado: 3 grupos con 8 tickets posiblemente relacionados.

## Arquitectura

El sistema utiliza Claude Agent SDK y un servidor MCP propio.

Flujo:

Usuario
  |
Guardrail de entrada
  |
Agente principal (Claude Haiku 4.5)
  |
  +-- Servidor MCP RepetiDesk
  |     |
  |     +-- listar_tickets
  |     +-- consultar_ticket
  |     +-- datos/tickets.json
  |
  +-- Subagente verificador
        |
        +-- Analiza la similitud
        +-- Verifica grupos candidatos
        +-- Consulta MCP si faltan datos
  |
Guardrail de salida
  |
Respuesta al usuario

### Servidor MCP

El servidor está implementado en server.py mediante FastMCP y reutiliza la estructura de los laboratorios L3 y L4.

Herramientas:

1. listar_tickets: consulta incidentes y permite filtrarlos por sistema y ubicación.
2. consultar_ticket: devuelve el detalle de un ticket específico.

Los datos se almacenan en datos/tickets.json.

El servidor utiliza datos simulados y no modifica tickets.

### Agente principal

Está implementado en agente.py usando Claude Agent SDK.

Se encarga de consultar los incidentes, identificar posibles grupos y solicitar su verificación.

### Subagente verificador

Se implementó mediante AgentDefinition, reutilizando el patrón del laboratorio L6.

Su función es comprobar si los incidentes candidatos presentan similitud funcional.

Se utiliza un subagente para separar el análisis inicial de la revisión de los grupos y reducir el riesgo de conclusiones incorrectas.

El verificador no confirma causas raíz ni modifica tickets.

## Video de demostración

Demostración del funcionamiento de RepetiDesk IA,
incluyendo el servidor MCP, subagente verificador,
guardrails, evaluaciones y optimización de costos.

https://youtu.be/anUUjNhzy6g

## Cómo correrlo

El proyecto funciona en el Cloud Workspace del curso, con Claude mediante Amazon Bedrock.

No requiere crear infraestructura adicional en AWS.

### 1. Abrir el proyecto

```bash
cd /workshop/aieng01/lab-09-capstone/workspace
```

### 2. Verificar los datos

```bash
python -c "from server import _load; print(len(_load()))"
```

Resultado esperado: 15 tickets.

### 3. Comprobar las herramientas MCP

```bash
python -c "import asyncio; from server import mcp; print([t.name for t in asyncio.run(mcp.list_tools())])"
```

Herramientas esperadas:

- consultar_ticket
- listar_tickets

El servidor MCP se inicia automáticamente mediante Claude Agent SDK. No es necesario ejecutarlo manualmente para usar el agente.

### 4. Ejecutar el agente

```bash
python agente.py "¿Qué incidentes repetidos hay en Helpdesk?"
```

### 5. Ejecutar con guardrails, trazas y costos

```bash
python adaptador.py "¿Qué incidentes repetidos hay en Helpdesk?"
```

### 6. Ejecutar evaluaciones

```bash
python evals.py --etiqueta optimizado
```

### 7. Consultar una traza

```bash
python ver_traza.py
```

### 8. Autoverificación

```bash
python3 /workshop/aieng01/lab-09-capstone/verificar.py
```

## Evaluación

Se reutilizó el sistema de evaluaciones del laboratorio L7.

El Golden Set contiene ocho casos, incluidos dos adversariales.

| Caso | Descripción |
|---|---|
| g01 | Incidentes de inventarios |
| g02 | Incidentes de impresoras |
| g03 | Incidentes de conectividad |
| g04 | Evitar agrupaciones incorrectas |
| g05 | Consulta individual de un ticket |
| g06 | Ticket inexistente |
| g07 | Inyección de instrucciones |
| g08 | Protección de datos sensibles |

### Resultados

Evaluación inicial sin guardrails:

4 de 8 pruebas aprobadas (50 %).

Evaluación corregida:

8 de 8 pruebas aprobadas (100 %).

Evaluación optimizada:

8 de 8 pruebas aprobadas (100 %).

Comparación de la versión corregida con la optimizada:

8/8 -> 8/8, sin regresiones observadas.

### Problemas encontrados y correcciones

- g01: el agente separaba un ticket de inventarios que debía considerarse potencialmente relacionado. Se ajustó el criterio de similitud funcional.
- g02: el agente suponía que dos reportes correspondían a la misma impresora física. Se limitaron las afirmaciones sin evidencia.
- g03: el agente sugería una causa raíz compartida sin comprobarla. Se ajustaron las instrucciones de precisión.
- g04: el guardrail producía un falso positivo con expresiones sobre contraseñas. Se corrigió la expresión regular.
- g07: se implementó el bloqueo de inyecciones antes de llamar al modelo.
- g08: se implementó el enmascaramiento de tarjetas y claves antes de llamar al modelo.

Los resultados se conservan en:

- resultados/antes.json
- resultados/despues_v2.json
- resultados/optimizado.json

## Guardrails

Se reutilizó guardrails.py del laboratorio L7.

### Guardrail de entrada

Detecta intentos de cambiar las instrucciones del agente y bloquea las solicitudes sospechosas.

También enmascara números de tarjeta y claves antes de enviarlos al modelo.

Ejemplo:

Entrada:

Mi tarjeta es 4111 1111 1111 1111 y mi clave es 4321. Consulta T001.

Texto enviado a Claude:

Mi tarjeta es [TARJETA] y mi clave [OCULTA]. Consulta T001.

### Guardrail de salida

Comprueba:

- Identificadores de tickets sin respaldo.
- Promesas prohibidas.
- Posibles números de tarjeta.
- Posibles claves expuestas.

Si encuentra información no permitida, sustituye la respuesta por un mensaje seguro.

### Falso positivo identificado

La expresión regular original podía interpretar una referencia normal a una contraseña como si contuviera una clave secreta.

Se corrigió la expresión regular para identificar asignaciones explícitas de claves y permitir consultas legítimas.

### Limitaciones de los guardrails

Las expresiones regulares no detectan todas las variantes posibles de inyección o información sensible. Las protecciones deben complementarse con controles adicionales antes de utilizar el sistema en producción.

## Costo y optimización

Se reutilizó el registro de costos del laboratorio L8 mediante adaptador.py y costing.py.

El agente utiliza Claude Haiku 4.5 mediante Amazon Bedrock.

### Optimización aplicada

Inicialmente, el agente principal consultaba los tickets con listar_tickets y el subagente volvía a consultar individualmente los tickets candidatos.

Se modificaron las instrucciones para transmitir al subagente los datos completos que ya obtuvo el agente principal.

Así, el verificador puede analizar los datos recibidos sin repetir llamadas innecesarias al servidor MCP.

### Comparación de una pregunta

Pregunta:

¿Qué incidentes repetidos hay en Helpdesk?

| Indicador | Antes | Optimizado |
|---|---:|---:|
| listar_tickets | 1 | 1 |
| Agent | 1 | 1 |
| consultar_ticket | 8 | 0 |
| Costo USD | 0.06175 | 0.06028 |

Reducción observada:

- 8 consultas MCP redundantes eliminadas.
- Ahorro de USD 0.00147 por pregunta.
- Reducción observada del costo: aproximadamente 2.38 %.

Estas cifras corresponden a dos ejecuciones de referencia. El ahorro económico requiere más repeticiones para confirmar su estabilidad.

### Proyección a 1.000 preguntas diarias

Utilizando los costos de referencia:

Antes:

USD 61.75 por 1.000 preguntas.

Optimizado:

USD 60.28 por 1.000 preguntas.

Ahorro estimado:

USD 1.47 por cada 1.000 preguntas.

La proyección supone que todas las consultas tienen un costo similar al de la prueba utilizada.

### Evaluación de tokens

Versión corregida: 90.828 tokens.

Versión optimizada: 87.177 tokens.

Reducción observada: 3.651 tokens, aproximadamente 4.02 %.

Las dos versiones aprobaron las ocho evaluaciones.

## Límites

RepetiDesk IA es un proyecto académico desarrollado con información simulada.

Sus principales limitaciones son:

- No está conectado a un sistema real de tickets.
- No confirma causas raíz.
- No identifica necesariamente duplicados exactos.
- No modifica ni cierra incidentes.
- Puede presentar errores cuando las descripciones son ambiguas.
- No utiliza información histórica real.
- Sus protecciones no garantizan detectar todas las amenazas.

### Mejoras futuras

Con una semana adicional de desarrollo se podría:

1. Incorporar una base de datos SQLite.
2. Agregar fecha y hora de cada incidente.
3. Implementar puntuaciones de similitud.
4. Ampliar el Golden Set con casos ambiguos.
5. Mejorar los guardrails de seguridad.
6. Repetir las mediciones para estimar costos de forma más estable.

## Tecnologías

- Python
- Claude Agent SDK
- Claude Haiku 4.5
- Amazon Bedrock
- FastMCP
- JSON
- Guardrails deterministas
- Golden Set y evaluaciones
- Trazas y medición de tokens

## Conclusión

RepetiDesk IA demuestra cómo un agente de inteligencia artificial puede apoyar una mesa de ayuda identificando posibles incidentes repetidos.

El proyecto integra un servidor MCP propio, un agente principal, un subagente verificador, protecciones de entrada y salida, evaluaciones y medición de costos.

La versión optimizada aprobó las ocho pruebas del Golden Set, sin regresiones observadas frente a la versión corregida.
