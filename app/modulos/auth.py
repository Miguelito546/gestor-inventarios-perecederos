"""RF-001 Iniciar sesión."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from datetime import datetime

from ..bd import bd, auditar
from ..seguridad import usuario

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if usuario():
        return redirect(url_for("panel.inicio"))
    if request.method == "POST":
        nombre = request.form.get("usuario", "").strip()
        contrasena = request.form.get("contrasena", "")
        u = bd().q1("SELECT * FROM usuarios WHERE username = %s", (nombre,))
        # RI-001: el mensaje no revela cuál dato falló; un usuario desactivado tampoco entra.
        if not u or not u["activo"] or not check_password_hash(u["password_hash"], contrasena):
            flash("Usuario o contraseña incorrectos, o la cuenta no está activa.", "error")
            return render_template("login.html", usuario=nombre), 401
        session.clear()
        session.permanent = True
        session["id_usuario"] = u["id_usuario"]
        session["ultima_actividad"] = datetime.now().timestamp()
        siguiente = request.args.get("siguiente", "")
        return redirect(siguiente if siguiente.startswith("/") and not siguiente.startswith("//") else url_for("panel.inicio"))
    return render_template("login.html")


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))
