
"""
AIENG01 - Proyecto Integrador L9
RepetiDesk IA - Detector de Incidentes Repetidos

Servidor MCP basado en los laboratorios L3 y L4.

Permite consultar tickets simulados de Helpdesk.
Las herramientas son de solo lectura.
"""

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError


# --------------------------------------------------
# 1. CONFIGURACION DEL SERVIDOR MCP
# --------------------------------------------------

mcp = FastMCP("repetidesk", log_level="WARNING")

# Ruta al archivo JSON con los tickets simulados.
# TICKETS_DB permite utilizar otro archivo en pruebas.
DB_PATH = Path(
    os.environ.get(
        "TICKETS_DB",
        str(Path(__file__).parent / "datos" / "tickets.json")
    )
)


# --------------------------------------------------
# 2. FUNCION PARA CARGAR LOS TICKETS
# Reutilizada del laboratorio L3/L4
# --------------------------------------------------

def _load() -> dict:
    """Carga los tickets almacenados en formato JSON."""

    try:
        with DB_PATH.open("r", encoding="utf-8") as archivo:
            db = json.load(archivo)

        if not isinstance(db, dict):
            raise ToolError(
                "El archivo tickets.json debe contener un objeto JSON."
            )

        return db

    except FileNotFoundError:
        raise ToolError(
            "No se encontro el archivo datos/tickets.json."
        )

    except json.JSONDecodeError:
        raise ToolError(
            "El archivo tickets.json tiene un formato invalido."
        )


# --------------------------------------------------
# 3. FUNCION PARA BUSCAR UN TICKET
# Adaptada de _caso() del laboratorio L4
# --------------------------------------------------

def _ticket(db: dict, ticket_id: str) -> dict:
    """Busca un ticket por su identificador."""

    ticket_id = ticket_id.strip().upper()

    if ticket_id not in db:
        raise ToolError(
            f"No existe el ticket {ticket_id}. "
            "Usa listar_tickets para encontrar un ID valido."
        )

    return {
        "id": ticket_id,
        **db[ticket_id]
    }


# --------------------------------------------------
# 4. HERRAMIENTA MCP: CONSULTAR TICKET
# Adaptada de get_case() del laboratorio L4
# --------------------------------------------------

@mcp.tool()
def consultar_ticket(ticket_id: str) -> dict:
    """
    Consulta el detalle de un ticket de Helpdesk por su ID.

    Utiliza esta herramienta cuando necesites comprobar
    la descripcion, sistema, ubicacion y estado de un
    incidente especifico.

    Devuelve los datos registrados del ticket.

    Si el ticket no existe, devuelve un error controlado.
    """

    db = _load()

    return _ticket(db, ticket_id)


# --------------------------------------------------
# 5. HERRAMIENTA MCP: LISTAR TICKETS
# Adaptada de search_cases() del laboratorio L4
# --------------------------------------------------

@mcp.tool()
def listar_tickets(
    sistema: str = "",
    ubicacion: str = ""
) -> list[dict]:
    """
    Consulta los tickets registrados de Helpdesk.

    Utiliza esta herramienta para buscar posibles
    incidentes repetidos.

    Permite filtrar por:
    - sistema: nombre del sistema o servicio afectado.
    - ubicacion: sede o lugar donde ocurre la falla.

    Si no se proporcionan filtros, devuelve todos
    los tickets disponibles.

    Cada resultado incluye:
    - ID del ticket
    - Sistema afectado
    - Ubicacion
    - Descripcion del incidente
    - Estado del ticket

    Esta herramienta no confirma la causa raiz
    de un incidente ni modifica informacion.
    """

    db = _load()
    resultados = []

    for ticket_id, ticket in db.items():

        # Filtrar por sistema, si se solicita
        if sistema:
            if sistema.lower() not in ticket["sistema"].lower():
                continue

        # Filtrar por ubicacion, si se solicita
        if ubicacion:
            if ubicacion.lower() not in ticket["ubicacion"].lower():
                continue

        resultados.append({
            "id": ticket_id,
            "sistema": ticket["sistema"],
            "ubicacion": ticket["ubicacion"],
            "descripcion": ticket["descripcion"],
            "estado": ticket["estado"]
        })

    return resultados


# --------------------------------------------------
# 6. RECURSO MCP: RESUMEN DE TICKETS
# Adaptado de resumen_casos() del laboratorio L3/L4
# --------------------------------------------------

@mcp.resource("repetidesk://resumen")
def resumen_tickets() -> str:
    """
    Devuelve un resumen general de los tickets
    agrupados por estado y sistema.
    """

    db = _load()

    por_estado = {}
    por_sistema = {}

    for ticket in db.values():

        estado = ticket["estado"]
        sistema = ticket["sistema"]

        por_estado[estado] = por_estado.get(estado, 0) + 1

        por_sistema[sistema] = por_sistema.get(sistema, 0) + 1

    resumen = {
        "total_tickets": len(db),
        "por_estado": por_estado,
        "por_sistema": por_sistema
    }

    return json.dumps(
        resumen,
        ensure_ascii=False
    )


# --------------------------------------------------
# 7. EJECUTAR SERVIDOR MCP
# Reutilizado del laboratorio L4
# --------------------------------------------------

if __name__ == "__main__":
    mcp.run()
