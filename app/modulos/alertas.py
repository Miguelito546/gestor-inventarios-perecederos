"""Módulo de Alertas.

RF-010 y RF-011 se generan en motor.py; aquí está RF-012 Gestionar alertas.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..bd import auditar, bd
from ..motor import candado, ciclo, config_sucursal, estado_por_caducidad
from ..seguridad import requiere_sesion, sucursal_actual, usuario, verificar_sucursal

bp = Blueprint("alertas", __name__)

SIGUIENTE = {"Reconocer": "Reconocida", "Atender": "En_atencion", "Cerrar": "Cerrada"}
PERMITIDO = {
    "Reconocer": ("Abierta",),
    "Atender": ("Abierta", "Reconocida"),
    "Cerrar": ("Abierta", "Reconocida", "En_atencion"),
}


@bp.route("/alertas")
@requiere_sesion
def lista():
    ver = request.args.get("ver", "activas")
    sql = ("SELECT a.*, l.codigo_lote, e.nombre_equipo FROM alertas a LEFT JOIN lotes l ON l.id_lote = a.id_lote "
           "LEFT JOIN equipos_almacenamiento e ON e.id_equipo = a.id_equipo WHERE a.id_sucursal = %s")
    if ver == "activas":
        sql += " AND a.estado_alerta <> 'Cerrada'"
    sql += " ORDER BY a.estado_alerta = 'Cerrada', FIELD(a.severidad, 'Critica', 'Alta', 'Media'), a.fecha_creacion DESC LIMIT 300"
    return render_template("alertas.html", alertas=bd().q(sql, (sucursal_actual(),)), ver=ver)


def lotes_afectados(base, alerta):
    if alerta["tipo_alerta"] == "Cadena_de_frio":
        return base.q(
            "SELECT l.*, i.nombre AS insumo, i.unidad_medida FROM lotes l JOIN insumos i ON i.id_insumo = l.id_insumo "
            "WHERE l.id_equipo = %s AND l.cantidad_actual > 0 AND l.estado_lote = 'Retenido'", (alerta["id_equipo"],))
    if alerta["id_lote"]:
        return base.q(
            "SELECT l.*, i.nombre AS insumo, i.unidad_medida FROM lotes l JOIN insumos i ON i.id_insumo = l.id_insumo "
            "WHERE l.id_lote = %s", (alerta["id_lote"],))
    return []


@bp.route("/alertas/<int:id_alerta>", methods=["GET", "POST"])
@requiere_sesion
def detalle(id_alerta):
    base = bd()
    alerta = base.q1(
        "SELECT a.*, l.codigo_lote, e.nombre_equipo, s.nombre AS sucursal FROM alertas a "
        "LEFT JOIN lotes l ON l.id_lote = a.id_lote LEFT JOIN equipos_almacenamiento e ON e.id_equipo = a.id_equipo "
        "JOIN sucursales s ON s.id_sucursal = a.id_sucursal WHERE a.id_alerta = %s", (id_alerta,))
    if not alerta:
        abort(404)
    verificar_sucursal(alerta["id_sucursal"])
    lotes = lotes_afectados(base, alerta)

    if request.method == "POST":
        if usuario()["rol"] != "Supervisor" and usuario()["rol"] != "Administrador":
            flash("Solo un supervisor puede cambiar el estado de una alerta (RF-012).", "error")
            return redirect(url_for("alertas.detalle", id_alerta=id_alerta))
        accion = request.form.get("accion")
        comentario = request.form.get("comentario", "").strip()
        if accion not in SIGUIENTE or alerta["estado_alerta"] not in PERMITIDO[accion]:
            flash("Esa acción no es válida para el estado actual de la alerta.", "error")
        elif accion in ("Atender", "Cerrar") and not comentario:
            flash("Para atender o cerrar una alerta debes escribir un comentario.", "error")
        else:
            cerrar_con_decisiones(base, alerta, accion, comentario or "Alerta reconocida.", lotes)
            return redirect(url_for("alertas.detalle", id_alerta=id_alerta))

    historial = base.q(
        "SELECT h.*, u.nombre_completo FROM historial_atencion_alertas h JOIN usuarios u ON u.id_usuario = h.id_usuario "
        "WHERE h.id_alerta = %s ORDER BY h.fecha_registro", (id_alerta,))
    return render_template("alerta_detalle.html", a=alerta, historial=historial, lotes=lotes,
                           acciones=[x for x, estados in PERMITIDO.items() if alerta["estado_alerta"] in estados])


def cerrar_con_decisiones(base, alerta, accion, comentario, lotes):
    yo = usuario()["id_usuario"]
    with candado, base.transaccion():
        base.ex("UPDATE alertas SET estado_alerta = %s WHERE id_alerta = %s", (SIGUIENTE[accion], alerta["id_alerta"]))
        base.ex("INSERT INTO historial_atencion_alertas (id_alerta, id_usuario, accion_tomada, comentario) VALUES (%s,%s,%s,%s)",
                (alerta["id_alerta"], yo, accion, comentario))
        auditar(base, yo, "alertas", "UPDATE", f"Alerta {alerta['id_alerta']}: {accion} — {comentario}")
        if accion == "Cerrar":
            ahora = base.ahora()
            dias_n = config_sucursal(base, alerta["id_sucursal"])["dias_anticipacion_caducidad"]
            for lote in lotes:
                decision = request.form.get(f"lote_{lote['id_lote']}")
                if decision == "merma":
                    # RN-005 / RD-004: baja del lote como merma con motivo.
                    motivo = ("Baja por ruptura de cadena de frío" if alerta["tipo_alerta"] == "Cadena_de_frio"
                              else "Baja de lote vencido (RN-005)")
                    base.ex("INSERT INTO movimientos_inventario (id_lote, id_usuario, tipo_movimiento, cantidad, motivo_merma, "
                            "sugerido_por_fefo) VALUES (%s,%s,'Merma',%s,%s,0)", (lote["id_lote"], yo, lote["cantidad_actual"], motivo))
                    base.ex("UPDATE lotes SET cantidad_actual = 0 WHERE id_lote = %s", (lote["id_lote"],))
                    base.ex("INSERT INTO historial_estados_lote (id_lote, estado_anterior, estado_nuevo, motivo_cambio, id_usuario) "
                            "VALUES (%s,%s,%s,%s,%s)", (lote["id_lote"], lote["estado_lote"], lote["estado_lote"], motivo + " — existencia en 0", yo))
                    auditar(base, yo, "lotes", "UPDATE", f"Merma total del lote {lote['codigo_lote']}: {motivo}")
                elif decision == "liberar" and lote["estado_lote"] == "Retenido":
                    nuevo = estado_por_caducidad(lote, ahora, dias_n)
                    base.ex("UPDATE lotes SET estado_lote = %s WHERE id_lote = %s", (nuevo, lote["id_lote"]))
                    base.ex("INSERT INTO historial_estados_lote (id_lote, estado_anterior, estado_nuevo, motivo_cambio, id_usuario) "
                            "VALUES (%s,'Retenido',%s,%s,%s)", (lote["id_lote"], nuevo, "Liberado por el supervisor: " + comentario, yo))
                    auditar(base, yo, "lotes", "UPDATE", f"Lote {lote['codigo_lote']} liberado")
            if alerta["tipo_alerta"] == "Cadena_de_frio":
                otra = base.q1("SELECT 1 FROM alertas WHERE id_equipo = %s AND tipo_alerta = 'Cadena_de_frio' "
                               "AND estado_alerta <> 'Cerrada'", (alerta["id_equipo"],))
                if not otra:
                    base.ex("UPDATE equipos_almacenamiento SET estado_operativo = 'normal' "
                            "WHERE id_equipo = %s AND estado_operativo = 'alerta_temperatura'", (alerta["id_equipo"],))
        ciclo(base)
    flash({"Reconocer": "Alerta reconocida.", "Atender": "Alerta en atención.", "Cerrar": "Alerta cerrada."}[accion], "ok")
