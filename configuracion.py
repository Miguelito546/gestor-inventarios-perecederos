"""
Configuración del prototipo.

Edita SOLO este archivo para adaptar la aplicación a tu computadora.
"""
import os

# --- Base de datos MariaDB -------------------------------------------------
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3307"))          # Puerto que elegiste al instalar MariaDB 11.4
DB_USUARIO = os.environ.get("DB_USUARIO", "root")
DB_CONTRASENA = os.environ.get("DB_CONTRASENA", "")        # <-- Escribe aquí la contraseña de root
DB_NOMBRE = os.environ.get("DB_NOMBRE", "kfc_inventory_db")

# --- Aplicación ------------------------------------------------------------
PUERTO_APP = int(os.environ.get("PUERTO_APP", "5000"))     # Se abre en http://localhost:5000
CLAVE_SECRETA = os.environ.get("CLAVE_SECRETA", "prototipo-equipo1-itvh-cambiar")
MINUTOS_INACTIVIDAD = 15        # RF-001: cierre de sesión por inactividad
ZONA_HORARIA = "-06:00"         # RNF-012: Villahermosa (sin horario de verano)

# --- Procesos automáticos --------------------------------------------------
CICLO_MOTOR_SEG = 30            # RF-003 / RF-010: cada cuánto se recalculan estados y alertas
SIMULADOR_INTEGRADO = True      # RF-008: el simulador IoT arranca junto con la aplicación
SIMULADOR_INTERVALO_SEG = 30    # Cada cuánto envía una lectura por equipo
TOKEN_SIMULADOR = os.environ.get("TOKEN_SIMULADOR", "simulador-demo")  # Para el simulador externo (RI-004)
