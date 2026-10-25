"""Sesión, roles y control de acceso por sucursal (RF-001, RNF-003, RNF-004)."""
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from .bd import bd

ROLES = ("Empleado", "Supervisor", "Administrador")


def usuario():
    return g.get("usuario")


def es_admin():
    u = usuario()
    return bool(u and u["rol"] == "Administrador")


def es_supervisor():
    u = usuario()
    return bool(u and u["rol"] == "Supervisor")


def requiere_sesion(vista):
    @wraps(vista)
    def envoltura(*a, **k):
        if not usuario():
            return redirect(url_for("auth.login", siguiente=request.path))
        return vista(*a, **k)

    return envoltura


def requiere_rol(*roles):
    def decorador(vista):
        @wraps(vista)
        def envoltura(*a, **k):
            if not usuario():
                return redirect(url_for("auth.login", siguiente=request.path))
            if usuario()["rol"] not in roles:
                flash("Tu rol no tiene permiso para esta sección.", "error")
                return redirect(url_for("panel.inicio"))
            return vista(*a, **k)

        return envoltura

    return decorador


def sucursal_actual():
    """Sucursal con la que trabaja el usuario.

    Empleados y supervisores: siempre la suya (RNF-004).
    Administrador: la que eligió en la barra superior.
    """
    u = usuario()
    if not u:
        return None
    if u["rol"] != "Administrador":
        return u["id_sucursal"]
    elegida = session.get("sucursal_admin")
    if not elegida:
        fila = bd().q1("SELECT id_sucursal FROM sucursales WHERE activa = 1 ORDER BY id_sucursal LIMIT 1")
        elegida = fila["id_sucursal"] if fila else None
        session["sucursal_admin"] = elegida
    return elegida


def verificar_sucursal(id_sucursal):
    """Niega el acceso a datos de otra sucursal (RNF-004)."""
    if es_admin():
        return
    if id_sucursal != usuario()["id_sucursal"]:
        abort(403)
