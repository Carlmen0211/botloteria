import telebot
import schedule
import time
import requests
from bs4 import BeautifulSoup
import cloudscraper
import threading
import http.server
import socketserver
import os

# ==========================================
# SERVIDOR WEB FALSO PARA RENDER
# ==========================================
def servidor_falso():
    handler = http.server.SimpleHTTPRequestHandler
    puerto = int(os.environ.get("PORT", 8080))
    with socketserver.TCPServer(("", puerto), handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=servidor_falso, daemon=True).start()

# ==========================================
# CONFIGURACIÓN
# ==========================================
TOKEN = "8802621773:AAGxMumGC1MWQXo4-M2L-DMimIlyBpX36Qw"
CANAL_ID = "@resultadoslafija" 

bot = telebot.TeleBot(TOKEN)
scraper = cloudscraper.create_scraper() # Cliente especial antibloqueos

URL_GUACHARITO = "https://elguacharitomillonario.com/resultados"
URL_SEGUNDA_LOTERIA = "https://www.guacharoactivo.com.ve/resultados"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

ULTIMO_GUACHARITO = ""
ULTIMO_SEGUNDA = ""

# ==========================================
# SCRAPERS CON PROTECCIÓN EVASIVA
# ==========================================

def obtener_resultado_guacharito():
    try:
        response = scraper.get(URL_GUACHARITO, headers=HEADERS, timeout=15)
        print(f"--- AUDITORÍA GUACHARITO (Status: {response.status_code}) ---")
        
        if response.status_code != 200: 
            print(response.text[:300]) # Muestra el error en Logs
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        tarjetas = soup.find_all("div", class_=lambda x: x and 'p-6' in x)
        
        ultimo_sorteo = None
        for tarjeta in tarjetas:
            div_hora = tarjeta.find(text=lambda t: 'M' in t if t else False)
            div_numero = tarjeta.find("div", class_=lambda x: x and 'text-2xl' in x)
            h3_animal = tarjeta.find(["h3", "div"], class_=lambda x: x and 'text-xl' in x)
            
            if div_numero and h3_animal:
                numero = div_numero.get_text(strip=True)
                animal = h3_animal.get_text(strip=True).capitalize()
                hora = div_hora.strip() if div_hora else "Sorteo"
                if numero == "00": numero = "100"
                if len(numero) <= 3:
                    ultimo_sorteo = {"hora": hora, "res": f"{numero} {animal}"}
        return ultimo_sorteo
    except Exception as e:
        print(f"❌ Error Scraper Guacharito: {e}")
        return None

def obtener_resultado_segunda_loteria():
    try:
        response = scraper.get(URL_SEGUNDA_LOTERIA, headers=HEADERS, timeout=15)
        print(f"--- AUDITORÍA GUÁCHARO (Status: {response.status_code}) ---")
        
        if response.status_code != 200:
            print(response.text[:300])
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        tarjetas = soup.find_all("div", class_=lambda x: x and 'rounded-3xl' in x)
        
        ultimo_sorteo = None
        for tarjeta in tarjetas:
            div_hora = tarjeta.find("div", class_=lambda x: x and 'text-lg' in x)
            div_num = tarjeta.find("div", class_=lambda x: x and 'text-3xl' in x)
            div_animal = tarjeta.find("div", class_=lambda x: x and 'text-xl' in x)
            
            if div_num and div_animal:
                numero = div_num.get_text(strip=True)
                animal = div_animal.get_text(strip=True).capitalize()
                hora = div_hora.get_text(strip=True) if div_hora else "Sorteo"
                
                if numero == "--" or "espera" in animal.lower():
                    continue
                if numero == "00": numero = "100"
                ultimo_sorteo = {"hora": hora, "res": f"{numero} {animal}"}
        return ultimo_sorteo
    except Exception as e:
        print(f"❌ Error Scraper Segunda Lotería: {e}")
        return None

# ==========================================
# PROCESOS DE TELEGRAM
# ==========================================

def revisar_y_publicar():
    global ULTIMO_GUACHARITO, ULTIMO_SEGUNDA
    print(f"[{time.strftime('%H:%M:%S')}] Escaneando actualizaciones...")
    
    res_g = obtener_resultado_guacharito()
    if res_g and res_g['res'] != ULTIMO_GUACHARITO:
        ULTIMO_GUACHARITO = res_g['res']
        mensaje = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guacharito Millonario* ({res_g['hora']}): `{res_g['res']}`\n\n🍀 *@resultadoslafija* 🍀"
        try: bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown")
        except: pass

    res_s = obtener_resultado_segunda_loteria()
    if res_s and res_s['res'] != ULTIMO_SEGUNDA:
        ULTIMO_SEGUNDA = res_s['res']
        mensaje = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guácharo Activo* ({res_s['hora']}): `{res_s['res']}`\n\n🍀 *@resultadoslafija* 🍀"
        try: bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown")
        except: pass

def generar_resumen_diario():
    print(f"[{time.strftime('%H:%M:%S')}] Generando recuento diario...")
    fecha_hoy = time.strftime("%d/%m/%Y")
    mensaje = f"🗓️ *BOT CONTROL INICIADO* ({fecha_hoy}) 🗓️\n\nEjecutando escaneo en la nube sin bloqueos locales.\n\n🎯 *@resultadoslafija*"
    try: bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown")
    except: pass

# ==========================================
# BUCLE PRINCIPAL
# ==========================================
print("🤖 Iniciando Super-Bot Inteligente...")
generar_resumen_diario()
revisar_y_publicar()

schedule.every(2).minutes.do(revisar_y_publicar)

while True:
    try:
        schedule.run_pending()
        time.sleep(1)
    except Exception as e:
        time.sleep(10)
