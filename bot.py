import os
import time
import json
import threading
import http.server
import socketserver

import requests
from bs4 import BeautifulSoup
import telebot

# ==============================================================================
# CONFIGURACION
# ==============================================================================

TOKEN = os.environ.get("BOT_TOKEN", "")
CANAL_ID = os.environ.get("CANAL_ID", "@resultadoslafija")
PORT = int(os.environ.get("PORT", 8080))

print(f"[INFO] Bot iniciando... PORT={PORT} CANAL={CANAL_ID}")

if not TOKEN:
    print("[WARN] BOT_TOKEN no definido. El bot no enviara mensajes.")

# ==============================================================================
# SCRAPER
# ==============================================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.text
        print(f"[WARN] HTTP {r.status_code} en {url}")
    except Exception as e:
        print(f"[WARN] Error fetch {url}: {e}")
    return None

def parsear(html, nombre):
    soup = BeautifulSoup(html, 'html.parser')
    resultados = []
    for h4 in soup.find_all('h4'):
        texto_h4 = h4.get_text(strip=True)
        h6 = h4.find_next('h6')
        if not h6:
            continue
        texto_h6 = h6.get_text(strip=True)
        if nombre.lower() not in texto_h6.lower():
            continue
        partes = texto_h4.split(None, 1)
        if len(partes) < 2:
            continue
        numero, animal = partes[0], partes[1]
        hora = ""
        for h in ["08:30 AM", "09:30 AM", "10:30 AM", "11:30 AM", 
                  "12:30 PM", "01:30 PM", "02:30 PM", "03:30 PM",
                  "04:30 PM", "05:30 PM", "06:30 PM", "07:30 PM"]:
            if h in texto_h6:
                hora = h
                break
        if hora:
            resultados.append({
                "hora": hora,
                "numero": numero,
                "animal": animal.capitalize(),
                "raw": f"{numero} {animal.capitalize()}"
            })
    return resultados[-1] if resultados else None

def obtener_guacharito():
    html = fetch("https://loteriadehoy.com/animalito/elguacharitomillonario/resultados/")
    return parsear(html, "Guacharito Millonario") if html else None

def obtener_guacharo():
    html = fetch("https://loteriadehoy.com/animalito/guacharoactivo/resultados/")
    return parsear(html, "Guacharo Activo") if html else None

# ==============================================================================
# PERSISTENCIA
# ==============================================================================

try:
    with open("store.json", "r") as f:
        store = json.load(f)
except:
    store = {"guacharito": "", "guacharo": ""}

def guardar():
    with open("store.json", "w") as f:
        json.dump(store, f)

def es_nuevo(key, val):
    if store.get(key) == val:
        return False
    store[key] = val
    guardar()
    return True

# ==============================================================================
# TELEGRAM
# ==============================================================================

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown") if TOKEN else None

def enviar(mensaje):
    if not bot:
        print("[WARN] Bot no configurado, no se envia mensaje")
        return False
    try:
        bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown")
        print("[OK] Mensaje enviado a Telegram")
        return True
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")
        return False

# ==============================================================================
# MONITOREO
# ==============================================================================

def ciclo():
    print("[INFO] Escaneando resultados...")
    
    r = obtener_guacharito()
    if r and es_nuevo("guacharito", r["raw"]):
        msg = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guacharito Millonario* ({r['hora']}):\n`{r['raw']}`\n\n🍀 *@resultadoslafija* 🍀"
        enviar(msg)
    else:
        print(f"[INFO] Guacharito: sin cambios (ultimo={store.get('guacharito','')})")
    
    r = obtener_guacharo()
    if r and es_nuevo("guacharo", r["raw"]):
        msg = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guácharo Activo* ({r['hora']}):\n`{r['raw']}`\n\n🍀 *@resultadoslafija* 🍀"
        enviar(msg)
    else:
        print(f"[INFO] Guacharo: sin cambios (ultimo={store.get('guacharo','')})")

def bucle_bot():
    time.sleep(2)
    ciclo()
    while True:
        time.sleep(90)
        try:
            ciclo()
        except Exception as e:
            print(f"[ERROR] En ciclo: {e}")

# ==============================================================================
# SERVIDOR HTTP
# ==============================================================================

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def servidor():
    print(f"[INFO] Servidor HTTP en puerto {PORT}")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

# ==============================================================================
# ARRANQUE
# ==============================================================================

if __name__ == "__main__":
    t = threading.Thread(target=servidor, name="ServidorHTTP")
    t.daemon = False
    t.start()
    bucle_bot()
