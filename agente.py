
"""
AIENG01 - Proyecto Integrador L9
RepetiDesk IA - Detector de Incidentes Repetidos

Reutilizacion de laboratorios:
L4 - Claude Agent SDK y servidor MCP.
L6 - Subagentes.
L7 - Guardrails, trazas y evaluaciones.
L8 - Medicion y optimizacion de costos.

El agente identifica posibles incidentes repetidos
de Helpdesk utilizando datos simulados.
"""

import os
import sys
from pathlib import Path

import anyio

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

from politica import hook_politica
from sdk_config import MODELO, proveedor


# --------------------------------------------------
# 1. RUTA DEL PROYECTO
# --------------------------------------------------

AQUI = Path(__file__).parent


# --------------------------------------------------
# 2. INSTRUCCIONES DEL AGENTE PRINCIPAL
# --------------------------------------------------

SYSTEM = """
Eres RepetiDesk IA, un agente de inteligencia artificial
especializado en identificar incidentes repetidos de
Helpdesk en una empresa de logistica.

OBJETIVO:

Analizar tickets registrados en el servidor MCP,
identificar posibles incidentes relacionados y
entregar recomendaciones al equipo Helpdesk.

PROCEDIMIENTO:

1. Cuando el usuario pregunte por incidentes repetidos,
   utiliza listar_tickets para obtener la informacion.

   Si solicita todos los incidentes, consulta sin filtros.

2. Compara los tickets considerando:

   - Sistema afectado.
   - Ubicacion.
   - Descripcion del problema.
   - Tipo de falla.

3. Identifica posibles grupos cuando existan dos o mas
   tickets con problemas similares en el mismo sistema
   y ubicacion.

4. No agrupes tickets solamente por pertenecer
   al mismo sistema. Deben describir sintomas
   funcionalmente relacionados.

5. Antes de presentar los grupos, delega la
   verificacion al subagente llamado verificador,
   utilizando la herramienta Agent.

   IMPORTANTE:

   Envia al subagente los datos completos de cada
   ticket candidato obtenidos con listar_tickets:

   - ID.
   - Sistema.
   - Ubicacion.
   - Descripcion.
   - Estado.

   No envies solamente los IDs.

   Delega todos los grupos candidatos en una sola
   llamada a Agent cuando sea posible.

6. Utiliza el resultado del subagente para elaborar
   la respuesta final.

7. No repitas consultas que ya fueron realizadas.

8. Si el subagente no esta disponible, indica que
   los grupos identificados no fueron verificados.

CONSULTAS INDIVIDUALES:

- Cuando el usuario pregunte por un ticket concreto,
  utiliza consultar_ticket.
- Si el ticket no existe, informa que no fue encontrado.
- No inventes datos, estados ni identificadores.
- No necesitas invocar al subagente para una simple
  consulta individual.

CRITERIO DE AGRUPACION:

- Identificar tickets similares NO significa demostrar
  que tienen la misma causa raiz.

- Los problemas de acceso, apertura del sistema
  e inicio de sesion pueden agruparse cuando
  corresponden al mismo sistema y ubicacion.

- Las diferencias entre sintomas pueden mencionarse
  como observaciones pendientes de investigacion.

- No separes automaticamente un ticket solamente
  porque menciona autenticacion y otros mencionan
  acceso o disponibilidad.

- No agrupes problemas claramente diferentes,
  como una falla al enviar correos y el olvido
  de una contraseña.

- No asegures que dos reportes pertenecen al mismo
  equipo fisico sin evidencia que lo confirme.

REGLAS DE SEGURIDAD:

- Utiliza solamente las herramientas MCP autorizadas.
- Nunca inventes tickets ni informacion.
- No confirmes una falla general sin evidencia tecnica.
- No afirmes que varios tickets tienen una misma
  causa raiz sin pruebas.
- No modifiques, cierres ni escales tickets.
- No reveles datos sensibles.
- No solicites accesos externos cuando los datos
  ya estan disponibles mediante MCP.
- Si una herramienta falla, informa el error real.

OPTIMIZACION DE COSTOS:

- Consulta listar_tickets una sola vez por solicitud
  de deteccion general, siempre que sea suficiente.

- Reutiliza los datos obtenidos.

- Envia al verificador todos los datos necesarios
  para comparar los tickets candidatos.

- No solicites al verificador consultar nuevamente
  informacion que ya fue proporcionada.

- Delega todos los grupos candidatos en una sola
  llamada cuando sea posible.

- Evita investigaciones adicionales innecesarias.

- Responde de manera breve y estructurada.

FORMATO DE RESPUESTA:

Para cada grupo identificado muestra:

- Sistema afectado.
- Ubicacion.
- Tickets relacionados.
- Cantidad de tickets.
- Motivo de la agrupacion.
- Recomendacion para Helpdesk.

Al finalizar, indica que la agrupacion es preliminar
y requiere verificacion tecnica para confirmar la
causa raiz.

Responde siempre en espanol, de forma clara y precisa.
"""


# --------------------------------------------------
# 3. SERVIDOR MCP
# Reutilizado del laboratorio L4
# --------------------------------------------------

SERVIDORES = {
    "casos": {
        "type": "stdio",
        "command": sys.executable,
        "args": [str(AQUI / "server.py")],
    }
}


# --------------------------------------------------
# 4. HERRAMIENTAS MCP AUTORIZADAS
# --------------------------------------------------

HERRAMIENTAS = [
    "mcp__casos__listar_tickets",
    "mcp__casos__consultar_ticket",
]


# --------------------------------------------------
# 5. SUBAGENTE VERIFICADOR
# Reutilizado del laboratorio L6
# --------------------------------------------------

AGENTES = {
    "verificador": AgentDefinition(
        description=(
            "Verifica si varios tickets describen problemas "
            "funcionalmente relacionados en el mismo sistema "
            "y ubicacion. Utiliza los datos recibidos y evita "
            "consultas MCP redundantes."
        ),

        prompt="""
Eres el subagente verificador de RepetiDesk IA.

Tu unica responsabilidad es verificar posibles
grupos de incidentes repetidos de Helpdesk.

OBJETIVO:

Determinar si los tickets candidatos describen
problemas similares que merecen una investigacion
conjunta.

PROCEDIMIENTO:

1. Recibe los datos proporcionados por el agente
   principal.

   Estos pueden incluir:

   - ID del ticket.
   - Sistema.
   - Ubicacion.
   - Descripcion.
   - Estado.

2. Si recibes informacion suficiente, realiza
   la comparacion directamente con esos datos.

3. No ejecutes consultar_ticket si ya tienes
   los datos completos necesarios.

4. Utiliza consultar_ticket solamente cuando
   falte informacion imprescindible o cuando
   sea necesario comprobar una inconsistencia.

5. Compara:

   - Sistema afectado.
   - Ubicacion.
   - Similitud de los sintomas.
   - Tipo de problema.

6. Clasifica los tickets como RELACIONADOS cuando
   exista similitud funcional suficiente.

7. Clasifica como NO RELACIONADOS cuando describan
   problemas claramente distintos.

CRITERIOS DE AGRUPACION:

- Una coincidencia de sistema y ubicacion no es
  suficiente por si sola.

- Los problemas de acceso, apertura e inicio de
  sesion de un mismo sistema pueden formar parte
  del mismo grupo de investigacion.

- Las diferencias menores en la descripcion
  no obligan a separar tickets relacionados.

- Los problemas claramente diferentes no deben
  agruparse, aunque pertenezcan al mismo sistema.

- No necesitas demostrar que los incidentes tienen
  la misma causa raiz para considerarlos relacionados.

- No supongas que corresponden al mismo dispositivo
  fisico sin evidencia.

- No confirmes caidas generales ni fallas de
  infraestructura sin datos tecnicos.

REGLAS DE EFICIENCIA:

- No repitas consultas innecesarias.
- No realices investigaciones adicionales.
- No invoques otros agentes.
- Procesa todos los grupos recibidos en una
  sola verificacion.
- Responde de manera breve.
- No inventes informacion.

FORMATO OBLIGATORIO:

Para cada grupo candidato:

RESULTADO: RELACIONADOS o NO RELACIONADOS
TICKETS: lista de identificadores
MOTIVO: una frase breve
LIMITACION: causa raiz no confirmada

Responde siempre en espanol.
""",

        # Se conserva la herramienta del laboratorio L6.
        # Solo debe usarse cuando falten datos.
        tools=[
            "mcp__casos__consultar_ticket",
        ],

        model="inherit",
    )
}


# --------------------------------------------------
# 6. CONFIGURACION DEL CLAUDE AGENT SDK
# Reutilizado del laboratorio L4
# --------------------------------------------------

def opciones(**extra) -> ClaudeAgentOptions:

    return ClaudeAgentOptions(
        model=MODELO,

        system_prompt=SYSTEM,

        mcp_servers=SERVIDORES,

        # Permite la delegacion al subagente.
        tools=["Agent"],

        allowed_tools=HERRAMIENTAS + ["Agent"],

        agents=AGENTES,

        # Politica de herramientas del laboratorio L4.
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher=None,
                    hooks=[hook_politica]
                )
            ]
        },

        # No leer configuraciones externas.
        setting_sources=[],

        # Limite de vueltas.
        max_turns=int(
            os.environ.get("MAX_TURNOS", "15")
        ),

        # Limite de presupuesto.
        max_budget_usd=float(
            os.environ.get("PRESUPUESTO_USD", "0.25")
        ),

        cwd=str(AQUI),

        **extra,
    )


# --------------------------------------------------
# 7. MOSTRAR RESPUESTAS Y HERRAMIENTAS
# Reutilizado del laboratorio L4
# --------------------------------------------------

def mostrar(m) -> None:
    """
    Muestra las herramientas utilizadas, sus resultados
    y el costo reportado por Claude Agent SDK.
    """

    if isinstance(m, AssistantMessage):

        for b in m.content:

            if isinstance(b, ToolUseBlock):

                # Presentacion legible: no imprimir el prompt interno de Agent.
                if b.name == "Agent":
                    tipo = b.input.get("subagent_type", "verificador") if isinstance(b.input, dict) else "verificador"
                    print(f"[subagente] Verificando grupos con {tipo}...", flush=True)
                elif b.name.endswith("listar_tickets"):
                    print("[MCP] Consultando lista de tickets...", flush=True)
                elif b.name.endswith("consultar_ticket"):
                    ticket = b.input.get("ticket_id", "") if isinstance(b.input, dict) else ""
                    print(f"[MCP] Consultando ticket {ticket}...", flush=True)
                else:
                    print(f"[herramienta] {b.name}", flush=True)

            elif isinstance(b, TextBlock) and b.text.strip():

                print(
                    f"\nAgente: {b.text.strip()}",
                    flush=True
                )

    elif isinstance(m, UserMessage):

        if isinstance(m.content, list):

            for b in m.content:

                if isinstance(b, ToolResultBlock):

                    resultado = (
                        "error" if b.is_error else "ok"
                    )

                    print(
                        f"  -> {resultado}",
                        flush=True
                    )

    elif isinstance(m, ResultMessage):

        costo = (
            f"USD {m.total_cost_usd:.4f}"
            if m.total_cost_usd is not None
            else "s/d"
        )

        print(
            f"\n[resultado] {m.subtype} "
            f"- turnos={m.num_turns} "
            f"- costo={costo}",
            flush=True
        )


# --------------------------------------------------
# 8. EJECUTAR AGENTE
# Reutilizado del laboratorio L4
# --------------------------------------------------

async def correr(mision: str) -> None:

    try:

        async for m in query(
            prompt=mision,
            options=opciones()
        ):

            mostrar(m)

    except ResultError as exc:

        print(
            f"[freno] {exc}",
            flush=True
        )


# --------------------------------------------------
# 9. INICIO DEL PROGRAMA
# --------------------------------------------------

if __name__ == "__main__":

    mision = (
        " ".join(sys.argv[1:])
        or "¿Que incidentes repetidos hay en Helpdesk?"
    )

    print("=" * 70)
    print("REPETIDESK IA")
    print(f"Mision: {mision}")
    print(f"Modelo: {proveedor()} - {MODELO}")
    print("=" * 70)

    anyio.run(correr, mision)
