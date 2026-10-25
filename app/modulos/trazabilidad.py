"""Módulo de Trazabilidad. RF-013 Consultar trazabilidad (RD-003)."""
from flask import Blueprint, abort, render_template, request

from ..bd import bd
from ..seguridad import es_admin, requiere_rol, requiere_sesion, usuario, verificar_sucursal
from .reportes import respuesta_csv

bp = Blueprint("trazabilidad", __name__)

BASE_LOTES = (
    "SELECT l.*, i.nombre AS insumo, i.unidad_medida, p.nombre_empresa AS proveedor, s.nombre AS sucursal, "
    "e.nombre_equipo FROM lotes l JOIN insumos i ON i.id_insumo = l.id_insumo "
    "JOIN proveedores p ON p.id_proveedor = l.id_proveedor JOIN sucursales s ON s.id_sucursal = l.id_sucursal "
    "JOIN equipos_almacenamiento e ON e.id_equipo = l.id_equipo WHERE 1 = 1"
)


def filtro_sucursal(sql, args):
    """El supervisor solo ve su sucursal; el administrador ve todas (RNF-004)."""
    if not es_admin():
        sql += " AND l.id_sucursal = %s"
        args.append(usuario()["id_sucursal"])
    return sql, args


@bp.route("/trazabilidad")
@requiere_rol("Supervisor", "Administrador")
def buscar():
    base = bd()
    texto = request.args.get("q", "").strip()
    resultados = None
    if texto:
        sql, args = filtro_sucursal(
            BASE_LOTES + " AND (l.codigo_lote LIKE %s OR i.nombre LIKE %s OR p.nombre_empresa LIKE %s)",
            [f"%{texto}%"] * 3)
        resultados = base.q(sql + " ORDER BY l.fecha_recepcion DESC LIMIT 200", args)
    return render_template("trazabilidad.html", q=texto, resultados=resultados,
                           proveedores=base.q("SELECT * FROM proveedores ORDER BY nombre_empresa"),
                           insumos=base.q("SELECT * FROM insumos ORDER BY nombre"))


@bp.route("/trazabilidad/afectados")
@requiere_rol("Supervisor", "Administrador")
def afectados():
    """Ante una alerta sanitaria: todos los lotes de un proveedor/insumo en un periodo, y sus sucursales."""
    base = bd()
    f = {k: request.args.get(k, "") for k in ("proveedor", "insumo", "desde", "hasta")}
    sql, args = BASE_LOTES, []
    for campo, columna in (("proveedor", "l.id_proveedor"), ("insumo", "l.id_insumo")):
        if f[campo]:
            sql += f" AND {columna} = %s"
            args.append(f[campo])
    if f["desde"]:
        sql += " AND DATE(l.fecha_recepcion) >= %s"
        args.append(f["desde"])
    if f["hasta"]:
        sql += " AND DATE(l.fecha_recepcion) <= %s"
        args.append(f["hasta"])
    sql, args = filtro_sucursal(sql, args)
    lotes = base.q(sql + " ORDER BY s.nombre, l.fecha_recepcion", args)
    if request.args.get("exportar") == "csv":
        return respuesta_csv(
            "lotes_afectados.csv",
            ["Lote", "Insumo", "Proveedor", "Sucursal", "Equipo", "Recepción", "Caducidad", "Cantidad actual", "Estado"],
            [[l["codigo_lote"], l["insumo"], l["proveedor"], l["sucursal"], l["nombre_equipo"],
              l["fecha_recepcion"].strftime("%d/%m/%Y %H:%M"), l["fecha_caducidad"].strftime("%d/%m/%Y %H:%M"),
              l["cantidad_actual"], l["estado_lote"]] for l in lotes])
    sucursales = sorted({l["sucursal"] for l in lotes})
    return render_template("afectados.html", lotes=lotes, sucursales=sucursales, f=f,
                           proveedores=base.q("SELECT * FROM proveedores ORDER BY nombre_empresa"),
                           insumos=base.q("SELECT * FROM insumos ORDER BY nombre"))


@bp.route("/lote/<int:id_lote>")
@requiere_sesion
def lote(id_lote):
    """Ficha completa del lote: origen, ubicación, movimientos, estados, alertas, descuentos y donaciones."""
    base = bd()
    l = base.q1(BASE_LOTES + " AND l.id_lote = %s", (id_lote,))
    if not l:
        abort(404)
    verificar_sucursal(l["id_sucursal"])
    movimientos = base.q(
        "SELECT m.*, u.nombre_completo FROM movimientos_inventario m JOIN usuarios u ON u.id_usuario = m.id_usuario "
        "WHERE m.id_lote = %s ORDER BY m.fecha_movimiento", (id_lote,))
    estados = base.q(
        "SELECT h.*, u.nombre_completo FROM historial_estados_lote h LEFT JOIN usuarios u ON u.id_usuario = h.id_usuario "
        "WHERE h.id_lote = %s ORDER BY h.fecha_cambio, h.id_historial_estado", (id_lote,))
    alertas = base.q(
        "SELECT * FROM alertas WHERE id_lote = %s OR (id_equipo = %s AND tipo_alerta = 'Cadena_de_frio' "
        "AND fecha_creacion >= %s) ORDER BY fecha_creacion", (id_lote, l["id_equipo"], l["fecha_recepcion"]))
    descuentos = base.q(
        "SELECT d.*, u.nombre_completo FROM sugerencias_descuento d LEFT JOIN usuarios u ON u.id_usuario = d.id_supervisor_autoriza "
        "WHERE d.id_lote = %s ORDER BY d.fecha_sugerencia", (id_lote,))
    donaciones = base.q(
        "SELECT p.folio_donacion, p.estado_propuesta, p.fecha_propuesta, d.cantidad_donada, b.nombre_institucion "
        "FROM detalle_donacion_lotes d JOIN propuestas_donacion p ON p.id_donacion = d.id_donacion "
        "JOIN bancos_alimentos b ON b.id_banco = p.id_banco WHERE d.id_lote = %s", (id_lote,))
    return render_template("lote.html", l=l, movimientos=movimientos, estados=estados, alertas=alertas,
                           descuentos=descuentos, donaciones=donaciones)
