"""Panel de inicio según el rol del usuario y aviso de cambios hechos en otros equipos."""
import hashlib
import logging

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from ..bd import bd
from ..seguridad import es_admin, requiere_sesion, sucursal_actual

bp = Blueprint("panel", __name__)
log = logging.getLogger("cambios")


def huella_datos(base, id_sucursal):
    """Resumen corto de los datos que se ven en pantalla. Si cambia, alguien (otro equipo o el
    motor automático) registró algo. Solo usa MAX/COUNT sobre llaves e índices: es muy ligera.
    Las lecturas de temperatura no cuentan (Monitoreo se actualiza aparte cada 30 s)."""
    fila = base.q1(
        "SELECT "
        " (SELECT MAX(id_bitacora) FROM bitacora_auditoria) AS b,"
        " (SELECT MAX(id_historial_estado) FROM historial_estados_lote) AS h,"
        " (SELECT MAX(id_movimiento) FROM movimientos_inventario) AS m,"
        " (SELECT MAX(id_lote) FROM lotes) AS l,"
        " (SELECT MAX(id_atencion) FROM historial_atencion_alertas) AS t,"
        " (SELECT CONCAT(COUNT(*), '-', COALESCE(MAX(id_alerta), 0), '-', COALESCE(SUM(estado_alerta <> 'Cerrada'), 0))"
        "    FROM alertas WHERE id_sucursal = %s) AS a,"
        " (SELECT CONCAT(COUNT(*), '-', COALESCE(MAX(id_descuento), 0), '-', COALESCE(SUM(estado_autorizacion = 'Pendiente'), 0))"
        "    FROM sugerencias_descuento) AS d,"
        " (SELECT CONCAT(COUNT(*), '-', COALESCE(SUM(estado_propuesta = 'Propuesta'), 0)) FROM propuestas_donacion) AS p,"
        " (SELECT COALESCE(SUM(CRC32(CONCAT(id_equipo, ':', estado_operativo))), 0)"
        "    FROM equipos_almacenamiento WHERE id_sucursal = %s) AS e",
        (id_sucursal or 0, id_sucursal or 0))
    texto = "|".join(str(fila[k]) for k in "bhmltadpe")
    return hashlib.md5(texto.encode(), usedforsecurity=False).hexdigest()[:16]


@bp.route("/api/cambios")
@requiere_sesion
def cambios():
    """Cada pantalla lo consulta cada 10 s para enterarse de cambios hechos en otros equipos."""
    return jsonify(h=huella_datos(bd(), sucursal_actual()))


@bp.route("/")
@requiere_sesion
def inicio():
    base = bd()
    suc = sucursal_actual()
    estados = {f["estado_lote"]: f["n"] for f in base.q(
        "SELECT estado_lote, COUNT(*) AS n FROM lotes WHERE id_sucursal = %s AND cantidad_actual > 0 GROUP BY estado_lote",
        (suc,))}
    alertas = base.q(
        "SELECT a.*, l.codigo_lote, e.nombre_equipo FROM alertas a LEFT JOIN lotes l ON l.id_lote = a.id_lote "
        "LEFT JOIN equipos_almacenamiento e ON e.id_equipo = a.id_equipo "
        "WHERE a.id_sucursal = %s AND a.estado_alerta <> 'Cerrada' "
        "ORDER BY FIELD(a.severidad, 'Critica', 'Alta', 'Media'), a.fecha_creacion DESC LIMIT 6", (suc,))
    equipos = base.q(
        "SELECT e.*, (SELECT temperatura_registrada FROM lecturas_temperatura t WHERE t.id_equipo = e.id_equipo "
        "ORDER BY fecha_hora_lectura DESC LIMIT 1) AS actual FROM equipos_almacenamiento e WHERE e.id_sucursal = %s",
        (suc,))
    proximos = base.q(
        "SELECT l.*, i.nombre AS insumo, i.unidad_medida FROM lotes l JOIN insumos i ON i.id_insumo = l.id_insumo "
        "WHERE l.id_sucursal = %s AND l.cantidad_actual > 0 AND l.estado_lote IN ('Próximo a vencer','Vencido','Retenido') "
        "ORDER BY l.fecha_caducidad LIMIT 6", (suc,))
    pendientes_desc = base.q1(
        "SELECT COUNT(*) AS n FROM sugerencias_descuento s JOIN lotes l ON l.id_lote = s.id_lote "
        "WHERE s.estado_autorizacion = 'Pendiente' AND l.id_sucursal = %s", (suc,))["n"]
    resumen = None
    if es_admin():
        resumen = base.q(
            "SELECT s.id_sucursal, s.nombre, s.activa, "
            "(SELECT COUNT(*) FROM lotes l WHERE l.id_sucursal = s.id_sucursal AND l.cantidad_actual > 0) AS lotes, "
            "(SELECT COUNT(*) FROM alertas a WHERE a.id_sucursal = s.id_sucursal AND a.estado_alerta <> 'Cerrada') AS alertas, "
            "(SELECT COUNT(*) FROM equipos_almacenamiento e WHERE e.id_sucursal = s.id_sucursal) AS equipos "
            "FROM sucursales s ORDER BY s.id_sucursal")
    return render_template("panel.html", estados=estados, alertas=alertas, equipos=equipos,
                           proximos=proximos, pendientes_desc=pendientes_desc, resumen=resumen)


@bp.route("/elegir-sucursal", methods=["POST"])
@requiere_sesion
def elegir_sucursal():
    if es_admin():
        session["sucursal_admin"] = int(request.form["id_sucursal"])
    return redirect(request.referrer or url_for("panel.inicio"))
