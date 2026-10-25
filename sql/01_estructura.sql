-- ============================================================================
-- PROYECTO: Gestor Inteligente de Inventarios y Trazabilidad de Productos Perecederos
-- INSTITUCIÓN: Instituto Tecnológico de Villahermosa
-- CURSO: Fundamentos de Ingeniería de Software
-- DOCUMENTO REF: SRS-001-Versión 0.2
-- AUTOR: Alfredo Alejandro Peralta Sarracino & Equipo 1
-- DATABASE ENGINE: MySQL 8.0+ / MariaDB 10.4+
-- VERSIÓN DEL SCRIPT: 2 (corregida para el prototipo; ver sql/CAMBIOS.md)
-- ============================================================================

-- Creación de la Base de Datos
CREATE DATABASE IF NOT EXISTS `kfc_inventory_db` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `kfc_inventory_db`;
SET NAMES utf8mb4;

-- Limpieza previa opcional de tablas (en orden inverso por las FK)
DROP TABLE IF EXISTS `bitacora_auditoria`;
DROP TABLE IF EXISTS `detalle_donacion_lotes`;
DROP TABLE IF EXISTS `propuestas_donacion`;
DROP TABLE IF EXISTS `sugerencias_descuento`;
DROP TABLE IF EXISTS `bancos_alimentos`;
DROP TABLE IF EXISTS `historial_atencion_alertas`;
DROP TABLE IF EXISTS `alertas`;
DROP TABLE IF EXISTS `lecturas_temperatura`;
DROP TABLE IF EXISTS `movimientos_inventario`;
DROP TABLE IF EXISTS `historial_estados_lote`;
DROP TABLE IF EXISTS `lotes`;
DROP TABLE IF EXISTS `insumos`;
DROP TABLE IF EXISTS `proveedores`;
DROP TABLE IF EXISTS `usuarios`;
DROP TABLE IF EXISTS `equipos_almacenamiento`;
DROP TABLE IF EXISTS `configuracion_umbrales`;
DROP TABLE IF EXISTS `sucursales`;

-- ----------------------------------------------------------------------------
-- 1. ESTRUCTURA BASE DE SUCURSALES Y CONFIGURACIÓN (RF-018, RNF-010)
-- ----------------------------------------------------------------------------

CREATE TABLE `sucursales` (
    `id_sucursal` INT AUTO_INCREMENT PRIMARY KEY,
    `nombre` VARCHAR(100) NOT NULL,
    `direccion` TEXT NOT NULL,
    `telefono` VARCHAR(20) NULL,
    `activa` TINYINT(1) DEFAULT 1,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE `configuracion_umbrales` (
    `id_config` INT AUTO_INCREMENT PRIMARY KEY,
    `id_sucursal` INT NOT NULL,
    `dias_anticipacion_caducidad` INT DEFAULT 2 COMMENT 'Días N para alerta de caducidad (RF-010)',
    `tiempo_tolerado_temp_min` INT DEFAULT 15 COMMENT 'Minutos de tolerancia fuera de rango (RF-011)',
    `pct_descuento_nivel_1` DECIMAL(5,2) DEFAULT 10.00 COMMENT '% descuento a N<=2 días (RN-003)',
    `pct_descuento_nivel_2` DECIMAL(5,2) DEFAULT 25.00 COMMENT '% descuento a N<=1 día (RN-003)',
    `horas_min_donacion` INT DEFAULT 24 COMMENT 'Horas mínimas de margen antes de vencer (RN-004)',
    `minutos_sin_senal` INT DEFAULT 10 COMMENT 'Minutos sin lecturas para alerta Sin señal (RF-011) [v2]',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_config_sucursal` (`id_sucursal`) COMMENT 'Una configuración por sucursal [v2]',
    FOREIGN KEY (`id_sucursal`) REFERENCES `sucursales`(`id_sucursal`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `equipos_almacenamiento` (
    `id_equipo` INT AUTO_INCREMENT PRIMARY KEY,
    `id_sucursal` INT NOT NULL,
    `nombre_equipo` VARCHAR(100) NOT NULL COMMENT 'Ej: Cámara 1, Congelador B',
    `tipo_equipo` ENUM('refrigeracion', 'congelacion') NOT NULL,
    `temp_min_permitida` DECIMAL(4,1) NOT NULL COMMENT 'Ej: 0.0 °C (RD-001)',
    `temp_max_permitida` DECIMAL(4,1) NOT NULL COMMENT 'Ej: 4.0 °C para refri, -18.0 °C para congelador',
    `estado_operativo` ENUM('normal', 'alerta_temperatura', 'fuera_de_servicio') DEFAULT 'normal',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`id_sucursal`) REFERENCES `sucursales`(`id_sucursal`) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 2. USUARIOS, ROLES Y AUTENTICACIÓN (RF-001, RF-017, RNF-003, RNF-004)
-- ----------------------------------------------------------------------------

CREATE TABLE `usuarios` (
    `id_usuario` INT AUTO_INCREMENT PRIMARY KEY,
    `id_sucursal` INT NULL COMMENT 'NULL para Administradores Globales (RNF-004)',
    `nombre_completo` VARCHAR(150) NOT NULL,
    `username` VARCHAR(50) UNIQUE NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL COMMENT 'Contraseña cifrada Hash (RNF-003)',
    `rol` ENUM('Empleado', 'Supervisor', 'Administrador') NOT NULL,
    `activo` TINYINT(1) DEFAULT 1,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- [v2] RESTRICT en lugar de SET NULL: un empleado sin sucursal se confundiría con un administrador global (RNF-004)
    FOREIGN KEY (`id_sucursal`) REFERENCES `sucursales`(`id_sucursal`) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 3. CATÁLOGO DE INSUMOS Y PROVEEDORES (RF-005, RF-006, RF-013)
-- ----------------------------------------------------------------------------

CREATE TABLE `proveedores` (
    `id_proveedor` INT AUTO_INCREMENT PRIMARY KEY,
    `nombre_empresa` VARCHAR(150) NOT NULL,
    `contacto_nombre` VARCHAR(100) NULL,
    `telefono` VARCHAR(20) NULL,
    `email` VARCHAR(100) NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE `insumos` (
    `id_insumo` INT AUTO_INCREMENT PRIMARY KEY,
    `nombre` VARCHAR(120) UNIQUE NOT NULL COMMENT 'Ej: Pollo marinado, Lácteos, Ensaladas',
    `categoria` VARCHAR(80) NOT NULL,
    `unidad_medida` VARCHAR(30) NOT NULL COMMENT 'Ej: kg, piezas, litros, cajas',
    `temp_min_conservacion` DECIMAL(4,1) NOT NULL,
    `temp_max_conservacion` DECIMAL(4,1) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 4. CONTROL DE LOTES, INVENTARIO Y ESTADOS (RF-003, RF-004, RF-006, RD-002)
-- ----------------------------------------------------------------------------

CREATE TABLE `lotes` (
    `id_lote` INT AUTO_INCREMENT PRIMARY KEY,
    `codigo_lote` VARCHAR(50) UNIQUE NOT NULL COMMENT 'Identificador único del lote (RF-006)',
    `id_insumo` INT NOT NULL,
    `id_proveedor` INT NOT NULL,
    `id_sucursal` INT NOT NULL,
    `id_equipo` INT NOT NULL COMMENT 'Equipo inicial/actual donde se almacena',
    `cantidad_inicial` DECIMAL(10,2) NOT NULL,
    `cantidad_actual` DECIMAL(10,2) NOT NULL COMMENT 'Cantidad disponible',
    `fecha_recepcion` DATETIME NOT NULL,
    `fecha_caducidad` DATETIME NOT NULL,
    `estado_lote` ENUM('Fresco', 'Próximo a vencer', 'Vencido', 'Retenido') DEFAULT 'Fresco' COMMENT 'Estado del lote (RF-003)',
    `riesgo_merma` ENUM('Bajo', 'Medio', 'Alto', 'Sin datos') DEFAULT 'Sin datos' COMMENT 'Riesgo de merma (RF-004)',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`id_insumo`) REFERENCES `insumos`(`id_insumo`),
    FOREIGN KEY (`id_proveedor`) REFERENCES `proveedores`(`id_proveedor`),
    FOREIGN KEY (`id_sucursal`) REFERENCES `sucursales`(`id_sucursal`),
    FOREIGN KEY (`id_equipo`) REFERENCES `equipos_almacenamiento`(`id_equipo`),
    CONSTRAINT `chk_cantidad_positiva` CHECK (`cantidad_actual` >= 0)
) ENGINE=InnoDB;

CREATE TABLE `historial_estados_lote` (
    `id_historial_estado` INT AUTO_INCREMENT PRIMARY KEY,
    `id_lote` INT NOT NULL,
    `estado_anterior` ENUM('Fresco', 'Próximo a vencer', 'Vencido', 'Retenido'),
    `estado_nuevo` ENUM('Fresco', 'Próximo a vencer', 'Vencido', 'Retenido') NOT NULL,
    `motivo_cambio` TEXT NULL,
    `id_usuario` INT NULL COMMENT 'Responsable del cambio; NULL si lo hizo el sistema (RF-012) [v2]',
    `fecha_cambio` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`id_lote`) REFERENCES `lotes`(`id_lote`) ON DELETE CASCADE,
    FOREIGN KEY (`id_usuario`) REFERENCES `usuarios`(`id_usuario`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `movimientos_inventario` (
    `id_movimiento` INT AUTO_INCREMENT PRIMARY KEY,
    `id_lote` INT NOT NULL,
    `id_usuario` INT NOT NULL,
    `tipo_movimiento` ENUM('Consumo', 'Merma', 'Ajuste_Descuento', 'Donacion') NOT NULL,
    `cantidad` DECIMAL(10,2) NOT NULL,
    `motivo_merma` VARCHAR(255) NULL COMMENT 'Obligatorio en tipo Merma (RF-007, RN-005)',
    `sugerido_por_fefo` TINYINT(1) DEFAULT 1 COMMENT 'Registra si aceptó la recomendación FEFO',
    `fecha_movimiento` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`id_lote`) REFERENCES `lotes`(`id_lote`),
    FOREIGN KEY (`id_usuario`) REFERENCES `usuarios`(`id_usuario`)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 5. MONITOREO DE TEMPERATURA Y SIMULADOR IOT (RF-008, RF-009, RI-004)
-- ----------------------------------------------------------------------------

CREATE TABLE `lecturas_temperatura` (
    `id_lectura` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `id_equipo` INT NOT NULL,
    `temperatura_registrada` DECIMAL(4,1) NOT NULL,
    `fecha_hora_lectura` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `fuera_de_rango` TINYINT(1) DEFAULT 0,
    FOREIGN KEY (`id_equipo`) REFERENCES `equipos_almacenamiento`(`id_equipo`) ON DELETE CASCADE,
    UNIQUE KEY `uk_equipo_timestamp` (`id_equipo`, `fecha_hora_lectura`)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 6. GESTIÓN DE ALERTAS Y SEGUIMIENTO (RF-010, RF-011, RF-012)
-- ----------------------------------------------------------------------------

CREATE TABLE `alertas` (
    `id_alerta` INT AUTO_INCREMENT PRIMARY KEY,
    `id_sucursal` INT NOT NULL,
    `tipo_alerta` ENUM('Caducidad', 'Cadena_de_frio', 'Sin_senal') NOT NULL,
    `severidad` ENUM('Media', 'Alta', 'Critica') NOT NULL,
    `id_lote` INT NULL,
    `id_equipo` INT NULL,
    `descripcion` TEXT NOT NULL,
    `estado_alerta` ENUM('Abierta', 'Reconocida', 'En_atencion', 'Cerrada') DEFAULT 'Abierta',
    `fecha_creacion` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`id_sucursal`) REFERENCES `sucursales`(`id_sucursal`),
    FOREIGN KEY (`id_lote`) REFERENCES `lotes`(`id_lote`) ON DELETE SET NULL,
    FOREIGN KEY (`id_equipo`) REFERENCES `equipos_almacenamiento`(`id_equipo`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `historial_atencion_alertas` (
    `id_atencion` INT AUTO_INCREMENT PRIMARY KEY,
    `id_alerta` INT NOT NULL,
    `id_usuario` INT NOT NULL,
    `accion_tomada` ENUM('Reconocer', 'Atender', 'Cerrar') NOT NULL,
    `comentario` TEXT NOT NULL COMMENT 'Comentario obligatorio (RF-012)',
    `fecha_registro` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`id_alerta`) REFERENCES `alertas`(`id_alerta`) ON DELETE CASCADE,
    FOREIGN KEY (`id_usuario`) REFERENCES `usuarios`(`id_usuario`)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 7. DESCUENTOS DINÁMICOS Y DONACIONES (RF-014, RF-015, RN-003, RN-004)
-- ----------------------------------------------------------------------------

CREATE TABLE `bancos_alimentos` (
    `id_banco` INT AUTO_INCREMENT PRIMARY KEY,
    `nombre_institucion` VARCHAR(150) NOT NULL,
    `direccion` TEXT NOT NULL,
    `contacto_telefono` VARCHAR(20) NULL,
    `email` VARCHAR(100) NULL,
    `activo` TINYINT(1) DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE `sugerencias_descuento` (
    `id_descuento` INT AUTO_INCREMENT PRIMARY KEY,
    `id_lote` INT NOT NULL,
    `porcentaje_sugerido` DECIMAL(5,2) NOT NULL COMMENT '10% o 25% (RN-003)',
    `estado_autorizacion` ENUM('Pendiente', 'Autorizado', 'Rechazado') DEFAULT 'Pendiente',
    `id_supervisor_autoriza` INT NULL,
    `motivo_rechazo` VARCHAR(255) NULL,
    `fecha_sugerencia` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `fecha_respuesta` DATETIME NULL,
    FOREIGN KEY (`id_lote`) REFERENCES `lotes`(`id_lote`) ON DELETE CASCADE,
    FOREIGN KEY (`id_supervisor_autoriza`) REFERENCES `usuarios`(`id_usuario`)
) ENGINE=InnoDB;

CREATE TABLE `propuestas_donacion` (
    `id_donacion` INT AUTO_INCREMENT PRIMARY KEY,
    `folio_donacion` VARCHAR(50) UNIQUE NOT NULL COMMENT 'Folio generado (RF-015)',
    `id_banco` INT NOT NULL,
    `id_supervisor` INT NOT NULL,
    `estado_propuesta` ENUM('Propuesta', 'Confirmada', 'Cancelada') DEFAULT 'Propuesta',
    `fecha_propuesta` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `fecha_confirmacion` DATETIME NULL,
    FOREIGN KEY (`id_banco`) REFERENCES `bancos_alimentos`(`id_banco`),
    FOREIGN KEY (`id_supervisor`) REFERENCES `usuarios`(`id_usuario`)
) ENGINE=InnoDB;

CREATE TABLE `detalle_donacion_lotes` (
    `id_detalle_donacion` INT AUTO_INCREMENT PRIMARY KEY,
    `id_donacion` INT NOT NULL,
    `id_lote` INT NOT NULL,
    `cantidad_donada` DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (`id_donacion`) REFERENCES `propuestas_donacion`(`id_donacion`) ON DELETE CASCADE,
    FOREIGN KEY (`id_lote`) REFERENCES `lotes`(`id_lote`)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 8. AUDITORÍA GENERAL DEL SISTEMA (RNF-011)
-- ----------------------------------------------------------------------------

CREATE TABLE `bitacora_auditoria` (
    `id_bitacora` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `id_usuario` INT NULL,
    `tabla_afectada` VARCHAR(50) NOT NULL,
    `operacion` ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    `detalles` TEXT NULL,
    `fecha_registro` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`id_usuario`) REFERENCES `usuarios`(`id_usuario`) ON DELETE SET NULL
) ENGINE=InnoDB;
