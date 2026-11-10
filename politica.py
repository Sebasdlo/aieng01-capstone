
"""
AIENG01 - Proyecto Integrador L9
RepetiDesk IA - Politica de herramientas

Basado en el laboratorio L4.

La politica controla que herramientas MCP
puede ejecutar el agente.

RepetiDesk IA solamente consulta tickets.
No permite modificar ni eliminar informacion.
"""

import os

# Herramientas permitidas para RepetiDesk IA
LECTURA = {
    "listar_tickets",
    "consultar_ticket"
}

# Herramientas antiguas de escritura
ESCRITURA = {
    "create_case",
    "add_note",
    "escalate_case"
}

PREFIJO = "mcp__casos__"


def decidir(
    herramienta: str,
    entrada: dict,
    modo_auditor: bool
) -> tuple[bool, str]:
    """
    Decide si una herramienta puede ejecutarse.

    Reutiliza la estructura del laboratorio L4.

    Reglas:
    1. Permitir las herramientas de consulta.
    2. Rechazar las herramientas de escritura.
    3. Rechazar herramientas desconocidas.
    """

    if herramienta in LECTURA:
        return True, ""

    if herramienta in ESCRITURA:
        return False, (
            "RepetiDesk IA es un agente de solo lectura. "
            "No puede crear, modificar ni escalar tickets."
        )

    return False, (
        f"La herramienta {herramienta} no esta autorizada "
        "para RepetiDesk IA."
    )


async def hook_politica(
    input_data: dict,
    tool_use_id: str | None,
    context
) -> dict:
    """
    Hook PreToolUse del Claude Agent SDK.

    Se ejecuta antes de utilizar una herramienta MCP.
    """

    nombre = input_data.get("tool_name", "")

    # Solo controla las herramientas de nuestro servidor.
    if not nombre.startswith(PREFIJO):
        return {}

    modo_auditor = os.environ.get("MODO_AUDITOR") == "1"

    permitido, razon = decidir(
        nombre.removeprefix(PREFIJO),
        input_data.get("tool_input", {}),
        modo_auditor
    )

    if permitido:
        return {}

    print(
        f"[politica] Herramienta denegada: {razon}",
        flush=True
    )

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": razon
        }
    }
