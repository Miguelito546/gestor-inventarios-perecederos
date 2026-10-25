-- ============================================================================
-- SCRIPT 3: CONSULTAS DE OPERACIÓN Y REPORTES GERENCIALES
-- PROYECTO: Gestor Inteligente de Inventarios (KFC Villahermosa)
-- DOCUMENTO REF: SRS-001-Versión 0.2
-- VERSIÓN DEL SCRIPT: 2 (ver sql/CAMBIOS.md). La aplicación usa estas mismas consultas con
-- la sucursal del usuario y las fechas que elige en pantalla en lugar de valores fijos.
-- ============================================================================

USE `kfc_inventory_db`;
SET time_zone = '-06:00';

-- ----------------------------------------------------------------------------
-- CONSULTA 1: CONSULTAR INVENTARIO POR SUCURSAL CON FILTROS Y ESTADO (RF-002)
-- ----------------------------------------------------------------------------
SELECT 
    l.codigo_lote,
    i.nombre AS insumo,
    i.categoria,
    l.cantidad_actual,
    i.unidad_medida,
    l.fecha_caducidad,
    l.estado_lote,
    l.riesgo_merma,
    e.nombre_equipo AS ubicacion
FROM lotes l
JOIN insumos i ON l.id_insumo = i.id_insumo
JOIN equipos_almacenamiento e ON l.id_equipo = e.id_equipo
WHERE l.id_sucursal = 1 -- Filtro por sucursal del usuario en sesión
  AND l.cantidad_actual > 0
ORDER BY l.fecha_caducidad ASC;

-- ----------------------------------------------------------------------------
-- CONSULTA 2: SUGERENCIA DE ROTACIÓN DE INVENTARIO FEFO (RF-007, RN-001)
-- Devuelve el lote con fecha de caducidad más próxima que esté FRESCO o PRÓXIMO A VENCER
-- ----------------------------------------------------------------------------
SELECT 
    l.id_lote,
    l.codigo_lote,
    i.nombre AS insumo,
    l.cantidad_actual,
    l.fecha_caducidad,
    DATEDIFF(l.fecha_caducidad, NOW()) AS dias_para_vencer
FROM lotes l
JOIN insumos i ON l.id_insumo = i.id_insumo
WHERE l.id_sucursal = 1
  AND l.id_insumo = 1 -- ID del insumo que se va a consumir (ej. Pollo crudo marinado)
  AND l.estado_lote IN ('Fresco', 'Próximo a vencer')
  AND l.fecha_caducidad > NOW() -- [v2] nunca sugerir un lote ya caducado (RD-004)
  AND l.cantidad_actual > 0
ORDER BY l.fecha_caducidad ASC
LIMIT 1;

-- ----------------------------------------------------------------------------
-- CONSULTA 3: MONITOREO Y HISTORIAL DE TEMPERATURA ÚLTIMAS 24 HRS (RF-009)
-- ----------------------------------------------------------------------------
SELECT 
    e.nombre_equipo,
    lt.temperatura_registrada,
    e.temp_min_permitida,
    e.temp_max_permitida,
    lt.fuera_de_rango,
    lt.fecha_hora_lectura
FROM lecturas_temperatura lt
JOIN equipos_almacenamiento e ON lt.id_equipo = e.id_equipo
WHERE e.id_sucursal = 1
  AND lt.fecha_hora_lectura >= NOW() - INTERVAL 24 HOUR
ORDER BY lt.fecha_hora_lectura DESC;

-- ----------------------------------------------------------------------------
-- CONSULTA 4: PANEL DE ALERTAS ACTIVAS PARA EL SUPERVISOR (RF-010, RF-011, RF-012)
-- ----------------------------------------------------------------------------
SELECT 
    a.id_alerta,
    a.tipo_alerta,
    a.severidad,
    a.descripcion,
    a.estado_alerta,
    a.fecha_creacion,
    COALESCE(l.codigo_lote, 'N/A') AS lote_afectado,
    COALESCE(e.nombre_equipo, 'N/A') AS equipo_afectado
FROM alertas a
LEFT JOIN lotes l ON a.id_lote = l.id_lote
LEFT JOIN equipos_almacenamiento e ON a.id_equipo = e.id_equipo
WHERE a.id_sucursal = 1
  AND a.estado_alerta IN ('Abierta', 'Reconocida', 'En_atencion')
ORDER BY 
    CASE a.severidad
        WHEN 'Critica' THEN 1
        WHEN 'Alta' THEN 2
        WHEN 'Media' THEN 3
    END ASC,
    a.fecha_creacion DESC;

-- ----------------------------------------------------------------------------
-- CONSULTA 5: REPORTE GERENCIAL DE MERMAS POR SUCURSAL Y PERIODO (RF-016)
-- ----------------------------------------------------------------------------
SELECT 
    s.nombre AS sucursal,
    i.nombre AS insumo,
    m.motivo_merma,
    SUM(m.cantidad) AS total_cantidad_mermada,
    i.unidad_medida,
    COUNT(m.id_movimiento) AS total_incidencias
FROM movimientos_inventario m
JOIN lotes l ON m.id_lote = l.id_lote
JOIN insumos i ON l.id_insumo = i.id_insumo
JOIN sucursales s ON l.id_sucursal = s.id_sucursal
WHERE m.tipo_movimiento = 'Merma'
  AND m.fecha_movimiento >= NOW() - INTERVAL 30 DAY -- [v2] periodo relativo (últimos 30 días)
GROUP BY s.nombre, i.nombre, m.motivo_merma, i.unidad_medida;

-- ----------------------------------------------------------------------------
-- CONSULTA 6: TRAZABILIDAD COMPLETA DE UN LOTE ANTE ALERTA SANITARIA (RF-013)
-- ----------------------------------------------------------------------------
SELECT 
    l.codigo_lote,
    i.nombre AS insumo,
    p.nombre_empresa AS proveedor,
    s.nombre AS sucursal,
    e.nombre_equipo AS ubicacion_actual,
    l.cantidad_inicial,
    l.cantidad_actual,
    l.fecha_recepcion,
    l.fecha_caducidad,
    l.estado_lote
FROM lotes l
JOIN insumos i ON l.id_insumo = i.id_insumo
JOIN proveedores p ON l.id_proveedor = p.id_proveedor
JOIN sucursales s ON l.id_sucursal = s.id_sucursal
JOIN equipos_almacenamiento e ON l.id_equipo = e.id_equipo
WHERE l.id_proveedor = 1; -- Filtra todos los lotes de un proveedor bajo alerta sanitaria

-- [v2] CONSULTA 6b: MOVIMIENTOS DEL LOTE (RF-013 pide movimientos con fecha y usuario)
SELECT
    m.fecha_movimiento,
    m.tipo_movimiento,
    m.cantidad,
    m.motivo_merma AS detalle,
    u.nombre_completo AS usuario
FROM movimientos_inventario m
JOIN usuarios u ON m.id_usuario = u.id_usuario
WHERE m.id_lote = 2
ORDER BY m.fecha_movimiento;

-- [v2] CONSULTA 6c: ALERTAS ASOCIADAS AL LOTE O AL EQUIPO DONDE SE GUARDA (RF-013)
SELECT
    a.id_alerta,
    a.tipo_alerta,
    a.severidad,
    a.estado_alerta,
    a.fecha_creacion
FROM alertas a
JOIN lotes l ON l.id_lote = 2
WHERE a.id_lote = l.id_lote
   OR (a.id_equipo = l.id_equipo AND a.tipo_alerta = 'Cadena_de_frio' AND a.fecha_creacion >= l.fecha_recepcion)
ORDER BY a.fecha_creacion;
