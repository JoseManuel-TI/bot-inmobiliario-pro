from flask import Flask, render_template
import json
import os
import threading
import time

from buscador import hacer_scraping

app = Flask(__name__, template_folder='.', static_folder='.')
DATA_PATH = 'propiedades.json'
DATA_MAX_AGE_SECONDS = int(os.environ.get("DATA_MAX_AGE_SECONDS", 6 * 60 * 60))
REFRESH_RETRY_SECONDS = int(os.environ.get("REFRESH_RETRY_SECONDS", 15 * 60))

_refresh_lock = threading.Lock()
_last_refresh_attempt = 0.0


def _is_data_stale():
    if not os.path.exists(DATA_PATH):
        return True
    age = time.time() - os.path.getmtime(DATA_PATH)
    return age > DATA_MAX_AGE_SECONDS


def _refresh_data_if_needed():
    global _last_refresh_attempt

    if not _is_data_stale():
        return

    now = time.time()
    if (now - _last_refresh_attempt) < REFRESH_RETRY_SECONDS:
        return

    if not _refresh_lock.acquire(blocking=False):
        return

    try:
        _last_refresh_attempt = now
        print("♻️ Datos vencidos, actualizando propiedades...")
        hacer_scraping()
    except Exception as e:
        print(f"❌ Error actualizando propiedades: {e}")
    finally:
        _refresh_lock.release()

@app.route('/')
def index():
    _refresh_data_if_needed()

    datos = []
    try:
        if os.path.exists(DATA_PATH):
            with open(DATA_PATH, 'r', encoding='utf-8') as f:
                datos = json.load(f)
    except Exception as e:
        print(f"Error leyendo JSON: {e}")

    # --- Lógica de Marketing ---
    # Mostramos solo las primeras 2 en la web para mantener el diseño limpio
    # y que el usuario sienta que hay mucho más contenido en el reporte full.
    datos_web = datos[:2] 

    return render_template('index.html', propiedades=datos_web)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
