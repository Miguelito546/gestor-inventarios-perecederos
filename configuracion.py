"""
Configuración del prototipo.

Los datos de conexión a la base de datos se leen del archivo **conexion.ini**, que va
junto a GestorInventarios.exe (o en la carpeta del proyecto si se ejecuta con Python).
Si no existe, se usan los valores de abajo (MariaDB local en el puerto 3307).

Prioridad: variables de entorno  >  conexion.ini  >  valores por defecto de este archivo.
"""
import configparser
import os
import sys
from pathlib import Path

# Carpeta donde viven conexion.ini, el certificado y el registro (junto al .exe o al proyecto)
if getattr(sys, "frozen", False):
    CARPETA_BASE = Path(sys.executable).resolve().parent
else:
    CARPETA_BASE = Path(__file__).resolve().parent

ARCHIVO_CONEXION = CARPETA_BASE / "conexion.ini"

# interpolation=None permite "%" en contraseñas; strict=False tolera secciones o claves repetidas
# (gana el último valor escrito).
_ini = configparser.ConfigParser(interpolation=None, strict=False)
ERROR_CONEXION_INI = ""
if ARCHIVO_CONEXION.exists():
    try:
        _ini.read(ARCHIVO_CONEXION, encoding="utf-8-sig")
    except (configparser.Error, UnicodeDecodeError) as _e:
        ERROR_CONEXION_INI = f"conexion.ini tiene un error de formato: {_e}"


def _valor(entorno, seccion, clave, defecto):
    if entorno in os.environ:
        return os.environ[entorno]
    return _ini.get(seccion, clave, fallback=defecto).strip()


def _si(texto):
    return str(texto).strip().lower() in ("si", "sí", "1", "true", "yes", "verdadero")


# --- Base de datos (MariaDB / MySQL) ----------------------------------------
DB_HOST = _valor("DB_HOST", "base_datos", "servidor", "localhost")
DB_PORT = int(_valor("DB_PORT", "base_datos", "puerto", "3307"))
DB_USUARIO = _valor("DB_USUARIO", "base_datos", "usuario", "root")
DB_CONTRASENA = _valor("DB_CONTRASENA", "base_datos", "contrasena", "")
DB_NOMBRE = _valor("DB_NOMBRE", "base_datos", "nombre_base", "kfc_inventory_db")
# Conexión cifrada: obligatoria en la nube (Aiven). En una base local se deja en "no".
DB_SSL = _si(_valor("DB_SSL", "base_datos", "ssl", "no"))
# Opcional: certificado de la nube (ca.pem). Si se indica, se verifica la identidad del servidor.
_ca = _valor("DB_CERTIFICADO", "base_datos", "certificado_ca", "")
DB_CERTIFICADO = str((CARPETA_BASE / _ca).resolve()) if _ca else ""

# --- Aplicación ------------------------------------------------------------
PUERTO_APP = int(_valor("PUERTO_APP", "aplicacion", "puerto", "5000"))   # http://localhost:5000
# "si": también se puede abrir desde el navegador de otro equipo o celular de la misma red
PERMITIR_RED = _si(_valor("PERMITIR_RED", "aplicacion", "permitir_red", "si"))
CLAVE_SECRETA = os.environ.get("CLAVE_SECRETA", "prototipo-equipo1-itvh-cambiar")
MINUTOS_INACTIVIDAD = 15        # RF-001: cierre de sesión por inactividad
ZONA_HORARIA = "-06:00"         # RNF-012: Villahermosa (sin horario de verano)

# --- Procesos automáticos --------------------------------------------------
# Con la base compartida, aunque haya varias copias abiertas, solo UNA ejecuta el motor
# y el simulador a la vez (se turnan solas mediante un candado en la base de datos).
CICLO_MOTOR_SEG = 30            # RF-003 / RF-010: cada cuánto se recalculan estados y alertas
SIMULADOR_INTEGRADO = _si(_valor("SIMULADOR", "aplicacion", "simulador", "si"))  # RF-008
SIMULADOR_INTERVALO_SEG = 30    # Cada cuánto envía una lectura por equipo
TOKEN_SIMULADOR = os.environ.get("TOKEN_SIMULADOR", "simulador-demo")  # Para el simulador externo (RI-004)
