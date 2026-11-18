"""Arranca el prototipo en modo navegador:  python ejecutar.py

Si la base de datos todavía no existe, la crea con los datos ficticios de prueba.
Para recargar los datos de demostración desde cero:  python ejecutar.py --reiniciar
(Para la ventana de escritorio, usa GestorInventarios.exe o:  python escritorio.py)
"""
import sys
import threading
import webbrowser

import configuracion as cfg
from app.arranque import crear_servidor, ip_local, preparar, puerto_libre


def main():
    print(f"Conectando con la base de datos en {cfg.DB_HOST}:{cfg.DB_PORT}...")
    try:
        preparar(reiniciar="--reiniciar" in sys.argv)
    except ConnectionError as e:
        print("\n[ERROR]", e, "\n")
        input("Presiona Enter para salir...")
        sys.exit(1)

    puerto = puerto_libre(cfg.PUERTO_APP)
    url = f"http://localhost:{puerto}"
    print("\n  Gestor de Inventarios Perecederos - prototipo v1")
    print(f"  Abre en tu navegador:  {url}")
    if cfg.PERMITIR_RED and ip_local():
        print(f"  Desde otro equipo o celular de la misma red:  http://{ip_local()}:{puerto}")
    print("  Usuarios: admin / supervisor / empleado   Contraseña: Demo2026")
    print("  Para detener la aplicación presiona Ctrl + C\n")
    if "--sin-navegador" not in sys.argv:
        threading.Timer(1.5, webbrowser.open, (url,)).start()
    try:
        crear_servidor(puerto).serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
