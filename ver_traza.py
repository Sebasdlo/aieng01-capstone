"""RepetiDesk IA | visor de trazas del laboratorio L7.

Uso:
    python ver_traza.py
    python ver_traza.py trazas/archivo.jsonl
    python ver_traza.py --detalle
    python ver_traza.py --detalle trazas/archivo.jsonl

Solo cambia la visualizacion: no altera el contenido de las trazas.
"""

import sys
from pathlib import Path

import trazas

# Tarifa orientativa para el calculo simple del visor; no contempla cache.
PRECIO_ENTRADA = 1.0
PRECIO_SALIDA = 5.0
ANCHO = 66


def _tiempo(ms):
    """Marca temporal relativa en minutos y segundos."""
    total_ms = max(0, int(ms or 0))
    minutos, resto = divmod(total_ms, 60_000)
    segundos, milesimas = divmod(resto, 1_000)
    return f"[{minutos:02}:{segundos:02}.{milesimas:03}]"


def _estado_herramienta(evento):
    if evento.get("is_error") or evento.get("clase") == "error":
        return "ERROR"
    if evento.get("clase") == "ok":
        return "OK"
    return "SIN CONFIRMAR"


def _descripcion_herramienta(evento):
    nombre = evento.get("nombre", "desconocida")
    if nombre == "listar_tickets":
        return "Consulta general de tickets"
    if nombre == "consultar_ticket":
        datos = evento.get("entrada") or {}
        ticket = datos.get("ticket_id") if isinstance(datos, dict) else None
        return f"Consulta individual de ticket{': ' + str(ticket) if ticket else ''}"
    if nombre == "Agent":
        datos = evento.get("entrada") or {}
        subagente = datos.get("subagent_type") if isinstance(datos, dict) else None
        return f"Subagente verificador{': ' + subagente if subagente else ''}"
    return f"Herramienta {nombre}"


def _num(valor):
    return f"{int(valor or 0):,}".replace(",", ".")


def mostrar(ruta: Path, detalle: bool = False) -> None:
    eventos = trazas.leer(ruta)
    if not eventos:
        print(f"La traza esta vacia: {ruta}")
        return

    primero = eventos[0]
    tin = sum(int(e.get("gen_ai.usage.input_tokens") or 0) for e in eventos)
    tout = sum(int(e.get("gen_ai.usage.output_tokens") or 0) for e in eventos)
    modelos = []
    for e in eventos:
        if e.get("tipo") == "modelo":
            for modelo in e.get("modelos", []):
                if modelo not in modelos:
                    modelos.append(modelo)
    fin = next((e for e in reversed(eventos) if e.get("nombre") == "fin"), None)
    duracion = (fin or {}).get("duracion_total_ms")
    if duracion is None:
        duracion = max((e.get("t_ms") or 0) for e in eventos)

    print("=" * ANCHO)
    print("REPETIDESK IA - TRAZABILIDAD DE EJECUCION")
    print("=" * ANCHO)
    print(f"Archivo:  {ruta}")
    print(f"Traza:    {primero.get('traza_id', 's/d')}")
    print(f"Pregunta: {primero.get('pregunta', 's/d')}")
    print("\nRECORRIDO DEL AGENTE")
    print("-" * ANCHO)

    for e in eventos:
        marca = _tiempo(e.get("t_ms", 0))
        tipo = e.get("tipo")
        nombre = e.get("nombre")
        if tipo == "guardrail":
            estado = "PERMITIDO" if e.get("permitir") else "BLOQUEADO"
            print(f"{marca} Guardrail de {nombre}: {estado}")
            if e.get("motivo"):
                print(f"           Detalle: {e['motivo']}")
        elif tipo == "herramienta":
            print(f"{marca} {_descripcion_herramienta(e)}: {_estado_herramienta(e)}")
            if detalle:
                print(f"           Nombre tecnico: {nombre}")
                print(f"           Parametros: {e.get('entrada')}")
        elif tipo == "modelo":
            print(f"{marca} Procesamiento del modelo: {e.get('stop_reason', 's/d')}")
            if detalle:
                print(f"           Vuelta: {e.get('vuelta', 's/d')}")
        elif tipo == "freno":
            print(f"{marca} Ejecucion detenida: {nombre}")
        elif nombre == "fin":
            print(f"{marca} Fin de la ejecucion")
            if detalle:
                print(f"           Resultado: {e.get('resultado', 's/d')}")

    print("\nRESUMEN DE EJECUCION")
    print("-" * ANCHO)
    print(f"Estado:             {(fin or {}).get('resultado', 'no registrado')}")
    print(f"Modelo(s):          {', '.join(modelos) or 'no registrado'}")
    print(f"Tokens de entrada:  {_num(tin)}")
    print(f"Tokens de salida:   {_num(tout)}")
    print(f"Duracion total:     {float(duracion) / 1000:.2f} segundos")
    estimado = (tin * PRECIO_ENTRADA + tout * PRECIO_SALIDA) / 1_000_000
    print(f"Costo simple*:      USD {estimado:.5f}")
    print("=" * ANCHO)
    print("* Estimacion con tarifa plana; no considera cache ni desglose")
    print("  por modelo. Para el costo registrado usa adaptador.py.")
    if not detalle:
        print("Detalle completo: python ver_traza.py --detalle")


if __name__ == "__main__":
    argumentos = sys.argv[1:]
    detalle = "--detalle" in argumentos
    rutas = [a for a in argumentos if a != "--detalle"]
    if len(rutas) > 1:
        sys.exit("Uso: python ver_traza.py [--detalle] [trazas/archivo.jsonl]")
    ruta = Path(rutas[0]) if rutas else trazas.ultima()
    if ruta is None or not ruta.exists():
        sys.exit('No hay trazas todavia: ejecuta primero python adaptador.py "tu pregunta".')
    mostrar(ruta, detalle=detalle)
