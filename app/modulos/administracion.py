"""Administración.

RF-017 Gestionar usuarios y roles
RF-018 Gestionar sucursales y umbrales
RNF-011 Consulta de la bitácora
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from ..bd import auditar, bd, reiniciar_base
from ..motor import candado
from ..seguridad import ROLES, requiere_rol, usuario
from .inventario import a_decimal

bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------- RF-017
@bp.route("/usuarios", methods=["GET", "POST"])
@requiere_rol("Administrador")
def usuarios():
    base = bd()
    sucursales = base.q("SELECT * FROM sucursales ORDER BY id_sucursal")
    editar = None
    if request.args.get("editar"):
        editar = base.q1("SELECT * FROM usuarios WHERE id_usuario = %s", (request.args["editar"],))
    if request.method == "POST":
        d = {k: request.form.get(k, "").strip() for k in ("id_usuario", "nombre_completo", "username", "contrasena", "rol", "id_sucursal")}
        activo = 1 if request.form.get("activo") else 0
        errores = []
        if not d["nombre_completo"] or not d["username"]:
            errores.append("Nombre y usuario son obligatorios.")
        if d["rol"] not in ROLES:
            errores.append("Elige un rol válido.")
        if d["rol"] in ("Empleado", "Supervisor") and not d["id_sucursal"]:
            errores.append("Los empleados y supervisores necesitan una sucursal.")
        if not d["id_usuario"] and len(d["contrasena"]) < 6:
            errores.append("La contraseña inicial debe tener al menos 6 caracteres.")
        if d["contrasena"] and len(d["contrasena"]) < 6:
            errores.append("La contraseña debe tener al menos 6 caracteres.")
        repetido = base.q1("SELECT id_usuario FROM usuarios WHERE username = %s AND id_usuario <> %s",
                           (d["username"], d["id_usuario"] or 0))
        if repetido:
            errores.append(f"El usuario «{d['username']}» ya existe.")
        if d["id_usuario"] and int(d["id_usuario"]) == usuario()["id_usuario"] and (not activo or d["rol"] != "Administrador"):
            errores.append("No puedes desactivarte ni quitarte el rol de administrador a ti mismo.")
        sucursal = int(d["id_sucursal"]) if d["id_sucursal"] and d["rol"] != "Administrador" else None
        if errores:
            for e in errores:
                flash(e, "error")
            return redirect(url_for("admin.usuarios", editar=d["id_usuario"] or None))
        yo = usuario()["id_usuario"]
        if d["id_usuario"]:
            base.ex("UPDATE usuarios SET nombre_completo=%s, username=%s, rol=%s, id_sucursal=%s, activo=%s WHERE id_usuario=%s",
                    (d["nombre_completo"], d["username"], d["rol"], sucursal, activo, d["id_usuario"]))
            if d["contrasena"]:
                base.ex("UPDATE usuarios SET password_hash=%s WHERE id_usuario=%s",
                        (generate_password_hash(d["contrasena"]), d["id_usuario"]))
            auditar(base, yo, "usuarios", "UPDATE",
                    f"Usuario {d['username']}: rol {d['rol']}, sucursal {sucursal}, {'activo' if activo else 'inactivo'}"
                    + (", contraseña cambiada" if d["contrasena"] else ""))
            flash(f"Usuario {d['username']} actualizado. Los permisos se aplican en su siguiente acción.", "ok")
        else:
            nuevo = base.ex("INSERT INTO usuarios (id_sucursal, nombre_completo, username, password_hash, rol, activo) "
                            "VALUES (%s,%s,%s,%s,%s,%s)",
                            (sucursal, d["nombre_completo"], d["username"], generate_password_hash(d["contrasena"]), d["rol"], activo))
            auditar(base, yo, "usuarios", "INSERT", f"Usuario {nuevo} {d['username']} ({d['rol']})")
            flash(f"Usuario {d['username']} creado.", "ok")
        return redirect(url_for("admin.usuarios"))
    lista = base.q("SELECT u.*, s.nombre AS sucursal FROM usuarios u LEFT JOIN sucursales s ON s.id_sucursal = u.id_sucursal "
                   "ORDER BY u.activo DESC, u.rol, u.nombre_completo")
    return render_template("usuarios.html", usuarios=lista, sucursales=sucursales, roles=ROLES, editar=editar)


# ---------------------------------------------------------------- RF-018
@bp.route("/sucursales", methods=["GET", "POST"])
@requiere_rol("Administrador")
def sucursales():
    base = bd()
    yo = usuario()["id_usuario"]
    if request.method == "POST":
        tipo = request.form.get("tipo")
        if tipo == "sucursal":
            id_s = request.form.get("id_sucursal")
            nombre, direccion = request.form.get("nombre", "").strip(), request.form.get("direccion", "").strip()
            activa = 1 if request.form.get("activa") else 0
            if not nombre or not direccion:
                flash("Nombre y dirección son obligatorios.", "error")
            elif base.q1("SELECT 1 FROM sucursales WHERE nombre = %s AND id_sucursal <> %s", (nombre, id_s or 0)):
                flash("Ya existe una sucursal con ese nombre.", "error")
            elif id_s:
                base.ex("UPDATE sucursales SET nombre=%s, direccion=%s, telefono=%s, activa=%s WHERE id_sucursal=%s",
                        (nombre, direccion, request.form.get("telefono") or None, activa, id_s))
                auditar(base, yo, "sucursales", "UPDATE", f"Sucursal {id_s}: {nombre}")
                flash("Sucursal actualizada.", "ok")
            else:
                with base.transaccion():
                    nuevo = base.ex("INSERT INTO sucursales (nombre, direccion, telefono) VALUES (%s,%s,%s)",
                                    (nombre, direccion, request.form.get("telefono") or None))
                    base.ex("INSERT INTO configuracion_umbrales (id_sucursal) VALUES (%s)", (nuevo,))
                    auditar(base, yo, "sucursales", "INSERT", f"Sucursal {nuevo}: {nombre}")
                flash(f"Sucursal registrada con los umbrales por defecto. Agrega sus equipos.", "ok")
                return redirect(url_for("admin.sucursales", ver=nuevo))
            return redirect(url_for("admin.sucursales", ver=id_s))
        if tipo == "equipo":
            guardar_equipo(base, yo)
            return redirect(url_for("admin.sucursales", ver=request.form.get("id_sucursal")))
        if tipo == "umbrales":
            guardar_umbrales(base, yo)
            return redirect(url_for("admin.sucursales", ver=request.form.get("id_sucursal")))
    lista = base.q("SELECT s.*, (SELECT COUNT(*) FROM equipos_almacenamiento e WHERE e.id_sucursal = s.id_sucursal) AS equipos "
                   "FROM sucursales s ORDER BY s.id_sucursal")
    ver = request.args.get("ver", type=int) or (lista[0]["id_sucursal"] if lista else None)
    actual = next((s for s in lista if s["id_sucursal"] == ver), None)
    equipos = base.q("SELECT * FROM equipos_almacenamiento WHERE id_sucursal = %s ORDER BY id_equipo", (ver,)) if actual else []
    umbrales = base.q1("SELECT * FROM configuracion_umbrales WHERE id_sucursal = %s", (ver,)) if actual else None
    editar_equipo = request.args.get("equipo", type=int)
    return render_template("sucursales.html", sucursales=lista, actual=actual, equipos=equipos, umbrales=umbrales,
                           editar_equipo=editar_equipo, nueva=request.args.get("nueva"))


def guardar_equipo(base, yo):
    f = request.form
    tipo_eq = f.get("tipo_equipo")
    tmin, tmax = a_decimal(f.get("temp_min")), a_decimal(f.get("temp_max"))
    if not f.get("nombre_equipo", "").strip() or tipo_eq not in ("refrigeracion", "congelacion"):
        flash("Nombre y tipo del equipo son obligatorios.", "error")
        return
    if tmin is None or tmax is None:
        flash("Las temperaturas deben ser números.", "error")
        return
    if tmin > tmax:
        flash("La temperatura mínima no puede ser mayor que la máxima.", "error")
        return
    estado = f.get("estado_operativo", "normal")
    if estado not in ("normal", "alerta_temperatura", "fuera_de_servicio"):
        estado = "normal"
    if f.get("id_equipo"):
        base.ex("UPDATE equipos_almacenamiento SET nombre_equipo=%s, tipo_equipo=%s, temp_min_permitida=%s, temp_max_permitida=%s, "
                "estado_operativo=%s WHERE id_equipo=%s AND id_sucursal=%s",
                (f["nombre_equipo"].strip(), tipo_eq, tmin, tmax, estado, f["id_equipo"], f["id_sucursal"]))
        auditar(base, yo, "equipos_almacenamiento", "UPDATE", f"Equipo {f['id_equipo']}: rango {tmin} a {tmax} °C, {estado}")
        flash("Equipo actualizado.", "ok")
    else:
        nuevo = base.ex("INSERT INTO equipos_almacenamiento (id_sucursal, nombre_equipo, tipo_equipo, temp_min_permitida, "
                        "temp_max_permitida) VALUES (%s,%s,%s,%s,%s)", (f["id_sucursal"], f["nombre_equipo"].strip(), tipo_eq, tmin, tmax))
        auditar(base, yo, "equipos_almacenamiento", "INSERT", f"Equipo {nuevo} en sucursal {f['id_sucursal']}")
        flash("Equipo registrado; el simulador empezará a enviar sus lecturas.", "ok")


def guardar_umbrales(base, yo):
    f = request.form
    campos = ("dias_anticipacion_caducidad", "tiempo_tolerado_temp_min", "pct_descuento_nivel_1",
              "pct_descuento_nivel_2", "horas_min_donacion", "minutos_sin_senal")
    valores = {c: a_decimal(f.get(c)) for c in campos}
    if any(v is None or v < 0 for v in valores.values()):
        flash("Todos los parámetros deben ser números positivos.", "error")
        return
    if valores["pct_descuento_nivel_1"] > 100 or valores["pct_descuento_nivel_2"] > 100:
        flash("Los porcentajes no pueden pasar de 100.", "error")
        return
    if valores["tiempo_tolerado_temp_min"] < 1 or valores["minutos_sin_senal"] < 1:
        flash("El tiempo tolerado y el de sin señal deben ser de al menos 1 minuto.", "error")
        return
    for c in ("dias_anticipacion_caducidad", "tiempo_tolerado_temp_min", "horas_min_donacion", "minutos_sin_senal"):
        valores[c] = int(valores[c])
    base.ex("UPDATE configuracion_umbrales SET " + ", ".join(f"{c} = %s" for c in campos) + " WHERE id_sucursal = %s",
            [valores[c] for c in campos] + [f["id_sucursal"]])
    auditar(base, yo, "configuracion_umbrales", "UPDATE",
            f"Sucursal {f['id_sucursal']}: " + ", ".join(f"{c}={valores[c]}" for c in campos))
    flash("Parámetros guardados; se aplican en las siguientes evaluaciones de alertas.", "ok")


# ---------------------------------------------------------------- RNF-011 y demostración
@bp.route("/bitacora")
@requiere_rol("Administrador")
def bitacora():
    registros = bd().q("SELECT b.*, u.nombre_completo FROM bitacora_auditoria b LEFT JOIN usuarios u ON u.id_usuario = b.id_usuario "
                       "ORDER BY b.id_bitacora DESC LIMIT 300")
    return render_template("bitacora.html", registros=registros)


@bp.route("/reiniciar-demo", methods=["POST"])
@requiere_rol("Administrador")
def reiniciar_demo():
    if request.form.get("confirmacion") != "REINICIAR":
        flash("Escribe REINICIAR para confirmar.", "error")
        return redirect(url_for("admin.bitacora"))
    with candado:
        reiniciar_base()  # también limpia los modos del simulador (tabla simulador_modos)
    session.clear()
    flash("Datos de demostración recargados. Inicia sesión de nuevo.", "ok")
    return redirect(url_for("auth.login"))
