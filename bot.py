import os
import time
import json
import threading
import http.server
import socketserver
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import telebot

# ==============================================================================
# CONFIGURACION
# ==============================================================================

TOKEN = os.environ.get("BOT_TOKEN", "")
CANAL_ID = os.environ.get("CANAL_ID", "@resultadoslafija")
PORT = int(os.environ.get("PORT", 8080))

print("=" * 60)
print("[BOOT] Bot iniciando...")
print(f"[BOOT] PORT={PORT} CANAL={CANAL_ID}")
print(f"[BOOT] TOKEN={'SI' if TOKEN else 'NO'}")
print("=" * 60)

# ==============================================================================
# PERSISTENCIA
# ==============================================================================

ARCHIVO_STORE = "store.json"

def cargar_store():
    try:
        with open(ARCHIVO_STORE, "r") as f:
            return json.load(f)
    except:
        return {
            "fecha": "",
            "guacharito": "", "guacharo": "", "centenaplus": "",
            "centenaplus_pendiente_raw": "", "centenaplus_pendiente_time": 0,
            "selva": "", "granjita": "",
            "lottoactivo": "", "lottoactivord": "", "lottoactivo2": "", "lottoactivoint": "",
            "historial_hoy": {}, "resumen_enviado": False
        }

def guardar_store(data):
    with open(ARCHIVO_STORE, "w") as f:
        json.dump(data, f, indent=2)

store = cargar_store()
print(f"[BOOT] Store: {store.get('fecha','nuevo')}")

hoy = datetime.now().strftime("%Y-%m-%d")
if store.get("fecha") != hoy:
    print(f"[BOOT] Nuevo dia: {hoy}")
    store["fecha"] = hoy
    store["historial_hoy"] = {}
    store["resumen_enviado"] = False
    for key in ["guacharito", "guacharo", "centenaplus", "selva", "granjita",
                "lottoactivo", "lottoactivord", "lottoactivo2", "lottoactivoint"]:
        store[key] = ""
    store["centenaplus_pendiente_raw"] = ""
    store["centenaplus_pendiente_time"] = 0
    guardar_store(store)

def es_nuevo(key, val):
    if store.get(key) == val:
        return False
    store[key] = val
    guardar_store(store)
    return True

def agregar_historial(loteria, hora, raw):
    if loteria not in store["historial_hoy"]:
        store["historial_hoy"][loteria] = []
    for item in store["historial_hoy"][loteria]:
        if item["hora"] == hora:
            return
    store["historial_hoy"][loteria].append({"hora": hora, "raw": raw})
    guardar_store(store)

def reset_store():
    global store
    store = {
        "fecha": hoy,
        "guacharito": "", "guacharo": "", "centenaplus": "",
        "centenaplus_pendiente_raw": "", "centenaplus_pendiente_time": 0,
        "selva": "", "granjita": "",
        "lottoactivo": "", "lottoactivord": "", "lottoactivo2": "", "lottoactivoint": "",
        "historial_hoy": {}, "resumen_enviado": False
    }
    guardar_store(store)
    print("[INFO] Store reseteado")

# ==============================================================================
# TELEGRAM
# ==============================================================================

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown") if TOKEN else None

if bot:
    @bot.message_handler(commands=['reset'])
    def cmd_reset(message):
        reset_store()
        bot.reply_to(message, "✅ Store reseteado")

    @bot.message_handler(commands=['status'])
    def cmd_status(message):
        msg = "📊 *Estado*\n"
        for k in ["guacharito","guacharo","centenaplus","selva","granjita",
                  "lottoactivo","lottoactivord","lottoactivo2","lottoactivoint"]:
            msg += f"{k}: `{store.get(k,'vacío')}`\n"
        bot.reply_to(message, msg, parse_mode="Markdown")

    def polling():
        print("[INFO] Comandos iniciados")
        bot.infinity_polling()

    threading.Thread(target=polling, daemon=True).start()
    print("[BOOT] Comandos activos")

# ==============================================================================
# ENVIO
# ==============================================================================

def enviar(mensaje):
    if not bot:
        print("[WARN] Sin bot")
        return False
    try:
        bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown")
        print("[OK] Enviado")
        return True
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")
        return False

# ==============================================================================
# SCRAPER
# ==============================================================================

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def fetch(url):
    print(f"[FETCH] {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"[FETCH] HTTP {r.status_code} {len(r.text)} chars")
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"[WARN] fetch error: {e}")
    return None

def parsear(html, nombre, horarios):
    print(f"[PARSE] {nombre}")
    soup = BeautifulSoup(html, 'html.parser')
    resultados = []
    h4s = soup.find_all('h4')
    print(f"[PARSE] {len(h4s)} h4")
    for h4 in h4s:
        txt4 = h4.get_text(strip=True)
        h5 = h4.find_next('h5')
        if not h5:
            h5 = h4.find_next_sibling('h5')
        if not h5:
            continue
        txt5 = h5.get_text(strip=True)
        if nombre.lower() not in txt5.lower():
            continue
        partes = txt4.split(None, 1)
        if len(partes) < 2:
            continue
        num, ani = partes[0], partes[1]
        hora = ""
        for h in horarios:
            if h in txt5:
                hora = h
                break
        if hora:
            resultados.append({"hora": hora, "numero": num, "animal": ani.capitalize(), "raw": f"{num} {ani.capitalize()}"})
    print(f"[PARSE] {len(resultados)} resultados")
    return resultados[-1] if resultados else None

# ==============================================================================
# HORARIOS
# ==============================================================================

H00 = ["08:00 AM","09:00 AM","10:00 AM","11:00 AM","12:00 PM","01:00 PM","02:00 PM","03:00 PM","04:00 PM","05:00 PM","06:00 PM","07:00 PM","08:00 PM"]
H30 = ["08:30 AM","09:30 AM","10:30 AM","11:30 AM","12:30 PM","01:30 PM","02:30 PM","03:30 PM","04:30 PM","05:30 PM","06:30 PM","07:30 PM"]
H05 = ["08:05 AM","09:05 AM","10:05 AM","11:05 AM","12:05 PM","01:05 PM","02:05 PM","03:05 PM","04:05 PM","05:05 PM","06:05 PM","07:05 PM"]
H15 = ["08:15 AM","09:15 AM","10:15 AM","11:15 AM","12:15 PM","01:15 PM","02:15 PM","03:15 PM","04:15 PM","05:15 PM","06:15 PM","07:15 PM","08:15 PM"]

# ==============================================================================
# LOTERIAS
# ==============================================================================

def get_selva(): return parsear(fetch("https://loteriadehoy.com/animalito/selvaplus/resultados/"), "Selva Plus", H00)
def get_granjita(): return parsear(fetch("https://loteriadehoy.com/animalito/lagranjita/resultados/"), "La Granjita", H00)
def get_lotto(): return parsear(fetch("https://loteriadehoy.com/animalito/lottoactivo/resultados/"), "Lotto Activo", H00)
def get_lottord(): return parsear(fetch("https://loteriadehoy.com/animalito/lottoactivord/resultados/"), "Lotto Activo RDominicana", H00)
def get_lotto2(): return parsear(fetch("https://loteriadehoy.com/animalito/lottoactivo2(monjemillonario)/resultados/"), "Lotto Activo 2 (Monje Millonario)", H05)
def get_guacharito(): return parsear(fetch("https://loteriadehoy.com/animalito/elguacharitomillonario/resultados/"), "El Guacharito Millonario", H30)
def get_lottoint(): return parsear(fetch("https://loteriadehoy.com/animalito/lottoactivordint/resultados/"), "Lotto Activo Rd Int", H30)
def get_centena(): return parsear(fetch("https://loteriadehoy.com/animalito/centenaplus/resultados/"), "Centena Plus", H15)
def get_guacharo(): return parsear(fetch("https://loteriadehoy.com/animalito/guacharoactivo/resultados/"), "Guacharo Activo", H00)

# ==============================================================================
# PROCESADORES
# ==============================================================================

DELAY = 300

def proc(key, r, nombre, emoji):
    print(f"[PROC] {nombre}")
    if not r:
        print(f"[PROC] {nombre}: SIN DATOS")
        return
    raw, hora = r["raw"], r["hora"]
    print(f"[PROC] {nombre}: {raw} @ {hora}")
    if es_nuevo(key, raw):
        agregar_historial(key, hora, raw)
        enviar(f"🔔 *RESULTADO RECIENTE* 🔔\n\n{emoji} *{nombre}* ({hora}):\n`{raw}`\n\n🍀 *@resultadoslafija* 🍀")
    else:
        print(f"[PROC] {nombre}: sin cambios")

def proc_centena(r):
    print("[PROC] Centena Plus")
    if not r:
        print("[PROC] Centena: SIN DATOS")
        return
    raw, hora = r["raw"], r["hora"]
    print(f"[PROC] Centena: {raw} @ {hora}")
    if store.get("centenaplus") == raw:
        print("[PROC] Centena: ya publicado")
        return
    pend = store.get("centenaplus_pendiente_raw","")
    pt = store.get("centenaplus_pendiente_time",0)
    if pend != raw:
        store["centenaplus_pendiente_raw"] = raw
        store["centenaplus_pendiente_time"] = time.time()
        guardar_store(store)
        print(f"[PROC] Centena: NUEVO - esperando {DELAY}s")
        return
    trans = time.time() - pt
    if trans >= DELAY:
        store["centenaplus"] = raw
        store["centenaplus_pendiente_raw"] = ""
        store["centenaplus_pendiente_time"] = 0
        agregar_historial("centenaplus", hora, raw)
        guardar_store(store)
        enviar(f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Centena Plus* ({hora}):\n`{raw}`\n\n🍀 *@resultadoslafija* 🍀")
        print(f"[OK] Centena PUBLICADO")
    else:
        print(f"[PROC] Centena: faltan {int(DELAY-trans)}s")

# ==============================================================================
# RESUMEN
# ==============================================================================

NOMBRES = {
    "selva":"Selva Plus","granjita":"La Granjita","lottoactivo":"Lotto Activo",
    "lottoactivord":"Lotto Activo RD","lottoactivo2":"Lotto Activo 2 (Monje Millonario)",
    "lottoactivoint":"Lotto Activo Internacional","guacharito":"Guacharito Millonario",
    "guacharo":"Guacharo Activo","centenaplus":"Centena Plus"
}
EMOJIS = {
    "selva":"🌴","granjita":"🐔","lottoactivo":"🎯","lottoactivord":"🇩🇴",
    "lottoactivo2":"🧙","lottoactivoint":"🌍","guacharito":"🎰","guacharo":"🐦","centenaplus":"💯"
}

def enviar_resumen():
    if store.get("resumen_enviado"):
        return
    fecha = datetime.now().strftime("%d/%m/%Y")
    msg = f"📋 *RESUMEN DEL DIA* 📋\n📅 {fecha}\n\n"
    for key in ["selva","granjita","lottoactivo","lottoactivord","lottoactivo2","lottoactivoint","guacharito","guacharo","centenaplus"]:
        datos = store.get("historial_hoy",{}).get(key,[])
        nom = NOMBRES.get(key,key)
        emo = EMOJIS.get(key,"🎲")
        msg += f"{emo} *{nom}*\n"
        for d in datos:
            msg += f"{d['hora']}: `{d['raw']}`\n"
        if not datos:
            msg += "Sin resultados\n"
        msg += "\n"
    msg += "🍀 *@resultadoslafija* 🍀"
    if enviar(msg):
        store["resumen_enviado"] = True
        guardar_store(store)

def debe_resumen():
    a = datetime.now()
    return a.hour >= 20 and a.minute >= 35

# ==============================================================================
# CICLO
# ==============================================================================

def ciclo():
    print(f"\n{'='*50}")
    print(f"[CICLO] {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    proc("selva", get_selva(), "Selva Plus", "🌴")
    proc("granjita", get_granjita(), "La Granjita", "🐔")
    proc("lottoactivo", get_lotto(), "Lotto Activo", "🎯")
    proc("lottoactivord", get_lottord(), "Lotto Activo RD", "🇩🇴")
    proc("guacharo", get_guacharo(), "Guacharo Activo", "🐦")
    proc("lottoactivo2", get_lotto2(), "Lotto Activo 2 (Monje Millonario)", "🧙")
    
    r = get_centena()
    if r: proc_centena(r)
    
    proc("guacharito", get_guacharito(), "Guacharito Millonario", "🎰")
    proc("lottoactivoint", get_lottoint(), "Lotto Activo Internacional", "🌍")
    
    if debe_resumen():
        enviar_resumen()
    
    print("[CICLO] Fin")

def bucle():
    print("[BOOT] Bucle inicia en 3s...")
    time.sleep(3)
    ciclo()
    print("[BOOT] Loop cada 90s")
    while True:
        time.sleep(90)
        try:
            ciclo()
        except Exception as e:
            print(f"[ERROR] {e}")

# ==============================================================================
# SERVIDOR HTTP (Render lo necesita)
# ==============================================================================

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Bot activo")
    def log_message(self, format, *args):
        pass

def servidor():
    print(f"[BOOT] Servidor HTTP puerto {PORT}")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

# ==============================================================================
# ARRANQUE: Servidor en thread, bot en main
# ==============================================================================

if __name__ == "__main__":
    # Servidor HTTP en thread separado (NO daemon - Render lo necesita vivo)
    srv = threading.Thread(target=servidor, name="HTTP")
    srv.daemon = False
    srv.start()
    
    # El bot corre en el hilo principal
    bucle()
