import os
import time
import json
import threading
import http.server
import socketserver
import re

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
            "guacharito": "",
            "guacharo": "",
            "centenaplus": "",
            "centenaplus_pendiente_raw": "",
            "centenaplus_pendiente_time": 0
        }

def guardar_store(data):
    with open(ARCHIVO_STORE, "w") as f:
        json.dump(data, f)

store = cargar_store()

def es_nuevo(key, val):
    if store.get(key) == val:
        return False
    store[key] = val
    guardar_store(store)
    return True

def reset_store():
    global store
    store = {
        "guacharito": "",
        "guacharo": "",
        "centenaplus": "",
        "centenaplus_pendiente_raw": "",
        "centenaplus_pendiente_time": 0
    }
    guardar_store(store)
    print("[INFO] Store reseteado. Proximo escaneo enviara todo.")

# ==============================================================================
# TELEGRAM BOT
# ==============================================================================

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown") if TOKEN else None

@bot.message_handler(commands=['reset'])
def cmd_reset(message):
    reset_store()
    bot.reply_to(message, "✅ Store reseteado. El proximo escaneo enviara los resultados actuales.")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    msg = (
        f"📊 *Estado del Bot*\n\n"
        f"Guacharito ultimo: `{store.get('guacharito','(vacío)')}`\n"
        f"Guacharo ultimo: `{store.get('guacharo','(vacío)')}`\n"
        f"Centena Plus ultimo: `{store.get('centenaplus','(vacío)')}`\n"
        f"Pendiente: `{store.get('centenaplus_pendiente_raw','(ninguno)')}`"
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

# ==============================================================================
# GUACHARITO MILLONARIO
# ==============================================================================

def parsear_guacharito(html):
    soup = BeautifulSoup(html, 'html.parser')
    resultados = []
    for h4 in soup.find_all('h4'):
        texto_h4 = h4.get_text(strip=True)
        h6 = h4.find_next('h6')
        if not h6:
            continue
        texto_h6 = h6.get_text(strip=True)
        if "guacharito millonario" not in texto_h6.lower():
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
    return parsear_guacharito(html) if html else None

# ==============================================================================
# GUACHARO ACTIVO
# ==============================================================================

def parsear_guacharo(html):
    soup = BeautifulSoup(html, 'html.parser')
    resultados = []
    for h4 in soup.find_all('h4'):
        texto_h4 = h4.get_text(strip=True)
        h6 = h4.find_next('h6')
        if not h6:
            continue
        texto_h6 = h6.get_text(strip=True)
        if "guacharo activo" not in texto_h6.lower():
            continue
        partes = texto_h4.split(None, 1)
        if len(partes) < 2:
            continue
        numero, animal = partes[0], partes[1]
        hora = ""
        for h in ["08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", 
                  "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM",
                  "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM"]:
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

def obtener_guacharo():
    html = fetch("https://loteriadehoy.com/animalito/guacharoactivo/resultados/")
    return parsear_guacharo(html) if html else None

# ==============================================================================
# CENTENA PLUS
# ==============================================================================

HORARIOS_CENTENA = [
    "08:15 AM", "09:15 AM", "10:15 AM", "11:15 AM", 
    "12:15 PM", "01:15 PM", "02:15 PM", "03:15 PM",
    "04:15 PM", "05:15 PM", "06:15 PM", "07:15 PM", "08:15 PM"
]

def parsear_centenaplus_oficial(html):
    """Parsea centenaplus.com/plus - busca patrones como '8:15AM · 86 Piojo'"""
    soup = BeautifulSoup(html, 'html.parser')
    texto = soup.get_text(separator=' ', strip=True)
    
    resultados = []
    # Patrones: 8:15AM, 8:15 AM, 08:15AM, 08:15 AM seguido de · o espacio y numero+animal
    patron = re.compile(
        r'(\d{1,2}):(\d{2})\s*(AM|PM)\s*[·\-\s]\s*(\d{1,2})\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\s]+?)(?=\s+\d{1,2}:\d{2}\s*(?:AM|PM)|$)',
        re.IGNORECASE
    )
    
    for match in patron.finditer(texto):
        hora_raw = f"{match.group(1)}:{match.group(2)} {match.group(3).upper()}"
        numero = match.group(4)
        animal = match.group(5).strip()
        
        # Normalizar hora a formato HH:MM AM/PM
        try:
            h = int(match.group(1))
            if match.group(3).upper() == "PM" and h != 12:
                h += 12
            elif match.group(3).upper() == "AM" and h == 12:
                h = 0
            hora_norm = f"{h:02d}:{match.group(2)} {match.group(3).upper()}"
        except:
            hora_norm = hora_raw
        
        resultados.append({
            "hora": hora_norm,
            "numero": numero,
            "animal": animal.capitalize(),
            "raw": f"{numero} {animal.capitalize()}"
        })
    
    # Si no encontró con regex, intentar buscar divs/headings
    if not resultados:
        for elem in soup.find_all(['h2', 'h3', 'h4', 'div', 'span']):
            txt = elem.get_text(strip=True)
            for h in HORARIOS_CENTENA:
                if h.replace(" ", "").lower() in txt.lower().replace(" ", "") or h in txt:
                    # Buscar numero y animal cercano
                    num_match = re.search(r'\b(\d{1,2})\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\s]+)', txt)
                    if num_match:
                        resultados.append({
                            "hora": h,
                            "numero": num_match.group(1),
                            "animal": num_match.group(2).strip().capitalize(),
                            "raw": f"{num_match.group(1)} {num_match.group(2).strip().capitalize()}"
                        })
                        break
    
    return resultados[-1] if resultados else None

def parsear_centenaplus_loteriadehoy(html):
    """Parsea loteriadehoy.com/animalito/centenaplus/resultados/"""
    soup = BeautifulSoup(html, 'html.parser')
    resultados = []
    for h4 in soup.find_all('h4'):
        texto_h4 = h4.get_text(strip=True)
        h6 = h4.find_next('h6')
        if not h6:
            continue
        texto_h6 = h6.get_text(strip=True)
        if "centena plus" not in texto_h6.lower():
            continue
        partes = texto_h4.split(None, 1)
        if len(partes) < 2:
            continue
        numero, animal = partes[0], partes[1]
        hora = ""
        for h in HORARIOS_CENTENA:
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

def obtener_centenaplus():
    # Fuente 1: Oficial
    html1 = fetch("https://centenaplus.com/plus")
    if html1:
        r = parsear_centenaplus_oficial(html1)
        if r:
            print(f"[INFO] Centena Plus desde OFICIAL: {r['raw']}")
            return r
    
    # Fuente 2: Respaldo
    html2 = fetch("https://loteriadehoy.com/animalito/centenaplus/resultados/")
    if html2:
        r = parsear_centenaplus_loteriadehoy(html2)
        if r:
            print(f"[INFO] Centena Plus desde RESPALDO: {r['raw']}")
            return r
    
    print("[WARN] Centena Plus: todas las fuentes fallaron")
    return None

# ==============================================================================
# DELAY CENTENA PLUS (5 minutos = 300 segundos)
# ==============================================================================

DELAY_CENTENA = 300  # 5 minutos

def procesar_centenaplus(r):
    """
    Logica de delay para Centena Plus:
    - Si es un resultado nuevo, lo guarda como PENDIENTE con timestamp
    - Si ya hay un pendiente y han pasado 5 min, lo publica
    - Si el resultado cambio, reinicia el pendiente
    """
    raw = r["raw"]
    hora = r["hora"]
    
    # Si ya fue publicado, ignorar
    if store.get("centenaplus") == raw:
        print(f"[INFO] Centena Plus: sin cambios (ya publicado: {raw})")
        return
    
    pendiente_raw = store.get("centenaplus_pendiente_raw", "")
    pendiente_time = store.get("centenaplus_pendiente_time", 0)
    
    # Si el resultado cambio, reiniciar pendiente
    if pendiente_raw != raw:
        store["centenaplus_pendiente_raw"] = raw
        store["centenaplus_pendiente_time"] = time.time()
        guardar_store(store)
        print(f"[INFO] Centena Plus: NUEVO detectado ({raw}) - esperando {DELAY_CENTENA}s...")
        return
    
    # Si es el mismo pendiente, verificar si ya paso el delay
    tiempo_transcurrido = time.time() - pendiente_time
    if tiempo_transcurrido >= DELAY_CENTENA:
        # Publicar!
        store["centenaplus"] = raw
        store["centenaplus_pendiente_raw"] = ""
        store["centenaplus_pendiente_time"] = 0
        guardar_store(store)
        
        msg = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Centena Plus* ({hora}):\n`{raw}`\n\n🍀 *@resultadoslafija* 🍀"
        enviar(msg)
        print(f"[OK] Centena Plus PUBLICADO tras {int(tiempo_transcurrido)}s de delay")
    else:
        restante = DELAY_CENTENA - tiempo_transcurrido
        print(f"[INFO] Centena Plus: pendiente ({raw}) - faltan {int(restante)}s para publicar")

# ==============================================================================
# MONITOREO PRINCIPAL
# ==============================================================================

def ciclo():
    print("[INFO] === Escaneando resultados ===")
    
    # --- Guacharito Millonario (inmediato) ---
    r = obtener_guacharito()
    print(f"[INFO] Guacharito scrap: {r}")
    if r and es_nuevo("guacharito", r["raw"]):
        msg = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guacharito Millonario* ({r['hora']}):\n`{r['raw']}`\n\n🍀 *@resultadoslafija* 🍀"
        enviar(msg)
    else:
        print(f"[INFO] Guacharito: sin cambios (ultimo={store.get('guacharito','')})")
    
    # --- Guacharo Activo (inmediato) ---
    r = obtener_guacharo()
    print(f"[INFO] Guacharo scrap: {r}")
    if r and es_nuevo("guacharo", r["raw"]):
        msg = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guácharo Activo* ({r['hora']}):\n`{r['raw']}`\n\n🍀 *@resultadoslafija* 🍀"
        enviar(msg)
    else:
        print(f"[INFO] Guacharo: sin cambios (ultimo={store.get('guacharo','')})")
    
    # --- Centena Plus (con delay de 5 min) ---
    r = obtener_centenaplus()
    print(f"[INFO] Centena Plus scrap: {r}")
    if r:
        procesar_centenaplus(r)
    else:
        print("[INFO] Centena Plus: sin datos")

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
