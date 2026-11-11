"""Corre tu agente del Claude Agent SDK (agente.py) con guardrails, traza y costo, una pregunta a la vez.

Ejecuta:
    python adaptador.py "tu pregunta"                 # una pregunta: respuesta, herramientas, modelos, costo y traza
    python adaptador.py --sin-guardrails "pregunta"   # la misma, sin guardrails (para comparar)
    python evals.py --sin-guardrails --etiqueta antes # el golden set completo (evals.py ya usa este adaptador)

Por cada pregunta deja:
  - una traza en trazas/<id>.jsonl (la lees con `python ver_traza.py`),
  - una línea de costo en usage_log.jsonl (la lees con costing.py, como en el L8).

No toques agente.py para usar este archivo: lo que cambias en tu agente (SYSTEM, SERVIDORES, HERRAMIENTAS, AGENTES)
se usa aquí tal cual.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

import anyio
from claude_agent_sdk import (AssistantMessage, ResultError, ResultMessage, TextBlock, ToolResultBlock,
                              ToolUseBlock, UserMessage, query)

import costing
import trazas
from agente import opciones                      # tu agente: el mismo que corres con `python agente.py`
from guardrails import revisar_entrada, revisar_salida


@dataclass
class Resultado:                                 # los campos que lee evals.py
    pregunta: str
    respuesta: str = ""
    entrada_al_modelo: str = ""
    herramientas: list = field(default_factory=list)
    evidencia: str = ""
    bloqueado_entrada: bool = False
    bloqueado_salida: bool = False
    motivo_guardrail: str = ""
    tokens_entrada: int = 0
    tokens_salida: int = 0
    costo_usd: float = 0.0
    modelos: list = field(default_factory=list)  # qué modelos respondieron (el agente y sus subagentes)
    traza: str = ""


def reiniciar_estado():                          # evals.py los llama antes de cada caso; con tu servidor MCP
    pass                                         # no hacen nada (si tus datos cambian, reinícialos aquí)


def configurar_fallas(n=0):
    pass


def _alias_precio(modelo: str) -> str:
    """Nombre de la tabla de precios de costing.py para cualquier forma del modelo (alias del gateway,
    id de Bedrock o ARN del perfil de tu cohorte)."""
    m = modelo.lower()
    for familia, alias in (("haiku", "claude-haiku-4-5"), ("sonnet", "claude-sonnet-4-6"), ("opus", "claude-opus-4-8")):
        if familia in m:
            return alias
    return modelo                                # un ARN de perfil: costing.py lo resuelve


async def _correr(res: Resultado, traza: trazas.Traza) -> None:
    textos, evidencia, pendientes = [], [], {}
    t0 = time.monotonic()
    try:
        async for m in query(prompt=res.entrada_al_modelo, options=opciones()):
            if isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, ToolUseBlock):      # mcp__casos__get_case → get_case
                        res.herramientas.append({"nombre": b.name.split("__")[-1], "entrada": b.input})
                        pendientes[b.id] = traza.evento("herramienta", b.name.split("__")[-1], entrada=b.input,
                                                        clase="pendiente")
                    elif isinstance(b, TextBlock) and b.text.strip():
                        textos.append(b.text.strip())
            elif isinstance(m, UserMessage) and isinstance(m.content, list):
                for b in m.content:
                    if isinstance(b, ToolResultBlock):
                        evidencia.append(str(b.content))
                        ev = pendientes.pop(b.tool_use_id, None)
                        if ev is not None:
                            ev["clase"] = "error" if b.is_error else "ok"
                            ev["is_error"] = bool(b.is_error)
            elif isinstance(m, ResultMessage):
                u = m.usage or {}
                res.tokens_entrada = sum(u.get(k, 0) or 0 for k in ("input_tokens", "cache_read_input_tokens",
                                                                   "cache_creation_input_tokens"))
                res.tokens_salida = u.get("output_tokens", 0) or 0
                res.modelos = sorted((m.model_usage or {}).keys())
                traza.evento("modelo", "agente", vuelta=m.num_turns, stop_reason=m.subtype,
                             modelos=res.modelos, **{"gen_ai.usage.input_tokens": res.tokens_entrada,
                                                     "gen_ai.usage.output_tokens": res.tokens_salida})
                # Costo: una línea por modelo usado (el agente y sus subagentes), con las 4 líneas de usage.
                for nombre, mu in (m.model_usage or {}).items():
                    uso = SimpleNamespace(input_tokens=mu.get("inputTokens", 0) or 0,
                                          output_tokens=mu.get("outputTokens", 0) or 0,
                                          cache_read_input_tokens=mu.get("cacheReadInputTokens", 0) or 0,
                                          cache_creation_input_tokens=mu.get("cacheCreationInputTokens", 0) or 0)
                    res.costo_usd += costing.log_usage("capstone", _alias_precio(nombre), uso,
                                                       latency_ms=m.duration_ms or (time.monotonic() - t0) * 1000,
                                                       modelo_real=nombre)["cost_usd"]
                if m.result:
                    textos.append(m.result.strip())
    except ResultError as exc:                   # un freno (max_turns, max_budget_usd) cortó la corrida
        textos.append(f"[freno] {exc}")
        traza.evento("freno", str(exc)[:120])
    res.respuesta = textos[-1] if textos else ""
    res.evidencia = "\n".join(evidencia)


def run_agent(pregunta: str, con_guardrails: bool = True, verboso: bool = False) -> Resultado:
    res = Resultado(pregunta=pregunta, entrada_al_modelo=pregunta)
    traza = trazas.Traza(pregunta)
    res.traza = traza.id
    if con_guardrails:
        d = revisar_entrada(pregunta)
        traza.evento("guardrail", "entrada", permitir=d.permitir, motivo=d.motivo)
        if not d.permitir:                       # bloqueado: el modelo ni se entera
            res.respuesta, res.bloqueado_entrada, res.motivo_guardrail = d.texto, True, d.motivo
            traza.cerrar(resultado="bloqueado en la entrada")
            return res
        res.entrada_al_modelo = d.texto          # con la PII enmascarada
    anyio.run(_correr, res, traza)
    if con_guardrails:
        d = revisar_salida(res.respuesta, pregunta + "\n" + res.evidencia)
        traza.evento("guardrail", "salida", permitir=d.permitir, motivo=d.motivo)
        if not d.permitir:
            res.respuesta, res.bloqueado_salida, res.motivo_guardrail = d.texto, True, d.motivo
    traza.cerrar(resultado=f"respondido · modelos: {', '.join(res.modelos) or 's/d'}")
    return res


if __name__ == "__main__":
    # Presentacion para diagnostico; no modifica run_agent() ni evals.py.
    from collections import Counter

    args = sys.argv[1:]
    con_guardrails = "--sin-guardrails" not in args
    mostrar_respuesta = "--respuesta" in args
    pregunta = " ".join(
        a for a in args if a not in ("--sin-guardrails", "--respuesta")
    ).strip()
    if not pregunta:
        sys.exit('Uso: python adaptador.py [--sin-guardrails] [--respuesta] "tu pregunta"')

    r = run_agent(pregunta, con_guardrails=con_guardrails)
    conteos = Counter(h["nombre"] for h in r.herramientas)

    linea = "=" * 59
    print(f"\n{linea}")
    print("REPETIDESK IA - DIAGNOSTICO DE EJECUCION")
    print(linea)
    print(f"Pregunta: {r.pregunta}")

    print("\nOPERACIONES REALIZADAS")
    print(f"Consulta general de tickets:          {conteos['listar_tickets']}")
    print(f"Consultas individuales de tickets:    {conteos['consultar_ticket']}")
    print(f"Verificaciones con subagente:         {conteos['Agent']}")
    otras = {nombre: n for nombre, n in conteos.items()
             if nombre not in ('listar_tickets', 'consultar_ticket', 'Agent')}
    for nombre, n in sorted(otras.items()):
        print(f"Otra herramienta ({nombre}): {n}")

    print("\nSEGURIDAD")
    if not con_guardrails:
        print("Guardrail de entrada:                 DESACTIVADO")
        print("Guardrail de salida:                  DESACTIVADO")
    elif r.bloqueado_entrada:
        print("Guardrail de entrada:                 BLOQUEADO")
        print("Guardrail de salida:                  NO EJECUTADO")
    elif r.bloqueado_salida:
        print("Guardrail de entrada:                 PERMITIDO")
        print("Guardrail de salida:                  BLOQUEADO")
    else:
        print("Guardrail de entrada:                 PERMITIDO")
        print("Guardrail de salida:                  PERMITIDO")
    if r.motivo_guardrail:
        print(f"Motivo: {r.motivo_guardrail}")

    print("\nCONSUMO")
    print(f"Modelo(s):                            {', '.join(r.modelos) or 'no ejecutado'}")
    print(f"Tokens de entrada:                    {r.tokens_entrada}")
    print(f"Tokens de salida:                     {r.tokens_salida}")
    print(f"Costo estimado:                       USD {r.costo_usd:.5f}")

    print("\nTRAZABILIDAD")
    print(f"Archivo de traza:                     trazas/{r.traza}.jsonl")
    print("Para consultar:                       python ver_traza.py")

    if mostrar_respuesta or r.bloqueado_entrada or r.bloqueado_salida:
        print("\nRESPUESTA DEL AGENTE")
        print(r.respuesta)
    print(linea)
