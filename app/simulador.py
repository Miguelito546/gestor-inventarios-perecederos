"""Simulador IoT integrado (RI-004): genera lecturas de temperatura de cada equipo.

Desde la pantalla "Simulador IoT" se puede forzar una falla de frío o cortar la señal
de un equipo para demostrar RF-011 en vivo.
"""
import logging
import random
import threading
import time

import configuracion as cfg
from .bd import BD, Turno
from . import motor

log = logging.getLogger("simulador")

# Los modos ("normal" | "falla" | "sin_senal") se guardan en la tabla simulador_modos para que
# cualquier computadora conectada a la base compartida pueda cambiarlos.
_temperaturas = {}
MODOS = ("normal", "falla", "sin_senal")


def leer_modos(base):
    return {r["id_equipo"]: r["modo"] for r in base.q("SELECT id_equipo, modo FROM simulador_modos")}


def cambiar_modo(base, id_equipo, modo):
    base.ex("INSERT INTO simulador_modos (id_equipo, modo) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE modo = VALUES(modo)", (id_equipo, modo))


def esta_activo(base):
    """True si alguna computadora conectada a la base está ejecutando el simulador."""
    return Turno.alguien_lo_tiene(base, "simulador")


def _siguiente(equipo, modo):
    minimo, maximo = float(equipo["temp_min_permitida"]), float(equipo["temp_max_permitida"])
    if equipo["tipo_equipo"] == "refrigeracion":
        objetivo = (minimo + maximo) / 2
    else:
        objetivo = maximo - 2.5  # congelador: unos grados por debajo del máximo (−20.5 °C)
    actual = _temperaturas.get(equipo["id_equipo"], objetivo)
    if modo == "falla":
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
    modos = leer_modos(base)
    for e in equipos:
        modo = modos.get(e["id_equipo"], "normal")
        if modo == "sin_senal":
            continue
        motor.recibir_lectura(base, {"id_equipo": e["id_equipo"], "temperatura": _siguiente(e, modo)})


def _bucle():
    turno = Turno("simulador")
    base = None
    while True:
        try:
            if turno.tengo_turno():  # solo una computadora genera las lecturas
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
