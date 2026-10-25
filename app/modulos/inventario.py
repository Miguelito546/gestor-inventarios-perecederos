"""Módulo de Inventario.

RF-002 Consultar inventario   RF-005 Registrar insumo (catálogos)
RF-006 Registrar lote         RF-007 Actualizar existencias (FEFO)
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..bd import auditar, bd
from ..motor import candado, ciclo
from ..seguridad import requiere_rol, requiere_sesion, sucursal_actual, usuario

bp = Blueprint("inventario", __name__)

ESTADOS = ("Fresco", "Próximo a vencer", "Vencido", "Retenido")


def a_decimal(texto):
    try:
        valor = Decimal(str(texto).replace(",", ".").strip())
        return valor if valor.is_finite() else None
    except (InvalidOperation, AttributeError):
        return None


def a_fecha(texto):
    try:
        return datetime.fromisoformat(texto.strip())
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------- RF-002
@bp.route("/inventario")
@requiere_sesion
def consultar():
    base = bd()
    suc = sucursal_actual()
    f = {k: request.args.get(k, "") for k in ("insumo", "estado", "desde", "hasta", "agotados")}
    sql = (
        "SELECT l.*, i.nombre AS insumo, i.categoria, i.unidad_medida, e.nombre_equipo, p.nombre_empresa AS proveedor, "
        "TIMESTAMPDIFF(HOUR, NOW(), l.fecha_caducidad) AS horas_restantes "
        "FROM lotes l JOIN insumos i ON i.id_insumo = l.id_insumo "
        "JOIN equipos_almacenamiento e ON e.id_equipo = l.id_equipo "
        "JOIN proveedores p ON p.id_proveedor = l.id_proveedor WHERE l.id_sucursal = %s"
    )
    args = [suc]
    if not f["agotados"]:
        sql += " AND l.cantidad_actual > 0"
    if f["insumo"]:
        sql += " AND l.id_insumo = %s"
        args.append(f["insumo"])
    if f["estado"] in ESTADOS:
        sql += " AND l.estado_lote = %s"
        args.append(f["estado"])
    if f["desde"]:
        sql += " AND DATE(l.fecha_caducidad) >= %s"
        args.append(f["desde"])
    if f["hasta"]:
        sql += " AND DATE(l.fecha_caducidad) <= %s"
        args.append(f["hasta"])
    sql += " ORDER BY l.fecha_caducidad"
    lotes = base.q(sql, args)
    insumos = base.q("SELECT id_insumo, nombre FROM insumos ORDER BY nombre")
    return render_template("inventario.html", lotes=lotes, insumos=insumos, estados=ESTADOS, f=f)


# ---------------------------------------------------------------- RF-005 y catálogos
@bp.route("/catalogos", methods=["GET", "POST"])
@requiere_rol("Supervisor", "Administrador")
def catalogos():
    base = bd()
    if request.method == "POST":
        tipo = request.form.get("tipo")
        if tipo == "insumo":
            registrar_insumo(base)
        elif tipo == "proveedor":
            nombre = request.form.get("nombre_empresa", "").strip()
            if not nombre:
                flash("El nombre del proveedor es obligatorio.", "error")
            else:
                nuevo = base.ex(
                    "INSERT INTO proveedores (nombre_empresa, contacto_nombre, telefono, email) VALUES (%s,%s,%s,%s)",
                    (nombre, request.form.get("contacto_nombre") or None, request.form.get("telefono") or None,
                     request.form.get("email") or None))
                auditar(base, usuario()["id_usuario"], "proveedores", "INSERT", f"Proveedor {nuevo}: {nombre}")
                flash(f"Proveedor registrado con id {nuevo}.", "ok")
        elif tipo == "banco":
            nombre = request.form.get("nombre_institucion", "").strip()
            direccion = request.form.get("direccion", "").strip()
            if not nombre or not direccion:
                flash("Nombre y dirección del banco de alimentos son obligatorios.", "error")
            else:
                nuevo = base.ex(
                    "INSERT INTO bancos_alimentos (nombre_institucion, direccion, contacto_telefono, email) VALUES (%s,%s,%s,%s)",
                    (nombre, direccion, request.form.get("contacto_telefono") or None, request.form.get("email") or None))
                auditar(base, usuario()["id_usuario"], "bancos_alimentos", "INSERT", f"Banco {nuevo}: {nombre}")
                flash(f"Banco de alimentos registrado con id {nuevo}.", "ok")
        return redirect(url_for("inventario.catalogos"))
    return render_template(
        "catalogos.html",
        insumos=base.q("SELECT * FROM insumos ORDER BY nombre"),
        proveedores=base.q("SELECT * FROM proveedores ORDER BY nombre_empresa"),
        bancos=base.q("SELECT * FROM bancos_alimentos ORDER BY nombre_institucion"),
    )


def registrar_insumo(base):
    d = {k: request.form.get(k, "").strip() for k in ("nombre", "categoria", "unidad_medida", "tmin", "tmax")}
    faltan = [k for k, v in d.items() if not v]
    if faltan:
        flash("Faltan datos obligatorios: " + ", ".join(faltan), "error")
        return
    tmin, tmax = a_decimal(d["tmin"]), a_decimal(d["tmax"])
    if tmin is None or tmax is None:
        flash("Las temperaturas deben ser números.", "error")
        return
    if tmin > tmax:
        flash("La temperatura mínima no puede ser mayor que la máxima.", "error")
        return
    if base.q1("SELECT 1 FROM insumos WHERE nombre = %s", (d["nombre"],)):
        flash(f"Ya existe un insumo llamado «{d['nombre']}».", "error")
        return
    nuevo = base.ex(
        "INSERT INTO insumos (nombre, categoria, unidad_medida, temp_min_conservacion, temp_max_conservacion) "
        "VALUES (%s,%s,%s,%s,%s)", (d["nombre"], d["categoria"], d["unidad_medida"], tmin, tmax))
    auditar(base, usuario()["id_usuario"], "insumos", "INSERT", f"Insumo {nuevo}: {d['nombre']}")
    flash(f"Insumo «{d['nombre']}» registrado con identificador {nuevo}.", "ok")


# ---------------------------------------------------------------- RF-006
@bp.route("/lotes/nuevo", methods=["GET", "POST"])
@requiere_rol("Empleado", "Supervisor", "Administrador")
def registrar_lote():
    base = bd()
    suc = sucursal_actual()
    insumos = base.q("SELECT * FROM insumos ORDER BY nombre")
    proveedores = base.q("SELECT * FROM proveedores ORDER BY nombre_empresa")
    equipos = base.q("SELECT * FROM equipos_almacenamiento WHERE id_sucursal = %s AND estado_operativo <> 'fuera_de_servicio'", (suc,))
    datos = request.form.to_dict() if request.method == "POST" else {
        "fecha_recepcion": base.ahora().strftime("%Y-%m-%dT%H:%M")}
    if request.method == "POST":
        errores = []
        for campo, nombre in (("id_insumo", "insumo"), ("id_proveedor", "proveedor"), ("cantidad", "cantidad"),
                              ("fecha_recepcion", "fecha de recepción"), ("fecha_caducidad", "fecha de caducidad"),
                              ("id_equipo", "equipo de almacenamiento")):
            if not datos.get(campo):
                errores.append(f"Falta {nombre}.")
        cantidad = a_decimal(datos.get("cantidad"))
        recepcion, caducidad = a_fecha(datos.get("fecha_recepcion")), a_fecha(datos.get("fecha_caducidad"))
        if datos.get("cantidad") and (cantidad is None or cantidad <= 0):
            errores.append("La cantidad debe ser un número mayor que cero.")
        if recepcion and caducidad and caducidad < recepcion:
            errores.append("La fecha de caducidad no puede ser anterior a la de recepción.")
        equipo = next((e for e in equipos if str(e["id_equipo"]) == datos.get("id_equipo")), None)
        if datos.get("id_equipo") and not equipo:
            errores.append("El equipo no pertenece a tu sucursal.")
        insumo = next((i for i in insumos if str(i["id_insumo"]) == datos.get("id_insumo")), None)
        if insumo and equipo:
            # RD-001: el equipo debe conservar el insumo dentro de su rango.
            if equipo["temp_max_permitida"] > insumo["temp_max_conservacion"] or equipo["temp_min_permitida"] < insumo["temp_min_conservacion"] - 10:
                errores.append(f"El equipo {equipo['nombre_equipo']} no es adecuado para {insumo['nombre']} "
                               f"({insumo['temp_min_conservacion']} a {insumo['temp_max_conservacion']} °C).")
        codigo = (datos.get("codigo_lote") or "").strip().upper()
        if not codigo and insumo and recepcion:
            prefijo = f"LOT-{insumo['nombre'][:5].upper().replace(' ', '')}-{recepcion:%Y%m%d}-"
            n = 1
            while base.q1("SELECT 1 FROM lotes WHERE codigo_lote = %s", (f"{prefijo}{n:02d}",)):
                n += 1
            codigo = f"{prefijo}{n:02d}"
        if codigo and base.q1("SELECT 1 FROM lotes WHERE codigo_lote = %s", (codigo,)):
            errores.append(f"El lote {codigo} ya existe.")
        if errores:
            for e in errores:
                flash(e, "error")
        else:
            with candado, base.transaccion():
                nuevo = base.ex(
                    "INSERT INTO lotes (codigo_lote, id_insumo, id_proveedor, id_sucursal, id_equipo, cantidad_inicial, "
                    "cantidad_actual, fecha_recepcion, fecha_caducidad, estado_lote) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Fresco')",
                    (codigo, insumo["id_insumo"], datos["id_proveedor"], suc, equipo["id_equipo"], cantidad, cantidad,
                     recepcion, caducidad))
                base.ex("INSERT INTO historial_estados_lote (id_lote, estado_anterior, estado_nuevo, motivo_cambio, id_usuario) "
                        "VALUES (%s, NULL, 'Fresco', 'Registro del lote (RF-006)', %s)", (nuevo, usuario()["id_usuario"]))
                auditar(base, usuario()["id_usuario"], "lotes", "INSERT",
                        f"Lote {codigo}: {cantidad} {insumo['unidad_medida']} de {insumo['nombre']}")
            ciclo(base)  # calcula de inmediato su estado real (RF-003)
            estado = base.q1("SELECT estado_lote FROM lotes WHERE id_lote = %s", (nuevo,))["estado_lote"]
            flash(f"Lote {codigo} registrado (identificador {nuevo}). Estado: {estado}.", "ok")
            return redirect(url_for("trazabilidad.lote", id_lote=nuevo))
    return render_template("lote_nuevo.html", insumos=insumos, proveedores=proveedores, equipos=equipos, d=datos)


# ---------------------------------------------------------------- RF-007
@bp.route("/movimientos/nuevo", methods=["GET", "POST"])
@requiere_rol("Empleado", "Supervisor", "Administrador")
def registrar_movimiento():
    base = bd()
    suc = sucursal_actual()
    tipo = request.values.get("tipo", "Consumo")
    id_insumo = request.values.get("id_insumo", "")
    insumos = base.q(
        "SELECT DISTINCT i.* FROM insumos i JOIN lotes l ON l.id_insumo = i.id_insumo "
        "WHERE l.id_sucursal = %s AND l.cantidad_actual > 0 ORDER BY i.nombre", (suc,))
    lotes, sugerido = [], None
    if id_insumo:
        lotes = base.q(
            "SELECT l.*, i.unidad_medida, e.nombre_equipo FROM lotes l JOIN insumos i ON i.id_insumo = l.id_insumo "
            "JOIN equipos_almacenamiento e ON e.id_equipo = l.id_equipo "
            "WHERE l.id_sucursal = %s AND l.id_insumo = %s AND l.cantidad_actual > 0 ORDER BY l.fecha_caducidad",
            (suc, id_insumo))
        # RN-001 FEFO: el que vence primero entre los que se pueden usar (RD-004).
        usables = [l for l in lotes if l["estado_lote"] in ("Fresco", "Próximo a vencer")] if tipo == "Consumo" else lotes
        sugerido = usables[0] if usables else None

    if request.method == "POST" and request.form.get("confirmar"):
        lote = next((l for l in lotes if str(l["id_lote"]) == request.form.get("id_lote")), None)
        cantidad = a_decimal(request.form.get("cantidad"))
        motivo = request.form.get("motivo", "").strip()
        error = None
        if tipo not in ("Consumo", "Merma"):
            error = "Tipo de movimiento inválido."
        elif not lote:
            error = "Selecciona un lote de tu sucursal."
        elif cantidad is None or cantidad <= 0:
            error = "La cantidad debe ser un número mayor que cero."
        elif cantidad > lote["cantidad_actual"]:
            error = f"La cantidad supera la existencia del lote ({lote['cantidad_actual']} {lote['unidad_medida']})."
        elif tipo == "Consumo" and lote["estado_lote"] in ("Vencido", "Retenido"):
            error = f"El lote está «{lote['estado_lote']}»: solo se permite registrar merma (RD-004)."
        elif tipo == "Merma" and not motivo:
            error = "La merma requiere un motivo."
        if error:
            flash(error, "error")
        else:
            with candado, base.transaccion():
                actual = base.q1("SELECT cantidad_actual FROM lotes WHERE id_lote = %s FOR UPDATE", (lote["id_lote"],))
                if cantidad > actual["cantidad_actual"]:
                    raise ValueError("Existencia cambió")
                base.ex("UPDATE lotes SET cantidad_actual = cantidad_actual - %s WHERE id_lote = %s", (cantidad, lote["id_lote"]))
                base.ex(
                    "INSERT INTO movimientos_inventario (id_lote, id_usuario, tipo_movimiento, cantidad, motivo_merma, sugerido_por_fefo) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (lote["id_lote"], usuario()["id_usuario"], tipo, cantidad, motivo or None,
                     int(bool(sugerido and sugerido["id_lote"] == lote["id_lote"]))))
                auditar(base, usuario()["id_usuario"], "movimientos_inventario", "INSERT",
                        f"{tipo} de {cantidad} en lote {lote['codigo_lote']}" + (f" ({motivo})" if motivo else ""))
            nueva = lote["cantidad_actual"] - cantidad
            flash(f"{'Consumo registrado' if tipo == 'Consumo' else 'Merma registrada'}. Nueva existencia de {lote['codigo_lote']}: {nueva} {lote['unidad_medida']}.", "ok")
            return redirect(url_for("inventario.registrar_movimiento", tipo=tipo, id_insumo=id_insumo))
    return render_template("movimiento.html", insumos=insumos, lotes=lotes, sugerido=sugerido,
                           tipo=tipo, id_insumo=id_insumo)
