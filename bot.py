import telebot
import schedule
import time
import requests
from bs4 import BeautifulSoup

# ==========================================
# CONFIGURACIÓN DE CREDENCIALES Y LINKS
# ==========================================
TOKEN = "8802621773:AAGxMumGC1MWQXo4-M2L-DMimIlyBpX36Qw"
CANAL_ID = "@resultadoslafija" 

bot = telebot.TeleBot(TOKEN)

# Enlaces de las páginas de resultados
URL_GUACHARITO = "https://elguacharitomillonario.com/resultados"
URL_SEGUNDA_LOTERIA = "https://www.guacharoactivo.com.ve/resultados" # ⚠️ REEMPLAZAR POR EL LINK REAL

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Memoria interna para evitar que se repita el mismo resultado en el canal
ULTIMO_GUACHARITO = ""
ULTIMO_SEGUNDA = ""

# ==========================================
# FUNCIONES DE WEB SCRAPING
# ==========================================

def obtener_resultado_guacharito():
    """ Extrae el último resultado disponible de El Guacharito Millonario """
    try:
        response = requests.get(URL_GUACHARITO, headers=HEADERS, timeout=15)
        if response.status_code != 200: return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        tarjetas = soup.find_all("div", class_="relative z-10 flex h-full flex-col items-center justify-between p-6")
        
        ultimo_sorteo = None
        for tarjeta in tarjetas:
            div_hora = tarjeta.find("div", class_="inline-flex items-center gap-2 self-start rounded-full")
            div_numero = tarjeta.find("div", class_="text-2xl font-black bg-gradient-to-r")
            h3_animal = tarjeta.find("h3", class_="text-xl font-bold uppercase text-white")
            
            if div_hora and div_numero and h3_animal:
                numero = div_numero.get_text(strip=True)
                animal = h3_animal.get_text(strip=True).capitalize()
                if numero == "00": numero = "100"
                ultimo_sorteo = {"hora": div_hora.get_text(strip=True), "res": f"{numero} {animal}"}
        return ultimo_sorteo
    except Exception as e:
        print(f"❌ Error Scraper Guacharito: {e}")
        return None

def obtener_resultado_segunda_loteria():
    """ Extrae el último resultado de la estructura HTML estilo Naranja/Cristal """
    if "URL_DE_LA_OTRA_LOTERIA" in URL_SEGUNDA_LOTERIA:
        print("⚠️ Alerta: Falta configurar la URL real de la segunda lotería.")
        return None
        
    try:
        response = requests.get(URL_SEGUNDA_LOTERIA, headers=HEADERS, timeout=15)
        if response.status_code != 200: return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        tarjetas = soup.find_all("div", class_=["group relative h-full overflow-hidden rounded-3xl border border-white/20 bg-gradient-to-br from-white/15 to-white/5 shadow-[0_8px_32px_rgba(0,0,0,0.12)] backdrop-blur-xl transition-all duration-500 hover:border-orange-500/40 hover:shadow-[0_16px_48px_rgba(234,88,12,0.15)]  ", "group relative h-full overflow-hidden rounded-3xl border border-white/20 bg-gradient-to-br from-white/15 to-white/5 shadow-[0_8px_32px_rgba(0,0,0,0.12)] backdrop-blur-xl transition-all duration-500 hover:border-orange-500/40 hover:shadow-[0_16px_48px_rgba(234,88,12,0.15)] ring-2 ring-orange-400/50 "])
        
        ultimo_sorteo = None
        for tarjeta in tarjetas:
            div_hora = tarjeta.find("div", class_="bg-gradient-to-r from-orange-400 to-red-500 bg-clip-text text-lg font-semibold text-transparent")
            div_textos = tarjeta.find("div", class_="text-center")
            if not div_textos: continue
            
            div_num = div_textos.find("div", class_="bg-gradient-to-br from-white via-white to-white/60 bg-clip-text text-3xl font-bold text-transparent md:text-4xl")
            div_animal = div_textos.find("div", class_="mt-1 text-xl font-bold text-white md:text-2xl")
            
            if div_hora and div_num and div_animal:
                numero = div_num.get_text(strip=True)
                animal = div_animal.get_text(strip=True).capitalize()
                
                if numero == "--" or "espera" in animal.lower():
                    continue
                    
                if numero == "00": numero = "100"
                ultimo_sorteo = {"hora": div_hora.get_text(strip=True), "res": f"{numero} {animal}"}
        return ultimo_sorteo
    except Exception as e:
        print(f"❌ Error Scraper Segunda Lotería: {e}")
        return None

# ==========================================
# GESTIÓN DE VERIFICACIÓN HORARIA
# ==========================================

def revisar_y_publicar():
    """ Compara los datos actuales con la memoria y publica solo si hay algo nuevo """
    global ULTIMO_GUACHARITO, ULTIMO_SEGUNDA
    print(f"[{time.strftime('%H:%M:%S')}] Escaneando actualizaciones en las páginas...")
    
    # 1. Monitoreo Guacharito
    res_g = obtener_resultado_guacharito()
    if res_g and res_g['res'] != ULTIMO_GUACHARITO:
        ULTIMO_GUACHARITO = res_g['res']
        mensaje = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Guacharito Millonario* ({res_g['hora']}): `{res_g['res']}`\n\n🍀 *@resultadoslafija* 🍀"
        
        for intento in range(1, 4):
            try:
                bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown", timeout=20)
                print(f"✅ Nuevo resultado Guacharito enviado: {res_g['res']}")
                break
            except Exception as e:
                print(f"⚠️ Error enviando Guacharito (Intento {intento}/3)...")
                if intento == 3: print(f"❌ Falla de red en Guacharito: {e}")
                time.sleep(10)

    # 2. Monitoreo Segunda Lotería
    res_s = obtener_resultado_segunda_loteria()
    if res_s and res_s['res'] != ULTIMO_SEGUNDA:
        ULTIMO_SEGUNDA = res_s['res']
        mensaje = f"🔔 *RESULTADO RECIENTE* 🔔\n\n🎰 *Nueva Lotería* ({res_s['hora']}): `{res_s['res']}`\n\n🍀 *@resultadoslafija* 🍀"
        
        for intento in range(1, 4):
            try:
                bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown", timeout=20)
                print(f"✅ Nuevo resultado Segunda Lotería enviado: {res_s['res']}")
                break
            except Exception as e:
                print(f"⚠️ Error enviando Segunda Lotería (Intento {intento}/3)...")
                if intento == 3: print(f"❌ Falla de red en Nueva Lotería: {e}")
                time.sleep(10)

# ==========================================
# GENERADOR DEL RECUENTO / RESUMEN DIARIO
# ==========================================

def generar_resumen_diario():
    """ Raspa de golpe todo lo que lleva el día y publica la cartelera completa """
    print(f"[{time.strftime('%H:%M:%S')}] Generando recuento diario acumulado...")
    resumen_g, resumen_s = [], []
    
    # Recuento Guacharito
    try:
        soup = BeautifulSoup(requests.get(URL_GUACHARITO, headers=HEADERS, timeout=15).text, 'html.parser')
        tarjetas = soup.find_all("div", class_="relative z-10 flex h-full flex-col items-center justify-between p-6")
        for t in tarjetas:
            div_h = t.find("div", class_="inline-flex items-center gap-2 self-start rounded-full")
            div_n = t.find("div", class_="text-2xl font-black bg-gradient-to-r")
            div_a = t.find("h3", class_="text-xl font-bold uppercase text-white")
            if div_h and div_n and div_a:
                n = div_n.get_text(strip=True)
                if n == "00": n = "100"
                resumen_g.append(f"• {div_h.get_text(strip=True)} -> *{n} {div_a.get_text(strip=True).capitalize()}*")
    except: 
        pass

    # Recuento Segunda Lotería
    try:
        soup = BeautifulSoup(requests.get(URL_SEGUNDA_LOTERIA, headers=HEADERS, timeout=15).text, 'html.parser')
        tarjetas = soup.find_all("div", class_=["group relative h-full overflow-hidden rounded-3xl border border-white/20 bg-gradient-to-br from-white/15 to-white/5 shadow-[0_8px_32px_rgba(0,0,0,0.12)] backdrop-blur-xl transition-all duration-500 hover:border-orange-500/40 hover:shadow-[0_16px_48px_rgba(234,88,12,0.15)]  ", "group relative h-full overflow-hidden rounded-3xl border border-white/20 bg-gradient-to-br from-white/15 to-white/5 shadow-[0_8px_32px_rgba(0,0,0,0.12)] backdrop-blur-xl transition-all duration-500 hover:border-orange-500/40 hover:shadow-[0_16px_48px_rgba(234,88,12,0.15)] ring-2 ring-orange-400/50 "])
        for t in tarjetas:
            div_h = t.find("div", class_="bg-gradient-to-r from-orange-400 to-red-500 bg-clip-text text-lg font-semibold text-transparent")
            dt = t.find("div", class_="text-center")
            if div_h and dt:
                div_n = dt.find("div", class_="bg-gradient-to-br from-white via-white to-white/60 bg-clip-text text-3xl font-bold text-transparent md:text-4xl")
                div_a = dt.find("div", class_="mt-1 text-xl font-bold text-white md:text-2xl")
                if div_n and div_a and div_n.get_text(strip=True) != "--":
                    n = div_n.get_text(strip=True)
                    if n == "00": n = "100"
                    resumen_s.append(f"• {div_h.get_text(strip=True)} -> *{n} {div_a.get_text(strip=True).capitalize()}*")
    except: 
        pass

    # Construcción de la cartelera informativa
    fecha_hoy = time.strftime("%d/%m/%Y")
    mensaje = f"🗓️ *RECUENTO DE RESULTADOS DIARIOS* ({fecha_hoy}) 🗓️\n\n"
    mensaje += "💥 *GUACHARITO MILLONARIO:*\n" + ("\n".join(resumen_g) if resumen_g else "• No se registraron sorteos.")
    mensaje += "\n\n🔸 *SEGUNDA LOTERÍA:*\n" + ("\n".join(resumen_s) if resumen_s else "• No se registraron sorteos.")
    mensaje += "\n\n🎯 _¡Sigue los resultados en vivo!:_ *@resultadoslafija*"

    # Sistema inteligente de reintentos con pausa contra caídas de internet
    for intento in range(1, 4):
        try:
            bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown", timeout=20)
            print("✅ Cartelera de recuento diario enviada con éxito.")
            break
        except Exception as e:
            print(f"⚠️ Intento {intento}/3 fallido por conexión lenta. Reintentando...")
            if intento == 3: print(f"❌ Error definitivo tras 3 intentos: {e}")
            time.sleep(15)

# ==========================================
# INICIALIZACIÓN Y PLANIFICACIÓN (CRON)
# ==========================================

print("🤖 Iniciando Super-Bot Inteligente...")

# Acción inmediata al encender (Lanza el recuento acumulado inicial)
generar_resumen_diario()

# Registra los sorteos del momento exacto para la memoria inicial
revisar_y_publicar()

# Programar chequeos continuos cada 2 minutos
schedule.every(2).minutes.do(revisar_y_publicar)

# Reporte consolidado automático fijo de cierre a las 7:45 PM
schedule.every().day.at("19:45").do(generar_resumen_diario)

print("⏱️ Monitoreo en tiempo real activado (Inspección cada 2 minutos).")

while True:
    try:
        schedule.run_pending()
        time.sleep(1)
    except KeyboardInterrupt:
        print("\nBot cerrado correctamente.")
        break
    except Exception as e:
        print(f"⚠️ Alerta en bucle de control: {e}")
        time.sleep(10)
