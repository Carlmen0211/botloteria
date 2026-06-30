"""
Bot de Resultados de Lotería - Versión Senior Corregida
Autor: Senior Dev
Funciona en: Render, VPS, Local
"""

import os
import sys
import time
import json
import logging
import threading
import http.server
import socketserver
from datetime import datetime
from typing import Optional, Dict, List, Tuple

import requests
from bs4 import BeautifulSoup
import cloudscraper
import telebot
from telebot.apihelper import ApiTelegramException

# ==============================================================================
# CONFIGURACIÓN PROFESIONAL (Variables de Entorno OBLIGATORIAS)
# ==============================================================================

TOKEN = os.environ.get("BOT_TOKEN", "")
CANAL_ID = os.environ.get("CANAL_ID", "@resultadoslafija")

if not TOKEN:
    print("❌ ERROR: Define la variable de entorno BOT_TOKEN")
    sys.exit(1)

# Configurar logging profesional
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# FUENTES DE DATOS (Múltiples fuentes por lotería para redundancia)
# ==============================================================================

FUENTES_GUACHARITO = [
    {
        "nombre": "LoteriaDeHoy",
        "url": "https://loteriadehoy.com/animalito/elguacharitomillonario/resultados/",
        "tipo": "html_estatico",
        "selectores": {
            "contenedor": "div.resultados-animalito",
            "hora": "span.hora-sorteo",
            "numero": "span.numero-animalito",
            "animal": "span.nombre-animalito"
        }
    },
    {
        "nombre": "Parley.la",
        "url": "https://m.parley.la/resultados/resultados-guacharito-millonario.php",
        "tipo": "html_estatico",
        "selectores": None  # Parseo especial definido abajo
    },
    {
        "nombre": "LottoVen",
        "url": "https://lotoven.com/animalito/elguacharitomillonario/resultados/",
        "tipo": "html_estatico",
        "selectores": None
    }
]

FUENTES_GUACHARO_ACTIVO = [
    {
        "nombre": "LoteriaDeHoy",
        "url": "https://loteriadehoy.com/animalito/guacharoactivo/resultados/",
        "tipo": "html_estatico",
        "selectores": {
            "contenedor": "div.resultados-animalito",
            "hora": "span.hora-sorteo",
            "numero": "span.numero-animalito",
            "animal": "span.nombre-animalito"
        }
    },
    {
        "nombre": "Parley.la",
        "url": "https://m.parley.la/resultados-guacharo-activo",
        "tipo": "html_estatico",
        "selectores": None
    },
    {
        "nombre": "CentroApuestasElRey",
        "url": "https://centrodeapuestaselrey.com.ve/resultados/guacharo",
        "tipo": "html_estatico",
        "selectores": None
    }
]

# Headers robustos para evitar bloqueos
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-VE,es;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# ==============================================================================
# PERSISTENCIA (SQLite simple para no depender de librerías externas)
# ==============================================================================

class ResultadoStore:
    """Almacena el último resultado enviado para evitar duplicados entre reinicios."""
    
    def __init__(self, archivo: str = "ultimos_resultados.json"):
        self.archivo = archivo
        self.datos = self._cargar()
    
    def _cargar(self) -> Dict:
        try:
            with open(self.archivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "guacharito": {"fingerprint": "", "timestamp": ""},
                "guacharo_activo": {"fingerprint": "", "timestamp": ""}
            }
    
    def _guardar(self):
        with open(self.archivo, 'w', encoding='utf-8') as f:
            json.dump(self.datos, f, indent=2, ensure_ascii=False)
    
    def es_nuevo(self, loteria: str, fingerprint: str) -> bool:
        """Devuelve True si el resultado es nuevo y lo guarda."""
        actual = self.datos.get(loteria, {}).get("fingerprint", "")
        if fingerprint == actual:
            return False
        self.datos[loteria] = {
            "fingerprint": fingerprint,
            "timestamp": datetime.now().isoformat()
        }
        self._guardar()
        return True
    
    def get_ultimo(self, loteria: str) -> str:
        return self.datos.get(loteria, {}).get("fingerprint", "")

store = ResultadoStore()

# ==============================================================================
# SCRAPERS ROBUSTOS (Múltiples estrategias de parseo)
# ==============================================================================

scraper = cloudscraper.create_scraper()

def fetch_html(url: str, timeout: int = 15) -> Optional[str]:
    """Obtiene HTML con reintentos y manejo de errores."""
    for intento in range(3):
        try:
            resp = scraper.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            logger.warning(f"HTTP {resp.status_code} en {url}")
        except Exception as e:
            logger.warning(f"Intento {intento+1}/3 fallido para {url}: {e}")
            time.sleep(2 ** intento)  # Backoff exponencial
    return None

def parsear_loteriadehoy(html: str, nombre_loteria: str) -> Optional[Dict]:
    """
    Parsea la estructura de loteriadehoy.com
    Busca patrones como: <h4>56 Tiburon</h4><h6>El Guacharito Millonario 08:30 AM</h6>
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Estructura observada: h4 con número+animal, h6 con nombre+hora
    resultados = []
    
    for h4 in soup.find_all('h4'):
        texto_h4 = h4.get_text(strip=True)
        # Buscar el h6 hermano o cercano
        h6 = h4.find_next('h6')
        if not h6:
            continue
            
        texto_h6 = h6.get_text(strip=True)
        
        # Verificar que sea la lotería correcta
        if nombre_loteria.lower() not in texto_h6.lower():
            continue
        
        # Extraer número y animal del h4 (ej: "56 Tiburon")
        partes = texto_h4.split(None, 1)
        if len(partes) < 2:
            continue
            
        numero, animal = partes[0], partes[1]
        
        # Extraer hora del h6 (ej: "El Guacharito Millonario 08:30 AM")
        hora_match = None
        for patron in ['08:30 AM', '09:30 AM', '10:30 AM', '11:30 AM', 
                       '12:30 PM', '01:30 PM', '02:30 PM', '03:30 PM',
                       '04:30 PM', '05:30 PM', '06:30 PM', '07:30 PM',
                       '08:00 AM', '09:00 AM', '10:00 AM', '11:00 AM',
                       '12:00 PM', '01:00 PM', '02:00 PM', '03:00 PM',
                       '04:00 PM', '05:00 PM', '06:00 PM', '07:00 PM']:
            if patron in texto_h6:
                hora_match = patron
                break
        
        if not hora_match:
            continue
            
        resultados.append({
            "hora": hora_match,
            "numero": numero,
            "animal": animal.capitalize(),
            "raw": f"{numero} {animal.capitalize()}"
        })
    
    # Devolver el ÚLTIMO sorteo del día (el más reciente)
    if resultados:
        return resultados[-1]
    return None

def parsear_parley_guacharito(html: str) -> Optional[Dict]:
    """Parsea m.parley.la/resultados-guacharito-millonario.php"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Buscar todos los headings que contengan la hora
    horarios = ['08:30 am', '09:30 am', '10:30 am', '11:30 am', '12:30 pm',
                '01:30 pm', '02:30 pm', '03:30 pm', '04:30 pm', '05:30 pm',
                '06:30 pm', '07:30 pm']
    
    for hora in reversed(horarios):  # Del más reciente al más antiguo
        # Buscar heading con la hora
        for elem in soup.find_all(text=lambda t: t and hora in t.lower()):
            parent = elem.parent
            # Buscar el resultado en un heading cercano (h2, h3, h4)
            resultado_elem = parent.find_next(['h2', 'h3', 'h4'])
            if resultado_elem:
                texto = resultado_elem.get_text(strip=True)
                # Formato esperado: "56 TIBURON"
                partes = texto.split(None, 1)
                if len(partes) == 2 and partes[0].isdigit():
                    return {
                        "hora": hora.upper(),
                        "numero": partes[0],
                        "animal": partes[1].capitalize(),
                        "raw": f"{partes[0]} {partes[1].capitalize()}"
                    }
    return None

def parsear_parley_guacharoactivo(html: str) -> Optional[Dict]:
    """Parsea m.parley.la/resultados-guacharo-activo"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # La estructura muestra: "Guacharo Activo 08:00 am · 63 CANGREJO"
    horarios = ['08:00 am', '09:00 am', '10:00 am', '11:00 am', '12:00 pm',
                '01:00 pm', '02:00 pm', '03:00 pm', '04:00 pm', '05:00 pm',
                '06:00 pm', '07:00 pm']
    
    for hora in reversed(horarios):
        for elem in soup.find_all(text=lambda t: t and f"Guacharo Activo {hora}" in t):
            # El resultado está en el mismo texto o cercano
            texto = elem.parent.get_text(strip=True)
            # Buscar patrón: número + ANIMAL en mayúsculas
            import re
            match = re.search(r'(\d+)\s+([A-ZÁÉÍÓÚÑ\s]+)', texto)
            if match:
                num = match.group(1)
                animal = match.group(2).strip().capitalize()
                return {
                    "hora": hora.upper(),
                    "numero": num,
                    "animal": animal,
                    "raw": f"{num} {animal}"
                }
    return None

def parsear_lottoven_guacharito(html: str) -> Optional[Dict]:
    """Parsea lotoven.com - estructura similar a loteriadehoy"""
    return parsear_loteriadehoy(html, "Guacharito Millonario")

def parsear_centroapuestas_guacharo(html: str) -> Optional[Dict]:
    """Parsea centrodeapuestaselrey.com.ve/resultados/guacharo"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Busca la lista de horarios con animales
    horarios = ['8:00 am', '9:00 am', '10:00 am', '11:00 am', '12:00 pm',
                '1:00 pm', '2:00 pm', '3:00 pm', '4:00 pm', '5:00 pm',
                '6:00 pm', '7:00 pm']
    
    resultados = []
    for hora in horarios:
        # Buscar el texto de la hora
        for elem in soup.find_all(text=lambda t: t and hora.lower() in t.lower()):
            parent = elem.parent
            # El animal suele estar en un heading o div cercano
            siguiente = parent.find_next(['h3', 'h4', 'div', 'span'])
            if siguiente:
                animal = siguiente.get_text(strip=True)
                if animal and len(animal) < 30 and not any(d in animal for d in '0123456789'):
                    # Buscar número en el texto completo del contenedor
                    contenedor = parent.find_parent(['div', 'li'])
                    num = "00"
                    if contenedor:
                        texto_cont = contenedor.get_text()
                        import re
                        m = re.search(r'\b(\d{1,2})\b', texto_cont)
                        if m:
                            num = m.group(1)
                    resultados.append({
                        "hora": hora.upper().replace(' ', ' '),
                        "numero": num,
                        "animal": animal.capitalize(),
                        "raw": f"{num} {animal.capitalize()}"
                    })
                    break
    
    if resultados:
        return resultados[-1]
    return None

def obtener_resultado_guacharito() -> Optional[Dict]:
    """Intenta múltiples fuentes hasta conseguir el resultado."""
    parsers = [
        ("LoteriaDeHoy", FUENTES_GUACHARITO[0]["url"], lambda h: parsear_loteriadehoy(h, "El Guacharito Millonario")),
        ("Parley", FUENTES_GUACHARITO[1]["url"], parsear_parley_guacharito),
        ("LottoVen", FUENTES_GUACHARITO[2]["url"], parsear_lottoven_guacharito),
    ]
    
    for nombre, url, parser in parsers:
        logger.info(f"🔍 Guacharito - Probando fuente: {nombre}")
        html = fetch_html(url)
        if html:
            try:
                resultado = parser(html)
                if resultado:
                    logger.info(f"✅ Guacharito - Éxito en {nombre}: {resultado['raw']}")
                    return resultado
            except Exception as e:
                logger.warning(f"⚠️ Error parseando {nombre}: {e}")
        else:
            logger.warning(f"❌ Guacharito - No se pudo obtener HTML de {nombre}")
    
    logger.error("❌ Guacharito - TODAS las fuentes fallaron")
    return None

def obtener_resultado_guacharo_activo() -> Optional[Dict]:
    """Intenta múltiples fuentes hasta conseguir el resultado."""
    parsers = [
        ("LoteriaDeHoy", FUENTES_GUACHARO_ACTIVO[0]["url"], lambda h: parsear_loteriadehoy(h, "Guacharo Activo")),
        ("Parley", FUENTES_GUACHARO_ACTIVO[1]["url"], parsear_parley_guacharoactivo),
        ("CentroApuestas", FUENTES_GUACHARO_ACTIVO[2]["url"], parsear_centroapuestas_guacharo),
    ]
    
    for nombre, url, parser in parsers:
        logger.info(f"🔍 Guácharo Activo - Probando fuente: {nombre}")
        html = fetch_html(url)
        if html:
            try:
                resultado = parser(html)
                if resultado:
                    logger.info(f"✅ Guácharo Activo - Éxito en {nombre}: {resultado['raw']}")
                    return resultado
            except Exception as e:
                logger.warning(f"⚠️ Error parseando {nombre}: {e}")
        else:
            logger.warning(f"❌ Guácharo Activo - No se pudo obtener HTML de {nombre}")
    
    logger.error("❌ Guácharo Activo - TODAS las fuentes fallaron")
    return None

# ==============================================================================
# TELEGRAM (Con reintentos y manejo de errores)
# ==============================================================================

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

def enviar_telegram(mensaje: str, max_reintentos: int = 3) -> bool:
    """Envía mensaje a Telegram con reintentos."""
    for intento in range(max_reintentos):
        try:
            bot.send_message(chat_id=CANAL_ID, text=mensaje, parse_mode="Markdown")
            logger.info("✅ Mensaje enviado a Telegram")
            return True
        except ApiTelegramException as e:
            logger.error(f"❌ Telegram API error: {e}")
            if e.error_code == 429:  # Rate limit
                time.sleep(5)
            else:
                time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Error enviando a Telegram: {e}")
            time.sleep(2 ** intento)
    return False

# ==============================================================================
# MOTOR DE MONITOREO (Thread-safe y robusto)
# ==============================================================================

def revisar_y_publicar():
    """Función principal de monitoreo."""
    logger.info("⏰ Iniciando ciclo de monitoreo...")
    
    # --- GUACHARITO MILLONARIO ---
    res_g = obtener_resultado_guacharito()
    if res_g:
        fingerprint = f"{res_g['hora']}|{res_g['numero']}|{res_g['animal']}"
        if store.es_nuevo("guacharito", fingerprint):
            mensaje = (
                f"🔔 *RESULTADO RECIENTE* 🔔\n\n"
                f"🎰 *Guacharito Millonario* ({res_g['hora']}):\n"
                f"`{res_g['raw']}`\n\n"
                f"🍀 *@resultadoslafija* 🍀"
            )
            enviar_telegram(mensaje)
        else:
            logger.info("⏭️ Guacharito - Sin cambios")
    else:
        logger.warning("⚠️ Guacharito - No se pudo obtener resultado")
    
    # --- GUÁCHARO ACTIVO ---
    res_s = obtener_resultado_guacharo_activo()
    if res_s:
        fingerprint = f"{res_s['hora']}|{res_s['numero']}|{res_s['animal']}"
        if store.es_nuevo("guacharo_activo", fingerprint):
            mensaje = (
                f"🔔 *RESULTADO RECIENTE* 🔔\n\n"
                f"🎰 *Guácharo Activo* ({res_s['hora']}):\n"
                f"`{res_s['raw']}`\n\n"
                f"🍀 *@resultadoslafija* 🍀"
            )
            enviar_telegram(mensaje)
        else:
            logger.info("⏭️ Guácharo Activo - Sin cambios")
    else:
        logger.warning("⚠️ Guácharo Activo - No se pudo obtener resultado")

# ==============================================================================
# SERVIDOR HTTP PARA RENDER (NO usar daemon=True)
# ==============================================================================

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK - Bot activo")
    
    def log_message(self, format, *args):
        # Silenciar logs del servidor HTTP para no contaminar
        pass

def iniciar_servidor():
    puerto = int(os.environ.get("PORT", 8080))
    with socketserver.TCPServer(("", puerto), HealthHandler) as httpd:
        logger.info(f"📡 Servidor HTTP escuchando en puerto {puerto}")
        httpd.serve_forever()

# ==============================================================================
# BUCLE PRINCIPAL (Thread separado, NO bloqueante)
# ==============================================================================

def bucle_monitoreo():
    """Bucle de monitoreo en thread separado."""
    logger.info("🤖 Bot iniciado - Monitoreo activo")
    
    # Primera ejecución inmediata
    revisar_y_publicar()
    
    # Ciclo cada 90 segundos (más rápido que 2 minutos para resultados en vivo)
    while True:
        time.sleep(90)
        try:
            revisar_y_publicar()
        except Exception as e:
            logger.critical(f"💥 Error crítico en bucle: {e}")
            time.sleep(10)

# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    # 1. Iniciar servidor HTTP en thread separado (NO daemon)
    servidor_thread = threading.Thread(target=iniciar_servidor, name="ServidorHTTP")
    servidor_thread.daemon = False  # CRÍTICO: Render necesita que el proceso principal siga vivo
    servidor_thread.start()
    
    # 2. Iniciar monitoreo en thread principal (o secundario)
    # Para Render, el monitoreo debe correr en el hilo principal o en uno no-daemon
    bucle_monitoreo()
