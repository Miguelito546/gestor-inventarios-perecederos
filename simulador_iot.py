"""Simulador IoT externo (RI-004): envía lecturas a la API del sistema por HTTP.

La aplicación ya trae un simulador integrado; este script sirve para demostrar que el
sistema recibe lecturas de un dispositivo externo (RF-008).

Uso:
    python simulador_iot.py                     # lecturas normales a los equipos 1, 2 y 3
    python simulador_iot.py --equipos 1 4       # elegir equipos
    python simulador_iot.py --falla 1           # el equipo 1 se calienta (falla de frío)
    python simulador_iot.py --una 1 9.5         # manda una sola lectura de 9.5 °C al equipo 1
"""
import argparse
import json
import random
import time
import urllib.request

import configuracion as cfg

URL = f"http://localhost:{cfg.PUERTO_APP}/api/lecturas"


def enviar(lecturas):
    peticion = urllib.request.Request(
        URL, data=json.dumps(lecturas).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Token": cfg.TOKEN_SIMULADOR})
    try:
        with urllib.request.urlopen(peticion, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def main():
    p = argparse.ArgumentParser(description="Simulador IoT externo")
    p.add_argument("--equipos", nargs="+", type=int, default=[1, 2, 3])
    p.add_argument("--falla", nargs="*", type=int, default=[])
    p.add_argument("--intervalo", type=int, default=30)
    p.add_argument("--una", nargs=2, metavar=("EQUIPO", "TEMPERATURA"))
    a = p.parse_args()

    if a.una:
        print(enviar({"id_equipo": int(a.una[0]), "temperatura": float(a.una[1])}))
        return
    temperaturas = {}
    print(f"Enviando lecturas a {URL} cada {a.intervalo} s. Ctrl + C para detener.")
    while True:
        lote = []
        for e in a.equipos:
            base = temperaturas.get(e, 2.5)
            base = base + random.uniform(0.3, 0.8) if e in a.falla else base + (2.5 - base) * 0.3 + random.uniform(-0.3, 0.3)
            temperaturas[e] = base
            lote.append({"id_equipo": e, "temperatura": round(base, 1)})
        for lectura, r in zip(lote, enviar(lote)):
            print(time.strftime("%H:%M:%S"), lectura, "->", r.get("estado"), r.get("detalle", ""),
                  "ALERTA GENERADA" if r.get("alerta_generada") else "")
        time.sleep(a.intervalo)


if __name__ == "__main__":
    main()
