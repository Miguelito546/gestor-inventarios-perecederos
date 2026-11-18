"""Arranque común para el modo navegador (ejecutar.py) y el modo escritorio (escritorio.py)."""
import logging
import socket
import threading

from werkzeug.serving import make_server

import configuracion as cfg
from . import crear_app, motor, simulador
from .bd import preparar_base

log = logging.getLogger("arranque")


def puerto_libre(preferido):
    """Usa el puerto configurado; si ya está ocupado (otra copia abierta en esta PC), toma uno libre."""
    for puerto in (preferido, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0" if cfg.PERMITIR_RED else "127.0.0.1", puerto))
                return s.getsockname()[1]
            except OSError:
                continue
    raise OSError("No hay puertos libres")


def preparar(reiniciar=False):
    """Conecta con la base (la crea con datos de prueba si está vacía) y arranca los procesos automáticos.

    Lanza ConnectionError con un mensaje claro si no se puede conectar.
    """
    if preparar_base(reiniciar):
        log.info("Base de datos creada con los datos ficticios de prueba")
    motor.iniciar()
    if cfg.SIMULADOR_INTEGRADO:
        simulador.iniciar()


def crear_servidor(puerto):
    host = "0.0.0.0" if cfg.PERMITIR_RED else "127.0.0.1"
    return make_server(host, puerto, crear_app(), threaded=True)


def iniciar_servidor_en_segundo_plano(puerto):
    servidor = crear_servidor(puerto)
    threading.Thread(target=servidor.serve_forever, name="servidor", daemon=True).start()
    return servidor


def ip_local():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # no envía nada; solo elige la interfaz de red
            return s.getsockname()[0]
    except OSError:
        return None
