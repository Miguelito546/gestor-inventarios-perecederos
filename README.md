# Gestor Inteligente de Inventarios y Trazabilidad de Productos Perecederos

Prototipo v1 de la aplicación descrita en la SRS v0.2 (Equipo 1, Fundamentos de Ingeniería de Software, ITVH).
Es una aplicación web con Python + Flask + MariaDB que se abre en el navegador, en computadora o celular.
Usa solo **datos ficticios** (RNF-013) y un **simulador IoT** para las temperaturas.

---

## 1. Qué necesitas instalado

| Programa | Versión | Para qué |
|---|---|---|
| Python | 3.12 o más reciente | Ejecuta la aplicación (al instalarlo, marca **"Add python.exe to PATH"**) |
| MariaDB | 11.4 | Base de datos (anota la **contraseña de root** y el **puerto**) |
| Navegador | Chrome, Edge o Firefox actualizados | Para usar la aplicación |

Flask y las demás librerías se instalan solas en el paso 3.

## 2. Descarga el proyecto

En GitHub, da clic en **Code → Download ZIP** y descomprímelo, por ejemplo en `Documentos\gestor-inventarios-perecederos`.
(Si usas Git: `git clone https://github.com/Miguelito546/gestor-inventarios-perecederos.git`.)

## 3. Instala las dependencias (solo la primera vez)

Da doble clic en **`instalar.bat`**. Crea una carpeta `venv` e instala Flask, PyMySQL y fpdf2.

> Sin Windows o sin el .bat, abre una terminal en la carpeta y ejecuta:
> `python -m venv venv`, luego `venv\Scripts\activate` (Windows) o `source venv/bin/activate` (Mac/Linux), y después `pip install -r requirements.txt`.

## 4. Configura la conexión a MariaDB

Abre **`configuracion.py`** con el Bloc de notas y cambia estas dos líneas:

```python
DB_PORT = int(os.environ.get("DB_PORT", "3307"))        # el puerto que elegiste al instalar MariaDB 11.4
DB_CONTRASENA = os.environ.get("DB_CONTRASENA", "")      # escribe tu contraseña entre las comillas: "miClave"
```

No hace falta crear la base de datos: la aplicación la crea sola la primera vez (`kfc_inventory_db`).

## 5. Arranca la aplicación

Da doble clic en **`iniciar.bat`**. Se abrirá el navegador en **http://localhost:5000**.
Para detenerla, cierra la ventana negra o presiona `Ctrl + C`.

### Usuarios de prueba (contraseña de todos: `Demo2026`)

| Usuario | Rol | Sucursal |
|---|---|---|
| `admin` | Administrador | Todas (elige la sucursal en la barra superior) |
| `supervisor` | Supervisor | Centro Villahermosa |
| `empleado` | Empleado | Centro Villahermosa |
| `supervisor2` | Supervisor | Plaza Galerías |
| `empleado2` | Empleado | Plaza Galerías |

### Antes de cada presentación

Da doble clic en **`reiniciar_datos.bat`**. Borra todo y vuelve a cargar los datos de prueba **con las fechas de ese día**.
También se puede hacer desde la aplicación: *Bitácora → Reiniciar datos de demostración* (como `admin`).

Desde el celular (misma red Wi-Fi): abre `http://IP-DE-TU-COMPUTADORA:5000`. La IP aparece al ejecutar `ipconfig`. Puede que Windows pida permitir Python en el firewall.

---

## 6. Guion sugerido para la demostración

1. **RF-001**: entra con una contraseña mal escrita (el mensaje no dice qué dato falló) y luego como `empleado`.
2. **RF-002**: en *Inventario*, los colores por estado y los filtros.
3. **RF-006 y RF-007**: *Registrar lote*, y luego *Consumo / merma*. El sistema sugiere el lote que vence primero (FEFO) y no deja consumir un lote vencido.
4. Entra como `supervisor`. En *Alertas* hay una de caducidad y otra de un lote vencido. Atiéndelas y ciérralas con comentario (RF-012).
5. **RF-011 en vivo**: como `admin`, en *Sucursales y umbrales*, baja el **tiempo tolerado a 1 minuto**. En *Simulador IoT*, da **Simular falla** a un refrigerador. En 1 o 2 minutos aparece la alerta crítica y los lotes de ese equipo pasan a **Retenido**. En *Monitoreo* la gráfica marca las lecturas en rojo (RF-009). Para cerrar la alerta, decide por cada lote si se libera o se da de baja.
6. **RF-014 y RF-015**: *Descuentos* (10 % o 25 % según los días) y *Donaciones* (folio, confirmar entrega).
7. **RF-013**: *Trazabilidad*. Busca "Avícola" y abre *Lotes afectados* (exporta CSV).
8. **RF-016**: *Reportes* en pantalla, PDF y CSV.
9. **RF-017 y RF-018**: como `admin`, en *Usuarios* y *Sucursales y umbrales*. Revisa también la *Bitácora* (RNF-011).
10. **RNF-004**: entra como `supervisor2`; solo ve Plaza Galerías.

---

## 7. Dónde está cada requisito

| Requisito | Archivo |
|---|---|
| RF-001 Iniciar sesión, cierre por inactividad (15 min) | `app/modulos/auth.py`, `app/__init__.py` |
| RF-002, RF-005, RF-006, RF-007 | `app/modulos/inventario.py` (módulo Inventario) |
| RF-003, RF-004, RF-010, RF-011, RF-014 (procesos automáticos cada 30 s) | `app/motor.py` |
| RF-008, RF-009 | `app/modulos/monitoreo.py` (módulo Monitoreo), `app/simulador.py` |
| RF-012 | `app/modulos/alertas.py` (módulo Alertas) |
| RF-013 | `app/modulos/trazabilidad.py` (módulo Trazabilidad) |
| RF-014, RF-015 | `app/modulos/aprovechamiento.py` |
| RF-016 | `app/modulos/reportes.py` (módulo Reportes) |
| RF-017, RF-018, bitácora | `app/modulos/administracion.py` |
| Base de datos (estructura, datos, consultas) | `sql/` (los cambios respecto al script original están en `sql/CAMBIOS.md`) |

### Simulador IoT externo (opcional)

La aplicación trae su propio simulador. Para mostrar que recibe lecturas de un dispositivo externo por la API (RI-004), abre otra terminal con la aplicación encendida:

```
venv\Scripts\activate
python simulador_iot.py --equipos 1 3 --falla 3
python simulador_iot.py --una 1 9.5
```

API: `POST /api/lecturas` con JSON `{"id_equipo": 1, "temperatura": 3.2, "marca_tiempo": "2026-10-25T10:30:00"}` (la marca de tiempo es opcional) y el encabezado `X-Token: simulador-demo`.

## 8. Problemas comunes

| Mensaje | Solución |
|---|---|
| `No se pudo conectar a MariaDB ...` | Revisa que el servicio de MariaDB 11.4 esté encendido (Servicios de Windows) y que el puerto y la contraseña en `configuracion.py` sean correctos. |
| `'python' no se reconoce como un comando` | Reinstala Python marcando "Add python.exe to PATH". |
| `Address already in use` / puerto 5000 ocupado | Cambia `PUERTO_APP` en `configuracion.py` (por ejemplo a 5050) y abre esa dirección. |
| Las fechas de los datos ya no cuadran | Ejecuta `reiniciar_datos.bat`. |
| Aparecen muchas alertas "Sin señal" | Salen cuando la aplicación estuvo apagada con el simulador detenido. Ejecuta `reiniciar_datos.bat`. |

## Licencias de terceros

Chart.js 4.4.1 (MIT) se incluye en `app/static/js/` para que la gráfica funcione sin internet.
