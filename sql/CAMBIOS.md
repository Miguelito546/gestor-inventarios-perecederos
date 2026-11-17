# Cambios a los scripts de base de datos (versión 2)

Los scripts originales de Alfredo Peralta (`GestionAlimentosKFC 1.sql`, `RegistrosKFC.sql` y `ConsultasKFC.sql`) se conservaron como base. La estructura de las 17 tablas es la misma; abajo están **todos** los cambios para que el equipo los revise.

| Archivo nuevo | Viene de |
|---|---|
| `01_estructura.sql` | Parte de estructura de `GestionAlimentosKFC 1.sql` |
| `02_datos_prueba.sql` | Datos de `GestionAlimentosKFC 1.sql` + `RegistrosKFC.sql` |
| `03_consultas.sql` | `ConsultasKFC.sql` |

Los cambios están marcados con `[v2]` dentro de los archivos.

## 01_estructura.sql

1. **`configuracion_umbrales`**: nueva columna `minutos_sin_senal` (por defecto 10), necesaria para la alerta "Sin señal" de RF-011.
2. **`configuracion_umbrales`**: `UNIQUE (id_sucursal)`, para que cada sucursal tenga una sola configuración (RF-018).
3. **`usuarios`**: la llave hacia `sucursales` pasa de `ON DELETE SET NULL` a `ON DELETE RESTRICT`. En este diseño, un usuario con sucursal vacía es un administrador global, así que al borrar una sucursal sus empleados habrían quedado con acceso a todo (RNF-004). En la aplicación, las sucursales se desactivan en vez de borrarse.
4. **`historial_estados_lote`**: nueva columna `id_usuario`, para registrar qué supervisor liberó o dio de baja un lote retenido (RF-012, RNF-011). Si el cambio lo hizo el sistema, queda vacía.
5. Se agregó `SET NAMES utf8mb4` para que los acentos se guarden bien desde cualquier cliente.

## 02_datos_prueba.sql

1. **Fechas relativas**: todas las fechas se calculan con `NOW()` y `CURDATE()`. El día de la presentación siempre habrá lotes frescos, próximos a vencer, vencidos y retenidos, y la gráfica tendrá 24 h de lecturas.
2. **Contraseñas**: el hash anterior era inventado y nadie podía iniciar sesión. Ahora es un hash real; la contraseña de todos los usuarios de prueba es `Demo2026`.
3. **Usuarios ficticios (RNF-013)**: se reemplazaron los nombres reales del equipo por nombres inventados. Los usuarios son `admin`, `supervisor`, `empleado`, `supervisor2` y `empleado2`, más `empleado_baja` (desactivado, para probar RF-001).
4. **Equipos por sucursal**: las sucursales 2 y 3 no tenían refrigeradores y sus lotes estaban guardados en equipos de Centro. Ahora cada sucursal tiene un refrigerador y un congelador, y cada lote está en un equipo de su propia sucursal.
5. **8 sucursales (RNF-010)**: se agregaron Ciudad Industrial (el caso simulado de la Propuesta), Tabasco 2000, Deportiva, Altabrisa y Universidad.
6. **Estados coherentes (RF-003, RN-002)**:
   - El lote vencido ya no aparece como "Fresco".
   - La alerta de cadena de frío del refrigerador de pollo quedó **cerrada**, con su historial completo y los lotes liberados.
   - El lote retenido de Plaza Galerías ahora sí tiene su alerta de cadena de frío abierta y lecturas fuera de rango que la justifican.
7. **Existencias que cuadran**: `cantidad_actual = cantidad_inicial − movimientos`. Antes, el lote 1 tenía un consumo de 10 kg y seguía con 50 kg.
8. **Consumo de la última semana**: un lote de pollo ya consumido (60 kg en 7 días) da el consumo promedio con el que se calcula el riesgo de merma (RF-004).
9. **Insumos**: "Lácteos" se renombró a "Leche entera", porque "Lácteos" es la categoría. Se agregaron "Papas a la francesa congeladas" y "Puré de papa". Las ensaladas ahora vienen de un proveedor de hortalizas.
10. Se agregaron un segundo banco de alimentos, el historial de estados de los lotes y un registro inicial en la bitácora.

## 03_consultas.sql

1. **Consulta 2 (FEFO)**: se agregó `fecha_caducidad > NOW()`. Antes sugería usar un lote ya caducado porque su estado guardado seguía siendo "Fresco".
2. **Consulta 5 (mermas)**: el periodo ahora es "últimos 30 días" en lugar de fechas fijas de octubre.
3. **Consultas 6b y 6c (nuevas)**: los movimientos y las alertas del lote, que RF-013 pide en la ficha de trazabilidad.
4. Se agregó `SET time_zone = '-06:00'` (hora de Villahermosa, RNF-012).

## Versión 3: base de datos compartida (noviembre 2026)

1. **Tabla nueva `simulador_modos`** (al final de `01_estructura.sql`): guarda si cada equipo del simulador está en "normal", "falla" o "sin señal". Antes vivía en la memoria de una sola computadora; con la base compartida, cualquier computadora puede simular una falla. No forma parte del modelo de la SRS; es solo de apoyo para la demostración.
2. Los scripts se probaron en **MySQL 8.0** (el que ofrece Aiven, con conexión cifrada obligatoria y llave primaria obligatoria en cada tabla) y en **MariaDB 11.4**. No hubo que cambiar nada más.
3. La aplicación ya **no recarga los datos** al arrancar si la base existe. Solo los crea la primera vez que se conecta a una base vacía, o cuando el `admin` lo pide desde *Bitácora*.

