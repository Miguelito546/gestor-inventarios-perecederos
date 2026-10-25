"""Arranca el prototipo:  python ejecutar.py

Si la base de datos todavía no existe, la crea con los datos ficticios de prueba.
Para recargar los datos de demostración desde cero:  python ejecutar.py --reiniciar
"""
import sys
import threading
import webbrowser

import configuracion as cfg
from app import crear_app, motor, simulador
from app.bd import BD, base_existe, reiniciar_base


def main():
    try:
        existe = base_existe()
    except ConnectionError as e:
        print("\n[ERROR]", e, "\n")
        input("Presiona Enter para salir...")
        sys.exit(1)

    if "--reiniciar" in sys.argv or not existe:
        print("Creando la base de datos y cargando los datos ficticios de prueba...")
        reiniciar_base()

    base = BD()
    motor.ciclo(base)  # estados y alertas al día antes de abrir la aplicación
    base.cerrar()
    motor.iniciar()
    if cfg.SIMULADOR_INTEGRADO:
        simulador.iniciar()

    print("\n  Gestor de Inventarios Perecederos - prototipo v1")
    print(f"  Abre en tu navegador:  http://localhost:{cfg.PUERTO_APP}")
    print("  Usuarios: admin / supervisor / empleado   Contraseña: Demo2026")
    print("  Para detener la aplicación presiona Ctrl + C\n")
    if "--sin-navegador" not in sys.argv:
        threading.Timer(1.5, webbrowser.open, (f"http://localhost:{cfg.PUERTO_APP}",)).start()
    crear_app().run(host="0.0.0.0", port=cfg.PUERTO_APP, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
