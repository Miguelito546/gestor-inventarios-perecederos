-- ============================================================================
-- SCRIPT 2: DATOS FICTICIOS DE PRUEBA (VERSIÓN 2)
-- PROYECTO: Gestor Inteligente de Inventarios (KFC Villahermosa)
-- DOCUMENTO REF: SRS-001-Versión 0.2
-- BASE: GestionAlimentosKFC 1.sql y RegistrosKFC.sql (Alfredo Peralta & Equipo 1)
--
-- Cambios de la versión 2 (detalle en sql/CAMBIOS.md):
--   * Todas las fechas son RELATIVAS al momento de ejecutar el script (NOW()),
--     para que la demostración siempre tenga lotes frescos, próximos a vencer y vencidos.
--   * Contraseñas con hash real. Contraseña de todos los usuarios de prueba: Demo2026
--   * Cada lote está en un equipo de SU sucursal; existencias y estados cuadran.
--   * Usuarios con nombres ficticios (RNF-013) y 8 sucursales (RNF-010).
-- ============================================================================

USE `kfc_inventory_db`;
SET NAMES utf8mb4;
SET time_zone = '-06:00';          -- Hora de Villahermosa (RNF-012)
SET @ahora = NOW();
SET @hoy = CURDATE();

-- ----------------------------------------------------------------------------
-- 1. Sucursales (8, RNF-010). Las 3 primeras son las del script original.
-- ----------------------------------------------------------------------------
INSERT INTO `sucursales` (`id_sucursal`, `nombre`, `direccion`, `telefono`, `activa`) VALUES
(1, 'KFC Sucursal Centro Villahermosa', 'Av. 27 de Febrero #102, Centro, Villahermosa, Tabasco', '9933123456', 1),
(2, 'KFC Sucursal Plaza Galerías', 'Prolongación 27 de Febrero, Carrizal, Villahermosa, Tabasco', '9933654321', 1),
(3, 'KFC Sucursal Guayabal', 'Av. Adolfo Ruiz Cortines, Guayabal, Villahermosa, Tabasco', '9933987654', 1),
(4, 'KFC Sucursal Ciudad Industrial', 'Av. Industrial s/n, Ciudad Industrial, Villahermosa, Tabasco', '9933001122', 1),
(5, 'KFC Sucursal Tabasco 2000', 'Paseo Tabasco, Tabasco 2000, Villahermosa, Tabasco', '9933002233', 1),
(6, 'KFC Sucursal Deportiva', 'Av. Méndez, Col. Atasta, Villahermosa, Tabasco', '9933003344', 1),
(7, 'KFC Sucursal Altabrisa', 'Periférico Carlos Pellicer Cámara, Villahermosa, Tabasco', '9933004455', 1),
(8, 'KFC Sucursal Universidad', 'Av. Universidad, Col. Magisterial, Villahermosa, Tabasco', '9933005566', 1);

-- Configuración de umbrales (valores confirmados por el equipo)
INSERT INTO `configuracion_umbrales` (`id_sucursal`, `dias_anticipacion_caducidad`, `tiempo_tolerado_temp_min`, `pct_descuento_nivel_1`, `pct_descuento_nivel_2`, `horas_min_donacion`, `minutos_sin_senal`)
SELECT `id_sucursal`, 2, 15, 10.00, 25.00, 24, 10 FROM `sucursales`;

-- ----------------------------------------------------------------------------
-- 2. Equipos de almacenamiento: cada sucursal tiene los suyos.
-- ----------------------------------------------------------------------------
INSERT INTO `equipos_almacenamiento` (`id_equipo`, `id_sucursal`, `nombre_equipo`, `tipo_equipo`, `temp_min_permitida`, `temp_max_permitida`, `estado_operativo`) VALUES
(1, 1, 'Refrigerador de Pollo Crudo 1', 'refrigeracion', 0.0, 4.0, 'normal'),
(2, 1, 'Congelador Principal', 'congelacion', -25.0, -18.0, 'normal'),
(3, 1, 'Refrigerador de Ensaladas y Lácteos', 'refrigeracion', 0.0, 4.0, 'normal'),
(4, 2, 'Refrigerador General', 'refrigeracion', 0.0, 4.0, 'alerta_temperatura'),
(5, 2, 'Congelador Principal', 'congelacion', -25.0, -18.0, 'normal'),
(6, 3, 'Refrigerador General', 'refrigeracion', 0.0, 4.0, 'normal'),
(7, 3, 'Congelador Principal', 'congelacion', -25.0, -18.0, 'normal'),
(8, 4, 'Refrigerador General', 'refrigeracion', 0.0, 4.0, 'normal'),
(9, 4, 'Congelador Principal', 'congelacion', -25.0, -18.0, 'normal'),
(10, 5, 'Refrigerador General', 'refrigeracion', 0.0, 4.0, 'normal'),
(11, 5, 'Congelador Principal', 'congelacion', -25.0, -18.0, 'normal'),
(12, 6, 'Refrigerador General', 'refrigeracion', 0.0, 4.0, 'normal'),
(13, 6, 'Congelador Principal', 'congelacion', -25.0, -18.0, 'normal'),
(14, 7, 'Refrigerador General', 'refrigeracion', 0.0, 4.0, 'normal'),
(15, 7, 'Congelador Principal', 'congelacion', -25.0, -18.0, 'normal'),
(16, 8, 'Refrigerador General', 'refrigeracion', 0.0, 4.0, 'normal'),
(17, 8, 'Congelador Principal', 'congelacion', -25.0, -18.0, 'normal');

-- ----------------------------------------------------------------------------
-- 3. Usuarios (nombres ficticios, RNF-013). Contraseña de todos: Demo2026
-- ----------------------------------------------------------------------------
SET @hash_demo = 'pbkdf2:sha256:600000$o8ZZtpVzNwDuoSek$145f19936c98328cc1189b08fe7dc8b6fc012c655124a5b7b488fdf0dcbf10ae';
INSERT INTO `usuarios` (`id_usuario`, `id_sucursal`, `nombre_completo`, `username`, `password_hash`, `rol`, `activo`) VALUES
(1, NULL, 'Laura Méndez Ruiz', 'admin', @hash_demo, 'Administrador', 1),
(2, 1, 'Jorge Hernández Cruz', 'supervisor', @hash_demo, 'Supervisor', 1),
(3, 1, 'Ana Torres Díaz', 'empleado', @hash_demo, 'Empleado', 1),
(4, 2, 'Carlos Ramírez León', 'supervisor2', @hash_demo, 'Supervisor', 1),
(5, 2, 'Sofía Pérez Gómez', 'empleado2', @hash_demo, 'Empleado', 1),
(6, 1, 'Pedro Sánchez Ortiz', 'empleado_baja', @hash_demo, 'Empleado', 0);

-- ----------------------------------------------------------------------------
-- 4. Proveedores, insumos y bancos de alimentos
-- ----------------------------------------------------------------------------
INSERT INTO `proveedores` (`id_proveedor`, `nombre_empresa`, `contacto_nombre`, `telefono`) VALUES
(1, 'Avícola Tabasqueña S.A. de C.V.', 'Carlos Pérez', '9931112233'),
(2, 'Lácteos y Derivados del Sureste', 'Ana Gómez', '9932223344'),
(3, 'Hortalizas Frescas del Golfo', 'Luis Martínez', '9933334455'),
(4, 'Congelados del Sureste S.A.', 'Rosa Jiménez', '9934445566');

INSERT INTO `insumos` (`id_insumo`, `nombre`, `categoria`, `unidad_medida`, `temp_min_conservacion`, `temp_max_conservacion`) VALUES
(1, 'Pollo crudo marinado', 'Carnes y Aves', 'kg', 0.0, 4.0),
(2, 'Leche entera', 'Lácteos', 'litros', 0.0, 4.0),
(3, 'Ensalada de col', 'Complementos', 'piezas', 0.0, 4.0),
(4, 'Papas a la francesa congeladas', 'Congelados', 'kg', -25.0, -18.0),
(5, 'Puré de papa', 'Complementos', 'kg', 0.0, 4.0);

INSERT INTO `bancos_alimentos` (`id_banco`, `nombre_institucion`, `direccion`, `contacto_telefono`) VALUES
(1, 'Banco de Alimentos de Tabasco I.A.P.', 'Periférico Carlos Pellicer Cámara, Villahermosa, Tabasco', '9933150000'),
(2, 'Comedor Comunitario Gaviotas', 'Col. Gaviotas Norte, Villahermosa, Tabasco', '9933160000');

-- ----------------------------------------------------------------------------
-- 5. Lotes (fechas relativas a hoy; cada lote en un equipo de su sucursal)
-- ----------------------------------------------------------------------------
INSERT INTO `lotes` (`id_lote`, `codigo_lote`, `id_insumo`, `id_proveedor`, `id_sucursal`, `id_equipo`, `cantidad_inicial`, `cantidad_actual`, `fecha_recepcion`, `fecha_caducidad`, `estado_lote`, `riesgo_merma`) VALUES
-- Sucursal 1 - Centro
(1, CONCAT('LOT-POLLO-', DATE_FORMAT(@hoy - INTERVAL 3 DAY, '%Y%m%d'), '-01'), 1, 1, 1, 1, 50.00, 40.00, @hoy - INTERVAL 3 DAY + INTERVAL 8 HOUR, @hoy + INTERVAL 4 DAY + INTERVAL 86399 SECOND, 'Fresco', 'Medio'),
(2, CONCAT('LOT-POLLO-', DATE_FORMAT(@hoy - INTERVAL 6 DAY, '%Y%m%d'), '-02'), 1, 1, 1, 1, 40.00, 25.00, @hoy - INTERVAL 6 DAY + INTERVAL 9 HOUR, @ahora + INTERVAL 40 HOUR, 'Próximo a vencer', 'Alto'),
(3, CONCAT('LOT-LACT-', DATE_FORMAT(@hoy - INTERVAL 10 DAY, '%Y%m%d'), '-01'), 2, 2, 1, 3, 20.00, 5.00, @hoy - INTERVAL 10 DAY + INTERVAL 10 HOUR, @hoy - INTERVAL 4 DAY + INTERVAL 86399 SECOND, 'Vencido', 'Alto'),
(6, CONCAT('LOT-PAPA-', DATE_FORMAT(@hoy - INTERVAL 5 DAY, '%Y%m%d'), '-01'), 4, 4, 1, 2, 80.00, 80.00, @hoy - INTERVAL 5 DAY + INTERVAL 7 HOUR, @hoy + INTERVAL 60 DAY, 'Fresco', 'Sin datos'),
(7, CONCAT('LOT-ENS-', DATE_FORMAT(@hoy - INTERVAL 1 DAY, '%Y%m%d'), '-01'), 3, 3, 1, 3, 40.00, 40.00, @hoy - INTERVAL 1 DAY + INTERVAL 7 HOUR, @hoy + INTERVAL 5 DAY + INTERVAL 86399 SECOND, 'Fresco', 'Sin datos'),
(8, CONCAT('LOT-POLLO-', DATE_FORMAT(@hoy, '%Y%m%d'), '-03'), 1, 1, 1, 1, 30.00, 30.00, @hoy + INTERVAL 7 HOUR, @hoy + INTERVAL 6 DAY + INTERVAL 86399 SECOND, 'Fresco', 'Bajo'),
(11, CONCAT('LOT-POLLO-', DATE_FORMAT(@hoy - INTERVAL 8 DAY, '%Y%m%d'), '-01'), 1, 1, 1, 1, 60.00, 0.00, @hoy - INTERVAL 8 DAY + INTERVAL 8 HOUR, @hoy - INTERVAL 1 DAY + INTERVAL 86399 SECOND, 'Fresco', 'Sin datos'),
-- Sucursal 2 - Plaza Galerías (lote retenido por la falla de frío del equipo 4)
(4, CONCAT('LOT-ENS-', DATE_FORMAT(@hoy - INTERVAL 2 DAY, '%Y%m%d'), '-01'), 3, 3, 2, 4, 30.00, 30.00, @hoy - INTERVAL 2 DAY + INTERVAL 7 HOUR + INTERVAL 30 MINUTE, @hoy + INTERVAL 4 DAY + INTERVAL 86399 SECOND, 'Retenido', 'Sin datos'),
(9, CONCAT('LOT-POLLO-', DATE_FORMAT(@hoy - INTERVAL 1 DAY, '%Y%m%d'), '-21'), 1, 1, 2, 4, 45.00, 45.00, @hoy - INTERVAL 1 DAY + INTERVAL 8 HOUR, @hoy + INTERVAL 5 DAY + INTERVAL 86399 SECOND, 'Retenido', 'Sin datos'),
-- Sucursal 3 - Guayabal
(5, CONCAT('LOT-POLLO-', DATE_FORMAT(@hoy - INTERVAL 2 DAY, '%Y%m%d'), '-03'), 1, 1, 3, 6, 60.00, 60.00, @hoy - INTERVAL 2 DAY + INTERVAL 8 HOUR + INTERVAL 15 MINUTE, @hoy + INTERVAL 5 DAY + INTERVAL 86399 SECOND, 'Fresco', 'Sin datos'),
-- Sucursal 4 - Ciudad Industrial
(10, CONCAT('LOT-LACT-', DATE_FORMAT(@hoy - INTERVAL 5 DAY, '%Y%m%d'), '-41'), 2, 2, 4, 8, 25.00, 25.00, @hoy - INTERVAL 5 DAY + INTERVAL 9 HOUR, @ahora + INTERVAL 30 HOUR, 'Próximo a vencer', 'Sin datos'),
(12, CONCAT('LOT-POLLO-', DATE_FORMAT(@hoy - INTERVAL 1 DAY, '%Y%m%d'), '-41'), 1, 1, 4, 8, 50.00, 50.00, @hoy - INTERVAL 1 DAY + INTERVAL 8 HOUR, @hoy + INTERVAL 6 DAY + INTERVAL 86399 SECOND, 'Fresco', 'Sin datos');

-- Historial de estados coherente con los lotes anteriores
INSERT INTO `historial_estados_lote` (`id_lote`, `estado_anterior`, `estado_nuevo`, `motivo_cambio`, `id_usuario`, `fecha_cambio`) VALUES
(2, 'Fresco', 'Próximo a vencer', 'Faltan 2 días o menos para su caducidad (RF-003)', NULL, @ahora - INTERVAL 8 HOUR),
(3, 'Fresco', 'Próximo a vencer', 'Faltan 2 días o menos para su caducidad (RF-003)', NULL, @hoy - INTERVAL 6 DAY),
(3, 'Próximo a vencer', 'Vencido', 'Fecha de caducidad alcanzada (RF-003)', NULL, @hoy - INTERVAL 3 DAY),
(1, 'Fresco', 'Retenido', 'Alerta de cadena de frío en Refrigerador de Pollo Crudo 1 (RN-002)', NULL, @ahora - INTERVAL 1205 MINUTE),
(1, 'Retenido', 'Fresco', 'Liberado por el supervisor: la temperatura volvió al rango en 30 min y el producto se revisó', 2, @ahora - INTERVAL 1110 MINUTE),
(2, 'Fresco', 'Retenido', 'Alerta de cadena de frío en Refrigerador de Pollo Crudo 1 (RN-002)', NULL, @ahora - INTERVAL 1205 MINUTE),
(2, 'Retenido', 'Fresco', 'Liberado por el supervisor: la temperatura volvió al rango en 30 min y el producto se revisó', 2, @ahora - INTERVAL 1110 MINUTE),
(4, 'Fresco', 'Retenido', 'Alerta de cadena de frío en Refrigerador General (RN-002)', NULL, @ahora - INTERVAL 10 MINUTE),
(9, 'Fresco', 'Retenido', 'Alerta de cadena de frío en Refrigerador General (RN-002)', NULL, @ahora - INTERVAL 10 MINUTE),
(10, 'Fresco', 'Próximo a vencer', 'Faltan 2 días o menos para su caducidad (RF-003)', NULL, @ahora - INTERVAL 18 HOUR);

-- ----------------------------------------------------------------------------
-- 6. Movimientos de inventario (cuadran con cantidad_inicial - cantidad_actual)
--    Lote 11: 60 kg consumidos en la última semana (da el consumo promedio para RF-004)
-- ----------------------------------------------------------------------------
INSERT INTO `movimientos_inventario` (`id_lote`, `id_usuario`, `tipo_movimiento`, `cantidad`, `motivo_merma`, `sugerido_por_fefo`, `fecha_movimiento`) VALUES
(11, 3, 'Consumo', 10.00, NULL, 1, @hoy - INTERVAL 7 DAY + INTERVAL 13 HOUR),
(11, 3, 'Consumo', 10.00, NULL, 1, @hoy - INTERVAL 6 DAY + INTERVAL 13 HOUR),
(11, 3, 'Consumo', 10.00, NULL, 1, @hoy - INTERVAL 5 DAY + INTERVAL 13 HOUR),
(11, 3, 'Consumo', 10.00, NULL, 1, @hoy - INTERVAL 4 DAY + INTERVAL 13 HOUR),
(11, 3, 'Consumo', 10.00, NULL, 1, @hoy - INTERVAL 3 DAY + INTERVAL 13 HOUR),
(11, 3, 'Consumo', 10.00, NULL, 1, @hoy - INTERVAL 2 DAY + INTERVAL 13 HOUR),
(2, 3, 'Consumo', 15.00, NULL, 1, @hoy - INTERVAL 1 DAY + INTERVAL 13 HOUR),
(1, 3, 'Consumo', 10.00, NULL, 0, @hoy - INTERVAL 1 DAY + INTERVAL 18 HOUR),
(3, 2, 'Merma', 15.00, 'Empaque dañado en la recepción', 0, @hoy - INTERVAL 8 DAY + INTERVAL 11 HOUR),
(2, 2, 'Ajuste_Descuento', 0.00, 'Descuento autorizado del 10 %', 0, @ahora - INTERVAL 7 HOUR);

-- ----------------------------------------------------------------------------
-- 7. Lecturas de temperatura de las últimas 24 h (cada 10 min) del simulador IoT
--    * Equipo 1: falla hace ~20 h (5.8 - 6.4 °C por 30 min), ya resuelta.
--    * Equipo 4: falla actual (últimos 30 min fuera de rango) -> alerta abierta.
-- ----------------------------------------------------------------------------
INSERT INTO `lecturas_temperatura` (`id_equipo`, `temperatura_registrada`, `fecha_hora_lectura`, `fuera_de_rango`)
WITH RECURSIVE pasos(n) AS (
    SELECT 1 UNION ALL SELECT n + 1 FROM pasos WHERE n < 144
),
valores AS (
    SELECT e.id_equipo, e.temp_min_permitida, e.temp_max_permitida, p.n,
           @ahora - INTERVAL (p.n * 10) MINUTE AS momento,
           CASE
               WHEN e.id_equipo = 1 AND p.n BETWEEN 118 AND 121 THEN 5.8 + (121 - p.n) * 0.2
               WHEN e.id_equipo = 4 AND p.n <= 4 THEN 6.6 - p.n * 0.3
               WHEN e.tipo_equipo = 'refrigeracion' THEN ROUND(2.4 + 0.9 * SIN(p.n / 7 + e.id_equipo), 1)
               ELSE ROUND(-20.5 + 1.2 * SIN(p.n / 5 + e.id_equipo), 1)
           END AS valor
    FROM equipos_almacenamiento e CROSS JOIN pasos p
)
SELECT id_equipo, valor, momento,
       CASE WHEN valor < temp_min_permitida OR valor > temp_max_permitida THEN 1 ELSE 0 END
FROM valores;

-- ----------------------------------------------------------------------------
-- 8. Alertas (RF-010, RF-011) e historial de atención (RF-012)
-- ----------------------------------------------------------------------------
INSERT INTO `alertas` (`id_alerta`, `id_sucursal`, `tipo_alerta`, `severidad`, `id_lote`, `id_equipo`, `descripcion`, `estado_alerta`, `fecha_creacion`) VALUES
(1, 1, 'Caducidad', 'Media', 2, NULL, 'El lote está a 2 días o menos de vencer.', 'Abierta', @ahora - INTERVAL 8 HOUR),
(2, 1, 'Cadena_de_frio', 'Critica', NULL, 1, 'Refrigerador de Pollo Crudo 1 superó los 4.0 °C durante más de 15 min.', 'Cerrada', @ahora - INTERVAL 1205 MINUTE),
(3, 1, 'Caducidad', 'Alta', 3, NULL, 'El lote se encuentra VENCIDO. Debe registrarse su baja como merma (RN-005).', 'Abierta', @hoy - INTERVAL 3 DAY),
(4, 2, 'Cadena_de_frio', 'Critica', NULL, 4, 'Refrigerador General superó los 4.0 °C durante más de 15 min.', 'Abierta', @ahora - INTERVAL 10 MINUTE),
(5, 4, 'Caducidad', 'Media', 10, NULL, 'El lote está a 2 días o menos de vencer.', 'Abierta', @ahora - INTERVAL 18 HOUR);

INSERT INTO `historial_atencion_alertas` (`id_alerta`, `id_usuario`, `accion_tomada`, `comentario`, `fecha_registro`) VALUES
(2, 2, 'Reconocer', 'Alerta detectada. Revisando empaque del motor del refrigerador.', @ahora - INTERVAL 1200 MINUTE),
(2, 2, 'Atender', 'Técnico de mantenimiento en camino. Productos reubicados temporalmente.', @ahora - INTERVAL 1185 MINUTE),
(2, 2, 'Cerrar', 'Se cambió el empaque; temperatura estable. Lotes revisados y liberados.', @ahora - INTERVAL 1110 MINUTE);

-- ----------------------------------------------------------------------------
-- 9. Descuentos (RF-014) y donaciones (RF-015)
-- ----------------------------------------------------------------------------
INSERT INTO `sugerencias_descuento` (`id_lote`, `porcentaje_sugerido`, `estado_autorizacion`, `id_supervisor_autoriza`, `fecha_sugerencia`, `fecha_respuesta`) VALUES
(2, 10.00, 'Autorizado', 2, @ahora - INTERVAL 8 HOUR, @ahora - INTERVAL 7 HOUR);

INSERT INTO `propuestas_donacion` (`id_donacion`, `folio_donacion`, `id_banco`, `id_supervisor`, `estado_propuesta`, `fecha_propuesta`) VALUES
(1, CONCAT('DON-', DATE_FORMAT(@hoy, '%Y%m%d'), '-001'), 1, 2, 'Propuesta', @ahora - INTERVAL 6 HOUR);

INSERT INTO `detalle_donacion_lotes` (`id_donacion`, `id_lote`, `cantidad_donada`) VALUES
(1, 2, 10.00);

-- Bitácora inicial (RNF-011)
INSERT INTO `bitacora_auditoria` (`id_usuario`, `tabla_afectada`, `operacion`, `detalles`, `fecha_registro`) VALUES
(NULL, 'todas', 'INSERT', 'Carga inicial de datos ficticios de prueba (script 02_datos_prueba.sql)', @ahora);
