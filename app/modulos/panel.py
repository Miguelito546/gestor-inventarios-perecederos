"""Panel de inicio según el rol del usuario."""
from flask import Blueprint, redirect, render_template, request, session, url_for

from ..bd import bd
from ..seguridad import es_admin, requiere_sesion, sucursal_actual

bp = Blueprint("panel", __name__)


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
