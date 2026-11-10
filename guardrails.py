
"""
AIENG01 - Proyecto Integrador L9
RepetiDesk IA - Guardrails de entrada y salida

Basado en el laboratorio L7.

ENTRADA:
- Detecta intentos de inyeccion de instrucciones.
- Enmascara tarjetas y claves antes de enviarlas a Claude.

SALIDA:
- Detecta IDs de tickets sin respaldo.
- Detecta promesas prohibidas.
- Evita revelar tarjetas y claves.

Compatible con adaptador.py y evals.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# --------------------------------------------------
# 1. ESTRUCTURA DE DECISION - LABORATORIO L7
# --------------------------------------------------

@dataclass
class Decision:
    permitir: bool
    texto: str
    motivo: str = ""
    hallazgos: list[str] = field(default_factory=list)


RESPUESTA_BLOQUEO_ENTRADA = (
    "No puedo atender solicitudes que intenten modificar "
    "mis instrucciones o acceder a informacion confidencial. "
    "Puedo ayudarte a consultar tickets e identificar "
    "posibles incidentes repetidos de Helpdesk."
)

RESPUESTA_SEGURA_SALIDA = (
    "No pude verificar completamente la informacion "
    "con los tickets registrados. "
    "Para evitar entregar datos incorrectos o sensibles, "
    "te recomiendo revisar el incidente con Helpdesk."
)


# --------------------------------------------------
# 2. GUARDRAIL DE ENTRADA - LABORATORIO L7
# --------------------------------------------------

PATRONES_INYECCION = [
    r"ignora\w*\s+(todas?\s+)?(las\s+|tus\s+)?(instrucciones|reglas|indicaciones)",
    r"olvida\w*\s+(todas?\s+)?(las\s+|tus\s+)?(instrucciones|reglas)",
    r"(system|sistema)\s*prompt",
    r"(modo|mode)\s+(desarrollador|developer|dios|admin)",
    r"ahora\s+eres\s+",
    r"desactiva\w*\s+(las\s+|tus\s+)?(reglas|protecciones|guardrails)"
]


# Tarjetas de 13 a 19 digitos.
RE_TARJETA = re.compile(
    r"\b\d(?:[ -]?\d){12,18}\b"
)

# Claves explicitas como:
# "mi clave es 4321", "PIN: 1234".
# Evita bloquear "olvide mi contraseña".
RE_CLAVE = re.compile(
    r"\b(clave|contraseña|contrasena|pin)\b"
    r"\s*(?:es\s+|:\s*|=\s*)"
    r"([^\s.,;]+)",
    re.IGNORECASE
)


def detectar_inyeccion(texto: str) -> str | None:
    """
    Detecta patrones de inyeccion de instrucciones.
    Devuelve el patron encontrado o None.
    """
    t = texto.lower()

    for patron in PATRONES_INYECCION:
        if re.search(patron, t):
            return patron

    return None


def enmascarar_pii(texto: str) -> tuple[str, list[str]]:
    """
    Oculta tarjetas y claves antes de enviar
    la consulta al modelo.

    Reutilizado del laboratorio L7.
    """
    hallazgos = []

    texto, n = RE_TARJETA.subn(
        "[TARJETA]",
        texto
    )

    if n:
        hallazgos.append("tarjeta")

    texto, n = RE_CLAVE.subn(
        lambda m: f"{m.group(1)} [OCULTA]",
        texto
    )

    if n:
        hallazgos.append("clave")

    return texto, hallazgos


def revisar_entrada(texto: str) -> Decision:
    """
    Verifica la entrada antes de llamar a Claude.

    Bloquea inyecciones de instrucciones y
    enmascara informacion sensible.
    """
    patron = detectar_inyeccion(texto)

    if patron:
        return Decision(
            False,
            RESPUESTA_BLOQUEO_ENTRADA,
            f"posible inyeccion de instrucciones ({patron})",
            ["inyeccion"]
        )

    saneado, hallazgos = enmascarar_pii(texto)

    return Decision(
        True,
        saneado,
        "pii enmascarada" if hallazgos else "",
        hallazgos
    )


# --------------------------------------------------
# 3. GUARDRAIL DE SALIDA - LABORATORIO L7
# --------------------------------------------------

# Reconoce T001, T015, T999 y formatos antiguos.
RE_IDS = re.compile(
    r"\b(?:T\d{3,}|T-\d+|CASE-\d+|CASO-\d+)\b",
    re.IGNORECASE
)

PROMESAS_PROHIBIDAS = [
    "te garantizo",
    "te prometo",
    "garantizamos",
    "con total seguridad",
    "es seguro que mañana"
]


def ids_no_respaldados(
    respuesta: str,
    evidencia: str
) -> list[str]:
    """
    Detecta identificadores mencionados en la
    respuesta que no aparecen en la evidencia.

    La evidencia incluye los resultados MCP
    y la pregunta original del usuario.
    """
    salida = []
    evidencia = evidencia.upper()

    for ticket_id in RE_IDS.findall(respuesta):

        ticket_id = ticket_id.upper()

        if ticket_id not in evidencia and ticket_id not in salida:
            salida.append(ticket_id)

    return salida


def promesas_prohibidas(respuesta: str) -> list[str]:
    """
    Detecta promesas no autorizadas.
    Evita bloquear expresiones negadas.
    """
    texto = respuesta.lower()
    encontradas = []

    for frase in PROMESAS_PROHIBIDAS:

        for coincidencia in re.finditer(
            re.escape(frase),
            texto
        ):

            anterior = texto[
                max(0, coincidencia.start() - 14):
                coincidencia.start()
            ]

            if not re.search(
                r"\bno\s+(\w+\s+)?$",
                anterior
            ):
                encontradas.append(frase)
                break

    return encontradas


def revisar_salida(
    respuesta: str,
    evidencia: str
) -> Decision:
    """
    Verifica la respuesta final del agente.

    Comprueba IDs sin respaldo, promesas
    prohibidas y datos sensibles.
    """
    hallazgos = []

    # Verificar tickets inventados.
    sin_respaldo = ids_no_respaldados(
        respuesta,
        evidencia
    )

    if sin_respaldo:
        hallazgos.append(
            f"tickets sin respaldo: {sin_respaldo}"
        )

    # Verificar promesas prohibidas.
    promesas = promesas_prohibidas(respuesta)

    if promesas:
        hallazgos.append(
            f"promesas: {promesas}"
        )

    # Verificar tarjetas.
    if RE_TARJETA.search(respuesta):
        hallazgos.append(
            "tarjeta en la respuesta"
        )

    # Verificar posibles claves explicitas.
    if RE_CLAVE.search(respuesta):
        hallazgos.append(
            "posible clave en la respuesta"
        )

    if hallazgos:
        return Decision(
            False,
            RESPUESTA_SEGURA_SALIDA,
            "; ".join(hallazgos),
            hallazgos
        )

    return Decision(
        True,
        respuesta
    )
