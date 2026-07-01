import os
import time
import json
import threading
import http.server
import socketserver
from datetime import datetime, timedelta

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
            "guacharito": "",
            "guacharo": "",
            "centenaplus": "",
            "centenaplus_pendiente_raw": "",
            "centenaplus_pendiente_time": 0,
            "condor": "",
            "selva": "",
            "granjita": "",
            "lottoactivo": "",
            "lottoactivord": "",
            "lottoactivo2": "",
            "lottoactivoint": "",
            "historial_hoy": {},
            "resumen_enviado": False
        }

def guardar_store(data):
    with open(ARCHIVO_STORE, "w") as f:
        json.dump(data, f, indent=2)

store = cargar_store()

# Resetear historial si cambio el dia
hoy = datetime.now().strftime("%Y-%m-%d")
if store.get("fecha") != hoy:
    print(f"[INFO] Nuevo dia detectado: {hoy}. Resetear historial.")
    store["fecha"] = hoy
    store["historial_hoy"] = {}
    store["resumen_enviado"] = False
    for key in ["guacharito", "guacharo", "centenaplus", "condor", "selva", 
                "granjita", "lottoactivo", "lottoactivord", "lottoactivo2", "lottoactivoint"]:
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
        "condor": "", "selva": "", "granjita": "",
        "lottoactivo": "", "lottoactivord": "", "lottoactivo2": "", "lottoactivoint": "",
        "historial_hoy": {}, "resumen_enviado": False
    }
    guardar_store(store)
    print("[INFO] Store reseteado.")

# ==============================================================================
# TELEGRAM BOT
# ==============================================================================

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown") if TOKEN else None

@bot.message_handler(commands=['reset'])
def cmd_reset(message):
    reset_store()
    bot.reply_to(message, "✅ Store reseteado. El proximo escaneo enviara todo.")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    msg = (
        f"📊 *Estado del Bot*\n\n"
        f"Guacharito: `{store.get('guacharito','(vacío)')}`\n"
        f"Guacharo: `{store.get('guacharo','(vacío)')}`\n"
        f"Centena Plus: `{store.get('centenaplus','(vacío)')}`\n"
        f"Condor Gana: `{store.get('condor','(vacío)')}`\n"
        f"Selva Plus: `{store.get('selva','(vacío)')}`\n"
        f"La Granjita: `{store.get('granjita','(vacío)')}`\n"
        f"Lotto Activo: `{store.get('lottoactivo','(vacío)')}`\n"
        f"Lotto Activo RD: `{store.get('lottoactivord','(vacío)')}`\n"
        f"Lotto Activo 2: `{store.get('lottoactivo2','(vacío)')}`\n"
        f"Lotto Activo Int: `{store.get('lottoactivoint','(vacío)')}`\n"
        f"Resumen enviado: {'SI' if store.get('resumen_enviado') else 'NO'}"
    )
    bot.reply_to(message, msg, parse_mode="Markdown")

def polling_comandos():
    print("[INFO] Hilo de comandos iniciado")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

if bot:
    t_cmd = threading.Thread(target=polling_comandos, daemon=True)
    t_cmd.start()

# ==============================================================================
# ENVIO
# ==============================================================================

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
# SCRAPER UTILS
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

def parsear_generico(html, nombre_buscar, horarios):
    """Parsea estructura generica de loteriadehoy.com: h4=numero+animal, h6=nombre+hora"""
    soup = BeautifulSoup(html, 'html.parser')
    resultados = []
    for h4 in soup.find_all('h4'):
        texto_h4 = h4.get_text(strip=True)
        h6 = h4.find_next('h6')
        if not h6:
            continue
        texto_h6 = h6.get_text(strip=True)
        if nombre_buscar.lower() not in texto_h6.lower():
            continue
        partes = texto_h4.split(None, 1)
        if len(partes) < 2:
            continue
        numero, animal = partes[0], partes[1]
        hora = ""
        for h in horarios:
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

# ==============================================================================
# LOTERIAS - HORARIOS
# ==============================================================================

HORARIOS_00 = ["08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", 
               "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM",
               "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM", "08:00 PM"]

HORARIOS_30 = ["08:30 AM", "09:30 AM", "10:30 AM", "11:30 AM", 
               "12:30 PM", "01:30 PM", "02:30 PM", "03:30 PM",
               "04:30 PM", "05:30 PM", "06:30 PM", "07:30 PM"]

HORARIOS_05 = ["08:05 AM", "09:05 AM", "10:05 AM", "11:05 AM", 
               "12:05 PM", "01:05 PM", "02:05 PM", "03:05 PM",
               "04:05 PM", "05:05 PM", "06:05 PM", "07:05 PM"]

HORARIOS_15 = ["08:15 AM", "09:15 AM", "10:15 AM", "11:15 AM", 
               "12:15 PM", "01:15 PM", "02:15 PM", "03:15 PM",
               "04:15 PM", "05:15 PM", "06:15 PM", "07:15 PM", "08:15 PM"]

# --- CONDOR GANA ---
def obtener_condor():
    html = fetch("https://loteriadehoy.com/animalito/condorgana/resultados/")
    return parsear_generico(html, "Condor Gana", HORARIOS_00) if html else None

# --- SELVA PLUS ---
def obtener_selva():
    html = fetch("https://loteriadehoy.com/animalito/selvaplus/resultados/")
    return parsear_generico(html, "Selva Plus", HORARIOS_00) if html else None

# --- LA GRANJITA ---
def obtener_granjita():
    html = fetch("https://loteriadehoy.com/animalito/lagranjita/resultados/")
    return parsear_generico(html, "La Granjita", HORARIOS_00) if html else None

# --- LOTTO ACTIVO ---
def obtener_lottoactivo():
    html = fetch("https://loteriadehoy.com/animalito/lottoactivo/resultados/")
    return parsear_generico(html, "Lotto Activo", HORARIOS_00) if html else None

# --- LOTTO ACTIVO RD ---
def obtener_lottoactivord():
    html = fetch("https://loteriadehoy.com/animalito/lottoactivord/resultados/")
    return parsear_generico(html, "Lotto Activo RDominicana", HORARIOS_00) if html else None

# --- LOTTO ACTIVO 2 (MONJE MILLONARIO) ---
def obtener_lottoactivo2():
    html = fetch("https://loteriadehoy.com/animalito/lottoactivo2(monjemillonario)/resultados/")
    return parsear_generico(html, "Lotto Activo 2 (Monje Millonario)", HORARIOS_05) if html else None

# --- GUACHARITO MILLONARIO ---
def obtener_guacharito():
    html = fetch("https://loteriadehoy.com/animalito/elguacharitomillonario/resultados/")
    return parsear_generico(html, "El Guacharito Millonario", HORARIOS_30) if html else None

# --- LOTTO ACTIVO INTERNACIONAL ---
def obtener_lottoactivoint():
    html = fetch("https://loteriadehoy.com/animalito/lottoactivordint/resultados/")
    return parsear_generico(html, "Lotto Activo Rd Int", HORARIOS_30) if html else None

# --- CENTENA PLUS ---
def obtener_centenaplus():
    html = fetch("https://loteriadehoy.com/animalito/centenaplus/resultados/")
    return parsear_generico(html, "Centena Plus", HORARIOS_15) if html else None

# --- GUACHARO ACTIVO ---
def obtener_guacharo():
    html = fetch("https://loteriadehoy.com/animalito/guacharoactivo/resultados/")
    return parsear_generico(html, "Guacharo Activo", HORARIOS_00) if html else None

# ==============================================================================
# PROCESADORES
# ==============================================================================

DELAY_CENTENA = 300  # 5 minutos

def procesar_inmediato(key, r, nombre, emoji):
    """Procesa loteria que envia inmediatamente"""
    if not r:
        return False
    raw = r["raw"]
    hora = r["hora"]
    if es_nuevo(key, raw):
        agregar_historial(key, hora, raw)
        msg = f"🔔 *RESULTADO RECIENTE* 🔔\n\n{emoji} *{nombre}* ({hora}):\n`{raw}`\n\n🍀 *@resultadoslafija* 🍀"
        enviar(msg)
        return True
    else:
        print(f"[INFO] {nombre}: sin cambios (ultimo={store.get(key,'')})")
    return False

def procesar_centenaplus(r):
    """Procesa Centena Plus con delay de 5 min"""
    if not r:
        return False
    raw = r["raw"]
    hora = r["hora"]
    
    if store.get("centenaplus") == raw:
        print(f"[INFO] Centena Plus: sin cambios (ya publicado: {raw})")
        return False
    
    pendiente_raw = store.get("centenaplus_pendiente_raw", "")
    pendiente_time = store.get("centenaplus_pendiente_time", 0)
    
    if pendiente_raw != raw:
        store["centenaplus_pendiente_raw"] = raw
        store["centenaplus_pendiente_time"] = time.time()
        guardar_store(store)
        print(f"[INFO] Centena Plus: NUEVO ({raw}) - esperando {DELAY_CENTENA}s...")
        return False
    
    tiempo_transcurrido = time.time() - pendiente_time
    if tiempo_transcurrido >= DELAY_CENTENA:
        store["centenaplus"] = raw
        store["centenaplus_pendiente_raw"] = ""
        store["centenaplus_pendiente_time"] = 0
        agregar_historial("centenaplus", hora, raw)
        guardar_store(store)
        msg = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Centena Plus* ({hora}):\n`{raw}`\n\n🍀 *@resultadoslafija* 🍀"
        enviar(msg)
        print(f"[OK] Centena Plus PUBLICADO tras {int(tiempo_transcurrido)}s")
        return True
    else:
        restante = DELAY_CENTENA - tiempo_transcurrido
        print(f"[INFO] Centena Plus: pendiente ({raw}) - faltan {int(restante)}s")
    return False

# ==============================================================================
# RESUMEN DIARIO
# ==============================================================================

NOMBRES_LOTERIAS = {
    "condor": "Condor Gana",
    "selva": "Selva Plus",
    "granjita": "La Granjita",
    "lottoactivo": "Lotto Activo",
    "lottoactivord": "Lotto Activo RD",
    "lottoactivo2": "Lotto Activo 2 (Monje Millonario)",
    "lottoactivoint": "Lotto Activo Internacional",
    "guacharito": "Guacharito Millonario",
    "guacharo": "Guacharo Activo",
    "centenaplus": "Centena Plus"
}

EMOJIS_LOTERIAS = {
    "condor": "🦅",
    "selva": "🌴",
    "granjita": "🐔",
    "lottoactivo": "🎯",
    "lottoactivord": "🇩🇴",
    "lottoactivo2": "🧙",
    "lottoactivoint": "🌍",
    "guacharito": "🎰",
    "guacharo": "🐦",
    "centenaplus": "💯"
}

def enviar_resumen_diario():
    """Envia resumen diario de todas las loterias"""
    if store.get("resumen_enviado"):
        print("[INFO] Resumen diario ya enviado hoy")
        return
    
    fecha_str = datetime.now().strftime("%d/%m/%Y")
    msg = f"📋 *RESUMEN DEL DIA* 📋\n📅 {fecha_str}\n\n"
    
    for key in ["condor", "selva", "granjita", "lottoactivo", "lottoactivord", 
                "lottoactivo2", "lottoactivoint", "guacharito", "guacharo", "centenaplus"]:
        datos = store.get("historial_hoy", {}).get(key, [])
        nombre = NOMBRES_LOTERIAS.get(key, key)
        emoji = EMOJIS_LOTERIAS.get(key, "🎲")
        
        msg += f"{emoji} *{nombre}*\n"
        if datos:
            for item in datos:
                msg += f"{item['hora']}: `{item['raw']}`\n"
        else:
            msg += "Sin resultados registrados\n"
        msg += "\n"
    
    msg += "🍀 *@resultadoslafija* 🍀"
    
    if enviar(msg):
        store["resumen_enviado"] = True
        guardar_store(store)
        print("[OK] Resumen diario enviado")

def debe_enviar_resumen():
    """Verifica si es hora de enviar resumen (despues de 8:35 PM)"""
    ahora = datetime.now()
    return ahora.hour >= 20 and ahora.minute >= 35

# ==============================================================================
# MONITOREO PRINCIPAL
# ==============================================================================

def ciclo():
    print(f"[INFO] === Escaneando {datetime.now().strftime('%H:%M:%S')} ===")
    
    # --- MIN 00: Condor, Selva, Granjita, Lotto Activo, Lotto Activo RD, Guacharo ---
    procesar_inmediato("condor", obtener_condor(), "Condor Gana", "🦅")
    procesar_inmediato("selva", obtener_selva(), "Selva Plus", "🌴")
    procesar_inmediato("granjita", obtener_granjita(), "La Granjita", "🐔")
    procesar_inmediato("lottoactivo", obtener_lottoactivo(), "Lotto Activo", "🎯")
    procesar_inmediato("lottoactivord", obtener_lottoactivord(), "Lotto Activo RD", "🇩🇴")
    procesar_inmediato("guacharo", obtener_guacharo(), "Guacharo Activo", "🐦")
    
    # --- MIN 05: Lotto Activo 2 ---
    procesar_inmediato("lottoactivo2", obtener_lottoactivo2(), "Lotto Activo 2 (Monje Millonario)", "🧙")
    
    # --- MIN 15: Centena Plus (con delay) ---
    r = obtener_centenaplus()
    print(f"[INFO] Centena Plus scrap: {r}")
    if r:
        procesar_centenaplus(r)
    
    # --- MIN 30: Guacharito, Lotto Activo Internacional ---
    procesar_inmediato("guacharito", obtener_guacharito(), "Guacharito Millonario", "🎰")
    procesar_inmediato("lottoactivoint", obtener_lottoactivoint(), "Lotto Activo Internacional", "🌍")
    
    # --- Resumen diario (despues de 8:35 PM) ---
    if debe_enviar_resumen():
        enviar_resumen_diario()

def bucle_bot():
    time.sleep(3)
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
