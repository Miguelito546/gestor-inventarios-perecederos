"""Módulo de Monitoreo.

RF-008 Recibir lecturas de temperatura (API para el simulador IoT, RI-004)
RF-009 Visualizar temperatura
"""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

import configuracion as cfg
from .. import simulador
from ..bd import bd
from ..motor import LecturaInvalida, recibir_lectura
from ..seguridad import es_admin, requiere_rol, requiere_sesion, sucursal_actual, verificar_sucursal

bp = Blueprint("monitoreo", __name__)


def equipos_con_actual(base, id_sucursal):
    # Última lectura de cada equipo con ROW_NUMBER() (funciona en MariaDB, MySQL 8 y TiDB)
    return base.q(
        "SELECT e.*, t.temperatura_registrada AS actual, t.fecha_hora_lectura AS hora, t.fuera_de_rango, "
        "(SELECT COUNT(*) FROM alertas a WHERE a.id_equipo = e.id_equipo AND a.estado_alerta <> 'Cerrada') AS alertas "
        "FROM equipos_almacenamiento e LEFT JOIN ("
        "  SELECT l.id_equipo, l.temperatura_registrada, l.fecha_hora_lectura, l.fuera_de_rango, "
        "         ROW_NUMBER() OVER (PARTITION BY l.id_equipo ORDER BY l.fecha_hora_lectura DESC, l.id_lectura DESC) AS n "
        "  FROM lecturas_temperatura l JOIN equipos_almacenamiento q ON q.id_equipo = l.id_equipo "
        "  WHERE q.id_sucursal = %s"
        ") t ON t.id_equipo = e.id_equipo AND t.n = 1 "
        "WHERE e.id_sucursal = %s ORDER BY e.id_equipo", (id_sucursal, id_sucursal))


@bp.route("/monitoreo")
@requiere_sesion
def ver():
    base = bd()
    equipos = equipos_con_actual(base, sucursal_actual())
    elegido = request.args.get("equipo", type=int) or (equipos[0]["id_equipo"] if equipos else None)
    equipo = next((e for e in equipos if e["id_equipo"] == elegido), None)
    return render_template("monitoreo.html", equipos=equipos, equipo=equipo)


@bp.route("/api/monitoreo/<int:id_equipo>")
@requiere_sesion
def datos_equipo(id_equipo):
    """Datos para la gráfica de las últimas 24 h (se consulta cada 30 s, RI-003)."""
    base = bd()
    equipo = base.q1("SELECT * FROM equipos_almacenamiento WHERE id_equipo = %s", (id_equipo,))
    if not equipo:
        abort(404)
    verificar_sucursal(equipo["id_sucursal"])
    lecturas = base.q(
        "SELECT temperatura_registrada AS t, fecha_hora_lectura AS f, fuera_de_rango AS fr FROM lecturas_temperatura "
        "WHERE id_equipo = %s AND fecha_hora_lectura >= NOW() - INTERVAL 24 HOUR ORDER BY fecha_hora_lectura", (id_equipo,))
    # Reduce puntos para que la gráfica sea ligera, sin perder las lecturas fuera de rango.
    paso = max(1, len(lecturas) // 400)
    lecturas = [l for i, l in enumerate(lecturas) if i % paso == 0 or l["fr"] or i == len(lecturas) - 1]
    return jsonify(
        equipo=equipo["nombre_equipo"],
        minimo=float(equipo["temp_min_permitida"]),
        maximo=float(equipo["temp_max_permitida"]),
        lecturas=[{"t": float(l["t"]), "f": l["f"].strftime("%d/%m %H:%M"), "fr": bool(l["fr"])} for l in lecturas],
        equipos=[{"id": e["id_equipo"], "actual": float(e["actual"]) if e["actual"] is not None else None,
                  "fr": bool(e["fuera_de_rango"]), "hora": e["hora"].strftime("%d/%m/%Y %H:%M:%S") if e["hora"] else None,
                  "alertas": e["alertas"], "estado": e["estado_operativo"]}
                 for e in equipos_con_actual(base, equipo["id_sucursal"])],
    )


@bp.route("/api/lecturas", methods=["POST"])
def api_lecturas():
    """RF-008: recibe lecturas del simulador IoT externo. Requiere el encabezado X-Token."""
    if request.headers.get("X-Token") != cfg.TOKEN_SIMULADOR:
        return jsonify(estado="rechazada", detalle="Token inválido."), 401
    datos = request.get_json(silent=True)
    if datos is None:
        return jsonify(estado="rechazada", detalle="El cuerpo debe ser JSON."), 400
    lote = datos if isinstance(datos, list) else [datos]
    respuestas = []
    for lectura in lote:
        try:
            respuestas.append(recibir_lectura(bd(), lectura if isinstance(lectura, dict) else {}))
        except LecturaInvalida as e:
            respuestas.append({"estado": "rechazada", "detalle": str(e)})
    codigo = 200 if any(r["estado"] != "rechazada" for r in respuestas) else 400
    return jsonify(respuestas if isinstance(datos, list) else respuestas[0]), codigo


# ---------------------------------------------------------------- Control del simulador (demostración)
@bp.route("/simulador", methods=["GET", "POST"])
@requiere_rol("Supervisor", "Administrador")
def control_simulador():
    base = bd()
    if request.method == "POST":
        id_equipo = int(request.form["id_equipo"])
        equipo = base.q1("SELECT * FROM equipos_almacenamiento WHERE id_equipo = %s", (id_equipo,))
        if not equipo:
            abort(404)
        verificar_sucursal(equipo["id_sucursal"])
        modo = request.form.get("modo", "normal")
        if modo not in simulador.MODOS:
            abort(400)
        simulador.cambiar_modo(base, id_equipo, modo)
        textos = {"normal": "envía temperaturas normales", "falla": "simula una falla de frío",
                  "sin_senal": "dejó de enviar lecturas"}
        flash(f"{equipo['nombre_equipo']} ahora {textos[modo]}.", "ok")
        return redirect(url_for("monitoreo.control_simulador"))
    equipos = equipos_con_actual(base, sucursal_actual())
    modos = simulador.leer_modos(base)
    for e in equipos:
        e["modo"] = modos.get(e["id_equipo"], "normal")
    return render_template("simulador.html", equipos=equipos, activo=simulador.esta_activo(base),
                           intervalo=cfg.SIMULADOR_INTERVALO_SEG)
