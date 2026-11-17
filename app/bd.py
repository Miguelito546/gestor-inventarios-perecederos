"""Acceso a la base de datos MariaDB (RI-005)."""
import logging
import ssl
import sys
from contextlib import contextmanager
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT
from flask import g

import configuracion as cfg

# Dentro del .exe los archivos de datos están en la carpeta temporal de PyInstaller
_RAIZ = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
CARPETA_SQL = _RAIZ / "sql"
log = logging.getLogger("bd")


def _opciones_ssl():
    """Conexión cifrada para la base en la nube (Aiven la exige)."""
    if not cfg.DB_SSL:
        return None
    if cfg.DB_CERTIFICADO:
        return {"ca": cfg.DB_CERTIFICADO}          # cifrado y verificando la identidad del servidor
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE           # cifrado, sin verificar el certificado
    return contexto


def conectar(con_base=True, multi=False):
    return pymysql.connect(
        host=cfg.DB_HOST,
        port=cfg.DB_PORT,
        user=cfg.DB_USUARIO,
        password=cfg.DB_CONTRASENA,
        database=cfg.DB_NOMBRE if con_base else None,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        init_command=f"SET time_zone = '{cfg.ZONA_HORARIA}'",
        client_flag=CLIENT.MULTI_STATEMENTS if multi else 0,
        ssl=_opciones_ssl(),
        connect_timeout=15,
    )


class BD:
    """Envoltura pequeña sobre una conexión: q() lista, q1() un registro, ex() escritura."""

    def __init__(self):
        self.cx = conectar()

    def q(self, sql, args=None):
        with self.cx.cursor() as c:
            c.execute(sql, args)
            return c.fetchall()

    def q1(self, sql, args=None):
        with self.cx.cursor() as c:
            c.execute(sql, args)
            return c.fetchone()

    def ex(self, sql, args=None):
        """Ejecuta una escritura y devuelve el id insertado (o filas afectadas si no hay id)."""
        with self.cx.cursor() as c:
            filas = c.execute(sql, args)
            return c.lastrowid or filas

    def ahora(self):
        return self.q1("SELECT NOW() AS n")["n"]

    @contextmanager
    def transaccion(self):
        self.cx.begin()
        try:
            yield self
            self.cx.commit()
        except Exception:
            self.cx.rollback()
            raise

    def cerrar(self):
        try:
            self.cx.close()
        except Exception:
            pass


def bd():
    """Conexión de la petición web actual."""
    if "bd" not in g:
        g.bd = BD()
    return g.bd


def cerrar_bd(_exc=None):
    conexion = g.pop("bd", None)
    if conexion:
        conexion.cerrar()


def auditar(base, id_usuario, tabla, operacion, detalles):
    """RNF-011: cada alta, modificación o eliminación queda con usuario, fecha y hora."""
    base.ex(
        "INSERT INTO bitacora_auditoria (id_usuario, tabla_afectada, operacion, detalles) VALUES (%s,%s,%s,%s)",
        (id_usuario, tabla, operacion, detalles),
    )


def base_existe():
    if cfg.ERROR_CONEXION_INI:
        raise ConnectionError(cfg.ERROR_CONEXION_INI + " Cada línea debe verse así: servidor = valor")
    try:
        cx = conectar(con_base=False)
    except pymysql.err.OperationalError as e:
        raise ConnectionError(
            f"No se pudo conectar a MariaDB en {cfg.DB_HOST}:{cfg.DB_PORT} con el usuario '{cfg.DB_USUARIO}'. "
            f"Revisa los datos de conexion.ini (servidor, puerto, usuario, contraseña y ssl) "
            f"y que haya internet o que MariaDB esté encendido. Detalle: {e.args[-1]}"
        ) from e
    with cx.cursor() as c:
        c.execute("SHOW DATABASES LIKE %s", (cfg.DB_NOMBRE,))
        existe = c.fetchone() is not None
        if existe:
            c.execute(f"SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = %s", (cfg.DB_NOMBRE,))
            existe = c.fetchone()["n"] >= 17
        if existe:  # si una carga anterior se interrumpió, las tablas existen pero vacías
            c.execute(f"SELECT COUNT(*) AS n FROM `{cfg.DB_NOMBRE}`.`usuarios`")
            existe = c.fetchone()["n"] > 0
    cx.close()
    return existe


def ejecutar_script(nombre):
    """Ejecuta un archivo .sql completo de la carpeta sql/."""
    texto = (CARPETA_SQL / nombre).read_text(encoding="utf-8")
    texto = texto.replace("`kfc_inventory_db`", f"`{cfg.DB_NOMBRE}`")
    cx = conectar(con_base=False, multi=True)
    with cx.cursor() as c:
        c.execute(texto)
        while c.nextset():
            pass
    cx.close()


def reiniciar_base():
    """Crea la base desde cero con la estructura y los datos ficticios de prueba."""
    ejecutar_script("01_estructura.sql")
    ejecutar_script("02_datos_prueba.sql")


# ---------------------------------------------------------------- Base compartida entre varias copias
TABLAS_EXTRA = """
CREATE TABLE IF NOT EXISTS `simulador_modos` (
    `id_equipo` INT PRIMARY KEY,
    `modo` VARCHAR(12) NOT NULL DEFAULT 'normal'
) ENGINE=InnoDB
"""


def asegurar_tablas_extra():
    """Tablas de apoyo del prototipo (no forman parte del modelo de la SRS)."""
    cx = conectar()
    with cx.cursor() as c:
        c.execute(TABLAS_EXTRA)
    cx.close()


def preparar_base(reiniciar=False):
    """Crea la base con los datos de prueba SOLO si todavía no existe (o si se pide reiniciar).

    Un candado en el servidor evita que dos computadoras la creen al mismo tiempo.
    Devuelve True si se crearon o recargaron los datos.
    """
    base_existe()  # lanza ConnectionError con un mensaje claro si no hay conexión
    cx = conectar(con_base=False)
    nombre = f"gestor_preparar_{cfg.DB_NOMBRE}"[:64]
    try:
        with cx.cursor() as c:
            c.execute("SELECT GET_LOCK(%s, 120) AS ok", (nombre,))
        creada = False
        if reiniciar or not base_existe():
            reiniciar_base()
            creada = True
        asegurar_tablas_extra()
        return creada
    finally:
        try:
            with cx.cursor() as c:
                c.execute("SELECT RELEASE_LOCK(%s)", (nombre,))
        finally:
            cx.close()


class Turno:
    """Candado con nombre en el servidor (GET_LOCK) para que una tarea corra en UNA sola copia.

    La copia que lo obtiene lo conserva mientras su conexión siga abierta. Si esa copia se
    cierra o pierde la conexión, el servidor libera el candado y otra copia toma el turno.
    """

    def __init__(self, tarea):
        self.nombre = f"gestor_{tarea}_{cfg.DB_NOMBRE}"[:64]
        self.cx = None
        self.sin_candados = False

    def tengo_turno(self):
        if self.sin_candados:
            return True
        try:
            if self.cx is None:
                self.cx = conectar(con_base=False)
        except Exception:
            self.soltar()
            return False  # sin conexión: se reintenta en la siguiente vuelta
        try:
            with self.cx.cursor() as c:
                c.execute("SELECT IS_USED_LOCK(%s) = CONNECTION_ID() AS mio", (self.nombre,))
                if (c.fetchone() or {}).get("mio") == 1:
                    return True
                c.execute("SELECT GET_LOCK(%s, 0) AS ok", (self.nombre,))
                return (c.fetchone() or {}).get("ok") == 1
        except pymysql.MySQLError as e:
            self.soltar()
            if e.args and isinstance(e.args[0], int) and not 2000 <= e.args[0] < 3000:
                # El servidor respondió, pero no admite GET_LOCK: esta copia lo ejecuta siempre
                log.warning("El servidor no admite candados (GET_LOCK): %s", e)
                self.sin_candados = True
                return True
            return False  # se perdió la conexión: se reintenta en la siguiente vuelta
        except Exception:
            self.soltar()
            return False

    def soltar(self):
        if self.cx is not None:
            try:
                self.cx.close()
            except Exception:
                pass
        self.cx = None

    @staticmethod
    def alguien_lo_tiene(base, tarea):
        nombre = f"gestor_{tarea}_{cfg.DB_NOMBRE}"[:64]
        try:
            return base.q1("SELECT IS_USED_LOCK(%s) AS id", (nombre,))["id"] is not None
        except pymysql.MySQLError:
            return True  # el servidor no admite candados; el simulador corre en cada copia
