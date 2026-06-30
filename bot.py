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

# ==============================================================================
# 1. TRUCO DEL PUERTO (OBLIGATORIO PARA QUE RENDER Siga EN "LIVE" Y NO CANCELE)
# ==============================================================================
def iniciar_servidor_falso():
    handler = http.server.SimpleHTTPRequestHandler
    puerto = int(os.environ.get("PORT", 8080))
    print(f"📡 Abriendo puerto falso {puerto} para cumplir requisitos de Render...")
    with socketserver.TCPServer(("", puerto), handler) as httpd:
        httpd.serve_forever()

# Se ejecuta en paralelo para que el bot pueda correr abajo sin interrupciones
threading.Thread(target=iniciar_servidor_falso, daemon=True).start()

# ==============================================================================
# 2. CONFIGURACIÓN GENERAL DEL BOT Y CREDENCIALES
# ==============================================================================
TOKEN = "8802621773:AAGxMumGC1MWQXo4-M2L-DMimIlyBpX36Qw"
CANAL_ID = "@resultadoslafija" 

bot = telebot.TeleBot(TOKEN)
scraper = cloudscraper.create_scraper() # Bypass automático para Cloudflare

URL_GUACHARITO = "https://elguacharitomillonario.com/resultados"
URL_SEGUNDA_LOTERIA = "https://www.guacharoactivo.com.ve/resultados"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Forzamos un estado inicial de prueba para que al arrancar envíe lo que encuentre
ULTIMO_GUACHARITO = "INICIO_VACIO"
ULTIMO_SEGUNDA = "INICIO_VACIO"

# ==============================================================================
# 3. SCRAPERS OPTIMIZADOS (ROBUSTOS FRENTE A CAMBIOS DE DISEÑO)
# ==============================================================================

def obtener_resultado_guacharito():
    try:
        response = scraper.get(URL_GUACHARITO, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"❌ Guacharito dio error de red: Status {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        tarjetas = soup.find_all("div")
        ultimo_sorteo = None
        
        for tarjeta in tarjetas:
            texto = tarjeta.get_text()
            # Filtro inteligente: caja que contiene formato de hora y números
            if ('AM' in texto or 'PM' in texto) and any(char.isdigit() for char in texto):
                div_numero = tarjeta.find(class_=lambda x: x and 'text-' in x and ('2xl' in x or '3xl' in x or 'black' in x))
                if div_numero:
                    numero = div_numero.get_text(strip=True)
                    animal = texto.replace(numero, "").replace("AM", "").replace("PM", "").strip()
                    
                    # Extraer hora aproximada limpia
                    hora = "Sorteo"
                    for h in ["09:", "10:", "11:", "12:", "01:", "02:", "03:", "04:", "05:", "06:", "07:"]:
                        if h in texto: 
                            pos = texto.find(h)
                            hora = texto[pos:pos+8].strip()
                    
                    if numero == "00": numero = "100"
                    if len(numero) <= 3 and len(animal) < 20:
                        ultimo_sorteo = {"hora": hora, "res": f"{numero} {animal.capitalize()}"}
                        
        if not ultimo_sorteo:
            print("⚠️ Guacharito connected pero no parseó estructuras div estándar.")
        return ultimo_sorteo
    except Exception as e:
        print(f"❌ Error crítico Scraper Guacharito: {e}")
        return None

def obtener_resultado_segunda_loteria():
    try:
        response = scraper.get(URL_SEGUNDA_LOTERIA, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"❌ Guácharo Activo dio error de red: Status {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        tarjetas = soup.find_all("div", class_=lambda x: x and ('rounded' in x or 'border' in x))
        
        ultimo_sorteo = None
        for tarjeta in tarjetas:
            texto = tarjeta.get_text()
            if ('AM' in texto or 'PM' in texto) and any(char.isdigit() for char in texto):
                div_num = tarjeta.find(class_=lambda x: x and 'text-3xl' in x)
                div_animal = tarjeta.find(class_=lambda x: x and 'text-xl' in x)
                
                if div_num and div_animal:
                    numero = div_num.get_text(strip=True)
                    animal = div_animal.get_text(strip=True).capitalize()
                    
                    if numero == "00": numero = "100"
                    if numero != "--" and "espera" not in animal.lower():
                        ultimo_sorteo = {"hora": "Sorteo", "res": f"{numero} {animal}"}
                        
        if not ultimo_sorteo:
            print("⚠️ Guácharo Activo connected pero el árbol HTML cambió.")
        return ultimo_sorteo
    except Exception as e:
        print(f"❌ Error crítico Scraper Guácharo: {e}")
        return None

# ==============================================================================
# 4. MONITOR DE VERIFICACIÓN Y PUBLICACIÓN AUTOMÁTICA
# ==============================================================================

def revisar_y_publicar():
    global ULTIMO_GUACHARITO, ULTIMO_SEGUNDA
    print(f"[{time.strftime('%H:%M:%S')}] Escaneando actualizaciones en las webs...")
    
    # Comprobación Guacharito
    res_g = obtener_resultado_guacharito()
    if res_g and res_g['res'] != ULTIMO_GUACHARITO:
        print(f"🔥 ¡Nuevo resultado Guacharito detectado!: {res_g['res']}")
        ULTIMO_GUACHARITO = res_g['res']
        mensaje = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guacharito Millonario* ({res_g['hora']}): `{res_g['res']}`\n\n🍀 *@resultadoslafija* 🍀"
        try: 
            bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown")
            print("✅ Mensaje enviado a Telegram (Guacharito).")
        except Exception as e:
            print(f"❌ Error enviando a Telegram: {e}")

    # Comprobación Guácharo Activo
    res_s = obtener_resultado_segunda_loteria()
    if res_s and res_s['res'] != ULTIMO_SEGUNDA:
        print(f"🔥 ¡Nuevo resultado Guácharo detectado!: {res_s['res']}")
        ULTIMO_SEGUNDA = res_s['res']
        mensaje = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guácharo Activo*:\n`{res_s['res']}`\n\n🍀 *@resultadoslafija* 🍀"
        try: 
            bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown")
            print("✅ Mensaje enviado a Telegram (Guácharo).")
        except Exception as e:
            print(f"❌ Error enviando a Telegram: {e}")

# ==============================================================================
# 5. BUCLE DE OPERACIÓN CONTINUA (PLANIFICADOR)
# ==============================================================================
print("🤖 Iniciando Super-Bot Inteligente...")

# Ejecución inicial forzada inmediata para testear raspado al arrancar
revisar_y_publicar()

# Programamos el escaneo recurrente cada 2 minutos
schedule.every(2).minutes.do(revisar_y_publicar)

print("⏱️ Monitoreo en segundo plano activado correctamente.")

while True:
    try:
        schedule.run_pending()
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ Alerta en el bucle principal: {e}")
        time.sleep(10)
