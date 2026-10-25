"""Acceso a la base de datos MariaDB (RI-005)."""
from contextlib import contextmanager
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT
from flask import g

import configuracion as cfg

CARPETA_SQL = Path(__file__).resolve().parent.parent / "sql"


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
    try:
        cx = conectar(con_base=False)
    except pymysql.err.OperationalError as e:
        raise ConnectionError(
            f"No se pudo conectar a MariaDB en {cfg.DB_HOST}:{cfg.DB_PORT} con el usuario '{cfg.DB_USUARIO}'. "
            f"Revisa que MariaDB esté encendido y la contraseña en configuracion.py. Detalle: {e.args[-1]}"
        ) from e
    with cx.cursor() as c:
        c.execute("SHOW DATABASES LIKE %s", (cfg.DB_NOMBRE,))
        existe = c.fetchone() is not None
        if existe:
            c.execute(f"SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = %s", (cfg.DB_NOMBRE,))
            existe = c.fetchone()["n"] >= 17
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
