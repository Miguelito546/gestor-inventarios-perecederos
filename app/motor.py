"""Procesos automáticos del sistema.

RF-003 Calcular estado del lote      RF-004 Estimar riesgo de merma
RF-008 Recibir lecturas              RF-010 Alerta de caducidad
RF-011 Alerta de cadena de frío      RF-014 Sugerir descuento dinámico
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import configuracion as cfg
from .bd import BD

log = logging.getLogger("motor")

# Evita que el ciclo y la recepción de lecturas generen alertas duplicadas al mismo tiempo.
candado = threading.RLock()
INICIO = datetime.now()

CONFIG_POR_DEFECTO = {
    "dias_anticipacion_caducidad": 2,
    "tiempo_tolerado_temp_min": 15,
    "pct_descuento_nivel_1": Decimal("10.00"),
    "pct_descuento_nivel_2": Decimal("25.00"),
    "horas_min_donacion": 24,
    "minutos_sin_senal": 10,
}


def config_sucursal(base, id_sucursal):
    fila = base.q1("SELECT * FROM configuracion_umbrales WHERE id_sucursal = %s", (id_sucursal,))
    return {**CONFIG_POR_DEFECTO, **(fila or {})}


def alerta_frio_abierta(base, id_equipo):
    return base.q1(
        "SELECT id_alerta FROM alertas WHERE id_equipo = %s AND tipo_alerta = 'Cadena_de_frio' "
        "AND estado_alerta <> 'Cerrada' LIMIT 1",
        (id_equipo,),
    )


def cambiar_estado_lote(base, lote, nuevo, motivo, id_usuario=None):
    if lote["estado_lote"] == nuevo:
        return
    base.ex("UPDATE lotes SET estado_lote = %s WHERE id_lote = %s", (nuevo, lote["id_lote"]))
    base.ex(
        "INSERT INTO historial_estados_lote (id_lote, estado_anterior, estado_nuevo, motivo_cambio, id_usuario) "
        "VALUES (%s,%s,%s,%s,%s)",
        (lote["id_lote"], lote["estado_lote"], nuevo, motivo, id_usuario),
    )
    lote["estado_lote"] = nuevo


def estado_por_caducidad(lote, ahora, dias_n):
    if lote["fecha_caducidad"] <= ahora:
        return "Vencido"
    if lote["fecha_caducidad"] - ahora <= timedelta(days=dias_n):
        return "Próximo a vencer"
    return "Fresco"


# ---------------------------------------------------------------- RF-003 / RF-010
def recalcular_estados(base):
    ahora = base.ahora()
    lotes = base.q(
        "SELECT l.*, i.nombre AS insumo, COALESCE(c.dias_anticipacion_caducidad, 2) AS dias_n "
        "FROM lotes l JOIN insumos i ON i.id_insumo = l.id_insumo "
        "LEFT JOIN configuracion_umbrales c ON c.id_sucursal = l.id_sucursal "
        "WHERE l.cantidad_actual > 0"
    )
    for lote in lotes:
        por_fecha = estado_por_caducidad(lote, ahora, lote["dias_n"])
        if por_fecha == "Vencido":
            nuevo, motivo = "Vencido", "Fecha de caducidad alcanzada (RF-003)"
        elif lote["estado_lote"] == "Retenido":
            nuevo, motivo = "Retenido", ""
        elif alerta_frio_abierta(base, lote["id_equipo"]):
            nuevo, motivo = "Retenido", "Equipo con alerta de cadena de frío abierta (RN-002)"
        elif por_fecha == "Próximo a vencer":
            nuevo, motivo = por_fecha, f"Faltan {lote['dias_n']} días o menos para su caducidad (RF-003)"
        else:
            nuevo, motivo = "Fresco", "Recalculado por fecha de caducidad (RF-003)"
        cambiar_estado_lote(base, lote, nuevo, motivo)
        generar_alerta_caducidad(base, lote, ahora)


def generar_alerta_caducidad(base, lote, ahora):
    if lote["estado_lote"] == "Vencido":
        severidad = "Alta"
        texto = (f"El lote {lote['codigo_lote']} ({lote['insumo']}) se encuentra VENCIDO. "
                 "Debe registrarse su baja como merma (RN-005).")
    elif lote["estado_lote"] == "Próximo a vencer" or (
        lote["estado_lote"] == "Retenido" and estado_por_caducidad(lote, ahora, lote["dias_n"]) == "Próximo a vencer"
    ):
        severidad = "Media"
        horas = int((lote["fecha_caducidad"] - ahora).total_seconds() // 3600)
        texto = f"El lote {lote['codigo_lote']} ({lote['insumo']}) vence en {horas} h."
    else:
        return
    existe = base.q1(
        "SELECT id_alerta FROM alertas WHERE id_lote = %s AND tipo_alerta = 'Caducidad' AND severidad = %s "
        "AND estado_alerta <> 'Cerrada'",
        (lote["id_lote"], severidad),
    )
    if not existe:
        base.ex(
            "INSERT INTO alertas (id_sucursal, tipo_alerta, severidad, id_lote, descripcion) "
            "VALUES (%s, 'Caducidad', %s, %s, %s)",
            (lote["id_sucursal"], severidad, lote["id_lote"], texto),
        )


# ---------------------------------------------------------------- RF-004
def calcular_riesgo(base):
    ahora = base.ahora()
    consumos = {
        (f["id_sucursal"], f["id_insumo"]): Decimal(f["total"]) / 7
        for f in base.q(
            "SELECT l.id_sucursal, l.id_insumo, SUM(m.cantidad) AS total FROM movimientos_inventario m "
            "JOIN lotes l ON l.id_lote = m.id_lote WHERE m.tipo_movimiento = 'Consumo' "
            "AND m.fecha_movimiento >= NOW() - INTERVAL 7 DAY GROUP BY l.id_sucursal, l.id_insumo"
        )
    }
    for lote in base.q("SELECT * FROM lotes WHERE cantidad_actual > 0"):
        promedio = consumos.get((lote["id_sucursal"], lote["id_insumo"]), 0)
        dias = Decimal((lote["fecha_caducidad"] - ahora).total_seconds() / 86400)
        if dias <= 0 or lote["estado_lote"] == "Vencido":
            riesgo = "Alto"
        elif not promedio:
            riesgo = "Sin datos"
        else:
            necesarios = lote["cantidad_actual"] / promedio
            riesgo = "Bajo" if necesarios <= dias / 2 else "Medio" if necesarios <= dias else "Alto"
        if riesgo != lote["riesgo_merma"]:
            base.ex("UPDATE lotes SET riesgo_merma = %s WHERE id_lote = %s", (riesgo, lote["id_lote"]))


# ---------------------------------------------------------------- RF-014
def sugerir_descuentos(base):
    ahora = base.ahora()
    # Las sugerencias pendientes de lotes que dejaron de ser elegibles se descartan.
    base.ex(
        "UPDATE sugerencias_descuento s JOIN lotes l ON l.id_lote = s.id_lote "
        "SET s.estado_autorizacion = 'Rechazado', s.motivo_rechazo = 'Lote ya no elegible (sistema)', "
        "s.fecha_respuesta = NOW() "
        "WHERE s.estado_autorizacion = 'Pendiente' AND (l.estado_lote IN ('Vencido','Retenido') OR l.cantidad_actual <= 0)"
    )
    lotes = base.q(
        "SELECT * FROM lotes WHERE estado_lote = 'Próximo a vencer' AND cantidad_actual > 0"
    )
    for lote in lotes:
        if alerta_frio_abierta(base, lote["id_equipo"]):
            continue
        c = config_sucursal(base, lote["id_sucursal"])
        horas = (lote["fecha_caducidad"] - ahora).total_seconds() / 3600
        if horas <= 24:
            pct = c["pct_descuento_nivel_2"]
        elif horas <= 48:
            pct = c["pct_descuento_nivel_1"]
        else:
            continue
        previas = base.q("SELECT * FROM sugerencias_descuento WHERE id_lote = %s", (lote["id_lote"],))
        if any(Decimal(p["porcentaje_sugerido"]) == Decimal(pct) for p in previas):
            continue  # ya se sugirió (y si se rechazó, no se vuelve a sugerir)
        pendiente = next((p for p in previas if p["estado_autorizacion"] == "Pendiente"), None)
        if pendiente:
            base.ex(
                "UPDATE sugerencias_descuento SET porcentaje_sugerido = %s, fecha_sugerencia = NOW() WHERE id_descuento = %s",
                (pct, pendiente["id_descuento"]),
            )
        else:
            base.ex("INSERT INTO sugerencias_descuento (id_lote, porcentaje_sugerido) VALUES (%s, %s)",
                    (lote["id_lote"], pct))


# ---------------------------------------------------------------- RF-008 / RF-011
class LecturaInvalida(ValueError):
    pass


def recibir_lectura(base, datos):
    """Valida y guarda una lectura del simulador (formato JSON acordado, RI-004).

    {"id_equipo": 1, "temperatura": 3.2, "marca_tiempo": "2026-10-25T10:30:00"}  (marca_tiempo opcional)
    """
    try:
        id_equipo = int(datos["id_equipo"])
        temperatura = Decimal(str(datos["temperatura"])).quantize(Decimal("0.1"))
        if not temperatura.is_finite() or abs(temperatura) > 999:
            raise InvalidOperation
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise LecturaInvalida("Formato inválido: se esperan id_equipo (entero) y temperatura (número).")
    marca = datos.get("marca_tiempo")
    if marca:
        try:
            marca = datetime.fromisoformat(str(marca)).replace(tzinfo=None, microsecond=0)
        except ValueError:
            raise LecturaInvalida("marca_tiempo debe tener formato ISO, por ejemplo 2026-10-25T10:30:00.")
    else:
        marca = base.ahora()

    equipo = base.q1("SELECT * FROM equipos_almacenamiento WHERE id_equipo = %s", (id_equipo,))
    if not equipo:
        log.warning("Lectura rechazada: el equipo %s no existe", id_equipo)
        raise LecturaInvalida(f"El equipo {id_equipo} no existe.")

    fuera = not (equipo["temp_min_permitida"] <= temperatura <= equipo["temp_max_permitida"])
    with candado:
        nuevas = base.ex(
            "INSERT IGNORE INTO lecturas_temperatura (id_equipo, temperatura_registrada, fecha_hora_lectura, fuera_de_rango) "
            "VALUES (%s,%s,%s,%s)",
            (id_equipo, temperatura, marca, int(fuera)),
        )
        if not nuevas:
            return {"estado": "ignorada", "detalle": "Lectura repetida (mismo equipo y marca de tiempo)."}
        alerta = evaluar_cadena_frio(base, equipo, marca) if fuera else None
    return {"estado": "recibida", "fuera_de_rango": fuera, "alerta_generada": alerta}


def evaluar_cadena_frio(base, equipo, marca):
    ultima_normal = base.q1(
        "SELECT MAX(fecha_hora_lectura) AS f FROM lecturas_temperatura "
        "WHERE id_equipo = %s AND fuera_de_rango = 0 AND fecha_hora_lectura <= %s",
        (equipo["id_equipo"], marca),
    )["f"]
    inicio = base.q1(
        "SELECT MIN(fecha_hora_lectura) AS f FROM lecturas_temperatura WHERE id_equipo = %s AND fuera_de_rango = 1 "
        "AND fecha_hora_lectura > %s AND fecha_hora_lectura <= %s",
        (equipo["id_equipo"], ultima_normal or datetime(2000, 1, 1), marca),
    )["f"]
    c = config_sucursal(base, equipo["id_sucursal"])
    if not inicio or marca - inicio < timedelta(minutes=c["tiempo_tolerado_temp_min"]):
        return None
    if alerta_frio_abierta(base, equipo["id_equipo"]):
        return None
    minutos = int((marca - inicio).total_seconds() // 60)
    id_alerta = base.ex(
        "INSERT INTO alertas (id_sucursal, tipo_alerta, severidad, id_equipo, descripcion) "
        "VALUES (%s, 'Cadena_de_frio', 'Critica', %s, %s)",
        (equipo["id_sucursal"], equipo["id_equipo"],
         f"{equipo['nombre_equipo']} está fuera de su rango ({equipo['temp_min_permitida']} a "
         f"{equipo['temp_max_permitida']} °C) desde hace {minutos} min (tolerancia {c['tiempo_tolerado_temp_min']} min)."),
    )
    base.ex("UPDATE equipos_almacenamiento SET estado_operativo = 'alerta_temperatura' WHERE id_equipo = %s",
            (equipo["id_equipo"],))
    for lote in base.q(
        "SELECT * FROM lotes WHERE id_equipo = %s AND cantidad_actual > 0 AND estado_lote <> 'Vencido'",
        (equipo["id_equipo"],),
    ):
        cambiar_estado_lote(base, lote, "Retenido",
                            f"Alerta de cadena de frío en {equipo['nombre_equipo']} (RN-002)")
    return id_alerta


def revisar_sin_senal(base):
    ahora = base.ahora()
    equipos = base.q(
        "SELECT e.*, MAX(t.fecha_hora_lectura) AS ultima FROM equipos_almacenamiento e "
        "JOIN sucursales s ON s.id_sucursal = e.id_sucursal AND s.activa = 1 "
        "JOIN lecturas_temperatura t ON t.id_equipo = e.id_equipo "
        "WHERE e.estado_operativo <> 'fuera_de_servicio' GROUP BY e.id_equipo"
    )
    for e in equipos:
        c = config_sucursal(base, e["id_sucursal"])
        limite = timedelta(minutes=c["minutos_sin_senal"])
        # Periodo de gracia al arrancar la aplicación, para no alertar por el tiempo que estuvo apagada.
        if datetime.now() - INICIO < limite or ahora - e["ultima"] < limite:
            continue
        existe = base.q1(
            "SELECT id_alerta FROM alertas WHERE id_equipo = %s AND tipo_alerta = 'Sin_senal' AND estado_alerta <> 'Cerrada'",
            (e["id_equipo"],),
        )
        if not existe:
            base.ex(
                "INSERT INTO alertas (id_sucursal, tipo_alerta, severidad, id_equipo, descripcion) "
                "VALUES (%s, 'Sin_senal', 'Alta', %s, %s)",
                (e["id_sucursal"], e["id_equipo"],
                 f"{e['nombre_equipo']} no envía lecturas desde hace más de {c['minutos_sin_senal']} min."),
            )


# ---------------------------------------------------------------- Ciclo
def ciclo(base):
    with candado:
        recalcular_estados(base)
        calcular_riesgo(base)
        sugerir_descuentos(base)
        revisar_sin_senal(base)


def _bucle():
    base = None
    while True:
        try:
            base = base or BD()
            ciclo(base)
        except Exception as e:  # la base pudo reiniciarse; se reconecta en la siguiente vuelta
            log.warning("Ciclo del motor con error: %s", e)
            if base:
                base.cerrar()
            base = None
        time.sleep(cfg.CICLO_MOTOR_SEG)


def iniciar():
    threading.Thread(target=_bucle, name="motor", daemon=True).start()
