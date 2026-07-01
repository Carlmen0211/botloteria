import os
import time
import json
import threading
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import telebot
from flask import Flask

# ==============================================================================
# CONFIGURACION
# ==============================================================================

TOKEN = os.environ.get("BOT_TOKEN", "")
CANAL_ID = os.environ.get("CANAL_ID", "@resultadoslafija")
PORT = int(os.environ.get("PORT", 8080))

print("=" * 60)
print("[BOOT] Bot iniciando...")
print(f"[BOOT] PORT={PORT}")
print(f"[BOOT] CANAL_ID={CANAL_ID}")
print(f"[BOOT] TOKEN presente: {'SI' if TOKEN else 'NO'}")
print("=" * 60)

# ==============================================================================
# PERSISTENCIA
# ==============================================================================

ARCHIVO_STORE = "store.json"

def cargar_store():
    try:
        with open(ARCHIVO_STORE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[BOOT] No se pudo cargar store.json: {e}")
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
print(f"[BOOT] Store cargado. Fecha: {store.get('fecha','(nueva)')}")

hoy = datetime.now().strftime("%Y-%m-%d")
if store.get("fecha") != hoy:
    print(f"[BOOT] Nuevo dia detectado: {hoy}. Resetear historial.")
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
    print("[INFO] Store reseteado.")

# ==============================================================================
# TELEGRAM BOT
# ==============================================================================

print("[BOOT] Iniciando Telegram bot...")
bot = None
if TOKEN:
    try:
        bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
        me = bot.get_me()
        print(f"[BOOT] Bot conectado: @{me.username}")
    except Exception as e:
        print(f"[BOOT] ERROR conectando bot: {e}")
else:
    print("[BOOT] WARNING: No hay TOKEN")

if bot:
    @bot.message_handler(commands=['reset'])
    def cmd_reset(message):
        reset_store()
        bot.reply_to(message, "✅ Store reseteado.")

    @bot.message_handler(commands=['status'])
    def cmd_status(message):
        msg = "📊 *Estado*\n"
        for k in ["guacharito", "guacharo", "centenaplus", "selva", "granjita",
                  "lottoactivo", "lottoactivord", "lottoactivo2", "lottoactivoint"]:
            msg += f"{k}: `{store.get(k,'(vacío)')}`\n"
        bot.reply_to(message, msg, parse_mode="Markdown")

    def polling_comandos():
        print("[INFO] Hilo de comandos iniciado")
        bot.infinity_polling(timeout=10, long_polling_timeout=5)

    threading.Thread(target=polling_comandos, daemon=True).start()

# ==============================================================================
# ENVIO
# ==============================================================================

def enviar(mensaje):
    if not bot:
        print("[WARN] Bot no configurado, no se envia mensaje")
        return False
    try:
        bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown")
        print("[OK] Enviado a Telegram")
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
        print(f"[FETCH] HTTP {r.status_code}, {len(r.text)} chars")
        if r.status_code == 200:
            return r.text
        print(f"[WARN] HTTP {r.status_code} en {url}")
    except Exception as e:
        print(f"[WARN] Error fetch {url}: {e}")
    return None

# ==============================================================================
# PARSEADOR: usa h5 (no h6)
# ==============================================================================

def parsear_generico(html, nombre_buscar, horarios):
    print(f"[PARSE] Buscando '{nombre_buscar}'")
    soup = BeautifulSoup(html, 'html.parser')
    resultados = []
    h4s = soup.find_all('h4')
    print(f"[PARSE] h4 encontrados: {len(h4s)}")
    
    for h4 in h4s:
        texto_h4 = h4.get_text(strip=True)
        h5 = h4.find_next('h5')
        if not h5:
            h5 = h4.find_next_sibling('h5')
        if not h5:
            continue
        
        texto_h5 = h5.get_text(strip=True)
        
        if nombre_buscar.lower() not in texto_h5.lower():
            continue
        
        partes = texto_h4.split(None, 1)
        if len(partes) < 2:
            continue
        
        numero, animal = partes[0], partes[1]
        hora = ""
        for h in horarios:
            if h in texto_h5:
                hora = h
                break
        
        if hora:
            resultados.append({
                "hora": hora,
                "numero": numero,
                "animal": animal.capitalize(),
                "raw": f"{numero} {animal.capitalize()}"
            })
    
    print(f"[PARSE] Resultados parseados: {len(resultados)}")
    return resultados[-1] if resultados else None

# ==============================================================================
# HORARIOS
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

# ==============================================================================
# OBTENEDORES
# ==============================================================================

def obtener_selva():
    html = fetch("https://loteriadehoy.com/animalito/selvaplus/resultados/")
    return parsear_generico(html, "Selva Plus", HORARIOS_00) if html else None

def obtener_granjita():
    html = fetch("https://loteriadehoy.com/animalito/lagranjita/resultados/")
    return parsear_generico(html, "La Granjita", HORARIOS_00) if html else None

def obtener_lottoactivo():
    html = fetch("https://loteriadehoy.com/animalito/lottoactivo/resultados/")
    return parsear_generico(html, "Lotto Activo", HORARIOS_00) if html else None

def obtener_lottoactivord():
    html = fetch("https://loteriadehoy.com/animalito/lottoactivord/resultados/")
    return parsear_generico(html, "Lotto Activo RDominicana", HORARIOS_00) if html else None

def obtener_lottoactivo2():
    html = fetch("https://loteriadehoy.com/animalito/lottoactivo2(monjemillonario)/resultados/")
    return parsear_generico(html, "Lotto Activo 2 (Monje Millonario)", HORARIOS_05) if html else None

def obtener_guacharito():
    html = fetch("https://loteriadehoy.com/animalito/elguacharitomillonario/resultados/")
    return parsear_generico(html, "El Guacharito Millonario", HORARIOS_30) if html else None

def obtener_lottoactivoint():
    html = fetch("https://loteriadehoy.com/animalito/lottoactivordint/resultados/")
    return parsear_generico(html, "Lotto Activo Rd Int", HORARIOS_30) if html else None

def obtener_centenaplus():
    html = fetch("https://loteriadehoy.com/animalito/centenaplus/resultados/")
    return parsear_generico(html, "Centena Plus", HORARIOS_15) if html else None

def obtener_guacharo():
    html = fetch("https://loteriadehoy.com/animalito/guacharoactivo/resultados/")
    return parsear_generico(html, "Guacharo Activo", HORARIOS_00) if html else None

# ==============================================================================
# PROCESADORES
# ==============================================================================

DELAY_CENTENA = 300  # 5 min

def procesar_inmediato(key, r, nombre, emoji):
    print(f"[PROC] {nombre}")
    if not r:
        print(f"[PROC] {nombre}: SIN DATOS")
        return False
    raw = r["raw"]
    hora = r["hora"]
    print(f"[PROC] {nombre}: scrap={raw} @ {hora}")
    if es_nuevo(key, raw):
        print(f"[PROC] {nombre}: ES NUEVO -> enviando")
        agregar_historial(key, hora, raw)
        msg = f"🔔 *RESULTADO RECIENTE* 🔔\n\n{emoji} *{nombre}* ({hora}):\n`{raw}`\n\n🍀 *@resultadoslafija* 🍀"
        enviar(msg)
        return True
    else:
        print(f"[PROC] {nombre}: sin cambios (ultimo={store.get(key,'')})")
    return False

def procesar_centenaplus(r):
    print("[PROC] Centena Plus")
    if not r:
        print("[PROC] Centena Plus: SIN DATOS")
        return False
    raw = r["raw"]
    hora = r["hora"]
    print(f"[PROC] Centena Plus: scrap={raw} @ {hora}")
    
    if store.get("centenaplus") == raw:
        print("[PROC] Centena Plus: ya publicado")
        return False
    
    pendiente_raw = store.get("centenaplus_pendiente_raw", "")
    pendiente_time = store.get("centenaplus_pendiente_time", 0)
    
    if pendiente_raw != raw:
        store["centenaplus_pendiente_raw"] = raw
        store["centenaplus_pendiente_time"] = time.time()
        guardar_store(store)
        print(f"[PROC] Centena Plus: NUEVO - esperando {DELAY_CENTENA}s...")
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
        print(f"[PROC] Centena Plus: faltan {int(restante)}s")
    return False

# ==============================================================================
# RESUMEN DIARIO
# ==============================================================================

NOMBRES = {
    "selva": "Selva Plus", "granjita": "La Granjita",
    "lottoactivo": "Lotto Activo", "lottoactivord": "Lotto Activo RD",
    "lottoactivo2": "Lotto Activo 2 (Monje Millonario)",
    "lottoactivoint": "Lotto Activo Internacional",
    "guacharito": "Guacharito Millonario", "guacharo": "Guacharo Activo",
    "centenaplus": "Centena Plus"
}

EMOJIS = {
    "selva": "🌴", "granjita": "🐔", "lottoactivo": "🎯",
    "lottoactivord": "🇩🇴", "lottoactivo2": "🧙", "lottoactivoint": "🌍",
    "guacharito": "🎰", "guacharo": "🐦", "centenaplus": "💯"
}

def enviar_resumen_diario():
    if store.get("resumen_enviado"):
        print("[RESUMEN] Ya enviado hoy")
        return
    fecha_str = datetime.now().strftime("%d/%m/%Y")
    msg = f"📋 *RESUMEN DEL DIA* 📋\n📅 {fecha_str}\n\n"
    for key in ["selva", "granjita", "lottoactivo", "lottoactivord",
                "lottoactivo2", "lottoactivoint", "guacharito", "guacharo", "centenaplus"]:
        datos = store.get("historial_hoy", {}).get(key, [])
        nombre = NOMBRES.get(key, key)
        emoji = EMOJIS.get(key, "🎲")
        msg += f"{emoji} *{nombre}*\n"
        if datos:
            for item in datos:
                msg += f"{item['hora']}: `{item['raw']}`\n"
        else:
            msg += "Sin resultados\n"
        msg += "\n"
    msg += "🍀 *@resultadoslafija* 🍀"
    if enviar(msg):
        store["resumen_enviado"] = True
        guardar_store(store)
        print("[OK] Resumen enviado")

def debe_enviar_resumen():
    ahora = datetime.now()
    return ahora.hour >= 20 and ahora.minute >= 35

# ==============================================================================
# MONITOREO
# ==============================================================================

def ciclo():
    print(f"\n{'='*60}")
    print(f"[CICLO] Escaneando {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    procesar_inmediato("selva", obtener_selva(), "Selva Plus", "🌴")
    procesar_inmediato("granjita", obtener_granjita(), "La Granjita", "🐔")
    procesar_inmediato("lottoactivo", obtener_lottoactivo(), "Lotto Activo", "🎯")
    procesar_inmediato("lottoactivord", obtener_lottoactivord(), "Lotto Activo RD", "🇩🇴")
    procesar_inmediato("guacharo", obtener_guacharo(), "Guacharo Activo", "🐦")
    procesar_inmediato("lottoactivo2", obtener_lottoactivo2(), "Lotto Activo 2 (Monje Millonario)", "🧙")
    
    r = obtener_centenaplus()
    if r:
        procesar_centenaplus(r)
    
    procesar_inmediato("guacharito", obtener_guacharito(), "Guacharito Millonario", "🎰")
    procesar_inmediato("lottoactivoint", obtener_lottoactivoint(), "Lotto Activo Internacional", "🌍")
    
    if debe_enviar_resumen():
        enviar_resumen_diario()
    
    print("[CICLO] Fin del escaneo")

def bucle_bot():
    print("[BOOT] Iniciando bucle de monitoreo en 3 segundos...")
    time.sleep(3)
    ciclo()
    print("[BOOT] Primera corrida completada. Entrando en loop cada 90s...")
    while True:
        time.sleep(90)
        try:
            ciclo()
        except Exception as e:
            print(f"[ERROR] En ciclo: {e}")

# ==============================================================================
# FLASK (Servidor HTTP para Render)
# ==============================================================================

app = Flask(__name__)

@app.route('/')
def health():
    return "OK - Bot activo", 200

@app.route('/favicon.ico')
def favicon():
    return "", 204

# ==============================================================================
# ARRANQUE
# ==============================================================================

if __name__ == "__main__":
    print("[BOOT] Iniciando Flask + Bot...")
    
    # El bot corre en un thread separado
    t = threading.Thread(target=bucle_bot, name="BotMonitoreo")
    t.daemon = True
    t.start()
    
    print(f"[BOOT] Flask iniciando en puerto {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
