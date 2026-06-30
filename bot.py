import telebot
import schedule
import time
import requests
from bs4 import BeautifulSoup
import threading
import http.server
import socketserver
import os

# ==========================================
# SERVIDOR WEB FALSO PARA RENDER (OBLIGATORIO)
# ==========================================
def servidor_falso():
    handler = http.server.SimpleHTTPRequestHandler
    puerto = int(os.environ.get("PORT", 8080))
    with socketserver.TCPServer(("", puerto), handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=servidor_falso, daemon=True).start()

# ==========================================
# CONFIGURACIÓN DE CREDENCIALES Y LINKS
# ==========================================
TOKEN = "8802621773:AAGxMumGC1MWQXo4-M2L-DMimIlyBpX36Qw"
CANAL_ID = "@resultadoslafija" 

bot = telebot.TeleBot(TOKEN)

URL_GUACHARITO = "https://elguacharitomillonario.com/resultados"
URL_SEGUNDA_LOTERIA = "https://www.guacharoactivo.com.ve/resultados"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

ULTIMO_GUACHARITO = ""
ULTIMO_SEGUNDA = ""

# ==========================================
# FUNCIONES DE WEB SCRAPING MEJORADAS
# ==========================================

def obtener_resultado_guacharito():
    """ Extrae el último resultado disponible de El Guacharito """
    try:
        response = requests.get(URL_GUACHARITO, headers=HEADERS, timeout=15)
        if response.status_code != 200: return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Buscamos de forma más abierta: cualquier tarjeta que contenga texto de sorteo
        tarjetas = soup.find_all("div", class_=lambda x: x and 'flex' in x and 'col' in x and 'p-6' in x)
        
        ultimo_sorteo = None
        for tarjeta in tarjetas:
            # Buscamos los textos por su contenido o etiquetas comunes en vez de clases kilométricas
            div_hora = tarjeta.find(text=lambda t: 'M' in t if t else False) # Captura AM o PM
            div_numero = tarjeta.find("div", class_=lambda x: x and ('text-2xl' in x or 'font-black' in x))
            h3_animal = tarjeta.find(["h3", "div"], class_=lambda x: x and ('text-xl' in x or 'font-bold' in x))
            
            if div_numero and h3_animal:
                numero = div_numero.get_text(strip=True)
                animal = h3_animal.get_text(strip=True).capitalize()
                hora = div_hora.strip() if div_hora else "Sorteo"
                
                if numero == "00": numero = "100"
                if numero and animal and len(numero) <= 3:
                    ultimo_sorteo = {"hora": hora, "res": f"{numero} {animal}"}
        return ultimo_sorteo
    except Exception as e:
        print(f"❌ Error Scraper Guacharito: {e}")
        return None

def obtener_resultado_segunda_loteria():
    """ Extrae el último resultado de la estructura de Guácharo Activo """
    try:
        response = requests.get(URL_SEGUNDA_LOTERIA, headers=HEADERS, timeout=15)
        if response.status_code != 200: return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # En Guácharo Activo las tarjetas suelen usar clases con 'orange' o bordes redondeados
        tarjetas = soup.find_all("div", class_=lambda x: x and 'rounded-3xl' in x)
        
        ultimo_sorteo = None
        for tarjeta in tarjetas:
            div_hora = tarjeta.find("div", class_=lambda x: x and 'text-lg' in x)
            div_num = tarjeta.find("div", class_=lambda x: x and 'text-3xl' in x)
            div_animal = tarjeta.find("div", class_=lambda x: x and 'text-xl' in x and 'text-white' in x)
            
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
# GESTIÓN DE VERIFICACIÓN HORARIA
# ==========================================

def revisar_y_publicar():
    global ULTIMO_GUACHARITO, ULTIMO_SEGUNDA
    print(f"[{time.strftime('%H:%M:%S')}] Escaneando actualizaciones...")
    
    res_g = obtener_resultado_guacharito()
    if res_g and res_g['res'] != ULTIMO_GUACHARITO:
        ULTIMO_GUACHARITO = res_g['res']
        mensaje = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guacharito Millonario* ({res_g['hora']}): `{res_g['res']}`\n\n🍀 *@resultadoslafija* 🍀"
        for intento in range(1, 4):
            try:
                bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown", timeout=20)
                break
            except:
                time.sleep(5)

    res_s = obtener_resultado_segunda_loteria()
    if res_s and res_s['res'] != ULTIMO_SEGUNDA:
        ULTIMO_SEGUNDA = res_s['res']
        mensaje = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guácharo Activo* ({res_s['hora']}): `{res_s['res']}`\n\n🍀 *@resultadoslafija* 🍀"
        for intento in range(1, 4):
            try:
                bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown", timeout=20)
                break
            except:
                time.sleep(5)

# ==========================================
# GENERADOR DEL RECUENTO / RESUMEN DIARIO
# ==========================================

def generar_resumen_diario():
    print(f"[{time.strftime('%H:%M:%S')}] Generando recuento diario acumulado...")
    resumen_g, resumen_s = [], []
    
    # Recuento Guacharito
    try:
        soup = BeautifulSoup(requests.get(URL_GUACHARITO, headers=HEADERS, timeout=15).text, 'html.parser')
        tarjetas = soup.find_all("div", class_=lambda x: x and 'flex' in x and 'col' in x and 'p-6' in x)
        for t in tarjetas:
            div_h = t.find(text=lambda text: 'M' in text if text else False)
            div_n = t.find("div", class_=lambda x: x and ('text-2xl' in x or 'font-black' in x))
            div_a = t.find(["h3", "div"], class_=lambda x: x and ('text-xl' in x or 'font-bold' in x))
            if div_n and div_a:
                n = div_n.get_text(strip=True)
                if n == "00": n = "100"
                if len(n) <= 3:
                    h = div_h.strip() if div_h else "Sorteo"
                    resumen_g.append(f"• {h} -> *{n} {div_a.get_text(strip=True).capitalize()}*")
    except: pass

    # Recuento Segunda Lotería
    try:
        soup = BeautifulSoup(requests.get(URL_SEGUNDA_LOTERIA, headers=HEADERS, timeout=15).text, 'html.parser')
        tarjetas = soup.find_all("div", class_=lambda x: x and 'rounded-3xl' in x)
        for t in tarjetas:
            div_h = t.find("div", class_=lambda x: x and 'text-lg' in x)
            div_n = t.find("div", class_=lambda x: x and 'text-3xl' in x)
            div_a = t.find("div", class_=lambda x: x and 'text-xl' in x and 'text-white' in x)
            if div_n and div_a and div_n.get_text(strip=True) != "--":
                n = div_n.get_text(strip=True)
                if n == "00": n = "100"
                h = div_h.get_text(strip=True) if div_h else "Sorteo"
                resumen_s.append(f"• {h} -> *{n} {div_a.get_text(strip=True).capitalize()}*")
    except: pass

    fecha_hoy = time.strftime("%d/%m/%Y")
    mensaje = f"🗓️ *RECUENTO DE RESULTADOS DIARIOS* ({fecha_hoy}) 🗓️\n\n"
    mensaje += "💥 *GUACHARITO MILLONARIO:*\n" + ("\n".join(resumen_g) if resumen_g else "• No se registraron sorteos.")
    mensaje += "\n\n🔸 *GUÁCHARO ACTIVO:*\n" + ("\n".join(resumen_s) if resumen_s else "• No se registraron sorteos.")
    mensaje += "\n\n🎯 _¡Sigue los resultados en vivo!:_ *@resultadoslafija*"

    for intento in range(1, 4):
        try:
            bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown", timeout=20)
            print("✅ Cartelera enviada con éxito.")
            break
        except Exception as e:
            time.sleep(15)

# ==========================================
# INICIALIZACIÓN Y PLANIFICACIÓN
# ==========================================

print("🤖 Iniciando Super-Bot Inteligente...")
generar_resumen_diario()
revisar_y_publicar()

schedule.every(2).minutes.do(revisar_y_publicar)
schedule.every().day.at("19:45").do(generar_resumen_diario)

print("⏱️ Monitoreo activo en la nube.")

while True:
    try:
        schedule.run_pending()
        time.sleep(1)
    except KeyboardInterrupt:
        break
    except Exception as e:
        time.sleep(10)
