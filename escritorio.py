"""Aplicación de escritorio: abre el prototipo en su propia ventana.

Es el programa que se convierte en GestorInventarios.exe. También se puede probar con:
    python escritorio.py

Lee la conexión de conexion.ini (junto al .exe). Si no existe, lo crea a partir de la plantilla.
Mientras la ventana está abierta, la aplicación también se puede usar desde el navegador.
"""
import html
import logging
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import configuracion as cfg

TITULO = "Gestor de Inventarios Perecederos"
_RAIZ = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
log = logging.getLogger("escritorio")
estado = {"url": None}


def configurar_registro():
    manejadores = [logging.StreamHandler()] if sys.stderr else []
    try:
        manejadores.append(logging.FileHandler(cfg.CARPETA_BASE / "gestor.log", encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", handlers=manejadores)


def asegurar_conexion_ini():
    """La primera vez crea conexion.ini con la plantilla para que solo haya que llenarlo."""
    if not cfg.ARCHIVO_CONEXION.exists():
        plantilla = _RAIZ / "conexion.ejemplo.ini"
        try:
            shutil.copyfile(plantilla, cfg.ARCHIVO_CONEXION)
            log.info("Se creó %s a partir de la plantilla", cfg.ARCHIVO_CONEXION)
        except OSError as e:
            log.warning("No se pudo crear conexion.ini: %s", e)


def abrir_archivo(ruta):
    ruta = str(ruta)
    if sys.platform.startswith("win"):
        os.startfile(ruta)  # noqa: S606 - abre con el programa predeterminado (Bloc de notas / Explorador)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", ruta])
    else:
        subprocess.Popen(["xdg-open", ruta])


class Api:
    """Funciones que la pantalla de error puede llamar desde la ventana."""

    def abrir_conexion(self):
        asegurar_conexion_ini()
        abrir_archivo(cfg.ARCHIVO_CONEXION)

    def abrir_carpeta(self):
        abrir_archivo(cfg.CARPETA_BASE)


# ------------------------------------------------------------------ Pantallas internas
ESTILO = """
<style>
  :root { color-scheme: light dark; }
  body { font-family: "Segoe UI", system-ui, sans-serif; margin: 0; min-height: 100vh; display: grid;
         place-items: center; background: #f4f6f8; color: #1f2933; }
  .caja { max-width: 640px; padding: 32px; background: #fff; border-radius: 12px;
          box-shadow: 0 4px 20px rgba(0,0,0,.08); }
  h1 { font-size: 20px; margin: 0 0 12px; }
  p, li { line-height: 1.5; }
  code { background: #eef1f4; padding: 2px 6px; border-radius: 4px; word-break: break-all; }
  .detalle { font-size: 13px; color: #52606d; background: #f8f9fa; padding: 10px; border-radius: 6px; }
  button { font: inherit; padding: 8px 16px; margin: 8px 8px 0 0; border-radius: 6px; border: 1px solid #c62828;
           background: #c62828; color: #fff; cursor: pointer; }
  button.claro { background: #fff; color: #c62828; }
  .giro { width: 36px; height: 36px; border: 4px solid #e0e0e0; border-top-color: #c62828; border-radius: 50%;
          animation: g 1s linear infinite; margin: 0 auto 16px; }
  @keyframes g { to { transform: rotate(360deg); } }
  @media (prefers-color-scheme: dark) {
    body { background: #111418; color: #e4e7eb; } .caja { background: #1b1f24; }
    code, .detalle { background: #262b31; color: #cbd2d9; } button.claro { background: #1b1f24; }
  }
</style>
"""

PANTALLA_CARGA = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">{ESTILO}</head>
<body><div class="caja" style="text-align:center"><div class="giro"></div>
<h1>{TITULO}</h1><p>Conectando con la base de datos compartida...</p>
<p class="detalle">{html.escape(cfg.DB_HOST)}:{cfg.DB_PORT}</p></div></body></html>"""


def pantalla_error(mensaje):
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">{ESTILO}</head>
<body><div class="caja"><h1>No se pudo conectar con la base de datos</h1>
<p>Revisa que haya internet y que los datos de <b>conexion.ini</b> sean correctos
(servidor, puerto, usuario, contraseña y <code>ssl = si</code> si la base está en la nube).</p>
<p>Archivo: <code>{html.escape(str(cfg.ARCHIVO_CONEXION))}</code></p>
<p class="detalle">{html.escape(mensaje)}</p>
<p>Después de guardar los cambios, <b>cierra esta ventana y vuelve a abrir el programa</b>.</p>
<button onclick="pywebview.api.abrir_conexion()">Abrir conexion.ini</button>
<button class="claro" onclick="pywebview.api.abrir_carpeta()">Abrir la carpeta del programa</button>
</div></body></html>"""


# ------------------------------------------------------------------ Arranque
def arrancar_aplicacion():
    """Conecta con la base, arranca el servidor interno y devuelve la dirección local."""
    from app.arranque import iniciar_servidor_en_segundo_plano, preparar, puerto_libre

    preparar()
    puerto = puerto_libre(cfg.PUERTO_APP)
    iniciar_servidor_en_segundo_plano(puerto)
    estado["url"] = f"http://127.0.0.1:{puerto}"
    log.info("Aplicación lista en %s", estado["url"])
    return estado["url"]


def modo_ventana(webview):
    from webview.menu import Menu, MenuAction, MenuSeparator

    webview.settings["ALLOW_DOWNLOADS"] = True          # reportes PDF y CSV
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True

    def abrir_en_navegador():
        if estado["url"]:
            webbrowser.open(estado["url"].replace("127.0.0.1", "localhost"))

    menu = [
        Menu("Opciones", [
            MenuAction("Abrir también en el navegador", abrir_en_navegador),
            MenuSeparator(),
            MenuAction("Editar conexion.ini", Api().abrir_conexion),
            MenuAction("Abrir la carpeta del programa", Api().abrir_carpeta),
        ])
    ]
    ventana = webview.create_window(TITULO, html=PANTALLA_CARGA, js_api=Api(), width=1280, height=820,
                                    min_size=(900, 600), menu=menu, text_select=True)

    def al_iniciar():
        try:
            ventana.load_url(arrancar_aplicacion())
        except Exception as e:  # sin conexión, contraseña incorrecta, etc.
            log.exception("No se pudo iniciar")
            ventana.load_html(pantalla_error(str(e)))

    webview.start(al_iniciar)


def modo_navegador_con_aviso():
    """Respaldo si la ventana integrada no está disponible: abre el navegador y muestra un aviso."""
    import tkinter as tk
    from tkinter import messagebox

    raiz = tk.Tk()
    raiz.title(TITULO)
    raiz.geometry("460x170")
    try:
        url = arrancar_aplicacion().replace("127.0.0.1", "localhost")
    except Exception as e:
        messagebox.showerror(TITULO, f"No se pudo conectar con la base de datos.\n\n{e}\n\n"
                                     f"Revisa {cfg.ARCHIVO_CONEXION} y vuelve a abrir el programa.")
        asegurar_conexion_ini()
        abrir_archivo(cfg.ARCHIVO_CONEXION)
        return
    webbrowser.open(url)
    tk.Label(raiz, text=f"La aplicación está abierta en tu navegador:\n{url}\n\n"
                        "Si cierras esta ventana, la aplicación se detiene.", justify="center").pack(expand=True)
    tk.Button(raiz, text="Abrir de nuevo en el navegador", command=lambda: webbrowser.open(url)).pack(pady=10)
    raiz.mainloop()


def verificar():
    """Prueba rápida del .exe (la usa GitHub al generarlo): revisa que todo venga empaquetado."""
    import app
    from app.bd import CARPETA_SQL

    faltan = [p for p in ("01_estructura.sql", "02_datos_prueba.sql") if not (CARPETA_SQL / p).exists()]
    aplicacion = app.crear_app()
    plantillas = aplicacion.jinja_env.list_templates()
    if "login.html" not in plantillas:
        faltan.append("plantillas")
    if not (Path(aplicacion.static_folder) / "js" / "chart.umd.js").exists():
        faltan.append("archivos estáticos")
    if not (_RAIZ / "conexion.ejemplo.ini").exists():
        faltan.append("conexion.ejemplo.ini")
    import webview  # noqa: F401  la ventana debe estar incluida
    if "--con-base" in sys.argv:  # además prueba la conexión real con conexion.ini
        from app.bd import preparar_base
        try:
            preparar_base()
        except Exception as e:  # noqa: BLE001
            faltan.append(f"conexión: {e}")
    resultado = "OK" if not faltan else "FALTAN: " + ", ".join(faltan)
    (cfg.CARPETA_BASE / "verificacion.txt").write_text(resultado, encoding="utf-8")
    return 0 if not faltan else 1


def main():
    configurar_registro()
    if "--verificar" in sys.argv:
        sys.exit(verificar())
    asegurar_conexion_ini()
    try:
        import webview
    except Exception as e:  # noqa: BLE001
        log.warning("Ventana integrada no disponible (%s); se usará el navegador", e)
        modo_navegador_con_aviso()
    else:
        try:
            modo_ventana(webview)
        except Exception as e:  # por ejemplo, Windows sin el componente WebView2
            log.exception("Falló la ventana integrada: %s", e)
            if estado["url"] is None:
                modo_navegador_con_aviso()
    os._exit(0)  # cierra también el servidor interno y los procesos automáticos


if __name__ == "__main__":
    main()
