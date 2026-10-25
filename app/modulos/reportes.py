"""Módulo de Reportes. RF-016 Generar reportes (PDF o CSV)."""
import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, flash, render_template, request

from ..bd import bd
from ..seguridad import es_admin, requiere_rol, usuario

bp = Blueprint("reportes", __name__)

TIPOS = {
    "mermas": "Reporte de mermas",
    "alertas": "Reporte de alertas",
    "temperaturas": "Reporte de temperaturas",
    "inventario": "Reporte de inventario",
}


def respuesta_csv(nombre, encabezados, filas):
    salida = io.StringIO()
    salida.write("﻿")  # para que Excel abra bien los acentos
    escritor = csv.writer(salida)
    escritor.writerow(encabezados)
    escritor.writerows(filas)
    return Response(salida.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={nombre}"})


def f_(v):
    return v.strftime("%d/%m/%Y %H:%M") if v else ""


def generar(tipo, id_sucursal, desde, hasta):
    """Devuelve (encabezados, filas, totales) del reporte pedido."""
    base = bd()
    cond, args = "", [desde, hasta]
    if id_sucursal:
        cond = " AND s.id_sucursal = %s"
        args.append(id_sucursal)
    if tipo == "mermas":
        filas = base.q(
            "SELECT s.nombre AS sucursal, l.codigo_lote, i.nombre AS insumo, m.cantidad, i.unidad_medida, m.motivo_merma, "
            "m.fecha_movimiento, u.nombre_completo FROM movimientos_inventario m JOIN lotes l ON l.id_lote = m.id_lote "
            "JOIN insumos i ON i.id_insumo = l.id_insumo JOIN sucursales s ON s.id_sucursal = l.id_sucursal "
            "JOIN usuarios u ON u.id_usuario = m.id_usuario WHERE m.tipo_movimiento = 'Merma' "
            "AND DATE(m.fecha_movimiento) BETWEEN %s AND %s" + cond + " ORDER BY m.fecha_movimiento", args)
        totales = {}
        for r in filas:
            clave = f"{r['insumo']} ({r['unidad_medida']})"
            totales[clave] = totales.get(clave, 0) + r["cantidad"]
        return (["Sucursal", "Lote", "Insumo", "Cantidad", "Unidad", "Motivo", "Fecha", "Usuario"],
                [[r["sucursal"], r["codigo_lote"], r["insumo"], r["cantidad"], r["unidad_medida"], r["motivo_merma"] or "",
                  f_(r["fecha_movimiento"]), r["nombre_completo"]] for r in filas],
                [f"Total {k}: {v}" for k, v in totales.items()] + [f"Incidencias: {len(filas)}"])
    if tipo == "alertas":
        filas = base.q(
            "SELECT s.nombre AS sucursal, a.id_alerta, a.tipo_alerta, a.severidad, a.estado_alerta, a.descripcion, "
            "a.fecha_creacion FROM alertas a JOIN sucursales s ON s.id_sucursal = a.id_sucursal "
            "WHERE DATE(a.fecha_creacion) BETWEEN %s AND %s" + cond + " ORDER BY a.fecha_creacion", args)
        conteo = {}
        for r in filas:
            conteo[r["tipo_alerta"]] = conteo.get(r["tipo_alerta"], 0) + 1
        nombres = {"Cadena_de_frio": "Cadena de frío", "Sin_senal": "Sin señal", "Caducidad": "Caducidad"}
        return (["Sucursal", "Id", "Tipo", "Severidad", "Estado", "Descripción", "Fecha"],
                [[r["sucursal"], r["id_alerta"], nombres.get(r["tipo_alerta"], r["tipo_alerta"]), r["severidad"],
                  r["estado_alerta"].replace("_", " "), r["descripcion"], f_(r["fecha_creacion"])] for r in filas],
                [f"{nombres.get(k, k)}: {v}" for k, v in conteo.items()] + [f"Total de alertas: {len(filas)}"])
    if tipo == "temperaturas":
        filas = base.q(
            "SELECT s.nombre AS sucursal, e.nombre_equipo, e.temp_min_permitida, e.temp_max_permitida, COUNT(*) AS lecturas, "
            "MIN(t.temperatura_registrada) AS minima, MAX(t.temperatura_registrada) AS maxima, "
            "ROUND(AVG(t.temperatura_registrada), 1) AS promedio, SUM(t.fuera_de_rango) AS fuera "
            "FROM lecturas_temperatura t JOIN equipos_almacenamiento e ON e.id_equipo = t.id_equipo "
            "JOIN sucursales s ON s.id_sucursal = e.id_sucursal WHERE DATE(t.fecha_hora_lectura) BETWEEN %s AND %s" + cond +
            " GROUP BY e.id_equipo ORDER BY s.nombre, e.nombre_equipo", args)
        return (["Sucursal", "Equipo", "Rango (°C)", "Lecturas", "Mínima", "Máxima", "Promedio", "Fuera de rango"],
                [[r["sucursal"], r["nombre_equipo"], f"{r['temp_min_permitida']} a {r['temp_max_permitida']}", r["lecturas"],
                  r["minima"], r["maxima"], r["promedio"], int(r["fuera"] or 0)] for r in filas],
                [f"Lecturas totales: {sum(r['lecturas'] for r in filas)}",
                 f"Lecturas fuera de rango: {sum(int(r['fuera'] or 0) for r in filas)}"])
    # inventario: lotes con existencia recibidos hasta la fecha final
    args = [hasta] + ([id_sucursal] if id_sucursal else [])
    filas = base.q(
        "SELECT s.nombre AS sucursal, l.codigo_lote, i.nombre AS insumo, l.cantidad_actual, i.unidad_medida, "
        "l.fecha_recepcion, l.fecha_caducidad, l.estado_lote, l.riesgo_merma FROM lotes l "
        "JOIN insumos i ON i.id_insumo = l.id_insumo JOIN sucursales s ON s.id_sucursal = l.id_sucursal "
        "WHERE l.cantidad_actual > 0 AND DATE(l.fecha_recepcion) <= %s" + cond + " ORDER BY s.nombre, l.fecha_caducidad", args)
    estados = {}
    for r in filas:
        estados[r["estado_lote"]] = estados.get(r["estado_lote"], 0) + 1
    return (["Sucursal", "Lote", "Insumo", "Existencia", "Unidad", "Recepción", "Caducidad", "Estado", "Riesgo de merma"],
            [[r["sucursal"], r["codigo_lote"], r["insumo"], r["cantidad_actual"], r["unidad_medida"], f_(r["fecha_recepcion"]),
              f_(r["fecha_caducidad"]), r["estado_lote"], r["riesgo_merma"]] for r in filas],
            [f"{k}: {v} lotes" for k, v in estados.items()] + [f"Total de lotes con existencia: {len(filas)}"])


def respuesta_pdf(titulo, subtitulo, encabezados, filas, totales):
    from fpdf import FPDF

    def t(v):  # las fuentes básicas de PDF usan Latin-1
        return str(v if v is not None else "").replace("≤", "<=").replace("—", "-").encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF(orientation="L", format="Letter")
    pdf.set_auto_page_break(True, 12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, t(titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, t(subtitulo), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    ancho = pdf.epw
    with pdf.table(width=ancho, line_height=5, text_align="LEFT", first_row_as_headings=True) as tabla:
        pdf.set_font("Helvetica", "", 7)
        fila = tabla.row()
        for e in encabezados:
            fila.cell(t(e))
        for r in filas:
            fila = tabla.row()
            for v in r:
                fila.cell(t(v))
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 9)
    for linea in totales:
        pdf.cell(0, 5, t(linea), new_x="LMARGIN", new_y="NEXT")
    if not filas:
        pdf.cell(0, 6, t("No hay datos en el periodo seleccionado."), new_x="LMARGIN", new_y="NEXT")
    return Response(bytes(pdf.output()), mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=reporte.pdf"})


@bp.route("/reportes")
@requiere_rol("Supervisor", "Administrador")
def generar_reporte():
    base = bd()
    hoy = date.today()
    p = {
        "tipo": request.args.get("tipo", "mermas"),
        "desde": request.args.get("desde", (hoy - timedelta(days=30)).isoformat()),
        "hasta": request.args.get("hasta", hoy.isoformat()),
        "sucursal": request.args.get("sucursal", ""),
    }
    sucursales = base.q("SELECT id_sucursal, nombre FROM sucursales ORDER BY id_sucursal")
    if not es_admin():  # el supervisor solo puede elegir su sucursal
        p["sucursal"] = str(usuario()["id_sucursal"])
        sucursales = [s for s in sucursales if s["id_sucursal"] == usuario()["id_sucursal"]]
    resultado = None
    if request.args.get("generar"):
        if p["tipo"] not in TIPOS:
            flash("Tipo de reporte inválido.", "error")
        elif p["desde"] > p["hasta"]:
            flash("La fecha inicial no puede ser posterior a la final.", "error")
        else:
            encabezados, filas, totales = generar(p["tipo"], int(p["sucursal"]) if p["sucursal"] else None, p["desde"], p["hasta"])
            nombre_suc = next((s["nombre"] for s in sucursales if str(s["id_sucursal"]) == p["sucursal"]), "Todas las sucursales")
            subtitulo = (f"{nombre_suc} · Periodo {date.fromisoformat(p['desde']):%d/%m/%Y} a "
                         f"{date.fromisoformat(p['hasta']):%d/%m/%Y} · Generado por {usuario()['nombre_completo']}")
            formato = request.args.get("formato", "pantalla")
            if formato == "csv":
                return respuesta_csv(f"reporte_{p['tipo']}.csv", encabezados, filas)
            if formato == "pdf":
                return respuesta_pdf(TIPOS[p["tipo"]], subtitulo, encabezados, filas, totales)
            resultado = {"titulo": TIPOS[p["tipo"]], "subtitulo": subtitulo, "encabezados": encabezados,
                         "filas": filas, "totales": totales}
    return render_template("reportes.html", p=p, tipos=TIPOS, sucursales=sucursales, r=resultado)
