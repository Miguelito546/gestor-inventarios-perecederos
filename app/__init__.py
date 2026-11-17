"""Gestor Inteligente de Inventarios y Trazabilidad de Productos Perecederos — prototipo v1."""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape

import configuracion as cfg
from .bd import bd, cerrar_bd
from .seguridad import sucursal_actual

ESTADO_CLASE = {"Fresco": "verde", "Próximo a vencer": "amarillo", "Vencido": "rojo", "Retenido": "morado"}
SEVERIDAD_CLASE = {"Critica": "rojo", "Alta": "naranja", "Media": "amarillo"}
NOMBRES = {
    "Cadena_de_frio": "Cadena de frío", "Sin_senal": "Sin señal", "En_atencion": "En atención",
    "Critica": "Crítica", "Ajuste_Descuento": "Descuento", "Donacion": "Donación",
    "refrigeracion": "Refrigeración", "congelacion": "Congelación",
    "alerta_temperatura": "Alerta de temperatura", "fuera_de_servicio": "Fuera de servicio", "normal": "Normal",
}


def crear_app():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=cfg.CLAVE_SECRETA,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=cfg.MINUTOS_INACTIVIDAD),
        JSON_AS_ASCII=False,
    )
    app.teardown_appcontext(cerrar_bd)

    # --- Formatos RNF-012: DD/MM/AAAA ---
    @app.template_filter("fecha")
    def fecha(v, hora=True):
        if not v:
            return "—"
        return v.strftime("%d/%m/%Y %H:%M" if hora and isinstance(v, datetime) else "%d/%m/%Y")

    @app.template_filter("num")
    def num(v, dec=2):
        if v is None:
            return "—"
        v = Decimal(v)
        texto = f"{v:,.{dec}f}"
        return texto.rstrip("0").rstrip(".") if "." in texto else texto

    @app.template_filter("nombre")
    def nombre(v):
        return NOMBRES.get(v, v)

    @app.template_filter("clase_estado")
    def clase_estado(v):
        return ESTADO_CLASE.get(v, "gris")

    @app.template_filter("clase_sev")
    def clase_sev(v):
        return SEVERIDAD_CLASE.get(v, "gris")

    # --- Sesión e inactividad (RF-001) ---
    @app.before_request
    def cargar_usuario():
        g.usuario = None
        if request.endpoint in ("static",):
            return
        id_usuario = session.get("id_usuario")
        if not id_usuario:
            return
        ultimo = session.get("ultima_actividad")
        ahora = datetime.now().timestamp()
        if ultimo and ahora - ultimo > cfg.MINUTOS_INACTIVIDAD * 60:
            session.clear()
            flash(f"Tu sesión se cerró tras {cfg.MINUTOS_INACTIVIDAD} min sin actividad.", "info")
            return redirect(url_for("auth.login"))
        u = bd().q1(
            "SELECT u.*, s.nombre AS sucursal FROM usuarios u LEFT JOIN sucursales s ON s.id_sucursal = u.id_sucursal "
            "WHERE u.id_usuario = %s",
            (id_usuario,),
        )
        if not u or not u["activo"]:
            session.clear()
            return redirect(url_for("auth.login"))
        g.usuario = u
        # Las actualizaciones automáticas de pantalla (/api/...) no cuentan como actividad.
        if not request.path.startswith("/api/"):
            session["ultima_actividad"] = ahora

    @app.context_processor
    def contexto():
        u = g.get("usuario")
        datos = {"u": u, "ahora": datetime.now()}
        if u:
            datos["ahora"] = bd().ahora()  # hora de la base (Villahermosa, RNF-012)
            datos["id_sucursal_actual"] = sucursal_actual()
            datos["alertas_pendientes"] = bd().q1(
                "SELECT COUNT(*) AS n FROM alertas WHERE estado_alerta <> 'Cerrada' AND id_sucursal = %s",
                (datos["id_sucursal_actual"],),
            )["n"]
            if u["rol"] == "Administrador":
                datos["sucursales_menu"] = bd().q("SELECT id_sucursal, nombre FROM sucursales ORDER BY id_sucursal")
        return datos

    # --- Estado vacío reutilizable (RF de consulta sin resultados) ---
    @app.template_global()
    def vacio(texto, url=None, accion=None, icono="∅", tipo=""):
        boton = f'<a class="btn chico claro" href="{escape(url)}">{escape(accion)}</a>' if url and accion else ""
        return Markup(f'<div class="vacio {escape(tipo)}"><span class="vacio-icono" aria-hidden="true">{escape(icono)}</span>'
                      f'<p>{escape(texto)}</p>{boton}</div>')

    # --- Pantallas de error con opción de reintentar ---
    @app.errorhandler(404)
    def no_encontrado(_e):
        return render_template("error.html", titulo="No encontramos esta página",
                               mensaje="Puede que el enlace sea incorrecto o que el registro ya no exista."), 404

    @app.errorhandler(500)
    def error_interno(_e):
        g.usuario = None  # no vuelve a consultar la base, que pudo ser la causa del error
        return render_template("error.html", titulo="Algo salió mal",
                               mensaje="No se pudo completar la operación. Revisa la conexión con la base de datos "
                                       "y vuelve a intentarlo."), 500

    @app.errorhandler(403)
    def prohibido(_e):
        flash("No tienes acceso a datos de otra sucursal (RNF-004).", "error")
        return redirect(url_for("panel.inicio"))

    from .modulos import (auth, panel, inventario, monitoreo, alertas, trazabilidad,
                          aprovechamiento, reportes, administracion)
    for modulo in (auth, panel, inventario, monitoreo, alertas, trazabilidad,
                   aprovechamiento, reportes, administracion):
        app.register_blueprint(modulo.bp)
    return app
