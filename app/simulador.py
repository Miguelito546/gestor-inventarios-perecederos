"""Simulador IoT integrado (RI-004): genera lecturas de temperatura de cada equipo.

Desde la pantalla "Simulador IoT" se puede forzar una falla de frío o cortar la señal
de un equipo para demostrar RF-011 en vivo.
"""
import logging
import random
import threading
import time

import configuracion as cfg
from .bd import BD
from . import motor

log = logging.getLogger("simulador")

# id_equipo -> "normal" | "falla" | "sin_senal"
modos = {}
_temperaturas = {}
activo = {"valor": False}


def _siguiente(equipo):
    minimo, maximo = float(equipo["temp_min_permitida"]), float(equipo["temp_max_permitida"])
    if equipo["tipo_equipo"] == "refrigeracion":
        objetivo = (minimo + maximo) / 2
    else:
        objetivo = maximo - 2.5  # congelador: unos grados por debajo del máximo (−20.5 °C)
    actual = _temperaturas.get(equipo["id_equipo"], objetivo)
    if modos.get(equipo["id_equipo"]) == "falla":
        actual = max(actual, maximo + 1.0) + random.uniform(0.2, 0.6)  # sube por encima del rango
        actual = min(actual, maximo + 8)
    else:
        if actual > maximo or actual < minimo:
            actual = actual + (objetivo - actual) * 0.6  # se recupera rápido al volver a "normal"
        actual += (objetivo - actual) * 0.2 + random.uniform(-0.4, 0.4)
    _temperaturas[equipo["id_equipo"]] = actual
    return round(actual, 1)


def enviar_ronda(base):
    equipos = base.q(
        "SELECT e.* FROM equipos_almacenamiento e JOIN sucursales s ON s.id_sucursal = e.id_sucursal "
        "WHERE s.activa = 1 AND e.estado_operativo <> 'fuera_de_servicio'"
    )
    for e in equipos:
        if modos.get(e["id_equipo"]) == "sin_senal":
            continue
        motor.recibir_lectura(base, {"id_equipo": e["id_equipo"], "temperatura": _siguiente(e)})


def _bucle():
    base = None
    activo["valor"] = True
    while True:
        try:
            base = base or BD()
            enviar_ronda(base)
        except Exception as e:
            log.warning("Simulador con error: %s", e)
            if base:
                base.cerrar()
            base = None
        time.sleep(cfg.SIMULADOR_INTERVALO_SEG)


def iniciar():
    threading.Thread(target=_bucle, name="simulador", daemon=True).start()
