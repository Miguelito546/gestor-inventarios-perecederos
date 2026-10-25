"""Descuentos dinámicos y donación.

RF-014 Sugerir descuento dinámico (las sugerencias las crea motor.py; aquí se autorizan)
RF-015 Proponer donación (RN-004)
"""
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..bd import auditar, bd
from ..motor import candado, config_sucursal
from ..seguridad import requiere_rol, sucursal_actual, usuario, verificar_sucursal
from .inventario import a_decimal

bp = Blueprint("aprovechamiento", __name__)


# ---------------------------------------------------------------- RF-014
@bp.route("/descuentos", methods=["GET", "POST"])
@requiere_rol("Supervisor", "Administrador")
def descuentos():
    base = bd()
    suc = sucursal_actual()
    if request.method == "POST":
        s = base.q1("SELECT s.*, l.id_sucursal, l.codigo_lote FROM sugerencias_descuento s JOIN lotes l ON l.id_lote = s.id_lote "
                    "WHERE s.id_descuento = %s", (request.form.get("id_descuento"),))
        if not s:
            abort(404)
        verificar_sucursal(s["id_sucursal"])
        yo = usuario()["id_usuario"]
        if s["estado_autorizacion"] != "Pendiente":
            flash("Esa sugerencia ya fue respondida.", "error")
        elif request.form.get("accion") == "autorizar":
            with base.transaccion():
                base.ex("UPDATE sugerencias_descuento SET estado_autorizacion = 'Autorizado', id_supervisor_autoriza = %s, "
                        "fecha_respuesta = NOW() WHERE id_descuento = %s", (yo, s["id_descuento"]))
                base.ex("INSERT INTO movimientos_inventario (id_lote, id_usuario, tipo_movimiento, cantidad, motivo_merma, sugerido_por_fefo) "
                        "VALUES (%s,%s,'Ajuste_Descuento',0,%s,0)",
                        (s["id_lote"], yo, f"Descuento autorizado del {s['porcentaje_sugerido']:.0f} %"))
                auditar(base, yo, "sugerencias_descuento", "UPDATE",
                        f"Descuento {s['porcentaje_sugerido']:.0f} % autorizado para {s['codigo_lote']}")
            flash(f"Descuento del {s['porcentaje_sugerido']:.0f} % autorizado para {s['codigo_lote']}.", "ok")
        else:
            motivo = request.form.get("motivo", "").strip()
            if not motivo:
                flash("Para rechazar escribe el motivo.", "error")
            else:
                base.ex("UPDATE sugerencias_descuento SET estado_autorizacion = 'Rechazado', id_supervisor_autoriza = %s, "
                        "motivo_rechazo = %s, fecha_respuesta = NOW() WHERE id_descuento = %s", (yo, motivo, s["id_descuento"]))
                auditar(base, yo, "sugerencias_descuento", "UPDATE", f"Descuento rechazado para {s['codigo_lote']}: {motivo}")
                flash("Sugerencia rechazada; no se volverá a sugerir ese porcentaje para el lote.", "ok")
        return redirect(url_for("aprovechamiento.descuentos"))
    consulta = (
        "SELECT s.*, l.codigo_lote, l.cantidad_actual, l.fecha_caducidad, l.estado_lote, i.nombre AS insumo, i.unidad_medida, "
        "TIMESTAMPDIFF(HOUR, NOW(), l.fecha_caducidad) AS horas, u.nombre_completo "
        "FROM sugerencias_descuento s JOIN lotes l ON l.id_lote = s.id_lote JOIN insumos i ON i.id_insumo = l.id_insumo "
        "LEFT JOIN usuarios u ON u.id_usuario = s.id_supervisor_autoriza WHERE l.id_sucursal = %s ")
    return render_template(
        "descuentos.html",
        pendientes=base.q(consulta + "AND s.estado_autorizacion = 'Pendiente' ORDER BY l.fecha_caducidad", (suc,)),
        historial=base.q(consulta + "AND s.estado_autorizacion <> 'Pendiente' ORDER BY s.fecha_respuesta DESC LIMIT 50", (suc,)))


# ---------------------------------------------------------------- RF-015
def lotes_elegibles(base, id_sucursal):
    """RN-004: próximos a vencer, con existencia, sin ruptura de cadena de frío y con ≥ 24 h antes de vencer."""
    horas = config_sucursal(base, id_sucursal)["horas_min_donacion"]
    return base.q(
        "SELECT l.*, i.nombre AS insumo, i.unidad_medida, TIMESTAMPDIFF(HOUR, NOW(), l.fecha_caducidad) AS horas, "
        "l.cantidad_actual - COALESCE((SELECT SUM(d.cantidad_donada) FROM detalle_donacion_lotes d "
        "  JOIN propuestas_donacion p ON p.id_donacion = d.id_donacion "
        "  WHERE d.id_lote = l.id_lote AND p.estado_propuesta = 'Propuesta'), 0) AS disponible "
        "FROM lotes l JOIN insumos i ON i.id_insumo = l.id_insumo "
        "WHERE l.id_sucursal = %s AND l.estado_lote = 'Próximo a vencer' AND l.cantidad_actual > 0 "
        "AND l.fecha_caducidad >= NOW() + INTERVAL %s HOUR "
        "AND NOT EXISTS (SELECT 1 FROM alertas a WHERE a.id_equipo = l.id_equipo AND a.tipo_alerta = 'Cadena_de_frio' "
        "  AND a.estado_alerta <> 'Cerrada') ORDER BY l.fecha_caducidad", (id_sucursal, horas))


@bp.route("/donaciones", methods=["GET", "POST"])
@requiere_rol("Supervisor", "Administrador")
def donaciones():
    base = bd()
    suc = sucursal_actual()
    yo = usuario()["id_usuario"]
    bancos = base.q("SELECT * FROM bancos_alimentos WHERE activo = 1 ORDER BY nombre_institucion")
    elegibles = lotes_elegibles(base, suc)
    if request.method == "POST" and request.form.get("accion") == "proponer":
        banco = next((b for b in bancos if str(b["id_banco"]) == request.form.get("id_banco")), None)
        elegidos = []
        for l in elegibles:
            if request.form.get(f"sel_{l['id_lote']}"):
                cantidad = a_decimal(request.form.get(f"cant_{l['id_lote']}"))
                if cantidad is None or cantidad <= 0 or cantidad > l["disponible"]:
                    flash(f"Cantidad inválida para {l['codigo_lote']} (disponible: {l['disponible']}).", "error")
                    return redirect(url_for("aprovechamiento.donaciones"))
                elegidos.append((l, cantidad))
        if not bancos:
            flash("No hay bancos de alimentos registrados; regístralo en Catálogos.", "error")
        elif not banco:
            flash("Selecciona el banco de alimentos.", "error")
        elif not elegidos:
            flash("Selecciona al menos un lote elegible.", "error")
        else:
            with candado, base.transaccion():
                hoy = base.ahora().strftime("%Y%m%d")
                n = base.q1("SELECT COUNT(*) AS n FROM propuestas_donacion WHERE folio_donacion LIKE %s", (f"DON-{hoy}-%",))["n"] + 1
                folio = f"DON-{hoy}-{n:03d}"
                id_don = base.ex("INSERT INTO propuestas_donacion (folio_donacion, id_banco, id_supervisor) VALUES (%s,%s,%s)",
                                 (folio, banco["id_banco"], yo))
                for l, cantidad in elegidos:
                    base.ex("INSERT INTO detalle_donacion_lotes (id_donacion, id_lote, cantidad_donada) VALUES (%s,%s,%s)",
                            (id_don, l["id_lote"], cantidad))
                auditar(base, yo, "propuestas_donacion", "INSERT", f"Propuesta {folio} a {banco['nombre_institucion']}")
            flash(f"Propuesta de donación {folio} generada.", "ok")
        return redirect(url_for("aprovechamiento.donaciones"))

    if request.method == "POST" and request.form.get("accion") in ("confirmar", "cancelar"):
        p = base.q1("SELECT p.*, u.id_sucursal FROM propuestas_donacion p JOIN usuarios u ON u.id_usuario = p.id_supervisor "
                    "WHERE p.id_donacion = %s", (request.form.get("id_donacion"),))
        if not p or p["estado_propuesta"] != "Propuesta":
            flash("La propuesta no existe o ya fue procesada.", "error")
            return redirect(url_for("aprovechamiento.donaciones"))
        detalle = base.q("SELECT d.*, l.codigo_lote, l.id_sucursal, l.cantidad_actual FROM detalle_donacion_lotes d "
                         "JOIN lotes l ON l.id_lote = d.id_lote WHERE d.id_donacion = %s", (p["id_donacion"],))
        if detalle:
            verificar_sucursal(detalle[0]["id_sucursal"])
        if request.form["accion"] == "cancelar":
            base.ex("UPDATE propuestas_donacion SET estado_propuesta = 'Cancelada' WHERE id_donacion = %s", (p["id_donacion"],))
            auditar(base, yo, "propuestas_donacion", "UPDATE", f"Propuesta {p['folio_donacion']} cancelada")
            flash(f"Propuesta {p['folio_donacion']} cancelada.", "ok")
            return redirect(url_for("aprovechamiento.donaciones"))
        ids_elegibles = {l["id_lote"] for l in lotes_elegibles(base, detalle[0]["id_sucursal"])} if detalle else set()
        with candado, base.transaccion():
            entregados, excluidos = 0, []
            for d in detalle:
                cantidad = min(Decimal(d["cantidad_donada"]), Decimal(d["cantidad_actual"]))
                if d["id_lote"] not in ids_elegibles or cantidad <= 0:
                    excluidos.append(d["codigo_lote"])  # dejó de ser elegible antes de confirmar
                    base.ex("DELETE FROM detalle_donacion_lotes WHERE id_detalle_donacion = %s", (d["id_detalle_donacion"],))
                    continue
                base.ex("UPDATE lotes SET cantidad_actual = cantidad_actual - %s WHERE id_lote = %s", (cantidad, d["id_lote"]))
                base.ex("INSERT INTO movimientos_inventario (id_lote, id_usuario, tipo_movimiento, cantidad, motivo_merma, sugerido_por_fefo) "
                        "VALUES (%s,%s,'Donacion',%s,%s,0)", (d["id_lote"], yo, cantidad, f"Donación {p['folio_donacion']}"))
                entregados += 1
            estado = "Confirmada" if entregados else "Cancelada"
            base.ex("UPDATE propuestas_donacion SET estado_propuesta = %s, fecha_confirmacion = NOW() WHERE id_donacion = %s",
                    (estado, p["id_donacion"]))
            auditar(base, yo, "propuestas_donacion", "UPDATE", f"Propuesta {p['folio_donacion']}: {estado}")
        if excluidos:
            flash("Se excluyeron lotes que dejaron de ser elegibles: " + ", ".join(excluidos), "info")
        flash(f"Donación {p['folio_donacion']} {estado.lower()}.", "ok")
        return redirect(url_for("aprovechamiento.donaciones"))

    propuestas = base.q(
        "SELECT p.*, b.nombre_institucion, u.nombre_completo, "
        "(SELECT GROUP_CONCAT(CONCAT(l.codigo_lote, ' (', d.cantidad_donada + 0, ' ', i.unidad_medida, ')') SEPARATOR ', ') "
        " FROM detalle_donacion_lotes d JOIN lotes l ON l.id_lote = d.id_lote JOIN insumos i ON i.id_insumo = l.id_insumo "
        " WHERE d.id_donacion = p.id_donacion) AS lotes "
        "FROM propuestas_donacion p JOIN bancos_alimentos b ON b.id_banco = p.id_banco "
        "JOIN usuarios u ON u.id_usuario = p.id_supervisor "
        "WHERE EXISTS (SELECT 1 FROM detalle_donacion_lotes d JOIN lotes l ON l.id_lote = d.id_lote "
        "  WHERE d.id_donacion = p.id_donacion AND l.id_sucursal = %s) OR (u.id_sucursal = %s) "
        "ORDER BY p.fecha_propuesta DESC LIMIT 50", (suc, suc))
    return render_template("donaciones.html", elegibles=elegibles, bancos=bancos, propuestas=propuestas)
