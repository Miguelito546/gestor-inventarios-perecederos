# Gestor Inteligente de Inventarios y Trazabilidad de Productos Perecederos

Prototipo v1 de la aplicación descrita en la SRS v0.2 (Equipo 1, Fundamentos de Ingeniería de Software, ITVH).
Es una aplicación de escritorio para Windows (**GestorInventarios.exe**) hecha con Python + Flask, con una **base de datos MariaDB/MySQL compartida** por todas las computadoras. También se puede abrir en el navegador, en computadora o celular.
Usa solo **datos ficticios** (RNF-013) y un **simulador IoT** para las temperaturas.

---

## 1. Cómo funciona

- **GestorInventarios.exe** abre la aplicación completa en su propia ventana de Windows. No hace falta instalar Python.
- Todas las computadoras se conectan a **una sola base de datos compartida** (en la nube con Aiven, o en una PC de la red local). Por eso todos ven los mismos usuarios, lotes y alertas.
- Mientras el .exe está abierto, la aplicación también se puede usar desde el **navegador** de esa PC (menú *Opciones → Abrir también en el navegador*) o desde un celular de la misma red Wi-Fi.
- Aunque haya varias computadoras abiertas, los procesos automáticos (estados, alertas, simulador IoT) corren en **una sola** a la vez. Si esa se cierra, otra toma el turno sola en menos de un minuto.

## 2. Crear la base de datos compartida en la nube (una sola vez)

Lo hace **una persona del equipo**; las demás solo copian los datos en su `conexion.ini`. Hay dos servicios probados:

| Servicio | Costo | Detalle |
|---|---|---|
| **Aiven, MySQL plan Developer** | $5 USD al mes, cubiertos por los créditos de prueba (no pide tarjeta) | MySQL 8 normal. Se apaga cuando termina la prueba o se acaban los créditos, a menos que agregues un pago. |
| **TiDB Cloud Starter** | Gratis y no caduca | Compatible con MySQL (la aplicación se probó en TiDB 8.5). Si pasa tiempo sin uso, la primera conexión puede tardar unos segundos. |

### Opción A: Aiven (MySQL)

1. Entra a **https://console.aiven.io** y crea una cuenta.
2. **Create service → MySQL**. En **Service tier** elige **Developer** (nunca *Professional*, que cuesta desde $250 USD al mes). En **Service summary** debe decir **$5**.
3. Ponle nombre (por ejemplo `gestor-bd`) y da clic en **Create service**. Espera a que diga **Running**.
4. En **Overview → Connection information** copia **Host**, **Port**, **User** (`avnadmin`), **Password** y **Database name** (`defaultdb`). Opcional: descarga el **CA certificate** como `ca.pem` y ponlo junto al .exe.
5. Llena `conexion.ini`:

```ini
[base_datos]
servidor    = mysql-xxxxxxx-tu-proyecto.x.aivencloud.com
puerto      = 12345
usuario     = avnadmin
contrasena  = la-contraseña-de-aiven
nombre_base = defaultdb
ssl         = si
certificado_ca = ca.pem
```

### Opción B: TiDB Cloud Starter (gratis)

1. Entra a **https://tidbcloud.com** y crea una cuenta (con Google o GitHub).
2. Crea un clúster **Starter** (el gratuito). Elige la región más cercana (por ejemplo, de Estados Unidos).
3. En el clúster, da clic en **Connect**. Elige **Connect With: General** (o *MySQL CLI*) y da clic en **Generate Password** (cópiala, solo se muestra una vez).
4. Copia **HOST**, **PORT** (normalmente `4000`) y **USERNAME** (tiene la forma `xxxxxxxx.root`).
5. Llena `conexion.ini`:

```ini
[base_datos]
servidor    = gateway01.us-east-1.prod.aws.tidbcloud.com
puerto      = 4000
usuario     = xxxxxxxx.root
contrasena  = la-contraseña-generada
nombre_base = gestor
ssl         = si
certificado_ca =
```

### Después (con cualquiera de las dos)

Abre el .exe. **La primera vez** crea las tablas y carga los datos ficticios de prueba (tarda unos segundos). Las siguientes veces, y en las demás computadoras, solo se conecta.

> La contraseña queda escrita en `conexion.ini`; compártela solo con el equipo. Como los datos son ficticios (RNF-013), el riesgo es bajo.

**Opción sin internet (red local):** en una PC con MariaDB, todos ponen en `conexion.ini` la IP de esa PC (por ejemplo `servidor = 192.168.1.50`), su puerto y `ssl = no`. Esa PC debe estar prendida, con el puerto permitido en el firewall y un usuario de MariaDB que acepte conexiones de la red.

## 3. Descargar y abrir el .exe (Windows)

1. En GitHub, entra a **Releases → Versión para Windows** y descarga **GestorInventarios_Windows.zip**.
   (Cada cambio también deja el .zip en la pestaña **Actions → Generar ejecutable para Windows → Artifacts**.)
2. Descomprímelo. Trae `GestorInventarios.exe`, `conexion.ini` y `LEEME.txt`.
3. Llena `conexion.ini` (paso 2) y da doble clic en **GestorInventarios.exe**.
   - Si Windows muestra *"Windows protegió tu PC"*: **Más información → Ejecutar de todas formas** (pasa con todo programa sin firma digital).
   - Si pregunta por el firewall, permite el acceso (sirve para entrar desde el celular).
4. Si no conecta, la ventana explica qué revisar y tiene un botón para abrir `conexion.ini`. Los detalles quedan en `gestor.log`.

Requisitos: Windows 10 u 11 (ya traen el componente WebView2 que usa la ventana) e internet si la base está en la nube.

## 4. Ejecutar con Python (para desarrollo, opcional)

1. Instala Python 3.12 marcando **"Add python.exe to PATH"** y da doble clic en **`instalar.bat`** (crea `venv` e instala Flask, PyMySQL y fpdf2).
2. Copia `conexion.ejemplo.ini` como **`conexion.ini`** y llénalo (paso 2). Si no existe, se usa MariaDB local en el puerto 3307 con el usuario `root` sin contraseña.
3. **`iniciar.bat`** abre la aplicación en el navegador (`http://localhost:5000`). Para la ventana de escritorio: `python escritorio.py` (requiere `pip install pywebview`).

Para generar el .exe en tu propia PC: `pip install -r requirements-escritorio.txt` y luego `pyinstaller GestorInventarios.spec`. Queda en `dist\`.

> Si antes escribiste tu contraseña de MariaDB en `configuracion.py`, ahora va en `conexion.ini`.

## 5. Antes de usarla

### Usuarios de prueba (contraseña de todos: `Demo2026`)

| Usuario | Rol | Sucursal |
|---|---|---|
| `admin` | Administrador | Todas (elige la sucursal en la barra superior) |
| `supervisor` | Supervisor | Centro Villahermosa |
| `empleado` | Empleado | Centro Villahermosa |
| `supervisor2` | Supervisor | Plaza Galerías |
| `empleado2` | Empleado | Plaza Galerías |

### Antes de cada presentación

Como `admin`, en *Bitácora → Reiniciar datos de demostración*. Borra todo y vuelve a cargar los datos de prueba **con las fechas de ese día**.
**Ojo:** con la base compartida, esto borra los datos para **todos**. (Con Python también existe `reiniciar_datos.bat`.)

Desde el celular (misma red Wi-Fi, con el .exe abierto en una PC): abre `http://IP-DE-ESA-COMPUTADORA:5000`. La IP aparece al ejecutar `ipconfig`.

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
| Diseño: tokens (colores, tipografía, espacios), modo oscuro, responsive y estados de carga/vacío/error | `app/static/css/estilos.css`, `app/static/js/interfaz.js`, `app/templates/base.html` |
| Ventana de escritorio (.exe) y arranque | `escritorio.py`, `GestorInventarios.spec`, `app/arranque.py`, `.github/workflows/generar-exe.yml` |
| Conexión a la base compartida y turnos entre computadoras | `conexion.ini`, `configuracion.py`, `app/bd.py` |
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
| `No se pudo conectar con la base de datos` | Revisa internet y los datos de `conexion.ini` (servidor, puerto, usuario, contraseña, `ssl = si` para Aiven). En Aiven, que el servicio diga **Running**; en TiDB, que el usuario lleve el prefijo (`xxxx.root`). Con MariaDB local, que el servicio esté encendido. |
| Windows no abre la ventana | Se abre el navegador como respaldo. Revisa `gestor.log`; en Windows 10 antiguo puede faltar *Microsoft Edge WebView2 Runtime* (se descarga gratis de Microsoft). |
| `'python' no se reconoce como un comando` | Reinstala Python marcando "Add python.exe to PATH". |
| Puerto 5000 ocupado | La aplicación elige otro puerto libre sola. Para fijar uno, cambia `puerto` en la sección `[aplicacion]` de `conexion.ini`. |
| Las fechas de los datos ya no cuadran | Reinicia los datos de demostración (sección 5). |
| Aparecen muchas alertas "Sin señal" | Salen cuando ninguna computadora tuvo la aplicación abierta por un tiempo. Reinicia los datos de demostración. |
| Las páginas tardan un poco | Es normal con la base en la nube: cada consulta viaja por internet. |

## Licencias de terceros

Chart.js 4.4.1 (MIT) se incluye en `app/static/js/` para que la gráfica funcione sin internet.
